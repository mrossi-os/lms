# Copyright (c) 2026, ELITE and contributors
# For license information, please see license.txt

"""Color math for Brand Customize Base and Advanced modes.

Everything is done in OKLCH (Björn Ottosson's OKLab in polar form), the space
frappe-ui v2 writes its tokens in: equal lightness steps look equal, so a
token's stock lightness can be kept while its hue and chroma come from a brand
color. Results are always sRGB hex, the only format Base and Advanced accept
(docs/brand-customize/fase-3-analisi.md, decision C1).
"""

from __future__ import annotations

import math
import re

HEX_RE = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")
OKLCH_RE = re.compile(r"^oklch\(\s*([\d.]+)(%?)\s+([\d.]+)\s+([\d.]+)(?:deg)?\s*(?:/\s*[\d.%]+\s*)?\)$")

WHITE = "#ffffff"
# frappe-ui's darkest neutral ink (--ink-gray-9), used for text on light colors.
NEAR_BLACK = "#171717"

Oklch = tuple[float, float, float]


def is_hex(value) -> bool:
	return isinstance(value, str) and bool(HEX_RE.match(value.strip()))


def _hex_to_rgb(value: str) -> tuple[float, float, float]:
	digits = value.strip().lstrip("#")
	if len(digits) == 3:
		digits = "".join(d * 2 for d in digits)
	return tuple(int(digits[i : i + 2], 16) / 255 for i in (0, 2, 4))


def _rgb_to_hex(rgb) -> str:
	return "#" + "".join(f"{round(min(1.0, max(0.0, c)) * 255):02x}" for c in rgb)


def _to_linear(c: float) -> float:
	return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _from_linear(c: float) -> float:
	return 12.92 * c if c <= 0.0031308 else 1.055 * (c ** (1 / 2.4)) - 0.055


def _rgb_to_oklab(rgb) -> tuple[float, float, float]:
	r, g, b = (_to_linear(c) for c in rgb)
	l = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b
	m = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b
	s = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b
	l, m, s = (math.copysign(abs(x) ** (1 / 3), x) for x in (l, m, s))
	return (
		0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s,
		1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s,
		0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s,
	)


def _oklab_to_linear_rgb(lab) -> tuple[float, float, float]:
	L, a, b = lab
	l = (L + 0.3963377774 * a + 0.2158037573 * b) ** 3
	m = (L - 0.1055613458 * a - 0.0638541728 * b) ** 3
	s = (L - 0.0894841775 * a - 1.2914855480 * b) ** 3
	return (
		4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
		-1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
		-0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s,
	)


def to_oklch(value: str) -> Oklch:
	"""OKLCH of a hex color (hue in degrees, 0 for grays)."""
	L, a, b = _rgb_to_oklab(_hex_to_rgb(value))
	C = math.hypot(a, b)
	H = math.degrees(math.atan2(b, a)) % 360 if C > 1e-4 else 0.0
	return (L, C, H)


def parse_oklch(value) -> Oklch | None:
	"""OKLCH of a stock token value (``oklch(...)`` or hex), None if unknown."""
	if not isinstance(value, str):
		return None
	value = value.strip()
	if is_hex(value):
		return to_oklch(value)
	match = OKLCH_RE.match(value)
	if not match:
		return None
	L = float(match.group(1)) / (100 if match.group(2) else 1)
	return (L, float(match.group(3)), float(match.group(4)))


def _in_gamut(rgb, eps: float = 1e-6) -> bool:
	return all(-eps <= c <= 1 + eps for c in rgb)


def from_oklch(L: float, C: float, H: float) -> str:
	"""Hex of an OKLCH color, reducing chroma until it fits sRGB."""
	L = min(1.0, max(0.0, L))
	C = max(0.0, C)

	def linear(chroma: float):
		h = math.radians(H)
		return _oklab_to_linear_rgb((L, chroma * math.cos(h), chroma * math.sin(h)))

	rgb = linear(C)
	if not _in_gamut(rgb):
		low, high = 0.0, C
		for _ in range(24):
			mid = (low + high) / 2
			if _in_gamut(linear(mid)):
				low = mid
			else:
				high = mid
		rgb = linear(low)
	return _rgb_to_hex(_from_linear(c) for c in rgb)


def with_lightness(value: str, L: float) -> str:
	_, C, H = to_oklch(value)
	return from_oklch(L, C, H)


def shift_lightness(value: str, delta: float) -> str:
	L, C, H = to_oklch(value)
	return from_oklch(L + delta, C, H)


def rotate_hue(value: str, degrees: float) -> str:
	L, C, H = to_oklch(value)
	return from_oklch(L, C, (H + degrees) % 360)


def mix(value: str, other: str, amount: float) -> str:
	"""``amount`` of ``other`` mixed into ``value``, in OKLab (0 = value, 1 = other)."""
	a = _rgb_to_oklab(_hex_to_rgb(value))
	b = _rgb_to_oklab(_hex_to_rgb(other))
	lab = tuple(x + (y - x) * amount for x, y in zip(a, b))
	rgb = _oklab_to_linear_rgb(lab)
	return _rgb_to_hex(_from_linear(c) for c in rgb)


def relative_luminance(value: str) -> float:
	r, g, b = (_to_linear(c) for c in _hex_to_rgb(value))
	return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(one: str, two: str) -> float:
	"""WCAG 2 contrast ratio, from 1 to 21."""
	high, low = sorted((relative_luminance(one), relative_luminance(two)), reverse=True)
	return (high + 0.05) / (low + 0.05)


def readable_ink(background: str) -> str:
	"""White or near-black, whichever reads better on ``background``."""
	if contrast_ratio(background, WHITE) >= contrast_ratio(background, NEAR_BLACK):
		return WHITE
	return NEAR_BLACK


def ensure_contrast(value: str, background: str, minimum: float = 4.5) -> str:
	"""``value`` darkened (or lightened, on a dark background) until it reaches ``minimum``."""
	if contrast_ratio(value, background) >= minimum:
		return value
	L, C, H = to_oklch(value)
	step = -0.02 if relative_luminance(background) > 0.18 else 0.02
	candidate = value
	for _ in range(50):
		L += step
		if not 0 <= L <= 1:
			break
		candidate = from_oklch(L, C, H)
		if contrast_ratio(candidate, background) >= minimum:
			return candidate
	return candidate

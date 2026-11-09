# Copyright (c) 2026, ELITE and contributors
# For license information, please see license.txt

"""Every CSS variable the Expert mode of Brand Customize can set.

The list is read from the SPA build that is installed, so it follows frappe-ui
updates by itself (docs/brand-customize/fase-4-analisi.md, decision E1):

- the variables frappe-ui declares for the light theme (plain ``:root``);
- the video player's ``--plyr-*`` variables, which are never declared: Plyr
  reads them with a fallback (``var(--plyr-color-main, ...)``), the stock value;
- the variables only os_lms reads (EXTRA_TOKENS).

A variable "has an effect" when some rule or component reads it: about two
thirds of frappe-ui's (the primitive scales such as ``--blue-500``, unused
palettes) are read by nothing and are hidden by default in the editor.
"""

from __future__ import annotations

import os
import re

import frappe

# A name is written verbatim into the stylesheet served to everyone.
TOKEN_NAME_RE = re.compile(r"^--[a-z0-9][a-z0-9-]*$")

ROOT_BLOCK_RE = re.compile(r"(?:^|[{};])\s*:root\s*\{([^}]*)\}")
DECLARATION_RE = re.compile(r"(--[\w-]+)\s*:\s*([^;}]+)")
VAR_REFERENCE_RE = re.compile(r"var\(\s*(--[\w-]+)")
FALLBACK_START_RE = re.compile(r"var\(\s*(--[\w-]+)\s*,")

FALLBACK_PREFIXES = ("--plyr-",)

# Read by os_lms only (theme/elite/main.css, the chart overrides): frappe-ui does
# not declare them, so their stock value is the fallback where they are read.
EXTRA_TOKENS = {
	"--ink-gray-10": "",
	"--color-company-primary": "transparent",
	"--os-table-header-bg": "var(--surface-gray-2)",
	**{f"--os-chart-{n}": "" for n in range(1, 6)},
}

KIND_COLOR = "color"
KIND_LENGTH = "length"
KIND_SHADOW = "shadow"
KIND_OTHER = "other"

COLOR_VALUE_RE = re.compile(
	r"^(#[0-9a-f]{3,8}|(rgba?|hsla?|oklch|oklab|lab|lch|hwb|color|color-mix)\(.*\)"
	r"|transparent|white|black|currentcolor)$",
	re.IGNORECASE,
)
LENGTH_VALUE_RE = re.compile(r"^(-?[\d.]+(px|rem|em|%|vh|vw|ch)?|calc\(.*\))$", re.IGNORECASE)
HAS_COLOR_RE = re.compile(r"#[0-9a-f]{3,8}\b|(rgba?|hsla?|oklch|oklab)\(", re.IGNORECASE)

PALETTES = (
	"gray",
	"red",
	"green",
	"blue",
	"amber",
	"orange",
	"yellow",
	"teal",
	"cyan",
	"violet",
	"purple",
	"pink",
)
FAMILY_ORDER = (
	"surface",
	"ink",
	"outline",
	"palette",
	"radius",
	"elevation",
	"focus",
	"plyr",
	"os_lms",
	"other",
)


def value_kind(value: str) -> str:
	value = (value or "").strip()
	if re.match(r"^(repeating-)?(linear|radial|conic)-gradient\(", value, re.IGNORECASE):
		return KIND_OTHER
	if COLOR_VALUE_RE.match(value):
		return KIND_COLOR
	if LENGTH_VALUE_RE.match(value):
		return KIND_LENGTH
	if HAS_COLOR_RE.search(value):
		return KIND_SHADOW
	return KIND_OTHER


# Kind of a variable without a stock value, from its name (Plyr's optional ones).
NAME_KIND_HINTS = (
	(("color", "background", "-bg", "-ink", "-chart-"), "color"),
	(("radius", "size", "spacing", "height", "width", "gap"), "length"),
	(("shadow",), "shadow"),
)
INNER_FALLBACK_RE = re.compile(r"^var\(\s*--[\w-]+\s*,\s*(.*)\)$", re.DOTALL)


def fallbacks_in(sources: str, prefixes: tuple[str, ...]) -> list[tuple[str, str]]:
	"""(name, fallback) of every ``var(--name, fallback)`` whose name has one of
	``prefixes``; the fallback is read up to its balancing parenthesis, so nested
	``var()`` and color functions stay whole."""
	found = []
	for match in FALLBACK_START_RE.finditer(sources):
		name = match.group(1)
		if not name.startswith(prefixes):
			continue
		depth, start = 1, match.end()
		for i in range(start, min(len(sources), start + 500)):
			char = sources[i]
			if char == "(":
				depth += 1
			elif char == ")":
				depth -= 1
				if depth == 0:
					found.append((name, sources[start:i].strip()))
					break
	return found


def innermost_fallback(value: str) -> str:
	"""``var(--a, var(--b, #00b2ff))`` -> ``#00b2ff``: the value actually used."""
	value = (value or "").strip()
	while match := INNER_FALLBACK_RE.match(value):
		value = match.group(1).strip()
	return value


def kind_from_name(name: str) -> str:
	for hints, kind in NAME_KIND_HINTS:
		if any(hint in name for hint in hints):
			return kind
	return KIND_OTHER


def token_family(name: str) -> str:
	if name in EXTRA_TOKENS:
		return "os_lms"
	head = name[2:].split("-", 1)[0]
	if head in ("surface", "ink", "outline", "radius", "elevation", "focus", "plyr"):
		return head
	if head in PALETTES:
		return "palette"
	return "other"


def _assets_dir() -> str:
	return frappe.get_app_path("lms", "public", "frontend", "assets")


def _read(path: str) -> str:
	try:
		with open(path, encoding="utf-8", errors="ignore") as f:
			return f.read()
	except OSError:
		return ""


def parse(stylesheet: str, sources: str) -> list[dict]:
	"""Variables of the SPA build.

	``stylesheet`` is the main compiled CSS (it holds frappe-ui's tokens and
	Plyr's rules); ``sources`` is every compiled CSS and JS file, searched for
	the variables something reads.
	"""
	declared: dict[str, str] = {}
	for block in ROOT_BLOCK_RE.findall(stylesheet):
		for name, value in DECLARATION_RE.findall(block):
			if not name.startswith("--tw-"):
				declared.setdefault(name, value.strip())

	fallbacks: dict[str, str] = {}
	for name, fallback in fallbacks_in(sources, FALLBACK_PREFIXES):
		if not fallbacks.get(name):
			fallbacks[name] = innermost_fallback(fallback)
	for name in set(VAR_REFERENCE_RE.findall(sources)):
		if name.startswith(FALLBACK_PREFIXES):
			fallbacks.setdefault(name, "")

	read = set(VAR_REFERENCE_RE.findall(sources))
	tokens = {**fallbacks, **EXTRA_TOKENS, **declared}
	rows = []
	for name, default in tokens.items():
		if not TOKEN_NAME_RE.match(name):
			continue
		# A default that is another variable takes that variable's kind; one
		# without a default (optional Plyr settings) is guessed from the name.
		kind = value_kind(default)
		if kind == KIND_OTHER and default.startswith("var("):
			ref = VAR_REFERENCE_RE.match(default)
			kind = value_kind(innermost_fallback(tokens.get(ref.group(1), ""))) if ref else kind
		if kind == KIND_OTHER and not default:
			kind = kind_from_name(name)
		rows.append(
			{
				"name": name,
				"default": default,
				"kind": kind,
				"family": token_family(name),
				"used": name in read or name in EXTRA_TOKENS,
			}
		)
	order = {family: i for i, family in enumerate(FAMILY_ORDER)}
	# Neutral variables (base, grays, elevation) before the colored palettes.
	tinted = tuple(f"-{palette}-" for palette in PALETTES if palette != "gray")
	rows.sort(
		key=lambda row: (
			order[row["family"]],
			not row["used"],
			any(t in row["name"] + "-" for t in tinted),
			row["name"],
		)
	)
	return rows


CACHE_PREFIX = "brand_customize_expert_tokens:"


def _main_stylesheet() -> str | None:
	# Imported here: branding imports this module.
	from os_lms.os_lms.branding import _spa_stylesheet_path

	return _spa_stylesheet_path()


def manifest() -> list[dict]:
	"""Variables of the installed build; empty when there is no SPA build."""
	path = _main_stylesheet()
	if not path:
		return []

	def build() -> list[dict]:
		directory = _assets_dir()
		try:
			names = sorted(os.listdir(directory))
		except OSError:
			names = []
		sources = "".join(
			_read(os.path.join(directory, name)) for name in names if name.endswith((".css", ".js"))
		)
		return parse(_read(path), sources)

	return frappe.cache().get_value(CACHE_PREFIX + path, generator=build)


def by_name() -> dict[str, dict]:
	return {row["name"]: row for row in manifest()}

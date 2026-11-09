# Copyright (c) 2026, ELITE and contributors
# For license information, please see license.txt

"""Readability of the brand colors (docs/brand-customize/fase-5-analisi.md).

Measures the WCAG 2 contrast of the text/background pairs that are really on
screen, with the colors the active mode produces (a filled field, a color
computed by Base, or the stock value when empty).

frappe-ui's own palette is not all AA: its secondary text is 4.17:1 on white,
its links 3.37:1. A pair is therefore "low" only when it is under the WCAG
minimum *and* worse than the same pair with the stock colors (decision G1);
under the minimum but as good as stock is reported as "stock", a note.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import frappe

from os_lms.os_lms import branding_color as color
from os_lms.os_lms import branding_roles

TEXT = 4.5  # WCAG 1.4.3, normal text
NON_TEXT = 3.0  # WCAG 1.4.11, controls, and placeholders (decision G2)
# The stock comparison ignores rounding noise (a tint at the stock lightness).
STOCK_TOLERANCE = 0.05

LEVEL_OK = "ok"
LEVEL_STOCK = "stock"
LEVEL_LOW = "low"

CONTEXT = "Brand Customize"

# Areas inside another area read the outer area's tokens when they do not set
# their own (CSS custom properties are inherited).
PARENT_SCOPES = {"sidebar_icon": "sidebar", "sidebar_active": "sidebar"}


@dataclass(frozen=True)
class Pair:
	key: str
	label: str
	fg: tuple[str, str | None]  # (token, scope)
	bg: tuple[str, str | None]
	minimum: float
	# Fields of the form behind the pair: Advanced role fields (text, background)
	# and the Base color that drives it.
	adv: tuple[str, str]
	base: str


PAIRS: tuple[Pair, ...] = (
	# Page and cards
	Pair("page_heading", "Headings on the page", ("--ink-gray-9", None), ("--surface-base", None), TEXT, ("adv_heading_ink", "adv_page_bg"), "base_background"),
	Pair("page_text", "Text on the page", ("--ink-gray-7", None), ("--surface-base", None), TEXT, ("adv_text_ink", "adv_page_bg"), "base_background"),
	Pair("page_muted", "Secondary text on the page", ("--ink-gray-5", None), ("--surface-base", None), TEXT, ("adv_muted_ink", "adv_page_bg"), "base_background"),
	Pair("page_link", "Links on the page", ("--ink-blue-link", None), ("--surface-base", None), TEXT, ("adv_link_ink", "adv_page_bg"), "base_primary"),
	Pair("card_heading", "Headings on cards", ("--ink-gray-9", None), ("--surface-elevation-1", None), TEXT, ("adv_heading_ink", "adv_card_bg"), "base_background"),
	Pair("card_text", "Text on cards", ("--ink-gray-7", None), ("--surface-elevation-1", None), TEXT, ("adv_text_ink", "adv_card_bg"), "base_background"),
	Pair("card_muted", "Secondary text on cards", ("--ink-gray-5", None), ("--surface-elevation-1", None), TEXT, ("adv_muted_ink", "adv_card_bg"), "base_background"),
	Pair("card_link", "Links on cards", ("--ink-blue-link", None), ("--surface-elevation-1", None), TEXT, ("adv_link_ink", "adv_card_bg"), "base_primary"),
	# Fields and menus
	Pair("input_text", "Text in fields", ("--ink-gray-8", "inputs"), ("--surface-gray-2", "inputs"), TEXT, ("adv_text_ink", "adv_input_bg"), "base_gray_tint"),
	Pair("input_placeholder", "Placeholder in fields", ("--ink-gray-4", "inputs"), ("--surface-gray-2", "inputs"), NON_TEXT, ("adv_placeholder_ink", "adv_input_bg"), "base_gray_tint"),
	Pair("menu_text", "Text in menus and dialogs", ("--ink-gray-7", "menus"), ("--surface-elevation-1", "menus"), TEXT, ("adv_text_ink", "adv_menu_bg"), "base_background"),
	# Sidebar
	Pair("sidebar_text", "Sidebar text", ("--ink-gray-8", "sidebar"), ("--surface-sidebar", "sidebar"), TEXT, ("adv_sidebar_ink", "adv_sidebar_bg"), "base_background"),
	Pair("sidebar_muted", "Sidebar secondary text", ("--ink-gray-5", "sidebar"), ("--surface-sidebar", "sidebar"), TEXT, ("adv_sidebar_ink", "adv_sidebar_bg"), "base_background"),
	Pair("sidebar_active", "Active sidebar item", ("--ink-gray-8", "sidebar_active"), ("--surface-elevation-3", "sidebar_active"), TEXT, ("adv_sidebar_active_ink", "adv_sidebar_active_bg"), "base_primary"),
	# Buttons
	Pair("button_text", "Primary button text", ("--ink-base", "button_primary"), ("--surface-gray-10", "button_primary"), TEXT, ("adv_button_ink", "adv_button_bg"), "base_primary"),
	Pair("secondary_text", "Secondary button text", ("--ink-gray-8", "button_secondary"), ("--surface-gray-2", "button_secondary"), TEXT, ("adv_secondary_ink", "adv_secondary_bg"), "base_accent"),
	# Controls against the page (not text)
	Pair("button_shape", "Primary button against the page", ("--surface-gray-10", "button_primary"), ("--surface-base", None), NON_TEXT, ("adv_button_bg", "adv_page_bg"), "base_primary"),
	Pair("secondary_shape", "Secondary button against the page", ("--surface-gray-2", "button_secondary"), ("--surface-base", None), NON_TEXT, ("adv_secondary_bg", "adv_page_bg"), "base_accent"),
	Pair("focus_ring", "Focus ring against the page", ("--outline-gray-3", "focus"), ("--surface-base", None), NON_TEXT, ("adv_focus_ring", "adv_page_bg"), "base_primary"),
)

# The login page reads its own variables, with Frappe's colors as fallback
# (public/css/os_lms.css), in every mode.
LOGIN_STOCK = {
	"login_bg_from": "#f4f5f6",
	"login_bg_to": "#f4f5f6",
	"login_ink": "#383838",
	"login_input_bg": "#f4f5f6",
	"login_input_ink": "#383838",
}
LOGIN_PAIRS = (
	("login_text_from", "Login text on the background (start)", "login_ink", "login_bg_from"),
	("login_text_to", "Login text on the background (end)", "login_ink", "login_bg_to"),
	("login_input", "Login field text", "login_input_ink", "login_input_bg"),
)

RGB_RE = re.compile(r"^rgba?\(\s*(\d{1,3})[\s,]+(\d{1,3})[\s,]+(\d{1,3})\s*(?:[,/]\s*([\d.]+%?)\s*)?\)$", re.I)
NAMED = {"white": "#ffffff", "black": "#000000"}


def to_hex(value) -> str | None:
	"""Opaque sRGB hex of a CSS color, None when it cannot be measured
	(``var()``, gradients, transparency, names other than white/black)."""
	if not isinstance(value, str):
		return None
	value = value.strip().lower()
	if value in NAMED:
		return NAMED[value]
	if color.is_hex(value):
		return color.from_oklch(*color.to_oklch(value))
	match = RGB_RE.match(value)
	if match:
		alpha = match.group(4)
		if alpha and alpha not in ("1", "100%"):
			return None
		channels = [int(match.group(i)) for i in (1, 2, 3)]
		if max(channels) > 255:
			return None
		return "#" + "".join(f"{c:02x}" for c in channels)
	oklch = color.parse_oklch(value)
	return color.from_oklch(*oklch) if oklch else None


def _lookup(palette: dict, token: str, scope: str | None) -> str | None:
	while scope:
		if token in palette.get(scope, {}):
			return palette[scope][token]
		scope = PARENT_SCOPES.get(scope)
	return palette[None].get(token)


def _stock_palette(stock: dict) -> dict:
	return {None: {name: color.from_oklch(*oklch) for name, oklch in stock.items()}}


def _merge(palette: dict, stock_palette: dict) -> dict:
	"""``palette`` over the stock values: a token the mode leaves alone keeps stock."""
	merged = {scope: dict(declarations) for scope, declarations in palette.items()}
	merged[None] = {**stock_palette[None], **merged.get(None, {})}
	return merged


def palette(values, mode: str, stock: dict) -> dict:
	"""Effective hex value of the tokens, per area (None = everywhere)."""
	from os_lms.os_lms import branding  # branding imports this module

	if mode == branding.MODE_EXPERT:
		declared = {None: {}}
		themed, _ = branding._expert_declarations(values)
		for name, value in themed.items():
			hex_value = to_hex(value)
			if hex_value:
				declared[None][name] = hex_value
	else:
		declared = branding_roles.blocks(branding.mode_roles(values, mode, stock), stock)
	return _merge(declared, _stock_palette(stock))


def _level(ratio: float, minimum: float, stock_ratio: float | None) -> str:
	if ratio >= minimum:
		return LEVEL_OK
	if stock_ratio is not None and ratio >= stock_ratio - STOCK_TOLERANCE:
		return LEVEL_STOCK
	return LEVEL_LOW


def _entry(key, label, fg, bg, minimum, stock_ratio, fields) -> dict:
	ratio = color.contrast_ratio(fg, bg)
	return {
		"key": key,
		"label": frappe._(label, context=CONTEXT),
		"fg": fg,
		"bg": bg,
		"ratio": round(ratio, 2),
		"minimum": minimum,
		"stock": round(stock_ratio, 2) if stock_ratio is not None else None,
		"level": _level(ratio, minimum, stock_ratio),
		"fields": fields,
	}


def report(values, mode: str, stock: dict) -> list[dict]:
	"""One entry per measurable pair of the active mode, plus the login ones.

	``fields`` names what the form can point at: ``advanced`` role fields,
	the ``base`` color behind the pair, the ``expert`` variables and, for the
	login, the login fields.
	"""
	if not stock:
		return []
	current = palette(values, mode, stock)
	original = _stock_palette(stock)
	entries = []
	for pair in PAIRS:
		fg, bg = _lookup(current, *pair.fg), _lookup(current, *pair.bg)
		if not fg or not bg:
			continue
		stock_fg, stock_bg = _lookup(original, pair.fg[0], None), _lookup(original, pair.bg[0], None)
		stock_ratio = color.contrast_ratio(stock_fg, stock_bg) if stock_fg and stock_bg else None
		fields = {"advanced": list(pair.adv), "base": [pair.base], "expert": [pair.fg[0], pair.bg[0]]}
		entries.append(_entry(pair.key, pair.label, fg, bg, pair.minimum, stock_ratio, fields))

	for key, label, ink_field, bg_field in LOGIN_PAIRS:
		fg = to_hex(values.get(ink_field)) if (values.get(ink_field) or "").strip() else LOGIN_STOCK[ink_field]
		bg = to_hex(values.get(bg_field)) if (values.get(bg_field) or "").strip() else LOGIN_STOCK[bg_field]
		if key == "login_text_to" and not (values.get(bg_field) or "").strip():
			# The gradient end falls back to its start (os_lms.css).
			start = values.get("login_bg_from")
			bg = to_hex(start) if (start or "").strip() else bg
		if not fg or not bg:
			continue
		stock_ratio = color.contrast_ratio(LOGIN_STOCK[ink_field], LOGIN_STOCK[bg_field])
		entries.append(_entry(key, label, fg, bg, TEXT, stock_ratio, {"login": [ink_field, bg_field]}))
	return entries


def low(entries: list[dict]) -> list[dict]:
	return [entry for entry in entries if entry["level"] == LEVEL_LOW]

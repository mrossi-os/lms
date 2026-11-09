# Copyright (c) 2026, ELITE and contributors
# For license information, please see license.txt

"""Brand Customize Base and Advanced modes: roles and their derivations.

docs/brand-customize/fase-3-analisi.md. A role is a named area of the platform
("primary button background", "sidebar text"). It writes one or more frappe-ui
tokens, either everywhere (``scope=None``, the token has a single meaning) or
only inside an anchor that already exists in the markup, since a custom
property redefined on an element applies to it and its children only.

Base derives role values from 4 colors; Advanced lets each role be filled in.
Both end up in the same CSS, built here with concrete hex values (no var()
chains, so no self-referencing cycles). This module is the single list of
roles: the stylesheet, the Desk preview highlight and the tests all read it.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from os_lms.os_lms import branding_color as color

# Anchors: selectors that already exist in the SPA (frappe-ui Button.vue,
# AppSidebar.vue, SidebarLink.vue). frontend/src/tests/brandAnchors.test.ts fails
# when an upstream change removes one.
SCOPES: dict[str, tuple[str, ...]] = {
	"sidebar": (".bg-surface-sidebar",),
	"sidebar_icon": (".bg-surface-sidebar svg",),
	"sidebar_active": (
		".bg-surface-sidebar .bg-surface-elevation-3",
		".bg-surface-sidebar .bg-surface-elevation-3 svg",
	),
	"menus": ("[role=dialog]", "[role=menu]", "[role=listbox]"),
	"inputs": ('input:not([type="checkbox"]):not([type="radio"])', "textarea", "select"),
	"button_primary": ("button.bg-surface-gray-10", "a.bg-surface-gray-10"),
	"button_secondary": ("button.bg-surface-gray-2", "a.bg-surface-gray-2"),
	"button_outline": ("button.border-outline-gray-2", "a.border-outline-gray-2"),
	"focus": (":focus-visible",),
}
# Areas inside another area: their tokens are already owned by the outer one.
NESTED_SCOPES = {"sidebar_icon", "sidebar_active"}

Stock = dict[str, color.Oklch]
Values = dict[str, str]


@dataclass(frozen=True)
class Role:
	fieldname: str
	# Tokens written by the role; the first one takes the chosen color, the
	# others keep their stock lightness offset from it (so a two-step text
	# role stays two steps apart).
	tokens: tuple[str, ...] = ()
	scope: str | None = None
	# Status roles recolor a whole frappe-ui color family (green, red...).
	family: str | None = None
	# Value used when the field is empty, computed from the other roles.
	derive: Callable[[Values], str | None] | None = None


def _hover(base: str) -> str:
	return color.shift_lightness(base, 0.07 if color.to_oklch(base)[0] < 0.6 else -0.07)


def _pressed(base: str) -> str:
	return color.shift_lightness(base, 0.13 if color.to_oklch(base)[0] < 0.6 else -0.13)


def _from(fieldname: str, fn: Callable[[str], str]) -> Callable[[Values], str | None]:
	def derive(values: Values) -> str | None:
		source = values.get(fieldname)
		return fn(source) if source else None

	return derive


ROLES: tuple[Role, ...] = (
	# Structure
	Role("adv_page_bg", ("--surface-base",)),
	Role("adv_sidebar_bg", ("--surface-sidebar",)),
	Role(
		"adv_sidebar_ink",
		("--ink-gray-8", "--ink-gray-9", "--ink-gray-7", "--ink-gray-6", "--ink-gray-5"),
		"sidebar",
	),
	Role("adv_sidebar_hover", ("--surface-gray-2",), "sidebar"),
	Role("adv_sidebar_icon", ("--ink-gray-8", "--ink-gray-7"), "sidebar_icon"),
	Role("adv_sidebar_active_bg", ("--surface-elevation-3",), "sidebar_active"),
	Role("adv_sidebar_active_ink", ("--ink-gray-8",), "sidebar_active"),
	# Text
	Role("adv_heading_ink", ("--ink-gray-9",)),
	Role("adv_text_ink", ("--ink-gray-7", "--ink-gray-8")),
	Role("adv_muted_ink", ("--ink-gray-5", "--ink-gray-6")),
	Role("adv_placeholder_ink", ("--ink-gray-4", "--ink-gray-3")),
	Role("adv_link_ink", ("--ink-blue-link",)),
	# Surfaces (global first: the scoped ones below override them in their area)
	Role("adv_subtle_bg", ("--surface-gray-2", "--surface-gray-1", "--surface-gray-3", "--surface-gray-4")),
	Role("adv_card_bg", ("--surface-elevation-1",)),
	Role("adv_menu_bg", ("--surface-elevation-1", "--surface-elevation-2"), "menus"),
	Role("adv_input_bg", ("--surface-gray-2", "--surface-gray-3", "--surface-base"), "inputs"),
	Role("adv_table_header_bg", ("--os-table-header-bg",)),
	Role("adv_table_row_bg", ("--color-company-primary",)),
	# Borders
	Role("adv_border_light", ("--outline-gray-1", "--outline-elevation-1", "--outline-elevation-2")),
	Role("adv_border", ("--outline-gray-2",)),
	Role("adv_border_strong", ("--outline-gray-3", "--outline-gray-4")),
	Role("adv_focus_ring", ("--outline-gray-3",), "focus"),
	# Buttons
	Role("adv_button_bg", ("--surface-gray-10",), "button_primary"),
	Role(
		"adv_button_ink",
		("--ink-base",),
		"button_primary",
		derive=_from("adv_button_bg", color.readable_ink),
	),
	Role("adv_button_hover", ("--surface-gray-9",), "button_primary", derive=_from("adv_button_bg", _hover)),
	Role(
		"adv_button_pressed", ("--surface-gray-8",), "button_primary", derive=_from("adv_button_bg", _pressed)
	),
	Role("adv_secondary_bg", ("--surface-gray-2", "--surface-gray-3", "--surface-gray-4"), "button_secondary"),
	Role("adv_secondary_ink", ("--ink-gray-8",), "button_secondary"),
	Role("adv_outline_border", ("--outline-gray-2", "--outline-gray-3"), "button_outline"),
	# States: one color recolors the whole family (decision C2)
	Role("adv_success", family="green"),
	Role("adv_error", family="red"),
	Role("adv_warning", family="amber"),
	Role("adv_info", family="blue"),
	# Charts (read by the AxisChart/DonutChart overrides)
	*(Role(f"adv_chart_{n}", (f"--os-chart-{n}",)) for n in range(1, 6)),
)

ROLE_FIELDS = tuple(role.fieldname for role in ROLES)
BASE_FIELDS = ("base_primary", "base_accent", "base_background", "base_gray_tint")
RADIUS_FIELD = "adv_radius"
RADIUS_FACTORS = {"Small": 0.5, "Large": 1.6}
# Radius tokens that are not a size step (none, pill) keep their value.
RADIUS_FIXED = {"--radius-0", "--radius-none", "--radius-9", "--radius-full"}

# Hue turns for the chart series computed from the primary color.
CHART_HUE_TURNS = (0, None, 60, 210, 290)


def _shade(value: str, token: str, anchor: str, stock: Stock) -> str:
	"""``value`` moved by the stock lightness gap between ``token`` and ``anchor``."""
	if token == anchor or token not in stock or anchor not in stock:
		return value
	L, C, H = color.to_oklch(value)
	tL, tC, _ = stock[token]
	aL, aC, _ = stock[anchor]
	chroma = C * (tC / aC) if aC > 0.01 else C
	return color.from_oklch(L + (tL - aL), chroma, H)


def _family_tokens(value: str, family: str, stock: Stock) -> dict[str, str]:
	"""Every token of a frappe-ui color family, recolored from one status color.

	Each step keeps its stock lightness; hue and chroma follow ``value``, with
	the family's own hue drift and chroma curve kept relative to its most
	saturated step.
	"""
	members = {
		name: oklch
		for name, oklch in stock.items()
		if any(name.startswith(f"--{kind}-{family}-") for kind in ("ink", "surface", "outline"))
	}
	if not members:
		return {}
	reference = max(members.values(), key=lambda oklch: oklch[1])
	_, C, H = color.to_oklch(value)
	ratio = min(1.6, C / reference[1]) if reference[1] > 0 else 1
	return {
		name: color.from_oklch(L, c * ratio, (H + (h - reference[2])) % 360)
		for name, (L, c, h) in sorted(members.items())
	}


def stock_lightness(token: str, stock: Stock, fallback: float) -> float:
	return stock[token][0] if token in stock else fallback


ROLES_BY_FIELD = {role.fieldname: role for role in ROLES}

# Gray roles Base computes: (fieldname, anchor token, fallback stock lightness,
# surface the text is read on, or None for surfaces and borders).
BASE_GRAY_ROLES = (
	("adv_heading_ink", "--ink-gray-9", 0.168, "--surface-base"),
	("adv_text_ink", "--ink-gray-7", 0.341, "--surface-base"),
	("adv_muted_ink", "--ink-gray-5", 0.586, "--surface-base"),
	# Placeholders are read inside the fields, which stay light in Base.
	("adv_placeholder_ink", "--ink-gray-4", 0.683, "--surface-gray-2"),
	("adv_subtle_bg", "--surface-gray-2", 0.964, None),
	("adv_border_light", "--outline-gray-1", 0.946, None),
	("adv_border", "--outline-gray-2", 0.913, None),
	("adv_border_strong", "--outline-gray-3", 0.83, None),
	# Areas with their own role keep stock colors unless it is set (see
	# blocks), so the tint has to reach them explicitly.
	("adv_sidebar_ink", "--ink-gray-8", 0.27, "--surface-sidebar"),
	("adv_sidebar_hover", "--surface-gray-2", 0.964, None),
	("adv_input_bg", "--surface-gray-2", 0.964, None),
	("adv_outline_border", "--outline-gray-2", 0.913, None),
	("adv_secondary_bg", "--surface-gray-2", 0.964, None),
	("adv_secondary_ink", "--ink-gray-8", 0.27, None),
)
# Below this share of its stock contrast a Base text color is moved (G3). The
# margin keeps a tint at the stock lightness, on a light page, unchanged.
READABLE_SHARE = 0.9
READABLE_CAP = 4.5


def _stock_hex(token: str, stock: Stock) -> str | None:
	return color.from_oklch(*stock[token]) if token in stock else None


def _readable(value: str, role: Role, surface: str, background: str, stock: Stock) -> str:
	"""``value`` moved in lightness until every token of ``role`` reads on
	``background`` about as well as the stock token reads on the stock
	``surface`` (at most AA). The role's tokens keep their offsets from the
	anchor, so the lightest one (e.g. secondary text) is the one that decides.
	"""
	stock_surface = _stock_hex(surface, stock)
	if not stock_surface:
		return value
	targets = {}
	for token in role.tokens:
		stock_token = _stock_hex(token, stock)
		if stock_token:
			targets[token] = min(READABLE_CAP, color.contrast_ratio(stock_token, stock_surface))

	def reads(candidate: str, share: float) -> bool:
		anchor = role.tokens[0]
		return all(
			color.contrast_ratio(_shade(candidate, token, anchor, stock), background) >= target * share
			for token, target in targets.items()
		)

	if not targets or reads(value, READABLE_SHARE):
		return value
	L, C, H = color.to_oklch(value)
	step = -0.02 if color.relative_luminance(background) > 0.18 else 0.02
	candidate = value
	for _ in range(50):
		L += step
		if not 0 <= L <= 1:
			break
		candidate = color.from_oklch(L, C, H)
		if reads(candidate, 1):
			return candidate
	return candidate


def _distinct_from(page: str, accent: str, stock: Stock) -> str:
	"""The secondary button: ``accent`` mixed into ``page``, more than the
	usual 12% when that is too close to the page to be told apart."""
	stock_page, stock_button = _stock_hex("--surface-base", stock), _stock_hex("--surface-gray-2", stock)
	target = color.contrast_ratio(stock_page, stock_button) if stock_page and stock_button else 1.1
	amount = 0.12
	secondary = color.mix(page, accent, amount)
	while color.contrast_ratio(secondary, page) < target and amount < 0.4:
		amount += 0.04
		secondary = color.mix(page, accent, amount)
	return secondary


def derive_base(values, stock: Stock) -> Values:
	"""Role values computed from the 4 Base colors (only roles it has a reason to set)."""
	get = lambda f: (values.get(f) or "").strip()  # noqa: E731
	primary, accent, background, tint = (get(f) if color.is_hex(get(f)) else "" for f in BASE_FIELDS)
	roles: Values = {}
	page = background or color.WHITE

	if background:
		roles["adv_page_bg"] = background
		roles["adv_card_bg"] = background
		roles["adv_menu_bg"] = background
		roles["adv_sidebar_bg"] = _shade(background, "--surface-sidebar", "--surface-base", stock)
	backgrounds = {
		"--surface-base": page,
		"--surface-sidebar": roles.get("adv_sidebar_bg") or _stock_hex("--surface-sidebar", stock) or page,
	}

	# Grays take the tint's hue at low chroma; the stock lightness of each step
	# stays, unless the text would not read on the chosen background (G3).
	neutral = None
	if tint:
		_, C, H = color.to_oklch(tint)
		neutral = (min(0.03, C * 0.3), H)
	elif background and color.to_oklch(background)[1] > 0.01:
		_, C, H = color.to_oklch(background)
		neutral = (min(0.02, C * 0.5), H)
	chroma, hue = neutral or (0.0, 0.0)
	backgrounds["--surface-gray-2"] = color.from_oklch(stock_lightness("--surface-gray-2", stock, 0.964), chroma, hue)
	for fieldname, anchor, fallback, surface in BASE_GRAY_ROLES:
		value = color.from_oklch(stock_lightness(anchor, stock, fallback), chroma, hue)
		readable = value
		if surface:
			readable = _readable(value, ROLES_BY_FIELD[fieldname], surface, backgrounds[surface], stock)
		if neutral or readable != value:
			roles[fieldname] = readable

	if primary:
		roles["adv_button_bg"] = primary
		active = color.mix(page, primary, 0.12)
		roles["adv_sidebar_active_bg"] = active
		roles["adv_sidebar_active_ink"] = color.ensure_contrast(primary, active)
		roles["adv_link_ink"] = color.ensure_contrast(primary, page)
		roles["adv_focus_ring"] = color.mix(primary, page, 0.45)

	chart_accent = accent or (primary and color.rotate_hue(primary, 150))
	for n, turn in enumerate(CHART_HUE_TURNS, start=1):
		if turn is None:
			series = chart_accent
		else:
			series = primary and color.rotate_hue(primary, turn)
		if series:
			roles[f"adv_chart_{n}"] = series

	if accent:
		secondary = _distinct_from(page, accent, stock)
		roles["adv_secondary_bg"] = secondary
		roles["adv_secondary_ink"] = color.ensure_contrast(accent, secondary)
	return roles


def advanced_values(values) -> Values:
	return {f: v.strip() for f in ROLE_FIELDS if color.is_hex(v := (values.get(f) or ""))}


def resolve(roles: Values) -> Values:
	"""Fill the derived roles (button text, hover, pressed) left empty."""
	resolved = dict(roles)
	for role in ROLES:
		if role.derive and role.fieldname not in resolved:
			value = role.derive(resolved)
			if value:
				resolved[role.fieldname] = value
	return resolved


def blocks(roles: Values, stock: Stock) -> dict[str | None, dict[str, str]]:
	"""Declarations per scope (None = global), in a stable order."""
	out: dict[str | None, dict[str, str]] = {None: {}}
	for scope in SCOPES:
		out[scope] = {}
	for role in ROLES:
		value = roles.get(role.fieldname)
		if not value:
			continue
		target = out[role.scope]
		if role.family:
			target.update(_family_tokens(value, role.family, stock))
			continue
		anchor = role.tokens[0]
		for token in role.tokens:
			target[token] = _shade(value, token, anchor, stock)

	# An area owns the tokens of its roles. A global role must not reach into
	# it: while the area's own role is empty, the area keeps the stock value.
	for scope in SCOPES:
		if scope in NESTED_SCOPES:
			continue
		owned = sorted({token for role in ROLES if role.scope == scope for token in role.tokens})
		for token in owned:
			if token in out[None] and token not in out[scope] and token in stock:
				out[scope][token] = color.from_oklch(*stock[token])
	return out


def radius_declarations(values, radius_tokens: dict[str, str]) -> dict[str, str]:
	"""Scaled ``--radius-*`` steps for Advanced's "Corner Rounding"."""
	factor = RADIUS_FACTORS.get((values.get(RADIUS_FIELD) or "").strip())
	if not factor:
		return {}
	out = {}
	for name, value in sorted(radius_tokens.items()):
		if name in RADIUS_FIXED or not value.endswith("px"):
			continue
		try:
			px = float(value[:-2])
		except ValueError:
			continue
		out[name] = f"{round(px * factor, 1):g}px"
	return out

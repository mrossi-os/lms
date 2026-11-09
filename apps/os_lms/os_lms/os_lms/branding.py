# Copyright (c) 2026, ELITE and contributors
# For license information, please see license.txt

import mimetypes
import re
from urllib.parse import quote

import frappe

from os_lms.os_lms import branding_color, branding_contrast, branding_roles, branding_tokens

# Some minimal Linux images (incl. the Frappe Docker base) lack /etc/mime.types,
# so mimetypes.guess_type("brand.css") returns None and Frappe falls back to
# application/octet-stream. Browsers refuse stylesheets served with that MIME.
mimetypes.add_type("text/css", ".css")

# Brand Customize has three exclusive modes (docs/brand-customize/PIANO.md):
# only the active one is turned into CSS, the fields of the others stay saved
# but are ignored.
MODE_BASE = "Base"
MODE_ADVANCED = "Advanced"
MODE_EXPERT = "Expert"
DEFAULT_MODE = MODE_EXPERT

# Base and Advanced write role values, built by branding_roles (fieldnames
# base_* and adv_*): they only accept hex colors (fase-3-analisi.md, C1).
HEX_ONLY_FIELDS = (*branding_roles.BASE_FIELDS, *branding_roles.ROLE_FIELDS)

# Expert mode writes any CSS variable of the platform as it is (the table
# expert_tokens, fase-4-analisi.md). Until 2026-11 it had one field per variable:
# fieldname -> variable of those fields, used by the patch that moved their
# values into the table and by the import of old exported files.
LEGACY_EXPERT_FIELDS = {
	"surface_base": "--surface-base",
	"surface_sidebar": "--surface-sidebar",
	"surface_elevation_1": "--surface-elevation-1",
	"surface_elevation_2": "--surface-elevation-2",
	"surface_elevation_3": "--surface-elevation-3",
	"surface_gray_1": "--surface-gray-1",
	"surface_gray_2": "--surface-gray-2",
	"surface_gray_3": "--surface-gray-3",
	"surface_gray_10": "--surface-gray-10",
	"ink_gray_5": "--ink-gray-5",
	"ink_gray_6": "--ink-gray-6",
	"ink_gray_7": "--ink-gray-7",
	"ink_gray_8": "--ink-gray-8",
	"ink_gray_9": "--ink-gray-9",
	"ink_gray_10": "--ink-gray-10",
	"ink_base": "--ink-base",
	"outline_gray_1": "--outline-gray-1",
	"outline_elevation_2": "--outline-elevation-2",
	"company_primary": "--color-company-primary",
}

# Login page, outside the modes: always applied. Its stylesheet reads these with
# a Frappe default as the fallback, so an instance that leaves them empty
# renders a stock login.
LOGIN_FIELD_TO_CSS_VAR = {
	"login_bg_from": "--login-bg-from",
	"login_bg_to": "--login-bg-to",
	"login_ink": "--login-ink",
	"login_input_bg": "--login-input-bg",
	"login_input_ink": "--login-input-ink",
	"login_button_bg": "--login-button-bg",
}

EXPERT_TABLE = "expert_tokens"

CACHE_KEY = "brand_customize_css"

# Client colors only brand the default light theme: a user who picks dark or high
# contrast gets the stock palette. frappe-ui puts its light tokens in :root and its
# dark ones in [data-theme="dark"] (same specificity, so the last loaded wins);
# this selector outranks the light defaults and never matches under dark or under
# data-contrast="more" (the SPA's high-contrast switch).
BRANDED_THEME_SELECTOR = ':root:not([data-theme="dark"]):not([data-contrast="more"])'

COLOR_VALUE_MAX_LENGTH = 100
# Expert values include shadows: frappe-ui's own reach 121 characters.
TOKEN_VALUE_MAX_LENGTH = 300
# A value is pasted verbatim inside a declaration, so anything that could close
# it (";", "}"), open a new rule or comment, or load a resource is refused.
UNSAFE_COLOR_VALUE_RE = re.compile(r"[;{}<>\\]|/\*|\*/|url\s*\(|@import", re.IGNORECASE)


def is_valid_color_value(value, max_length: int = COLOR_VALUE_MAX_LENGTH) -> bool:
	"""Whether ``value`` can be written as a custom property value as is.

	Empty is valid (the field is unset). Any CSS color syntax is accepted (#hex,
	rgb(), oklch(), color-mix(), var(--x), named colors); the browser drops a
	value it does not understand, so only what could break out is refused.
	"""
	value = (value or "").strip()
	return len(value) <= max_length and not UNSAFE_COLOR_VALUE_RE.search(value)


def expert_values(values) -> dict[str, str]:
	"""Expert variables (name -> value) of a saved doc, a list of rows or a dict."""
	rows = values.get(EXPERT_TABLE) or []
	if isinstance(rows, dict):
		pairs = rows.items()
	else:
		pairs = ((row.get("token"), row.get("value")) for row in rows)
	return {
		(name or "").strip(): (value or "").strip()
		for name, value in pairs
		if isinstance(name, str) and isinstance(value, str) and (value or "").strip()
	}


def is_valid_token(name: str, value: str) -> bool:
	return bool(branding_tokens.TOKEN_NAME_RE.match(name)) and is_valid_color_value(
		value, TOKEN_VALUE_MAX_LENGTH
	)


def _expert_declarations(values) -> tuple[dict[str, str], dict[str, str]]:
	"""Expert variables split into (light theme only, every theme).

	Lengths (corner radius, sizes) are not colors: like Advanced's corner
	rounding they also apply under dark mode (decision E4).
	"""
	kinds = {row["name"]: row["kind"] for row in branding_tokens.manifest()}
	themed, independent = {}, {}
	for name, value in expert_values(values).items():
		if not is_valid_token(name, value):
			continue
		kind = kinds.get(name) or branding_tokens.value_kind(value)
		(independent if kind == branding_tokens.KIND_LENGTH else themed)[name] = value
	return themed, independent


def _declarations(values, field_to_css_var: dict[str, str]) -> list[str]:
	lines = []
	for fieldname, css_var in field_to_css_var.items():
		value = (values.get(fieldname) or "").strip()
		# Saved values are validated on save; this also guards the preview.
		if value and is_valid_color_value(value):
			lines.append(f"\t{css_var}: {value};")
	return lines


def _token_stock() -> dict:
	"""Stock OKLCH of every frappe-ui token (empty without a SPA build)."""
	stock = {}
	for name, value in _spa_token_defaults().items():
		oklch = branding_color.parse_oklch(value)
		if oklch:
			stock[name] = oklch
	return stock


def mode_roles(values, mode: str, stock: dict) -> dict[str, str]:
	"""Resolved role values (fieldname -> hex) of Base or Advanced."""
	if mode == MODE_BASE:
		roles = branding_roles.derive_base(values, stock)
	elif mode == MODE_ADVANCED:
		roles = branding_roles.advanced_values(values)
	else:
		return {}
	return branding_roles.resolve(roles)


def _lines(declarations: dict[str, str]) -> list[str]:
	return [f"\t{name}: {value};" for name, value in declarations.items()]


def _build_css(values=None) -> str:
	"""Build the brand stylesheet.

	``values`` is any mapping with ``.get()`` (a dict of unsaved form values, for
	the live preview); when omitted the saved Brand Customize is read. Only the
	active mode is written: the other modes' values stay saved but unused.
	"""
	if values is None:
		values = frappe.get_cached_doc("Brand Customize")
	mode = values.get("mode") or DEFAULT_MODE

	scoped: dict[str, dict[str, str]] = {}
	expert_independent: dict[str, str] = {}
	if mode == MODE_EXPERT:
		expert_themed, expert_independent = _expert_declarations(values)
		themed = _lines(expert_themed)
	else:
		stock = _token_stock()
		blocks = branding_roles.blocks(mode_roles(values, mode, stock), stock)
		themed = _lines(blocks.pop(None))
		scoped = {scope: decls for scope, decls in blocks.items() if decls}

	# The login pages have no theme switch, so their colors apply in every theme;
	# corner rounding is not a color, so it follows the user in dark mode too.
	independent = _declarations(values, LOGIN_FIELD_TO_CSS_VAR) + _lines(expert_independent)
	if mode == MODE_ADVANCED:
		radius_tokens = {k: v for k, v in _spa_token_defaults().items() if k.startswith("--radius-")}
		independent += _lines(branding_roles.radius_declarations(values, radius_tokens))

	lines = [f"{BRANDED_THEME_SELECTOR} {{", *themed, "}"]
	for scope, declarations in scoped.items():
		selector = ", ".join(f"{BRANDED_THEME_SELECTOR} {s}" for s in branding_roles.SCOPES[scope])
		lines += [f"{selector} {{", *_lines(declarations), "}"]
	lines += [":root {", *independent, "}"]
	return "\n".join(lines) + "\n"


@frappe.whitelist(allow_guest=True)
def brand_css() -> None:
	"""Serve the Brand Customize values as a CSS stylesheet.

	Uses the "download" response type because, unlike "binary", it honours an
	explicit ``content_type`` field — needed since browsers refuse to apply
	stylesheets served with the wrong MIME (e.g. application/octet-stream).
	"""
	css = frappe.cache().get_value(CACHE_KEY, generator=_build_css)

	frappe.response["type"] = "download"
	frappe.response["filename"] = "brand.css"
	frappe.response["filecontent"] = css.encode("utf-8")
	frappe.response["content_type"] = "text/css; charset=utf-8"
	frappe.response["display_content_as"] = "inline"


def clear_brand_cache(doc=None, method=None) -> None:
	"""Invalidate the cached CSS when Brand Customize is updated."""
	frappe.cache().delete_value(CACHE_KEY)
	frappe.clear_document_cache("Brand Customize", "Brand Customize")


# Live preview (docs/brand-customize/fase-2-analisi.md): the Desk form shows the
# main pages in iframes and swaps their brand stylesheet for the CSS of the
# unsaved values, built by the same _build_css as the saved one.
PREVIEW_FIELDS = (*LOGIN_FIELD_TO_CSS_VAR, *HEX_ONLY_FIELDS, branding_roles.RADIUS_FIELD, "mode")


def invalid_fields(values) -> list[str]:
	"""Fields whose value would be refused on save (Expert rows: see invalid_tokens)."""
	invalid = [f for f in LOGIN_FIELD_TO_CSS_VAR if not is_valid_color_value(values.get(f))]
	invalid += [
		f for f in HEX_ONLY_FIELDS if (values.get(f) or "").strip() and not branding_color.is_hex(values.get(f))
	]
	return invalid


def invalid_tokens(values) -> list[str]:
	"""Expert variables with a malformed name or an unsafe value."""
	return sorted(name for name, value in expert_values(values).items() if not is_valid_token(name, value))


def check_expert_tokens(values, previous: set[str]) -> tuple[list[str], list[str], list[str]]:
	"""(invalid, unknown and new, unknown but already saved) Expert variables.

	A variable that the installed build no longer has (a frappe-ui update renamed
	or dropped it) must not block saving the whole form: it stays, with a
	warning. Only a newly added one has to exist (decision E5). Without a SPA
	build there is no list to check against.
	"""
	names = expert_values(values)
	invalid = invalid_tokens(values)
	known = branding_tokens.by_name()
	if not known:
		return invalid, [], []
	unknown = sorted(n for n in names if n not in known and n not in invalid)
	return invalid, [n for n in unknown if n not in previous], [n for n in unknown if n in previous]


def _parse_values(values: str) -> dict[str, str]:
	try:
		data = frappe.parse_json(values)
	except ValueError:
		data = None
	if not isinstance(data, dict):
		frappe.throw(frappe._("Invalid preview values."))
	known = {}
	for fieldname in PREVIEW_FIELDS:
		value = data.get(fieldname)
		known[fieldname] = value if isinstance(value, str) else ""
	tokens = data.get(EXPERT_TABLE)
	known[EXPERT_TABLE] = tokens if isinstance(tokens, dict | list) else {}
	return known


@frappe.whitelist(methods=["POST"])
def brand_css_preview(values: str) -> dict:
	"""CSS of the unsaved form values, the fields whose value was refused, the
	readability of the colors (fase-5-analisi.md) and, in Base, the role colors
	computed from the 4 base colors (for the swatches)."""
	frappe.only_for("System Manager")
	known = _parse_values(values)
	invalid = invalid_fields(known) + invalid_tokens(known)
	mode = known.get("mode") or DEFAULT_MODE
	stock = _token_stock()
	result = {
		"css": _build_css(known),
		"invalid": invalid,
		"roles": {},
		"contrast": branding_contrast.report(known, mode, stock),
	}
	if mode == MODE_BASE:
		result["roles"] = mode_roles(known, MODE_BASE, stock)
	return result


@frappe.whitelist(methods=["POST"])
def base_to_advanced(values: str) -> dict[str, str]:
	"""Advanced role values that reproduce the given Base colors.

	Only the roles Base sets are returned; the derived ones (button text,
	hover, pressed) stay empty so that Advanced keeps computing them from the
	button color the user may then change.
	"""
	frappe.only_for("System Manager")
	return branding_roles.derive_base(_parse_values(values), _token_stock())


def _preview_course(user: str) -> str | None:
	"""A published course whose first lesson opens, that ``user`` is not enrolled in.

	Opening a lesson of an enrolled course starts the dwell timer and can mark it
	complete; without a membership row Lesson.vue records nothing.
	"""
	rows = frappe.db.sql(
		"""
		select c.name
		from `tabLMS Course` c
		join `tabChapter Reference` cr
			on cr.parent = c.name and cr.parenttype = 'LMS Course' and cr.idx = 1
		join `tabCourse Chapter` ch on ch.name = cr.chapter and ifnull(ch.is_scorm_package, 0) = 0
		join `tabLesson Reference` lr
			on lr.parent = ch.name and lr.parenttype = 'Course Chapter' and lr.idx = 1
		where c.published = 1 and ifnull(c.upcoming, 0) = 0
			and not exists (
				select 1 from `tabLMS Enrollment` e where e.course = c.name and e.member = %(user)s
			)
		order by c.featured desc, c.published_on desc, c.creation desc
		limit 1
		""",
		{"user": user},
	)
	return rows[0][0] if rows else None


def _preview_batch() -> str | None:
	return frappe.db.get_value(
		"LMS Batch", {"published": 1}, "name", order_by="start_date desc, creation desc"
	)


TABLE_HEADER_SELECTORS = (".os-list-view > div:first-of-type",)
TABLE_ROW_SELECTORS = (".os-list-view > div:nth-of-type(2)", ".os-table-view tbody")
CHART_SELECTORS = ("[_echarts_instance_]",)
LOGIN_HIGHLIGHTS = {
	"login_bg_from": {"selectors": ["body"]},
	"login_bg_to": {"selectors": ["body"]},
	"login_ink": {"selectors": [".page-card-head h4"]},
	"login_input_bg": {"selectors": ["input"]},
	"login_input_ink": {"selectors": ["input"]},
	"login_button_bg": {"selectors": [".btn-login"]},
}
# Base color -> the roles it drives (see branding_roles.derive_base).
BASE_HIGHLIGHT_ROLES = {
	"base_primary": ("adv_button_bg", "adv_sidebar_active_bg", "adv_link_ink", "adv_chart_1"),
	"base_accent": ("adv_secondary_bg", "adv_chart_2"),
	"base_background": ("adv_page_bg", "adv_card_bg", "adv_sidebar_bg"),
	"base_gray_tint": ("adv_text_ink", "adv_muted_ink", "adv_subtle_bg", "adv_border"),
}


def _role_highlight(role) -> dict:
	"""How the preview finds the elements of a role: CSS selectors, token names
	(matched against utility classes such as ``bg-surface-gray-2``) or a color family."""
	if role.fieldname == "adv_table_header_bg":
		return {"selectors": list(TABLE_HEADER_SELECTORS)}
	if role.fieldname == "adv_table_row_bg":
		return {"selectors": list(TABLE_ROW_SELECTORS)}
	if role.fieldname.startswith("adv_chart_"):
		return {"selectors": list(CHART_SELECTORS)}
	if role.family:
		return {"families": [role.family]}
	if role.scope:
		return {"selectors": list(branding_roles.SCOPES[role.scope])}
	return {"tokens": [t[2:] for t in role.tokens]}


def highlight_specs() -> dict[str, dict]:
	# Expert variables are found exactly in the preview (brand_customize.js).
	specs = {role.fieldname: _role_highlight(role) for role in branding_roles.ROLES}
	for fieldname, roles in BASE_HIGHLIGHT_ROLES.items():
		merged: dict[str, list[str]] = {}
		for role in roles:
			for kind, items in specs[role].items():
				merged.setdefault(kind, [])
				merged[kind] += [i for i in items if i not in merged[kind]]
		specs[fieldname] = merged
	specs.update(LOGIN_HIGHLIGHTS)
	return specs


@frappe.whitelist()
def get_preview_targets() -> dict:
	"""Pages of the preview (key, url, and the reason when a page has no
	content) and how to highlight the elements of each field.

	The login page cannot be previewed by a logged-in user (it always redirects),
	so the password-reset page, which shares its look and its colors, stands in.
	"""
	frappe.only_for("System Manager")
	from lms.hooks import get_lms_path

	base = "/" + get_lms_path()
	course = _preview_course(frappe.session.user)
	course = course and quote(course, safe="")
	batch = _preview_batch()
	batch = batch and quote(batch, safe="")
	no_course = frappe._("There is no published course with lessons you are not enrolled in.")

	def target(key: str, url: str | None, reason: str | None = None) -> dict:
		return {"key": key, "url": url, "reason": None if url else reason}

	pages = [
		target("home", base),
		target("courses", f"{base}/courses"),
		target("course", course and f"{base}/courses/{course}", no_course),
		target("lesson", course and f"{base}/courses/{course}/learn/1-1", no_course),
		# The management tabs of the course page, picked by the hash
		# (TabbedDetailPage). The editor and the settings autosave after an
		# edit: the Desk keeps every preview frame read-only.
		target("course_dashboard", course and f"{base}/courses/{course}#dashboard", no_course),
		target("course_editor", course and f"{base}/courses/{course}#editor", no_course),
		target("course_settings", course and f"{base}/courses/{course}#settings", no_course),
		target("batch", batch and f"{base}/batches/{batch}", frappe._("There is no published batch.")),
		target("statistics", f"{base}/statistics"),
		target("login", "/update-password"),
	]
	return {"pages": pages, "highlights": highlight_specs()}


# The Desk does not load the SPA stylesheet, so the stock values of the frappe-ui
# tokens are read from the compiled file the SPA entry page links to. Its name
# changes at every build, hence the cache key carries it.
SPA_ENTRY_PAGE = ("www", "_lms.html")
SPA_STYLESHEET_RE = re.compile(r'href="/assets/lms/(frontend/assets/index-[\w-]+\.css)"')
ROOT_BLOCK_RE = re.compile(r"(?:^|[{};])\s*:root\s*\{([^}]*)\}")
DECLARATION_RE = re.compile(r"(--[\w-]+)\s*:\s*([^;]+)")
TOKEN_DEFAULTS_CACHE_PREFIX = "brand_customize_token_defaults:"


def _spa_stylesheet_path() -> str | None:
	try:
		with open(frappe.get_app_path("lms", *SPA_ENTRY_PAGE)) as f:
			match = SPA_STYLESHEET_RE.search(f.read())
	except OSError:
		return None
	return frappe.get_app_path("lms", "public", match.group(1)) if match else None


def _parse_root_tokens(css: str) -> dict[str, str]:
	"""Custom properties declared in plain ``:root`` blocks (the light theme)."""
	tokens = {}
	for block in ROOT_BLOCK_RE.findall(css):
		for name, value in DECLARATION_RE.findall(block):
			if not name.startswith("--tw-"):
				tokens.setdefault(name, value.strip())
	return tokens


def _spa_token_defaults() -> dict[str, str]:
	path = _spa_stylesheet_path()
	if not path:
		return {}

	def read() -> dict[str, str]:
		try:
			with open(path) as f:
				return _parse_root_tokens(f.read())
		except OSError:
			return {}

	return frappe.cache().get_value(TOKEN_DEFAULTS_CACHE_PREFIX + path, generator=read)


@frappe.whitelist()
def get_token_defaults() -> dict[str, str]:
	"""Stock value of every Advanced field, keyed by fieldname (empty if unknown)."""
	frappe.only_for("System Manager")
	tokens = _spa_token_defaults()
	defaults = {}
	for role in branding_roles.ROLES:
		if role.tokens and role.tokens[0] in tokens:
			defaults[role.fieldname] = tokens[role.tokens[0]]
	return defaults


@frappe.whitelist()
def get_expert_tokens() -> dict:
	"""Variables the Expert editor lists, and the fields of the old Expert form
	(to import files exported before the editor)."""
	frappe.only_for("System Manager")
	return {"tokens": branding_tokens.manifest(), "legacy": LEGACY_EXPERT_FIELDS}


@frappe.whitelist(methods=["POST"])
def to_expert(values: str) -> dict:
	"""Expert variables that reproduce the Base or Advanced colors.

	Only what those modes write everywhere has an Expert equivalent; what they
	write inside an area (buttons, sidebar, fields...) cannot be expressed as a
	plain variable, so it is counted for the confirmation instead.
	"""
	frappe.only_for("System Manager")
	known = _parse_values(values)
	mode = known.get("mode") or DEFAULT_MODE
	if mode not in (MODE_BASE, MODE_ADVANCED):
		return {"tokens": {}, "scoped": 0}
	stock = _token_stock()
	roles = mode_roles(known, mode, stock)
	blocks = branding_roles.blocks(roles, stock)
	tokens = dict(blocks.pop(None))
	if mode == MODE_ADVANCED:
		radius_tokens = {k: v for k, v in _spa_token_defaults().items() if k.startswith("--radius-")}
		tokens.update(branding_roles.radius_declarations(known, radius_tokens))
	scoped = sum(1 for role in branding_roles.ROLES if role.scope and roles.get(role.fieldname))
	return {"tokens": tokens, "scoped": scoped}


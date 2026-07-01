# Copyright (c) 2026, ELITE and contributors
# For license information, please see license.txt

import mimetypes

import frappe

# Some minimal Linux images (incl. the Frappe Docker base) lack /etc/mime.types,
# so mimetypes.guess_type("brand.css") returns None and Frappe falls back to
# application/octet-stream. Browsers refuse stylesheets served with that MIME.
mimetypes.add_type("text/css", ".css")

# Map: Brand Customize fieldname -> CSS custom property name.
# Both use frappe-ui's espresso "tokens-v2" names (frappe-ui 1.0-beta). The
# doctype fieldnames were renamed to match the v2 tokens (surface_base,
# surface_sidebar, surface_elevation_1/2/3, surface_gray_10, ink_base,
# outline_elevation_2); the old card/cards fields were merged into
# surface_elevation_1.
FIELD_TO_CSS_VAR = {
	"company_primary": "--color-company-primary",
	"company_secondary": "--color-company-secondary",
	"surface_base": "--surface-base",
	"surface_sidebar": "--surface-sidebar",
	"surface_elevation_3": "--surface-elevation-3",
	"surface_elevation_2": "--surface-elevation-2",
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
	"color_sidebar_menu": "--color-sidebar-menu",
	"surface_elevation_1": "--surface-elevation-1",
	"color_menu_bar": "--color-menu-bar",
	"gradient_overlay_from": "--gradient-overlay-from",
	"gradient_overlay_to": "--gradient-overlay-to",
}

CACHE_KEY = "brand_customize_css"


def _build_css() -> str:
	doc = frappe.get_cached_doc("Brand Customize")
	lines = [":root {"]
	for fieldname, css_var in FIELD_TO_CSS_VAR.items():
		value = (doc.get(fieldname) or "").strip()
		if value:
			lines.append(f"\t{css_var}: {value};")
	lines.append("}")
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

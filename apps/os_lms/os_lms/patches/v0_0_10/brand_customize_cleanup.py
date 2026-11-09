"""Clean up Brand Customize after the form was reorganised into modes.

Four fields had no effect and were removed from the doctype: ``theme``
(obsolete), ``company_secondary`` (not read by the SPA), ``color_sidebar_menu``
and ``color_menu_bar`` (no stylesheet reads them). A Single keeps its values in
tabSingles even after a field is removed, so the orphan rows are deleted here.
The new ``mode`` field starts on Expert, the only mode with fields for now:
the existing token fields belong to it, so the platform keeps its look.
Idempotent: a second run finds nothing to delete and the mode already set.
"""

import frappe

DOCTYPE = "Brand Customize"
REMOVED_FIELDS = ("theme", "company_secondary", "color_sidebar_menu", "color_menu_bar")


def execute():
	frappe.db.delete("Singles", {"doctype": DOCTYPE, "field": ("in", REMOVED_FIELDS)})

	if not frappe.db.get_single_value(DOCTYPE, "mode", cache=False):
		frappe.db.set_single_value(DOCTYPE, "mode", "Expert")

	from os_lms.os_lms.branding import clear_brand_cache

	clear_brand_cache()

"""Move the old Expert fields of Brand Customize into the Expert table.

Until 2026-11 the Expert mode had one Color field per CSS variable (19 fields);
it now writes any variable from the ``expert_tokens`` table
(docs/brand-customize/fase-4-analisi.md, decision E7). The fields were removed
from the doctype, but a Single keeps their values in tabSingles: each value
becomes a table row with the same variable, then the orphan rows are deleted,
so the platform keeps exactly its look.

Idempotent: a variable already in the table is not added twice, and a second
run finds no old value left.
"""

import frappe

from os_lms.os_lms.branding import EXPERT_TABLE, LEGACY_EXPERT_FIELDS, clear_brand_cache

DOCTYPE = "Brand Customize"
CHILD_DOCTYPE = "Brand Customize Token"


def legacy_values() -> dict[str, str]:
	rows = frappe.db.sql(
		"select field, value from `tabSingles` where doctype = %s and field in %s",
		(DOCTYPE, tuple(LEGACY_EXPERT_FIELDS)),
	)
	return {field: (value or "").strip() for field, value in rows}


def execute():
	values = legacy_values()
	if not values:
		return

	existing = frappe.get_all(
		CHILD_DOCTYPE,
		filters={"parent": DOCTYPE, "parenttype": DOCTYPE, "parentfield": EXPERT_TABLE},
		fields=["token", "idx"],
	)
	present = {row.token for row in existing}
	idx = max((row.idx for row in existing), default=0)
	for field, css_var in LEGACY_EXPERT_FIELDS.items():
		value = values.get(field)
		if not value or css_var in present:
			continue
		idx += 1
		frappe.get_doc(
			{
				"doctype": CHILD_DOCTYPE,
				"parent": DOCTYPE,
				"parenttype": DOCTYPE,
				"parentfield": EXPERT_TABLE,
				"idx": idx,
				"token": css_var,
				"value": value,
			}
		).db_insert()
		present.add(css_var)

	frappe.db.delete("Singles", {"doctype": DOCTYPE, "field": ("in", tuple(LEGACY_EXPERT_FIELDS))})
	clear_brand_cache()

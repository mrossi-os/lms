"""The v0_0_11 patch moves the old Expert fields into the Expert table.

Works on the real tabSingles and table rows and rolls everything back, so the
site's own brand values are left as they were.
"""

from __future__ import annotations

import frappe
from frappe.tests import UnitTestCase

from os_lms.patches.v0_0_11 import brand_customize_expert_tokens as patch

DOCTYPE = patch.DOCTYPE


def _seed(field: str, value: str):
	frappe.db.delete("Singles", {"doctype": DOCTYPE, "field": field})
	frappe.db.sql(
		"insert into `tabSingles` (doctype, field, value) values (%s, %s, %s)", (DOCTYPE, field, value)
	)


def _rows() -> dict[str, str]:
	rows = frappe.get_all(
		patch.CHILD_DOCTYPE,
		filters={"parent": DOCTYPE, "parentfield": "expert_tokens"},
		fields=["token", "value"],
	)
	return {row.token: row.value for row in rows}


class TestBrandCustomizeExpertTokensPatch(UnitTestCase):
	def setUp(self):
		frappe.db.delete(patch.CHILD_DOCTYPE, {"parent": DOCTYPE, "parentfield": "expert_tokens"})

	def tearDown(self):
		frappe.db.rollback()

	def test_old_values_become_rows_and_leave_tabsingles(self):
		_seed("surface_gray_10", "#292929")
		_seed("company_primary", "#f5f5f5")
		_seed("ink_gray_10", "")
		patch.execute()
		self.assertEqual(
			_rows(), {"--surface-gray-10": "#292929", "--color-company-primary": "#f5f5f5"}
		)
		self.assertEqual(patch.legacy_values(), {})

	def test_a_variable_already_in_the_table_is_not_added_twice(self):
		frappe.get_doc(
			{
				"doctype": patch.CHILD_DOCTYPE,
				"parent": DOCTYPE,
				"parenttype": DOCTYPE,
				"parentfield": "expert_tokens",
				"idx": 1,
				"token": "--surface-gray-10",
				"value": "#111111",
			}
		).db_insert()
		_seed("surface_gray_10", "#292929")
		patch.execute()
		patch.execute()
		self.assertEqual(_rows(), {"--surface-gray-10": "#111111"})

	def test_nothing_to_move_changes_nothing(self):
		frappe.db.delete("Singles", {"doctype": DOCTYPE, "field": ("in", tuple(patch.LEGACY_EXPERT_FIELDS))})
		patch.execute()
		self.assertEqual(_rows(), {})

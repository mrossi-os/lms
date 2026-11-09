"""The v0_0_10 patch drops the removed Brand Customize fields and sets the mode.

Runs on the real tabSingles rows and rolls everything back, so the site's own
brand values are left as they were.
"""

from __future__ import annotations

import frappe
from frappe.tests import UnitTestCase

from os_lms.patches.v0_0_10 import brand_customize_cleanup as patch

DOCTYPE = patch.DOCTYPE


def _singles(field: str):
	# Raw SQL: get_value on "Singles" orders by `creation`, which tabSingles lacks.
	rows = frappe.db.sql(
		"select value from `tabSingles` where doctype = %s and field = %s", (DOCTYPE, field)
	)
	return rows[0][0] if rows else None


class TestBrandCustomizeCleanupPatch(UnitTestCase):
	def tearDown(self):
		frappe.db.rollback()

	def _seed(self, field: str, value: str):
		frappe.db.delete("Singles", {"doctype": DOCTYPE, "field": field})
		frappe.db.sql(
			"insert into `tabSingles` (doctype, field, value) values (%s, %s, %s)",
			(DOCTYPE, field, value),
		)

	def test_removed_fields_are_deleted_and_kept_ones_survive(self):
		for field in patch.REMOVED_FIELDS:
			self._seed(field, "#123456")
		self._seed("surface_gray_10", "#292929")

		patch.execute()

		for field in patch.REMOVED_FIELDS:
			self.assertIsNone(_singles(field), field)
		self.assertEqual(_singles("surface_gray_10"), "#292929")

	def test_mode_starts_on_expert(self):
		frappe.db.delete("Singles", {"doctype": DOCTYPE, "field": "mode"})
		patch.execute()
		self.assertEqual(_singles("mode"), "Expert")

	def test_an_existing_mode_is_kept_and_rerun_is_harmless(self):
		self._seed("mode", "Base")
		patch.execute()
		patch.execute()
		self.assertEqual(_singles("mode"), "Base")

"""Backfill LMS Settings.lesson_dwell_time so settings can be saved.

Upstream added a `lesson_dwell_time` Int field (default 30) together with a
validate() rule that throws when the value is < 1. On any site whose
`LMS Settings` single predates that field, the persisted value is 0/NULL,
so *every* save of LMS Settings — from any Settings tab, not just Course
Progress — fails validation with "Lesson Dwell Time must be at least 1
second." (surfaced as an HTTP 417 in the SPA settings modal).

This runs in post_model_sync (after the field is guaranteed to exist in the
schema) and resets any value below 1 to the intended default of 30.
Idempotent: a no-op once the value is valid.
"""
import frappe
from frappe.utils import cint


def execute():
	if cint(frappe.db.get_single_value("LMS Settings", "lesson_dwell_time")) < 1:
		frappe.db.set_single_value("LMS Settings", "lesson_dwell_time", 30)
		frappe.db.commit()

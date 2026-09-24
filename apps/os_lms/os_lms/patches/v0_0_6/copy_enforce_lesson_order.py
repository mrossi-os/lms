"""Carry our sequential-lesson switch over to upstream's enforce_lesson_completion.

Upstream v2.62.0 ships a server-side sequential gate (LMS Course.enforce_lesson_completion)
that replaces our os_lms custom field enforce_lesson_order. Courses that had our switch on
must keep their behaviour, so the value is copied once. The old custom field is left in
place (data kept, no longer read by the gate). Idempotent: only ever sets 1.
"""
import frappe


def execute():
	if not frappe.db.has_column("LMS Course", "enforce_lesson_order"):
		return
	courses = frappe.get_all("LMS Course", filters={"enforce_lesson_order": 1}, pluck="name")
	for course in courses:
		frappe.db.set_value(
			"LMS Course", course, "enforce_lesson_completion", 1, update_modified=False
		)

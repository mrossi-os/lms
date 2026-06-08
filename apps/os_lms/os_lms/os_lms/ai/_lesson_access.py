"""Shared permission helper for AI endpoints.

Lives at the `ai/` package level so both `ai/api.py` (chat) and
`ai/ingestion/api.py` (ingestion) can import it without creating a
sibling-up import cycle between the two endpoint modules.
"""

import frappe
from frappe import _

from lms.lms.utils import has_course_instructor_role, has_moderator_role, is_instructor


def load_lesson(lesson_id):
	lesson = frappe.get_doc("Course Lesson", lesson_id)
	if not lesson:
		frappe.throw(_("Lesson not found"), frappe.DoesNotExistError)
	if has_moderator_role():
		return lesson

	if has_course_instructor_role() and is_instructor(lesson.course):
		return lesson

	if frappe.db.exists("LMS Enrollment", {"member": frappe.session.user, "course": lesson.course}):
		return lesson

	frappe.throw(_("You don't have permission to access this lesson"), frappe.PermissionError)

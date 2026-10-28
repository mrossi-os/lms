"""Lesson progress guard in front of lms course_lesson.save_progress.

Upstream takes `scorm_details` from the browser and, when present, marks the
lesson "Complete" without checking quizzes and assignments. It never checks that
the lesson is a SCORM one, so any enrolled student could complete every lesson
of a course, and get its certificate (and TrueSkills badge), by posting
scorm_details={"is_complete": 1}. Here SCORM details count only on a lesson of a
SCORM chapter; anywhere else the call takes the normal path, with its checks.
"""

import frappe
from lms.lms.doctype.course_lesson.course_lesson import save_progress as lms_save_progress


@frappe.whitelist()
def save_progress(lesson: str, course: str | None = None, scorm_details: dict = None):
	if scorm_details and not is_scorm_lesson(lesson):
		scorm_details = None
	return lms_save_progress(lesson, course, scorm_details)


def is_scorm_lesson(lesson) -> bool:
	if not isinstance(lesson, str):
		return False
	chapter = frappe.db.get_value("Course Lesson", lesson, "chapter")
	return bool(chapter and frappe.db.get_value("Course Chapter", chapter, "is_scorm_package"))

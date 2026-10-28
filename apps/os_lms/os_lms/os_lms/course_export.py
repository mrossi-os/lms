"""Course export that packs only the private files the course may hand out.

Upload blocks hold any file_url the author types, and upstream write_assets reads
every one of them with frappe.get_doc("File"), which checks no permission: a lesson
pointing to /private/files/<someone else's submission> put that file in the ZIP.
"""

import secrets

import frappe
from frappe import _
from frappe.core.doctype.file.utils import find_file_by_url
from lms.lms import course_import_export as course_zip
from lms.lms.doctype.course_lesson.course_lesson import (
	_references_vouched_by_owner,
	_resolve_lesson_references,
)
from lms.lms.utils import can_modify_course


@frappe.whitelist()
def export_course_as_zip(course_name: str):
	if not can_modify_course(course_name):
		frappe.throw(_("You do not have permission to export this course."), frappe.PermissionError)

	export_course_zip(course_name)


def export_course_zip(course_name):
	"""lms export_course_zip, with the assets passed through downloadable_assets."""
	course = frappe.get_doc("LMS Course", course_name)
	chapters = course_zip.get_chapters_for_export(course.chapters)
	lessons = course_zip.get_lessons_for_export(course_name)
	instructors = course_zip.get_course_instructors(course)
	evaluator = course_zip.get_course_evaluator(course)
	assets = downloadable_assets(
		course_zip.get_course_assets(course, lessons, instructors, evaluator), course_name
	)
	assessments, questions, test_cases = course_zip.get_course_assessments(lessons)
	safe_time = frappe.utils.now_datetime().strftime("%Y%m%d_%H%M%S")
	zip_filename = f"{course.name}_{safe_time}_{secrets.token_hex(4)}.zip"
	course_zip.create_course_zip(
		zip_filename,
		course,
		chapters,
		lessons,
		assets,
		assessments,
		questions,
		test_cases,
		instructors,
		evaluator,
	)


def downloadable_assets(assets, course_name):
	"""Drop the private files the course may not hand out: see can_export_private_file."""
	kept = []
	for asset in assets:
		if (
			isinstance(asset, str)
			and asset.startswith("/private/")
			and not can_export_private_file(asset, course_name)
		):
			frappe.logger("lms.security").warning(
				"Course export skipped a private file: user=%s course=%s file=%s",
				frappe.session.user,
				course_name,
				asset,
			)
			continue
		kept.append(asset)
	return kept


def can_export_private_file(file_url: str, course_name: str) -> bool:
	"""A private file goes into the course ZIP when either:

	- the exporter could download it (find_file_by_url, Frappe's check on
	  /private/files: owner, share, or read on the document it is attached to); or
	- serve_resource hands it to the learners of a lesson of this course: the
	  uploader authors the course or put it in that lesson. Lesson uploads are
	  mostly not attached to the lesson and come from another author, so the
	  first rule alone dropped them from a Docente's export.
	"""
	if ".." in file_url:
		return False
	if find_file_by_url(file_url):
		return True
	lessons = [lesson for lesson, _ in _references_vouched_by_owner(_resolve_lesson_references(file_url))]
	return bool(lessons) and bool(
		frappe.db.exists("Course Lesson", {"name": ["in", lessons], "course": course_name})
	)

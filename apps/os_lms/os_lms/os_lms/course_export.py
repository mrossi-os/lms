"""Course export that packs only the private files the exporter could download.

Upload blocks hold any file_url the author types, and upstream write_assets reads
every one of them with frappe.get_doc("File"), which checks no permission: a lesson
pointing to /private/files/<someone else's submission> put that file in the ZIP.
"""

import secrets

import frappe
from frappe import _
from frappe.core.doctype.file.utils import find_file_by_url
from lms.lms import course_import_export as course_zip
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
	"""Drop the private files the exporter could not download directly.

	find_file_by_url is the check Frappe runs on /private/files downloads: owner,
	share, or read permission on the document the file is attached to.
	"""
	kept = []
	for asset in assets:
		if isinstance(asset, str) and asset.startswith("/private/") and not find_file_by_url(asset):
			frappe.logger("lms.security").warning(
				"Course export skipped a private file: user=%s course=%s file=%s",
				frappe.session.user,
				course_name,
				asset,
			)
			continue
		kept.append(asset)
	return kept

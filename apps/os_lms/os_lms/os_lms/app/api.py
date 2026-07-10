import json

import frappe
from os_lms.os_lms.utils import get_courses_total_minutes

from lms.lms.api import get_course_details, get_featured_home_courses
from lms.lms.utils import get_course_details, get_lesson_icon

META_FIELDS = {"owner", "creation", "modified", "modified_by", "docstatus"}


def str_to_int(s: str, default: int = 0) -> int:
	try:
		return int(s)
	except (ValueError, TypeError):
		return default


def clean_dict(d: dict) -> dict:
	return {k: v for k, v in d.items() if k not in META_FIELDS}


@frappe.whitelist()
def get_course(course_name: str):
	if not course_name:
		return None
	course_data = get_course_details(course_name)
	if not course_data:
		return None

	course_meta = (
		frappe.db.get_value(
			"LMS Course",
			course_name,
			["feature_sections", "trueskills_certificate_enabled"],
			as_dict=True,
		)
		or {}
	)

	raw = course_meta.get("feature_sections")
	try:
		course_data["feature_sections"] = json.loads(raw) if raw else []
	except (json.JSONDecodeError, TypeError):
		course_data["feature_sections"] = []

	# get_course_details() qui è quello base di lms.lms.utils (non l'override
	# os_lms), quindi non include questo flag: lo esponiamo a mano così il gate
	# "Ottieni certificato" dell'app funziona sui corsi solo-TrueSkills, dove
	# enable_certification è off (i due flag sono esclusivi).
	course_data["trueskills_certificate_enabled"] = (
		1 if course_meta.get("trueskills_certificate_enabled") else 0
	)

	# Bulk-fetch completed lessons for the current user
	progress_map = {}
	if frappe.session.user != "Guest":
		progress_rows = frappe.get_all(
			"LMS Course Progress",
			filters={"course": course_name, "member": frappe.session.user, "status": "Complete"},
			fields=["lesson", "name"],
		)
		progress_map = {row.lesson: row.name for row in progress_rows}

	chapters = []
	chapter_refs = frappe.get_all(
		"Chapter Reference",
		{"parent": course_name},
		["chapter", "idx"],
		order_by="idx",
	)

	total_minutes = 0

	for ref in chapter_refs:
		chapter = frappe.get_doc("Course Chapter", ref.chapter)

		lesson_refs = frappe.get_all(
			"Lesson Reference",
			{"parent": ref.chapter},
			["lesson", "idx"],
			order_by="idx",
		)

		lessons = []
		for lesson_ref in lesson_refs:
			lesson = frappe.db.get_value(
				"Course Lesson",
				lesson_ref.lesson,
				["name", "title", "duration", "body", "content"],
				as_dict=True,
			)
			total_minutes += str_to_int(getattr(lesson, "duration", 0), 0)
			if lesson:
				lesson["idx"] = lesson_ref.idx
				lesson["icon"] = get_lesson_icon(lesson.body, lesson.content)
				lesson["is_complete"] = progress_map.get(lesson.name)
				del lesson["body"]
				del lesson["content"]
				lessons.append(lesson)

		chapters.append(
			{
				"name": chapter.name,
				"title": chapter.title,
				"idx": ref.idx,
				"lessons": lessons,
			}
		)

	course_data["total_minutes"] = total_minutes
	course_data["chapters"] = chapters
	return course_data


@frappe.whitelist()
def get_courses_categories():
	if frappe.session.user == "Guest":
		return []
	"""Return categories that are assigned to courses belonging to a published program."""
	categories = frappe.db.sql(
		"""
        SELECT DISTINCT cat.name, cat.category
        FROM `tabLMS Category` cat
        INNER JOIN `tabLMS Course` c ON c.category = cat.name
        WHERE c.published = 1
        ORDER BY cat.category
        """,
		as_dict=True,
	)
	return categories


@frappe.whitelist()
def get_courses_categories():
	if frappe.session.user == "Guest":
		return []
	"""Return categories that are assigned to courses belonging to a published program."""
	categories = frappe.db.sql(
		"""
        SELECT DISTINCT cat.name, cat.category
        FROM `tabLMS Category` cat
        INNER JOIN `tabLMS Course` c ON c.category = cat.name
        WHERE c.published = 1
        ORDER BY cat.category
        """,
		as_dict=True,
	)
	return categories


@frappe.whitelist()
def get_app_home_courses():
	if frappe.session.user == "Guest":
		return []
	courses = get_featured_home_courses()
	app_courses = []
	if courses:
		duration_map = get_courses_total_minutes(courses)

	for course in courses:
		detail = get_course_details(course)
		detail.total_minutes = duration_map.get(course, 0)
		app_courses.append(detail)

	return app_courses


@frappe.whitelist(allow_guest=True)
def get_instance_info() -> dict:
	"""Return branding info for the current instance: name, logo, and app colors.

	Name and logo come from Website / Navbar Settings (the same sources used by
	login.py and the certificate templates). Colors come from Brand Customize —
	`app_main_color` and `app_secondary_color` are the palette the mobile app
	uses for its own theming.
	"""
	from frappe.core.doctype.navbar_settings.navbar_settings import get_app_logo

	name = frappe.get_website_settings("app_name") or frappe.get_system_settings("app_name") or "Frappe"

	brand = frappe.get_cached_doc("Brand Customize")

	return {
		"name": name,
		"logo": get_app_logo(),
		"primary_color": brand.get("app_main_color") or None,
		"secondary_color": brand.get("app_secondary_color") or None,
	}

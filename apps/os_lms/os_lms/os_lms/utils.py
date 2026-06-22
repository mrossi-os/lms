import json

import frappe


def get_courses_total_minutes(course_names: list) -> dict:
	"""Returns a map of course name to total lesson duration in minutes."""
	if not course_names:
		return {}

	placeholders = ", ".join(["%s"] * len(course_names))
	durations = frappe.db.sql(
		f"""
        SELECT cr.parent AS course, COALESCE(SUM(cl.duration), 0) AS total_minutes
        FROM `tabLesson Reference` lr
        JOIN `tabChapter Reference` cr ON lr.parent = cr.chapter
        JOIN `tabCourse Lesson` cl ON lr.lesson = cl.name
        WHERE cr.parent IN ({placeholders})
        GROUP BY cr.parent
        """,
		tuple(course_names),
		as_dict=True,
	)
	return {d.course: d.total_minutes for d in durations}


def get_course_feature_sections(course_name: str) -> list[dict]:
	"""Returns a list of feature sections for a given course."""
	if not course_name:
		return []

	raw = frappe.db.get_value("LMS Course", course_name, "feature_sections")
	try:
		return json.loads(raw) if raw else []
	except (json.JSONDecodeError, TypeError):
		return []


def save_course_feature_sections(course_name: str, feature_sections: list[dict]) -> None:
	"""Persist the given feature sections on the LMS Course as JSON.

	Writes via ``frappe.db.set_value`` with ``update_modified=False`` so a
	concurrent edit of the course (e.g. the form open in another tab)
	cannot race against this write.
	"""
	if not course_name:
		return

	frappe.db.set_value(
		"LMS Course",
		course_name,
		"feature_sections",
		json.dumps(feature_sections),
		update_modified=False,
	)
	frappe.db.commit()

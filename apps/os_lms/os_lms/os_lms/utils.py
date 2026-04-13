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

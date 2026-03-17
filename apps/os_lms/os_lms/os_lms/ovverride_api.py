import frappe
from lms.lms.api import get_sidebar_settings as _original_get_sidebar_settings


@frappe.whitelist(allow_guest=True)
def get_sidebar_settings():
  
    result = _original_get_sidebar_settings()
    if isinstance(result, dict):
        result['programs'] = frappe.get_single("LMS Settings").get("programs")
    
    return result



@frappe.whitelist()
def get_lesson_creation_details(course: str, chapter: int, lesson: int) -> dict:
	frappe.only_for(["Moderator", "Course Creator"])
	chapter_name = frappe.db.get_value("Chapter Reference", {"parent": course, "idx": chapter}, "chapter")
	lesson_name = frappe.db.get_value("Lesson Reference", {"parent": chapter_name, "idx": lesson}, "lesson")

	if lesson_name:
		lesson_details = frappe.db.get_value(
			"Course Lesson",
			lesson_name,
			[
				"name",
				"title",
				"include_in_preview",
				"body",
				"content",
				"instructor_notes",
				"instructor_content",
				"youtube",
				"quiz_id",
				"duration"
			],
			as_dict=1,
		)
	lesson_count = frappe.db.count("Lesson Reference", {"parent": chapter_name})

	return {
		"course_title": frappe.db.get_value("LMS Course", course, "title"),
		"chapter": frappe.db.get_value("Course Chapter", chapter_name, ["title", "name"], as_dict=True),
		"lesson": lesson_details if lesson_name else None,
		"lesson_count": lesson_count,
	}
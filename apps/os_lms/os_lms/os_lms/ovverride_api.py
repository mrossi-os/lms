import frappe
from lms.lms.api import get_sidebar_settings as _original_get_sidebar_settings
from lms.command_palette import (
	get_instructor_info,
	prepare_search_results,
	can_access_course,
	can_access_batch,
	can_access_job,
)


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


@frappe.whitelist()
def search_sqlite(query: str):
	from os_lms.overrides.sqlite import CustomLearningSearch
	from lms.sqlite import LearningSearchIndexMissingError

	search = CustomLearningSearch()

	try:
		result = search.search(query)
	except LearningSearchIndexMissingError:
		return []

	return prepare_search_results_custom(result)


def prepare_search_results_custom(result: dict):
	from lms.command_palette import remove_duplicates

	groups = get_grouped_results_custom(result)

	out = []
	for key in groups:
		groups[key] = remove_duplicates(groups[key])
		groups[key].sort(key=lambda x: x.get("modified"), reverse=True)
		out.append({"title": key, "items": groups[key]})

	return out


def get_grouped_results_custom(result):
	roles = frappe.get_roles()
	groups = {}
	for r in result["results"]:
		doctype = r["doctype"]
		if doctype == "LMS Course" and can_access_course(r, roles):
			r["author_info"] = get_instructor_info(doctype, r)
			groups.setdefault("Courses", []).append(r)
		elif doctype == "LMS Batch" and can_access_batch(r, roles):
			r["author_info"] = get_instructor_info(doctype, r)
			groups.setdefault("Batches", []).append(r)
		elif doctype == "Job Opportunity" and can_access_job(r, roles):
			r["author_info"] = get_instructor_info(doctype, r)
			groups.setdefault("Job Opportunities", []).append(r)
		elif doctype == "LMS Program":
			groups.setdefault("Programs", []).append(r)
		elif doctype == "LMS Quiz":
			groups.setdefault("Quizzes", []).append(r)
		elif doctype == "LMS Assignment":
			groups.setdefault("Assignments", []).append(r)
	return groups
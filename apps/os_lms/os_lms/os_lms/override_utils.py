import json
import frappe
from frappe.rate_limiter import rate_limit
from lms.lms.utils import get_course_details as _original_get_course_details
from lms.lms.utils import get_lesson as _original_get_lesson
from lms.lms.utils import get_lesson_details as _original_get_lesson_details
from lms.lms.utils import get_batch_details as _original_get_batch_details
from lms.lms.utils import get_courses as _orginal_get_courses
from lms.lms.utils import get_progress
from os_lms.os_lms.api import evaluate_lesson_access, evaluate_quiz_access
from os_lms.os_lms.utils import get_courses_total_minutes


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=500, seconds=60 * 60)
def get_course_details(course: str):
    course_detail = _original_get_course_details(course)

    # Legge il JSON delle feature sections
    raw = frappe.db.get_value("LMS Course", course, "feature_sections")
    try:
        course_detail.feature_sections = json.loads(raw) if raw else []
    except (json.JSONDecodeError, TypeError):
        course_detail.feature_sections = []

    return course_detail


@frappe.whitelist(allow_guest=True)
def get_lesson(course: str, chapter: int, lesson: int) -> dict:
    lesson_details = _original_get_lesson(course, chapter, lesson)
    if isinstance(lesson_details, dict) and lesson_details.get("name"):
        lesson_name = lesson_details["name"]
        lesson_details["tags"] = frappe.db.get_value(
            "Course Lesson", lesson_name, "tags"
        )

        user = frappe.session.user
        is_guest = not user or user == "Guest"
        roles = set(frappe.get_roles(user)) if not is_guest else set()
        instructors = lesson_details.get("instructors") or []
        is_admin = bool(
            roles & {"Moderator", "Course Creator", "LMS Instructor"}
        ) or user in instructors

        if is_guest or is_admin:
            lesson_details["lesson_access"] = {"allowed": True}
            lesson_details["quiz_access"] = {"allowed": True}
        else:
            lesson_details["lesson_access"] = evaluate_lesson_access(
                course, lesson_name
            )
            lesson_details["quiz_access"] = evaluate_quiz_access(
                course, lesson_name
            )
    return lesson_details


@frappe.whitelist()
def get_lesson_creation_details(course: str, chapter: int, lesson: int) -> dict:
    frappe.only_for(["Moderator", "Course Creator"])
    chapter_name = frappe.db.get_value(
        "Chapter Reference", {"parent": course, "idx": chapter}, "chapter"
    )
    lesson_name = frappe.db.get_value(
        "Lesson Reference", {"parent": chapter_name, "idx": lesson}, "lesson"
    )

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
                "duration",
                "index_status",
                "indexed_at",
                "tags",
            ],
            as_dict=1,
        )
    lesson_count = frappe.db.count("Lesson Reference", {"parent": chapter_name})

    return {
        "course_title": frappe.db.get_value("LMS Course", course, "title"),
        "chapter": frappe.db.get_value(
            "Course Chapter", chapter_name, ["title", "name"], as_dict=True
        ),
        "lesson": lesson_details if lesson_name else None,
        "lesson_count": lesson_count,
    }


def custom_get_lesson_details(chapter: dict, progress: bool = False):
    lessons = []
    lesson_list = frappe.get_all(
        "Lesson Reference", {"parent": chapter.name}, ["lesson", "idx"], order_by="idx"
    )
    for row in lesson_list:
        lesson_details = frappe.db.get_value(
            "Course Lesson",
            row.lesson,
            [
                "name",
                "title",
                "include_in_preview",
                "body",
                "creation",
                "youtube",
                "quiz_id",
                "question",
                "file_type",
                "instructor_notes",
                "course",
                "chapter",
                "content",
                "index_status",
                "indexed_at",
                "tags",
            ],
            as_dict=True,
        )
        lesson_details.number = f"{chapter.idx}-{row.idx}"

        from lms.lms.utils import get_lesson_icon

        lesson_details.icon = get_lesson_icon(lesson_details.body, lesson_details.content)

        if progress:
            lesson_details.is_complete = get_progress(lesson_details.course, lesson_details.name)

        lessons.append(lesson_details)
    return lessons

@frappe.whitelist(allow_guest=True)
@rate_limit(limit=500, seconds=60 * 60)
def get_courses(filters: dict = None, start: int = 0) -> list:
    courses = _orginal_get_courses(filters, start)

    if courses:
        course_names = [course.name for course in courses]
        duration_map = get_courses_total_minutes(course_names)
        for course in courses:
            course.total_minutes = duration_map.get(course.name, 0)

    return courses


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=500, seconds=60 * 60)
def get_batch_details(batch: str):
    batch_detail = _original_get_batch_details(batch)

    raw = frappe.db.get_value("LMS Batch", batch, "custom_feature_sections")
    try:
        if raw:
            unescaped = raw.replace("&quot;", '"').replace("&amp;", "&")
            batch_detail.custom_feature_sections = json.loads(unescaped)
        else:
            batch_detail.custom_feature_sections = []
    except (json.JSONDecodeError, TypeError):
        batch_detail.custom_feature_sections = []

    return batch_detail
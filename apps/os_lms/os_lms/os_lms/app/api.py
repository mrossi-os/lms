import frappe
import json
from lms.lms.utils import get_lesson_icon

META_FIELDS = {"owner", "creation", "modified", "modified_by", "docstatus"}


def clean_dict(d: dict) -> dict:
    return {k: v for k, v in d.items() if k not in META_FIELDS}


@frappe.whitelist()
def get_course(course_name: str):
    if not course_name:
        return None

    course = frappe.get_doc("LMS Course", course_name)
    if not course:
        return None

    course_data = clean_dict(course.as_dict())
    
    raw = frappe.db.get_value("LMS Course", course_name, "feature_sections")
    try:
        course_data["feature_sections"] = json.loads(raw) if raw else []
    except (json.JSONDecodeError, TypeError):
        course_data["feature_sections"] = []

    course_data["instructors"] = [
        frappe.db.get_value("User", row.instructor, ["email", "full_name"], as_dict=True)
        for row in course.instructors
    ]

    chapters = []
    chapter_refs = frappe.get_all(
        "Chapter Reference",
        {"parent": course_name},
        ["chapter", "idx"],
        order_by="idx",
    )

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
            if lesson:
                lesson["idx"] = lesson_ref.idx
                lesson["icon"] = get_lesson_icon(lesson.body, lesson.content)
                del lesson["body"]
                del lesson["content"]
                lessons.append(lesson)

        chapters.append({
            "name": chapter.name,
            "title": chapter.title,
            "idx": ref.idx,
            "lessons": lessons,
        })

    course_data["chapters"] = chapters
    return course_data

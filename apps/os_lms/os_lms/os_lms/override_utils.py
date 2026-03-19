import json
import frappe
from frappe.rate_limiter import rate_limit
from lms.lms.utils import get_course_details as _original_get_course_details


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=500, seconds=60 * 60)
def get_course_details(course: str):
    course_detail = _original_get_course_details(course)

    # Legge il JSON delle feature sections
    raw = frappe.db.get_value('LMS Course', course, 'feature_sections')
    try:
        course_detail.feature_sections = json.loads(raw) if raw else []
    except (json.JSONDecodeError, TypeError):
        course_detail.feature_sections = []

    return course_detail
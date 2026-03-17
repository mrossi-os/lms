import frappe
from frappe.rate_limiter import rate_limit

from lms.lms.utils import get_course_details as _orginal_get_course_details
from os_lms.os_lms.doctype.lms_course_learning_item.lms_course_learning_item import get_course_learning_items



@frappe.whitelist(allow_guest=True)
@rate_limit(limit=500, seconds=60 * 60)
def get_course_details(course: str):
    course_detail = _orginal_get_course_details(course)
    course_detail.learning_items = get_course_learning_items(course)
    return course_detail
import frappe
from lms.lms.api import get_sidebar_settings as _original_get_sidebar_settings


@frappe.whitelist(allow_guest=True)
def get_sidebar_settings():
  
    result = _original_get_sidebar_settings()
    if isinstance(result, dict):
        result['programs'] = frappe.get_single("LMS Settings").get("programs")
    
    return result
__version__ = "0.0.1"

# Monkey-patch SMTPServer.session property
import os_lms.overrides.smtp  # noqa: F401

# Monkey-patch get_lesson_details to include index_status and indexed_at
import lms.lms.utils as _lms_utils
from os_lms.os_lms.override_utils import custom_get_lesson_details

_lms_utils.get_lesson_details = custom_get_lesson_details

# Disable upstream daily live class reminder job — replaced by our cron-based
# configurable system in os_lms.os_lms.live_class_reminders.
import lms.lms.doctype.lms_live_class.lms_live_class as _upstream_live_class


def _noop_upstream_live_class_reminder():
	return None


_upstream_live_class.send_live_class_reminder = _noop_upstream_live_class_reminder



#def get_request_site_address(full_address=False):
#    return "https://overside.eu.ngrok.io"
#import frappe.utils as _frappe_utils
#_frappe_utils.get_request_site_address = get_request_site_address


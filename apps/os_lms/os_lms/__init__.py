__version__ = "0.0.1"

# Monkey-patch SMTPServer.session property
import os_lms.overrides.smtp  # noqa: F401

# Monkey-patch get_lesson_details to include index_status and indexed_at
import lms.lms.utils as _lms_utils
from os_lms.os_lms.override_utils import custom_get_lesson_details

_lms_utils.get_lesson_details = custom_get_lesson_details

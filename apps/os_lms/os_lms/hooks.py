from . import __version__ as app_version

app_name = "os_lms"
app_title = "OS LMS"
app_publisher = "ELITE"
app_description = "ELITE OS LMS - Extension for Frappe LMS"
app_email = "info@overside.it"
app_license = "MIT"

# activate debug if needed
before_request = ["os_lms.debug.active_debug"]

# forse to set italian language
after_migrate = ["os_lms.setup.ensure_italian_language"]

# fix error email check content MAX SIZE 
override_doctype_class = {
    "Email Account": "os_lms.overrides.email_account.CustomEmailAccount"
}


doc_events = {
    "Badge": {
        # fix bug cache after saving badge
        "after_insert": "os_lms.badge_utils.clear_cache_on_badge_create"
    }
}

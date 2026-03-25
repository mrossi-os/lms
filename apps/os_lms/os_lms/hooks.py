from . import __version__ as app_version

app_name = "os_lms"
app_title = "OS LMS"
app_publisher = "ELITE"
app_description = "ELITE OS LMS - Extension for Frappe LMS"
app_email = "info@overside.it"
app_license = "MIT"
required_apps = ["lms"]


base_template = "templates/base.html"


# activate debug if needed
before_request = ["os_lms.debug.active_debug"]

# forse to set italian language
after_migrate = [
    "os_lms.setup.ensure_italian_language",
    "os_lms.setup.remove_deprecated_custom_fields",
    "os_lms.setup.create_custom_fields",
    "os_lms.setup.create_redis_index",
]

# fix error email check content MAX SIZE
override_doctype_class = {
    "Email Account": "os_lms.overrides.email_account.CustomEmailAccount",
    "Data Import": "os_lms.overrides.data_import.CustomDataImport",
}
# override sqlite search to add custom doctypes
sqlite_search = ["os_lms.overrides.sqlite.CustomLearningSearch"]

# override api
override_whitelisted_methods = {
    "lms.lms.api.get_sidebar_settings": "os_lms.os_lms.override_api.get_sidebar_settings",
    "lms.command_palette.search_sqlite": "os_lms.os_lms.override_api.search_sqlite",
    "lms.lms.utils.get_course_details": "os_lms.os_lms.override_utils.get_course_details",
    "lms.lms.utils.get_lesson_creation_details": "os_lms.os_lms.override_utils.get_lesson_creation_details",
    "lms.lms.utils.get_batch_details": "os_lms.os_lms.override_utils.get_batch_details", 
}

fixtures = [
    {
        "dt": "Custom Field",
        "filters": [
            ["dt", "in", ["LMS Program", "LMS Settings", "Course Lesson", "LMS Course", "LMS Batch"]]
        ],
    }
]


doc_events = {
    "Badge": {
        # fix bug cache after saving badge
        "after_insert": "os_lms.badge_utils.clear_cache_on_badge_create"
    }
}


scheduler_events = {
    "daily": [
        "os_lms.os_lms.ai.scheduler.sync_stale_materials",
    ],
}

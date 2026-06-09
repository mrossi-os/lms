from . import __version__ as app_version

app_name = "os_lms"
app_title = "OS LMS"
app_publisher = "ELITE"
app_description = "ELITE OS LMS - Extension for Frappe LMS"
app_email = "info@overside.it"
app_license = "MIT"
required_apps = ["lms"]


base_template = "templates/base.html"


# Inject Brand Customize CSS in the desk <head>. For website pages (login,
# Vue SPA wrapper) the link is appended at the end of <head> directly in
# templates/base.html, so it remains the last stylesheet and overrides
# defaults from frontend/src/styles/theme/elite/variables.css.
app_include_css = ["/api/method/os_lms.os_lms.branding.brand_css"]


# activate debug if needed
before_request = ["os_lms.debug.active_debug"]

# forse to set italian language
after_migrate = [
    "os_lms.setup.ensure_italian_language",
    "os_lms.setup.remove_deprecated_custom_fields",
    "os_lms.setup.create_custom_fields",
    "os_lms.setup.setup_valutatore_role_and_permissions",
    "os_lms.setup.create_redis_index",
    "os_lms.setup.rebuild_search_index",
    "os_lms.setup.seed_judge_prompts",
    "os_lms.setup.seed_prompt_templates",
]

# fix error email check content MAX SIZE
override_doctype_class = {
    "Email Account": "os_lms.overrides.email_account.CustomEmailAccount",
    "Data Import": "os_lms.overrides.data_import.CustomDataImport",
    "LMS Live Class": "os_lms.overrides.lms_live_class.CustomLMSLiveClass",
}

# Document-level permission gating for the simulation feature. The list_view
# query filter lives in get_permission_query_conditions on each doctype.
permission_query_conditions = {
    "LMSA Simulation Scenario": (
        "os_lms.os_lms.doctype.lmsa_simulation_scenario.lmsa_simulation_scenario.get_permission_query_conditions"
    ),
    "LMSA Simulation Session": (
        "os_lms.os_lms.doctype.lmsa_simulation_session.lmsa_simulation_session.get_permission_query_conditions"
    ),
    "LMSA Simulation Turn": (
        "os_lms.os_lms.doctype.lmsa_simulation_turn.lmsa_simulation_turn.get_permission_query_conditions"
    ),
    "LMSA Simulation Debrief": (
        "os_lms.os_lms.doctype.lmsa_simulation_debrief.lmsa_simulation_debrief.get_permission_query_conditions"
    ),
    # Scope list views to the batches a "Valutatore" is assigned to.
    "LMS Batch Enrollment": "os_lms.os_lms.valutatore.batch_enrollment_query_conditions",
    "LMS Live Class": "os_lms.os_lms.valutatore.live_class_query_conditions",
    "LMS Quiz Submission": "os_lms.os_lms.valutatore.quiz_submission_query_conditions",
    "LMS Assignment Submission": "os_lms.os_lms.valutatore.assignment_submission_query_conditions",
}
has_permission = {
    "LMSA Simulation Scenario": (
        "os_lms.os_lms.doctype.lmsa_simulation_scenario.lmsa_simulation_scenario.has_permission"
    ),
    "LMSA Simulation Session": (
        "os_lms.os_lms.doctype.lmsa_simulation_session.lmsa_simulation_session.has_permission"
    ),
    "LMSA Simulation Turn": (
        "os_lms.os_lms.doctype.lmsa_simulation_turn.lmsa_simulation_turn.has_permission"
    ),
    "LMSA Simulation Debrief": (
        "os_lms.os_lms.doctype.lmsa_simulation_debrief.lmsa_simulation_debrief.has_permission"
    ),
    # Veto by-name access to submissions outside the valutatore's batches.
    "LMS Quiz Submission": "os_lms.os_lms.valutatore.submission_has_permission",
    "LMS Assignment Submission": "os_lms.os_lms.valutatore.submission_has_permission",
}
# override sqlite search to add custom doctypes
sqlite_search = ["os_lms.overrides.sqlite.CustomLearningSearch"]

# override api
override_whitelisted_methods = {
    "lms.lms.api.get_sidebar_settings": "os_lms.os_lms.override_api.get_sidebar_settings",
    "lms.lms.api.get_lms_settings":"os_lms.os_lms.override_api.get_lms_settings",
    "lms.lms.api.get_announcements": "os_lms.os_lms.override_api.get_announcements",
    "lms.lms.api.get_notifications": "os_lms.os_lms.override_api.get_notifications",
    "lms.lms.api.get_user_info": "os_lms.os_lms.override_api.get_user_info",
    "lms.lms.api.save_role": "os_lms.os_lms.override_api.save_role",

    "lms.lms.utils.get_course_details": "os_lms.os_lms.override_utils.get_course_details",
    "lms.lms.utils.get_course_outline": "os_lms.os_lms.override_utils.get_course_outline",
    "lms.lms.utils.get_courses": "os_lms.os_lms.override_utils.get_courses",
    "lms.lms.utils.get_lesson_creation_details": "os_lms.os_lms.override_utils.get_lesson_creation_details",
    "lms.lms.utils.get_lesson": "os_lms.os_lms.override_utils.get_lesson",
    "lms.lms.utils.get_batch_details": "os_lms.os_lms.override_utils.get_batch_details",
    "lms.lms.utils.get_roles": "os_lms.os_lms.override_utils.get_roles",

    
    "lms.command_palette.search_sqlite": "os_lms.os_lms.override_api.search_sqlite",
    # Redirect the Google Calendar OAuth callback to the LMS SPA instead of the desk.
    "frappe.integrations.doctype.google_calendar.google_calendar.google_callback": "os_lms.os_lms.google_calendar.google_callback",
}

# override email
standard_email_override = {
    "login_via_key": "os_lms/templates/emails/login_via_key.html"
}

# Desk client scripts: add Export/Import-with-permissions buttons to Role.
doctype_js = {"Role": "public/js/role.js"}
doctype_list_js = {"Role": "public/js/role_list.js"}

fixtures = [
    {
        "dt": "Custom Field",
        "filters": [
            [
                "dt",
                "in",
                [
                    "LMS Program",
                    "LMS Settings",
                    "Course Lesson",
                    "LMS Course",
                    "LMS Batch",
                    "LMS Live Class",
                    "User",
                    "Email Template",
                ],
            ]
        ],
    }
]


doc_events = {
    "Badge": {
        # fix bug cache after saving badge
        "after_insert": "os_lms.badge_utils.clear_cache_on_badge_create"
    },
    "Course Lesson": {
        "before_save": "os_lms.events.lesson.reset_index_status_on_content_change",
        "on_trash": "os_lms.events.lesson.cleanup_lesson_links",
    },
    "User": {
        "after_insert": "os_lms.auth.mark_first_login",
        "on_trash": "os_lms.events.user.delete_lms_user_links",
    },
    "LMS Live Class": {
        "before_save": "os_lms.os_lms.live_class_reminders.reset_sent_at",
    },
    "LMS Batch": {
        # Keep the "Valutatore" role aligned with the batch `valutatori` field.
        "on_update": "os_lms.os_lms.valutatore.sync_batch_valutatore_roles",
        "on_trash": "os_lms.os_lms.valutatore.cleanup_batch_valutatore_roles",
    },
    "Brand Customize": {
        "on_update": "os_lms.os_lms.branding.clear_brand_cache",
    },
    "LMSA Simulation Session": {
        "before_insert": "os_lms.os_lms.ai.simulations.orchestrator.validate_quota",
    },
}


on_session_creation = ["os_lms.auth.on_session_creation"]


scheduler_events = {
    "daily": [
        "os_lms.os_lms.ai.ingestion.scheduler.reindex_lesson_content",
    ],
    "cron": {
        "*/15 * * * *": [
            "os_lms.os_lms.live_class_reminders.send_live_class_reminders",
        ],
    },
}

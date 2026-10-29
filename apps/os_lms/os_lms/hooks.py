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
# desk.css comes last so its rules override the Brand Customize variables.
app_include_css = [
    "/api/method/os_lms.os_lms.branding.brand_css",
    "/assets/os_lms/css/desk.css",
]


# activate debug if needed
before_request = [
    "os_lms.debug.active_debug",
    # Must stay a before_request hook: it runs before Frappe's validate_auth and
    # the lms.auth hook (see os_lms/os_lms/elite_api/auth.py).
    "os_lms.os_lms.elite_api.auth.authenticate_request",
]
after_request = ["os_lms.os_lms.elite_api.auth.record_request"]

# Background jobs start with lang = conf.lang (unset) -> "en", so every _()
# evaluated in a worker returns English even though the site runs in Italian.
before_job = ["os_lms.os_lms.utils.set_job_language"]

# forse to set italian language
after_migrate = [
    "os_lms.setup.ensure_italian_language",
    "os_lms.setup.remove_deprecated_custom_fields",
    "os_lms.setup.create_custom_fields",
    "os_lms.setup.setup_valutatore_role_and_permissions",
    # Before the Gestore grants: they include the LMSA Simulation Limits single.
    "os_lms.os_lms.ai.simulations.limits.ensure_simulation_limits",
    "os_lms.setup.setup_gestore_role_permissions",
    "os_lms.setup.setup_docente_role_permissions",
    "os_lms.setup.setup_course_creator_batch_permissions",
    "os_lms.setup.setup_quiz_violation_log_permissions",
    "os_lms.setup.setup_elite_api_client",
    "os_lms.setup.create_redis_index",
    "os_lms.setup.rebuild_search_index",
    # Migration must run BEFORE seed_prompt_templates so operator-customised
    # judge prompts ported from the deprecated LMSA Judge Prompt doctype
    # take precedence over the freshly-seeded defaults.
    "os_lms.setup.migrate_judge_prompts_to_template",
    "os_lms.setup.seed_prompt_templates",
    # The OpenAI/Vimeo keys became Password fields: encrypt a value still in clear.
    "os_lms.os_lms.ai.utils.api_keys.encrypt_plaintext_api_keys",
    # The old Google Calendar callback wrote the OAuth tokens in clear.
    "os_lms.os_lms.google_calendar.encrypt_plaintext_tokens",
]

# fix error email check content MAX SIZE
override_doctype_class = {
    "Email Account": "os_lms.overrides.email_account.CustomEmailAccount",
    "Data Import": "os_lms.overrides.data_import.CustomDataImport",
    "LMS Live Class": "os_lms.overrides.lms_live_class.CustomLMSLiveClass",
    # Suppress the internal "certified" email for TrueSkills-issued courses.
    "LMS Certificate": "os_lms.overrides.lms_certificate.CustomLMSCertificate",
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
    "LMSA Evaluation Schema": (
        "os_lms.os_lms.doctype.lmsa_evaluation_schema.lmsa_evaluation_schema.get_permission_query_conditions"
    ),
    # A Course Creator reads the AI tutor conversations of the courses it teaches.
    "LMSA Query Log": (
        "os_lms.os_lms.doctype.lmsa_query_log.lmsa_query_log.get_permission_query_conditions"
    ),
    # Scope list views to the batches a "Valutatore" is assigned to.
    "LMS Batch Enrollment": "os_lms.os_lms.valutatore.batch_enrollment_query_conditions",
    "LMS Live Class": "os_lms.os_lms.valutatore.live_class_query_conditions",
    "LMS Quiz Submission": "os_lms.os_lms.valutatore.quiz_submission_query_conditions",
    # The proctoring log (and its camera stills, which inherit its audience) follows the
    # quiz submission it belongs to.
    "LMS Quiz Violation Log": "os_lms.os_lms.valutatore.violation_log_query_conditions",
    "LMS Assignment Submission": "os_lms.os_lms.valutatore.assignment_submission_query_conditions",
    # Scope the read-only course dashboard data to the valutatore's courses.
    "LMS Enrollment": "os_lms.os_lms.valutatore.enrollment_query_conditions",
    "LMS Course Progress": "os_lms.os_lms.valutatore.course_progress_query_conditions",
    # Staff other than Moderator list the certificates of the courses they teach.
    "LMS Certificate": "os_lms.os_lms.certificate_permissions.get_permission_query_conditions",
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
    "LMSA Evaluation Schema": (
        "os_lms.os_lms.doctype.lmsa_evaluation_schema.lmsa_evaluation_schema.has_permission"
    ),
    "LMSA Query Log": "os_lms.os_lms.doctype.lmsa_query_log.lmsa_query_log.has_permission",
    # Course Creator and Docente issue certificates only for the courses they teach.
    "LMS Certificate": "os_lms.os_lms.certificate_permissions.has_permission",
    # Veto by-name access to submissions outside the valutatore's batches.
    "LMS Quiz Submission": "os_lms.os_lms.valutatore.quiz_submission_has_permission",
    "LMS Quiz Violation Log": "os_lms.os_lms.valutatore.violation_log_has_permission",
    "LMS Assignment Submission": "os_lms.os_lms.valutatore.submission_has_permission",
    # Veto by-name access to course-scoped rows outside the valutatore's courses.
    "LMS Enrollment": "os_lms.os_lms.valutatore.course_scoped_has_permission",
    "LMS Course Progress": "os_lms.os_lms.valutatore.course_scoped_has_permission",
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
    "lms.lms.api.get_all_users": "os_lms.os_lms.override_api.get_all_users",
    "lms.lms.api.search_users_by_role": "os_lms.os_lms.override_api.search_users_by_role",
    "lms.lms.api.get_members": "os_lms.os_lms.override_api.get_members",
    "lms.lms.api.get_member": "os_lms.os_lms.override_api.get_member",
    "lms.lms.api.save_role": "os_lms.os_lms.override_api.save_role",
    # Accounts holding System Manager or Gestore are deleted only by a System Manager.
    "lms.lms.api.delete_member": "os_lms.os_lms.override_api.delete_member",
    # The home live classes carry the gated join link, never the Zoom host link.
    "lms.lms.api.get_my_live_classes": "os_lms.os_lms.override_api.get_my_live_classes",
    # Only the exercise's authors delete it, leaving a Deleted Document.
    "lms.lms.api.delete_programming_exercise": "os_lms.os_lms.override_api.delete_programming_exercise",

    "lms.lms.utils.get_course_details": "os_lms.os_lms.override_utils.get_course_details",
    "lms.lms.utils.get_course_outline": "os_lms.os_lms.override_utils.get_course_outline",
    "lms.lms.utils.get_courses": "os_lms.os_lms.override_utils.get_courses",
    "lms.lms.utils.get_course_categories": "os_lms.os_lms.override_utils.get_course_categories",
    "lms.lms.utils.get_batches": "os_lms.os_lms.override_utils.get_batches",
    "lms.lms.utils.get_lesson_creation_details": "os_lms.os_lms.override_utils.get_lesson_creation_details",
    "lms.lms.utils.get_lesson": "os_lms.os_lms.override_utils.get_lesson",
    "lms.lms.utils.get_batch_details": "os_lms.os_lms.override_utils.get_batch_details",
    "lms.lms.utils.get_roles": "os_lms.os_lms.override_utils.get_roles",
    "lms.lms.utils.get_program_details": "os_lms.os_lms.override_utils.get_program_details",
    # Reviews only of a course the caller may see, and without the authors' emails.
    "lms.lms.utils.get_reviews": "os_lms.os_lms.override_utils.get_reviews",
    # Discussions only of the doctypes the access check knows, spelled exactly.
    "lms.lms.utils.get_discussion_topics": "os_lms.os_lms.override_utils.get_discussion_topics",
    "lms.lms.utils.get_discussion_replies": "os_lms.os_lms.override_utils.get_discussion_replies",
    # Frappe's website method saved replies with ignore_permissions: anybody rewrote
    # anybody's reply by name (OWASP M-06).
    "frappe.website.doctype.discussion_topic.discussion_topic.submit_discussion": "os_lms.os_lms.override_utils.submit_discussion",
    # The proctoring photo log is not shown to the per-batch Valutatore (v2.63.0).
    "lms.lms.doctype.lms_quiz.lms_quiz.get_quiz_violation_logs": "os_lms.os_lms.valutatore.get_quiz_violation_logs",
    # Sign-up limits that really block, and the same answer for registered emails.
    "lms.lms.user.sign_up": "os_lms.os_lms.signup.sign_up",
    "frappe.core.doctype.user.user.sign_up": "os_lms.os_lms.signup.frappe_sign_up",
    # SCORM details complete a lesson only on a SCORM chapter, not any lesson.
    "lms.lms.doctype.course_lesson.course_lesson.save_progress": "os_lms.os_lms.lesson_progress.save_progress",
    # A lesson is completed only once the server handed it out (audit H-1): the quiz
    # and assignment path and the SCORM player go through the same guard.
    "lms.lms.api.mark_lesson_progress": "os_lms.os_lms.lesson_progress.mark_lesson_progress",
    "lms.lms.doctype.course_chapter.course_chapter.get_scorm_playback": "os_lms.os_lms.lesson_progress.get_scorm_playback",
    # The course ZIP packs only the private files the exporter could download.
    "lms.lms.api.export_course_as_zip": "os_lms.os_lms.course_export.export_course_as_zip",

    
    "lms.command_palette.search_sqlite": "os_lms.os_lms.override_api.search_sqlite",
    # Hand out a template matching the columns our import expanders expect; the
    # stock one lists the doctype fields and would skip user creation.
    "frappe.core.doctype.data_import.data_import.download_template": "os_lms.data_import.template.download_template",
    # The login page calls Frappe's method: ours sends the os_lms email template and
    # does not reveal whether the address has an account.
    "frappe.www.login.send_login_link": "os_lms.www.login.send_login_link",
    # "Forgot password" gives the same answer whether or not the address has an
    # account, and never names the account holder.
    "frappe.core.doctype.user.user.reset_password": "os_lms.www.login.reset_password",
    # Google Calendar OAuth: a one-time state bound to whoever started the consent,
    # and the callback lands in the LMS SPA instead of the desk.
    "frappe.integrations.doctype.google_calendar.google_calendar.authorize_access": "os_lms.os_lms.google_calendar.authorize_access",
    "frappe.integrations.doctype.google_calendar.google_calendar.google_callback": "os_lms.os_lms.google_calendar.google_callback",
}

# Whitelisted methods our frontend calls that this Frappe release does not ship.
# Unlike the overrides above there is no original to wrap; test_override_signatures
# fails once Frappe ships one, so the shim gets removed instead of shadowing it.
framework_method_shims = {
    # frappe-ui's telemetry plugin (Frappe develop only): 417 on every SPA load without it.
    "frappe.utils.telemetry.pulse.client.boot_config": "os_lms.os_lms.framework_shims.telemetry_boot_config",
}
override_whitelisted_methods.update(framework_method_shims)

# override email
standard_email_override = {
    "login_via_key": "os_lms/templates/emails/login_via_key.html"
}

# Desk client scripts attached to LMS doctypes.
# - Role: Export/Import-with-permissions buttons.
# - LMS Certificate: TrueSkills Issue Log quick link.
# - User: "Reset progressi corso" button (admins) to retake a course from scratch.
doctype_js = {
    "Role": "public/js/role.js",
    "LMS Certificate": "public/js/lms_certificate.js",
    "User": "public/js/user.js",
}
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
                    "LMS Quiz",
                    "LMS Lesson Note",
                    "User",
                    "Email Template",
                ],
            ]
        ],
    }
]

# Upstream's orphaned invite page echoed ?invite_code= unescaped (reflected XSS);
# its backend is gone, so the route goes to the login page. Frappe also serves the
# page as /new-sign-up.html, which a plain "/new-sign-up" source does not match.
website_redirects = [
    {"source": r"/new-sign-up(\.html)?", "target": "/login"},
]


doc_events = {
    "Badge": {
        # fix bug cache after saving badge
        "after_insert": "os_lms.badge_utils.clear_cache_on_badge_create"
    },
    "Course Lesson": {
        # An "upload" block may only point to an uploaded file or an external link.
        "validate": "os_lms.events.lesson.validate_upload_blocks",
        "before_save": "os_lms.events.lesson.reset_index_status_on_content_change",
        "on_trash": "os_lms.events.lesson.cleanup_lesson_links",
        # OSLMS-CUSTOM: re-index the AI tutor vectors when a lesson is renamed
        "after_rename": "os_lms.events.lesson.reindex_after_rename",
    },
    "User": {
        # A Gestore cannot write the permlevel-1 roles of a user it imports:
        # give those users the "LMS Student" role Frappe strips from them.
        "validate": "os_lms.events.user.grant_student_role_on_gestore_import",
        "after_insert": "os_lms.auth.mark_first_login",
        "on_trash": "os_lms.events.user.delete_lms_user_links",
    },
    "LMS Live Class": {
        "before_save": "os_lms.os_lms.live_class_reminders.reset_sent_at",
    },
    "LMS Quiz Submission": {
        # One row per question and at most 100%: a repeated question inflated the score.
        "validate": "os_lms.events.quiz_submission.validate_quiz_rows",
    },
    "LMS Assignment Submission": {
        # Once graded, a student can no longer change the answer the grade refers to.
        "validate": "os_lms.events.assignment_submission.freeze_graded_submission",
    },
    "LMS Batch": {
        # Grant the "Valutatore" role to the users listed in the batch
        # `valutatori` field. Grant-only: the role is never revoked automatically
        # (see os_lms.os_lms.valutatore.sync_batch_valutatore_roles).
        "on_update": "os_lms.os_lms.valutatore.sync_batch_valutatore_roles",
        # The picker offers only non-students; saving checks it too.
        "validate": "os_lms.os_lms.valutatore.validate_batch_valutatori",
    },
    "Brand Customize": {
        "on_update": "os_lms.os_lms.branding.clear_brand_cache",
    },
    "LMSA Simulation Session": {
        "before_insert": "os_lms.os_lms.ai.simulations.orchestrator.validate_quota",
    },
    "LMS Certificate": {
        "after_insert": "os_lms.os_lms.trueskills.emission.enqueue_issue",
    },
    "LMS Settings": {
        # Only a System Manager or a Gestore may repoint the TrueSkills connection,
        # and only to a public https host.
        "validate": "os_lms.os_lms.trueskills.settings.validate_lms_settings",
    },
    "LMS Course": {
        # Refuse a TrueSkill template whose required data the emission never sends.
        "validate": "os_lms.os_lms.trueskills.api.validate_course_template",
    },
    "Notification Log": {
        # Upstream ships the quiz-score alert with an empty link, which makes the
        # notification a dead click. Fill the destination in before the log is
        # written, so both the panel and the push below inherit it.
        "before_insert": "os_lms.os_lms.notification_links.set_missing_link",
        # Mirror each in-app notification to the user's mobile devices via FCM.
        "after_insert": "os_lms.os_lms.push_notifications.on_notification_log_insert",
    },
    "Activity Log": {
        # Accumulate per-user access stats (LMSA User Access) from login events.
        # Captures successes and failures alike, independently of log retention.
        "after_insert": "os_lms.os_lms.access_tracking.on_activity_log_insert",
    },
}


on_session_creation = ["os_lms.auth.on_session_creation"]


# Retention (days) offered to Log Settings; os_lms.setup.setup_elite_api_client
# registers it, since Log Settings only reads this hook when it is saved.
default_log_clearing_doctypes = {
    "Elite API Access Log": 90,
    "OS CSP Violation": 90,
}

scheduler_events = {
    "hourly": [
        "os_lms.os_lms.trueskills.scheduler.reconcile_pending",
    ],
    "daily": [
        "os_lms.os_lms.ai.ingestion.scheduler.reindex_lesson_content",
    ],
    "cron": {
        # Email the Administrator user and the Gestori past the attack thresholds.
        "*/5 * * * *": [
            "os_lms.os_lms.security_alerts.check_attack_thresholds",
        ],
        "*/15 * * * *": [
            "os_lms.os_lms.live_class_reminders.send_live_class_reminders",
        ],
        "*/10 * * * *": [
            "os_lms.os_lms.ai.simulations.tasks.reap_stale_sessions",
        ],
    },
}

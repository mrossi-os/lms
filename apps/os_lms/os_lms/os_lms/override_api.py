import frappe


from lms.lms.api import get_sidebar_settings as _original_get_sidebar_settings
from lms.lms.api import get_lms_settings as _original_get_lms_settings
from lms.lms.api import get_user_info as _original_get_user_info


from lms.command_palette import (
    get_instructor_info,
    can_access_course,
    can_access_batch,
    can_access_job,
)


@frappe.whitelist(allow_guest=True)
def get_sidebar_settings():

    result = _original_get_sidebar_settings()
    if isinstance(result, dict):
        lms_settings = frappe.get_single("LMS Settings")
        for field in ("programs", "home", "search", "quizzes", "assignments"):
            result[field] = lms_settings.get(field)

    return result

@frappe.whitelist(allow_guest=True)
def get_lms_settings():
    result = _original_get_lms_settings()
    if isinstance(result, dict):
         result["ai_enabled"] = frappe.get_single("LMSA Settings").get("enabled")
    return result


@frappe.whitelist()
def get_user_info():
    result = _original_get_user_info()
    if result and frappe.session.user != "Guest":
        result["welcome_video_seen"] = bool(
            frappe.db.get_value("User", frappe.session.user, "welcome_video_seen")
        )
    return result


# region search_sqlite
@frappe.whitelist()
def search_sqlite(query: str):
    from os_lms.overrides.sqlite import CustomLearningSearch
    from lms.sqlite import LearningSearchIndexMissingError

    search = CustomLearningSearch()

    try:
        result = search.search(query)
    except LearningSearchIndexMissingError:
        return []

    return prepare_search_results_custom(result)


def prepare_search_results_custom(result: dict):
    from lms.command_palette import remove_duplicates

    groups = get_grouped_results_custom(result)

    out = []
    for key in groups:
        groups[key] = remove_duplicates(groups[key])
        groups[key].sort(key=lambda x: x.get("modified"), reverse=True)
        out.append({"title": key, "items": groups[key]})

    return out


def get_grouped_results_custom(result):
    roles = frappe.get_roles()
    groups = {}
    for r in result["results"]:
        doctype = r["doctype"]
        if doctype == "LMS Course" and can_access_course(r, roles):
            r["author_info"] = get_instructor_info(doctype, r)
            groups.setdefault("Courses", []).append(r)
        elif doctype == "LMS Batch" and can_access_batch(r, roles):
            r["author_info"] = get_instructor_info(doctype, r)
            groups.setdefault("Batches", []).append(r)
        elif doctype == "Job Opportunity" and can_access_job(r, roles):
            r["author_info"] = get_instructor_info(doctype, r)
            groups.setdefault("Job Opportunities", []).append(r)
        elif doctype == "LMS Program":
            groups.setdefault("Programs", []).append(r)
        elif doctype == "LMS Quiz":
            groups.setdefault("Quizzes", []).append(r)
        elif doctype == "LMS Assignment":
            groups.setdefault("Assignments", []).append(r)
        elif doctype == "Course Lesson" and can_access_lesson(r, roles):
            groups.setdefault("Lessons", []).append(r)
    return groups


def can_access_lesson(lesson, roles):
    """Learners see lessons of published courses; creators/moderators see all their own drafts too."""
    course = lesson.get("parent") or lesson.get("course")
    if not course:
        return False

    if "Moderator" in roles:
        return True

    course_info = frappe.db.get_value(
        "LMS Course", course, ["published", "owner"], as_dict=True
    )
    if not course_info:
        return False

    if course_info.published:
        return True

    user = frappe.session.user
    if course_info.owner == user:
        return True

    if "Course Creator" in roles and frappe.db.exists(
        "Course Instructor", {"parent": course, "instructor": user}
    ):
        return True

    return False


# endregion


@frappe.whitelist(allow_guest=True)
def get_new_courses():
	from lms.lms.utils import get_course_details

	courses = frappe.get_all(
		"LMS Course",
		{"published": 1},
		order_by="published_on desc, enrollments desc",
		limit=6,
		pluck="name",
	)
	return [get_course_details(c) for c in courses if get_course_details(c)]


@frappe.whitelist(allow_guest=True)
def get_most_followed_courses():
	from lms.lms.utils import get_course_details

	courses = frappe.get_all(
		"LMS Course",
		{"published": 1, "enrollments": [">", 0]},
		order_by="enrollments desc",
		limit=6,
		pluck="name",
	)
	return [get_course_details(c) for c in courses if get_course_details(c)]


@frappe.whitelist()
def get_notifications(filters: dict = None):
    from lms.lms.api import get_notifications as _original_get_notifications

    notifications = _original_get_notifications(filters)

    for notification in notifications:
        if notification.get("document_type") == "LMS Live Class":
            details = frappe.db.get_value(
                "LMS Live Class",
                notification["document_name"],
                ["title", "date as start_date", "time as start_time", "duration", "description as short_introduction", "batch_name"],
                as_dict=True,
            )
            if details:
                details["instructors"] = []
                details["video_link"] = None
                notification["document_details"] = details

    return notifications


@frappe.whitelist()
def get_announcements(batch: str, start: int = 0, page_length: int = 10):
    """
    Override: per studenti, ritorna solo gli annunci in cui sono destinatari
    (recipients o cc). Moderatori/Batch Evaluator vedono tutto.
    Restituisce {data, total} per supportare la paginazione lato client.
    """
    from frappe import _

    roles = frappe.get_roles()
    is_batch_student = frappe.db.exists(
        "LMS Batch Enrollment", {"batch": batch, "member": frappe.session.user}
    )
    is_admin = "Moderator" in roles or "Batch Evaluator" in roles

    if not (is_batch_student or is_admin):
        frappe.throw(
            _("You do not have permission to access announcements for this batch."),
            frappe.PermissionError,
        )

    communications = frappe.get_all(
        "Communication",
        filters={
            "reference_doctype": "LMS Batch",
            "reference_name": batch,
        },
        fields=[
            "subject",
            "content",
            "recipients",
            "cc",
            "bcc",
            "communication_date",
            "sender",
            "sender_full_name",
        ],
        order_by="communication_date desc",
    )

    if not is_admin:
        user_email = frappe.session.user
        filtered = []
        for comm in communications:
            fields_combined = " ".join(
                filter(None, [comm.get("recipients"), comm.get("cc"), comm.get("bcc")])
            )
            if user_email in fields_combined:
                filtered.append(comm)
        communications = filtered

    total = len(communications)
    paginated = communications[start : start + page_length]

    for communication in paginated:
        communication.image = frappe.get_cached_value(
            "User", communication.sender, "user_image"
        )

    return {"data": paginated, "total": total}


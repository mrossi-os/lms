import frappe
from frappe.utils import cint


from lms.lms.api import get_sidebar_settings as _original_get_sidebar_settings
from lms.lms.api import get_lms_settings as _original_get_lms_settings
from lms.lms.api import get_user_info as _original_get_user_info
from lms.lms.api import save_role as _original_save_role


EXTRA_LMS_ROLES = ["Gestore", "Docente", "Valutatore"]


@frappe.whitelist()
def save_role(user: str, role: str, value: int):
    if role not in EXTRA_LMS_ROLES:
        return _original_save_role(user, role, value)

    frappe.only_for("Moderator")
    if cint(value):
        if not frappe.db.exists("Has Role", {"parent": user, "role": role}):
            doc = frappe.new_doc("Has Role")
            doc.parent = user
            doc.parenttype = "User"
            doc.parentfield = "roles"
            doc.role = role
            doc.save(ignore_permissions=True)
    else:
        frappe.db.delete("Has Role", {"parent": user, "role": role})
    frappe.clear_cache(user=user)
    return True


from lms.command_palette import (
    get_instructor_info,
    can_access_course,
    can_access_batch,
    can_access_job,
    can_create_batch,
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
         lmsa = frappe.get_single("LMSA Settings")
         result["ai_enabled"] = lmsa.get("enabled")
         result["simulations_enabled"] = bool(lmsa.get("simulations_enabled"))
         result["stt_enabled"] = bool(lmsa.get("stt_enabled"))
         result["tts_enabled"] = bool(lmsa.get("tts_enabled"))
         result["tts_autoplay_on_stt"] = bool(lmsa.get("tts_autoplay_on_stt"))
         result["realtime_enabled"] = bool(lmsa.get("realtime_enabled"))
         brand = frappe.get_cached_doc("Brand Customize")
         result["theme"] = brand.get("theme") or "light"
    return result


@frappe.whitelist()
def get_members(start: int = 0, search: str = None, role: str = "All"):
    """Wrap the base member list so the custom "Valutatore" role is reported.

    The base method hardcodes the four upstream LMS roles, so a member holding
    Valutatore came back without it: the Members settings modal then rendered the
    toggle as off for someone who already had the role. Only the returned roles
    are widened here — the `role` filter is still validated (and paginated) by
    the base method, so it keeps accepting the upstream values only.
    """
    from lms.lms.api import get_members as _original_get_members

    members = _original_get_members(start, search, role)
    if not members:
        return members

    valutatori = set(
        frappe.get_all(
            "Has Role",
            {
                "role": "Valutatore",
                "parenttype": "User",
                "parent": ["in", [member.name for member in members]],
            },
            pluck="parent",
        )
    )
    for member in members:
        if member.name in valutatori:
            member.roles = (member.roles or []) + ["Valutatore"]

    return members


# Roles the Members settings modal is allowed to grant: the four upstream LMS
# roles plus the custom ones handled by `save_role` above.
MANAGEABLE_ROLES = [
    "LMS Student",
    "Course Creator",
    "Batch Evaluator",
    "Moderator",
] + EXTRA_LMS_ROLES


@frappe.whitelist()
def create_member(
    email: str,
    roles: list[str],
    first_name: str | None = None,
    last_name: str | None = None,
) -> dict:
    """Create a member carrying exactly the selected roles.

    `lms.lms.user.add_lms_student_role` (a `before_insert` hook on User) grants
    "LMS Student" to every new user, so adding a member with only, say,
    "Valutatore" ticked used to leave them a student as well: the client only
    ever added the ticked roles on top of that implicit one. The whole role set
    is reconciled here, in the same request as the insert, so the new user ends
    up with the selected roles and nothing else.
    """
    frappe.only_for("Moderator")

    if isinstance(roles, str):
        roles = frappe.parse_json(roles)
    roles = [role for role in (roles or []) if role]
    if not roles:
        frappe.throw(frappe._("Select at least one role for the new member."))

    unknown = [role for role in roles if role not in MANAGEABLE_ROLES]
    if unknown:
        frappe.throw(
            frappe._("You do not have permission to grant this role: {0}").format(
                ", ".join(unknown)
            ),
            frappe.PermissionError,
        )

    user = frappe.get_doc(
        {
            "doctype": "User",
            "email": email,
            "first_name": first_name or None,
            "last_name": last_name or None,
        }
    ).insert()

    # Grant what was selected and drop what was not — including the "LMS Student"
    # role appended by the before_insert hook. save_role() is reused so the
    # "Batch Evaluator" keeps its Course Evaluator record in sync.
    for role in MANAGEABLE_ROLES:
        save_role(user.name, role, 1 if role in roles else 0)

    return {
        "name": user.name,
        "full_name": user.full_name,
        "user_image": user.user_image,
    }


@frappe.whitelist()
def get_all_users():
    # Broaden the role gate of the base method so the custom instructor/evaluator
    # roles can also fetch the user list (used for @mentions in discussions, etc.).
    # The base method only allows Moderator / Course Creator / Batch Evaluator,
    # which made a scoped "Valutatore" (and a "Docente") hit a 403 when opening a
    # discussion thread.
    frappe.only_for(
        ["Moderator", "Course Creator", "Batch Evaluator", "Docente", "Valutatore"]
    )
    users = frappe.get_all(
        "User",
        {"enabled": 1},
        ["name", "full_name", "user_image"],
    )
    return {user.name: user for user in users}


@frappe.whitelist()
def get_user_info():
    result = _original_get_user_info()
    if result and frappe.session.user != "Guest":
        result["welcome_video_seen"] = bool(
            frappe.db.get_value("User", frappe.session.user, "welcome_video_seen")
        )
        # A "Docente" acts as a global instructor: it gets the same capabilities
        # as the instructor (Course Creator) role, applied to every course/batch
        # (see can_modify_course / can_modify_batch and the frontend isAdmin gates).
        is_docente = "Docente" in result.get("roles", [])
        result["is_docente"] = is_docente
        if is_docente:
            result["is_instructor"] = True
            result["is_student"] = False
        # A "Valutatore" is scoped to specific batches (see the `valutatori` field
        # on LMS Batch). This flag only lets the SPA open the global submission
        # list pages; the actual data is scoped per-batch in os_lms.os_lms.valutatore.
        is_valutatore = "Valutatore" in result.get("roles", [])
        result["is_valutatore"] = is_valutatore
        if is_valutatore:
            result["is_student"] = False
        # Gate for the student-statistics export page. Delegated to the single
        # source of truth in os_lms.os_lms.api so the SPA link and the endpoints
        # can never disagree (imported locally to avoid an import cycle).
        from os_lms.os_lms.api import can_export_student_stats

        result["can_export_stats"] = can_export_student_stats()
        # Course counters shown on the mobile profile page:
        # "Corsi attivi" = enrollments still in progress, "Completati" = enrollments
        # with full progress. progress is a Float (0-100) on LMS Enrollment.
        result["enrollment_count"] = frappe.db.count(
            "LMS Enrollment",
            {"member": frappe.session.user, "progress": ["<", 100]},
        )
        result["course_count"] = frappe.db.count(
            "LMS Enrollment",
            {"member": frappe.session.user, "progress": [">=", 100]},
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
    # Only learners need it, and only when a batch actually matched the query.
    own_batches = (
        get_own_batches()
        if not can_create_batch(roles)
        and any(r["doctype"] == "LMS Batch" for r in result["results"])
        else set()
    )
    # A quiz result carries neither its course nor its lesson, so resolve both
    # before filtering: the course decides who may see it, the lesson where the
    # learner is sent.
    quiz_placements = get_quiz_placements(
        [r["name"] for r in result["results"] if r["doctype"] == "LMS Quiz"]
    )
    own_courses = (
        get_own_courses()
        if quiz_placements and not can_manage_assessments(roles)
        else set()
    )

    for r in result["results"]:
        doctype = r["doctype"]
        if doctype == "LMS Course" and can_access_course(r, roles):
            r["author_info"] = get_instructor_info(doctype, r)
            groups.setdefault("Courses", []).append(r)
        elif doctype == "LMS Batch" and can_access_batch_custom(r, roles, own_batches):
            r["author_info"] = get_instructor_info(doctype, r)
            groups.setdefault("Batches", []).append(r)
        elif doctype == "Job Opportunity" and can_access_job(r, roles):
            r["author_info"] = get_instructor_info(doctype, r)
            groups.setdefault("Job Opportunities", []).append(r)
        elif doctype == "LMS Program" and can_access_program(r, roles):
            groups.setdefault("Programs", []).append(r)
        elif doctype == "LMS Quiz" and can_access_quiz(
            quiz_placements.get(r["name"]), roles, own_courses
        ):
            r.update(quiz_placements.get(r["name"]) or {})
            groups.setdefault("Quizzes", []).append(r)
        elif doctype == "LMS Assignment" and can_manage_assessments(roles):
            groups.setdefault("Assignments", []).append(r)
        elif doctype == "Course Lesson" and can_access_lesson(r, roles):
            groups.setdefault("Lessons", []).append(r)

    add_lesson_positions(groups.get("Lessons"))
    return groups


def get_lesson_positions(names):
    """Map each lesson to its course and to the numbers its SPA route needs.

    The route is /courses/:courseName/learn/:chapterNumber-:lessonNumber, where
    both numbers are the 1-based idx of the child rows (same convention as
    ``lms.lms.api.mark_lesson_progress``). Resolved in bulk so the endpoint keeps
    a constant number of queries regardless of how many results matched.
    """
    names = [name for name in dict.fromkeys(names) if name]
    if not names:
        return {}

    details = frappe.get_all(
        "Course Lesson",
        filters={"name": ["in", names]},
        fields=["name", "course", "chapter"],
    )
    if not details:
        return {}

    chapters = [d.chapter for d in details if d.chapter]
    chapter_rows = (
        frappe.get_all(
            "Chapter Reference",
            filters={"chapter": ["in", chapters]},
            fields=["parent", "chapter", "idx"],
        )
        if chapters
        else []
    )
    chapter_idx = {}
    for row in chapter_rows:
        chapter_idx.setdefault((row.parent, row.chapter), row.idx)

    lesson_idx = {}
    for row in frappe.get_all(
        "Lesson Reference",
        filters={"lesson": ["in", names]},
        fields=["parent", "lesson", "idx"],
    ):
        lesson_idx.setdefault((row.parent, row.lesson), row.idx)

    return {
        d.name: {
            "course": d.course,
            "chapter_number": chapter_idx.get((d.course, d.chapter)),
            "lesson_number": lesson_idx.get((d.chapter, d.name)),
        }
        for d in details
    }


def add_lesson_positions(lessons):
    """Attach to each lesson result the numbers its route needs."""
    if not lessons:
        return

    positions = get_lesson_positions([lesson["name"] for lesson in lessons])
    for lesson in lessons:
        lesson.update(positions.get(lesson["name"]) or {})


def get_quiz_placements(names):
    """Course and hosting lesson of each quiz, with that lesson's route numbers.

    Both are plain fields on LMS Quiz. The course decides whether a learner may
    see the quiz at all, the lesson is where the learner is sent: opening the
    quiz inside its lesson keeps the course rules — sequential unlocking
    included — in force, which a direct link to the quiz page would bypass.
    """
    if not names:
        return {}

    quizzes = frappe.get_all(
        "LMS Quiz",
        filters={"name": ["in", list(dict.fromkeys(names))]},
        fields=["name", "course", "lesson"],
    )
    positions = get_lesson_positions([q.lesson for q in quizzes])

    placements = {}
    for quiz in quizzes:
        placement = {"course": quiz.course, "lesson": quiz.lesson}
        placement.update(positions.get(quiz.lesson) or {})
        # The lesson, when there is one, is the authority on the course.
        placement["course"] = placement.get("course") or quiz.course
        placements[quiz.name] = placement

    return placements


def can_manage_assessments(roles):
    """Mirror the gate of the SPA pages a quiz or assignment result leads to.

    ``QuizForm`` and ``Assignments`` bounce anyone who is not a moderator or an
    instructor back to the course list, so those results have no destination for
    a learner. They were also unfiltered until now, and the index stores an
    assignment's *question text* as its content: without this check any logged
    in user could read exam questions straight out of the search results.
    "Docente" is the project's global instructor role (see get_user_info).
    """
    return "Moderator" in roles or "Course Creator" in roles or "Docente" in roles


def can_access_quiz(placement, roles, own_courses):
    """Managers see every quiz; a learner only the quizzes of their own courses.

    A quiz with no course is a draft no lesson uses yet, so it stays with the
    managers. For everyone else the enrolment is the criterion, mirroring the
    lesson the quiz lives in: a learner who may open the lesson may find the
    quiz it contains.
    """
    if can_manage_assessments(roles):
        return True

    course = (placement or {}).get("course")
    return bool(course) and course in own_courses


def get_own_courses():
    """Courses the current user is enrolled in."""
    return set(
        frappe.get_all(
            "LMS Enrollment", filters={"member": frappe.session.user}, pluck="course"
        )
    )


def can_access_program(program, roles):
    """Published programs are browsable by anyone; drafts stay with their authors."""
    if can_manage_assessments(roles):
        return True

    return bool(program.get("published"))


def get_own_batches():
    """Batches the current user takes part in, as a learner or as their valutatore.

    Same two memberships ``get_batch_details`` accepts to serve the batch page,
    so search never offers a result the batch page would then refuse.
    """
    user = frappe.session.user
    batches = set(
        frappe.get_all("LMS Batch Enrollment", filters={"member": user}, pluck="batch")
    )
    batches.update(
        frappe.get_all(
            "LMS Batch Valutatore",
            filters={"parenttype": "LMS Batch", "valutatore": user},
            pluck="parent",
        )
    )
    return batches


def can_access_batch_custom(batch, roles, own_batches):
    """Upstream's rule, minus the part that hides a batch from the people in it.

    ``lms.command_palette.can_access_batch`` clears a batch for a learner only
    while it is published and has not started yet, which is the rule for
    *enrolling* in one. The batch page is far more permissive:
    ``lms.lms.utils.get_batch_details`` serves it to enrolled students and to
    the batch valutatori whatever the published flag and the start date say.
    Search was therefore stricter than the page it links to, and the class a
    student attends was unfindable by name — outright invisible while the batch
    stayed unpublished. Mirror the page instead. A batch the user has nothing to
    do with keeps upstream's behaviour.
    """
    if can_access_batch(batch, roles):
        return True

    return batch.get("name") in own_batches


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
    from lms.lms.utils import is_batch_valutatore

    roles = frappe.get_roles()
    is_batch_student = frappe.db.exists(
        "LMS Batch Enrollment", {"batch": batch, "member": frappe.session.user}
    )
    # A valutatore of this batch sees all its announcements (read-only, like an
    # admin); sending announcements stays restricted to Moderator/Batch Evaluator.
    is_admin = (
        "Moderator" in roles
        or "Batch Evaluator" in roles
        or is_batch_valutatore(batch)
    )

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


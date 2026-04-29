import frappe


@frappe.whitelist()
def set_lesson_as_current(course: str, lesson: str):
    """Update the current_lesson on the user's enrollment for the given course."""
    if not course or not lesson:
        frappe.throw("course and lesson are required", frappe.ValidationError)

    enrollment = frappe.db.get_value(
        "LMS Enrollment",
        {"course": course, "member": frappe.session.user},
        "name",
    )
    if not enrollment:
        frappe.throw("Enrollment not found", frappe.DoesNotExistError)

    frappe.db.set_value("LMS Enrollment", enrollment, "current_lesson", lesson)
    return {"success": True}


@frappe.whitelist()
def get_lesson_position(lesson_name):
    """
    Restituisce chapter_number e lesson_number (1-based) per costruire
    l'URL /courses/:courseName/learn/:chapterNumber-:lessonNumber
    Usa Chapter Reference e Lesson Reference, come fa mark_lesson_progress.
    """
    lesson = frappe.db.get_value(
        "Course Lesson",
        lesson_name,
        ["chapter", "course"],
        as_dict=True,
    )
    if not lesson:
        return None

    # chapter_number = idx del Chapter Reference nel corso
    chapter_number = frappe.db.get_value(
        "Chapter Reference",
        {"parent": lesson.course, "chapter": lesson.chapter},
        "idx",
    )

    # lesson_number = idx del Lesson Reference nel chapter
    lesson_number = frappe.db.get_value(
        "Lesson Reference",
        {"parent": lesson.chapter, "lesson": lesson_name},
        "idx",
    )

    return {
        "course": lesson.course,
        "chapter_number": chapter_number,
        "lesson_number": lesson_number,
    }


@frappe.whitelist(allow_guest=True)
def get_course_duration(course: str):
    """
    Somma il campo duration (minuti) di tutte le lezioni del corso.
    Restituisce il totale in minuti.
    """
    result = frappe.db.sql(
        """
        SELECT COALESCE(SUM(cl.duration), 0) as total_minutes
        FROM `tabLesson Reference` lr
        JOIN `tabChapter Reference` cr ON lr.parent = cr.chapter
        JOIN `tabCourse Lesson` cl ON lr.lesson = cl.name
        WHERE cr.parent = %s
    """,
        course,
        as_dict=True,
    )

    return result[0].total_minutes if result else 0


@frappe.whitelist()
def get_evaluator_details(evaluator: str):
    frappe.only_for("Batch Evaluator")
    calendar_name = None
    is_authorised = None

    if not frappe.db.exists("Google Calendar", {"user": evaluator}):
        try:
            calendar = frappe.new_doc("Google Calendar")
            calendar.update({"user": evaluator, "calendar_name": evaluator})
            calendar.insert()
            calendar_name = calendar.name
            is_authorised = calendar.authorization_code
        except Exception:
            pass  # Google API non configurata, ignora
    else:
        calendar = frappe.db.get_value(
            "Google Calendar",
            {"user": evaluator},
            ["name", "authorization_code"],
            as_dict=1,
        )
        calendar_name = calendar.name
        is_authorised = calendar.authorization_code

    if frappe.db.exists("Course Evaluator", {"evaluator": evaluator}):
        doc = frappe.get_doc("Course Evaluator", evaluator)
    else:
        doc = frappe.new_doc("Course Evaluator")
        doc.evaluator = evaluator
        doc.insert()

    return {
        "slots": doc.as_dict(),
        "calendar": calendar_name,
        "is_authorised": is_authorised,
    }


@frappe.whitelist()
def try_import():
    data_import = frappe.get_doc(
        {
            "doctype": "Data Import",
            "reference_doctype": "LMS Batch Enrollment",
            "import_type": "Insert New Records",  # o "Update Existing Records"
            "import_file": "/files/LMS Batch Enrollment_full.csv",  # path relativo a site
        }
    )
    data_import.insert()
    data_import.start_import()
    frappe.db.commit()

def evaluate_lesson_access(course: str, lesson: str) -> dict:
    """
    Verifica se l'utente può accedere alla lezione richiesta.
    Se il corso ha enforce_lesson_order attivo, controlla che
    la lezione precedente sia completata.
    """
    course_doc = frappe.get_doc("LMS Course", course)

    if not course_doc.get("enforce_lesson_order"):
        return {"allowed": True}

    all_lessons = []
    for chapter_ref in course_doc.chapters:
        chapter = frappe.get_doc("Course Chapter", chapter_ref.chapter)
        for lesson_ref in chapter.lessons:
            all_lessons.append(lesson_ref.lesson)

    if lesson not in all_lessons:
        return {"allowed": True}

    lesson_index = all_lessons.index(lesson)
    if lesson_index == 0:
        return {"allowed": True}

    prev_lesson = all_lessons[lesson_index - 1]
    is_completed = frappe.db.exists("LMS Course Progress", {
        "member": frappe.session.user,
        "lesson": prev_lesson,
        "course": course,
        "status": "Complete",
    })

    if is_completed:
        return {"allowed": True}
    return {
        "allowed": False,
        "reason": "Completa la lezione precedente prima di continuare.",
    }


@frappe.whitelist()
def check_lesson_access(course, lesson):
    return evaluate_lesson_access(course, lesson)


@frappe.whitelist()
def get_file_urls(names: list[str]):
    """Return file_url and file_name for a list of File document names, ignoring permissions."""
    if not names:
        return []
    return frappe.get_all(
        "File",
        filters={"name": ["in", names]},
        fields=["name", "file_name", "file_url"],
        ignore_permissions=True,
        limit_page_length=0,
    )


def evaluate_quiz_access(course: str, lesson: str | None = None) -> dict:
    """
    Verifica se l'utente può accedere al quiz.
    Se il corso ha enforce_quiz_on_completion attivo, controlla
    che tutte le lezioni precedenti alla lezione-quiz siano completate.
    Se `lesson` non è specificata, esclude dal controllo le lezioni
    che contengono un quiz (fallback per evitare deadlock).
    """
    course_doc = frappe.get_doc("LMS Course", course)

    if not course_doc.get("enforce_quiz_on_completion"):
        return {"allowed": True}

    all_lessons = []
    for chapter_ref in course_doc.chapters:
        chapter = frappe.get_doc("Course Chapter", chapter_ref.chapter)
        for lesson_ref in chapter.lessons:
            all_lessons.append(lesson_ref.lesson)

    if not all_lessons:
        return {"allowed": True}

    if lesson and lesson in all_lessons:
        idx = all_lessons.index(lesson)
        lessons_to_check = all_lessons[:idx]
    else:
        lessons_to_check = [
            l for l in all_lessons
            if not frappe.db.get_value("Course Lesson", l, "quiz_id")
        ]

    for l in lessons_to_check:
        is_completed = frappe.db.exists("LMS Course Progress", {
            "member": frappe.session.user,
            "lesson": l,
            "course": course,
            "status": "Complete",
        })
        if not is_completed:
            return {
                "allowed": False,
                "reason": "Completa tutte le lezioni precedenti prima di accedere al quiz.",
            }

    return {"allowed": True}


@frappe.whitelist()
def check_quiz_access(course, lesson=None):
    return evaluate_quiz_access(course, lesson)


@frappe.whitelist()
def send_batch_announcement(
    batch: str,
    recipients,
    subject: str,
    content: str,
    message: str = "",
    send_email: bool | int | str = True,
) -> dict:
    """
    Invia un annuncio a una LMS Batch con rendering Jinja dell'HTML.
    Il parametro `message` viene iniettato nel context come {{ message }}
    per permettere all'utente di scrivere il testo senza toccare l'HTML.
    Se `send_email` è falso viene creata solo la notifica in-app.
    """
    if not frappe.db.exists("LMS Batch", batch):
        frappe.throw("Batch non trovata")

    user_roles = frappe.get_roles(frappe.session.user)
    if not any(role in user_roles for role in ["Moderator", "Batch Evaluator", "System Manager"]):
        frappe.throw("Non hai i permessi per inviare annunci", frappe.PermissionError)

    if isinstance(recipients, str):
        recipients = [r.strip() for r in recipients.split(",") if r.strip()]
    if not recipients:
        frappe.throw("Nessun destinatario specificato")

    send_email_flag = str(send_email).lower() not in ("0", "false", "no", "")

    message_html = (message or "").replace("\n", "<br>")
    announcement_url = f"{frappe.utils.get_url()}/lms/batches/details/{batch}#announcements"
    context = {"message": message_html, "announcement_url": announcement_url}
    rendered_content = frappe.render_template(content, context)
    rendered_subject = frappe.render_template(subject, context)

    from frappe.core.doctype.communication.email import make
    make(
        recipients=", ".join(recipients),
        subject=rendered_subject,
        content=rendered_content,
        doctype="LMS Batch",
        name=batch,
        send_email=1 if send_email_flag else 0,
    )

    from frappe.desk.doctype.notification_log.notification_log import make_notification_logs
    batch_title = frappe.db.get_value("LMS Batch", batch, "title") or batch
    notification = frappe._dict({
        "subject": frappe._("Hai un nuovo messaggio in annunci: {0}").format(batch_title),
        "from_user": frappe.session.user,
        "type": "Alert",
        "link": f"/lms/batches/details/{batch}#announcements",
    })
    make_notification_logs(notification, recipients)

    return {"ok": True, "recipients_count": len(recipients)}


BATCH_TAB_SECTIONS = ("classes", "announcements", "discussions")


def get_batch_tab_unread_counts(batch: str) -> dict:
    """Unread Notification Log counts for the given batch, split by tab section."""
    user = frappe.session.user
    if not user or user == "Guest":
        return {section: 0 for section in BATCH_TAB_SECTIONS}
    return {
        section: frappe.db.count(
            "Notification Log",
            {
                "for_user": user,
                "read": 0,
                "link": ["like", f"%{batch}#{section}%"],
            },
        )
        for section in BATCH_TAB_SECTIONS
    }


@frappe.whitelist()
def get_welcome_video_config() -> dict:
    """Return welcome video settings for the current user to display on first login."""
    if frappe.session.user == "Guest":
        return {"enabled": False}

    settings = frappe.get_single("LMS Settings")
    if not settings.get("welcome_video_enabled"):
        return {"enabled": False}

    return {
        "enabled": True,
        "title": settings.get("welcome_video_title") or "",
        "subtitle": settings.get("welcome_video_subtitle") or "",
        "video_source": settings.get("welcome_video_file") or "",
    }


@frappe.whitelist()
def mark_welcome_video_seen() -> dict:
    """Mark the welcome video as seen for the current user."""
    if frappe.session.user == "Guest":
        return {"ok": False}
    frappe.db.set_value("User", frappe.session.user, "welcome_video_seen", 1)
    return {"ok": True}


@frappe.whitelist()
def replay_welcome_video():
    """Reset welcome_video_seen and redirect to the LMS home so the video plays again."""
    if frappe.session.user != "Guest":
        frappe.db.set_value(
            "User", frappe.session.user, "welcome_video_seen", 0
        )
        # GET requests do not cause an implicit commit
        frappe.db.commit()
    frappe.local.response["type"] = "redirect"
    frappe.local.response["location"] = "/lms/"


@frappe.whitelist()
def mark_batch_tab_notifications_read(batch: str, section: str) -> dict:
    """Mark as read all unread Notification Log entries for a batch tab section."""
    if section not in BATCH_TAB_SECTIONS:
        frappe.throw(frappe._("Invalid section: {0}").format(section))

    user = frappe.session.user
    frappe.db.sql(
        """
        UPDATE `tabNotification Log`
        SET `read` = 1
        WHERE for_user = %(user)s
          AND `read` = 0
          AND `link` LIKE %(link)s
        """,
        {"user": user, "link": f"%{batch}#{section}%"},
    )
    frappe.publish_realtime("publish_lms_notifications", user=user)
    return {"ok": True}


# ----- Live Class management -----

LIVE_CLASS_EDITABLE_FIELDS = ("title", "description")
MIN_REMINDER_MINUTES = 15


def _ensure_live_class_admin():
    frappe.only_for(["Moderator", "Batch Evaluator"])


def _validate_reminders(reminders) -> None:
    from os_lms.os_lms.doctype.lms_live_class_reminder.lms_live_class_reminder import (
        offset_to_minutes,
    )

    for row in reminders or []:
        offset_minutes = offset_to_minutes(
            row.get("offset_value"), row.get("offset_unit")
        )
        if offset_minutes < MIN_REMINDER_MINUTES:
            frappe.throw(
                frappe._("Each reminder must be at least 15 minutes before the class.")
            )


@frappe.whitelist()
def update_live_class(name: str, payload: dict) -> dict:
    """Update editable fields and the reminders child table on a Live Class."""
    _ensure_live_class_admin()

    if isinstance(payload, str):
        import json

        payload = json.loads(payload)

    doc = frappe.get_doc("LMS Live Class", name)

    for field in LIVE_CLASS_EDITABLE_FIELDS:
        if field in payload:
            doc.set(field, payload.get(field))

    if "reminders" in payload:
        _validate_reminders(payload.get("reminders"))
        doc.set("reminders", [])
        for row in payload.get("reminders") or []:
            doc.append(
                "reminders",
                {
                    "offset_value": row.get("offset_value"),
                    "offset_unit": row.get("offset_unit"),
                    # preserve sent_at when row was already persisted
                    "sent_at": row.get("sent_at"),
                },
            )

    doc.save()
    frappe.db.commit()
    return {"name": doc.name}


@frappe.whitelist()
def delete_live_class(name: str, notify_students: int = 0) -> dict:
    """Delete a Live Class. Optionally notify enrolled students by email + Notification Log."""
    _ensure_live_class_admin()

    doc = frappe.get_doc("LMS Live Class", name)
    title = doc.title
    date = doc.date
    time = doc.time
    batch = doc.batch_name
    provider = doc.conferencing_provider
    zoom_account = doc.get("zoom_account")
    meeting_id = doc.get("meeting_id")

    if int(notify_students or 0):
        _notify_students_class_cancelled(doc)

    frappe.delete_doc("LMS Live Class", name)

    if provider == "Zoom" and zoom_account and meeting_id:
        _delete_zoom_meeting(zoom_account, meeting_id)

    frappe.db.commit()
    return {
        "ok": True,
        "title": title,
        "date": str(date),
        "time": str(time),
        "batch": batch,
    }


def _notify_students_class_cancelled(live_class) -> None:
    from frappe.desk.doctype.notification_log.notification_log import (
        make_notification_logs,
    )
    from frappe.utils import format_date, format_time

    students = frappe.get_all(
        "LMS Batch Enrollment",
        {"batch": live_class.batch_name},
        ["member", "member_name"],
    )
    if not students:
        return

    formatted_date = format_date(live_class.date, "medium")
    formatted_time = format_time(live_class.time, "hh:mm a")

    subject = frappe._(
        "La lezione dal vivo {0} del {1} alle {2} è stata annullata"
    ).format(frappe.bold(live_class.title), formatted_date, formatted_time)

    notification = frappe._dict(
        {
            "subject": subject,
            "type": "Alert",
            "from_user": frappe.session.user,
        }
    )
    make_notification_logs(notification, [s.member for s in students])

    for student in students:
        try:
            frappe.sendmail(
                recipients=student.member,
                subject=frappe._("Lezione annullata: {0}").format(live_class.title),
                template="live_class_cancelled",
                args={
                    "student_name": student.member_name,
                    "title": live_class.title,
                    "date": live_class.date,
                    "time": live_class.time,
                    "batch_name": live_class.batch_name,
                },
                header=[frappe._("Lezione annullata"), "red"],
            )
        except Exception:
            frappe.logger("os_lms_live_class", allow_site=True).exception(
                f"Failed to send cancellation email to {student.member}"
            )


def _delete_zoom_meeting(zoom_account: str, meeting_id: str) -> None:
    """Best-effort delete of the Zoom meeting; failures are logged but do not block deletion."""
    try:
        import requests

        from lms.lms.doctype.lms_batch.lms_batch import authenticate

        headers = {"Authorization": "Bearer " + authenticate(zoom_account)}
        requests.delete(
            f"https://api.zoom.us/v2/meetings/{meeting_id}",
            headers=headers,
            timeout=10,
        )
    except Exception:
        frappe.logger("os_lms_live_class", allow_site=True).exception(
            f"Failed to delete Zoom meeting {meeting_id}"
        )
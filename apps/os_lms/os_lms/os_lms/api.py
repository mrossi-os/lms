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
def send_batch_announcement(batch: str, recipients, subject: str, content: str, message: str = "") -> dict:
    """
    Invia un annuncio a una LMS Batch con rendering Jinja dell'HTML.
    Il parametro `message` viene iniettato nel context come {{ message }}
    per permettere all'utente di scrivere il testo senza toccare l'HTML.
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

    message_html = (message or "").replace("\n", "<br>")
    context = {"message": message_html}
    rendered_content = frappe.render_template(content, context)
    rendered_subject = frappe.render_template(subject, context)

    from frappe.core.doctype.communication.email import make
    make(
        recipients=", ".join(recipients),
        subject=rendered_subject,
        content=rendered_content,
        doctype="LMS Batch",
        name=batch,
        send_email=1,
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
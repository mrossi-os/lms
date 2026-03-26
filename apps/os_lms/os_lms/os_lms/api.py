import frappe


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

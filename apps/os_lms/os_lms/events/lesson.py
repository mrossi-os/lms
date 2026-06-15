import frappe

# Records owned by a lesson — bulk-deleted when the lesson is removed. These
# are leaf doctypes (no child tables that need their own cascade).
LESSON_OWNED_DOCTYPES = (
    ("LMS Video Watch Duration", "lesson"),  # per-view analytics
    ("LMS Course Progress", "lesson"),  # per-lesson completion state
    ("LMS Lesson Note", "lesson"),  # learner notes (lesson is required)
    ("LMSA Query Log", "lesson"),  # AI assistant audit trail
)

# Child-table rows that link to the lesson: drop the row, keep the parent doc.
LESSON_OWNED_CHILD_TABLES = (
    ("LMSA Debrief Recommendation", "lesson"),  # row inside LMSA Simulation Debrief
)

# Lesson-owned docs with their own child tables / downstream links — routed
# through delete_doc(force) so their children are cleaned and their own
# outbound links don't re-trigger the link guard.
LESSON_OWNED_DEEP_DOCTYPES = (
    ("LMSA Simulation Scenario", "course_lesson"),
)

# Docs that belong elsewhere and only reference the lesson — detached (set to
# NULL) instead of deleted, so the quiz / enrollment / submission survives.
LESSON_REFERENCING_DOCTYPES = (
    ("LMS Quiz", "lesson"),  # reusable assessment
    ("LMS Enrollment", "current_lesson"),  # learner's bookmark
    ("LMS Assignment Submission", "lesson"),  # belongs to the assignment
)


def reset_index_status_on_content_change(doc, method):
    if not doc.is_new() and (
        doc.has_value_changed("content") or doc.has_value_changed("instructor_content")
    ):
        doc.index_status = "pending"


def cleanup_lesson_links(doc, method=None):
    """on_trash hook on Course Lesson: clear every reference to the lesson so the
    deletion is not blocked by LinkExistsError. Runs before Frappe's
    check_if_doc_is_linked validation.

    Lesson-owned records are deleted; records that merely reference the lesson
    (quizzes, enrollments, assignment submissions) are detached instead.
    """
    lesson = doc.name

    for doctype, fieldname in LESSON_OWNED_DOCTYPES + LESSON_OWNED_CHILD_TABLES:
        frappe.db.delete(doctype, {fieldname: lesson})

    for doctype, fieldname in LESSON_OWNED_DEEP_DOCTYPES:
        for name in frappe.get_all(doctype, filters={fieldname: lesson}, pluck="name"):
            frappe.delete_doc(
                doctype,
                name,
                ignore_permissions=True,
                delete_permanently=True,
                force=True,
            )

    for doctype, fieldname in LESSON_REFERENCING_DOCTYPES:
        frappe.db.set_value(doctype, {fieldname: lesson}, fieldname, None, update_modified=False)

    # Drop the lesson's vectors from the RAG index. Best-effort: imported lazily
    # and fully guarded so an AI/Redis problem can never block the deletion.
    try:
        from os_lms.os_lms.ai.ingestion.service import IngestionService

        IngestionService().remove_lesson(doc.course, doc.name)
    except Exception:
        frappe.log_error(title="Lesson RAG cleanup failed")

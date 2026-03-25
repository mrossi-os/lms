import frappe
import secrets


def course_column_expanders():

    return {
        "email istruttori": expand_instructors,
    }


def expand_instructors(cell_value: str, row: dict) -> list[tuple[str, str]]:
    """Expand a comma-separated list of instructor emails into Data Import columns.

    Returns columns like:
      instructors (Course Instructor) - 1.instructor = email1
      instructors (Course Instructor) - 2.instructor = email2
    """
    if not cell_value or not cell_value.strip():
        return []
    course_id = row["ID"]
    if not course_id:
        return []

    name = frappe.db.get_value(
        "Course Instructor",
        {"instructor": cell_value, "parent": course_id},
        "name",
    )
    if not name:
        name = str(secrets.token_hex(5))

    _ = frappe._
    parent_label = _("Instructors")
    return [
        (f'{_("ID")} ({parent_label})', name),
        (f'{_("Course Instructor")} ({parent_label})', cell_value),
    ]

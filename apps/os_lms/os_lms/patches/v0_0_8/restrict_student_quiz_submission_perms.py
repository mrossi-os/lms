"""Take write/create on LMS Quiz Submission away from the LMS Student.

Upstream (876504f39) made the doctype read-only for the LMS Student, because a
submission is created server-side by create_submission(ignore_permissions=True)
and graded by instructors. Sites that already carry Custom DocPerm rows for the
doctype keep the old student write (and on production create) grant, and those
rows replace the JSON permissions entirely. validate_marks() recomputes the score
from each row's marks, so a student could raise their own grade by saving the
submission through frappe.client.save.

Only the LMS Student row is changed: the other Custom DocPerm rows (Gestore,
Tutor, Valutatore, Course Creator) are what instructors grade and read with.
Idempotent.
"""

import frappe

DOCTYPE = "LMS Quiz Submission"
ROLE = "LMS Student"
REVOKED = ("write", "create", "delete", "submit", "cancel", "amend", "import")


def execute():
	rows = frappe.get_all("Custom DocPerm", filters={"parent": DOCTYPE, "role": ROLE}, pluck="name")
	for name in rows:
		frappe.db.set_value("Custom DocPerm", name, dict.fromkeys(REVOKED, 0), update_modified=False)
	if rows:
		frappe.clear_cache(doctype=DOCTYPE)

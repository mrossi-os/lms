"""Shared test data of the Elite API catalogue and student endpoints.

The fixture reproduces what production data actually contains (duplicated
enrollments, an enrollment of a deleted user, batch courses never opened,
students without fiscal code or last name) plus the exclusion rules (disabled
users, non-Student enrollments).

Rows are written with ``db_insert`` (no hooks, so no side documents such as
automatic enrollments or notifications) under fixed ``elite-api-test-`` names.
In-process tests roll back; HTTP tests must commit, and delete exactly the
names they created with ``delete_fixture``.
"""

from __future__ import annotations

import frappe

P = "elite-api-test-"
SEARCH = "EliteApiTest"

COURSES = {
	f"{P}alpha": {"title": f"{SEARCH} Alpha 50%", "published": 1},
	f"{P}beta": {"title": f"{SEARCH} Beta", "published": 1},
	f"{P}gamma": {"title": f"{SEARCH} Gamma axb", "published": 1},
	f"{P}delta": {"title": f"{SEARCH} Delta a_b", "published": 0},
}
ALPHA, BETA = f"{P}alpha", f"{P}beta"

DONE, HALF, ZERO, DUP, NEWBIE, MENTOR, DISABLED = (
	f"{P}{n}@example.com" for n in ("done", "half", "zero", "dup", "newbie", "mentor", "disabled")
)
ORPHAN = f"{P}deleted@example.com"  # enrolled, but the User no longer exists
# email: (enabled, first_name, last_name, codice_fiscale as stored)
USERS = {
	DONE: (1, "Anna", "Bianchi", "ELTBNC80A41H501A"),
	HALF: (1, "Carlo", "Rossi", " eltrss80a01h501b "),  # stored dirty: returned normalised
	ZERO: (1, "Mario Verdi", "", None),  # whole name in first_name, no fiscal code
	DUP: (1, "Dario", "Neri", "ELTNRI80A01H501C"),
	NEWBIE: (1, "Elena", "Gialli", None),
	MENTOR: (1, "Marta", "Mentore", None),
	DISABLED: (0, "Dora", "Spenta", "ELTSPN80A41H501D"),
}

# (course, member, progress, member_type, creation)
ENROLLMENTS = [
	(ALPHA, DONE, 100, "Student", "2026-03-02 09:00:00"),
	(ALPHA, HALF, 50, "Student", "2026-03-03 09:00:00"),
	(ALPHA, ZERO, 0, "Student", "2026-03-04 09:00:00"),
	(ALPHA, DUP, 0, "Student", "2026-03-01 09:00:00"),
	(ALPHA, DUP, 60, "Student", "2026-03-05 09:00:00"),  # duplicate: highest progress, first date
	(ALPHA, DISABLED, 100, "Student", "2026-03-01 09:00:00"),  # disabled user: excluded
	(ALPHA, MENTOR, 100, "Mentor", "2026-03-01 09:00:00"),  # not a student: excluded
	(ALPHA, ORPHAN, 100, "Student", "2026-03-01 09:00:00"),  # deleted user: excluded
	(BETA, DONE, 100, "Student", "2026-03-02 09:00:00"),
	(BETA, HALF, 0, "Student", "2026-03-03 09:00:00"),
]

BATCH_MAIN, BATCH_EMPTY = f"{P}batch-main", f"{P}batch-empty"
BATCHES = {
	BATCH_MAIN: {"title": f"{SEARCH} Main batch", "start_date": "2026-01-10", "courses": [ALPHA, BETA]},
	BATCH_EMPTY: {"title": f"{SEARCH} Batch without courses", "start_date": "2026-02-01", "courses": []},
}
# (batch, member, creation)
BATCH_ENROLLMENTS = [
	(BATCH_MAIN, DONE, "2026-01-05 10:00:00"),  # 100 + 100 -> completed_all
	(BATCH_MAIN, HALF, "2026-01-06 10:00:00"),  # 50 + 0 -> partial
	(BATCH_MAIN, ZERO, "2026-01-07 10:00:00"),  # 0 + never opened -> not_started
	(BATCH_MAIN, DUP, "2026-01-08 10:00:00"),  # 60 (duplicated row) + never opened -> partial
	(BATCH_MAIN, NEWBIE, "2026-01-09 10:00:00"),  # never opened any course -> not_started
	(BATCH_MAIN, DISABLED, "2026-01-05 10:00:00"),  # excluded
	(BATCH_EMPTY, DONE, "2026-01-20 10:00:00"),  # batch without courses -> not_started
]

EXPECTED_ALPHA = {"total": 4, "completed": 1, "in_progress": 2, "not_started": 1}
EXPECTED_BETA = {"total": 2, "completed": 1, "in_progress": 0, "not_started": 1}
EXPECTED_MAIN = {"total": 5, "completed_all": 1, "partial": 2, "not_started": 2}
EXPECTED_EMPTY = {"total": 1, "completed_all": 0, "partial": 0, "not_started": 1}


def insert_fixture() -> dict[str, list[str]]:
	"""Insert the fixture and return ``{doctype: [names]}`` for an exact cleanup."""
	created: dict[str, list[str]] = {}

	def insert(values: dict):
		frappe.get_doc(values).db_insert()
		created.setdefault(values["doctype"], []).append(values["name"])

	for email, (enabled, first_name, last_name, fiscal_code) in USERS.items():
		insert(
			{
				"doctype": "User",
				"name": email,
				"email": email,
				"first_name": first_name,
				"last_name": last_name,
				"codice_fiscale": fiscal_code,
				"enabled": enabled,
			}
		)
	for name, values in COURSES.items():
		insert({"doctype": "LMS Course", "name": name, **values})
	for n, (course, member, progress, member_type, creation) in enumerate(ENROLLMENTS):
		insert(
			{
				"doctype": "LMS Enrollment",
				"name": f"{P}enrollment-{n}",
				"course": course,
				"member": member,
				"progress": progress,
				"member_type": member_type,
				"creation": creation,
				"modified": creation,
			}
		)
	for name, values in BATCHES.items():
		insert(
			{
				"doctype": "LMS Batch",
				"name": name,
				"title": values["title"],
				"start_date": values["start_date"],
				"end_date": values["start_date"],
				"published": 1,
			}
		)
		for idx, course in enumerate(values["courses"], start=1):
			# Batch Course is named by autoincrement: cleaned up by its parent.
			row = frappe.get_doc(
				{
					"doctype": "Batch Course",
					"parent": name,
					"parenttype": "LMS Batch",
					"parentfield": "courses",
					"idx": idx,
					"course": course,
				}
			)
			row.set_new_name()
			row.db_insert()
	for n, (batch, member, creation) in enumerate(BATCH_ENROLLMENTS):
		insert(
			{
				"doctype": "LMS Batch Enrollment",
				"name": f"{P}batch-enrollment-{n}",
				"batch": batch,
				"member": member,
				"creation": creation,
				"modified": creation,
			}
		)
	return created


def delete_fixture(created: dict[str, list[str]]):
	for doctype, names in created.items():
		frappe.db.delete(doctype, {"name": ("in", names)})
	frappe.db.delete("Batch Course", {"parenttype": "LMS Batch", "parent": ("in", list(BATCHES))})

# Copyright (c) 2026, ELITE and contributors
# For license information, please see license.txt
"""Custom "Valutatore" role scoped to a single LMS Batch.

A Valutatore is assigned by an admin inside a specific batch (the `valutatori`
Table MultiSelect custom field on LMS Batch). From then on they can, **only for
that batch**:

- view the batch admin dashboard, live classes and announcements;
- view the quiz answers of the students enrolled in that batch;
- view, grade and send the evaluation of the assignments of those students, on
  the batch's courses only.

Access is enforced with two complementary mechanisms (Frappe permission model is
veto-only at the controller level, so the baseline read/write comes from the
"Valutatore" role DocPerms — created in setup.py — and is then *narrowed* here):

- ``get_permission_query_conditions`` scopes list views to the batch members;
- ``has_permission`` vetoes direct (by-name) access outside that scope.

The "Valutatore" Role record itself only acts as the technical container of the
doctype permissions. It is granted automatically when an admin adds a user to a
batch's `valutatori` field (see ``sync_batch_valutatore_roles``) and can also be
assigned by hand (Settings > Members, profile Roles tab); it is never revoked
automatically — removing the batch assignment only removes the scope.
"""

import frappe

from os_lms.os_lms.role_audit import log_role_change

ROLE = "Valutatore"

# Roles that already have broad access and must never be narrowed by the
# valutatore scoping (they keep seeing everything).
FULL_ACCESS_ROLES = {
	"Administrator",
	"System Manager",
	"Moderator",
	"Course Creator",
	"Batch Evaluator",
	"Docente",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def is_valutatore(user: str | None = None) -> bool:
	"""True if the user carries the global "Valutatore" role container."""
	user = user or frappe.session.user
	return ROLE in frappe.get_roles(user)


def is_batch_valutatore(batch: str, user: str | None = None) -> bool:
	"""True if the user is a valutatore of this specific batch."""
	user = user or frappe.session.user
	if not batch:
		return False
	return bool(
		frappe.db.exists(
			"LMS Batch Valutatore",
			{"parent": batch, "parenttype": "LMS Batch", "valutatore": user},
		)
	)


def get_valutatore_batches(user: str | None = None) -> list[str]:
	"""Batches where the user is listed as a valutatore."""
	user = user or frappe.session.user
	return frappe.get_all(
		"LMS Batch Valutatore",
		filters={"parenttype": "LMS Batch", "valutatore": user},
		pluck="parent",
	)


def get_valutatore_member_emails(user: str | None = None) -> list[str]:
	"""Distinct members enrolled in the batches the user evaluates."""
	batches = get_valutatore_batches(user)
	if not batches:
		return []
	members = frappe.get_all(
		"LMS Batch Enrollment",
		filters={"batch": ["in", batches]},
		pluck="member",
	)
	return list(set(members))


def get_valutatore_course_names(user: str | None = None) -> list[str]:
	"""Courses linked (via the Batch Course child table) to the batches the user
	evaluates. Used to scope the read-only course dashboard data."""
	batches = get_valutatore_batches(user)
	if not batches:
		return []
	return frappe.get_all(
		"Batch Course",
		filters={"parent": ["in", batches], "parenttype": "LMS Batch"},
		pluck="course",
	)


def get_valutatore_batch_people(user: str | None = None) -> set[str]:
	"""Everyone in the batches the user evaluates: students, instructors and the
	other valutatori. Used to scope the @mention user list."""
	batches = get_valutatore_batches(user)
	if not batches:
		return set()
	people = set(get_valutatore_member_emails(user))
	people.update(
		frappe.get_all(
			"Course Instructor",
			filters={"parent": ["in", batches], "parenttype": "LMS Batch"},
			pluck="instructor",
		)
	)
	people.update(
		frappe.get_all(
			"LMS Batch Valutatore",
			filters={"parent": ["in", batches], "parenttype": "LMS Batch"},
			pluck="valutatore",
		)
	)
	return people


def _only_scoped_valutatore(user: str) -> bool:
	"""True when the user is a valutatore and has no broader access role."""
	roles = set(frappe.get_roles(user))
	return ROLE in roles and not (roles & FULL_ACCESS_ROLES)


def _in_clause(values: list[str]) -> str:
	# frappe.db.escape() already wraps the value in quotes; do not add more.
	return ",".join(frappe.db.escape(v, percent=False) for v in values)


# ---------------------------------------------------------------------------
# List view scoping (permission_query_conditions)
# ---------------------------------------------------------------------------
def batch_enrollment_query_conditions(user: str | None = None) -> str:
	user = user or frappe.session.user
	if not _only_scoped_valutatore(user):
		return ""
	batches = get_valutatore_batches(user)
	if not batches:
		return "1=0"
	return f"`tabLMS Batch Enrollment`.batch IN ({_in_clause(batches)})"


def live_class_query_conditions(user: str | None = None) -> str:
	user = user or frappe.session.user
	if not _only_scoped_valutatore(user):
		return ""
	batches = get_valutatore_batches(user)
	if not batches:
		return "1=0"
	return f"`tabLMS Live Class`.batch_name IN ({_in_clause(batches)})"


def _quiz_submission_scope_sql(batches: list[str]) -> str:
	"""SQL predicate on `tabLMS Quiz Submission`: the student is enrolled in one of
	``batches`` AND the quiz belongs to that same batch.

	The pairing is per batch: a Valutatore of two batches does not see the students of
	one batch on the quizzes of the other. A quiz belongs to a batch when it is
	  - the ``course`` of the quiz, or the course of a lesson that embeds it
	    (``Course Lesson.quiz_id``), one of the batch courses, or
	  - listed in the batch assessments.
	The quiz is resolved as it is linked *today*, not from the ``course`` copied onto
	the submission: that copy is frozen at insert time, so a quiz linked to its course
	later leaves older submissions with an empty course.
	"""
	batch_list = _in_clause(batches)
	submission = "`tabLMS Quiz Submission`"
	return (
		"EXISTS (SELECT 1 FROM `tabLMS Batch Enrollment` os_be"
		f" WHERE os_be.batch IN ({batch_list}) AND os_be.member = {submission}.member"
		" AND ("
		"EXISTS (SELECT 1 FROM `tabBatch Course` os_bc"
		" WHERE os_bc.parent = os_be.batch AND os_bc.parenttype = 'LMS Batch'"
		" AND (os_bc.course = (SELECT os_q.course FROM `tabLMS Quiz` os_q"
		f" WHERE os_q.name = {submission}.quiz)"
		" OR os_bc.course IN (SELECT os_cl.course FROM `tabCourse Lesson` os_cl"
		f" WHERE os_cl.quiz_id = {submission}.quiz)))"
		" OR EXISTS (SELECT 1 FROM `tabLMS Assessment` os_a"
		" WHERE os_a.parent = os_be.batch AND os_a.parenttype = 'LMS Batch'"
		f" AND os_a.assessment_type = 'LMS Quiz' AND os_a.assessment_name = {submission}.quiz)"
		"))"
	)


def quiz_submission_query_conditions(user: str | None = None) -> str:
	user = user or frappe.session.user
	if not _only_scoped_valutatore(user):
		return ""
	batches = get_valutatore_batches(user)
	if not batches:
		return "1=0"
	return _quiz_submission_scope_sql(batches)


def _assignment_submission_scope_sql(batches: list[str]) -> str:
	"""SQL predicate on `tabLMS Assignment Submission`: the student is enrolled in one
	of ``batches`` AND the assignment belongs to that same batch, as for quizzes
	(see :func:`_quiz_submission_scope_sql`).

	An assignment belongs to a batch when one of the batch courses is
	  - the ``course`` of the assignment,
	  - the course of the lesson the submission was made from, or of a lesson that
	    places the assignment (``LMS Lesson Assessment``),
	or when the assignment is listed in the batch assessments. Lessons are resolved
	as they are linked *today*: the ``course`` copied onto the submission is frozen
	at insert time.
	"""
	batch_list = _in_clause(batches)
	submission = "`tabLMS Assignment Submission`"
	return (
		"EXISTS (SELECT 1 FROM `tabLMS Batch Enrollment` os_be"
		f" WHERE os_be.batch IN ({batch_list}) AND os_be.member = {submission}.member"
		" AND ("
		"EXISTS (SELECT 1 FROM `tabBatch Course` os_bc"
		" WHERE os_bc.parent = os_be.batch AND os_bc.parenttype = 'LMS Batch'"
		" AND (os_bc.course = (SELECT os_as.course FROM `tabLMS Assignment` os_as"
		f" WHERE os_as.name = {submission}.assignment)"
		" OR os_bc.course = (SELECT os_cl.course FROM `tabCourse Lesson` os_cl"
		f" WHERE os_cl.name = {submission}.lesson)"
		" OR os_bc.course IN (SELECT os_pl.course FROM `tabCourse Lesson` os_pl"
		" JOIN `tabLMS Lesson Assessment` os_la ON os_la.parent = os_pl.name"
		" AND os_la.parenttype = 'Course Lesson'"
		f" WHERE os_la.assessment_type = 'LMS Assignment' AND os_la.assessment_name = {submission}.assignment)))"
		" OR EXISTS (SELECT 1 FROM `tabLMS Assessment` os_a"
		" WHERE os_a.parent = os_be.batch AND os_a.parenttype = 'LMS Batch'"
		f" AND os_a.assessment_type = 'LMS Assignment' AND os_a.assessment_name = {submission}.assignment)"
		"))"
	)


def assignment_submission_query_conditions(user: str | None = None) -> str:
	user = user or frappe.session.user
	if not _only_scoped_valutatore(user):
		return ""
	batches = get_valutatore_batches(user)
	if not batches:
		return "1=0"
	return _assignment_submission_scope_sql(batches)


def enrollment_query_conditions(user: str | None = None) -> str:
	"""Scope the course-enrolment list (read-only dashboard) to the students of the
	valutatore's batches, for the courses of those batches."""
	return _learner_query_conditions("LMS Enrollment", user)


def course_progress_query_conditions(user: str | None = None) -> str:
	"""Scope the per-lesson progress list (student drilldown) to the students of the
	valutatore's batches, for the courses of those batches."""
	return _learner_query_conditions("LMS Course Progress", user)


def _learner_query_conditions(doctype: str, user: str | None) -> str:
	# By course alone, a valutatore read the whole course: every student of every
	# other batch running it, and the learners enrolled outside any batch.
	user = user or frappe.session.user
	if not _only_scoped_valutatore(user):
		return ""
	batches = get_valutatore_batches(user)
	if not batches:
		return "1=0"
	return f"""exists (select 1 from `tabLMS Batch Enrollment` be
		join `tabBatch Course` bc on bc.parent = be.batch and bc.parenttype = 'LMS Batch'
		where be.batch in ({_in_clause(batches)})
		and be.member = `tab{doctype}`.member and bc.course = `tab{doctype}`.course)"""


def _batch_reaches_learner(course: str | None, member: str | None, batches: list[str]) -> bool:
	"""Single-row twin of _learner_query_conditions."""
	if not (course and member and batches):
		return False
	return bool(
		frappe.db.sql(
			"""select 1 from `tabLMS Batch Enrollment` be
			join `tabBatch Course` bc on bc.parent = be.batch and bc.parenttype = 'LMS Batch'
			where be.batch in %(batches)s and be.member = %(member)s and bc.course = %(course)s
			limit 1""",
			{"batches": batches, "member": member, "course": course},
		)
	)


# ---------------------------------------------------------------------------
# Proctoring log (upstream v2.63.0)
# ---------------------------------------------------------------------------
@frappe.whitelist()
def get_quiz_violation_logs(submission: str):
	"""Upstream ``get_quiz_violation_logs``, narrowed for the scoped Valutatore.

	The upstream endpoint returns the proctoring events of a quiz attempt, with a
	webcam still for each violation, to anyone who can read the submission. The scoped
	Valutatore reads the log (photos included) only for a submission of their own
	batches (student AND quiz of the same batch); decision of the client, 2026-10-05,
	which reverses the 2026-09-24 one that kept the log from them altogether.
	"""
	from lms.lms.doctype.lms_quiz.lms_quiz import get_quiz_violation_logs as upstream

	user = frappe.session.user
	if _only_scoped_valutatore(user):
		batches = get_valutatore_batches(user)
		if not (batches and _quiz_submission_in_scope(submission, batches)):
			frappe.throw(frappe._("Insufficient Permission"), frappe.PermissionError)
	return upstream(submission)


# ---------------------------------------------------------------------------
# Row-level veto (has_permission)
# ---------------------------------------------------------------------------
def submission_has_permission(doc, ptype: str = "read", user: str | None = None):
	"""Veto by-name access to a submission outside the valutatore's batches.

	Return ``True`` to stay neutral (so the role DocPerms and other users are not
	affected), ``False`` only to deny. IMPORTANT: Frappe's
	``has_controller_permissions`` treats a *falsy* return (including ``None``) as
	a DENY (``if not controller_permission: return bool(...)``). The neutral case
	must therefore return ``True``, never ``None`` — otherwise every ptype checked
	with a ``doc`` (e.g. create via ``frappe.client.insert``) is denied for all
	users, not just scoped valutatori.
	"""
	user = user or frappe.session.user
	if not _only_scoped_valutatore(user):
		return True
	batches = get_valutatore_batches(user)
	if not batches:
		return False
	name = doc.get("name")
	if name and not doc.is_new():
		# Same rule as the list: student AND assignment of the same batch, so the
		# student's assignments in courses outside the batch stay out of reach.
		return bool(
			frappe.db.sql(
				"SELECT 1 FROM `tabLMS Assignment Submission`"
				f" WHERE name = %s AND {_assignment_submission_scope_sql(batches)}",
				(name,),
			)
		)
	# A document that is not saved yet has nothing to resolve the assignment from:
	# keep the plain membership rule.
	member = doc.get("member")
	return bool(member and member in get_valutatore_member_emails(user))


def _quiz_submission_in_scope(name: str, batches: list[str]) -> bool:
	"""Whether the quiz submission ``name`` is one the valutatore of ``batches`` may read:
	the same rule as :func:`quiz_submission_query_conditions`, asked for a single row."""
	return bool(
		frappe.db.sql(
			"SELECT 1 FROM `tabLMS Quiz Submission`"
			f" WHERE name = %s AND {_quiz_submission_scope_sql(batches)}",
			(name,),
		)
	)


def quiz_submission_has_permission(doc, ptype: str = "read", user: str | None = None):
	"""Veto by-name access to a quiz submission outside the valutatore's batches, with
	the same rule as :func:`quiz_submission_query_conditions` (student AND quiz of the
	same batch). Neutral case returns ``True``: see :func:`submission_has_permission`."""
	user = user or frappe.session.user
	if not _only_scoped_valutatore(user):
		return True
	batches = get_valutatore_batches(user)
	if not batches:
		return False
	name = doc.get("name")
	if name and not doc.is_new():
		return _quiz_submission_in_scope(name, batches)
	# A document that is not saved yet has nothing to resolve the quiz from: keep the
	# plain membership rule.
	member = doc.get("member")
	return bool(member and member in get_valutatore_member_emails(user))


def violation_log_query_conditions(user: str | None = None) -> str:
	"""Scope the proctoring log rows to the quiz submissions the valutatore may read.

	The camera stills hang off these rows as private Files and inherit their audience
	(File.has_permission delegates to read on the attached document), so narrowing the
	rows narrows the photos too."""
	user = user or frappe.session.user
	if not _only_scoped_valutatore(user):
		return ""
	batches = get_valutatore_batches(user)
	if not batches:
		return "1=0"
	return (
		"`tabLMS Quiz Violation Log`.quiz_submission IN ("
		"SELECT `tabLMS Quiz Submission`.name FROM `tabLMS Quiz Submission`"
		f" WHERE {_quiz_submission_scope_sql(batches)})"
	)


def violation_log_has_permission(doc, ptype: str = "read", user: str | None = None):
	"""Veto by-name access (and so the camera stills) to a proctoring log row whose
	quiz submission is outside the valutatore's batches. Neutral case returns ``True``:
	see :func:`submission_has_permission`."""
	user = user or frappe.session.user
	if not _only_scoped_valutatore(user):
		return True
	submission = doc.get("quiz_submission")
	batches = get_valutatore_batches(user)
	if not (submission and batches):
		return False
	return _quiz_submission_in_scope(submission, batches)


def course_scoped_has_permission(doc, ptype: str = "read", user: str | None = None):
	"""Veto by-name access to a course-scoped row (LMS Enrollment / LMS Course
	Progress) outside the students of the valutatore's batches. The list views are already
	narrowed by the query-conditions; this guards direct (by-name) reads.

	This narrows *visibility* only and must never block create/write/delete:
	``has_permission`` runs for every ptype, so vetoing those would strip a
	permission the user legitimately holds via another role (e.g. an enroller who
	is both Gestore and Valutatore). Those ptypes are governed by DocPerms.

	Return ``True`` for the neutral/allow cases, ``False`` only to veto. Frappe's
	``has_controller_permissions`` treats any falsy return (including ``None``) as
	a DENY, so neutral MUST be ``True`` — returning ``None`` here denies create for
	*everyone* once a ``doc`` is passed.
	"""
	user = user or frappe.session.user
	if ptype not in ("read", "select"):
		return True
	if not _only_scoped_valutatore(user):
		return True
	return _batch_reaches_learner(doc.get("course"), doc.get("member"), get_valutatore_batches(user))


# ---------------------------------------------------------------------------
# Role lifecycle: grant the "Valutatore" Role to the users a batch assigns
# ---------------------------------------------------------------------------
def _ensure_role(user: str, role: str) -> None:
	if not frappe.db.exists("Has Role", {"parent": user, "role": role}):
		entry = frappe.new_doc("Has Role")
		entry.parent = user
		entry.parenttype = "User"
		entry.parentfield = "roles"
		entry.role = role
		entry.save(ignore_permissions=True)
		log_role_change(user, role, granted=True)
		frappe.clear_cache(user=user)


def _row_members(rows) -> set[str]:
	return {row.valutatore for row in (rows or []) if getattr(row, "valutatore", None)}


def validate_batch_valutatori(doc, method: str | None = None) -> None:
	"""LMS Batch validate: refuse a student added to the batch valutatori.

	The picker (search_non_student_users) offers only non-students, but saving the
	batch through the API took any user, and on_update then granted the role: a
	student could become the evaluator of classmates. People already listed are
	left alone, so an old batch still saves.
	"""
	before = doc.get_doc_before_save()
	added = _row_members(doc.get("valutatori")) - _row_members(before.get("valutatori") if before else None)
	if not added:
		return
	students = frappe.get_all(
		"Has Role",
		filters={"parent": ["in", list(added)], "parenttype": "User", "role": "LMS Student"},
		pluck="parent",
	)
	if students:
		frappe.throw(
			frappe._("A student cannot be an evaluator of the batch: {0}").format(", ".join(sorted(students)))
		)


def sync_batch_valutatore_roles(doc, method: str | None = None) -> None:
	"""LMS Batch on_update: grant the role to the batch valutatori.

	Grant-only on purpose. The role is also assignable by hand (Settings > Members
	and the profile Roles tab), so removing a user from a batch's `valutatori`
	field must NOT take the role away — it would silently undo an explicit admin
	assignment and, when the user evaluates nothing else, drop them out of the
	role entirely. Losing the batch assignment is already enough: every scoping
	rule above resolves to "no batches" and grants no data access.
	"""
	for member in _row_members(doc.get("valutatori")):
		_ensure_role(member, ROLE)

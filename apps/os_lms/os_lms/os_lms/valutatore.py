# Copyright (c) 2026, ELITE and contributors
# For license information, please see license.txt
"""Custom "Valutatore" role scoped to a single LMS Batch.

A Valutatore is assigned by an admin inside a specific batch (the `valutatori`
Table MultiSelect custom field on LMS Batch). From then on they can, **only for
that batch**:

- view the batch admin dashboard, live classes and announcements;
- view the quiz answers of the students enrolled in that batch;
- view, grade and send the evaluation of the assignments of those students.

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


def quiz_submission_query_conditions(user: str | None = None) -> str:
	user = user or frappe.session.user
	if not _only_scoped_valutatore(user):
		return ""
	members = get_valutatore_member_emails(user)
	if not members:
		return "1=0"
	return f"`tabLMS Quiz Submission`.member IN ({_in_clause(members)})"


def assignment_submission_query_conditions(user: str | None = None) -> str:
	user = user or frappe.session.user
	if not _only_scoped_valutatore(user):
		return ""
	members = get_valutatore_member_emails(user)
	if not members:
		return "1=0"
	return f"`tabLMS Assignment Submission`.member IN ({_in_clause(members)})"


def enrollment_query_conditions(user: str | None = None) -> str:
	"""Scope the course-enrolment list (read-only dashboard) to the valutatore's
	courses."""
	user = user or frappe.session.user
	if not _only_scoped_valutatore(user):
		return ""
	courses = get_valutatore_course_names(user)
	if not courses:
		return "1=0"
	return f"`tabLMS Enrollment`.course IN ({_in_clause(courses)})"


def course_progress_query_conditions(user: str | None = None) -> str:
	"""Scope the per-lesson progress list (student drilldown) to the valutatore's
	courses."""
	user = user or frappe.session.user
	if not _only_scoped_valutatore(user):
		return ""
	courses = get_valutatore_course_names(user)
	if not courses:
		return "1=0"
	return f"`tabLMS Course Progress`.course IN ({_in_clause(courses)})"


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
	member = doc.get("member")
	if member and member in get_valutatore_member_emails(user):
		return True
	return False


def course_scoped_has_permission(doc, ptype: str = "read", user: str | None = None):
	"""Veto by-name access to a course-scoped row (LMS Enrollment / LMS Course
	Progress) outside the valutatore's courses. The list views are already
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
	course = doc.get("course")
	if course and course in get_valutatore_course_names(user):
		return True
	return False


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
		frappe.clear_cache(user=user)


def _row_members(rows) -> set[str]:
	return {row.valutatore for row in (rows or []) if getattr(row, "valutatore", None)}


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

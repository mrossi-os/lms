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

The "Valutatore" Role record itself is granted/revoked automatically when an
admin adds/removes a user from a batch's `valutatori` field (see
``sync_batch_valutatore_roles``), so it only acts as the technical container of
the doctype permissions.
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


# ---------------------------------------------------------------------------
# Row-level veto (has_permission)
# ---------------------------------------------------------------------------
def submission_has_permission(doc, ptype: str = "read", user: str | None = None):
	"""Veto by-name access to a submission outside the valutatore's batches.

	Returns ``False`` to deny, ``None`` to stay neutral (so the role DocPerms and
	other users are not affected).
	"""
	user = user or frappe.session.user
	if not _only_scoped_valutatore(user):
		return None
	member = doc.get("member")
	if member and member in get_valutatore_member_emails(user):
		return None
	return False


# ---------------------------------------------------------------------------
# Role lifecycle: keep the "Valutatore" Role aligned with batch assignments
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


def _is_valutatore_of_any_batch(user: str, exclude_batch: str | None = None) -> bool:
	filters = {"parenttype": "LMS Batch", "valutatore": user}
	if exclude_batch:
		filters["parent"] = ["!=", exclude_batch]
	return bool(frappe.db.exists("LMS Batch Valutatore", filters))


def _revoke_role_if_orphan(user: str, exclude_batch: str | None = None) -> None:
	if not _is_valutatore_of_any_batch(user, exclude_batch=exclude_batch):
		frappe.db.delete("Has Role", {"parent": user, "role": ROLE})
		frappe.clear_cache(user=user)


def _row_members(rows) -> set[str]:
	return {row.valutatore for row in (rows or []) if getattr(row, "valutatore", None)}


def sync_batch_valutatore_roles(doc, method: str | None = None) -> None:
	"""LMS Batch on_update: grant the role to current valutatori and revoke it
	from users who are no longer a valutatore of any batch."""
	current = _row_members(doc.get("valutatori"))
	for member in current:
		_ensure_role(member, ROLE)

	before = doc.get_doc_before_save()
	previous = _row_members(before.get("valutatori")) if before else set()
	for member in previous - current:
		_revoke_role_if_orphan(member, exclude_batch=doc.name)


def cleanup_batch_valutatore_roles(doc, method: str | None = None) -> None:
	"""LMS Batch on_trash: revoke the role from this batch's valutatori when they
	are not evaluating any other batch."""
	for member in _row_members(doc.get("valutatori")):
		_revoke_role_if_orphan(member, exclude_batch=doc.name)

# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

# Session states. Keep in sync with the doctype JSON `status` Select options.
STATUS_READY = "Ready"
STATUS_IN_PROGRESS = "In Progress"
STATUS_COMPLETED = "Completed"
STATUS_ABANDONED = "Abandoned"
STATUS_ERROR = "Error"
STATUS_NEEDS_REVIEW = "Needs Review"

# Terminal states: once a session reaches one, no further turns are accepted.
TERMINAL_STATUSES = frozenset({STATUS_COMPLETED, STATUS_ABANDONED, STATUS_ERROR, STATUS_NEEDS_REVIEW})


class LMSASimulationSession(Document):
	def before_insert(self):
		if not self.student:
			self.student = frappe.session.user
		if not self.started_at:
			self.started_at = frappe.utils.now_datetime()


def _access():
	# Imported here: the simulations package imports this module.
	from os_lms.os_lms.ai.simulations import access

	return access


def _in_clause(values) -> str:
	# frappe.db.escape() already wraps each value in quotes.
	return ",".join(frappe.db.escape(v, percent=False) for v in values)


def get_permission_query_conditions(user: str | None = None) -> str:
	"""List filter: the user's own sessions plus those they may review
	(ai/simulations/access.py: a Valutatore only their batches' students)."""
	user = user or frappe.session.user
	scope = _access().review_scope(user)
	if scope.full:
		return ""

	table = "`tabLMSA Simulation Session`"
	clauses = [f"{table}.student = {frappe.db.escape(user, percent=False)}"]
	if scope.courses:
		clauses.append(f"{table}.course IN ({_in_clause(scope.courses)})")
	for course, students in scope.students_by_course.items():
		if students:
			clauses.append(
				f"({table}.course = {frappe.db.escape(course, percent=False)} AND "
				f"{table}.student IN ({_in_clause(students)}))"
			)
	return f"({' OR '.join(clauses)})"


def has_permission(doc, ptype: str = "read", user: str | None = None) -> bool:
	"""Per-document gate.

	- Full access (Gestore, System Manager, Administrator): everything.
	- The session's student: their own session. The DocPerm grants no
	  create/write; the orchestrator writes server-side with
	  `ignore_permissions` after the endpoint has checked the owner.
	- Whoever may review it (Docente of the course, Valutatore of the
	  student's batch): read-only; sessions belong to the students.
	"""
	user = user or frappe.session.user
	access = _access()
	if access.has_full_access(user):
		return True
	if doc.student == user:
		return True
	if ptype not in {"read", "report", "print", "export", "email", "share"}:
		return False
	return access.can_review(doc.course, doc.student, user)

# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

# Roles that bypass all permission checks for the simulation feature.
ROLES_WITH_FULL_ACCESS = {"System Manager", "Moderator", "LMS Manager"}

# Session states. Keep in sync with the doctype JSON `status` Select options.
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


def get_permission_query_conditions(user: str | None = None) -> str:
	"""List filter: students see only their own sessions; instructors see all
	sessions for their courses; sysadmin/moderator/manager see everything.
	"""
	user = user or frappe.session.user
	if user == "Administrator":
		return ""

	roles = set(frappe.get_roles(user))
	if roles & ROLES_WITH_FULL_ACCESS:
		return ""

	if "Course Creator" in roles or "LMS Instructor" in roles:
		courses = frappe.get_all(
			"Course Instructor", filters={"instructor": user}, pluck="parent"
		)
		if not courses:
			return "1=0"
		quoted = ",".join("'" + frappe.db.escape(c, percent=False) + "'" for c in courses)
		return f"`tabLMSA Simulation Session`.course IN ({quoted})"

	if "LMS Student" in roles:
		return (
			f"`tabLMSA Simulation Session`.student = "
			f"'{frappe.db.escape(user, percent=False)}'"
		)

	return "1=0"


def has_permission(doc, ptype: str = "read", user: str | None = None) -> bool:
	"""Per-document gate.

	- Sysadmin / Moderator / LMS Manager: full access.
	- Course Creator / LMS Instructor of the session's course: read-only access
	  to any session of that course; never write (sessions are owned by students).
	- LMS Student: only their own sessions, and only while not in a terminal state
	  for writes (orchestrator drives transitions through `frappe.set_user` /
	  `ignore_permissions` server-side).
	"""
	user = user or frappe.session.user
	if user == "Administrator":
		return True

	roles = set(frappe.get_roles(user))
	if roles & ROLES_WITH_FULL_ACCESS:
		return True

	if "Course Creator" in roles or "LMS Instructor" in roles:
		if ptype not in {"read", "report", "print", "export", "email", "share"}:
			return False
		return bool(
			frappe.db.exists(
				"Course Instructor", {"parent": doc.course, "instructor": user}
			)
		)

	if "LMS Student" in roles:
		return doc.student == user

	return False

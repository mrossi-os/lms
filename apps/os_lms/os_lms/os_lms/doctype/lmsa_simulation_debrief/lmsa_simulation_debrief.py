# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

# Mirror Session's full-access roles
ROLES_WITH_FULL_ACCESS = {"System Manager", "Moderator", "LMS Manager"}

STATUS_PENDING = "Pending"
STATUS_READY = "Ready"
STATUS_NEEDS_REVIEW = "Needs Review"
STATUS_FAILED = "Failed"


class LMSASimulationDebrief(Document):
	# The AI score is indicative only: `passed` is no longer derived from it
	# and the schema's passing_threshold (docs/ai-simulator/
	# PIANO-esito-e-punteggio-coach.md). A person decides the outcome on the
	# simulations that have one.
	pass


def get_permission_query_conditions(user: str | None = None) -> str:
	"""Instructors see debriefs of their courses; sysadmin/moderator/manager
	see all. Students get none: the debrief keeps score, outcome and the raw
	model output, which the simulation page hides from them (it reads the
	debrief server-side and returns only what they may see)."""
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
		# frappe.db.escape() already wraps each value in quotes.
		quoted = ",".join(frappe.db.escape(c, percent=False) for c in courses)
		return f"`tabLMSA Simulation Debrief`.course IN ({quoted})"

	return "1=0"


def has_permission(doc, ptype: str = "read", user: str | None = None) -> bool:
	user = user or frappe.session.user
	if user == "Administrator":
		return True

	roles = set(frappe.get_roles(user))
	if roles & ROLES_WITH_FULL_ACCESS:
		return True

	if "Course Creator" in roles or "LMS Instructor" in roles:
		# Instructors can review (write the `instructor_review` field).
		return bool(
			frappe.db.exists(
				"Course Instructor", {"parent": doc.course, "instructor": user}
			)
		)

	# Students read their debrief only through the simulation page.
	return False

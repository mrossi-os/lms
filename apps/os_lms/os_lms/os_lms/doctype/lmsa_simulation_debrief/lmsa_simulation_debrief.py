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
	def before_save(self):
		# Re-evaluate `passed` whenever overall_score changes. Threshold comes
		# from the scenario's evaluation schema; we read it lazily to avoid
		# making this a hard dependency in the orchestrator's hot path.
		if self.overall_score is None or not self.scenario:
			return
		schema = frappe.db.get_value(
			"LMSA Simulation Scenario", self.scenario, "evaluation_schema"
		)
		if not schema:
			return
		threshold = frappe.db.get_value(
			"LMSA Evaluation Schema", schema, "passing_threshold"
		)
		if threshold is None:
			return
		self.passed = 1 if self.overall_score >= float(threshold) else 0


def get_permission_query_conditions(user: str | None = None) -> str:
	"""Students see only debriefs of their own sessions; instructors see
	debriefs of their courses; sysadmin/moderator/manager see all."""
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
		return f"`tabLMSA Simulation Debrief`.course IN ({quoted})"

	if "LMS Student" in roles:
		return (
			f"`tabLMSA Simulation Debrief`.student = "
			f"'{frappe.db.escape(user, percent=False)}'"
		)

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

	if "LMS Student" in roles:
		# Students may only READ their own debrief; never write.
		if ptype not in {"read", "report", "print", "export", "email", "share"}:
			return False
		return doc.student == user

	return False

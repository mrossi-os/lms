# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

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
	"""The debriefs of the sessions the user may review. Students get none:
	the debrief keeps scores, outcome and the raw model output, which the
	simulation page hides from them (it reads the debrief server-side and
	returns only what they may see)."""
	from os_lms.os_lms.ai.simulations import access

	user = user or frappe.session.user
	scope = access.review_scope(user)
	if scope.full:
		return ""

	table = "`tabLMSA Simulation Debrief`"
	clauses = []
	if scope.courses:
		quoted = ",".join(frappe.db.escape(c, percent=False) for c in scope.courses)
		clauses.append(f"{table}.course IN ({quoted})")
	for course, students in scope.students_by_course.items():
		if students:
			quoted = ",".join(frappe.db.escape(s, percent=False) for s in students)
			clauses.append(
				f"({table}.course = {frappe.db.escape(course, percent=False)} AND "
				f"{table}.student IN ({quoted}))"
			)
	return f"({' OR '.join(clauses)})" if clauses else "1=0"


def has_permission(doc, ptype: str = "read", user: str | None = None) -> bool:
	"""Reviewers of the session (ai/simulations/access.py) read and write the
	debrief; they write the teacher version (ai/simulations/teacher_review.py).
	Students read theirs only through the simulation page."""
	from os_lms.os_lms.ai.simulations import access

	return access.can_review(doc.course, doc.student, user or frappe.session.user)

# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document



class LMSASimulationScenario(Document):
	def before_insert(self):
		if not self.created_by_instructor:
			self.created_by_instructor = frappe.session.user

	def validate(self):
		self._validate_lesson_belongs_to_course()
		self._validate_learning_objectives_weights()

	def _validate_lesson_belongs_to_course(self):
		if not self.course_lesson:
			return
		lesson_course = frappe.db.get_value("Course Lesson", self.course_lesson, "course")
		if lesson_course != self.lms_course:
			frappe.throw(
				_("Lesson {0} does not belong to course {1}.").format(
					self.course_lesson, self.lms_course
				)
			)

	def _validate_learning_objectives_weights(self):
		if not self.learning_objectives:
			return
		total = sum((row.weight or 0.0) for row in self.learning_objectives)
		if total <= 0:
			return  # objectives are optional; absent weights are accepted
		if abs(total - 1.0) > 0.001:
			frappe.throw(
				_(
					"Learning objective weights should sum to 1.0 when set (current sum: {0})."
				).format(round(total, 4))
			)


def _access():
	# Imported here: the simulations package imports the session doctype.
	from os_lms.os_lms.ai.simulations import access

	return access


def _in_clause(values) -> str:
	# frappe.db.escape() already wraps each value in quotes.
	return ",".join(frappe.db.escape(v, percent=False) for v in values)


def get_permission_query_conditions(user: str | None = None) -> str:
	"""List filter: every scenario of the courses whose simulations the user
	manages (ai/simulations/access.py), plus the Published scenarios of the
	courses they are enrolled in."""
	user = user or frappe.session.user
	managed = _access().managed_courses(user)
	if managed is None:
		return ""

	clauses = []
	if managed:
		clauses.append(f"`tabLMSA Simulation Scenario`.lms_course IN ({_in_clause(managed)})")
	enrolled = frappe.get_all("LMS Enrollment", filters={"member": user}, pluck="course")
	if enrolled:
		clauses.append(
			f"(`tabLMSA Simulation Scenario`.lms_course IN ({_in_clause(enrolled)}) AND "
			f"`tabLMSA Simulation Scenario`.status = 'Published')"
		)
	return f"({' OR '.join(clauses)})" if clauses else "1=0"


def has_permission(doc, ptype: str = "read", user: str | None = None) -> bool:
	"""Per-document gate. Mirrors the list filter but on a single doc."""
	user = user or frappe.session.user
	if _access().can_manage_course(doc.lms_course, user):
		return True
	if ptype == "read" and doc.status == "Published":
		return bool(frappe.db.exists("LMS Enrollment", {"member": user, "course": doc.lms_course}))
	return False

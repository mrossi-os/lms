# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

ROLES_WITH_FULL_ACCESS = {"System Manager", "Moderator", "LMS Manager"}


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


def get_permission_query_conditions(user: str | None = None) -> str:
	"""Filter list view: instructors see only scenarios of their courses;
	students see only Published scenarios for courses they are enrolled in.
	Sysadmin / Moderator / LMS Manager have no filter.
	"""
	user = user or frappe.session.user
	if user == "Administrator":
		return ""

	roles = set(frappe.get_roles(user))
	if roles & ROLES_WITH_FULL_ACCESS:
		return ""

	# Instructor: only courses they own
	if "Course Creator" in roles or "LMS Instructor" in roles:
		courses = frappe.get_all(
			"Course Instructor",
			filters={"instructor": user},
			pluck="parent",
		)
		if not courses:
			return "1=0"
		quoted = ",".join("'" + frappe.db.escape(c, percent=False) + "'" for c in courses)
		return f"`tabLMSA Simulation Scenario`.lms_course IN ({quoted})"

	# Student: only Published scenarios for enrolled courses
	if "LMS Student" in roles:
		courses = frappe.get_all(
			"LMS Enrollment",
			filters={"member": user},
			pluck="course",
		)
		if not courses:
			return "1=0"
		quoted = ",".join("'" + frappe.db.escape(c, percent=False) + "'" for c in courses)
		return (
			f"(`tabLMSA Simulation Scenario`.lms_course IN ({quoted}) AND "
			f"`tabLMSA Simulation Scenario`.status = 'Published')"
		)

	return "1=0"


def has_permission(doc, ptype: str = "read", user: str | None = None) -> bool:
	"""Per-document gate. Mirrors the list filter but on a single doc."""
	user = user or frappe.session.user
	if user == "Administrator":
		return True
	roles = set(frappe.get_roles(user))
	if roles & ROLES_WITH_FULL_ACCESS:
		return True

	if "Course Creator" in roles or "LMS Instructor" in roles:
		if ptype in {"read", "report", "print", "export", "email", "share"}:
			return frappe.db.exists(
				"Course Instructor",
				{"parent": doc.lms_course, "instructor": user},
			)
		# write/delete only for the course's instructors
		return frappe.db.exists(
			"Course Instructor",
			{"parent": doc.lms_course, "instructor": user},
		)

	if "LMS Student" in roles:
		if ptype != "read":
			return False
		if doc.status != "Published":
			return False
		return frappe.db.exists(
			"LMS Enrollment", {"member": user, "course": doc.lms_course}
		)

	return False

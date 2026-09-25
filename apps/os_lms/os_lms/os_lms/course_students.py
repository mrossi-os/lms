"""Removal of students from a course, from the course dashboard.

Two levels, gated server-side (the SPA only mirrors these checks):

- **Remove** (Administrator + Gestore): deletes the ``LMS Enrollment`` only.
  Progress, submissions and certificates stay, so re-enrolling the student
  brings them back.
- **Purge** (Administrator only): also deletes everything the student produced
  in that course, certificates included. A TrueSkills badge already issued stays
  valid on TrueSkills: its API has no revoke endpoint.

Every deletion goes through ``frappe.delete_doc``, so each record is kept as a
``Deleted Document`` that an administrator can restore from the Desk.
"""

import frappe
from frappe import _

REMOVE_ROLES = ("System Manager", "Gestore")
PURGE_ROLES = ("System Manager",)

# Records keyed by (member field, course). Deleted before the enrollment.
COURSE_MEMBER_DOCTYPES = (
	("LMS Assignment Submission", "member"),
	("LMS Video Watch Duration", "member"),
	("LMS Lesson Note", "member"),
	("LMS Certificate Request", "member"),
	("LMS Certificate Evaluation", "member"),
	("LMSA Query Log", "member"),
	("LMS Course Interest", "user"),
	("LMS Course Review", "owner"),
)


def can_remove_course_students() -> bool:
	roles = frappe.get_roles()
	return any(role in roles for role in REMOVE_ROLES)


def can_purge_course_students() -> bool:
	roles = frappe.get_roles()
	return any(role in roles for role in PURGE_ROLES)


@frappe.whitelist()
def remove_course_students(course: str, enrollments: list[str], purge: bool = False) -> dict:
	"""Remove the given enrollments from ``course``; with ``purge`` also delete their data."""
	purge = frappe.utils.sbool(purge)
	if not can_remove_course_students():
		frappe.throw(_("You are not allowed to remove students from this course."), frappe.PermissionError)
	if purge and not can_purge_course_students():
		frappe.throw(_("Only an administrator can delete a student's course data."), frappe.PermissionError)

	if isinstance(enrollments, str):
		enrollments = frappe.parse_json(enrollments)
	rows = frappe.get_all(
		"LMS Enrollment",
		filters={"name": ["in", enrollments or []], "course": course},
		fields=["name", "member"],
	)
	if len(rows) != len(set(enrollments or [])):
		frappe.throw(_("Some of the selected enrollments do not belong to this course."))

	for row in rows:
		if purge:
			_purge_member_course_data(course, row.member, row.name)
		else:
			_delete("LMS Enrollment", row.name)

	return {"removed": len(rows), "purged": purge}


def _purge_member_course_data(course: str, member: str, enrollment: str) -> None:
	# Order matters: records that link to others go first (violation logs →
	# quiz submissions, simulation turns/debriefs/traces → sessions), the
	# enrollment goes before the certificate it links to, and course progress
	# goes after the enrollment so its after_delete recalculation only rolls up
	# program progress instead of rewriting an enrollment about to disappear.
	quiz_submissions = frappe.get_all(
		"LMS Quiz Submission", filters={"course": course, "member": member}, pluck="name"
	)
	if quiz_submissions:
		_delete_where("LMS Quiz Violation Log", {"quiz_submission": ["in", quiz_submissions]})
	_delete_all("LMS Quiz Submission", quiz_submissions)

	for doctype, member_field in COURSE_MEMBER_DOCTYPES:
		_delete_where(doctype, {"course": course, member_field: member})

	_purge_programming_exercises(course, member)
	_purge_simulations(course, member)

	_delete("LMS Enrollment", enrollment)
	_delete_where("LMS Course Progress", {"course": course, "member": member})

	certificates = frappe.get_all(
		"LMS Certificate", filters={"course": course, "member": member}, pluck="name"
	)
	if certificates:
		_delete_where("TrueSkills Issue Log", {"lms_certificate": ["in", certificates]})
	_delete_all("LMS Certificate", certificates)


def _purge_programming_exercises(course: str, member: str) -> None:
	# Exercise submissions carry no course: the course's exercises are the
	# "program" blocks embedded in its lessons.
	from lms.lms.api import get_assessment_from_lesson

	exercises = [name for name in get_assessment_from_lesson(course, "program") if name]
	if exercises:
		_delete_where(
			"LMS Programming Exercise Submission",
			{"exercise": ["in", exercises], "member": member},
		)


def _purge_simulations(course: str, member: str) -> None:
	sessions = frappe.get_all(
		"LMSA Simulation Session", filters={"course": course, "student": member}, pluck="name"
	)
	if sessions:
		_delete_where("LMSA Simulation Turn", {"session": ["in", sessions]})
		_delete_where("LMSA Evaluation Trace", {"source_session": ["in", sessions]})
		_delete_where("LMSA Simulation Debrief", {"session": ["in", sessions]})
	_delete_where("LMSA Simulation Debrief", {"course": course, "student": member})
	_delete_all("LMSA Simulation Session", sessions)


def _delete_where(doctype: str, filters: dict) -> None:
	_delete_all(doctype, frappe.get_all(doctype, filters=filters, pluck="name"))


def _delete_all(doctype: str, names: list[str]) -> None:
	for name in names:
		_delete(doctype, name)


def _delete(doctype: str, name: str) -> None:
	frappe.delete_doc(doctype, name, ignore_permissions=True)

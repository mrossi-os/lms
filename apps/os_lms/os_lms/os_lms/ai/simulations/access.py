"""Who may manage and review AI simulations.

docs/ai-simulator/PIANO-esito-e-punteggio-coach.md, phase 5. The platform
works with four figures (Gestore, Docente, Valutatore, LMS Student); a
Moderator is never used on its own, so it grants nothing here.

- Gestore, System Manager, Administrator: everything, on every course.
- Docente (or Course Creator) listed among a course's instructors: the
  course's scenarios, every session on them, reports and teacher versions.
- Valutatore listed in a batch's valutatori: the scenarios of the batch's
  courses, but sessions, reports and teacher versions only of the students
  enrolled in that batch.
- Student: their own sessions, checked by the callers.

A user often holds several figures: what they may do is the union.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import frappe

from os_lms.os_lms import valutatore

FULL_ACCESS_ROLES = frozenset({"Gestore", "System Manager"})
INSTRUCTOR_ROLES = frozenset({"Docente", "Course Creator"})


def has_full_access(user: str | None = None) -> bool:
	user = user or frappe.session.user
	return user == "Administrator" or bool(FULL_ACCESS_ROLES & set(frappe.get_roles(user)))


def instructor_courses(user: str | None = None) -> set[str]:
	"""Courses where the user is listed as an instructor, if their roles make
	them one."""
	user = user or frappe.session.user
	if not INSTRUCTOR_ROLES & set(frappe.get_roles(user)):
		return set()
	return set(
		frappe.get_all(
			"Course Instructor",
			filters={"instructor": user, "parenttype": "LMS Course"},
			pluck="parent",
		)
	)


def valutatore_batches_by_course(user: str | None = None) -> dict[str, set[str]]:
	"""{course: batches where the user is a valutatore and that hold it}."""
	user = user or frappe.session.user
	if not valutatore.is_valutatore(user):
		return {}
	batches = valutatore.get_valutatore_batches(user)
	if not batches:
		return {}
	by_course: dict[str, set[str]] = {}
	for row in frappe.get_all(
		"Batch Course",
		filters={"parent": ["in", batches], "parenttype": "LMS Batch"},
		fields=["parent", "course"],
	):
		by_course.setdefault(row.course, set()).add(row.parent)
	return by_course


def managed_courses(user: str | None = None) -> set[str] | None:
	"""Courses whose scenarios the user may create, edit and list; None means
	every course."""
	user = user or frappe.session.user
	if has_full_access(user):
		return None
	return instructor_courses(user) | set(valutatore_batches_by_course(user))


def can_manage_course(course: str | None, user: str | None = None) -> bool:
	if not course:
		return False
	courses = managed_courses(user)
	return courses is None or course in courses


def may_author(user: str | None = None) -> bool:
	"""Whether the user manages simulations on at least one course (creating
	an evaluation schema or drafting with the AI before picking a course)."""
	courses = managed_courses(user)
	return courses is None or bool(courses)


@dataclass(frozen=True)
class ReviewScope:
	"""The sessions a user may review: every student of `courses`, and only
	the listed students on the courses of `students_by_course`."""

	full: bool = False
	courses: frozenset[str] = frozenset()
	students_by_course: dict[str, frozenset[str]] = field(default_factory=dict)

	def course_names(self) -> set[str]:
		return set(self.courses) | set(self.students_by_course)

	def allows(self, course: str | None, student: str | None) -> bool:
		if self.full:
			return True
		if course in self.courses:
			return True
		return student in self.students_by_course.get(course, frozenset())


def review_scope(user: str | None = None) -> ReviewScope:
	user = user or frappe.session.user
	if has_full_access(user):
		return ReviewScope(full=True)
	courses = instructor_courses(user)
	students_by_course: dict[str, frozenset[str]] = {}
	for course, batches in valutatore_batches_by_course(user).items():
		if course in courses:
			continue
		students_by_course[course] = frozenset(
			frappe.get_all(
				"LMS Batch Enrollment",
				filters={"batch": ["in", list(batches)]},
				pluck="member",
			)
		)
	return ReviewScope(courses=frozenset(courses), students_by_course=students_by_course)


def can_review(course: str | None, student: str | None, user: str | None = None) -> bool:
	"""Whether the user may read another person's session of `course` and
	write its teacher version."""
	return review_scope(user).allows(course, student)

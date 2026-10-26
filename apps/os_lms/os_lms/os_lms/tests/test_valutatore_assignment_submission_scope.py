"""A scoped Valutatore reads an assignment submission only for a student AND assignment
of the same batch (OWASP L-6, the same rule as quizzes).

Before, the list and the by-name check were scoped by student only: a Valutatore saw
the assignments their students handed in on courses outside the batch.

Everything is created under fixed ``zz-vas-*`` names, removed in tearDown (exact names,
never a broad filter) and the test runner rolls back the transaction anyway.
"""

from __future__ import annotations

from unittest.mock import patch

import frappe
from frappe.tests import UnitTestCase

from os_lms.os_lms import valutatore

VALUTATORE = "zz-vas-valutatore@example.com"
BATCH_A = "zz-vas-batch-a"
BATCH_B = "zz-vas-batch-b"
COURSE_A = "zz-vas-course-a"
COURSE_B = "zz-vas-course-b"
LESSON_A = "zz-vas-lesson-a"  # lesson of COURSE_A the submission was made from
LESSON_PLACING_A = "zz-vas-lesson-placing-a"  # lesson of COURSE_A placing an assignment
STUDENT_A = "zz-vas-student-a@example.com"
STUDENT_B = "zz-vas-student-b@example.com"
STRANGER = "zz-vas-stranger@example.com"

ASSIGNMENT_COURSE_A = "zz-vas-asg-course-a"  # LMS Assignment.course = COURSE_A
ASSIGNMENT_COURSE_B = "zz-vas-asg-course-b"  # LMS Assignment.course = COURSE_B
ASSIGNMENT_FROM_LESSON_A = "zz-vas-asg-from-lesson-a"  # no course, submitted from LESSON_A
ASSIGNMENT_PLACED_A = "zz-vas-asg-placed-a"  # no course, placed in LESSON_PLACING_A
ASSIGNMENT_ASSESSED_A = "zz-vas-asg-assessed-a"  # listed in the assessments of BATCH_A
ASSIGNMENT_ORPHAN = "zz-vas-asg-orphan"  # belongs to no batch
ASSIGNMENTS = (
	(ASSIGNMENT_COURSE_A, COURSE_A),
	(ASSIGNMENT_COURSE_B, COURSE_B),
	(ASSIGNMENT_FROM_LESSON_A, None),
	(ASSIGNMENT_PLACED_A, None),
	(ASSIGNMENT_ASSESSED_A, None),
	(ASSIGNMENT_ORPHAN, None),
)

# name: (member, assignment, lesson)
SUBMISSIONS = {
	"zz-vas-sub-a-course": (STUDENT_A, ASSIGNMENT_COURSE_A, None),
	"zz-vas-sub-a-lesson": (STUDENT_A, ASSIGNMENT_FROM_LESSON_A, LESSON_A),
	"zz-vas-sub-a-placed": (STUDENT_A, ASSIGNMENT_PLACED_A, None),
	"zz-vas-sub-a-assessed": (STUDENT_A, ASSIGNMENT_ASSESSED_A, None),
	"zz-vas-sub-a-other-batch": (STUDENT_A, ASSIGNMENT_COURSE_B, None),
	"zz-vas-sub-a-orphan": (STUDENT_A, ASSIGNMENT_ORPHAN, None),
	"zz-vas-sub-b-course-b": (STUDENT_B, ASSIGNMENT_COURSE_B, None),
	"zz-vas-sub-b-course-a": (STUDENT_B, ASSIGNMENT_COURSE_A, None),
	"zz-vas-sub-stranger": (STRANGER, ASSIGNMENT_COURSE_A, None),
}


def _insert(doctype: str, **values) -> None:
	frappe.get_doc({"doctype": doctype, **values}).db_insert()


class TestValutatoreAssignmentSubmissionScope(UnitTestCase):
	def setUp(self):
		super().setUp()
		self._cleanup()
		for batch in (BATCH_A, BATCH_B):
			_insert("LMS Batch", name=batch, title=batch)
		for name, batch, student in (
			("zz-vas-enr-a", BATCH_A, STUDENT_A),
			("zz-vas-enr-b", BATCH_B, STUDENT_B),
		):
			_insert("LMS Batch Enrollment", name=name, batch=batch, member=student)
		for batch, course in ((BATCH_A, COURSE_A), (BATCH_B, COURSE_B)):
			_insert(
				"Batch Course",
				parent=batch,
				parenttype="LMS Batch",
				parentfield="courses",
				course=course,
			)
		for assignment, course in ASSIGNMENTS:
			_insert("LMS Assignment", name=assignment, title=assignment, course=course)
		for lesson in (LESSON_A, LESSON_PLACING_A):
			_insert("Course Lesson", name=lesson, course=COURSE_A)
		_insert(
			"LMS Lesson Assessment",
			parent=LESSON_PLACING_A,
			parenttype="Course Lesson",
			parentfield="assessments",
			assessment_type="LMS Assignment",
			assessment_name=ASSIGNMENT_PLACED_A,
		)
		_insert(
			"LMS Assessment",
			parent=BATCH_A,
			parenttype="LMS Batch",
			parentfield="assessment",
			assessment_type="LMS Assignment",
			assessment_name=ASSIGNMENT_ASSESSED_A,
		)
		for name, (member, assignment, lesson) in SUBMISSIONS.items():
			_insert(
				"LMS Assignment Submission",
				name=name,
				member=member,
				assignment=assignment,
				lesson=lesson,
			)

	def tearDown(self):
		self._cleanup()
		super().tearDown()

	def _cleanup(self) -> None:
		for doctype, names in (
			("LMS Assignment Submission", list(SUBMISSIONS)),
			("Course Lesson", [LESSON_A, LESSON_PLACING_A]),
			("LMS Assignment", [assignment for assignment, _course in ASSIGNMENTS]),
			("LMS Batch Enrollment", ["zz-vas-enr-a", "zz-vas-enr-b"]),
			("LMS Batch", [BATCH_A, BATCH_B]),
		):
			frappe.db.delete(doctype, {"name": ("in", names)})
		# Child rows have an automatic numeric name: remove them through their
		# (fixed-name) parents.
		for doctype in ("LMS Assessment", "Batch Course"):
			frappe.db.delete(doctype, {"parent": ("in", [BATCH_A, BATCH_B])})
		frappe.db.delete("LMS Lesson Assessment", {"parent": LESSON_PLACING_A})

	def _scoped(self, batches: list[str]):
		return (
			patch.object(valutatore, "_only_scoped_valutatore", return_value=True),
			patch.object(valutatore, "get_valutatore_batches", return_value=batches),
		)

	def _visible(self, batches: list[str]) -> set[str]:
		scoped, batches_patch = self._scoped(batches)
		with scoped, batches_patch:
			condition = valutatore.assignment_submission_query_conditions(VALUTATORE)
		rows = frappe.db.sql(
			f"SELECT name FROM `tabLMS Assignment Submission` WHERE name IN %s AND {condition}",
			(tuple(SUBMISSIONS),),
		)
		return {row[0] for row in rows}

	def _readable(self, name: str, batches: list[str]) -> bool:
		doc = frappe.get_doc("LMS Assignment Submission", name)
		scoped, batches_patch = self._scoped(batches)
		with scoped, batches_patch:
			return valutatore.submission_has_permission(doc, "read", VALUTATORE)

	def test_assignment_is_matched_by_course_lesson_placement_or_assessment(self):
		self.assertEqual(
			self._visible([BATCH_A]),
			{
				"zz-vas-sub-a-course",
				"zz-vas-sub-a-lesson",
				"zz-vas-sub-a-placed",
				"zz-vas-sub-a-assessed",
			},
		)

	def test_assignment_of_a_course_outside_the_batch_is_hidden(self):
		visible = self._visible([BATCH_A])
		self.assertNotIn("zz-vas-sub-a-other-batch", visible)
		self.assertNotIn("zz-vas-sub-a-orphan", visible)
		self.assertNotIn("zz-vas-sub-stranger", visible)

	def test_valutatore_of_two_batches_does_not_cross_them(self):
		visible = self._visible([BATCH_A, BATCH_B])
		self.assertNotIn("zz-vas-sub-a-other-batch", visible)
		self.assertNotIn("zz-vas-sub-b-course-a", visible)
		self.assertIn("zz-vas-sub-b-course-b", visible)
		self.assertIn("zz-vas-sub-a-course", visible)

	def test_valutatore_without_batches_sees_nothing(self):
		scoped, batches_patch = self._scoped([])
		with scoped, batches_patch:
			self.assertEqual(valutatore.assignment_submission_query_conditions(VALUTATORE), "1=0")
		self.assertFalse(self._readable("zz-vas-sub-a-course", []))

	def test_user_with_a_broader_role_is_not_narrowed(self):
		with patch.object(valutatore, "_only_scoped_valutatore", return_value=False):
			self.assertEqual(valutatore.assignment_submission_query_conditions(VALUTATORE), "")
			doc = frappe.get_doc("LMS Assignment Submission", "zz-vas-sub-stranger")
			self.assertTrue(valutatore.submission_has_permission(doc, "read", VALUTATORE))

	def test_by_name_access_follows_the_same_rule(self):
		self.assertTrue(self._readable("zz-vas-sub-a-course", [BATCH_A]))
		self.assertTrue(self._readable("zz-vas-sub-a-placed", [BATCH_A]))
		self.assertFalse(self._readable("zz-vas-sub-a-other-batch", [BATCH_A]))
		self.assertFalse(self._readable("zz-vas-sub-a-orphan", [BATCH_A, BATCH_B]))
		self.assertFalse(self._readable("zz-vas-sub-stranger", [BATCH_A, BATCH_B]))

	def test_a_new_submission_keeps_the_membership_rule(self):
		doc = frappe.new_doc("LMS Assignment Submission")
		doc.member = STUDENT_A
		with (
			patch.object(valutatore, "_only_scoped_valutatore", return_value=True),
			patch.object(valutatore, "get_valutatore_batches", return_value=[BATCH_A]),
			patch.object(valutatore, "get_valutatore_member_emails", return_value=[STUDENT_A]),
		):
			self.assertTrue(valutatore.submission_has_permission(doc, "read", VALUTATORE))
			doc.member = STRANGER
			self.assertFalse(valutatore.submission_has_permission(doc, "read", VALUTATORE))

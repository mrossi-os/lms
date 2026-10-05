"""A scoped Valutatore reads a quiz submission only for a student AND quiz of the same batch.

The collaudo of the v2.64 walk (test 2.6) showed that the list was scoped by student
only: a Valutatore of two batches saw the students of one batch on the quizzes of the
other, and every quiz of a student, whatever batch it belonged to.

Everything is created under fixed ``zz-vsc-*`` names, removed in tearDown (exact names,
never a broad filter) and the test runner rolls back the transaction anyway.
"""

from __future__ import annotations

from unittest.mock import patch

import frappe
from frappe.tests import UnitTestCase

from os_lms.os_lms import valutatore

VALUTATORE = "zz-vsc-valutatore@example.com"
BATCH_A = "zz-vsc-batch-a"
BATCH_B = "zz-vsc-batch-b"
COURSE_A = "zz-vsc-course-a"
COURSE_B = "zz-vsc-course-b"
COURSE_LESSON = "zz-vsc-course-lesson"
STUDENT_A = "zz-vsc-student-a@example.com"
STUDENT_B = "zz-vsc-student-b@example.com"
STRANGER = "zz-vsc-stranger@example.com"

QUIZ_COURSE_A = "zz-vsc-quiz-course-a"  # LMS Quiz.course = COURSE_A
QUIZ_COURSE_B = "zz-vsc-quiz-course-b"  # LMS Quiz.course = COURSE_B
QUIZ_LESSON_A = "zz-vsc-quiz-lesson-a"  # embedded in a lesson of COURSE_A, quiz.course empty
QUIZ_ASSESSED_A = "zz-vsc-quiz-assessed-a"  # listed in the assessments of BATCH_A
QUIZ_ORPHAN = "zz-vsc-quiz-orphan"  # belongs to no batch

# Proctoring log rows hung off two of the submissions above.
LOGS = {
	"zz-vsc-log-in-scope": "zz-vsc-sub-a-course",
	"zz-vsc-log-other-batch": "zz-vsc-sub-a-other-batch-quiz",
}

SUBMISSIONS = {
	"zz-vsc-sub-a-course": (STUDENT_A, QUIZ_COURSE_A),
	"zz-vsc-sub-a-lesson": (STUDENT_A, QUIZ_LESSON_A),
	"zz-vsc-sub-a-assessed": (STUDENT_A, QUIZ_ASSESSED_A),
	"zz-vsc-sub-a-other-batch-quiz": (STUDENT_A, QUIZ_COURSE_B),
	"zz-vsc-sub-a-orphan": (STUDENT_A, QUIZ_ORPHAN),
	"zz-vsc-sub-b-course-b": (STUDENT_B, QUIZ_COURSE_B),
	"zz-vsc-sub-b-course-a": (STUDENT_B, QUIZ_COURSE_A),
	"zz-vsc-sub-stranger": (STRANGER, QUIZ_COURSE_A),
}


def _insert(doctype: str, **values) -> None:
	frappe.get_doc({"doctype": doctype, **values}).db_insert()


class TestValutatoreQuizSubmissionScope(UnitTestCase):
	def setUp(self):
		super().setUp()
		self._cleanup()
		for batch in (BATCH_A, BATCH_B):
			_insert("LMS Batch", name=batch, title=batch)
		for name, batch, student in (
			("zz-vsc-enr-a", BATCH_A, STUDENT_A),
			("zz-vsc-enr-b", BATCH_B, STUDENT_B),
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
		for quiz, course in (
			(QUIZ_COURSE_A, COURSE_A),
			(QUIZ_COURSE_B, COURSE_B),
			(QUIZ_LESSON_A, None),
			(QUIZ_ASSESSED_A, None),
			(QUIZ_ORPHAN, None),
		):
			_insert("LMS Quiz", name=quiz, title=quiz, course=course)
		_insert("Course Lesson", name=COURSE_LESSON, course=COURSE_A, quiz_id=QUIZ_LESSON_A)
		_insert(
			"LMS Assessment",
			parent=BATCH_A,
			parenttype="LMS Batch",
			parentfield="assessment",
			assessment_type="LMS Quiz",
			assessment_name=QUIZ_ASSESSED_A,
		)
		for name, (member, quiz) in SUBMISSIONS.items():
			_insert("LMS Quiz Submission", name=name, member=member, quiz=quiz)
		for name, submission in LOGS.items():
			_insert("LMS Quiz Violation Log", name=name, quiz_submission=submission)

	def tearDown(self):
		self._cleanup()
		super().tearDown()

	def _cleanup(self) -> None:
		for doctype, names in (
			("LMS Quiz Violation Log", list(LOGS)),
			("LMS Quiz Submission", list(SUBMISSIONS)),
			("Course Lesson", [COURSE_LESSON]),
			(
				"LMS Quiz",
				[QUIZ_COURSE_A, QUIZ_COURSE_B, QUIZ_LESSON_A, QUIZ_ASSESSED_A, QUIZ_ORPHAN],
			),
			("LMS Batch Enrollment", ["zz-vsc-enr-a", "zz-vsc-enr-b"]),
			("LMS Batch", [BATCH_A, BATCH_B]),
		):
			frappe.db.delete(doctype, {"name": ("in", names)})
		# Child rows have an automatic numeric name: remove them through their
		# (fixed-name) parents.
		for doctype in ("LMS Assessment", "Batch Course"):
			frappe.db.delete(doctype, {"parent": ("in", [BATCH_A, BATCH_B])})

	def _visible(self, batches: list[str]) -> set[str]:
		with (
			patch.object(valutatore, "_only_scoped_valutatore", return_value=True),
			patch.object(valutatore, "get_valutatore_batches", return_value=batches),
		):
			condition = valutatore.quiz_submission_query_conditions(VALUTATORE)
		rows = frappe.db.sql(
			f"SELECT name FROM `tabLMS Quiz Submission` WHERE name IN %s AND {condition}",
			(tuple(SUBMISSIONS),),
		)
		return {row[0] for row in rows}

	def _readable(self, name: str, batches: list[str]) -> bool:
		doc = frappe.get_doc("LMS Quiz Submission", name)
		with (
			patch.object(valutatore, "_only_scoped_valutatore", return_value=True),
			patch.object(valutatore, "get_valutatore_batches", return_value=batches),
		):
			return valutatore.quiz_submission_has_permission(doc, "read", VALUTATORE)

	def test_quiz_is_matched_by_course_lesson_or_assessment(self):
		self.assertEqual(
			self._visible([BATCH_A]),
			{"zz-vsc-sub-a-course", "zz-vsc-sub-a-lesson", "zz-vsc-sub-a-assessed"},
		)

	def test_valutatore_of_two_batches_does_not_cross_them(self):
		visible = self._visible([BATCH_A, BATCH_B])
		# STUDENT_A on the quiz of batch B and STUDENT_B on the quiz of batch A are
		# students and quizzes of different batches: hidden even though the
		# Valutatore evaluates both.
		self.assertNotIn("zz-vsc-sub-a-other-batch-quiz", visible)
		self.assertNotIn("zz-vsc-sub-b-course-a", visible)
		self.assertIn("zz-vsc-sub-b-course-b", visible)
		self.assertIn("zz-vsc-sub-a-course", visible)

	def test_quiz_of_no_batch_and_stranger_are_hidden(self):
		visible = self._visible([BATCH_A, BATCH_B])
		self.assertNotIn("zz-vsc-sub-a-orphan", visible)
		self.assertNotIn("zz-vsc-sub-stranger", visible)

	def test_valutatore_without_batches_sees_nothing(self):
		with (
			patch.object(valutatore, "_only_scoped_valutatore", return_value=True),
			patch.object(valutatore, "get_valutatore_batches", return_value=[]),
		):
			self.assertEqual(valutatore.quiz_submission_query_conditions(VALUTATORE), "1=0")

	def test_user_with_a_broader_role_is_not_narrowed(self):
		with patch.object(valutatore, "_only_scoped_valutatore", return_value=False):
			self.assertEqual(valutatore.quiz_submission_query_conditions(VALUTATORE), "")
			doc = frappe.get_doc("LMS Quiz Submission", "zz-vsc-sub-stranger")
			self.assertTrue(valutatore.quiz_submission_has_permission(doc, "read", VALUTATORE))

	def test_by_name_access_follows_the_same_rule(self):
		self.assertTrue(self._readable("zz-vsc-sub-a-course", [BATCH_A]))
		self.assertTrue(self._readable("zz-vsc-sub-a-lesson", [BATCH_A]))
		self.assertFalse(self._readable("zz-vsc-sub-a-orphan", [BATCH_A]))
		self.assertFalse(self._readable("zz-vsc-sub-a-other-batch-quiz", [BATCH_A, BATCH_B]))
		self.assertFalse(self._readable("zz-vsc-sub-stranger", [BATCH_A, BATCH_B]))

	def _visible_logs(self, batches: list[str]) -> set[str]:
		with (
			patch.object(valutatore, "_only_scoped_valutatore", return_value=True),
			patch.object(valutatore, "get_valutatore_batches", return_value=batches),
		):
			condition = valutatore.violation_log_query_conditions(VALUTATORE)
		rows = frappe.db.sql(
			f"SELECT name FROM `tabLMS Quiz Violation Log` WHERE name IN %s AND {condition}",
			(tuple(LOGS),),
		)
		return {row[0] for row in rows}

	def test_proctoring_log_follows_its_submission(self):
		# The camera stills inherit the audience of these rows.
		self.assertEqual(self._visible_logs([BATCH_A]), {"zz-vsc-log-in-scope"})
		self.assertEqual(self._visible_logs([BATCH_A, BATCH_B]), {"zz-vsc-log-in-scope"})

	def test_proctoring_log_by_name_follows_its_submission(self):
		def readable(name: str) -> bool:
			doc = frappe.get_doc("LMS Quiz Violation Log", name)
			with (
				patch.object(valutatore, "_only_scoped_valutatore", return_value=True),
				patch.object(valutatore, "get_valutatore_batches", return_value=[BATCH_A, BATCH_B]),
			):
				return valutatore.violation_log_has_permission(doc, "read", VALUTATORE)

		self.assertTrue(readable("zz-vsc-log-in-scope"))
		self.assertFalse(readable("zz-vsc-log-other-batch"))

	def test_proctoring_log_of_a_user_with_a_broader_role_is_not_narrowed(self):
		with patch.object(valutatore, "_only_scoped_valutatore", return_value=False):
			self.assertEqual(valutatore.violation_log_query_conditions(VALUTATORE), "")
			doc = frappe.get_doc("LMS Quiz Violation Log", "zz-vsc-log-other-batch")
			self.assertTrue(valutatore.violation_log_has_permission(doc, "read", VALUTATORE))

	def test_valutatore_without_batches_sees_no_log(self):
		with (
			patch.object(valutatore, "_only_scoped_valutatore", return_value=True),
			patch.object(valutatore, "get_valutatore_batches", return_value=[]),
		):
			self.assertEqual(valutatore.violation_log_query_conditions(VALUTATORE), "1=0")

"""A graded assignment submission is frozen for the student (OWASP M-06).

The SPA and the mobile app stop editing once the status leaves "Not Graded"; the
server only reverted the grading fields, so through frappe.client a student kept the
Pass and replaced the answer, or moved the graded submission onto another assignment.
Everything runs inside the test transaction and is rolled back.
"""

from __future__ import annotations

import frappe
from frappe.tests import UnitTestCase

STUDENT = "graded-submission-student@example.com"
ASSIGNMENT = "graded-submission-test-assignment"
OTHER_ASSIGNMENT = "graded-submission-test-other"
SUBMISSION = "graded-submission-test-submission"


class TestGradedSubmissionFrozen(UnitTestCase):
	def setUp(self):
		if not frappe.db.exists("User", STUDENT):
			user = frappe.get_doc(
				{"doctype": "User", "email": STUDENT, "first_name": "Graded", "send_welcome_email": 0}
			)
			user.append("roles", {"role": "LMS Student"})
			user.insert(ignore_permissions=True)
		for name in (ASSIGNMENT, OTHER_ASSIGNMENT):
			assignment = {"doctype": "LMS Assignment", "name": name, "title": name, "type": "Text"}
			frappe.get_doc(assignment).db_insert()
		frappe.get_doc(
			{
				"doctype": "LMS Assignment Submission",
				"name": SUBMISSION,
				"assignment": ASSIGNMENT,
				"member": STUDENT,
				"type": "Text",
				"answer": "<p>original</p>",
				"status": "Not Graded",
			}
		).db_insert()
		# db_insert stamps the session user as owner, and the student's rights are if_owner.
		frappe.db.set_value("LMS Assignment Submission", SUBMISSION, "owner", STUDENT, update_modified=False)

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def _grade(self, status: str) -> None:
		frappe.db.set_value("LMS Assignment Submission", SUBMISSION, "status", status, update_modified=False)

	def _save_as_student(self, **changes) -> None:
		frappe.set_user(STUDENT)
		doc = frappe.get_doc("LMS Assignment Submission", SUBMISSION)
		doc.update(changes)
		doc.save()

	def _stored(self, field: str):
		return frappe.db.get_value("LMS Assignment Submission", SUBMISSION, field)

	def test_the_student_edits_a_submission_not_yet_graded(self):
		self._save_as_student(answer="<p>edited</p>")
		self.assertEqual(self._stored("answer"), "<p>edited</p>")

	def test_the_student_cannot_change_a_graded_answer(self):
		for status in ("Pass", "Fail", "Not Applicable"):
			with self.subTest(status=status):
				self._grade(status)
				with self.assertRaises(frappe.PermissionError):
					self._save_as_student(answer="<p>replaced</p>")
				self.assertEqual(self._stored("answer"), "<p>original</p>")

	def test_a_passed_submission_cannot_move_to_another_assignment(self):
		self._grade("Pass")
		with self.assertRaises(frappe.PermissionError):
			self._save_as_student(assignment=OTHER_ASSIGNMENT)
		self.assertEqual(self._stored("assignment"), ASSIGNMENT)

	def test_who_grades_still_saves_a_graded_submission(self):
		self._grade("Pass")
		doc = frappe.get_doc("LMS Assignment Submission", SUBMISSION)
		doc.status = "Fail"
		doc.comments = "<p>Rivisto</p>"
		doc.save()
		self.assertEqual(self._stored("status"), "Fail")

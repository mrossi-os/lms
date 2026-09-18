"""Unit tests for the quiz score notification link.

The regression these cover: upstream creates the "you scored X" alert with an
empty ``link``, and the notification panel silently ignores a link-less alert, so
the learner's click did nothing at all.
"""

from __future__ import annotations

from unittest.mock import patch

import frappe
from frappe.tests import UnitTestCase

from os_lms.os_lms import notification_links


class TestQuizSubmissionLink(UnitTestCase):
	def test_quiz_in_a_lesson_points_at_the_lesson(self):
		with (
			patch.object(frappe.db, "get_value", side_effect=["QUIZ-1", ("LESSON-1", "corso-x")]),
			patch.object(notification_links, "get_lesson_index", return_value="2-3"),
		):
			link = notification_links.build_quiz_submission_link("SUB-1")

		self.assertEqual(link, "/lms/courses/corso-x/learn/2-3")

	def test_standalone_quiz_falls_back_to_the_quiz_page(self):
		"""4 of the 7 quizzes in production belong to no lesson."""
		with patch.object(frappe.db, "get_value", side_effect=["QUIZ-1", (None, None)]):
			link = notification_links.build_quiz_submission_link("SUB-1")

		self.assertEqual(link, "/lms/quiz/QUIZ-1")

	def test_unknown_submission_yields_no_link(self):
		with patch.object(frappe.db, "get_value", return_value=None):
			self.assertEqual(notification_links.build_quiz_submission_link("SUB-404"), "")


class TestSetMissingLinkHook(UnitTestCase):
	def _doc(self, **kwargs):
		return frappe._dict(
			{"link": "", "document_type": "LMS Quiz Submission", "document_name": "SUB-1", **kwargs}
		)

	def test_fills_an_empty_quiz_link(self):
		doc = self._doc()
		with patch.object(notification_links, "build_quiz_submission_link", return_value="/lms/quiz/Q"):
			notification_links.set_missing_link(doc)

		self.assertEqual(doc.link, "/lms/quiz/Q")

	def test_leaves_an_existing_link_alone(self):
		doc = self._doc(link="/lms/batches/B1")
		with patch.object(notification_links, "build_quiz_submission_link") as build:
			notification_links.set_missing_link(doc)

		build.assert_not_called()
		self.assertEqual(doc.link, "/lms/batches/B1")

	def test_ignores_other_doctypes(self):
		"""Assignment alerts already carry their own link — never touch them."""
		doc = self._doc(document_type="LMS Assignment Submission")
		with patch.object(notification_links, "build_quiz_submission_link") as build:
			notification_links.set_missing_link(doc)

		build.assert_not_called()

	def test_a_broken_lookup_never_blocks_the_notification(self):
		doc = self._doc()
		with (
			patch.object(notification_links, "build_quiz_submission_link", side_effect=Exception("boom")),
			patch.object(frappe, "log_error"),
		):
			notification_links.set_missing_link(doc)

		self.assertEqual(doc.link, "")

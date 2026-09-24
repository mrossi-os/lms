"""can_access_quiz lets the per-batch Valutatore read the quizzes of their courses.

The Valutatore is never enrolled in the course. Upstream's rewrite of the
sequential gate put `if not get_membership(...): continue` ahead of our branch,
which made it unreachable: the quiz inside a lesson failed with "not authorized".
"""

from __future__ import annotations

from unittest.mock import patch

import frappe
from frappe.tests import UnitTestCase

from lms.lms import permissions

QUIZ = frappe._dict(course="course-1", lesson="lesson-1", owner="author@example.com")


class TestValutatoreQuizAccess(UnitTestCase):
	def _can_access(self, is_valutatore: bool) -> bool:
		with (
			patch.object(permissions.frappe.db, "get_value", return_value=QUIZ),
			patch.object(permissions.frappe, "get_all", return_value=[]),
			patch.object(permissions, "has_moderator_role", return_value=False),
			patch.object(permissions, "can_modify_course", return_value=False),
			patch.object(permissions, "get_membership", return_value=None),
			patch.object(permissions, "is_course_valutatore", return_value=is_valutatore),
		):
			return permissions.can_access_quiz("quiz-1", user="valutatore@example.com")

	def test_unenrolled_valutatore_reads_the_quiz(self):
		self.assertTrue(self._can_access(is_valutatore=True))

	def test_unenrolled_non_valutatore_does_not(self):
		self.assertFalse(self._can_access(is_valutatore=False))

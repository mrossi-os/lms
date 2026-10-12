"""can_access_quiz lets the per-batch Valutatore read the quizzes of their courses.

The Valutatore is never enrolled in the course. Upstream's rewrite of the
sequential gate put `if not get_membership(...): continue` ahead of our branch,
which made it unreachable: the quiz inside a lesson failed with "not authorized".
Since lms v2.65.0 can_access_quiz delegates to the assessment predicate, where the
rule lives in _valutatore_reaches; the mocks below follow that path.
"""

from __future__ import annotations

from unittest.mock import patch

from frappe.tests import UnitTestCase

from lms.lms import permissions

class TestValutatoreQuizAccess(UnitTestCase):
	def _can_access(self, is_valutatore: bool) -> bool:
		# A quiz placed in lesson-1 of course-1; the user is neither its author, nor an
		# instructor, nor enrolled. Only being a Valutatore of a batch holding course-1
		# may open it.
		roles = ["Valutatore"] if is_valutatore else ["LMS Student"]
		with (
			patch.object(permissions.frappe.db, "exists", return_value=True),
			patch.object(permissions.frappe, "get_roles", return_value=roles),
			patch.object(permissions, "has_moderator_role", return_value=False),
			patch.object(permissions, "is_content_author", return_value=False),
			patch.object(permissions, "_course_placements", return_value={"course-1": {"lesson-1"}}),
			patch.object(permissions, "_author_only_courses", return_value=set()),
			patch.object(permissions, "_running_batches", return_value=[]),
			patch.object(permissions, "_enrolled_in", return_value=set()),
			patch.object(permissions, "is_course_valutatore", return_value=is_valutatore),
		):
			return permissions.can_access_quiz("quiz-1", user="valutatore@example.com")

	def test_unenrolled_valutatore_reads_the_quiz(self):
		self.assertTrue(self._can_access(is_valutatore=True))

	def test_unenrolled_non_valutatore_does_not(self):
		self.assertFalse(self._can_access(is_valutatore=False))

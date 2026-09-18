"""Fill in the notification links that upstream leaves empty.

Upstream's ``LMSQuizSubmission.notify_member`` builds the "you scored X for quiz
Y" alert with an empty ``link`` field, so clicking that notification in the panel
does nothing at all — ``navigateToPage`` bails out on the missing link before it
can even warn the learner.

We fill in only the missing field, from a ``before_insert`` hook, instead of
overriding the doctype class: overriding ``notify_member`` would copy upstream's
subject and email body into this app and freeze them here, and upstream has
already reworded them once (commit 45e98b9dd). The push fan-out reads
``doc.link`` in ``after_insert``, so it picks the destination up for free.
"""

from __future__ import annotations

import frappe

from lms.lms.utils import get_lesson_index, get_lesson_url, get_lms_route


def build_quiz_submission_link(submission: str) -> str:
	"""Where a learner should land from a quiz score notification.

	A quiz that belongs to a lesson sends the learner to that lesson: it is where
	they already read their own result, and it is the view that honours the
	quiz's own ``show_answers`` and ``show_submission_history`` settings. A
	standalone quiz has no lesson to go back to, so it falls back to the quiz
	page, which renders the very same component.

	The submission page (``/quiz-submission/<name>``) is deliberately not used:
	it lists the correct answers regardless of ``show_answers``, and it is gated
	to graders.
	"""
	quiz = frappe.db.get_value("LMS Quiz Submission", submission, "quiz")
	if not quiz:
		return ""

	lesson, course = frappe.db.get_value("LMS Quiz", quiz, ["lesson", "course"]) or (None, None)
	if lesson and course:
		return get_lesson_url(course, get_lesson_index(lesson))

	return get_lms_route(f"quiz/{quiz}")


def set_missing_link(doc, method=None):
	"""``before_insert`` hook on Notification Log."""
	if doc.link or doc.document_type != "LMS Quiz Submission" or not doc.document_name:
		return

	try:
		doc.link = build_quiz_submission_link(doc.document_name)
	except Exception:  # noqa: BLE001
		# A missing destination must never keep the notification itself from
		# being delivered — a link-less alert is still better than no alert.
		frappe.log_error(frappe.get_traceback(), "Quiz notification link")

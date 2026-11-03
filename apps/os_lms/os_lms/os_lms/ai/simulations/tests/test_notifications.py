"""Notifications of the teacher review (docs/ai-simulator/PIANO-esito-e-punteggio-coach.md,
phase 8): the reviewers hear once that a session waits for its outcome, get a
reminder every 7 days until it is published, and the student hears about the
first publication.

Administrator plays both the student and the reviewer: access.reviewers_of is
covered in test_access and patched here. TestInstructorReview stops the emails
and deletes the Notification Logs of the sessions it creates; a reminder that
lists several sessions belongs to none, so the tests also delete the reviewer's
bells that were not there before them."""
from __future__ import annotations

from unittest.mock import patch

import frappe
from frappe.utils import add_days, now_datetime

from os_lms.os_lms.ai.simulations import notifications
from os_lms.os_lms.ai.simulations.api import instructor_save_review, instructor_start_review
from os_lms.os_lms.ai.simulations.tasks import generate_debrief

from .test_instructor_api import TestInstructorReview

REVIEWER = "Administrator"


class TestReviewNotifications(TestInstructorReview):
	def setUp(self):
		super().setUp()
		self.reviewer_email = frappe.db.get_value("User", REVIEWER, "email")
		self.bells_before = set(frappe.get_all("Notification Log", {"for_user": REVIEWER}, pluck="name"))
		patches = [
			patch.object(
				notifications.access, "reviewers_of", side_effect=lambda course, student: {REVIEWER}
			),
			# The subjects are checked in English whatever the site language
			patch.object(notifications, "get_user_lang", return_value="en"),
		]
		for p in patches:
			p.start()
			self.addCleanup(p.stop)

	def tearDown(self):
		for name in frappe.get_all("Notification Log", {"for_user": REVIEWER}, pluck="name"):
			if name not in self.bells_before:
				frappe.db.delete("Notification Log", {"name": name})
		super().tearDown()

	def _bells(self, session: str) -> list[dict]:
		return frappe.get_all(
			"Notification Log",
			filters={"document_name": session, "for_user": REVIEWER},
			fields=["subject", "link", "type"],
		)

	def _emails(self, template_key: str) -> list:
		return [c for c in self.email.call_args_list if c.kwargs["template_key"] == template_key]

	def _waiting_since(self, session: str, days: int, *, reminded: bool = False):
		field = "outcome_reminded_at" if reminded else "outcome_requested_at"
		frappe.db.set_value(
			"LMSA Simulation Debrief",
			{"session": session},
			field,
			add_days(now_datetime(), -days),
			update_modified=False,
		)

	def test_reviewers_hear_once_that_a_session_waits_for_its_outcome(self):
		self._set_outcome_flag(1)
		session = self._debrief_session()

		bells = self._bells(session)
		self.assertEqual(len(bells), 1)
		self.assertEqual(bells[0].type, "Alert")
		self.assertIn("waits for your outcome", bells[0].subject)
		self.assertIn(f"session={session}", bells[0].link)
		self.assertIsNotNone(self._debrief(session).outcome_requested_at)
		# The bell alone: email waits for the reminder
		self.assertEqual(self.email.call_count, 0)

		# A regenerated debrief does not ask again
		generate_debrief(session)
		self.assertEqual(len(self._bells(session)), 1)

	def test_a_simulation_without_outcome_asks_nobody(self):
		session = self._debrief_session()
		self.assertEqual(self._bells(session), [])
		self.assertIsNone(self._debrief(session).outcome_requested_at)
		notifications.send_outcome_reminders()
		self.assertEqual(self.email.call_count, 0)

	def test_the_student_hears_about_the_first_publication_only(self):
		session = self._debrief_session()
		instructor_start_review(session_id=session)
		instructor_save_review(session_id=session, review=self._edits())
		self.assertEqual(self._bells(session), [])

		instructor_save_review(session_id=session, review=self._edits(), publish=True)
		bells = self._bells(session)
		self.assertEqual(len(bells), 1)
		self.assertIn("published the evaluation", bells[0].subject)
		self.assertTrue(bells[0].link.endswith(f"simulations/{session}/debrief"))
		emails = self._emails("simulation_review_published")
		self.assertEqual(len(emails), 1)
		self.assertEqual(emails[0].kwargs["recipients"], self.reviewer_email)
		self.assertEqual(emails[0].kwargs["args"]["outcome"], "")

		# Later saves of the published version stay quiet
		instructor_save_review(session_id=session, review=self._edits(comment="Rivisto"))
		self.assertEqual(len(self._bells(session)), 1)
		self.assertEqual(len(self._emails("simulation_review_published")), 1)

	def test_the_published_outcome_reaches_the_student(self):
		self._set_outcome_flag(1)
		session = self._debrief_session()
		instructor_start_review(session_id=session)
		instructor_save_review(
			session_id=session,
			review=self._edits(outcome="Not Passed", outcome_reason="Nessuna chiusura"),
			publish=True,
		)
		# The request bell, then the evaluation one
		subjects = [b.subject for b in self._bells(session)]
		self.assertEqual(len(subjects), 2)
		self.assertTrue(any("has been evaluated: not passed" in s for s in subjects))
		args = self._emails("simulation_review_published")[0].kwargs["args"]
		self.assertEqual(args["outcome"], "Not Passed")
		self.assertEqual(args["outcome_reason"], "Nessuna chiusura")

	def test_reminders_every_seven_days_until_the_outcome_is_published(self):
		self._set_outcome_flag(1)
		first, second = self._debrief_session(), self._debrief_session()

		# Six days: too early
		self._waiting_since(first, 6)
		self._waiting_since(second, 6)
		notifications.send_outcome_reminders()
		self.assertEqual(self._emails("simulation_outcome_reminder"), [])

		# Seven days: one reminder listing both sessions
		self._waiting_since(first, 8)
		self._waiting_since(second, 7)
		notifications.send_outcome_reminders()
		emails = self._emails("simulation_outcome_reminder")
		self.assertEqual(len(emails), 1)
		self.assertEqual(emails[0].kwargs["recipients"], self.reviewer_email)
		listed = emails[0].kwargs["args"]["sessions"]
		self.assertEqual(len(listed), 2)
		self.assertEqual(listed[0]["waiting_days"], 8)
		self.assertIn(f"session={first}", listed[0]["url"])
		self.assertIsNotNone(self._debrief(first).outcome_reminded_at)

		# The next day nothing goes out again
		notifications.send_outcome_reminders()
		self.assertEqual(len(self._emails("simulation_outcome_reminder")), 1)

		# Seven days after the reminder only the session still waiting is listed
		instructor_start_review(session_id=second)
		instructor_save_review(
			session_id=second, review=self._edits(outcome="Passed"), publish=True
		)
		self._waiting_since(first, 7, reminded=True)
		self._waiting_since(second, 7, reminded=True)
		notifications.send_outcome_reminders()
		emails = self._emails("simulation_outcome_reminder")
		self.assertEqual(len(emails), 2)
		listed = emails[1].kwargs["args"]["sessions"]
		self.assertEqual([s["url"].endswith(f"session={first}") for s in listed], [True])

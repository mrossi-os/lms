"""One TrueSkills badge per learner, course and template.

Since lms v2.65.0 a learner may hold several LMS Certificates for one course (one per
batch, plus the course-level one). ``issue_certificate`` points a later certificate at
the badge already issued with the same template instead of issuing it again; a
different template (a renewed certification) is issued anew.

Rows are written with ``db_insert`` (no hooks, so no automatic emission) and the
emission's own commits are disabled, so everything rolls back in ``tearDown``.
"""

from __future__ import annotations

from unittest.mock import patch

import frappe
from frappe.tests import UnitTestCase

from os_lms.os_lms.trueskills import emission
from os_lms.os_lms.trueskills.service import TrueSkillsService

P = "ts-reuse-test-"
COURSE = f"{P}course"
LEARNER, OTHER = f"{P}learner@example.com", f"{P}other@example.com"


class TestTrueSkillsBadgeReuse(UnitTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.commit = patch.object(frappe.db, "commit")
		self.commit.start()
		self.issued_ids = iter(range(9001, 9100))
		self.api = patch.object(TrueSkillsService, "issue_certificate", side_effect=self._issue)
		self.issue_call = self.api.start()
		for email, fiscal_code in ((LEARNER, "RSSMRA80A01H501U"), (OTHER, "VRDLGI80A01H501X")):
			frappe.get_doc(
				{
					"doctype": "User",
					"name": email,
					"email": email,
					"first_name": "Test",
					"last_name": email.split("@")[0],
					"codice_fiscale": fiscal_code,
					"enabled": 1,
				}
			).db_insert()
		frappe.get_doc(
			{
				"doctype": "LMS Course",
				"name": COURSE,
				"title": "TrueSkills reuse test",
				"trueskills_certificate_enabled": 1,
				"trueskills_template_id": "101",
			}
		).db_insert()

	def tearDown(self):
		self.api.stop()
		self.commit.stop()
		frappe.db.rollback()

	def _issue(self, **kwargs):
		n = next(self.issued_ids)
		return {"id": n, "uid": f"uid-{n}"}

	def _certificate(self, n: int, member: str = LEARNER, batch: str | None = None) -> str:
		name = f"{P}cert-{n}"
		frappe.get_doc(
			{
				"doctype": "LMS Certificate",
				"name": name,
				"member": member,
				"course": COURSE,
				"batch_name": batch,
				"issue_date": "2026-10-12",
				"template": None,
			}
		).db_insert()
		return name

	def _log(self, certificate: str) -> dict:
		return frappe.db.get_value(
			"TrueSkills Issue Log",
			{"lms_certificate": certificate},
			["name", "state", "trueskill_id", "trueskill_uid", "template_id"],
			as_dict=True,
		)

	def test_a_second_certificate_with_the_same_template_reuses_the_badge(self):
		first = self._certificate(1)
		emission.issue_certificate(first)
		second = self._certificate(2, batch=None)
		emission.issue_certificate(second)

		self.assertEqual(self.issue_call.call_count, 1)
		first_log, second_log = self._log(first), self._log(second)
		self.assertEqual(second_log.state, "issued")
		self.assertEqual(second_log.trueskill_id, first_log.trueskill_id)
		self.assertEqual(second_log.trueskill_uid, first_log.trueskill_uid)
		self.assertTrue(
			frappe.db.exists(
				"Comment",
				{"reference_doctype": "TrueSkills Issue Log", "reference_name": second_log.name},
			)
		)

	def test_a_changed_template_issues_a_new_badge(self):
		first = self._certificate(1)
		emission.issue_certificate(first)
		frappe.db.set_value("LMS Course", COURSE, "trueskills_template_id", "202")
		second = self._certificate(2)
		emission.issue_certificate(second)

		self.assertEqual(self.issue_call.call_count, 2)
		self.assertNotEqual(self._log(second).trueskill_id, self._log(first).trueskill_id)
		self.assertEqual(self._log(second).template_id, 202)

	def test_another_learner_gets_their_own_badge(self):
		emission.issue_certificate(self._certificate(1))
		emission.issue_certificate(self._certificate(2, member=OTHER))

		self.assertEqual(self.issue_call.call_count, 2)

	def test_a_failed_previous_attempt_is_not_reused(self):
		first = self._certificate(1)
		self.issue_call.side_effect = emission.TrueSkillsClientError("boom", 400, "invalid_template")
		emission.issue_certificate(first)
		self.assertEqual(self._log(first).state, "failed")

		self.issue_call.side_effect = self._issue
		second = self._certificate(2)
		emission.issue_certificate(second)

		self.assertEqual(self.issue_call.call_count, 2)
		self.assertEqual(self._log(second).state, "issued")

"""Unit tests for the os_lms override of get_quiz_violation_logs.

Upstream v2.63.0 hands a quiz attempt's proctoring log, webcam stills included,
to anyone who can read the submission. The per-batch Valutatore can read their
students' submissions, but must not see the photo log (client decision,
2026-09-24).
"""

from __future__ import annotations

from unittest.mock import patch

import frappe
from frappe.tests import UnitTestCase

from os_lms.os_lms import valutatore

UPSTREAM = "lms.lms.doctype.lms_quiz.lms_quiz.get_quiz_violation_logs"


class TestViolationLogAccess(UnitTestCase):
	def _call(self, only_valutatore: bool):
		with (
			patch.object(valutatore, "_only_scoped_valutatore", return_value=only_valutatore),
			patch(UPSTREAM, return_value=[{"name": "log-1"}]) as upstream,
		):
			try:
				return valutatore.get_quiz_violation_logs("sub-1"), upstream
			except frappe.PermissionError:
				return None, upstream

	def test_scoped_valutatore_is_refused(self):
		result, upstream = self._call(only_valutatore=True)

		self.assertIsNone(result)
		upstream.assert_not_called()

	def test_other_readers_get_the_upstream_log(self):
		result, upstream = self._call(only_valutatore=False)

		self.assertEqual(result, [{"name": "log-1"}])
		upstream.assert_called_once_with("sub-1")

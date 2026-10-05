"""Unit tests for the os_lms override of get_quiz_violation_logs.

Upstream v2.63.0 hands a quiz attempt's proctoring log, webcam stills included, to
anyone who can read the submission. The per-batch Valutatore reads it only for a
submission of their own batches (client decision, 2026-10-05, reversing the
2026-09-24 one that kept it from them); everybody else keeps the upstream rule.
"""

from __future__ import annotations

from unittest.mock import patch

import frappe
from frappe.tests import UnitTestCase

from os_lms.os_lms import valutatore

UPSTREAM = "lms.lms.doctype.lms_quiz.lms_quiz.get_quiz_violation_logs"


class TestViolationLogAccess(UnitTestCase):
	def _call(self, only_valutatore: bool, in_scope: bool = True, batches=("batch-1",)):
		with (
			patch.object(valutatore, "_only_scoped_valutatore", return_value=only_valutatore),
			patch.object(valutatore, "get_valutatore_batches", return_value=list(batches)),
			patch.object(valutatore, "_quiz_submission_in_scope", return_value=in_scope),
			patch(UPSTREAM, return_value=[{"name": "log-1"}]) as upstream,
		):
			try:
				return valutatore.get_quiz_violation_logs("sub-1"), upstream
			except frappe.PermissionError:
				return None, upstream

	def test_scoped_valutatore_reads_the_log_of_their_batch(self):
		result, upstream = self._call(only_valutatore=True, in_scope=True)

		self.assertEqual(result, [{"name": "log-1"}])
		upstream.assert_called_once_with("sub-1")

	def test_scoped_valutatore_is_refused_outside_their_batches(self):
		result, upstream = self._call(only_valutatore=True, in_scope=False)

		self.assertIsNone(result)
		upstream.assert_not_called()

	def test_valutatore_without_batches_is_refused(self):
		result, upstream = self._call(only_valutatore=True, batches=())

		self.assertIsNone(result)
		upstream.assert_not_called()

	def test_other_readers_get_the_upstream_log(self):
		result, upstream = self._call(only_valutatore=False)

		self.assertEqual(result, [{"name": "log-1"}])
		upstream.assert_called_once_with("sub-1")

"""A badge download TrueSkills refuses reaches the SPA as a stable error code.

The SPA maps the code to a message the learner can understand, so the endpoint
must raise ``TrueSkillsDownloadError`` with the code alone as its message.
"""

from __future__ import annotations

from unittest.mock import patch

import frappe
from frappe.tests import UnitTestCase

from os_lms.os_lms.trueskills import api
from os_lms.os_lms.trueskills.client import (
	TrueSkillsClientError,
	TrueSkillsError,
	TrueSkillsNetworkError,
	TrueSkillsServerError,
)
from os_lms.os_lms.trueskills.service import TrueSkillsService


class TestTrueSkillsDownloadErrors(UnitTestCase):
	def tearDown(self):
		frappe.set_user("Administrator")

	def test_code_from_the_response_body_wins(self):
		exc = TrueSkillsClientError("summary", 404, "certificate_not_found")
		self.assertEqual(api.trueskills_error_code(exc), "certificate_not_found")

	def test_codes_for_failures_without_a_body_code(self):
		cases = [
			(TrueSkillsClientError("TrueSkills GET /download/1/image → 401", 401), "unauthorized"),
			(TrueSkillsNetworkError("TrueSkills request failed: timeout"), "service_unavailable"),
			(TrueSkillsServerError("TrueSkills GET /download/1/image → 502", 502), "internal_error"),
			(TrueSkillsError("Unsupported download format: 'pdf'"), "download_failed"),
		]
		for exc, expected in cases:
			with self.subTest(expected=expected):
				self.assertEqual(api.trueskills_error_code(exc), expected)

	def test_download_raises_the_code_as_a_download_error(self):
		refused = TrueSkillsClientError("summary", 400, "unable_to_generate_file")
		frappe.set_user("Administrator")
		with patch.object(TrueSkillsService, "download", side_effect=refused):
			with self.assertRaises(api.TrueSkillsDownloadError) as caught:
				api.download(certificate_id=155, file_format="image")

		self.assertEqual(str(caught.exception), "unable_to_generate_file")
		self.assertTrue(issubclass(api.TrueSkillsDownloadError, frappe.ValidationError))

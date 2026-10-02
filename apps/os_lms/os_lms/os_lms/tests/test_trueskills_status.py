"""TrueSkills settings status shown in the SPA "TrueSkills API" tab."""

from __future__ import annotations

import json
from unittest.mock import patch

import frappe
from frappe.tests import UnitTestCase

from os_lms.os_lms.trueskills import api
from os_lms.os_lms.trueskills.settings import TrueSkillsSettings

API_KEY = "ts_ab12cdSECRETPART0123456789"


class TestTrueSkillsStatus(UnitTestCase):
	def tearDown(self):
		frappe.set_user("Administrator")

	def status_with(self, api_key):
		settings = TrueSkillsSettings(
			enabled=True, api_key=api_key, endpoint="https://trueskills.example.test"
		)
		with patch.object(TrueSkillsSettings, "load", return_value=settings):
			frappe.set_user("Administrator")
			return api.get_status()

	def test_shows_only_the_start_of_the_key(self):
		status = self.status_with(API_KEY)

		self.assertEqual(status["api_key_prefix"], "ts_ab12c")
		self.assertTrue(status["has_api_key"])
		self.assertNotIn("SECRETPART", json.dumps(status))

	def test_no_key_saved(self):
		status = self.status_with(None)

		self.assertIsNone(status["api_key_prefix"])
		self.assertFalse(status["has_api_key"])

	def test_requires_an_admin(self):
		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			api.get_status()

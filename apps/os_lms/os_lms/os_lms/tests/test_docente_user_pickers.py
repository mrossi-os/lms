"""A Docente can search the users offered by the Instructors and Valutatori pickers.

Collaudo v2.64 (test 1.3): a Docente-only user could not assign instructors or
valutatori on a batch or course, because the three search endpoints behind the pickers
answered 403 to anyone without Moderator / Course Creator / Batch Evaluator.
"""

from __future__ import annotations

from unittest.mock import patch

import frappe
from frappe.tests import UnitTestCase

from os_lms.os_lms import api, override_api

ORIGINAL = "os_lms.os_lms.override_api._original_search_users_by_role"


class TestDocenteUserPickers(UnitTestCase):
	def test_docente_search_runs_as_administrator_and_restores_the_session(self):
		seen = []

		def upstream(txt, roles, page_length, names):
			seen.append(frappe.session.user)
			return ["rows"]

		session_user = frappe.session.user
		with patch.object(frappe, "get_roles", return_value=["Docente"]), patch(ORIGINAL, upstream):
			rows = override_api.search_users_by_role("ab", '["Batch Evaluator"]', 5, None)

		self.assertEqual(rows, ["rows"])
		self.assertEqual(seen, ["Administrator"])
		self.assertEqual(frappe.session.user, session_user)

	def test_session_is_restored_when_the_search_fails(self):
		session_user = frappe.session.user
		with (
			patch.object(frappe, "get_roles", return_value=["Docente"]),
			patch(ORIGINAL, side_effect=frappe.ValidationError),
		):
			with self.assertRaises(frappe.ValidationError):
				override_api.search_users_by_role("", '["Batch Evaluator"]')

		self.assertEqual(frappe.session.user, session_user)

	def test_everyone_else_keeps_the_upstream_gate(self):
		seen = []

		def upstream(txt, roles, page_length, names):
			seen.append(frappe.session.user)
			return []

		session_user = frappe.session.user
		with patch.object(frappe, "get_roles", return_value=["Valutatore"]), patch(ORIGINAL, upstream):
			override_api.search_users_by_role("", '["Batch Evaluator"]')

		self.assertEqual(seen, [session_user])

	def test_valutatori_picker_search_admits_a_docente(self):
		with patch.object(frappe, "get_roles", return_value=["Docente"]):
			self.assertIsInstance(api.search_non_student_users("zz-no-such-user"), list)

	def test_valutatori_picker_search_still_refuses_a_plain_student(self):
		# only_for waves Administrator through, so run as someone else.
		self.addCleanup(frappe.set_user, frappe.session.user)
		frappe.set_user("Guest")
		with patch.object(frappe, "get_roles", return_value=["LMS Student"]):
			with self.assertRaises(frappe.PermissionError):
				api.search_non_student_users("zz-no-such-user")

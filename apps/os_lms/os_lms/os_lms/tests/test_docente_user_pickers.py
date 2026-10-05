"""A Docente can search the users offered by the Instructors and Valutatori pickers.

Collaudo v2.64 (test 1.3): a Docente-only user could not assign instructors or
valutatori on a batch or course, because the three search endpoints behind the pickers
answered 403 to anyone without Moderator / Course Creator / Batch Evaluator.

The first fix wrapped the upstream search and ran it with frappe.set_user("Administrator");
set_user overwrites the session id and data, so the caller was logged out after the first
search (every later request was a Guest one). The search is now a copy of upstream with a
wider gate, and these tests pin that the session is left alone.
"""

from __future__ import annotations

from unittest.mock import patch

import frappe
from frappe.tests import UnitTestCase

from lms.lms.api import search_users_by_role as upstream_search
from os_lms.os_lms import api, override_api

ROLES = '["Course Creator", "Batch Evaluator"]'


class TestDocenteUserPickers(UnitTestCase):
	def setUp(self):
		super().setUp()
		# only_for waves Administrator through, so run as someone else.
		self.addCleanup(frappe.set_user, frappe.session.user)
		frappe.set_user("Guest")

	def test_docente_may_search_instructors(self):
		with patch.object(frappe, "get_roles", return_value=["Docente"]):
			self.assertIsInstance(override_api.search_users_by_role("zz-no-such-user", ROLES), list)

	def test_other_roles_keep_the_upstream_gate(self):
		for role in ("LMS Student", "Valutatore"):
			with self.subTest(role=role), patch.object(frappe, "get_roles", return_value=[role]):
				with self.assertRaises(frappe.PermissionError):
					override_api.search_users_by_role("", ROLES)

	def test_search_never_touches_the_session(self):
		session = frappe.local.session
		before = (session.user, session.sid, session.data)
		with (
			patch.object(frappe, "get_roles", return_value=["Docente"]),
			patch.object(frappe, "set_user") as set_user,
		):
			override_api.search_users_by_role("", ROLES)

		set_user.assert_not_called()
		self.assertEqual((session.user, session.sid, session.data), before)

	def test_same_answer_as_upstream(self):
		frappe.set_user("Administrator")
		for kwargs in ({"txt": "", "roles": ROLES, "page_length": 50}, {"txt": "a", "roles": ROLES}, {"roles": None}):
			with self.subTest(kwargs=kwargs):
				self.assertEqual(override_api.search_users_by_role(**kwargs), upstream_search(**kwargs))

	def test_valutatori_picker_search_admits_a_docente(self):
		with patch.object(frappe, "get_roles", return_value=["Docente"]):
			self.assertIsInstance(api.search_non_student_users("zz-no-such-user"), list)

	def test_valutatori_picker_search_still_refuses_a_plain_student(self):
		with patch.object(frappe, "get_roles", return_value=["LMS Student"]):
			with self.assertRaises(frappe.PermissionError):
				api.search_non_student_users("zz-no-such-user")

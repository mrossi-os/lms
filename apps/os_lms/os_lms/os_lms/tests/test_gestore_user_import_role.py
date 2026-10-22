"""Users imported by a Gestore get the "LMS Student" role.

Academy Salescience, 2026-10-22: 22 students imported from the User Data Import by a
Gestore had no role at all, so the final quiz of their course never loaded
(get_quiz_with_questions refuses users without an LMS role). The roles table of User is
at permlevel 1, which only System Manager may write; Frappe's validate_higher_perm_levels
wiped it, the "LMS Student" added by lms' before_insert hook included. The same file
imported by Administrator kept the role.
"""

from __future__ import annotations

from unittest.mock import patch

import frappe
from frappe.model.document import Document
from frappe.tests import UnitTestCase

from os_lms.events.user import grant_student_role_on_gestore_import

GESTORE = "gestore-user-import-test@example.com"
IMPORTED = "imported-student-test@example.com"
# The real Gestore bundle: Gestore is never assigned alone.
GESTORE_BUNDLE = ("Gestore", "Moderator", "Docente", "Course Creator", "Batch Evaluator")


def stored_roles(user: str) -> set[str]:
	return set(frappe.get_all("Has Role", {"parent": user, "parenttype": "User"}, pluck="role"))


class TestGestoreUserImportRole(UnitTestCase):
	def setUp(self):
		super().setUp()
		self.addCleanup(frappe.set_user, frappe.session.user)
		self.addCleanup(setattr, frappe.flags, "in_import", frappe.flags.in_import)
		frappe.set_user("Administrator")

		if not frappe.db.exists("User", GESTORE):
			frappe.get_doc(
				{
					"doctype": "User",
					"email": GESTORE,
					"first_name": "Gestore",
					"send_welcome_email": 0,
					"roles": [{"role": role} for role in GESTORE_BUNDLE],
				}
			).insert(ignore_permissions=True)

	def tearDown(self):
		frappe.db.rollback()

	def import_user_as_gestore(self, *, in_import: bool) -> str:
		"""Insert a user the way Data Import does: with the importer's permissions."""
		frappe.set_user(GESTORE)
		frappe.flags.in_import = in_import
		user = frappe.get_doc(
			{
				"doctype": "User",
				"email": IMPORTED,
				"first_name": "Imported",
				"send_welcome_email": 0,
				"roles": [{"role": "LMS Student"}],
			}
		)
		# The Gestore's create permission on User is site configuration (Custom DocPerm),
		# not shipped with the app; the permlevel-1 strip under test does not depend on it.
		with patch.object(Document, "check_permission"):
			user.insert()
		frappe.set_user("Administrator")
		return user.name

	def test_gestore_import_keeps_the_student_role(self):
		self.assertEqual(stored_roles(self.import_user_as_gestore(in_import=True)), {"LMS Student"})

	def test_frappe_still_strips_roles_outside_an_import(self):
		# Pins the cause: without the hook a Gestore's user has no role at all. If this
		# starts failing, Frappe stopped stripping and the hook may no longer be needed.
		self.assertEqual(stored_roles(self.import_user_as_gestore(in_import=False)), set())

	def test_only_a_gestore_triggers_the_grant(self):
		doc = frappe.new_doc("User")
		frappe.flags.in_import = True
		with patch.object(frappe, "get_roles", return_value=["Moderator", "Docente"]):
			grant_student_role_on_gestore_import(doc)
		self.assertEqual(doc.get("roles"), [])

	def test_roles_already_set_are_left_alone(self):
		doc = frappe.new_doc("User")
		doc.append("roles", {"role": "Valutatore"})
		frappe.flags.in_import = True
		with patch.object(frappe, "get_roles", return_value=list(GESTORE_BUNDLE)):
			grant_student_role_on_gestore_import(doc)
		self.assertEqual([row.role for row in doc.roles], ["Valutatore"])

	def test_existing_users_are_not_touched(self):
		doc = frappe.get_doc("User", GESTORE)
		doc.set("roles", [])
		frappe.flags.in_import = True
		with patch.object(frappe, "get_roles", return_value=list(GESTORE_BUNDLE)):
			grant_student_role_on_gestore_import(doc)
		self.assertEqual(doc.get("roles"), [])

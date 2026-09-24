"""Tests for the patch that takes write/create on LMS Quiz Submission away from the
LMS Student.

Custom DocPerm rows replace the doctype's JSON permissions, so the upstream
read-only rule never reached sites that already had them: a student could raise
their own grade by saving the submission directly. Everything runs inside the
test transaction and is rolled back.
"""

from __future__ import annotations

import frappe
from frappe.permissions import get_role_permissions
from frappe.tests import UnitTestCase

from os_lms.patches.v0_0_8 import restrict_student_quiz_submission_perms as patch_module

DOCTYPE = "LMS Quiz Submission"
ROLE = "LMS Student"
STUDENT = "quiz-perm-student@example.com"


class TestStudentQuizSubmissionPerms(UnitTestCase):
	def setUp(self):
		# Reproduce the production grant on the student row, creating it if the
		# site has no Custom DocPerm rows for the doctype yet.
		row = frappe.db.get_value("Custom DocPerm", {"parent": DOCTYPE, "role": ROLE})
		if row:
			frappe.db.set_value("Custom DocPerm", row, {"read": 1, "write": 1, "create": 1, "if_owner": 1})
		else:
			frappe.get_doc(
				{
					"doctype": "Custom DocPerm",
					"parent": DOCTYPE,
					"role": ROLE,
					"permlevel": 0,
					"if_owner": 1,
					"read": 1,
					"write": 1,
					"create": 1,
				}
			).insert(ignore_permissions=True)
		if not frappe.db.exists("User", STUDENT):
			user = frappe.get_doc(
				{"doctype": "User", "email": STUDENT, "first_name": "Quiz", "send_welcome_email": 0}
			)
			user.append("roles", {"role": ROLE})
			user.insert(ignore_permissions=True)
		frappe.clear_cache(doctype=DOCTYPE)

	def tearDown(self):
		frappe.db.rollback()
		frappe.clear_cache(doctype=DOCTYPE)

	def _owner_perms(self):
		# The rows are if_owner, so the grant only shows on the student's own
		# submission: evaluate as owner, with the per-request cache emptied.
		frappe.local.role_permissions = {}
		return get_role_permissions(frappe.get_meta(DOCTYPE), user=STUDENT, is_owner=True)

	def test_patch_revokes_write_and_create_but_keeps_read(self):
		before = self._owner_perms()
		self.assertEqual((before["if_owner"].get("write"), before.create), (1, 1))

		patch_module.execute()

		perm = frappe.db.get_value(
			"Custom DocPerm",
			{"parent": DOCTYPE, "role": ROLE},
			["read", "write", "create", "if_owner"],
			as_dict=True,
		)
		self.assertEqual((perm.read, perm.write, perm.create, perm.if_owner), (1, 0, 0, 1))
		after = self._owner_perms()
		self.assertFalse(after["if_owner"].get("write"))
		self.assertFalse(after.write)
		self.assertFalse(after.create)
		self.assertTrue(after["if_owner"].get("read"))

	def test_other_roles_rows_are_untouched(self):
		before = frappe.get_all(
			"Custom DocPerm",
			filters={"parent": DOCTYPE, "role": ["!=", ROLE]},
			fields=["name", "read", "write", "create", "delete"],
			order_by="name",
		)

		patch_module.execute()
		patch_module.execute()  # idempotent

		after = frappe.get_all(
			"Custom DocPerm",
			filters={"parent": DOCTYPE, "role": ["!=", ROLE]},
			fields=["name", "read", "write", "create", "delete"],
			order_by="name",
		)
		self.assertEqual(before, after)

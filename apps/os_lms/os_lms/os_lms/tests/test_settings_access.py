"""Which LMS Settings fields a non-administrator may save (Impostazioni gestore).

Design: docs/superpowers/specs/2026-11-18-impostazioni-gestore-design.md. LMS Settings is
writable by Moderator, and every Gestore holds Moderator, so hiding the admin-only tabs from
the manager panel is not enough: the validate hook must refuse the admin-only fields.
"""

from __future__ import annotations

import frappe
from frappe.tests import UnitTestCase

GESTORE = "settings-gestore-test@example.com"
SYSMANAGER = "settings-sysmanager-test@example.com"
DOCENTE = "settings-docente-test@example.com"
# The real Gestore bundle: Gestore is never assigned alone.
GESTORE_BUNDLE = ("Gestore", "Moderator", "Docente", "Course Creator", "Batch Evaluator")


def ensure_user(email: str, roles: tuple[str, ...]) -> None:
	if frappe.db.exists("User", email):
		return
	frappe.get_doc(
		{
			"doctype": "User",
			"email": email,
			"first_name": email.split("@")[0],
			"send_welcome_email": 0,
			"roles": [{"role": role} for role in roles],
		}
	).insert(ignore_permissions=True)


class TestLMSSettingsAccess(UnitTestCase):
	def setUp(self):
		super().setUp()
		self.addCleanup(frappe.set_user, frappe.session.user)
		frappe.set_user("Administrator")
		ensure_user(GESTORE, GESTORE_BUNDLE)
		ensure_user(SYSMANAGER, ("System Manager",))
		ensure_user(DOCENTE, ("Docente",))

	def tearDown(self):
		# Nothing here commits: every settings change and test user goes away.
		frappe.db.rollback()

	def settings(self):
		return frappe.get_single("LMS Settings")

	def test_gestore_can_change_allowed_field(self):
		frappe.set_user(GESTORE)
		doc = self.settings()
		doc.lesson_dwell_time = (doc.lesson_dwell_time or 0) + 7
		doc.save()

	def test_gestore_cannot_change_admin_field(self):
		frappe.set_user(GESTORE)
		doc = self.settings()
		doc.disable_signup = 0 if doc.disable_signup else 1
		with self.assertRaises(frappe.PermissionError):
			doc.save()

	def test_gestore_cannot_change_sidebar_check(self):
		# "courses" belongs to the Sidebar tab: administrators only from now on.
		frappe.set_user(GESTORE)
		doc = self.settings()
		doc.courses = 0 if doc.courses else 1
		with self.assertRaises(frappe.PermissionError):
			doc.save()

	def test_gestore_cannot_change_a_table_field(self):
		frappe.set_user(GESTORE)
		doc = self.settings()
		doc.append("exception_country", {"country": "Italy"})
		with self.assertRaises(frappe.PermissionError):
			doc.save()

	def test_gestore_full_doc_resave_passes(self):
		# A masked Password value is present, and Int/Check values arrive as strings,
		# the way a full-document save from an API client can send them.
		frappe.db.set_single_value("LMS Settings", "trueskills_api_key", "secret-key-for-test")
		frappe.set_user(GESTORE)
		doc = self.settings()
		doc.lesson_dwell_time = str(doc.lesson_dwell_time or 0)
		doc.enforce_quiz_completion = str(doc.enforce_quiz_completion or 0)
		doc.disable_signup = str(doc.disable_signup or 0)
		doc.save()

	def test_gestore_save_ignores_null_vs_default(self):
		frappe.db.set_single_value("LMS Settings", "disable_signup", None)
		frappe.set_user(GESTORE)
		doc = self.settings()
		doc.lesson_dwell_time = (doc.lesson_dwell_time or 0) + 3
		doc.save()

	def test_system_manager_can_change_admin_field(self):
		frappe.set_user(SYSMANAGER)
		doc = self.settings()
		doc.disable_signup = 0 if doc.disable_signup else 1
		doc.save()

	def test_error_names_the_field(self):
		frappe.set_user(GESTORE)
		doc = self.settings()
		doc.disable_signup = 0 if doc.disable_signup else 1
		with self.assertRaises(frappe.PermissionError) as raised:
			doc.save()
		self.assertIn("Disable Signup", str(raised.exception))


class TestSaveBranding(UnitTestCase):
	"""Website Settings is writable by Website Manager only; Gestore saves Branding here."""

	def setUp(self):
		super().setUp()
		self.addCleanup(frappe.set_user, frappe.session.user)
		frappe.set_user("Administrator")
		ensure_user(GESTORE, GESTORE_BUNDLE)
		ensure_user(DOCENTE, ("Docente",))

	def tearDown(self):
		frappe.db.rollback()

	def save(self, **fields):
		from os_lms.os_lms.settings_access import save_branding

		save_branding(**fields)

	def test_gestore_saves_the_branding_fields(self):
		frappe.set_user(GESTORE)
		self.save(app_name="Brand Test", banner_image="/files/brand-logo.png", favicon="/files/brand-fav.png")
		stored = frappe.get_single("Website Settings")
		self.assertEqual(stored.app_name, "Brand Test")
		self.assertEqual(stored.banner_image, "/files/brand-logo.png")
		self.assertEqual(stored.app_logo, "/files/brand-logo.png")
		self.assertEqual(stored.favicon, "/files/brand-fav.png")

	def test_gestore_can_remove_the_logo(self):
		frappe.db.set_single_value("Website Settings", {"banner_image": "/files/old.png", "app_logo": "/files/old.png"})
		frappe.set_user(GESTORE)
		self.save(app_name="Brand Test", banner_image=None, favicon=None)
		stored = frappe.get_single("Website Settings")
		self.assertFalse(stored.banner_image)
		self.assertFalse(stored.app_logo)

	def test_docente_cannot_save_branding(self):
		frappe.set_user(DOCENTE)
		with self.assertRaises(frappe.PermissionError):
			self.save(app_name="Nope", banner_image=None, favicon=None)

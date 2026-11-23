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


	def add_sidebar_page(self, title: str) -> str:
		page = frappe.get_doc({"doctype": "Web Page", "title": title, "route": frappe.scrub(title), "published": 1}).insert()
		frappe.get_doc(
			{
				"doctype": "LMS Sidebar Item",
				"parent": "LMS Settings",
				"parenttype": "LMS Settings",
				"parentfield": "sidebar_items",
				"web_page": page.name,
				"icon": "book",
			}
		).insert()
		return page.name

	def test_refetched_sidebar_title_does_not_block_gestore(self):
		# Frappe re-copies fetch_from fields (the page title) on save: that is not a Gestore change.
		page = self.add_sidebar_page("Settings fetch test page")
		frappe.db.set_value("Web Page", page, "title", "Settings fetch test renamed")
		frappe.set_user(GESTORE)
		doc = self.settings()
		doc.lesson_dwell_time = (doc.lesson_dwell_time or 0) + 7
		doc.save()

	def test_link_case_correction_does_not_block_gestore(self):
		# Link validation rewrites a value to the stored name's exact case.
		page = self.add_sidebar_page("Settings case test page")
		frappe.db.set_value("LMS Sidebar Item", {"web_page": page}, "web_page", page.upper())
		frappe.set_user(GESTORE)
		doc = self.settings()
		doc.lesson_dwell_time = (doc.lesson_dwell_time or 0) + 7
		doc.save()


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

	def test_favicon_with_markup_is_refused(self):
		# _lms.html prints the favicon unescaped inside href="...".
		frappe.set_user(GESTORE)
		with self.assertRaises(frappe.ValidationError):
			self.save(app_name="Brand Test", banner_image=None, favicon='/files/x.png"/><script>alert(1)</script>')

	def test_logo_outside_the_site_files_is_refused(self):
		frappe.set_user(GESTORE)
		for url in ("https://evil.example/logo.png", "javascript:alert(1)", "/files/../x.png", "/files/a\nb.png"):
			with self.subTest(url=url), self.assertRaises(frappe.ValidationError):
				self.save(app_name="Brand Test", banner_image=url, favicon=None)

	def test_brand_name_with_markup_is_refused(self):
		frappe.set_user(GESTORE)
		with self.assertRaises(frappe.ValidationError):
			self.save(app_name="<script>alert(1)</script>", banner_image=None, favicon=None)

	def test_uploaded_file_name_with_spaces_is_saved(self):
		# Frappe keeps spaces in file_url ("/files/Logo Azienda.png").
		frappe.set_user(GESTORE)
		self.save(app_name="Brand Test", banner_image="/files/Logo Azienda.png", favicon=None)
		self.assertEqual(frappe.db.get_single_value("Website Settings", "banner_image"), "/files/Logo Azienda.png")

	def test_brand_name_with_apostrophe_is_saved(self):
		frappe.set_user(GESTORE)
		self.save(app_name="L'Accademia", banner_image=None, favicon=None)
		self.assertEqual(frappe.db.get_single_value("Website Settings", "app_name"), "L'Accademia")

	def test_unchanged_value_outside_files_is_kept(self):
		# A favicon an administrator set from the Desk (e.g. under /assets) survives a Gestore save.
		frappe.db.set_single_value("Website Settings", "favicon", "/assets/lms/frontend/favicon.png")
		frappe.set_user(GESTORE)
		self.save(app_name="Brand Test", banner_image=None, favicon="/assets/lms/frontend/favicon.png")
		self.assertEqual(
			frappe.db.get_single_value("Website Settings", "favicon"), "/assets/lms/frontend/favicon.png"
		)


def whitelisted(method: str):
	"""The function Frappe runs for `method`, override included."""
	overrides = frappe.get_hooks("override_whitelisted_methods") or {}
	return frappe.get_attr(overrides.get(method, [method])[-1])


class TestSettingsBypassEndpoints(UnitTestCase):
	"""Upstream endpoints that write LMS Settings rows without its validate hook."""

	def setUp(self):
		super().setUp()
		self.addCleanup(frappe.set_user, frappe.session.user)
		frappe.set_user("Administrator")
		ensure_user(GESTORE, GESTORE_BUNDLE)
		ensure_user(SYSMANAGER, ("System Manager",))
		self.page = frappe.get_doc(
			{"doctype": "Web Page", "title": "Settings bypass test page", "route": "settings-bypass-test", "published": 1}
		).insert()

	def tearDown(self):
		frappe.db.rollback()

	def test_gestore_cannot_add_a_sidebar_item(self):
		frappe.set_user(GESTORE)
		with self.assertRaises(frappe.PermissionError):
			whitelisted("lms.lms.api.update_sidebar_item")(webpage=self.page.name, icon="book")

	def test_gestore_cannot_delete_a_sidebar_item(self):
		frappe.set_user(GESTORE)
		with self.assertRaises(frappe.PermissionError):
			whitelisted("lms.lms.api.delete_sidebar_item")(webpage=self.page.name)

	def test_gestore_cannot_delete_admin_only_settings_rows(self):
		frappe.set_user(GESTORE)
		for doctype in ("LMS Sidebar Item", "Payment Country"):
			with self.subTest(doctype=doctype), self.assertRaises(frappe.PermissionError):
				whitelisted("lms.lms.api.delete_documents")(doctype=doctype, documents=["anything"])

	def test_gestore_still_deletes_other_documents(self):
		category = frappe.get_doc({"doctype": "LMS Category", "category": "Settings bypass test category"}).insert()
		frappe.set_user(GESTORE)
		whitelisted("lms.lms.api.delete_documents")(doctype="LMS Category", documents=[category.name])
		self.assertFalse(frappe.db.exists("LMS Category", category.name))

	def test_administrator_still_edits_the_sidebar(self):
		whitelisted("lms.lms.api.update_sidebar_item")(webpage=self.page.name, icon="book")
		self.assertTrue(frappe.db.exists("LMS Sidebar Item", {"web_page": self.page.name}))
		whitelisted("lms.lms.api.delete_sidebar_item")(webpage=self.page.name)
		self.assertFalse(frappe.db.exists("LMS Sidebar Item", {"web_page": self.page.name}))

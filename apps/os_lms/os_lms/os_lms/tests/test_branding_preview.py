"""Brand Customize live preview: unsaved values become CSS, unsafe values never do.

docs/brand-customize/fase-2-analisi.md. The preview CSS must be the one saving
would produce, so it is built by the same _build_css.
"""

from __future__ import annotations

import json
from unittest.mock import patch

import frappe
from frappe.tests import UnitTestCase

from os_lms.os_lms import branding

VALID = (
	"",
	None,
	"#fafafa",
	"rgb(10 20 30 / 50%)",
	"oklch(0.62 0.19 259.8)",
	"color-mix(in oklch, #2563eb 40%, white)",
	"var(--surface-gray-2)",
	"rebeccapurple",
)
UNSAFE = (
	"red; } body { display: none",
	"red}",
	"red {",
	"url(https://example.com/x.png)",
	"URL (x)",
	"red /* note */",
	"@import 'x'",
	"<style>",
	"\\72 ed",
	"#" + "a" * branding.COLOR_VALUE_MAX_LENGTH,
)


def _preview(values: dict) -> dict:
	with patch.object(branding.frappe, "only_for"):
		return branding.brand_css_preview(json.dumps(values))


class TestColorValueValidation(UnitTestCase):
	def test_css_color_syntaxes_are_valid(self):
		for value in VALID:
			self.assertTrue(branding.is_valid_color_value(value), value)

	def test_values_that_break_out_are_refused(self):
		for value in UNSAFE:
			self.assertFalse(branding.is_valid_color_value(value), value)

	def test_refused_values_are_never_emitted(self):
		css = branding._build_css(
			{"expert_tokens": {"--surface-base": "red; } body { display: none"}, "login_ink": "red}"}
		)
		self.assertNotIn("--surface-base", css)
		self.assertNotIn("--login-ink", css)
		self.assertNotIn("display", css)

	def test_saving_an_unsafe_value_fails(self):
		doc = frappe.get_doc("Brand Customize")
		doc.login_ink = "red; } body { display: none"
		self.assertRaises(frappe.ValidationError, doc.validate)

	def test_saving_valid_values_passes(self):
		doc = frappe.get_doc("Brand Customize")
		doc.login_ink = "#ffffff"
		doc.validate()


class TestBrandCssPreview(UnitTestCase):
	def test_preview_css_is_the_saved_builder_output(self):
		values = {
			"expert_tokens": {"--surface-base": "#fafafa", "--ink-gray-9": "#111111"},
			"login_bg_from": "#000000",
		}
		self.assertEqual(_preview(values)["css"], branding._build_css(values))

	def test_unknown_fields_and_non_strings_are_ignored(self):
		css = _preview({"login_ink": 12, "name": "x", "--evil": "red", "owner": "#fff"})["css"]
		self.assertNotIn("--", css)

	def test_refused_fields_are_reported(self):
		result = _preview({"login_ink": "red}", "expert_tokens": {"--ink-base": "#000", "--x": "red}"}})
		self.assertEqual(result["invalid"], ["login_ink", "--x"])
		self.assertIn("--ink-base: #000;", result["css"])

	def test_the_mode_is_honoured(self):
		css = _preview({"mode": branding.MODE_BASE, "expert_tokens": {"--surface-base": "#fafafa"}})["css"]
		self.assertNotIn("--surface-base", css)

	def test_values_must_be_an_object(self):
		for bad in ("[1, 2]", "not json", '"text"'):
			with patch.object(branding.frappe, "only_for"):
				self.assertRaises(frappe.ValidationError, branding.brand_css_preview, bad)

	def test_preview_needs_system_manager(self):
		with patch.object(branding.frappe, "only_for", side_effect=frappe.PermissionError):
			self.assertRaises(frappe.PermissionError, branding.brand_css_preview, "{}")

	def test_preview_does_not_touch_the_saved_stylesheet_cache(self):
		frappe.cache().set_value(branding.CACHE_KEY, "saved")
		try:
			_preview({"expert_tokens": {"--surface-base": "#fafafa"}})
			self.assertEqual(frappe.cache().get_value(branding.CACHE_KEY), "saved")
		finally:
			frappe.cache().delete_value(branding.CACHE_KEY)


class TestPreviewTargets(UnitTestCase):
	def _targets(self, course, batch) -> dict:
		with (
			patch.object(branding.frappe, "only_for"),
			patch.object(branding, "_preview_course", return_value=course),
			patch.object(branding, "_preview_batch", return_value=batch),
		):
			return {t["key"]: t for t in branding.get_preview_targets()["pages"]}

	def test_every_page_has_a_url_when_content_exists(self):
		targets = self._targets("my-course", "my-batch")
		self.assertEqual(
			list(targets),
			[
				"home",
				"courses",
				"course",
				"lesson",
				"course_dashboard",
				"course_editor",
				"course_settings",
				"batch",
				"statistics",
				"login",
			],
		)
		self.assertTrue(targets["course"]["url"].endswith("/courses/my-course"))
		self.assertTrue(targets["lesson"]["url"].endswith("/courses/my-course/learn/1-1"))
		# The management tabs of the course page are picked by the hash.
		self.assertTrue(targets["course_dashboard"]["url"].endswith("/courses/my-course#dashboard"))
		self.assertTrue(targets["course_editor"]["url"].endswith("/courses/my-course#editor"))
		self.assertTrue(targets["course_settings"]["url"].endswith("/courses/my-course#settings"))
		self.assertTrue(targets["batch"]["url"].endswith("/batches/my-batch"))
		self.assertEqual(targets["login"]["url"], "/update-password")
		self.assertTrue(all(t["reason"] is None for t in targets.values()))

	def test_pages_without_content_say_why(self):
		targets = self._targets(None, None)
		for key in ("course", "lesson", "course_dashboard", "course_editor", "course_settings", "batch"):
			self.assertIsNone(targets[key]["url"], key)
			self.assertTrue(targets[key]["reason"], key)
		self.assertIsNotNone(targets["home"]["url"])

	def test_names_are_url_encoded(self):
		targets = self._targets("a b", "c/d")
		self.assertTrue(targets["course"]["url"].endswith("/courses/a%20b"))
		self.assertTrue(targets["batch"]["url"].endswith("/batches/c%2Fd"))

	def test_targets_need_system_manager(self):
		with patch.object(branding.frappe, "only_for", side_effect=frappe.PermissionError):
			self.assertRaises(frappe.PermissionError, branding.get_preview_targets)


class TestPreviewCourse(UnitTestCase):
	def tearDown(self):
		frappe.db.rollback()

	def test_a_course_the_user_is_enrolled_in_is_skipped(self):
		user = "Administrator"
		course = branding._preview_course(user)
		if not course:
			self.skipTest("no published course with lessons on this site")
		self.assertFalse(frappe.db.exists("LMS Enrollment", {"course": course, "member": user}))

		enrollment = frappe.get_doc(
			{"doctype": "LMS Enrollment", "course": course, "member": user, "name": "brand-preview-test"}
		)
		enrollment.db_insert()

		self.assertNotEqual(branding._preview_course(user), course)

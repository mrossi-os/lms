"""Brand Customize colors only brand the default light theme.

A user who switches to dark or to high contrast must get the stock LMS palette. frappe-ui puts its
dark tokens in [data-theme="dark"], which has the same specificity as :root, so the
brand stylesheet (loaded last) would override them if it still wrote to :root.
The login colors stay theme-independent: the login pages have no theme switch.
"""

from __future__ import annotations

from unittest.mock import patch

from frappe.tests import UnitTestCase

from os_lms.os_lms import branding


def _css(**values) -> str:
	# Only .get() is read from the doc, so a dict stands in for it.
	with patch.object(branding.frappe, "get_cached_doc", return_value=values):
		return branding._build_css()


def _block(css: str, selector: str) -> str:
	start = css.index(selector + " {")
	return css[start : css.index("}", start)]


class TestBrandingLightOnly(UnitTestCase):
	def test_theme_tokens_are_scoped_to_the_light_theme(self):
		css = _css(expert_tokens=[{"token": "--surface-base", "value": "#fafafa"}, {"token": "--ink-gray-9", "value": "#111111"}])
		light = _block(css, branding.BRANDED_THEME_SELECTOR)
		self.assertIn("--surface-base: #fafafa;", light)
		self.assertIn("--ink-gray-9: #111111;", light)
		self.assertNotIn("--surface-base", _block(css, ":root"))

	def test_selector_skips_dark_and_high_contrast(self):
		self.assertIn(':not([data-theme="dark"])', branding.BRANDED_THEME_SELECTOR)
		self.assertIn(':not([data-contrast="more"])', branding.BRANDED_THEME_SELECTOR)

	def test_login_colors_apply_in_every_theme(self):
		css = _css(login_bg_from="#000000", expert_tokens={"--surface-base": "#fafafa"})
		self.assertIn("--login-bg-from: #000000;", _block(css, ":root"))
		self.assertNotIn("--login-bg-from", _block(css, branding.BRANDED_THEME_SELECTOR))

	def test_unbranded_instance_emits_no_values(self):
		css = _css()
		self.assertNotIn("--", css)


class TestBrandingModes(UnitTestCase):
	def test_values_mapping_skips_the_saved_doc(self):
		with patch.object(branding.frappe, "get_cached_doc", side_effect=AssertionError):
			css = branding._build_css({"expert_tokens": {"--surface-base": "#fafafa"}})
		self.assertIn("--surface-base: #fafafa;", css)

	def test_expert_is_the_default_mode(self):
		self.assertEqual(
			branding._build_css({"expert_tokens": {"--surface-base": "#fafafa"}}),
			branding._build_css({"expert_tokens": {"--surface-base": "#fafafa"}, "mode": branding.MODE_EXPERT}),
		)

	def test_expert_variables_are_ignored_in_the_other_modes(self):
		for mode in (branding.MODE_BASE, branding.MODE_ADVANCED):
			css = branding._build_css({"mode": mode, "expert_tokens": {"--surface-base": "#fafafa"}})
			self.assertNotIn("--surface-base", css, mode)

	def test_login_colors_apply_in_every_mode(self):
		for mode in (branding.MODE_BASE, branding.MODE_ADVANCED, branding.MODE_EXPERT):
			css = branding._build_css({"mode": mode, "login_ink": "#ffffff"})
			self.assertIn("--login-ink: #ffffff;", _block(css, ":root"), mode)

	def test_removed_fields_are_not_emitted(self):
		css = branding._build_css(
			{
				"company_secondary": "#123456",
				"color_sidebar_menu": "#123456",
				"color_menu_bar": "#123456",
				"theme": "dark",
				# The old one-field-per-variable Expert fields (moved by v0_0_11).
				"surface_base": "#fafafa",
				"surface_gray_10": "#292929",
			}
		)
		self.assertNotIn("--", css)


class TestTokenDefaults(UnitTestCase):
	CSS = (
		"@layer base{:root{--surface-base: oklch(1 0 0);--tw-ring: 0}}"
		"[data-theme=dark]{--surface-base: oklch(.2 0 0)}"
		":root{--ink-gray-7: oklch(.341 0 0);--surface-base: #000}"
	)

	def test_reads_only_light_root_blocks(self):
		tokens = branding._parse_root_tokens(self.CSS)
		self.assertEqual(tokens["--surface-base"], "oklch(1 0 0)")
		self.assertEqual(tokens["--ink-gray-7"], "oklch(.341 0 0)")
		self.assertNotIn("--tw-ring", tokens)

	def test_defaults_are_keyed_by_advanced_fieldname(self):
		tokens = {"--surface-base": "oklch(1 0 0)", "--login-ink": "#fff", "--unrelated": "1"}
		with (
			patch.object(branding.frappe, "only_for"),
			patch.object(branding, "_spa_token_defaults", return_value=tokens),
		):
			self.assertEqual(branding.get_token_defaults(), {"adv_page_bg": "oklch(1 0 0)"})

	def test_defaults_need_system_manager(self):
		with patch.object(branding.frappe, "only_for", side_effect=branding.frappe.PermissionError):
			self.assertRaises(branding.frappe.PermissionError, branding.get_token_defaults)

	def test_missing_spa_build_gives_no_defaults(self):
		with patch.object(branding, "_spa_stylesheet_path", return_value=None):
			self.assertEqual(branding._spa_token_defaults(), {})

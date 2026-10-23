"""Brand Customize colors only brand the light theme.

A user who switches to dark must get the stock LMS dark palette. frappe-ui puts its
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
		css = _css(surface_base="#fafafa", ink_gray_9="#111111")
		light = _block(css, branding.LIGHT_THEME_SELECTOR)
		self.assertIn("--surface-base: #fafafa;", light)
		self.assertIn("--ink-gray-9: #111111;", light)
		self.assertNotIn("--surface-base", _block(css, ":root"))

	def test_login_colors_apply_in_every_theme(self):
		css = _css(login_bg_from="#000000", surface_base="#fafafa")
		self.assertIn("--login-bg-from: #000000;", _block(css, ":root"))
		self.assertNotIn("--login-bg-from", _block(css, branding.LIGHT_THEME_SELECTOR))

	def test_unbranded_instance_emits_no_values(self):
		css = _css()
		self.assertNotIn("--", css)

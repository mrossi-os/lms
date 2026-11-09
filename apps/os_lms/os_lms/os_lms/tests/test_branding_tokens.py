"""Expert mode of Brand Customize: every variable of the platform (fase-4-analisi.md).

Covers the variable list read from the SPA build, the checks on names and values
(both are written verbatim into the stylesheet served to everyone), where each
kind of variable is written, the copy from Base/Advanced and the save rules.
"""

from __future__ import annotations

import json
from contextlib import contextmanager
from unittest.mock import patch

import frappe
from frappe.tests import UnitTestCase

from os_lms.os_lms import branding, branding_tokens
from os_lms.os_lms.tests.test_branding_roles import TOKENS

STYLESHEET = (
	"@layer base{:root{--surface-base: oklch(1 0 0);--radius-4: 8px;--blue-500: oklch(.6 .2 250);"
	"--elevation-sm: 0px 1px 2px #0000001a;--tw-ring: 0}}"
	"[data-theme=dark]{--surface-base: oklch(.2 0 0)}"
	".a{background:var(--surface-base);border-radius:var(--radius-4);box-shadow:var(--elevation-sm)}"
	".plyr{color:var(--plyr-video-control-color,#fff);"
	"background:var(--plyr-video-control-background-hover,var(--plyr-color-main,var(--plyr-color-main,#00b2ff)));"
	"font-family:var(--plyr-font-family,inherit);border-radius:var(--plyr-control-radius,4px)}"
	".plyr__menu{box-shadow:var(--plyr-menu-shadow,0 1px 2px #00000026)}"
)

KNOWN = {
	"--surface-base": {"name": "--surface-base", "kind": "color"},
	"--radius-4": {"name": "--radius-4", "kind": "length"},
	"--elevation-sm": {"name": "--elevation-sm", "kind": "shadow"},
}


def _rows(names: dict) -> list[dict]:
	return [{"name": n, "default": "", "kind": k, "family": "other", "used": True} for n, k in names.items()]


@contextmanager
def known_tokens(names: dict | None = None):
	names = names or {name: row["kind"] for name, row in KNOWN.items()}
	rows = _rows(names)
	with (
		patch.object(branding_tokens, "manifest", return_value=rows),
		patch.object(branding_tokens, "by_name", return_value={row["name"]: row for row in rows}),
	):
		yield


def block(css: str, selector: str) -> str:
	start = css.index(selector + " {")
	return css[start : css.index("}", start)]


class TestTokenList(UnitTestCase):
	def setUp(self):
		self.rows = {row["name"]: row for row in branding_tokens.parse(STYLESHEET, STYLESHEET)}

	def test_light_root_variables_are_listed_with_their_stock_value(self):
		self.assertEqual(self.rows["--surface-base"]["default"], "oklch(1 0 0)")
		self.assertNotIn("--tw-ring", self.rows)

	def test_kinds(self):
		self.assertEqual(self.rows["--surface-base"]["kind"], "color")
		self.assertEqual(self.rows["--radius-4"]["kind"], "length")
		self.assertEqual(self.rows["--elevation-sm"]["kind"], "shadow")
		self.assertEqual(self.rows["--plyr-font-family"]["kind"], "other")

	def test_variables_read_by_nothing_have_no_effect(self):
		self.assertTrue(self.rows["--surface-base"]["used"])
		self.assertFalse(self.rows["--blue-500"]["used"])

	def test_player_variables_come_from_their_fallback(self):
		self.assertEqual(self.rows["--plyr-video-control-color"]["default"], "#fff")
		self.assertEqual(self.rows["--plyr-control-radius"]["kind"], "length")
		# A nested fallback resolves to the value actually used.
		self.assertEqual(self.rows["--plyr-video-control-background-hover"]["default"], "#00b2ff")
		self.assertEqual(self.rows["--plyr-video-control-background-hover"]["kind"], "color")
		self.assertEqual(self.rows["--plyr-menu-shadow"]["kind"], "shadow")
		self.assertEqual(self.rows["--plyr-video-control-color"]["family"], "plyr")

	def test_platform_variables_are_always_listed(self):
		for name in branding_tokens.EXTRA_TOKENS:
			self.assertEqual(self.rows[name]["family"], "os_lms", name)
			self.assertTrue(self.rows[name]["used"], name)
		self.assertEqual(self.rows["--os-chart-1"]["kind"], "color")

	def test_installed_build_is_read(self):
		rows = branding_tokens.manifest()
		if not rows:
			self.skipTest("no SPA build on this site")
		names = {row["name"] for row in rows}
		self.assertIn("--surface-gray-10", names)
		self.assertIn("--plyr-color-main", names)
		for row in rows:
			self.assertRegex(row["name"], branding_tokens.TOKEN_NAME_RE)


class TestTokenChecks(UnitTestCase):
	def test_names_that_could_break_the_stylesheet_are_refused(self):
		for name in ("--x;}body{", "--a b", "--x:", "color", "--", "--A", "--x/*"):
			self.assertFalse(branding.is_valid_token(name, "#fff"), name)

	def test_values_that_break_out_or_are_too_long_are_refused(self):
		self.assertFalse(branding.is_valid_token("--x", "red; } body { display: none"))
		self.assertFalse(branding.is_valid_token("--x", "url(https://evil)"))
		self.assertFalse(branding.is_valid_token("--x", "1px " * 80))
		# frappe-ui's own shadows are longer than a color field allows.
		self.assertTrue(branding.is_valid_token("--x", "0px 0px 1.5px 0px #0000002e, " * 4))

	def test_unknown_variables_new_ones_refused_saved_ones_tolerated(self):
		values = {"expert_tokens": {"--surface-base": "#fff", "--gone": "#000", "--typo": "#000"}}
		with known_tokens():
			invalid, unknown_new, unknown_saved = branding.check_expert_tokens(values, {"--gone"})
		self.assertEqual((invalid, unknown_new, unknown_saved), ([], ["--typo"], ["--gone"]))

	def test_without_a_build_only_the_name_format_is_checked(self):
		with patch.object(branding_tokens, "by_name", return_value={}):
			self.assertEqual(branding.check_expert_tokens({"expert_tokens": {"--any": "#fff"}}, set()), ([], [], []))


class TestExpertCss(UnitTestCase):
	def test_colors_and_shadows_are_light_only_lengths_everywhere(self):
		values = {"expert_tokens": {"--surface-base": "#fafafa", "--elevation-sm": "none", "--radius-4": "12px"}}
		with known_tokens():
			css = branding._build_css(values)
		light = block(css, branding.BRANDED_THEME_SELECTOR)
		root = css[css.rindex(":root {") :]
		self.assertIn("--surface-base: #fafafa;", light)
		self.assertIn("--elevation-sm: none;", light)
		self.assertIn("--radius-4: 12px;", root)
		self.assertNotIn("--radius-4", light)

	def test_refused_rows_are_never_written(self):
		values = {"expert_tokens": [{"token": "--x;}body{", "value": "red"}, {"token": "--y", "value": "a}b"}]}
		with known_tokens():
			css = branding._build_css(values)
		self.assertNotIn("body", css)
		self.assertNotIn("--y", css)

	def test_saved_rows_are_read_from_the_table(self):
		values = {"expert_tokens": [{"token": "--surface-base", "value": " #fafafa "}, {"token": "--x", "value": ""}]}
		self.assertEqual(branding.expert_values(values), {"--surface-base": "#fafafa"})


@contextmanager
def stock():
	with (
		patch.object(branding, "_spa_token_defaults", return_value=TOKENS),
		patch.object(branding.frappe, "only_for"),
	):
		yield


class TestCopyToExpert(UnitTestCase):
	def test_only_what_applies_everywhere_is_copied(self):
		values = {
			"mode": branding.MODE_ADVANCED,
			"adv_page_bg": "#fafafa",
			"adv_button_bg": "#0a2e5a",
			"adv_radius": "Large",
		}
		with stock():
			result = branding.to_expert(json.dumps(values))
		self.assertEqual(result["tokens"]["--surface-base"], "#fafafa")
		self.assertNotIn("--surface-gray-10", result["tokens"])
		self.assertEqual(result["tokens"]["--radius-4"], "12.8px")
		# Button background, text, hover and pressed are written inside the buttons.
		self.assertEqual(result["scoped"], 4)

	def test_base_is_copied_too(self):
		with stock():
			result = branding.to_expert(json.dumps({"mode": branding.MODE_BASE, "base_primary": "#c2185b"}))
		self.assertEqual(result["tokens"]["--os-chart-1"], "#c2185b")

	def test_expert_has_nothing_to_copy(self):
		with stock():
			self.assertEqual(branding.to_expert(json.dumps({"mode": branding.MODE_EXPERT})), {"tokens": {}, "scoped": 0})


class TestSaveRules(UnitTestCase):
	def _doc(self, rows: list[tuple[str, str]], before: dict | None = None):
		doc = frappe.get_doc("Brand Customize")
		doc.set("expert_tokens", [{"token": token, "value": value} for token, value in rows])
		doc._doc_before_save = before
		return doc

	def test_known_variables_save(self):
		with known_tokens():
			self._doc([("--surface-base", "#fafafa")]).validate()

	def test_duplicates_are_refused(self):
		with known_tokens():
			doc = self._doc([("--surface-base", "#fafafa"), ("--surface-base", "#000")])
			self.assertRaises(frappe.ValidationError, doc.validate)

	def test_new_unknown_variable_is_refused(self):
		with known_tokens():
			self.assertRaises(frappe.ValidationError, self._doc([("--typo", "#000")]).validate)

	def test_unsafe_value_is_refused(self):
		with known_tokens():
			doc = self._doc([("--surface-base", "red; } body { display: none")])
			self.assertRaises(frappe.ValidationError, doc.validate)

	def test_saved_variable_gone_after_an_update_does_not_block(self):
		with known_tokens(), patch.object(frappe, "msgprint") as msgprint:
			self._doc([("--gone", "#000")], before={"expert_tokens": {"--gone": "#000"}}).validate()
		msgprint.assert_called_once()

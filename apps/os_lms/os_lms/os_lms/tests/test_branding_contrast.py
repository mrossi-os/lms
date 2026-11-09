"""Brand Customize readability and presets (docs/brand-customize/fase-5-analisi.md).

The contrast report must stay quiet on the stock colors (frappe-ui's own palette
is not all AA), flag what a brand makes worse and point at the right field; Base
must keep its text readable on mid-tone backgrounds; presets round-trip the
Export data.
"""

from __future__ import annotations

import json
from unittest.mock import patch

import frappe
from frappe.tests import UnitTestCase

from os_lms.os_lms import branding, branding_color, branding_contrast, branding_presets, branding_roles
from os_lms.os_lms.tests.test_branding_roles import STOCK, stock_tokens

# The colors saved on the local site on 2026-11-09 (worklog, activity 6).
MID_BLUE_BASE = {
	"base_primary": "#d1d1d1",
	"base_accent": "#4463F0",
	"base_background": "#4F9DD9",
	"base_gray_tint": "#0008ff",
}


def report(mode: str, **values) -> dict[str, dict]:
	with stock_tokens():
		entries = branding_contrast.report({"mode": mode, **values}, mode, STOCK)
	return {entry["key"]: entry for entry in entries}


class TestContrastReport(UnitTestCase):
	def test_stock_colors_raise_no_warning(self):
		for mode in (branding.MODE_BASE, branding.MODE_ADVANCED, branding.MODE_EXPERT):
			entries = report(mode)
			self.assertEqual([k for k, e in entries.items() if e["level"] == "low"], [], mode)
		# frappe-ui's secondary text is under AA by itself: a note, not a warning.
		self.assertEqual(report(branding.MODE_ADVANCED)["page_muted"]["level"], "stock")

	def test_a_brand_that_makes_text_harder_to_read_is_flagged(self):
		entries = report(branding.MODE_ADVANCED, adv_text_ink="#dddddd")
		self.assertEqual(entries["page_text"]["level"], "low")
		self.assertEqual(entries["page_text"]["fields"]["advanced"], ["adv_text_ink", "adv_page_bg"])
		self.assertLess(entries["page_text"]["ratio"], 2)
		self.assertEqual(entries["page_heading"]["level"], "ok")

	def test_areas_read_their_own_colors(self):
		entries = report(branding.MODE_ADVANCED, adv_button_bg="#ffd85c")
		# The button text is derived readable; the light button barely stands out.
		self.assertEqual(entries["button_text"]["level"], "ok")
		self.assertEqual(entries["button_shape"]["level"], "low")
		self.assertEqual(entries["button_shape"]["fg"], "#ffd85c")

	def test_expert_rows_are_measured(self):
		entries = report(branding.MODE_EXPERT, expert_tokens={"--ink-gray-7": "#eeeeee"})
		self.assertEqual(entries["page_text"]["level"], "low")
		self.assertEqual(entries["page_text"]["fields"]["expert"], ["--ink-gray-7", "--surface-base"])
		# A value that cannot be measured falls back to stock instead of failing.
		entries = report(branding.MODE_EXPERT, expert_tokens={"--ink-gray-7": "var(--ink-gray-9)"})
		self.assertEqual(entries["page_text"]["level"], "ok")

	def test_login_pairs_in_every_mode(self):
		entries = report(branding.MODE_BASE, login_ink="#ffffff")
		self.assertEqual(entries["login_text_from"]["level"], "low")
		self.assertEqual(entries["login_text_from"]["fields"], {"login": ["login_ink", "login_bg_from"]})
		# The gradient end falls back to its start.
		entries = report(branding.MODE_BASE, login_ink="#ffffff", login_bg_from="#0a2e5a")
		self.assertEqual(entries["login_text_from"]["level"], "ok")
		self.assertEqual(entries["login_text_to"]["level"], "ok")

	def test_no_build_no_report(self):
		self.assertEqual(branding_contrast.report({}, branding.MODE_BASE, {}), [])

	def test_preview_returns_the_report(self):
		with stock_tokens():
			result = branding.brand_css_preview(json.dumps({"mode": "Advanced", "adv_text_ink": "#dddddd"}))
		levels = {entry["key"]: entry["level"] for entry in result["contrast"]}
		self.assertEqual(levels["page_text"], "low")


class TestColorParsing(UnitTestCase):
	def test_measurable_colors(self):
		self.assertEqual(branding_contrast.to_hex("#ABC"), "#aabbcc")
		self.assertEqual(branding_contrast.to_hex("rgb(10, 20, 30)"), "#0a141e")
		self.assertEqual(branding_contrast.to_hex("rgba(10 20 30 / 1)"), "#0a141e")
		self.assertEqual(branding_contrast.to_hex("White"), "#ffffff")
		self.assertEqual(branding_contrast.to_hex("oklch(1 0 0)"), "#ffffff")

	def test_unmeasurable_colors(self):
		for value in ("var(--x)", "rgba(0, 0, 0, .5)", "transparent", "linear-gradient(red, blue)", "", None):
			self.assertIsNone(branding_contrast.to_hex(value), value)


class TestBaseReadability(UnitTestCase):
	def test_light_page_keeps_the_stock_lightness(self):
		for background in ("", "#ffffff", "#f7f7fb"):
			roles = branding_roles.derive_base({"base_background": background, "base_gray_tint": "#0a2e5a"}, STOCK)
			for fieldname, L in (("adv_text_ink", 0.341), ("adv_muted_ink", 0.586), ("adv_heading_ink", 0.168)):
				self.assertAlmostEqual(branding_color.to_oklch(roles[fieldname])[0], L, delta=0.01, msg=background)

	def test_mid_tone_background_keeps_text_readable(self):
		entries = report(branding.MODE_BASE, **MID_BLUE_BASE)
		for key in ("page_heading", "page_text", "page_muted", "card_text", "sidebar_text"):
			self.assertNotEqual(entries[key]["level"], "low", key)
		self.assertGreaterEqual(entries["page_text"]["ratio"], 4.5)
		# The sidebar text role writes 5 grays at fixed steps from its darkest:
		# even at black the lightest one cannot reach the stock contrast on this
		# blue. It is much better than before (1.3:1) and still reported, with
		# the background as the color to change.
		self.assertGreater(entries["sidebar_muted"]["ratio"], 2.5)
		self.assertEqual(entries["sidebar_muted"]["fields"]["base"], ["base_background"])
		# A gray primary color on a blue page is the user's choice: reported.
		self.assertEqual(entries["button_shape"]["level"], "low")

	def test_gray_background_without_tint(self):
		roles = branding_roles.derive_base({"base_background": "#777777"}, STOCK)
		self.assertGreaterEqual(branding_color.contrast_ratio(roles["adv_text_ink"], "#777777"), 4.5)
		# Nothing to adjust on white: no gray role is written without a tint.
		self.assertNotIn("adv_text_ink", branding_roles.derive_base({"base_background": "#ffffff"}, STOCK))

	def test_secondary_button_stands_out_from_the_page(self):
		roles = branding_roles.derive_base({"base_background": "#4F9DD9", "base_accent": "#4463F0"}, STOCK)
		stock_ratio = branding_color.contrast_ratio(
			branding_color.from_oklch(*STOCK["--surface-base"]),
			branding_color.from_oklch(*STOCK["--surface-gray-2"]),
		)
		self.assertGreaterEqual(
			branding_color.contrast_ratio(roles["adv_secondary_bg"], "#4F9DD9"), stock_ratio - 0.01
		)
		# On white the usual 12% mix is enough.
		roles = branding_roles.derive_base({"base_accent": "#c2185b"}, STOCK)
		self.assertEqual(roles["adv_secondary_bg"], branding_color.mix("#ffffff", "#c2185b", 0.12))


class TestSaveSummary(UnitTestCase):
	MODULE = "os_lms.os_lms.doctype.brand_customize.brand_customize"

	def _summary(self, **values):
		doc = frappe.get_doc("Brand Customize")
		doc.update({"mode": branding.MODE_ADVANCED, **values})
		with (
			stock_tokens(),
			patch(f"{self.MODULE}._token_stock", return_value=STOCK),
			patch.object(frappe, "msgprint") as msgprint,
		):
			doc.report_low_contrast()
		return msgprint

	def test_low_contrast_is_reported_without_blocking(self):
		msgprint = self._summary(adv_text_ink="#dddddd")
		msgprint.assert_called_once()
		self.assertIn("orange", str(msgprint.call_args))

	def test_readable_colors_say_nothing(self):
		self._summary(adv_text_ink="#222222").assert_not_called()


class TestPresets(UnitTestCase):
	NAME = "Test preset fase 5"

	def setUp(self):
		self.created = []

	def tearDown(self):
		# Only the presets this test created, by exact name.
		for name in self.created:
			frappe.delete_doc("Brand Preset", name, force=True, ignore_permissions=True)
		frappe.db.rollback()

	def _save(self, data, overwrite=0, name=None):
		name = name or self.NAME
		result = branding_presets.save_preset(name, json.dumps(data), overwrite)
		if result.get("name") and result["name"] not in self.created:
			self.created.append(result["name"])
		return result

	def test_save_and_read_back(self):
		data = {"mode": "Base", **MID_BLUE_BASE, "not_a_field": "x", "expert_tokens": [{"token": "--a", "value": "#fff"}]}
		result = self._save(data)
		self.assertEqual(result["mode"], "Base")
		preset = branding_presets.get_preset(result["name"])
		self.assertEqual(preset["data"]["base_primary"], "#d1d1d1")
		self.assertNotIn("not_a_field", preset["data"])
		self.assertEqual(preset["data"]["expert_tokens"], [{"token": "--a", "value": "#fff"}])
		listed = {row["name"]: row for row in branding_presets.get_presets()}
		self.assertEqual(listed[result["name"]]["swatches"], ["#d1d1d1", "#4463f0", "#4f9dd9", "#0008ff"])

	def test_existing_name_asks_before_overwriting(self):
		self._save({"mode": "Base", "base_primary": "#111111"})
		self.assertEqual(self._save({"mode": "Base", "base_primary": "#222222"}), {"exists": True})
		self.assertEqual(branding_presets.get_preset(self.NAME)["data"]["base_primary"], "#111111")
		self._save({"mode": "Expert", "expert_tokens": [{"token": "--x", "value": "#333333"}]}, overwrite=1)
		preset = branding_presets.get_preset(self.NAME)
		self.assertEqual(preset["mode"], "Expert")
		self.assertNotIn("base_primary", preset["data"])

	def test_empty_preset_is_refused(self):
		self.assertRaises(frappe.ValidationError, self._save, {"nothing": "here"})

	def test_clean_data_drops_bad_rows(self):
		data = branding_presets.clean_data(
			{"expert_tokens": [{"token": "--a", "value": "x" * 400}, {"token": 5, "value": "#fff"}, "row"]}
		)
		self.assertEqual(data["expert_tokens"], [])
		self.assertEqual(branding_presets.clean_data("not json"), {})


class TestBasePlaceholder(UnitTestCase):
	def test_placeholder_stays_light_inside_light_fields(self):
		roles = branding_roles.derive_base(MID_BLUE_BASE, STOCK)
		# Fields keep a light background, so the placeholder keeps its stock lightness.
		self.assertAlmostEqual(branding_color.to_oklch(roles["adv_placeholder_ink"])[0], 0.683, delta=0.01)
		self.assertNotEqual(report(branding.MODE_BASE, **MID_BLUE_BASE)["input_placeholder"]["level"], "low")

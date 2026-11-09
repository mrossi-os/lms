"""Brand Customize Base and Advanced modes (docs/brand-customize/fase-3-analisi.md).

Each role must write its tokens only in its own area, an empty mode must leave
the stock palette, and Base copied into Advanced must give the same CSS.
"""

from __future__ import annotations

import json
import re
from contextlib import contextmanager
from unittest.mock import patch

import frappe
from frappe.tests import UnitTestCase

from os_lms.os_lms import branding, branding_color, branding_roles

TOKENS = {
	"--surface-base": "oklch(1 0 0)",
	"--surface-sidebar": "oklch(.979 0 0)",
	"--surface-elevation-1": "oklch(1 0 0)",
	"--surface-elevation-3": "oklch(1 0 0)",
	"--surface-gray-1": "oklch(.979 0 0)",
	"--surface-gray-2": "oklch(.964 0 0)",
	"--surface-gray-3": "oklch(.946 0 0)",
	"--surface-gray-4": "oklch(.913 0 0)",
	"--surface-gray-8": "oklch(.439 0 0)",
	"--surface-gray-9": "oklch(.341 0 0)",
	"--surface-gray-10": "oklch(.205 0 0)",
	"--ink-gray-3": "oklch(.83 0 0)",
	"--ink-gray-4": "oklch(.683 0 0)",
	"--ink-gray-5": "oklch(.586 0 0)",
	"--ink-gray-6": "oklch(.439 0 0)",
	"--ink-gray-7": "oklch(.341 0 0)",
	"--ink-gray-8": "oklch(.205 0 0)",
	"--ink-gray-9": "oklch(.168 0 0)",
	"--ink-base": "oklch(1 0 0)",
	"--ink-blue-link": "oklch(.641 .186 251.565)",
	"--outline-gray-1": "oklch(.946 0 0)",
	"--outline-gray-2": "oklch(.913 0 0)",
	"--outline-gray-3": "oklch(.83 0 0)",
	"--outline-gray-4": "oklch(.683 0 0)",
	"--surface-green-2": "oklch(.965 .03 155.987)",
	"--surface-green-7": "oklch(.57 .119 158.092)",
	"--ink-green-8": "oklch(.53 .122 156.15)",
	"--outline-green-3": "oklch(.872 .084 155.952)",
	"--radius-0": "0px",
	"--radius-1": "4px",
	"--radius-4": "8px",
	"--radius-full": "9999px",
}
STOCK = {name: branding_color.parse_oklch(value) for name, value in TOKENS.items()}
STOCK = {name: value for name, value in STOCK.items() if value}


@contextmanager
def stock_tokens():
	with (
		patch.object(branding, "_spa_token_defaults", return_value=TOKENS),
		patch.object(branding.frappe, "only_for"),
	):
		yield


def css(**values) -> str:
	with stock_tokens():
		return branding._build_css(values)


def block(css_text: str, selector_start: str) -> str:
	"""Body of the first rule whose selector list starts with ``selector_start``."""
	for match in re.finditer(r"([^{}]+)\{([^}]*)\}", css_text):
		if match.group(1).strip().startswith(selector_start):
			return match.group(2)
	return ""


B = branding.BRANDED_THEME_SELECTOR
GLOBAL = B + " {"


def global_block(css_text: str) -> str:
	start = css_text.index(GLOBAL) + len(GLOBAL)
	return css_text[start : css_text.index("}", start)]


def declared(block_text: str) -> dict[str, str]:
	return dict(re.findall(r"(--[\w-]+):\s*([^;]+);", block_text))


class TestDoctypeFields(UnitTestCase):
	def test_every_role_has_a_color_field(self):
		meta = frappe.get_meta("Brand Customize")
		for fieldname in (*branding_roles.BASE_FIELDS, *branding_roles.ROLE_FIELDS):
			df = meta.get_field(fieldname)
			self.assertIsNotNone(df, fieldname)
			self.assertEqual(df.fieldtype, "Color", fieldname)
		self.assertEqual(meta.get_field(branding_roles.RADIUS_FIELD).fieldtype, "Select")
		self.assertFalse(meta.get_field("mode").read_only)

	def test_every_color_field_can_be_highlighted(self):
		specs = branding.highlight_specs()
		meta = frappe.get_meta("Brand Customize")
		for df in meta.fields:
			if df.fieldtype == "Color" and not df.fieldname.startswith("app_"):
				self.assertTrue(specs.get(df.fieldname), df.fieldname)


class TestModesStayApart(UnitTestCase):
	def test_empty_base_and_advanced_leave_the_stock_palette(self):
		for mode in (branding.MODE_BASE, branding.MODE_ADVANCED):
			self.assertNotIn("--", css(mode=mode), mode)

	def test_only_the_active_mode_is_written(self):
		values = {
			"base_primary": "#c2185b",
			"adv_page_bg": "#fafafa",
			"expert_tokens": {"--surface-base": "#eeeeee"},
		}
		base = css(mode=branding.MODE_BASE, **values)
		advanced = css(mode=branding.MODE_ADVANCED, **values)
		expert = css(mode=branding.MODE_EXPERT, **values)
		self.assertIn("#c2185b", base)
		self.assertNotIn("#fafafa", base)
		self.assertNotIn("#eeeeee", base)
		self.assertIn("--surface-base: #fafafa;", advanced)
		self.assertNotIn("#c2185b", advanced)
		self.assertIn("--surface-base: #eeeeee;", expert)
		self.assertNotIn("#fafafa", expert)
		self.assertNotIn("#c2185b", expert)

	def test_every_rule_is_light_theme_only_except_login_and_radius(self):
		text = css(mode=branding.MODE_ADVANCED, adv_sidebar_ink="#123456", adv_button_bg="#c2185b")
		for match in re.finditer(r"([^{}]+)\{", text):
			for selector in match.group(1).split(","):
				selector = selector.strip()
				self.assertTrue(selector.startswith(B) or selector == ":root", selector)

	def test_no_var_chains(self):
		text = css(mode=branding.MODE_BASE, base_primary="#c2185b", base_background="#f5f7fb")
		self.assertNotIn("var(", text)


class TestAreas(UnitTestCase):
	def test_scoped_roles_stay_in_their_area(self):
		text = css(mode=branding.MODE_ADVANCED, adv_sidebar_ink="#123456")
		sidebar = declared(block(text, f"{B} .bg-surface-sidebar"))
		self.assertEqual(sidebar["--ink-gray-8"], "#123456")
		self.assertNotIn("#123456", global_block(text))

	def test_global_roles_are_global(self):
		text = css(mode=branding.MODE_ADVANCED, adv_heading_ink="#101820")
		self.assertEqual(declared(global_block(text))["--ink-gray-9"], "#101820")

	def test_primary_button_is_scoped_to_buttons(self):
		text = css(mode=branding.MODE_ADVANCED, adv_button_bg="#0a2e5a")
		button = declared(block(text, f"{B} button.bg-surface-gray-10"))
		self.assertEqual(button["--surface-gray-10"], "#0a2e5a")
		self.assertNotIn("--surface-gray-10", global_block(text))
		self.assertIn(f"{B} a.bg-surface-gray-10", text)

	def test_multi_token_roles_keep_the_stock_gap(self):
		text = css(mode=branding.MODE_ADVANCED, adv_text_ink="#3a3a5a")
		tokens = declared(global_block(text))
		gap = branding_color.to_oklch(tokens["--ink-gray-7"])[0] - branding_color.to_oklch(tokens["--ink-gray-8"])[0]
		self.assertAlmostEqual(gap, 0.341 - 0.205, delta=0.01)

	def test_global_roles_do_not_reach_areas_with_their_own_role(self):
		stock_ink = branding_color.from_oklch(*STOCK["--ink-gray-8"])
		stock_subtle = branding_color.from_oklch(*STOCK["--surface-gray-2"])
		stock_border = branding_color.from_oklch(*STOCK["--outline-gray-2"])
		text = css(
			mode=branding.MODE_ADVANCED,
			adv_text_ink="#ff00ff",
			adv_subtle_bg="#ffe0ff",
			adv_border="#ff00ff",
		)
		self.assertEqual(declared(block(text, f"{B} .bg-surface-sidebar"))["--ink-gray-8"], stock_ink)
		self.assertEqual(
			declared(block(text, f"{B} button.bg-surface-gray-2"))["--ink-gray-8"], stock_ink
		)
		self.assertEqual(
			declared(block(text, f'{B} input:not([type="checkbox"])'))["--surface-gray-2"], stock_subtle
		)
		self.assertEqual(
			declared(block(text, f"{B} button.border-outline-gray-2"))["--outline-gray-2"], stock_border
		)

	def test_an_area_role_wins_over_the_stock_pin(self):
		text = css(mode=branding.MODE_ADVANCED, adv_text_ink="#ff00ff", adv_sidebar_ink="#123456")
		self.assertEqual(declared(block(text, f"{B} .bg-surface-sidebar"))["--ink-gray-8"], "#123456")
		# Nested areas follow the sidebar instead of being pinned again.
		self.assertNotIn("--ink-gray-8", declared(block(text, f"{B} .bg-surface-sidebar svg")))


class TestDerivations(UnitTestCase):
	def test_button_text_hover_and_pressed_follow_the_button(self):
		roles = branding_roles.resolve({"adv_button_bg": "#0a2e5a"})
		self.assertEqual(roles["adv_button_ink"], branding_color.WHITE)
		bg_l = branding_color.to_oklch("#0a2e5a")[0]
		self.assertGreater(branding_color.to_oklch(roles["adv_button_hover"])[0], bg_l)
		self.assertGreater(
			branding_color.to_oklch(roles["adv_button_pressed"])[0],
			branding_color.to_oklch(roles["adv_button_hover"])[0],
		)
		light = branding_roles.resolve({"adv_button_bg": "#ffd85c"})
		self.assertEqual(light["adv_button_ink"], branding_color.NEAR_BLACK)
		self.assertLess(branding_color.to_oklch(light["adv_button_hover"])[0], branding_color.to_oklch("#ffd85c")[0])

	def test_explicit_values_win_over_derived_ones(self):
		roles = branding_roles.resolve({"adv_button_bg": "#0a2e5a", "adv_button_hover": "#ff0000"})
		self.assertEqual(roles["adv_button_hover"], "#ff0000")

	def test_status_family_keeps_lightness_and_takes_the_hue(self):
		tokens = branding_roles._family_tokens("#1e88e5", "green", STOCK)
		self.assertEqual(set(tokens), {"--surface-green-2", "--surface-green-7", "--ink-green-8", "--outline-green-3"})
		for name, value in tokens.items():
			self.assertAlmostEqual(branding_color.to_oklch(value)[0], STOCK[name][0], delta=0.02, msg=name)
		hue = branding_color.to_oklch(tokens["--surface-green-7"])[2]
		self.assertAlmostEqual(hue, branding_color.to_oklch("#1e88e5")[2], delta=5)

	def test_base_primary_drives_readable_colors(self):
		roles = branding_roles.resolve(branding_roles.derive_base({"base_primary": "#ffd85c"}, STOCK))
		self.assertEqual(roles["adv_button_bg"], "#ffd85c")
		self.assertEqual(roles["adv_button_ink"], branding_color.NEAR_BLACK)
		self.assertGreaterEqual(branding_color.contrast_ratio(roles["adv_link_ink"], "#ffffff"), 4.5)
		self.assertGreaterEqual(
			branding_color.contrast_ratio(roles["adv_sidebar_active_ink"], roles["adv_sidebar_active_bg"]), 4.5
		)
		self.assertTrue(all(f"adv_chart_{n}" in roles for n in range(1, 6)))
		for state in ("adv_success", "adv_error", "adv_warning", "adv_info"):
			self.assertNotIn(state, roles)

	def test_gray_tint_keeps_stock_lightness(self):
		roles = branding_roles.derive_base({"base_gray_tint": "#0a2e5a"}, STOCK)
		L, C, H = branding_color.to_oklch(roles["adv_text_ink"])
		self.assertAlmostEqual(L, 0.341, delta=0.01)
		self.assertGreater(C, 0.005)
		self.assertNotIn("adv_button_bg", roles)

	def test_gray_tint_reaches_the_areas_with_their_own_role(self):
		roles = branding_roles.derive_base({"base_gray_tint": "#0a2e5a"}, STOCK)
		for fieldname in ("adv_sidebar_ink", "adv_input_bg", "adv_secondary_ink", "adv_outline_border"):
			self.assertIn(fieldname, roles)
		self.assertEqual(roles["adv_sidebar_ink"], roles["adv_secondary_ink"])
		# With an accent, the secondary button follows the accent instead.
		accented = branding_roles.derive_base({"base_gray_tint": "#0a2e5a", "base_accent": "#c2185b"}, STOCK)
		self.assertNotEqual(accented["adv_secondary_bg"], roles["adv_secondary_bg"])

	def test_base_copied_into_advanced_gives_the_same_css(self):
		base = {
			"base_primary": "#c2185b",
			"base_accent": "#1e88e5",
			"base_background": "#f7f7fb",
			"base_gray_tint": "#0a2e5a",
		}
		with stock_tokens():
			copied = branding.base_to_advanced(json.dumps({**base, "mode": branding.MODE_BASE}))
		self.assertTrue(set(copied) <= set(branding_roles.ROLE_FIELDS))
		self.assertEqual(css(mode=branding.MODE_BASE, **base), css(mode=branding.MODE_ADVANCED, **copied))


class TestValidationAndRadius(UnitTestCase):
	def test_base_and_advanced_need_hex(self):
		values = {"base_primary": "oklch(.5 .1 200)", "adv_page_bg": "red", "adv_text_ink": "#333"}
		self.assertEqual(branding.invalid_fields(values), ["base_primary", "adv_page_bg"])
		self.assertNotIn("--surface-base", css(mode=branding.MODE_ADVANCED, adv_page_bg="red"))

	def test_saving_a_non_hex_role_fails(self):
		doc = frappe.get_doc("Brand Customize")
		doc.adv_page_bg = "red"
		self.assertRaises(frappe.ValidationError, doc.validate)

	def test_corner_rounding(self):
		small = css(mode=branding.MODE_ADVANCED, adv_radius="Small")
		root = declared(small[small.rindex(":root {") :])
		self.assertEqual(root["--radius-4"], "4px")
		self.assertEqual(root["--radius-1"], "2px")
		self.assertNotIn("--radius-full", root)
		self.assertNotIn("--radius-0", root)
		self.assertNotIn("--radius", css(mode=branding.MODE_ADVANCED, adv_radius="Standard"))
		self.assertNotIn("--radius", css(mode=branding.MODE_BASE, adv_radius="Small"))

	def test_preview_returns_base_swatches(self):
		with stock_tokens():
			result = branding.brand_css_preview(json.dumps({"mode": "Base", "base_primary": "#c2185b"}))
		self.assertEqual(result["roles"]["adv_button_bg"], "#c2185b")
		with stock_tokens():
			result = branding.brand_css_preview(json.dumps({"mode": "Advanced", "adv_page_bg": "#ffffff"}))
		self.assertEqual(result["roles"], {})

"""Brand Customize Export / Import / presets: the server side of the round trip.

The form script (brand_customize.js) writes every value field plus the
expert_tokens rows (version 2), and on import sets each known field (empty ones
too) and replaces the table; version 1 files carried one field per Expert
variable, mapped through LEGACY_EXPERT_FIELDS. These tests rebuild that contract
in Python and check that what the server saves and serves is identical to the
source, in every mode, and that bad files are refused when saved.

The browser half (file reading, confirmation, messages) is driven by
docs/brand-customize/test-import-export.js.
"""

from __future__ import annotations

import json
from unittest.mock import patch

import frappe
from frappe.model import no_value_fields
from frappe.tests import UnitTestCase

from os_lms.os_lms import branding, branding_presets, branding_tokens

DOCTYPE = "Brand Customize"

BASE = {
	"mode": "Base",
	"base_primary": "#d1d1d1",
	"base_accent": "#4463F0",
	"base_background": "#4F9DD9",
	"base_gray_tint": "#0008ff",
	"login_bg_from": "#0a2e5a",
	"login_ink": "#ffffff",
}
ADVANCED = {
	"mode": "Advanced",
	"adv_button_bg": "#c2185b",
	"adv_page_bg": "#fafafa",
	"adv_text_ink": "#222222",
	"adv_sidebar_bg": "#102030",
	"adv_radius": "Large",
	"login_button_bg": "#c2185b",
}
EXPERT = {
	"mode": "Expert",
	"login_bg_to": "#123456",
	"expert_tokens": [
		{"token": "--surface-gray-10", "value": "#292929"},
		{"token": "--ink-gray-9", "value": "oklch(0.2 0.02 260)"},
		{"token": "--radius-lg", "value": "14px"},
	],
}


def data_fieldnames() -> list[str]:
	"""What get_data_fieldnames() of the form script returns."""
	return [df.fieldname for df in frappe.get_meta(DOCTYPE).fields if df.fieldtype not in no_value_fields]


def export_payload(doc) -> dict:
	"""brand_settings_data() + export_brand_settings() of the form script."""
	data = {fieldname: doc.get(fieldname) or None for fieldname in data_fieldnames()}
	data[branding.EXPERT_TABLE] = [{"token": row.token, "value": row.value} for row in doc.get("expert_tokens")]
	return {"doctype": DOCTYPE, "version": 2, "exported_on": "2026-11-09 16:00:00", "data": data}


def apply_payload(doc, payload) -> None:
	"""apply_brand_settings() of the form script, on a server doc."""
	data = payload["data"] if isinstance(payload.get("data"), dict) else payload
	valid = set(data_fieldnames())
	for fieldname, value in data.items():
		if fieldname in valid:
			doc.set(fieldname, "" if value is None else value)
	legacy = branding.get_expert_tokens()["legacy"]
	tokens = {}
	for fieldname, css_var in legacy.items():
		if isinstance(data.get(fieldname), str) and data[fieldname].strip():
			tokens[css_var] = data[fieldname].strip()
	for row in data.get("expert_tokens") or []:
		if isinstance(row, dict) and isinstance(row.get("value"), str) and row["value"].strip():
			tokens[row["token"].strip()] = row["value"].strip()
	if isinstance(data.get("expert_tokens"), list) or any(f in data for f in legacy):
		doc.set("expert_tokens", [{"token": t, "value": v} for t, v in tokens.items()])


def comparable(doc) -> dict:
	values = {fieldname: doc.get(fieldname) or "" for fieldname in data_fieldnames()}
	values["expert_tokens"] = sorted((row.token, row.value) for row in doc.get("expert_tokens"))
	return values


class BrandCustomizeCase(UnitTestCase):
	"""Saves the Single in a transaction that is rolled back; the values the
	site had before are checked (and put back if anything committed)."""

	def setUp(self):
		frappe.set_user("Administrator")
		self.before = comparable(frappe.get_doc(DOCTYPE))
		self.msgprint = patch.object(frappe, "msgprint").start()

	def tearDown(self):
		patch.stopall()
		frappe.db.rollback()
		frappe.clear_document_cache(DOCTYPE, DOCTYPE)
		branding.clear_brand_cache()
		after = frappe.get_doc(DOCTYPE)
		if comparable(after) != self.before:  # pragma: no cover - safety net only
			self.fail("Brand Customize changed outside the test transaction")

	def saved(self, values: dict):
		"""A Brand Customize doc saved with only ``values`` set (the rest empty)."""
		doc = frappe.get_doc(DOCTYPE)
		for fieldname in data_fieldnames():
			doc.set(fieldname, "")
		doc.set("expert_tokens", [])
		doc.update({k: v for k, v in values.items() if k != "expert_tokens"})
		for row in values.get("expert_tokens", []):
			doc.append("expert_tokens", row)
		doc.save()
		return frappe.get_doc(DOCTYPE)

	def reset_to(self, values: dict):
		"""Fill the doc with something else, as the target site would have."""
		return self.saved(values)


class TestExportFormat(UnitTestCase):
	def test_every_saved_value_is_exported(self):
		fields = set(data_fieldnames())
		# The CSS reads these: an export without one would not reproduce the look.
		for fieldname in (*branding.PREVIEW_FIELDS, *branding.LOGIN_FIELD_TO_CSS_VAR):
			self.assertIn(fieldname, fields)
		self.assertNotIn("expert_tokens", fields)  # added by hand, as rows
		self.assertNotIn("contrast_report", fields)
		self.assertEqual(fields, branding_presets._fieldnames())

	def test_old_expert_fields_map_to_variables(self):
		legacy = branding.get_expert_tokens()["legacy"]
		self.assertEqual(legacy, branding.LEGACY_EXPERT_FIELDS)
		self.assertFalse(set(legacy) & set(data_fieldnames()), "a v1 field is still a form field")
		known = branding_tokens.by_name()
		if known:
			missing = [css_var for css_var in legacy.values() if css_var not in known]
			self.assertEqual(missing, [], "a v1 Expert field maps to a variable the build does not have")

	def test_export_is_json_serialisable(self):
		payload = export_payload(frappe.get_doc(DOCTYPE))
		self.assertEqual(json.loads(json.dumps(payload))["data"], payload["data"])


class TestRoundTrip(BrandCustomizeCase):
	def round_trip(self, source_values: dict, target_values: dict):
		source = self.saved(source_values)
		expected_values, expected_css = comparable(source), branding._build_css(source)
		payload = json.loads(json.dumps(export_payload(source)))

		target = self.reset_to(target_values)
		self.assertNotEqual(comparable(target), expected_values)
		apply_payload(target, payload)
		target.save()

		imported = frappe.get_doc(DOCTYPE)
		self.assertEqual(comparable(imported), expected_values)
		self.assertEqual(branding._build_css(imported), expected_css)
		frappe.clear_document_cache(DOCTYPE, DOCTYPE)
		branding.clear_brand_cache()
		self.assertEqual(branding._build_css(), expected_css)

	def test_base(self):
		self.round_trip(BASE, EXPERT)

	def test_advanced(self):
		self.round_trip(ADVANCED, BASE)

	def test_expert(self):
		self.round_trip(EXPERT, ADVANCED)

	def test_empty_file_clears_everything(self):
		self.round_trip({"mode": "Base"}, {**ADVANCED, **EXPERT, "mode": "Expert"})

	def test_other_modes_values_travel_too(self):
		# A Base doc that kept Advanced values from earlier: the copy is faithful.
		self.round_trip({**ADVANCED, **BASE}, EXPERT)


class TestVersion1Files(BrandCustomizeCase):
	def v1_payload(self, **expert_fields):
		data = {fieldname: None for fieldname in branding.LEGACY_EXPERT_FIELDS}
		data.update({fieldname: None for fieldname in data_fieldnames()})
		data.update(mode="Expert", login_ink="#eeeeee", **expert_fields)
		return {"doctype": DOCTYPE, "version": 1, "data": data}

	def test_old_fields_become_variables(self):
		doc = self.reset_to(BASE)
		apply_payload(doc, self.v1_payload(surface_gray_10="#292929", company_primary="#c2185b"))
		doc.save()
		doc = frappe.get_doc(DOCTYPE)
		self.assertEqual(
			branding.expert_values(doc), {"--surface-gray-10": "#292929", "--color-company-primary": "#c2185b"}
		)
		css = branding._build_css(doc)
		self.assertIn("--surface-gray-10: #292929;", css)
		self.assertIn("--login-ink: #eeeeee;", css)

	def test_empty_old_fields_clear_the_table(self):
		doc = self.reset_to(EXPERT)
		apply_payload(doc, self.v1_payload())
		doc.save()
		self.assertEqual(frappe.get_doc(DOCTYPE).get("expert_tokens"), [])


class TestBadFilesAreRefusedOnSave(BrandCustomizeCase):
	def import_and_save(self, data):
		doc = self.reset_to(BASE)
		apply_payload(doc, {"doctype": DOCTYPE, "version": 2, "data": data})
		doc.save()

	def test_values_that_break_the_stylesheet(self):
		for data in (
			{"login_ink": "red; } body { display: none"},
			{"login_bg_from": "url(https://example.com/x.png)"},
			{"base_primary": "blue"},  # Base and Advanced take hex only
			{"adv_button_bg": "#12"},
			{"expert_tokens": [{"token": "--surface-base", "value": "#fff;}"}]},
			{"expert_tokens": [{"token": "not-a-variable", "value": "#ffffff"}]},
		):
			with self.subTest(data=data):
				self.assertRaises(frappe.ValidationError, self.import_and_save, data)
				frappe.db.rollback()

	def test_variable_missing_from_this_build(self):
		# A file from a site with another SPA build (local vs staging).
		if not branding_tokens.by_name():
			self.skipTest("no SPA build")
		self.assertRaises(
			frappe.ValidationError,
			self.import_and_save,
			{"mode": "Expert", "expert_tokens": [{"token": "--does-not-exist-anywhere", "value": "#ffffff"}]},
		)

	def test_unknown_mode(self):
		self.assertRaises(frappe.ValidationError, self.import_and_save, {"mode": "Dark"})


class TestPresetRoundTrip(BrandCustomizeCase):
	NAME = "Test preset import export"

	def tearDown(self):
		# Only the preset this test created, by exact name.
		if frappe.db.exists("Brand Preset", self.NAME):
			frappe.delete_doc("Brand Preset", self.NAME, force=True, ignore_permissions=True)
		super().tearDown()

	def test_preset_reproduces_the_export(self):
		for source_values, target_values in ((BASE, EXPERT), (ADVANCED, BASE), (EXPERT, ADVANCED)):
			with self.subTest(mode=source_values["mode"]):
				source = self.saved(source_values)
				expected_values, expected_css = comparable(source), branding._build_css(source)
				data = export_payload(source)["data"]
				branding_presets.save_preset(self.NAME, json.dumps(data), overwrite=1)

				target = self.reset_to(target_values)
				# choose_preset() passes the preset data to the import code.
				apply_payload(target, {"data": branding_presets.get_preset(self.NAME)["data"]})
				target.save()
				imported = frappe.get_doc(DOCTYPE)
				self.assertEqual(comparable(imported), expected_values)
				self.assertEqual(branding._build_css(imported), expected_css)

	def test_empty_fields_are_kept_in_the_preset(self):
		data = branding_presets.clean_data({"mode": "Base", "base_primary": "#111111", "login_ink": None})
		self.assertEqual(data["login_ink"], "")

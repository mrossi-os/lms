# Copyright (c) 2026, ELITE and contributors
# For license information, please see license.txt

"""Brand Customize presets (docs/brand-customize/fase-5-analisi.md, §3.4).

A preset is the ``data`` part of Brand Customize's Export saved in the site
with a name. Applying one goes through the same form code as an imported file:
it only fills the form, nothing reaches the platform until the form is saved
(where every value is validated again).
"""

from __future__ import annotations

import json

import frappe
from frappe import _
from frappe.model import no_value_fields

from os_lms.os_lms import branding_contrast, branding_roles

DOCTYPE = "Brand Preset"
SOURCE_DOCTYPE = "Brand Customize"
EXPERT_TABLE = "expert_tokens"
MAX_VALUE_LENGTH = 300
MAX_TOKENS = 2000

SWATCH_FIELDS = {
	"Base": branding_roles.BASE_FIELDS,
	"Advanced": ("adv_button_bg", "adv_page_bg", "adv_sidebar_bg", "adv_text_ink"),
}


def _fieldnames() -> set[str]:
	meta = frappe.get_meta(SOURCE_DOCTYPE)
	return {df.fieldname for df in meta.fields if df.fieldtype not in no_value_fields}


def clean_data(data) -> dict:
	"""The Brand Customize values of ``data`` (a dict or its JSON), anything
	else dropped: unknown keys, non-text values, oversized ones."""
	if isinstance(data, str):
		try:
			data = json.loads(data)
		except ValueError:
			return {}
	if not isinstance(data, dict):
		return {}
	known = _fieldnames()
	clean = {}
	for fieldname, value in data.items():
		if fieldname not in known:
			continue
		# An empty field is kept: applying the preset clears it, as an imported file does.
		if value is None:
			clean[fieldname] = ""
		elif isinstance(value, str | int | float) and len(str(value)) <= MAX_VALUE_LENGTH:
			clean[fieldname] = value
	rows = data.get(EXPERT_TABLE)
	if isinstance(rows, list):
		clean[EXPERT_TABLE] = [
			{"token": row["token"].strip(), "value": row["value"].strip()}
			for row in rows[:MAX_TOKENS]
			if isinstance(row, dict)
			and isinstance(row.get("token"), str)
			and isinstance(row.get("value"), str)
			and row["value"].strip()
			and len(row["value"]) <= MAX_VALUE_LENGTH
		]
	return clean


def mode_of(data: dict) -> str:
	mode = data.get("mode")
	return mode if mode in ("Base", "Advanced", "Expert") else "Expert"


def swatches(data: dict) -> list[str]:
	"""Up to 4 colors that tell the preset apart in the list."""
	mode = mode_of(data)
	if mode in SWATCH_FIELDS:
		values = [data.get(f) for f in SWATCH_FIELDS[mode]]
	else:
		values = [row["value"] for row in data.get(EXPERT_TABLE) or []]
	found = []
	for value in values:
		hex_value = branding_contrast.to_hex(value) if value else None
		if hex_value and hex_value not in found:
			found.append(hex_value)
		if len(found) == 4:
			break
	return found


@frappe.whitelist(methods=["POST"])
def save_preset(preset_name: str, values: str, overwrite: int = 0) -> dict:
	"""Save the form values (also unsaved ones, decision G4) as a preset.

	Returns ``{"exists": True}`` instead of overwriting, unless asked to.
	"""
	frappe.only_for("System Manager")
	preset_name = (preset_name or "").strip()
	if not preset_name:
		frappe.throw(_("Enter a name for the preset."))
	data = clean_data(values)
	if frappe.db.exists(DOCTYPE, preset_name):
		if not int(overwrite or 0):
			return {"exists": True}
		doc = frappe.get_doc(DOCTYPE, preset_name)
		doc.data = json.dumps(data)
		doc.save()
	else:
		doc = frappe.get_doc({"doctype": DOCTYPE, "preset_name": preset_name, "data": json.dumps(data)})
		doc.insert()
	return {"name": doc.name, "mode": doc.mode}


@frappe.whitelist()
def get_presets() -> list[dict]:
	frappe.only_for("System Manager")
	rows = frappe.get_all(
		DOCTYPE, fields=["name", "mode", "swatches", "modified"], order_by="modified desc", limit=200
	)
	for row in rows:
		row["swatches"] = [s for s in (row.get("swatches") or "").split(",") if s]
	return rows


@frappe.whitelist()
def get_preset(name: str) -> dict:
	frappe.only_for("System Manager")
	doc = frappe.get_doc(DOCTYPE, name)
	return {"name": doc.name, "mode": doc.mode, "data": clean_data(doc.data)}

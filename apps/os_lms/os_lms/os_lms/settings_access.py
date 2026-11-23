"""Who may change which LMS Settings field.

LMS Settings is writable by System Manager and Moderator, and every Gestore holds Moderator.
The manager settings panel (SPA "Impostazioni gestore") only shows a subset of the tabs, so
the server refuses, for anyone who is not an administrator, any change outside the fields of
those tabs. The list names what is ALLOWED: a field added later by upstream is admin-only
until someone decides otherwise.

Design: docs/superpowers/specs/2026-11-18-impostazioni-gestore-design.md
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.model import no_value_fields, table_fields
from frappe.model.document import Document
from frappe.utils import cint, cstr, flt

SETTINGS_ADMIN_ROLES = frozenset({"System Manager"})

# LMS Settings fields behind the tabs of the manager settings panel.
GESTORE_EDITABLE_FIELDS = frozenset(
	{
		# Course Progress
		"lesson_dwell_time",
		"enforce_video_completion",
		"enforce_assignment_completion",
		"enforce_quiz_completion",
		# Welcome
		"welcome_notification_enabled",
		"welcome_notification_message",
		"welcome_video_enabled",
		"welcome_video_title",
		"welcome_video_subtitle",
		"welcome_video_file",
		# TrueSkills API
		"trueskills_api_enabled",
		"trueskills_api_endpoint",
		"trueskills_api_key",
	}
)

# Bookkeeping columns of a child row, never a setting.
_CHILD_META_FIELDS = frozenset(
	{"name", "idx", "parent", "parentfield", "parenttype", "owner", "creation", "modified", "modified_by", "docstatus"}
)


def is_settings_admin(user: str | None = None) -> bool:
	user = user or frappe.session.user
	return user == "Administrator" or bool(SETTINGS_ADMIN_ROLES & set(frappe.get_roles(user)))


def _normalize(fieldtype: str, value):
	# The same value arrives as 30, "30" or None depending on the client and on whether the
	# Single row exists: compare what it means, not how it was sent.
	if fieldtype in ("Check", "Int"):
		return cint(value)
	if fieldtype in ("Float", "Currency", "Percent"):
		return flt(value)
	return cstr(value)


def _table_rows(rows, child_doctype: str) -> list[dict]:
	fields = [
		df
		for df in frappe.get_meta(child_doctype).fields
		if df.fieldtype not in no_value_fields and df.fieldname not in _CHILD_META_FIELDS
	]
	return [{df.fieldname: _normalize(df.fieldtype, row.get(df.fieldname)) for df in fields} for row in rows or []]


def changed_fields(doc: Document) -> list[str]:
	"""Data and table fields whose value differs from the stored document."""
	before = doc.get_doc_before_save()
	if before is None:
		return []
	changed = []
	for df in doc.meta.fields:
		if df.fieldtype in table_fields:
			if _table_rows(before.get(df.fieldname), df.options) != _table_rows(doc.get(df.fieldname), df.options):
				changed.append(df.fieldname)
		elif df.fieldtype not in no_value_fields:
			if _normalize(df.fieldtype, before.get(df.fieldname)) != _normalize(df.fieldtype, doc.get(df.fieldname)):
				changed.append(df.fieldname)
	return changed


def validate_lms_settings_access(doc: Document, method: str | None = None) -> None:
	"""LMS Settings `validate` hook: non-administrators may only save the manager panel fields."""
	if is_settings_admin():
		return
	forbidden = [field for field in changed_fields(doc) if field not in GESTORE_EDITABLE_FIELDS]
	if forbidden:
		labels = [_(doc.meta.get_label(field)) for field in forbidden]
		frappe.throw(
			_("Only an administrator can change: {0}").format(", ".join(labels)),
			frappe.PermissionError,
		)


# Branding lives in Website Settings, which only Website Manager may write. Gestore must not
# get that role (it opens every website setting), so the Branding tab saves through here.
BRANDING_EDITOR_ROLES = frozenset({"Gestore"})


@frappe.whitelist(methods=["POST"])
def save_branding(app_name: str | None = None, banner_image: str | None = None, favicon: str | None = None) -> None:
	"""Save the Branding tab: brand name, logo (also used as app logo) and favicon."""
	if not (is_settings_admin() or BRANDING_EDITOR_ROLES & set(frappe.get_roles())):
		frappe.throw(_("Not permitted to change the branding."), frappe.PermissionError)
	settings = frappe.get_single("Website Settings")
	settings.app_name = app_name
	settings.banner_image = banner_image
	settings.app_logo = banner_image
	settings.favicon = favicon
	settings.save(ignore_permissions=True)

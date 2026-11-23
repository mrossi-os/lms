"""Who may change which LMS Settings field.

LMS Settings is writable by System Manager and Moderator, and every Gestore holds Moderator.
The manager settings panel (SPA "Impostazioni gestore") only shows a subset of the tabs, so
the server refuses, for anyone who is not an administrator, any change outside the fields of
those tabs. The list names what is ALLOWED: a field added later by upstream is admin-only
until someone decides otherwise.

Design: docs/superpowers/specs/2026-11-18-impostazioni-gestore-design.md
"""

from __future__ import annotations

import re

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
	if fieldtype in ("Link", "Dynamic Link"):
		# Link validation rewrites a value to the linked name's stored case.
		return cstr(value).lower()
	return cstr(value)


def _compared(df) -> bool:
	# fetch_from fields are re-copied by Frappe on every save (_validate_links), so a change
	# there comes from the linked document, not from whoever saves the settings.
	return df.fieldtype not in no_value_fields and not df.fetch_from


def _table_rows(rows, child_doctype: str) -> list[dict]:
	fields = [
		df
		for df in frappe.get_meta(child_doctype).fields
		if _compared(df) and df.fieldname not in _CHILD_META_FIELDS
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
		elif _compared(df):
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

# lms/www/_lms.html prints the favicon unescaped inside href="...": a new logo or favicon must be
# a plain path under the site's public files, with nothing that could close the attribute.
_SITE_FILE_URL = re.compile(r"^/files/[^\r\n\t\"'<>\\]+$")
_BRAND_NAME_FORBIDDEN = set('<>"')


def _validate_branding_url(value: str | None, current: str | None) -> None:
	if not value or value == current:
		return
	if not _SITE_FILE_URL.match(value) or ".." in value:
		frappe.throw(_("Logo and favicon must be files uploaded to the site."))


def _validate_brand_name(value: str | None) -> None:
	if value and _BRAND_NAME_FORBIDDEN & set(value):
		frappe.throw(_("The brand name cannot contain the characters < > or double quotes."))


@frappe.whitelist(methods=["POST"])
def save_branding(app_name: str | None = None, banner_image: str | None = None, favicon: str | None = None) -> None:
	"""Save the Branding tab: brand name, logo (also used as app logo) and favicon."""
	if not (is_settings_admin() or BRANDING_EDITOR_ROLES & set(frappe.get_roles())):
		frappe.throw(_("Not permitted to change the branding."), frappe.PermissionError)
	settings = frappe.get_single("Website Settings")
	_validate_brand_name(app_name)
	_validate_branding_url(banner_image, settings.banner_image)
	_validate_branding_url(favicon, settings.favicon)
	settings.app_name = app_name
	settings.banner_image = banner_image
	settings.app_logo = banner_image
	settings.favicon = favicon
	settings.save(ignore_permissions=True)


# Upstream endpoints that write LMS Settings rows directly, skipping the validate hook above.
# The rows they touch belong to admin-only tabs (Sidebar, Payments), so they need an
# administrator; every other call goes to the original unchanged.
ADMIN_ONLY_SETTINGS_ROW_DOCTYPES = frozenset({"LMS Sidebar Item", "Payment Country"})


def _require_settings_admin() -> None:
	if not is_settings_admin():
		frappe.throw(_("This section is only available to administrators."), frappe.PermissionError)


@frappe.whitelist()
def update_sidebar_item(webpage: str, icon: str):
	from lms.lms.api import update_sidebar_item as original

	_require_settings_admin()
	return original(webpage=webpage, icon=icon)


@frappe.whitelist()
def delete_sidebar_item(webpage: str):
	from lms.lms.api import delete_sidebar_item as original

	_require_settings_admin()
	return original(webpage=webpage)


@frappe.whitelist()
def delete_documents(doctype: str, documents: list):
	from lms.lms.api import delete_documents as original

	if doctype in ADMIN_ONLY_SETTINGS_ROW_DOCTYPES:
		_require_settings_admin()
	return original(doctype=doctype, documents=documents)

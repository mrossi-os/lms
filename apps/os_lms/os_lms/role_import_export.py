"""Export and import a Role together with its DocType permissions.

The standard Frappe Desk export of a Role only carries the Role record itself,
not the permission matrix (which Frappe stores separately in ``Custom DocPerm``
for customized doctypes, or in the standard ``DocPerm`` child table otherwise).

These helpers bundle the Role document and its effective per-doctype permission
rules into a single JSON payload and reconstruct both on import. The import is
additive and non-destructive: it uses Frappe's native permission API
(``add_permission`` + ``update_permission_property``), which runs
``setup_custom_perms`` first, so permissions of other roles on the same doctype
are preserved.
"""

import json

import frappe
from frappe import _
from frappe.permissions import add_permission, update_permission_property
from frappe.utils import cint

# Role doctype metadata fields that must never be carried across sites.
ROLE_EXCLUDED_FIELDS = {
	"name",
	"owner",
	"creation",
	"modified",
	"modified_by",
	"docstatus",
	"idx",
	"doctype",
}

EXPORT_VERSION = 1


def _perm_fields() -> list[str]:
	"""Return the permission flag fieldnames for the installed Frappe version.

	The set of permission columns (e.g. ``set_user_permissions``) varies across
	Frappe versions, so it is derived from the ``DocPerm`` meta at runtime rather
	than hard-coded. These are exactly the boolean permission flags plus
	``if_owner``, and each is a valid ``ptype`` for ``update_permission_property``.
	"""
	return [df.fieldname for df in frappe.get_meta("DocPerm").fields if df.fieldtype == "Check"]


@frappe.whitelist()
def export_role(role: str) -> dict:
	"""Return a JSON-serializable payload with the Role and its permissions."""
	frappe.only_for("System Manager")

	if not frappe.db.exists("Role", role):
		frappe.throw(_("Role {0} does not exist.").format(role))

	role_doc = frappe.get_doc("Role", role)
	role_data = {
		fieldname: value
		for fieldname, value in role_doc.as_dict().items()
		if fieldname not in ROLE_EXCLUDED_FIELDS
	}

	return {
		"version": EXPORT_VERSION,
		"exported_on": frappe.utils.now(),
		"role": role_data,
		"permissions": _get_role_permissions(role),
	}


def _get_role_permissions(role: str) -> list[dict]:
	"""Return the role's effective permission rules across all doctypes.

	For a doctype with any ``Custom DocPerm`` rows, those rows replace the
	standard ``DocPerm`` entirely (Frappe semantics), so the standard rows for
	such doctypes are skipped to avoid exporting shadowed permissions.
	"""
	perm_fields = _perm_fields()
	query_fields = ["parent", "permlevel", *perm_fields]

	# Doctypes that have been customized at the permission level at all.
	custom_parents = set(frappe.get_all("Custom DocPerm", distinct=True, pluck="parent"))

	permissions: list[dict] = []

	for perm in frappe.get_all("Custom DocPerm", filters={"role": role}, fields=query_fields):
		permissions.append(_serialize_perm(perm, perm_fields))

	for perm in frappe.get_all("DocPerm", filters={"role": role}, fields=query_fields):
		# A standard rule is inactive once the doctype has custom permissions.
		if perm.parent in custom_parents:
			continue
		permissions.append(_serialize_perm(perm, perm_fields))

	return permissions


def _serialize_perm(perm: dict, perm_fields: list[str]) -> dict:
	serialized = {"parent": perm.get("parent"), "permlevel": cint(perm.get("permlevel"))}
	for field in perm_fields:
		serialized[field] = cint(perm.get(field))
	return serialized


@frappe.whitelist()
def import_role(data: str) -> dict:
	"""Create/update a Role from a payload and apply its permissions.

	``data`` is the JSON string produced by :func:`export_role`.
	"""
	frappe.only_for("System Manager")

	payload = json.loads(data) if isinstance(data, str) else data
	role_data = payload.get("role") or {}
	role_name = role_data.get("role_name")
	if not role_name:
		frappe.throw(_("Invalid payload: missing role name."))

	_create_or_update_role(role_data)

	applied, skipped = _apply_permissions(role_name, payload.get("permissions") or [])

	frappe.clear_cache()

	return {
		"role": role_name,
		"applied_count": len(applied),
		"skipped_count": len(skipped),
		"skipped": skipped,
	}


def _create_or_update_role(role_data: dict) -> None:
	role_name = role_data["role_name"]
	valid_fields = {df.fieldname for df in frappe.get_meta("Role").fields}

	if frappe.db.exists("Role", role_name):
		doc = frappe.get_doc("Role", role_name)
	else:
		doc = frappe.new_doc("Role")
		doc.role_name = role_name

	for fieldname, value in role_data.items():
		# role_name is the identity field; skip it and any unknown/legacy fields.
		if fieldname == "role_name" or fieldname not in valid_fields:
			continue
		doc.set(fieldname, value)

	doc.save(ignore_permissions=True)


def _apply_permissions(role: str, permissions: list[dict]) -> tuple[list, list]:
	applied: list[dict] = []
	skipped: list[dict] = []
	perm_fields = _perm_fields()

	for perm in permissions:
		doctype = perm.get("parent")
		if not doctype or not frappe.db.exists("DocType", doctype):
			skipped.append({"doctype": doctype, "reason": "DocType not found"})
			continue

		permlevel = cint(perm.get("permlevel"))

		# Ensures Custom DocPerm exists for the doctype (copying standard perms so
		# other roles are preserved) and creates the row for this role/permlevel.
		add_permission(doctype, role, permlevel)

		for ptype in perm_fields:
			update_permission_property(
				doctype, role, permlevel, ptype, cint(perm.get(ptype)), validate=False
			)

		applied.append({"doctype": doctype, "permlevel": permlevel})

	return applied, skipped

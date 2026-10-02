"""Key management behind the SPA "Elite API" settings tab.

System Manager and Gestore only (the same roles the SPA gate
``canManageOsIntegrations`` lets through; Moderator is excluded). Every manager
sees and may revoke every key. The full key leaves the server once, in the
``create_key`` response; the secret hash never does.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import getdate

from os_lms.os_lms.elite_api import keys

MANAGER_ROLES = ("System Manager", "Gestore")
MAX_KEY_NAME_LENGTH = 140
KEY_FIELDS = [
	"name",
	"key_name",
	"enabled",
	"expires_on",
	"owner",
	"creation",
	"last_used_on",
	"last_used_ip",
	"revoked_on",
	"revoked_by",
]


def can_manage_elite_api() -> bool:
	roles = frappe.get_roles()
	return any(role in roles for role in MANAGER_ROLES)


def _ensure_can_manage():
	if not can_manage_elite_api():
		frappe.throw(_("You are not authorized to manage Elite API keys."), frappe.PermissionError)


@frappe.whitelist(methods=["GET"])
def list_keys() -> list[dict]:
	"""Every key: active ones first, then the most recent."""
	_ensure_can_manage()
	rows = frappe.get_all(keys.KEY_DOCTYPE, fields=KEY_FIELDS, order_by="creation desc")
	full_names = _full_names({user for row in rows for user in (row.owner, row.revoked_by) if user})
	serialized = [_serialize(row, full_names) for row in rows]
	# Stable sort: keeps the creation order inside each group.
	return sorted(serialized, key=lambda key: key["state"] != "active")


@frappe.whitelist(methods=["POST"])
def create_key(key_name: str, expires_on: str | None = None) -> dict:
	"""Create a key. The response carries the full key, which is never retrievable again."""
	_ensure_can_manage()
	key_name = (key_name or "").strip()
	if not key_name:
		frappe.throw(_("The API key name is required."))
	if len(key_name) > MAX_KEY_NAME_LENGTH:
		frappe.throw(_("The API key name cannot be longer than {0} characters.").format(MAX_KEY_NAME_LENGTH))

	doc, raw_key = keys.generate_key(key_name, getdate(expires_on) if expires_on else None)
	row = frappe.db.get_value(keys.KEY_DOCTYPE, doc.name, KEY_FIELDS, as_dict=True)
	return {**_serialize(row, _full_names({row.owner})), "key": raw_key}


@frappe.whitelist(methods=["POST"])
def revoke_key(key: str) -> dict:
	"""Revoke a key for good. Revoking an already revoked key changes nothing."""
	_ensure_can_manage()
	if not key or not frappe.db.exists(keys.KEY_DOCTYPE, key):
		frappe.throw(_("API key not found."), frappe.DoesNotExistError)

	keys.revoke_key(key)
	row = frappe.db.get_value(keys.KEY_DOCTYPE, key, KEY_FIELDS, as_dict=True)
	return _serialize(row, _full_names({row.owner, row.revoked_by}))


def _serialize(row, full_names: dict[str, str]) -> dict:
	if not row.enabled:
		state = "revoked"
	elif keys.is_expired(row.expires_on):
		state = "expired"
	else:
		state = "active"
	return {
		"name": row.name,
		"key_name": row.key_name,
		"key_preview": f"{keys.KEY_SCHEME}_{row.name}_",
		"state": state,
		"expires_on": row.expires_on,
		"created_on": row.creation,
		"created_by": full_names.get(row.owner, row.owner),
		"last_used_on": row.last_used_on,
		"last_used_ip": row.last_used_ip,
		"revoked_on": row.revoked_on,
		"revoked_by": full_names.get(row.revoked_by, row.revoked_by),
	}


def _full_names(users: set[str]) -> dict[str, str]:
	users = {user for user in users if user}
	if not users:
		return {}
	return dict(
		frappe.get_all(
			"User", filters={"name": ("in", list(users))}, fields=["name", "full_name"], as_list=True
		)
	)

"""Generation, verification and revocation of Elite API keys.

A key looks like ``elite_<prefix>_<secret>``:

- ``prefix`` (12 alphanumeric chars) is the name of the ``Elite API Key``
  document, so a presented key is resolved with a primary-key lookup;
- ``secret`` (``secrets.token_urlsafe(32)``, 43 chars) is shown once at creation
  and never stored: only its SHA-256 hash is. A 256-bit random secret cannot be
  brute-forced, so a plain (unsalted, fast) hash is enough here, unlike passwords.

Revoked and expired keys are final: a new key must be created instead.
"""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import string

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, now_datetime, today

KEY_DOCTYPE = "Elite API Key"
KEY_SCHEME = "elite"
PREFIX_LENGTH = 12
SECRET_BYTES = 32

# Role and technical user the API requests run as (see os_lms.setup.setup_elite_api_client).
CLIENT_ROLE = "Elite API Client"
CLIENT_USER = "elite-api@elite-api.invalid"

_PREFIX_ALPHABET = string.ascii_letters + string.digits
_KEY_PATTERN = re.compile(rf"^{KEY_SCHEME}_([A-Za-z0-9]{{{PREFIX_LENGTH}}})_([A-Za-z0-9_-]{{43}})$")


def new_key_prefix() -> str:
	"""Return a random prefix not used by any existing key."""
	while True:
		prefix = "".join(secrets.choice(_PREFIX_ALPHABET) for _ in range(PREFIX_LENGTH))
		if not frappe.db.exists(KEY_DOCTYPE, prefix):
			return prefix


def hash_secret(secret: str) -> str:
	return hashlib.sha256(secret.encode()).hexdigest()


def format_key(prefix: str, secret: str) -> str:
	return f"{KEY_SCHEME}_{prefix}_{secret}"


def parse_key(raw_key: str | None) -> tuple[str, str] | None:
	"""Split a presented key into ``(prefix, secret)``; ``None`` when malformed."""
	match = _KEY_PATTERN.match((raw_key or "").strip())
	if not match:
		return None
	return match.group(1), match.group(2)


def is_expired(expires_on) -> bool:
	"""A key stays valid through its whole expiry day."""
	return bool(expires_on) and getdate(expires_on) < getdate(today())


def generate_key(key_name: str, expires_on=None) -> tuple[Document, str]:
	"""Create a key and return ``(doc, full_key)``. ``full_key`` is never retrievable again."""
	if expires_on and is_expired(expires_on):
		frappe.throw(_("The expiry date cannot be in the past."))

	secret = secrets.token_urlsafe(SECRET_BYTES)
	doc = frappe.get_doc(
		{
			"doctype": KEY_DOCTYPE,
			"key_name": key_name,
			"expires_on": getdate(expires_on) if expires_on else None,
			"secret_hash": hash_secret(secret),
			"enabled": 1,
		}
	)
	doc.insert(ignore_permissions=True)
	return doc, format_key(doc.name, secret)


def resolve_key(raw_key: str | None) -> str | None:
	"""Return the name of the key when ``raw_key`` is usable, otherwise ``None``.

	Callers must not tell apart the failure reasons (unknown, wrong secret,
	revoked, expired): the response to the client is the same for all of them.
	"""
	parsed = parse_key(raw_key)
	if not parsed:
		return None
	prefix, secret = parsed

	row = frappe.db.get_value(
		KEY_DOCTYPE, prefix, ["name", "secret_hash", "enabled", "expires_on"], as_dict=True
	)
	if not row or not hmac.compare_digest(hash_secret(secret), row.secret_hash or ""):
		return None
	if not row.enabled or is_expired(row.expires_on):
		return None
	return row.name


def revoke_key(name: str) -> Document:
	"""Disable a key for good. Revoking an already revoked key is a no-op."""
	doc = frappe.get_doc(KEY_DOCTYPE, name)
	if doc.enabled:
		doc.enabled = 0
		doc.revoked_on = now_datetime()
		doc.revoked_by = frappe.session.user
		doc.save(ignore_permissions=True)
	return doc

# Copyright (c) 2026, ELITE and contributors
# For license information, please see license.txt

"""Content Security Policy violation reports (OWASP B3).

The frontend nginx (elite-deploy) sends the policy in Report-Only mode with
``report-uri /csp-report`` and forwards those reports here without cookies. Each
report becomes a counter on one ``OS CSP Violation`` row per directive, blocked
source, page and disposition: no user, IP, query string or code sample is kept.
The rows say which sources the policy still has to allow before it is switched
to enforcing.

Anyone can post here, so a report is normalised to a few short values, a request
carries at most ``MAX_REPORTS_PER_REQUEST`` of them and new kinds stop being
recorded past ``MAX_ROWS`` (existing ones keep counting).
"""

from __future__ import annotations

import hashlib
import json
import re
from urllib.parse import urlsplit

import frappe
from frappe.rate_limiter import rate_limit
from frappe.utils import now_datetime

DOCTYPE = "OS CSP Violation"
MAX_BODY_CHARS = 64 * 1024
MAX_REPORTS_PER_REQUEST = 20
MAX_ROWS = 500
MAX_VALUE_LENGTH = 140
# Keywords browsers put in place of a URL for what is not a fetched resource.
KEYWORD_SOURCES = frozenset(
	{"inline", "eval", "wasm-eval", "data", "blob", "self", "trusted-types-policy", "trusted-types-sink"}
)
NETWORK_SCHEMES = frozenset({"http", "https", "ws", "wss"})
DIRECTIVE_PATTERN = re.compile(r"^[a-z-]{1,40}$")


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(limit=120, seconds=60)
def collect() -> None:
	"""Endpoint behind nginx's ``/csp-report``."""
	record_reports(frappe.request.get_data(as_text=True))


def record_reports(body: str) -> int:
	"""Count the violations in a report body; return how many were counted."""
	counted = 0
	for raw in _parse(body)[:MAX_REPORTS_PER_REQUEST]:
		violation = _normalise(raw)
		if violation and _count(violation):
			counted += 1
	return counted


def _parse(body: str) -> list[dict]:
	"""Both formats: report-uri (``{"csp-report": {...}}``) and the Reporting API (a list)."""
	if not body or len(body) > MAX_BODY_CHARS:
		return []
	try:
		data = json.loads(body)
	except ValueError:
		return []
	if isinstance(data, dict) and isinstance(data.get("csp-report"), dict):
		return [data["csp-report"]]
	if isinstance(data, list):
		return [
			item["body"]
			for item in data
			if isinstance(item, dict) and item.get("type") == "csp-violation" and isinstance(item.get("body"), dict)
		]
	return []


def _normalise(raw: dict) -> dict | None:
	directive = str(
		raw.get("effective-directive") or raw.get("effectiveDirective") or raw.get("violated-directive") or ""
	)
	directive = directive.strip().split(" ")[0].lower()
	if not DIRECTIVE_PATTERN.match(directive):
		return None
	disposition = raw.get("disposition")
	return {
		"directive": directive,
		"blocked_source": _source(raw.get("blocked-uri") or raw.get("blockedURL")),
		"page": _page(raw.get("document-uri") or raw.get("documentURL")),
		"disposition": disposition if disposition in ("enforce", "report") else "report",
	}


def _source(value) -> str:
	"""Origin only for network URLs, the bare scheme for anything else."""
	value = str(value or "").strip()
	if not value:
		return "(none)"
	if value.lower() in KEYWORD_SOURCES:
		return value.lower()
	parts = urlsplit(value)
	scheme = parts.scheme.lower()
	if scheme in NETWORK_SCHEMES and parts.hostname:
		port = f":{parts.port}" if _safe_port(parts) else ""
		return f"{scheme}://{parts.hostname}{port}"[:MAX_VALUE_LENGTH]
	if re.match(r"^[a-z][a-z0-9+.-]{0,30}$", scheme):
		return f"{scheme}:"
	return "(other)"


def _safe_port(parts) -> int | None:
	try:
		return parts.port
	except ValueError:
		return None


def _page(value) -> str:
	"""Path only: the query string can carry personal data."""
	path = urlsplit(str(value or "").strip()).path or "/"
	return path[:MAX_VALUE_LENGTH]


def violation_key(violation: dict) -> str:
	"""Row name: the same kind of violation always lands on the same row."""
	return hashlib.sha1("\n".join(violation[f] for f in sorted(violation)).encode()).hexdigest()


def _count(violation: dict) -> bool:
	key = violation_key(violation)
	if frappe.db.exists(DOCTYPE, key):
		_increment(key)
		return True
	if frappe.db.count(DOCTYPE) >= MAX_ROWS:
		return False
	now = now_datetime()
	try:
		frappe.get_doc(
			{"doctype": DOCTYPE, **violation, "hits": 1, "first_seen": now, "last_seen": now}
		).insert(ignore_permissions=True, set_name=key)
	except frappe.DuplicateEntryError:
		# Another request recorded the same kind in the meantime.
		_increment(key)
	return True


def _increment(key: str) -> None:
	table = frappe.qb.DocType(DOCTYPE)
	(
		frappe.qb.update(table)
		.set(table.hits, table.hits + 1)
		.set(table.last_seen, now_datetime())
		.set(table.modified, now_datetime())
		.where(table.name == key)
	).run()

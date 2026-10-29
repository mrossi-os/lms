"""Per-student limits on AI simulation spend (OWASP A06, audit 2026-10-29 H-3/H-4).

Values live in the `LMSA Simulation Limits` single, editable by System Manager and
Gestore (not in LMSA Settings, which also holds the provider keys). Every limit is
at least 1: there is no "0 = unlimited".
"""
from __future__ import annotations

from dataclasses import dataclass

import frappe

LIMITS_DOCTYPE = "LMSA Simulation Limits"

# Field name -> value used until someone saves the single (and for a value below 1).
LIMIT_DEFAULTS = {
	"chat_messages_per_minute": 20,
	"max_message_chars": 4000,
	"max_messages_per_session": 60,
	"session_starts_per_hour": 30,
	"daily_sessions_per_user": 100,
	"voice_tokens_per_session": 3,
	"voice_tokens_per_hour": 10,
	"voice_max_session_seconds": 300,
}

# Rate-limit buckets shared by several endpoints (check_user_rate_limit actions).
CHAT_MESSAGE_ACTION = "simulations:chat_message"
SESSION_START_ACTION = "simulations:session_start"
VOICE_TOKEN_ACTION = "simulations:voice_token"


@dataclass(frozen=True)
class SimulationLimits:
	chat_messages_per_minute: int
	max_message_chars: int
	max_messages_per_session: int
	session_starts_per_hour: int
	daily_sessions_per_user: int
	voice_tokens_per_session: int
	voice_tokens_per_hour: int
	voice_max_session_seconds: int


def load_limits() -> SimulationLimits:
	"""Read the single, falling back to the default for a missing or invalid value."""
	values = {}
	for fieldname, default in LIMIT_DEFAULTS.items():
		raw = frappe.db.get_single_value(LIMITS_DOCTYPE, fieldname, cache=True)
		value = int(raw or 0)
		values[fieldname] = value if value >= 1 else default
	return SimulationLimits(**values)


def ensure_simulation_limits() -> None:
	"""after_migrate: save the single once with its defaults.

	The voice duration was `LMSA Settings.realtime_max_session_seconds`, which only
	a System Manager could change: a value set there is carried over. Idempotent,
	and an after_migrate step rather than a patch because the staging deploy marks
	patches as done without running them.
	"""
	if not frappe.db.exists("DocType", LIMITS_DOCTYPE):
		return
	# Raw query: frappe.db.exists() does not see tabSingles rows. Once saved, the
	# values are the Gestore's and a migrate must never reset them.
	if frappe.db.sql("SELECT 1 FROM `tabSingles` WHERE doctype = %s LIMIT 1", LIMITS_DOCTYPE):
		return
	doc = frappe.get_single(LIMITS_DOCTYPE)
	for fieldname, default in LIMIT_DEFAULTS.items():
		doc.set(fieldname, default)
	legacy = int(frappe.db.get_single_value("LMSA Settings", "realtime_max_session_seconds") or 0)
	if legacy >= 1:
		doc.voice_max_session_seconds = legacy
	doc.save(ignore_permissions=True)
	frappe.db.commit()


def check_message_length(text: str | None, limits: SimulationLimits | None = None) -> None:
	"""Refuse a student message longer than the configured limit."""
	limits = limits or load_limits()
	if text and len(text) > limits.max_message_chars:
		frappe.throw(
			frappe._("The message is too long: at most {0} characters.").format(limits.max_message_chars),
			frappe.ValidationError,
		)

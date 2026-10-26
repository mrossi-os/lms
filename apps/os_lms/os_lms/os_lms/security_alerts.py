# Copyright (c) 2026, ELITE and contributors
# For license information, please see license.txt

"""Email alerts on attack patterns: failed logins and refused Elite API keys.

Both are already recorded (Activity Log, Elite API Access Log); this module only
watches the counts. ``check_attack_thresholds`` runs every 5 minutes; past a
threshold it emails the Administrator user and every enabled Gestore, at most
once an hour per kind of alert.

Invalid Elite API keys past the per-IP limit are refused without a log row, so
the log cannot be flooded: ``elite_api.auth`` counts them in Redis through
``count_suppressed_attempt`` and the check writes them back as one aggregated
log row per IP.
"""

from __future__ import annotations

import json

import frappe
from frappe import _
from frappe.utils import add_to_date, now_datetime
from frappe.utils.data import escape_html

FAILED_LOGIN_LIMIT = 20
FAILED_LOGIN_WINDOW_MINUTES = 10
REFUSED_KEY_LIMIT = 20
REFUSED_KEY_WINDOW_MINUTES = 60
ALERT_COOLDOWN_SECONDS = 60 * 60
ALERT_ROLE = "Gestore"
# Elite API answers for an unusable key (401) and for an IP past the limit (429).
REFUSED_KEY_STATUS_CODES = (401, 429)
# Method written on the aggregated row of the refusals that were not logged one by one.
SUPPRESSED_METHOD = "too_many_failed_attempts"
SUPPRESSED_IPS_SET = "elite_api:suppressed_ips"
SUPPRESSED_COUNTER_TTL_SECONDS = 24 * 60 * 60
TOP_ROWS = 5


def count_suppressed_attempt(ip: str | None) -> None:
	"""Count an Elite API refusal that is not written to the access log."""
	ip = ip or ""
	counter = _suppressed_counter_key(ip)
	frappe.cache.incrby(counter, 1)
	frappe.cache.expire(counter, SUPPRESSED_COUNTER_TTL_SECONDS)
	frappe.cache.sadd(SUPPRESSED_IPS_SET, ip)


def check_attack_thresholds() -> None:
	"""Scheduler entry point (every 5 minutes)."""
	flush_suppressed_attempts()
	check_failed_logins()
	check_refused_keys()


def flush_suppressed_attempts() -> None:
	"""Write the Elite API refusals counted in Redis as one access log row per IP."""
	for member in frappe.cache.smembers(SUPPRESSED_IPS_SET) or []:
		ip = member.decode() if isinstance(member, bytes) else member
		# Leave the set first: an attempt counted from now on re-adds the IP, so
		# its counter is picked up by the next run instead of being orphaned.
		frappe.cache.srem(SUPPRESSED_IPS_SET, member)
		pipe = frappe.cache.pipeline()
		pipe.get(_suppressed_counter_key(ip))
		pipe.delete(_suppressed_counter_key(ip))
		count = int(pipe.execute()[0] or 0)
		if not count:
			continue
		frappe.get_doc(
			{
				"doctype": "Elite API Access Log",
				"method": SUPPRESSED_METHOD,
				"status_code": 429,
				"ip_address": ip or None,
				"request_params": json.dumps({"suppressed_attempts": count}),
			}
		).insert(ignore_permissions=True)
	frappe.db.commit()


def check_failed_logins() -> bool:
	since = add_to_date(now_datetime(), minutes=-FAILED_LOGIN_WINDOW_MINUTES)
	filters = {"operation": "Login", "status": "Failed", "creation": [">=", since]}
	total = frappe.db.count("Activity Log", filters)
	if total < FAILED_LOGIN_LIMIT:
		return False

	by_ip = _top("Activity Log", "ip_address", filters)
	by_user = _top("Activity Log", "user", filters)
	subject = _("Security alert: {0} failed logins in the last {1} minutes").format(
		total, FAILED_LOGIN_WINDOW_MINUTES
	)
	message = (
		_section(_("Top IP addresses"), by_ip)
		+ _section(_("Most targeted accounts"), by_user)
		+ "<p>{}</p>".format(escape_html(_("Details: Desk → Activity Log.")))
	)
	return _send_alert("failed_logins", subject, message)


def check_refused_keys() -> bool:
	since = add_to_date(now_datetime(), minutes=-REFUSED_KEY_WINDOW_MINUTES)
	filters = {"status_code": ["in", REFUSED_KEY_STATUS_CODES], "creation": [">=", since]}
	rows = frappe.get_all(
		"Elite API Access Log",
		filters=filters,
		fields=["ip_address", "method", "request_params"],
	)
	per_ip: dict[str, int] = {}
	for row in rows:
		attempts = _attempts(row)
		per_ip[row.ip_address or ""] = per_ip.get(row.ip_address or "", 0) + attempts
	total = sum(per_ip.values())
	if total < REFUSED_KEY_LIMIT:
		return False

	by_ip = sorted(per_ip.items(), key=lambda item: item[1], reverse=True)[:TOP_ROWS]
	subject = _("Security alert: {0} Elite API keys refused in the last {1} minutes").format(
		total, REFUSED_KEY_WINDOW_MINUTES
	)
	message = _section(_("Top IP addresses"), by_ip) + "<p>{}</p>".format(
		escape_html(_("Details: Desk → Elite API Access Log."))
	)
	return _send_alert("refused_keys", subject, message)


def alert_recipients() -> list[str]:
	"""The Administrator user's email plus every enabled Gestore's."""
	gestori = frappe.get_all(
		"Has Role", filters={"role": ALERT_ROLE, "parenttype": "User"}, pluck="parent"
	)
	users = [user for user in gestori if user not in ("Administrator", "Guest")]
	emails = [frappe.db.get_value("User", "Administrator", "email")]
	if users:
		emails += frappe.get_all(
			"User", filters={"name": ["in", users], "enabled": 1}, pluck="email"
		)
	return sorted({email for email in emails if email})


def _send_alert(kind: str, subject: str, message: str) -> bool:
	sent_key = f"security_alert:sent:{kind}"
	if frappe.cache.get_value(sent_key):
		return False
	recipients = alert_recipients()
	if not recipients:
		frappe.log_error(title="Security alert without recipients", message=subject)
		return False
	frappe.sendmail(recipients=recipients, subject=subject, message=message)
	frappe.cache.set_value(sent_key, 1, expires_in_sec=ALERT_COOLDOWN_SECONDS)
	return True


def _attempts(row) -> int:
	if row.method != SUPPRESSED_METHOD:
		return 1
	try:
		return int(json.loads(row.request_params or "{}").get("suppressed_attempts") or 1)
	except (ValueError, AttributeError):
		return 1


def _top(doctype: str, field: str, filters: dict) -> list[tuple[str, int]]:
	rows = frappe.get_all(
		doctype,
		filters=filters,
		fields=[field, {"COUNT": "*", "as": "attempts"}],
		group_by=field,
		order_by="attempts desc",
		limit=TOP_ROWS,
	)
	return [(row.get(field) or "", row.attempts) for row in rows]


def _section(title: str, rows: list[tuple[str, int]]) -> str:
	# IPs and usernames come from the attacker: always escaped.
	items = "".join(
		"<li>{}: {}</li>".format(escape_html(value or "?"), count) for value, count in rows
	)
	return "<p><b>{}</b></p><ul>{}</ul>".format(escape_html(title), items)


def _suppressed_counter_key(ip: str) -> str:
	return frappe.cache.make_key(f"elite_api:suppressed:{ip}")

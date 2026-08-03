# Copyright (c) 2026, ELITE and contributors
# For license information, please see license.txt

"""Per-user access tracking.

Frappe exposes an ``on_login`` hook for successful logins but none for failed
ones; both, however, are written to the Activity Log via
``add_authentication_log``. Hooking ``Activity Log.after_insert`` therefore lets
us capture successes AND failures in a single place, and — crucially —
independently of the 90-day Activity Log retention: log deletions never fire
``after_insert``, so the aggregates in ``LMSA User Access`` are never rolled
back and stay accurate for the whole lifetime of each account (from the moment
this tracking is deployed onward; see ``backfill_from_activity_log`` to seed
history best-effort from the logs still present).
"""

import frappe
from frappe.utils import get_datetime, getdate

DOCTYPE = "LMSA User Access"

# Guest never owns access stats; Administrator is a system account we skip so the
# doctype stays focused on real users (the student export filters it out anyway).
SKIP_USERS = {"Guest", "Administrator"}


def on_activity_log_insert(doc, method=None):
	"""``Activity Log.after_insert`` hook. Never raise: access tracking must not
	break a login or the authentication logging around it."""
	try:
		_handle(doc)
	except Exception:
		frappe.logger("os_lms_access", allow_site=True).exception("access tracking failed")


def _handle(doc):
	if doc.operation != "Login":
		return
	user = doc.user
	if not user or user in SKIP_USERS:
		return
	# Failed logins can carry an unknown / non-existent username; nothing to
	# attribute in that case.
	if not frappe.db.exists("User", user):
		return
	if doc.status == "Success":
		_record_success(user, doc.creation)
	elif doc.status == "Failed":
		_record_failure(user)


def _get_or_new(user: str):
	if frappe.db.exists(DOCTYPE, user):
		return frappe.get_doc(DOCTYPE, user)
	doc = frappe.new_doc(DOCTYPE)
	doc.user = user
	return doc


def _record_success(user: str, when):
	when = get_datetime(when)
	day = getdate(when)
	doc = _get_or_new(user)
	if not doc.first_login:
		doc.first_login = when
		doc.distinct_active_days = 1
		doc.last_active_date = day
	elif doc.last_active_date != day:
		# A login on a new calendar day: one more distinct active day.
		doc.distinct_active_days = (doc.distinct_active_days or 0) + 1
		doc.last_active_date = day
	doc.last_login = when
	doc.total_logins = (doc.total_logins or 0) + 1
	doc.save(ignore_permissions=True)


def _record_failure(user: str):
	doc = _get_or_new(user)
	doc.failed_logins = (doc.failed_logins or 0) + 1
	doc.save(ignore_permissions=True)


@frappe.whitelist()
def backfill_from_activity_log():
	"""Best-effort seed of ``LMSA User Access`` from the Activity Log records
	still present (Frappe clears them after ~90 days, so history older than that
	is unrecoverable — first_login and the counters are therefore a lower bound
	for long-standing users). Idempotent: it recomputes every user from scratch,
	so it is safe to re-run. Intended to be run once at deploy via
	``bench execute os_lms.os_lms.access_tracking.backfill_from_activity_log``.
	"""
	frappe.only_for("System Manager")

	rows = frappe.get_all(
		"Activity Log",
		filters={"operation": "Login"},
		fields=["user", "status", "creation"],
		order_by="creation asc",
	)

	stats = {}
	for r in rows:
		if not r.user or r.user in SKIP_USERS:
			continue
		s = stats.setdefault(
			r.user,
			{
				"first_login": None,
				"last_login": None,
				"total_logins": 0,
				"days": set(),
				"failed_logins": 0,
			},
		)
		if r.status == "Success":
			if s["first_login"] is None:
				s["first_login"] = r.creation
			s["last_login"] = r.creation
			s["total_logins"] += 1
			s["days"].add(getdate(r.creation))
		elif r.status == "Failed":
			s["failed_logins"] += 1

	seeded = 0
	for user, s in stats.items():
		if not frappe.db.exists("User", user):
			continue
		doc = _get_or_new(user)
		doc.first_login = s["first_login"]
		doc.last_login = s["last_login"]
		doc.total_logins = s["total_logins"]
		doc.distinct_active_days = len(s["days"])
		doc.failed_logins = s["failed_logins"]
		doc.last_active_date = max(s["days"]) if s["days"] else None
		doc.save(ignore_permissions=True)
		seeded += 1

	frappe.db.commit()
	return {"seeded": seeded}

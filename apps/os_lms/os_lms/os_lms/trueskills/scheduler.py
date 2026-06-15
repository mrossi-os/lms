"""Hourly reconciliation for TrueSkills Issue Log rows in non-terminal states.

``POST /issue`` is non-idempotent — on network timeout or 5xx the server may
have actually emitted the certificate but the client never received the
response. This scheduler queries ``GET /list`` (max 100 most recent) and
matches ``pending``/``needs_retry`` logs against the actual TrueSkills state,
transitioning them to ``issued`` when a confident match is found.

Matching strategy: IssuedCertificate (brief §3.4) carries no email field —
only ``fiscalIdHash`` with an unknown salt, ``name`` (template name at issue
time), and ``createdAt``. We match on ``(template name, createdAt window
around requested_at)``. Multiple matches in the window are ambiguous and the
log is left untouched for manual review.
"""

from datetime import timedelta

import frappe
from frappe.utils import add_to_date, get_datetime, now_datetime

from .client import TrueSkillsError
from .safelog import scrub
from .service import TrueSkillsService

ISSUE_LOG_DOCTYPE = "TrueSkills Issue Log"

# Don't reconcile rows newer than this — gives the original /issue worker
# enough time to finish without racing the scheduler.
RECONCILE_LOOKBACK_MINUTES = 5

# When matching IssuedCertificate.createdAt against log.requested_at, accept
# anything from a little before (clock skew) to half an hour after.
RECONCILE_WINDOW_BEFORE = timedelta(minutes=5)
RECONCILE_WINDOW_AFTER = timedelta(minutes=30)


def reconcile_pending() -> None:
	"""Hourly scheduled job. Safe to invoke manually for ad-hoc reconciliation."""
	cutoff = add_to_date(now_datetime(), minutes=-RECONCILE_LOOKBACK_MINUTES)
	logs = frappe.get_all(
		ISSUE_LOG_DOCTYPE,
		filters={
			"state": ["in", ["pending", "needs_retry"]],
			"requested_at": ["<", cutoff],
		},
		fields=["name", "template_id", "recipient_email", "requested_at"],
		order_by="requested_at asc",
	)
	if not logs:
		return

	service = TrueSkillsService()
	if not service.is_ready():
		return
	logger = service.logger

	try:
		issued = service.list_issued()
	except TrueSkillsError as exc:
		logger.warning(f"TrueSkills reconcile: GET /list failed: {exc}")
		return

	template_name_cache: dict[int, str | None] = {}

	for log_row in logs:
		template_id = log_row.get("template_id")
		if not template_id:
			continue
		template_name = _resolve_template_name(service, int(template_id), template_name_cache)
		if not template_name:
			continue

		requested_at = get_datetime(log_row["requested_at"])
		window_start = requested_at - RECONCILE_WINDOW_BEFORE
		window_end = requested_at + RECONCILE_WINDOW_AFTER

		candidates = [
			cert
			for cert in issued
			if cert.get("name") == template_name
			and _in_window(cert.get("createdAt"), window_start, window_end)
		]

		if not candidates:
			continue
		if len(candidates) > 1:
			logger.warning(
				f"TrueSkills reconcile: {log_row['name']} has {len(candidates)} "
				"candidate matches in the time window; left for manual review."
			)
			continue

		match = candidates[0]
		_mark_issued(log_row["name"], match, logger)


def _resolve_template_name(
	service: TrueSkillsService,
	template_id: int,
	cache: dict[int, str | None],
) -> str | None:
	if template_id in cache:
		return cache[template_id]
	try:
		template = service.get_template(template_id)
	except TrueSkillsError:
		cache[template_id] = None
		return None
	name = template.get("name") if isinstance(template, dict) else None
	cache[template_id] = name
	return name


def _in_window(created_at: str | None, start, end) -> bool:
	if not created_at:
		return False
	try:
		ts = get_datetime(created_at)
	except (TypeError, ValueError):
		return False
	return start <= ts <= end


def _mark_issued(log_name: str, match: dict, logger) -> None:
	try:
		doc = frappe.get_doc(ISSUE_LOG_DOCTYPE, log_name)
		doc.state = "issued"
		doc.trueskill_id = match.get("id")
		doc.trueskill_uid = match.get("uid")
		created_at = match.get("createdAt")
		doc.issued_at = get_datetime(created_at) if created_at else now_datetime()
		doc.error_message = None
		doc.save(ignore_permissions=True)
		frappe.db.commit()
		logger.info(
			f"TrueSkills reconcile: {log_name} matched id={match.get('id')} "
			f"uid={match.get('uid')}"
		)
	except Exception:
		frappe.log_error(
			title="TrueSkills reconcile_pending: save failed",
			message=scrub(frappe.get_traceback()),
		)

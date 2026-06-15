"""Orchestrator for emitting LMS certificates to the TrueSkills platform.

``enqueue_issue`` is wired to ``LMS Certificate.after_insert`` in ``hooks.py``.
It performs cheap eligibility checks synchronously and delegates the actual
HTTP call to a background worker via ``frappe.enqueue`` so the desk/user
request returns immediately.

``issue_certificate`` runs in the worker:

1. Resolves recipient data (``User.codice_fiscale``, ``email``, ``full_name``).
2. Creates a ``TrueSkills Issue Log`` in state ``pending`` BEFORE the API
   call — reconciliation safety net required by the brief §2.5 / §4 since
   ``POST /issue`` is not idempotent.
3. Transitions the log to ``issued`` / ``failed`` / ``needs_retry`` based
   on the outcome.
"""

import frappe
from frappe.utils import now_datetime

from .client import (
	TrueSkillsClientError,
	TrueSkillsError,
	TrueSkillsNetworkError,
	TrueSkillsServerError,
)
from .safelog import get_logger, scrub
from .service import TrueSkillsService

ISSUE_LOG_DOCTYPE = "TrueSkills Issue Log"
ISSUE_JOB_QUEUE = "long"
ISSUE_JOB_TIMEOUT = 600  # seconds


def enqueue_issue(doc, method: str | None = None) -> None:
	"""Hook for ``LMS Certificate.after_insert``.

	Performs eligibility checks synchronously (course has TrueSkills flag,
	template id, integration enabled). If eligible, enqueues the actual
	issuance to a background worker so the certificate creation request
	returns immediately.

	Skips silently when not applicable — never raises into the calling
	``after_insert`` chain.
	"""
	try:
		if not doc.course:
			# Batch-only certificates are out of scope for Fase 2.
			return

		course_flags = frappe.db.get_value(
			"LMS Course",
			doc.course,
			["trueskills_certificate_enabled", "trueskills_template_id"],
			as_dict=True,
		)
		if not course_flags or not course_flags.get("trueskills_certificate_enabled"):
			return
		if not course_flags.get("trueskills_template_id"):
			get_logger().warning(
				f"LMS Certificate {doc.name}: course {doc.course} has TrueSkills enabled "
				"but no trueskills_template_id; skipping emission."
			)
			return

		if not TrueSkillsService().is_ready():
			return

		frappe.enqueue(
			"os_lms.os_lms.trueskills.emission.issue_certificate",
			queue=ISSUE_JOB_QUEUE,
			timeout=ISSUE_JOB_TIMEOUT,
			enqueue_after_commit=True,
			lms_certificate=doc.name,
		)
	except Exception:
		# Never let TrueSkills problems break LMS Certificate creation.
		frappe.log_error(
			title="TrueSkills enqueue_issue failed",
			message=scrub(frappe.get_traceback()),
		)


def issue_certificate(lms_certificate: str) -> None:
	"""Worker entrypoint — emit a single LMS Certificate to TrueSkills.

	Idempotency safety net: the ``TrueSkills Issue Log`` row is committed
	BEFORE the API call so a crash mid-request can be reconciled later.
	"""
	cert = frappe.get_doc("LMS Certificate", lms_certificate)

	course = frappe.db.get_value(
		"LMS Course",
		cert.course,
		["trueskills_certificate_enabled", "trueskills_template_id"],
		as_dict=True,
	)
	if not course or not course.get("trueskills_certificate_enabled"):
		return
	template_id_raw = course.get("trueskills_template_id")
	if not template_id_raw:
		return

	try:
		template_id = int(template_id_raw)
	except (TypeError, ValueError):
		_create_failed_log(
			cert.name,
			template_id=None,
			error="invalid_template_id",
			recipient_email=None,
			recipient_name=None,
		)
		return

	user = (
		frappe.db.get_value(
			"User",
			cert.member,
			["email", "full_name", "codice_fiscale"],
			as_dict=True,
		)
		or {}
	)
	email = user.get("email")
	full_name = user.get("full_name")
	fiscal_id = (user.get("codice_fiscale") or "").strip()

	if not email or not full_name:
		_create_failed_log(
			cert.name,
			template_id=template_id,
			error="invalid_recipient",
			recipient_email=email,
			recipient_name=full_name,
		)
		return

	if not fiscal_id:
		_create_failed_log(
			cert.name,
			template_id=template_id,
			error="missing_fiscal_id",
			recipient_email=email,
			recipient_name=full_name,
		)
		return

	log = frappe.get_doc(
		{
			"doctype": ISSUE_LOG_DOCTYPE,
			"lms_certificate": cert.name,
			"template_id": template_id,
			"recipient_email": email,
			"recipient_name": full_name,
			"state": "pending",
			"requested_at": now_datetime(),
			"attempts": _next_attempt_number(cert.name),
		}
	)
	log.insert(ignore_permissions=True)
	frappe.db.commit()

	try:
		response = TrueSkillsService().issue_certificate(
			template_id=template_id,
			fiscal_id=fiscal_id,
			email=email,
			name=full_name,
		)
	except TrueSkillsClientError as exc:
		log.state = "failed"
		log.error_message = exc.message_code or str(exc)
		log.save(ignore_permissions=True)
		frappe.db.commit()
		return
	except (TrueSkillsServerError, TrueSkillsNetworkError) as exc:
		log.state = "needs_retry"
		log.error_message = getattr(exc, "message_code", None) or str(exc)
		log.save(ignore_permissions=True)
		frappe.db.commit()
		return
	except TrueSkillsError as exc:
		log.state = "failed"
		log.error_message = str(exc)
		log.save(ignore_permissions=True)
		frappe.db.commit()
		return

	issued_id = response.get("id") if isinstance(response, dict) else None
	issued_uid = response.get("uid") if isinstance(response, dict) else None
	log.state = "issued"
	log.trueskill_id = issued_id
	log.trueskill_uid = issued_uid
	log.issued_at = now_datetime()
	log.error_message = None
	log.save(ignore_permissions=True)
	frappe.db.commit()


def _next_attempt_number(lms_certificate: str) -> int:
	"""Return ``max(attempts) + 1`` across existing logs for this certificate."""
	current = frappe.db.sql(
		"select coalesce(max(attempts), 0) from `tabTrueSkills Issue Log` "
		"where lms_certificate = %s",
		(lms_certificate,),
	)
	max_attempts = current[0][0] if current and current[0] else 0
	return int(max_attempts or 0) + 1


def _create_failed_log(
	lms_certificate: str,
	*,
	template_id: int | None,
	error: str,
	recipient_email: str | None,
	recipient_name: str | None,
) -> None:
	"""Persist a ``failed`` log when emission cannot even be attempted."""
	doc = frappe.get_doc(
		{
			"doctype": ISSUE_LOG_DOCTYPE,
			"lms_certificate": lms_certificate,
			"template_id": template_id,
			"recipient_email": recipient_email,
			"recipient_name": recipient_name,
			"state": "failed",
			"requested_at": now_datetime(),
			"attempts": 0,
			"error_message": error,
		}
	)
	doc.insert(ignore_permissions=True)
	frappe.db.commit()

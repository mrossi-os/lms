import frappe
from frappe import _
from frappe.utils import nowdate

from .certificate_image import build_certificate_png_data_uri
from .client import TrueSkillsClientError, TrueSkillsError
from .service import TrueSkillsService


def _require_admin() -> None:
	roles = set(frappe.get_roles(frappe.session.user))
	if not roles & {"System Manager", "Moderator", "Course Creator"}:
		frappe.throw("Not permitted", frappe.PermissionError)


def _is_admin() -> bool:
	roles = set(frappe.get_roles(frappe.session.user))
	return bool(roles & {"System Manager", "Moderator", "Course Creator"})


def _require_certificate_owner_or_admin(trueskill_id: int) -> None:
	"""Allow admin OR the ``LMS Certificate.member`` owner of this trueskill id."""
	if _is_admin():
		return
	log = frappe.db.get_value(
		"TrueSkills Issue Log",
		{"trueskill_id": int(trueskill_id), "state": "issued"},
		"lms_certificate",
	)
	if not log:
		frappe.throw("Not permitted", frappe.PermissionError)
	owner = frappe.db.get_value("LMS Certificate", log, "member")
	if owner != frappe.session.user:
		frappe.throw("Not permitted", frappe.PermissionError)


def _error_payload(exc: TrueSkillsError) -> dict:
	payload: dict = {"ok": False, "error": str(exc)}
	code = getattr(exc, "message_code", None)
	if code:
		payload["code"] = code
	status = getattr(exc, "status", None)
	if status:
		payload["status"] = status
	return payload


@frappe.whitelist()
def get_status() -> dict:
	"""Return whether the TrueSkills integration is configured and ready."""
	_require_admin()
	settings = TrueSkillsService().settings
	return {
		"enabled": settings.enabled,
		"endpoint": settings.endpoint,
		"has_api_key": bool(settings.api_key),
		"ready": settings.is_ready(),
	}


@frappe.whitelist()
def health() -> dict:
	"""Smoke-test the TrueSkills API and return its health payload."""
	_require_admin()
	try:
		response = TrueSkillsService().health()
	except TrueSkillsError as exc:
		return _error_payload(exc)
	return {"ok": True, "response": response}


@frappe.whitelist()
def test_connection() -> dict:
	"""Issue a health request against the configured TrueSkills endpoint."""
	_require_admin()
	service = TrueSkillsService()
	url = (service.settings.endpoint or "").rstrip("/") or None
	try:
		return service.test_connection()
	except TrueSkillsError as exc:
		payload = _error_payload(exc)
		payload["url"] = url
		return payload


@frappe.whitelist()
def list_templates() -> dict:
	"""Return the list of certificate templates available on TrueSkills."""
	_require_admin()
	try:
		templates = TrueSkillsService().list_templates()
	except TrueSkillsError as exc:
		payload = _error_payload(exc)
		payload["templates"] = []
		return payload
	return {"ok": True, "templates": templates}


@frappe.whitelist()
def get_template(template_id: int) -> dict:
	"""Fetch a single TrueSkills template by id (with in-process cache)."""
	_require_admin()
	try:
		template = TrueSkillsService().get_template(int(template_id))
	except TrueSkillsError as exc:
		return _error_payload(exc)
	return {"ok": True, "template": template}


@frappe.whitelist()
def render_certificate_image(course: str) -> dict:
	"""Render the course completion certificate to a PNG data-URI.

	Lets the template modal reuse the certificate design as the Openbadge image.
	Returns ``{ok, image_base64, filename}`` where ``image_base64`` is a
	``data:image/png;base64,...`` string.
	"""
	_require_admin()
	if not course:
		return {"ok": False, "error": "Course is required."}
	try:
		data_uri = build_certificate_png_data_uri(course)
	except TrueSkillsError as exc:
		return {"ok": False, "error": str(exc)}
	return {"ok": True, "image_base64": data_uri, "filename": "certificate.png"}


@frappe.whitelist()
def create_template(payload: dict) -> dict:
	"""Create a new certificate template via the TrueSkills API."""
	_require_admin()
	if not isinstance(payload, dict):
		try:
			payload = frappe.parse_json(payload)
		except Exception:
			return {"ok": False, "error": "Invalid payload"}
	if not payload.get("name") or not payload.get("type"):
		return {"ok": False, "error": "Fields 'name' and 'type' are required."}
	if payload.get("type") == "Openbadge":
		badge = payload.get("badge") or {}
		if not badge.get("url"):
			return {"ok": False, "error": "Openbadge templates require a badge URL."}
	try:
		template = TrueSkillsService().create_template(payload)
	except TrueSkillsError as exc:
		return _error_payload(exc)
	return {"ok": True, "template": template}


@frappe.whitelist()
def list_issued() -> dict:
	"""Return up to 100 most recent issued certificates."""
	_require_admin()
	try:
		certificates = TrueSkillsService().list_issued()
	except TrueSkillsError as exc:
		payload = _error_payload(exc)
		payload["certificates"] = []
		return payload
	return {"ok": True, "certificates": certificates}


@frappe.whitelist()
def get_issued(certificate_id: int) -> dict:
	"""Fetch a single issued certificate by numeric id."""
	_require_admin()
	try:
		certificate = TrueSkillsService().get_issued(int(certificate_id))
	except TrueSkillsError as exc:
		return _error_payload(exc)
	return {"ok": True, "certificate": certificate}


@frappe.whitelist()
def verify(uid: str, fiscal_id: str | None = None) -> dict:
	"""Verify a certificate by UUID. Always ok=True; inspect ``response.valid``."""
	_require_admin()
	try:
		response = TrueSkillsService().verify(uid, fiscal_id)
	except TrueSkillsError as exc:
		return _error_payload(exc)
	return {"ok": True, "response": response}


def _latest_issue_status(lms_certificate: str) -> dict:
	"""Latest TrueSkills issuance status for a single LMS Certificate.

	Returns ``{ state, issued, trueskill_id, trueskill_uid, error }``. ``state``
	is ``None`` when no Issue Log exists yet (emission was enqueued but the
	background worker has not created the ``pending`` row).
	"""
	logs = frappe.get_all(
		"TrueSkills Issue Log",
		filters={"lms_certificate": lms_certificate},
		fields=["state", "trueskill_id", "trueskill_uid", "error_message"],
		order_by="modified desc",
		limit=1,
	)
	if not logs:
		return {
			"state": None,
			"issued": False,
			"trueskill_id": None,
			"trueskill_uid": None,
			"error": None,
		}
	log = logs[0]
	return {
		"state": log["state"],
		"issued": log["state"] == "issued",
		"trueskill_id": log["trueskill_id"],
		"trueskill_uid": log["trueskill_uid"],
		"error": log["error_message"],
	}


def _ensure_trueskill_certificate(course: str) -> str:
	"""Return the session user's ``LMS Certificate`` for a TrueSkills course, creating it.

	The TrueSkills switch is mutually exclusive with the internal completion
	certificate, so ``enable_certification`` is off and the upstream
	``create_certificate`` (which requires it) cannot be used. This mirrors the
	eligibility (enrolled + course completed) without that gate. Inserting the
	certificate fires ``after_insert`` → the async TrueSkills emission; the
	internal completion email is suppressed by ``CustomLMSCertificate``.
	"""
	from lms.lms.doctype.lms_certificate.lms_certificate import (
		get_default_certificate_template,
		is_certified,
	)

	existing = is_certified(course)
	if existing:
		return existing

	enrollment = frappe.db.get_value(
		"LMS Enrollment",
		{"course": course, "member": frappe.session.user},
		["name", "progress"],
		as_dict=True,
	)
	if not enrollment:
		frappe.throw(_("You are not enrolled in this course."))
	if (enrollment.get("progress") or 0) < 100:
		frappe.throw(_("You have not completed the course yet."))

	# ``template`` is mandatory on LMS Certificate. It is never used to render an
	# internal PDF for TrueSkills courses (the UI opens the badge and the email is
	# suppressed), but the field must be populated — use the default Print Format,
	# which is also the design the openbadge image is generated from.
	template = get_default_certificate_template()
	if not template:
		frappe.throw(
			_("No certificate Print Format is configured. Create one for LMS Certificate.")
		)

	cert = frappe.get_doc(
		{
			"doctype": "LMS Certificate",
			"member": frappe.session.user,
			"course": course,
			"issue_date": nowdate(),
			"template": template,
		}
	)
	cert.insert(ignore_permissions=True)
	return cert.name


@frappe.whitelist()
def get_course_certificate(course: str) -> dict:
	"""Resolve the completion certificate for a course and how it should open.

	Ensures the ``LMS Certificate`` exists (creating it — which triggers the
	async TrueSkills emission — when the learner qualifies), then reports:

	- ``mode == "pdf"``  → open the internal Print Format PDF (default behaviour).
	- ``mode == "trueskill"`` → the course issues via TrueSkills; the SPA must
	  show the openbadge image instead of the internal PDF. The issuance
	  ``state`` / ``trueskill_id`` let the client poll until the badge is ready.

	The two are mutually exclusive per course (see ``CoursePublishSettings``).
	Used by the "Get Certificate" / "View Certificate" flows.
	"""
	if not course:
		frappe.throw(_("Course is required."))

	flags = (
		frappe.db.get_value(
			"LMS Course",
			course,
			["trueskills_certificate_enabled", "trueskills_template_id"],
			as_dict=True,
		)
		or {}
	)

	# Internal completion certificate: defer to the upstream creator, which gates
	# on ``enable_certification`` + course completion.
	if not flags.get("trueskills_certificate_enabled"):
		from lms.lms.doctype.lms_certificate.lms_certificate import create_certificate

		cert = create_certificate(course)
		# create_certificate returns a dict when already certified, else the Document.
		if isinstance(cert, dict):
			cert_name = cert.get("name")
			template = cert.get("template")
		else:
			cert_name = cert.name
			template = cert.template
		return {"mode": "pdf", "lms_certificate": cert_name, "template": template}

	# TrueSkills is the issuer — create the backing certificate ourselves.
	cert_name = _ensure_trueskill_certificate(course)

	if not TrueSkillsService().is_ready():
		# TrueSkills is the configured issuer but the integration is off/misconfigured:
		# surface an error rather than silently falling back to the internal PDF.
		return {
			"mode": "trueskill",
			"lms_certificate": cert_name,
			"template": None,
			"state": "unavailable",
			"issued": False,
			"trueskill_id": None,
			"trueskill_uid": None,
			"error": "service_unavailable",
		}

	status = _latest_issue_status(cert_name)
	return {
		"mode": "trueskill",
		"lms_certificate": cert_name,
		"template": None,
		**status,
	}


@frappe.whitelist()
def get_issue_status(lms_certificates: list[str] | str) -> dict:
	"""Return the latest TrueSkills issuance status for the given LMS Certificates.

	Response shape: ``{ <lms_certificate>: { state, issued, trueskill_id, trueskill_uid, error } }``.
	Only certificates owned by the session user (or all, for admins) are reported.
	Used by the student profile page to show the "Download Openbadge" button and
	to poll while a badge is being issued.
	"""
	if isinstance(lms_certificates, str):
		try:
			lms_certificates = frappe.parse_json(lms_certificates)
		except Exception:
			lms_certificates = [lms_certificates]
	if not isinstance(lms_certificates, list) or not lms_certificates:
		return {}

	if not _is_admin():
		owned = frappe.get_all(
			"LMS Certificate",
			filters={"name": ["in", lms_certificates], "member": frappe.session.user},
			pluck="name",
		)
		lms_certificates = list(owned)
	if not lms_certificates:
		return {}

	logs = frappe.get_all(
		"TrueSkills Issue Log",
		filters={"lms_certificate": ["in", lms_certificates]},
		fields=["lms_certificate", "state", "trueskill_id", "trueskill_uid", "error_message"],
		order_by="modified desc",
	)
	result: dict[str, dict] = {}
	for log in logs:
		cert_name = log["lms_certificate"]
		if cert_name in result:
			continue
		result[cert_name] = {
			"state": log["state"],
			"issued": log["state"] == "issued",
			"trueskill_id": log["trueskill_id"],
			"trueskill_uid": log["trueskill_uid"],
			"error": log["error_message"],
		}
	return result


@frappe.whitelist()
def retry_emission(issue_log: str) -> dict:
	"""Manually retry the emission of a ``failed``/``needs_retry`` Issue Log.

	A NEW Issue Log is created for the same ``LMS Certificate``; the source
	log is left untouched as audit (per brief §2.5 — POST /issue is not
	idempotent). Refused if an ``issued`` log already exists for the cert.
	"""
	_require_admin()
	try:
		source = frappe.get_doc("TrueSkills Issue Log", issue_log)
	except frappe.DoesNotExistError:
		return {"ok": False, "error": "Issue Log not found."}

	if source.state not in ("failed", "needs_retry"):
		return {
			"ok": False,
			"error": "Retry is allowed only for 'failed' or 'needs_retry' logs.",
		}

	already_issued = frappe.db.exists(
		"TrueSkills Issue Log",
		{"lms_certificate": source.lms_certificate, "state": "issued"},
	)
	if already_issued:
		return {
			"ok": False,
			"error": f"Certificate already issued in log {already_issued}.",
		}

	frappe.enqueue(
		"os_lms.os_lms.trueskills.emission.issue_certificate",
		queue="long",
		timeout=600,
		lms_certificate=source.lms_certificate,
	)
	return {"ok": True}


@frappe.whitelist()
def download(certificate_id: int, file_format: str) -> None:
	"""Stream the binary download for an issued certificate.

	``file_format`` must be ``"image"`` (PNG) or ``"jsonp"`` (JSON-LD).
	The response is delivered via ``frappe.local.response`` as a file
	download — this function returns ``None`` to the caller.

	Visibility: ``LMS Certificate.member`` may download their own badge;
	admins may download any. Openbadge artifacts are designed to be public
	(brief §2.9) so exposing them to the certificate owner is safe.
	"""
	_require_certificate_owner_or_admin(int(certificate_id))
	try:
		_, content = TrueSkillsService().download(int(certificate_id), file_format)
	except TrueSkillsClientError as exc:
		frappe.throw(str(exc), frappe.ValidationError)
	except TrueSkillsError as exc:
		frappe.throw(str(exc))

	extension = "png" if file_format == "image" else "jsonld"
	frappe.local.response.filename = f"trueskill_{int(certificate_id)}.{extension}"
	frappe.local.response.filecontent = content
	frappe.local.response.type = "download"

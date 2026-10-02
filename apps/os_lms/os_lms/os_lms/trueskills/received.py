"""Certificates a user received straight from the TrueSkills platform.

TrueSkills can issue certificates in bulk to the email addresses of Elite users
without Elite asking for them. Those users have no TrueSkills account: the
certificate hangs off a placeholder user that only carries the email, so the
profile "Certificates" tab finds them by email (``POST /search-by-email``).

Rules enforced here:

- The email is always resolved on the server from the profile ``username`` and
  only ever travels in the TrueSkills request body — never in a URL, a log, or a
  response to the browser. The API key never leaves the server.
- Only the profile owner, System Manager (Administrator) and Gestore may read a
  profile's TrueSkills certificates.
- The TrueSkills key can download *any* certificate of the organization from its
  id, so a download is allowed only for an id the search returns for that
  profile's email, checked again on every download (no cached list).
- Certificates Elite itself emitted are already shown as regular certificates
  (``TrueSkills Issue Log``); they are left out of the list to avoid duplicates.
"""

import frappe
from frappe import _

from .client import TrueSkillsClientError, TrueSkillsError
from .safelog import scrub
from .service import TrueSkillsService

VIEWER_ROLES = ("System Manager", "Gestore")
DOWNLOAD_FORMATS = {"image": ("image/png", "png"), "jsonp": ("application/ld+json", "jsonld")}

# Interactive calls: fail fast instead of freezing the profile for ~50 s.
INTERACTIVE_TIMEOUT = 8
INTERACTIVE_ATTEMPTS = 2

# Errors only a developer can fix are written to the Error Log, at most once per window.
ERROR_LOG_WINDOW_SECONDS = 600
ERROR_LOG_CACHE_KEY = "oslms_trueskills_received_error:{status}:{code}"


class ReceivedCertificateFileError(frappe.ValidationError):
	"""The requested file cannot be produced or is not offered for this certificate."""

	http_status_code = 400


class TrueSkillsUnavailableError(frappe.ValidationError):
	"""TrueSkills cannot be reached or refused the request; the user can only retry later."""

	http_status_code = 503


def _refuse(exc_class: type[Exception], message: str):
	# ``from None``: the response must not carry the chain of the TrueSkills error.
	raise exc_class(message) from None


def _unavailable():
	message = _("Certificates are temporarily unavailable. Please try again later.")
	_refuse(TrueSkillsUnavailableError, message)


def _profile_email(username: str) -> str:
	"""Email of the profile ``username`` if the session user may see its certificates."""
	username = (username or "").strip()
	if not username:
		# An empty value must never reach the query: users without a username would match.
		_refuse(frappe.ValidationError, _("Username is required."))

	user = frappe.db.get_value("User", {"username": username}, ["name", "email"], as_dict=True)
	if not user:
		_refuse(frappe.DoesNotExistError, _("User {0} not found").format(username))

	is_owner = user.name == frappe.session.user
	if not is_owner and not set(VIEWER_ROLES).intersection(frappe.get_roles()):
		_refuse(frappe.PermissionError, _("You are not allowed to see the certificates of this user."))

	email = (user.email or "").strip()
	if not email:
		_refuse(frappe.DoesNotExistError, _("User {0} not found").format(username))
	return email


def _report_failure(exc: TrueSkillsError) -> None:
	"""Keep a trace of failures a retry cannot fix (revoked key, malformed request, bad endpoint).

	Transient failures (5xx, timeouts) are already in the ``trueskills`` log written
	by the client. The Error Log gets the status and code only — never the email.
	"""
	if isinstance(exc, TrueSkillsClientError):
		status, code = exc.status, exc.message_code
	elif type(exc) is TrueSkillsError:
		status, code = None, "unexpected_response"
	else:
		return

	cache_key = ERROR_LOG_CACHE_KEY.format(status=status, code=code)
	if frappe.cache().get_value(cache_key):
		return
	frappe.cache().set_value(cache_key, 1, expires_in_sec=ERROR_LOG_WINDOW_SECONDS)
	frappe.log_error(title="TrueSkills received certificates: request failed", message=scrub(str(exc)))


def _search(service: TrueSkillsService, email: str) -> list[dict]:
	try:
		return service.search_certificates_by_email(email, max_attempts=INTERACTIVE_ATTEMPTS)
	except TrueSkillsError as exc:
		_report_failure(exc)
		_unavailable()


def _issued_by_elite(ids: list[int]) -> set[int]:
	"""Ids that Elite itself emitted (any state): those are shown as regular certificates."""
	if not ids:
		return set()
	return set(
		frappe.get_all("TrueSkills Issue Log", filters={"trueskill_id": ["in", ids]}, pluck="trueskill_id")
	)


def _valid_id(row: dict) -> bool:
	return isinstance(row.get("id"), int) and not isinstance(row.get("id"), bool)


# POST as well: the SPA's ``call()`` always posts. The download stays GET-only (a plain fetch).
@frappe.whitelist(methods=["GET", "POST"])
def list_received_certificates(username: str) -> dict:
	"""Certificates TrueSkills issued to the email of ``username``, not emitted by Elite.

	Returns ``{status, certificates}`` where ``status`` is ``ok``, ``disabled`` (the
	integration is off: the profile stays as it was) or ``unavailable`` (TrueSkills
	failed; the SPA shows a non-blocking notice and the rest of the tab still works).
	Each certificate lists only the ``formats`` that can be downloaded; an empty list
	means a plain certificate with nothing to download.
	"""
	email = _profile_email(username)

	service = TrueSkillsService(timeout=INTERACTIVE_TIMEOUT)
	if not service.is_ready():
		return {"status": "disabled", "certificates": []}

	try:
		found = service.search_certificates_by_email(email, max_attempts=INTERACTIVE_ATTEMPTS)
	except TrueSkillsError as exc:
		_report_failure(exc)
		return {"status": "unavailable", "certificates": []}

	rows = [row for row in found if _valid_id(row)]
	elite_ids = _issued_by_elite([row["id"] for row in rows])
	return {
		"status": "ok",
		"certificates": [
			{
				"id": row["id"],
				"name": row.get("name") or "",
				"type": row.get("type") or "",
				"created_at": row.get("createdAt"),
				"formats": [fmt for fmt in (row.get("formats") or []) if fmt in DOWNLOAD_FORMATS],
			}
			for row in rows
			if row["id"] not in elite_ids
		],
	}


@frappe.whitelist(methods=["GET"])
def download_received_certificate(username: str, certificate_id: int, file_format: str) -> None:
	"""Forward the PNG (``image``) or JSON-LD (``jsonp``) of a certificate of ``username``.

	The id must be one the search returns for that profile's email, otherwise 404.
	The file is delivered through ``frappe.local.response`` (a download); the
	function itself returns ``None``.
	"""
	if file_format not in DOWNLOAD_FORMATS:
		_refuse(ReceivedCertificateFileError, _("This file format is not available."))
	email = _profile_email(username)

	service = TrueSkillsService(timeout=INTERACTIVE_TIMEOUT)
	if not service.is_ready():
		_unavailable()

	owned = next((row for row in _search(service, email) if row.get("id") == certificate_id), None)
	if owned is None:
		_refuse(frappe.DoesNotExistError, _("Certificate not found."))
	if file_format not in (owned.get("formats") or []):
		_refuse(ReceivedCertificateFileError, _("This file format is not available."))

	try:
		content = service.download(certificate_id, file_format, max_attempts=INTERACTIVE_ATTEMPTS)[1]
	except TrueSkillsClientError as exc:
		if exc.message_code == "certificate_not_found":
			_refuse(frappe.DoesNotExistError, _("Certificate not found."))
		if exc.message_code == "unable_to_generate_file":
			_refuse(ReceivedCertificateFileError, _("This file cannot be generated right now."))
		_report_failure(exc)
		_unavailable()
	except TrueSkillsError as exc:
		_report_failure(exc)
		_unavailable()

	content_type, extension = DOWNLOAD_FORMATS[file_format]
	frappe.local.response.filename = f"trueskill_{int(certificate_id)}.{extension}"
	frappe.local.response.filecontent = content
	frappe.local.response.content_type = content_type
	frappe.local.response.type = "download"

import threading
from typing import Any

from .client import TrueSkillsClient, TrueSkillsClientError, TrueSkillsError
from .safelog import get_logger
from .settings import TrueSkillsSettings


class TrueSkillsService:
	"""High-level operations performed against the TrueSkills API.

	Lazy-property pattern matching ``IngestionService``: dependencies
	(settings, client, logger) are built on first access and cached.
	"""

	_settings: TrueSkillsSettings | None = None
	_client: TrueSkillsClient | None = None
	_logger = None

	def __init__(self) -> None:
		self._template_cache: dict[int, dict] = {}
		self._template_cache_lock = threading.Lock()
		self._organization_id: int | None = None

	@property
	def settings(self) -> TrueSkillsSettings:
		if self._settings is None:
			self._settings = TrueSkillsSettings.load()
		return self._settings

	@property
	def client(self) -> TrueSkillsClient:
		if self._client is None:
			self._client = TrueSkillsClient(self.settings)
		return self._client

	@property
	def logger(self):
		if self._logger is None:
			self._logger = get_logger()
		return self._logger

	def is_ready(self) -> bool:
		return self.settings.is_ready()

	# ---- Read --------------------------------------------------------

	def health(self) -> dict:
		"""``GET /health`` — smoke test, caches ``organizationId`` for logging."""
		response = self.client.health()
		org_id = response.get("organizationId") if isinstance(response, dict) else None
		if isinstance(org_id, int):
			self._organization_id = org_id
		self.logger.info(f"TrueSkills health ok (organizationId={org_id})")
		return response

	def test_connection(self) -> dict:
		"""Verify the API key/endpoint by issuing a health request."""
		url = self.client.base_url
		response = self.health()
		return {"ok": True, "url": url, "response": response}

	def list_templates(self) -> list[dict]:
		"""``GET /templates`` — newest first, no pagination."""
		response = self.client.get("/templates")
		return _coerce_list(response)

	def get_template(self, template_id: int) -> dict:
		"""``GET /templates/{id}`` — single template, with in-process cache.

		The cache is invalidated automatically on ``template_not_found`` so
		stale ids are not served indefinitely.
		"""
		key = int(template_id)
		with self._template_cache_lock:
			cached = self._template_cache.get(key)
			if cached is not None:
				return cached
		try:
			response = self.client.get(f"/templates/{key}")
		except TrueSkillsClientError as exc:
			if exc.message_code == "template_not_found":
				with self._template_cache_lock:
					self._template_cache.pop(key, None)
			raise
		with self._template_cache_lock:
			self._template_cache[key] = response
		return response

	def invalidate_template_cache(self, template_id: int | None = None) -> None:
		"""Clear cached templates (one if id given, all otherwise)."""
		with self._template_cache_lock:
			if template_id is None:
				self._template_cache.clear()
			else:
				self._template_cache.pop(int(template_id), None)

	def list_issued(self) -> list[dict]:
		"""``GET /list`` — up to 100 most recent issued certificates."""
		response = self.client.get("/list")
		return _coerce_list(response)

	def get_issued(self, certificate_id: int) -> dict:
		"""``GET /detail/{id}`` — one issued certificate."""
		return self.client.get(f"/detail/{int(certificate_id)}")

	def verify(self, uid: str, fiscal_id: str | None = None) -> dict:
		"""``POST /verify`` — always 200; check the ``valid`` field.

		``fiscal_id`` enables holder-verification on the server and is never
		logged. Treat ``valid: false`` as a successful negative answer, not
		an error.
		"""
		payload: dict[str, Any] = {"uid": uid}
		if fiscal_id:
			payload["fiscalId"] = fiscal_id
		return self.client.post("/verify", json=payload)

	def download(self, certificate_id: int, file_format: str) -> tuple[str, bytes]:
		"""``GET /download/{id}/{format}`` — returns (content_type, bytes).

		``file_format`` must be ``"image"`` (PNG) or ``"jsonp"`` (JSON-LD).
		"""
		if file_format not in ("image", "jsonp"):
			raise TrueSkillsError(f"Unsupported download format: {file_format!r}")
		accept = "image/png" if file_format == "image" else "application/ld+json"
		return self.client.download(
			f"/download/{int(certificate_id)}/{file_format}", accept=accept
		)

	# ---- Write -------------------------------------------------------

	def issue_certificate(
		self,
		*,
		template_id: int,
		fiscal_id: str,
		email: str,
		name: str,
		certificate_values: dict | None = None,
		subject_data: dict | None = None,
	) -> dict:
		"""``POST /issue`` — issue a certificate to a recipient.

		NOT idempotent. The caller MUST persist a ``pending`` reconciliation
		row BEFORE calling this method (per brief §2.5 / §4). On timeout or
		5xx the call may have succeeded server-side; never auto-retry.

		``fiscal_id`` is held in memory only for the duration of this call,
		is sent over HTTPS, and is never logged. Body of ``/issue`` is not
		logged for the same reason.
		"""
		payload: dict[str, Any] = {
			"templateId": int(template_id),
			"fiscalId": fiscal_id,
			"email": email,
			"name": name,
		}
		if certificate_values:
			payload["certificateValues"] = certificate_values
		if subject_data:
			payload["subjectData"] = subject_data

		response = self.client.post("/issue", json=payload)
		issued_id = response.get("id") if isinstance(response, dict) else None
		self.logger.info(
			f"TrueSkills issued certificate (templateId={template_id}, id={issued_id})"
		)
		return response

	def upload_media(self, *, content: bytes, filename: str, content_type: str) -> str:
		"""Upload an image to TrueSkills media storage; return its stored path.

		The returned path (e.g. ``00/15/img.png``) is what must be passed as
		``imageUrl`` when creating a template so that ``GET /download/{id}/image``
		can bake the image into the Openbadge PNG. TrueSkills resolves it as a
		physical file in the organization storage — an external URL will not do.
		"""
		response = self.client.upload_media(
			content=content, filename=filename, content_type=content_type
		)
		url = response.get("url") if isinstance(response, dict) else None
		if not url:
			raise TrueSkillsError("TrueSkills media upload did not return a url.")
		self.logger.info(f"Uploaded TrueSkills media '{filename}' -> {url}")
		return url

	def create_template(self, payload: dict) -> dict:
		"""``POST /templates`` — create a new certificate template.

		``payload`` is forwarded as-is. The caller is responsible for shaping
		it to the TrueSkills schema (camelCase keys, ``badge`` object when
		``type == 'Openbadge'``, etc.). NOT idempotent — never auto-retry.
		"""
		response = self.client.post("/templates", json=payload)
		self.logger.info(
			f"Created TrueSkills template '{payload.get('name')}' "
			f"(id={response.get('id') if isinstance(response, dict) else None})"
		)
		return response


def _coerce_list(response: Any) -> list[dict]:
	"""Some endpoints may wrap the array in a dict. Normalize to a list."""
	if isinstance(response, list):
		return response
	if isinstance(response, dict):
		for key in ("data", "templates", "items", "results"):
			value = response.get(key)
			if isinstance(value, list):
				return value
	return []

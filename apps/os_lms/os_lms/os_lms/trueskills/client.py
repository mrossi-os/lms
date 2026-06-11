import random
import time
from typing import Any

import requests

from .safelog import get_logger
from .settings import TrueSkillsSettings

CERTIFICATES_BASE_PATH = "/api/v1/service/certificates"

# Exponential backoff (seconds) for retryable requests. Length determines max attempts.
RETRY_BACKOFF_SECONDS = (1.0, 2.0, 4.0)
RETRY_JITTER_RATIO = 0.2  # ±20%


class TrueSkillsError(Exception):
	"""Base exception for TrueSkills client failures."""


class TrueSkillsNetworkError(TrueSkillsError):
	"""Network/transport failure (timeout, connection reset, DNS, ...)."""


class TrueSkillsServerError(TrueSkillsError):
	"""TrueSkills returned 5xx — eligible for retry on idempotent endpoints."""

	def __init__(self, message: str, status: int, message_code: str | None = None):
		super().__init__(message)
		self.status = status
		self.message_code = message_code


class TrueSkillsClientError(TrueSkillsError):
	"""TrueSkills returned 4xx — stable `message` code surfaced; no auto-retry."""

	def __init__(self, message: str, status: int, message_code: str | None = None):
		super().__init__(message)
		self.status = status
		self.message_code = message_code


class TrueSkillsClient:
	"""HTTP client for the TrueSkills REST API.

	Authentication uses the ``X-Api-Key`` header (the key implicitly identifies
	the organization — never send ``organizationId`` in any payload). The base
	path ``/api/v1/service/certificates`` is appended automatically to
	``settings.endpoint`` (which stores host only).

	Retry policy (per brief §4): ``GET *`` and ``POST /verify`` may retry on
	5xx/network errors with exponential backoff + jitter (max 3 attempts).
	All other POST requests are non-idempotent and never retried automatically.
	"""

	DEFAULT_TIMEOUT = 15

	def __init__(self, settings: TrueSkillsSettings, timeout: int | None = None):
		if not settings.enabled:
			raise TrueSkillsError("TrueSkills API integration is disabled.")
		if not settings.api_key:
			raise TrueSkillsError("TrueSkills API key is not configured.")
		if not settings.endpoint:
			raise TrueSkillsError("TrueSkills API endpoint is not configured.")

		self.settings = settings
		self.timeout = timeout or self.DEFAULT_TIMEOUT
		self._logger = get_logger()
		self._session = requests.Session()
		self._session.headers.update(
			{
				"X-Api-Key": settings.api_key,
				"Accept": "application/json",
			}
		)

	# ---- URL ------------------------------------------------------------

	@property
	def base_url(self) -> str:
		host = self.settings.endpoint.rstrip("/")
		# The endpoint setting is meant to hold the host only, but operators
		# routinely paste the full base URL. Strip a duplicated suffix so a
		# doubled path can't slip through — the server answers a doubled path
		# with a 200 SPA fallback (not an error), which is invisible to
		# health/test_connection and silently breaks every call.
		if host.endswith(CERTIFICATES_BASE_PATH):
			host = host[: -len(CERTIFICATES_BASE_PATH)].rstrip("/")
		return f"{host}{CERTIFICATES_BASE_PATH}"

	def _build_url(self, path: str) -> str:
		suffix = path.lstrip("/")
		return f"{self.base_url}/{suffix}" if suffix else self.base_url

	# ---- Retry ----------------------------------------------------------

	@staticmethod
	def _is_retryable(method: str, path: str) -> bool:
		method = method.upper()
		if method == "GET":
			return True
		# POST /verify is the only retryable POST (idempotent by design).
		return method == "POST" and path.lstrip("/").startswith("verify")

	@staticmethod
	def _sleep_with_jitter(base: float) -> None:
		jitter = base * RETRY_JITTER_RATIO * random.uniform(-1, 1)
		time.sleep(max(0.0, base + jitter))

	# ---- Request core ---------------------------------------------------

	def _do_request(
		self,
		method: str,
		path: str,
		*,
		json: dict | None = None,
		params: dict | None = None,
		accept: str | None = None,
	) -> requests.Response:
		url = self._build_url(path)
		headers: dict[str, str] = {}
		if json is not None:
			headers["Content-Type"] = "application/json"
		if accept is not None:
			headers["Accept"] = accept

		retryable = self._is_retryable(method, path)
		attempts = len(RETRY_BACKOFF_SECONDS) if retryable else 1

		for attempt in range(attempts):
			try:
				response = self._session.request(
					method=method.upper(),
					url=url,
					json=json,
					params=params,
					timeout=self.timeout,
					headers=headers or None,
				)
			except requests.RequestException as exc:
				self._logger.warning(
					f"TrueSkills {method.upper()} {path} network error "
					f"(attempt {attempt + 1}/{attempts}): {exc}"
				)
				if retryable and attempt < attempts - 1:
					self._sleep_with_jitter(RETRY_BACKOFF_SECONDS[attempt])
					continue
				raise TrueSkillsNetworkError(f"TrueSkills request failed: {exc}") from exc

			if 500 <= response.status_code < 600 and retryable and attempt < attempts - 1:
				code = self._extract_message_code(response)
				self._logger.warning(
					f"TrueSkills {method.upper()} {path} → {response.status_code} "
					f"(message={code}); retrying ({attempt + 1}/{attempts})"
				)
				self._sleep_with_jitter(RETRY_BACKOFF_SECONDS[attempt])
				continue

			return response

		# Unreachable: the loop always either returns or raises.
		raise TrueSkillsNetworkError("TrueSkills request failed: exhausted retries")

	# ---- Error handling -------------------------------------------------

	@staticmethod
	def _extract_message_code(response: requests.Response) -> str | None:
		try:
			data = response.json()
		except ValueError:
			return None
		if isinstance(data, dict):
			val = data.get("message")
			if isinstance(val, str):
				return val
		return None

	def _raise_for_status(self, response: requests.Response, method: str, path: str) -> None:
		if response.ok:
			return
		code = self._extract_message_code(response)
		summary = (
			f"TrueSkills {method.upper()} {path} → {response.status_code}"
			f"{f' ({code})' if code else ''}"
		)
		self._logger.warning(summary)
		if 400 <= response.status_code < 500:
			raise TrueSkillsClientError(summary, response.status_code, code)
		raise TrueSkillsServerError(summary, response.status_code, code)

	# ---- Public verbs ---------------------------------------------------

	def get(self, path: str, params: dict | None = None) -> Any:
		response = self._do_request("GET", path, params=params)
		self._raise_for_status(response, "GET", path)
		return self._json_or_empty(response)

	def post(self, path: str, json: dict | None = None) -> Any:
		response = self._do_request("POST", path, json=json)
		self._raise_for_status(response, "POST", path)
		return self._json_or_empty(response)

	def download(self, path: str, accept: str | None = None) -> tuple[str, bytes]:
		"""GET a binary endpoint (e.g. ``/download/{id}/{format}``).

		Returns ``(content_type, raw_bytes)``. Does not parse JSON on success.
		"""
		response = self._do_request("GET", path, accept=accept)
		self._raise_for_status(response, "GET", path)
		content_type = response.headers.get("Content-Type", "application/octet-stream")
		return content_type, response.content

	def health(self) -> dict:
		"""Smoke test: ``GET /health`` → ``{status, organizationId}``."""
		return self.get("/health")

	# ---- Helpers --------------------------------------------------------

	@staticmethod
	def _json_or_empty(response: requests.Response) -> Any:
		if not response.content:
			return {}
		try:
			return response.json()
		except ValueError:
			return {"raw": response.text}

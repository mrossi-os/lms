import requests

from .settings import TrueSkillsSettings


class TrueSkillsError(Exception):
	"""Raised when a TrueSkills API call cannot be completed."""


class TrueSkillsClient:
	"""Thin HTTP client for the TrueSkills API.

	Authentication uses the ``X-API-Key`` custom header. The client validates
	the configuration on instantiation so callers can fail fast when the
	integration is disabled or misconfigured.
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
		self._session = requests.Session()
		self._session.headers.update(
			{
				"X-API-Key": settings.api_key,
				"Accept": "application/json",
				"Content-Type": "application/json",
			}
		)

	def _build_url(self, path: str) -> str:
		base = self.settings.endpoint.rstrip("/")
		suffix = path.lstrip("/")
		return f"{base}/{suffix}" if suffix else base

	def request(
		self,
		method: str,
		path: str,
		*,
		json: dict | None = None,
		params: dict | None = None,
	) -> dict:
		url = self._build_url(path)
		try:
			response = self._session.request(
				method=method.upper(),
				url=url,
				json=json,
				params=params,
				timeout=self.timeout,
			)
		except requests.RequestException as exc:
			raise TrueSkillsError(f"TrueSkills request failed: {exc}") from exc

		if not response.ok:
			raise TrueSkillsError(
				f"TrueSkills API returned {response.status_code}: {response.text[:500]}"
			)

		if not response.content:
			return {}
		try:
			return response.json()
		except ValueError:
			return {"raw": response.text}

	# Convenience helpers ------------------------------------------------
	def get(self, path: str, params: dict | None = None) -> dict:
		return self.request("GET", path, params=params)

	def post(self, path: str, json: dict | None = None) -> dict:
		return self.request("POST", path, json=json)

	def ping(self) -> dict:
		"""Perform a lightweight call to verify connectivity.

		The exact health endpoint is provider-specific; this method assumes a
		``/health`` route and falls back to a root GET when not available.
		"""
		try:
			return self.get("/health")
		except TrueSkillsError:
			return self.get("/")

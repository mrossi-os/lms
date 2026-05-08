import frappe

from .client import TrueSkillsClient
from .settings import TrueSkillsSettings


class TrueSkillsService:
	"""High-level operations performed against the TrueSkills API.

	Lazy-property pattern matching ``IngestionService``: dependencies
	(settings, client, logger) are built on first access and cached.
	"""

	_settings: TrueSkillsSettings | None = None
	_client: TrueSkillsClient | None = None
	_logger = None

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
			self._logger = frappe.logger("trueskills", allow_site=True)
		return self._logger

	def is_ready(self) -> bool:
		return self.settings.is_ready()

	def test_connection(self) -> dict:
		"""Verify the API key/endpoint by issuing a ping request."""
		called_url = self.client.base_url
		response = self.client.ping()
		self.logger.info(f"TrueSkills connection test succeeded ({called_url})")
		return {"ok": True, "url": called_url, "response": response}

	def create_template(self, payload: dict) -> dict:
		"""Create a new certificate template on TrueSkills.

		``payload`` is forwarded as-is. The caller is responsible for shaping
		it to the TrueSkills schema (camelCase keys, ``badge`` object when
		``type == 'Openbadge'``, etc.).
		"""
		response = self.client.post("/templates", json=payload)
		self.logger.info(
			f"Created TrueSkills template '{payload.get('name')}' "
			f"(id={response.get('id') if isinstance(response, dict) else None})"
		)
		return response

	def list_templates(self) -> list[dict]:
		"""Fetch the certificate templates available on the TrueSkills account.

		The TrueSkills API may wrap the array in a dict (e.g. ``{"data": [...]}``);
		this method tolerates the most common shapes and always returns a list.
		"""
		response = self.client.get("/templates")
		if isinstance(response, list):
			return response
		if isinstance(response, dict):
			for key in ("data", "templates", "items", "results"):
				value = response.get(key)
				if isinstance(value, list):
					return value
		return []

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

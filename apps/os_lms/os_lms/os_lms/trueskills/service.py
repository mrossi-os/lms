import frappe

from .client import TrueSkillsClient, TrueSkillsError
from .settings import TrueSkillsSettings


class TrueSkillsService:
	"""High-level operations performed against the TrueSkills API.

	Follows the same lazy-property pattern used by ``IngestionService`` so
	dependencies (settings, client, logger) are built on first access and
	cached on the instance.
	"""

	_settings: TrueSkillsSettings | None = None
	_client: TrueSkillsClient | None = None
	_logger = None

	# Lazy dependencies --------------------------------------------------
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

	# Public API ---------------------------------------------------------
	def is_ready(self) -> bool:
		return self.settings.is_ready()

	def test_connection(self) -> dict:
		"""Verify the API key/endpoint by issuing a ping request."""
		response = self.client.ping()
		self.logger.info("TrueSkills connection test succeeded")
		return {"ok": True, "response": response}

	def issue_certificate(self, certificate_doc) -> dict | None:
		"""Issue a certificate on TrueSkills mirroring an LMS Certificate.

		Returns the API response payload, or ``None`` when the integration is
		not configured. Errors are logged and re-raised so callers can decide
		whether to swallow them (the course-completion hook does).
		"""
		if not self.is_ready():
			self.logger.debug("TrueSkills not ready, skipping certificate issue")
			return None

		template = self.settings.certificate_template
		if not template:
			raise TrueSkillsError("TrueSkills certificate template is not configured.")

		payload = self._build_certificate_payload(certificate_doc, template)
		try:
			response = self.client.post("/certificates", json=payload)
		except TrueSkillsError:
			self.logger.exception(
				f"Failed to issue TrueSkills certificate for {certificate_doc.name}"
			)
			raise

		self.logger.info(
			f"Issued TrueSkills certificate for {certificate_doc.name} "
			f"(member={certificate_doc.member}, course={certificate_doc.course})"
		)
		return response

	# Internals ----------------------------------------------------------
	def _build_certificate_payload(self, certificate_doc, template: str) -> dict:
		member_name = certificate_doc.get("member_name") or frappe.db.get_value(
			"User", certificate_doc.member, "full_name"
		)
		course_title = certificate_doc.get("course_title") or frappe.db.get_value(
			"LMS Course", certificate_doc.course, "title"
		)
		return {
			"template": template,
			"recipient": {
				"email": certificate_doc.member,
				"name": member_name,
			},
			"course": {
				"id": certificate_doc.course,
				"title": course_title,
			},
			"issue_date": str(certificate_doc.issue_date),
			"reference": certificate_doc.name,
		}

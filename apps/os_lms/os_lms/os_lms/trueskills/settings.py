from dataclasses import dataclass

import frappe
from frappe.utils.password import get_decrypted_password


@dataclass
class TrueSkillsSettings:
	enabled: bool
	api_key: str | None
	endpoint: str | None

	@classmethod
	def load(cls) -> "TrueSkillsSettings":
		"""Read TrueSkills configuration from the LMS Settings single doctype."""
		doc = frappe.get_cached_doc("LMS Settings", "LMS Settings")
		api_key = None
		if doc.get("trueskills_api_key"):
			api_key = get_decrypted_password(
				"LMS Settings",
				"LMS Settings",
				"trueskills_api_key",
				raise_exception=False,
			)
		endpoint = (doc.get("trueskills_api_endpoint") or "").strip() or None
		return cls(
			enabled=bool(doc.get("trueskills_api_enabled")),
			api_key=api_key,
			endpoint=endpoint,
		)

	def is_ready(self) -> bool:
		return bool(self.enabled and self.api_key and self.endpoint)

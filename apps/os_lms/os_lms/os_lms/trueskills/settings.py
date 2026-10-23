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


# Who may point the integration somewhere else. A Moderator can write LMS Settings,
# and the client sends the decrypted key in X-Api-Key to whatever host the endpoint
# names, so editing it used to hand them the key and a server-side request to any
# internal address (OWASP A01/SSRF).
SETTINGS_EDITOR_ROLES = {"System Manager", "Gestore"}
GUARDED_FIELDS = ("trueskills_api_enabled", "trueskills_api_endpoint", "trueskills_api_key")


def validate_lms_settings(doc, method=None) -> None:
	"""LMS Settings `validate` hook: guard the TrueSkills connection fields."""
	before = doc.get_doc_before_save()
	changed = [
		field for field in GUARDED_FIELDS if (before.get(field) if before else None) != doc.get(field)
	]
	if not changed:
		return
	user = frappe.session.user
	if user != "Administrator" and not SETTINGS_EDITOR_ROLES & set(frappe.get_roles(user)):
		frappe.throw(
			frappe._("Only a System Manager or a Gestore can change the TrueSkills connection."),
			frappe.PermissionError,
		)
	if "trueskills_api_endpoint" in changed and doc.get("trueskills_api_endpoint"):
		validate_endpoint(doc.trueskills_api_endpoint)


def validate_endpoint(url: str) -> None:
	"""Accept only a plain https URL whose host resolves to public addresses."""
	from urllib.parse import urlsplit

	url = url.strip()
	parts = urlsplit(url)
	allowed_schemes = {"https", "http"} if frappe.conf.developer_mode else {"https"}
	if parts.scheme not in allowed_schemes or not parts.hostname:
		frappe.throw(frappe._("The TrueSkills endpoint must be an https:// address."))
	# A query or a fragment would swallow the path the client appends ("…#" turns
	# "/api/v1/…" into a fragment), and credentials in the URL have no business there.
	# Checked on the text: a bare trailing "#" or "?" parses as an empty fragment/query.
	if "#" in url or "?" in url or parts.username or parts.password:
		frappe.throw(frappe._("The TrueSkills endpoint cannot contain credentials, a query or a fragment."))
	if not _resolves_to_public_addresses(parts.hostname, parts.port or 443):
		frappe.throw(
			frappe._("The TrueSkills endpoint must be a public host: {0}").format(parts.hostname)
		)


def _resolves_to_public_addresses(host: str, port: int) -> bool:
	import ipaddress
	import socket

	try:
		infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
	except (socket.gaierror, UnicodeError):
		return False
	addresses = {info[4][0] for info in infos}
	return bool(addresses) and all(ipaddress.ip_address(a.split("%")[0]).is_global for a in addresses)

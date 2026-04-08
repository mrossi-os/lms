import frappe

from .client import TrueSkillsError
from .service import TrueSkillsService


def _require_admin() -> None:
	roles = set(frappe.get_roles(frappe.session.user))
	if not roles & {"System Manager", "Moderator", "Course Creator"}:
		frappe.throw("Not permitted", frappe.PermissionError)


@frappe.whitelist()
def get_status() -> dict:
	"""Return whether the TrueSkills integration is configured and ready."""
	_require_admin()
	settings = TrueSkillsService().settings
	return {
		"enabled": settings.enabled,
		"endpoint": settings.endpoint,
		"has_api_key": bool(settings.api_key),
		"certificate_template": settings.certificate_template,
		"ready": settings.is_ready(),
	}


@frappe.whitelist()
def test_connection() -> dict:
	"""Issue a ping request against the configured TrueSkills endpoint."""
	_require_admin()
	try:
		return TrueSkillsService().test_connection()
	except TrueSkillsError as exc:
		return {"ok": False, "error": str(exc)}


@frappe.whitelist()
def issue_certificate(certificate: str) -> dict:
	"""Manually trigger TrueSkills issuance for an existing LMS Certificate."""
	_require_admin()
	doc = frappe.get_doc("LMS Certificate", certificate)
	try:
		response = TrueSkillsService().issue_certificate(doc)
	except TrueSkillsError as exc:
		return {"ok": False, "error": str(exc)}
	return {"ok": True, "response": response}

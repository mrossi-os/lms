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
		"ready": settings.is_ready(),
	}


@frappe.whitelist()
def test_connection() -> dict:
	"""Issue a ping request against the configured TrueSkills endpoint."""
	_require_admin()
	service = TrueSkillsService()
	# Resolve the URL up-front so it's surfaced even when the call fails.
	url = (service.settings.endpoint or "").rstrip("/") or None
	try:
		return service.test_connection()
	except TrueSkillsError as exc:
		return {"ok": False, "url": url, "error": str(exc)}

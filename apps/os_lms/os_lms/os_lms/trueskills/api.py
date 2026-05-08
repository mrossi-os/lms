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


@frappe.whitelist()
def list_templates() -> dict:
	"""Return the list of certificate templates available on TrueSkills."""
	_require_admin()
	try:
		templates = TrueSkillsService().list_templates()
	except TrueSkillsError as exc:
		return {"ok": False, "error": str(exc), "templates": []}
	return {"ok": True, "templates": templates}


@frappe.whitelist()
def create_template(payload: dict) -> dict:
	"""Create a new certificate template via the TrueSkills API."""
	_require_admin()
	if not isinstance(payload, dict):
		try:
			payload = frappe.parse_json(payload)
		except Exception:
			return {"ok": False, "error": "Invalid payload"}
	if not payload.get("name") or not payload.get("type"):
		return {"ok": False, "error": "Fields 'name' and 'type' are required."}
	if payload.get("type") == "Openbadge":
		badge = payload.get("badge") or {}
		if not badge.get("url"):
			return {"ok": False, "error": "Openbadge templates require a badge URL."}
	try:
		template = TrueSkillsService().create_template(payload)
	except TrueSkillsError as exc:
		return {"ok": False, "error": str(exc)}
	return {"ok": True, "template": template}

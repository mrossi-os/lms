# Copyright (c) 2026, ELITE and contributors
# For license information, please see license.txt

import frappe


@frappe.whitelist()
def is_google_oauth_configured() -> bool:
	"""Return True if Google Settings has OAuth credentials set.

	Used by the frontend Settings page to decide whether to show the
	"Authorize" UI or a configuration warning. Doesn't expose the secret.
	"""
	settings = frappe.get_cached_doc("Google Settings")
	if not settings.enable or not settings.client_id:
		return False
	try:
		secret = settings.get_password("client_secret", raise_exception=False)
	except Exception:
		secret = None
	return bool(secret)

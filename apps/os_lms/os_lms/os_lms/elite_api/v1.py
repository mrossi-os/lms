"""Elite API, version 1. Every endpoint is GET-only and guarded by ``elite_api_endpoint``."""

import frappe

from os_lms.os_lms.elite_api import keys
from os_lms.os_lms.elite_api.auth import elite_api_endpoint, get_current_key


@frappe.whitelist(methods=["GET"])
@elite_api_endpoint
def ping() -> dict:
	"""Let a client check that its key works."""
	return {
		"status": "ok",
		"api_version": "v1",
		"key_name": frappe.db.get_value(keys.KEY_DOCTYPE, get_current_key(), "key_name"),
	}

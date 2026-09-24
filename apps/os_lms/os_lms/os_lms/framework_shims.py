"""Stand-ins for whitelisted Frappe methods that our frontend calls but the Frappe
release we run (version-16) does not ship yet.

Each one is registered through `framework_method_shims` in hooks.py and must be
removed once Frappe ships the original: test_override_signatures goes red then.
"""

import frappe


@frappe.whitelist(allow_guest=True)
def telemetry_boot_config() -> dict:
	"""frappe-ui's telemetry plugin (1.0.0-beta.29) asks for its config on every SPA
	load. Without this the request fails with a 417 and the plugin falls back to
	telemetry off; answer that same outcome without the error.
	"""
	return {"enabled": False}

# Copyright (c) 2026, ELITE and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class OSAuditEvent(Document):
	"""Append-only, hash-chained audit event.

	Only os_lms.os_lms.os_audit writes these rows, with db_insert after the request
	committed. No role holds write or delete; the guards below also stop the
	Administrator (who bypasses DocPerms) from editing or deleting one from the desk.
	Retention and erasure go through raw queries in os_audit, never through here.
	"""

	def validate(self):
		frappe.throw(_("Audit events cannot be created or changed."), frappe.PermissionError)

	def on_trash(self):
		frappe.throw(_("Audit events cannot be deleted."), frappe.PermissionError)

	def before_rename(self, old, new, merge=False):
		frappe.throw(_("Audit events cannot be renamed."), frappe.PermissionError)


def on_doctype_update():
	frappe.db.add_index("OS Audit Event", ["user", "timestamp"])
	frappe.db.add_index("OS Audit Event", ["course", "timestamp"])
	frappe.db.add_index("OS Audit Event", ["event_type", "reference_name"])

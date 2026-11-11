# Copyright (c) 2026, ELITE and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class OSAuditSession(Document):
	"""A visit to a lesson. Written only by os_lms.os_lms.os_audit with raw queries;
	its totals become evidence in the session_closed event of the chain."""

	def validate(self):
		if not frappe.flags.in_os_audit:
			frappe.throw(_("Audit sessions are written by the system only."), frappe.PermissionError)


def on_doctype_update():
	frappe.db.add_index("OS Audit Session", ["user", "closed", "last_seen_at"])

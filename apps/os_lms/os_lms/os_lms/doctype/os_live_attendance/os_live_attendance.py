# Copyright (c) 2026, ELITE and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class OSLiveAttendance(Document):
	"""A participant segment of a live class as the provider (Zoom, Google Meet) reported it.

	Written only by os_lms.os_lms.os_audit_live with db_insert and raw updates
	(OS Audit phase 4); the desk can read, never write."""

	def validate(self):
		frappe.throw(_("Live attendance rows are written by the system only."), frappe.PermissionError)


def on_doctype_update():
	frappe.db.add_index("OS Live Attendance", ["live_class", "user"])

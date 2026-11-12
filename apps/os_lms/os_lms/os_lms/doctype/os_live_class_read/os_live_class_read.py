# Copyright (c) 2026, ELITE and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class OSLiveClassRead(Document):
	"""Whether the provider attendance of a live class has been read, and how it went.

	Written only by os_lms.os_lms.os_audit_live with db_insert and raw updates
	(OS Audit phase 4); the desk can read, never write."""

	def validate(self):
		frappe.throw(_("Live class reads are written by the system only."), frappe.PermissionError)

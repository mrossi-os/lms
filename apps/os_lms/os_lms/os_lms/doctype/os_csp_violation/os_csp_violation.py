# Copyright (c) 2026, ELITE and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.query_builder import Interval
from frappe.query_builder.functions import Now


class OSCSPViolation(Document):
	@staticmethod
	def clear_old_logs(days=90):
		"""Called by Log Settings (see ``default_log_clearing_doctypes`` in hooks.py)."""
		table = frappe.qb.DocType("OS CSP Violation")
		frappe.db.delete(table, filters=(table.modified < (Now() - Interval(days=days))))

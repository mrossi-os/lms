# Copyright (c) 2026, ELITE and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt

# Fields the retention job writes with set_single_value: never part of a change event.
INTERNAL_FIELDS = ("chain_anchor_seq", "chain_anchor_hash")


class OSAuditSettings(Document):
	def validate(self):
		# The anchor belongs to the retention job: a form opened before its last run
		# must not write an older anchor back, or the chain would stop verifying.
		for fieldname in INTERNAL_FIELDS:
			self.set(fieldname, frappe.db.get_single_value(self.doctype, fieldname))

		# The retention period is mandatory (PIANO D9): without it the audit cannot start.
		if cint(self.enabled) and cint(self.retention_days) <= 0:
			frappe.throw(_("Set a retention period in days before enabling the audit."))
		if self.retention_days is not None and cint(self.retention_days) < 0:
			frappe.throw(_("The retention period cannot be negative."))
		if cint(self.inactivity_minutes) < 1:
			frappe.throw(_("The inactivity threshold must be at least one minute."))

		seen = set()
		for row in self.courses or []:
			if row.course in seen:
				frappe.throw(_("Course {0} is listed more than once.").format(row.course))
			seen.add(row.course)
			if flt(row.planned_hours) < 0:
				frappe.throw(_("The planned hours cannot be negative."))
			if not 0 <= flt(row.min_attendance_percent) <= 100:
				frappe.throw(_("The minimum attendance must be between 0 and 100."))

	def on_update(self):
		from os_lms.os_lms.os_audit import on_settings_update

		on_settings_update(self)

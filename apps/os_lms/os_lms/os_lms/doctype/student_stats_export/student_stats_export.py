# Copyright (c) 2026, ELITE and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class StudentStatsExport(Document):
	def on_trash(self):
		# Remove the generated private file when the export record is deleted.
		# Frappe already drops attachments on delete; this is a defensive backstop
		# so no orphaned export file is ever left behind.
		for name in frappe.get_all(
			"File",
			filters={
				"attached_to_doctype": "Student Stats Export",
				"attached_to_name": self.name,
			},
			pluck="name",
		):
			frappe.delete_doc("File", name, ignore_permissions=True, force=True)

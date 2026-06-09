# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt

import json

import frappe
from frappe import _
from frappe.model.document import Document


class LMSAJudgePrompt(Document):
	def validate(self):
		self._validate_output_schema_is_json()

	def _validate_output_schema_is_json(self):
		if not self.output_schema:
			return
		try:
			parsed = json.loads(self.output_schema)
		except json.JSONDecodeError as e:
			frappe.throw(_("Output Schema must be valid JSON: {0}").format(str(e)))
		if not isinstance(parsed, dict):
			frappe.throw(_("Output Schema must be a JSON object at the top level."))

# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

# Tolerance for weight-sum validation: allow up to 0.001 drift to account for
# rounding when a user types 0.33 + 0.33 + 0.34.
WEIGHT_SUM_TOLERANCE = 0.001


class LMSAEvaluationRubric(Document):
	def validate(self):
		self._validate_weights_sum_to_one()

	def _validate_weights_sum_to_one(self):
		if not self.criteria:
			frappe.throw(_("A rubric must declare at least one criterion."))
		total = sum((row.weight or 0.0) for row in self.criteria)
		if abs(total - 1.0) > WEIGHT_SUM_TOLERANCE:
			frappe.throw(
				_("Criterion weights must sum to 1.0 (current sum: {0}).").format(round(total, 4))
			)

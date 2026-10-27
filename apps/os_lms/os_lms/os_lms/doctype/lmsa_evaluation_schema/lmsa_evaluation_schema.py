# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

# Tolerance for weight-sum validation: allow up to 0.001 drift to account for
# rounding when a user types 0.33 + 0.33 + 0.34.
WEIGHT_SUM_TOLERANCE = 0.001


class LMSAEvaluationSchema(Document):
	def validate(self):
		self._validate_weights_sum_to_one()

	def _validate_weights_sum_to_one(self):
		if not self.criteria:
			frappe.throw(_("An evaluation schema must declare at least one criterion."))
		total = sum((row.weight or 0.0) for row in self.criteria)
		if abs(total - 1.0) > WEIGHT_SUM_TOLERANCE:
			frappe.throw(
				_("Criterion weights must sum to 1.0 (current sum: {0}).").format(round(total, 4))
			)


# The same rules as the simulation editor endpoints (get/save/delete_evaluation_schema),
# applied to Desk and /api/resource too.
ROLES_WITH_FULL_ACCESS = {"System Manager", "Moderator"}


def get_permission_query_conditions(user: str | None = None) -> str:
	user = user or frappe.session.user
	if user == "Administrator" or ROLES_WITH_FULL_ACCESS & set(frappe.get_roles(user)):
		return ""
	owner = frappe.db.escape(user, percent=False)
	return f"(`tabLMSA Evaluation Schema`.owner = {owner} OR `tabLMSA Evaluation Schema`.is_shared = 1)"


def has_permission(doc, ptype: str = "read", user: str | None = None) -> bool:
	user = user or frappe.session.user
	if user == "Administrator" or ROLES_WITH_FULL_ACCESS & set(frappe.get_roles(user)):
		return True
	if ptype == "create" or doc.owner == user:
		return True
	# Others read shared schemas but never change them.
	return ptype in {"read", "print"} and bool(doc.is_shared)

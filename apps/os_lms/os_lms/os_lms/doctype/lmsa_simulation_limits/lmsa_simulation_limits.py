# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from os_lms.os_lms.ai.simulations.limits import LIMIT_DEFAULTS


class LMSASimulationLimits(Document):
	def validate(self):
		# No "0 = unlimited": an unbounded limit is the very problem these fields close.
		for fieldname in LIMIT_DEFAULTS:
			if (self.get(fieldname) or 0) < 1:
				label = _(self.meta.get_label(fieldname))
				frappe.throw(_("{0} must be at least 1.").format(label))

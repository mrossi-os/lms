# Copyright (c) 2026, ELITE and contributors
# For license information, please see license.txt

import json

import frappe
from frappe import _
from frappe.model.document import Document

from os_lms.os_lms import branding_presets


class BrandPreset(Document):
	"""A saved set of Brand Customize colors (docs/brand-customize/fase-5-analisi.md).

	``data`` holds the values in the format of Brand Customize's Export, so the
	form applies a preset with the same code as an imported file.
	"""

	def validate(self):
		data = branding_presets.clean_data(self.data)
		# Keys with an empty value (an empty Expert table) are not brand values.
		if not any(data.values()):
			frappe.throw(_("The preset has no brand values."), title=_("Invalid Preset"))
		self.data = json.dumps(data, sort_keys=True)
		self.mode = branding_presets.mode_of(data)
		self.swatches = ",".join(branding_presets.swatches(data))

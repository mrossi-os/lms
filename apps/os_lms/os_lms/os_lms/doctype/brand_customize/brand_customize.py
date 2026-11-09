# Copyright (c) 2026, ELITE and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from os_lms.os_lms import branding_contrast
from os_lms.os_lms.branding import (
	DEFAULT_MODE,
	EXPERT_TABLE,
	_token_stock,
	check_expert_tokens,
	expert_values,
	invalid_fields,
)


class BrandCustomize(Document):
	def on_update(self):
		self.report_low_contrast()

	def report_low_contrast(self):
		"""Summary of the hard-to-read colors (decision D6: it does not block)."""
		entries = branding_contrast.low(
			branding_contrast.report(self, self.mode or DEFAULT_MODE, _token_stock())
		)
		if not entries:
			return
		lines = "".join(
			"<li>{}</li>".format(
				_("{0}: {1}:1 (minimum {2}:1)", context=self.doctype).format(
					frappe.utils.escape_html(entry["label"]),
					frappe.format(entry["ratio"], {"fieldtype": "Float", "precision": 1}),
					frappe.format(entry["minimum"], {"fieldtype": "Float", "precision": 1}),
				)
			)
			for entry in entries
		)
		frappe.msgprint(
			_("Saved. These colors are harder to read than the standard ones:")
			+ f"<ul>{lines}</ul>",
			title=_("Low Contrast"),
			indicator="orange",
		)

	def validate(self):
		# Values are written verbatim into the brand stylesheet: one that closes
		# the declaration would break the look of the whole platform. Base and
		# Advanced colors must also be hex, since their shades are computed.
		invalid = invalid_fields(self)
		if invalid:
			labels = ", ".join(_(self.meta.get_label(f), context=self.doctype) for f in invalid)
			frappe.throw(
				_("These colors are not valid CSS values: {0}").format(labels),
				title=_("Invalid Color"),
			)
		self.validate_expert_tokens()

	def validate_expert_tokens(self):
		names = [(row.token or "").strip() for row in self.get(EXPERT_TABLE) or []]
		duplicates = sorted({name for name in names if names.count(name) > 1})
		if duplicates:
			frappe.throw(
				_("These variables are set more than once: {0}").format(", ".join(duplicates)),
				title=_("Invalid Variable"),
			)

		before = self.get_doc_before_save()
		previous = set(expert_values(before)) if before else set()
		invalid, unknown_new, unknown_saved = check_expert_tokens(self, previous)
		if invalid:
			frappe.throw(
				_("These variables have a name or a value that cannot be used: {0}").format(", ".join(invalid)),
				title=_("Invalid Variable"),
			)
		if unknown_new:
			frappe.throw(
				_("These variables do not exist on the platform: {0}").format(", ".join(unknown_new)),
				title=_("Invalid Variable"),
			)
		if unknown_saved:
			frappe.msgprint(
				_(
					"These saved variables no longer exist on the platform, probably after an update: {0}. "
					"They are kept but have no effect."
				).format(", ".join(unknown_saved)),
				title=_("Variables Without Effect"),
				indicator="orange",
			)

# Copyright (c) 2026, ELITE and contributors
# For license information, please see license.txt

import re

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint

SECRET_HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class EliteAPIKey(Document):
	def autoname(self):
		# The document name IS the public key prefix, so a presented key is
		# resolved with a primary-key lookup. Imported lazily: the service
		# module imports this doctype's name, not its controller.
		from os_lms.os_lms.elite_api.keys import new_key_prefix

		self.name = new_key_prefix()

	def validate(self):
		self.key_name = (self.key_name or "").strip()
		if not self.key_name:
			frappe.throw(_("The API key name is required."))
		if not SECRET_HASH_PATTERN.match(self.secret_hash or ""):
			frappe.throw(_("Invalid API key secret hash."))
		if not self.is_new():
			self.validate_immutable_after_creation()

	def validate_immutable_after_creation(self):
		"""A key's lifetime is fixed at creation: revoked or expired keys are replaced, never revived."""
		before = self.get_doc_before_save()
		if not before:
			return
		if not cint(before.enabled) and cint(self.enabled):
			frappe.throw(_("A revoked API key cannot be re-enabled. Create a new key instead."))
		if str(before.expires_on or "") != str(self.expires_on or ""):
			frappe.throw(_("The expiry date of an API key cannot be changed. Create a new key instead."))
		if before.secret_hash != self.secret_hash:
			frappe.throw(_("The secret of an API key cannot be changed. Create a new key instead."))

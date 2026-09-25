import frappe
from frappe import _

from lms.lms.doctype.lms_certificate.lms_certificate import LMSCertificate


class MissingFiscalIdError(frappe.ValidationError):
	# The SPA matches this class name (exc_type) to show the "add your fiscal
	# code" message, so keep it stable.
	pass


class CustomLMSCertificate(LMSCertificate):
	def validate(self):
		super().validate()
		self.validate_trueskills_fiscal_id()

	def validate_trueskills_fiscal_id(self):
		# TrueSkills requires the recipient's fiscal code, so a certificate for a
		# TrueSkills course cannot be created without it: the learner would get a
		# certificate whose badge can never be issued. Only new certificates are
		# checked, so existing ones stay editable.
		if not self.is_new() or not self.course or not self.member:
			return
		if not frappe.db.get_value("LMS Course", self.course, "trueskills_certificate_enabled"):
			return
		if (frappe.db.get_value("User", self.member, "codice_fiscale") or "").strip():
			return
		if self.member == frappe.session.user:
			message = _("Add your fiscal code to your profile to get the certificate for this course.")
		else:
			message = _("{0} has no fiscal code: the TrueSkills certificate cannot be issued.").format(
				frappe.bold(self.member)
			)
		frappe.throw(message, MissingFiscalIdError, title=_("Fiscal code missing"))

	def send_certification_email(self):
		# Courses that issue through TrueSkills do not produce the internal
		# completion certificate (the two are mutually exclusive per course), so
		# its "you are certified" email must not be sent — the learner receives
		# the TrueSkills badge instead.
		if self.course and frappe.db.get_value(
			"LMS Course", self.course, "trueskills_certificate_enabled"
		):
			return
		super().send_certification_email()

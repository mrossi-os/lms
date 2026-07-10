import frappe

from lms.lms.doctype.lms_certificate.lms_certificate import LMSCertificate


class CustomLMSCertificate(LMSCertificate):
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

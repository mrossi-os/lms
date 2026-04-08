import frappe

from os_lms.os_lms.trueskills.client import TrueSkillsError
from os_lms.os_lms.trueskills.service import TrueSkillsService


def issue_on_trueskills(doc, method):
	"""Mirror a freshly created LMS Certificate on TrueSkills.

	Runs in addition to the standard Frappe certificate flow. Errors are
	logged but never propagated, otherwise a downstream API failure would
	roll back the local certificate creation.
	"""
	try:
		service = TrueSkillsService()
		if not service.is_ready():
			return
		service.issue_certificate(doc)
	except TrueSkillsError as exc:
		frappe.log_error(
			title="TrueSkills certificate issuance failed",
			message=f"Certificate {doc.name}: {exc}",
		)
	except Exception:
		frappe.log_error(title="TrueSkills certificate issuance failed")

import frappe
from frappe import _

from lms.lms.doctype.lms_assignment_submission.lms_assignment_submission import PRIVILEGED_ROLES


def freeze_graded_submission(doc, method=None):
	"""validate hook on LMS Assignment Submission: once graded, only who grades saves it.

	The SPA and the mobile app stop editing when the status leaves "Not Graded", but the
	server did not (OWASP M-06): with frappe.client a student kept the Pass and replaced
	the answer and the attachment, or moved the graded submission to another assignment.
	"""
	if doc.is_new() or PRIVILEGED_ROLES & set(frappe.get_roles()):
		return
	previous = doc.get_doc_before_save()
	stored_status = previous.status if previous else frappe.db.get_value(doc.doctype, doc.name, "status")
	if stored_status and stored_status != "Not Graded":
		frappe.throw(
			_("This submission has already been graded and can no longer be changed."),
			frappe.PermissionError,
		)

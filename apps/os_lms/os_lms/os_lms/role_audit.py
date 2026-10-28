"""A trace of every Gestore, Docente and Valutatore role granted or revoked.

save_role and the batch valutatori sync write Has Role directly instead of saving
the User, so no Version row recorded who gave which role to whom. Each change
now writes an Activity Log row on the user's timeline: who (user), to whom
(reference_name), which role and when (subject, creation).
"""

import frappe
from frappe import _


def log_role_change(user: str, role: str, granted: bool) -> None:
	subject = (
		_("Role {0} granted to {1}") if granted else _("Role {0} revoked from {1}")
	).format(role, user)
	frappe.get_doc(
		{
			"doctype": "Activity Log",
			"subject": subject,
			"status": "Success",
			"user": frappe.session.user,
			"reference_doctype": "User",
			"reference_name": user,
		}
	).insert(ignore_permissions=True)

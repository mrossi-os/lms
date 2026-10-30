"""Acceptance of the privacy policy (ESG requirement, GDPR art. 7(1)).

When ``LMS Settings.privacy_policy_url`` is set, a new user accepts the policy
on the sign-up form (checked again in ``os_lms.os_lms.signup.sign_up``); anyone
without a recorded acceptance (existing accounts, imported or created by staff,
social login) gets a blocking dialog in the SPA after login, driven by
``privacy_consent_required`` in get_user_info.

What was accepted, when and where is kept on the User, so the controller can
show it; it goes with the account when the account is erased.
"""

import frappe
from frappe import _
from frappe.utils import now_datetime

EXEMPT_USERS = ("Administrator", "Guest")
FRAPPE_SIGNUP_TEMPLATE = "frappe/templates/signup.html"
SIGNUP_WITH_PRIVACY_TEMPLATE = "os_lms/templates/signup-privacy.html"


def get_privacy_policy_url() -> str:
	return (frappe.db.get_single_value("LMS Settings", "privacy_policy_url") or "").strip()


def is_consent_required(user: str) -> bool:
	if user in EXEMPT_USERS or not get_privacy_policy_url():
		return False
	return not frappe.db.get_value("User", user, "privacy_accepted_on")


def record_consent(user: str, via: str) -> None:
	frappe.db.set_value(
		"User",
		user,
		{
			"privacy_accepted_on": now_datetime(),
			"privacy_accepted_url": get_privacy_policy_url(),
			"privacy_accepted_via": via,
		},
		update_modified=False,
	)


def signup_form_template() -> str:
	"""hooks.signup_form_template, read last-app-wins by lms/www/login.py.
	Upstream picks lms's form when the site has custom sign-up content (we
	grafted the privacy box into it) and Frappe's own form otherwise; that
	one has no box, so with a policy URL it becomes os_lms's copy with the box.
	lms's form is not the default for the box: it is styled for lms's login page,
	not for os_lms's, where it renders unstyled."""
	from lms.plugins import show_custom_signup

	template = show_custom_signup()
	if template == FRAPPE_SIGNUP_TEMPLATE and get_privacy_policy_url():
		return SIGNUP_WITH_PRIVACY_TEMPLATE
	return template


@frappe.whitelist(methods=["POST"])
def accept_privacy_policy() -> dict:
	user = frappe.session.user
	if user in EXEMPT_USERS:
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	if not get_privacy_policy_url():
		return {"accepted": False}
	record_consent(user, "Login")
	return {"accepted": True}

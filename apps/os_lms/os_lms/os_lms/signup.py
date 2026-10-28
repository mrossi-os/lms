"""Sign-up guard in front of lms.lms.user.sign_up.

Upstream only warns past the hourly sign-up limit and still creates the user,
and tells anyone that an address is "already registered". This override blocks
for real (site-wide limit plus a per-IP one) and gives the same answer whether
or not the address has an account; the owner of an existing account gets an
email instead.
"""

import math

import frappe
from frappe import _
from frappe.utils import cint, get_url
from frappe.website.utils import is_signup_disabled
from lms.lms.user import sign_up as lms_sign_up

from os_lms.os_lms.email_utils import send_templated_email

SIGNUPS_PER_IP_PER_HOUR = 10
WINDOW_SECONDS = 60 * 60
ALREADY_REGISTERED_EMAIL_COOLDOWN_SECONDS = 60 * 60


@frappe.whitelist(allow_guest=True)  # nosemgrep: frappe-semgrep-rules.rules.security.guest-whitelisted-method
def sign_up(email: str, full_name: str, verify_terms: bool, user_category: str):
	if is_signup_disabled():
		frappe.throw(_("Sign Up is disabled"), _("Not Allowed"))

	if limited := _limit_message():
		return 0, limited

	user = frappe.db.get_value("User", {"email": email}, ["name", "enabled"], as_dict=True)
	if user:
		if user.enabled:
			_send_already_registered_email(user.name)
		return _check_your_email()

	code, message = lms_sign_up(email, full_name, verify_terms, user_category)
	if cint(code) == 0:
		# A concurrent sign-up for the same address won the race.
		return _check_your_email()
	return code, message


@frappe.whitelist(allow_guest=True)  # nosemgrep: frappe-semgrep-rules.rules.security.guest-whitelisted-method
def frappe_sign_up(email: str, full_name: str, redirect_to: str | None = None):
	"""Frappe's own sign-up, which no page of ours calls, routed through the guard
	above: it answered "Already Registered" and created users past the per-IP limit.
	redirect_to is dropped: the confirmation email leads to the LMS anyway."""
	return sign_up(email, full_name, verify_terms=False, user_category="")


def _check_your_email():
	return 1, _("Signup successful. Please check your email for verification.")


def _limit_message() -> str | None:
	max_per_hour = cint(frappe.get_system_settings("max_signups_allowed_per_hour") or 300)
	if frappe.db.get_creation_count("User", 60) >= max_per_hour:
		return _(
			"Too many users signed up recently, so the registration is disabled. Please try back in an hour"
		)

	# Every attempt counts, existing addresses included, or the per-IP limit
	# would not slow down probing for registered emails.
	key = frappe.cache.make_key(f"os_lms:signup:ip:{getattr(frappe.local, 'request_ip', None)}")
	attempts = frappe.cache.incrby(key, 1)
	if attempts == 1:
		frappe.cache.expire(key, WINDOW_SECONDS)
	if attempts > SIGNUPS_PER_IP_PER_HOUR:
		minutes = max(1, math.ceil(frappe.cache.ttl(key) / 60))
		return _("Too many sign-up attempts from your network. Please try again in {0} minutes.").format(
			minutes
		)
	return None


def _send_already_registered_email(user: str) -> None:
	# At most one per hour, so repeated sign-ups cannot flood the owner's inbox.
	cooldown_key = f"os_lms:signup:already_registered:{user}"
	if frappe.cache.get_value(cooldown_key):
		return
	frappe.cache.set_value(cooldown_key, 1, expires_in_sec=ALREADY_REGISTERED_EMAIL_COOLDOWN_SECONDS)

	app_name = (
		frappe.get_website_settings("app_name") or frappe.get_system_settings("app_name") or _("Frappe")
	)
	send_templated_email(
		template_key="signup_already_registered",
		recipients=user,
		subject=_("You already have an account on {0}").format(app_name),
		args={
			"app_name": app_name,
			"login_url": get_url("/login"),
			"reset_url": get_url("/login#forgot"),
		},
	)

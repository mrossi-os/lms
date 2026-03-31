# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE


from urllib.parse import urlparse

import frappe
import frappe.utils
from frappe import _
from frappe.apps import get_default_path
from frappe.core.doctype.navbar_settings.navbar_settings import get_app_logo
from frappe.utils import cint
from frappe.utils.data import escape_html
from frappe.utils.html_utils import get_icon_html
from frappe.utils.jinja import guess_is_path
from frappe.utils.oauth import get_oauth2_authorize_url, get_oauth_keys
from frappe.utils.password import get_decrypted_password
from frappe.website.utils import get_home_page

no_cache = True


def get_context(context):
	redirect_to = frappe.local.request.args.get("redirect-to")
	redirect_to = sanitize_redirect(redirect_to)

	if frappe.session.user != "Guest":
		if not redirect_to:
			if frappe.session.data.user_type == "Website User":
				redirect_to = get_default_path() or get_home_page()
			else:
				redirect_to = get_default_path() or "/desk"

		if redirect_to != "login":
			frappe.local.flags.redirect_location = redirect_to
			raise frappe.Redirect

	context.no_header = True
	context.for_test = "login.html"
	context["title"] = "Login"
	context["hide_login"] = True  # dont show login link on login page again.
	context["provider_logins"] = []
	context["disable_signup"] = cint(frappe.get_website_settings("disable_signup"))
	context["show_footer_on_login"] = cint(frappe.get_website_settings("show_footer_on_login"))
	context["disable_user_pass_login"] = cint(frappe.get_system_settings("disable_user_pass_login"))
	context["logo"] = get_app_logo()
	context["app_name"] = (
		frappe.get_website_settings("app_name") or frappe.get_system_settings("app_name") or _("Frappe")
	)

	signup_form_template = frappe.get_hooks("signup_form_template")
	if signup_form_template and len(signup_form_template):
		path = signup_form_template[-1]
		if not guess_is_path(path):
			path = frappe.get_attr(signup_form_template[-1])()
	else:
		path = "frappe/templates/signup.html"

	if path:
		context["signup_form_template"] = frappe.get_template(path).render()

	providers = frappe.get_all(
		"Social Login Key",
		filters={"enable_social_login": 1},
		fields=["name", "client_id", "base_url", "provider_name", "icon"],
		order_by="name",
	)

	for provider in providers:
		client_secret = get_decrypted_password(
			"Social Login Key", provider.name, "client_secret", raise_exception=False
		)
		if not client_secret:
			continue

		icon = None
		if provider.icon:
			if provider.provider_name == "Custom":
				icon = get_icon_html(provider.icon, small=True)
			else:
				icon = f"<img src={escape_html(provider.icon)!r} alt={escape_html(provider.provider_name)!r}>"

		if provider.client_id and provider.base_url and get_oauth_keys(provider.name):
			context.provider_logins.append(
				{
					"name": provider.name,
					"provider_name": provider.provider_name,
					"auth_url": get_oauth2_authorize_url(provider.name, redirect_to),
					"icon": icon,
				}
			)
			context["social_login"] = True

	if cint(frappe.db.get_value("LDAP Settings", "LDAP Settings", "enabled")):
		from frappe.integrations.doctype.ldap_settings.ldap_settings import LDAPSettings

		context["ldap_settings"] = LDAPSettings.get_ldap_client_settings()

	login_label = [_("Email")]

	if frappe.utils.cint(frappe.get_system_settings("allow_login_using_mobile_number")):
		login_label.append(_("Mobile"))

	if frappe.utils.cint(frappe.get_system_settings("allow_login_using_user_name")):
		login_label.append(_("Username"))

	context["login_label"] = f" {_('or')} ".join(login_label)

	context["login_with_email_link"] = frappe.get_system_settings("login_with_email_link")
	context["login_with_frappe_cloud_url"] = None

	return context


def sanitize_redirect(redirect: str | None) -> str | None:
	"""Only allow redirect on same domain.

	Allowed redirects:
	- Same host e.g. https://frappe.localhost/path
	- Just path e.g. /app gets converted to https://frappe.localhost/app
	"""
	if not redirect:
		return redirect

	parsed_redirect = urlparse(redirect)

	parsed_request_host = urlparse(frappe.local.request.url)
	output_parsed_url = parsed_redirect._replace(
		netloc=parsed_request_host.netloc, scheme=parsed_request_host.scheme
	)
	if parsed_redirect.netloc:
		if parsed_request_host.netloc != parsed_redirect.netloc:
			output_parsed_url = output_parsed_url._replace(path="/desk")
		else:
			output_parsed_url = output_parsed_url._replace(path=parsed_redirect.path)

	return output_parsed_url.geturl()

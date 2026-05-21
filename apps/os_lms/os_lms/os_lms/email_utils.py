"""Helpers for sending emails with optional desk-managed template overrides.

Each `template_key` corresponds to:
  - a file in `os_lms/templates/emails/{template_key}.html` (default fallback)
  - a field `{template_key}_template` on the singleton `OS LMS Email Settings`
    that links to an `Email Template` doctype to use instead.
"""

import frappe
from frappe.email.doctype.email_template.email_template import get_email_template


def _get_custom_template_name(template_key: str) -> str | None:
	fieldname = f"{template_key}_template"
	try:
		return frappe.db.get_single_value("OS LMS Email Settings", fieldname)
	except Exception:
		return None


def send_templated_email(
	template_key: str,
	recipients,
	subject: str,
	args: dict,
	**kwargs,
) -> None:
	"""Send an email, preferring a desk-managed `Email Template` when configured.

	Falls back to the file-based template at `templates/emails/{template_key}.html`.
	Extra keyword arguments are forwarded to `frappe.sendmail`.
	"""
	custom_template_name = _get_custom_template_name(template_key)

	if custom_template_name:
		email_template = get_email_template(custom_template_name, args)
		frappe.sendmail(
			recipients=recipients,
			subject=email_template.get("subject") or subject,
			content=email_template.get("message"),
			**kwargs,
		)
		return

	frappe.sendmail(
		recipients=recipients,
		subject=subject,
		template=template_key,
		args=args,
		**kwargs,
	)

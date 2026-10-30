"""Account deletion on request, reviewed by a Gestore (ESG, GDPR art. 12 and 17).

With ``LMS Settings.account_deletion_requires_review`` on, a user who is
neither a Gestore nor a System Manager does not delete their account: after
the same password or code check, ``account_deletion.delete_my_account`` files
an ``OS Account Deletion Request`` instead. The account stays active and the
user may withdraw the request. A Gestore (or an administrator) approves it,
which runs the same erasure as a direct deletion, or rejects it with a reason
that reaches the user by email. The decision is due within REVIEW_DAYS; past
that nothing happens on its own (client choice): the Gestori are reminded.

Once the account is erased the request stays as the record of the decision:
events/user.py empties its ``user`` (ROLE_LINK_FIELDS) instead of deleting it.
"""

import frappe
from frappe import _
from frappe.utils import add_days, cint, escape_html, get_url, getdate, now_datetime

REVIEW_DAYS = 60
# Remind this many days before the due date, on it, and every week past it.
REMIND_BEFORE_DAYS = 7
REMIND_EVERY_DAYS = 7
# Who deletes directly even with the review on, and who reviews the requests.
MANAGER_ROLES = {"Gestore", "System Manager"}
DOCTYPE = "OS Account Deletion Request"
REVIEW_PAGE = "/lms/account-deletion-requests"
MAX_REASON_LENGTH = 1000


def review_enabled() -> bool:
	return bool(cint(frappe.db.get_single_value("LMS Settings", "account_deletion_requires_review")))


def is_manager(user: str | None = None) -> bool:
	user = user or frappe.session.user
	return user == "Administrator" or bool(MANAGER_ROLES & set(frappe.get_roles(user)))


def has_requests_to_review() -> bool:
	"""Whether the review page has a place in the menu: the review is on, or
	requests filed before it was turned off still wait."""
	return review_enabled() or bool(frappe.db.exists(DOCTYPE, {"status": "Pending"}))


def needs_review(user: str) -> bool:
	return review_enabled() and not is_manager(user)


def get_pending(user: str) -> dict | None:
	return frappe.db.get_value(
		DOCTYPE,
		{"user": user, "status": "Pending"},
		["name", "requested_on", "due_on"],
		as_dict=True,
	)


def file_request(user: str) -> dict:
	"""The user's pending request, filed now if there is none."""
	if pending := get_pending(user):
		return pending
	requested_on = now_datetime()
	doc = frappe.get_doc(
		{
			"doctype": DOCTYPE,
			"user": user,
			"status": "Pending",
			"requested_on": requested_on,
			"due_on": add_days(getdate(requested_on), REVIEW_DAYS),
		}
	)
	doc.insert(ignore_permissions=True)
	_notify_managers(_("New account deletion request"), [doc])
	return {"name": doc.name, "requested_on": doc.requested_on, "due_on": doc.due_on}


@frappe.whitelist(methods=["POST"])
def withdraw_my_request() -> dict:
	user = frappe.session.user
	pending = get_pending(user)
	if not pending:
		frappe.throw(_("You have no pending account deletion request."))
	frappe.db.set_value(
		DOCTYPE, pending.name, {"status": "Withdrawn", "decided_on": now_datetime()}
	)
	return {"withdrawn": True}


def _assert_can_review() -> None:
	if not is_manager():
		frappe.throw(_("Not permitted"), frappe.PermissionError)


@frappe.whitelist(methods=["GET"])
def get_requests() -> dict:
	"""Pending requests, oldest due first, and the latest decisions."""
	_assert_can_review()
	fields = [
		"name",
		"user",
		"full_name",
		"status",
		"requested_on",
		"due_on",
		"decided_by",
		"decided_on",
		"rejection_reason",
	]
	pending = frappe.get_all(
		DOCTYPE, filters={"status": "Pending"}, fields=fields, order_by="due_on asc, creation asc"
	)
	decided = frappe.get_all(
		DOCTYPE,
		filters={"status": ["!=", "Pending"]},
		fields=fields,
		order_by="decided_on desc, creation desc",
		limit=50,
	)
	names = list({row.decided_by for row in decided if row.decided_by})
	deciders = {}
	if names:
		deciders = dict(
			frappe.get_all("User", filters={"name": ["in", names]}, fields=["name", "full_name"], as_list=True)
		)
	today = getdate()
	for row in pending:
		row.days_left = (getdate(row.due_on) - today).days
	for row in decided:
		row.decided_by_name = deciders.get(row.decided_by) or row.decided_by
	return {"pending": pending, "decided": decided, "review_days": REVIEW_DAYS}


def _pending_request(name: str):
	_assert_can_review()
	doc = frappe.get_doc(DOCTYPE, name)
	if doc.status != "Pending" or not doc.user:
		frappe.throw(_("This request has already been decided."))
	if doc.user == frappe.session.user:
		frappe.throw(_("You cannot decide on your own request."), frappe.PermissionError)
	return doc


@frappe.whitelist(methods=["POST"])
def approve_request(name: str) -> dict:
	from os_lms.os_lms.account_deletion import queue_erasure
	from os_lms.os_lms.override_api import PROTECTED_ACCOUNT_ROLES

	doc = _pending_request(name)
	# Same rule as deleting a member: a System Manager or a Gestore account is
	# deleted only by a System Manager.
	protected = PROTECTED_ACCOUNT_ROLES & set(frappe.get_roles(doc.user))
	if protected and "System Manager" not in frappe.get_roles():
		frappe.throw(_("This user cannot be deleted."), frappe.PermissionError)

	doc.status = "Approved"
	doc.decided_by = frappe.session.user
	doc.decided_on = now_datetime()
	doc.save(ignore_permissions=True)
	queue_erasure(doc.user)
	return {"approved": True}


@frappe.whitelist(methods=["POST"])
def reject_request(name: str, reason: str) -> dict:
	reason = (reason or "").strip() if isinstance(reason, str) else ""
	if not reason:
		frappe.throw(_("Enter the reason for the rejection: the user receives it by email."))
	if len(reason) > MAX_REASON_LENGTH:
		frappe.throw(_("The reason can be at most {0} characters long.").format(MAX_REASON_LENGTH))

	doc = _pending_request(name)
	doc.status = "Rejected"
	doc.decided_by = frappe.session.user
	doc.decided_on = now_datetime()
	doc.rejection_reason = reason
	doc.save(ignore_permissions=True)
	_send_rejection(doc)
	return {"rejected": True}


def _send_rejection(doc) -> None:
	user = frappe.db.get_value("User", doc.user, ["email", "full_name", "language"], as_dict=True)
	if not user or not user.email:
		return
	previous_lang = frappe.local.lang
	if user.language:
		frappe.local.lang = user.language
	try:
		frappe.sendmail(
			recipients=[user.email],
			subject=_("Your account deletion request was not accepted"),
			message=_(
				"Hello {0}, your request of {1} to delete your account was not accepted, for this reason:"
				"<br><br>{2}<br><br>Your account stays active. For questions, reply to this email or "
				"contact the platform managers."
			).format(
				escape_html(user.full_name or ""),
				frappe.utils.format_date(doc.requested_on),
				escape_html(doc.rejection_reason).replace("\n", "<br>"),
			),
		)
	finally:
		frappe.local.lang = previous_lang


def send_reminders() -> None:
	"""Daily (hooks.scheduler_events): remind the Gestori of the requests whose
	date is a week away, today, or a whole number of weeks past."""
	today = getdate()
	due = []
	pending = frappe.get_all(
		DOCTYPE, filters={"status": "Pending"}, fields=["name", "requested_on", "due_on", "last_reminder_on"]
	)
	for row in pending:
		if row.last_reminder_on and getdate(row.last_reminder_on) == today:
			continue
		days_left = (getdate(row.due_on) - today).days
		if days_left == REMIND_BEFORE_DAYS or (days_left <= 0 and -days_left % REMIND_EVERY_DAYS == 0):
			due.append(row)
	if not due:
		return
	_notify_managers(_("Account deletion requests waiting for a decision"), due)
	for row in due:
		frappe.db.set_value(DOCTYPE, row.name, "last_reminder_on", today, update_modified=False)
	frappe.db.commit()


def _notify_managers(subject: str, requests: list) -> None:
	"""Dates only, never who asked: the email outlives the account in Email
	Queue, and erase_user only clears the user's own messages there."""
	from os_lms.os_lms.security_alerts import alert_recipients

	recipients = alert_recipients()
	if not recipients:
		frappe.log_error(title="Account deletion request without recipients", message=subject)
		return
	today = getdate()
	rows = []
	for request in requests:
		days_left = (getdate(request.due_on) - today).days
		if days_left > 0:
			when = _("due in {0} days").format(days_left)
		elif days_left == 0:
			when = _("due today")
		else:
			when = _("overdue by {0} days").format(-days_left)
		requested = frappe.utils.format_date(request.requested_on)
		rows.append(f"<li>{_('Requested on {0}, {1}').format(requested, when)}</li>")
	link = get_url(REVIEW_PAGE)
	frappe.sendmail(
		recipients=recipients,
		subject=subject,
		message=_(
			"Some users asked to delete their account. Approve or reject each request within {0} days "
			"of the request:<ul>{1}</ul>Review them here: {2}"
		).format(REVIEW_DAYS, "".join(rows), f'<a href="{link}">{link}</a>'),
	)

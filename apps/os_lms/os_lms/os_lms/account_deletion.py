"""Self-service deletion of one's own account (ESG requirement, GDPR art. 17).

Deletion, not anonymisation: Frappe's Personal Data Deletion Request renames
the user to ``deleted-user-NNNN`` and keeps every record under that name, plus
the original email on the request itself, which is pseudonymisation and does
not satisfy an erasure request. Here everything the user owns is deleted for
good, everything they only acted on stays without their name, and nothing is
left behind in ``Deleted Document``.

Flow: the SPA asks how the user proves it is them (``start_account_deletion``:
their password, or a code by email for accounts without one), then calls
``delete_my_account``. The account is disabled and every session closed at
once; ``erase_user`` runs in a background job and sends a last email when done.

Any user may delete their own account, staff included; only Administrator
cannot. A teacher's courses, lessons and live classes belong to the client and
stay: ``os_lms.events.user.delete_lms_user_links`` (on_trash of User) deletes
the user's own LMS records and detaches them from everyone else's.
"""

import hashlib
import json
import re
import secrets

import frappe
from frappe import _
from frappe.rate_limiter import rate_limit
from frappe.utils import parse_addr, split_emails

CODE_TTL_SECONDS = 15 * 60
FORBIDDEN_USERS = ("Administrator", "Guest")

# Records the user wrote that the Link-based cascade cannot find: they name the
# user only in `owner`. A discussion topic other people answered stays (owner
# reassigned with everything else): deleting it would take their replies.
OWNED_RECORDS = ("Discussion Reply", "LMS Course Review")

# Frappe keeps these when a User is deleted (hooks.ignore_links_on_delete or no
# link at all), each with the user's email in it. (doctype, field) pairs.
LOG_RECORDS = (
	("Activity Log", "user"),
	("Activity Log", "owner"),
	("Access Log", "user"),
	("Route History", "user"),
	("Notification Log", "for_user"),
	("Comment", "comment_email"),
	("Comment", "owner"),
	("Communication", "user"),
	("Communication", "sender"),
	("Communication", "recipients"),
	("Contact", "email_id"),
	("Contact", "user"),
	("Personal Data Download Request", "user"),
	("User Invitation", "email"),
	("Permission Log", "for_document"),
	("Permission Log", "changed_by"),
)

# Fields that only say who created or last saved a record, not whom it is about.
AUTHORSHIP_FIELDS = ("owner", "modified_by")


def _code_key(user: str) -> str:
	return f"os_lms:account_deletion_code:{user}"


def _hash(code: str) -> str:
	return hashlib.sha256(code.encode()).hexdigest()


def _session_user() -> str:
	user = frappe.session.user
	if user in FORBIDDEN_USERS:
		frappe.throw(_("This account cannot be deleted."), frappe.PermissionError)
	return user


def _has_password(user: str) -> bool:
	return bool(
		frappe.db.sql(
			"SELECT 1 FROM `__Auth` WHERE doctype = 'User' AND name = %s AND fieldname = 'password'",
			user,
		)
	)


@frappe.whitelist(methods=["POST"])
@rate_limit(limit=5, seconds=60 * 60)
def start_account_deletion() -> dict:
	"""Tell the dialog how the user confirms. Accounts without a password
	(social login) get a one-time code by email instead."""
	user = _session_user()
	if _has_password(user):
		return {"method": "password"}

	code = f"{secrets.randbelow(10**6):06d}"
	frappe.cache.set_value(_code_key(user), _hash(code), expires_in_sec=CODE_TTL_SECONDS)
	frappe.sendmail(
		recipients=[frappe.db.get_value("User", user, "email") or user],
		subject=_("Code to delete your account"),
		message=_(
			"Your code to delete your account is <b>{0}</b>. It expires in {1} minutes. "
			"If you did not ask to delete your account, ignore this email and change your password."
		).format(code, CODE_TTL_SECONDS // 60),
		now=True,
	)
	return {"method": "code"}


@frappe.whitelist(methods=["POST"])
@rate_limit(limit=5, seconds=60 * 60)
def delete_my_account(secret: str) -> dict:
	"""Disable the account, close its sessions and queue the erasure."""
	user = _session_user()
	if not secret:
		frappe.throw(_("Enter your password to confirm."))

	if _has_password(user):
		# A plain ValidationError on purpose: Frappe answers an AuthenticationError
		# with 401 and clears the session cookies, so one typo would log out.
		try:
			from frappe.utils.password import check_password

			check_password(user, secret)
		except frappe.AuthenticationError:
			frappe.throw(_("The password is not correct."))
	else:
		expected = frappe.cache.get_value(_code_key(user))
		if not expected or not secrets.compare_digest(expected, _hash(secret.strip())):
			frappe.throw(_("The code is not correct or has expired."))
		frappe.cache.delete_value(_code_key(user))

	frappe.db.set_value("User", user, "enabled", 0, update_modified=False)
	frappe.local.login_manager.logout(user=user)
	from frappe.sessions import clear_sessions

	clear_sessions(user=user, force=True)
	# Queued last: logging out commits on its way, and a job queued before it
	# ran ahead of the "Force Logged out" Activity Log and left it behind.
	frappe.enqueue(
		"os_lms.os_lms.account_deletion.erase_user",
		queue="long",
		timeout=3000,
		enqueue_after_commit=True,
		user=user,
	)
	return {"queued": True}


def erase_user(user: str, notify: bool = True) -> None:
	"""Delete the user and every trace of them. Safe to run again on a user
	already gone: it then only sweeps what is left."""
	if user in FORBIDDEN_USERS:
		return
	frappe.set_user("Administrator")

	email = frappe.db.get_value("User", user, "email") or user
	full_name = frappe.db.get_value("User", user, "full_name")
	lang = frappe.db.get_value("User", user, "language")

	# delete_my_account already closed them; run from the console it has not,
	# and User.on_trash only logs out when a request is around. The logout
	# Activity Logs this writes go with the others below.
	from frappe.sessions import clear_sessions

	clear_sessions(user=user, force=True)

	_delete_owned_records(user)
	_delete_owned_topics(user)
	_delete_where("TrueSkills Issue Log", {"recipient_email": email})
	_delete_unattached_files(user)

	if frappe.db.exists("User", user):
		frappe.delete_doc("User", user, ignore_permissions=True, force=True, delete_permanently=True)

	_delete_logs(user, email)
	_reassign_ownership(user)
	_delete_email_queue(email)
	_clean_deleted_documents(user, email)
	# The global search index copies field values of indexed records (Contact,
	# Communication, ...); a kept record gets its row back on its next save.
	for needle in {user, email}:
		frappe.db.sql(
			"DELETE FROM `__global_search` WHERE content LIKE %s AND content REGEXP %s",
			(f"%{needle}%", _address_regexp(needle)),
		)
	_scrub_error_logs({user, email})
	frappe.db.commit()

	if notify:
		_send_goodbye(email, full_name, lang)


def _delete_owned_records(user: str) -> None:
	for doctype in OWNED_RECORDS:
		_delete_where(doctype, {"owner": user})


def _delete_owned_topics(user: str) -> None:
	for topic in frappe.get_all("Discussion Topic", filters={"owner": user}, pluck="name"):
		if not frappe.db.exists("Discussion Reply", {"topic": topic, "owner": ["!=", user]}):
			_delete_where("Discussion Reply", {"topic": topic})
			_delete("Discussion Topic", topic)


def _delete_unattached_files(user: str) -> None:
	# Files attached to a record go with it (or stay with a course the user
	# authored). Orphan uploads, e.g. images pasted in an answer, are the user's.
	# File's own on_trash removes the file from disk, so it is not skipped.
	for name in frappe.get_all(
		"File", filters={"owner": user, "attached_to_name": ["is", "not set"], "is_folder": 0}, pluck="name"
	):
		frappe.delete_doc("File", name, ignore_permissions=True, force=True, delete_permanently=True)


def _is_address(value: str | None, email: str) -> bool:
	return bool(value) and parse_addr(value)[1].lower() == email.lower()


def _lists_address(value: str | None, email: str) -> bool:
	return any(_is_address(part, email) for part in split_emails(value or ""))


def _delete_logs(user: str, email: str) -> None:
	for doctype, fieldname in LOG_RECORDS:
		if not frappe.db.exists("DocType", doctype):
			continue
		if fieldname in ("sender", "recipients"):
			# Address lists ("Name <a@b.it>, c@d.it"): LIKE finds candidates,
			# the exact match is checked here so a@b.it never takes ba@b.it.
			rows = frappe.get_all(
				doctype, filters={fieldname: ["like", f"%{email}%"]}, fields=["name", fieldname]
			)
			names = [row.name for row in rows if _lists_address(row[fieldname], email)]
		else:
			value = email if fieldname in ("comment_email", "email_id", "email") else user
			names = frappe.get_all(doctype, filters={fieldname: value}, pluck="name")
		_delete_all(doctype, names)
	frappe.db.delete("Version", {"ref_doctype": "User", "docname": user})
	frappe.db.delete("Comment", {"reference_doctype": "User", "reference_name": user})
	# A non-permanent delete_doc leaves a "Deleted" comment titled "<Doctype>
	# <name>": User.on_trash deletes the user's Notification Settings that way.
	for row in frappe.get_all(
		"Comment",
		filters={"comment_type": "Deleted", "subject": ["like", f"%{user}"]},
		fields=["name", "subject"],
	):
		if row.subject.rsplit(" ", 1)[-1] == user:
			frappe.db.delete("Comment", {"name": row.name})
	frappe.db.delete("DefaultValue", {"parent": user})
	frappe.db.set_value("Notification Log", {"from_user": user}, "from_user", None, update_modified=False)


def _reassign_ownership(user: str) -> None:
	"""`owner` and `modified_by` are plain text columns on every table: what
	the user created and stays (courses, lessons, graded work) keeps their email
	there. Same walk as frappe's User.after_rename, in one schema query."""
	columns = frappe.db.sql(
		"""
		SELECT TABLE_NAME AS tab, COLUMN_NAME AS col
		FROM information_schema.COLUMNS
		WHERE TABLE_SCHEMA = DATABASE() AND COLUMN_NAME IN ('owner', 'modified_by')
		""",
		as_dict=True,
	)
	for row in columns:
		frappe.db.sql(
			f"UPDATE `{row.tab}` SET `{row.col}` = 'Administrator' WHERE `{row.col}` = %s",
			user,
		)


def _delete_email_queue(email: str) -> None:
	queued = frappe.get_all("Email Queue Recipient", filters={"recipient": email}, pluck="parent")
	frappe.db.delete("Email Queue Recipient", {"recipient": email})
	for name in set(queued):
		if not frappe.db.exists("Email Queue Recipient", {"parent": name}):
			frappe.db.delete("Email Queue", {"name": name})
	sent_by_user = frappe.get_all(
		"Email Queue", filters={"sender": ["like", f"%{email}%"]}, fields=["name", "sender"]
	)
	for row in sent_by_user:
		if _is_address(row.sender, email):
			frappe.db.delete("Email Queue Recipient", {"parent": row.name})
			frappe.db.delete("Email Queue", {"name": row.name})


def _clean_deleted_documents(user: str, email: str) -> None:
	"""A Deleted Document about the user goes; one the user only created or
	saved (a teacher removed an enrollment) keeps its restore copy, with the
	authorship rewritten to Administrator."""
	frappe.db.delete("Deleted Document", {"deleted_name": user})
	needles = {user, email}
	candidates = frappe.get_all(
		"Deleted Document",
		or_filters=[["data", "like", f'%"{needle}"%'] for needle in needles],
		fields=["name", "data"],
	)
	for row in candidates:
		try:
			data = json.loads(row.data)
		except (TypeError, ValueError):
			continue
		if _mentions(data, needles):
			frappe.db.delete("Deleted Document", {"name": row.name})
		else:
			frappe.db.set_value(
				"Deleted Document", row.name, "data", json.dumps(data), update_modified=False
			)


def _mentions(node, needles: set[str]) -> bool:
	"""True when a value outside the authorship fields names the user; rewrites
	the authorship fields it walks past to Administrator."""
	if isinstance(node, list):
		return any([_mentions(item, needles) for item in node])
	if not isinstance(node, dict):
		return False
	about_user = False
	for key, value in node.items():
		if key in AUTHORSHIP_FIELDS and value in needles:
			node[key] = "Administrator"
		elif isinstance(value, str):
			about_user = about_user or value in needles
		else:
			about_user = _mentions(value, needles) or about_user
	return about_user


def _send_goodbye(email: str, full_name: str | None, lang: str | None) -> None:
	# Sent last and the queue row removed right after, so the address does not
	# outlive the account in Email Queue.
	if lang:
		frappe.local.lang = lang
	try:
		frappe.sendmail(
			recipients=[email],
			subject=_("Your account has been deleted"),
			message=_(
				"Hello {0}, your account and your personal data have been deleted as you asked. "
				"Badges already issued on TrueSkills stay on TrueSkills."
			).format(frappe.utils.escape_html(full_name or "")),
			now=True,
		)
	except Exception:
		frappe.log_error(title="Account deletion: goodbye email not sent")
	finally:
		_delete_email_queue(email)
		frappe.db.commit()


def _delete_where(doctype: str, filters: dict) -> None:
	if frappe.db.exists("DocType", doctype):
		_delete_all(doctype, frappe.get_all(doctype, filters=filters, pluck="name"))


def _delete_all(doctype: str, names: list[str]) -> None:
	for name in names:
		_delete(doctype, name)


def _delete(doctype: str, name: str) -> None:
	frappe.delete_doc(
		doctype,
		name,
		ignore_permissions=True,
		force=True,
		delete_permanently=True,
		ignore_on_trash=True,
	)


ERROR_LOG_TEXT_FIELDS = ("method", "error", "metadata")


def _scrub_error_logs(needles: set[str]) -> None:
	"""Error Log records the session user in `metadata` and sometimes in the
	traceback. The logs stay for whoever debugs the error; the address goes."""
	for needle in needles:
		pattern = re.compile(_address_regexp(needle))
		rows = frappe.get_all(
			"Error Log",
			or_filters=[[field, "like", f"%{needle}%"] for field in ERROR_LOG_TEXT_FIELDS],
			fields=["name", *ERROR_LOG_TEXT_FIELDS],
		)
		for row in rows:
			updates = {}
			for field in ERROR_LOG_TEXT_FIELDS:
				value = row[field]
				if value and pattern.search(value):
					updates[field] = pattern.sub(lambda m: m.group(1) + "[deleted user]" + m.group(2), value)
			if updates:
				frappe.db.set_value("Error Log", row.name, updates, update_modified=False)


def _address_regexp(needle: str) -> str:
	"""MariaDB REGEXP matching `needle` as a whole address, so that the LIKE
	that narrows the rows never takes a@b.it for xa@b.it."""
	edge = "[^A-Za-z0-9._%+-]"
	return f"(^|{edge}){re.escape(needle)}($|{edge})"


def find_traces(email: str, user: str | None = None) -> list[tuple[str, str]]:
	"""(table, column) pairs where `email` or `user` still appears in a text
	column. Read-only; the acceptance check of the tests, also handy from the
	console after a deletion."""
	needles = {email, user or email}
	columns = frappe.db.sql(
		"""
		SELECT TABLE_NAME AS tab, COLUMN_NAME AS col
		FROM information_schema.COLUMNS
		WHERE TABLE_SCHEMA = DATABASE()
		  AND DATA_TYPE IN ('varchar', 'text', 'mediumtext', 'longtext', 'json')
		""",
		as_dict=True,
	)
	found = []
	for row in columns:
		for needle in needles:
			if frappe.db.sql(
				f"SELECT 1 FROM `{row.tab}` WHERE `{row.col}` LIKE %s AND `{row.col}` REGEXP %s LIMIT 1",
				(f"%{needle}%", _address_regexp(needle)),
			):
				found.append((row.tab, row.col))
				break
	return found

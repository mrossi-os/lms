"""Draft state of an LMS Live Class.

Every class is inserted as a draft: the meeting and the calendar event exist, but the
students are not told and cannot see it. Publishing (`os_lms.os_lms.api.publish_live_class`)
sends the invitation and the in-app notification.

`status` is an os_lms Custom Field with no default: classes created before it existed
keep an empty status and count as published, so no data patch is needed.
"""

import frappe
from frappe.query_builder import Bracket

from lms.lms.permissions import authored_batch_condition, can_author_batch, is_site_administrator

DRAFT = "Draft"
PUBLISHED = "Published"

# Roles that see every live class of every batch, drafts included.
_ALL_CLASSES_ROLES = {"Moderator", "Docente", "Batch Evaluator"}


def is_draft(doc_or_status) -> bool:
	"""Whether a live class (doc, dict or bare status value) is a draft."""
	if isinstance(doc_or_status, dict) or hasattr(doc_or_status, "get"):
		doc_or_status = doc_or_status.get("status")
	return doc_or_status == DRAFT


def can_see_drafts(batch: str | None, user: str | None = None) -> bool:
	"""Who may see the drafts of `batch`: its authors (Moderator, Docente, site admin,
	tagged instructors/evaluators), the Batch Evaluator role and its Valutatori.
	Enrolled students may not."""
	from lms.lms.utils import is_batch_valutatore

	user = user or frappe.session.user
	if can_author_batch(batch, user=user):
		return True
	if "Batch Evaluator" in frappe.get_roles(user):
		return True
	return bool(batch) and bool(is_batch_valutatore(batch, user))


def has_permission(doc, ptype="read", user=None) -> bool:
	"""Controller hook: a draft exists only for the people who can see drafts.

	Returns True for anything else — a falsy return is a DENY in Frappe.
	"""
	if not is_draft(doc):
		return True
	user = user or frappe.session.user
	if user == "Administrator":
		return True
	return can_see_drafts(doc.get("batch_name"), user)


def query_conditions(user: str | None = None) -> str:
	"""List-read counterpart of `has_permission`: drafts drop out of a student's lists.

	ANDed by Frappe with the lms and Valutatore conditions on the same doctype.
	"""
	user = user or frappe.session.user
	if user == "Administrator" or is_site_administrator(user):
		return ""
	if _ALL_CLASSES_ROLES & set(frappe.get_roles(user)):
		return ""

	live_class = frappe.qb.DocType("LMS Live Class")
	authored = Bracket(authored_batch_condition(live_class.batch_name, user)).get_sql(
		with_namespace=True, quote_char="`" if frappe.db.db_type == "mariadb" else '"'
	)
	escaped = frappe.db.escape(user)
	return f"""(ifnull(`tabLMS Live Class`.status, '') != {frappe.db.escape(DRAFT)}
		or {authored}
		or `tabLMS Live Class`.batch_name in (
			select parent from `tabLMS Batch Valutatore`
			where parenttype = 'LMS Batch' and valutatore = {escaped}
		))"""

"""LMS Certificate scoped to the courses a staff member teaches.

Upstream lets every Course Creator, and so every Docente, create, change or revoke
any certificate, even for someone never enrolled, and list them all; on a
TrueSkill course the insert issues the external badge. Frappe ANDs these hooks
with upstream's, so they only narrow:

- Moderator and site administrators keep everything;
- the other staff reach a certificate of a course (or a batch, for a certificate
  with no course) they are listed instructor of, or the ones upstream's evaluator
  rule gives them; they read published certificates as anyone does;
- a certificate with neither course nor batch is left to Moderator and System Manager;
- learners are not touched: upstream decides for them.
"""

import frappe
from lms.lms.doctype.lms_certificate.lms_certificate import evaluates_certificate, is_assigned_evaluator
from lms.lms.permissions import is_site_administrator

STAFF_ROLES = {"Course Creator", "Batch Evaluator", "Docente"}
READ_PTYPES = ("read", "select", "print")


def has_permission(doc, ptype="read", user=None):
	user = user or frappe.session.user
	if not _is_scoped_staff(user):
		return True
	if ptype in READ_PTYPES and (doc.published or doc.member == user):
		return True

	stored = None
	if not doc.is_new():
		stored = frappe.db.get_value(
			"LMS Certificate", doc.name, ["course", "batch_name", "member", "published"], as_dict=True
		)
	if ptype in READ_PTYPES and stored and (stored.published or stored.member == user):
		return True

	# Both the row as stored and as sent: an instructor must not re-home another
	# course's certificate into theirs, nor theirs into another course.
	rows = [doc] + ([stored] if stored else [])
	if all(_teaches(row.course, row.batch_name, user) for row in rows):
		return True
	if ptype in READ_PTYPES:
		return bool(stored) and evaluates_certificate(stored.course, stored.batch_name, stored.member, user)
	return is_assigned_evaluator(doc, ptype, user)


def get_permission_query_conditions(user=None, doctype=None):
	user = user or frappe.session.user
	if not _is_scoped_staff(user):
		return None
	user_sql = frappe.db.escape(user)
	return f"""(`tabLMS Certificate`.published = 1
		or `tabLMS Certificate`.member = {user_sql}
		or `tabLMS Certificate`.evaluator = {user_sql}
		or (ifnull(`tabLMS Certificate`.course, '') != '' and `tabLMS Certificate`.course in (
			select parent from `tabCourse Instructor`
			where parenttype = 'LMS Course' and instructor = {user_sql}))
		or (ifnull(`tabLMS Certificate`.course, '') = '' and `tabLMS Certificate`.batch_name in (
			select parent from `tabCourse Instructor`
			where parenttype = 'LMS Batch' and instructor = {user_sql}))
		or `tabLMS Certificate`.batch_name in (
			select parent from `tabBatch Course`
			where parenttype = 'LMS Batch' and evaluator = {user_sql}))"""


def _is_scoped_staff(user: str) -> bool:
	roles = set(frappe.get_roles(user))
	if is_site_administrator(user) or "Moderator" in roles:
		return False
	return bool(roles & STAFF_ROLES)


def _teaches(course, batch_name, user) -> bool:
	"""Listed instructor of the certificate's course, or of its batch when it has no
	course. The Docente's global instructor rule does not apply here (client
	decision of 28/10): it teaches the courses it is listed on."""
	if course:
		parent, parenttype = course, "LMS Course"
	elif batch_name:
		parent, parenttype = batch_name, "LMS Batch"
	else:
		return False
	return bool(
		frappe.db.exists(
			"Course Instructor", {"parent": parent, "parenttype": parenttype, "instructor": user}
		)
	)

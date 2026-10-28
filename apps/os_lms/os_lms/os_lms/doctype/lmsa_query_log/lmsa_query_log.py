# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class LMSAQueryLog(Document):
	pass


# The log holds the students' questions to the AI tutor. Only the server writes
# it (ai/tutor/tutor_ai.py); a Course Creator reads the rows of the courses it
# teaches, and only these roles read every course.
ROLES_WITH_FULL_ACCESS = {"System Manager", "Moderator"}
READ_PTYPES = {"read", "print", "report", "export"}


def _has_full_access(user: str) -> bool:
	return user == "Administrator" or bool(ROLES_WITH_FULL_ACCESS & set(frappe.get_roles(user)))


def get_permission_query_conditions(user: str | None = None) -> str:
	user = user or frappe.session.user
	if _has_full_access(user):
		return ""
	instructor = frappe.db.escape(user, percent=False)
	return (
		"`tabLMSA Query Log`.course in (select parent from `tabCourse Instructor`"
		f" where parenttype = 'LMS Course' and instructor = {instructor})"
	)


def has_permission(doc, ptype: str = "read", user: str | None = None) -> bool:
	user = user or frappe.session.user
	if _has_full_access(user):
		return True
	return (
		ptype in READ_PTYPES
		and bool(doc.course)
		and bool(
			frappe.db.exists(
				"Course Instructor", {"parenttype": "LMS Course", "parent": doc.course, "instructor": user}
			)
		)
	)

# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class LMSASimulationTurn(Document):
	pass


def get_permission_query_conditions(user: str | None = None) -> str:
	"""Delegate list filtering to the parent Session: a turn is visible iff
	its session is visible to the user."""
	user = user or frappe.session.user
	if user == "Administrator":
		return ""

	from os_lms.os_lms.doctype.lmsa_simulation_session.lmsa_simulation_session import (
		get_permission_query_conditions as session_filter,
	)
	parent_cond = session_filter(user)
	if parent_cond == "":
		return ""
	if parent_cond == "1=0":
		return "1=0"
	# The parent condition references `tabLMSA Simulation Session`.<col> — those
	# references remain valid inside a subquery on the same table.
	return (
		f"`tabLMSA Simulation Turn`.session IN ("
		f"SELECT name FROM `tabLMSA Simulation Session` "
		f"WHERE {parent_cond})"
	)


def has_permission(doc, ptype: str = "read", user: str | None = None) -> bool:
	"""Defer to the parent Session's has_permission."""
	user = user or frappe.session.user
	if user == "Administrator":
		return True
	if not doc.session:
		return False
	from os_lms.os_lms.doctype.lmsa_simulation_session.lmsa_simulation_session import (
		has_permission as session_has_permission,
	)
	try:
		session_doc = frappe.get_doc("LMSA Simulation Session", doc.session)
	except frappe.DoesNotExistError:
		return False
	return session_has_permission(session_doc, ptype="read", user=user)

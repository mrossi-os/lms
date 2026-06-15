"""Authorization helpers shared by every eval API endpoint.

Instructor membership is delegated to ``lms.lms.utils.is_instructor`` so the
definition stays in sync with the rest of the LMS app.
"""
from __future__ import annotations

import frappe

from lms.lms.utils import is_instructor


def require_scenario_access(scenario_name: str) -> None:
	"""Raise frappe.PermissionError if the current user can neither read
	the scenario as its owner nor as an instructor of its course."""
	user = frappe.session.user
	if user == "Administrator":
		return
	if not frappe.db.exists("LMSA Simulation Scenario", scenario_name):
		frappe.throw(
			f"Scenario {scenario_name} not found",
			exc=frappe.DoesNotExistError,
		)
	owner = frappe.db.get_value(
		"LMSA Simulation Scenario", scenario_name, "owner"
	)
	if owner == user:
		return
	course = frappe.db.get_value(
		"LMSA Simulation Scenario", scenario_name, "lms_course"
	)
	if course and is_instructor(course):
		return
	raise frappe.PermissionError(
		f"User {user} is not allowed to access scenario {scenario_name}"
	)


def require_session_access(session_name: str) -> None:
	"""Same as require_scenario_access but starting from a session id."""
	user = frappe.session.user
	if user == "Administrator":
		return
	if not frappe.db.exists("LMSA Simulation Session", session_name):
		frappe.throw(
			f"Session {session_name} not found",
			exc=frappe.DoesNotExistError,
		)
	scenario = frappe.db.get_value(
		"LMSA Simulation Session", session_name, "scenario"
	)
	if scenario:
		require_scenario_access(scenario)

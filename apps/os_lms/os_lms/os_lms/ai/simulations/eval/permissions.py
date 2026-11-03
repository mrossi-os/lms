"""Authorization helpers shared by every eval API endpoint.

Who may manage or review simulations is decided in ``ai/simulations/access.py``
so the quality evaluations follow the same rules as the rest of the feature.
"""
from __future__ import annotations

import frappe

from os_lms.os_lms.ai.simulations import access


def require_scenario_access(scenario_name: str) -> None:
	"""Raise frappe.PermissionError unless the current user owns the scenario
	or manages the simulations of its course."""
	user = frappe.session.user
	if not frappe.db.exists("LMSA Simulation Scenario", scenario_name):
		frappe.throw(
			frappe._("Scenario {0} not found").format(scenario_name),
			exc=frappe.DoesNotExistError,
		)
	owner, course = frappe.db.get_value(
		"LMSA Simulation Scenario", scenario_name, ["owner", "lms_course"]
	)
	if owner == user or access.can_manage_course(course):
		return
	raise frappe.PermissionError(
		frappe._("User {0} is not allowed to access scenario {1}").format(
			user, scenario_name
		)
	)


def require_session_access(session_name: str) -> None:
	"""Raise frappe.PermissionError unless the session is the current user's
	own or one they may review (a Valutatore: only their students')."""
	if not frappe.db.exists("LMSA Simulation Session", session_name):
		frappe.throw(
			frappe._("Session {0} not found").format(session_name),
			exc=frappe.DoesNotExistError,
		)
	student, course = frappe.db.get_value(
		"LMSA Simulation Session", session_name, ["student", "course"]
	)
	if student == frappe.session.user or access.can_review(course, student):
		return
	raise frappe.PermissionError(
		frappe._("User {0} is not allowed to access session {1}").format(
			frappe.session.user, session_name
		)
	)


def require_evaluation_access(evaluation) -> None:
	"""Scenario access, plus review access to every real session the
	evaluation carries: its traces hold those students' transcripts."""
	require_scenario_access(evaluation.scenario)
	for session in {t.source_session for t in evaluation.traces or [] if t.source_session}:
		require_session_access(session)

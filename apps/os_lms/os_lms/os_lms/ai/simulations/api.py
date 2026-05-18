"""Whitelisted REST endpoints for the simulations feature.

URL prefix: /api/method/os_lms.os_lms.ai.simulations.api.<name>

The HTTP layer is a thin shell: it validates inputs, gates by permissions,
delegates to SessionOrchestrator, and returns plain dicts. Realtime events
are emitted by the orchestrator (frappe.publish_realtime), so the HTTP
response and the WebSocket stream stay in sync without extra glue.
"""
from __future__ import annotations

import frappe
from frappe import _

from lms.lms.utils import has_course_instructor_role, has_moderator_role, is_instructor

from .orchestrator import (
    QuotaExceededError,
    SessionOrchestrator,
    SessionTerminatedError,
)


def _service() -> SessionOrchestrator:
    return SessionOrchestrator()


def load_session(session_id: str):
    """Resolve a Session and gate access. Mirrors `load_lesson` in ai/api.py.

    Returns the Document on success. Throws PermissionError otherwise.
    """
    if not session_id or not frappe.db.exists("LMSA Simulation Session", session_id):
        frappe.throw(_("Simulation session not found"), frappe.DoesNotExistError)

    session = frappe.get_doc("LMSA Simulation Session", session_id)
    user = frappe.session.user

    if has_moderator_role():
        return session
    if user == session.student:
        return session
    if has_course_instructor_role() and session.course and is_instructor(session.course):
        return session

    frappe.throw(
        _("You don't have permission to access this simulation session"),
        frappe.PermissionError,
    )


def _resolve_published_scenario(scenario_id: str):
    """Load a Published scenario and gate by enrollment / instructor role."""
    if not scenario_id or not frappe.db.exists("LMSA Simulation Scenario", scenario_id):
        frappe.throw(_("Scenario not found"), frappe.DoesNotExistError)

    scenario = frappe.get_doc("LMSA Simulation Scenario", scenario_id)
    user = frappe.session.user

    if has_moderator_role():
        return scenario
    if has_course_instructor_role() and is_instructor(scenario.lms_course):
        return scenario
    if scenario.status != "Published":
        frappe.throw(
            _("Scenario {0} is not published").format(scenario.name),
            frappe.PermissionError,
        )
    if not frappe.db.exists(
        "LMS Enrollment", {"member": user, "course": scenario.lms_course}
    ):
        frappe.throw(
            _("You are not enrolled in the course owning this scenario"),
            frappe.PermissionError,
        )
    return scenario


# ----- Endpoints -----


@frappe.whitelist()
def start_session(scenario_id: str, modality: str = "chat") -> dict:
    """Create a Session for the current user and return the first customer turn."""
    if modality not in ("chat", "voice"):
        frappe.throw(_("Unsupported modality: {0}").format(modality))

    scenario = _resolve_published_scenario(scenario_id)
    try:
        result = _service().start_session(scenario_id=scenario.name, modality=modality)
    except QuotaExceededError as e:
        frappe.throw(str(e), frappe.ValidationError)
    return dict(result)


@frappe.whitelist()
def send_message(session_id: str, text: str) -> dict:
    """Append a user turn and return the assistant's reply."""
    if not text or not text.strip():
        frappe.throw(_("Message cannot be empty"))

    session = load_session(session_id)
    if session.student != frappe.session.user:
        frappe.throw(
            _("Only the session owner can send messages"), frappe.PermissionError
        )

    try:
        result = _service().send_message(session_id=session.name, user_text=text)
    except SessionTerminatedError:
        frappe.throw(
            _("This session is no longer accepting messages"), frappe.ValidationError
        )
    return dict(result)


@frappe.whitelist()
def end_session(session_id: str, reason: str = "completed") -> dict:
    """Mark a session as completed or abandoned."""
    if reason not in ("completed", "abandoned"):
        frappe.throw(_("Unsupported reason: {0}").format(reason))

    session = load_session(session_id)
    if session.student != frappe.session.user and not has_moderator_role():
        frappe.throw(_("Only the session owner can end the session"), frappe.PermissionError)

    return dict(_service().end_session(session_id=session.name, reason=reason))


@frappe.whitelist()
def get_session(session_id: str) -> dict:
    """Return session metadata + ordered list of turns."""
    session = load_session(session_id)
    turns = frappe.get_all(
        "LMSA Simulation Turn",
        filters={"session": session.name},
        fields=[
            "name",
            "turn_index",
            "role",
            "text_content",
            "latency_ms",
            "tokens_input",
            "tokens_output",
            "provider_used",
            "model_used",
            "injection_attempt_detected",
        ],
        order_by="turn_index asc",
    )
    return {
        "session": {
            "name": session.name,
            "scenario": session.scenario,
            "course": session.course,
            "modality": session.modality,
            "status": session.status,
            "started_at": str(session.started_at) if session.started_at else None,
            "ended_at": str(session.ended_at) if session.ended_at else None,
            "turn_count": session.turn_count,
            "generated_persona": session.generated_persona,
            "generated_situation": session.generated_situation,
            "chat_provider_used": session.chat_provider_used,
            "chat_model_used": session.chat_model_used,
        },
        "turns": turns,
    }


@frappe.whitelist()
def list_scenarios(course: str | None = None) -> list[dict]:
    """List Published scenarios accessible to the current user.

    - Students: scenarios of courses they are enrolled in.
    - Instructors of the course: all scenarios of that course (any status).
    - Moderator / sysadmin: all scenarios (filtered by `course` if provided).
    """
    user = frappe.session.user
    filters: dict = {}
    if course:
        filters["lms_course"] = course

    if has_moderator_role():
        return frappe.get_all(
            "LMSA Simulation Scenario",
            filters=filters,
            fields=["name", "scenario_name", "lms_course", "course_lesson", "difficulty", "modality", "status"],
            order_by="modified desc",
        )

    if has_course_instructor_role():
        # Restrict to courses the user instructs
        instructor_courses = frappe.get_all(
            "Course Instructor", filters={"instructor": user}, pluck="parent"
        )
        if course and course not in instructor_courses:
            instructor_courses = [c for c in instructor_courses if c == course]
        if instructor_courses:
            filters["lms_course"] = ["in", instructor_courses] if not course else course
            return frappe.get_all(
                "LMSA Simulation Scenario",
                filters=filters,
                fields=["name", "scenario_name", "lms_course", "course_lesson", "difficulty", "modality", "status"],
                order_by="modified desc",
            )

    # Student path: enrolled courses + Published scenarios
    enrolled = frappe.get_all(
        "LMS Enrollment", filters={"member": user}, pluck="course"
    )
    if not enrolled:
        return []
    filters["status"] = "Published"
    if course:
        if course not in enrolled:
            return []
    else:
        filters["lms_course"] = ["in", enrolled]
    return frappe.get_all(
        "LMSA Simulation Scenario",
        filters=filters,
        fields=["name", "scenario_name", "lms_course", "course_lesson", "difficulty", "modality"],
        order_by="modified desc",
    )

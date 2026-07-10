"""Shared test fixtures for the simulations test suite."""
from __future__ import annotations

import frappe

from os_lms.os_lms.ai.simulations.prompts import PersonaVariant, ScenarioVariant

CANNED_VARIANT = ScenarioVariant(
    situation="Anna ha appena visto un'offerta competitor del -20%.",
    student_brief="Il tuo compito è convincere Anna a confermare l'ordine.",
    persona=PersonaVariant(
        name="Anna",
        role="Head Buyer",
        context="Acme",
        mood="diffidente",
        key_objection="prezzo troppo alto",
        hidden_motivation="budget tagliato dal CFO",
    ),
)


def make_evaluation_schema(name: str = "Test Schema"):
    if frappe.db.exists("LMSA Evaluation Schema", name):
        frappe.delete_doc("LMSA Evaluation Schema", name, force=True, ignore_permissions=True)
    schema = frappe.new_doc("LMSA Evaluation Schema")
    schema.schema_name = name
    schema.scoring_scale = "0-10"
    schema.passing_threshold = 70
    schema.append("criteria", {"criterion_name": "Listening", "weight": 0.5})
    schema.append("criteria", {"criterion_name": "Closing", "weight": 0.5})
    schema.insert()
    return schema


def make_published_scenario(
    *,
    name: str = "Test Scenario",
    course: str | None = None,
    evaluation_schema: str | None = None,
):
    course = course or frappe.get_all("LMS Course", limit=1, pluck="name")[0]
    evaluation_schema = evaluation_schema or make_evaluation_schema().name
    if frappe.db.exists("LMSA Simulation Scenario", {"scenario_name": name}):
        for row in frappe.get_all("LMSA Simulation Scenario", filters={"scenario_name": name}, pluck="name"):
            frappe.delete_doc("LMSA Simulation Scenario", row, force=True, ignore_permissions=True)
    sc = frappe.new_doc("LMSA Simulation Scenario")
    sc.scenario_name = name
    sc.lms_course = course
    sc.difficulty = "medium"
    sc.modality = "chat"
    sc.roleplay_persona = "Cliente B2B."
    sc.situation_template = "Il cliente esita."
    sc.evaluation_schema = evaluation_schema
    sc.status = "Published"
    sc.insert()
    return sc


def enable_mock_provider():
    """Configure LMSA Settings so the chat provider resolves to MockProvider."""
    doc = frappe.get_single("LMSA Settings")
    doc.simulations_enabled = 1
    doc.simulation_chat_provider = "mock"
    doc.simulation_debrief_provider = "mock"
    doc.simulation_provider_default = "openai"  # never reached when chat=mock
    doc.save(ignore_permissions=True)
    frappe.db.commit()


def reset_settings():
    doc = frappe.get_single("LMSA Settings")
    doc.simulations_enabled = 0
    doc.simulation_chat_provider = "auto"
    doc.simulation_debrief_provider = "auto"
    doc.simulation_provider_default = "openai"
    doc.save(ignore_permissions=True)
    frappe.db.commit()


def cleanup_sessions_and_turns():
    for name in frappe.get_all("LMSA Simulation Turn", pluck="name"):
        frappe.delete_doc("LMSA Simulation Turn", name, force=True, ignore_permissions=True)
    for name in frappe.get_all("LMSA Simulation Session", pluck="name"):
        s = frappe.get_doc("LMSA Simulation Session", name)
        if s.docstatus == 1:
            try:
                s.cancel()
            except Exception:
                pass
        frappe.delete_doc("LMSA Simulation Session", name, force=True, ignore_permissions=True)
    frappe.db.commit()


def _make_test_user(prefix: str):
    """Create a User bypassing Frappe's per-minute creation throttle.

    The throttle (`throttle_user_creation`) trips after 60 user inserts
    in 60s — easy to hit when many tests in a row build fixture users.
    Tests don't care about the throttle so we flip `in_import` for the
    insert.
    """
    prev = frappe.flags.get("in_import")
    frappe.flags.in_import = True
    try:
        return frappe.get_doc({
            "doctype": "User",
            "email": f"{prefix}-{frappe.generate_hash(length=6)}@example.com",
            "first_name": prefix.title(),
            "send_welcome_email": 0,
        }).insert(ignore_permissions=True)
    finally:
        frappe.flags.in_import = prev


def make_scenario_with_instructor():
    """Returns (scenario_doc, instructor_user_doc, outsider_user_doc).

    Used by eval permission tests. Builds 2 users, 1 LMS Course with the
    first user listed in Course Instructor, and 1 LMSA Simulation Scenario
    published on that course via make_published_scenario.
    """
    instructor = _make_test_user("instr")
    outsider = _make_test_user("out")

    course = frappe.get_doc({
        "doctype": "LMS Course",
        "title": f"Eval Test Course {frappe.generate_hash(length=4)}",
        "short_introduction": "Eval test fixture course.",
        "description": "Eval test fixture course used by permission tests.",
        "instructors": [{"instructor": instructor.name}],
    }).insert(ignore_permissions=True)

    scenario = make_published_scenario(
        name=f"Eval Test Scenario {frappe.generate_hash(length=4)}",
        course=course.name,
    )

    return scenario, instructor, outsider


def make_completed_session(scenario=None, student: str | None = None):
    """Create a LMSA Simulation Session in Completed status with 2 turns.

    If no scenario is provided, builds one via make_published_scenario.
    If no student is provided, creates a fresh user so the orchestrator's
    daily simulation quota never bites tests that build many sessions.
    Returns the session doc.
    """
    scenario = scenario or make_published_scenario(
        name=f"Eval Session Scenario {frappe.generate_hash(length=4)}",
    )

    if student is None:
        student_doc = _make_test_user("student")
        student = student_doc.name

    session = frappe.get_doc({
        "doctype": "LMSA Simulation Session",
        "scenario": scenario.name,
        "course": scenario.lms_course,
        "student": student,
        "modality": "chat",
        "status": "Completed",
        "started_at": frappe.utils.now_datetime(),
    }).insert(ignore_permissions=True)

    for i, (role, text) in enumerate([
        ("user", "Buongiorno"),
        ("assistant", "Buongiorno a lei."),
    ]):
        frappe.get_doc({
            "doctype": "LMSA Simulation Turn",
            "session": session.name,
            "turn_index": i,
            "role": role,
            "text_content": text,
        }).insert(ignore_permissions=True)

    return session

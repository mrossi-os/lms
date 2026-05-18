"""Shared test fixtures for the simulations test suite."""
from __future__ import annotations

import frappe

from os_lms.os_lms.ai.simulations.prompts import PersonaVariant, ScenarioVariant

CANNED_VARIANT = ScenarioVariant(
    situation="Anna ha appena visto un'offerta competitor del -20%.",
    persona=PersonaVariant(
        name="Anna",
        role="Head Buyer",
        company="Acme",
        mood="diffidente",
        key_objection="prezzo troppo alto",
        hidden_motivation="budget tagliato dal CFO",
    ),
)


def make_rubric(name: str = "Test Rubric"):
    if frappe.db.exists("LMSA Evaluation Rubric", name):
        frappe.delete_doc("LMSA Evaluation Rubric", name, force=True, ignore_permissions=True)
    rubric = frappe.new_doc("LMSA Evaluation Rubric")
    rubric.rubric_name = name
    rubric.scoring_scale = "0-10"
    rubric.passing_threshold = 70
    rubric.append("criteria", {"criterion_name": "Listening", "weight": 0.5})
    rubric.append("criteria", {"criterion_name": "Closing", "weight": 0.5})
    rubric.insert()
    return rubric


def make_published_scenario(
    *,
    name: str = "Test Scenario",
    course: str | None = None,
    rubric: str | None = None,
):
    course = course or frappe.get_all("LMS Course", limit=1, pluck="name")[0]
    rubric = rubric or make_rubric().name
    if frappe.db.exists("LMSA Simulation Scenario", {"scenario_name": name}):
        for row in frappe.get_all("LMSA Simulation Scenario", filters={"scenario_name": name}, pluck="name"):
            frappe.delete_doc("LMSA Simulation Scenario", row, force=True, ignore_permissions=True)
    sc = frappe.new_doc("LMSA Simulation Scenario")
    sc.scenario_name = name
    sc.lms_course = course
    sc.difficulty = "medium"
    sc.modality = "chat"
    sc.customer_persona = "Cliente B2B."
    sc.situation_template = "Il cliente esita."
    sc.evaluation_rubric = rubric
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

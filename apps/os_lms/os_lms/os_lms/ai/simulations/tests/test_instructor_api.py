"""Tests for instructor-facing endpoints (DOC-4.*)."""
from __future__ import annotations

from unittest.mock import patch

import frappe
from frappe.tests import UnitTestCase

from os_lms.os_lms.ai.simulations import SessionOrchestrator
from os_lms.os_lms.ai.simulations.api import (
    delete_evaluation_schema,
    delete_scenario,
    get_evaluation_schema,
    get_scenario,
    get_transcript,
    instructor_report,
    instructor_review_debrief,
    list_my_evaluation_schemas,
    list_my_scenarios,
    save_evaluation_schema,
    save_scenario,
)
from os_lms.os_lms.ai.simulations.tasks import generate_debrief
from os_lms.os_lms.ai.utils.llm.provider import ChatResponse, Usage
from os_lms.os_lms.ai.utils.llm.providers.mock import MockProvider

from . import _fixtures as F


def _stub_generate_variant(self, scenario, seed, provider):
    return F.CANNED_VARIANT


VALID_DEBRIEF_JSON = (
    '{"overall_score":75,"criterion_scores":['
    '{"criterion":"Listening","score":8},'
    '{"criterion":"Closing","score":6}'
    '],"strengths":[{"title":"Empatia"}],'
    '"improvements":[{"title":"Closing diretto","suggestion":"Proponi un check-call"}],'
    '"behavioral_analysis":"Ottimo ritmo","recommended_content":[]}'
)


class _MockBase(UnitTestCase):
    """Sets up mock provider + scenario/schema + a Course Instructor link."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        F.cleanup_sessions_and_turns()
        for n in frappe.get_all("LMSA Simulation Debrief", pluck="name"):
            frappe.delete_doc("LMSA Simulation Debrief", n, force=True, ignore_permissions=True)
        F.enable_mock_provider()

        cls.course = frappe.get_all("LMS Course", limit=1, pluck="name")[0]

        # Make Administrator a Course Instructor of the test course so the
        # instructor-only endpoints accept the calls.
        cls._instructor_row = None
        existing = frappe.db.get_value(
            "Course Instructor",
            {"parent": cls.course, "instructor": "Administrator"},
            "name",
        )
        if not existing:
            row = frappe.get_doc(
                {
                    "doctype": "Course Instructor",
                    "parent": cls.course,
                    "parenttype": "LMS Course",
                    "parentfield": "instructors",
                    "instructor": "Administrator",
                }
            )
            row.insert(ignore_permissions=True)
            cls._instructor_row = row.name
            frappe.db.commit()

        cls.schema = F.make_evaluation_schema(name="Instructor Test Schema")
        cls.scenario = F.make_published_scenario(
            name="Instructor Test Scenario", evaluation_schema=cls.schema.name, course=cls.course
        )

    @classmethod
    def tearDownClass(cls):
        F.cleanup_sessions_and_turns()
        for n in frappe.get_all("LMSA Simulation Debrief", pluck="name"):
            frappe.delete_doc("LMSA Simulation Debrief", n, force=True, ignore_permissions=True)
        for n in frappe.get_all(
            "LMSA Simulation Scenario",
            filters={"scenario_name": ["like", "Instructor Test%"]},
            pluck="name",
        ):
            frappe.delete_doc("LMSA Simulation Scenario", n, force=True, ignore_permissions=True)
        for n in frappe.get_all(
            "LMSA Evaluation Schema",
            filters={"schema_name": ["like", "Instructor Test%"]},
            pluck="name",
        ):
            frappe.delete_doc("LMSA Evaluation Schema", n, force=True, ignore_permissions=True)
        if cls._instructor_row:
            frappe.delete_doc(
                "Course Instructor", cls._instructor_row, force=True, ignore_permissions=True
            )
            frappe.db.commit()
        F.reset_settings()
        super().tearDownClass()


class TestInstructorReview(_MockBase):
    def setUp(self):
        super().setUp()
        F.cleanup_sessions_and_turns()
        for n in frappe.get_all("LMSA Simulation Debrief", pluck="name"):
            frappe.delete_doc("LMSA Simulation Debrief", n, force=True, ignore_permissions=True)
        self._variant_patch = patch.object(
            SessionOrchestrator, "_generate_variant", _stub_generate_variant
        )
        self._variant_patch.start()
        self._orig_chat = MockProvider.chat

        def patched(slf, messages, *, system=None, model=None, temperature=0.7,
                    top_p=1.0, max_tokens=1024, stop=None,
                    response_format=None, stream=False, timeout=60.0):
            if response_format is not None and response_format.name == "debrief":
                return ChatResponse(
                    text=VALID_DEBRIEF_JSON,
                    finish_reason="stop",
                    usage=Usage(40, 60),
                    model=model or "mock-1",
                    provider="mock",
                    raw={"mock": True},
                )
            return self._orig_chat(
                slf, messages, system=system, model=model, temperature=temperature,
                top_p=top_p, max_tokens=max_tokens, stop=stop,
                response_format=response_format, stream=stream, timeout=timeout,
            )

        MockProvider.chat = patched

    def tearDown(self):
        MockProvider.chat = self._orig_chat
        self._variant_patch.stop()
        super().tearDown()

    def test_persists_review_with_author_and_timestamp(self):
        svc = SessionOrchestrator()
        start = svc.start_session(scenario_id=self.scenario.name)
        svc.end_session(session_id=start.session, reason="completed")
        generate_debrief(start.session)

        result = instructor_review_debrief(
            session_id=start.session,
            review="Bell'ascolto attivo, lavora sul closing diretto.",
        )
        self.assertIn("name", result)
        debrief = frappe.get_doc("LMSA Simulation Debrief", result["name"])
        self.assertEqual(debrief.instructor_reviewed_by, "Administrator")
        self.assertIsNotNone(debrief.instructor_reviewed_at)
        self.assertIn("ascolto", debrief.instructor_review)

    def test_empty_review_rejected(self):
        svc = SessionOrchestrator()
        start = svc.start_session(scenario_id=self.scenario.name)
        svc.end_session(session_id=start.session, reason="completed")
        generate_debrief(start.session)
        with self.assertRaises(frappe.exceptions.ValidationError):
            instructor_review_debrief(session_id=start.session, review="   ")


class TestInstructorReport(_MockBase):
    def setUp(self):
        super().setUp()
        F.cleanup_sessions_and_turns()
        for n in frappe.get_all("LMSA Simulation Debrief", pluck="name"):
            frappe.delete_doc("LMSA Simulation Debrief", n, force=True, ignore_permissions=True)
        self._variant_patch = patch.object(
            SessionOrchestrator, "_generate_variant", _stub_generate_variant
        )
        self._variant_patch.start()
        self._orig_chat = MockProvider.chat

        def patched(slf, messages, *, system=None, model=None, temperature=0.7,
                    top_p=1.0, max_tokens=1024, stop=None,
                    response_format=None, stream=False, timeout=60.0):
            if response_format is not None and response_format.name == "debrief":
                return ChatResponse(
                    text=VALID_DEBRIEF_JSON, finish_reason="stop", usage=Usage(40, 60),
                    model=model or "mock-1", provider="mock", raw={},
                )
            return self._orig_chat(
                slf, messages, system=system, model=model, temperature=temperature,
                top_p=top_p, max_tokens=max_tokens, stop=stop,
                response_format=response_format, stream=stream, timeout=timeout,
            )

        MockProvider.chat = patched

    def tearDown(self):
        MockProvider.chat = self._orig_chat
        self._variant_patch.stop()
        super().tearDown()

    def test_empty_report_when_no_sessions(self):
        report = instructor_report(course=self.course, period_days=7)
        self.assertEqual(report["kpi"]["total_sessions"], 0)
        self.assertEqual(report["sessions"], [])

    def test_report_aggregates_completed_session(self):
        svc = SessionOrchestrator()
        start = svc.start_session(scenario_id=self.scenario.name)
        svc.send_message(session_id=start.session, user_text="ok")
        svc.end_session(session_id=start.session, reason="completed")
        generate_debrief(start.session)

        report = instructor_report(course=self.course, period_days=7)
        self.assertEqual(report["kpi"]["total_sessions"], 1)
        self.assertEqual(report["kpi"]["completed_sessions"], 1)
        self.assertEqual(report["kpi"]["students_count"], 1)
        self.assertEqual(report["kpi"]["avg_score"], 75)
        self.assertEqual(report["sessions"][0]["overall_score"], 75)
        # top_improvement_titles must include the canned improvement
        titles = [r["title"] for r in report["top_improvement_titles"]]
        self.assertIn("Closing diretto", titles)


class TestScenarioCRUD(_MockBase):
    def setUp(self):
        super().setUp()
        for n in frappe.get_all(
            "LMSA Simulation Scenario", filters={"scenario_name": ["like", "CRUD%"]}, pluck="name"
        ):
            frappe.delete_doc("LMSA Simulation Scenario", n, force=True, ignore_permissions=True)
        frappe.db.commit()

    def test_save_creates_then_updates(self):
        r1 = save_scenario({
            "scenario_name": "CRUD Test 1",
            "lms_course": self.course,
            "difficulty": "easy",
            "modality": "chat",
            "status": "Draft",
            "roleplay_persona": "P",
            "situation_template": "S",
            "evaluation_schema": self.schema.name,
            "learning_objectives": [{"objective_text": "O1", "weight": 1.0}],
        })
        self.assertTrue(r1["name"])

        loaded = get_scenario(r1["name"])
        self.assertEqual(loaded["scenario_name"], "CRUD Test 1")
        self.assertEqual(len(loaded["learning_objectives"]), 1)

        r2 = save_scenario({**loaded, "status": "Published"})
        self.assertEqual(r1["name"], r2["name"])
        self.assertEqual(
            frappe.db.get_value("LMSA Simulation Scenario", r1["name"], "status"),
            "Published",
        )

    def test_list_my_scenarios_returns_instructor_courses(self):
        save_scenario({
            "scenario_name": "CRUD List",
            "lms_course": self.course,
            "difficulty": "medium",
            "modality": "chat",
            "status": "Draft",
            "roleplay_persona": "x",
            "situation_template": "y",
            "evaluation_schema": self.schema.name,
        })
        rows = list_my_scenarios(course=self.course)
        names = [r["scenario_name"] for r in rows]
        self.assertIn("CRUD List", names)

    def test_delete_scenario_without_sessions(self):
        r = save_scenario({
            "scenario_name": "CRUD Delete",
            "lms_course": self.course,
            "difficulty": "easy",
            "modality": "chat",
            "status": "Draft",
            "roleplay_persona": "x",
            "situation_template": "y",
            "evaluation_schema": self.schema.name,
        })
        delete_scenario(r["name"])
        self.assertFalse(frappe.db.exists("LMSA Simulation Scenario", r["name"]))


class TestEvaluationSchemaCRUD(_MockBase):
    def setUp(self):
        super().setUp()
        for n in frappe.get_all(
            "LMSA Evaluation Schema", filters={"schema_name": ["like", "SCH CRUD%"]}, pluck="name"
        ):
            frappe.delete_doc("LMSA Evaluation Schema", n, force=True, ignore_permissions=True)
        frappe.db.commit()

    def test_save_then_get(self):
        r = save_evaluation_schema({
            "schema_name": "SCH CRUD 1",
            "scoring_scale": "0-10",
            "passing_threshold": 60,
            "is_shared": 0,
            "criteria": [
                {"criterion_name": "A", "weight": 0.4, "description": "desc"},
                {"criterion_name": "B", "weight": 0.6},
            ],
        })
        loaded = get_evaluation_schema(r["name"])
        self.assertEqual(loaded["schema_name"], "SCH CRUD 1")
        self.assertEqual(len(loaded["criteria"]), 2)
        self.assertAlmostEqual(
            sum(c["weight"] for c in loaded["criteria"]), 1.0, places=2
        )

    def test_save_with_invalid_weights_raises(self):
        with self.assertRaises(frappe.exceptions.ValidationError):
            save_evaluation_schema({
                "schema_name": "SCH CRUD Bad",
                "scoring_scale": "0-10",
                "passing_threshold": 60,
                "criteria": [
                    {"criterion_name": "A", "weight": 0.3},
                    {"criterion_name": "B", "weight": 0.3},
                ],
            })

    def test_list_my_evaluation_schemas_includes_owned(self):
        save_evaluation_schema({
            "schema_name": "SCH CRUD Listed",
            "scoring_scale": "0-10",
            "passing_threshold": 70,
            "criteria": [{"criterion_name": "x", "weight": 1.0}],
        })
        rows = list_my_evaluation_schemas()
        self.assertTrue(any(r["schema_name"] == "SCH CRUD Listed" for r in rows))


class TestTranscript(_MockBase):
    def test_returns_session_and_turns_for_instructor(self):
        svc = SessionOrchestrator()
        start = svc.start_session(scenario_id=self.scenario.name)
        svc.send_message(session_id=start.session, user_text="Ciao")
        payload = get_transcript(session_id=start.session)
        self.assertEqual(payload["session"]["name"], start.session)
        self.assertGreaterEqual(len(payload["turns"]), 2)

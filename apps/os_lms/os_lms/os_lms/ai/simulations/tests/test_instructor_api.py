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
    instructor_override_score,
    instructor_report,
    instructor_reset_score,
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


# The overall score is computed from the criteria (equal weights in the
# fixture schema): 8 and 7 out of 10 give the same 75 the model writes.
VALID_DEBRIEF_JSON = (
    '{"overall_score":75,"criterion_scores":['
    '{"criterion":"Listening","score":8},'
    '{"criterion":"Closing","score":7}'
    '],"strengths":[{"title":"Empatia"}],'
    '"improvements":[{"title":"Closing diretto","suggestion":"Proponi un check-call"}],'
    '"behavioral_analysis":"Ottimo ritmo","recommended_content":[]}'
)


class _MockBase(UnitTestCase):
    """Sets up mock provider + scenario/schema + a Course Instructor link."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # end_session enqueues generate_debrief; a running dev worker would race
        # the tests on the same debrief rows. Tests call generate_debrief inline.
        cls._enqueue_patch = patch("frappe.enqueue")
        cls._enqueue_patch.start()
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
        cls._enqueue_patch.stop()
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


class TestInstructorScoreOverride(TestInstructorReview):
    """Human oversight: the instructor corrects the AI's overall score.

    The fixture schema passes at 70 and the mocked AI scores 75."""

    def _debrief_session(self) -> str:
        svc = SessionOrchestrator()
        start = svc.start_session(scenario_id=self.scenario.name)
        svc.end_session(session_id=start.session, reason="completed")
        generate_debrief(start.session)
        return start.session

    def _debrief(self, session_id: str):
        name = frappe.db.get_value(
            "LMSA Simulation Debrief", {"session": session_id}, "name"
        )
        return frappe.get_doc("LMSA Simulation Debrief", name)

    def test_ai_score_is_kept_in_its_own_field(self):
        debrief = self._debrief(self._debrief_session())
        self.assertEqual(debrief.ai_overall_score, 75)
        self.assertEqual(debrief.overall_score, 75)
        self.assertTrue(debrief.passed)

    def test_override_keeps_ai_score_records_author_and_recomputes_passed(self):
        session_id = self._debrief_session()
        result = instructor_override_score(
            session_id=session_id, score=60, reason="  Closing mai tentato.  "
        )
        self.assertEqual(result["overall_score"], 60)
        self.assertFalse(result["passed"])
        self.assertTrue(result["score_overridden"])
        self.assertEqual(result["ai_overall_score"], 75)

        debrief = self._debrief(session_id)
        self.assertEqual(debrief.overall_score, 60)
        self.assertEqual(debrief.ai_overall_score, 75)
        self.assertFalse(debrief.passed)
        self.assertEqual(debrief.score_override_reason, "Closing mai tentato.")
        self.assertEqual(debrief.score_overridden_by, "Administrator")
        self.assertIsNotNone(debrief.score_overridden_at)

    def test_override_of_debrief_older_than_ai_score_field_keeps_ai_score(self):
        # Debriefs written before ai_overall_score existed carry 0 there, not
        # NULL: Frappe creates Float columns as NOT NULL DEFAULT 0.
        session_id = self._debrief_session()
        name = self._debrief(session_id).name
        frappe.db.set_value("LMSA Simulation Debrief", name, "ai_overall_score", 0)
        frappe.db.commit()
        self.assertEqual(get_transcript(session_id=session_id)["debrief"]["ai_overall_score"], 75)

        result = instructor_override_score(session_id=session_id, score=60, reason="Rivisto")
        self.assertEqual(result["ai_overall_score"], 75)
        self.assertEqual(self._debrief(session_id).ai_overall_score, 75)
        self.assertEqual(instructor_reset_score(session_id=session_id)["overall_score"], 75)

    def test_second_override_does_not_touch_ai_score(self):
        session_id = self._debrief_session()
        instructor_override_score(session_id=session_id, score=60, reason="Primo")
        instructor_override_score(session_id=session_id, score=82, reason="Secondo")
        debrief = self._debrief(session_id)
        self.assertEqual(debrief.overall_score, 82)
        self.assertTrue(debrief.passed)
        self.assertEqual(debrief.ai_overall_score, 75)
        self.assertEqual(debrief.score_override_reason, "Secondo")

    def test_reason_is_required(self):
        session_id = self._debrief_session()
        with self.assertRaises(frappe.exceptions.ValidationError):
            instructor_override_score(session_id=session_id, score=60, reason="   ")
        self.assertEqual(self._debrief(session_id).overall_score, 75)

    def test_score_out_of_range_or_not_a_number_rejected(self):
        session_id = self._debrief_session()
        for bad in (-1, 100.5, "abc", float("nan")):
            with self.assertRaises(frappe.exceptions.ValidationError, msg=bad):
                instructor_override_score(session_id=session_id, score=bad, reason="x")
        self.assertEqual(self._debrief(session_id).overall_score, 75)

    def test_reset_goes_back_to_ai_score(self):
        session_id = self._debrief_session()
        instructor_override_score(session_id=session_id, score=60, reason="Troppo alto")
        result = instructor_reset_score(session_id=session_id)
        self.assertEqual(result["overall_score"], 75)
        self.assertTrue(result["passed"])
        self.assertFalse(result["score_overridden"])
        debrief = self._debrief(session_id)
        self.assertFalse(debrief.score_overridden_by)
        self.assertFalse(debrief.score_override_reason)

    def test_reset_without_override_rejected(self):
        session_id = self._debrief_session()
        with self.assertRaises(frappe.exceptions.ValidationError):
            instructor_reset_score(session_id=session_id)

    def test_regenerated_debrief_keeps_instructor_score(self):
        session_id = self._debrief_session()
        instructor_override_score(session_id=session_id, score=60, reason="Rivisto")
        generate_debrief(session_id)
        debrief = self._debrief(session_id)
        self.assertEqual(debrief.overall_score, 60)
        self.assertEqual(debrief.ai_overall_score, 75)
        self.assertFalse(debrief.passed)

    def test_transcript_shows_correction_to_instructor(self):
        session_id = self._debrief_session()
        instructor_override_score(session_id=session_id, score=60, reason="Rivisto")
        debrief = get_transcript(session_id=session_id)["debrief"]
        self.assertEqual(debrief["overall_score"], 60)
        self.assertEqual(debrief["ai_overall_score"], 75)
        self.assertEqual(debrief["score_override_reason"], "Rivisto")

    def test_non_instructor_cannot_override(self):
        session_id = self._debrief_session()
        frappe.set_user("Guest")
        try:
            with self.assertRaises(frappe.PermissionError):
                instructor_override_score(session_id=session_id, score=10, reason="x")
        finally:
            frappe.set_user("Administrator")
        self.assertEqual(self._debrief(session_id).overall_score, 75)


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

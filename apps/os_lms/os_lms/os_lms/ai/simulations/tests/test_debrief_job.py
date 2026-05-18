"""End-to-end tests for generate_debrief + get_debrief endpoint."""
from __future__ import annotations

import json
from unittest.mock import patch

import frappe
from frappe.tests import UnitTestCase

from os_lms.os_lms.ai.simulations import SessionOrchestrator
from os_lms.os_lms.ai.simulations.api import get_debrief
from os_lms.os_lms.ai.simulations.tasks import generate_debrief
from os_lms.os_lms.ai.utils.llm.provider import ChatResponse, Usage
from os_lms.os_lms.ai.utils.llm.providers.mock import MockProvider

from . import _fixtures as F


VALID_DEBRIEF_JSON = json.dumps({
    "overall_score": 82.5,
    "criterion_scores": [
        {"criterion": "Listening", "score": 9, "max_score": 10, "evidence_quote": "capisco"},
        {"criterion": "Closing", "score": 7, "max_score": 10},
    ],
    "strengths": [{"title": "Empatia", "detail": "Hai riconosciuto il timore."}],
    "improvements": [{"title": "Closing diretto", "suggestion": "Proponi un check-call"}],
    "behavioral_analysis": "Buon ritmo.",
    "recommended_content": [{"title": "Tecniche closing", "why": "Allenamento"}],
})


def _stub_generate_variant(self, scenario, seed, provider):
    return F.CANNED_VARIANT


class _DebriefMockBase(UnitTestCase):
    """Test base that patches MockProvider.chat to return a canned debrief JSON
    when response_format is requested. Restores the original chat() in teardown.
    """

    canned_debrief_text: str = VALID_DEBRIEF_JSON

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        F.cleanup_sessions_and_turns()
        for n in frappe.get_all("LMSA Simulation Debrief", pluck="name"):
            frappe.delete_doc("LMSA Simulation Debrief", n, force=True, ignore_permissions=True)
        F.enable_mock_provider()
        cls.rubric = F.make_rubric(name="Debrief Test Rubric")
        cls.scenario = F.make_published_scenario(
            name="Debrief Test Scenario", rubric=cls.rubric.name
        )

    @classmethod
    def tearDownClass(cls):
        F.cleanup_sessions_and_turns()
        for n in frappe.get_all("LMSA Simulation Debrief", pluck="name"):
            frappe.delete_doc("LMSA Simulation Debrief", n, force=True, ignore_permissions=True)
        for n in frappe.get_all(
            "LMSA Simulation Scenario", filters={"scenario_name": ["like", "Debrief Test%"]}, pluck="name"
        ):
            frappe.delete_doc("LMSA Simulation Scenario", n, force=True, ignore_permissions=True)
        for n in frappe.get_all(
            "LMSA Evaluation Rubric", filters={"rubric_name": ["like", "Debrief Test%"]}, pluck="name"
        ):
            frappe.delete_doc("LMSA Evaluation Rubric", n, force=True, ignore_permissions=True)
        F.reset_settings()
        super().tearDownClass()

    def setUp(self):
        super().setUp()
        F.cleanup_sessions_and_turns()
        for n in frappe.get_all("LMSA Simulation Debrief", pluck="name"):
            frappe.delete_doc("LMSA Simulation Debrief", n, force=True, ignore_permissions=True)
        self._variant_patch = patch.object(
            SessionOrchestrator, "_generate_variant", _stub_generate_variant
        )
        self._variant_patch.start()
        self._orig_mock_chat = MockProvider.chat
        canned = self.canned_debrief_text

        def patched_chat(slf, messages, *, system=None, model=None,
                         temperature=0.7, top_p=1.0, max_tokens=1024, stop=None,
                         response_format=None, stream=False, timeout=60.0):
            if response_format is not None and response_format.name == "debrief":
                return ChatResponse(
                    text=canned, finish_reason="stop", usage=Usage(50, 80),
                    model=model or "mock-1", provider="mock", raw={"mock": True},
                )
            return self._orig_mock_chat(
                slf, messages, system=system, model=model, temperature=temperature,
                top_p=top_p, max_tokens=max_tokens, stop=stop,
                response_format=response_format, stream=stream, timeout=timeout,
            )

        MockProvider.chat = patched_chat

    def tearDown(self):
        MockProvider.chat = self._orig_mock_chat
        self._variant_patch.stop()
        super().tearDown()


class TestDebriefJob(_DebriefMockBase):
    def _run_full_flow(self) -> str:
        """Start a session, send one user turn, end, and run the debrief inline."""
        svc = SessionOrchestrator()
        start = svc.start_session(scenario_id=self.scenario.name)
        svc.send_message(session_id=start.session, user_text="Buongiorno Anna")
        svc.end_session(session_id=start.session, reason="completed")
        return generate_debrief(start.session)

    def test_generate_debrief_creates_ready_doc(self):
        name = self._run_full_flow()
        debrief = frappe.get_doc("LMSA Simulation Debrief", name)
        self.assertEqual(debrief.status, "Ready")
        self.assertEqual(debrief.overall_score, 82.5)
        self.assertTrue(debrief.passed)  # threshold 70 in fixture rubric
        self.assertEqual(len(debrief.criterion_scores), 2)
        self.assertEqual(len(debrief.strengths), 1)
        self.assertEqual(len(debrief.improvements), 1)
        self.assertEqual(debrief.debrief_provider_used, "mock")

    def test_generate_debrief_is_idempotent(self):
        first = self._run_full_flow()
        # Re-running the job over the same session reuses the same Debrief doc.
        session_name = frappe.db.get_value("LMSA Simulation Debrief", first, "session")
        second = generate_debrief(session_name)
        self.assertEqual(first, second)

    def test_score_below_threshold_marks_not_passed(self):
        low_score = json.dumps({
            "overall_score": 40,
            "criterion_scores": [{"criterion": "Listening", "score": 4}],
            "strengths": [], "improvements": [],
            "behavioral_analysis": "",
            "recommended_content": [],
        })
        self.canned_debrief_text = low_score
        # Restart patch with new canned text
        MockProvider.chat = self._orig_mock_chat
        self.setUp()  # re-patch with the updated canned text

        try:
            name = self._run_full_flow()
            debrief = frappe.get_doc("LMSA Simulation Debrief", name)
            self.assertEqual(debrief.overall_score, 40.0)
            self.assertFalse(bool(debrief.passed))
        finally:
            # Restore default canned text for any subsequent test method.
            self.canned_debrief_text = VALID_DEBRIEF_JSON


class TestDebriefJobNeedsReview(_DebriefMockBase):
    canned_debrief_text = "not json at all"

    def test_parse_failure_marks_needs_review(self):
        svc = SessionOrchestrator()
        start = svc.start_session(scenario_id=self.scenario.name)
        svc.end_session(session_id=start.session, reason="completed")
        name = generate_debrief(start.session)
        debrief = frappe.get_doc("LMSA Simulation Debrief", name)
        self.assertEqual(debrief.status, "Needs Review")
        self.assertIn("not json", debrief.raw_llm_response)


class TestGetDebriefEndpoint(_DebriefMockBase):
    def test_returns_not_started_for_in_progress(self):
        svc = SessionOrchestrator()
        start = svc.start_session(scenario_id=self.scenario.name)
        payload = get_debrief(session_id=start.session)
        self.assertEqual(payload["status"], "not_started")

    def test_returns_pending_when_job_not_run_yet(self):
        svc = SessionOrchestrator()
        start = svc.start_session(scenario_id=self.scenario.name)
        svc.end_session(session_id=start.session, reason="completed")
        # The orchestrator enqueues; in tests it's a no-op so no row exists.
        # Remove anything that may have been auto-created by the enqueue path.
        for n in frappe.get_all(
            "LMSA Simulation Debrief", filters={"session": start.session}, pluck="name"
        ):
            frappe.delete_doc("LMSA Simulation Debrief", n, force=True, ignore_permissions=True)
        payload = get_debrief(session_id=start.session)
        self.assertEqual(payload["status"], "pending")

    def test_returns_full_payload_when_ready(self):
        svc = SessionOrchestrator()
        start = svc.start_session(scenario_id=self.scenario.name)
        svc.end_session(session_id=start.session, reason="completed")
        generate_debrief(start.session)

        payload = get_debrief(session_id=start.session)
        self.assertEqual(payload["status"], "ready")
        self.assertEqual(payload["overall_score"], 82.5)
        self.assertEqual(len(payload["criterion_scores"]), 2)
        self.assertTrue(payload["passed"])

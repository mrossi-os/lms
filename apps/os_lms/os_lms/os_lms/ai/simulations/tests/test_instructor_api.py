"""Tests for instructor-facing endpoints (DOC-4.*)."""
from __future__ import annotations

from unittest.mock import patch

import frappe
from frappe.tests import UnitTestCase

from os_lms.os_lms.ai.simulations import SessionOrchestrator
from os_lms.os_lms.ai.simulations.api import (
    _first_to_last_improvement,
    _mark_improvements,
    delete_evaluation_schema,
    delete_scenario,
    get_evaluation_schema,
    get_scenario,
    get_transcript,
    _serialize_debrief,
    instructor_discard_review,
    instructor_report,
    instructor_save_review,
    instructor_start_review,
    list_my_evaluation_schemas,
    list_my_scenarios,
    list_my_sessions,
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

    def _set_outcome_flag(self, value: int):
        frappe.db.set_value("LMSA Simulation Scenario", self.scenario.name, "has_human_outcome", value)
        self.addCleanup(
            frappe.db.set_value, "LMSA Simulation Scenario", self.scenario.name, "has_human_outcome", 0
        )

    @staticmethod
    def _edits(**overrides) -> dict:
        review = {
            "overall_score": 62,
            "criterion_scores": [
                {"criterion_name": "Listening", "score": 8, "note": "Buone domande"},
                {"criterion_name": "Closing", "score": 4.5, "note": "Mai chiesto l'impegno"},
            ],
            "strengths": [{"title": "Empatia", "detail": "Riconosce il problema"}],
            "improvements": [
                {"title": "Closing", "detail": "Chiudi", "suggestion": "Proponi una data"},
                {"title": "   ", "detail": "row without a title is dropped"},
            ],
            "comment": "  Buon lavoro, manca la chiusura.  ",
            "outcome": "",
            "outcome_reason": "",
        }
        review.update(overrides)
        return review


class TestTeacherVersion(TestInstructorReview):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Names come back as full names, which differ between sites
        cls.admin_name = frappe.db.get_value("User", "Administrator", "full_name") or "Administrator"

    """The teacher version of the debrief (ai/simulations/teacher_review.py)."""

    def test_start_copies_the_ai_version_as_a_draft(self):
        session_id = self._debrief_session()
        payload = instructor_start_review(session_id=session_id)
        version = payload["teacher_version"]
        self.assertEqual(version["status"], "draft")
        self.assertEqual(version["overall_score"], 75)
        self.assertEqual(
            [(c["criterion_name"], c["score"]) for c in version["criterion_scores"]],
            [("Listening", 8), ("Closing", 7)],
        )
        self.assertEqual([s["title"] for s in version["strengths"]], ["Empatia"])
        self.assertEqual(version["improvements"][0]["suggestion"], "Proponi un check-call")
        self.assertFalse(payload["outcome_required"])

        # Starting again keeps the teacher's edits
        instructor_save_review(session_id=session_id, review=self._edits())
        again = instructor_start_review(session_id=session_id)["teacher_version"]
        self.assertEqual(again["overall_score"], 62)

    def test_saving_changes_only_the_teacher_version(self):
        session_id = self._debrief_session()
        instructor_start_review(session_id=session_id)
        version = instructor_save_review(session_id=session_id, review=self._edits())["teacher_version"]
        self.assertEqual(version["overall_score"], 62)
        self.assertEqual(version["criterion_scores"][1]["score"], 4.5)
        self.assertEqual(version["criterion_scores"][1]["max_score"], 10)
        self.assertEqual([i["title"] for i in version["improvements"]], ["Closing"])
        self.assertEqual(version["comment"], "Buon lavoro, manca la chiusura.")
        self.assertEqual(version["edited_by_name"], self.admin_name)

        debrief = self._debrief(session_id)
        self.assertEqual(debrief.overall_score, 75)
        self.assertEqual([c.score for c in debrief.criterion_scores], [8, 7])
        self.assertEqual(debrief.improvements[0].title, "Closing diretto")
        self.assertEqual(debrief.review_status, "Draft")
        self.assertFalse(debrief.passed)

    def test_regenerated_debrief_keeps_the_teacher_version(self):
        session_id = self._debrief_session()
        instructor_start_review(session_id=session_id)
        instructor_save_review(session_id=session_id, review=self._edits())
        generate_debrief(session_id)
        debrief = self._debrief(session_id)
        self.assertEqual(debrief.overall_score, 75)
        self.assertEqual(debrief.review_overall_score, 62)

    def test_invalid_edits_are_rejected(self):
        session_id = self._debrief_session()
        with self.assertRaises(frappe.exceptions.ValidationError):
            instructor_save_review(session_id=session_id, review=self._edits())
        instructor_start_review(session_id=session_id)
        bad_edits = [
            {"overall_score": 100.5},
            {"overall_score": "abc"},
            {"criterion_scores": [{"criterion_name": "Listening", "score": 11}]},
            {"criterion_scores": [{"criterion_name": "Invented", "score": 5}]},
            {"criterion_scores": [
                {"criterion_name": "Closing", "score": 5},
                {"criterion_name": "Closing", "score": 6},
            ]},
            {"strengths": [{"title": "x" * 141}]},
            {"comment": "x" * 5001},
            {"outcome": "Passed"},  # the scenario has no outcome
        ]
        for edits in bad_edits:
            with self.assertRaises(frappe.exceptions.ValidationError, msg=edits):
                instructor_save_review(session_id=session_id, review=self._edits(**edits))
        self.assertEqual(self._debrief(session_id).review_overall_score, 75)

    def test_publishing_shows_it_to_the_student(self):
        session_id = self._debrief_session()
        instructor_start_review(session_id=session_id)
        instructor_save_review(session_id=session_id, review=self._edits())

        # A draft stays hidden: the student sees the AI version only
        student_view = _serialize_debrief(self._debrief(session_id), reviewer=False)
        self.assertIsNone(student_view["teacher_version"])
        self.assertEqual(student_view["review_state"], "not_reviewed")
        self.assertEqual(student_view["overall_score"], 75)

        version = instructor_save_review(
            session_id=session_id, review=self._edits(), publish=True
        )["teacher_version"]
        self.assertEqual(version["status"], "published")
        self.assertEqual(version["published_by_name"], self.admin_name)

        # Once published the student sees it whole, scores included (phase 6)
        student_view = _serialize_debrief(self._debrief(session_id), reviewer=False)
        self.assertEqual(student_view["review_state"], "published")
        self.assertEqual(student_view["teacher_version"]["status"], "published")
        self.assertEqual(student_view["teacher_version"]["overall_score"], 62)
        self.assertEqual(len(student_view["teacher_version"]["criterion_scores"]), 2)
        self.assertEqual(student_view["teacher_version"]["comment"], "Buon lavoro, manca la chiusura.")
        self.assertEqual(student_view["overall_score"], 75)

        # Later saves reach the student at once
        instructor_save_review(session_id=session_id, review=self._edits(comment="Rivisto"))
        self.assertEqual(self._debrief(session_id).review_status, "Published")
        student_view = _serialize_debrief(self._debrief(session_id), reviewer=False)
        self.assertEqual(student_view["teacher_version"]["comment"], "Rivisto")

    def test_attempts_show_the_published_teacher_score_or_the_ai_one(self):
        self._set_outcome_flag(1)
        first = self._debrief_session()
        second = self._debrief_session()
        frappe.db.set_value(
            "LMSA Simulation Session", first, "started_at", "2026-01-01 10:00:00"
        )
        instructor_start_review(session_id=second)
        instructor_save_review(
            session_id=second,
            review=self._edits(overall_score=82, outcome="Passed"),
            publish=True,
        )

        rows = {r["name"]: r for r in list_my_sessions(scenario=self.scenario.name)}
        self.assertEqual(
            (rows[first]["score"], rows[first]["score_source"], rows[first]["review_state"]),
            (75, "ai", "awaiting_outcome"),
        )
        self.assertEqual(rows[first]["outcome"], "")
        self.assertIsNone(rows[first]["improvement"])
        self.assertEqual(
            (rows[second]["score"], rows[second]["score_source"], rows[second]["outcome"]),
            (82, "teacher", "Passed"),
        )
        self.assertEqual(rows[second]["improvement"], 7)

    def test_only_improvements_above_five_points_are_shown(self):
        sessions = [
            {"scenario": "A", "started_at": "1", "score": 50},
            {"scenario": "A", "started_at": "2", "score": 55},  # +5: noise
            {"scenario": "A", "started_at": "3", "score": None},  # not scored yet
            {"scenario": "A", "started_at": "4", "score": 60.5},  # +5.5 on 55
            {"scenario": "A", "started_at": "5", "score": 40},  # a drop
            {"scenario": "B", "started_at": "6", "score": 90},  # other scenario
        ]
        _mark_improvements(sessions)
        self.assertEqual([s["improvement"] for s in sessions], [None, None, None, 5.5, None, None])

    def test_report_counts_teacher_scores_and_human_outcomes(self):
        self._set_outcome_flag(1)
        waiting = self._debrief_session()
        reviewed = self._debrief_session()
        frappe.db.set_value(
            "LMSA Simulation Session", waiting, "started_at", frappe.utils.add_to_date(
                frappe.utils.now_datetime(), hours=-1
            )
        )
        instructor_start_review(session_id=reviewed)
        instructor_save_review(
            session_id=reviewed,
            review=self._edits(overall_score=85, outcome="Passed"),
            publish=True,
        )

        report = instructor_report(course=self.course, period_days=7)
        kpi = report["kpi"]
        # Scores the students see: 75 (AI, waiting) and 85 (teacher)
        self.assertEqual(kpi["avg_score"], 80)
        self.assertEqual(kpi["reviewed"], {"count": 1, "ai_avg": 75, "teacher_avg": 85})
        self.assertEqual(kpi["outcomes"], {"decided": 1, "passed": 1, "rate": 100})
        self.assertEqual(kpi["to_evaluate"], 1)
        # Same student and scenario: first attempt 75, last 85
        self.assertEqual(kpi["improvement"], {"pairs": 1, "avg_gain": 10, "improved": 1})
        rows = {r["name"]: r for r in report["sessions"]}
        self.assertTrue(rows[waiting]["to_evaluate"])
        self.assertEqual(rows[reviewed]["outcome"], "Passed")
        self.assertEqual(rows[reviewed]["score_source"], "teacher")

    def test_first_to_last_improvement(self):
        def row(student, scenario, at, score):
            return {"student": student, "scenario": scenario, "started_at": at, "score": score}

        result = _first_to_last_improvement([
            row("a", "S", "3", 70), row("a", "S", "1", 50), row("a", "S", "2", 90),  # +20
            row("b", "S", "1", 60), row("b", "S", "2", 64),  # +4: not improved
            row("c", "S", "1", 80),  # one attempt only
            row("a", "T", "1", 40), row("a", "T", "2", None),  # one scored attempt only
        ])
        self.assertEqual(result, {"pairs": 2, "avg_gain": 12, "improved": 1})

    def test_the_student_waits_for_the_outcome_until_it_is_published(self):
        self._set_outcome_flag(1)
        session_id = self._debrief_session()
        instructor_start_review(session_id=session_id)
        instructor_save_review(
            session_id=session_id, review=self._edits(outcome="Passed")
        )
        student_view = _serialize_debrief(self._debrief(session_id), reviewer=False)
        self.assertEqual(student_view["review_state"], "awaiting_outcome")
        self.assertIsNone(student_view["teacher_version"])

        instructor_save_review(
            session_id=session_id, review=self._edits(outcome="Passed"), publish=True
        )
        student_view = _serialize_debrief(self._debrief(session_id), reviewer=False)
        self.assertEqual(student_view["review_state"], "published")
        self.assertEqual(student_view["teacher_version"]["outcome"], "Passed")

    def test_only_a_draft_can_be_discarded(self):
        session_id = self._debrief_session()
        instructor_start_review(session_id=session_id)
        instructor_save_review(session_id=session_id, review=self._edits())
        payload = instructor_discard_review(session_id=session_id)
        self.assertIsNone(payload["teacher_version"])
        debrief = self._debrief(session_id)
        self.assertFalse(debrief.review_status)
        self.assertFalse(debrief.review_criterion_scores)
        self.assertFalse(debrief.instructor_review)

        instructor_start_review(session_id=session_id)
        instructor_save_review(session_id=session_id, review=self._edits(), publish=True)
        with self.assertRaises(frappe.exceptions.ValidationError):
            instructor_discard_review(session_id=session_id)

    def test_outcome_is_needed_to_publish_on_a_simulation_with_outcome(self):
        self._set_outcome_flag(1)
        session_id = self._debrief_session()
        self.assertTrue(instructor_start_review(session_id=session_id)["outcome_required"])

        # A draft can wait for the decision
        instructor_save_review(session_id=session_id, review=self._edits())
        with self.assertRaises(frappe.exceptions.ValidationError):
            instructor_save_review(session_id=session_id, review=self._edits(), publish=True)
        with self.assertRaises(frappe.exceptions.ValidationError):
            instructor_save_review(
                session_id=session_id, review=self._edits(outcome="Not Passed"), publish=True
            )
        self.assertEqual(self._debrief(session_id).review_status, "Draft")

        version = instructor_save_review(
            session_id=session_id,
            review=self._edits(outcome="Not Passed", outcome_reason=" Nessuna chiusura "),
            publish=True,
        )["teacher_version"]
        self.assertEqual(version["outcome"], "Not Passed")
        self.assertEqual(version["outcome_reason"], "Nessuna chiusura")
        self.assertEqual(version["outcome_decided_by_name"], self.admin_name)
        self.assertFalse(self._debrief(session_id).passed)

        # Once published the outcome cannot be taken back to undecided
        with self.assertRaises(frappe.exceptions.ValidationError):
            instructor_save_review(session_id=session_id, review=self._edits())

    def test_passed_comes_from_the_published_outcome_only(self):
        self._set_outcome_flag(1)
        session_id = self._debrief_session()
        instructor_start_review(session_id=session_id)
        instructor_save_review(session_id=session_id, review=self._edits(outcome="Passed"))
        self.assertFalse(self._debrief(session_id).passed)

        instructor_save_review(session_id=session_id, review=self._edits(outcome="Passed"), publish=True)
        debrief = self._debrief(session_id)
        self.assertTrue(debrief.passed)
        self.assertEqual(debrief.outcome_decided_by, "Administrator")
        decided_at = debrief.outcome_decided_at

        # Editing other parts keeps who decided and when
        instructor_save_review(
            session_id=session_id, review=self._edits(outcome="Passed", comment="Altro")
        )
        self.assertEqual(self._debrief(session_id).outcome_decided_at, decided_at)

    def test_non_instructor_cannot_edit(self):
        session_id = self._debrief_session()
        frappe.set_user("Guest")
        try:
            with self.assertRaises(frappe.PermissionError):
                instructor_start_review(session_id=session_id)
        finally:
            frappe.set_user("Administrator")
        self.assertFalse(self._debrief(session_id).review_status)


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
        # No person decided an outcome: no pass rate (the AI never decides one)
        self.assertEqual(report["kpi"]["outcomes"], {"decided": 0, "passed": 0, "rate": None})
        self.assertEqual(report["kpi"]["to_evaluate"], 0)
        row = report["sessions"][0]
        self.assertEqual((row["score"], row["score_source"], row["ai_score"]), (75, "ai", 75))
        # top_improvement_titles must include the canned improvement
        titles = [r["title"] for r in report["top_improvement_titles"]]
        self.assertIn("Closing diretto", titles)

        # The teacher version copies the improvements into its own rows; the
        # report still counts the AI's once
        instructor_start_review(session_id=start.session)
        report = instructor_report(course=self.course, period_days=7)
        counts = {r["title"]: r["occurrences"] for r in report["top_improvement_titles"]}
        self.assertEqual(counts["Closing diretto"], 1)


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

    def test_outcome_flag_is_off_by_default_and_round_trips(self):
        base = {
            "scenario_name": "CRUD Outcome",
            "lms_course": self.course,
            "difficulty": "easy",
            "modality": "chat",
            "status": "Draft",
            "roleplay_persona": "P",
            "situation_template": "S",
            "evaluation_schema": self.schema.name,
        }
        r = save_scenario(base)
        self.assertEqual(get_scenario(r["name"])["has_human_outcome"], 0)

        # The editor's checkbox sends a boolean
        save_scenario({**base, "name": r["name"], "has_human_outcome": True})
        self.assertEqual(get_scenario(r["name"])["has_human_outcome"], 1)

        # A save without the field (older editor, JSON import) leaves it as is
        save_scenario({**base, "name": r["name"]})
        self.assertEqual(get_scenario(r["name"])["has_human_outcome"], 1)

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

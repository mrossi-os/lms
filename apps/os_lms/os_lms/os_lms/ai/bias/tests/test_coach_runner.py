"""Unit tests for the Coach bias-test runner (no LLM calls, no DB writes)."""
from __future__ import annotations

import json

from frappe.tests import UnitTestCase

from os_lms.os_lms.ai.bias import coach_runner
from os_lms.os_lms.ai.bias.dataset import OUTPUT_FILE
from os_lms.os_lms.ai.utils.llm.errors import LLMRateLimit
from os_lms.os_lms.ai.utils.llm.provider import ChatResponse, Usage

VALID = json.dumps({
    "overall_score": 72,
    "criterion_scores": [{"criterion": "Closing e prossimo passo", "score": 7, "max_score": 10,
                          "evidence_quote": None, "note": None}],
    "strengths": [], "improvements": [], "behavioral_analysis": "ok", "recommended_content": [],
})
SCHEMA = [{"name": "Closing e prossimo passo", "weight": 1.0}]


class _ScriptedProvider:
    """Replies with the given texts (or raises the given errors) in order."""

    name = "scripted"

    def __init__(self, *replies):
        self.replies = list(replies)
        self.calls = []

    def chat(self, messages, **kwargs):
        self.calls.append({"messages": messages, **kwargs})
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return ChatResponse(text=reply, finish_reason="stop", usage=Usage(10, 5), model="m", provider=self.name)


class TestCoachRunner(UnitTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.dataset = json.loads(OUTPUT_FILE.read_text())
        cls.prompt = json.loads(coach_runner.PROMPT_FILE.read_text())

    def test_jobs_use_the_snapshot_prompt_and_interleave_variants(self):
        jobs = coach_runner.build_jobs(self.dataset, self.prompt, repeats=2, cases=["c01", "c02"])
        self.assertEqual(len(jobs), 2 * 2 * 5)
        self.assertEqual(
            [(j["repeat"], j["case_id"], j["variant"]) for j in jobs[:6]],
            [(1, "c01", "A"), (1, "c01", "B"), (1, "c01", "C"), (1, "c01", "D"), (1, "c01", "E"), (1, "c02", "A")],
        )
        job = jobs[1]
        self.assertTrue(job["system"].startswith("Sei un coach esperto e formatore."))
        user = job["messages"][0]["content"]
        self.assertIn("Sales Transformation", user)
        self.assertIn("Piacere di conoscerla, sono Matteo.", user)
        self.assertNotIn("{{", job["system"] + user)

    def test_variants_differ_only_in_student_turns(self):
        jobs = coach_runner.build_jobs(self.dataset, self.prompt, repeats=1, cases=["c03"])
        systems = {j["system"] for j in jobs}
        self.assertEqual(len(systems), 1)
        users = {j["variant"]: j["messages"][0]["content"] for j in jobs}
        self.assertNotEqual(users["A"], users["B"])
        counterpart = [line for line in users["A"].splitlines() if "[CONTROPARTE]" in line]
        for text in users.values():
            self.assertEqual([line for line in text.splitlines() if "[CONTROPARTE]" in line], counterpart)

    def test_evaluate_parses_the_debrief(self):
        provider = _ScriptedProvider(VALID)
        record = coach_runner.evaluate(provider, "system", [{"role": "user", "content": "x"}], SCHEMA)
        # The overall score is computed from the criteria, as for the students;
        # the model's own 72 is kept beside it.
        self.assertEqual(
            (record["overall_score"], record["criteria"], record["retried"], record["error"], record["tokens"]),
            (70.0, {"Closing e prossimo passo": 70.0}, False, None, 15),
        )
        self.assertEqual((record["model_overall_score"], record["overall_method"]), (72.0, "weighted"))
        call = provider.calls[0]
        self.assertEqual((call["temperature"], call["max_tokens"], call["system"]), (0.2, 2000, "system"))

    def test_evaluate_retries_invalid_json_at_temperature_zero(self):
        provider = _ScriptedProvider("not json", VALID)
        record = coach_runner.evaluate(provider, "system", [{"role": "user", "content": "x"}], SCHEMA)
        self.assertEqual((record["overall_score"], record["retried"]), (70.0, True))
        retry = provider.calls[1]
        self.assertEqual(retry["temperature"], 0)
        self.assertEqual(retry["messages"][-1].content, coach_runner.RETRY_PROMPT)

    def test_evaluate_records_failures_instead_of_raising(self):
        provider = _ScriptedProvider("not json", "still not json")
        record = coach_runner.evaluate(provider, "system", [{"role": "user", "content": "x"}], SCHEMA)
        self.assertIsNone(record["overall_score"])
        self.assertTrue(record["error"].startswith("ValueError"))

    def test_evaluate_retries_transient_errors(self):
        coach_runner_sleep = coach_runner.time.sleep
        coach_runner.time.sleep = lambda seconds: None
        try:
            provider = _ScriptedProvider(LLMRateLimit("slow down"), VALID)
            record = coach_runner.evaluate(provider, "system", [{"role": "user", "content": "x"}], SCHEMA)
        finally:
            coach_runner.time.sleep = coach_runner_sleep
        self.assertEqual((record["overall_score"], len(provider.calls)), (70.0, 2))

    def test_report_renders(self):
        records = [
            {"case_id": f"c{i:02d}", "variant": var, "repeat": r, "overall_score": 60.0 + i + r,
             "criteria": {"Closing e prossimo passo": 60.0}, "criterion_max_scores": [10.0], "retried": False, "error": None, "tokens": 10}
            for i in range(3) for var in "ABCD" for r in (1, 2)
        ]
        records.append({"case_id": "c00", "variant": "B", "repeat": 3, "overall_score": None, "criteria": {},
                        "criterion_max_scores": [], "retried": True, "error": "ValueError: bad", "tokens": 0})
        results = {
            "run_id": "test", "date": "2026-11-02", "dataset": "d", "synthetic": True, "scenario": "SCN-0144",
            "passing_threshold": 70.0, "provider": "scripted", "model": "m",
            "prompt": {"source": "s", "version": "debrief.v1", "system_template_sha256": "a" * 64,
                       "user_template_sha256": "b" * 64},
            "temperature": 0.2, "repeats": 3, "elapsed_seconds": 1, "records": records,
        }
        results["analysis"] = coach_runner.analyse(results)
        report = coach_runner.render_report(results)
        self.assertIn("| B | 3 | +0.0 |", report)
        self.assertIn("entro le soglie", report)
        self.assertIn("c00 B #3: ValueError: bad", report)
        self.assertIn("| B | su 10: 6 |", report)
        self.assertIn("| origine del nome: D rispetto a B | 3 | +0.0 |", report)
        self.assertEqual(results["analysis"]["failed"], 1)

"""Unit tests for the evaluation pipeline."""
from __future__ import annotations

import json
from dataclasses import dataclass, field

from frappe.tests import UnitTestCase

from os_lms.os_lms.ai.utils.llm.provider import (
	ChatResponse, Usage,
)
from os_lms.os_lms.ai.simulations.eval.pipeline import evaluate_transcript
from os_lms.os_lms.ai.simulations.eval.types import (
	ScenarioRef, ALL_DIMENSIONS,
	DIMENSION_PERSONA, DIMENSION_COVERAGE, DIMENSION_DEBRIEF, DIMENSION_DIFFICULTY,
)


@dataclass
class FakeProvider:
	"""Mirrors LLMProvider.chat() shape: returns queued ChatResponse objects."""
	responses: list[str]
	calls: list[dict] = field(default_factory=list)
	name: str = "fake"

	def chat(self, messages, *, system=None, model=None, **kwargs):
		self.calls.append({"system": system, "messages": list(messages)})
		if not self.responses:
			raise AssertionError("FakeProvider exhausted")
		text = self.responses.pop(0)
		return ChatResponse(
			text=text,
			finish_reason="stop",
			usage=Usage(prompt_tokens=0, completion_tokens=0),
			model=model or "fake-1",
			provider="fake",
		)


_SCENARIO = ScenarioRef(
	name="SC-1", scenario_name="X",
	learning_objectives=["o1"], difficulty="medium",
	roleplay_persona="x", situation_template="y", max_turns=10,
)

_TRANSCRIPT = [
	{"turn_index": 0, "role": "user", "text": "ciao"},
	{"turn_index": 1, "role": "assistant", "text": "salve"},
]


def _ok(extra=None):
	base = {"score": 0.7, "summary": "ok", "evidence_quotes": []}
	if extra:
		base.update(extra)
	return json.dumps(base)


class TestPipeline(UnitTestCase):
	def test_runs_four_judges(self):
		provider = FakeProvider(responses=[
			_ok(),
			_ok({"by_objective": []}),
			_ok(),
			_ok({"calibration_offset": 0}),
		])
		scores = evaluate_transcript(
			transcript=_TRANSCRIPT,
			scenario=_SCENARIO,
			trace_kind="llm_student",
			provider=provider,
			debrief_payload={"overall_score": 50, "criterion_scores": []},
		)
		self.assertEqual(len(scores), 4)
		self.assertEqual({s.dimension for s in scores}, set(ALL_DIMENSIONS))
		self.assertEqual(len(provider.calls), 4)

	def test_skips_debrief_when_payload_missing(self):
		# 3 actual chat calls: persona, coverage, difficulty.
		# Debrief is skipped via skipped_score() — no provider call.
		provider = FakeProvider(responses=[
			_ok(),
			_ok({"by_objective": []}),
			_ok({"calibration_offset": 0}),
		])
		scores = evaluate_transcript(
			transcript=_TRANSCRIPT,
			scenario=_SCENARIO,
			trace_kind="production_session",
			provider=provider,
			debrief_payload=None,
		)
		debrief_score = next(s for s in scores if s.dimension == DIMENSION_DEBRIEF)
		self.assertIsNone(debrief_score.score)
		self.assertIn("debrief_missing", debrief_score.warnings)
		self.assertEqual(len(provider.calls), 3)

	def test_handles_judge_parse_failure(self):
		# Persona returns garbage → score=None, warnings=["judge_parse_error"];
		# the other three judges still run.
		provider = FakeProvider(responses=[
			"not json",                       # persona — parse fail
			_ok({"by_objective": []}),        # coverage — ok
			_ok(),                            # debrief — ok
			_ok({"calibration_offset": 0}),   # difficulty — ok
		])
		scores = evaluate_transcript(
			transcript=_TRANSCRIPT,
			scenario=_SCENARIO,
			trace_kind="llm_student",
			provider=provider,
			debrief_payload={"overall_score": 50, "criterion_scores": []},
		)
		persona_score = next(s for s in scores if s.dimension == DIMENSION_PERSONA)
		self.assertIsNone(persona_score.score)
		self.assertIn("judge_parse_error", persona_score.warnings)
		# Other three still got their score
		for dim in (DIMENSION_COVERAGE, DIMENSION_DEBRIEF, DIMENSION_DIFFICULTY):
			s = next(x for x in scores if x.dimension == dim)
			self.assertEqual(s.score, 0.7)

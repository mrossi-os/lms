"""Unit tests for the difficulty calibration judge."""
from __future__ import annotations

import json

from frappe.tests import UnitTestCase

from os_lms.os_lms.ai.simulations.eval.judges import difficulty as judge
from os_lms.os_lms.ai.simulations.eval.types import (
	DIMENSION_DIFFICULTY, ScenarioRef,
)


def _scenario(diff="medium"):
	return ScenarioRef(
		name="SC-1", scenario_name="X", learning_objectives=["o1"],
		difficulty=diff, customer_persona="x", situation_template="y",
		max_turns=20,
	)


class TestDifficultyJudge(UnitTestCase):
	def test_build_messages_includes_difficulty_and_score(self):
		_, msgs = judge.build_messages(
			transcript=[{"turn_index": 0, "role": "user", "text": "x"}],
			scenario=_scenario("hard"),
			trace_kind="llm_student",
			runtime_overall_score=85,
		)
		self.assertIn("hard", msgs[0]["content"])
		self.assertIn("85", msgs[0]["content"])

	def test_build_messages_handles_missing_score(self):
		_, msgs = judge.build_messages(
			transcript=[{"turn_index": 0, "role": "user", "text": "x"}],
			scenario=_scenario("easy"),
			trace_kind="llm_student",
			runtime_overall_score=None,
		)
		self.assertIn("non disponibile", msgs[0]["content"].lower())

	def test_parse_output_with_calibration(self):
		text = json.dumps({
			"score": 0.7,
			"summary": "Slightly harder than label",
			"evidence_quotes": [],
			"expected_difficulty": "medium",
			"perceived_difficulty": "medium-hard",
			"calibration_offset": 0.5,
		})
		result = judge.parse_output(text)
		self.assertEqual(result.dimension, DIMENSION_DIFFICULTY)
		self.assertEqual(result.score, 0.7)
		self.assertEqual(result.extras["calibration_offset"], 0.5)
		self.assertEqual(result.extras["perceived_difficulty"], "medium-hard")

	def test_judge_version(self):
		self.assertEqual(judge.JUDGE_VERSION, "difficulty.v1")

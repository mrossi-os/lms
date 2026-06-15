"""Unit tests for the difficulty calibration judge."""
from __future__ import annotations

import json

from frappe.tests import UnitTestCase

from os_lms.os_lms.ai.simulations.eval.judges import difficulty as judge
from os_lms.os_lms.ai.simulations.eval.types import (
	DIMENSION_DIFFICULTY, ScenarioRef,
)
from os_lms.os_lms.ai.utils.default_prompt import judge_difficulty as judge_default


def _scenario(diff="medium"):
	return ScenarioRef(
		name="SC-1", scenario_name="X", learning_objectives=["o1"],
		difficulty=diff, roleplay_persona="x", situation_template="y",
		max_turns=20,
	)


class TestDifficultyJudge(UnitTestCase):
	def test_build_user_message_includes_difficulty_and_score(self):
		content = judge.build_user_message(
			transcript=[{"turn_index": 0, "role": "user", "text": "x"}],
			scenario=_scenario("hard"),
			trace_kind="llm_student",
			runtime_overall_score=85,
		)
		self.assertIn("hard", content)
		self.assertIn("85", content)

	def test_build_user_message_handles_missing_score(self):
		content = judge.build_user_message(
			transcript=[{"turn_index": 0, "role": "user", "text": "x"}],
			scenario=_scenario("easy"),
			trace_kind="llm_student",
			runtime_overall_score=None,
		)
		self.assertIn("non disponibile", content.lower())

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
		self.assertEqual(judge_default.VERSION, "difficulty.v1")

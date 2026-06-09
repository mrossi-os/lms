"""Unit tests for the persona consistency judge."""
from __future__ import annotations

import json

from frappe.tests import UnitTestCase

from os_lms.os_lms.ai.simulations.eval.judges import persona
from os_lms.os_lms.ai.simulations.eval.types import (
	DimensionScore,
	DIMENSION_PERSONA,
	ScenarioRef,
)


def _scenario():
	return ScenarioRef(
		name="SC-1",
		scenario_name="Negoziazione",
		learning_objectives=["o1"],
		difficulty="medium",
		roleplay_persona="42 anni, dirigente, scettico",
		situation_template="Cliente competitor.",
		max_turns=20,
	)


class TestPersonaJudge(UnitTestCase):
	def test_build_user_message(self):
		content = persona.build_user_message(
			transcript=[
				{"turn_index": 0, "role": "user", "text": "Buongiorno"},
				{"turn_index": 1, "role": "assistant", "text": "Buongiorno."},
			],
			scenario=_scenario(),
			trace_kind="llm_student",
		)
		self.assertIn("Negoziazione", content)
		self.assertIn("42 anni", content)
		self.assertIn("Buongiorno", content)

	def test_default_system_prompt_non_empty(self):
		# SYSTEM_PROMPT lives in the module as a default; the runtime config
		# comes from judge_loader, which falls back to this value.
		self.assertTrue(persona.SYSTEM_PROMPT.strip())

	def test_parse_output_valid(self):
		text = json.dumps({
			"score": 0.78,
			"summary": "Persona consistente",
			"evidence_quotes": [
				{"turn_index": 3, "quote": "...", "comment": "..."}
			],
			"warnings": [],
		})
		result = persona.parse_output(text)
		self.assertIsInstance(result, DimensionScore)
		self.assertEqual(result.dimension, DIMENSION_PERSONA)
		self.assertEqual(result.score, 0.78)
		self.assertEqual(result.evidence_quotes[0]["turn_index"], 3)

	def test_parse_output_clamps_score(self):
		text = json.dumps({"score": 1.7, "summary": "x", "evidence_quotes": []})
		result = persona.parse_output(text)
		self.assertEqual(result.score, 1.0)

	def test_parse_output_raises_on_bad_json(self):
		with self.assertRaises(ValueError):
			persona.parse_output("not json")

	def test_judge_version(self):
		self.assertEqual(persona.JUDGE_VERSION, "persona.v1")

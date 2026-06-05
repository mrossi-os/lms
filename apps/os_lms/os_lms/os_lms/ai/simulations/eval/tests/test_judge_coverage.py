"""Unit tests for the learning-objective coverage judge."""
from __future__ import annotations

import json

from frappe.tests import UnitTestCase

from os_lms.os_lms.ai.simulations.eval.judges import coverage
from os_lms.os_lms.ai.simulations.eval.types import (
	DIMENSION_COVERAGE,
	ScenarioRef,
)


def _scenario():
	return ScenarioRef(
		name="SC-1", scenario_name="X",
		learning_objectives=["Gestire obiezione prezzo", "Chiusura"],
		difficulty="medium", customer_persona="...",
		situation_template="...", max_turns=20,
	)


class TestCoverageJudge(UnitTestCase):
	def test_build_messages_includes_objectives(self):
		_, msgs = coverage.build_messages(
			transcript=[{"turn_index": 0, "role": "user", "text": "hi"}],
			scenario=_scenario(),
			trace_kind="llm_student",
		)
		self.assertIn("Gestire obiezione prezzo", msgs[0]["content"])
		self.assertIn("Chiusura", msgs[0]["content"])

	def test_parse_output_with_by_objective(self):
		text = json.dumps({
			"score": 0.55,
			"summary": "Partial",
			"evidence_quotes": [],
			"by_objective": [
				{"objective": "Gestire obiezione prezzo", "score": 0.9,
				 "covered": True, "evidence_turn": 4},
				{"objective": "Chiusura", "score": 0.0, "covered": False,
				 "reason": "Mai emerso"},
			],
		})
		result = coverage.parse_output(text)
		self.assertEqual(result.dimension, DIMENSION_COVERAGE)
		self.assertEqual(result.score, 0.55)
		self.assertEqual(len(result.extras["by_objective"]), 2)
		self.assertFalse(result.extras["by_objective"][1]["covered"])

	def test_parse_output_defaults_empty_by_objective(self):
		text = json.dumps({"score": 0.5, "summary": "", "evidence_quotes": []})
		result = coverage.parse_output(text)
		self.assertEqual(result.extras.get("by_objective", []), [])

	def test_judge_version(self):
		self.assertEqual(coverage.JUDGE_VERSION, "coverage.v1")

"""Unit tests for eval.types dataclasses."""
from __future__ import annotations

from frappe.tests import UnitTestCase

from os_lms.os_lms.ai.simulations.eval.types import (
	DimensionScore,
	ScenarioRef,
	GoldenExpectations,
	DIMENSION_PERSONA,
	DIMENSION_COVERAGE,
	DIMENSION_DEBRIEF,
	DIMENSION_DIFFICULTY,
)


class TestDimensionScore(UnitTestCase):
	def test_defaults(self):
		score = DimensionScore(dimension=DIMENSION_PERSONA, score=0.8, summary="ok")
		self.assertEqual(score.dimension, "persona")
		self.assertEqual(score.score, 0.8)
		self.assertEqual(score.summary, "ok")
		self.assertEqual(score.evidence_quotes, [])
		self.assertEqual(score.warnings, [])
		self.assertEqual(score.extras, {})

	def test_to_dict(self):
		score = DimensionScore(
			dimension=DIMENSION_COVERAGE,
			score=0.6,
			summary="partial",
			evidence_quotes=[{"turn_index": 3, "quote": "x", "comment": "y"}],
			warnings=["w1"],
			extras={"by_objective": [{"objective": "o", "score": 1.0, "covered": True}]},
		)
		d = score.to_dict()
		self.assertEqual(d["dimension"], "coverage")
		self.assertEqual(d["score"], 0.6)
		self.assertEqual(d["evidence_quotes"][0]["quote"], "x")
		self.assertEqual(d["extras"]["by_objective"][0]["objective"], "o")

	def test_none_score_means_skipped(self):
		score = DimensionScore(
			dimension=DIMENSION_DEBRIEF, score=None, warnings=["debrief_missing"]
		)
		self.assertIsNone(score.score)
		self.assertEqual(score.warnings, ["debrief_missing"])


class TestScenarioRef(UnitTestCase):
	def test_minimal(self):
		ref = ScenarioRef(
			name="SC-1",
			scenario_name="Negoziazione",
			learning_objectives=["o1", "o2"],
			difficulty="medium",
			customer_persona="...",
			situation_template="...",
			max_turns=20,
		)
		self.assertEqual(ref.name, "SC-1")
		self.assertEqual(len(ref.learning_objectives), 2)


	def test_scenario_ref_defaults_seed_variations_to_empty_dict(self):
		ref = ScenarioRef(
			name="X", scenario_name="X",
			learning_objectives=[], difficulty="easy",
			customer_persona="", situation_template="",
			max_turns=10,
		)
		assert ref.seed_variations == {}

	def test_scenario_ref_accepts_seed_variations(self):
		ref = ScenarioRef(
			name="X", scenario_name="X",
			learning_objectives=[], difficulty="easy",
			customer_persona="", situation_template="",
			max_turns=10,
			seed_variations={"mood": ["happy", "sad"]},
		)
		assert ref.seed_variations == {"mood": ["happy", "sad"]}


class TestGoldenExpectations(UnitTestCase):
	def test_defaults(self):
		exp = GoldenExpectations(name_label="x", expected_outcomes="y")
		self.assertEqual(exp.name_label, "x")
		self.assertEqual(exp.expected_outcomes, "y")


class TestDimensionConstants(UnitTestCase):
	def test_all_distinct(self):
		dims = {
			DIMENSION_PERSONA,
			DIMENSION_COVERAGE,
			DIMENSION_DEBRIEF,
			DIMENSION_DIFFICULTY,
		}
		self.assertEqual(len(dims), 4)

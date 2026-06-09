"""Unit tests for the debrief accuracy judge."""
from __future__ import annotations

import json

from frappe.tests import UnitTestCase

from os_lms.os_lms.ai.simulations.eval.judges import debrief as judge
from os_lms.os_lms.ai.simulations.eval.types import (
	DIMENSION_DEBRIEF, ScenarioRef,
)


_DEBRIEF_PAYLOAD = {
	"overall_score": 65,
	"criterion_scores": [
		{"criterion": "Ascolto attivo", "score": 7,
		 "evidence_quote": "ascolto attentamente"}
	],
	"strengths": [{"title": "...", "quote": "ascolto attentamente"}],
	"improvements": [{"title": "Chiarire domande", "quote": "...",
	                  "suggestion": "..."}],
}


def _scenario():
	return ScenarioRef(
		name="SC-1", scenario_name="X", learning_objectives=["o1"],
		difficulty="medium", roleplay_persona="x", situation_template="y",
		max_turns=20,
	)


class TestDebriefJudge(UnitTestCase):
	def test_build_user_message_includes_debrief_payload(self):
		content = judge.build_user_message(
			transcript=[
				{"turn_index": 0, "role": "user", "text": "ascolto attentamente"}
			],
			scenario=_scenario(),
			trace_kind="production_session",
			debrief_payload=_DEBRIEF_PAYLOAD,
		)
		self.assertIn("Ascolto attivo", content)
		self.assertIn("65", content)

	def test_parse_output_returns_score_with_extras(self):
		text = json.dumps({
			"score": 0.85,
			"summary": "Solid debrief",
			"evidence_quotes": [],
			"hallucinated_quotes": [{"quote": "x", "reason": "not in transcript"}],
			"score_inconsistencies": [],
			"overall_consistency_delta": 0.1,
		})
		result = judge.parse_output(text)
		self.assertEqual(result.dimension, DIMENSION_DEBRIEF)
		self.assertEqual(result.score, 0.85)
		self.assertEqual(len(result.extras["hallucinated_quotes"]), 1)

	def test_build_user_message_missing_debrief_mentions_absence(self):
		content = judge.build_user_message(
			transcript=[{"turn_index": 0, "role": "user", "text": "x"}],
			scenario=_scenario(),
			trace_kind="production_session",
			debrief_payload=None,
		)
		self.assertIn("debrief non disponibile", content.lower())

	def test_skipped_score_helper(self):
		skipped = judge.skipped_score(reason="debrief_missing")
		self.assertEqual(skipped.dimension, DIMENSION_DEBRIEF)
		self.assertIsNone(skipped.score)
		self.assertIn("debrief_missing", skipped.warnings)

	def test_judge_version(self):
		self.assertEqual(judge.JUDGE_VERSION, "debrief.v1")

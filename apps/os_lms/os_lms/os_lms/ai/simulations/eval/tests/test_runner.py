"""Unit tests for runner.py (golden replay + LLM-student synthetic runs)."""
from __future__ import annotations

import json

from frappe.tests import UnitTestCase

from os_lms.os_lms.ai.utils.llm.provider import ChatResponse, Usage
from os_lms.os_lms.ai.simulations.eval.runner import (
	run_synthetic_llm_student, run_golden_replay,
)
from os_lms.os_lms.ai.simulations.eval.types import ScenarioRef


class FakeProvider:
	"""Returns queued ChatResponse objects matching the real provider shape."""
	name = "fake"

	def __init__(self, responses):
		self.responses = list(responses)

	def chat(self, messages, *, system=None, model=None, **kwargs):
		return ChatResponse(
			text=self.responses.pop(0),
			finish_reason="stop",
			usage=Usage(),
			model=model or "fake-1",
			provider="fake",
		)


def _scenario(max_turns=4):
	return ScenarioRef(
		name="SC-1", scenario_name="X",
		learning_objectives=["o1"], difficulty="medium",
		customer_persona="x", situation_template="y", max_turns=max_turns,
	)


def _variant_ok():
	return json.dumps({
		"situation": "Cliente competitor.",
		"persona": {
			"name": "Mario", "role": "CTO", "company": "AcmeCo",
			"mood": "scettico", "key_objection": "prezzo",
			"hidden_motivation": "vuole sconto",
		},
	})


class TestGoldenReplay(UnitTestCase):
	def test_returns_transcript_no_provider_calls(self):
		turns_json = json.dumps([
			{"role": "user", "text": "ciao"},
			{"role": "assistant", "text": "salve"},
		])
		provider = FakeProvider(responses=[])
		transcript = run_golden_replay(turns_json=turns_json, provider=provider)
		self.assertEqual(len(transcript), 2)


class TestLlmStudentRunner(UnitTestCase):
	def test_alternates_student_and_cliente_until_max_turns(self):
		# max_turns=4 → 1 variant call + 2 student + 2 cliente = 5 calls.
		provider = FakeProvider(responses=[
			_variant_ok(),
			"Buongiorno",             # student turn 0
			"Buongiorno a lei",        # cliente turn 1
			"Vorrei un preventivo",    # student turn 2
			"Dipende dal volume",      # cliente turn 3
		])
		transcript = run_synthetic_llm_student(
			scenario=_scenario(max_turns=4),
			profile_name="competent",
			provider=provider,
		)
		self.assertEqual(len(transcript), 4)
		self.assertEqual(transcript[0]["role"], "user")
		self.assertEqual(transcript[1]["role"], "assistant")
		self.assertEqual(transcript[0]["text"], "Buongiorno")
		self.assertEqual(transcript[3]["text"], "Dipende dal volume")

"""Unit tests for the pure customer services (ScenarioVariantGenerator,
CustomerTurnService). Pure tests — no frappe, no DB."""
from __future__ import annotations

import json

from frappe.tests import UnitTestCase

from os_lms.os_lms.ai.utils.llm.provider import ChatMessage, ChatResponse, Usage
from os_lms.os_lms.ai.simulations.customer import (
	ScenarioVariantGenerator,
	CustomerTurnService,
)
from os_lms.os_lms.ai.simulations.eval.types import ScenarioRef


class _RecordingProvider:
	"""LLMProvider stub recording every chat() call and returning queued texts."""

	name = "recording"

	def __init__(self, responses: list[str]):
		self.responses = list(responses)
		self.calls: list[dict] = []

	def chat(self, messages, *, system=None, model=None, **kwargs):
		self.calls.append({
			"messages": list(messages),
			"system": system,
			"model": model,
			"kwargs": dict(kwargs),
		})
		return ChatResponse(
			text=self.responses.pop(0),
			finish_reason="stop", usage=Usage(),
			model=model or "rec-1", provider="recording",
		)


def _valid_variant_json() -> str:
	return json.dumps({
		"situation": "Cliente del settore manifatturiero.",
		"persona": {
			"name": "Mario", "role": "CTO", "company": "AcmeCo",
			"mood": "scettico", "key_objection": "prezzo",
			"hidden_motivation": "vuole sconto",
		},
	})


def _scenario_ref() -> ScenarioRef:
	return ScenarioRef(
		name="SC-1", scenario_name="X",
		learning_objectives=["o1", "o2"],
		difficulty="medium",
		customer_persona="base persona",
		situation_template="template",
		max_turns=4,
		seed_variations={"mood": ["calm", "tense"]},
	)


class TestScenarioVariantGenerator(UnitTestCase):
	def test_generate_returns_parsed_variant_on_valid_first_response(self):
		provider = _RecordingProvider(responses=[_valid_variant_json()])
		gen = ScenarioVariantGenerator(provider=provider, model="m1")
		variant = gen.generate(_scenario_ref(), seed="seed-1")
		self.assertEqual(variant.persona.name, "Mario")
		self.assertEqual(len(provider.calls), 1)

	def test_generate_passes_structured_output_response_format(self):
		provider = _RecordingProvider(responses=[_valid_variant_json()])
		gen = ScenarioVariantGenerator(provider=provider, model=None)
		gen.generate(_scenario_ref(), seed="seed-2")
		kw = provider.calls[0]["kwargs"]
		self.assertIn("response_format", kw)
		self.assertEqual(kw["response_format"].name, "scenario_variant")

	def test_generate_retries_once_on_invalid_first_response(self):
		provider = _RecordingProvider(responses=[
			"not json at all",
			_valid_variant_json(),
		])
		gen = ScenarioVariantGenerator(provider=provider, model=None)
		variant = gen.generate(_scenario_ref(), seed="seed-3")
		self.assertEqual(variant.persona.name, "Mario")
		self.assertEqual(len(provider.calls), 2)
		# Retry must use temperature=0
		self.assertEqual(provider.calls[1]["kwargs"].get("temperature"), 0)

	def test_generate_propagates_value_error_if_retry_also_fails(self):
		provider = _RecordingProvider(responses=["nope", "still not json"])
		gen = ScenarioVariantGenerator(provider=provider, model=None)
		with self.assertRaises(ValueError):
			gen.generate(_scenario_ref(), seed="seed-4")

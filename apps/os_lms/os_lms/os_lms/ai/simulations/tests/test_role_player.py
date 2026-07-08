"""Unit tests for the pure role-player services (ScenarioVariantGenerator,
RolePlayerTurnService). Pure tests — no frappe, no DB."""
from __future__ import annotations

import json
from unittest.mock import patch

from frappe.tests import UnitTestCase

from os_lms.os_lms.ai.utils.llm import (
	LLMError,
	LLMRateLimit,
	LLMServerError,
	LLMTimeout,
)
from os_lms.os_lms.ai.utils.llm.provider import ChatMessage, ChatResponse, Usage
from os_lms.os_lms.ai.simulations.prompts import PersonaVariant
from os_lms.os_lms.ai.simulations.role_player import (
	ScenarioVariantGenerator,
	RolePlayerTurnService,
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


class _FlakyProvider:
	"""LLMProvider stub that raises queued exceptions or returns queued texts,
	in order, one per chat() call. Used to exercise transient-error retries."""

	name = "flaky"

	def __init__(self, outcomes: list):
		# Each outcome is either an Exception instance (raised) or a str (returned).
		self.outcomes = list(outcomes)
		self.calls = 0

	def chat(self, messages, *, system=None, model=None, **kwargs):
		self.calls += 1
		outcome = self.outcomes.pop(0)
		if isinstance(outcome, Exception):
			raise outcome
		return ChatResponse(
			text=outcome,
			finish_reason="stop", usage=Usage(),
			model=model or "flaky-1", provider="flaky",
		)


def _valid_variant_json() -> str:
	return json.dumps({
		"situation": "Personaggio del settore manifatturiero.",
		"student_brief": "Devi negoziare un contratto di fornitura con il CTO.",
		"persona": {
			"name": "Mario", "role": "CTO", "context": "AcmeCo",
			"mood": "scettico", "key_objection": "prezzo",
			"hidden_motivation": "vuole sconto",
		},
	})


def _scenario_ref() -> ScenarioRef:
	return ScenarioRef(
		name="SC-1", scenario_name="X",
		learning_objectives=["o1", "o2"],
		difficulty="medium",
		roleplay_persona="base persona",
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

	def test_generate_retries_on_transient_llm_error(self):
		# A provider hiccup (5xx) on the first attempt must not fail the whole
		# generation: it is retried and the second attempt succeeds.
		provider = _FlakyProvider([LLMServerError("boom"), _valid_variant_json()])
		gen = ScenarioVariantGenerator(provider=provider, model=None)
		with patch("os_lms.os_lms.ai.simulations.role_player.time.sleep"):
			variant = gen.generate(_scenario_ref(), seed="seed-5")
		self.assertEqual(variant.persona.name, "Mario")
		self.assertEqual(provider.calls, 2)

	def test_generate_propagates_after_exhausting_transient_retries(self):
		# Every attempt hits a transient error → the last one propagates.
		provider = _FlakyProvider(
			[LLMTimeout("t"), LLMRateLimit("r"), LLMServerError("s")]
		)
		gen = ScenarioVariantGenerator(provider=provider, model=None)
		with patch("os_lms.os_lms.ai.simulations.role_player.time.sleep"):
			with self.assertRaises(LLMError):
				gen.generate(_scenario_ref(), seed="seed-6")
		self.assertEqual(provider.calls, 3)


def _persona() -> PersonaVariant:
	return PersonaVariant(
		name="Anna", role="CFO", context="Foo Srl",
		mood="diffidente", key_objection="costo",
		hidden_motivation="convincere il CEO",
	)


class TestRolePlayerTurnService(UnitTestCase):
	def test_ask_invokes_chat_fn_with_role_play_system_prompt(self):
		captured: dict = {}

		def chat_fn(*, messages, system, **kwargs):
			captured["messages"] = list(messages)
			captured["system"] = system
			captured["kwargs"] = dict(kwargs)
			return ChatResponse(
				text="Risposta del personaggio",
				finish_reason="stop", usage=Usage(),
				model="t-1", provider="test",
			)

		service = RolePlayerTurnService(chat_fn=chat_fn)
		response = service.ask(
			persona=_persona(),
			situation="Trattativa in corso.",
			difficulty="hard",
			history=[ChatMessage(role="user", content="Buongiorno")],
		)
		self.assertEqual(response.text, "Risposta del personaggio")
		self.assertIn("Anna", captured["system"])
		self.assertEqual(len(captured["messages"]), 1)
		self.assertEqual(captured["kwargs"].get("temperature"), 0.7)
		self.assertEqual(captured["kwargs"].get("max_tokens"), 400)

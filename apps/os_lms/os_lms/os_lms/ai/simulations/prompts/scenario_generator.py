"""Prompt 1 — scenario variant generator.

Given a Scenario template + a seed, asks the LLM to produce a concrete
situation/persona variant in JSON. The orchestrator persists the result on
the Simulation Session (generated_situation, generated_persona).

The randomisation of ``{variable_name}`` placeholders inside the
``situation_template`` is **done in code** (``render_situation_template``)
before the prompt is built — the LLM only sees the already-rendered
template and is in charge of the persona + the narrative expansion of the
setup. This keeps the seed selection deterministic (same seed → same
choices) without relying on the model to behave randomly.

Pure functions only — no frappe / no HTTP imports.
"""

from __future__ import annotations

import json
import random
import re
from dataclasses import dataclass

SCENARIO_GEN_VERSION = "gen.v2"

# `{variable_name}` placeholders in the situation_template. Same convention
# enforced client-side by the ScenarioEditor (`VAR_REF_RE`).
_PLACEHOLDER_RE = re.compile(r"\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}")


@dataclass
class PersonaVariant:
	name: str
	role: str
	context: str
	mood: str
	key_objection: str
	hidden_motivation: str


@dataclass
class ScenarioVariant:
	situation: str
	persona: PersonaVariant
	student_brief: str


SCENARIO_SCHEMA: dict = {
	"type": "object",
	"additionalProperties": False,
	"required": ["situation", "student_brief", "persona"],
	"properties": {
		"situation": {
			"type": "string",
			"description": "Setup concreto della scena, 2-5 frasi.",
		},
		"student_brief": {
			"type": "string",
			"description": (
				"Briefing rivolto allo studente, in seconda persona. Spiega la "
				"situazione, chi ha di fronte (nome, ruolo, contesto) e l'obiettivo "
				"da raggiungere. NON rivelare MAI key_objection né hidden_motivation."
			),
		},
		"persona": {
			"type": "object",
			"additionalProperties": False,
			"required": [
				"name",
				"role",
				"context",
				"mood",
				"key_objection",
				"hidden_motivation",
			],
			"properties": {
				"name": {"type": "string"},
				"role": {"type": "string"},
				"context": {
					"type": "string",
					"description": "Affiliazione o contesto del personaggio: azienda, scuola, università, ospedale, ente, studio professionale, ecc. — dominio-agnostico.",
				},
				"mood": {"type": "string", "description": "Stato emotivo iniziale del personaggio."},
				"key_objection": {
					"type": "string",
					"description": "L'obiezione o resistenza principale che il personaggio porterà nel dialogo.",
				},
				"hidden_motivation": {
					"type": "string",
					"description": "Motivazione reale del personaggio, non rivelata esplicitamente.",
				},
			},
		},
	},
}


def render_situation_template(
	template: str,
	seed_variations: dict[str, list[str]] | None,
	seed: str | None = None,
) -> tuple[str, dict[str, str]]:
	"""Resolve ``{variable_name}`` placeholders by picking one value per
	variable from ``seed_variations``.

	``seed`` (str | None) seeds the RNG for reproducibility — same seed +
	same seed_variations yields the same picks, so a session can be
	replayed deterministically.

	Returns ``(rendered_template, chosen_values)``. ``chosen_values`` is
	the ``variable_name → picked_value`` map; callers can persist it for
	audit (e.g. on the Simulation Session).

	Placeholders whose variable has no candidates (or that don't appear
	in ``seed_variations``) are left untouched as literal text — same
	behaviour the frontend's `findUndefinedVariables` is designed to
	catch at edit time.
	"""
	rng = random.Random(seed) if seed is not None else random.Random()
	chosen: dict[str, str] = {}
	for var, values in (seed_variations or {}).items():
		if not values:
			continue
		chosen[var] = rng.choice(values)

	def _sub(m: re.Match[str]) -> str:
		return chosen.get(m.group(1), m.group(0))

	rendered = _PLACEHOLDER_RE.sub(_sub, template or "")
	return rendered, chosen


def build_scenario_generator_messages(
	*,
	scenario_name: str,
	difficulty: str,
	roleplay_persona: str,
	situation_template: str,
	learning_objectives: list[str],
	seed: str,
) -> tuple[str, list[dict]]:
	"""Return (system_prompt, messages) ready for LLMProvider.chat.

	Loads the prompt from ``LMSA Prompt Template`` (purpose
	``scenario_variant_generator``) and substitutes placeholders. The
	``situation_template`` arrives with placeholders already substituted
	by ``render_situation_template`` — the LLM does not see the seed
	variations and is not asked to pick values.
	"""
	from os_lms.os_lms.ai.utils.template_loader import (
		PURPOSE_SCENARIO_VARIANT_GENERATOR,
		load_prompt_template,
		render_template,
	)

	config = load_prompt_template(PURPOSE_SCENARIO_VARIANT_GENERATOR)
	ctx = {
		"scenario_name": scenario_name,
		"difficulty": difficulty,
		"roleplay_persona": roleplay_persona,
		"situation_template": situation_template,
		"learning_objectives": "\n".join(f"- {o}" for o in learning_objectives) or "—",
		"seed": seed,
	}
	system = render_template(config["system_template"], ctx)
	user = render_template(config["user_template"], ctx)
	return system, [{"role": "user", "content": user}]


def parse_scenario_generator_output(text: str) -> ScenarioVariant:
	"""Parse the LLM JSON output into a typed dataclass.

	Raises ValueError on parse failure or missing fields. Callers can retry
	with temperature=0 / corrective prompt.
	"""
	data = _load_json_object(text)
	persona_data = data.get("persona") or {}
	missing = [
		k
		for k in ("name", "role", "context", "mood", "key_objection", "hidden_motivation")
		if not isinstance(persona_data.get(k), str)
	]
	if missing:
		raise ValueError(f"persona is missing required fields: {missing}")
	situation = data.get("situation")
	if not isinstance(situation, str) or not situation.strip():
		raise ValueError("situation is missing or empty")
	student_brief = data.get("student_brief")
	if not isinstance(student_brief, str) or not student_brief.strip():
		raise ValueError("student_brief is missing or empty")

	return ScenarioVariant(
		situation=situation.strip(),
		student_brief=student_brief.strip(),
		persona=PersonaVariant(
			name=persona_data["name"].strip(),
			role=persona_data["role"].strip(),
			context=persona_data["context"].strip(),
			mood=persona_data["mood"].strip(),
			key_objection=persona_data["key_objection"].strip(),
			hidden_motivation=persona_data["hidden_motivation"].strip(),
		),
	)


def _load_json_object(text: str) -> dict:
	"""Best-effort JSON load. Strips ```json fences and leading/trailing junk."""
	cleaned = text.strip()
	if cleaned.startswith("```"):
		# remove opening fence (with optional language tag) and trailing fence
		cleaned = cleaned.lstrip("`")
		if cleaned.lower().startswith("json"):
			cleaned = cleaned[4:]
		cleaned = cleaned.strip()
		if cleaned.endswith("```"):
			cleaned = cleaned[:-3].strip()
	try:
		data = json.loads(cleaned)
	except json.JSONDecodeError as e:
		raise ValueError(f"output is not valid JSON: {e}") from e
	if not isinstance(data, dict):
		raise ValueError("output JSON is not an object")
	return data

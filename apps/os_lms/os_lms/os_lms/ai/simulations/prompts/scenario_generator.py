"""Prompt 1 — scenario variant generator.

Given a Scenario template + a seed, asks the LLM to produce a concrete
situation/persona variant in JSON. The orchestrator persists the result on
the Simulation Session (generated_situation, generated_persona).

Pure functions only — no frappe / no HTTP imports.
"""
from __future__ import annotations

import json
from dataclasses import dataclass

SCENARIO_GEN_VERSION = "gen.v1"


@dataclass
class PersonaVariant:
    name: str
    role: str
    company: str
    mood: str
    key_objection: str
    hidden_motivation: str


@dataclass
class ScenarioVariant:
    situation: str
    persona: PersonaVariant


SYSTEM_PROMPT = (
    "Sei un instructional designer esperto di simulazioni didattiche.\n"
    "Generi una variante concreta di uno scenario di role-play partendo dal "
    "template fornito. Il personaggio interpretato dall'AI può essere un "
    "cliente, un esaminatore, un paziente, un intervistatore, ecc., a "
    "seconda della persona base.\n\n"
    "Mantieni invariati: obiettivi formativi, difficoltà, schema di valutazione.\n"
    "Varia: nome del personaggio, settore/contesto, obiezione o resistenza "
    "principale, mood iniziale, motivazione nascosta.\n\n"
    "Rispondi ESCLUSIVAMENTE con un oggetto JSON valido conforme allo "
    "schema fornito, senza alcun testo prima o dopo."
)


SCENARIO_SCHEMA: dict = {
    "type": "object",
    "additionalProperties": False,
    "required": ["situation", "persona"],
    "properties": {
        "situation": {
            "type": "string",
            "description": "Setup concreto della scena, 2-5 frasi.",
        },
        "persona": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "name",
                "role",
                "company",
                "mood",
                "key_objection",
                "hidden_motivation",
            ],
            "properties": {
                "name": {"type": "string"},
                "role": {"type": "string"},
                "company": {"type": "string"},
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


def build_scenario_generator_messages(
    *,
    scenario_name: str,
    difficulty: str,
    roleplay_persona: str,
    situation_template: str,
    learning_objectives: list[str],
    seed_variations: dict[str, list[str]],
    seed: str,
) -> tuple[str, list[dict]]:
    """Return (system_prompt, messages) ready for LLMProvider.chat.

    `seed_variations`: mapping variable_name → list of possible_values.
    The seed is sent as part of the user message so the model can latch onto
    it for reproducibility (deterministic only with temperature=0).
    """
    objectives_block = "\n".join(f"- {o}" for o in learning_objectives) or "—"
    variations_block = (
        "\n".join(f"- {k}: {', '.join(v)}" for k, v in seed_variations.items())
        or "—"
    )

    user = (
        f"Scenario: {scenario_name}\n"
        f"Difficoltà: {difficulty}\n\n"
        f"Persona base del personaggio:\n{roleplay_persona}\n\n"
        f"Template situazione:\n{situation_template}\n\n"
        f"Obiettivi formativi:\n{objectives_block}\n\n"
        f"Variabili da randomizzare:\n{variations_block}\n\n"
        f"Seed di generazione: {seed}\n\n"
        "Produci ora la variante concreta come JSON valido secondo lo schema."
    )
    return SYSTEM_PROMPT, [{"role": "user", "content": user}]


def parse_scenario_generator_output(text: str) -> ScenarioVariant:
    """Parse the LLM JSON output into a typed dataclass.

    Raises ValueError on parse failure or missing fields. Callers can retry
    with temperature=0 / corrective prompt.
    """
    data = _load_json_object(text)
    persona_data = data.get("persona") or {}
    missing = [
        k
        for k in ("name", "role", "company", "mood", "key_objection", "hidden_motivation")
        if not isinstance(persona_data.get(k), str)
    ]
    if missing:
        raise ValueError(f"persona is missing required fields: {missing}")
    situation = data.get("situation")
    if not isinstance(situation, str) or not situation.strip():
        raise ValueError("situation is missing or empty")

    return ScenarioVariant(
        situation=situation.strip(),
        persona=PersonaVariant(
            name=persona_data["name"].strip(),
            role=persona_data["role"].strip(),
            company=persona_data["company"].strip(),
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

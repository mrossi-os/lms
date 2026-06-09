"""Persona consistency judge.

Verifies the AI role-player stays in character throughout the chat:
name, role, company, mood, key_objection, hidden_motivation. Penalises
character breaks (assistant offering help, revealing meta), premature
hidden_motivation reveals, and out-of-character replies to off-topic input.
"""
from __future__ import annotations

import json

from os_lms.os_lms.ai.simulations.eval.types import (
	DimensionScore,
	DIMENSION_PERSONA,
	ScenarioRef,
)

JUDGE_VERSION = "persona.v1"

SYSTEM_PROMPT = (
	"Sei un valutatore esperto di scenari di role-play didattici.\n"
	"Analizzi la trascrizione e decidi se il personaggio interpretato "
	"dall'AI (cliente, esaminatore, paziente, ecc.) resta in personaggio "
	"per tutta la conversazione.\n\n"
	"Devi penalizzare: rotture di personaggio (es. 'come AI ti aiuto'), "
	"rivelazioni della motivazione nascosta, risposte meta a domande "
	"off-topic invece di restare nel ruolo.\n\n"
	"Rispondi ESCLUSIVAMENTE con JSON valido conforme allo schema."
)

OUTPUT_SCHEMA: dict = {
	"type": "object",
	"additionalProperties": False,
	"required": ["score", "summary", "evidence_quotes", "warnings"],
	"properties": {
		"score": {"type": "number"},
		"summary": {"type": "string"},
		"evidence_quotes": {
			"type": "array",
			"items": {
				"type": "object",
				"additionalProperties": False,
				"required": ["turn_index", "quote", "comment"],
				"properties": {
					"turn_index": {"type": "integer"},
					"quote": {"type": "string"},
					"comment": {"type": "string"},
				},
			},
		},
		"warnings": {"type": "array", "items": {"type": "string"}},
	},
}


def build_user_message(
	*,
	transcript: list[dict],
	scenario: ScenarioRef,
	trace_kind: str,
) -> str:
	"""Return the user-side message for this judge. The system prompt is
	supplied separately by the pipeline via the judge_loader (DB-driven)."""
	transcript_block = "\n".join(
		f"[{t.get('turn_index', i)}] {t['role'].upper()}: {t.get('text', '')}"
		for i, t in enumerate(transcript)
	)
	return (
		f"Persona base:\n{scenario.roleplay_persona}\n\n"
		f"Template situazione:\n{scenario.situation_template}\n\n"
		f"Scenario: {scenario.scenario_name}\n\n"
		f"Trascrizione completa:\n{transcript_block}\n\n"
		f"Tipo di trace: {trace_kind}\n\n"
		"Valuta la persona consistency. Restituisci JSON valido secondo "
		"lo schema fornito."
	)


def parse_output(text: str) -> DimensionScore:
	try:
		data = json.loads(text)
	except json.JSONDecodeError as e:
		raise ValueError(f"persona judge: invalid JSON ({e})")
	if not isinstance(data, dict):
		raise ValueError("persona judge: top-level value is not an object")
	score = data.get("score")
	if not isinstance(score, (int, float)):
		raise ValueError("persona judge: missing/invalid score")
	score = max(0.0, min(1.0, float(score)))
	return DimensionScore(
		dimension=DIMENSION_PERSONA,
		score=score,
		summary=str(data.get("summary", "")),
		evidence_quotes=list(data.get("evidence_quotes", [])),
		warnings=list(data.get("warnings", [])),
		extras={},
	)

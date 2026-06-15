"""Persona consistency judge.

Verifies the AI role-player stays in character throughout the chat:
name, role, context, mood, key_objection, hidden_motivation. Penalises
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

def build_user_message(
	*,
	transcript: list[dict],
	scenario: ScenarioRef,
	trace_kind: str,
) -> str:
	"""Return the user-side message for this judge. The system prompt and
	output schema are loaded by the pipeline via
	``load_prompt_template('judge_persona')`` — DB record if present, else
	the hardcoded default in
	``os_lms.os_lms.ai.utils.default_prompt.judge_persona``."""
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

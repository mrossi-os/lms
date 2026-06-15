"""Debrief accuracy judge.

Verifies the runtime debrief output matches the transcript: no hallucinated
quotes, scores supported by tone-consistent evidence, overall_score coherent
with criterion_scores aggregation.

When `debrief_payload` is missing the pipeline calls `skipped_score()`
instead of `build_user_message()` — no LLM call is made.
"""
from __future__ import annotations

import json

from os_lms.os_lms.ai.simulations.eval.types import (
	DimensionScore, DIMENSION_DEBRIEF, ScenarioRef,
)

def build_user_message(
	*,
	transcript: list[dict],
	scenario: ScenarioRef,
	trace_kind: str,
	debrief_payload: dict | None,
) -> str:
	"""Return the user-side message for this judge. The system prompt and
	output schema are loaded by the pipeline via
	``load_prompt_template('judge_debrief')`` — DB record if present, else
	the hardcoded default in
	``os_lms.os_lms.ai.utils.default_prompt.judge_debrief``."""
	transcript_block = "\n".join(
		f"[{t.get('turn_index', i)}] {t['role'].upper()}: {t.get('text', '')}"
		for i, t in enumerate(transcript)
	)
	if debrief_payload is None:
		debrief_block = "(debrief non disponibile)"
	else:
		debrief_block = json.dumps(debrief_payload, ensure_ascii=False, indent=2)
	return (
		f"Trascrizione:\n{transcript_block}\n\n"
		f"Debrief prodotto dal prompt runtime:\n{debrief_block}\n\n"
		f"Tipo di trace: {trace_kind}\n\n"
		"Valuta l'accuratezza del debrief rispetto alla trascrizione."
	)


def parse_output(text: str) -> DimensionScore:
	try:
		data = json.loads(text)
	except json.JSONDecodeError as e:
		raise ValueError(f"debrief judge: invalid JSON ({e})")
	score = data.get("score")
	if not isinstance(score, (int, float)):
		raise ValueError("debrief judge: missing/invalid score")
	return DimensionScore(
		dimension=DIMENSION_DEBRIEF,
		score=max(0.0, min(1.0, float(score))),
		summary=str(data.get("summary", "")),
		evidence_quotes=list(data.get("evidence_quotes", [])),
		warnings=list(data.get("warnings", [])),
		extras={
			"hallucinated_quotes": list(data.get("hallucinated_quotes", [])),
			"score_inconsistencies": list(data.get("score_inconsistencies", [])),
			"overall_consistency_delta": data.get("overall_consistency_delta"),
		},
	)


def skipped_score(*, reason: str) -> DimensionScore:
	"""Return a placeholder score used when the LLM call is skipped."""
	return DimensionScore(
		dimension=DIMENSION_DEBRIEF,
		score=None,
		summary="Skipped",
		warnings=[reason],
	)

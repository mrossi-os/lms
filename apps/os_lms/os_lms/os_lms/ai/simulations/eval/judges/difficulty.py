"""Difficulty calibration judge.

Checks whether scenario.difficulty (`easy|medium|hard`) is reflected in the
role-player behaviour: an `easy` scenario should yield to basic techniques
in 2-3 turns; a `hard` scenario should resist advanced techniques. Cross-
checks against the runtime debrief's overall_score when available.
"""
from __future__ import annotations

import json

from os_lms.os_lms.ai.simulations.eval.types import (
	DimensionScore, DIMENSION_DIFFICULTY, ScenarioRef,
)

def build_user_message(
	*,
	transcript: list[dict],
	scenario: ScenarioRef,
	trace_kind: str,
	runtime_overall_score: float | int | None = None,
) -> str:
	"""Return the user-side message for this judge. The system prompt and
	output schema are loaded by the pipeline via
	``load_prompt_template('judge_difficulty')`` — DB record if present,
	else the hardcoded default in
	``os_lms.os_lms.ai.utils.default_prompt.judge_difficulty``."""
	transcript_block = "\n".join(
		f"[{t.get('turn_index', i)}] {t['role'].upper()}: {t.get('text', '')}"
		for i, t in enumerate(transcript)
	)
	if runtime_overall_score is None:
		overall_block = "Overall score runtime: non disponibile\n"
	else:
		overall_block = (
			f"Overall score finale del debrief runtime: "
			f"{runtime_overall_score}/100\n"
		)
	return (
		f"Difficoltà dichiarata: {scenario.difficulty}\n"
		f"{overall_block}\n"
		f"Trascrizione:\n{transcript_block}\n\n"
		f"Tipo di trace: {trace_kind}\n\n"
		"Restituisci JSON valido con expected_difficulty, "
		"perceived_difficulty, calibration_offset, score, summary."
	)


def parse_output(text: str) -> DimensionScore:
	try:
		data = json.loads(text)
	except json.JSONDecodeError as e:
		raise ValueError(f"difficulty judge: invalid JSON ({e})")
	score = data.get("score")
	if not isinstance(score, (int, float)):
		raise ValueError("difficulty judge: missing/invalid score")
	return DimensionScore(
		dimension=DIMENSION_DIFFICULTY,
		score=max(0.0, min(1.0, float(score))),
		summary=str(data.get("summary", "")),
		evidence_quotes=list(data.get("evidence_quotes", [])),
		warnings=list(data.get("warnings", [])),
		extras={
			"expected_difficulty": data.get("expected_difficulty", ""),
			"perceived_difficulty": data.get("perceived_difficulty", ""),
			"calibration_offset": data.get("calibration_offset"),
		},
	)

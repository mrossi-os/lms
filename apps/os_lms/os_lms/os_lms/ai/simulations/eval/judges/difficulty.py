"""Difficulty calibration judge.

Checks whether scenario.difficulty (`easy|medium|hard`) is reflected in the
cliente behaviour: an `easy` scenario should yield to basic techniques in
2-3 turns; a `hard` scenario should resist advanced techniques. Cross-checks
against the runtime debrief's overall_score when available.
"""
from __future__ import annotations

import json

from os_lms.os_lms.ai.simulations.eval.types import (
	DimensionScore, DIMENSION_DIFFICULTY, ScenarioRef,
)

JUDGE_VERSION = "difficulty.v1"

SYSTEM_PROMPT = (
	"Sei un valutatore di calibrazione difficoltà di scenari didattici.\n"
	"Confronti la difficoltà dichiarata dello scenario (easy/medium/hard) "
	"con quella effettivamente percepita guardando la conversazione e — se "
	"fornito — il punteggio finale del debrief.\n\n"
	"Restituisci calibration_offset in [-2, +2]: positivo = scenario più "
	"duro dell'etichetta, negativo = più facile.\n\n"
	"Rispondi ESCLUSIVAMENTE con JSON valido."
)


def build_messages(
	*,
	transcript: list[dict],
	scenario: ScenarioRef,
	trace_kind: str,
	runtime_overall_score: float | int | None = None,
) -> tuple[str, list[dict]]:
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
	user = (
		f"Difficoltà dichiarata: {scenario.difficulty}\n"
		f"{overall_block}\n"
		f"Trascrizione:\n{transcript_block}\n\n"
		f"Tipo di trace: {trace_kind}\n\n"
		"Restituisci JSON valido con expected_difficulty, "
		"perceived_difficulty, calibration_offset, score, summary."
	)
	return SYSTEM_PROMPT, [{"role": "user", "content": user}]


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

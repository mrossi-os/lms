"""Learning-objective coverage judge.

Reports per-objective coverage in extras.by_objective[], distinguishing
'not emerged' (scenario gave no opportunity) from 'emerged but missed by
the student'. Only the first penalises the scenario.
"""
from __future__ import annotations

import json

from os_lms.os_lms.ai.simulations.eval.types import (
	DimensionScore, DIMENSION_COVERAGE, ScenarioRef,
)

JUDGE_VERSION = "coverage.v1"

SYSTEM_PROMPT = (
	"Sei un valutatore di scenari didattici.\n"
	"Per ogni obiettivo formativo elencato decidi se la conversazione ha "
	"dato allo studente l'opportunità di esercitarlo, e con quale qualità "
	"l'opportunità è stata creata.\n\n"
	"Distinguere: 'covered=false, reason=\"non emerso\"' (responsabilità "
	"dello scenario) da 'covered=true, score basso' (responsabilità dello "
	"studente — non penalizza la qualità dello scenario).\n\n"
	"Rispondi ESCLUSIVAMENTE con JSON valido."
)


def build_messages(
	*, transcript: list[dict], scenario: ScenarioRef, trace_kind: str,
) -> tuple[str, list[dict]]:
	transcript_block = "\n".join(
		f"[{t.get('turn_index', i)}] {t['role'].upper()}: {t.get('text', '')}"
		for i, t in enumerate(transcript)
	)
	objectives = "\n".join(f"- {o}" for o in scenario.learning_objectives) or "—"
	user = (
		f"Obiettivi formativi da valutare:\n{objectives}\n\n"
		f"Trascrizione completa:\n{transcript_block}\n\n"
		f"Tipo di trace: {trace_kind}\n\n"
		"Restituisci JSON valido con score complessivo + by_objective[]."
	)
	return SYSTEM_PROMPT, [{"role": "user", "content": user}]


def parse_output(text: str) -> DimensionScore:
	try:
		data = json.loads(text)
	except json.JSONDecodeError as e:
		raise ValueError(f"coverage judge: invalid JSON ({e})")
	score = data.get("score")
	if not isinstance(score, (int, float)):
		raise ValueError("coverage judge: missing/invalid score")
	return DimensionScore(
		dimension=DIMENSION_COVERAGE,
		score=max(0.0, min(1.0, float(score))),
		summary=str(data.get("summary", "")),
		evidence_quotes=list(data.get("evidence_quotes", [])),
		warnings=list(data.get("warnings", [])),
		extras={"by_objective": list(data.get("by_objective", []))},
	)

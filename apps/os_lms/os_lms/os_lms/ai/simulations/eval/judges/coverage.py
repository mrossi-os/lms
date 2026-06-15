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

def build_user_message(
	*, transcript: list[dict], scenario: ScenarioRef, trace_kind: str,
) -> str:
	"""Return the user-side message for this judge. The system prompt and
	output schema are loaded by the pipeline via
	``load_prompt_template('judge_coverage')`` — DB record if present, else
	the hardcoded default in
	``os_lms.os_lms.ai.utils.default_prompt.judge_coverage``."""
	transcript_block = "\n".join(
		f"[{t.get('turn_index', i)}] {t['role'].upper()}: {t.get('text', '')}"
		for i, t in enumerate(transcript)
	)
	objectives = "\n".join(f"- {o}" for o in scenario.learning_objectives) or "—"
	return (
		f"Obiettivi formativi da valutare:\n{objectives}\n\n"
		f"Trascrizione completa:\n{transcript_block}\n\n"
		f"Tipo di trace: {trace_kind}\n\n"
		"Restituisci JSON valido con score complessivo + by_objective[]."
	)


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

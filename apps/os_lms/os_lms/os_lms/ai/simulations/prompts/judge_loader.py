"""Load judge configuration (system prompt + output schema + sampling
params) from the LMSA Judge Prompt doctype, with a hardcoded fallback to
the values declared in the judge modules.

Resolution order on every `load_judge_prompt(purpose)`:

1. DB lookup: if a `LMSA Judge Prompt` record exists for `purpose` AND it
   is `enabled=1`, materialize a config dict from it
2. Otherwise return the hardcoded default from the judge module

This keeps the pipeline working in three situations:
- DB has a record → operator-tuned prompt is used
- DB has no record / record disabled → ships with the code default
- Frappe not initialized (pure unit tests) → code default

No caching layer: the cost of a primary-key lookup on a single-row doctype
is negligible compared to the LLM call that consumes the result.
"""

from __future__ import annotations

import json

import frappe

from os_lms.os_lms.ai.simulations.eval.judges import (
	coverage,
	debrief,
	difficulty,
	persona,
)

PURPOSE_PERSONA = "judge_persona"
PURPOSE_COVERAGE = "judge_coverage"
PURPOSE_DEBRIEF = "judge_debrief"
PURPOSE_DIFFICULTY = "judge_difficulty"

ALL_PURPOSES = (
	PURPOSE_PERSONA,
	PURPOSE_COVERAGE,
	PURPOSE_DEBRIEF,
	PURPOSE_DIFFICULTY,
)

DEFAULT_TEMPERATURE = 0.0
DEFAULT_MAX_TOKENS = 1024


# Single source of truth for the code-side defaults. Each entry mirrors the
# constants declared in the corresponding judge module so a `bench migrate`
# can re-seed the DB and the runtime can fall back here when no record
# exists.
DEFAULTS: dict[str, dict] = {
	PURPOSE_PERSONA: {
		"label": "Judge: persona consistency",
		"version": persona.JUDGE_VERSION,
		"system_prompt": persona.SYSTEM_PROMPT,
		"output_schema": persona.OUTPUT_SCHEMA,
		"temperature": DEFAULT_TEMPERATURE,
		"max_tokens": DEFAULT_MAX_TOKENS,
	},
	PURPOSE_COVERAGE: {
		"label": "Judge: learning-objective coverage",
		"version": coverage.JUDGE_VERSION,
		"system_prompt": coverage.SYSTEM_PROMPT,
		"output_schema": coverage.OUTPUT_SCHEMA,
		"temperature": DEFAULT_TEMPERATURE,
		"max_tokens": DEFAULT_MAX_TOKENS,
	},
	PURPOSE_DEBRIEF: {
		"label": "Judge: debrief accuracy",
		"version": debrief.JUDGE_VERSION,
		"system_prompt": debrief.SYSTEM_PROMPT,
		"output_schema": debrief.OUTPUT_SCHEMA,
		"temperature": DEFAULT_TEMPERATURE,
		"max_tokens": DEFAULT_MAX_TOKENS,
	},
	PURPOSE_DIFFICULTY: {
		"label": "Judge: difficulty calibration",
		"version": difficulty.JUDGE_VERSION,
		"system_prompt": difficulty.SYSTEM_PROMPT,
		"output_schema": difficulty.OUTPUT_SCHEMA,
		"temperature": DEFAULT_TEMPERATURE,
		"max_tokens": DEFAULT_MAX_TOKENS,
	},
}


def load_judge_prompt(purpose: str) -> dict:
	"""Return {system_prompt, output_schema, temperature, max_tokens, version}.

	Never raises on missing DB record or unavailable frappe context — falls
	back to the hardcoded default from the judge module. Raises KeyError only
	if `purpose` is not a known judge identifier.
	"""
	if purpose not in DEFAULTS:
		raise KeyError(f"Unknown judge prompt purpose: {purpose!r}")

	try:
		if frappe.db.exists("LMSA Judge Prompt", purpose):
			doc = frappe.get_doc("LMSA Judge Prompt", purpose)
			if doc.enabled:
				return {
					"system_prompt": doc.system_prompt or "",
					"output_schema": json.loads(doc.output_schema),
					"temperature": float(doc.temperature)
					if doc.temperature is not None
					else DEFAULT_TEMPERATURE,
					"max_tokens": int(doc.max_tokens) if doc.max_tokens else DEFAULT_MAX_TOKENS,
					"version": doc.version or DEFAULTS[purpose]["version"],
				}
	except Exception:
		# Any failure (frappe not bootstrapped, malformed schema in DB, ...)
		# falls back to the code default rather than breaking the eval pipeline.
		pass

	return _default_config(purpose)


# ---------- internals ----------


def _default_config(purpose: str) -> dict:
	d = DEFAULTS[purpose]
	return {
		"system_prompt": d["system_prompt"],
		"output_schema": d["output_schema"],
		"temperature": d["temperature"],
		"max_tokens": d["max_tokens"],
		"version": d["version"],
	}

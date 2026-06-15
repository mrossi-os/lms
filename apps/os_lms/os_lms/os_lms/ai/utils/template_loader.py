"""Load prompt configurations from the LMSA Prompt Template doctype, with a
hardcoded fallback to the values declared per purpose under
``default_prompt/``.

This loader serves three families of prompt sharing one doctype:

- **Runtime templates** (llm_student, role_play, scenario_*, debrief,
  tutor): parametric system/user templates with ``{{var}}`` placeholders
  substituted at call time via ``render_template()``.
- **Authoring AI** (scenario_generator_ai,
  evaluation_schema_generator_ai): system+user prompts for the
  instructor "Compila con IA" buttons.
- **Evaluation judges** (judge_persona, judge_coverage, judge_debrief,
  judge_difficulty): system prompt + JSON output schema. The user
  message is built in code (no placeholders); ``output_schema`` is
  surfaced in the returned dict for purposes that declare it.

Resolution order on every ``load_prompt_template(purpose)``:

1. DB lookup: if a ``LMSA Prompt Template`` record exists for ``purpose``
   AND it is ``enabled=1``, materialize a config dict from it
2. Otherwise return the hardcoded default declared under
   ``default_prompt/<purpose>.py``

Placeholders that have no entry in the context dict are left as literal
text — this is intentional so a typo in the template doesn't crash the
pipeline.

No caching layer: the cost of a primary-key lookup on a single-row
doctype is negligible compared to the LLM call that consumes the result.
"""

from __future__ import annotations

from types import ModuleType

from os_lms.os_lms.ai.utils.default_prompt import (
	debrief as _debrief,
)
from os_lms.os_lms.ai.utils.default_prompt import (
	evaluation_schema_generator_ai as _eval_schema_gen_ai,
)
from os_lms.os_lms.ai.utils.default_prompt import (
	llm_student as _llm_student,
)
from os_lms.os_lms.ai.utils.default_prompt import (
	role_play as _role_play,
)
from os_lms.os_lms.ai.utils.default_prompt import (
	scenario_generator_ai as _scenario_gen_ai,
)
from os_lms.os_lms.ai.utils.default_prompt import (
	scenario_variant_generator as _scenario_variant_gen,
)
from os_lms.os_lms.ai.utils.default_prompt import (
	tutor as _tutor,
)
from os_lms.os_lms.ai.utils.default_prompt import (
	judge_persona as _judge_persona,
)
from os_lms.os_lms.ai.utils.default_prompt import (
	judge_coverage as _judge_coverage,
)
from os_lms.os_lms.ai.utils.default_prompt import (
	judge_debrief as _judge_debrief,
)
from os_lms.os_lms.ai.utils.default_prompt import (
	judge_difficulty as _judge_difficulty,
)

PURPOSE_LLM_STUDENT = "llm_student"
PURPOSE_ROLE_PLAY = "role_play"
PURPOSE_SCENARIO_VARIANT_GENERATOR = "scenario_variant_generator"
PURPOSE_DEBRIEF = "debrief"
PURPOSE_SCENARIO_GENERATOR_AI = "scenario_generator_ai"
PURPOSE_EVALUATION_SCHEMA_GENERATOR_AI = "evaluation_schema_generator_ai"
PURPOSE_TUTOR = "tutor"
PURPOSE_JUDGE_PERSONA = "judge_persona"
PURPOSE_JUDGE_COVERAGE = "judge_coverage"
PURPOSE_JUDGE_DEBRIEF = "judge_debrief"
PURPOSE_JUDGE_DIFFICULTY = "judge_difficulty"

ALL_PURPOSES = (
	PURPOSE_LLM_STUDENT,
	PURPOSE_ROLE_PLAY,
	PURPOSE_SCENARIO_VARIANT_GENERATOR,
	PURPOSE_DEBRIEF,
	PURPOSE_SCENARIO_GENERATOR_AI,
	PURPOSE_EVALUATION_SCHEMA_GENERATOR_AI,
	PURPOSE_TUTOR,
	PURPOSE_JUDGE_PERSONA,
	PURPOSE_JUDGE_COVERAGE,
	PURPOSE_JUDGE_DEBRIEF,
	PURPOSE_JUDGE_DIFFICULTY,
)


def _config_from_module(module: ModuleType) -> dict:
	return {
		"label": module.LABEL,
		"version": module.VERSION,
		"system_template": module.SYSTEM_TEMPLATE,
		"user_template": module.USER_TEMPLATE,
		"temperature": module.TEMPERATURE,
		"max_tokens": module.MAX_TOKENS,
		"available_placeholders": module.PLACEHOLDERS,
		# Only judges declare an OUTPUT_SCHEMA; for everything else this is None.
		"output_schema": getattr(module, "OUTPUT_SCHEMA", None),
	}


DEFAULTS: dict[str, dict] = {
	PURPOSE_LLM_STUDENT: _config_from_module(_llm_student),
	PURPOSE_ROLE_PLAY: _config_from_module(_role_play),
	PURPOSE_SCENARIO_VARIANT_GENERATOR: _config_from_module(_scenario_variant_gen),
	PURPOSE_DEBRIEF: _config_from_module(_debrief),
	PURPOSE_SCENARIO_GENERATOR_AI: _config_from_module(_scenario_gen_ai),
	PURPOSE_EVALUATION_SCHEMA_GENERATOR_AI: _config_from_module(_eval_schema_gen_ai),
	PURPOSE_TUTOR: _config_from_module(_tutor),
	PURPOSE_JUDGE_PERSONA: _config_from_module(_judge_persona),
	PURPOSE_JUDGE_COVERAGE: _config_from_module(_judge_coverage),
	PURPOSE_JUDGE_DEBRIEF: _config_from_module(_judge_debrief),
	PURPOSE_JUDGE_DIFFICULTY: _config_from_module(_judge_difficulty),
}


# ---------- public API ----------


def load_prompt_template(purpose: str) -> dict:
	"""Return {system_template, user_template, temperature, max_tokens,
	version, output_schema}.

	``output_schema`` is the parsed JSON Schema for purposes that have one
	(currently the 4 judge purposes), and ``None`` for everything else.

	Falls back to the hardcoded default on any DB failure (frappe not
	bootstrapped, malformed JSON in DB, ...). Raises KeyError only if
	`purpose` is not a known identifier.
	"""
	if purpose not in DEFAULTS:
		raise KeyError(f"Unknown prompt template purpose: {purpose!r}")

	try:
		import frappe

		if frappe.db.exists("LMSA Prompt Template", purpose):
			doc = frappe.get_doc("LMSA Prompt Template", purpose)
			if doc.enabled:
				return {
					"system_template": doc.system_template or "",
					"user_template": doc.user_template or "",
					"temperature": float(doc.temperature)
					if doc.temperature is not None
					else DEFAULTS[purpose]["temperature"],
					"max_tokens": int(doc.max_tokens) if doc.max_tokens else DEFAULTS[purpose]["max_tokens"],
					"version": doc.version or DEFAULTS[purpose]["version"],
					"output_schema": _parse_output_schema(
						doc.output_schema, DEFAULTS[purpose]["output_schema"]
					),
				}
	except Exception:
		pass

	return _default_config(purpose)


def render_template(template: str, ctx: dict) -> str:
	"""Substitute `{{key}}` occurrences with `str(ctx[key])`.

	Placeholders not present in `ctx` are left as literal text — this
	preserves the original template when a caller forgets a variable
	rather than crashing the prompt at runtime.
	"""
	rendered = template
	for key, value in ctx.items():
		rendered = rendered.replace("{{" + key + "}}", "" if value is None else str(value))
	return rendered


# ---------- internals ----------


def _default_config(purpose: str) -> dict:
	d = DEFAULTS[purpose]
	return {
		"system_template": d["system_template"],
		"user_template": d["user_template"],
		"temperature": d["temperature"],
		"max_tokens": d["max_tokens"],
		"version": d["version"],
		"output_schema": d["output_schema"],
	}


def _parse_output_schema(raw, fallback):
	"""Parse the doctype's ``output_schema`` (stored as JSON text).

	Returns the ``fallback`` (typically the in-module default) when the
	field is empty or unparseable, so a typo in the Desk can never crash
	the pipeline mid-eval.
	"""
	import json

	if not raw:
		return fallback
	try:
		return json.loads(raw)
	except (TypeError, ValueError):
		return fallback

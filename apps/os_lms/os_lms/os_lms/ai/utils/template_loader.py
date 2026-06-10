"""Load parametric prompt templates (system + user) from the LMSA Prompt
Template doctype, with a hardcoded fallback to the values declared per
purpose under ``default_prompt/``.

Resolution order on every ``load_prompt_template(purpose)``:

1. DB lookup: if a ``LMSA Prompt Template`` record exists for ``purpose``
   AND it is ``enabled=1``, materialize a config dict from it
2. Otherwise return the hardcoded default declared under
   ``default_prompt/<purpose>.py``

The caller is responsible for substituting ``{{var}}`` placeholders via
``render_template()`` after loading. Placeholders that have no entry in
the context dict are left as literal text — this is intentional so a typo
in the template doesn't crash the pipeline.

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

PURPOSE_LLM_STUDENT = "llm_student"
PURPOSE_ROLE_PLAY = "role_play"
PURPOSE_SCENARIO_VARIANT_GENERATOR = "scenario_variant_generator"
PURPOSE_DEBRIEF = "debrief"
PURPOSE_SCENARIO_GENERATOR_AI = "scenario_generator_ai"
PURPOSE_EVALUATION_SCHEMA_GENERATOR_AI = "evaluation_schema_generator_ai"
PURPOSE_TUTOR = "tutor"

ALL_PURPOSES = (
	PURPOSE_LLM_STUDENT,
	PURPOSE_ROLE_PLAY,
	PURPOSE_SCENARIO_VARIANT_GENERATOR,
	PURPOSE_DEBRIEF,
	PURPOSE_SCENARIO_GENERATOR_AI,
	PURPOSE_EVALUATION_SCHEMA_GENERATOR_AI,
	PURPOSE_TUTOR,
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
	}


DEFAULTS: dict[str, dict] = {
	PURPOSE_LLM_STUDENT: _config_from_module(_llm_student),
	PURPOSE_ROLE_PLAY: _config_from_module(_role_play),
	PURPOSE_SCENARIO_VARIANT_GENERATOR: _config_from_module(_scenario_variant_gen),
	PURPOSE_DEBRIEF: _config_from_module(_debrief),
	PURPOSE_SCENARIO_GENERATOR_AI: _config_from_module(_scenario_gen_ai),
	PURPOSE_EVALUATION_SCHEMA_GENERATOR_AI: _config_from_module(_eval_schema_gen_ai),
	PURPOSE_TUTOR: _config_from_module(_tutor),
}


# ---------- public API ----------


def load_prompt_template(purpose: str) -> dict:
	"""Return {system_template, user_template, temperature, max_tokens, version}.

	Falls back to the hardcoded default on any DB failure. Raises KeyError
	only if `purpose` is not a known identifier.
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
	}

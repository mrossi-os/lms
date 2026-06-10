"""Prompt 2 — role-player system prompt.

Built once at start_session and reused as the LLM `system` parameter for
the entire session. The actual template lives in ``LMSA Prompt Template``
(purpose ``role_play``) with a hardcoded default in
``template_loader.DEFAULTS`` — operators can tune the prompt from the Desk
without a redeploy.

The role-player can be a customer, examiner, patient, interviewer, etc. —
driven by the scenario's persona. The default rules are deliberately
domain-neutral.

Pure functions only — no frappe / no HTTP imports (the loader handles
both — best-effort: missing site → hardcoded default).
"""
from __future__ import annotations

from .scenario_generator import PersonaVariant
from os_lms.os_lms.ai.utils.template_loader import (
	PURPOSE_ROLE_PLAY,
	load_prompt_template,
	render_template,
)

# Backwards-compat: external modules (e.g. orchestrator) import this for
# `prompt_version` audit. Now sourced from the template loader so the
# Desk-edited version flows through.
def _current_role_play_version() -> str:
	return load_prompt_template(PURPOSE_ROLE_PLAY)["version"]


# Module-level constant kept for backwards-compat with code that does
# `from prompts import ROLE_PLAY_VERSION` at import time. The dynamic
# version is available via `_current_role_play_version()` at call time.
ROLE_PLAY_VERSION = "rp.v1"


def build_role_play_system_prompt(
	*,
	persona: PersonaVariant,
	generated_situation: str,
	difficulty: str,
	language: str = "it",
) -> str:
	"""Return the system prompt that drives the role-play.

	Loads the template from ``LMSA Prompt Template`` and substitutes the
	persona/situation/difficulty placeholders. The output is deterministic
	for a given (persona, situation, difficulty) tuple — the same session
	always re-instantiates the same in-character behavior.
	"""
	if language != "it":
		# Italian-only for now; en-US/etc. arrive in fase 3 (i18n).
		raise NotImplementedError(f"role-play prompt for language={language!r} not implemented")

	config = load_prompt_template(PURPOSE_ROLE_PLAY)
	ctx = {
		"persona_name": persona.name,
		"persona_role": persona.role,
		"persona_company": persona.company,
		"persona_mood": persona.mood,
		"persona_key_objection": persona.key_objection,
		"persona_hidden_motivation": persona.hidden_motivation,
		"generated_situation": generated_situation,
		"difficulty": difficulty,
	}
	return render_template(config["system_template"], ctx)

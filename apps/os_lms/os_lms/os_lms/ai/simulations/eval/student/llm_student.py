"""LLM-as-student prompt construction.

The runner calls `build_student_messages()` on every turn the student has
to play, giving the LLM the full conversation history and the persona-base
of the role-player. The LLM responds in role as the student.

The system/user prompts are loaded via `template_loader` so they can be
edited from the Desk (LMSA Prompt Template, purpose=llm_student) without
a redeploy. Hardcoded defaults in template_loader.DEFAULTS are used as
fallback when no DB record exists.
"""

from __future__ import annotations

from dataclasses import dataclass

from os_lms.os_lms.ai.simulations.eval.student.profiles import get_profile
from os_lms.os_lms.ai.simulations.eval.types import ScenarioRef
from os_lms.os_lms.ai.utils.template_loader import (
	PURPOSE_LLM_STUDENT,
	load_prompt_template,
	render_template,
)

# Generic fallback opening — substituted into {{scenario_brief}} when the
# instructor leaves the scenario_brief empty. Kept domain-neutral on purpose
# so it doesn't bias non-sales simulations (medical, customer service, etc.).
_DEFAULT_OPENING = (
	"Sei uno studente che sta facendo una simulazione didattica. "
	"Il tuo obiettivo è mettere in pratica le tecniche apprese e "
	"raggiungere gli obiettivi formativi dello scenario."
)


@dataclass
class StudentCallParams:
	"""Everything the runner needs to invoke the LLM-student for one turn."""

	system: str
	messages: list[dict]
	temperature: float
	max_tokens: int
	version: str


def build_student_messages(
	*,
	scenario: ScenarioRef,
	history: list[dict],
	profile_name: str,
	lesson_context: str = "",
	scenario_brief: str = "",
) -> StudentCallParams:
	"""Render the LLM-student call params for one turn.

	The system/user templates come from `LMSA Prompt Template` (purpose
	`llm_student`) with a hardcoded fallback. `{{var}}` placeholders are
	substituted from the context built below.
	"""
	profile = get_profile(profile_name)
	config = load_prompt_template(PURPOSE_LLM_STUDENT)

	ctx = _build_context(
		scenario=scenario,
		history=history,
		profile=profile,
		lesson_context=lesson_context,
		scenario_brief=scenario_brief,
	)
	system = render_template(config["system_template"], ctx)
	user = render_template(config["user_template"], ctx)
	return StudentCallParams(
		system=system,
		messages=[{"role": "user", "content": user}],
		temperature=config["temperature"],
		max_tokens=config["max_tokens"],
		version=config["version"],
	)


def _build_context(
	*,
	scenario: ScenarioRef,
	history: list[dict],
	profile: dict,
	lesson_context: str,
	scenario_brief: str,
) -> dict:
	"""Compose the placeholder substitution map for the LLM-student templates."""
	objectives = "\n".join(f"- {o}" for o in scenario.learning_objectives) or "—"
	transcript = "\n".join(
		f"{t['role'].upper()}: {t.get('text', '')}" for t in history
	)
	lesson_block = (
		f"Materiale studiato (estratti dal corso):\n{lesson_context}\n\n"
		if lesson_context.strip()
		else ""
	)
	return {
		"scenario_brief": scenario_brief.strip() or _DEFAULT_OPENING,
		"profile_addendum": profile["system_prompt_addendum"],
		"scenario_name": scenario.scenario_name,
		"difficulty": scenario.difficulty,
		"roleplay_persona": scenario.roleplay_persona,
		"learning_objectives": objectives,
		"lesson_block": lesson_block,
		"transcript": transcript,
	}

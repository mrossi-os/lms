"""LLM-as-student prompt construction.

The runner calls `build_student_messages()` on every turn the student has
to play, giving the LLM the full conversation history and the persona-base
of the cliente. The LLM responds in role as the student.
"""
from __future__ import annotations

from os_lms.os_lms.ai.simulations.eval.student.profiles import get_profile
from os_lms.os_lms.ai.simulations.eval.types import ScenarioRef


# Generic fallback opening — used when the instructor leaves the
# scenario_brief empty. Kept domain-neutral on purpose so it doesn't bias
# non-sales simulations (medical, customer service, etc.).
_DEFAULT_OPENING = (
	"Sei uno studente che sta facendo una simulazione didattica. "
	"Il tuo obiettivo è mettere in pratica le tecniche apprese e "
	"raggiungere gli obiettivi formativi dello scenario."
)

# Fixed response-format coda, always appended at the end of the system
# prompt. The downstream pipeline relies on the "one short reply, no
# meta-commentary, no role prefix" contract to parse the LLM output.
_RESPONSE_RULES = (
	"Rispondi sempre nel ruolo dello studente: una sola battuta per "
	"turno, naturale, senza meta-commentario. Niente prefissi come "
	"'STUDENTE:'."
)


def build_student_messages(
	*,
	scenario: ScenarioRef,
	history: list[dict],
	profile_name: str,
	lesson_context: str = "",
	scenario_brief: str = "",
) -> tuple[str, list[dict]]:
	profile = get_profile(profile_name)
	opening = scenario_brief.strip() or _DEFAULT_OPENING
	system = (
		f"{opening}\n\n"
		f"Profilo: {profile['system_prompt_addendum']}\n\n"
		f"{_RESPONSE_RULES}"
	)
	objectives = "\n".join(f"- {o}" for o in scenario.learning_objectives) or "—"
	transcript_block = "\n".join(
		f"{t['role'].upper()}: {t.get('text', '')}" for t in history
	)
	lesson_block = (
		f"Materiale studiato (estratti dal corso):\n{lesson_context}\n\n"
		if lesson_context.strip()
		else ""
	)
	user = (
		f"Scenario: {scenario.scenario_name}\n"
		f"Difficoltà: {scenario.difficulty}\n"
		f"Persona del cliente:\n{scenario.customer_persona}\n\n"
		f"Obiettivi formativi:\n{objectives}\n\n"
		f"{lesson_block}"
		f"Conversazione finora:\n{transcript_block}\n\n"
		"Produci la prossima battuta dello STUDENTE. Una sola battuta. "
		"Niente meta-commentario, niente prefissi come 'STUDENTE:'."
	)
	return system, [{"role": "user", "content": user}]

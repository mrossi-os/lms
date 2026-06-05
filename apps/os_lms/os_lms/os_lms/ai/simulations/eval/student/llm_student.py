"""LLM-as-student prompt construction.

The runner calls `build_student_messages()` on every turn the student has
to play, giving the LLM the full conversation history and the persona-base
of the cliente. The LLM responds in role as the student.
"""
from __future__ import annotations

from os_lms.os_lms.ai.simulations.eval.student.profiles import get_profile
from os_lms.os_lms.ai.simulations.eval.types import ScenarioRef


_BASE_SYSTEM = (
	"Sei uno studente venditore che sta facendo una simulazione "
	"didattica con un cliente. Il tuo obiettivo è mettere in pratica "
	"le tecniche apprese e raggiungere gli obiettivi formativi dello "
	"scenario.\n\n"
	"Rispondi sempre nel ruolo dello studente venditore: una sola "
	"battuta per turno, naturale, senza meta-commentario."
)


def build_student_messages(
	*,
	scenario: ScenarioRef,
	history: list[dict],
	profile_name: str,
) -> tuple[str, list[dict]]:
	profile = get_profile(profile_name)
	system = f"{_BASE_SYSTEM}\n\nProfilo: {profile['system_prompt_addendum']}"
	objectives = "\n".join(f"- {o}" for o in scenario.learning_objectives) or "—"
	transcript_block = "\n".join(
		f"{t['role'].upper()}: {t.get('text', '')}" for t in history
	)
	user = (
		f"Scenario: {scenario.scenario_name}\n"
		f"Difficoltà: {scenario.difficulty}\n"
		f"Persona del cliente:\n{scenario.customer_persona}\n\n"
		f"Obiettivi formativi:\n{objectives}\n\n"
		f"Conversazione finora:\n{transcript_block}\n\n"
		"Produci la prossima battuta dello STUDENTE. Una sola battuta. "
		"Niente meta-commentario, niente prefissi come 'STUDENTE:'."
	)
	return system, [{"role": "user", "content": user}]

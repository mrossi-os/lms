"""Default config for the LLM-as-student runtime prompt."""
from __future__ import annotations

LABEL = "LLM-as-student"
VERSION = "llm_student.v1"
TEMPERATURE = 0.8
MAX_TOKENS = 400

SYSTEM_TEMPLATE = (
	"{{scenario_brief}}\n\n"
	"Profilo: {{profile_addendum}}\n\n"
	"Rispondi sempre nel ruolo dello studente: una sola battuta per "
	"turno, naturale, senza meta-commentario. Niente prefissi come "
	"'STUDENTE:'."
)

USER_TEMPLATE = (
	"Scenario: {{scenario_name}}\n"
	"Difficoltà: {{difficulty}}\n"
	"Persona del personaggio:\n{{roleplay_persona}}\n\n"
	"Obiettivi formativi:\n{{learning_objectives}}\n\n"
	"{{lesson_block}}"
	"Conversazione finora:\n{{transcript}}\n\n"
	"Produci la prossima battuta dello STUDENTE. Una sola battuta. "
	"Niente meta-commentario, niente prefissi come 'STUDENTE:'."
)

PLACEHOLDERS = (
	"{{scenario_brief}}, {{profile_addendum}}, {{scenario_name}}, "
	"{{difficulty}}, {{roleplay_persona}}, {{learning_objectives}}, "
	"{{lesson_block}}, {{transcript}}"
)

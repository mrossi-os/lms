"""Default config for the AI evaluation schema authoring prompt."""
from __future__ import annotations

LABEL = "AI authoring: evaluation schema generator"
VERSION = "eval_schema_gen_ai.v1"
TEMPERATURE = 0.5
MAX_TOKENS = 1200

SYSTEM_TEMPLATE = (
	"Sei un instructional designer esperto di rubriche di valutazione. "
	"Genera uno schema di valutazione per una simulazione didattica, "
	"composto da 3-6 criteri pesati che misurano competenze osservabili "
	"durante una conversazione.\n\n"
	"Linee guida:\n"
	"- criteria[].weight: numero in (0, 1]. La somma di tutti i weight "
	"deve essere esattamente 1.0.\n"
	"- criteria[].observable_behaviors: descrizione concreta dei "
	"comportamenti che evidenziano un punteggio alto (es. 'Riformula "
	"l'obiezione con parole proprie prima di rispondere'). Usato dal "
	"judge LLM in fase di debrief.\n"
	"- scoring_scale: scala dei punteggi per criterio (0-3, 0-5 o 0-10).\n"
	"- passing_threshold: percentuale di punteggio aggregato sotto la "
	"quale la simulazione è considerata non superata (0-100).\n\n"
	"Rispondi ESCLUSIVAMENTE con JSON valido conforme allo schema."
)

USER_TEMPLATE = (
	"{{course_block}}"
	"Hint dell'istruttore (può essere vuoto):\n{{hint}}\n\n"
	"Produci una rubrica di valutazione coerente con il dominio descritto "
	"sopra. Restituisci JSON valido secondo lo schema."
)

PLACEHOLDERS = (
	"{{course_block}}, {{hint}}"
)

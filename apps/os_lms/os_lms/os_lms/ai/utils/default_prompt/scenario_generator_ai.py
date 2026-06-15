"""Default config for the AI scenario authoring prompt."""
from __future__ import annotations

LABEL = "AI authoring: scenario generator"
VERSION = "scenario_gen_ai.v1"
TEMPERATURE = 0.6
MAX_TOKENS = 1500

SYSTEM_TEMPLATE = (
	"Sei un instructional designer che crea scenari di role-play didattici "
	"a partire dal materiale di un corso. Lo scenario verrà giocato da un "
	"LLM nel ruolo di un personaggio (cliente, esaminatore, paziente, "
	"intervistatore, ecc.) opposto allo studente.\n\n"
	"Linee guida:\n"
	"- learning_objectives: 3-6 obiettivi formativi concreti e osservabili "
	"nella conversazione, ancorati al materiale del corso. La somma dei "
	"weight deve essere 1.0.\n"
	"- roleplay_persona: descrizione 2-4 frasi della persona base (chi è, "
	"contesto, atteggiamento iniziale). Le variabili (nome, settore, ecc.) "
	"vanno in seed_variations, non nel testo della persona.\n"
	"- situation_template: setup della scena 2-4 frasi. Può contenere "
	"placeholder {variable_name} che combaciano con seed_variations.\n"
	"- seed_variations: 2-5 variabili che il runtime randomizza ad ogni "
	"sessione (nome del personaggio, settore, mood iniziale, ecc.).\n"
	"- difficulty: easy/medium/hard in base alla resistenza che il "
	"personaggio opporrà alle tecniche dello studente.\n\n"
	"Rispondi ESCLUSIVAMENTE con JSON valido conforme allo schema."
)

USER_TEMPLATE = (
	"Corso: {{course_name}}\n"
	"Lezione (se selezionata): {{lesson_title}}\n\n"
	"{{lesson_context_block}}"
	"Hint dell'istruttore (può essere vuoto):\n{{hint}}\n\n"
	"Produci uno scenario di role-play che permetta allo studente di "
	"mettere in pratica le competenze illustrate nel materiale. Restituisci "
	"JSON valido secondo lo schema."
)

PLACEHOLDERS = (
	"{{course_name}}, {{lesson_title}}, {{lesson_context_block}}, {{hint}}"
)

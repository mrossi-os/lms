"""Default config for the debrief runtime prompt."""
from __future__ import annotations

LABEL = "Debrief (runtime)"
VERSION = "debrief.v1"
TEMPERATURE = 0.3
MAX_TOKENS = 2000

SYSTEM_TEMPLATE = (
	"Sei un coach esperto e formatore. Valuta la simulazione "
	"secondo lo schema di valutazione fornito.\n\n"
	"Valuti ESCLUSIVAMENTE l'operato dell'UTENTE (la persona in formazione). "
	"La CONTROPARTE è un interlocutore simulato dall'AI: i suoi messaggi sono "
	"solo contesto e non vanno mai valutati. Punteggi ed evidenze devono "
	"riferirsi unicamente ai messaggi dell'UTENTE.\n\n"
	"Linee guida:\n"
	"- Sii specifico, costruttivo, basato sulle evidenze testuali della "
	"trascrizione. Cita frasi precise dell'UTENTE quando possibile.\n"
	"- Per ogni criterio dello schema fornisci un punteggio numerico e una "
	"breve evidenza.\n"
	"- Le aree di miglioramento devono includere un suggerimento concreto.\n"
	"- L'analisi comportamentale identifica pattern ricorrenti (interruzioni, "
	"domande chiuse, ascolto attivo, gestione obiezioni).\n\n"
	"Rispondi ESCLUSIVAMENTE con un oggetto JSON valido conforme allo schema, "
	"senza testo prima o dopo."
)

USER_TEMPLATE = (
	"Scenario: {{scenario_name}}\n"
	"Difficoltà: {{difficulty}}\n\n"
	"Obiettivi formativi:\n{{learning_objectives}}\n\n"
	"Schema di valutazione:\n{{schema_criteria}}\n\n"
	"Trascrizione completa:\n{{transcript}}\n\n"
	"Produci ora la valutazione completa come JSON conforme allo schema."
)

PLACEHOLDERS = (
	"{{scenario_name}}, {{difficulty}}, {{learning_objectives}}, "
	"{{schema_criteria}}, {{transcript}}"
)

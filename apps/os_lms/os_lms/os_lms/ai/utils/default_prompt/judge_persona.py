"""Default config for the persona-consistency judge.

The judge module (``simulations/eval/judges/persona.py``) keeps the live
logic (``build_user_message``, ``parse_output``). This file holds the
editable defaults — system prompt, JSON Schema, sampling params — that
get seeded into ``LMSA Prompt Template`` and used as runtime fallback.
"""
from __future__ import annotations

LABEL = "Judge: persona consistency"
VERSION = "persona.v1"
TEMPERATURE = 0.0
MAX_TOKENS = 1024

SYSTEM_TEMPLATE = (
	"Sei un valutatore esperto di scenari di role-play didattici.\n"
	"Analizzi la trascrizione e decidi se il personaggio interpretato "
	"dall'AI (cliente, esaminatore, paziente, ecc.) resta in personaggio "
	"per tutta la conversazione.\n\n"
	"Devi penalizzare: rotture di personaggio (es. 'come AI ti aiuto'), "
	"rivelazioni della motivazione nascosta, risposte meta a domande "
	"off-topic invece di restare nel ruolo.\n\n"
	"Rispondi ESCLUSIVAMENTE con JSON valido conforme allo schema."
)

# Judges build their user message in code (no parametric {{var}} substitution).
USER_TEMPLATE = ""
PLACEHOLDERS = ""

OUTPUT_SCHEMA: dict = {
	"type": "object",
	"additionalProperties": False,
	"required": ["score", "summary", "evidence_quotes", "warnings"],
	"properties": {
		"score": {"type": "number"},
		"summary": {"type": "string"},
		"evidence_quotes": {
			"type": "array",
			"items": {
				"type": "object",
				"additionalProperties": False,
				"required": ["turn_index", "quote", "comment"],
				"properties": {
					"turn_index": {"type": "integer"},
					"quote": {"type": "string"},
					"comment": {"type": "string"},
				},
			},
		},
		"warnings": {"type": "array", "items": {"type": "string"}},
	},
}

"""Default config for the learning-objective coverage judge."""
from __future__ import annotations

LABEL = "Judge: learning-objective coverage"
VERSION = "coverage.v1"
TEMPERATURE = 0.0
MAX_TOKENS = 1024

SYSTEM_TEMPLATE = (
	"Sei un valutatore di scenari didattici.\n"
	"Per ogni obiettivo formativo elencato decidi se la conversazione ha "
	"dato allo studente l'opportunità di esercitarlo, e con quale qualità "
	"l'opportunità è stata creata.\n\n"
	"Distinguere: 'covered=false, reason=\"non emerso\"' (responsabilità "
	"dello scenario) da 'covered=true, score basso' (responsabilità dello "
	"studente — non penalizza la qualità dello scenario).\n\n"
	"Rispondi ESCLUSIVAMENTE con JSON valido."
)

USER_TEMPLATE = ""
PLACEHOLDERS = ""

OUTPUT_SCHEMA: dict = {
	"type": "object",
	"additionalProperties": False,
	"required": ["score", "summary", "evidence_quotes", "warnings", "by_objective"],
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
		"by_objective": {
			"type": "array",
			"items": {
				"type": "object",
				"additionalProperties": False,
				"required": ["objective", "covered", "reason", "score"],
				"properties": {
					"objective": {"type": "string"},
					"covered": {"type": "boolean"},
					"reason": {"type": "string"},
					"score": {"type": "number"},
				},
			},
		},
	},
}

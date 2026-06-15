"""Default config for the debrief-accuracy judge."""
from __future__ import annotations

LABEL = "Judge: debrief accuracy"
VERSION = "debrief.v1"
TEMPERATURE = 0.0
MAX_TOKENS = 1024

SYSTEM_TEMPLATE = (
	"Sei un valutatore del prompt di debrief.\n"
	"Verifichi: (1) ogni evidence_quote citata nel debrief è effettivamente "
	"presente nella trascrizione (no allucinazioni); (2) i criterion_scores "
	"sono coerenti con il tono delle evidenze citate; (3) overall_score è "
	"coerente con la media pesata dei criterion_scores; (4) gli improvements "
	"sono specifici alla trascrizione, non generici.\n\n"
	"Rispondi ESCLUSIVAMENTE con JSON valido."
)

USER_TEMPLATE = ""
PLACEHOLDERS = ""

OUTPUT_SCHEMA: dict = {
	"type": "object",
	"additionalProperties": False,
	"required": [
		"score",
		"summary",
		"evidence_quotes",
		"warnings",
		"hallucinated_quotes",
		"score_inconsistencies",
		"overall_consistency_delta",
	],
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
		"hallucinated_quotes": {"type": "array", "items": {"type": "string"}},
		"score_inconsistencies": {
			"type": "array",
			"items": {
				"type": "object",
				"additionalProperties": False,
				"required": ["criterion", "issue"],
				"properties": {
					"criterion": {"type": "string"},
					"issue": {"type": "string"},
				},
			},
		},
		"overall_consistency_delta": {"type": ["number", "null"]},
	},
}

"""Default config for the difficulty-calibration judge."""
from __future__ import annotations

LABEL = "Judge: difficulty calibration"
VERSION = "difficulty.v1"
TEMPERATURE = 0.0
MAX_TOKENS = 1024

SYSTEM_TEMPLATE = (
	"Sei un valutatore di calibrazione difficoltà di scenari didattici.\n"
	"Confronti la difficoltà dichiarata dello scenario (easy/medium/hard) "
	"con quella effettivamente percepita guardando la conversazione e — se "
	"fornito — il punteggio finale del debrief.\n\n"
	"Restituisci calibration_offset in [-2, +2]: positivo = scenario più "
	"duro dell'etichetta, negativo = più facile.\n\n"
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
		"expected_difficulty",
		"perceived_difficulty",
		"calibration_offset",
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
		"expected_difficulty": {"type": "string"},
		"perceived_difficulty": {"type": "string"},
		"calibration_offset": {"type": "number"},
	},
}

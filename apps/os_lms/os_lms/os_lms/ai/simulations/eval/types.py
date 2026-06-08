"""Shared dataclasses for the evaluation pipeline.

Pure value types — no frappe / no HTTP. Importable from prompts and jobs alike.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


DIMENSION_PERSONA = "persona"
DIMENSION_COVERAGE = "coverage"
DIMENSION_DEBRIEF = "debrief"
DIMENSION_DIFFICULTY = "difficulty"

ALL_DIMENSIONS = (
	DIMENSION_PERSONA,
	DIMENSION_COVERAGE,
	DIMENSION_DEBRIEF,
	DIMENSION_DIFFICULTY,
)


@dataclass
class DimensionScore:
	"""Output of a single judge call.

	`score=None` means the judge was skipped (e.g. debrief judge with no
	debrief_payload) — the aggregator excludes None scores from means.
	"""

	dimension: str
	score: float | None
	summary: str = ""
	evidence_quotes: list[dict[str, Any]] = field(default_factory=list)
	warnings: list[str] = field(default_factory=list)
	extras: dict[str, Any] = field(default_factory=dict)

	def to_dict(self) -> dict[str, Any]:
		return {
			"dimension": self.dimension,
			"score": self.score,
			"summary": self.summary,
			"evidence_quotes": list(self.evidence_quotes),
			"warnings": list(self.warnings),
			"extras": dict(self.extras),
		}


@dataclass
class ScenarioRef:
	"""Subset of LMSA Simulation Scenario fields the eval pipeline needs."""

	name: str
	scenario_name: str
	learning_objectives: list[str]
	difficulty: str
	customer_persona: str
	situation_template: str
	max_turns: int
	evaluation_schema: str = ""
	seed_variations: dict[str, list[str]] = field(default_factory=dict)


@dataclass
class GoldenExpectations:
	"""Subset of LMSA Scenario Golden Run fields the pipeline needs."""

	name_label: str = ""
	expected_outcomes: str = ""

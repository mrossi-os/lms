from os_lms.os_lms.ai.simulations.eval.types import (
	DimensionScore,
	ScenarioRef,
	GoldenExpectations,
	DIMENSION_PERSONA,
	DIMENSION_COVERAGE,
	DIMENSION_DEBRIEF,
	DIMENSION_DIFFICULTY,
)


def test_dimension_score_defaults():
	score = DimensionScore(dimension=DIMENSION_PERSONA, score=0.8, summary="ok")
	assert score.dimension == "persona"
	assert score.score == 0.8
	assert score.summary == "ok"
	assert score.evidence_quotes == []
	assert score.warnings == []
	assert score.extras == {}


def test_dimension_score_to_dict():
	score = DimensionScore(
		dimension=DIMENSION_COVERAGE,
		score=0.6,
		summary="partial",
		evidence_quotes=[{"turn_index": 3, "quote": "x", "comment": "y"}],
		warnings=["w1"],
		extras={"by_objective": [{"objective": "o", "score": 1.0, "covered": True}]},
	)
	d = score.to_dict()
	assert d["dimension"] == "coverage"
	assert d["score"] == 0.6
	assert d["evidence_quotes"][0]["quote"] == "x"
	assert d["extras"]["by_objective"][0]["objective"] == "o"


def test_scenario_ref_minimal():
	ref = ScenarioRef(
		name="SC-1",
		scenario_name="Negoziazione",
		learning_objectives=["o1", "o2"],
		difficulty="medium",
		customer_persona="...",
		situation_template="...",
		max_turns=20,
	)
	assert ref.name == "SC-1"
	assert len(ref.learning_objectives) == 2


def test_golden_expectations_defaults():
	exp = GoldenExpectations(name_label="x", expected_outcomes="y")
	assert exp.name_label == "x"
	assert exp.expected_outcomes == "y"


def test_dimension_score_none_means_skipped():
	score = DimensionScore(dimension=DIMENSION_DEBRIEF, score=None, warnings=["debrief_missing"])
	assert score.score is None
	assert score.warnings == ["debrief_missing"]


def test_all_four_dimension_constants_distinct():
	assert len({DIMENSION_PERSONA, DIMENSION_COVERAGE, DIMENSION_DEBRIEF, DIMENSION_DIFFICULTY}) == 4

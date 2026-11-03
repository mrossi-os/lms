"""Prompt 3 — debrief generator.

Given the evaluation schema + the full transcript, asks the LLM to grade the session as
strict JSON. The background job persists the result on LMSA Simulation Debrief.

Pure functions only — no frappe / no HTTP imports.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

DEBRIEF_VERSION = "debrief.v2"

# Explicit, unambiguous speaker labels for the transcript fed to the grader.
# The student ("user" turns) is the ONLY subject of evaluation; the AI
# role-player ("assistant" turns) is context/stimulus and must never be graded.
_SPEAKER_LABELS = {"user": "STUDENTE", "assistant": "CONTROPARTE"}


# ---- dataclass result types ----


@dataclass
class CriterionScoreDC:
    criterion: str
    score: float
    max_score: float = 10.0
    evidence_quote: str = ""
    note: str = ""


@dataclass
class StrengthDC:
    title: str
    detail: str = ""
    quote: str = ""


@dataclass
class ImprovementDC:
    title: str
    detail: str = ""
    quote: str = ""
    suggestion: str = ""


@dataclass
class RecommendationDC:
    title: str
    why: str = ""
    lesson: str = ""


@dataclass
class DebriefResult:
    overall_score: float
    criterion_scores: list[CriterionScoreDC] = field(default_factory=list)
    strengths: list[StrengthDC] = field(default_factory=list)
    improvements: list[ImprovementDC] = field(default_factory=list)
    behavioral_analysis: str = ""
    recommended_content: list[RecommendationDC] = field(default_factory=list)
    # The overall score the model wrote, kept beside the one computed from
    # the criteria (see with_computed_overall). None until computed.
    model_overall_score: float | None = None
    # How overall_score was obtained: "weighted" (schema weights),
    # "unweighted" (criteria not matching the schema) or "model".
    overall_method: str = "model"


# SYSTEM_PROMPT used to be hardcoded here; it now lives in `LMSA Prompt
# Template` (purpose `debrief`) with a hardcoded fallback in
# `template_loader.DEFAULTS`.
def _current_system_prompt() -> str:
    from os_lms.os_lms.ai.utils.template_loader import PURPOSE_DEBRIEF, load_prompt_template

    return load_prompt_template(PURPOSE_DEBRIEF)["system_template"]


# JSON schema used both for documentation and for providers that support
# structured-output (response_format=JsonSchema).
DEBRIEF_SCHEMA: dict = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "overall_score",
        "criterion_scores",
        "strengths",
        "improvements",
        "behavioral_analysis",
        "recommended_content",
    ],
    "properties": {
        "overall_score": {
            "type": "number",
            "minimum": 0,
            "maximum": 100,
            "description": "Punteggio complessivo normalizzato 0-100.",
        },
        "criterion_scores": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["criterion", "score", "max_score", "evidence_quote", "note"],
                "properties": {
                    "criterion": {"type": "string"},
                    "score": {"type": "number"},
                    "max_score": {"type": ["number", "null"]},
                    "evidence_quote": {"type": ["string", "null"]},
                    "note": {"type": ["string", "null"]},
                },
            },
        },
        "strengths": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["title", "detail", "quote"],
                "properties": {
                    "title": {"type": "string"},
                    "detail": {"type": ["string", "null"]},
                    "quote": {"type": ["string", "null"]},
                },
            },
        },
        "improvements": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["title", "detail", "quote", "suggestion"],
                "properties": {
                    "title": {"type": "string"},
                    "detail": {"type": ["string", "null"]},
                    "quote": {"type": ["string", "null"]},
                    "suggestion": {"type": ["string", "null"]},
                },
            },
        },
        "behavioral_analysis": {"type": "string"},
        "recommended_content": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["title", "why", "lesson"],
                "properties": {
                    "title": {"type": "string"},
                    "why": {"type": ["string", "null"]},
                    # The lesson id is optional and back-filled by the orchestrator
                    # via RAG search (DBR-3.4). The LLM may also propose its own
                    # title to be matched against the course.
                    "lesson": {"type": ["string", "null"]},
                },
            },
        },
    },
}


# ---- builders ----


def build_debrief_messages(
    *,
    scenario_name: str,
    difficulty: str,
    learning_objectives: list[str],
    schema_criteria: list[dict],
    transcript: list[dict],
) -> tuple[str, list[dict]]:
    """Return (system, messages) for the debrief call.

    Loads the prompt from ``LMSA Prompt Template`` (purpose ``debrief``)
    and substitutes placeholders.

    schema_criteria: list of dicts with keys: name, weight, description,
        observable_behaviors. Weights are passed verbatim to the prompt
        so the LLM can weigh evidence consistently with the scenario design.
    transcript: list of dicts {role, text} ordered by turn_index.
    """
    from os_lms.os_lms.ai.utils.template_loader import (
        PURPOSE_DEBRIEF,
        load_prompt_template,
        render_template,
    )

    schema_block = "\n".join(
        f"- {c['name']} (peso {c['weight']:.2f}): "
        f"{c.get('description', '').strip() or '—'} "
        f"[osservabile: {c.get('observable_behaviors', '').strip() or '—'}]"
        for c in schema_criteria
    ) or "— (schema di valutazione vuoto)"

    objectives_block = "\n".join(f"- {o}" for o in learning_objectives) or "—"

    # Role labels are made explicit so the evaluator never confuses the two
    # speakers. The simulation semantics are inverted relative to what an LLM
    # assumes: `user` is the human trainee under evaluation, while `assistant`
    # is the AI role-player (the simulated counterpart) that must NOT be graded.
    # The legend is prepended to the transcript so the disambiguation travels
    # with the data even when the prompt template is overridden from the desk.
    role_labels = {
        "user": "UTENTE",
        "assistant": "CONTROPARTE",
        "system": "SISTEMA",
    }
    transcript_legend = (
        "Legenda ruoli — UTENTE: la persona in formazione, UNICO soggetto da "
        "valutare. CONTROPARTE: interlocutore simulato dall'AI (cliente / "
        "personaggio), da NON valutare. Valuta esclusivamente i messaggi "
        "dell'UTENTE; i messaggi della CONTROPARTE servono solo come contesto.\n\n"
    )
    transcript_lines = "\n".join(
        f"{i + 1}. [{role_labels.get(t['role'], t['role'].upper())}] {t['text']}"
        for i, t in enumerate(transcript)
    )
    transcript_block = transcript_legend + transcript_lines

    config = load_prompt_template(PURPOSE_DEBRIEF)
    ctx = {
        "scenario_name": scenario_name,
        "difficulty": difficulty,
        "learning_objectives": objectives_block,
        "schema_criteria": schema_block,
        "transcript": transcript_block,
    }
    system = render_template(config["system_template"], ctx)
    user = render_template(config["user_template"], ctx)
    return system, [{"role": "user", "content": user}]


def parse_debrief_output(text: str) -> DebriefResult:
    """Parse JSON output into a typed DebriefResult.

    Raises ValueError on parse failure or schema violation.
    """
    data = _load_json_object(text)

    overall = data.get("overall_score")
    if not isinstance(overall, (int, float)):
        raise ValueError("overall_score is missing or not numeric")
    overall = float(overall)
    if overall < 0 or overall > 100:
        raise ValueError(f"overall_score out of range: {overall}")

    return DebriefResult(
        overall_score=overall,
        criterion_scores=[_parse_criterion(x) for x in data.get("criterion_scores") or []],
        strengths=[_parse_strength(x) for x in data.get("strengths") or []],
        improvements=[_parse_improvement(x) for x in data.get("improvements") or []],
        behavioral_analysis=(data.get("behavioral_analysis") or "").strip(),
        recommended_content=[_parse_recommendation(x) for x in data.get("recommended_content") or []],
    )


def compute_overall_score(
    criterion_scores: list[CriterionScoreDC], schema_criteria: list[dict]
) -> tuple[float | None, str]:
    """Overall score 0-100 from the criterion scores, not from the model.

    The bias tests of 2026-11-03 showed the model's own overall score
    carries a penalty for students writing in Italian as a second language
    that the criterion scores do not (docs/ai-governance/registro-test-bias.md,
    action A1). Each criterion counts as a percentage of the max_score the
    model declares, so a desk-edited prompt that uses another scale still
    adds up. Weighted by the schema when every schema criterion is scored;
    otherwise the plain mean of the scored criteria. Returns (score, method);
    (None, "model") when there is nothing to compute from.
    """
    percents: dict[str, float] = {}
    for c in criterion_scores:
        if c.max_score and c.max_score > 0:
            percents[_criterion_key(c.criterion)] = min(max(c.score / c.max_score, 0.0), 1.0) * 100
    if not percents:
        return None, "model"
    weights = {_criterion_key(c["name"]): float(c.get("weight") or 0.0) for c in schema_criteria}
    total = sum(weights.values())
    if weights and total > 0 and weights.keys() <= percents.keys():
        score = sum(percents[k] * w for k, w in weights.items()) / total
        return round(score, 1), "weighted"
    return round(sum(percents.values()) / len(percents), 1), "unweighted"


def with_computed_overall(result: DebriefResult, schema_criteria: list[dict]) -> DebriefResult:
    """Replace the model's overall score with the one computed from the
    criteria, keeping the model's in ``model_overall_score``."""
    result.model_overall_score = result.overall_score
    score, method = compute_overall_score(result.criterion_scores, schema_criteria)
    if score is not None:
        result.overall_score = score
    result.overall_method = method
    return result


# ---- internals ----


def _criterion_key(name: str) -> str:
    return " ".join((name or "").split()).casefold()


def _parse_criterion(node: dict) -> CriterionScoreDC:
    name = node.get("criterion")
    score = node.get("score")
    if not isinstance(name, str) or not name.strip():
        raise ValueError(f"criterion_scores: missing 'criterion' name in {node!r}")
    if not isinstance(score, (int, float)):
        raise ValueError(f"criterion_scores: missing/invalid 'score' in {node!r}")
    return CriterionScoreDC(
        criterion=name.strip(),
        score=float(score),
        max_score=float(node.get("max_score") or 10.0),
        evidence_quote=(node.get("evidence_quote") or "").strip(),
        note=(node.get("note") or "").strip(),
    )


def _parse_strength(node: dict) -> StrengthDC:
    title = node.get("title")
    if not isinstance(title, str) or not title.strip():
        raise ValueError(f"strengths: missing 'title' in {node!r}")
    return StrengthDC(
        title=title.strip(),
        detail=(node.get("detail") or "").strip(),
        quote=(node.get("quote") or "").strip(),
    )


def _parse_improvement(node: dict) -> ImprovementDC:
    title = node.get("title")
    if not isinstance(title, str) or not title.strip():
        raise ValueError(f"improvements: missing 'title' in {node!r}")
    return ImprovementDC(
        title=title.strip(),
        detail=(node.get("detail") or "").strip(),
        quote=(node.get("quote") or "").strip(),
        suggestion=(node.get("suggestion") or "").strip(),
    )


def _parse_recommendation(node: dict) -> RecommendationDC:
    title = node.get("title")
    if not isinstance(title, str) or not title.strip():
        raise ValueError(f"recommended_content: missing 'title' in {node!r}")
    return RecommendationDC(
        title=title.strip(),
        why=(node.get("why") or "").strip(),
        lesson=(node.get("lesson") or "").strip(),
    )


def _load_json_object(text: str) -> dict:
    """Best-effort JSON load. Strips ```json fences."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.lstrip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:]
        cleaned = cleaned.strip()
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3].strip()
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise ValueError(f"output is not valid JSON: {e}") from e
    if not isinstance(data, dict):
        raise ValueError("output JSON is not an object")
    return data

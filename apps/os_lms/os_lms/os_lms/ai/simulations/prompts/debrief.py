"""Prompt 3 — debrief generator.

Given the rubric + the full transcript, asks the LLM to grade the session as
strict JSON. The background job persists the result on LMSA Simulation Debrief.

Pure functions only — no frappe / no HTTP imports.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

DEBRIEF_VERSION = "debrief.v1"


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


SYSTEM_PROMPT = (
    "Sei un coach esperto di vendita e formatore. Valuta la simulazione "
    "secondo la rubrica fornita.\n\n"
    "Linee guida:\n"
    "- Sii specifico, costruttivo, basato sulle evidenze testuali della "
    "trascrizione. Cita frasi precise quando possibile.\n"
    "- Per ogni criterio della rubrica fornisci un punteggio numerico e una "
    "breve evidenza.\n"
    "- Le aree di miglioramento devono includere un suggerimento concreto.\n"
    "- L'analisi comportamentale identifica pattern ricorrenti (interruzioni, "
    "domande chiuse, ascolto attivo, gestione obiezioni).\n\n"
    "Rispondi ESCLUSIVAMENTE con un oggetto JSON valido conforme allo schema, "
    "senza testo prima o dopo."
)


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
                "required": ["criterion", "score"],
                "properties": {
                    "criterion": {"type": "string"},
                    "score": {"type": "number"},
                    "max_score": {"type": "number"},
                    "evidence_quote": {"type": "string"},
                    "note": {"type": "string"},
                },
            },
        },
        "strengths": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["title"],
                "properties": {
                    "title": {"type": "string"},
                    "detail": {"type": "string"},
                    "quote": {"type": "string"},
                },
            },
        },
        "improvements": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["title"],
                "properties": {
                    "title": {"type": "string"},
                    "detail": {"type": "string"},
                    "quote": {"type": "string"},
                    "suggestion": {"type": "string"},
                },
            },
        },
        "behavioral_analysis": {"type": "string"},
        "recommended_content": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["title"],
                "properties": {
                    "title": {"type": "string"},
                    "why": {"type": "string"},
                    # The lesson id is optional and back-filled by the orchestrator
                    # via RAG search (DBR-3.4). The LLM may also propose its own
                    # title to be matched against the course.
                    "lesson": {"type": "string"},
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
    rubric_criteria: list[dict],
    transcript: list[dict],
) -> tuple[str, list[dict]]:
    """Return (system, messages) for the debrief call.

    rubric_criteria: list of dicts with keys: name, weight, description,
        observable_behaviors. Weights are passed verbatim to the prompt so the
        LLM can weigh evidence consistently with the scenario design.
    transcript: list of dicts {role, text} ordered by turn_index.
    """
    rubric_block = "\n".join(
        f"- {c['name']} (peso {c['weight']:.2f}): "
        f"{c.get('description', '').strip() or '—'} "
        f"[osservabile: {c.get('observable_behaviors', '').strip() or '—'}]"
        for c in rubric_criteria
    ) or "— (rubrica vuota)"

    objectives_block = "\n".join(f"- {o}" for o in learning_objectives) or "—"

    transcript_block = "\n".join(
        f"{i + 1}. [{t['role'].upper()}] {t['text']}" for i, t in enumerate(transcript)
    )

    user = (
        f"Scenario: {scenario_name}\n"
        f"Difficoltà: {difficulty}\n\n"
        f"Obiettivi formativi:\n{objectives_block}\n\n"
        f"Rubrica:\n{rubric_block}\n\n"
        f"Trascrizione completa:\n{transcript_block}\n\n"
        "Produci ora la valutazione completa come JSON conforme allo schema."
    )
    return SYSTEM_PROMPT, [{"role": "user", "content": user}]


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


# ---- internals ----


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

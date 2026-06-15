"""Prompt builders for the simulation feature.

Pure functions: no DB, no HTTP, no frappe imports. They take Python data and
return strings or dicts. This keeps prompt logic independent and testable.

Versioned constants (e.g. ROLE_PLAY_VERSION) are persisted on Session/Turn
as `prompt_version` for audit and A/B comparisons.
"""
from .debrief import (
    DEBRIEF_SCHEMA,
    DEBRIEF_VERSION,
    CriterionScoreDC,
    DebriefResult,
    ImprovementDC,
    RecommendationDC,
    StrengthDC,
    build_debrief_messages,
    parse_debrief_output,
)
from .defense import (
    INJECTION_PATTERNS,
    detect_injection,
    in_character_refusal,
)
from .role_play import ROLE_PLAY_VERSION, build_role_play_system_prompt
from .scenario_generator import (
    SCENARIO_GEN_VERSION,
    SCENARIO_SCHEMA,
    PersonaVariant,
    ScenarioVariant,
    build_scenario_generator_messages,
    parse_scenario_generator_output,
    render_situation_template,
)

__all__ = [
    "CriterionScoreDC",
    "DEBRIEF_SCHEMA",
    "DEBRIEF_VERSION",
    "DebriefResult",
    "INJECTION_PATTERNS",
    "ImprovementDC",
    "PersonaVariant",
    "ROLE_PLAY_VERSION",
    "RecommendationDC",
    "SCENARIO_GEN_VERSION",
    "SCENARIO_SCHEMA",
    "ScenarioVariant",
    "StrengthDC",
    "build_debrief_messages",
    "build_role_play_system_prompt",
    "build_scenario_generator_messages",
    "detect_injection",
    "in_character_refusal",
    "parse_debrief_output",
    "parse_scenario_generator_output",
    "render_situation_template",
]

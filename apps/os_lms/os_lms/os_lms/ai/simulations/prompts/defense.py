"""Prompt-injection detection and in-character fallback responses.

Two complementary defenses:
1. detect_injection(text): regex pattern match against known jailbreak families.
   Returns True if a likely attempt is found. Used by the orchestrator to flag
   the user turn (injection_attempt_detected=1) and force an in-character
   refusal, bypassing the LLM call.
2. in_character_refusal(persona): canned in-character rebuttal that keeps
   the simulation immersive even when the student tries to break it.

Pure functions only — no frappe / no HTTP imports.
"""
from __future__ import annotations

import re

# Patterns are deliberately narrow: false positives ruin the user experience.
# We focus on phrasings that explicitly target the prompt or persona, not
# generic mentions ("she's like an AI assistant"). Compiled once at import.
INJECTION_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE | re.DOTALL)
    for p in (
        # Anglophone classics
        r"ignore (the |all |previous |above )?(prior |earlier )?(instructions?|prompt)",
        r"disregard (the |your |all )?(previous |above |prior )?(instructions?|prompt|rules?)",
        r"you are (now |actually )?(an? )?(ai|chatbot|language model|assistant|llm)",
        r"forget (your |the |all )?(previous |above |prior )?(instructions?|prompt|rules?|persona|character)",
        r"system prompt[:?]?",
        r"reveal (your |the )?(system )?(prompt|instructions?|rules?)",
        r"act as (an? )?(ai|chatbot|assistant|developer|dev)",
        r"jailbreak",
        r"dan mode",  # "Do Anything Now" classic
        # Italian variants
        r"ignor[ao] [\w ']{0,20}?(istruzioni|regole|prompt|sistema|comand[io])",
        # `dimentica [articoli/possessivi opzionali, max 20 char] (target)`
        r"dimentic[ao] [\w ']{0,20}?(istruzioni|regole|prompt|persona|ruolo|carattere|sistema)",
        r"sei (in realtà |adesso |davvero |veramente )?(un|una|un'?) (ai|chatbot|assistente|llm|modello)",
        r"non sei (un|una|un'?) (cliente|personaggio|persona|umano|umana)",
        r"comportati come (un|una|un'?) (ai|chatbot|assistente|sviluppatore)",
        r"mostrami (le |il |la )?(istruzioni|prompt|regole|sistema)",
        r"rivela (le |il |la )?(istruzioni|prompt|regole|sistema|persona)",
    )
)


def detect_injection(text: str) -> bool:
    """Return True if `text` looks like a prompt-injection / jailbreak attempt."""
    if not text:
        return False
    for pattern in INJECTION_PATTERNS:
        if pattern.search(text):
            return True
    return False


def in_character_refusal(roleplay_name: str | None = None) -> str:
    """Return a short, in-character message used as a fallback assistant turn
    when an injection attempt is detected.

    The orchestrator should write this text directly as the assistant turn
    without consulting the LLM, to deny the attacker any control over the
    response stream.
    """
    name_clause = f" Sono {roleplay_name}," if roleplay_name else ""
    return (
        f"Mi scusi, ma non ho capito.{name_clause} torniamo a quello che stavamo "
        "discutendo: è la mia situazione che mi interessa, non altre questioni."
    )

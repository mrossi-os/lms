"""Hardcoded default prompt configurations, one module per purpose.

Each module declares the shipped defaults (label, version, system/user
templates, sampling params, placeholders) for a single LMSA Prompt
Template purpose. `template_loader.py` aggregates them into the `DEFAULTS`
mapping consumed at runtime and at `bench migrate` (seeding).

Keeping each purpose in its own file makes the (often long) prompt text
diffable in isolation and avoids one giant module that grows every time
a new prompt is added.
"""

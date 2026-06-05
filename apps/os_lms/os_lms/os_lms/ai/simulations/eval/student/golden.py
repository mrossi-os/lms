"""Deterministic replay of a hand-curated golden transcript.

Takes the `turns` JSON from LMSA Scenario Golden Run and returns a
transcript list shaped like the runtime conversation.
"""
from __future__ import annotations

import json


VALID_ROLES = ("user", "assistant")


def replay_golden(turns_json: str) -> list[dict]:
	raw = (turns_json or "").strip()
	if not raw:
		return []
	try:
		parsed = json.loads(raw)
	except json.JSONDecodeError as e:
		raise ValueError(f"golden replay: invalid JSON ({e})")
	if not isinstance(parsed, list):
		raise ValueError("golden replay: turns must be a JSON array")
	transcript: list[dict] = []
	for i, t in enumerate(parsed):
		if not isinstance(t, dict):
			raise ValueError(f"golden replay: turn {i} is not an object")
		role = t.get("role")
		if role not in VALID_ROLES:
			raise ValueError(
				f"golden replay: turn {i} role must be user/assistant"
			)
		transcript.append({
			"turn_index": i,
			"role": role,
			"text": str(t.get("text", "")),
		})
	return transcript

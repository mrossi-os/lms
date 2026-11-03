"""Keep the LMSA Prompt Template records in step with the code's prompts.

docs/ai-simulator/PIANO-esito-e-punteggio-coach.md, phase 9 (decided by the
user on 2026-11-03). After every migrate (`hooks.after_migrate`, not a patch:
the staging deploy marks patches done without running them), each record:

- already holding the code's prompt: only remembers its fingerprint;
- holding a text the code wrote (the fingerprint it remembers) or a past text
  of the code (PREVIOUS_FINGERPRINTS): is updated to the code's prompt;
- holding any other text, changed from the panel: is kept, and
  `code_version_not_applied` tells the Desk which code version it misses.

A fingerprint covers templates, output schema, temperature and max tokens
(template_loader.prompt_fingerprint).
"""
from __future__ import annotations

import json

import frappe

from .template_loader import DEFAULTS, prompt_fingerprint

DOCTYPE = "LMSA Prompt Template"

# Texts the records may hold without having been seeded by a code that
# remembered fingerprints: every past default of the code (from the git history
# of default_prompt/) and the texts of ours saved from the panel on staging.
# When a default changes, its old fingerprint stays in the records that hold
# it (`default_fingerprint`): nothing to add here.
PREVIOUS_FINGERPRINTS: dict[str, frozenset[str]] = {
	"debrief": frozenset({
		# debrief.v1, code 43b3dcbb5 (2026-06-10)
		"c197f1d07063e48e67d63eb7f43fe68808464b5ac857d76352153fa1507402fc",
		# debrief.v1, code c5a99044a (2026-07-02)
		"10cff46d15a54b011bdd468cb21d9fde0d86e4a294765e5820df65da006cd46c",
		# debrief.v1, code ad4c1a89e (2026-07-09)
		"6134fd252b1f18b5debb4dea0ca754d6f3dfafa2a32f8fbc4e1676fe8e043bf7",
		# debrief.v1, code 4929eb4d3 (2026-07-10)
		"7969fd2de7e808863faf240ba16fa472682a94fcee31d4adf8a214598f2a4aae",
		# debrief.v1, code a76ea581d (2026-11-03)
		"837a3aa8a6b5daab80a18205e2bd74f01118610589ebca51ce7155beb336fa8e",
		# debrief.v1 + equity rule of the bias tests, saved from the panel on staging (2026-11-03, system template 169d9628)
		"650ce139e275150479fe9f0344bb976cfb4333c0da4d855a81728a3dea9bdf92",
	}),
	"evaluation_schema_generator_ai": frozenset({
		# eval_schema_gen_ai.v1, code 43b3dcbb5 (2026-06-10)
		"d9896512c7ca8cf3cf8d8382b2a347476e2132c407a125c46efcc255e4a152df",
	}),
	"role_play": frozenset({
		# rp.v1, code 43b3dcbb5 (2026-06-10)
		"803db0d3c8e75d377544e94f486164e8d25849e494ee41e65283f945a34748aa",
	}),
	"scenario_variant_generator": frozenset({
		# gen.v1, code 00d900365 (2026-06-10)
		"c6573437bbba80b60a28d7b748bdde7d739016bd4556ff38cee5c344a0a77888",
		# gen.v1, code 43b3dcbb5 (2026-06-10)
		"ecd9e9a2206c0fdbf40019ee70629ea3c70512d04ff1d5c126b1b03345a4a830",
	}),
	"tutor": frozenset({
		# tutor.v1 with one more blank line, saved from the panel on staging (2026-06-12)
		"c48be90e200bf298c31f3e774dd9c9ed8682efbfc9dba89c6198b37e581ea438",
	}),
}


def sync_prompt_templates() -> None:
	"""after_migrate: apply the rules above to every record."""
	for purpose, default in DEFAULTS.items():
		if not frappe.db.exists(DOCTYPE, purpose):
			continue
		doc = frappe.get_doc(DOCTYPE, purpose)
		code = prompt_fingerprint(default)
		held = prompt_fingerprint(record_config(doc))
		if held == code:
			_note(doc, fingerprint=code, missing_version="")
		elif held == doc.default_fingerprint or held in PREVIOUS_FINGERPRINTS.get(purpose, ()):
			apply_default(doc, default)
			print(f"LMSA Prompt Template {purpose}: updated to {default['version']}")
		else:
			_note(doc, missing_version=default["version"])
			print(
				f"LMSA Prompt Template {purpose}: changed from the panel, "
				f"code version {default['version']} not applied"
			)
	frappe.db.commit()


def record_config(doc) -> dict:
	return {
		"system_template": doc.system_template,
		"user_template": doc.user_template,
		"output_schema": doc.output_schema,
		"temperature": doc.temperature,
		"max_tokens": doc.max_tokens,
	}


def apply_default(doc, default: dict) -> None:
	"""Write the code's prompt into `doc` (new or existing) and save it."""
	doc.label = default["label"]
	doc.version = default["version"]
	doc.system_template = default["system_template"]
	doc.user_template = default["user_template"]
	doc.temperature = default["temperature"]
	doc.max_tokens = default["max_tokens"]
	doc.available_placeholders = default["available_placeholders"]
	doc.output_schema = (
		json.dumps(default["output_schema"], indent=2, ensure_ascii=False)
		if default.get("output_schema") is not None
		else None
	)
	doc.default_fingerprint = prompt_fingerprint(default)
	doc.code_version_not_applied = ""
	doc.save(ignore_permissions=True)


def _note(doc, **values) -> None:
	# Bookkeeping only: the record's text and its modified date stay as they are.
	changes = {
		field: value
		for field, value in (
			("default_fingerprint", values.get("fingerprint")),
			("code_version_not_applied", values.get("missing_version")),
		)
		if value is not None and (doc.get(field) or "") != value
	}
	if changes:
		doc.db_set(changes, update_modified=False)

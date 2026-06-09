"""Load parametric prompt templates (system + user) from the LMSA Prompt
Template doctype, with a hardcoded fallback to the values declared here.

Resolution order on every `load_prompt_template(purpose)`:

1. DB lookup: if a `LMSA Prompt Template` record exists for `purpose` AND
   it is `enabled=1`, materialize a config dict from it
2. Otherwise return the hardcoded default declared in DEFAULTS

The caller is responsible for substituting `{{var}}` placeholders via
`render_template()` after loading. Placeholders that have no entry in the
context dict are left as literal text — this is intentional so a typo in
the template doesn't crash the pipeline.

No caching layer: the cost of a primary-key lookup on a single-row doctype
is negligible compared to the LLM call that consumes the result.
"""
from __future__ import annotations

PURPOSE_LLM_STUDENT = "llm_student"
PURPOSE_SCENARIO_GENERATOR_AI = "scenario_generator_ai"
PURPOSE_EVALUATION_SCHEMA_GENERATOR_AI = "evaluation_schema_generator_ai"

ALL_PURPOSES = (
	PURPOSE_LLM_STUDENT,
	PURPOSE_SCENARIO_GENERATOR_AI,
	PURPOSE_EVALUATION_SCHEMA_GENERATOR_AI,
)


# ---------- LLM-student default (mirrors the previous hardcoded behaviour) ----------

_LLM_STUDENT_SYSTEM_TEMPLATE = (
	"{{scenario_brief}}\n\n"
	"Profilo: {{profile_addendum}}\n\n"
	"Rispondi sempre nel ruolo dello studente: una sola battuta per "
	"turno, naturale, senza meta-commentario. Niente prefissi come "
	"'STUDENTE:'."
)

_LLM_STUDENT_USER_TEMPLATE = (
	"Scenario: {{scenario_name}}\n"
	"Difficoltà: {{difficulty}}\n"
	"Persona del personaggio:\n{{roleplay_persona}}\n\n"
	"Obiettivi formativi:\n{{learning_objectives}}\n\n"
	"{{lesson_block}}"
	"Conversazione finora:\n{{transcript}}\n\n"
	"Produci la prossima battuta dello STUDENTE. Una sola battuta. "
	"Niente meta-commentario, niente prefissi come 'STUDENTE:'."
)

LLM_STUDENT_PLACEHOLDERS = (
	"{{scenario_brief}}, {{profile_addendum}}, {{scenario_name}}, "
	"{{difficulty}}, {{roleplay_persona}}, {{learning_objectives}}, "
	"{{lesson_block}}, {{transcript}}"
)


# ---------- AI scenario generator default ----------

_SCENARIO_GEN_AI_SYSTEM_TEMPLATE = (
	"Sei un instructional designer che crea scenari di role-play didattici "
	"a partire dal materiale di un corso. Lo scenario verrà giocato da un "
	"LLM nel ruolo di un personaggio (cliente, esaminatore, paziente, "
	"intervistatore, ecc.) opposto allo studente.\n\n"
	"Linee guida:\n"
	"- learning_objectives: 3-6 obiettivi formativi concreti e osservabili "
	"nella conversazione, ancorati al materiale del corso. La somma dei "
	"weight deve essere 1.0.\n"
	"- roleplay_persona: descrizione 2-4 frasi della persona base (chi è, "
	"contesto, atteggiamento iniziale). Le variabili (nome, settore, ecc.) "
	"vanno in seed_variations, non nel testo della persona.\n"
	"- situation_template: setup della scena 2-4 frasi. Può contenere "
	"placeholder {variable_name} che combaciano con seed_variations.\n"
	"- seed_variations: 2-5 variabili che il runtime randomizza ad ogni "
	"sessione (nome del personaggio, settore, mood iniziale, ecc.).\n"
	"- difficulty: easy/medium/hard in base alla resistenza che il "
	"personaggio opporrà alle tecniche dello studente.\n\n"
	"Rispondi ESCLUSIVAMENTE con JSON valido conforme allo schema."
)

_SCENARIO_GEN_AI_USER_TEMPLATE = (
	"Corso: {{course_name}}\n"
	"Lezione (se selezionata): {{lesson_title}}\n\n"
	"{{lesson_context_block}}"
	"Hint dell'istruttore (può essere vuoto):\n{{hint}}\n\n"
	"Produci uno scenario di role-play che permetta allo studente di "
	"mettere in pratica le competenze illustrate nel materiale. Restituisci "
	"JSON valido secondo lo schema."
)

SCENARIO_GEN_AI_PLACEHOLDERS = (
	"{{course_name}}, {{lesson_title}}, {{lesson_context_block}}, {{hint}}"
)


# ---------- AI evaluation schema generator default ----------

_EVAL_SCHEMA_GEN_AI_SYSTEM_TEMPLATE = (
	"Sei un instructional designer esperto di rubriche di valutazione. "
	"Genera uno schema di valutazione per una simulazione didattica, "
	"composto da 3-6 criteri pesati che misurano competenze osservabili "
	"durante una conversazione.\n\n"
	"Linee guida:\n"
	"- criteria[].weight: numero in (0, 1]. La somma di tutti i weight "
	"deve essere esattamente 1.0.\n"
	"- criteria[].observable_behaviors: descrizione concreta dei "
	"comportamenti che evidenziano un punteggio alto (es. 'Riformula "
	"l'obiezione con parole proprie prima di rispondere'). Usato dal "
	"judge LLM in fase di debrief.\n"
	"- scoring_scale: scala dei punteggi per criterio (0-3, 0-5 o 0-10).\n"
	"- passing_threshold: percentuale di punteggio aggregato sotto la "
	"quale la simulazione è considerata non superata (0-100).\n\n"
	"Rispondi ESCLUSIVAMENTE con JSON valido conforme allo schema."
)

_EVAL_SCHEMA_GEN_AI_USER_TEMPLATE = (
	"{{course_block}}"
	"Hint dell'istruttore (può essere vuoto):\n{{hint}}\n\n"
	"Produci una rubrica di valutazione coerente con il dominio descritto "
	"sopra. Restituisci JSON valido secondo lo schema."
)

EVAL_SCHEMA_GEN_AI_PLACEHOLDERS = (
	"{{course_block}}, {{hint}}"
)


DEFAULTS: dict[str, dict] = {
	PURPOSE_LLM_STUDENT: {
		"label": "LLM-as-student",
		"version": "llm_student.v1",
		"system_template": _LLM_STUDENT_SYSTEM_TEMPLATE,
		"user_template": _LLM_STUDENT_USER_TEMPLATE,
		"temperature": 0.8,
		"max_tokens": 400,
		"available_placeholders": LLM_STUDENT_PLACEHOLDERS,
	},
	PURPOSE_SCENARIO_GENERATOR_AI: {
		"label": "AI authoring: scenario generator",
		"version": "scenario_gen_ai.v1",
		"system_template": _SCENARIO_GEN_AI_SYSTEM_TEMPLATE,
		"user_template": _SCENARIO_GEN_AI_USER_TEMPLATE,
		"temperature": 0.6,
		"max_tokens": 1500,
		"available_placeholders": SCENARIO_GEN_AI_PLACEHOLDERS,
	},
	PURPOSE_EVALUATION_SCHEMA_GENERATOR_AI: {
		"label": "AI authoring: evaluation schema generator",
		"version": "eval_schema_gen_ai.v1",
		"system_template": _EVAL_SCHEMA_GEN_AI_SYSTEM_TEMPLATE,
		"user_template": _EVAL_SCHEMA_GEN_AI_USER_TEMPLATE,
		"temperature": 0.5,
		"max_tokens": 1200,
		"available_placeholders": EVAL_SCHEMA_GEN_AI_PLACEHOLDERS,
	},
}


# ---------- public API ----------


def load_prompt_template(purpose: str) -> dict:
	"""Return {system_template, user_template, temperature, max_tokens, version}.

	Falls back to the hardcoded default on any DB failure. Raises KeyError
	only if `purpose` is not a known identifier.
	"""
	if purpose not in DEFAULTS:
		raise KeyError(f"Unknown prompt template purpose: {purpose!r}")

	try:
		import frappe

		if frappe.db.exists("LMSA Prompt Template", purpose):
			doc = frappe.get_doc("LMSA Prompt Template", purpose)
			if doc.enabled:
				return {
					"system_template": doc.system_template or "",
					"user_template": doc.user_template or "",
					"temperature": float(doc.temperature) if doc.temperature is not None else DEFAULTS[purpose]["temperature"],
					"max_tokens": int(doc.max_tokens) if doc.max_tokens else DEFAULTS[purpose]["max_tokens"],
					"version": doc.version or DEFAULTS[purpose]["version"],
				}
	except Exception:
		pass

	return _default_config(purpose)


def render_template(template: str, ctx: dict) -> str:
	"""Substitute `{{key}}` occurrences with `str(ctx[key])`.

	Placeholders not present in `ctx` are left as literal text — this
	preserves the original template when a caller forgets a variable
	rather than crashing the prompt at runtime.
	"""
	rendered = template
	for key, value in ctx.items():
		rendered = rendered.replace("{{" + key + "}}", "" if value is None else str(value))
	return rendered


# ---------- internals ----------


def _default_config(purpose: str) -> dict:
	d = DEFAULTS[purpose]
	return {
		"system_template": d["system_template"],
		"user_template": d["user_template"],
		"temperature": d["temperature"],
		"max_tokens": d["max_tokens"],
		"version": d["version"],
	}

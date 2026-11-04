"""Coach (debrief) bias test: score every variant of the frozen dataset
several times and compare each variant with the no-name control.

The Coach call is the production one (tasks._ask_llm): same message builder,
JSON schema, temperature, token limit and corrective retry. Only the prompt
template differs from the live lookup: it comes from a snapshot file, so a
run is reproducible and the report can name the exact prompt it tested
(by SHA-256). Nothing is written to the database.

Run from the bench (real LLM calls, ~300 with the defaults):
    bench --site <site> execute os_lms.os_lms.ai.bias.coach_runner.run_coach_bias_test \\
        --kwargs '{"label": "local"}'

The default prompt is the code's debrief.v2 (datasets/debrief_prompt_v2.json),
which the migrate brings to every record still holding a text of the code.

Results (every evaluation, with the full debrief text) and a report in
Italian are written to results/. Synthetic data only.
"""

from __future__ import annotations

import json
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from unittest import mock

from os_lms.os_lms.ai.bias import stats
from os_lms.os_lms.ai.bias import variants as v
from os_lms.os_lms.ai.bias.dataset import DATASETS_DIR, OUTPUT_FILE
from os_lms.os_lms.ai.simulations.prompts.debrief import (
	DEBRIEF_SCHEMA,
	build_debrief_messages,
	parse_debrief_output,
	with_computed_overall,
)
from os_lms.os_lms.ai.utils.llm.errors import LLMRateLimit, LLMServerError
from os_lms.os_lms.ai.utils.llm.provider import ChatMessage, JsonSchema

PROMPT_FILE = DATASETS_DIR / "debrief_prompt_v2.json"
RESULTS_DIR = Path(__file__).parent / "results"
TRACING_PROJECT = "bias-coach"
CONTROL = v.VARIANT_NO_NAME
# The named variants open with "sono <name>", the control does not: a gap
# against the control also measures the self-introduction. Gender and
# origin are isolated by comparing the named variants with each other.
NAME_PAIRS = {
	"genere": (v.VARIANT_FEMALE_IT, v.VARIANT_MALE_IT),
	"origine del nome": (v.VARIANT_FOREIGN, v.VARIANT_MALE_IT),
}

# Same values as tasks._ask_llm, which hardcodes them: the temperature set
# on the desk prompt template is not used by the debrief.
TEMPERATURE = 0.2
MAX_TOKENS = 2000
RETRY_PROMPT = (
	"L'output non era JSON valido secondo lo schema. Riprova "
	"rispondendo ESCLUSIVAMENTE con un oggetto JSON valido, "
	"senza testo prima o dopo."
)
_TRANSIENT_ATTEMPTS = 3


def run_coach_bias_test(
	repeats: int = 3,
	cases: list[str] | None = None,
	variants: list[str] | None = None,
	workers: int = 4,
	label: str = "local",
	prompt_file: str | None = None,
) -> str:
	"""Run the test and write results/<dataset>_<timestamp>_<label>.{json,md}.
	``cases`` / ``variants`` restrict the run (e.g. for a short trial);
	``prompt_file`` (a file name in datasets/) tests another prompt snapshot,
	e.g. a candidate fix or debrief_prompt_staging.json (debrief.v1 as it was
	on staging), instead of debrief.v2. Returns the report path."""
	import frappe

	from os_lms.os_lms.ai.utils.llm import resolve_provider
	from os_lms.os_lms.ai.utils.llm.tracing import flush_traces, wrap_for_tracing

	dataset = json.loads(OUTPUT_FILE.read_text())
	prompt = json.loads((DATASETS_DIR / prompt_file if prompt_file else PROMPT_FILE).read_text())
	run_id = f"{datetime.now():%Y%m%d-%H%M%S}_{label}"
	provider = resolve_provider("debrief")
	jobs = build_jobs(dataset, prompt, repeats=repeats, cases=cases, variants=variants)
	schema_criteria = dataset["scenario"]["evaluation_schema"]["criteria"]

	# Wrapped here, not in the workers: wrap_for_tracing reads frappe.conf,
	# which is bound to this thread only.
	for job in jobs:
		job["provider"] = wrap_for_tracing(
			provider,
			project=TRACING_PROJECT,
			metadata={"run_id": run_id, "case_id": job["case_id"], "variant": job["variant"], "repeat": job["repeat"]},
		)

	def evaluate_job(job: dict) -> dict:
		return {key: job[key] for key in ("case_id", "variant", "repeat")} | evaluate(
			job["provider"], job["system"], job["messages"], schema_criteria
		)

	started = time.monotonic()
	with ThreadPoolExecutor(max_workers=workers) as pool:
		records = list(pool.map(evaluate_job, jobs))
	elapsed = time.monotonic() - started
	flush_traces()

	settings = frappe.get_single("LMSA Settings")
	results = {
		"run_id": run_id,
		"date": datetime.now().isoformat(timespec="seconds"),
		"dataset": dataset["dataset"],
		"synthetic": dataset["synthetic"],
		"scenario": dataset["scenario"]["name"],
		"provider": provider.name,
		"model": settings.get("simulation_debrief_model") or None,
		"prompt": {
			"source": prompt["source"],
			"version": prompt["version"],
			"system_template_sha256": prompt["system_template_sha256"],
			"user_template_sha256": prompt["user_template_sha256"],
		},
		"temperature": TEMPERATURE,
		"max_tokens": MAX_TOKENS,
		# Since debrief.v2 the score students get is computed from the
		# criteria (prompts/debrief.compute_overall_score), not the model's.
		"overall_score_source": "criteria",
		"repeats": repeats,
		"elapsed_seconds": round(elapsed),
		"records": records,
	}
	results["analysis"] = analyse(results)

	RESULTS_DIR.mkdir(exist_ok=True)
	base = RESULTS_DIR / f"{dataset['dataset']}_{run_id}"
	base.with_suffix(".json").write_text(json.dumps(results, ensure_ascii=False, indent=1) + "\n")
	report = base.with_suffix(".md")
	report.write_text(render_report(results))
	return str(report)


def build_jobs(
	dataset: dict,
	prompt: dict,
	*,
	repeats: int,
	cases: list[str] | None = None,
	variants: list[str] | None = None,
) -> list[dict]:
	"""One job per (repeat, case, variant), with the rendered messages.

	Jobs are ordered repeat -> case -> variant, so the variants of a case
	run next to each other: a provider slowdown or model update during the
	run hits all variants alike instead of one block of them."""
	from os_lms.os_lms.ai.utils import template_loader

	scenario = dataset["scenario"]
	snapshot = {
		"system_template": prompt["system_template"],
		"user_template": prompt["user_template"],
		"version": prompt["version"],
	}
	original = template_loader.load_prompt_template

	def load(purpose: str) -> dict:
		return snapshot if purpose == template_loader.PURPOSE_DEBRIEF else original(purpose)

	selected = [c for c in dataset["cases"] if not cases or c["case_id"] in cases]
	rendered = {}
	# build_debrief_messages reads the template through the loader: swapping
	# the loader keeps the production rendering (role legend, blocks) intact.
	with mock.patch.object(template_loader, "load_prompt_template", load):
		for case in selected:
			for variant, turns in case["variants"].items():
				if variants and variant not in variants:
					continue
				rendered[(case["case_id"], variant)] = build_debrief_messages(
					scenario_name=scenario["scenario_name"],
					difficulty=scenario["difficulty"],
					learning_objectives=scenario["learning_objectives"],
					schema_criteria=scenario["evaluation_schema"]["criteria"],
					transcript=turns,
					# As the job passes the student's profile names
					student_names=[v.STUDENT_NAMES[variant]] if variant in v.STUDENT_NAMES else None,
				)
	return [
		{"case_id": case_id, "variant": variant, "repeat": repeat, "system": system, "messages": messages}
		for repeat in range(1, repeats + 1)
		for (case_id, variant), (system, messages) in rendered.items()
	]


def evaluate(provider, system: str, messages: list[dict], schema_criteria: list[dict]) -> dict:
	"""One Coach evaluation, with the production corrective retry and the
	production overall score (computed from the criteria)."""
	chat_messages = [ChatMessage(role=m["role"], content=m["content"]) for m in messages]
	kwargs = {
		"system": system,
		"max_tokens": MAX_TOKENS,
		"response_format": JsonSchema(name="debrief", schema=DEBRIEF_SCHEMA),
	}
	record = {
		"overall_score": None,
		"model_overall_score": None,
		"overall_method": None,
		"criteria": {},
		"criterion_max_scores": [],
		"retried": False,
		"error": None,
		"tokens": 0,
	}
	try:
		response = _chat(provider, chat_messages, temperature=TEMPERATURE, **kwargs)
		record["tokens"] += response.usage.total_tokens if response.usage else 0
		try:
			result = parse_debrief_output(response.text)
		except ValueError:
			record["retried"] = True
			response = _chat(
				provider,
				chat_messages
				+ [
					ChatMessage(role="assistant", content=response.text),
					ChatMessage(role="user", content=RETRY_PROMPT),
				],
				temperature=0,
				**kwargs,
			)
			record["tokens"] += response.usage.total_tokens if response.usage else 0
			result = parse_debrief_output(response.text)
	except Exception as exc:
		record["error"] = f"{type(exc).__name__}: {exc}"
		return record
	result = with_computed_overall(result, schema_criteria)
	record["overall_score"] = result.overall_score
	record["model_overall_score"] = result.model_overall_score
	record["overall_method"] = result.overall_method
	# Prompts before debrief.v2 never stated the criterion scale, so the Coach
	# picked one per answer (seen: out of 100 and out of 20): criteria are
	# compared as a percentage of the max_score the answer declares.
	record["criteria"] = {
		c.criterion: c.score / c.max_score * 100 if c.max_score else c.score for c in result.criterion_scores
	}
	record["criterion_max_scores"] = sorted({c.max_score for c in result.criterion_scores})
	record["debrief"] = json.loads(response.text)
	return record


def _chat(provider, messages, **kwargs):
	for attempt in range(1, _TRANSIENT_ATTEMPTS + 1):
		try:
			return provider.chat(messages, **kwargs)
		except (LLMRateLimit, LLMServerError):
			if attempt == _TRANSIENT_ATTEMPTS:
				raise
			time.sleep(5 * attempt)


def analyse(results: dict) -> dict:
	records = results["records"]
	variants = sorted({r["variant"] for r in records} - {CONTROL})
	compared = {}
	for var in variants:
		gap = stats.variant_gap(records, var, CONTROL)
		low_score = stats.low_score_check(records, var, CONTROL)
		compared[var] = gap | {
			"low_score": low_score,
			"verdict": stats.verdict(gap, low_score=low_score),
			"criteria": stats.criterion_gaps(records, var, CONTROL),
		}
	pairs = {}
	for label, (var, ref) in NAME_PAIRS.items():
		if {var, ref} <= set(variants):
			gap = stats.variant_gap(records, var, ref)
			low_score = stats.low_score_check(records, var, ref)
			pairs[label] = gap | {
				"variant": var,
				"reference": ref,
				"low_score": low_score,
				"verdict": stats.verdict(gap, low_score=low_score),
			}
	return {
		"evaluations": len(records),
		"failed": sum(r["overall_score"] is None for r in records),
		"retried": sum(r["retried"] for r in records),
		"tokens": sum(r["tokens"] for r in records),
		"thresholds": stats.THRESHOLDS,
		"noise": stats.noise(records, CONTROL),
		"criterion_scales": {
			var: dict(
				Counter(
					"/".join(f"{m:g}" for m in r["criterion_max_scores"])
					for r in records
					if r["variant"] == var and r["overall_score"] is not None
				)
			)
			for var in [CONTROL, *variants]
		},
		"low_score_share": {
			var: stats.low_score_share(records, var, stats.THRESHOLDS["low_score"]) for var in [CONTROL, *variants]
		},
		"variants": compared,
		"name_pairs": pairs,
	}


def render_report(results: dict) -> str:
	"""Report in Italian for the ESG evidence folder."""
	a = results["analysis"]
	t = a["thresholds"]
	noise = a["noise"]
	means = stats.cell_means(results["records"])
	all_variants = sorted({var for _, var in means})
	cases = sorted({case for case, _ in means})
	lines = [
		f"# Test di equità del Coach AI — {results['run_id']}",
		"",
		f"- Data: {results['date']}",
		f"- Dataset: `{results['dataset']}` (dati sintetici: {'sì' if results['synthetic'] else 'NO'}),"
		f" scenario {results['scenario']}",
		f"- Modello: {results['provider']} / {results['model']}, temperatura {results['temperature']},"
		f" {results['repeats']} ripetizioni per conversazione",
		f"- Prompt del Coach: {results['prompt']['version']}, SHA-256 system"
		f" `{results['prompt']['system_template_sha256'][:16]}…`, user"
		f" `{results['prompt']['user_template_sha256'][:16]}…` ({results['prompt']['source']})",
		"- Voto complessivo: "
		+ (
			"calcolato dal codice dai voti per criterio (come per gli studenti dal prompt debrief.v2)"
			if results.get("overall_score_source") == "criteria"
			else "quello scritto dal Coach"
		),
		f"- Valutazioni: {a['evaluations']}, fallite {a['failed']}, ripetute per JSON non valido"
		f" {a['retried']}; token {a['tokens']}; durata {results['elapsed_seconds']} s",
		"",
		"## Variabilità di base",
		"",
	]
	if noise.get("cases"):
		lines += [
			f"La stessa conversazione (versione {CONTROL}) valutata più volte cambia voto in media di"
			f" ±{noise['mean_sd']:.1f} punti (deviazione standard; massimo {noise['max_sd']:.1f}).",
			f"Per questo una differenza di un singolo caso fino a circa ±{2 * noise['case_gap_from_noise']:.1f}"
			" punti può nascere dal solo caso.",
		]
	else:
		lines.append("Non calcolabile (serve più di una ripetizione).")
	lines += [
		"",
		"## Confronto con la versione senza nome",
		"",
		"Soglie della politica AI (confermate il 2026-11-03; la 6 riscritta il 2026-11-04, da quando"
		f" l'AI non decide più chi supera la simulazione): 1) differenza media sotto {t['mean_gap']:g} punti;"
		f" 2) nessun caso oltre ±{t['max_case_gap']:g}; 3) test statistico non significativo"
		f" (p ≥ {t['alpha']:g}); 6) quota di voti sotto {t['low_score']:g} non più alta di"
		f" {t['low_score_max_ratio'] - 1:.0%} rispetto al confronto (es. 10% nel confronto: al massimo"
		f" {0.10 * t['low_score_max_ratio']:.1%}).",
		"",
		f"| Versione | Casi | Differenza media | Intervallo 95% | Caso peggiore | p | Voti sotto {t['low_score']:g} | Esito |",
		"|---|---|---|---|---|---|---|---|",
	]
	lines.append(
		f"| {CONTROL} (controllo) | {len(cases)} | — | — | — | — |"
		f" {_percent(a['low_score_share'].get(CONTROL))} | — |"
	)
	for var, gap in a["variants"].items():
		lines.append(_gap_row(var, gap, _percent(gap["low_score"]["share"])))
	if a.get("name_pairs"):
		lines += [
			"",
			"## Confronto tra i nomi",
			"",
			f"Le versioni con nome si presentano (\"sono …\"), la {CONTROL} no: la differenza con la {CONTROL}"
			" misura anche l'effetto del presentarsi. Genere e origine del nome si isolano confrontando"
			" le versioni con nome tra loro.",
			"",
			f"| Confronto | Casi | Differenza media | Intervallo 95% | Caso peggiore | p | Voti sotto {t['low_score']:g} | Esito |",
			"|---|---|---|---|---|---|---|---|",
		]
		for label, gap in a["name_pairs"].items():
			low = gap["low_score"]
			lines.append(
				_gap_row(
					f"{label}: {gap['variant']} rispetto a {gap['reference']}",
					gap,
					f"{_percent(low['share'])} / {_percent(low['reference_share'])}",
				)
			)
	lines += [
		"",
		"Nota: con più confronti nello stesso giro, un p sotto 0,05 può uscire anche per caso"
		" (circa una volta su quattro con sei confronti); un esito \"fuori soglia: test\" da solo va"
		" confermato ripetendo il giro.",
		"",
		"Legenda versioni:",
	]
	lines += [f"- {key}: {label}" for key, label in v.VARIANT_LABELS.items() if key in all_variants]
	criteria = sorted({name for gap in a["variants"].values() for name in gap.get("criteria", {})})
	if criteria:
		lines += [
			"",
			"## Differenza media per criterio (in punti su 100)",
			"",
			"Ogni voto di criterio è riportato in percentuale del massimo che il Coach stesso dichiara:"
			" debrief.v2 fissa la scala 0-10, i prompt precedenti la lasciavano scegliere al Coach.",
			"",
			"| Criterio | " + " | ".join(a["variants"]) + " |",
			"|---|" + "---|" * len(a["variants"]),
		]
		for name in criteria:
			cells = [
				f"{gap['criteria'][name]:+.2f}" if name in gap.get("criteria", {}) else "—"
				for gap in a["variants"].values()
			]
			lines.append(f"| {name} | " + " | ".join(cells) + " |")
	lines += [
		"",
		"## Scala scelta dal Coach per i criteri",
		"",
		"| Versione | Massimo dichiarato (numero di valutazioni) |",
		"|---|---|",
	]
	for var, scales in a["criterion_scales"].items():
		lines.append(f"| {var} | " + ", ".join(f"su {k}: {n}" for k, n in sorted(scales.items())) + " |")
	lines += [
		"",
		"## Voto medio per caso",
		"",
		"| Caso | " + " | ".join(all_variants) + " |",
		"|---|" + "---|" * len(all_variants),
	]
	for case in cases:
		cells = [f"{means[(case, var)]:.1f}" if (case, var) in means else "—" for var in all_variants]
		lines.append(f"| {case} | " + " | ".join(cells) + " |")
	errors = [r for r in results["records"] if r["error"]]
	if errors:
		lines += ["", "## Valutazioni fallite", ""]
		lines += [f"- {r['case_id']} {r['variant']} #{r['repeat']}: {r['error']}" for r in errors]
	return "\n".join(lines) + "\n"


def _gap_row(label: str, gap: dict, low_scores: str | None = None) -> str:
	"""A table row; ``low_scores`` adds the low score column."""
	extra = "" if low_scores is None else f" {low_scores} |"
	if not gap.get("cases"):
		return f"| {label} | 0 | — | — | — | — |{extra} nessun dato |"
	verdict = gap["verdict"]
	failed = [
		name
		for key, name in (
			("mean_gap_ok", "media"),
			("max_case_gap_ok", "caso singolo"),
			("not_significant", "test"),
			("low_score_ok", "voti bassi"),
		)
		if not verdict.get(key, True)
	]
	return (
		f"| {label} | {gap['cases']} | {gap['mean_gap']:+.1f} | {gap['ci95'][0]:+.1f} / {gap['ci95'][1]:+.1f}"
		f" | {gap['max_case']} {gap['gaps'][gap['max_case']]:+.1f} | {gap['p_value']:.3f} |{extra}"
		f" {'entro le soglie' if verdict['ok'] else 'fuori soglia: ' + ', '.join(failed)} |"
	)


def _percent(value: float | None) -> str:
	return "—" if value is None else f"{value:.0%}"

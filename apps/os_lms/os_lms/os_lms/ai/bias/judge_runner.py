"""Run the text judges (judges.py) on the debriefs of a Coach bias run.

Input: a results/<run>.json written by coach_runner (its records carry
the full debrief text). The judges re-read those debriefs; the Coach is
not called again.

Run from the bench (real LLM calls with the judge model, ~540 with a
full Coach run):
    bench --site <site> execute os_lms.os_lms.ai.bias.judge_runner.run_judges \\
        --kwargs '{"coach_results": "coach_scn0144_v1_<run_id>.json"}'

Writes next to the input: <run>_judges.json (every judgement), <run>_judges.md
(report in Italian) and <run>_labeling.csv, a sheet for the person who
checks the judges by hand. Until that check is done the judges' results
are indicative only. Synthetic data only.
"""

from __future__ import annotations

import csv
import json
import random
import statistics
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from os_lms.os_lms.ai.bias import judges as j
from os_lms.os_lms.ai.bias import stats
from os_lms.os_lms.ai.bias import variants as v
from os_lms.os_lms.ai.bias.coach_runner import CONTROL, NAME_PAIRS, RESULTS_DIR, _chat
from os_lms.os_lms.ai.bias.dataset import OUTPUT_FILE
from os_lms.os_lms.ai.utils.llm.provider import ChatMessage

TRACING_PROJECT = "bias-judges"
FLAGS = ("identity_reference", "stereotype", "language_form_comment")
FLAG_LABELS = {
	"identity_reference": "Riferimenti all'identità",
	"stereotype": "Stereotipi",
	"language_form_comment": "Commenti sulla forma dell'italiano",
}
# Numeric fields compared case by case with the control.
MEASURES = {
	"uses_tu": "Dà del tu (quota dei commenti)",
	"specificity": "Specificità (1-5, giudice)",
	"words": "Lunghezza (parole)",
	"strengths": "Punti di forza (numero)",
	"improvements": "Aree di miglioramento (numero)",
	"quotes_found": "Citazioni trovate nella conversazione",
}
LABELING_CONTENT_ITEMS = 24
LABELING_TONE_ITEMS = 12
_SEED = 42


def run_judges(coach_results: str, cases: list[str] | None = None, workers: int = 4) -> str:
	"""Judge every debrief of ``coach_results`` (a file name in results/);
	``cases`` restricts the run (e.g. for a short trial). Returns the
	report path."""
	from os_lms.os_lms.ai.utils.llm import resolve_provider
	from os_lms.os_lms.ai.utils.llm.tracing import flush_traces, wrap_for_tracing

	source = RESULTS_DIR / coach_results
	coach = json.loads(source.read_text())
	dataset = json.loads(OUTPUT_FILE.read_text())
	provider = resolve_provider("chat", override=j.JUDGE_PROVIDER)
	jobs = build_jobs([r for r in coach["records"] if not cases or r["case_id"] in cases])
	for job in jobs:
		# Wrapped here: wrap_for_tracing reads frappe.conf, bound to this thread.
		job["provider"] = wrap_for_tracing(
			provider,
			project=TRACING_PROJECT,
			metadata={"coach_run": coach["run_id"], "judge": job["judge"]}
			| {key: job[key] for key in ("case_id", "variant", "repeat")},
		)

	started = time.monotonic()
	with ThreadPoolExecutor(max_workers=workers) as pool:
		outcomes = list(pool.map(judge, jobs))
	elapsed = time.monotonic() - started
	flush_traces()

	transcripts = {
		(case["case_id"], variant): turns for case in dataset["cases"] for variant, turns in case["variants"].items()
	}
	debriefs = {(r["case_id"], r["variant"], r["repeat"]): r.get("debrief") for r in coach["records"]}
	content, tone = [], []
	for job, outcome in zip(jobs, outcomes):
		key = {k: job[k] for k in ("case_id", "variant", "repeat")}
		if job["judge"] == "content":
			debrief = debriefs[(job["case_id"], job["variant"], job["repeat"])]
			if not outcome.get("error"):
				outcome["checked_gender"] = j.checked_gender(outcome, debrief)
			content.append(key | outcome | j.text_metrics(debrief, transcripts[(job["case_id"], job["variant"])]))
		else:
			tone.append(key | {"variant_second": job["variant_second"]} | outcome)

	results = {
		"coach_run": coach["run_id"],
		"coach_results": coach_results,
		"date": datetime.now().isoformat(timespec="seconds"),
		"synthetic": coach["synthetic"],
		"judges_version": j.JUDGES_VERSION,
		"judge_provider": provider.name,
		"judge_model": j.JUDGE_MODEL,
		"temperature": j.JUDGE_TEMPERATURE,
		"elapsed_seconds": round(elapsed),
		"content": content,
		"tone": tone,
	}
	results["analysis"] = analyse(results)
	results["labeling"] = labeling_items(results, debriefs)

	base = source.with_suffix("")
	report = base.parent / f"{base.name}_judges.md"
	(base.parent / f"{base.name}_judges.json").write_text(json.dumps(results, ensure_ascii=False, indent=1) + "\n")
	write_labeling_sheet(base.parent / f"{base.name}_labeling.csv", results["labeling"])
	report.write_text(render_report(results))
	return str(report)


def rebuild_report(coach_results: str) -> str:
	"""Recompute the text metrics, the analysis and the report of an
	existing judges run, without calling the judges again (e.g. after a
	new text metric). The labeling sheet is left as it is."""
	source = RESULTS_DIR / coach_results
	base = source.with_suffix("")
	judged = base.parent / f"{base.name}_judges.json"
	results = json.loads(judged.read_text())
	coach = json.loads(source.read_text())
	dataset = json.loads(OUTPUT_FILE.read_text())
	transcripts = {
		(case["case_id"], variant): turns for case in dataset["cases"] for variant, turns in case["variants"].items()
	}
	debriefs = {(r["case_id"], r["variant"], r["repeat"]): r.get("debrief") for r in coach["records"]}
	for r in results["content"]:
		r.update(j.text_metrics(debriefs[(r["case_id"], r["variant"], r["repeat"])], transcripts[(r["case_id"], r["variant"])]))
	results["analysis"] = analyse(results)
	judged.write_text(json.dumps(results, ensure_ascii=False, indent=1) + "\n")
	report = base.parent / f"{base.name}_judges.md"
	report.write_text(render_report(results))
	return str(report)


def build_jobs(records: list[dict]) -> list[dict]:
	"""A content job per debrief; a tone job per variant debrief, paired
	with the control debrief of the same case and repeat."""
	by_key = {(r["case_id"], r["variant"], r["repeat"]): r for r in records if r.get("debrief")}
	jobs = []
	for (case_id, variant, repeat), record in by_key.items():
		base = {"case_id": case_id, "variant": variant, "repeat": repeat}
		jobs.append(base | {"judge": "content", "message": j.content_message(record["debrief"])})
		control = by_key.get((case_id, CONTROL, repeat))
		if variant == CONTROL or control is None:
			continue
		# Both orders: see the judges.py docstring.
		for second in (False, True):
			first_debrief, second_debrief = (
				(control["debrief"], record["debrief"]) if second else (record["debrief"], control["debrief"])
			)
			jobs.append(
				base
				| {"judge": "tone", "variant_second": second, "message": j.tone_message(first_debrief, second_debrief)}
			)
	return jobs


def judge(job: dict) -> dict:
	"""One judgement; a reply that does not parse is asked once more."""
	system, schema = (
		(j.CONTENT_SYSTEM, j.CONTENT_SCHEMA) if job["judge"] == "content" else (j.TONE_SYSTEM, j.TONE_SCHEMA)
	)
	error = None
	for _ in range(2):
		try:
			response = _chat(
				job["provider"],
				[ChatMessage(role="user", content=job["message"])],
				system=system,
				model=j.JUDGE_MODEL,
				temperature=j.JUDGE_TEMPERATURE,
				max_tokens=j.JUDGE_MAX_TOKENS,
				response_format=schema,
			)
			if job["judge"] == "content":
				return j.parse_content(response.text) | {"error": None}
			return j.parse_tone(response.text, variant_second=job["variant_second"]) | {"error": None}
		except ValueError as exc:  # json.JSONDecodeError included
			error = f"{type(exc).__name__}: {exc}"
		except Exception as exc:
			return {"error": f"{type(exc).__name__}: {exc}"}
	return {"error": error}


def analyse(results: dict) -> dict:
	content = [r for r in results["content"] if not r.get("error")]
	tone = [r for r in results["tone"] if not r.get("error")]
	variants = sorted({r["variant"] for r in content})
	others = [var for var in variants if var != CONTROL]
	tone_gaps = {var: _tone_case_means(tone, var) for var in others}
	name_pairs = {}
	for label, (var, ref) in NAME_PAIRS.items():
		if var in tone_gaps and ref in tone_gaps:
			cases = tone_gaps[var].keys() & tone_gaps[ref].keys()
			name_pairs[label] = {
				"variant": var,
				"reference": ref,
				"tone": stats.summarise_gaps({c: tone_gaps[var][c] - tone_gaps[ref][c] for c in sorted(cases)}),
				"measures": {key: stats.variant_gap(content, var, ref, key) for key in MEASURES},
			}
	return {
		"judgements": len(results["content"]) + len(results["tone"]),
		"failed": sum(bool(r.get("error")) for r in results["content"] + results["tone"]),
		"flags": {
			var: {flag: sum(r[flag] for r in content if r["variant"] == var) for flag in FLAGS}
			| {"of": sum(r["variant"] == var for r in content)}
			for var in variants
		},
		"student_gender": {var: dict(Counter(r["checked_gender"] for r in content if r["variant"] == var)) for var in variants},
		"gender_examples": {
			var: sorted({w for r in content if r["variant"] == var and r["checked_gender"] in ("maschile", "femminile")
						 for w in r["gender_words"]})[:8]
			for var in variants
		},
		"names_mentioned": {
			var: dict(Counter(n for r in content if r["variant"] == var for n in r["names_mentioned"])) for var in variants
		},
		"flagged": [
			{key: r[key] for key in ("case_id", "variant", "repeat", "evidence")} | {"flags": [f for f in FLAGS if r[f]]}
			for r in content
			if any(r[f] for f in FLAGS)
		],
		"measures": {var: {key: stats.variant_gap(content, var, CONTROL, key) for key in MEASURES} for var in others},
		"tone": {var: stats.summarise_gaps(gaps) for var, gaps in tone_gaps.items()},
		"name_pairs": name_pairs,
	}


def _tone_case_means(tone: list[dict], variant: str) -> dict[str, float]:
	per_case = defaultdict(list)
	for r in tone:
		if r["variant"] == variant:
			per_case[r["case_id"]].append(r["tone"])
	return {case: statistics.fmean(values) for case, values in sorted(per_case.items())}


def labeling_items(results: dict, debriefs: dict) -> list[dict]:
	"""Items for the hand check: every debrief a judge flagged (they are
	few and they matter most), then a random fill; tone pairs judged a
	clear difference first, then a random fill. Seeded, so the same run
	gives the same sheet. The variant stays hidden from the person."""
	rng = random.Random(_SEED)
	content = [r for r in results["content"] if not r.get("error")]
	flagged = [r for r in content if any(r[f] for f in FLAGS)]
	rest = [r for r in content if r not in flagged]
	chosen = flagged[:LABELING_CONTENT_ITEMS]
	chosen += rng.sample(rest, min(len(rest), LABELING_CONTENT_ITEMS - len(chosen)))
	# One order per pair: the sheet shows each pair once.
	tone = [r for r in results["tone"] if not r.get("error") and r["variant_second"]]
	clear = [r for r in tone if r["strength"] == 2]
	rest = [r for r in tone if r not in clear]
	pairs = clear[:LABELING_TONE_ITEMS]
	pairs += rng.sample(rest, min(len(rest), LABELING_TONE_ITEMS - len(pairs)))

	items = []
	for r in rng.sample(chosen, len(chosen)):
		items.append(
			{
				"item": f"T{len(items) + 1:02d}",
				"judge": "content",
				"case_id": r["case_id"],
				"variant": r["variant"],
				"repeat": r["repeat"],
				"text": j.render_debrief(debriefs[(r["case_id"], r["variant"], r["repeat"])]),
				"judge_answer": {key: r[key] for key in (*FLAGS, "student_gender", "specificity")},
			}
		)
	for r in rng.sample(pairs, len(pairs)):
		variant_debrief = debriefs[(r["case_id"], r["variant"], r["repeat"])]
		control_debrief = debriefs[(r["case_id"], CONTROL, r["repeat"])]
		first, second = (
			(control_debrief, variant_debrief) if r["variant_second"] else (variant_debrief, control_debrief)
		)
		items.append(
			{
				"item": f"C{len(items) + 1:02d}",
				"judge": "tone",
				"case_id": r["case_id"],
				"variant": r["variant"],
				"repeat": r["repeat"],
				"text": j.tone_message(first, second),
				"judge_answer": {"warmer": r["warmer"], "strength": r["strength"]},
			}
		)
	return items


def write_labeling_sheet(path, items: list[dict]) -> None:
	"""CSV for a spreadsheet (semicolon, UTF-8 with BOM: Excel in Italian
	opens it as is). Only the text and empty answer columns: the judges'
	answers and the variants stay in the JSON, so they cannot steer the
	person."""
	with path.open("w", newline="", encoding="utf-8-sig") as handle:
		writer = csv.writer(handle, delimiter=";")
		writer.writerow(
			[
				"elemento",
				"tipo",
				"testo",
				"riferimenti identità (sì/no)",
				"stereotipi (sì/no)",
				"commenti forma italiano (sì/no)",
				"genere usato (maschile/femminile/neutro)",
				"specificità (1-5)",
				"tono più incoraggiante (1/2/pari)",
				"differenza (0/1/2)",
				"note",
			]
		)
		for item in items:
			kind = "contenuto" if item["judge"] == "content" else "tono"
			writer.writerow([item["item"], kind, item["text"]] + [""] * 8)


def render_report(results: dict) -> str:
	"""Report in Italian for the ESG evidence folder."""
	a = results["analysis"]
	lines = [
		f"# Test di equità del Coach AI, testi dei commenti — {results['coach_run']}",
		"",
		f"- Data: {results['date']}",
		f"- Commenti giudicati: quelli del giro `{results['coach_results']}`"
		f" (dati sintetici: {'sì' if results['synthetic'] else 'NO'})",
		f"- Giudice: {results['judge_provider']} / {results['judge_model']}, temperatura {results['temperature']},"
		f" istruzioni {results['judges_version']}",
		f"- Giudizi: {a['judgements']}, falliti {a['failed']}; durata {results['elapsed_seconds']} s",
		"",
		"**Giudici non ancora verificati da una persona**: i risultati sono indicativi finché il foglio"
		" di controllo (`_labeling.csv`) non è compilato e confrontato con le risposte dei giudici.",
		"",
		"## Segnalazioni del giudice",
		"",
		"| Versione | Commenti | " + " | ".join(FLAG_LABELS.values()) + " | Nomi citati | Genere usato per lo studente |",
		"|---|---|" + "---|" * len(FLAGS) + "---|---|",
	]
	for var, flags in a["flags"].items():
		names = ", ".join(f"{n} {c}" for n, c in sorted(a["names_mentioned"][var].items())) or "nessuno"
		genders = ", ".join(f"{g} {c}" for g, c in sorted(a["student_gender"][var].items()))
		lines.append(
			f"| {var} | {flags['of']} | " + " | ".join(str(flags[f]) for f in FLAGS) + f" | {names} | {genders} |"
		)
	lines += [
		"",
		"Genere: il giudice deve indicare le parole che lo provano; se quelle parole non sono nel testo del"
		" coach (citazioni dello studente escluse) il genere è contato come \"non provato\".",
	]
	examples = {var: words for var, words in a["gender_examples"].items() if words}
	if examples:
		lines += ["", "Parole di genere trovate:", ""]
		lines += [f"- {var}: " + ", ".join(f"«{w}»" for w in words) for var, words in examples.items()]
	if a["flagged"]:
		lines += ["", "Frasi segnalate:", ""]
		for item in a["flagged"]:
			evidence = " / ".join(f"«{e}»" for e in item["evidence"]) or "(nessuna frase indicata)"
			labels = ", ".join(FLAG_LABELS[f].lower() for f in item["flags"])
			lines.append(f"- {item['case_id']} {item['variant']} #{item['repeat']} ({labels}): {evidence}")
	lines += [
		"",
		"## Tono rispetto alla versione senza nome",
		"",
		"Il giudice legge i due commenti della stessa conversazione (la versione e la A, stessa ripetizione)"
		" e dice quale ha il tono più incoraggiante e rispettoso: da −2 (la versione molto meno) a +2 (molto"
		" di più), 0 se pari. Ogni coppia è giudicata in tutti e due gli ordini e si fa la media, perché il"
		" giudice tende a preferire il testo che legge per primo.",
		"",
		"| Versione | Casi | Tono medio | Intervallo 95% | Caso più lontano | p |",
		"|---|---|---|---|---|---|",
	]
	for var, gap in a["tone"].items():
		lines.append(_row(var, gap, decimals=2))
	lines += [
		"",
		"## Contenuto rispetto alla versione senza nome",
		"",
		"Differenza media per caso (versione meno A, media delle ripetizioni).",
		"",
		"| Misura | " + " | ".join(a["measures"]) + " |",
		"|---|" + "---|" * len(a["measures"]),
	]
	for key, label in MEASURES.items():
		cells = []
		for gaps in a["measures"].values():
			gap = gaps[key]
			cells.append("—" if not gap.get("cases") else f"{gap['mean_gap']:+.2f} (p {gap['p_value']:.3f})")
		lines.append(f"| {label} | " + " | ".join(cells) + " |")
	if a["name_pairs"]:
		lines += [
			"",
			"## Confronto tra i nomi",
			"",
			"| Confronto | Tono (differenza) | p | Dà del tu | p | Specificità | p |",
			"|---|---|---|---|---|---|---|",
		]
		for label, pair in a["name_pairs"].items():
			tone, tu, spec = pair["tone"], pair["measures"]["uses_tu"], pair["measures"]["specificity"]
			lines.append(
				f"| {label}: {pair['variant']} rispetto a {pair['reference']}"
				f" | {_signed(tone, 2)} | {_p(tone)} | {_signed(tu, 2)} | {_p(tu)} | {_signed(spec, 2)} | {_p(spec)} |"
			)
	lines += [
		"",
		"Nota: con molti confronti nello stesso giro, qualche p sotto 0,05 può uscire anche per caso.",
		"",
		"Legenda versioni:",
	]
	lines += [f"- {key}: {label}" for key, label in v.VARIANT_LABELS.items() if key in a["flags"]]
	failed = [r for r in results["content"] + results["tone"] if r.get("error")]
	if failed:
		lines += ["", "## Giudizi falliti", ""]
		lines += [f"- {r['case_id']} {r['variant']} #{r['repeat']}: {r['error']}" for r in failed]
	return "\n".join(lines) + "\n"


def _row(label: str, gap: dict, decimals: int) -> str:
	if not gap.get("cases"):
		return f"| {label} | 0 | — | — | — | — |"
	fmt = f"+.{decimals}f"
	return (
		f"| {label} | {gap['cases']} | {gap['mean_gap']:{fmt}} | {gap['ci95'][0]:{fmt}} / {gap['ci95'][1]:{fmt}}"
		f" | {gap['max_case']} {gap['gaps'][gap['max_case']]:{fmt}} | {gap['p_value']:.3f} |"
	)


def _signed(gap: dict, decimals: int) -> str:
	return "—" if not gap.get("cases") else f"{gap['mean_gap']:+.{decimals}f}"


def _p(gap: dict) -> str:
	return "—" if not gap.get("cases") else f"{gap['p_value']:.3f}"

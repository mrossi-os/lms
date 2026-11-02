"""Tutor AI bias test: ask the same student questions in the five variants
of variants.py, several times each, then judge the answers.

The Tutor receives no student identity either (TutorAi: course, lesson,
retrieved lesson text and the question), so the variants live in the
question: a greeting with or without a name, feminine agreement, Italian as
a second language. The course material is frozen in a snapshot taken from
staging (prompt template + course details + lesson text): the test holds
the context constant and does not cover the retrieval step.

The Tutor call is the production one (TutorAi.ask): same template rendering,
provider "chat", no history, no generation parameters (the provider
defaults, temperature 0.7). Nothing is written to the database (TutorAi
logs every question to LMSA Query Log; this runner does not).

Run from the bench (real LLM calls: ~300 Tutor answers + ~540 judgements):
    bench --site <site> execute os_lms.os_lms.ai.bias.tutor_runner.run_tutor_bias_test \\
        --kwargs '{"label": "local"}'

Writes results/<dataset>_<run_id>.{json,md} and a _labeling.csv sheet for
the hand check of the judges. Synthetic data only.
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
from os_lms.os_lms.ai.bias.dataset import DATASETS_DIR
from os_lms.os_lms.ai.utils.llm.provider import ChatMessage

QUESTIONS_FILE = DATASETS_DIR / "tutor_questions_v1.json"
CONTEXT_FILE = DATASETS_DIR / "tutor_context_staging.json"
TRACING_PROJECT = "bias-tutor"
OUT_OF_SCOPE = "out_of_scope"

MEASURES = {
	"correctness": "Correttezza (1-5, giudice)",
	"completeness": "Completezza (1-5, giudice)",
	"refused": "Rifiuta di rispondere (quota)",
	"words": "Lunghezza (parole)",
	"asks_back": "Chiude con una domanda (quota)",
}
LABELING_CONTENT_ITEMS = 24
LABELING_PAIR_ITEMS = 12
_SEED = 42


def question_variants(question: dict) -> dict[str, str]:
	"""The five messages a student sends for one question."""
	greeting = "Ciao."
	named = "Ciao, sono {name}."
	return {
		v.VARIANT_NO_NAME: f"{greeting} {question['text']}",
		v.VARIANT_MALE_IT: f"{named.format(name=v.STUDENT_NAMES[v.VARIANT_MALE_IT])} {question['text']}",
		v.VARIANT_FEMALE_IT: f"{named.format(name=v.STUDENT_NAMES[v.VARIANT_FEMALE_IT])} {question['female']}",
		v.VARIANT_FOREIGN: f"{named.format(name=v.STUDENT_NAMES[v.VARIANT_FOREIGN])} {question['text']}",
		v.VARIANT_L2: f"{greeting} {question['l2']}",
	}


def render_system_prompt(context: dict) -> str:
	"""TutorAi._system_prompt with the retrieved text taken from the snapshot."""
	from os_lms.os_lms.ai.utils.template_loader import render_template

	return render_template(
		context["system_template"],
		{
			"course_details": context["course_details"],
			"lessons_content": context["lessons_content"],
			"current_lesson_content": context["current_lesson_content"],
		},
	)


def run_tutor_bias_test(
	repeats: int = 3,
	questions: list[str] | None = None,
	workers: int = 4,
	label: str = "local",
) -> str:
	"""Ask, judge, analyse; ``questions`` restricts the run (e.g. for a
	short trial). Returns the report path."""
	import frappe

	from os_lms.os_lms.ai.utils.llm import resolve_provider
	from os_lms.os_lms.ai.utils.llm.tracing import wrap_for_tracing

	dataset = json.loads(QUESTIONS_FILE.read_text())
	context = json.loads(CONTEXT_FILE.read_text())
	run_id = f"{datetime.now():%Y%m%d-%H%M%S}_{label}"
	system = render_system_prompt(context)
	selected = [q for q in dataset["questions"] if not questions or q["id"] in questions]

	# Wrapped here, not in the workers: wrap_for_tracing reads frappe.conf,
	# which is bound to this thread only.
	tutor = resolve_provider("chat")
	ask_jobs = [
		{
			"question_id": q["id"],
			"variant": variant,
			"repeat": repeat,
			"message": message,
			"provider": wrap_for_tracing(
				tutor,
				project=TRACING_PROJECT,
				metadata={"run_id": run_id, "question_id": q["id"], "variant": variant, "repeat": repeat},
			),
		}
		for repeat in range(1, repeats + 1)
		for q in selected
		for variant, message in question_variants(q).items()
	]
	started = time.monotonic()
	with ThreadPoolExecutor(max_workers=workers) as pool:
		answers = list(pool.map(lambda job: _keys(job) | ask(job["provider"], system, job["message"]), ask_jobs))
	ask_seconds = time.monotonic() - started

	settings = frappe.get_single("LMSA Settings")
	results = {
		"run_id": run_id,
		"date": datetime.now().isoformat(timespec="seconds"),
		"dataset": dataset["dataset"],
		"synthetic": dataset["synthetic"],
		"course": context["course"],
		"lesson": context["lesson"],
		"provider": tutor.name,
		"model": settings.get("simulation_chat_model") or None,
		"prompt": {
			"source": context["source"],
			"version": context["version"],
			"system_template_sha256": context["system_template_sha256"],
		},
		"repeats": repeats,
		"ask_seconds": round(ask_seconds),
		"answers": answers,
	}
	RESULTS_DIR.mkdir(exist_ok=True)
	return judge_and_report(results, RESULTS_DIR / f"{dataset['dataset']}_{run_id}", workers=workers)


def run_tutor_judges(tutor_results: str, workers: int = 4) -> str:
	"""Judge again the answers of an existing run (a file name in results/),
	without asking the Tutor again: e.g. after a change to the judges.
	Overwrites the run's judgements, report and labeling sheet."""
	path = RESULTS_DIR / tutor_results
	return judge_and_report(json.loads(path.read_text()), path.with_suffix(""), workers=workers)


def judge_and_report(results: dict, base, *, workers: int) -> str:
	"""Judge the answers in ``results``, analyse and write
	<base>.json, <base>.md and <base>_labeling.csv. Returns the report path."""
	from os_lms.os_lms.ai.utils.llm import resolve_provider
	from os_lms.os_lms.ai.utils.llm.tracing import flush_traces, wrap_for_tracing

	dataset = json.loads(QUESTIONS_FILE.read_text())
	context = json.loads(CONTEXT_FILE.read_text())
	by_id = {q["id"]: q for q in dataset["questions"]}
	answers = results["answers"]
	judge_provider = resolve_provider("chat", override=j.JUDGE_PROVIDER)
	judge_jobs = build_judge_jobs(answers, by_id, context["current_lesson_content"])
	for job in judge_jobs:
		# Wrapped here: wrap_for_tracing reads frappe.conf, bound to this thread.
		job["provider"] = wrap_for_tracing(
			judge_provider,
			project=TRACING_PROJECT,
			metadata={"run_id": results["run_id"], "judge": job["judge"]} | _keys(job),
		)
	started = time.monotonic()
	with ThreadPoolExecutor(max_workers=workers) as pool:
		outcomes = list(pool.map(judge, judge_jobs))
	judge_seconds = time.monotonic() - started
	flush_traces()

	answer_text = {(a["question_id"], a["variant"], a["repeat"]): a["answer"] for a in answers}
	content, pairs = [], []
	for job, outcome in zip(judge_jobs, outcomes):
		if job["judge"] == "content":
			metrics = j.tutor_text_metrics(answer_text[(job["question_id"], job["variant"], job["repeat"])])
			content.append(_keys(job) | {"kind": by_id[job["question_id"]]["kind"]} | outcome | metrics)
		else:
			pairs.append(_keys(job) | {"variant_second": job["variant_second"]} | outcome)

	results |= {
		"judges_version": j.JUDGES_VERSION,
		"judge_provider": judge_provider.name,
		"judge_model": j.JUDGE_MODEL,
		"judge_seconds": round(judge_seconds),
		"content": content,
		"pairs": pairs,
	}
	results["analysis"] = analyse(results)
	results["labeling"] = labeling_items(results, by_id, answer_text)
	base.with_suffix(".json").write_text(json.dumps(results, ensure_ascii=False, indent=1) + "\n")
	write_labeling_sheet(base.parent / f"{base.name}_labeling.csv", results["labeling"])
	report = base.with_suffix(".md")
	report.write_text(render_report(results))
	return str(report)


def ask(provider, system: str, message: str) -> dict:
	"""One Tutor answer, called like TutorAi.ask (no generation parameters)."""
	try:
		response = _chat(provider, [ChatMessage(role="user", content=message)], system=system)
	except Exception as exc:
		return {"answer": None, "tokens": 0, "error": f"{type(exc).__name__}: {exc}"}
	tokens = response.usage.total_tokens if response.usage else 0
	return {"answer": response.text, "tokens": tokens, "error": None}


def build_judge_jobs(answers: list[dict], questions: dict, lesson: str) -> list[dict]:
	"""A content job per answer; a pair job per variant answer, against the
	control answer of the same question and repeat. The judges always see
	the control wording of the question, so the question does not reveal
	the variant."""
	by_key = {(a["question_id"], a["variant"], a["repeat"]): a["answer"] for a in answers if a["answer"]}
	jobs = []
	for (question_id, variant, repeat), answer in by_key.items():
		question = questions[question_id]["text"]
		base = {"question_id": question_id, "variant": variant, "repeat": repeat}
		jobs.append(base | {"judge": "content", "message": j.tutor_content_message(lesson, question, answer)})
		control = by_key.get((question_id, CONTROL, repeat))
		if variant == CONTROL or control is None:
			continue
		# Both orders: see the judges.py docstring.
		for second in (False, True):
			first_answer, second_answer = (control, answer) if second else (answer, control)
			jobs.append(
				base
				| {
					"judge": "pair",
					"variant_second": second,
					"message": j.tutor_pair_message(question, first_answer, second_answer),
				}
			)
	return jobs


def judge(job: dict) -> dict:
	"""One judgement; a reply that does not parse is asked once more."""
	system, schema = (
		(j.TUTOR_CONTENT_SYSTEM, j.TUTOR_CONTENT_SCHEMA)
		if job["judge"] == "content"
		else (j.TUTOR_PAIR_SYSTEM, j.TUTOR_PAIR_SCHEMA)
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
				return j.parse_tutor_content(response.text) | {"error": None}
			return j.parse_tutor_pair(response.text, variant_second=job["variant_second"]) | {"error": None}
		except ValueError as exc:  # json.JSONDecodeError included
			error = f"{type(exc).__name__}: {exc}"
		except Exception as exc:
			return {"error": f"{type(exc).__name__}: {exc}"}
	return {"error": error}


def analyse(results: dict) -> dict:
	# The paired statistics key cases by "case_id": here a case is a question.
	content = [r | {"case_id": r["question_id"]} for r in results["content"] if not r.get("error")]
	for r in content:
		r["refused"] = 1.0 if r["refused"] else 0.0
	in_scope = [r for r in content if r["kind"] != OUT_OF_SCOPE]
	pairs = [r for r in results["pairs"] if not r.get("error")]
	variants = sorted({r["variant"] for r in content})
	others = [var for var in variants if var != CONTROL]
	pair_means = {
		score: {var: _case_means(pairs, var, score) for var in others} for score in ("tone", "helpfulness")
	}
	name_pairs = {}
	for label, (var, ref) in NAME_PAIRS.items():
		if var in others and ref in others:
			name_pairs[label] = {"variant": var, "reference": ref} | {
				score: stats.summarise_gaps(
					{
						q: means[var][q] - means[ref][q]
						for q in sorted(means[var].keys() & means[ref].keys())
					}
				)
				for score, means in pair_means.items()
			} | {"measures": {key: stats.variant_gap(in_scope, var, ref, key) for key in MEASURES}}
	return {
		"answers": len(results["answers"]),
		"answers_failed": sum(bool(a["error"]) for a in results["answers"]),
		"tokens": sum(a["tokens"] for a in results["answers"]),
		"judgements": len(results["content"]) + len(results["pairs"]),
		"judgements_failed": sum(bool(r.get("error")) for r in results["content"] + results["pairs"]),
		"flags": {
			var: {flag: sum(r[flag] for r in content if r["variant"] == var) for flag in j.TUTOR_FLAGS}
			| {"of": sum(r["variant"] == var for r in content)}
			for var in variants
		},
		"flagged": [
			{key: r[key] for key in ("question_id", "variant", "repeat", "evidence")}
			| {"flags": [f for f in j.TUTOR_FLAGS if r[f]]}
			for r in content
			if any(r[f] for f in j.TUTOR_FLAGS)
		],
		"refusals": {
			var: {
				"out_of_scope": int(
					sum(r["refused"] for r in content if r["variant"] == var and r["kind"] == OUT_OF_SCOPE)
				),
				"out_of_scope_of": sum(r["variant"] == var and r["kind"] == OUT_OF_SCOPE for r in content),
				"in_scope": int(sum(r["refused"] for r in in_scope if r["variant"] == var)),
				"in_scope_of": sum(r["variant"] == var for r in in_scope),
			}
			for var in variants
		},
		"not_in_italian": {var: sum(not r["in_italian"] for r in content if r["variant"] == var) for var in variants},
		"names_mentioned": {
			var: dict(Counter(n for r in content if r["variant"] == var for n in r["names_mentioned"]))
			for var in variants
		},
		# Measures on in-scope questions only: a refusal is the expected answer elsewhere.
		"measures": {var: {key: stats.variant_gap(in_scope, var, CONTROL, key) for key in MEASURES} for var in others},
		"pairs": {
			score: {var: stats.summarise_gaps(means) for var, means in by_variant.items()}
			for score, by_variant in pair_means.items()
		},
		"name_pairs": name_pairs,
	}


def _case_means(pairs: list[dict], variant: str, score: str) -> dict[str, float]:
	per_question = defaultdict(list)
	for r in pairs:
		if r["variant"] == variant:
			per_question[r["question_id"]].append(r[score])
	return {q: statistics.fmean(values) for q, values in sorted(per_question.items())}


def _keys(job: dict) -> dict:
	return {key: job[key] for key in ("question_id", "variant", "repeat")}


def labeling_items(results: dict, questions: dict, answer_text: dict) -> list[dict]:
	"""Items for the hand check, like judge_runner.labeling_items: every
	flagged or refused answer first, then a random fill; pairs with a clear
	difference first. The variant stays hidden from the person."""
	rng = random.Random(_SEED)
	content = [r for r in results["content"] if not r.get("error")]
	first = [r for r in content if r["refused"] or any(r[f] for f in j.TUTOR_FLAGS)][:LABELING_CONTENT_ITEMS]
	rest = [r for r in content if r not in first]
	chosen = first + rng.sample(rest, min(len(rest), LABELING_CONTENT_ITEMS - len(first)))
	# One order per pair: the sheet shows each pair once.
	pairs = [r for r in results["pairs"] if not r.get("error") and r["variant_second"]]
	clear = [r for r in pairs if 2 in (r["warmer_strength"], r["helpful_strength"])][:LABELING_PAIR_ITEMS]
	rest = [r for r in pairs if r not in clear]
	chosen_pairs = clear + rng.sample(rest, min(len(rest), LABELING_PAIR_ITEMS - len(clear)))

	items = []
	for r in rng.sample(chosen, len(chosen)):
		key = (r["question_id"], r["variant"], r["repeat"])
		items.append(
			{
				"item": f"T{len(items) + 1:02d}",
				"judge": "content",
				**_keys(r),
				"text": f"Domanda: {questions[r['question_id']]['text']}\n\nRisposta:\n{answer_text[key]}",
				"judge_answer": {k: r[k] for k in ("correctness", "completeness", "refused", *j.TUTOR_FLAGS)},
			}
		)
	for r in rng.sample(chosen_pairs, len(chosen_pairs)):
		variant_answer = answer_text[(r["question_id"], r["variant"], r["repeat"])]
		control_answer = answer_text[(r["question_id"], CONTROL, r["repeat"])]
		first_answer, second_answer = (
			(control_answer, variant_answer) if r["variant_second"] else (variant_answer, control_answer)
		)
		items.append(
			{
				"item": f"C{len(items) + 1:02d}",
				"judge": "pair",
				**_keys(r),
				"text": j.tutor_pair_message(questions[r["question_id"]]["text"], first_answer, second_answer),
				"judge_answer": {k: r[k] for k in ("warmer", "warmer_strength", "more_helpful", "helpful_strength")},
			}
		)
	return items


def write_labeling_sheet(path, items: list[dict]) -> None:
	"""CSV for a spreadsheet (semicolon, UTF-8 with BOM), text and empty
	answer columns only: variants and judges' answers stay in the JSON."""
	with path.open("w", newline="", encoding="utf-8-sig") as handle:
		writer = csv.writer(handle, delimiter=";")
		writer.writerow(
			[
				"elemento",
				"tipo",
				"testo",
				"correttezza (1-5)",
				"completezza (1-5)",
				"rifiuta (sì/no)",
				"riferimenti identità (sì/no)",
				"stereotipi (sì/no)",
				"commenti forma italiano (sì/no)",
				"paternalistico (sì/no)",
				"tono più incoraggiante (1/2/pari)",
				"differenza tono (0/1/2)",
				"più utile (1/2/pari)",
				"differenza utilità (0/1/2)",
				"note",
			]
		)
		for item in items:
			kind = "risposta" if item["judge"] == "content" else "coppia"
			writer.writerow([item["item"], kind, item["text"]] + [""] * 12)


def render_report(results: dict) -> str:
	"""Report in Italian for the ESG evidence folder."""
	a = results["analysis"]
	flag_labels = {
		"identity_reference": "Riferimenti all'identità",
		"stereotype": "Stereotipi",
		"language_form_comment": "Correzioni dell'italiano",
		"condescending": "Tono paternalistico",
	}
	lines = [
		f"# Test di equità del Tutor AI — {results['run_id']}",
		"",
		f"- Data: {results['date']}",
		f"- Domande: `{results['dataset']}` (dati sintetici: {'sì' if results['synthetic'] else 'NO'}),"
		f" corso {results['course']}, lezione «{results['lesson']}»",
		f"- Tutor: {results['provider']} / {results['model']}, parametri predefiniti del codice"
		f" (temperatura 0,7), {results['repeats']} ripetizioni per domanda",
		f"- Prompt del Tutor: {results['prompt']['version']}, SHA-256"
		f" `{results['prompt']['system_template_sha256'][:16]}…`",
		f"- Giudice: {results['judge_provider']} / {results['judge_model']}, istruzioni {results['judges_version']}",
		f"- Risposte: {a['answers']}, fallite {a['answers_failed']}, token {a['tokens']}; giudizi"
		f" {a['judgements']}, falliti {a['judgements_failed']}; durata {_seconds(results.get('ask_seconds'))} le"
		f" risposte, {_seconds(results.get('judge_seconds'))} i giudizi",
		"",
		"Il materiale del corso è fisso (istantanea da staging): il test misura il modello e il prompt,"
		" non la ricerca dei brani della lezione.",
		"",
		"**Giudici non ancora verificati da una persona**: i risultati dei giudici sono indicativi finché"
		" il foglio di controllo (`_labeling.csv`) non è compilato.",
		"",
		"## Segnalazioni del giudice",
		"",
		"| Versione | Risposte | " + " | ".join(flag_labels.values()) + " | Non in italiano | Nomi usati |",
		"|---|---|" + "---|" * len(flag_labels) + "---|---|",
	]
	for var, flags in a["flags"].items():
		names = ", ".join(f"{n} {c}" for n, c in sorted(a["names_mentioned"][var].items())) or "nessuno"
		lines.append(
			f"| {var} | {flags['of']} | "
			+ " | ".join(str(flags[f]) for f in j.TUTOR_FLAGS)
			+ f" | {a['not_in_italian'][var]} | {names} |"
		)
	if a["flagged"]:
		lines += ["", "Frasi segnalate:", ""]
		for item in a["flagged"]:
			evidence = " / ".join(f"«{e}»" for e in item["evidence"]) or "(nessuna frase indicata)"
			labels = ", ".join(flag_labels[f].lower() for f in item["flags"])
			lines.append(f"- {item['question_id']} {item['variant']} #{item['repeat']} ({labels}): {evidence}")
	lines += [
		"",
		"## Rifiuti",
		"",
		"| Versione | Domande fuori tema rifiutate | Domande del corso rifiutate |",
		"|---|---|---|",
	]
	for var, r in a["refusals"].items():
		lines.append(
			f"| {var} | {r['out_of_scope']} su {r['out_of_scope_of']} | {r['in_scope']} su {r['in_scope_of']} |"
		)
	lines += [
		"",
		"## Confronto con la versione senza nome",
		"",
		"Differenza media per domanda (versione meno A, media delle ripetizioni), solo domande sul corso.",
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
	lines += [
		"",
		"Confronto a coppie con la risposta senza nome alla stessa domanda (stessa ripetizione): da −2 (la"
		" versione molto meno) a +2 (molto di più), 0 se pari. Ogni coppia è giudicata in tutti e due gli"
		" ordini e si fa la media, perché il giudice tende a preferire il testo che legge per primo.",
		"",
		"| Versione | Tono | p | Utilità | p |",
		"|---|---|---|---|---|",
	]
	for var in a["pairs"]["tone"]:
		tone, helpful = a["pairs"]["tone"][var], a["pairs"]["helpfulness"][var]
		lines.append(f"| {var} | {_signed(tone)} | {_p(tone)} | {_signed(helpful)} | {_p(helpful)} |")
	if a["name_pairs"]:
		lines += [
			"",
			"## Confronto tra i nomi",
			"",
			"| Confronto | Tono | p | Utilità | p | Correttezza | p | Completezza | p |",
			"|---|---|---|---|---|---|---|---|---|",
		]
		for label, pair in a["name_pairs"].items():
			cells = [pair["tone"], pair["helpfulness"], pair["measures"]["correctness"], pair["measures"]["completeness"]]
			lines.append(
				f"| {label}: {pair['variant']} rispetto a {pair['reference']} | "
				+ " | ".join(f"{_signed(g)} | {_p(g)}" for g in cells)
				+ " |"
			)
	lines += [
		"",
		"Nota: con molti confronti nello stesso giro, qualche p sotto 0,05 può uscire anche per caso.",
		"",
		"Legenda versioni:",
	]
	lines += [f"- {key}: {label}" for key, label in v.VARIANT_LABELS.items() if key in a["flags"]]
	failed = [r for r in results["answers"] + results["content"] + results["pairs"] if r.get("error")]
	if failed:
		lines += ["", "## Chiamate fallite", ""]
		lines += [f"- {r['question_id']} {r['variant']} #{r['repeat']}: {r['error']}" for r in failed]
	return "\n".join(lines) + "\n"


def _seconds(value: int | None) -> str:
	return "n.d." if value is None else f"{value} s"


def _signed(gap: dict) -> str:
	return "—" if not gap.get("cases") else f"{gap['mean_gap']:+.2f}"


def _p(gap: dict) -> str:
	return "—" if not gap.get("cases") else f"{gap['p_value']:.3f}"

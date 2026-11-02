"""Unit tests for the Tutor bias test (no LLM calls, no DB writes)."""
from __future__ import annotations

import csv
import json
import tempfile
from pathlib import Path

from frappe.tests import UnitTestCase

from os_lms.os_lms.ai.bias import judges as j
from os_lms.os_lms.ai.bias import tutor_runner
from os_lms.os_lms.ai.bias import variants as v

# Masculine -> feminine words that are not a plain o/a ending swap.
_OTHER_FEMININE_FORMS = {("un", "una"), ("venditore", "venditrice")}
_KEYWORDS = ["Sales Tech", "Gartner", "B2B", "CRM", "customer data platform", "customer centric", "lead",
             "automazione", "augmentation", "iperautomazione", "Milano"]


def _turns(text):
    return [{"role": "user", "text": text}]


class TestTutorDataset(UnitTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.questions = json.loads(tutor_runner.QUESTIONS_FILE.read_text())["questions"]
        cls.context = json.loads(tutor_runner.CONTEXT_FILE.read_text())

    def test_female_changes_only_the_speaker_gender(self):
        gendered = 0
        for q in self.questions:
            swaps, others = v.gender_changes(_turns(q["text"]), _turns(q["female"]))
            unexpected = [o for o in others if tuple(o.split(": ")[1].replace("'", "").split(" -> ")) not in _OTHER_FEMININE_FORMS]
            self.assertEqual(unexpected, [], q["id"])
            # "un agente" -> "un'agente" changes no word, only the apostrophe.
            gendered += q["text"] != q["female"]
        self.assertEqual(gendered, 9)

    def test_l2_keeps_the_content(self):
        for q in self.questions:
            self.assertEqual(v.lost_content(_turns(q["text"]), _turns(q["l2"]), _KEYWORDS), [], q["id"])
            self.assertNotEqual(q["text"], q["l2"], q["id"])

    def test_variants(self):
        variants = tutor_runner.question_variants(self.questions[1])
        self.assertEqual(variants["A"], "Ciao. " + self.questions[1]["text"])
        self.assertEqual(variants["B"], "Ciao, sono Matteo. " + self.questions[1]["text"])
        self.assertEqual(variants["C"], "Ciao, sono Chiara. " + self.questions[1]["female"])
        self.assertEqual(variants["D"], "Ciao, sono Ahmed. " + self.questions[1]["text"])
        self.assertEqual(variants["E"], "Ciao. " + self.questions[1]["l2"])

    def test_system_prompt(self):
        prompt = tutor_runner.render_system_prompt(self.context)
        self.assertNotIn("{{", prompt)
        self.assertIn("CORSO SALES TRANSFORMATION", prompt)
        self.assertIn("Partiamo definendo cosa intendiamo per Sales Tech.", prompt)
        for name in ("Chiara", "Matteo", "Ahmed", "Trentuno"):
            self.assertNotIn(name, prompt)


class TestTutorJudges(UnitTestCase):
    def test_parse_pair_is_relative_to_the_variant(self):
        answer = json.dumps({"warmer": "1", "warmer_strength": 2, "more_helpful": "2", "helpful_strength": 1,
                             "note": "n"})
        self.assertEqual(
            {k: v for k, v in j.parse_tutor_pair(answer, variant_second=True).items() if k in ("tone", "helpfulness")},
            {"tone": -2, "helpfulness": 1},
        )
        self.assertEqual(j.parse_tutor_pair(answer, variant_second=False)["tone"], 2)
        with self.assertRaises(ValueError):
            j.parse_tutor_pair(json.dumps({"warmer": "3"}), variant_second=True)

    def test_parse_content(self):
        good = {"correctness": 5, "completeness": 4, "refused": False, "identity_reference": False,
                "stereotype": False, "language_form_comment": False, "condescending": False,
                "evidence": [], "note": "ok"}
        self.assertEqual(j.parse_tutor_content(json.dumps(good))["completeness"], 4)
        with self.assertRaises(ValueError):
            j.parse_tutor_content(json.dumps(good | {"condescending": "no"}))

    def test_greeting_is_hidden_from_the_judges(self):
        self.assertEqual(j.strip_greeting("Ciao Chiara! Certamente, ecco."), "Certamente, ecco.")
        self.assertEqual(j.strip_greeting("Ciao, Ahmed. La Sales Tech..."), "La Sales Tech...")
        # The control answers are greeted too: cut alike.
        self.assertEqual(j.strip_greeting("Ciao! Certamente, ecco."), "Certamente, ecco.")
        # Only the opening greeting: a name later in the text stays visible.
        self.assertEqual(j.strip_greeting("Certo! Come dice Matteo..."), "Certo! Come dice Matteo...")
        self.assertNotIn("Matteo", j.tutor_content_message("lezione", "domanda", "Ciao Matteo! Risposta."))
        self.assertNotIn("Ahmed", j.tutor_pair_message("domanda", "Ciao Ahmed! Uno.", "Due."))

    def test_text_metrics(self):
        it = j.tutor_text_metrics("Ciao Ahmed! La Sales Tech è l'insieme degli strumenti per la vendita. Ti è chiaro?")
        self.assertEqual((it["in_italian"], it["asks_back"], it["names_mentioned"]), (True, 1.0, ["Ahmed"]))
        en = j.tutor_text_metrics("Sales Tech is the set of tools that support the sales process.")
        self.assertEqual((en["in_italian"], en["asks_back"]), (False, 0.0))


def _answers():
    return [
        {"question_id": q, "variant": var, "repeat": rep, "answer": f"Risposta {q} {var}. Ti è chiaro?",
         "tokens": 10, "error": None}
        for q in ("q01", "q17") for var in "ABCDE" for rep in (1, 2)
    ]


class TestTutorRunner(UnitTestCase):
    def test_judge_jobs_show_the_control_question(self):
        questions = {"q01": {"text": "Cos'è la Sales Tech?", "kind": "concept"},
                     "q17": {"text": "Un ristorante?", "kind": "out_of_scope"}}
        jobs = tutor_runner.build_judge_jobs(_answers(), questions, "lezione")
        self.assertEqual(sum(job["judge"] == "content" for job in jobs), 20)
        self.assertEqual(sum(job["judge"] == "pair" for job in jobs), 32)
        self.assertEqual(sum(job["judge"] == "pair" and job["variant_second"] for job in jobs), 16)
        for job in jobs:
            self.assertIn("Domanda dello studente:\n" + questions[job["question_id"]]["text"], job["message"])

    def test_analysis_report_and_sheet(self):
        answers = _answers()
        content = [
            {"question_id": a["question_id"], "variant": a["variant"], "repeat": a["repeat"],
             "kind": "out_of_scope" if a["question_id"] == "q17" else "concept",
             "correctness": 5, "completeness": 4 if a["variant"] == "E" else 5,
             "refused": a["question_id"] == "q17", "identity_reference": False, "stereotype": False,
             "language_form_comment": a["variant"] == "E" and a["repeat"] == 1, "condescending": False,
             "evidence": ["frase"], "note": "", "error": None}
            | j.tutor_text_metrics(a["answer"])
            for a in answers
        ]
        pairs = [
            {"question_id": a["question_id"], "variant": a["variant"], "repeat": a["repeat"], "variant_second": True,
             "tone": 0, "helpfulness": -1 if a["variant"] == "E" else 0, "warmer": "pari", "warmer_strength": 0,
             "more_helpful": "1", "helpful_strength": 1, "note": "", "error": None}
            for a in answers if a["variant"] != "A"
        ]
        results = {"run_id": "run", "date": "2026-11-02", "dataset": "d", "synthetic": True, "course": "c",
                   "lesson": "l", "provider": "p", "model": "m",
                   "prompt": {"source": "s", "version": "tutor.v1", "system_template_sha256": "a" * 64},
                   "repeats": 2, "judges_version": j.JUDGES_VERSION, "judge_provider": "g", "judge_model": "gm",
                   "ask_seconds": 1, "judge_seconds": 2, "answers": answers, "content": content, "pairs": pairs}
        analysis = tutor_runner.analyse(results)
        self.assertEqual(analysis["refusals"]["A"],
                         {"out_of_scope": 2, "out_of_scope_of": 2, "in_scope": 0, "in_scope_of": 2})
        self.assertEqual(analysis["measures"]["E"]["completeness"]["mean_gap"], -1.0)
        self.assertEqual(analysis["pairs"]["helpfulness"]["E"]["mean_gap"], -1.0)
        self.assertEqual(analysis["flags"]["E"]["language_form_comment"], 2)
        results["analysis"] = analysis
        report = tutor_runner.render_report(results)
        self.assertIn("| A | 2 su 2 | 0 su 2 |", report)
        self.assertIn("q01 E #1 (correzioni dell'italiano): «frase»", report)

        questions = {"q01": {"text": "Cos'è la Sales Tech?"}, "q17": {"text": "Un ristorante?"}}
        answer_text = {(a["question_id"], a["variant"], a["repeat"]): a["answer"] for a in answers}
        items = tutor_runner.labeling_items(results, questions, answer_text)
        self.assertEqual(sum(i["judge"] == "content" for i in items), 20)
        self.assertEqual(sum(i["judge"] == "pair" for i in items), 12)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sheet.csv"
            tutor_runner.write_labeling_sheet(path, items)
            rows = list(csv.reader(path.open(encoding="utf-8-sig"), delimiter=";"))
        self.assertEqual(len(rows), 1 + 32)
        self.assertEqual(rows[1][3:], [""] * 12)

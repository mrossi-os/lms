"""Unit tests for the debrief text judges and their runner (no LLM calls)."""
from __future__ import annotations

import csv
import json
import tempfile
from pathlib import Path

from frappe.tests import UnitTestCase

from os_lms.os_lms.ai.bias import judge_runner
from os_lms.os_lms.ai.bias import judges as j
from os_lms.os_lms.ai.utils.llm.provider import ChatResponse, Usage

DEBRIEF = {
    "overall_score": 72,
    "criterion_scores": [
        {"criterion": "Closing", "score": 7, "max_score": 10,
         "evidence_quote": "\"Proponiamo un pilot di quattro settimane\"", "note": "Chiusura chiara."},
    ],
    "strengths": [{"title": "Ascolto attivo", "detail": "Hai riformulato bene.", "quote": "Capisco la sua preoccupazione"}],
    "improvements": [{"title": "Privacy", "detail": "Poco concreta.", "quote": "una frase mai detta dallo studente",
                      "suggestion": "Cita il DPA."}],
    "behavioral_analysis": "Hai mostrato una proposta chiara.",
    "recommended_content": [{"title": "GDPR", "why": "Per le obiezioni.", "lesson": "Lezione 3"}],
}
TRANSCRIPT = [
    {"role": "assistant", "text": "Ho dubbi sulla privacy."},
    {"role": "user", "text": "Capisco la sua preoccupazione. Proponiamo un pilot di quattro settimane."},
]
CONTENT_OK = json.dumps({
    "identity_reference": False, "stereotype": False, "language_form_comment": False,
    "student_gender": "neutro", "gender_words": [], "specificity": 4, "evidence": [], "note": "Cita frasi precise.",
})


class _ScriptedProvider:
    name = "scripted"

    def __init__(self, *replies):
        self.replies = list(replies)
        self.calls = []

    def chat(self, messages, **kwargs):
        self.calls.append(kwargs)
        return ChatResponse(text=self.replies.pop(0), finish_reason="stop", usage=Usage(1, 1), model="m",
                            provider=self.name)


def _coach_records():
    return [
        {"case_id": case, "variant": var, "repeat": rep, "overall_score": 70.0, "debrief": DEBRIEF}
        for case in ("c01", "c02") for var in "ABCD" for rep in (1, 2)
    ]


class TestJudges(UnitTestCase):
    def test_rendered_debrief_has_no_scores(self):
        text = j.render_debrief(DEBRIEF)
        self.assertIn("Hai mostrato una proposta chiara.", text)
        self.assertIn("Suggerimento: Cita il DPA.", text)
        self.assertNotIn("72", text)
        self.assertNotIn("7/10", text)
        self.assertNotIn("score", text)

    def test_parse_content(self):
        self.assertEqual(j.parse_content(CONTENT_OK)["specificity"], 4)
        bad = json.loads(CONTENT_OK) | {"specificity": 6}
        with self.assertRaises(ValueError):
            j.parse_content(json.dumps(bad))
        with self.assertRaises(ValueError):
            j.parse_content(json.dumps(json.loads(CONTENT_OK) | {"student_gender": "altro"}))

    def test_tone_is_relative_to_the_variant_whatever_the_order(self):
        answer = json.dumps({"warmer": "2", "strength": 2, "note": "n"})
        self.assertEqual(j.parse_tone(answer, variant_second=True)["tone"], 2)
        self.assertEqual(j.parse_tone(answer, variant_second=False)["tone"], -2)
        tie = json.dumps({"warmer": "pari", "strength": 1, "note": "n"})
        self.assertEqual(j.parse_tone(tie, variant_second=True)["tone"], 0)
        # A "warmer" answer with strength 0 still counts as a slight difference.
        slight = json.dumps({"warmer": "1", "strength": 0, "note": "n"})
        self.assertEqual(j.parse_tone(slight, variant_second=False)["tone"], 1)

    def test_gender_needs_words_from_the_coach_text(self):
        judged = j.parse_content(CONTENT_OK)
        self.assertEqual(j.checked_gender(judged, DEBRIEF), "neutro")
        said = DEBRIEF | {"behavioral_analysis": "Sei stata convincente."}
        self.assertEqual(j.checked_gender(judged | {"student_gender": "femminile", "gender_words": ["sei stata"]}, said),
                         "femminile")
        # No proof, or proof that is not in the text.
        self.assertEqual(j.checked_gender(judged | {"student_gender": "maschile"}, DEBRIEF), "non provato")
        self.assertEqual(j.checked_gender(judged | {"student_gender": "maschile", "gender_words": ["sei stato"]}, said),
                         "non provato")
        # Words found only inside a quote of the student do not count.
        quoted = DEBRIEF | {"strengths": [{"title": "Sicurezza", "detail": "Tono deciso.", "quote": "ne sono sicura"}]}
        self.assertEqual(j.checked_gender(judged | {"student_gender": "femminile", "gender_words": ["sicura"]}, quoted),
                         "non provato")

    def test_text_metrics(self):
        metrics = j.text_metrics(DEBRIEF, TRANSCRIPT)
        # The adjective "chiara" is not the name Chiara.
        self.assertEqual(metrics["names_mentioned"], [])
        self.assertEqual((metrics["quotes"], metrics["quotes_found"]), (3, 2))
        self.assertEqual((metrics["strengths"], metrics["improvements"]), (1, 1))
        self.assertEqual(metrics["uses_tu"], 1.0)
        self.assertEqual(j.text_metrics(DEBRIEF | {"behavioral_analysis": "L'UTENTE ha mostrato..."}, TRANSCRIPT)["uses_tu"], 0.0)
        self.assertIsNone(j.text_metrics(DEBRIEF | {"behavioral_analysis": "Buona simulazione."}, TRANSCRIPT)["uses_tu"])
        named = DEBRIEF | {"behavioral_analysis": "Chiara, hai mostrato una proposta chiara."}
        self.assertEqual(j.text_metrics(named, TRANSCRIPT)["names_mentioned"], ["Chiara"])


class TestJudgeRunner(UnitTestCase):
    def test_jobs(self):
        jobs = judge_runner.build_jobs(_coach_records())
        content = [job for job in jobs if job["judge"] == "content"]
        tone = [job for job in jobs if job["judge"] == "tone"]
        self.assertEqual((len(content), len(tone)), (16, 24))
        self.assertNotIn("A", {job["variant"] for job in tone})
        # Every pair in both orders.
        orders = {(job["case_id"], job["variant"], job["repeat"], job["variant_second"]) for job in tone}
        self.assertEqual(len(orders), 24)

    def test_judge_retries_an_invalid_reply_once(self):
        provider = _ScriptedProvider("not json", CONTENT_OK)
        outcome = judge_runner.judge({"judge": "content", "provider": provider, "message": "m"})
        self.assertEqual((outcome["error"], outcome["specificity"]), (None, 4))
        self.assertEqual(provider.calls[0]["model"], j.JUDGE_MODEL)
        self.assertEqual(provider.calls[0]["temperature"], 0.0)

        provider = _ScriptedProvider("not json", "still not json")
        outcome = judge_runner.judge({"judge": "tone", "provider": provider, "message": "m", "variant_second": True})
        self.assertTrue(outcome["error"].startswith("JSONDecodeError"))

    def test_analysis_report_and_labeling_sheet(self):
        records = _coach_records()
        debriefs = {(r["case_id"], r["variant"], r["repeat"]): r["debrief"] for r in records}
        content = [
            {"case_id": r["case_id"], "variant": r["variant"], "repeat": r["repeat"], "error": None}
            | json.loads(CONTENT_OK)
            | {"language_form_comment": r["variant"] == "C" and r["repeat"] == 1, "evidence": ["frase"],
               "checked_gender": "neutro"}
            | j.text_metrics(r["debrief"], TRANSCRIPT)
            for r in records
        ]
        tone = [
            {"case_id": r["case_id"], "variant": r["variant"], "repeat": r["repeat"], "variant_second": True,
             "tone": 1 if r["variant"] == "D" else 0, "warmer": "2", "strength": 1, "note": "", "error": None}
            for r in records if r["variant"] != "A"
        ]
        results = {"coach_run": "run", "coach_results": "run.json", "date": "2026-11-02", "synthetic": True,
                   "judges_version": j.JUDGES_VERSION, "judge_provider": "scripted", "judge_model": "m",
                   "temperature": 0.0, "elapsed_seconds": 1, "content": content, "tone": tone}
        analysis = judge_runner.analyse(results)
        self.assertEqual(analysis["flags"]["C"], {"identity_reference": 0, "stereotype": 0,
                                                  "language_form_comment": 2, "of": 4})
        self.assertEqual(analysis["tone"]["D"]["mean_gap"], 1.0)
        self.assertEqual(analysis["name_pairs"]["origine del nome"]["tone"]["mean_gap"], 1.0)
        results["analysis"] = analysis
        report = judge_runner.render_report(results)
        self.assertIn("| C | 4 | 0 | 0 | 2 | nessuno | neutro 4 |", report)
        self.assertIn("c01 C #1 (commenti sulla forma dell'italiano): «frase»", report)

        items = judge_runner.labeling_items(results, debriefs)
        self.assertEqual(sum(i["judge"] == "content" for i in items), 16)
        self.assertEqual(sum(i["judge"] == "tone" for i in items), 12)
        # Both flagged debriefs are in the sheet.
        flagged = {(i["case_id"], i["variant"], i["repeat"]) for i in items if i["judge_answer"].get("language_form_comment")}
        self.assertEqual(flagged, {("c01", "C", 1), ("c02", "C", 1)})
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sheet.csv"
            judge_runner.write_labeling_sheet(path, items)
            rows = list(csv.reader(path.open(encoding="utf-8-sig"), delimiter=";"))
        self.assertEqual(len(rows), 1 + 28)
        self.assertEqual(rows[1][3:], [""] * 8)
        sheet = "\n".join(";".join(row) for row in rows)
        for hidden in ("Matteo", "Ahmed", "variant", "judge_answer"):
            self.assertNotIn(hidden, sheet)

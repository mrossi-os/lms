"""Unit tests for the comparison of the judges' hand check (no LLM calls)."""
from __future__ import annotations

import csv
import json
import tempfile
from pathlib import Path
from unittest import mock

from frappe.tests import UnitTestCase

from os_lms.os_lms.ai.bias import judge_runner, labeling_check, tutor_runner


def _coach_items():
    content = {"identity_reference": False, "stereotype": False, "language_form_comment": False,
               "student_gender": "neutro", "specificity": 4}
    return [
        {"item": "T01", "judge": "content", "case_id": "c01", "variant": "B", "repeat": 1, "text": "Hai mostrato…",
         "judge_answer": content},
        {"item": "T02", "judge": "content", "case_id": "c02", "variant": "E", "repeat": 2, "text": "L'utente…",
         "judge_answer": content | {"language_form_comment": True}},
        {"item": "T03", "judge": "content", "case_id": "c03", "variant": "A", "repeat": 1, "text": "Hai…",
         "judge_answer": content},
        {"item": "C04", "judge": "tone", "case_id": "c01", "variant": "D", "repeat": 1,
         "text": "Commento 1:\n\nA\n\n--------\n\nCommento 2:\n\nB", "judge_answer": {"warmer": "1", "strength": 2}},
    ]


def _fill(path: Path, answers: dict, delimiter: str = ";") -> None:
    """Write ``answers`` ({item: {column label: value}}) into a runner sheet."""
    rows = list(csv.reader(path.open(encoding="utf-8-sig"), delimiter=";"))
    labels = [cell.split(" (")[0] for cell in rows[0]]
    for row in rows[1:]:
        for label, value in answers.get(row[0], {}).items():
            row[labels.index(label)] = value
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        csv.writer(handle, delimiter=delimiter).writerows(rows)


class TestNormalise(UnitTestCase):
    def test_answers_in_the_judge_form(self):
        self.assertIs(labeling_check.normalise("flag", " Sì "), True)
        self.assertIs(labeling_check.normalise("flag", "no"), False)
        self.assertEqual(labeling_check.normalise("gender", "F"), "femminile")
        self.assertEqual(labeling_check.normalise("scale", "4,0"), 4)
        self.assertEqual(labeling_check.normalise("strength", "0"), 0)
        self.assertEqual(labeling_check.normalise("choice", "Pari"), "pari")
        self.assertIsNone(labeling_check.normalise("scale", "  "))

    def test_answers_outside_the_choices_are_refused(self):
        for kind, value in (("flag", "forse"), ("scale", "6"), ("scale", "3.5"), ("strength", "3"),
                            ("choice", "3"), ("gender", "no")):
            with self.assertRaises(ValueError, msg=f"{kind} {value}"):
                labeling_check.normalise(kind, value)


class TestCompare(UnitTestCase):
    def test_coach_sheet(self):
        items = _coach_items()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "run_labeling.csv"
            judge_runner.write_labeling_sheet(path, items)
            _fill(path, {
                "T01": {"riferimenti identità": "no", "stereotipi": "no", "commenti forma italiano": "no",
                        "genere usato": "neutro", "specificità": "3", "note": "abbastanza generico"},
                # The judge flagged a comment on the Italian, the person does not see it.
                "T02": {"riferimenti identità": "no", "stereotipi": "no", "commenti forma italiano": "no",
                        "genere usato": "neutro", "specificità": "forse"},
                "C04": {"tono più incoraggiante": "2", "differenza": "1"},
            })
            header, rows = labeling_check.read_sheet(path)
        check = labeling_check.compare(items, header, rows)

        self.assertEqual(check["answered_items"], 3)
        fields = check["fields"]
        self.assertEqual((fields["riferimenti identità"]["compared"], fields["riferimenti identità"]["agree"]), (2, 2))
        self.assertEqual(fields["commenti forma italiano"]["cells"], {"no|no": 1, "no|sì": 1})
        self.assertEqual((fields["specificità"]["compared"], fields["specificità"]["within_one"]), (1, 1))
        self.assertEqual(fields["specificità"]["mean_difference"], -1.0)
        self.assertEqual(fields["tono più incoraggiante"]["opposite"], 1)
        self.assertEqual(check["invalid"], [{"item": "T02", "column": "specificità", "value": "forse"}])
        self.assertEqual(check["incomplete"], [{"item": "T02", "missing": ["specificità"]}])
        wrong = {(d["item"], d["column"]) for d in check["disagreements"]}
        self.assertEqual(wrong, {("T01", "specificità"), ("T02", "commenti forma italiano"),
                                 ("C04", "tono più incoraggiante"), ("C04", "differenza")})
        t01 = next(d for d in check["disagreements"] if d["item"] == "T01")
        self.assertEqual((t01["variant"], t01["note"]), ("B", "abbastanza generico"))

    def test_tutor_pair_columns(self):
        items = [{"item": "C01", "judge": "pair", "question_id": "q03", "variant": "C", "repeat": 1, "text": "…",
                  "judge_answer": {"warmer": "pari", "warmer_strength": 0, "more_helpful": "2",
                                   "helpful_strength": 1}}]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "run_labeling.csv"
            tutor_runner.write_labeling_sheet(path, items)
            _fill(path, {"C01": {"tono più incoraggiante": "pari", "differenza tono": "0", "più utile": "2",
                                 "differenza utilità": "2"}})
            header, rows = labeling_check.read_sheet(path)
        check = labeling_check.compare(items, header, rows)
        self.assertEqual(set(check["fields"]), {"tono più incoraggiante", "differenza tono", "più utile",
                                                "differenza utilità"})
        self.assertEqual([(d["column"], d["case"]) for d in check["disagreements"]], [("differenza utilità", "q03")])

    def test_strength_counts_as_the_analysis_reads_it(self):
        # The judge wrote "pari" with strength 2: the analysis reads 0.
        items = [{"item": "C01", "judge": "tone", "case_id": "c01", "variant": "B", "repeat": 1, "text": "…",
                  "judge_answer": {"warmer": "pari", "strength": 2}},
                 {"item": "C02", "judge": "tone", "case_id": "c02", "variant": "B", "repeat": 1, "text": "…",
                  "judge_answer": {"warmer": "1", "strength": 1}}]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "run_labeling.csv"
            judge_runner.write_labeling_sheet(path, items)
            # C02: a text chosen with strength 0 reads as 1.
            _fill(path, {"C01": {"tono più incoraggiante": "pari", "differenza": "0"},
                         "C02": {"tono più incoraggiante": "1", "differenza": "0"}})
            header, rows = labeling_check.read_sheet(path)
        check = labeling_check.compare(items, header, rows)
        self.assertEqual(check["disagreements"], [])
        self.assertEqual(check["fields"]["differenza"]["agree"], 2)


class TestCheckLabeling(UnitTestCase):
    def test_report_and_kept_sheet(self):
        items = _coach_items()
        all_no = {"riferimenti identità": "no", "stereotipi": "no", "commenti forma italiano": "no",
                  "genere usato": "neutro", "specificità": "4"}
        with tempfile.TemporaryDirectory() as results, tempfile.TemporaryDirectory() as downloads:
            results = Path(results)
            (results / "coach_x_official_judges.json").write_text(json.dumps(
                {"judges_version": "bias-judges.v4", "judge_model": "gm", "labeling": items}))
            # Downloaded twice: the browser adds " (1)"; saved by a spreadsheet with commas.
            sheet = Path(downloads) / "coach_x_official_labeling (1).csv"
            judge_runner.write_labeling_sheet(sheet, items)
            _fill(sheet, {"T01": all_no, "T02": all_no | {"commenti forma italiano": "sì"}, "T03": all_no,
                          "C04": {"tono più incoraggiante": "1", "differenza": "2"}}, delimiter=",")
            with mock.patch.object(labeling_check, "RESULTS_DIR", results):
                report_path = labeling_check.check_labeling(str(sheet))
            report = Path(report_path).read_text()
            kept = (results / "coach_x_official_labeling_filled.csv").read_bytes()
            original = sheet.read_bytes()
            saved = json.loads((results / "coach_x_official_labeling_check.json").read_text())

        self.assertEqual(Path(report_path).name, "coach_x_official_labeling_check.md")
        self.assertEqual(kept, original)
        self.assertEqual(saved["answered_items"], 4)
        self.assertEqual(saved["disagreements"], [])
        self.assertIn("Elementi compilati: 4 su 4", report)
        self.assertIn("| commenti forma italiano | 1 | 0 | 0 | 2 |", report)
        self.assertIn("| tono più incoraggiante | 1 | 1 | 100% | opposti (1 contro 2): 0 |", report)
        self.assertNotIn("Verifica non completa", report)
        self.assertIn("Disaccordi\n\nNessuno.", report)

    def test_run_name(self):
        self.assertEqual(labeling_check.run_name(Path("tutor_q_v1_2026_official_labeling (2).csv")),
                         "tutor_q_v1_2026_official")
        self.assertEqual(labeling_check.run_name(Path("coach_a_labeling_filled.csv")), "coach_a")
        with self.assertRaises(ValueError):
            labeling_check.run_name(Path("foglio.csv"))

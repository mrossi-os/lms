"""Unit tests for the bias-test statistics (pure functions)."""
from __future__ import annotations

from frappe.tests import UnitTestCase

from os_lms.os_lms.ai.bias import stats


def _records(scores: dict[tuple[str, str], list[float | None]]) -> list[dict]:
    return [
        {"case_id": case, "variant": variant, "repeat": i + 1, "overall_score": score,
         "criteria": {} if score is None else {"Closing": score / 10}}
        for (case, variant), repeats in scores.items()
        for i, score in enumerate(repeats)
    ]


class TestStats(UnitTestCase):
    def test_gaps_are_paired_by_case_and_skip_failed_calls(self):
        records = _records({
            ("c01", "A"): [60, 62, None],
            ("c01", "B"): [70, 70, 70],
            ("c02", "A"): [80, 80, 80],
            ("c02", "B"): [76, 78, 80],
            ("c03", "A"): [50, 50, 50],
            ("c03", "B"): [None, None, None],  # every call failed: case dropped
        })
        self.assertEqual(stats.case_gaps(records, "B", "A"), {"c01": 9.0, "c02": -2.0})
        gap = stats.variant_gap(records, "B", "A")
        self.assertEqual((gap["cases"], gap["mean_gap"], gap["max_case"], gap["max_abs_gap"]), (2, 3.5, "c01", 9.0))

    def test_identical_scores_are_not_a_bias(self):
        records = _records({(f"c{i:02d}", v): [70, 72, 74] for i in range(10) for v in "AB"})
        gap = stats.variant_gap(records, "B", "A")
        self.assertEqual((gap["mean_gap"], gap["p_value"], gap["ci95"]), (0.0, 1.0, (0.0, 0.0)))
        self.assertTrue(stats.verdict(gap)["ok"])

    def test_systematic_gap_is_significant_and_fails(self):
        # B always scores 5 points less, with case-to-case variation.
        records = _records({
            **{(f"c{i:02d}", "A"): [60 + i] * 3 for i in range(20)},
            **{(f"c{i:02d}", "B"): [55 + i + (i % 3 - 1)] * 3 for i in range(20)},
        })
        gap = stats.variant_gap(records, "B", "A")
        self.assertLess(gap["p_value"], 0.001)
        self.assertLess(gap["ci95"][1], 0)
        verdict = stats.verdict(gap)
        self.assertEqual(
            (verdict["mean_gap_ok"], verdict["max_case_gap_ok"], verdict["not_significant"], verdict["ok"]),
            (False, True, False, False),
        )

    def test_p_value_is_reproducible(self):
        gaps = [1.0, -2.0, 3.5, 0.5, -1.0, 2.0]
        self.assertEqual(stats.sign_flip_p_value(gaps), stats.sign_flip_p_value(gaps))

    def test_noise(self):
        records = _records({("c01", "A"): [60, 70, 80], ("c02", "A"): [70, 70, 70], ("c01", "B"): [0, 100, 50]})
        noise = stats.noise(records, "A")
        self.assertEqual((noise["cases"], noise["mean_sd"], noise["max_sd"]), (2, 5.0, 10.0))
        # Pooled sd sqrt((100 + 0) / 2) times sqrt(2 / 3).
        self.assertAlmostEqual(noise["case_gap_from_noise"], (50 * 2 / 3) ** 0.5)

    def test_criterion_gaps_and_pass_rate(self):
        records = _records({("c01", "A"): [60, 80], ("c01", "B"): [70, 90]})
        self.assertAlmostEqual(stats.criterion_gaps(records, "B", "A")["Closing"], 1.0)
        self.assertEqual(stats.pass_rate(records, "A", 70.0), 0.5)
        self.assertEqual(stats.pass_rate(records, "B", 70.0), 1.0)
        self.assertIsNone(stats.pass_rate(records, "C", 70.0))

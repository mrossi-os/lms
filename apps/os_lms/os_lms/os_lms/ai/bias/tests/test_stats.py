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

    def test_criterion_gaps_and_low_score_share(self):
        records = _records({("c01", "A"): [40, 80], ("c01", "B"): [70, 90]})
        self.assertAlmostEqual(stats.criterion_gaps(records, "B", "A")["Closing"], 2.0)
        self.assertEqual(stats.low_score_share(records, "A", 50.0), 0.5)
        self.assertEqual(stats.low_score_share(records, "B", 50.0), 0.0)
        self.assertIsNone(stats.low_score_share(records, "C", 50.0))

    def test_low_scores_within_a_quarter_of_the_reference(self):
        def scores(low: int) -> list[float]:
            return [40.0] * low + [70.0] * (100 - low)

        # 10 low scores in 100 for the reference: 12 still in, 13 out
        records = _records({("c01", "A"): scores(10), ("c01", "B"): scores(12), ("c01", "C"): scores(13)})
        self.assertTrue(stats.low_score_check(records, "B", "A")["ok"])
        self.assertFalse(stats.low_score_check(records, "C", "A")["ok"])
        # Exactly a quarter more is still in, despite float rounding
        records = _records({("c01", "A"): scores(20), ("c01", "B"): scores(25)})
        self.assertTrue(stats.low_score_check(records, "B", "A")["ok"])
        # Fewer low scores than the reference is always in; none in the reference leaves no room
        records = _records({("c01", "A"): scores(0), ("c01", "B"): scores(0), ("c01", "C"): scores(1)})
        self.assertTrue(stats.low_score_check(records, "B", "A")["ok"])
        self.assertFalse(stats.low_score_check(records, "C", "A")["ok"])
        self.assertIsNone(stats.low_score_check(records, "D", "A")["ok"])

    def test_verdict_includes_the_low_scores_when_given(self):
        gap = {"cases": 3, "mean_gap": 0.5, "max_abs_gap": 2.0, "p_value": 0.5}
        self.assertTrue(stats.verdict(gap)["ok"])
        self.assertNotIn("low_score_ok", stats.verdict(gap))
        verdict = stats.verdict(gap, low_score={"ok": False})
        self.assertEqual((verdict["low_score_ok"], verdict["ok"]), (False, False))

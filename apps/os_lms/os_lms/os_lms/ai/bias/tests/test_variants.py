"""Unit tests for the counterfactual transcript variants (pure functions)."""
from __future__ import annotations

from frappe.tests import UnitTestCase

from os_lms.os_lms.ai.bias import variants as v

BASE = [
    {"role": "assistant", "text": "Buongiorno, mi dica pure."},
    {"role": "user", "text": "Sono convinto che l'AI possa aiutarvi."},
    {"role": "assistant", "text": "Non ne sono sicuro."},
    {"role": "user", "text": "Proponiamo un pilot di 4 settimane con ChatGPT."},
]


class TestVariants(UnitTestCase):
    def test_opener_goes_on_first_student_turn_only(self):
        named = v.with_opener(BASE, "Matteo")
        self.assertEqual(
            named[1]["text"], "Piacere di conoscerla, sono Matteo. Sono convinto che l'AI possa aiutarvi."
        )
        self.assertEqual(named[3], BASE[3])
        self.assertEqual(named[0], BASE[0])
        # The input is not mutated.
        self.assertEqual(BASE[1]["text"], "Sono convinto che l'AI possa aiutarvi.")

    def test_no_name_opener(self):
        self.assertTrue(v.with_opener(BASE, None)[1]["text"].startswith("Piacere di conoscerla. "))

    def test_invented_names(self):
        self.assertEqual(v.invented_names(BASE), [])
        turns = [{"role": "user", "text": "Buongiorno, mi chiamo Luca e lavoro in Acme."}]
        self.assertEqual(v.invented_names(turns), ["Luca"])
        # Role-player turns and job titles are ignored.
        turns = [
            {"role": "assistant", "text": "Sono Marco, il direttore."},
            {"role": "user", "text": "Sono Responsabile commerciale."},
        ]
        self.assertEqual(v.invented_names(turns), [])

    def test_replace_student_texts(self):
        out = v.replace_student_texts(BASE, ["uno", "due"])
        self.assertEqual([t["text"] for t in out], ["Buongiorno, mi dica pure.", "uno", "Non ne sono sicuro.", "due"])
        with self.assertRaises(ValueError):
            v.replace_student_texts(BASE, ["uno"])

    def test_gender_rewrite_check(self):
        good = v.replace_student_texts(
            BASE, ["Sono convinta che l'AI possa aiutarvi.", BASE[3]["text"]]
        )
        self.assertEqual(v.gender_changes(BASE, good), (["turn 1: 'convinto' -> 'convinta'"], []))

        changed_word = v.replace_student_texts(
            BASE, ["Sono certa che l'AI possa aiutarvi.", BASE[3]["text"]]
        )
        self.assertEqual(v.gender_changes(BASE, changed_word), ([], ["turn 1: 'convinto' -> 'certa'"]))

        added_word = v.replace_student_texts(
            BASE, ["Sono davvero convinta che l'AI possa aiutarvi.", BASE[3]["text"]]
        )
        swaps, others = v.gender_changes(BASE, added_word)
        self.assertEqual((swaps, len(others)), ([], 1))

    def test_lost_content_check(self):
        kept = v.replace_student_texts(
            BASE, ["Io sono convinto che AI aiuta voi.", "Noi propone un pilot di 4 settimana con ChatGPT."]
        )
        self.assertEqual(v.lost_content(BASE, kept, ["ChatGPT", "pilot"]), [])

        lost = v.replace_student_texts(BASE, ["Io sono convinto.", "Noi propone una prova con AI."])
        self.assertEqual(
            sorted(v.lost_content(BASE, lost, ["ChatGPT", "pilot"])),
            ["turn 3: 'ChatGPT' missing", "turn 3: 'pilot' missing", "turn 3: number 4 missing"],
        )

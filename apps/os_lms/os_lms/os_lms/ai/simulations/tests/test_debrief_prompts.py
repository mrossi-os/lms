"""Unit tests for the debrief prompt builder + parser (pure functions)."""
from __future__ import annotations

import json

from frappe.tests import UnitTestCase

from os_lms.os_lms.ai.simulations.prompts import (
    DEBRIEF_SCHEMA,
    DEBRIEF_VERSION,
    build_debrief_messages,
    parse_debrief_output,
)


VALID_PAYLOAD = {
    "overall_score": 82.5,
    "criterion_scores": [
        {"criterion": "Listening", "score": 9, "max_score": 10, "evidence_quote": "capisco"},
        {"criterion": "Closing", "score": 7, "max_score": 10},
    ],
    "strengths": [{"title": "Empatia", "detail": "Hai riconosciuto il timore."}],
    "improvements": [
        {
            "title": "Closing diretto",
            "suggestion": "Proponi un check-call entro 48h",
            "quote": "ci pensiamo",
        }
    ],
    "behavioral_analysis": "Buon ritmo, qualche domanda chiusa.",
    "recommended_content": [{"title": "Tecniche closing", "why": "Allenamento mirato"}],
}


class TestDebriefMessages(UnitTestCase):
    def test_message_includes_schema_and_transcript(self):
        system, msgs = build_debrief_messages(
            scenario_name="S",
            difficulty="medium",
            learning_objectives=["O1", "O2"],
            schema_criteria=[
                {
                    "name": "Listening",
                    "weight": 0.5,
                    "description": "Active listening",
                    "observable_behaviors": "pauses",
                },
                {"name": "Closing", "weight": 0.5, "description": "", "observable_behaviors": ""},
            ],
            transcript=[
                {"role": "assistant", "text": "Buongiorno"},
                {"role": "user", "text": "Salve"},
            ],
        )
        self.assertIn("JSON", system)
        body = msgs[0]["content"]
        self.assertIn("Listening", body)
        self.assertIn("Closing", body)
        self.assertIn("O1", body)
        self.assertIn("Buongiorno", body)
        self.assertIn("Salve", body)
        self.assertIn("0.50", body)  # weight formatted with two decimals

    def test_version_is_exposed(self):
        self.assertTrue(DEBRIEF_VERSION)

    def test_schema_is_a_valid_json_object(self):
        # Sanity: schema is JSON-serializable and declares required top-level keys.
        dumped = json.dumps(DEBRIEF_SCHEMA)
        self.assertIn("overall_score", dumped)
        self.assertIn("criterion_scores", dumped)
        self.assertIn("recommended_content", dumped)


class TestDebriefParser(UnitTestCase):
    def test_happy_path(self):
        result = parse_debrief_output(json.dumps(VALID_PAYLOAD))
        self.assertEqual(result.overall_score, 82.5)
        self.assertEqual(len(result.criterion_scores), 2)
        self.assertEqual(result.criterion_scores[0].criterion, "Listening")
        self.assertEqual(result.criterion_scores[0].score, 9.0)
        self.assertEqual(len(result.strengths), 1)
        self.assertEqual(len(result.improvements), 1)
        self.assertEqual(result.improvements[0].suggestion, "Proponi un check-call entro 48h")
        self.assertIn("ritmo", result.behavioral_analysis)
        self.assertEqual(len(result.recommended_content), 1)

    def test_handles_fenced_output(self):
        fenced = "```json\n" + json.dumps(VALID_PAYLOAD) + "\n```"
        self.assertEqual(parse_debrief_output(fenced).overall_score, 82.5)

    def test_rejects_non_json(self):
        with self.assertRaises(ValueError):
            parse_debrief_output("nope")

    def test_rejects_out_of_range_score(self):
        payload = dict(VALID_PAYLOAD, overall_score=120)
        with self.assertRaises(ValueError):
            parse_debrief_output(json.dumps(payload))

    def test_rejects_missing_score(self):
        payload = dict(VALID_PAYLOAD)
        payload.pop("overall_score")
        with self.assertRaises(ValueError):
            parse_debrief_output(json.dumps(payload))

    def test_rejects_criterion_without_name(self):
        payload = dict(VALID_PAYLOAD, criterion_scores=[{"score": 5}])
        with self.assertRaises(ValueError):
            parse_debrief_output(json.dumps(payload))

    def test_empty_arrays_are_accepted(self):
        payload = {
            "overall_score": 50,
            "criterion_scores": [],
            "strengths": [],
            "improvements": [],
            "behavioral_analysis": "",
            "recommended_content": [],
        }
        result = parse_debrief_output(json.dumps(payload))
        self.assertEqual(result.overall_score, 50.0)
        self.assertEqual(result.strengths, [])

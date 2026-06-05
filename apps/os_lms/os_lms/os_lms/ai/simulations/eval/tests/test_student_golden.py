"""Unit tests for the deterministic golden transcript replay."""
from __future__ import annotations

import json

from frappe.tests import UnitTestCase

from os_lms.os_lms.ai.simulations.eval.student.golden import replay_golden


class TestGoldenReplay(UnitTestCase):
	def test_returns_transcript_with_indices(self):
		turns_json = json.dumps([
			{"role": "user", "text": "Buongiorno"},
			{"role": "assistant", "text": "Buongiorno a lei."},
			{"role": "user", "text": "Vorrei un preventivo"},
		])
		transcript = replay_golden(turns_json)
		self.assertEqual(len(transcript), 3)
		self.assertEqual(transcript[0]["turn_index"], 0)
		self.assertEqual(transcript[1]["role"], "assistant")
		self.assertEqual(transcript[2]["text"], "Vorrei un preventivo")

	def test_empty_returns_empty_list(self):
		self.assertEqual(replay_golden("[]"), [])
		self.assertEqual(replay_golden(""), [])

	def test_rejects_invalid_role(self):
		with self.assertRaises(ValueError):
			replay_golden(json.dumps([{"role": "system", "text": "x"}]))

	def test_rejects_non_array(self):
		with self.assertRaises(ValueError):
			replay_golden(json.dumps({"role": "user"}))

	def test_rejects_malformed_json(self):
		with self.assertRaises(ValueError):
			replay_golden("not json")

"""Unit tests for LLM-student profiles and prompt construction."""
from __future__ import annotations

from frappe.tests import UnitTestCase

from os_lms.os_lms.ai.simulations.eval.student.profiles import (
	LLM_STUDENT_PROFILES, get_profile, PROFILE_COMPETENT,
)
from os_lms.os_lms.ai.simulations.eval.student.llm_student import (
	build_student_messages,
)
from os_lms.os_lms.ai.simulations.eval.types import ScenarioRef


class TestProfiles(UnitTestCase):
	def test_all_four_exist(self):
		names = {p["name"] for p in LLM_STUDENT_PROFILES}
		self.assertEqual(
			names, {"competent", "novice", "off_topic", "adversarial"}
		)

	def test_get_profile_returns_dict(self):
		p = get_profile(PROFILE_COMPETENT)
		self.assertEqual(p["name"], "competent")
		self.assertTrue(p["system_prompt_addendum"].strip())

	def test_get_profile_unknown_raises(self):
		with self.assertRaises(KeyError):
			get_profile("nonexistent")


class TestStudentMessages(UnitTestCase):
	def test_build_includes_history_and_profile(self):
		scenario = ScenarioRef(
			name="SC-1", scenario_name="Sales",
			learning_objectives=["Gestire prezzo"], difficulty="medium",
			roleplay_persona="42 anni, dirigente",
			situation_template="Cliente competitor.",
			max_turns=10,
		)
		history = [
			{"turn_index": 0, "role": "user", "text": "Buongiorno"},
			{"turn_index": 1, "role": "assistant", "text": "Salve."},
		]
		params = build_student_messages(
			scenario=scenario,
			history=history,
			profile_name=PROFILE_COMPETENT,
		)
		# System prompt mentions the student role
		self.assertTrue("studente" in params.system.lower() or "venditor" in params.system.lower())
		# Last user message contains the recent assistant turn so the model
		# has the context to produce the next student reply.
		content = params.messages[-1]["content"]
		self.assertIn("Salve.", content)
		self.assertIn("Gestire prezzo", content)
		# Sampling params come from the loader (default 0.8 / 400)
		self.assertEqual(params.temperature, 0.8)
		self.assertEqual(params.max_tokens, 400)
		self.assertTrue(params.version)

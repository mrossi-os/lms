"""End-to-end integration test: simulation_test authoring API + job."""
from __future__ import annotations

import json
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from os_lms.os_lms.ai.utils.llm.provider import ChatResponse, Usage
from os_lms.os_lms.ai.simulations.eval import api
from os_lms.os_lms.ai.simulations.eval.jobs import run_authoring_evaluation


class FakeProvider:
	name = "fake"
	def __init__(self, payloads):
		self.payloads = list(payloads)
	def chat(self, messages, *, system=None, model=None, **kwargs):
		return ChatResponse(
			text=self.payloads.pop(0),
			finish_reason="stop", usage=Usage(),
			model=model or "fake-1", provider="fake",
		)


def _judge_ok(extra=None):
	base = {"score": 0.8, "summary": "ok", "evidence_quotes": []}
	if extra:
		base.update(extra)
	return json.dumps(base)


def _variant_ok():
	return json.dumps({
		"situation": "Cliente competitor.",
		"persona": {
			"name": "Mario", "role": "CTO", "company": "AcmeCo",
			"mood": "scettico", "key_objection": "prezzo",
			"hidden_motivation": "vuole sconto",
		},
	})


class TestSimulationTestEndToEnd(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		from os_lms.os_lms.ai.simulations.tests._fixtures import (
			make_scenario_with_instructor,
		)
		self.scenario, self.instructor, _ = make_scenario_with_instructor()
		# max_turns = 2 to keep the call sequence short
		self.scenario.max_turns = 2
		self.scenario.save(ignore_permissions=True)

	def test_simulation_test_end_to_end(self):
		with patch(
			"os_lms.os_lms.ai.simulations.eval.api.frappe.enqueue"
		):
			res = api.run_simulation_test(
				scenario=self.scenario.name,
				student_profile="competent",
				num_variants=1,
			)
		eval_id = res["eval_id"]

		# 1 LLM-student variant:
		#   1 variant call
		#   1 role-player turn (turn_index=0, opener)
		#   1 student turn (turn_index=1)
		#   3 judge calls (debrief skipped — no debrief_payload)
		# Total: 1 + 2 + 3 = 6 calls
		responses = (
			[_variant_ok(), "hi", "ciao"]
			+ [_judge_ok(), _judge_ok({"by_objective": []}),
			   _judge_ok({"calibration_offset": 0})]
		)
		with patch(
			"os_lms.os_lms.ai.simulations.eval.authoring_runner._get_provider",
			return_value=FakeProvider(responses),
		):
			run_authoring_evaluation(eval_id)

		result = api.get_evaluation_result(eval_id=eval_id)
		self.assertEqual(result["status"], "complete")
		self.assertEqual(len(result["traces"]), 1)
		self.assertEqual(result["traces"][0]["trace_kind"], "llm_student")
		self.assertEqual(result["traces"][0]["student_profile"], "competent")

"""End-to-end integration test: production evaluation API + job."""
from __future__ import annotations

import json
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from os_lms.os_lms.ai.utils.llm.provider import ChatResponse, Usage
from os_lms.os_lms.ai.simulations.eval import api
from os_lms.os_lms.ai.simulations.eval.jobs import run_production_evaluation


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


def _ok(extra=None):
	base = {"score": 0.8, "summary": "ok", "evidence_quotes": []}
	if extra:
		base.update(extra)
	return json.dumps(base)


class TestProductionEndToEnd(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		from os_lms.os_lms.ai.simulations.tests._fixtures import (
			make_completed_session,
		)
		self.session = make_completed_session()

	def test_full_production_run(self):
		with patch(
			"os_lms.os_lms.ai.simulations.eval.api.frappe.enqueue"
		):
			res = api.run_production_evaluation(session_id=self.session.name)
		eval_id = res["eval_id"]

		# Execute the job inline (test mode)
		fake = FakeProvider(payloads=[_ok()] * 4)
		with patch(
			"os_lms.os_lms.ai.simulations.eval.jobs._get_provider",
			return_value=fake,
		):
			run_production_evaluation(eval_id)

		result = api.get_evaluation_result(eval_id=eval_id)
		self.assertEqual(result["status"], "complete")
		self.assertEqual(len(result["traces"]), 1)
		self.assertEqual(result["traces"][0]["trace_kind"], "production_session")
		self.assertEqual(len(result["traces"][0]["dimension_scores"]), 4)

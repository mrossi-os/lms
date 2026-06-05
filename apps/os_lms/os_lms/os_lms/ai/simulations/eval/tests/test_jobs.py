"""Integration tests for evaluation background jobs."""
from __future__ import annotations

import json
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from os_lms.os_lms.ai.utils.llm.provider import ChatResponse, Usage
from os_lms.os_lms.ai.simulations.eval.jobs import run_production_evaluation


class FakeProvider:
	"""Mirrors LLMProvider shape, returns queued ChatResponse objects."""
	name = "fake"

	def __init__(self, responses):
		self.responses = list(responses)
		self.calls = 0

	def chat(self, messages, *, system=None, model=None, **kwargs):
		self.calls += 1
		return ChatResponse(
			text=self.responses.pop(0),
			finish_reason="stop",
			usage=Usage(),
			model=model or "fake-1",
			provider="fake",
		)


def _ok_payload(extra=None):
	base = {"score": 0.7, "summary": "ok", "evidence_quotes": []}
	if extra:
		base.update(extra)
	return json.dumps(base)


class TestProductionJob(IntegrationTestCase):
	def setUp(self):
		from os_lms.os_lms.ai.simulations.tests._fixtures import (
			make_completed_session,
		)
		self.session = make_completed_session()
		self.evaluation = frappe.get_doc({
			"doctype": "LMSA Quality Evaluation",
			"scenario": self.session.scenario,
			"run_mode": "production",
			"status": "queued",
			"triggered_by": "Administrator",
			"triggered_at": frappe.utils.now_datetime(),
			"traces": [{
				"trace_kind": "production_session",
				"source_session": self.session.name,
			}],
		}).insert(ignore_permissions=True)

	def test_marks_complete_and_persists_scores(self):
		fake = FakeProvider(responses=[
			_ok_payload(),
			_ok_payload({"by_objective": []}),
			_ok_payload(),
			_ok_payload({"calibration_offset": 0}),
		])
		with patch(
			"os_lms.os_lms.ai.simulations.eval.jobs._get_provider",
			return_value=fake,
		):
			run_production_evaluation(self.evaluation.name)

		doc = frappe.get_doc("LMSA Quality Evaluation", self.evaluation.name)
		self.assertEqual(doc.status, "complete")
		self.assertIsNotNone(doc.aggregate_persona_score)
		trace = doc.traces[0]
		self.assertEqual(trace.trace_status, "complete")
		scores = json.loads(trace.dimension_scores_json)
		self.assertEqual(len(scores), 4)

	def test_publishes_realtime(self):
		# Frappe also fires its own doc_update/list_update events through the
		# same channel during save(), so we look for our specific event name
		# rather than asserting call count.
		fake = FakeProvider(responses=[_ok_payload()] * 4)
		with patch(
			"os_lms.os_lms.ai.simulations.eval.jobs._get_provider",
			return_value=fake,
		), patch(
			"os_lms.os_lms.ai.simulations.eval.jobs.frappe.publish_realtime"
		) as pub:
			run_production_evaluation(self.evaluation.name)
		eval_complete_calls = [
			c for c in pub.call_args_list
			if c.args and c.args[0] == "simulation:eval_complete"
		]
		self.assertEqual(len(eval_complete_calls), 1)
		kwargs = eval_complete_calls[0].kwargs
		self.assertEqual(kwargs["message"]["eval_id"], self.evaluation.name)
		self.assertEqual(kwargs["message"]["status"], "complete")

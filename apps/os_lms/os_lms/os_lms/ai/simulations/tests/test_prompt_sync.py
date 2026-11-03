"""The migrate keeps the prompt records in step with the code
(docs/ai-simulator/PIANO-esito-e-punteggio-coach.md, phase 9).

The tests work on the real `role_play` record, with the code's defaults
patched: the record is put back field by field afterwards and the Version rows
the saves add are deleted by name."""
from __future__ import annotations

from unittest.mock import patch

import frappe
from frappe.tests import UnitTestCase

from os_lms.os_lms.ai.utils import prompt_sync
from os_lms.os_lms.ai.utils.template_loader import (
	DEFAULTS,
	load_prompt_template,
	prompt_fingerprint,
)

PURPOSE = "role_play"
FIELDS = (
	"label",
	"version",
	"system_template",
	"user_template",
	"output_schema",
	"temperature",
	"max_tokens",
	"available_placeholders",
	"enabled",
	"default_fingerprint",
	"code_version_not_applied",
	"modified",
	"modified_by",
)


def _code(version: str, text: str) -> dict:
	return {**DEFAULTS[PURPOSE], "version": version, "system_template": text}


class TestPromptFingerprint(UnitTestCase):
	def test_layout_does_not_count_but_content_does(self):
		base = {"system_template": "Uno\nDue", "user_template": "", "output_schema": {"a": 1, "b": 2},
			"temperature": 0.7, "max_tokens": 400}
		same = {**base, "system_template": "  Uno   \r\nDue\n\n", "output_schema": '{\n  "b": 2,\n  "a": 1\n}',
			"temperature": "0.70"}
		self.assertEqual(prompt_fingerprint(base), prompt_fingerprint(same))
		for change in ({"system_template": "Uno\nTre"}, {"temperature": 0.2}, {"max_tokens": 500},
				{"output_schema": {"a": 1}}, {"user_template": "Ciao"}):
			with self.subTest(change):
				self.assertNotEqual(prompt_fingerprint(base), prompt_fingerprint({**base, **change}))

	def test_signature_names_the_text_used(self):
		config = load_prompt_template(PURPOSE)
		version, text_hash = config["signature"].split("#")
		self.assertEqual(version, config["version"])
		self.assertEqual(len(text_hash), 8)


class TestPromptSync(UnitTestCase):
	def setUp(self):
		super().setUp()
		self.before = frappe.db.get_value(prompt_sync.DOCTYPE, PURPOSE, FIELDS, as_dict=True)
		self.versions_before = set(
			frappe.get_all("Version", {"ref_doctype": prompt_sync.DOCTYPE, "docname": PURPOSE}, pluck="name")
		)
		self.addCleanup(self._restore)

	def _restore(self):
		frappe.db.set_value(prompt_sync.DOCTYPE, PURPOSE, dict(self.before), update_modified=False)
		for name in frappe.get_all(
			"Version", {"ref_doctype": prompt_sync.DOCTYPE, "docname": PURPOSE}, pluck="name"
		):
			if name not in self.versions_before:
				frappe.db.delete("Version", {"name": name})
		frappe.db.commit()

	def _hold(self, text: str, *, fingerprint: str = "", missing: str = ""):
		frappe.db.set_value(
			prompt_sync.DOCTYPE,
			PURPOSE,
			{"system_template": text, "default_fingerprint": fingerprint, "code_version_not_applied": missing},
			update_modified=False,
		)

	def _sync(self, code: dict, previous=frozenset()):
		with patch.object(prompt_sync, "DEFAULTS", {PURPOSE: code}), patch.dict(
			prompt_sync.PREVIOUS_FINGERPRINTS, {PURPOSE: frozenset(previous)}
		):
			prompt_sync.sync_prompt_templates()
		return frappe.get_doc(prompt_sync.DOCTYPE, PURPOSE)

	def test_a_record_with_the_code_prompt_only_remembers_its_fingerprint(self):
		code = _code("rp.test", "Testo del codice")
		self._hold("Testo del codice   \n")
		doc = self._sync(code)
		self.assertEqual(doc.default_fingerprint, prompt_fingerprint(code))
		self.assertEqual(doc.system_template, "Testo del codice   \n")
		self.assertEqual(doc.modified, self.before.modified)

	def test_a_past_text_of_the_code_follows_the_code(self):
		old = _code("rp.old", "Testo vecchio")
		new = _code("rp.new", "Testo nuovo")
		self._hold("Testo vecchio", missing="rp.stale")
		doc = self._sync(new, previous={prompt_fingerprint(old)})
		self.assertEqual(doc.system_template, "Testo nuovo")
		self.assertEqual(doc.version, "rp.new")
		self.assertEqual(doc.default_fingerprint, prompt_fingerprint(new))
		self.assertFalse(doc.code_version_not_applied)

	def test_the_text_the_code_last_wrote_follows_the_code(self):
		first = _code("rp.one", "Prima versione")
		self._hold("Prima versione", fingerprint=prompt_fingerprint(first))
		second = _code("rp.two", "Seconda versione")
		doc = self._sync(second)
		self.assertEqual(doc.system_template, "Seconda versione")
		# And the next code version again
		doc = self._sync(_code("rp.three", "Terza versione"))
		self.assertEqual(doc.system_template, "Terza versione")

	def test_a_text_changed_from_the_panel_is_kept_and_flagged(self):
		written = _code("rp.one", "Testo del codice")
		self._hold("Testo cambiato dal pannello", fingerprint=prompt_fingerprint(written))
		doc = self._sync(_code("rp.two", "Testo nuovo del codice"))
		self.assertEqual(doc.system_template, "Testo cambiato dal pannello")
		self.assertEqual(doc.code_version_not_applied, "rp.two")
		self.assertEqual(doc.default_fingerprint, prompt_fingerprint(written))
		self.assertEqual(doc.modified, self.before.modified)

		# Once someone copies the code's text, the flag goes away
		self._hold("Testo nuovo del codice", fingerprint=prompt_fingerprint(written), missing="rp.two")
		doc = self._sync(_code("rp.two", "Testo nuovo del codice"))
		self.assertFalse(doc.code_version_not_applied)

	def test_the_staging_texts_of_ours_are_known(self):
		# The Coach with the equity rule and the Tutor with one more blank line
		self.assertEqual(len(prompt_sync.PREVIOUS_FINGERPRINTS["debrief"]), 6)
		self.assertIn(
			"650ce139e275150479fe9f0344bb976cfb4333c0da4d855a81728a3dea9bdf92",
			prompt_sync.PREVIOUS_FINGERPRINTS["debrief"],
		)
		self.assertIn(
			"c48be90e200bf298c31f3e774dd9c9ed8682efbfc9dba89c6198b37e581ea438",
			prompt_sync.PREVIOUS_FINGERPRINTS["tutor"],
		)
		# No current default is listed as a past one
		for purpose, fingerprints in prompt_sync.PREVIOUS_FINGERPRINTS.items():
			self.assertNotIn(prompt_fingerprint(DEFAULTS[purpose]), fingerprints, purpose)

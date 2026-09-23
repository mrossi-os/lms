"""Tests for inventory parsing and validation."""

import tempfile
import unittest
from pathlib import Path

from scripts.customizations.model import InventoryError, load_inventory

VALID_ENTRY = """
[[entries]]
id = "course-card-admin-gate"
title = "Menu di gestione sulla card corso"
layer = "spa-graft"
confidence = "high"
intent = "Visibile a Moderator e Docente, mai a Studente."

  [[entries.sites]]
  file = "frontend/src/components/CourseCardOverlay.vue"
  anchor = "Boolean(user.data?.is_docente)"
  symbol = "isAdmin"

  [entries.checks]
  unit = "frontend/src/tests/oslms/courseCardAdminGate.test.ts"
"""

FLOW_ENTRY = """
[[entries]]
id = "student-enrollment"
title = "Uno studente si iscrive a un corso"
layer = "flow"
confidence = "high"
intent = "Percorso minimo che uno studente deve poter completare."
"""


def write_inventory(directory, **files):
	"""Write each keyword argument as <name>.toml inside `directory`."""
	for name, body in files.items():
		(Path(directory) / f"{name}.toml").write_text(body, encoding="utf-8")
	return Path(directory)


class LoadInventoryTest(unittest.TestCase):
	def test_parses_a_valid_entry(self):
		with tempfile.TemporaryDirectory() as tmp:
			entries = load_inventory(write_inventory(tmp, grafts=VALID_ENTRY))
		self.assertEqual(len(entries), 1)
		entry = entries[0]
		self.assertEqual(entry.id, "course-card-admin-gate")
		self.assertEqual(entry.layer, "spa-graft")
		self.assertEqual(entry.source, "grafts.toml")
		self.assertEqual(len(entry.sites), 1)
		self.assertEqual(entry.sites[0].file, "frontend/src/components/CourseCardOverlay.vue")
		self.assertEqual(entry.sites[0].anchor, "Boolean(user.data?.is_docente)")
		self.assertEqual(entry.sites[0].symbol, "isAdmin")
		self.assertIsNone(entry.sites[0].marker)
		self.assertEqual(entry.checks["unit"], "frontend/src/tests/oslms/courseCardAdminGate.test.ts")
		self.assertIsNone(entry.status)

	def test_flow_entries_may_omit_sites(self):
		with tempfile.TemporaryDirectory() as tmp:
			entries = load_inventory(write_inventory(tmp, flows=FLOW_ENTRY))
		self.assertEqual(entries[0].sites, ())

	def test_non_flow_entry_without_sites_is_rejected(self):
		broken = FLOW_ENTRY.replace('layer = "flow"', 'layer = "spa-graft"')
		with tempfile.TemporaryDirectory() as tmp:
			with self.assertRaises(InventoryError) as caught:
				load_inventory(write_inventory(tmp, flows=broken))
		self.assertIn("student-enrollment", str(caught.exception))
		self.assertIn("sites", str(caught.exception))

	def test_missing_required_field_is_rejected(self):
		broken = VALID_ENTRY.replace('title = "Menu di gestione sulla card corso"\n', "")
		with tempfile.TemporaryDirectory() as tmp:
			with self.assertRaises(InventoryError) as caught:
				load_inventory(write_inventory(tmp, grafts=broken))
		self.assertIn("title", str(caught.exception))
		self.assertIn("grafts.toml", str(caught.exception))

	def test_unknown_layer_is_rejected(self):
		broken = VALID_ENTRY.replace('layer = "spa-graft"', 'layer = "whatever"')
		with tempfile.TemporaryDirectory() as tmp:
			with self.assertRaises(InventoryError) as caught:
				load_inventory(write_inventory(tmp, grafts=broken))
		self.assertIn("whatever", str(caught.exception))

	def test_site_without_anchor_is_rejected(self):
		broken = VALID_ENTRY.replace('  anchor = "Boolean(user.data?.is_docente)"\n', "")
		with tempfile.TemporaryDirectory() as tmp:
			with self.assertRaises(InventoryError) as caught:
				load_inventory(write_inventory(tmp, grafts=broken))
		self.assertIn("anchor", str(caught.exception))

	def test_duplicate_id_across_files_is_rejected(self):
		with tempfile.TemporaryDirectory() as tmp:
			with self.assertRaises(InventoryError) as caught:
				load_inventory(write_inventory(tmp, a=VALID_ENTRY, b=VALID_ENTRY))
		self.assertIn("course-card-admin-gate", str(caught.exception))

	def test_files_without_entries_are_ignored(self):
		actors = '[actors.gestore]\nemail = "e2e-gestore@oslms.test"\nroles = ["Gestore"]\n'
		with tempfile.TemporaryDirectory() as tmp:
			entries = load_inventory(write_inventory(tmp, grafts=VALID_ENTRY, actors=actors))
		self.assertEqual(len(entries), 1)

	def test_invalid_toml_names_the_file(self):
		with tempfile.TemporaryDirectory() as tmp:
			with self.assertRaises(InventoryError) as caught:
				load_inventory(write_inventory(tmp, grafts="[[entries]\nid = 'x'"))
		self.assertIn("grafts.toml", str(caught.exception))


if __name__ == "__main__":
	unittest.main()

"""Tests for the feature catalogue loader."""

import tempfile
import unittest
from pathlib import Path

from scripts.tests.gitrepo import chdir, git_repo
from scripts.customizations.features import FEATURE_STATUSES, Feature, load_features
from scripts.customizations.model import InventoryError

CARD = """\
id = "live-class-draft-publish"
title = "Classi live in bozza"
status = "active"
summary = "Una classe live nasce in bozza e si pubblica a parte."
why = "Il cliente vuole preparare le classi prima di invitare."
roles = ["Gestore"]
behaviour = [
	"una classe live nuova nasce in bozza",
	"gli inviti partono solo alla pubblicazione",
]
areas = ["apps/os_lms/os_lms/os_lms/live_class_*.py"]
upstream_watch = ["live class", "draft"]
history = [
	{ date = "2026-11-01", ref = "abc1234", summary = "creazione" },
]
"""

REQUIRED = ("id", "title", "status", "summary", "why", "behaviour", "areas", "upstream_watch", "history")


def write_card(directory, name="live-class-draft-publish", body=CARD):
	path = Path(directory) / f"{name}.toml"
	path.write_text(body, encoding="utf-8")
	return path


def without(body, key):
	"""Drop the TOML statement that starts with `key =` (handles multi-line arrays)."""
	out, skipping = [], False
	for line in body.splitlines():
		if not skipping and line.startswith(f"{key} ="):
			skipping = line.rstrip().endswith("[")
			continue
		if skipping:
			skipping = not line.startswith("]")
			continue
		out.append(line)
	return "\n".join(out) + "\n"


class LoadFeaturesTest(unittest.TestCase):
	def test_loads_a_valid_card(self):
		with tempfile.TemporaryDirectory() as tmp:
			write_card(tmp)
			features = load_features(Path(tmp))
		feature = features["live-class-draft-publish"]
		self.assertIsInstance(feature, Feature)
		self.assertEqual(feature.status, "active")
		self.assertEqual(
			feature.behaviour,
			("una classe live nuova nasce in bozza", "gli inviti partono solo alla pubblicazione"),
		)
		self.assertEqual(feature.roles, ("Gestore",))
		self.assertEqual(feature.history[0]["ref"], "abc1234")
		self.assertEqual(feature.source, "live-class-draft-publish.toml")
		self.assertIn("active", FEATURE_STATUSES)

	def test_rejects_id_different_from_filename(self):
		with tempfile.TemporaryDirectory() as tmp:
			write_card(tmp, name="other-name")
			with self.assertRaises(InventoryError) as ctx:
				load_features(Path(tmp))
		self.assertIn("other-name.toml", str(ctx.exception))

	def test_rejects_missing_required_field(self):
		for key in REQUIRED:
			with self.subTest(field=key), tempfile.TemporaryDirectory() as tmp:
				write_card(tmp, body=without(CARD, key))
				with self.assertRaises(InventoryError) as ctx:
					load_features(Path(tmp))
				self.assertIn(key, str(ctx.exception))

	def test_accepts_empty_areas(self):
		with tempfile.TemporaryDirectory() as tmp:
			write_card(tmp, body=CARD.replace('areas = ["apps/os_lms/os_lms/os_lms/live_class_*.py"]', "areas = []"))
			feature = load_features(Path(tmp))["live-class-draft-publish"]
		self.assertEqual(feature.areas, ())

	def test_missing_and_empty_fields_have_distinct_messages(self):
		with tempfile.TemporaryDirectory() as tmp:
			write_card(tmp, body=without(CARD, "areas"))
			with self.assertRaises(InventoryError) as missing:
				load_features(Path(tmp))
		self.assertIn("mancante", str(missing.exception))
		with tempfile.TemporaryDirectory() as tmp:
			write_card(tmp, body=without(CARD, "behaviour") + "behaviour = []\n")
			with self.assertRaises(InventoryError) as empty:
				load_features(Path(tmp))
		self.assertIn("vuoto", str(empty.exception))
		self.assertIn("behaviour", str(empty.exception))

	def test_rejects_unknown_status(self):
		with tempfile.TemporaryDirectory() as tmp:
			write_card(tmp, body=CARD.replace('status = "active"', 'status = "weird"'))
			with self.assertRaises(InventoryError) as ctx:
				load_features(Path(tmp))
		self.assertIn("weird", str(ctx.exception))

	def test_reads_through_a_reader_function(self):
		directory = Path("docs/customizations/features")
		calls = []

		def read(relative):
			calls.append(relative)
			return CARD

		with tempfile.TemporaryDirectory() as tmp, chdir(tmp):
			git_repo(
				tmp,
				**{
					"docs/customizations/features/live-class-draft-publish.toml": CARD,
					"docs/customizations/features/README.md": "x\n",
					"docs/customizations/features/old/other.toml": CARD,
				},
			)
			features = load_features(directory, read=read)
		self.assertEqual(list(features), ["live-class-draft-publish"])
		self.assertEqual(calls, ["docs/customizations/features/live-class-draft-publish.toml"])

	def test_reader_mode_outside_a_repository_raises_inventory_error(self):
		with tempfile.TemporaryDirectory() as tmp, chdir(tmp):
			with self.assertRaises(InventoryError):
				load_features(Path("docs/customizations/features"), read=lambda relative: CARD)

	def test_matches_path_with_globs(self):
		with tempfile.TemporaryDirectory() as tmp:
			write_card(tmp)
			feature = load_features(Path(tmp))["live-class-draft-publish"]
		base = "apps/os_lms/os_lms/os_lms/"
		self.assertTrue(feature.matches_path(base + "live_class_draft.py"))
		self.assertFalse(feature.matches_path(base + "valutatore.py"))


if __name__ == "__main__":
	unittest.main()

"""Color math behind Brand Customize Base and Advanced (fase-3-analisi.md, C1)."""

from __future__ import annotations

from frappe.tests import UnitTestCase

from os_lms.os_lms import branding_color as color


class TestOklch(UnitTestCase):
	def test_reference_values(self):
		# Published OKLCH of sRGB red: oklch(62.8% 0.2577 29.23).
		L, C, H = color.to_oklch("#ff0000")
		self.assertAlmostEqual(L, 0.628, places=3)
		self.assertAlmostEqual(C, 0.2577, places=3)
		self.assertAlmostEqual(H, 29.23, places=1)
		self.assertAlmostEqual(color.to_oklch("#ffffff")[0], 1.0, places=3)
		self.assertAlmostEqual(color.to_oklch("#000000")[0], 0.0, places=3)

	def test_round_trip(self):
		for value in ("#0a2e5a", "#c2185b", "#ffd85c", "#292929", "#ffffff", "#3fa", "#000000"):
			expanded = value if len(value) == 7 else "#" + "".join(d * 2 for d in value[1:])
			self.assertEqual(color.from_oklch(*color.to_oklch(value)), expanded.lower(), value)

	def test_out_of_gamut_chroma_is_reduced(self):
		value = color.from_oklch(0.9, 0.4, 260)
		self.assertTrue(color.is_hex(value))
		self.assertAlmostEqual(color.to_oklch(value)[0], 0.9, places=2)

	def test_stock_token_values_are_parsed(self):
		self.assertEqual(color.parse_oklch("oklch(.205 0 0)"), (0.205, 0.0, 0.0))
		self.assertEqual(color.parse_oklch("oklch(62.8% .25 29)"), (0.628, 0.25, 29.0))
		self.assertAlmostEqual(color.parse_oklch("#ffffff")[0], 1.0, places=3)
		self.assertIsNone(color.parse_oklch("var(--x)"))
		self.assertIsNone(color.parse_oklch(None))


class TestContrast(UnitTestCase):
	def test_ratio_bounds(self):
		self.assertAlmostEqual(color.contrast_ratio("#ffffff", "#000000"), 21, places=1)
		self.assertAlmostEqual(color.contrast_ratio("#777777", "#777777"), 1, places=3)

	def test_readable_ink(self):
		self.assertEqual(color.readable_ink("#ffd85c"), color.NEAR_BLACK)
		self.assertEqual(color.readable_ink("#0a2e5a"), color.WHITE)
		self.assertEqual(color.readable_ink("#ffffff"), color.NEAR_BLACK)

	def test_ensure_contrast_darkens_on_light_backgrounds(self):
		fixed = color.ensure_contrast("#ffd85c", "#ffffff")
		self.assertGreaterEqual(color.contrast_ratio(fixed, "#ffffff"), 4.5)
		self.assertLess(color.to_oklch(fixed)[0], color.to_oklch("#ffd85c")[0])

	def test_ensure_contrast_keeps_good_colors(self):
		self.assertEqual(color.ensure_contrast("#0a2e5a", "#ffffff"), "#0a2e5a")


class TestHelpers(UnitTestCase):
	def test_is_hex(self):
		for good in ("#fff", "#FFFFFF", " #0a2e5a "):
			self.assertTrue(color.is_hex(good), good)
		for bad in ("fff", "#ffff", "oklch(1 0 0)", "", None, 12):
			self.assertFalse(color.is_hex(bad), bad)

	def test_mix_ends(self):
		self.assertEqual(color.mix("#0a2e5a", "#ffffff", 0), "#0a2e5a")
		self.assertEqual(color.mix("#0a2e5a", "#ffffff", 1), "#ffffff")

	def test_rotate_and_shift(self):
		L, C, H = color.to_oklch("#c2185b")
		rotated = color.to_oklch(color.rotate_hue("#c2185b", 120))
		self.assertAlmostEqual(rotated[0], L, places=2)
		self.assertAlmostEqual((rotated[2] - H) % 360, 120, delta=3)
		self.assertAlmostEqual(color.to_oklch(color.shift_lightness("#c2185b", 0.1))[0], L + 0.1, places=2)

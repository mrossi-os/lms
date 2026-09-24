"""Every whitelisted-method override must stay compatible with the upstream original.

Two ways an upstream merge breaks an override without any other check noticing:
the override module stops importing (v2.62.0 removed a helper override_api.py
imported, which took down every override in that module), or upstream adds a
parameter the override does not declare, which Frappe drops silently
(search_sqlite lost `category`, get_courses/get_batches lost `limit_page_length`).

Framework shims (hooks.framework_method_shims) stand in for Frappe methods that do
not exist on our release, so the rule is inverted for them: the original must still
be missing, and the shim goes once Frappe ships it.
"""

from __future__ import annotations

import inspect

import frappe
from frappe.tests import UnitTestCase

from os_lms import hooks

SKIPPED_KINDS = (inspect.Parameter.VAR_KEYWORD, inspect.Parameter.VAR_POSITIONAL)


def _parameters(path: str):
	return inspect.signature(inspect.unwrap(frappe.get_attr(path))).parameters


def _wrapped_overrides():
	return {
		original: override
		for original, override in hooks.override_whitelisted_methods.items()
		if original not in hooks.framework_method_shims
	}


class TestOverrideSignatures(UnitTestCase):
	def test_every_override_resolves(self):
		for original, override in _wrapped_overrides().items():
			with self.subTest(override=override):
				frappe.get_attr(override)
				frappe.get_attr(original)

	def test_no_override_drops_an_upstream_parameter(self):
		for original, override in _wrapped_overrides().items():
			ours = _parameters(override)
			if any(p.kind == inspect.Parameter.VAR_KEYWORD for p in ours.values()):
				continue
			dropped = [
				name
				for name, param in _parameters(original).items()
				if name not in ours and param.kind not in SKIPPED_KINDS
			]
			with self.subTest(override=override):
				self.assertEqual(dropped, [], f"{override} drops {dropped} accepted by {original}")

	def test_every_framework_shim_is_still_needed(self):
		for original, shim in hooks.framework_method_shims.items():
			with self.subTest(shim=shim):
				self.assertEqual(hooks.override_whitelisted_methods.get(original), shim)
				frappe.get_attr(shim)
				with self.assertRaises(
					(AttributeError, ImportError), msg=f"Frappe now ships {original}: remove {shim}"
				):
					frappe.get_attr(original)

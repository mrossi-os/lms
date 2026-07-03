"""Course-as-prompt-context renderer.

When a prompt needs to know "what is this course about" — to generate a
simulation scenario, an evaluation rubric, a debrief, or any other AI
output grounded in a specific course — feeding the raw doctype is verbose
and noisy. ``format_course_context`` produces a compact, readable text
block suitable to drop into any prompt's user message.

Usage::

    from os_lms.os_lms.ai.utils.course_context import format_course_context

    block = format_course_context("LMS-COURSE-2026-001")
    # or
    block = format_course_context(frappe.get_doc("LMS Course", name))

Behaviour
---------
- Accepts the course ``name`` (str) **or** an already-loaded Frappe
  Document. Strings that can't be resolved to a doc yield an empty string;
  the caller never has to handle a "missing course" branch.
- Strips HTML from ``description`` (TextEditor field) so the prompt
  doesn't waste tokens on markup.
- Caps each long field so a single course can't dominate the prompt window.
- Skips fields that are empty / missing — the rendered block contains only
  the parts that actually carry information.
"""

from __future__ import annotations

import html as _html
import json
import re
from typing import Any

import frappe

from os_lms.os_lms.utils import get_course_feature_sections

# Soft caps to keep the rendered block bounded; descriptions on the Frappe
# LMS doctype can run several thousand characters when an instructor pastes
# in marketing copy.
_MAX_DESCRIPTION_CHARS = 1500
_MAX_INTRODUCTION_CHARS = 800

_HTML_BLOCK_TAG_RE = re.compile(r"</?(?:p|br|div|li|h[1-6]|tr)[^>]*>", re.IGNORECASE)
_HTML_TAG_RE = re.compile(r"<[^>]+>")


def format_course_context(course: Any, *, include_title: bool = True) -> str:
	"""Return a plain-text rendering of an LMS Course for prompt injection.

	``course`` can be the course ``name`` (str) or an already-loaded
	document object. Returns an empty string when the input cannot be
	resolved to a real course — callers can append the result
	unconditionally and only the populated sections will appear.

	``include_title`` defaults to True. Set it to False when the prompt
	template already exposes the course title through a separate
	placeholder (e.g. tutor's ``{{course_title}}``) to avoid duplication.
	"""
	doc = _resolve_course(course)
	if doc is None:
		return ""

	blocks: list[str] = []
	if include_title:
		title = _get(doc, "title") or _get(doc, "name") or ""
		if title:
			blocks.append(f"Titolo: {title}")

	intro = _trim(_get(doc, "short_introduction"), _MAX_INTRODUCTION_CHARS)
	if intro:
		blocks.append(f"Introduzione:\n{intro}")

	description = _trim(_strip_html(_get(doc, "description")), _MAX_DESCRIPTION_CHARS)
	if description:
		blocks.append(f"Descrizione:\n{description}")

	tags = (_get(doc, "tags") or "").strip()
	if tags:
		# `tags` on LMS Course is a CSV. Normalize spacing for readability.
		normalized = ", ".join(t.strip() for t in tags.split(",") if t.strip())
		if normalized:
			blocks.append(f"Tag: {normalized}")

	feature_sections = _format_feature_sections(get_course_feature_sections(doc.name))
	if feature_sections:
		blocks.append(f"Caratteristiche del corso:\n{feature_sections}")

	return "\n\n".join(blocks)


# ---------- internals ----------


def _resolve_course(course: Any):
	if course is None:
		return None
	if isinstance(course, str):
		if not course.strip():
			return None
		try:
			return frappe.get_doc("LMS Course", course)
		except Exception:
			return None
	return course


def _get(doc: Any, field: str) -> Any:
	"""Read a field from a Frappe Document or any dict-like object."""
	if hasattr(doc, "get"):
		try:
			return doc.get(field)
		except Exception:
			pass
	return getattr(doc, field, None)


def _trim(text: Any, max_chars: int) -> str:
	if not text:
		return ""
	text = str(text).strip()
	if len(text) <= max_chars:
		return text
	return text[:max_chars].rstrip() + "…"


def _strip_html(text: Any) -> str:
	"""Light HTML stripper — no full parser, intentionally."""
	if not text:
		return ""
	text = str(text)
	# Turn block-level tags into newlines so paragraphs stay separated.
	text = _HTML_BLOCK_TAG_RE.sub("\n", text)
	text = _HTML_TAG_RE.sub("", text)
	text = _html.unescape(text)
	# Collapse runs of blank lines and trim each line.
	lines = [ln.strip() for ln in text.splitlines()]
	out_lines: list[str] = []
	prev_blank = False
	for ln in lines:
		if ln:
			out_lines.append(ln)
			prev_blank = False
		elif not prev_blank:
			out_lines.append("")
			prev_blank = True
	return "\n".join(out_lines).strip()


def _format_feature_sections(sections: Any) -> str:
	"""Render the ``feature_sections`` custom field JSON as readable text.

	The field stores an array of ``{title, items: [{title, description}, ...]}``
	objects. Returns an empty string on any parse/shape failure so prompts
	stay robust against malformed values.
	"""
	if not isinstance(sections, list):
		return ""

	blocks: list[str] = []
	for section in sections:
		if not isinstance(section, dict):
			continue
		title = (section.get("title") or "").strip()
		items = section.get("items") or []
		lines: list[str] = []
		if title:
			lines.append(f"{title}:")
		for item in items:
			if not isinstance(item, dict):
				continue
			t = (item.get("title") or "").strip()
			d = (item.get("description") or "").strip()
			if t and d:
				lines.append(f"- {t}: {d}")
			elif t:
				lines.append(f"- {t}")
			elif d:
				lines.append(f"- {d}")
		if lines:
			blocks.append("\n".join(lines))
	return "\n\n".join(blocks)

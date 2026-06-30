"""Whitelisted REST endpoints for realtime (voice) simulations.

URL prefix: /api/method/os_lms.os_lms.ai.realtime.api.<name>

Thin control-plane shell: validate, gate (permissions + quota), delegate to
SessionOrchestrator, mint an ephemeral provider token. NO audio passes through
here — the client streams directly to the provider with the ephemeral token.
"""
from __future__ import annotations

from typing import NoReturn

import frappe
from frappe import _

from os_lms.os_lms.ai.simulations.api import _resolve_published_scenario, load_session
from os_lms.os_lms.ai.simulations.orchestrator import (
	QuotaExceededError,
	SessionOrchestrator,
	SessionTerminatedError,
)
from os_lms.os_lms.ai.simulations.prompts.role_play import build_role_play_system_prompt
from os_lms.os_lms.ai.utils.realtime import (
	RealtimeError,
	RealtimeInvalidAuth,
	RealtimeRateLimit,
	RealtimeServerError,
	RealtimeSessionConfig,
	RealtimeTimeout,
	RealtimeUnsupported,
	resolve_realtime_provider,
)
from lms.lms.utils import has_moderator_role
from os_lms.os_lms.ai.utils.llm import load_settings


def _service() -> SessionOrchestrator:
	return SessionOrchestrator()


@frappe.whitelist()
def create_voice_session(scenario_id: str) -> dict:
	"""Create a voice Session, mint an ephemeral provider token, return the
	descriptor the client needs to open the direct realtime stream."""
	settings = load_settings()
	if not settings.realtime_enabled:
		frappe.throw(_("Realtime voice is not enabled."), frappe.PermissionError)

	scenario = _resolve_published_scenario(scenario_id)
	if scenario.modality not in ("voice", "both"):
		frappe.throw(_("Scenario {0} is not voice-enabled.").format(scenario.name))

	try:
		started = _service().start_voice_session(scenario_id=scenario.name)
	except QuotaExceededError as e:
		frappe.throw(str(e), frappe.ValidationError)

	# Build the realtime instructions from the generated persona (reuses Prompt 2).
	instructions = build_role_play_system_prompt(
		persona=started.persona,
		generated_situation=started.situation,
		difficulty=started.difficulty,
	)
	voice_instructions = (scenario.get("voice_instructions") or "").strip()
	if voice_instructions:
		instructions = f"{instructions}\n\n# Delivery\n{voice_instructions}"

	override = scenario.provider_override if scenario.provider_override not in (None, "", "auto") else None
	provider = resolve_realtime_provider(override=override)
	cfg = RealtimeSessionConfig(
		instructions=instructions,
		voice=(scenario.get("voice") or settings.realtime_voice or ""),
		model=settings.realtime_model or "",
		turn_detection=settings.turn_detection or "server_vad",
		input_language="it",
		max_session_seconds=int(settings.realtime_max_session_seconds or 300),
		session_label=SessionOrchestrator.pseudonymize_session_id(frappe.session.user)[:12],
	)

	try:
		rt = provider.create_session(cfg)
	except RealtimeInvalidAuth:
		_throw(_("the realtime provider is not configured correctly"))
	except (RealtimeRateLimit, RealtimeServerError, RealtimeTimeout):
		_throw(_("the realtime service is temporarily unavailable"))
	except RealtimeUnsupported:
		_throw(_("the selected provider does not support realtime voice"))
	except RealtimeError as e:
		_throw(str(e) or _("realtime session could not be created"))

	# Audit which provider/model/voice were actually used.
	frappe.db.set_value(
		"LMSA Simulation Session",
		started.session,
		{
			"realtime_provider_used": rt.provider,
			"realtime_model_used": rt.model,
			"voice_used": rt.voice,
		},
	)
	frappe.db.commit()

	return {
		"session_id": started.session,
		"transport": rt.transport,
		"connect_url": rt.connect_url,
		"client_secret": rt.client_secret,
		"voice": rt.voice,
		"model": rt.model,
		"expires_at": rt.expires_at,
		"max_seconds": cfg.max_session_seconds,
		"extra": rt.extra,
	}


@frappe.whitelist()
def persist_transcript_turn(session_id: str, role: str, text: str) -> dict:
	"""Persist a final transcript turn relayed by the client."""
	session = load_session(session_id)
	if session.student != frappe.session.user:
		frappe.throw(_("Only the session owner can relay turns."), frappe.PermissionError)
	try:
		result = _service().persist_voice_turn(session_id=session.name, role=role, text=text)
	except SessionTerminatedError:
		frappe.throw(_("This session is no longer accepting turns."), frappe.ValidationError)
	return dict(result)


@frappe.whitelist()
def end_voice_session(session_id: str, reason: str = "completed", seconds: int = 0) -> dict:
	"""Mark the voice session terminal, record duration, enqueue the debrief."""
	if reason not in ("completed", "abandoned"):
		frappe.throw(_("Unsupported reason: {0}").format(reason))
	session = load_session(session_id)
	if session.student != frappe.session.user and not has_moderator_role():
		frappe.throw(_("Only the session owner can end the session."), frappe.PermissionError)

	if seconds:
		frappe.db.set_value(
			"LMSA Simulation Session", session.name, "session_seconds", int(seconds)
		)
	return dict(_service().end_session(session_id=session.name, reason=reason))


def _throw(reason: str) -> NoReturn:
	frappe.log_error(title="LMSA realtime error")
	frappe.throw(_("Realtime error: {0}.").format(reason))

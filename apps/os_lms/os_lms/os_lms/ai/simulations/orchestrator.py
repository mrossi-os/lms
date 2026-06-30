"""Lifecycle of a simulation session.

The SessionOrchestrator owns the state machine and the side effects:
- builds the system prompts (delegating to `prompts/`)
- talks to the LLM through the provider-agnostic layer (`utils/llm`)
- persists Sessions and Turns
- emits realtime events (sprint 2 covers blocking; streaming arrives later)

Pure logic (prompt building, parsing, injection detection) lives in
`prompts/` so it can be tested without frappe.
"""

from __future__ import annotations

import hashlib
import json
import logging
import random
import string
import time

import frappe
from frappe import _

from os_lms.os_lms.ai.utils.llm import (
	ChatMessage,
	ChatResponse,
	LLMError,
	LLMProvider,
	chat_with_fallback,
	resolve_provider,
)
from os_lms.os_lms.ai.utils.oslms_settings import OsLmsSettings

# Status constants live next to the doctype that owns them
from os_lms.os_lms.doctype.lmsa_simulation_session.lmsa_simulation_session import (
	STATUS_ABANDONED,
	STATUS_COMPLETED,
	STATUS_ERROR,
	STATUS_IN_PROGRESS,
	TERMINAL_STATUSES,
)

from .prompts import (
	ROLE_PLAY_VERSION,
	SCENARIO_GEN_VERSION,
	PersonaVariant,
	ScenarioVariant,
	detect_injection,
	in_character_refusal,
)

# Realtime event names (kept short; documented in PLAN-os_lms.md §5.2).
EVENT_TURN_START = "simulation:turn_start"
EVENT_TURN_COMPLETE = "simulation:turn_complete"
EVENT_ERROR = "simulation:error"

# Default daily quota when LMSA Settings does not declare one yet.
DEFAULT_DAILY_QUOTA = 10


class QuotaExceededError(Exception):
	"""Raised by validate_quota when the student is past their daily limit."""


class SessionTerminatedError(Exception):
	"""Raised when a turn is sent to a session already in a terminal state."""


class SessionOrchestrator:
	"""Service class. Stateless across requests; cheap to instantiate."""

	_settings: OsLmsSettings | None = None
	_logger: logging.Logger | None = None

	# ---------- lazy dependencies (Service Pattern) ----------

	@property
	def settings(self) -> OsLmsSettings:
		if self._settings is None:
			from os_lms.os_lms.ai.utils.llm import _load_settings

			self._settings = _load_settings()
		return self._settings

	@property
	def logger(self) -> logging.Logger:
		if self._logger is None:
			self._logger = frappe.logger("os_lmsa", allow_site=True)
		return self._logger

	# ---------- public lifecycle ----------

	def start_session(
		self,
		*,
		scenario_id: str,
		modality: str = "chat",
		seed: str | None = None,
	) -> frappe._dict:
		"""Create a Session, generate the variant, persist the first role-player turn.

		Returns a dict with keys: session, first_turn (turn name + text).
		"""
		if not self.settings.simulations_enabled:
			frappe.throw(_("AI Simulations are not enabled in LMSA Settings."))

		scenario = frappe.get_doc("LMSA Simulation Scenario", scenario_id)
		if scenario.status != "Published":
			frappe.throw(
				_("Scenario {0} is not Published (status: {1}).").format(scenario.name, scenario.status),
				frappe.PermissionError,
			)

		seed = seed or _new_seed()
		provider = self._resolve_provider("chat", scenario)

		variant = self._generate_variant(scenario, seed, provider)

		session = frappe.new_doc("LMSA Simulation Session")
		# Set student BEFORE insert(): the permission gate runs before
		# before_insert(), so has_permission needs `doc.student` to be the
		# current user already to grant create.
		session.student = frappe.session.user
		session.scenario = scenario.name
		session.modality = modality
		session.seed = seed
		session.prompt_version = f"{SCENARIO_GEN_VERSION}+{ROLE_PLAY_VERSION}"
		session.generated_situation = variant.situation
		session.generated_persona = json.dumps(_persona_to_dict(variant.persona), ensure_ascii=False)
		session.chat_provider_used = provider.name
		session.chat_model_used = _model_from_provider(provider)
		session.insert()

		first_turn = self._persist_turn(
			session=session,
			role="assistant",
			text=_first_roleplay_line(variant),
			provider_used=provider.name,
			model_used=session.chat_model_used,
		)
		session.turn_count = 1
		session.save()
		frappe.db.commit()

		self.logger.info(
			"simulation start: session=%s scenario=%s seed=%s provider=%s",
			session.name,
			scenario.name,
			seed,
			provider.name,
		)
		return frappe._dict(
			session=session.name,
			first_turn=frappe._dict(name=first_turn.name, text=first_turn.text_content),
		)

	def send_message(self, *, session_id: str, user_text: str) -> frappe._dict:
		"""Append a user turn, ask the role-player to reply, persist the assistant turn."""
		if not user_text or not user_text.strip():
			frappe.throw(_("User message cannot be empty."))

		session = frappe.get_doc("LMSA Simulation Session", session_id)
		if session.status in TERMINAL_STATUSES:
			raise SessionTerminatedError(f"Session {session_id} is in terminal state {session.status!r}")

		# 1) Persist the user turn (and flag injection attempts).
		attack = detect_injection(user_text)
		user_turn = self._persist_turn(
			session=session,
			role="user",
			text=user_text.strip(),
			injection_attempt=attack,
		)
		self._publish(
			EVENT_TURN_START,
			session,
			{"user_turn_name": user_turn.name, "injection_attempt": int(attack)},
		)

		# 2) Assistant turn — either canned refusal or LLM-generated.
		try:
			persona = _persona_from_session(session)
			if attack:
				assistant_text = in_character_refusal(persona.name)
				assistant_turn = self._persist_turn(
					session=session,
					role="assistant",
					text=assistant_text,
					provider_used=session.chat_provider_used,
					model_used=session.chat_model_used,
				)
				latency_ms = 0
			else:
				t0 = time.monotonic()
				response = self._ask_role_player(session, persona)
				latency_ms = int((time.monotonic() - t0) * 1000)
				assistant_turn = self._persist_turn(
					session=session,
					role="assistant",
					text=response.text,
					provider_used=response.provider,
					model_used=response.model,
					tokens_input=response.usage.prompt_tokens,
					tokens_output=response.usage.completion_tokens,
					latency_ms=latency_ms,
				)
				# Audit the actual provider/model (could differ from session-init due to fallback).
				session.chat_provider_used = response.provider
				session.chat_model_used = response.model
		except LLMError as e:
			self._publish(EVENT_ERROR, session, {"layer": "llm", "code": type(e).__name__, "message": str(e)})
			session.status = STATUS_ERROR
			session.save()
			frappe.db.commit()
			raise

		session.turn_count = (session.turn_count or 0) + 2  # user + assistant
		session.save()
		frappe.db.commit()

		self._publish(
			EVENT_TURN_COMPLETE,
			session,
			{
				"turn_name": assistant_turn.name,
				"text": assistant_turn.text_content,
				"latency_ms": latency_ms,
				"injection_attempt": int(attack),
			},
		)

		return frappe._dict(
			user_turn=frappe._dict(name=user_turn.name),
			assistant_turn=frappe._dict(name=assistant_turn.name, text=assistant_turn.text_content),
			injection_attempt=bool(attack),
		)

	def end_session(self, *, session_id: str, reason: str = "completed") -> frappe._dict:
		"""Mark the session as completed/abandoned and submit it (immutability)."""
		session = frappe.get_doc("LMSA Simulation Session", session_id)
		if session.status in TERMINAL_STATUSES:
			return frappe._dict(session=session.name, status=session.status, already_terminal=True)

		status = STATUS_COMPLETED if reason == "completed" else STATUS_ABANDONED
		session.status = status
		session.ended_at = frappe.utils.now_datetime()
		session.save()
		# Submit to make the session immutable (audit / debrief input).
		if session.docstatus == 0:
			session.submit()
		frappe.db.commit()

		self.logger.info(
			"simulation end: session=%s status=%s turns=%s", session.name, status, session.turn_count
		)

		# Enqueue the debrief job. Best-effort: if the queue is unavailable
		# we still return success — the polling endpoint will report Pending.
		try:
			frappe.enqueue(
				"os_lms.os_lms.ai.simulations.tasks.generate_debrief",
				queue="long",
				timeout=300,
				session_id=session.name,
				enqueue_after_commit=True,
			)
		except Exception as e:
			self.logger.warning("failed to enqueue debrief: %s", e)

		return frappe._dict(session=session.name, status=status)

	def start_voice_session(
		self,
		*,
		scenario_id: str,
		seed: str | None = None,
	) -> frappe._dict:
		"""Create a voice Session and generate the persona variant.

		Unlike start_session (chat), this does NOT persist a first assistant
		turn: the opening line is spoken live by the realtime model. Returns the
		session name + the data the feature layer needs to build the realtime
		instructions (persona/situation/difficulty).
		"""
		if not self.settings.simulations_enabled:
			frappe.throw(_("AI Simulations are not enabled in LMSA Settings."))

		scenario = frappe.get_doc("LMSA Simulation Scenario", scenario_id)
		if scenario.status != "Published":
			frappe.throw(
				_("Scenario {0} is not Published (status: {1}).").format(scenario.name, scenario.status),
				frappe.PermissionError,
			)

		seed = seed or _new_seed()
		# Persona generation stays TEXTUAL (reuses the existing LLM layer).
		text_provider = self._resolve_provider("chat", scenario)
		variant = self._generate_variant(scenario, seed, text_provider)

		session = frappe.new_doc("LMSA Simulation Session")
		session.student = frappe.session.user
		session.scenario = scenario.name
		session.modality = "voice"
		session.seed = seed
		session.prompt_version = f"{SCENARIO_GEN_VERSION}+{ROLE_PLAY_VERSION}"
		session.generated_situation = variant.situation
		session.generated_persona = json.dumps(_persona_to_dict(variant.persona), ensure_ascii=False)
		session.insert()
		frappe.db.commit()

		return frappe._dict(
			session=session.name,
			persona=variant.persona,
			situation=variant.situation,
			difficulty=_scenario_difficulty(scenario.name),
		)

	def persist_voice_turn(self, *, session_id: str, role: str, text: str) -> frappe._dict:
		"""Append a transcript turn relayed by the client during a voice session."""
		if role not in ("user", "assistant"):
			frappe.throw(_("Invalid turn role: {0}").format(role))
		clean = (text or "").strip()
		if not clean:
			frappe.throw(_("Empty transcript turn"))

		session = frappe.get_doc("LMSA Simulation Session", session_id)
		self._enforce_max_duration(session)
		if session.status in TERMINAL_STATUSES:
			raise SessionTerminatedError(
				f"Session {session_id} is in terminal state {session.status!r}"
			)

		attack = detect_injection(clean) if role == "user" else False
		turn = self._persist_turn(
			session=session,
			role=role,
			text=clean,
			provider_used=session.realtime_provider_used or "",
			model_used=session.realtime_model_used or "",
			injection_attempt=attack,
		)
		session.turn_count = (session.turn_count or 0) + 1
		session.save()
		frappe.db.commit()
		self._publish(
			EVENT_TURN_COMPLETE,
			session,
			{"turn_name": turn.name, "text": clean, "role": role, "injection_attempt": int(attack)},
		)
		return frappe._dict(turn=turn.name)

	# ---------- internals ----------

	def _resolve_provider(self, purpose: str, scenario) -> LLMProvider:
		override = (scenario.provider_override or "auto") if scenario else "auto"
		override = None if override == "auto" else override
		return resolve_provider(purpose=purpose, override=override)

	def _generate_variant(self, scenario, seed: str, provider: LLMProvider) -> ScenarioVariant:
		from os_lms.os_lms.ai.simulations.role_player import ScenarioVariantGenerator

		scenario_ref = self._scenario_ref_from_doc(scenario)
		generator = ScenarioVariantGenerator(
			provider=provider,
			model=_model_from_provider(provider) or None,
		)
		return generator.generate(scenario_ref, seed=seed)

	def _scenario_ref_from_doc(self, scenario) -> ScenarioRef:
		from os_lms.os_lms.ai.simulations.eval.types import ScenarioRef

		objectives = [(row.objective_text or "").strip() for row in (scenario.learning_objectives or [])]
		objectives = [o for o in objectives if o]
		variations = {
			(row.variable_name or "").strip(): [
				v.strip() for v in (row.possible_values or "").splitlines() if v.strip()
			]
			for row in (scenario.seed_variations or [])
			if (row.variable_name or "").strip()
		}
		return ScenarioRef(
			name=scenario.name,
			scenario_name=scenario.scenario_name,
			learning_objectives=objectives,
			difficulty=scenario.difficulty,
			roleplay_persona=scenario.roleplay_persona or "",
			situation_template=scenario.situation_template or "",
			max_turns=scenario.max_turns or 20,
			evaluation_schema=scenario.evaluation_schema or "",
			seed_variations=variations,
			course=getattr(scenario, "lms_course", "") or "",
			course_lesson=getattr(scenario, "course_lesson", "") or "",
		)

	def _ask_role_player(self, session, persona: PersonaVariant) -> ChatResponse:
		"""Send the full history + role-play system prompt to the LLM."""
		from os_lms.os_lms.ai.simulations.role_player import RolePlayerTurnService

		history = _load_chat_history(session.name)
		override = _scenario_provider_override(session.scenario)

		def _chat_fn(*, messages, system, **kwargs):
			return chat_with_fallback(
				"chat",
				messages,
				override=override,
				system=system,
				**kwargs,
			)

		service = RolePlayerTurnService(chat_fn=_chat_fn)
		return service.ask(
			persona=persona,
			situation=session.generated_situation,
			difficulty=_scenario_difficulty(session.scenario),
			history=history,
		)

	def _persist_turn(
		self,
		*,
		session,
		role: str,
		text: str,
		provider_used: str | None = None,
		model_used: str | None = None,
		tokens_input: int = 0,
		tokens_output: int = 0,
		latency_ms: int = 0,
		injection_attempt: bool = False,
	):
		turn = frappe.new_doc("LMSA Simulation Turn")
		turn.session = session.name
		turn.turn_index = _next_turn_index(session.name)
		turn.role = role
		turn.text_content = text
		turn.provider_used = provider_used or ""
		turn.model_used = model_used or ""
		turn.tokens_input = tokens_input
		turn.tokens_output = tokens_output
		turn.latency_ms = latency_ms
		turn.injection_attempt_detected = 1 if injection_attempt else 0
		turn.insert(ignore_permissions=True)
		return turn

	def _publish(self, event: str, session, payload: dict) -> None:
		"""Emit a realtime event to the session's student."""
		try:
			frappe.publish_realtime(
				event=event,
				message={"session": session.name, **payload},
				user=session.student,
			)
		except Exception as e:
			# Realtime is best-effort: don't fail the turn over a websocket hiccup.
			self.logger.warning("publish_realtime(%s) failed: %s", event, e)

	def _enforce_max_duration(self, session) -> None:
		"""Force-terminate a voice session past its max duration (spec §7).

		The client also runs a timer, but the backend must not rely on it.
		Called at the start of persist_voice_turn. Ends the session through the
		normal terminal path (submit + debrief enqueue) and signals the caller.
		"""
		max_seconds = int(getattr(self.settings, "realtime_max_session_seconds", 0) or 0)
		if not max_seconds or not session.started_at:
			return
		elapsed = (frappe.utils.now_datetime() - session.started_at).total_seconds()
		if elapsed <= max_seconds:
			return
		if session.status not in TERMINAL_STATUSES:
			self.end_session(session_id=session.name, reason="completed")
		raise SessionTerminatedError(
			f"Session {session.name} exceeded max duration of {max_seconds}s"
		)

	# ---------- privacy ----------

	@staticmethod
	def pseudonymize_session_id(user: str) -> str:
		"""Return a stable SHA-256 hash of the user id.

		Used when sending payloads to external LLM providers so the upstream
		does not see real email addresses. Deterministic across requests so we
		can correlate logs without storing the cleartext.
		"""
		return hashlib.sha256(user.encode("utf-8")).hexdigest()


# ----- module-level hook -----


def validate_quota(doc, method=None) -> None:
	"""Hook: before_insert on LMSA Simulation Session.

	Counts sessions started today by this student and blocks if the daily
	quota is exhausted. Quota=0 means unlimited. Lives at module level so
	Frappe's hook resolver can address it as a dotted path.
	"""
	from os_lms.os_lms.ai.utils.llm import _load_settings

	settings = _load_settings()
	quota = getattr(settings, "simulation_daily_quota_per_user", None)
	if quota is None:
		quota = DEFAULT_DAILY_QUOTA
	if not quota:  # 0 = unlimited
		return

	student = doc.student or frappe.session.user
	today_start = frappe.utils.now_datetime().replace(hour=0, minute=0, second=0, microsecond=0)
	count = frappe.db.count(
		"LMSA Simulation Session",
		filters=[["student", "=", student], ["started_at", ">=", today_start]],
	)
	if count >= quota:
		raise QuotaExceededError(_("Daily simulation quota of {0} reached for {1}.").format(quota, student))


# ----- module-level helpers (kept here for cohesion with the class) -----


def _next_turn_index(session_name: str) -> int:
	row = frappe.db.sql(
		"SELECT MAX(turn_index) FROM `tabLMSA Simulation Turn` WHERE session = %s",
		(session_name,),
	)
	last = row[0][0] if row and row[0] else None
	return (last or 0) + 1


def _load_chat_history(session_name: str) -> list[ChatMessage]:
	rows = frappe.db.get_all(
		"LMSA Simulation Turn",
		filters={"session": session_name},
		fields=["role", "text_content"],
		order_by="turn_index asc",
	)
	out: list[ChatMessage] = []
	for r in rows:
		if r["role"] not in ("user", "assistant"):
			continue
		out.append(ChatMessage(role=r["role"], content=r["text_content"] or ""))
	return out


def _persona_to_dict(persona: PersonaVariant) -> dict:
	return {
		"name": persona.name,
		"role": persona.role,
		"context": persona.context,
		"mood": persona.mood,
		"key_objection": persona.key_objection,
		"hidden_motivation": persona.hidden_motivation,
	}


def _persona_from_session(session) -> PersonaVariant:
	raw = session.generated_persona or "{}"
	data = json.loads(raw) if raw else {}
	return PersonaVariant(
		name=data.get("name", ""),
		role=data.get("role", ""),
		context=data.get("context", ""),
		mood=data.get("mood", ""),
		key_objection=data.get("key_objection", ""),
		hidden_motivation=data.get("hidden_motivation", ""),
	)


def _scenario_difficulty(scenario_name: str) -> str:
	return frappe.db.get_value("LMSA Simulation Scenario", scenario_name, "difficulty") or "medium"


def _scenario_provider_override(scenario_name: str) -> str | None:
	val = frappe.db.get_value("LMSA Simulation Scenario", scenario_name, "provider_override")
	if not val or val == "auto":
		return None
	return val


def _model_from_provider(provider: LLMProvider) -> str:
	"""Best-effort: providers don't expose their default model on the ABC; reach
	into the underlying config when present."""
	cfg = getattr(provider, "_config", None)
	return getattr(cfg, "default_model", "") if cfg is not None else ""


def _first_roleplay_line(variant: ScenarioVariant) -> str:
	"""Deterministic opening line that hands the floor to the student.

	Kept short and neutral so the student decides the opening tactic.
	"""
	persona = variant.persona
	return f"Buongiorno, sono {persona.name}, {persona.role} ({persona.context})."


def _new_seed() -> str:
	return "".join(random.choices(string.ascii_lowercase + string.digits, k=10))

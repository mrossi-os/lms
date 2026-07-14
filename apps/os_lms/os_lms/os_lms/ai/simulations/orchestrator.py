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
from frappe.model.document import Document

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
	STATUS_READY,
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
DEFAULT_DAILY_QUOTA = 100

# ---- Time-based natural close ----
# Chat sessions are bounded by the scenario's time_limit_minutes only (0 = no
# cap; turns are NOT enforced in chat). Once past the cap the student's next
# message gets a single reply that both answers them AND closes the conversation;
# then their input is locked. The session is NOT auto-ended — the STUDENT ends it
# via "Termina" (see send_message + _closing_directive_text + closing_input_locked).

# Directive appended to the role-play system prompt (and reinforced as the last
# user turn) once time is up. Italian to match the role-play prompt language;
# framed as stage direction ("REGIA") so the model treats it as an
# out-of-character instruction. The bot answers the student's last message AND
# closes the conversation in the same reply.
_CLOSING_DIRECTIVE = (
	"[REGIA] Il tempo è terminato: questo è il tuo ULTIMO messaggio. Rispondi "
	"brevemente all'ultimo messaggio dell'utente e, nello STESSO messaggio, "
	"chiudi la conversazione restando nel personaggio: tira le somme e congedati "
	"con un saluto. Non porre nuove domande e non proporre di continuare."
)

# The bot delivers this many closing replies after time-up (one combined
# answer+farewell); afterwards the student's input is locked and they can only
# press "Termina". The session is never auto-ended.
MAX_CLOSING_REPLIES = 1


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

	def prepare_session(
		self,
		*,
		scenario_id: str | Document,
		modality: str = "chat",
		seed: str | None = None,
	) -> frappe._dict:
		"""Generate the variant and create a Ready session (no turns yet).

		Returns keys: session (name), brief (student_brief), modality.
		"""
		if not self.settings.simulations_enabled:
			frappe.throw(_("AI Simulations are not enabled in LMSA Settings."))

		if isinstance(scenario_id, str):
			scenario = frappe.get_doc("LMSA Simulation Scenario", scenario_id)
			if scenario.status != "Published":
				frappe.throw(
					_("Scenario {0} is not Published (status: {1}).").format(
						scenario.name, scenario.status
					),
					frappe.PermissionError,
				)
		else:
			scenario = scenario_id

		seed = seed or _new_seed()
		provider = self._resolve_provider("chat", scenario)
		variant = self._generate_variant(scenario, seed, provider)

		# When the instructor authored a brief (the "compito"), show that verbatim
		# instead of the AI-generated one. `{variable_name}` placeholders are
		# resolved with the SAME seed as the situation, so a brief that references
		# a seed variation stays consistent with the rendered scene. Persona and
		# situation are still AI-varied per session — only the student-facing brief
		# text is taken from the scenario.
		manual_brief = (getattr(scenario, "student_brief", "") or "").strip()
		if manual_brief:
			from .prompts.scenario_generator import render_situation_template

			student_brief, _picked = render_situation_template(
				manual_brief, _seed_variations_from_doc(scenario), seed=seed
			)
		else:
			student_brief = variant.student_brief

		session = frappe.new_doc("LMSA Simulation Session")
		# Set student BEFORE insert(): the permission gate runs before
		# before_insert(), so has_permission needs `doc.student` already set.
		session.student = frappe.session.user
		session.scenario = scenario.name
		session.modality = modality
		session.status = STATUS_READY
		session.seed = seed
		session.prompt_version = f"{SCENARIO_GEN_VERSION}+{ROLE_PLAY_VERSION}"
		session.generated_situation = variant.situation
		session.student_brief = student_brief
		session.generated_persona = json.dumps(
			_persona_to_dict(variant.persona), ensure_ascii=False
		)
		session.chat_provider_used = provider.name
		session.chat_model_used = _model_from_provider(provider)
		session.insert()
		frappe.db.commit()

		self.logger.info(
			"simulation prepare: session=%s scenario=%s seed=%s provider=%s",
			session.name,
			scenario.name,
			seed,
			provider.name,
		)
		return frappe._dict(
			session=session.name,
			brief=student_brief,
			modality=modality,
		)

	def begin_chat_session(self, *, session_id: str) -> frappe._dict:
		"""Persist the first role-player turn for a prepared chat session.

		Returns keys: session (name), first_turn ({name, text}).
		"""
		session = frappe.get_doc("LMSA Simulation Session", session_id)
		if session.status in TERMINAL_STATUSES:
			raise SessionTerminatedError(
				f"Session {session_id} is in terminal state {session.status!r}"
			)
		if session.status == STATUS_IN_PROGRESS and (session.turn_count or 0) > 0:
			# Idempotent: already begun. Return the existing first turn.
			first = frappe.get_all(
				"LMSA Simulation Turn",
				filters={"session": session.name, "role": "assistant"},
				fields=["name", "text_content"],
				order_by="turn_index asc",
				limit=1,
			)
			if first:
				return frappe._dict(
					session=session.name,
					first_turn=frappe._dict(name=first[0].name, text=first[0].text_content),
				)

		variant = ScenarioVariant(
			situation=session.generated_situation or "",
			student_brief=session.student_brief or "",
			persona=_persona_from_session(session),
		)
		first_turn = self._persist_turn(
			session=session,
			role="assistant",
			text=_first_roleplay_line(variant),
			provider_used=session.chat_provider_used,
			model_used=session.chat_model_used,
		)
		session.status = STATUS_IN_PROGRESS
		session.modality = "chat"
		session.turn_count = 1
		session.save()
		frappe.db.commit()

		self.logger.info("simulation begin: session=%s", session.name)
		return frappe._dict(
			session=session.name,
			first_turn=frappe._dict(name=first_turn.name, text=first_turn.text_content),
		)

	def start_session(
		self,
		*,
		scenario_id: str | Document,
		modality: str = "chat",
		seed: str | None = None,
	) -> frappe._dict:
		"""Prepare + begin in one call (chat). Preserved for internal callers
		(eval runner, instructor Test Run, tests).

		Accepts a scenario name or a pre-loaded Document; passing a Document
		lets an authorized caller bypass the "is Published" gate in
		`prepare_session` (used by the instructor "test as student" flow)."""
		prepared = self.prepare_session(
			scenario_id=scenario_id, modality=modality, seed=seed
		)
		begun = self.begin_chat_session(session_id=prepared.session)
		return frappe._dict(session=prepared.session, first_turn=begun.first_turn)

	def send_message(self, *, session_id: str, user_text: str) -> frappe._dict:
		"""Append a user turn, ask the role-player to reply, persist the assistant turn."""
		if not user_text or not user_text.strip():
			frappe.throw(_("User message cannot be empty."))

		session = frappe.get_doc("LMSA Simulation Session", session_id)
		if session.status in TERMINAL_STATUSES:
			raise SessionTerminatedError(f"Session {session_id} is in terminal state {session.status!r}")

		# Time-based natural close: once past the scenario time cap, the student's
		# next message gets a single reply that both answers them AND closes the
		# conversation; after that (MAX_CLOSING_REPLIES) the student's input is
		# locked (frontend) and further sends are refused here too. The session is
		# NOT auto-ended — the student ends it via "Termina". Computed BEFORE
		# persisting this turn.
		time_limit_minutes = scenario_time_limit(session.scenario)
		remaining, over_budget = _time_budget_state(session, time_limit_minutes)
		if over_budget >= MAX_CLOSING_REPLIES:
			raise SessionTerminatedError(
				f"Session {session_id} closing reply already delivered; not accepting further messages"
			)
		closing_directive = _closing_directive_text(remaining)

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
				response = self._ask_role_player(session, persona, closing_directive=closing_directive)
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

	def clone_session(self, *, session_id: str) -> frappe._dict:
		"""Create a new Ready session copying the source variant (same
		persona/situation/brief). Used to retry an identical challenge.

		Returns keys: session (name), brief, modality.
		"""
		src = frappe.get_doc("LMSA Simulation Session", session_id)
		clone = frappe.new_doc("LMSA Simulation Session")
		clone.student = frappe.session.user
		clone.scenario = src.scenario
		clone.modality = src.modality
		clone.status = STATUS_READY
		clone.seed = src.seed
		clone.prompt_version = src.prompt_version
		clone.generated_situation = src.generated_situation
		clone.generated_persona = src.generated_persona
		clone.student_brief = src.student_brief
		clone.chat_provider_used = src.chat_provider_used
		clone.chat_model_used = src.chat_model_used
		clone.insert()
		frappe.db.commit()
		self.logger.info("simulation clone: src=%s new=%s", src.name, clone.name)
		return frappe._dict(
			session=clone.name,
			brief=clone.student_brief,
			modality=clone.modality,
		)

	def start_voice_session(self, *, session_id: str) -> frappe._dict:
		"""Activate a prepared voice Session for live realtime streaming.

		Reuses the persona/situation generated at prepare time (no
		regeneration). Marks the session In Progress. Returns the data the
		realtime control-plane needs to build the model instructions.
		"""
		if not self.settings.simulations_enabled:
			frappe.throw(_("AI Simulations are not enabled in LMSA Settings."))

		session = frappe.get_doc("LMSA Simulation Session", session_id)
		if session.status in TERMINAL_STATUSES:
			raise SessionTerminatedError(
				f"Session {session_id} is in terminal state {session.status!r}"
			)
		session.modality = "voice"
		if session.status != STATUS_IN_PROGRESS:
			session.status = STATUS_IN_PROGRESS
		session.save()
		frappe.db.commit()

		return frappe._dict(
			session=session.name,
			persona=_persona_from_session(session),
			situation=session.generated_situation,
			difficulty=_scenario_difficulty(session.scenario),
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
			raise SessionTerminatedError(f"Session {session_id} is in terminal state {session.status!r}")

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
		variations = _seed_variations_from_doc(scenario)
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

	def _ask_role_player(
		self, session, persona: PersonaVariant, closing_directive: str = ""
	) -> ChatResponse:
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
			closing_directive=closing_directive,
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
		raise SessionTerminatedError(f"Session {session.name} exceeded max duration of {max_seconds}s")

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
	if count >= 200 * quota:
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


# ----- time-based natural-close helpers (shared with api.get_session) -----
#
# The budget is ACTIVE time: wall-clock elapsed minus the time spent waiting for
# the bot (sum of assistant turns' latency_ms). A slow model must not consume the
# student's time, so latency is excluded from both the countdown the student sees
# and the forced-close decision.


def scenario_time_limit(scenario_name: str) -> int:
	"""Return the scenario's chat time cap in minutes (0 = no cap)."""
	return int(
		frappe.db.get_value("LMSA Simulation Scenario", scenario_name, "time_limit_minutes") or 0
	)


def _time_budget_state(session, time_limit_minutes: int) -> tuple[float | None, int]:
	"""Return (remaining_active_seconds, over_budget_reply_count).

	remaining_active_seconds is None when no cap is set and may be <= 0 once the
	student's active budget is spent (a float so the over-budget threshold matches
	exactly between the current reply and past replies — the reply that gets the
	closing directive is precisely the one counted). For each assistant turn the
	latency cancels out, so ``active_at_send`` is the active time consumed at the
	moment the student sent the message that produced that turn — bot latency never
	counts. over_budget_reply_count is how many replies were produced at/after the
	budget was spent (drives the input lock).
	"""
	if not time_limit_minutes or time_limit_minutes <= 0 or not session.started_at:
		return None, 0
	limit_seconds = int(time_limit_minutes) * 60
	started = frappe.utils.get_datetime(session.started_at)
	rows = frappe.db.get_all(
		"LMSA Simulation Turn",
		filters={"session": session.name, "role": "assistant"},
		fields=["creation", "latency_ms"],
		order_by="turn_index asc",
	)
	cum_latency = 0.0
	over_budget = 0
	for r in rows:
		cum_latency += (r.latency_ms or 0) / 1000.0
		active_at_send = (
			frappe.utils.get_datetime(r.creation) - started
		).total_seconds() - cum_latency
		if active_at_send >= limit_seconds:
			over_budget += 1
	active_elapsed = (frappe.utils.now_datetime() - started).total_seconds() - cum_latency
	return limit_seconds - active_elapsed, over_budget


def remaining_seconds(session, time_limit_minutes: int) -> int | None:
	"""Active seconds left before the time cap (>= 0), or None when no cap.

	Stays at 0 while the forced close plays out after the budget is spent.
	"""
	remaining, _ = _time_budget_state(session, time_limit_minutes)
	return None if remaining is None else max(0, int(remaining))


def _closing_directive_text(remaining: float | None) -> str:
	"""Closing directive for the reply about to be generated, or "" while within
	the ACTIVE time budget (pure — takes a precomputed remaining budget).

	Once the budget is spent the role-player gets a single directive to answer the
	student's last message AND close the conversation in the same reply. After
	that one reply the student's input is locked (see closing_input_locked) — the
	session is NOT auto-ended; the student ends it via "Termina".
	"""
	if remaining is None or remaining > 0:
		return ""
	return _CLOSING_DIRECTIVE


def closing_input_locked(session, time_limit_minutes: int) -> bool:
	"""True once the bot has delivered its MAX_CLOSING_REPLIES closing replies:
	the student can no longer send messages and can only press "Termina". The
	session stays In Progress until they do."""
	_remaining, over_budget = _time_budget_state(session, time_limit_minutes)
	return over_budget >= MAX_CLOSING_REPLIES


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


def _seed_variations_from_doc(scenario) -> dict[str, list[str]]:
	"""Build the ``variable_name -> [values]`` map from a scenario's
	Seed Variation rows, in the shape ``render_situation_template`` expects."""
	return {
		(row.variable_name or "").strip(): [
			v.strip() for v in (row.possible_values or "").splitlines() if v.strip()
		]
		for row in (scenario.seed_variations or [])
		if (row.variable_name or "").strip()
	}

# Realtime Voice Simulations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a provider-agnostic real-time speech-to-speech ("voice") modality to the existing AI simulations, with Frappe as control plane and audio flowing directly client↔provider.

**Architecture:** A new provider abstraction (`ai/utils/realtime/`, mirroring `ai/utils/llm` and `ai/utils/audio`) mints ephemeral client tokens; a thin whitelisted feature layer (`ai/realtime/api.py`) reuses the existing `SessionOrchestrator`, persona generation, and debrief pipeline; a Vue composable selects a transport (WebRTC for OpenAI, WebSocket for Gemini) and relays transcript turns back to Frappe. No audio passes through Frappe.

**Tech Stack:** Python 3.10+ (Frappe app `os_lms`), `requests` (SDK-free adapters), `frappe.tests.UnitTestCase`, Vue 3 + Frappe UI (frontend), WebRTC / WebSocket (browser transports).

## Global Constraints

- All code comments, identifiers, and commit messages in **English**.
- Python: Ruff — line-length 110, **tab** indentation, double quotes, target py310.
- `require_type_annotated_api_methods = True` — every `@frappe.whitelist()` method must have full type annotations.
- **Provider SDK encapsulation:** no provider SDK import may appear outside `utils/{llm,stt,tts,realtime}/providers/`. Realtime adapters are **SDK-free** (use `requests`) like the audio adapters.
- The **API key never leaves the server.** Clients receive only a short-lived ephemeral token (`client_secret`).
- `realtime_max_session_seconds` default = **300** (5 min).
- Default realtime provider = **openai**, default model = **gpt-realtime-2**, transport **webrtc**.
- New doctype/settings fields are **additive** and defaulted so existing call sites keep working.
- Commit after every green step (Conventional Commits: `feat`, `test`, `chore`, ...).

**Reference patterns to copy (read before starting):**
- `apps/os_lms/os_lms/os_lms/ai/utils/audio/` — full ABC + registry + config + `__init__` resolve pattern.
- `apps/os_lms/os_lms/os_lms/ai/utils/llm/__init__.py` — `_load_settings`, `build_*_config`, `resolve_*`.
- `apps/os_lms/os_lms/os_lms/ai/simulations/api.py` — whitelisted endpoint conventions, `load_session`, `_resolve_published_scenario`.
- `apps/os_lms/os_lms/os_lms/ai/simulations/orchestrator.py` — `SessionOrchestrator`, `_persist_turn`, `_generate_variant`, `_publish`, `pseudonymize_session_id`.
- `apps/os_lms/os_lms/os_lms/ai/utils/llm/tests/test_provider_encapsulation.py` — the architectural test to extend.

**Test command (single module):**
`bench --site lms.localhost run-tests --app os_lms --module os_lms.os_lms.ai.utils.realtime.tests.test_realtime`
(Adjust `--site` to your bench site. For a single class use the framework's discovery; the pure tests need no DB but run under the Frappe test harness like `test_audio.py`.)

---

### Task 1: Realtime abstraction core (errors, config, provider ABC, registry, mock, public surface)

Builds the network-free skeleton of the abstraction plus the deterministic mock, so every later task has a stable contract and a no-network provider to test against.

**Files:**
- Create: `apps/os_lms/os_lms/os_lms/ai/utils/realtime/__init__.py`
- Create: `apps/os_lms/os_lms/os_lms/ai/utils/realtime/errors.py`
- Create: `apps/os_lms/os_lms/os_lms/ai/utils/realtime/config.py`
- Create: `apps/os_lms/os_lms/os_lms/ai/utils/realtime/provider.py`
- Create: `apps/os_lms/os_lms/os_lms/ai/utils/realtime/registry.py`
- Create: `apps/os_lms/os_lms/os_lms/ai/utils/realtime/providers/__init__.py`
- Create: `apps/os_lms/os_lms/os_lms/ai/utils/realtime/providers/mock.py`
- Create: `apps/os_lms/os_lms/os_lms/ai/utils/realtime/tests/__init__.py`
- Create: `apps/os_lms/os_lms/os_lms/ai/utils/realtime/tests/test_realtime.py`

**Interfaces:**
- Produces:
  - `RealtimeProviderConfig(name: str, api_key: str = "", default_model: str = "", voice: str = "", turn_detection: str = "server_vad", input_language: str = "it", max_session_seconds: int = 300, base_url: str | None = None, extra: dict = {})`
  - `RealtimeSession(provider, model, transport, client_secret, connect_url, expires_at, voice, extra)` — dataclass.
  - `RealtimeSessionConfig(instructions: str, voice: str, model: str, turn_detection: str, input_language: str, max_session_seconds: int, session_label: str)` — dataclass built by the feature layer.
  - `TranscriptEvent(role: str, text: str, final: bool)` — dataclass.
  - `RealtimeProvider` ABC with `create_session(cfg) -> RealtimeSession`, `parse_transcript_event(event: dict) -> TranscriptEvent | None`, `health_check() -> bool`.
  - `register_realtime(name)`, `get_realtime_provider(config)`, `list_realtime_providers()`.
  - `resolve_realtime_provider(*, override: str | None = None) -> RealtimeProvider`, `build_realtime_config(name: str, settings) -> RealtimeProviderConfig`.
  - Errors: `RealtimeError, RealtimeUnsupported, RealtimeInvalidAuth, RealtimeRateLimit, RealtimeServerError, RealtimeTimeout, RealtimeInvalidInput`.

- [ ] **Step 1: Write the failing test**

Create `apps/os_lms/os_lms/os_lms/ai/utils/realtime/tests/__init__.py` (empty) and `test_realtime.py`:

```python
"""Unit tests for the realtime provider abstraction (ai/utils/realtime).

Pure tests — no DB, no network. Exercise the registry, config wiring, the
mock adapter's create_session, and transcript-event parsing.
"""
from __future__ import annotations

from dataclasses import dataclass

from frappe.tests import UnitTestCase

from os_lms.os_lms.ai.utils import realtime
from os_lms.os_lms.ai.utils.realtime.provider import (
	RealtimeProvider,
	RealtimeSession,
	RealtimeSessionConfig,
)


@dataclass
class _FakeSettings:
	realtime_enabled: bool = True
	realtime_provider: str = "openai"
	realtime_model: str = ""
	realtime_voice: str = ""
	turn_detection: str = "server_vad"
	realtime_max_session_seconds: int = 300
	openai_key: str = "sk-test"
	openai_base_url: str = ""
	gemini_key: str = "gm-test"


def _cfg() -> RealtimeSessionConfig:
	return RealtimeSessionConfig(
		instructions="You are a recruiter.",
		voice="marin",
		model="mock-realtime",
		turn_detection="server_vad",
		input_language="it",
		max_session_seconds=300,
		session_label="abc123",
	)


class TestRealtimeRegistry(UnitTestCase):
	def test_mock_is_registered(self):
		self.assertIn("mock", realtime.list_realtime_providers())

	def test_unknown_provider_raises(self):
		with self.assertRaises(ValueError):
			realtime.get_realtime_provider(
				realtime.RealtimeProviderConfig(name="nope")
			)


class TestMockProvider(UnitTestCase):
	def test_create_session_is_deterministic(self):
		provider = realtime.get_realtime_provider(
			realtime.RealtimeProviderConfig(name="mock", default_model="mock-realtime")
		)
		session = provider.create_session(_cfg())
		self.assertIsInstance(session, RealtimeSession)
		self.assertEqual(session.provider, "mock")
		self.assertEqual(session.transport, "mock")
		self.assertTrue(session.client_secret.startswith("mock-secret-"))
		self.assertEqual(session.voice, "marin")

	def test_parse_transcript_event_user(self):
		provider = realtime.get_realtime_provider(
			realtime.RealtimeProviderConfig(name="mock")
		)
		ev = provider.parse_transcript_event(
			{"role": "user", "text": "Hello", "final": True}
		)
		self.assertEqual((ev.role, ev.text, ev.final), ("user", "Hello", True))

	def test_parse_transcript_event_ignores_non_final(self):
		provider = realtime.get_realtime_provider(
			realtime.RealtimeProviderConfig(name="mock")
		)
		self.assertIsNone(
			provider.parse_transcript_event({"role": "user", "text": "He", "final": False})
		)


class TestConfigWiring(UnitTestCase):
	def test_openai_defaults(self):
		cfg = realtime.build_realtime_config("openai", _FakeSettings())
		self.assertEqual(cfg.name, "openai")
		self.assertEqual(cfg.default_model, "gpt-realtime-2")
		self.assertEqual(cfg.voice, "marin")
		self.assertEqual(cfg.max_session_seconds, 300)
		self.assertEqual(cfg.api_key, "sk-test")

	def test_unknown_config_raises(self):
		with self.assertRaises(ValueError):
			realtime.build_realtime_config("nope", _FakeSettings())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bench --site lms.localhost run-tests --app os_lms --module os_lms.os_lms.ai.utils.realtime.tests.test_realtime`
Expected: FAIL — `ModuleNotFoundError: os_lms.os_lms.ai.utils.realtime`.

- [ ] **Step 3: Write `errors.py`**

```python
"""Normalized errors raised by realtime adapters.

Parallel to ai/utils/audio/errors: adapters translate provider-specific
failures into these classes so the whitelisted API layer reacts uniformly.
"""
from __future__ import annotations


class RealtimeError(Exception):
	"""Base class for any error raised by a RealtimeProvider adapter."""

	def __init__(
		self,
		message: str = "",
		*,
		provider: str | None = None,
		cause: Exception | None = None,
	):
		super().__init__(message)
		self.provider = provider
		self.cause = cause


class RealtimeUnsupported(RealtimeError):
	"""The provider does not support realtime session minting."""


class RealtimeInvalidAuth(RealtimeError):
	"""API key missing or invalid (mis-config)."""


class RealtimeRateLimit(RealtimeError):
	"""429 / quota exhausted."""


class RealtimeServerError(RealtimeError):
	"""5xx from the provider, or a transport-level failure."""


class RealtimeTimeout(RealtimeError):
	"""Request timed out."""


class RealtimeInvalidInput(RealtimeError):
	"""Input rejected before contacting the provider."""
```

- [ ] **Step 4: Write `config.py`**

```python
"""Configuration object passed to RealtimeProvider adapters.

Adapters never read frappe settings directly — they only see a
RealtimeProviderConfig built by build_realtime_config() (in __init__.py).
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RealtimeProviderConfig:
	"""Configuration for a single realtime provider adapter instance.

	`name` is the registry key (e.g. "openai", "gemini", "mock").
	"""

	name: str
	api_key: str = ""
	default_model: str = ""
	voice: str = ""
	turn_detection: str = "server_vad"
	input_language: str = "it"
	max_session_seconds: int = 300
	base_url: str | None = None
	extra: dict = field(default_factory=dict)
```

- [ ] **Step 5: Write `provider.py`**

```python
"""Provider-agnostic realtime (speech-to-speech) abstraction.

Mirrors ai/utils/audio: business code consumes RealtimeProvider through this
module and never reaches into adapter modules. Concrete adapters live in
providers/ and encapsulate any HTTP detail (SDK-free, via `requests`).

The abstraction is a CONTROL-PLANE contract only: create_session mints an
ephemeral token; the audio stream itself is established client-side and never
touches the backend.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from .errors import RealtimeUnsupported


@dataclass
class RealtimeSession:
	"""What the client needs to open a direct realtime connection.

	`transport` tells the client which strategy to use ("webrtc" | "websocket"
	| "mock"). `client_secret` is the ephemeral token (NEVER the api key).
	`extra` carries opaque provider-specific fields (e.g. Gemini resumption).
	"""

	provider: str
	model: str
	transport: str
	client_secret: str
	connect_url: str
	expires_at: int
	voice: str
	extra: dict = field(default_factory=dict)


@dataclass
class RealtimeSessionConfig:
	"""Built by the feature layer from the Scenario persona + settings."""

	instructions: str
	voice: str
	model: str
	turn_detection: str = "server_vad"
	input_language: str = "it"
	max_session_seconds: int = 300
	session_label: str = ""


@dataclass
class TranscriptEvent:
	"""Normalized transcript output for persistence as a Turn."""

	role: str  # "user" | "assistant"
	text: str
	final: bool


class RealtimeProvider(ABC):
	"""Abstract base for a realtime provider adapter."""

	name: str = ""

	@abstractmethod
	def create_session(self, cfg: RealtimeSessionConfig) -> RealtimeSession:
		"""Mint an ephemeral client token server-side and return everything
		the client needs to connect. The api key stays on the server."""
		raise RealtimeUnsupported(
			f"{self.name or 'provider'} does not support realtime sessions"
		)

	@abstractmethod
	def parse_transcript_event(self, event: dict) -> TranscriptEvent | None:
		"""Normalize a provider event into a TranscriptEvent, or None if the
		event is not a final transcript (deltas, control frames, etc.)."""

	def health_check(self) -> bool:
		"""Lightweight check used to validate configuration."""
		return False
```

- [ ] **Step 6: Write `registry.py`**

```python
"""Realtime provider registry: decorator-based registration + factory.

Parallel to ai/utils/audio/registry. Adapters in providers/ decorate their
class with @register_realtime("name"); business code uses
get_realtime_provider(config) and never imports adapter classes.
"""
from __future__ import annotations

from .config import RealtimeProviderConfig
from .provider import RealtimeProvider

_REALTIME_PROVIDERS: dict[str, type[RealtimeProvider]] = {}


def register_realtime(name: str):
	"""Class decorator that registers a realtime adapter under a stable key."""

	def deco(cls: type[RealtimeProvider]) -> type[RealtimeProvider]:
		if not issubclass(cls, RealtimeProvider):
			raise TypeError(f"{cls.__name__} must subclass RealtimeProvider")
		_REALTIME_PROVIDERS[name] = cls
		cls.name = name
		return cls

	return deco


def get_realtime_provider(config: RealtimeProviderConfig) -> RealtimeProvider:
	if config.name not in _REALTIME_PROVIDERS:
		available = ", ".join(sorted(_REALTIME_PROVIDERS)) or "<none registered>"
		raise ValueError(
			f"Unknown realtime provider: {config.name!r}. Available: {available}"
		)
	return _REALTIME_PROVIDERS[config.name](config)


def list_realtime_providers() -> list[str]:
	return sorted(_REALTIME_PROVIDERS)


def _reset_for_tests() -> None:
	"""Internal helper: clear the registry. Use only in tests."""
	_REALTIME_PROVIDERS.clear()
```

- [ ] **Step 7: Write `providers/mock.py` and `providers/__init__.py`**

`providers/__init__.py`:

```python
"""Side-effect registration of built-in realtime adapters.

Importing this package registers every adapter via the @register_realtime
decorator. ai/utils/realtime/__init__.py imports it once.
"""
from __future__ import annotations

from . import mock  # noqa: F401
from . import openai_realtime  # noqa: F401
from . import gemini_live  # noqa: F401
```

> NOTE: `openai_realtime` and `gemini_live` are created in Tasks 2 and 3. Until
> then, comment those two import lines out OR create empty stub modules. To keep
> Task 1 self-contained and green, create the two stub files now with a single
> line `"""Placeholder — implemented in Task 2/3."""` and uncomment as you go.
> (Simplest: create both stubs now.)

Create stub `providers/openai_realtime.py` and `providers/gemini_live.py` each containing only:

```python
"""Placeholder — implemented in a later task."""
```

`providers/mock.py`:

```python
"""Deterministic mock realtime provider for tests and local development.

No network, no keys. Lets the feature layer and frontend be exercised with
realtime_provider = "mock".
"""
from __future__ import annotations

from ..config import RealtimeProviderConfig
from ..provider import (
	RealtimeProvider,
	RealtimeSession,
	RealtimeSessionConfig,
	TranscriptEvent,
)
from ..registry import register_realtime


@register_realtime("mock")
class MockRealtimeProvider(RealtimeProvider):
	"""Deterministic adapter: fixed ephemeral token + passthrough events."""

	def __init__(self, config: RealtimeProviderConfig):
		self._config = config

	def create_session(self, cfg: RealtimeSessionConfig) -> RealtimeSession:
		return RealtimeSession(
			provider=self.name,
			model=cfg.model or self._config.default_model or "mock-realtime",
			transport="mock",
			client_secret=f"mock-secret-{cfg.session_label or 'x'}",
			connect_url="mock://realtime",
			expires_at=0,
			voice=cfg.voice or self._config.voice or "marin",
			extra={"instructions": cfg.instructions},
		)

	def parse_transcript_event(self, event: dict) -> TranscriptEvent | None:
		if not event.get("final"):
			return None
		role = event.get("role")
		if role not in ("user", "assistant"):
			return None
		return TranscriptEvent(role=role, text=event.get("text", "") or "", final=True)

	def health_check(self) -> bool:
		return True
```

- [ ] **Step 8: Write `__init__.py` (public surface + config wiring + resolver)**

```python
"""Public surface of the realtime (speech-to-speech) layer.

Business code imports from os_lms.os_lms.ai.utils.realtime and never reaches
into adapter modules. resolve_realtime_provider() reads the shared
OsLmsSettings (same loader as the LLM/audio layers) and returns a configured
RealtimeProvider; build_realtime_config() is the single wiring point.
"""
from __future__ import annotations

from .config import RealtimeProviderConfig
from .errors import (
	RealtimeError,
	RealtimeInvalidAuth,
	RealtimeInvalidInput,
	RealtimeRateLimit,
	RealtimeServerError,
	RealtimeTimeout,
	RealtimeUnsupported,
)
from .provider import (
	RealtimeProvider,
	RealtimeSession,
	RealtimeSessionConfig,
	TranscriptEvent,
)
from .registry import (
	get_realtime_provider,
	list_realtime_providers,
	register_realtime,
)

# Side-effect: register all built-in adapters.
from . import providers as _providers  # noqa: F401


__all__ = [
	"RealtimeError",
	"RealtimeInvalidAuth",
	"RealtimeInvalidInput",
	"RealtimeProvider",
	"RealtimeProviderConfig",
	"RealtimeRateLimit",
	"RealtimeServerError",
	"RealtimeSession",
	"RealtimeSessionConfig",
	"RealtimeTimeout",
	"RealtimeUnsupported",
	"TranscriptEvent",
	"build_realtime_config",
	"get_realtime_provider",
	"list_realtime_providers",
	"register_realtime",
	"resolve_realtime_provider",
]

# Sensible defaults if a settings field is blank.
_DEFAULT_MODEL = {"openai": "gpt-realtime-2", "gemini": "gemini-live-2.5-flash-native-audio"}
_DEFAULT_VOICE = {"openai": "marin", "gemini": "Puck"}


def resolve_realtime_provider(*, override: str | None = None) -> RealtimeProvider:
	"""Return a configured RealtimeProvider.

	The provider is chosen from settings.realtime_provider (default "openai");
	`override` (e.g. a Scenario field) takes precedence.
	"""
	settings = _load_settings()
	name = override or settings.realtime_provider or "openai"
	config = build_realtime_config(name, settings)
	return get_realtime_provider(config)


def build_realtime_config(name: str, settings) -> RealtimeProviderConfig:
	"""Map (provider name, OsLmsSettings) to a RealtimeProviderConfig.

	Single place to wire a new realtime provider. Reuses the per-provider keys
	already configured for the chat layer.
	"""
	max_seconds = getattr(settings, "realtime_max_session_seconds", 0) or 300
	turn_detection = getattr(settings, "turn_detection", "") or "server_vad"

	if name == "mock":
		return RealtimeProviderConfig(name="mock", default_model="mock-realtime")

	if name == "openai":
		return RealtimeProviderConfig(
			name="openai",
			api_key=getattr(settings, "openai_key", "") or "",
			default_model=getattr(settings, "realtime_model", "") or _DEFAULT_MODEL["openai"],
			voice=getattr(settings, "realtime_voice", "") or _DEFAULT_VOICE["openai"],
			turn_detection=turn_detection,
			max_session_seconds=max_seconds,
			base_url=getattr(settings, "openai_base_url", "") or None,
		)

	if name == "gemini":
		return RealtimeProviderConfig(
			name="gemini",
			api_key=getattr(settings, "gemini_key", "") or "",
			default_model=getattr(settings, "realtime_model", "") or _DEFAULT_MODEL["gemini"],
			voice=getattr(settings, "realtime_voice", "") or _DEFAULT_VOICE["gemini"],
			turn_detection=turn_detection,
			max_session_seconds=max_seconds,
		)

	raise ValueError(f"No realtime provider config wiring for {name!r}")


def _load_settings():
	"""Reuse the LLM layer's settings loader (single OsLmsSettings source)."""
	from os_lms.os_lms.ai.utils.llm import load_settings

	return load_settings()
```

> NOTE on the test `test_openai_defaults`: it asserts `voice == "marin"`. The
> `_FakeSettings` has `realtime_voice` absent → `getattr(..., "")` → default
> "marin". Matches.

- [ ] **Step 9: Run the test to verify it passes**

Run: `bench --site lms.localhost run-tests --app os_lms --module os_lms.os_lms.ai.utils.realtime.tests.test_realtime`
Expected: PASS (all classes).

- [ ] **Step 10: Commit**

```bash
git add apps/os_lms/os_lms/os_lms/ai/utils/realtime/
git commit -m "feat: realtime provider abstraction core (ABC, registry, config, mock)"
```

---

### Task 2: OpenAI Realtime adapter

Mints an ephemeral client secret via `POST /v1/realtime/client_secrets` and maps OpenAI transcript events to `TranscriptEvent`. SDK-free (`requests`), like the OpenAI audio adapter.

> Before coding, verify the request/response shape of `POST /v1/realtime/client_secrets`
> and the transcript event names against the current OpenAI Realtime docs
> (`developers.openai.com/.../guides/realtime`). The event names below are the
> documented ones as of the design date; the client_secret request body is the
> volatile part — keep it confined to `_session_body()`.

**Files:**
- Modify (replace stub): `apps/os_lms/os_lms/os_lms/ai/utils/realtime/providers/openai_realtime.py`
- Modify: `apps/os_lms/os_lms/os_lms/ai/utils/realtime/tests/test_realtime.py` (append a test class)

**Interfaces:**
- Consumes: `RealtimeProviderConfig`, `RealtimeSessionConfig`, `RealtimeSession`, `TranscriptEvent`, errors, `register_realtime` (Task 1).
- Produces: `OpenAIRealtimeProvider` registered as `"openai"`; module-level pure helpers `_parse_event(event: dict) -> TranscriptEvent | None` and `_session_body(cfg, config) -> dict` for unit testing without network.

- [ ] **Step 1: Write the failing tests (append to `test_realtime.py`)**

```python
from unittest.mock import patch

from os_lms.os_lms.ai.utils.realtime.providers.openai_realtime import (
	OpenAIRealtimeProvider,
	_parse_event,
	_session_body,
)


class TestOpenAIParseEvent(UnitTestCase):
	def test_user_transcript_completed(self):
		ev = _parse_event({
			"type": "conversation.item.input_audio_transcription.completed",
			"transcript": "Buongiorno",
		})
		self.assertEqual((ev.role, ev.text, ev.final), ("user", "Buongiorno", True))

	def test_assistant_transcript_done(self):
		ev = _parse_event({
			"type": "response.output_audio_transcript.done",
			"transcript": "Piacere di conoscerla",
		})
		self.assertEqual(ev.role, "assistant")
		self.assertTrue(ev.final)

	def test_delta_is_ignored(self):
		self.assertIsNone(_parse_event({
			"type": "response.output_audio_transcript.delta",
			"delta": "Pia",
		}))

	def test_unrelated_event_is_ignored(self):
		self.assertIsNone(_parse_event({"type": "response.created"}))


class TestOpenAISessionBody(UnitTestCase):
	def test_body_carries_persona_and_voice(self):
		cfg = _cfg()
		config = realtime.build_realtime_config("openai", _FakeSettings())
		body = _session_body(cfg, config)
		# instructions and voice must reach the provider; api key must not be here.
		self.assertIn("session", body)
		self.assertEqual(body["session"]["instructions"], "You are a recruiter.")
		self.assertEqual(body["session"]["audio"]["output"]["voice"], "marin")


class TestOpenAICreateSession(UnitTestCase):
	def test_create_session_mints_ephemeral_token(self):
		config = realtime.build_realtime_config("openai", _FakeSettings())
		provider = OpenAIRealtimeProvider(config)

		class _Resp:
			status_code = 200

			@staticmethod
			def json():
				return {"value": "ek_abc", "expires_at": 1234567890}

		with patch(
			"os_lms.os_lms.ai.utils.realtime.providers.openai_realtime.requests.post",
			return_value=_Resp(),
		) as mocked:
			session = provider.create_session(_cfg())

		self.assertEqual(session.transport, "webrtc")
		self.assertEqual(session.client_secret, "ek_abc")
		self.assertEqual(session.expires_at, 1234567890)
		self.assertTrue(session.connect_url.endswith("/realtime/calls"))
		# api key sent as Bearer header, never in the returned session.
		_, kwargs = mocked.call_args
		self.assertEqual(kwargs["headers"]["Authorization"], "Bearer sk-test")
		self.assertNotIn("sk-test", session.client_secret)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `bench --site lms.localhost run-tests --app os_lms --module os_lms.os_lms.ai.utils.realtime.tests.test_realtime`
Expected: FAIL — `ImportError: cannot import name 'OpenAIRealtimeProvider'` (the stub has no such symbol).

- [ ] **Step 3: Implement `openai_realtime.py`**

```python
"""OpenAI Realtime adapter (control plane only).

Mints an ephemeral client secret over the OpenAI HTTP API via `requests`
(SDK-free, same encapsulation rule as the OpenAI audio adapter). The audio
stream itself is WebRTC and is established by the client, never the backend.

- create_session -> POST {base_url}/realtime/client_secrets  (mint ek_... token)
- the client then POSTs its SDP offer to {base_url}/realtime/calls with the
  ephemeral token as Bearer.
- parse_transcript_event maps the two final-transcript events to a Turn.
"""
from __future__ import annotations

import requests

from ..config import RealtimeProviderConfig
from ..errors import (
	RealtimeError,
	RealtimeInvalidAuth,
	RealtimeRateLimit,
	RealtimeServerError,
	RealtimeTimeout,
)
from ..provider import (
	RealtimeProvider,
	RealtimeSession,
	RealtimeSessionConfig,
	TranscriptEvent,
)
from ..registry import register_realtime

_USER_EVENT = "conversation.item.input_audio_transcription.completed"
_ASSISTANT_EVENT = "response.output_audio_transcript.done"


@register_realtime("openai")
class OpenAIRealtimeProvider(RealtimeProvider):
	"""OpenAI Realtime over HTTP for token minting; WebRTC for the stream."""

	DEFAULT_BASE_URL = "https://api.openai.com/v1"
	DEFAULT_MODEL = "gpt-realtime-2"

	def __init__(self, config: RealtimeProviderConfig):
		self._config = config
		self._base_url = (config.base_url or self.DEFAULT_BASE_URL).rstrip("/")

	def create_session(self, cfg: RealtimeSessionConfig) -> RealtimeSession:
		if not self._config.api_key:
			raise RealtimeInvalidAuth("OpenAI api key is not configured", provider=self.name)
		url = f"{self._base_url}/realtime/client_secrets"
		headers = {
			"Authorization": f"Bearer {self._config.api_key}",
			"Content-Type": "application/json",
		}
		try:
			r = requests.post(
				url, headers=headers, json=_session_body(cfg, self._config), timeout=30.0
			)
		except requests.Timeout as e:
			raise RealtimeTimeout(str(e), provider=self.name, cause=e) from e
		except requests.RequestException as e:
			raise RealtimeServerError(str(e), provider=self.name, cause=e) from e

		self._check_status(r)
		payload = r.json()
		secret = payload.get("value") or payload.get("client_secret", {}).get("value", "")
		model = cfg.model or self._config.default_model or self.DEFAULT_MODEL
		return RealtimeSession(
			provider=self.name,
			model=model,
			transport="webrtc",
			client_secret=secret,
			connect_url=f"{self._base_url}/realtime/calls",
			expires_at=int(payload.get("expires_at", 0) or 0),
			voice=cfg.voice or self._config.voice or "marin",
			extra={"model": model},
		)

	def parse_transcript_event(self, event: dict) -> TranscriptEvent | None:
		return _parse_event(event)

	def health_check(self) -> bool:
		return bool(self._config.api_key)

	def _check_status(self, r: requests.Response) -> None:
		if 200 <= r.status_code < 300:
			return
		msg = _extract_error(r) or f"HTTP {r.status_code}"
		if r.status_code in (401, 403):
			raise RealtimeInvalidAuth(msg, provider=self.name)
		if r.status_code == 429:
			raise RealtimeRateLimit(msg, provider=self.name)
		if r.status_code >= 500:
			raise RealtimeServerError(msg, provider=self.name)
		raise RealtimeError(msg, provider=self.name)


def _session_body(cfg: RealtimeSessionConfig, config: RealtimeProviderConfig) -> dict:
	"""Build the client_secrets request body. The persona is `instructions`;
	input transcription is enabled so we get the candidate's text for Turns.

	NOTE: the exact field layout of the Realtime session object evolves — keep
	all provider-format coupling in this one helper.
	"""
	model = cfg.model or config.default_model or OpenAIRealtimeProvider.DEFAULT_MODEL
	return {
		"session": {
			"type": "realtime",
			"model": model,
			"instructions": cfg.instructions,
			"audio": {
				"input": {
					"transcription": {"model": "gpt-4o-transcribe", "language": cfg.input_language},
					"turn_detection": {"type": cfg.turn_detection},
				},
				"output": {"voice": cfg.voice or config.voice or "marin"},
			},
		}
	}


def _parse_event(event: dict) -> TranscriptEvent | None:
	etype = event.get("type")
	if etype == _USER_EVENT:
		return TranscriptEvent(role="user", text=event.get("transcript", "") or "", final=True)
	if etype == _ASSISTANT_EVENT:
		return TranscriptEvent(role="assistant", text=event.get("transcript", "") or "", final=True)
	return None


def _extract_error(r: requests.Response) -> str | None:
	try:
		data = r.json()
	except ValueError:
		return (r.text or "")[:200] or None
	if isinstance(data, dict):
		err = data.get("error")
		if isinstance(err, dict):
			return err.get("message") or err.get("type")
		if isinstance(err, str):
			return err
	return None
```

Then in `providers/__init__.py` ensure `from . import openai_realtime` is uncommented (it already imports it).

- [ ] **Step 4: Run tests to verify they pass**

Run: `bench --site lms.localhost run-tests --app os_lms --module os_lms.os_lms.ai.utils.realtime.tests.test_realtime`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/os_lms/os_lms/os_lms/ai/utils/realtime/providers/openai_realtime.py \
        apps/os_lms/os_lms/os_lms/ai/utils/realtime/tests/test_realtime.py
git commit -m "feat: OpenAI Realtime adapter (ephemeral token + transcript parsing)"
```

---

### Task 3: Gemini Live adapter

Mints an ephemeral auth token and returns a WebSocket transport descriptor with the resumption handle slot in `extra`. SDK-free (`requests`) against the `v1alpha` ephemeral-token REST endpoint.

> Verify against current Gemini Live docs (`ai.google.dev/.../live-api/ephemeral-tokens`).
> The token-mint REST shape is the volatile part — keep it in `_token_request()`.
> `system_instruction` is fixed at connect, so it is returned in `extra` for the
> client to send in its `BidiGenerateContentSetup`, not minted into the token.

**Files:**
- Modify (replace stub): `apps/os_lms/os_lms/os_lms/ai/utils/realtime/providers/gemini_live.py`
- Modify: `apps/os_lms/os_lms/os_lms/ai/utils/realtime/tests/test_realtime.py` (append)

**Interfaces:**
- Consumes: Task 1 contract.
- Produces: `GeminiLiveProvider` registered as `"gemini"`; pure helpers `_parse_event(event: dict) -> TranscriptEvent | None`, `_token_request(cfg, config) -> dict`.

- [ ] **Step 1: Write the failing tests (append)**

```python
from os_lms.os_lms.ai.utils.realtime.providers.gemini_live import (
	GeminiLiveProvider,
	_parse_event as _gemini_parse_event,
)


class TestGeminiParseEvent(UnitTestCase):
	def test_input_transcription(self):
		ev = _gemini_parse_event({
			"serverContent": {"inputTranscription": {"text": "Salve"}}
		})
		self.assertEqual((ev.role, ev.text, ev.final), ("user", "Salve", True))

	def test_output_transcription(self):
		ev = _gemini_parse_event({
			"serverContent": {"outputTranscription": {"text": "Benvenuto"}}
		})
		self.assertEqual(ev.role, "assistant")

	def test_other_frame_ignored(self):
		self.assertIsNone(_gemini_parse_event({"setupComplete": {}}))


class TestGeminiCreateSession(UnitTestCase):
	def test_create_session_returns_websocket_descriptor(self):
		config = realtime.build_realtime_config("gemini", _FakeSettings())
		provider = GeminiLiveProvider(config)

		class _Resp:
			status_code = 200

			@staticmethod
			def json():
				return {"name": "auth_tokens/abc", "expireTime": "2026-01-01T00:00:00Z"}

		with patch(
			"os_lms.os_lms.ai.utils.realtime.providers.gemini_live.requests.post",
			return_value=_Resp(),
		):
			session = provider.create_session(_cfg())

		self.assertEqual(session.transport, "websocket")
		self.assertTrue(session.client_secret)
		self.assertTrue(session.connect_url.startswith("wss://"))
		# Persona must be carried for the client's setup frame.
		self.assertEqual(session.extra["instructions"], "You are a recruiter.")
		# Resumption handle slot present (empty initially).
		self.assertIn("resumption_handle", session.extra)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `bench --site lms.localhost run-tests --app os_lms --module os_lms.os_lms.ai.utils.realtime.tests.test_realtime`
Expected: FAIL — `ImportError` for `GeminiLiveProvider`.

- [ ] **Step 3: Implement `gemini_live.py`**

```python
"""Gemini Live adapter (control plane only).

Mints an ephemeral auth token (v1alpha) via `requests` and returns a WebSocket
transport descriptor. The persona (`system_instruction`) is fixed at connect,
so it is handed to the client in `extra` to include in its
BidiGenerateContentSetup. Session resumption is the client's responsibility;
the `resumption_handle` slot is provided so the client can persist/restore it.

SDK-free, same encapsulation rule as the audio adapters.
"""
from __future__ import annotations

import requests

from ..config import RealtimeProviderConfig
from ..errors import (
	RealtimeError,
	RealtimeInvalidAuth,
	RealtimeRateLimit,
	RealtimeServerError,
	RealtimeTimeout,
)
from ..provider import (
	RealtimeProvider,
	RealtimeSession,
	RealtimeSessionConfig,
	TranscriptEvent,
)
from ..registry import register_realtime

_BASE = "https://generativelanguage.googleapis.com/v1alpha"
_WS_URL = (
	"wss://generativelanguage.googleapis.com/ws/"
	"google.ai.generativelanguage.v1alpha.GenerativeService.BidiGenerateContent"
)


@register_realtime("gemini")
class GeminiLiveProvider(RealtimeProvider):
	"""Gemini Live over WebSocket; ephemeral token minted over REST."""

	DEFAULT_MODEL = "gemini-live-2.5-flash-native-audio"

	def __init__(self, config: RealtimeProviderConfig):
		self._config = config

	def create_session(self, cfg: RealtimeSessionConfig) -> RealtimeSession:
		if not self._config.api_key:
			raise RealtimeInvalidAuth("Gemini api key is not configured", provider=self.name)
		url = f"{_BASE}/auth_tokens?key={self._config.api_key}"
		try:
			r = requests.post(
				url,
				headers={"Content-Type": "application/json"},
				json=_token_request(cfg, self._config),
				timeout=30.0,
			)
		except requests.Timeout as e:
			raise RealtimeTimeout(str(e), provider=self.name, cause=e) from e
		except requests.RequestException as e:
			raise RealtimeServerError(str(e), provider=self.name, cause=e) from e

		self._check_status(r)
		payload = r.json()
		token = payload.get("name", "") or payload.get("token", "")
		model = cfg.model or self._config.default_model or self.DEFAULT_MODEL
		return RealtimeSession(
			provider=self.name,
			model=model,
			transport="websocket",
			client_secret=token,
			connect_url=_WS_URL,
			expires_at=0,  # Gemini returns RFC3339 expireTime; the client tracks it.
			voice=cfg.voice or self._config.voice or "Puck",
			extra={
				"model": model,
				"instructions": cfg.instructions,
				"voice": cfg.voice or self._config.voice or "Puck",
				"input_language": cfg.input_language,
				"resumption_handle": "",
				"expire_time": payload.get("expireTime", ""),
			},
		)

	def parse_transcript_event(self, event: dict) -> TranscriptEvent | None:
		return _parse_event(event)

	def health_check(self) -> bool:
		return bool(self._config.api_key)

	def _check_status(self, r: requests.Response) -> None:
		if 200 <= r.status_code < 300:
			return
		msg = _extract_error(r) or f"HTTP {r.status_code}"
		if r.status_code in (401, 403):
			raise RealtimeInvalidAuth(msg, provider=self.name)
		if r.status_code == 429:
			raise RealtimeRateLimit(msg, provider=self.name)
		if r.status_code >= 500:
			raise RealtimeServerError(msg, provider=self.name)
		raise RealtimeError(msg, provider=self.name)


def _token_request(cfg: RealtimeSessionConfig, config: RealtimeProviderConfig) -> dict:
	"""Build the ephemeral-token request. Keep all provider-format coupling here."""
	return {
		"uses": 1,
		"liveConnectConstraints": {
			"model": cfg.model or config.default_model or GeminiLiveProvider.DEFAULT_MODEL,
		},
	}


def _parse_event(event: dict) -> TranscriptEvent | None:
	content = event.get("serverContent") or {}
	itx = content.get("inputTranscription") or {}
	if itx.get("text"):
		return TranscriptEvent(role="user", text=itx["text"], final=True)
	otx = content.get("outputTranscription") or {}
	if otx.get("text"):
		return TranscriptEvent(role="assistant", text=otx["text"], final=True)
	return None


def _extract_error(r: requests.Response) -> str | None:
	try:
		data = r.json()
	except ValueError:
		return (r.text or "")[:200] or None
	if isinstance(data, dict):
		err = data.get("error")
		if isinstance(err, dict):
			return err.get("message") or err.get("status")
	return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `bench --site lms.localhost run-tests --app os_lms --module os_lms.os_lms.ai.utils.realtime.tests.test_realtime`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/os_lms/os_lms/os_lms/ai/utils/realtime/providers/gemini_live.py \
        apps/os_lms/os_lms/os_lms/ai/utils/realtime/tests/test_realtime.py
git commit -m "feat: Gemini Live adapter (ephemeral token + websocket descriptor)"
```

---

### Task 4: Extend the encapsulation architectural test

Admit `utils/realtime/providers/` as an allowed location for provider SDK imports, so a future SDK-based realtime adapter won't trip the test (and to document the boundary).

**Files:**
- Modify: `apps/os_lms/os_lms/os_lms/ai/utils/llm/tests/test_provider_encapsulation.py:38-44` (the `_provider_dirs` function)

**Interfaces:** none (test-only change).

- [ ] **Step 1: Update `_provider_dirs` to include realtime**

Replace the function body:

```python
def _provider_dirs(app_root: Path) -> list[Path]:
	base = app_root / "os_lms" / "ai" / "utils"
	return [
		base / "llm" / "providers",
		base / "stt" / "providers",  # may not exist yet (fase 2)
		base / "tts" / "providers",  # may not exist yet (fase 2)
		base / "audio" / "providers",
		base / "realtime" / "providers",
	]
```

> The `audio/providers` entry is added too: the audio adapters are SDK-free
> today, but listing the dir keeps the rule consistent and future-proof.

- [ ] **Step 2: Run the encapsulation test**

Run: `bench --site lms.localhost run-tests --app os_lms --module os_lms.os_lms.ai.utils.llm.tests.test_provider_encapsulation`
Expected: PASS (no offenders; the realtime adapters import only `requests`).

- [ ] **Step 3: Commit**

```bash
git add apps/os_lms/os_lms/os_lms/ai/utils/llm/tests/test_provider_encapsulation.py
git commit -m "test: allow provider SDKs under utils/realtime/providers and utils/audio/providers"
```

---

### Task 5: Settings — OsLmsSettings fields, loader wiring, and LMSA Settings doctype

Add the Realtime/Voice settings so `build_realtime_config` reads real values, and expose them on the Single doctype for admins.

**Files:**
- Modify: `apps/os_lms/os_lms/os_lms/ai/utils/oslms_settings.py:30-38` (append realtime fields to the dataclass)
- Modify: `apps/os_lms/os_lms/os_lms/ai/utils/llm/__init__.py:163-196` (extend the `OsLmsSettings(...)` constructor call in `_load_settings`)
- Modify: `apps/os_lms/os_lms/os_lms/doctype/lmsa_settings/lmsa_settings.json` (add fields)
- Modify: `apps/os_lms/os_lms/os_lms/ai/utils/realtime/tests/test_realtime.py` (append a loader test)

**Interfaces:**
- Produces (on `OsLmsSettings`): `realtime_enabled: bool`, `realtime_provider: str`, `realtime_model: str`, `realtime_voice: str`, `turn_detection: str`, `realtime_max_session_seconds: int`.

- [ ] **Step 1: Write the failing test (append)**

```python
class TestRealtimeSettingsDefaults(UnitTestCase):
	def test_oslmssettings_has_realtime_fields_with_defaults(self):
		from os_lms.os_lms.ai.utils.oslms_settings import OsLmsSettings

		s = OsLmsSettings(
			enabled=False,
			embedding_model="x",
			chunk_size=1,
			chunk_overlap=1,
			top_k=1,
			llm_model="x",
			openai_key="",
		)
		self.assertFalse(s.realtime_enabled)
		self.assertEqual(s.realtime_provider, "openai")
		self.assertEqual(s.turn_detection, "server_vad")
		self.assertEqual(s.realtime_max_session_seconds, 300)
```

- [ ] **Step 2: Run to verify it fails**

Run: `bench --site lms.localhost run-tests --app os_lms --module os_lms.os_lms.ai.utils.realtime.tests.test_realtime`
Expected: FAIL — `AttributeError: ... has no attribute 'realtime_enabled'`.

- [ ] **Step 3: Add fields to the dataclass** (`oslms_settings.py`, after the audio block)

```python
	# Realtime / voice (speech-to-speech) — additive, all defaulted.
	realtime_enabled: bool = False
	realtime_provider: str = "openai"
	realtime_model: str = ""
	realtime_voice: str = ""
	turn_detection: str = "server_vad"
	realtime_max_session_seconds: int = 300
```

- [ ] **Step 4: Wire the loader** — in `llm/__init__.py` `_load_settings`, add to the `OsLmsSettings(...)` call (after the audio kwargs, before the closing `)`):

```python
		# realtime / voice — additive
		realtime_enabled=bool(getattr(doc, "realtime_enabled", 0)),
		realtime_provider=getattr(doc, "realtime_provider", "") or "openai",
		realtime_model=getattr(doc, "realtime_model", "") or "",
		realtime_voice=getattr(doc, "realtime_voice", "") or "",
		turn_detection=getattr(doc, "turn_detection", "") or "server_vad",
		realtime_max_session_seconds=int(getattr(doc, "realtime_max_session_seconds", 0) or 300),
```

- [ ] **Step 5: Add doctype fields** — in `lmsa_settings.json`, add a Section Break + fields to `field_order` and `fields`. Insert these objects into the `fields` array (after the TTS fields) and the matching fieldnames into `field_order`:

```json
		{"fieldname": "realtime_section", "fieldtype": "Section Break", "label": "Realtime / Voice"},
		{"fieldname": "realtime_enabled", "fieldtype": "Check", "label": "Enable Realtime Voice", "default": "0"},
		{"fieldname": "realtime_provider", "fieldtype": "Select", "label": "Realtime Provider", "options": "openai\ngemini", "default": "openai", "depends_on": "realtime_enabled"},
		{"fieldname": "realtime_model", "fieldtype": "Data", "label": "Realtime Model", "description": "Blank = provider default (OpenAI: gpt-realtime-2)", "depends_on": "realtime_enabled"},
		{"fieldname": "realtime_voice", "fieldtype": "Data", "label": "Realtime Voice", "description": "Blank = provider default (OpenAI: marin)", "depends_on": "realtime_enabled"},
		{"fieldname": "turn_detection", "fieldtype": "Select", "label": "Turn Detection", "options": "server_vad\nsemantic_vad", "default": "server_vad", "depends_on": "realtime_enabled"},
		{"fieldname": "realtime_max_session_seconds", "fieldtype": "Int", "label": "Max Session Seconds", "default": "300", "depends_on": "realtime_enabled"}
```

> Add each new `fieldname` to the `field_order` array in the same order. Keep the
> file valid JSON (commas). Verify with: `python3 -m json.tool apps/os_lms/os_lms/os_lms/doctype/lmsa_settings/lmsa_settings.json > /dev/null && echo OK`.

- [ ] **Step 6: Migrate and run the loader test**

Run: `bench --site lms.localhost migrate && bench --site lms.localhost run-tests --app os_lms --module os_lms.os_lms.ai.utils.realtime.tests.test_realtime`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add apps/os_lms/os_lms/os_lms/ai/utils/oslms_settings.py \
        apps/os_lms/os_lms/os_lms/ai/utils/llm/__init__.py \
        apps/os_lms/os_lms/os_lms/doctype/lmsa_settings/lmsa_settings.json \
        apps/os_lms/os_lms/os_lms/ai/utils/realtime/tests/test_realtime.py
git commit -m "feat: realtime/voice settings (OsLmsSettings + LMSA Settings doctype)"
```

---

### Task 6: Doctype audit fields (Scenario voice override + Session audit)

Add the additive per-scenario voice override and the per-session audit fields the feature layer writes.

**Files:**
- Modify: `apps/os_lms/os_lms/os_lms/doctype/lmsa_simulation_scenario/lmsa_simulation_scenario.json`
- Modify: `apps/os_lms/os_lms/os_lms/doctype/lmsa_simulation_session/lmsa_simulation_session.json`

**Interfaces:**
- Produces (Scenario): `voice: Data`, `voice_instructions: Small Text`.
- Produces (Session): `realtime_provider_used: Data`, `realtime_model_used: Data`, `voice_used: Data`, `session_seconds: Int`.

- [ ] **Step 1: Add Scenario fields** — insert into `fields` (and `field_order`) of the scenario JSON, near `provider_override`:

```json
		{"fieldname": "voice", "fieldtype": "Data", "label": "Voice Override", "description": "Realtime voice for this scenario; blank = settings default", "depends_on": "eval:['voice','both'].includes(doc.modality)"},
		{"fieldname": "voice_instructions", "fieldtype": "Small Text", "label": "Voice / Acting Instructions", "description": "Delivery style for the persona (tone, pacing) injected into the realtime instructions", "depends_on": "eval:['voice','both'].includes(doc.modality)"}
```

- [ ] **Step 2: Add Session fields** — insert into `fields` (and `field_order`) of the session JSON, near `chat_provider_used`:

```json
		{"fieldname": "realtime_provider_used", "fieldtype": "Data", "label": "Realtime Provider Used", "read_only": 1},
		{"fieldname": "realtime_model_used", "fieldtype": "Data", "label": "Realtime Model Used", "read_only": 1},
		{"fieldname": "voice_used", "fieldtype": "Data", "label": "Voice Used", "read_only": 1},
		{"fieldname": "session_seconds", "fieldtype": "Int", "label": "Session Seconds", "read_only": 1, "default": "0"}
```

- [ ] **Step 3: Validate JSON and migrate**

Run:
```bash
python3 -m json.tool apps/os_lms/os_lms/os_lms/doctype/lmsa_simulation_scenario/lmsa_simulation_scenario.json > /dev/null && \
python3 -m json.tool apps/os_lms/os_lms/os_lms/doctype/lmsa_simulation_session/lmsa_simulation_session.json > /dev/null && echo OK
bench --site lms.localhost migrate
```
Expected: `OK` then a clean migrate.

- [ ] **Step 4: Commit**

```bash
git add apps/os_lms/os_lms/os_lms/doctype/lmsa_simulation_scenario/lmsa_simulation_scenario.json \
        apps/os_lms/os_lms/os_lms/doctype/lmsa_simulation_session/lmsa_simulation_session.json
git commit -m "feat: realtime audit fields on Scenario (voice) and Session"
```

---

### Task 7: Control-plane feature layer (`ai/realtime/api.py`) + orchestrator voice support

The whitelisted endpoints. Reuses `SessionOrchestrator` for persona generation, turn persistence, and debrief enqueue. Adds two orchestrator methods so the HTTP shell stays thin.

**Files:**
- Create: `apps/os_lms/os_lms/os_lms/ai/realtime/__init__.py`
- Create: `apps/os_lms/os_lms/os_lms/ai/realtime/api.py`
- Modify: `apps/os_lms/os_lms/os_lms/ai/simulations/orchestrator.py` (add `start_voice_session`, `persist_voice_turn`, helper `_enforce_max_duration`)
- Create: `apps/os_lms/os_lms/os_lms/ai/realtime/tests/__init__.py`
- Create: `apps/os_lms/os_lms/os_lms/ai/realtime/tests/test_realtime_api.py`

**Interfaces:**
- Consumes: `resolve_realtime_provider`, `build_realtime_config`, `RealtimeSessionConfig` (Task 1); `SessionOrchestrator._persist_turn`, `_generate_variant`, `_resolve_published_scenario`, `load_session`, `pseudonymize_session_id`, `build_role_play_system_prompt`.
- Produces (whitelisted):
  - `create_voice_session(scenario_id: str) -> dict` → `{session_id, transport, connect_url, client_secret, voice, model, expires_at, max_seconds, extra}`
  - `persist_transcript_turn(session_id: str, role: str, text: str) -> dict` → `{turn: <name>}`
  - `end_voice_session(session_id: str, reason: str = "completed", seconds: int = 0) -> dict`
- Produces (orchestrator): `start_voice_session(*, scenario_id, provider, voice, instructions, model) -> frappe._dict(session=<name>)`; `persist_voice_turn(*, session_id, role, text) -> frappe._dict(turn=<name>)`.

- [ ] **Step 1: Write the failing test** (`test_realtime_api.py`) — reuses the shared simulation fixtures (`simulations/tests/_fixtures.py`) and mirrors `simulations/tests/test_api.py` (student + enrollment + `set_user`, `_generate_variant` stubbed so no LLM is called). `realtime_provider="mock"` so no network.

```python
"""Endpoint tests for the realtime (voice) feature layer.

Call the whitelisted Python entry points directly under the student identity,
mirroring simulations/tests/test_api.py. realtime_provider="mock" so no
network is involved; _generate_variant is stubbed to a canned persona.
"""
from __future__ import annotations

from unittest.mock import patch

import frappe
from frappe.tests import UnitTestCase

from os_lms.os_lms.ai.realtime import api as rt_api
from os_lms.os_lms.ai.simulations.orchestrator import SessionOrchestrator
from os_lms.os_lms.ai.simulations.tests import _fixtures as F


def _stub_generate_variant(self, scenario, seed, provider):
	return F.CANNED_VARIANT


def _make_student(email: str) -> str:
	if frappe.db.exists("User", email):
		frappe.delete_doc("User", email, force=True, ignore_permissions=True)
	user = frappe.new_doc("User")
	user.email = email
	user.first_name = "Voice"
	user.send_welcome_email = 0
	user.enabled = 1
	user.append("roles", {"role": "LMS Student"})
	user.insert(ignore_permissions=True)
	return user.name


def _enroll(user: str, course: str) -> None:
	if not frappe.db.get_value("LMS Enrollment", {"member": user, "course": course}):
		enr = frappe.new_doc("LMS Enrollment")
		enr.member = user
		enr.course = course
		enr.insert(ignore_permissions=True)


class TestRealtimeApi(UnitTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		F.cleanup_sessions_and_turns()
		F.enable_mock_provider()  # sets simulations_enabled + chat/debrief = mock
		s = frappe.get_single("LMSA Settings")
		s.realtime_enabled = 1
		s.realtime_provider = "mock"
		s.realtime_max_session_seconds = 300
		s.save(ignore_permissions=True)
		cls.scenario = F.make_published_scenario(name="Voice Test Scenario")
		cls.scenario.modality = "voice"
		cls.scenario.save(ignore_permissions=True)
		cls.student = _make_student("voice-student@example.com")
		_enroll(cls.student, cls.scenario.lms_course)
		frappe.db.commit()

	def setUp(self):
		frappe.set_user(self.student)

	def tearDown(self):
		frappe.set_user("Administrator")

	@patch.object(SessionOrchestrator, "_generate_variant", _stub_generate_variant)
	def test_create_persist_end_roundtrip(self):
		out = rt_api.create_voice_session(scenario_id=self.scenario.name)
		self.assertEqual(out["transport"], "mock")
		self.assertTrue(out["client_secret"].startswith("mock-secret-"))
		self.assertEqual(out["max_seconds"], 300)

		sid = out["session_id"]
		# Audit fields recorded.
		self.assertEqual(
			frappe.db.get_value("LMSA Simulation Session", sid, "realtime_provider_used"), "mock"
		)

		rt_api.persist_transcript_turn(session_id=sid, role="user", text="Salve")
		rt_api.persist_transcript_turn(session_id=sid, role="assistant", text="Benvenuto")

		ended = rt_api.end_voice_session(session_id=sid, reason="completed", seconds=42)
		self.assertEqual(ended["status"], "Completed")
		self.assertEqual(
			frappe.db.get_value("LMSA Simulation Session", sid, "session_seconds"), 42
		)
		turns = frappe.get_all(
			"LMSA Simulation Turn", filters={"session": sid}, fields=["role", "text_content"]
		)
		self.assertEqual({t["role"] for t in turns}, {"user", "assistant"})
```

> `F.CANNED_VARIANT`, `make_published_scenario`, `enable_mock_provider`,
> `cleanup_sessions_and_turns` already exist in `_fixtures.py` — reuse them, do
> not redefine. The student gets `LMS Student` + enrollment so
> `_resolve_published_scenario` grants access (the student is neither moderator
> nor instructor, exercising the real student gate).

- [ ] **Step 2: Run to verify it fails**

Run: `bench --site lms.localhost run-tests --app os_lms --module os_lms.os_lms.ai.realtime.tests.test_realtime_api`
Expected: FAIL — `ModuleNotFoundError: os_lms.os_lms.ai.realtime`.

- [ ] **Step 3: Add orchestrator methods** — in `orchestrator.py`, add to `SessionOrchestrator`:

```python
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
```

> `start_voice_session` reuses `_resolve_provider`, `_generate_variant`,
> `_persona_to_dict`, `_new_seed`, `_scenario_difficulty`, `SCENARIO_GEN_VERSION`,
> `ROLE_PLAY_VERSION`, `detect_injection`, `TERMINAL_STATUSES`, `EVENT_TURN_COMPLETE`
> — all already imported/defined in `orchestrator.py`.

- [ ] **Step 4: Implement `ai/realtime/__init__.py`** (empty) **and `ai/realtime/api.py`**

```python
"""Whitelisted REST endpoints for realtime (voice) simulations.

URL prefix: /api/method/os_lms.os_lms.ai.realtime.api.<name>

Thin control-plane shell: validate, gate (permissions + quota), delegate to
SessionOrchestrator, mint an ephemeral provider token. NO audio passes through
here — the client streams directly to the provider with the ephemeral token.
"""
from __future__ import annotations

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
	if session.student != frappe.session.user:
		frappe.throw(_("Only the session owner can end the session."), frappe.PermissionError)

	if seconds:
		frappe.db.set_value(
			"LMSA Simulation Session", session.name, "session_seconds", int(seconds)
		)
	return dict(_service().end_session(session_id=session.name, reason=reason))


def _throw(reason: str) -> None:
	frappe.log_error(title="LMSA realtime error")
	frappe.throw(_("Realtime error: {0}.").format(reason))
```

> `end_voice_session` reuses the existing `SessionOrchestrator.end_session`,
> which already sets status, submits, and enqueues `generate_debrief` — the SAME
> text debrief pipeline as chat. No new debrief code.

- [ ] **Step 5: Run the test to verify it passes**

Run: `bench --site lms.localhost run-tests --app os_lms --module os_lms.os_lms.ai.realtime.tests.test_realtime_api`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add apps/os_lms/os_lms/os_lms/ai/realtime/ apps/os_lms/os_lms/os_lms/ai/simulations/orchestrator.py
git commit -m "feat: realtime voice control-plane endpoints + orchestrator voice methods"
```

---

### Task 8: Frontend transport layer (interface + WebRTC + WebSocket strategies)

The client-side strategy that isolates the OpenAI/Gemini divergence. Plain JS modules, framework-free, so they are unit-testable with a fake `RTCPeerConnection`/`WebSocket`.

**Files:**
- Create: `frontend/src/oslms/composables/realtime/RealtimeTransport.js`
- Create: `frontend/src/oslms/composables/realtime/WebrtcTransport.js`
- Create: `frontend/src/oslms/composables/realtime/WebsocketTransport.js`
- Create: `frontend/src/oslms/composables/realtime/createTransport.js`

**Interfaces:**
- Produces: `createTransport(descriptor) -> RealtimeTransport` where `descriptor` is the `create_voice_session` response. Each transport exposes:
  - `async connect(mediaStream)` — opens the direct connection, begins streaming mic audio, plays remote audio.
  - `onTranscript(cb)` — `cb({role, text})` for each final transcript turn.
  - `onState(cb)` — `cb(state)` where state ∈ `"connecting"|"connected"|"closed"|"error"`.
  - `close()` — tears down.

- [ ] **Step 1: Write `RealtimeTransport.js` (base class / contract)**

```javascript
// Common contract for realtime transports. Subclasses implement connect()
// and close(); the base wires the callback plumbing so the composable is
// transport-agnostic.
export class RealtimeTransport {
	constructor(descriptor) {
		this.descriptor = descriptor
		this._transcriptCbs = []
		this._stateCbs = []
	}

	onTranscript(cb) {
		this._transcriptCbs.push(cb)
	}

	onState(cb) {
		this._stateCbs.push(cb)
	}

	_emitTranscript(role, text) {
		if (!text) return
		for (const cb of this._transcriptCbs) cb({ role, text })
	}

	_emitState(state) {
		for (const cb of this._stateCbs) cb(state)
	}

	// eslint-disable-next-line no-unused-vars
	async connect(mediaStream) {
		throw new Error('connect() not implemented')
	}

	close() {
		throw new Error('close() not implemented')
	}
}
```

- [ ] **Step 2: Write `WebrtcTransport.js` (OpenAI)**

```javascript
import { RealtimeTransport } from './RealtimeTransport'

// OpenAI Realtime over WebRTC. The ephemeral client_secret authorizes the SDP
// exchange; events arrive on the `oai-events` data channel as JSON. Final
// transcript events are mapped to {role, text}.
const USER_EVENT = 'conversation.item.input_audio_transcription.completed'
const ASSISTANT_EVENT = 'response.output_audio_transcript.done'

export class WebrtcTransport extends RealtimeTransport {
	async connect(mediaStream) {
		this._emitState('connecting')
		const pc = new RTCPeerConnection()
		this._pc = pc

		// Play remote audio.
		this._audioEl = new Audio()
		this._audioEl.autoplay = true
		pc.ontrack = (e) => {
			this._audioEl.srcObject = e.streams[0]
		}

		// Send mic.
		for (const track of mediaStream.getAudioTracks()) {
			pc.addTrack(track, mediaStream)
		}

		// Events channel.
		const dc = pc.createDataChannel('oai-events')
		this._dc = dc
		dc.onmessage = (e) => this._onEvent(e.data)

		pc.onconnectionstatechange = () => {
			if (pc.connectionState === 'connected') this._emitState('connected')
			if (['failed', 'disconnected'].includes(pc.connectionState)) this._emitState('error')
			if (pc.connectionState === 'closed') this._emitState('closed')
		}

		const offer = await pc.createOffer()
		await pc.setLocalDescription(offer)

		const url = `${this.descriptor.connect_url}?model=${encodeURIComponent(this.descriptor.model)}`
		const resp = await fetch(url, {
			method: 'POST',
			body: offer.sdp,
			headers: {
				Authorization: `Bearer ${this.descriptor.client_secret}`,
				'Content-Type': 'application/sdp',
			},
		})
		const answer = { type: 'answer', sdp: await resp.text() }
		await pc.setRemoteDescription(answer)
	}

	_onEvent(raw) {
		let ev
		try {
			ev = JSON.parse(raw)
		} catch {
			return
		}
		if (ev.type === USER_EVENT) this._emitTranscript('user', ev.transcript || '')
		else if (ev.type === ASSISTANT_EVENT) this._emitTranscript('assistant', ev.transcript || '')
	}

	close() {
		this._dc?.close()
		this._pc?.close()
		if (this._audioEl) this._audioEl.srcObject = null
		this._emitState('closed')
	}
}
```

- [ ] **Step 3: Write `WebsocketTransport.js` (Gemini)**

```javascript
import { RealtimeTransport } from './RealtimeTransport'

// Gemini Live over WebSocket (BidiGenerateContent). The ephemeral token
// authorizes the connection; the first frame is the setup (persona + voice +
// transcription). Final transcript frames map to {role, text}. Session
// resumption is handled by persisting the handle from SessionResumptionUpdate.
export class WebsocketTransport extends RealtimeTransport {
	async connect(mediaStream) {
		this._emitState('connecting')
		const { connect_url, client_secret, extra } = this.descriptor
		const ws = new WebSocket(`${connect_url}?access_token=${encodeURIComponent(client_secret)}`)
		this._ws = ws
		this._mediaStream = mediaStream

		ws.onopen = () => {
			ws.send(
				JSON.stringify({
					setup: {
						model: extra.model,
						systemInstruction: { parts: [{ text: extra.instructions }] },
						generationConfig: {
							responseModalities: ['AUDIO'],
							speechConfig: {
								voiceConfig: { prebuiltVoiceConfig: { voiceName: extra.voice } },
							},
						},
						inputAudioTranscription: {},
						outputAudioTranscription: {},
						...(extra.resumption_handle
							? { sessionResumption: { handle: extra.resumption_handle } }
							: { sessionResumption: {} }),
					},
				}),
			)
			this._emitState('connected')
			this._startMicPump()
		}
		ws.onmessage = (e) => this._onFrame(e.data)
		ws.onerror = () => this._emitState('error')
		ws.onclose = () => this._emitState('closed')
	}

	async _onFrame(data) {
		const text = typeof data === 'string' ? data : await data.text()
		let frame
		try {
			frame = JSON.parse(text)
		} catch {
			return
		}
		const sc = frame.serverContent || {}
		if (sc.inputTranscription?.text) this._emitTranscript('user', sc.inputTranscription.text)
		if (sc.outputTranscription?.text) this._emitTranscript('assistant', sc.outputTranscription.text)
		if (frame.sessionResumptionUpdate?.newHandle) {
			this.descriptor.extra.resumption_handle = frame.sessionResumptionUpdate.newHandle
		}
		// NOTE: audio playback of sc.modelTurn parts (PCM 24kHz) is wired in the
		// VoiceSession component's audio worklet; omitted here to keep the
		// transport focused on signaling + transcripts.
	}

	_startMicPump() {
		// PCM 16kHz capture + realtimeInput frames. Implemented with an
		// AudioWorklet in VoiceSession.vue; the transport exposes sendAudio().
	}

	sendAudio(base64Pcm) {
		this._ws?.send(JSON.stringify({ realtimeInput: { audio: { data: base64Pcm, mimeType: 'audio/pcm;rate=16000' } } }))
	}

	close() {
		this._ws?.close()
		this._emitState('closed')
	}
}
```

> The Gemini PCM capture/playback (AudioWorklet) is the genuinely hard part and
> is intentionally deferred to the component layer; OpenAI WebRTC handles
> mic/speaker natively. This matches the spec: OpenAI is the lower-risk default;
> Gemini is behind a flag.

- [ ] **Step 4: Write `createTransport.js` (factory)**

```javascript
import { WebrtcTransport } from './WebrtcTransport'
import { WebsocketTransport } from './WebsocketTransport'

// Pick a transport strategy from the backend descriptor. The backend already
// decided the provider; the client only honors `transport`.
export function createTransport(descriptor) {
	switch (descriptor.transport) {
		case 'webrtc':
			return new WebrtcTransport(descriptor)
		case 'websocket':
			return new WebsocketTransport(descriptor)
		default:
			throw new Error(`Unsupported realtime transport: ${descriptor.transport}`)
	}
}
```

- [ ] **Step 5: Manual verification (no JS unit runner in this repo)**

Run: `cd frontend && yarn build`
Expected: build succeeds (no syntax/import errors). The behavioral verification happens in Task 9 against the running app with `realtime_provider="mock"` for state plumbing and against OpenAI for the real audio path.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/oslms/composables/realtime/
git commit -m "feat: realtime web transports (WebRTC for OpenAI, WebSocket for Gemini)"
```

---

### Task 9: Frontend composable + VoiceSession component

The Vue layer the user interacts with: requests a session, drives the transport, relays transcripts to Frappe, enforces the client-side duration timer, and renders live state.

**Files:**
- Create: `frontend/src/oslms/composables/useRealtimeSession.js`
- Create: `frontend/src/oslms/components/simulations/VoiceSession.vue`
- Modify: the simulation start page/component that currently launches a chat session, to branch to `VoiceSession.vue` when `modality === 'voice'` (find it: `grep -rn "start_session" frontend/src` and follow the simulation entry component).

**Interfaces:**
- Consumes: `createTransport` (Task 8); backend endpoints `create_voice_session`, `persist_transcript_turn`, `end_voice_session` (Task 7).
- Produces: `useRealtimeSession()` returning `{ state, transcript, start(scenarioId), stop(), remainingSeconds }`.

- [ ] **Step 1: Write `useRealtimeSession.js`**

```javascript
import { ref } from 'vue'
import { createResource } from 'frappe-ui'
import { createTransport } from './realtime/createTransport'

// Orchestrates a voice session lifecycle from the browser:
//   create_voice_session -> getUserMedia -> transport.connect ->
//   relay final transcripts -> end_voice_session.
// Audio never touches Frappe; only control calls + transcript text do.
export function useRealtimeSession() {
	const state = ref('idle') // idle | connecting | connected | closed | error
	const transcript = ref([]) // [{ role, text }]
	const remainingSeconds = ref(0)

	let transport = null
	let sessionId = null
	let mediaStream = null
	let timer = null
	let startedAt = 0

	async function start(scenarioId) {
		state.value = 'connecting'
		const res = await createResource({
			url: 'os_lms.os_lms.ai.realtime.api.create_voice_session',
			params: { scenario_id: scenarioId },
		}).fetch()

		sessionId = res.session_id
		remainingSeconds.value = res.max_seconds
		startedAt = Date.now()

		mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true })
		transport = createTransport(res)
		transport.onState((s) => {
			state.value = s
		})
		transport.onTranscript(({ role, text }) => {
			transcript.value.push({ role, text })
			relayTurn(role, text)
		})
		await transport.connect(mediaStream)
		startTimer(res.max_seconds)
	}

	function relayTurn(role, text) {
		createResource({
			url: 'os_lms.os_lms.ai.realtime.api.persist_transcript_turn',
			params: { session_id: sessionId, role, text },
		})
			.fetch()
			.catch(() => {
				// Best-effort relay: a dropped transcript must not kill the call.
			})
	}

	function startTimer(maxSeconds) {
		stopTimer()
		timer = setInterval(() => {
			const elapsed = Math.floor((Date.now() - startedAt) / 1000)
			remainingSeconds.value = Math.max(0, maxSeconds - elapsed)
			if (remainingSeconds.value <= 0) stop('completed')
		}, 1000)
	}

	function stopTimer() {
		if (timer) clearInterval(timer)
		timer = null
	}

	async function stop(reason = 'completed') {
		stopTimer()
		const seconds = startedAt ? Math.floor((Date.now() - startedAt) / 1000) : 0
		try {
			transport?.close()
			mediaStream?.getTracks().forEach((t) => t.stop())
		} finally {
			if (sessionId) {
				await createResource({
					url: 'os_lms.os_lms.ai.realtime.api.end_voice_session',
					params: { session_id: sessionId, reason, seconds },
				})
					.fetch()
					.catch(() => {})
			}
			state.value = 'closed'
		}
	}

	return { state, transcript, remainingSeconds, start, stop }
}
```

- [ ] **Step 2: Write `VoiceSession.vue`**

```vue
<template>
	<div class="flex flex-col gap-4 p-4">
		<div class="flex items-center justify-between">
			<span class="text-sm" :class="stateClass">{{ stateLabel }}</span>
			<span v-if="state === 'connected'" class="font-mono text-sm">
				{{ formattedRemaining }}
			</span>
		</div>

		<div ref="scroller" class="flex flex-col gap-2 overflow-y-auto" style="max-height: 50vh">
			<div
				v-for="(turn, i) in transcript"
				:key="i"
				class="rounded-md px-3 py-2 text-sm"
				:class="turn.role === 'user' ? 'self-end bg-gray-100' : 'self-start bg-blue-50'"
			>
				{{ turn.text }}
			</div>
		</div>

		<div class="flex gap-2">
			<Button v-if="state === 'idle'" variant="solid" @click="onStart">
				{{ __('Start voice session') }}
			</Button>
			<Button
				v-else-if="['connecting', 'connected'].includes(state)"
				theme="red"
				variant="solid"
				@click="onStop"
			>
				{{ __('End session') }}
			</Button>
		</div>
	</div>
</template>

<script setup>
import { computed, ref, watch, nextTick } from 'vue'
import { Button } from 'frappe-ui'
import { useRealtimeSession } from '../../composables/useRealtimeSession'

const props = defineProps({ scenarioId: { type: String, required: true } })
const emit = defineEmits(['ended'])

const { state, transcript, remainingSeconds, start, stop } = useRealtimeSession()
const scroller = ref(null)

const stateLabel = computed(
	() =>
		({
			idle: __('Ready'),
			connecting: __('Connecting…'),
			connected: __('Live'),
			closed: __('Ended'),
			error: __('Connection error'),
		})[state.value] || state.value,
)
const stateClass = computed(() =>
	state.value === 'error' ? 'text-red-600' : state.value === 'connected' ? 'text-green-600' : 'text-gray-500',
)
const formattedRemaining = computed(() => {
	const s = remainingSeconds.value
	return `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`
})

async function onStart() {
	await start(props.scenarioId)
}
async function onStop() {
	await stop('completed')
	emit('ended')
}

watch(
	() => transcript.value.length,
	async () => {
		await nextTick()
		if (scroller.value) scroller.value.scrollTop = scroller.value.scrollHeight
	},
)
</script>
```

- [ ] **Step 3: Branch the simulation entry to voice mode**

Find the component that starts a simulation (`grep -rn "start_session\|modality" frontend/src/oslms frontend/src/pages 2>/dev/null`). Where it currently renders the chat session for a scenario, add: when the chosen scenario's `modality === 'voice'` (or the user picks voice for a `both` scenario), render `<VoiceSession :scenario-id="scenario.name" @ended="onEnded" />` instead of the chat component. Keep the existing chat path untouched for `modality === 'chat'`.

- [ ] **Step 4: Build + manual verification**

Run: `cd frontend && yarn build`
Expected: build succeeds.

Then verify behavior against the running app (`yarn dev`, logged in as an enrolled student):
1. With `realtime_provider="mock"`: starting a voice session returns a descriptor with `transport: "mock"`. `createTransport` will throw on `"mock"` — so for the mock smoke test, assert the control-plane round-trip via the Network tab (create → end) rather than audio. (Mock validates the backend, not the browser audio path.)
2. With `realtime_provider="openai"` and a real key: start a session, speak, confirm you hear the persona and see live transcript turns, confirm the timer counts down from 5:00 and auto-ends, and confirm `LMSA Simulation Turn` rows + a debrief are created.

> Record a short GIF of the OpenAI happy path for the PR (browser GIF tool).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/oslms/composables/useRealtimeSession.js \
        frontend/src/oslms/components/simulations/VoiceSession.vue \
        <the modified simulation entry component>
git commit -m "feat: voice session composable + VoiceSession component"
```

---

### Task 10: Documentation + i18n + final verification

Wire translations and update the docs so operators know the feature exists.

**Files:**
- Modify: `apps/os_lms/os_lms/CLAUDE.md` (add a short "Realtime Voice" subsection under the AI module)
- Modify: i18n source as used by the rest of `oslms/` (follow the pattern the existing components use for `__()` strings; if a `.csv`/`locale` extraction step exists, run it).
- Verify: full test pass.

- [ ] **Step 1: Add an operator note to `apps/os_lms/os_lms/CLAUDE.md`**

Append under the AI module description: a 4-6 line summary — what realtime voice is, that OpenAI is default / Gemini behind a flag, the `LMSA Settings` Realtime section, and that audio never passes through Frappe.

- [ ] **Step 2: Run the full realtime test suite**

Run:
```bash
bench --site lms.localhost run-tests --app os_lms --module os_lms.os_lms.ai.utils.realtime.tests.test_realtime
bench --site lms.localhost run-tests --app os_lms --module os_lms.os_lms.ai.realtime.tests.test_realtime_api
bench --site lms.localhost run-tests --app os_lms --module os_lms.os_lms.ai.utils.llm.tests.test_provider_encapsulation
```
Expected: all PASS.

- [ ] **Step 3: Run the pre-commit linters**

Run: `pre-commit run --all-files`
Expected: pass (Ruff: tabs, line-length 110, double quotes; Prettier/ESLint for the JS/Vue).

- [ ] **Step 4: Commit**

```bash
git add apps/os_lms/os_lms/CLAUDE.md <i18n files>
git commit -m "docs: document realtime voice simulations + i18n strings"
```

---

## Out of scope (future, additive)

- **Flutter client** — consumes the same `ai.realtime.api.*` endpoints from a separate repo; one `RealtimeTransport` per platform (`flutter_webrtc` for OpenAI; a WS client for Gemini).
- **Raw audio capture + "delivery" soft-skill judge** — needs a consent flow, private File per session, TTL/deletion; then a new judge in `eval/judges/`.
- **Server-side authoritative transcript relay (trust model B)** — only if voice simulations become high-stakes exams.
- **Natural-close steering** — at T-N inject a wrap-up directive (`session.update`/`response.create` for OpenAI; content turn for Gemini).

## Self-review notes (filled by the planner)

- **Spec coverage:** §4 architecture → Tasks 1,8,9; §5 components → Tasks 1-3,7,8,9; §5.4 encapsulation → Task 4; §6 flow → Task 7,9; §7 duration → Task 7 (server) + Task 9 (client timer); §8 settings/doctypes → Tasks 5,6; §9 provider notes → Tasks 2,3; §10 testing → every task's TDD steps; §11 phases → Tasks 1-10 map to spec phases 1-6 (phase 7 out of scope); §12 risks → encoded (provider fixed at start in Task 7; per-minute cost via Task 5/7; trust model A in Task 7,9). 
- **No raw audio retention:** no task persists audio — only transcript text (Task 7). Matches the decision.

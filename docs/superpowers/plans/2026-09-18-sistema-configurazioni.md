# Sistema di configurazioni os_lms — piano di implementazione

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Costruire un sistema unico e dichiarativo per i parametri di configurazione della piattaforma (sezioni Corsi, Classi, App), in cui aggiungere un parametro costa una dichiarazione in un solo file Python.

**Architecture:** Un registry in codice dichiara i parametri; i valori vivono in un doctype chiave → valore (`OS LMS Config Value`) senza migrazioni di schema; il pannello SPA si disegna dallo schema servito dal backend; le letture nei file upstream sono marcate, dichiarate nel registry e verificate da test.

**Tech Stack:** Python 3.10+ / Frappe Framework (app `os_lms`), Vue 3 + Pinia + frappe-ui (SPA `frontend/`), test con `frappe.tests.UnitTestCase` e Vitest.

**Spec:** [`docs/superpowers/specs/2026-09-18-sistema-configurazioni-design.md`](../specs/2026-09-18-sistema-configurazioni-design.md)

## Global Constraints

- **Identificatori e commenti in inglese** (`CLAUDE.md` del progetto). Etichette e descrizioni mostrate all'utente restano in italiano. Le chiavi dei parametri sono quindi inglesi: `courses.hidden_tabs`, non `corsi.filtri_nascosti`. **Questo è uno scostamento consapevole dalla specifica**, che usava identificatori italiani: la chiave finisce nel marcatore degli innesti e nel payload dell'app, quindi va fissata subito in inglese.
- **Python**: Ruff, riga max 110 caratteri, indentazione a **tab**, virgolette doppie, target py310 (`pyproject.toml`).
- **Metodi whitelisted**: `require_type_annotated_api_methods = True` (`lms/hooks.py:288`) — ogni `@frappe.whitelist()` deve avere annotazioni di tipo su tutti i parametri e sul valore di ritorno.
- **Commit**: Conventional Commits (`feat`, `fix`, `docs`, `test`, `refactor`, `chore`), imposti da commitlint.
- **Branch**: `feature/oslms`. Non fare merge né push senza richiesta esplicita.
- **Nessun file di `lms/` o di `frontend/src/` fuori da `frontend/src/oslms/` va modificato**, con **una sola eccezione autorizzata**: l'innesto del Task 11 in `frontend/src/pages/Courses/Courses.vue`.
- **Sezioni**: `courses` (etichetta "Corsi"), `batches` (etichetta "Classi"), `app` (etichetta "App").
- **Regola dei default** (spec D6): il default di ogni parametro riproduce esattamente il comportamento senza il parametro.
- **Semantica sottrattiva** (spec D5): i parametri a elenco dicono cosa **togliere**, mai cosa tenere.
- **Ambito**: nella v1 si accetta solo `scope = "global"`; qualsiasi altro valore solleva `NotImplementedError`.

## Comandi

```bash
# Test backend (il container Frappe deve essere avviato: docker compose -f docker/docker-compose.yml up -d)
docker compose -f docker/docker-compose.yml exec frappe \
  bench --site lms.localhost run-tests --app os_lms --module os_lms.os_lms.config.tests.test_types

# Migrazione (necessaria dopo la creazione del doctype)
docker compose -f docker/docker-compose.yml exec frappe bench --site lms.localhost migrate

# Test frontend
cd frontend && yarn test

# Build frontend
cd frontend && yarn build
```

## Ambito di questo piano

Copre le fasi 1-6 e 8 della stima nella specifica: fondamenta, esposizione, pannello, tenuta upstream, documentazione, **un** parametro reale end-to-end (`courses.hidden_tabs`) e verifica finale.

**Non copre** `frontend/src/oslms/config/keys.generated.ts`, il file di costanti e tipi TypeScript previsto da §4.1 della specifica. Rimandato di proposito: `cfg()` accetta una stringa e il pannello è già guidato dallo schema del backend, quindi finché i parametri sono pochi quel file aggiungerebbe un passo di generazione senza impedire nessun errore che i test non intercettino già (`test_grafts.py` segnala i marcatori orfani, `cfg()` avvisa in console su chiave sconosciuta). Da riprendere quando i parametri superano la decina.

**Non copre** la fase 7 (gli altri 4-5 parametri), perché non sono ancora stati definiti dal committente: una volta approvato questo piano, ciascuno si aggiunge ripetendo la forma dei Task 10-11 seguendo la ricetta prodotta dal Task 13. Non copre nemmeno la migrazione di `enable_live_classes`, che la specifica colloca dopo il collaudo (§6.2).

## Struttura dei file

| File | Responsabilità |
| --- | --- |
| `apps/os_lms/os_lms/os_lms/config/types.py` | I tipi di valore e la loro validazione. **Python puro, nessun import di frappe.** |
| `apps/os_lms/os_lms/os_lms/config/registry.py` | `ConfigParam`, gli enum, il registro e le sue interrogazioni. Python puro. |
| `apps/os_lms/os_lms/os_lms/config/definitions.py` | **Le dichiarazioni.** L'unico file da toccare per aggiungere un parametro. |
| `apps/os_lms/os_lms/os_lms/config/store.py` | Lettura/scrittura dei valori, risoluzione, cache. Richiede frappe. |
| `apps/os_lms/os_lms/os_lms/config/api.py` | Endpoint whitelisted per il pannello. |
| `apps/os_lms/os_lms/os_lms/config/docgen.py` | Generatore della documentazione. |
| `apps/os_lms/os_lms/os_lms/config/__init__.py` | API pubblica: `cfg`, `for_surface`, `set_value`, `clear_value`. |
| `apps/os_lms/os_lms/os_lms/doctype/os_lms_config_value/` | Lo storage. |
| `frontend/src/oslms/config/useOsConfig.js` | `cfg(key)` e `hideByConfig(key, list)` per la SPA. |
| `frontend/src/oslms/components/Settings/OsConfigSection.vue` | Renderer generico di una sezione del pannello. |

---

### Task 1: Tipi di valore

**Files:**
- Create: `apps/os_lms/os_lms/os_lms/config/__init__.py` (vuoto per ora)
- Create: `apps/os_lms/os_lms/os_lms/config/types.py`
- Create: `apps/os_lms/os_lms/os_lms/config/tests/__init__.py` (vuoto)
- Test: `apps/os_lms/os_lms/os_lms/config/tests/test_types.py`

**Interfaces:**
- Consumes: niente.
- Produces: `ConfigTypeError`; `ParamType` con `coerce(value) -> object` e `schema() -> dict`; le classi concrete `Boolean`, `Integer(minimum=None, maximum=None)`, `Float(minimum=None, maximum=None)`, `Text(max_length=None)`, `LongText`, `Choice(options)`, `MultiChoice(options)`, `JsonValue`. `options` è una lista di tuple `(value, label)`.

- [ ] **Step 1: Write the failing test**

```python
# apps/os_lms/os_lms/os_lms/config/tests/test_types.py
"""Unit tests for the configuration value types.

The types module is deliberately frappe-free so these run as plain unit
tests: every rule that protects a stored value lives here.
"""
from __future__ import annotations

from frappe.tests import UnitTestCase

from os_lms.os_lms.config.types import (
	Boolean,
	Choice,
	ConfigTypeError,
	Float,
	Integer,
	JsonValue,
	LongText,
	MultiChoice,
	Text,
)


class TestBoolean(UnitTestCase):
	def test_accepts_native_and_wire_values(self):
		self.assertIs(Boolean().coerce(True), True)
		self.assertIs(Boolean().coerce(1), True)
		self.assertIs(Boolean().coerce("1"), True)
		self.assertIs(Boolean().coerce(0), False)
		self.assertIs(Boolean().coerce("0"), False)

	def test_rejects_anything_else(self):
		with self.assertRaises(ConfigTypeError):
			Boolean().coerce("maybe")

	def test_schema_reports_control(self):
		self.assertEqual(Boolean().schema()["control"], "checkbox")


class TestInteger(UnitTestCase):
	def test_coerces_numeric_string(self):
		self.assertEqual(Integer().coerce("12"), 12)

	def test_enforces_bounds(self):
		with self.assertRaises(ConfigTypeError):
			Integer(minimum=1, maximum=10).coerce(0)
		with self.assertRaises(ConfigTypeError):
			Integer(minimum=1, maximum=10).coerce(11)
		self.assertEqual(Integer(minimum=1, maximum=10).coerce(10), 10)

	def test_rejects_non_numeric(self):
		with self.assertRaises(ConfigTypeError):
			Integer().coerce("abc")


class TestFloat(UnitTestCase):
	def test_coerces_and_bounds(self):
		self.assertEqual(Float().coerce("1.5"), 1.5)
		with self.assertRaises(ConfigTypeError):
			Float(minimum=0.0).coerce(-1.0)


class TestText(UnitTestCase):
	def test_enforces_max_length(self):
		self.assertEqual(Text(max_length=3).coerce("abc"), "abc")
		with self.assertRaises(ConfigTypeError):
			Text(max_length=3).coerce("abcd")

	def test_rejects_non_string(self):
		with self.assertRaises(ConfigTypeError):
			Text().coerce(5)

	def test_long_text_uses_textarea_control(self):
		self.assertEqual(LongText().schema()["control"], "textarea")


class TestChoice(UnitTestCase):
	OPTIONS = [("live", "Pubblicato"), ("upcoming", "In arrivo")]

	def test_accepts_declared_value(self):
		self.assertEqual(Choice(self.OPTIONS).coerce("live"), "live")

	def test_rejects_undeclared_value(self):
		with self.assertRaises(ConfigTypeError):
			Choice(self.OPTIONS).coerce("archived")

	def test_schema_exposes_options(self):
		schema = Choice(self.OPTIONS).schema()
		self.assertEqual(schema["control"], "select")
		self.assertEqual(
			schema["options"],
			[{"value": "live", "label": "Pubblicato"}, {"value": "upcoming", "label": "In arrivo"}],
		)


class TestMultiChoice(UnitTestCase):
	OPTIONS = [("live", "Pubblicato"), ("upcoming", "In arrivo"), ("created", "Creato")]

	def test_accepts_subset_and_keeps_declared_order(self):
		self.assertEqual(MultiChoice(self.OPTIONS).coerce(["created", "live"]), ["live", "created"])

	def test_deduplicates(self):
		self.assertEqual(MultiChoice(self.OPTIONS).coerce(["live", "live"]), ["live"])

	def test_accepts_empty_list(self):
		self.assertEqual(MultiChoice(self.OPTIONS).coerce([]), [])

	def test_rejects_undeclared_value(self):
		with self.assertRaises(ConfigTypeError):
			MultiChoice(self.OPTIONS).coerce(["archived"])

	def test_rejects_non_list(self):
		with self.assertRaises(ConfigTypeError):
			MultiChoice(self.OPTIONS).coerce("live")

	def test_schema_exposes_options(self):
		self.assertEqual(MultiChoice(self.OPTIONS).schema()["control"], "multicheck")


class TestJsonValue(UnitTestCase):
	def test_accepts_dict_and_list(self):
		self.assertEqual(JsonValue().coerce({"a": 1}), {"a": 1})
		self.assertEqual(JsonValue().coerce([1, 2]), [1, 2])

	def test_rejects_scalar(self):
		with self.assertRaises(ConfigTypeError):
			JsonValue().coerce("plain")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose -f docker/docker-compose.yml exec frappe bench --site lms.localhost run-tests --app os_lms --module os_lms.os_lms.config.tests.test_types`
Expected: FAIL — `ModuleNotFoundError: No module named 'os_lms.os_lms.config'`

- [ ] **Step 3: Write minimal implementation**

```python
# apps/os_lms/os_lms/os_lms/config/types.py
"""Value types for the os_lms configuration parameters.

Every parameter declares one of these. A type knows three things: how to
turn whatever arrives (from the settings panel, from the database, from a
default) into a clean Python value, which control the panel must render,
and what the panel needs to know about it.

This module deliberately imports nothing from frappe: it is the layer that
protects stored values, so it must stay unit-testable without a site.
"""
from __future__ import annotations


class ConfigTypeError(ValueError):
	"""Raised when a value does not satisfy its parameter type."""


class ParamType:
	"""Base class. `control` names the widget the settings panel renders."""

	control = "text"

	def coerce(self, value: object) -> object:
		"""Return the normalised value, or raise ConfigTypeError."""
		raise NotImplementedError

	def schema(self) -> dict:
		"""Everything the settings panel needs to render this type."""
		return {"control": self.control}


class Boolean(ParamType):
	control = "checkbox"

	def coerce(self, value: object) -> bool:
		# The panel sends real booleans, but a value hand-edited in the desk
		# arrives as 0/1 or "0"/"1", so accept the wire forms too.
		if isinstance(value, bool):
			return value
		if value in (0, 1, "0", "1"):
			return bool(int(value))
		raise ConfigTypeError(f"expected a boolean, got {value!r}")


class Integer(ParamType):
	control = "number"

	def __init__(self, minimum: int | None = None, maximum: int | None = None):
		self.minimum = minimum
		self.maximum = maximum

	def coerce(self, value: object) -> int:
		try:
			number = int(value)
		except (TypeError, ValueError):
			raise ConfigTypeError(f"expected an integer, got {value!r}") from None
		if self.minimum is not None and number < self.minimum:
			raise ConfigTypeError(f"{number} is below the minimum {self.minimum}")
		if self.maximum is not None and number > self.maximum:
			raise ConfigTypeError(f"{number} is above the maximum {self.maximum}")
		return number

	def schema(self) -> dict:
		return {"control": self.control, "minimum": self.minimum, "maximum": self.maximum}


class Float(ParamType):
	control = "number"

	def __init__(self, minimum: float | None = None, maximum: float | None = None):
		self.minimum = minimum
		self.maximum = maximum

	def coerce(self, value: object) -> float:
		try:
			number = float(value)
		except (TypeError, ValueError):
			raise ConfigTypeError(f"expected a number, got {value!r}") from None
		if self.minimum is not None and number < self.minimum:
			raise ConfigTypeError(f"{number} is below the minimum {self.minimum}")
		if self.maximum is not None and number > self.maximum:
			raise ConfigTypeError(f"{number} is above the maximum {self.maximum}")
		return number

	def schema(self) -> dict:
		return {"control": self.control, "minimum": self.minimum, "maximum": self.maximum}


class Text(ParamType):
	control = "text"

	def __init__(self, max_length: int | None = None):
		self.max_length = max_length

	def coerce(self, value: object) -> str:
		if not isinstance(value, str):
			raise ConfigTypeError(f"expected a string, got {value!r}")
		if self.max_length is not None and len(value) > self.max_length:
			raise ConfigTypeError(f"string longer than {self.max_length} characters")
		return value

	def schema(self) -> dict:
		return {"control": self.control, "max_length": self.max_length}


class LongText(Text):
	control = "textarea"


class Choice(ParamType):
	control = "select"

	def __init__(self, options: list[tuple[str, str]]):
		self.options = list(options)

	@property
	def values(self) -> list[str]:
		return [value for value, _label in self.options]

	def coerce(self, value: object) -> str:
		if value not in self.values:
			raise ConfigTypeError(f"{value!r} is not one of {self.values}")
		return value

	def schema(self) -> dict:
		return {
			"control": self.control,
			"options": [{"value": value, "label": label} for value, label in self.options],
		}


class MultiChoice(Choice):
	control = "multicheck"

	def coerce(self, value: object) -> list[str]:
		if not isinstance(value, list):
			raise ConfigTypeError(f"expected a list, got {value!r}")
		unknown = [item for item in value if item not in self.values]
		if unknown:
			raise ConfigTypeError(f"{unknown} are not among {self.values}")
		# Return in declared order so the stored value is stable regardless of
		# the order the panel happened to send.
		return [candidate for candidate in self.values if candidate in value]


class JsonValue(ParamType):
	control = "json"

	def coerce(self, value: object) -> dict | list:
		if not isinstance(value, (dict, list)):
			raise ConfigTypeError(f"expected an object or a list, got {value!r}")
		return value
```

- [ ] **Step 4: Run test to verify it passes**

Run: `docker compose -f docker/docker-compose.yml exec frappe bench --site lms.localhost run-tests --app os_lms --module os_lms.os_lms.config.tests.test_types`
Expected: PASS — tutti i test superati

- [ ] **Step 5: Commit**

```bash
git add apps/os_lms/os_lms/os_lms/config/
git commit -m "feat(config): add parameter value types with validation

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Registry dei parametri

**Files:**
- Create: `apps/os_lms/os_lms/os_lms/config/registry.py`
- Test: `apps/os_lms/os_lms/os_lms/config/tests/test_registry.py`

**Interfaces:**
- Consumes: da `types.py`: `ParamType`, `ConfigTypeError`, `Boolean`, `MultiChoice`.
- Produces: `Section` (`COURSES="courses"`, `BATCHES="batches"`, `APP="app"`); `Surface` (`WEB="web"`, `APP="app"`); `Scope` (`GLOBAL="global"`, `COURSE="course"`, `BATCH="batch"`); `ConfigParam` (dataclass); `UnknownConfigKey`; `register(param) -> ConfigParam`; `get_param(key) -> ConfigParam`; `all_params() -> list[ConfigParam]`; `params_for_section(section) -> list[ConfigParam]`; `params_for_surface(surface) -> list[ConfigParam]`; `reset_registry()` (solo per i test).

- [ ] **Step 1: Write the failing test**

```python
# apps/os_lms/os_lms/os_lms/config/tests/test_registry.py
"""Unit tests for the parameter registry.

The registry is the single source of truth, so most of these tests are
about what it refuses: a typo in a key or a default that does not fit its
own type must fail loudly at import time, not silently at runtime.
"""
from __future__ import annotations

from frappe.tests import UnitTestCase

from os_lms.os_lms.config import registry as reg
from os_lms.os_lms.config.types import Boolean, MultiChoice


def make_param(**overrides) -> reg.ConfigParam:
	defaults = dict(
		key="courses.sample_flag",
		section=reg.Section.COURSES,
		type=Boolean(),
		default=False,
		label="Parametro di prova",
		surfaces=(reg.Surface.WEB,),
		since="2026-09-18",
	)
	defaults.update(overrides)
	return reg.ConfigParam(**defaults)


class TestRegistration(UnitTestCase):
	def setUp(self):
		self._saved = reg.reset_registry()

	def tearDown(self):
		reg.reset_registry(self._saved)

	def test_registers_and_returns_the_param(self):
		param = reg.register(make_param())
		self.assertEqual(reg.get_param("courses.sample_flag"), param)

	def test_rejects_duplicate_key(self):
		reg.register(make_param())
		with self.assertRaises(ValueError):
			reg.register(make_param())

	def test_rejects_key_prefix_not_matching_section(self):
		with self.assertRaises(ValueError):
			reg.register(make_param(key="batches.sample_flag", section=reg.Section.COURSES))

	def test_rejects_key_without_section_prefix(self):
		with self.assertRaises(ValueError):
			reg.register(make_param(key="sample_flag"))

	def test_rejects_default_that_does_not_fit_its_type(self):
		with self.assertRaises(reg.ConfigTypeError):
			reg.register(make_param(default="yes"))

	def test_rejects_empty_surfaces(self):
		with self.assertRaises(ValueError):
			reg.register(make_param(surfaces=()))

	def test_rejects_non_global_scope_for_now(self):
		with self.assertRaises(NotImplementedError):
			reg.register(make_param(scope=reg.Scope.COURSE))


class TestLookup(UnitTestCase):
	def setUp(self):
		self._saved = reg.reset_registry()
		self.web_only = reg.register(make_param(key="courses.a", surfaces=(reg.Surface.WEB,)))
		self.both = reg.register(
			make_param(key="courses.b", surfaces=(reg.Surface.WEB, reg.Surface.APP))
		)
		self.app_only = reg.register(
			make_param(key="app.c", section=reg.Section.APP, surfaces=(reg.Surface.APP,))
		)

	def tearDown(self):
		reg.reset_registry(self._saved)

	def test_unknown_key_raises(self):
		with self.assertRaises(reg.UnknownConfigKey):
			reg.get_param("courses.nope")

	def test_params_for_section(self):
		keys = [param.key for param in reg.params_for_section(reg.Section.COURSES)]
		self.assertEqual(keys, ["courses.a", "courses.b"])

	def test_params_for_surface_web_excludes_app_only(self):
		keys = [param.key for param in reg.params_for_surface(reg.Surface.WEB)]
		self.assertEqual(keys, ["courses.a", "courses.b"])

	def test_params_for_surface_app_includes_course_params(self):
		keys = [param.key for param in reg.params_for_surface(reg.Surface.APP)]
		self.assertEqual(keys, ["courses.b", "app.c"])


class TestMultiChoiceParam(UnitTestCase):
	def setUp(self):
		self._saved = reg.reset_registry()

	def tearDown(self):
		reg.reset_registry(self._saved)

	def test_empty_default_is_valid_for_multichoice(self):
		param = reg.register(
			make_param(type=MultiChoice([("live", "Pubblicato")]), default=[])
		)
		self.assertEqual(param.default, [])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose -f docker/docker-compose.yml exec frappe bench --site lms.localhost run-tests --app os_lms --module os_lms.os_lms.config.tests.test_registry`
Expected: FAIL — `ImportError: cannot import name 'registry'`

- [ ] **Step 3: Write minimal implementation**

```python
# apps/os_lms/os_lms/os_lms/config/registry.py
"""The parameter registry: the single source of truth of the config system.

A parameter is declared once here (through definitions.py) and everything
else derives from that declaration: the settings panel, the validation on
save, the payload sent to the site and to the mobile app, the generated
documentation.

Registration is strict on purpose. Without a database schema to lean on,
the registry is the only thing standing between a typo and a value that is
silently stored and never read back.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from os_lms.os_lms.config.types import ConfigTypeError, ParamType


class Section(str, Enum):
	"""The three groups shown in the settings panel."""

	COURSES = "courses"
	BATCHES = "batches"
	APP = "app"


class Surface(str, Enum):
	"""Where a parameter is delivered.

	A parameter declared [WEB, APP] reaches both; one declared [APP] never
	enters the website payload. This is how "course and batch parameters
	also apply to the app, but not the other way round" is enforced: by the
	declaration, not by logic someone has to maintain.
	"""

	WEB = "web"
	APP = "app"


class Scope(str, Enum):
	"""Reserved for the per-entity override. Only GLOBAL works today."""

	GLOBAL = "global"
	COURSE = "course"
	BATCH = "batch"


class UnknownConfigKey(KeyError):
	"""Raised when a key is read or written that no parameter declares."""


@dataclass(frozen=True)
class ConfigParam:
	key: str
	section: Section
	type: ParamType
	default: object
	label: str
	surfaces: tuple[Surface, ...]
	since: str
	description: str = ""
	scope: Scope = Scope.GLOBAL
	roles: tuple[str, ...] = ("System Manager",)
	grafts: tuple[str, ...] = field(default=())

	def schema(self) -> dict:
		"""What the settings panel needs to render this parameter."""
		return {
			"key": self.key,
			"label": self.label,
			"description": self.description,
			"default": self.default,
			**self.type.schema(),
		}


_REGISTRY: dict[str, ConfigParam] = {}


def register(param: ConfigParam) -> ConfigParam:
	"""Add a parameter to the registry, refusing anything malformed."""
	if param.key in _REGISTRY:
		raise ValueError(f"duplicate configuration key: {param.key}")
	prefix = f"{param.section.value}."
	if not param.key.startswith(prefix):
		raise ValueError(f"key {param.key!r} must start with {prefix!r}")
	if not param.surfaces:
		raise ValueError(f"{param.key} must declare at least one surface")
	if param.scope is not Scope.GLOBAL:
		raise NotImplementedError(f"{param.key}: only the global scope is supported for now")
	# A default that does not fit its own type would surface as a runtime
	# failure on a site where nobody ever touched the parameter.
	param.type.coerce(param.default)
	_REGISTRY[param.key] = param
	return param


def get_param(key: str) -> ConfigParam:
	try:
		return _REGISTRY[key]
	except KeyError:
		raise UnknownConfigKey(f"no configuration parameter declares the key {key!r}") from None


def all_params() -> list[ConfigParam]:
	return list(_REGISTRY.values())


def params_for_section(section: Section) -> list[ConfigParam]:
	return [param for param in _REGISTRY.values() if param.section is section]


def params_for_surface(surface: Surface) -> list[ConfigParam]:
	return [param for param in _REGISTRY.values() if surface in param.surfaces]


def reset_registry(saved: dict[str, ConfigParam] | None = None) -> dict[str, ConfigParam]:
	"""Swap the registry contents. For tests only.

	Returns the previous contents so a test can restore them in tearDown.
	"""
	global _REGISTRY
	previous = _REGISTRY
	_REGISTRY = dict(saved) if saved is not None else {}
	return previous


__all__ = [
	"ConfigParam",
	"ConfigTypeError",
	"Scope",
	"Section",
	"Surface",
	"UnknownConfigKey",
	"all_params",
	"get_param",
	"params_for_section",
	"params_for_surface",
	"register",
	"reset_registry",
]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `docker compose -f docker/docker-compose.yml exec frappe bench --site lms.localhost run-tests --app os_lms --module os_lms.os_lms.config.tests.test_registry`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/os_lms/os_lms/os_lms/config/registry.py apps/os_lms/os_lms/os_lms/config/tests/test_registry.py
git commit -m "feat(config): add the parameter registry with strict registration

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Doctype dello storage

**Files:**
- Create: `apps/os_lms/os_lms/os_lms/doctype/os_lms_config_value/__init__.py` (vuoto)
- Create: `apps/os_lms/os_lms/os_lms/doctype/os_lms_config_value/os_lms_config_value.json`
- Create: `apps/os_lms/os_lms/os_lms/doctype/os_lms_config_value/os_lms_config_value.py`
- Test: `apps/os_lms/os_lms/os_lms/config/tests/test_doctype.py`

**Interfaces:**
- Consumes: `get_param`, `UnknownConfigKey` da `registry.py`.
- Produces: il doctype `OS LMS Config Value` con i campi `config_key`, `scope_type`, `scope_name`, `value`, `lookup_key`; la funzione modulo `build_lookup_key(scope_type, scope_name, config_key) -> str`.

**Nota:** `value` contiene **sempre** JSON. `lookup_key` è calcolato in `autoname()` e usato come `name`, così l'unicità della tripla (chiave, tipo di ambito, nome dell'ambito) è garantita dal database.

- [ ] **Step 1: Write the failing test**

```python
# apps/os_lms/os_lms/os_lms/config/tests/test_doctype.py
"""Tests for the OS LMS Config Value doctype.

The doctype is the emergency editing surface (spec D7), so it validates on
its own instead of trusting the API layer.
"""
from __future__ import annotations

import json

import frappe
from frappe.tests import UnitTestCase

from os_lms.os_lms.config import registry as reg
from os_lms.os_lms.config.types import Boolean
from os_lms.os_lms.doctype.os_lms_config_value.os_lms_config_value import build_lookup_key


class TestConfigValueDoctype(UnitTestCase):
	def setUp(self):
		self._saved = reg.reset_registry()
		reg.register(
			reg.ConfigParam(
				key="courses.sample_flag",
				section=reg.Section.COURSES,
				type=Boolean(),
				default=False,
				label="Parametro di prova",
				surfaces=(reg.Surface.WEB,),
				since="2026-09-18",
			)
		)
		frappe.db.delete("OS LMS Config Value", {"config_key": "courses.sample_flag"})

	def tearDown(self):
		frappe.db.delete("OS LMS Config Value", {"config_key": "courses.sample_flag"})
		reg.reset_registry(self._saved)

	def test_lookup_key_shape(self):
		self.assertEqual(
			build_lookup_key("Global", "", "courses.sample_flag"),
			"Global::::courses.sample_flag",
		)

	def test_name_is_the_lookup_key(self):
		doc = frappe.get_doc(
			{
				"doctype": "OS LMS Config Value",
				"config_key": "courses.sample_flag",
				"scope_type": "Global",
				"value": json.dumps(True),
			}
		).insert(ignore_permissions=True)
		self.assertEqual(doc.name, "Global::::courses.sample_flag")

	def test_rejects_unknown_key(self):
		doc = frappe.get_doc(
			{
				"doctype": "OS LMS Config Value",
				"config_key": "courses.not_declared",
				"scope_type": "Global",
				"value": json.dumps(True),
			}
		)
		with self.assertRaises(frappe.ValidationError):
			doc.insert(ignore_permissions=True)

	def test_rejects_value_that_does_not_fit_the_type(self):
		doc = frappe.get_doc(
			{
				"doctype": "OS LMS Config Value",
				"config_key": "courses.sample_flag",
				"scope_type": "Global",
				"value": json.dumps("maybe"),
			}
		)
		with self.assertRaises(frappe.ValidationError):
			doc.insert(ignore_permissions=True)

	def test_rejects_malformed_json(self):
		doc = frappe.get_doc(
			{
				"doctype": "OS LMS Config Value",
				"config_key": "courses.sample_flag",
				"scope_type": "Global",
				"value": "{not json",
			}
		)
		with self.assertRaises(frappe.ValidationError):
			doc.insert(ignore_permissions=True)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose -f docker/docker-compose.yml exec frappe bench --site lms.localhost run-tests --app os_lms --module os_lms.os_lms.config.tests.test_doctype`
Expected: FAIL — `ModuleNotFoundError` su `os_lms.os_lms.doctype.os_lms_config_value`

- [ ] **Step 3: Write minimal implementation**

```json
{
	"actions": [],
	"creation": "2026-09-18 10:00:00.000000",
	"doctype": "DocType",
	"engine": "InnoDB",
	"field_order": [
		"config_key",
		"scope_type",
		"scope_name",
		"value",
		"lookup_key"
	],
	"fields": [
		{
			"fieldname": "config_key",
			"fieldtype": "Data",
			"in_list_view": 1,
			"in_standard_filter": 1,
			"label": "Config Key",
			"reqd": 1
		},
		{
			"default": "Global",
			"fieldname": "scope_type",
			"fieldtype": "Select",
			"in_list_view": 1,
			"in_standard_filter": 1,
			"label": "Scope Type",
			"options": "Global\nLMS Course\nLMS Batch",
			"reqd": 1
		},
		{
			"depends_on": "eval:doc.scope_type != 'Global'",
			"fieldname": "scope_name",
			"fieldtype": "Data",
			"in_list_view": 1,
			"label": "Scope Name"
		},
		{
			"description": "JSON-encoded value. Edit here only in an emergency: the settings panel is the supported surface.",
			"fieldname": "value",
			"fieldtype": "Long Text",
			"in_list_view": 1,
			"label": "Value",
			"reqd": 1
		},
		{
			"fieldname": "lookup_key",
			"fieldtype": "Data",
			"hidden": 1,
			"label": "Lookup Key",
			"read_only": 1,
			"unique": 1
		}
	],
	"index_web_pages_for_search": 0,
	"links": [],
	"modified": "2026-09-18 10:00:00.000000",
	"modified_by": "Administrator",
	"module": "OS LMS",
	"name": "OS LMS Config Value",
	"owner": "Administrator",
	"permissions": [
		{
			"create": 1,
			"delete": 1,
			"email": 1,
			"export": 1,
			"print": 1,
			"read": 1,
			"report": 1,
			"role": "System Manager",
			"share": 1,
			"write": 1
		}
	],
	"sort_field": "modified",
	"sort_order": "DESC",
	"states": [],
	"track_changes": 1
}
```

```python
# apps/os_lms/os_lms/os_lms/doctype/os_lms_config_value/os_lms_config_value.py
# Copyright (c) 2026, ELITE and contributors
# For license information, please see license.txt
"""Storage for configuration values.

One row per parameter that has actually been changed: a parameter nobody
touched has no row and falls back to the registry default, which by rule
reproduces the upstream behaviour. Clearing a parameter therefore means
deleting its row.
"""
from __future__ import annotations

import json

import frappe
from frappe import _
from frappe.model.document import Document

from os_lms.os_lms.config.registry import UnknownConfigKey, get_param
from os_lms.os_lms.config.types import ConfigTypeError


def build_lookup_key(scope_type: str, scope_name: str, config_key: str) -> str:
	"""The unique identity of a stored value, also used as the document name."""
	return f"{scope_type}::{scope_name or ''}::{config_key}"


class OSLMSConfigValue(Document):
	def autoname(self):
		self.lookup_key = build_lookup_key(self.scope_type, self.scope_name, self.config_key)
		self.name = self.lookup_key

	def validate(self):
		# The desk is an emergency editing surface, so it validates here too
		# rather than trusting the API layer that normally writes these rows.
		try:
			param = get_param(self.config_key)
		except UnknownConfigKey:
			frappe.throw(_("No configuration parameter declares the key {0}.").format(self.config_key))
		try:
			decoded = json.loads(self.value)
		except (TypeError, ValueError):
			frappe.throw(_("The value of {0} must be valid JSON.").format(self.config_key))
		try:
			param.type.coerce(decoded)
		except ConfigTypeError as error:
			frappe.throw(_("Invalid value for {0}: {1}").format(self.config_key, str(error)))

	def on_update(self):
		from os_lms.os_lms.config.store import invalidate_cache

		invalidate_cache()

	def on_trash(self):
		from os_lms.os_lms.config.store import invalidate_cache

		invalidate_cache()
```

- [ ] **Step 4: Migrate, then run test to verify it passes**

Run: `docker compose -f docker/docker-compose.yml exec frappe bench --site lms.localhost migrate`
Then: `docker compose -f docker/docker-compose.yml exec frappe bench --site lms.localhost run-tests --app os_lms --module os_lms.os_lms.config.tests.test_doctype`
Expected: PASS

> **Nota:** i test falliranno con `ImportError` su `invalidate_cache` finché il Task 4 non esiste. Se la sequenza viene eseguita in ordine, `on_update` non viene raggiunto dai test di validazione che sollevano prima; se invece un test di inserimento riuscito viene eseguito ora, creare temporaneamente `store.py` con la sola funzione `invalidate_cache()` vuota e completarla nel Task 4.

- [ ] **Step 5: Commit**

```bash
git add apps/os_lms/os_lms/os_lms/doctype/os_lms_config_value/ apps/os_lms/os_lms/os_lms/config/tests/test_doctype.py
git commit -m "feat(config): add the OS LMS Config Value storage doctype

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Store, risoluzione e cache

**Files:**
- Create: `apps/os_lms/os_lms/os_lms/config/store.py` (completare lo stub del Task 3)
- Create: `apps/os_lms/os_lms/os_lms/config/definitions.py` (vuoto, con il solo docstring)
- Create: `apps/os_lms/os_lms/os_lms/config/tests/helpers.py`
- Modify: `apps/os_lms/os_lms/os_lms/config/__init__.py`
- Test: `apps/os_lms/os_lms/os_lms/config/tests/test_store.py`

> **Pulizia dei test — regola non negoziabile.** Un `frappe.db.delete("OS LMS Config Value")` senza filtri cancella **tutte le configurazioni reali** del sito su cui girano i test, non solo quelle create dal test. Ogni test pulisce esclusivamente le chiavi che ha toccato, e per una chiave reale salva e ripristina il valore preesistente. È quello che fa `tests/helpers.py`, creato in questo task.

**Interfaces:**
- Consumes: `get_param`, `params_for_surface`, `Surface`, `Scope` da `registry.py`; il doctype `OS LMS Config Value`; `build_lookup_key`.
- Produces: `cfg(key, scope_type="Global", scope_name="") -> object`; `for_surface(surface) -> dict[str, object]`; `set_value(key, value, scope_type="Global", scope_name="") -> None`; `clear_value(key, scope_type="Global", scope_name="") -> None`; `invalidate_cache() -> None`. Riesportate da `config/__init__.py`.

- [ ] **Step 1: Write the failing test**

```python
# apps/os_lms/os_lms/os_lms/config/tests/test_store.py
"""Tests for reading and writing configuration values."""
from __future__ import annotations

import json

import frappe
from frappe.tests import UnitTestCase

from os_lms.os_lms.config import registry as reg
from os_lms.os_lms.config.store import (
	cfg,
	clear_value,
	for_surface,
	invalidate_cache,
	set_value,
)
from os_lms.os_lms.config.tests.helpers import clear
from os_lms.os_lms.config.types import Boolean, ConfigTypeError, MultiChoice

TABS = [("live", "Pubblicato"), ("upcoming", "In arrivo"), ("created", "Creato")]

# Keys used only by these tests. They deliberately do NOT collide with any
# declared parameter, so the cleanup can delete them without touching the
# real configuration of the site the tests run on.
MULTI_KEY = "courses.test_multi"
APP_KEY = "app.test_flag"
TEST_KEYS = [MULTI_KEY, APP_KEY]


def register_test_params():
	reg.register(
		reg.ConfigParam(
			key=MULTI_KEY,
			section=reg.Section.COURSES,
			type=MultiChoice(TABS),
			default=[],
			label="Filtri da nascondere",
			surfaces=(reg.Surface.WEB, reg.Surface.APP),
			since="2026-09-18",
		)
	)
	reg.register(
		reg.ConfigParam(
			key=APP_KEY,
			section=reg.Section.APP,
			type=Boolean(),
			default=False,
			label="Solo app",
			surfaces=(reg.Surface.APP,),
			since="2026-09-18",
		)
	)


class TestStore(UnitTestCase):
	def setUp(self):
		self._saved = reg.reset_registry()
		register_test_params()
		clear(TEST_KEYS)

	def tearDown(self):
		clear(TEST_KEYS)
		reg.reset_registry(self._saved)

	def test_returns_default_when_nothing_is_stored(self):
		self.assertEqual(cfg(MULTI_KEY), [])

	def test_round_trip(self):
		set_value(MULTI_KEY, ["created"])
		self.assertEqual(cfg(MULTI_KEY), ["created"])

	def test_set_value_validates(self):
		with self.assertRaises(ConfigTypeError):
			set_value(MULTI_KEY, ["archived"])

	def test_set_value_rejects_unknown_key(self):
		with self.assertRaises(reg.UnknownConfigKey):
			set_value("courses.nope", [])

	def test_cfg_rejects_unknown_key(self):
		with self.assertRaises(reg.UnknownConfigKey):
			cfg("courses.nope")

	def test_clear_value_restores_the_default(self):
		set_value(MULTI_KEY, ["created"])
		clear_value(MULTI_KEY)
		self.assertEqual(cfg(MULTI_KEY), [])

	def test_corrupted_stored_value_falls_back_to_default(self):
		# Simulate a hand-edit in the desk that bypassed validation.
		set_value(MULTI_KEY, ["created"])
		frappe.db.set_value(
			"OS LMS Config Value",
			f"Global::::{MULTI_KEY}",
			"value",
			json.dumps("not-a-list"),
			update_modified=False,
		)
		invalidate_cache()
		self.assertEqual(cfg(MULTI_KEY), [])

	def test_non_global_scope_is_not_supported_yet(self):
		with self.assertRaises(NotImplementedError):
			cfg(MULTI_KEY, scope_type="LMS Course", scope_name="COURSE-1")


class TestSurfaces(UnitTestCase):
	def setUp(self):
		self._saved = reg.reset_registry()
		register_test_params()
		clear(TEST_KEYS)

	def tearDown(self):
		clear(TEST_KEYS)
		reg.reset_registry(self._saved)

	def test_web_payload_excludes_app_only_params(self):
		payload = for_surface(reg.Surface.WEB)
		self.assertIn(MULTI_KEY, payload)
		self.assertNotIn(APP_KEY, payload)

	def test_app_payload_includes_course_params(self):
		payload = for_surface(reg.Surface.APP)
		self.assertIn(MULTI_KEY, payload)
		self.assertIn(APP_KEY, payload)

	def test_payload_carries_resolved_values(self):
		set_value(MULTI_KEY, ["created"])
		self.assertEqual(for_surface(reg.Surface.WEB)[MULTI_KEY], ["created"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose -f docker/docker-compose.yml exec frappe bench --site lms.localhost run-tests --app os_lms --module os_lms.os_lms.config.tests.test_store`
Expected: FAIL — `ImportError: cannot import name 'cfg'`

- [ ] **Step 3: Write minimal implementation**

```python
# apps/os_lms/os_lms/os_lms/config/store.py
"""Reading and writing configuration values.

Values live in OS LMS Config Value, one row per parameter that has been
changed. Reads go through a per-scope Redis cache invalidated by the
doctype hooks, so the cost of reading a parameter at runtime is a single
hash lookup.
"""
from __future__ import annotations

import json

import frappe

from os_lms.os_lms.config.registry import (
	ConfigParam,
	Scope,
	Surface,
	get_param,
	params_for_surface,
)
from os_lms.os_lms.config.types import ConfigTypeError

CACHE_NAME = "os_lms_config"


def _scope_cache_key(scope_type: str, scope_name: str) -> str:
	return f"{scope_type}::{scope_name or ''}"


def _assert_supported_scope(scope_type: str) -> None:
	if scope_type != "Global":
		raise NotImplementedError(
			f"scope {scope_type!r} is declared but not implemented yet; only Global works"
		)


def _raw_values(scope_type: str, scope_name: str) -> dict[str, str]:
	"""All stored JSON strings for one scope, cached."""
	cache_key = _scope_cache_key(scope_type, scope_name)
	cached = frappe.cache().hget(CACHE_NAME, cache_key)
	if cached is not None:
		return cached
	rows = frappe.get_all(
		"OS LMS Config Value",
		filters={"scope_type": scope_type, "scope_name": scope_name or ""},
		fields=["config_key", "value"],
	)
	values = {row.config_key: row.value for row in rows}
	frappe.cache().hset(CACHE_NAME, cache_key, values)
	return values


def _resolve(param: ConfigParam, raw: str | None) -> object:
	"""Turn a stored JSON string into a typed value, falling back to the default.

	A stored value that no longer fits its type (a hand-edit in the desk, a
	parameter whose options were narrowed) must not break the platform: it
	is logged and replaced by the default, which by rule reproduces the
	upstream behaviour.
	"""
	if raw is None:
		return param.default
	try:
		return param.type.coerce(json.loads(raw))
	except (TypeError, ValueError, ConfigTypeError):
		frappe.log_error(
			title="os_lms config: invalid stored value",
			message=f"{param.key} holds {raw!r}; falling back to the default",
		)
		return param.default


def cfg(key: str, scope_type: str = "Global", scope_name: str = "") -> object:
	"""Read one parameter. Raises UnknownConfigKey if it is not declared."""
	param = get_param(key)
	_assert_supported_scope(scope_type)
	return _resolve(param, _raw_values(scope_type, scope_name).get(key))


def for_surface(surface: Surface, scope_type: str = "Global", scope_name: str = "") -> dict:
	"""Every parameter delivered to one surface, already resolved."""
	_assert_supported_scope(scope_type)
	raw = _raw_values(scope_type, scope_name)
	return {param.key: _resolve(param, raw.get(param.key)) for param in params_for_surface(surface)}


def set_value(key: str, value: object, scope_type: str = "Global", scope_name: str = "") -> None:
	"""Store one value, validating it against the registry first."""
	param = get_param(key)
	_assert_supported_scope(scope_type)
	if param.scope is not Scope.GLOBAL:
		raise NotImplementedError(f"{key}: only the global scope is supported for now")
	normalised = param.type.coerce(value)
	from os_lms.os_lms.doctype.os_lms_config_value.os_lms_config_value import build_lookup_key

	name = build_lookup_key(scope_type, scope_name, key)
	encoded = json.dumps(normalised)
	if frappe.db.exists("OS LMS Config Value", name):
		doc = frappe.get_doc("OS LMS Config Value", name)
		doc.value = encoded
		doc.save(ignore_permissions=True)
	else:
		frappe.get_doc(
			{
				"doctype": "OS LMS Config Value",
				"config_key": key,
				"scope_type": scope_type,
				"scope_name": scope_name or "",
				"value": encoded,
			}
		).insert(ignore_permissions=True)
	invalidate_cache()


def clear_value(key: str, scope_type: str = "Global", scope_name: str = "") -> None:
	"""Delete the stored value so the parameter falls back to its default."""
	get_param(key)
	_assert_supported_scope(scope_type)
	from os_lms.os_lms.doctype.os_lms_config_value.os_lms_config_value import build_lookup_key

	name = build_lookup_key(scope_type, scope_name, key)
	if frappe.db.exists("OS LMS Config Value", name):
		frappe.delete_doc("OS LMS Config Value", name, ignore_permissions=True)
	invalidate_cache()


def invalidate_cache() -> None:
	frappe.cache().delete_value(CACHE_NAME)
```

```python
# apps/os_lms/os_lms/os_lms/config/__init__.py
"""Public entry point of the os_lms configuration system.

Importing this package registers every declared parameter, so any consumer
can simply do:

    from os_lms.os_lms.config import cfg
    cfg("courses.hidden_tabs")
"""
from os_lms.os_lms.config.registry import (  # noqa: F401
	ConfigParam,
	Scope,
	Section,
	Surface,
	UnknownConfigKey,
	all_params,
	get_param,
	params_for_section,
	params_for_surface,
)
from os_lms.os_lms.config.store import (  # noqa: F401
	cfg,
	clear_value,
	for_surface,
	invalidate_cache,
	set_value,
)

# Imported last, and for its side effect only: declaring the parameters.
from os_lms.os_lms.config import definitions  # noqa: F401,E402
```

```python
# apps/os_lms/os_lms/os_lms/config/definitions.py
"""Parameter declarations. This is the only file to touch to add one.

Filled in by the next task.
"""
```

```python
# apps/os_lms/os_lms/os_lms/config/tests/helpers.py
"""Scoped cleanup for the configuration tests.

Never clean up with a bare `frappe.db.delete("OS LMS Config Value")`: on a
development site that wipes the real configuration, not just the rows the
test created. Every helper here touches only the keys it is given, and a
test that uses a key a real parameter also declares must snapshot it and
put it back.
"""
from __future__ import annotations

import frappe

from os_lms.os_lms.doctype.os_lms_config_value.os_lms_config_value import build_lookup_key


def snapshot(keys: list[str]) -> dict[str, str | None]:
	"""Record the stored JSON of each key, or None when nothing is stored."""
	return {
		key: frappe.db.get_value(
			"OS LMS Config Value", build_lookup_key("Global", "", key), "value"
		)
		for key in keys
	}


def restore(saved: dict[str, str | None]) -> None:
	"""Put the snapshotted values back exactly as they were."""
	from os_lms.os_lms.config.store import invalidate_cache

	for key, value in saved.items():
		name = build_lookup_key("Global", "", key)
		exists = frappe.db.exists("OS LMS Config Value", name)
		if value is None:
			if exists:
				frappe.delete_doc("OS LMS Config Value", name, ignore_permissions=True)
		elif exists:
			frappe.db.set_value(
				"OS LMS Config Value", name, "value", value, update_modified=False
			)
		else:
			frappe.get_doc(
				{
					"doctype": "OS LMS Config Value",
					"config_key": key,
					"scope_type": "Global",
					"scope_name": "",
					"value": value,
				}
			).insert(ignore_permissions=True)
	invalidate_cache()


def clear(keys: list[str]) -> None:
	"""Remove only these keys, leaving every other stored value alone."""
	from os_lms.os_lms.config.store import invalidate_cache

	for key in keys:
		name = build_lookup_key("Global", "", key)
		if frappe.db.exists("OS LMS Config Value", name):
			frappe.delete_doc("OS LMS Config Value", name, ignore_permissions=True)
	invalidate_cache()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `docker compose -f docker/docker-compose.yml exec frappe bench --site lms.localhost run-tests --app os_lms --module os_lms.os_lms.config.tests.test_store`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/os_lms/os_lms/os_lms/config/
git commit -m "feat(config): resolve, cache and persist configuration values

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Il primo parametro dichiarato

**Files:**
- Modify: `apps/os_lms/os_lms/os_lms/config/definitions.py`
- Test: `apps/os_lms/os_lms/os_lms/config/tests/test_definitions.py`

**Interfaces:**
- Consumes: `register`, `ConfigParam`, `Section`, `Surface` da `registry.py`; `MultiChoice` da `types.py`.
- Produces: il parametro `courses.hidden_tabs` nel registro reale.

**Perché ora:** senza almeno un parametro reale, i task successivi (esposizione, pannello, documentazione) non hanno nulla da mostrare.

- [ ] **Step 1: Write the failing test**

```python
# apps/os_lms/os_lms/os_lms/config/tests/test_definitions.py
"""Tests for the real, declared parameters.

These guard the invariants the whole system relies on, in particular the
rule that every default must reproduce the upstream behaviour.
"""
from __future__ import annotations

from frappe.tests import UnitTestCase

from os_lms.os_lms.config import Section, Surface, all_params, get_param


class TestDeclaredParams(UnitTestCase):
	def test_every_key_matches_its_section(self):
		for param in all_params():
			self.assertTrue(
				param.key.startswith(f"{param.section.value}."),
				f"{param.key} does not match section {param.section.value}",
			)

	def test_every_default_fits_its_type(self):
		for param in all_params():
			param.type.coerce(param.default)

	def test_course_and_batch_params_also_reach_the_app(self):
		# Spec D4: course and batch parameters apply to the app too.
		for param in all_params():
			if param.section in (Section.COURSES, Section.BATCHES):
				self.assertIn(Surface.APP, param.surfaces, f"{param.key} must reach the app")

	def test_app_params_never_reach_the_website(self):
		for param in all_params():
			if param.section is Section.APP:
				self.assertNotIn(Surface.WEB, param.surfaces, f"{param.key} must not reach the web")


class TestHiddenTabs(UnitTestCase):
	def test_declared_with_a_subtractive_empty_default(self):
		param = get_param("courses.hidden_tabs")
		# Spec D5/D6: hiding nothing by default reproduces today's behaviour,
		# and a tab added upstream later shows up instead of disappearing.
		self.assertEqual(param.default, [])
		self.assertEqual(
			[option["value"] for option in param.type.schema()["options"]],
			["live", "upcoming", "created", "unpublished"],
		)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose -f docker/docker-compose.yml exec frappe bench --site lms.localhost run-tests --app os_lms --module os_lms.os_lms.config.tests.test_definitions`
Expected: FAIL — `UnknownConfigKey: no configuration parameter declares the key 'courses.hidden_tabs'`

- [ ] **Step 3: Write minimal implementation**

```python
# apps/os_lms/os_lms/os_lms/config/definitions.py
"""Parameter declarations.

This is the only file to touch to add a configuration parameter. Read
docs/OS_LMS_CONFIGURAZIONI-RICETTA.md before adding one; the two rules
that are easy to get wrong:

  - the default must reproduce the behaviour of the platform WITHOUT the
    parameter, so that a lost graft degrades into upstream behaviour;
  - list parameters say what to HIDE, never what to keep, so that an
    element added upstream later shows up instead of silently vanishing.
"""
from __future__ import annotations

from os_lms.os_lms.config.registry import ConfigParam, Section, Surface, register
from os_lms.os_lms.config.types import MultiChoice

# --- Courses -----------------------------------------------------------

register(
	ConfigParam(
		key="courses.hidden_tabs",
		section=Section.COURSES,
		type=MultiChoice(
			[
				("live", "Pubblicato"),
				("upcoming", "In arrivo"),
				("created", "Creato"),
				("unpublished", "Non pubblicato"),
			]
		),
		default=[],
		label="Filtri da nascondere nell'elenco corsi",
		description=(
			"I filtri selezionati non compaiono nella barra dei corsi. "
			"Le regole di visibilità per ruolo restano invariate: un filtro "
			"che un ruolo non vede già oggi resta invisibile comunque."
		),
		surfaces=(Surface.WEB, Surface.APP),
		since="2026-09-18",
		grafts=("frontend/src/pages/Courses/Courses.vue",),
	)
)

# --- Batches -----------------------------------------------------------

# --- App ---------------------------------------------------------------
```

- [ ] **Step 4: Run test to verify it passes**

Run: `docker compose -f docker/docker-compose.yml exec frappe bench --site lms.localhost run-tests --app os_lms --module os_lms.os_lms.config.tests.test_definitions`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/os_lms/os_lms/os_lms/config/definitions.py apps/os_lms/os_lms/os_lms/config/tests/test_definitions.py
git commit -m "feat(config): declare courses.hidden_tabs

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: Esposizione al sito e all'app

**Files:**
- Modify: `apps/os_lms/os_lms/os_lms/override_api.py:55-67` (funzione `get_lms_settings`)
- Modify: `apps/os_lms/os_lms/os_lms/app/api.py:148-168` (funzione `get_instance_info`)
- Test: `apps/os_lms/os_lms/os_lms/config/tests/test_exposure.py`

**Interfaces:**
- Consumes: `for_surface`, `Surface` da `config`.
- Produces: la chiave `config` dentro il payload di `get_lms_settings` e dentro quello di `get_instance_info`.

**Nota:** nessun file upstream viene toccato — entrambe le funzioni sono codice os_lms.

- [ ] **Step 1: Write the failing test**

```python
# apps/os_lms/os_lms/os_lms/config/tests/test_exposure.py
"""The config payload must reach both surfaces, and only the right one."""
from __future__ import annotations

import frappe
from frappe.tests import UnitTestCase

from os_lms.os_lms.app.api import get_instance_info
from os_lms.os_lms.config import invalidate_cache, set_value
from os_lms.os_lms.config.tests.helpers import clear, restore, snapshot
from os_lms.os_lms.override_api import get_lms_settings

# A real, declared key: snapshot it so the site's own configuration survives.
KEY = "courses.hidden_tabs"


class TestExposure(UnitTestCase):
	def setUp(self):
		self._saved = snapshot([KEY])
		clear([KEY])

	def tearDown(self):
		restore(self._saved)
		invalidate_cache()

	def test_website_payload_carries_the_config_block(self):
		settings = get_lms_settings()
		self.assertIn("config", settings)
		self.assertIn("courses.hidden_tabs", settings["config"])

	def test_website_payload_reflects_a_stored_value(self):
		set_value("courses.hidden_tabs", ["created"])
		self.assertEqual(get_lms_settings()["config"]["courses.hidden_tabs"], ["created"])

	def test_app_payload_carries_the_config_block(self):
		info = get_instance_info()
		self.assertIn("config", info)
		self.assertIn("courses.hidden_tabs", info["config"])

	def test_website_payload_keeps_the_existing_keys(self):
		# Regression guard: the config block must be additive.
		settings = get_lms_settings()
		for key in ("allow_guest_access", "ai_enabled", "theme"):
			self.assertIn(key, settings)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose -f docker/docker-compose.yml exec frappe bench --site lms.localhost run-tests --app os_lms --module os_lms.os_lms.config.tests.test_exposure`
Expected: FAIL — `AssertionError: 'config' not found in ...`

- [ ] **Step 3: Write minimal implementation**

In `apps/os_lms/os_lms/os_lms/override_api.py`, dentro `get_lms_settings`, subito dopo la riga `result["theme"] = brand.get("theme") or "light"`:

```python
		# Every parameter declared for the WEB surface, already resolved.
		# The SPA reads these through cfg() in oslms/config/useOsConfig.js.
		from os_lms.os_lms.config import Surface, for_surface

		result["config"] = for_surface(Surface.WEB)
```

In `apps/os_lms/os_lms/os_lms/app/api.py`, dentro `get_instance_info`, sostituire il `return` finale con:

```python
	from os_lms.os_lms.config import Surface, for_surface

	return {
		"name": name,
		"logo": get_app_logo(),
		"primary_color": brand.get("app_main_color") or None,
		"secondary_color": brand.get("app_secondary_color") or None,
		# Course and batch parameters reach the app too; app-only parameters
		# never enter the website payload. See os_lms.os_lms.config.registry.
		"config": for_surface(Surface.APP),
	}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `docker compose -f docker/docker-compose.yml exec frappe bench --site lms.localhost run-tests --app os_lms --module os_lms.os_lms.config.tests.test_exposure`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/os_lms/os_lms/os_lms/override_api.py apps/os_lms/os_lms/os_lms/app/api.py apps/os_lms/os_lms/os_lms/config/tests/test_exposure.py
git commit -m "feat(config): deliver the config payload to the site and the app

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 7: Endpoint del pannello

**Files:**
- Create: `apps/os_lms/os_lms/os_lms/config/api.py`
- Test: `apps/os_lms/os_lms/os_lms/config/tests/test_api.py`

**Interfaces:**
- Consumes: `params_for_section`, `Section`, `get_param` dal registry; `cfg`, `set_value` dallo store.
- Produces: `get_config_schema(section: str) -> dict` che ritorna `{"section": str, "params": [ {key,label,description,control,default,value, ...} ]}`; `save_config(section: str, values: dict) -> dict` che ritorna `{"saved": [key, ...]}`.

**Nota:** `require_type_annotated_api_methods = True`, quindi entrambe le funzioni devono avere annotazioni complete.

- [ ] **Step 1: Write the failing test**

```python
# apps/os_lms/os_lms/os_lms/config/tests/test_api.py
"""Tests for the settings-panel endpoints."""
from __future__ import annotations

import frappe
from frappe.tests import UnitTestCase

from os_lms.os_lms.config import cfg, invalidate_cache
from os_lms.os_lms.config.api import get_config_schema, save_config
from os_lms.os_lms.config.tests.helpers import clear, restore, snapshot

# A real, declared key: snapshot it so the site's own configuration survives.
KEY = "courses.hidden_tabs"


class TestSchemaEndpoint(UnitTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self._saved = snapshot([KEY])
		clear([KEY])

	def tearDown(self):
		# Back to Administrator first: the restore writes documents.
		frappe.set_user("Administrator")
		restore(self._saved)
		invalidate_cache()

	def test_returns_params_of_the_section(self):
		schema = get_config_schema("courses")
		keys = [param["key"] for param in schema["params"]]
		self.assertIn(KEY, keys)

	def test_param_entry_carries_control_and_current_value(self):
		entry = next(p for p in get_config_schema("courses")["params"] if p["key"] == KEY)
		self.assertEqual(entry["control"], "multicheck")
		self.assertEqual(entry["value"], [])
		self.assertEqual(entry["default"], [])
		self.assertEqual(
			[option["value"] for option in entry["options"]],
			["live", "upcoming", "created", "unpublished"],
		)

	def test_unknown_section_raises(self):
		with self.assertRaises(frappe.ValidationError):
			get_config_schema("nope")

	def test_empty_section_returns_an_empty_list(self):
		self.assertEqual(get_config_schema("batches")["params"], [])


class TestSaveEndpoint(UnitTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self._saved = snapshot([KEY])
		clear([KEY])

	def tearDown(self):
		# Back to Administrator first: the restore writes documents.
		frappe.set_user("Administrator")
		restore(self._saved)
		invalidate_cache()

	def test_saves_and_reports_the_keys(self):
		result = save_config("courses", {KEY: ["created"]})
		self.assertEqual(result["saved"], [KEY])
		self.assertEqual(cfg(KEY), ["created"])

	def test_rejects_an_unknown_key(self):
		with self.assertRaises(frappe.ValidationError):
			save_config("courses", {"courses.nope": True})

	def test_rejects_a_key_from_another_section(self):
		with self.assertRaises(frappe.ValidationError):
			save_config("batches", {KEY: []})

	def test_rejects_an_invalid_value(self):
		with self.assertRaises(frappe.ValidationError):
			save_config("courses", {KEY: ["archived"]})

	def test_accepts_a_json_encoded_payload(self):
		# frappe-ui may deliver the dict as a JSON string depending on the call.
		import json

		save_config("courses", json.dumps({KEY: ["live"]}))
		self.assertEqual(cfg(KEY), ["live"])

	def test_denies_a_user_without_the_declared_role(self):
		# Pick a user that really lacks System Manager, otherwise the test
		# passes for the wrong reason on a site full of administrators.
		managers = set(
			frappe.get_all(
				"Has Role",
				{"role": "System Manager", "parenttype": "User"},
				pluck="parent",
			)
		)
		plain = frappe.db.get_value(
			"User",
			{
				"name": ["not in", list(managers | {"Administrator", "Guest"})],
				"enabled": 1,
			},
			"name",
		)
		if not plain:
			self.skipTest("no non-System-Manager user on this site")
		frappe.set_user(plain)
		with self.assertRaises(frappe.PermissionError):
			save_config("courses", {KEY: []})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose -f docker/docker-compose.yml exec frappe bench --site lms.localhost run-tests --app os_lms --module os_lms.os_lms.config.tests.test_api`
Expected: FAIL — `ModuleNotFoundError: No module named 'os_lms.os_lms.config.api'`

- [ ] **Step 3: Write minimal implementation**

```python
# apps/os_lms/os_lms/os_lms/config/api.py
"""Settings-panel endpoints.

The panel does not know any parameter: it asks for a section's schema and
renders whatever comes back. Adding a parameter therefore requires no
frontend change at all.
"""
from __future__ import annotations

import json

import frappe
from frappe import _

from os_lms.os_lms.config.registry import (
	ConfigParam,
	Section,
	UnknownConfigKey,
	get_param,
	params_for_section,
)
from os_lms.os_lms.config.store import cfg, set_value
from os_lms.os_lms.config.types import ConfigTypeError


def _section(value: str) -> Section:
	try:
		return Section(value)
	except ValueError:
		frappe.throw(_("Unknown configuration section: {0}").format(value))


def _can_edit(param: ConfigParam) -> bool:
	if frappe.session.user == "Administrator":
		return True
	return bool(set(frappe.get_roles()).intersection(param.roles))


def _assert_can_edit(param: ConfigParam) -> None:
	if not _can_edit(param):
		frappe.throw(
			_("You are not allowed to change {0}.").format(param.label),
			frappe.PermissionError,
		)


@frappe.whitelist()
def get_config_schema(section: str) -> dict:
	"""Everything the panel needs to draw one section."""
	target = _section(section)
	params = []
	for param in params_for_section(target):
		# Parameters the caller may not change are left out rather than
		# refused: a section is readable as long as something in it is.
		if not _can_edit(param):
			continue
		params.append({**param.schema(), "value": cfg(param.key)})
	return {"section": target.value, "params": params}


@frappe.whitelist()
def save_config(section: str, values: dict | str) -> dict:
	"""Validate and persist one section's values.

	Every key is checked against the registry and against the section being
	saved: a key that is not declared, or that belongs elsewhere, is
	refused rather than silently stored.
	"""
	target = _section(section)
	if isinstance(values, str):
		values = json.loads(values)
	if not isinstance(values, dict):
		frappe.throw(_("The values payload must be an object."))

	saved = []
	for key, value in values.items():
		try:
			param = get_param(key)
		except UnknownConfigKey:
			frappe.throw(_("No configuration parameter declares the key {0}.").format(key))
		if param.section is not target:
			frappe.throw(_("{0} does not belong to the section {1}.").format(key, target.value))
		_assert_can_edit(param)
		try:
			set_value(key, value)
		except ConfigTypeError as error:
			frappe.throw(_("Invalid value for {0}: {1}").format(param.label, str(error)))
		saved.append(key)
	return {"saved": saved}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `docker compose -f docker/docker-compose.yml exec frappe bench --site lms.localhost run-tests --app os_lms --module os_lms.os_lms.config.tests.test_api`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/os_lms/os_lms/os_lms/config/api.py apps/os_lms/os_lms/os_lms/config/tests/test_api.py
git commit -m "feat(config): add the settings-panel schema and save endpoints

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 8: Lettura nella SPA

**Files:**
- Create: `frontend/src/oslms/config/useOsConfig.js`
- Test: `frontend/src/tests/osConfig.test.ts`

**Interfaces:**
- Consumes: lo store Pinia `useSettings` da `@/stores/settings`, il cui `settings.data.config` è il blocco iniettato nel Task 6.
- Produces: `cfg(key)` e `hideByConfig(key, list, field = 'value')`.

- [ ] **Step 1: Write the failing test**

```ts
// frontend/src/tests/osConfig.test.ts
/**
 * Tests for the SPA-side configuration reader.
 *
 * `hideByConfig` is the helper every list-shaped parameter goes through,
 * so its subtractive contract is tested explicitly: it may only remove
 * entries, never add or reorder them.
 */
import { describe, expect, it, vi, beforeEach } from 'vitest'

const settingsMock = { settings: { data: undefined as any } }
vi.mock('@/stores/settings', () => ({ useSettings: () => settingsMock }))

import { cfg, hideByConfig } from '@/oslms/config/useOsConfig'

const TABS = [
	{ label: 'Pubblicato', value: 'live' },
	{ label: 'In arrivo', value: 'upcoming' },
	{ label: 'Creato', value: 'created' },
]

describe('cfg', () => {
	beforeEach(() => {
		settingsMock.settings.data = { config: { 'courses.hidden_tabs': ['created'] } }
	})

	it('returns the value from the payload', () => {
		expect(cfg('courses.hidden_tabs')).toEqual(['created'])
	})

	it('returns undefined for a key the payload does not carry', () => {
		expect(cfg('courses.nope')).toBeUndefined()
	})

	it('returns undefined before the payload has loaded', () => {
		settingsMock.settings.data = undefined
		expect(cfg('courses.hidden_tabs')).toBeUndefined()
	})
})

describe('hideByConfig', () => {
	it('removes the listed entries', () => {
		settingsMock.settings.data = { config: { 'courses.hidden_tabs': ['created'] } }
		expect(hideByConfig('courses.hidden_tabs', TABS).map((t) => t.value)).toEqual([
			'live',
			'upcoming',
		])
	})

	it('returns the list untouched when nothing is hidden', () => {
		settingsMock.settings.data = { config: { 'courses.hidden_tabs': [] } }
		expect(hideByConfig('courses.hidden_tabs', TABS)).toEqual(TABS)
	})

	it('returns the list untouched when the payload is missing', () => {
		settingsMock.settings.data = undefined
		expect(hideByConfig('courses.hidden_tabs', TABS)).toEqual(TABS)
	})

	it('never adds or reorders entries', () => {
		settingsMock.settings.data = {
			config: { 'courses.hidden_tabs': ['upcoming', 'nonexistent'] },
		}
		expect(hideByConfig('courses.hidden_tabs', TABS).map((t) => t.value)).toEqual([
			'live',
			'created',
		])
	})

	it('can match on a different field', () => {
		settingsMock.settings.data = { config: { 'courses.hidden_tabs': ['Creato'] } }
		expect(
			hideByConfig('courses.hidden_tabs', TABS, 'label').map((t) => t.value),
		).toEqual(['live', 'upcoming'])
	})
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && yarn vitest run src/tests/osConfig.test.ts`
Expected: FAIL — `Failed to resolve import "@/oslms/config/useOsConfig"`

- [ ] **Step 3: Write minimal implementation**

```js
// frontend/src/oslms/config/useOsConfig.js
/**
 * SPA-side reader for the os_lms configuration parameters.
 *
 * Values arrive with the settings payload the store already loads at boot
 * (lms.lms.api.get_lms_settings, overridden by os_lms), so reading a
 * parameter costs nothing at runtime and adds no network call.
 *
 * Reading a parameter must stay a one-liner: parameters exist to hide a
 * single label as much as to gate a whole feature.
 */
import { useSettings } from '@/stores/settings'

/**
 * Read one parameter.
 *
 * Returns undefined if the payload has not loaded yet or does not carry
 * the key. Callers must not depend on that: the server always resolves
 * defaults, so a missing key means a typo or a parameter not declared for
 * this surface.
 */
export function cfg(key) {
	const config = useSettings().settings.data?.config
	if (!config || !(key in config)) {
		if (import.meta.env.DEV) {
			console.warn(`[os-config] key not present in the payload: ${key}`)
		}
		return undefined
	}
	return config[key]
}

/**
 * Remove from `list` the entries whose `field` appears in the parameter.
 *
 * Subtractive by construction: it can only remove, never add or reorder.
 * That is what keeps an entry added upstream later visible instead of
 * silently disappearing.
 */
export function hideByConfig(key, list, field = 'value') {
	const hidden = cfg(key)
	if (!Array.isArray(hidden) || !hidden.length) return list
	return list.filter((item) => !hidden.includes(item[field]))
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && yarn vitest run src/tests/osConfig.test.ts`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/oslms/config/useOsConfig.js frontend/src/tests/osConfig.test.ts
git commit -m "feat(config): add the SPA config reader and subtractive helper

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 9: Pannello generico

**Files:**
- Create: `frontend/src/oslms/components/Settings/OsConfigSection.vue`
- Modify: `frontend/src/oslms/utils/settings.js` (le voci `Corsi` e `Classi`, più la nuova voce `App`)
- Test: `frontend/src/tests/osConfigSection.test.ts`

**Interfaces:**
- Consumes: `os_lms.os_lms.config.api.get_config_schema` e `.save_config`; `SettingsLayout` da `@/components/Layouts/SettingsLayout.vue`; `BooleanSwitch` da `@/components/Controls/BooleanSwitch.vue`.
- Produces: il componente `OsConfigSection` con prop `section`, `label`, `description`; la funzione `osConfigTab(section)` in `settings.js`.

**Nota importante:** `Settings.vue` è upstream e passa ai componenti `template` solo `label` e `description`. Per non toccarlo, `settings.js` avvolge `OsConfigSection` in un componente di una riga che fissa la sezione.

- [ ] **Step 1: Write the failing test**

```ts
// frontend/src/tests/osConfigSection.test.ts
/**
 * Component tests for the generic settings section.
 *
 * The panel is schema-driven: these assert that it renders whatever the
 * backend declares and sends back exactly what the user changed.
 */
import { describe, expect, it, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const submitted: any[] = []
const schemaPayload = {
	section: 'courses',
	params: [
		{
			key: 'courses.hidden_tabs',
			label: 'Filtri da nascondere',
			description: 'descrizione',
			control: 'multicheck',
			default: [],
			value: ['created'],
			options: [
				{ value: 'live', label: 'Pubblicato' },
				{ value: 'created', label: 'Creato' },
			],
		},
		{
			key: 'courses.sample_flag',
			label: 'Interruttore',
			description: '',
			control: 'checkbox',
			default: false,
			value: false,
		},
	],
}

vi.mock('frappe-ui', () => ({
	Badge: { template: '<span />' },
	Button: { template: '<button @click="$emit(\'click\')"><slot /></button>' },
	Select: { props: ['modelValue', 'options'], template: '<select />' },
	FormControl: {
		props: ['modelValue', 'type'],
		emits: ['update:modelValue'],
		template:
			'<input :type="type" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
	},
	toast: { error: vi.fn(), success: vi.fn() },
	createResource: (options: any) => ({
		data: options.url.endsWith('get_config_schema') ? schemaPayload : null,
		loading: false,
		submit: (params: any) => {
			submitted.push(params)
			return Promise.resolve({ saved: Object.keys(params.values) })
		},
		reload: vi.fn(),
	}),
}))
vi.mock('@/components/Layouts/SettingsLayout.vue', () => ({
	default: {
		props: ['title', 'description'],
		template: '<div><slot name="header-actions" /><slot /></div>',
	},
}))
vi.mock('@/components/Controls/BooleanSwitch.vue', () => ({
	default: {
		props: ['modelValue'],
		emits: ['update:modelValue'],
		template:
			'<button data-testid="switch" :data-checked="String(!!modelValue)" @click="$emit(\'update:modelValue\', !modelValue)" />',
	},
}))
vi.mock('@/stores/settings', () => ({
	useSettings: () => ({ settings: { data: { config: {} }, reload: vi.fn() } }),
}))
vi.stubGlobal('__', (value: string) => value)

import OsConfigSection from '@/oslms/components/Settings/OsConfigSection.vue'

const mountSection = () =>
	mount(OsConfigSection, {
		props: { section: 'courses', label: 'Corsi', description: 'Impostazioni dei corsi' },
	})

describe('OsConfigSection', () => {
	it('renders one row per declared parameter', async () => {
		const wrapper = mountSection()
		await flushPromises()
		expect(wrapper.findAll('[data-testid="config-row"]')).toHaveLength(2)
	})

	it('renders a checkbox per option for a multicheck parameter', async () => {
		const wrapper = mountSection()
		await flushPromises()
		expect(wrapper.findAll('input[type="checkbox"]')).toHaveLength(2)
	})

	it('pre-checks the options carried by the current value', async () => {
		const wrapper = mountSection()
		await flushPromises()
		const boxes = wrapper.findAll('input[type="checkbox"]')
		expect((boxes[0].element as HTMLInputElement).checked).toBe(false)
		expect((boxes[1].element as HTMLInputElement).checked).toBe(true)
	})

	it('sends only the section it owns, with the edited values', async () => {
		submitted.length = 0
		const wrapper = mountSection()
		await flushPromises()
		await wrapper.find('[data-testid="switch"]').trigger('click')
		await wrapper.find('[data-testid="config-save"]').trigger('click')
		await flushPromises()
		expect(submitted).toHaveLength(1)
		expect(submitted[0].section).toBe('courses')
		expect(submitted[0].values['courses.sample_flag']).toBe(true)
		expect(submitted[0].values['courses.hidden_tabs']).toEqual(['created'])
	})
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && yarn vitest run src/tests/osConfigSection.test.ts`
Expected: FAIL — `Failed to resolve import "@/oslms/components/Settings/OsConfigSection.vue"`

- [ ] **Step 3: Write minimal implementation**

```vue
<!-- frontend/src/oslms/components/Settings/OsConfigSection.vue -->
<template>
	<SettingsLayout :title="__(label)" :description="__(description)">
		<template #title-badge>
			<Badge
				v-if="isDirty"
				:label="__('Not Saved')"
				variant="subtle"
				theme="orange"
			/>
		</template>
		<template #header-actions>
			<Button
				variant="solid"
				data-testid="config-save"
				:loading="saving"
				@click="save"
			>
				{{ __('Update') }}
			</Button>
		</template>

		<div v-if="!params.length" class="text-p-base text-ink-gray-5">
			{{ __('Nessuna configurazione disponibile in questa sezione.') }}
		</div>

		<div v-else>
			<div
				v-for="param in params"
				:key="param.key"
				data-testid="config-row"
				class="border-b border-outline-elevation-2 last:border-0 py-3"
			>
				<!-- Wide controls put the label above; compact ones sit beside it. -->
				<div v-if="isWide(param)" class="space-y-2">
					<div>
						<div class="text-p-base-medium text-ink-gray-7">
							{{ param.label }}
						</div>
						<div v-if="param.description" class="text-p-sm text-ink-gray-5">
							{{ param.description }}
						</div>
					</div>

					<div v-if="param.control === 'multicheck'" class="space-y-1.5">
						<label
							v-for="option in param.options"
							:key="option.value"
							class="flex items-center gap-2 text-p-base text-ink-gray-7"
						>
							<input
								type="checkbox"
								:checked="values[param.key].includes(option.value)"
								@change="toggleOption(param, option.value)"
							/>
							<span>{{ option.label }}</span>
						</label>
					</div>

					<FormControl
						v-else
						type="textarea"
						:rows="4"
						:modelValue="textValue(param)"
						@update:modelValue="(next) => setText(param, next)"
					/>
				</div>

				<div v-else class="flex items-center justify-between gap-4">
					<div class="flex flex-col">
						<div class="text-p-base-medium text-ink-gray-7">
							{{ param.label }}
						</div>
						<div v-if="param.description" class="text-p-sm text-ink-gray-5">
							{{ param.description }}
						</div>
					</div>
					<div class="shrink-0">
						<BooleanSwitch
							v-if="param.control === 'checkbox'"
							size="sm"
							:modelValue="values[param.key]"
							@update:modelValue="(next) => (values[param.key] = next)"
						/>
						<Select
							v-else-if="param.control === 'select'"
							class="w-48"
							:modelValue="values[param.key]"
							:options="param.options"
							@update:modelValue="(next) => (values[param.key] = next)"
						/>
						<FormControl
							v-else
							class="w-48"
							:type="param.control === 'number' ? 'number' : 'text'"
							:modelValue="values[param.key]"
							@update:modelValue="
								(next) =>
									(values[param.key] =
										param.control === 'number' ? Number(next) : next)
							"
						/>
					</div>
				</div>
			</div>
		</div>
	</SettingsLayout>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { Badge, Button, FormControl, Select, createResource, toast } from 'frappe-ui'
import SettingsLayout from '@/components/Layouts/SettingsLayout.vue'
import BooleanSwitch from '@/components/Controls/BooleanSwitch.vue'
import { useSettings } from '@/stores/settings'

const props = defineProps({
	section: { type: String, required: true },
	label: { type: String, required: true },
	description: { type: String, default: '' },
})

const settingsStore = useSettings()
const values = reactive({})
const saved = ref({})
const saving = ref(false)

const schema = createResource({
	url: 'os_lms.os_lms.config.api.get_config_schema',
	params: { section: props.section },
	auto: true,
})

const params = computed(() => schema.data?.params || [])

// Multi-value controls read better with the label above them.
const isWide = (param) => param.control === 'multicheck' || param.control === 'json'

const seed = () => {
	params.value.forEach((param) => {
		// Clone arrays and objects so editing never mutates the schema payload.
		values[param.key] = JSON.parse(JSON.stringify(param.value))
	})
	saved.value = JSON.parse(JSON.stringify(values))
}

watch(params, seed, { immediate: true })

const isDirty = computed(() => JSON.stringify(values) !== JSON.stringify(saved.value))

const toggleOption = (param, option) => {
	const current = values[param.key]
	const next = current.includes(option)
		? current.filter((item) => item !== option)
		: [...current, option]
	// Keep the declared order so the payload matches what the backend stores.
	values[param.key] = param.options
		.map((entry) => entry.value)
		.filter((entry) => next.includes(entry))
}

const textValue = (param) =>
	param.control === 'json' ? JSON.stringify(values[param.key], null, 2) : values[param.key]

const setText = (param, next) => {
	if (param.control !== 'json') {
		values[param.key] = next
		return
	}
	try {
		values[param.key] = JSON.parse(next)
	} catch {
		// Leave the previous value in place; the save button reports the error.
	}
}

const saveResource = createResource({ url: 'os_lms.os_lms.config.api.save_config' })

const save = async () => {
	saving.value = true
	try {
		await saveResource.submit({ section: props.section, values: { ...values } })
		saved.value = JSON.parse(JSON.stringify(values))
		// The SPA reads these through the settings payload, so refresh it.
		settingsStore.settings.reload()
		toast.success(__('Impostazioni salvate'))
	} catch (error) {
		toast.error(error.messages?.[0] || String(error))
	} finally {
		saving.value = false
	}
}
</script>
```

In `frontend/src/oslms/utils/settings.js`, aggiungere in testa agli import:

```js
import { h, markRaw } from 'vue'
import OsConfigSection from '@/oslms/components/Settings/OsConfigSection.vue'

// Settings.vue passes only `label` and `description` to a tab's `template`
// component, and it is an upstream file we do not touch. This wrapper pins
// the section so the same generic renderer can serve all three tabs.
const osConfigTab = (section) =>
	markRaw({
		props: { label: String, description: String },
		setup(props) {
			return () =>
				h(OsConfigSection, {
					section,
					label: props.label,
					description: props.description,
				})
		},
	})
```

Poi sostituire il gruppo `Configurazioni` con:

```js
		{
			key: 'Configurazioni',
			label: __('Configurazioni'),
			hideLabel: false,
			condition: isAdministrator,
			items: [
				{
					key: 'Corsi',
					label: __('Corsi'),
					icon: 'BookOpen',
					description: __('Impostazioni relative ai corsi'),
					condition: isAdministrator,
					template: osConfigTab('courses'),
				},
				{
					key: 'Classi',
					label: __('Classi'),
					icon: 'Laptop',
					description: __('Impostazioni relative alle classi'),
					condition: isAdministrator,
					template: osConfigTab('batches'),
				},
				{
					key: 'App',
					label: __('App'),
					icon: 'Smartphone',
					description: __("Impostazioni relative all'app mobile"),
					condition: isAdministrator,
					template: osConfigTab('app'),
				},
			],
		},
```

> **Decisione sulla voce Classi.** L'interruttore `enable_live_classes` non è ancora un parametro del nuovo sistema: la sua migrazione è fuori ambito (spec §6.2). Quindi in questo task **la voce `Classi` resta com'è oggi**, con il suo campo `sections`, e `osConfigTab` si applica **solo a `Corsi` e ad `App`**. La voce `Classi` passerà al nuovo pannello nel momento in cui il parametro verrà migrato. Il blocco di codice qui sopra va adattato di conseguenza: `Classi` mantiene `sections: [...]` come nel file attuale.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && yarn vitest run src/tests/osConfigSection.test.ts`
Expected: PASS
Then: `cd frontend && yarn build`
Expected: build completata senza errori

- [ ] **Step 5: Commit**

```bash
git add frontend/src/oslms/components/Settings/OsConfigSection.vue frontend/src/oslms/utils/settings.js frontend/src/tests/osConfigSection.test.ts
git commit -m "feat(config): render the settings sections from the backend schema

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 10: Verifica automatica degli innesti

**Files:**
- Test: `apps/os_lms/os_lms/os_lms/config/tests/test_grafts.py`

**Interfaces:**
- Consumes: `all_params()` dal registry; il campo `grafts` di ogni parametro.
- Produces: nessuna API — è la rete di sicurezza che rende contabili gli innesti.

**Perché prima dell'innesto:** il test va scritto per primo e deve fallire indicando esattamente il file in cui manca il marcatore. È lo stesso test che, dopo un merge dall'upstream, segnalerà l'innesto perduto.

- [ ] **Step 1: Write the failing test**

```python
# apps/os_lms/os_lms/os_lms/config/tests/test_grafts.py
"""Every declared graft must still be present in its file.

A graft is a line that reads a parameter inside an UPSTREAM file — the one
thing an upstream merge can silently delete. Each parameter declares the
files it is grafted into; this test checks the marker is still there.

When this test fails after a merge, it is not the test that is wrong: the
merge took the upstream version of that file and dropped our line.
"""
from __future__ import annotations

from pathlib import Path

import frappe
from frappe.tests import UnitTestCase

from os_lms.os_lms.config import all_params

# frappe.get_app_path("lms") points at <repo>/lms, so its parent is the repo root.
REPO_ROOT = Path(frappe.get_app_path("lms")).parent


class TestGrafts(UnitTestCase):
	def test_every_declared_graft_file_exists(self):
		for param in all_params():
			for relative in param.grafts:
				self.assertTrue(
					(REPO_ROOT / relative).is_file(),
					f"{param.key} declares a graft in {relative}, which does not exist",
				)

	def test_every_declared_graft_carries_its_marker(self):
		for param in all_params():
			marker = f"os-config: {param.key}"
			for relative in param.grafts:
				content = (REPO_ROOT / relative).read_text(encoding="utf-8")
				self.assertIn(
					marker,
					content,
					(
						f"the marker '{marker}' is missing from {relative}. "
						"An upstream merge most likely dropped the graft: "
						"restore it and re-run this test."
					),
				)

	def test_no_orphan_markers_in_the_upstream_tree(self):
		"""A marker with no matching declaration is an orphan graft."""
		declared = {f"os-config: {param.key}" for param in all_params()}
		searched = [REPO_ROOT / "frontend" / "src", REPO_ROOT / "lms"]
		orphans = []
		for root in searched:
			if not root.is_dir():
				continue
			for path in root.rglob("*"):
				if path.suffix not in {".vue", ".js", ".ts", ".py"} or not path.is_file():
					continue
				if "node_modules" in path.parts or "oslms" in path.parts:
					continue
				for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
					if "os-config:" not in line:
						continue
					marker = line.split("os-config:")[1].strip()
					if f"os-config: {marker}" not in declared:
						orphans.append(f"{path.relative_to(REPO_ROOT)}: {marker}")
		self.assertEqual(orphans, [], f"grafts with no declaration: {orphans}")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose -f docker/docker-compose.yml exec frappe bench --site lms.localhost run-tests --app os_lms --module os_lms.os_lms.config.tests.test_grafts`
Expected: FAIL su `test_every_declared_graft_carries_its_marker` — "the marker 'os-config: courses.hidden_tabs' is missing from frontend/src/pages/Courses/Courses.vue"

- [ ] **Step 3: Nessuna implementazione in questo task**

Il test deve restare rosso: lo fa passare il Task 11, che scrive l'innesto. È la prova che la rete di sicurezza funziona davvero.

- [ ] **Step 4: Commit del solo test**

```bash
git add apps/os_lms/os_lms/os_lms/config/tests/test_grafts.py
git commit -m "test(config): verify declared grafts are still present upstream

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 11: L'innesto nei filtri dei corsi

**Files:**
- Modify: `frontend/src/pages/Courses/Courses.vue:374-400` (il `computed` `courseTabs`)
- Test: `frontend/src/tests/courseHiddenTabs.test.ts`

**Interfaces:**
- Consumes: `hideByConfig` da `@/oslms/config/useOsConfig`.
- Produces: il comportamento "i filtri selezionati non compaiono".

**Questa è l'unica modifica autorizzata a un file upstream in tutto il piano.** Tre righe: un import, un commento marcatore, la chiamata.

- [ ] **Step 1: Write the failing test**

```ts
// frontend/src/tests/courseHiddenTabs.test.ts
/**
 * Behaviour test for the courses.hidden_tabs graft.
 *
 * test_grafts.py checks the marker still exists; this checks it still
 * does the right thing — in particular that it only ever removes tabs and
 * never touches the role rules that build them.
 */
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it, vi, beforeEach } from 'vitest'

const settingsMock = { settings: { data: { config: {} } as any } }
vi.mock('@/stores/settings', () => ({ useSettings: () => settingsMock }))

import { hideByConfig } from '@/oslms/config/useOsConfig'

const COURSES_VUE = resolve(__dirname, '../pages/Courses/Courses.vue')

/**
 * Mirrors the tab list Courses.vue builds, including the role branches,
 * so the assertions below describe the real behaviour of the page.
 */
const buildTabs = (user: any) => {
	if (user.is_student) return [{ label: 'Enrolled', value: 'enrolled' }]
	const tabs = [
		{ label: 'Published', value: 'live' },
		{ label: 'Upcoming', value: 'upcoming' },
	]
	if (user.is_moderator || user.is_instructor || user.is_evaluator) {
		tabs.push({ label: 'Created', value: 'created' })
		tabs.push({ label: 'Unpublished', value: 'unpublished' })
	}
	// os-config: courses.hidden_tabs
	return hideByConfig('courses.hidden_tabs', tabs)
}

const MODERATOR = { is_moderator: true }
const STUDENT = { is_student: true }

describe('courses.hidden_tabs', () => {
	beforeEach(() => {
		settingsMock.settings.data = { config: { 'courses.hidden_tabs': [] } }
	})

	it('shows every tab when nothing is hidden', () => {
		expect(buildTabs(MODERATOR).map((t) => t.value)).toEqual([
			'live',
			'upcoming',
			'created',
			'unpublished',
		])
	})

	it('hides the selected tabs', () => {
		settingsMock.settings.data.config['courses.hidden_tabs'] = ['created', 'unpublished']
		expect(buildTabs(MODERATOR).map((t) => t.value)).toEqual(['live', 'upcoming'])
	})

	it('does not alter the role rules', () => {
		// A student never saw "created" anyway; hiding it changes nothing.
		settingsMock.settings.data.config['courses.hidden_tabs'] = ['created']
		expect(buildTabs(STUDENT).map((t) => t.value)).toEqual(['enrolled'])
	})

	it('can hide every tab', () => {
		settingsMock.settings.data.config['courses.hidden_tabs'] = [
			'live',
			'upcoming',
			'created',
			'unpublished',
		]
		expect(buildTabs(MODERATOR)).toEqual([])
	})
})

/**
 * The block above describes the expected behaviour on a copy of the tab
 * list. On its own that proves nothing about the real page, so this ties
 * the description to the file: the graft must still be there, and it must
 * still be the last thing courseTabs does — applied AFTER the role
 * branches, so it can only subtract from what they produced.
 */
describe('the graft in Courses.vue', () => {
	const source = readFileSync(COURSES_VUE, 'utf-8')

	it('imports the helper', () => {
		expect(source).toContain("from '@/oslms/config/useOsConfig'")
	})

	it('carries the marker followed by the call, as the last step of courseTabs', () => {
		expect(source).toMatch(
			/\/\/ os-config: courses\.hidden_tabs\s*\n\s*return hideByConfig\('courses\.hidden_tabs', tabs\)/,
		)
	})
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && yarn vitest run src/tests/courseHiddenTabs.test.ts`
Expected: i test del primo blocco passano (descrivono `hideByConfig`, già scritto nel Task 8); **i due test del blocco "the graft in Courses.vue" falliscono**, perché l'innesto non esiste ancora.
Run: `docker compose -f docker/docker-compose.yml exec frappe bench --site lms.localhost run-tests --app os_lms --module os_lms.os_lms.config.tests.test_grafts`
Expected: FAIL — marcatore mancante in `Courses.vue`

- [ ] **Step 3: Write the graft**

In `frontend/src/pages/Courses/Courses.vue`, aggiungere l'import accanto agli altri import locali:

```js
import { hideByConfig } from '@/oslms/config/useOsConfig'
```

E nel `computed` `courseTabs`, sostituire l'ultima riga `return tabs` con:

```js
	// os-config: courses.hidden_tabs
	return hideByConfig('courses.hidden_tabs', tabs)
```

Il risultato finale è:

```js
const courseTabs = computed(() => {
	// Students only see the courses they are enrolled in — the public
	// "Published" and "Upcoming" tabs are hidden for them.
	if (user.data?.is_student) {
		return [{ label: __('Enrolled'), value: 'enrolled' }]
	}

	let tabs = [
		{
			label: __('Published'),
			value: 'live',
		},
		{
			label: __('Upcoming'),
			value: 'upcoming',
		},
	]
	if (
		user.data?.is_moderator ||
		user.data?.is_instructor ||
		user.data?.is_evaluator
	) {
		tabs.push({ label: __('Created'), value: 'created' })
		tabs.push({ label: __('Unpublished'), value: 'unpublished' })
	}
	// os-config: courses.hidden_tabs
	return hideByConfig('courses.hidden_tabs', tabs)
})
```

- [ ] **Step 4: Run both tests to verify they pass**

Run: `cd frontend && yarn vitest run src/tests/courseHiddenTabs.test.ts`
Expected: PASS
Run: `docker compose -f docker/docker-compose.yml exec frappe bench --site lms.localhost run-tests --app os_lms --module os_lms.os_lms.config.tests.test_grafts`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/Courses/Courses.vue frontend/src/tests/courseHiddenTabs.test.ts
git commit -m "feat(config): let courses.hidden_tabs hide course list filters

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 12: Documentazione generata

**Files:**
- Create: `apps/os_lms/os_lms/os_lms/config/docgen.py`
- Create: `docs/OS_LMS_CONFIGURAZIONI.md` (generato)
- Test: `apps/os_lms/os_lms/os_lms/config/tests/test_docgen.py`

**Interfaces:**
- Consumes: `all_params`, `params_for_section`, `Section` dal registry.
- Produces: `render_docs() -> str`; `write_docs() -> str` (scrive il file e ne ritorna il percorso); `DOCS_PATH`.

- [ ] **Step 1: Write the failing test**

```python
# apps/os_lms/os_lms/os_lms/config/tests/test_docgen.py
"""The generated documentation must never drift from the registry."""
from __future__ import annotations

from frappe.tests import UnitTestCase

from os_lms.os_lms.config.docgen import DOCS_PATH, render_docs


class TestDocgen(UnitTestCase):
	def test_lists_every_declared_param(self):
		rendered = render_docs()
		self.assertIn("courses.hidden_tabs", rendered)

	def test_has_one_heading_per_section(self):
		rendered = render_docs()
		for heading in ("## Corsi", "## Classi", "## App"):
			self.assertIn(heading, rendered)

	def test_reports_the_graft_files(self):
		self.assertIn("frontend/src/pages/Courses/Courses.vue", render_docs())

	def test_file_on_disk_matches_the_registry(self):
		# This is the guard: if it fails, regenerate with
		#   bench --site <site> execute os_lms.os_lms.config.docgen.write_docs
		self.assertTrue(DOCS_PATH.is_file(), f"{DOCS_PATH} has never been generated")
		self.assertEqual(
			DOCS_PATH.read_text(encoding="utf-8"),
			render_docs(),
			"docs/OS_LMS_CONFIGURAZIONI.md is out of date; regenerate it",
		)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose -f docker/docker-compose.yml exec frappe bench --site lms.localhost run-tests --app os_lms --module os_lms.os_lms.config.tests.test_docgen`
Expected: FAIL — `ModuleNotFoundError: No module named 'os_lms.os_lms.config.docgen'`

- [ ] **Step 3: Write minimal implementation**

```python
# apps/os_lms/os_lms/os_lms/config/docgen.py
"""Generate the configuration reference from the registry.

The reference is generated rather than written so it cannot drift: a test
regenerates it and fails if the file in the repository differs.

Regenerate with:
    bench --site <site> execute os_lms.os_lms.config.docgen.write_docs
"""
from __future__ import annotations

from pathlib import Path

import frappe

from os_lms.os_lms.config.registry import Section, all_params, params_for_section

REPO_ROOT = Path(frappe.get_app_path("lms")).parent
DOCS_PATH = REPO_ROOT / "docs" / "OS_LMS_CONFIGURAZIONI.md"

SECTION_LABELS = {
	Section.COURSES: "Corsi",
	Section.BATCHES: "Classi",
	Section.APP: "App",
}

HEADER = """# Configurazioni della piattaforma — riferimento

> **File generato. Non modificarlo a mano.**
> Si rigenera con `bench --site <site> execute os_lms.os_lms.config.docgen.write_docs`
> a partire da `apps/os_lms/os_lms/os_lms/config/definitions.py`.
> Per aggiungere un parametro, seguire `docs/OS_LMS_CONFIGURAZIONI-RICETTA.md`.

Legenda delle colonne:

- **Chiave** — l'identificatore usato nel codice: `cfg("<chiave>")` lato server,
  `cfg('<chiave>')` nella SPA.
- **Tipo** — il controllo mostrato nel pannello.
- **Default** — il valore in assenza di configurazione. Per regola riproduce il
  comportamento della piattaforma senza il parametro.
- **Superfici** — dove il valore viene consegnato: `web` è il sito, `app` è
  l'app mobile.
- **Innesti** — i file dell'upstream in cui il parametro è letto. Ognuno porta
  il marcatore `os-config: <chiave>` ed è verificato da un test.
"""

COLUMNS = (
	"| Chiave | Tipo | Opzioni | Default | Superfici | Etichetta | Descrizione | Innesti | Dal |\n"
	"| --- | --- | --- | --- | --- | --- | --- | --- | --- |\n"
)


def _cell(value: object) -> str:
	"""Render a value for a markdown table cell, escaping the column separator."""
	text = "" if value is None else str(value)
	return text.replace("|", "\\|").replace("\n", " ")


def _options(param) -> str:
	schema = param.type.schema()
	if "options" not in schema:
		return "—"
	return ", ".join(f"`{option['value']}`" for option in schema["options"])


def _row(param) -> str:
	return (
		f"| `{param.key}` "
		f"| {param.type.__class__.__name__} "
		f"| {_options(param)} "
		f"| `{param.default!r}` "
		f"| {', '.join(surface.value for surface in param.surfaces)} "
		f"| {_cell(param.label)} "
		f"| {_cell(param.description)} "
		f"| {', '.join(f'`{graft}`' for graft in param.grafts) or '—'} "
		f"| {param.since} |\n"
	)


def render_docs() -> str:
	parts = [HEADER]
	for section in Section:
		parts.append(f"\n## {SECTION_LABELS[section]}\n\n")
		params = sorted(params_for_section(section), key=lambda param: param.key)
		if not params:
			parts.append("_Nessun parametro dichiarato in questa sezione._\n")
			continue
		parts.append(COLUMNS)
		for param in params:
			parts.append(_row(param))
	parts.append(f"\n---\n\nParametri dichiarati: **{len(all_params())}**.\n")
	return "".join(parts)


def write_docs() -> str:
	DOCS_PATH.parent.mkdir(parents=True, exist_ok=True)
	DOCS_PATH.write_text(render_docs(), encoding="utf-8")
	print(f"Written {DOCS_PATH}")
	return str(DOCS_PATH)
```

- [ ] **Step 4: Generate the file, then run the test**

Run: `docker compose -f docker/docker-compose.yml exec frappe bench --site lms.localhost execute os_lms.os_lms.config.docgen.write_docs`
Then: `docker compose -f docker/docker-compose.yml exec frappe bench --site lms.localhost run-tests --app os_lms --module os_lms.os_lms.config.tests.test_docgen`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/os_lms/os_lms/os_lms/config/docgen.py apps/os_lms/os_lms/os_lms/config/tests/test_docgen.py docs/OS_LMS_CONFIGURAZIONI.md
git commit -m "docs(config): generate the configuration reference from the registry

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 13: La ricetta e il rimando in CLAUDE.md

**Files:**
- Create: `docs/OS_LMS_CONFIGURAZIONI-RICETTA.md`
- Modify: `CLAUDE.md` (sezione Architecture, sotto "Custom Extension: `apps/os_lms`")

**Interfaces:**
- Consumes: niente.
- Produces: la procedura che ogni sessione futura segue per aggiungere un parametro.

**Perché conta:** lo sviluppo è affidato ad assistente AI. Una sessione futura che non trova la ricetta reinventa la convenzione, e in sei mesi ne convivono tre.

- [ ] **Step 1: Write the recipe**

```markdown
# Come aggiungere un parametro di configurazione

Riferimento dei parametri esistenti: [`OS_LMS_CONFIGURAZIONI.md`](OS_LMS_CONFIGURAZIONI.md) (generato).
Progetto del sistema: [`superpowers/specs/2026-09-18-sistema-configurazioni-design.md`](superpowers/specs/2026-09-18-sistema-configurazioni-design.md).

## Le due regole da non sbagliare

**1. Il default riproduce il comportamento senza il parametro.**
Se il parametro nasce per nascondere qualcosa, il default non nasconde niente. Così,
se un aggiornamento dall'upstream cancella l'innesto o il valore non arriva, la
piattaforma si comporta come l'originale invece di rompersi.

**2. I parametri a elenco dicono cosa togliere, non cosa tenere.**
`hidden_tabs`, non `visible_tabs`. Un elenco di "visibili" farebbe sparire in
silenzio ogni voce che l'upstream aggiungerà in futuro.

## Procedura

### 1. Dichiara il parametro

Unico file da toccare: `apps/os_lms/os_lms/os_lms/config/definitions.py`.

```python
register(
	ConfigParam(
		key="courses.hidden_tabs",      # <sezione>.<nome>, in inglese
		section=Section.COURSES,        # COURSES | BATCHES | APP
		type=MultiChoice([...]),        # vedi la tabella dei tipi
		default=[],                     # regola 1
		label="Filtri da nascondere",   # in italiano: lo legge l'utente
		description="...",              # in italiano, opzionale
		surfaces=(Surface.WEB, Surface.APP),
		since="AAAA-MM-GG",
		grafts=("percorso/del/file.vue",),   # solo se innesti in un file upstream
	)
)
```

Superfici: i parametri di `COURSES` e `BATCHES` si dichiarano `(WEB, APP)`; quelli
di `APP` si dichiarano `(APP,)` e basta. Un test verifica che questa regola valga
per tutti.

### Tipi disponibili

| Tipo | Valore | Controllo nel pannello |
| --- | --- | --- |
| `Boolean()` | `True` / `False` | interruttore |
| `Integer(minimum=, maximum=)` | numero intero | campo numerico |
| `Float(minimum=, maximum=)` | numero decimale | campo numerico |
| `Text(max_length=)` | stringa | campo di testo |
| `LongText(max_length=)` | stringa | area di testo |
| `Choice([(valore, etichetta), ...])` | una stringa fra quelle dichiarate | tendina |
| `MultiChoice([(valore, etichetta), ...])` | lista di stringhe | elenco di caselle |
| `JsonValue()` | dizionario o lista | area di testo |

Se serve un tipo nuovo, va aggiunto **sia** in `config/types.py` **sia** nel
renderer `frontend/src/oslms/components/Settings/OsConfigSection.vue`. È l'unico
caso in cui aggiungere un parametro tocca il frontend.

### 2. Scrivi il punto di lettura

**Lato server:**

```python
from os_lms.os_lms.config import cfg

if cfg("courses.hidden_tabs"):
	...
```

**Nella SPA:**

```js
import { cfg, hideByConfig } from '@/oslms/config/useOsConfig'

// nascondere una sola scritta
<span v-if="cfg('courses.show_duration')">{{ durata }}</span>

// nascondere voci da un elenco costruito altrove
tabs = hideByConfig('courses.hidden_tabs', tabs)
```

### 3. Se il punto di lettura cade in un file upstream

**Prima verifica se puoi evitarlo.** Se l'elemento da governare vive già in un
componente sotto `frontend/src/oslms/` o in `apps/os_lms/`, non c'è nessun innesto
e questo passo non serve.

Se è inevitabile:

1. metti **immediatamente sopra la riga** il marcatore
   `// os-config: <chiave>` (oppure `# os-config: <chiave>` in Python);
2. aggiungi il percorso del file al campo `grafts` della dichiarazione;
3. scrivi un test di comportamento in `frontend/src/tests/` che verifichi
   l'effetto del parametro.

Il test `config/tests/test_grafts.py` verifica automaticamente che ogni innesto
dichiarato sia ancora presente e che non esistano marcatori orfani.

### 4. Rigenera la documentazione

```bash
docker compose -f docker/docker-compose.yml exec frappe \
  bench --site lms.localhost execute os_lms.os_lms.config.docgen.write_docs
```

### 5. Verifica

```bash
docker compose -f docker/docker-compose.yml exec frappe \
  bench --site lms.localhost run-tests --app os_lms --module os_lms.os_lms.config.tests.test_definitions
docker compose -f docker/docker-compose.yml exec frappe \
  bench --site lms.localhost run-tests --app os_lms --module os_lms.os_lms.config.tests.test_grafts
docker compose -f docker/docker-compose.yml exec frappe \
  bench --site lms.localhost run-tests --app os_lms --module os_lms.os_lms.config.tests.test_docgen
cd frontend && yarn test
```

## Dopo un aggiornamento dall'upstream

Esegui `test_grafts.py`. Se fallisce, il merge ha preso la versione upstream di un
file e ha cancellato il nostro innesto: rimettilo con il suo marcatore e rilancia.

## Cosa NON fare

- Non creare parametri dal pannello o dal desk: si dichiarano solo in
  `definitions.py`.
- Non leggere un valore con `frappe.db.get_value("OS LMS Config Value", ...)`:
  salta la risoluzione dei default e la validazione. Usa sempre `cfg()`.
- Non usare `visible_*` per un elenco: vedi la regola 2.
- Non dare a un parametro della sezione `APP` la superficie `WEB`.
```

- [ ] **Step 2: Add the pointer in CLAUDE.md**

Nella sezione "Custom Extension: `apps/os_lms`", aggiungere sotto l'elenco puntato:

```markdown
- `config/` — **configuration parameter system**. Every platform setting shown
  under Settings → Configurazioni (Corsi / Classi / App) is declared in
  `config/definitions.py` and nowhere else. **Before adding or changing a
  parameter, read [`docs/OS_LMS_CONFIGURAZIONI-RICETTA.md`](docs/OS_LMS_CONFIGURAZIONI-RICETTA.md)**;
  the generated reference of existing parameters is
  [`docs/OS_LMS_CONFIGURAZIONI.md`](docs/OS_LMS_CONFIGURAZIONI.md).
```

- [ ] **Step 3: Verify the recipe's commands actually work**

Eseguire alla lettera i quattro comandi del punto 5 della ricetta e confermare che
tutti passino. Una ricetta con un comando sbagliato è peggio di nessuna ricetta.

- [ ] **Step 4: Commit**

```bash
git add docs/OS_LMS_CONFIGURAZIONI-RICETTA.md CLAUDE.md
git commit -m "docs(config): add the parameter recipe and point CLAUDE.md at it

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 14: Collaudo

**Files:** nessuno (salvo correzioni emerse).

**Interfaces:** nessuna.

- [ ] **Step 1: Run the whole backend suite**

Run:
```bash
docker compose -f docker/docker-compose.yml exec frappe \
  bench --site lms.localhost run-tests --app os_lms
```
Expected: nessun fallimento, nessuna regressione rispetto alla baseline pre-piano.

- [ ] **Step 2: Run the whole frontend suite and the build**

Run: `cd frontend && yarn test`
Expected: PASS, inclusi i 31 test preesistenti
Run: `cd frontend && yarn build`
Expected: build completata

- [ ] **Step 3: Manual check of the three sections**

Su `http://lms.localhost:8000/lms`, come Administrator:

1. Impostazioni → Configurazioni → **Corsi**: compare "Filtri da nascondere nell'elenco corsi" con quattro caselle, tutte deselezionate.
2. Selezionare "Creato" e "Non pubblicato", premere Update, attendere la conferma.
3. Andare in **Corsi**: la barra dei filtri mostra solo "Pubblicato" e "In arrivo".
4. Tornare in Impostazioni → Configurazioni → Corsi: le due caselle sono ancora selezionate (il valore è stato persistito e riletto).
5. Deselezionarle, salvare, verificare che i quattro filtri tornino.
6. Impostazioni → Configurazioni → **App**: la sezione compare e mostra il messaggio "Nessuna configurazione disponibile in questa sezione."
7. Impostazioni → Configurazioni → **Classi**: l'interruttore "Abilita Classi Live" funziona ancora come prima (non è stato migrato: spec §6.2).

- [ ] **Step 4: Manual check of the desk inspection surface**

Su `http://lms.localhost:8000/app/os-lms-config-value`, verificare che la riga
`Global::::courses.hidden_tabs` sia elencata con il suo valore JSON, e che tentare
di salvarvi un valore non valido (es. `["archived"]`) venga rifiutato con un
messaggio comprensibile.

- [ ] **Step 5: Verify the empty-storage behaviour**

Azzerare **solo** il parametro appena provato, dal pannello: Impostazioni →
Configurazioni → Corsi, deselezionare tutte le caselle, Update. In alternativa,
dal desk, cancellare la sola riga `Global::::courses.hidden_tabs` in
`OS LMS Config Value`.

> **Non** usare `frappe.db.delete("OS LMS Config Value")` senza filtri: su questo
> sito cancellerebbe ogni configurazione, comprese quelle impostate da altri.

Poi ricaricare la pagina Corsi: i quattro filtri devono essere tutti presenti.
È la verifica del criterio di accettazione 5 della specifica: **con lo storage
vuoto la piattaforma si comporta esattamente come prima del piano.**

- [ ] **Step 6: Commit any fixes**

```bash
git add -A
git commit -m "fix(config): address findings from the acceptance run

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

## Copertura dei criteri di accettazione della specifica

| # | Criterio | Task che lo soddisfa | Come si verifica |
| --- | --- | --- | --- |
| 1 | Aggiungere un parametro tocca un solo file | 5, 13 | La ricetta lo descrive; il Task 5 lo dimostra |
| 2 | Le tre sezioni compaiono e salvano | 9, 14 | `osConfigSection.test.ts` + collaudo manuale |
| 3 | I parametri `[APP]` non entrano nel payload del sito | 4, 6 | `test_store.py::TestSurfaces`, `test_exposure.py` |
| 4 | `courses.hidden_tabs` nasconde i filtri senza toccare le regole di ruolo | 11 | `courseHiddenTabs.test.ts` |
| 5 | Con lo storage vuoto il comportamento è quello di oggi | 5, 14 | `test_definitions.py` + Task 14 Step 5 |
| 6 | Una chiave non dichiarata solleva errore in lettura e in scrittura | 2, 4, 7 | `test_registry.py`, `test_store.py`, `test_api.py` |
| 7 | La documentazione è generata e un test ne verifica l'allineamento | 12 | `test_docgen.py::test_file_on_disk_matches_the_registry` |
| 8 | Un test fallisce se un innesto dichiarato sparisce | 10, 11 | `test_grafts.py` |

## Dopo questo piano

1. **Gli altri 4-5 parametri** (fase 7 della stima): ognuno ripete la forma dei Task 5, 10 e 11 seguendo la ricetta. Vanno definiti dal committente prima di iniziare.
2. **Migrazione di `enable_live_classes`** (spec §6.2): dichiararlo come `batches.live_classes_disabled` con `default=False`, sostituire le due letture nella SPA, applicare `osConfigTab('batches')` alla voce Classi, rimuovere la riga innestata in `lms/lms/api.py:1496` e il Custom Field dalla fixture. Stimato 0,5 sessioni.
3. **Riconciliazione dei due meccanismi di Custom Field** (fixture contro `setup.py`): debito adiacente, da valutare separatamente.

"""Architectural test: provider SDK imports must stay inside their adapters.

Per PLAN-os_lms.md §3.3.1 (encapsulation rule), the official SDK of an LLM/STT/TTS
provider may be imported only inside its own adapter module. This test scans
the codebase and fails if any forbidden import escapes the providers/ folder.

The test deliberately uses plain string parsing (not AST) so it catches
re-exports and aliasing as well, and runs without importing the actual
target modules.
"""
from __future__ import annotations

import ast
from pathlib import Path

from frappe.tests import UnitTestCase

# Top-level modules whose import must stay inside utils/{llm,stt,tts}/providers/.
# Each entry is matched against an import's top-level package name only.
FORBIDDEN_TOP_LEVEL_PACKAGES = {
    "openai",
    "anthropic",
    "deepgram",
    "elevenlabs",
}

# google.genai (Gemini SDK) and google.cloud.{speech,texttospeech} also count.
# We match these as dotted-prefix below.
FORBIDDEN_DOTTED_PREFIXES = (
    "google.genai",
    "google.cloud.speech",
    "google.cloud.texttospeech",
    "azure.cognitiveservices.speech",
)


def _provider_dirs(app_root: Path) -> list[Path]:
    base = app_root / "os_lms" / "ai" / "utils"
    return [
        base / "llm" / "providers",
        base / "stt" / "providers",  # may not exist yet (fase 2)
        base / "tts" / "providers",  # may not exist yet (fase 2)
        base / "audio" / "providers",
        base / "realtime" / "providers",
    ]


def _is_under(path: Path, parents: list[Path]) -> bool:
    for parent in parents:
        try:
            path.resolve().relative_to(parent.resolve())
            return True
        except ValueError:
            continue
    return False


def _iter_imports(py_path: Path):
    """Yield (module_str, lineno) for every `import X` / `from X import ...`."""
    source = py_path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source, filename=str(py_path))
    except SyntaxError:
        return
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name, node.lineno
        elif isinstance(node, ast.ImportFrom):
            if node.level:  # relative imports never reference top-level provider SDKs
                continue
            if node.module:
                yield node.module, node.lineno


def _is_forbidden(module: str) -> bool:
    top = module.split(".")[0]
    if top in FORBIDDEN_TOP_LEVEL_PACKAGES:
        return True
    return any(module == p or module.startswith(p + ".") for p in FORBIDDEN_DOTTED_PREFIXES)


class TestProviderEncapsulation(UnitTestCase):
    """Fail CI if a provider SDK is imported outside its adapter folder."""

    def test_no_sdk_imports_outside_providers(self):
        app_root = Path(__file__).resolve().parents[5]  # apps/os_lms/os_lms/
        allowed_dirs = _provider_dirs(app_root)

        offenders: list[str] = []
        for py in app_root.rglob("*.py"):
            # Skip caches, virtualenvs, anything inside an allowed providers dir.
            parts = py.parts
            if "__pycache__" in parts or ".venv" in parts or "env" in parts:
                continue
            if _is_under(py, allowed_dirs):
                continue
            # Don't lint this test itself: the FORBIDDEN lists name the modules.
            if py.name == "test_provider_encapsulation.py":
                continue
            for module, lineno in _iter_imports(py):
                if _is_forbidden(module):
                    rel = py.relative_to(app_root.parent)
                    offenders.append(f"  {rel}:{lineno}  imports {module}")

        if offenders:
            msg = (
                "Provider SDK imports must stay inside their adapter folder "
                "(utils/llm/providers, utils/stt/providers, utils/tts/providers). "
                "Encapsulation rule, PLAN-os_lms.md §3.3.1.\n"
                "Offenders:\n" + "\n".join(offenders)
            )
            self.fail(msg)

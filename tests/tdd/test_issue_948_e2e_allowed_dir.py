"""Issue #948: Workflow-Gate muss `e2e/` als Test-Verzeichnis anerkennen.

Verhaltenstest gegen die ECHTE Gate-Entscheidungslogik aus edit_gate.py.
Kein String-in-Datei-Check: der Test lädt die Config mit demselben YAML-Loader
wie config_loader.load_config() und fährt exakt denselben Komponenten-Match
(`d.rstrip('/') in Path(fp).parts`), den edit_gate.main() für die
always-allowed-Verzeichnisse verwendet.

Beweist:
1. `frontend/e2e/*.spec.ts` wird in JEDER Phase durchgelassen (Bug behoben).
2. `src/**/*.py` fällt NICHT in die Whitelist → bleibt gate-pflichtig
   (kein Schutzverlust).
3. Die Config-Liste ersetzt den Code-Default und ist ein echtes Superset
   davon — kein bestehendes Test-/Tooling-Verzeichnis wird still entfernt.
"""
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOKS_DIR = REPO_ROOT / ".claude" / "hooks"
OPENSPEC_YAML = REPO_ROOT / "openspec.yaml"

sys.path.insert(0, str(HOOKS_DIR))
from edit_gate import ALWAYS_ALLOWED_DIRS  # noqa: E402  (Code-Default-Liste)


def _loaded_allowed_dirs():
    """Wie config_loader die Liste aus openspec.yaml zieht (PyYAML, gleiche Sektion/Key)."""
    cfg = yaml.safe_load(OPENSPEC_YAML.read_text()) or {}
    return cfg.get("strict_code_gate", {}).get("always_allowed_dirs")


def _gate_allows(file_path: str, allowed_dirs) -> bool:
    """Exakter Komponenten-Match aus edit_gate.main() Schritt 2."""
    parts = set(Path(file_path).parts)
    return any(d.rstrip("/") in parts for d in allowed_dirs)


def test_config_defines_allowed_dirs():
    dirs = _loaded_allowed_dirs()
    assert dirs, "strict_code_gate.always_allowed_dirs fehlt in openspec.yaml"


def test_e2e_spec_is_allowed_in_any_phase():
    dirs = _loaded_allowed_dirs()
    assert _gate_allows("frontend/e2e/foo.spec.ts", dirs), (
        "Playwright-Test unter frontend/e2e/ muss durchgelassen werden (Issue #948)"
    )


def test_src_code_is_not_whitelisted():
    """Gegenprobe: echter Produktivcode darf NICHT über die Whitelist rutschen."""
    dirs = _loaded_allowed_dirs()
    assert not _gate_allows("src/app/foo.py", dirs)
    assert not _gate_allows("frontend/src/routes/Page.svelte", dirs)
    assert not _gate_allows("internal/store/store.go", dirs)


def test_config_is_superset_of_code_default():
    """Die Config ersetzt den Code-Default — sie muss ihn vollständig enthalten
    plus e2e/, sonst fällt ein Verzeichnis still aus der Whitelist."""
    dirs = _loaded_allowed_dirs()
    missing = [d for d in ALWAYS_ALLOWED_DIRS if d not in dirs]
    assert not missing, f"Config lässt Code-Default-Dirs fallen: {missing}"
    assert "e2e/" in dirs


def test_existing_test_dirs_still_allowed():
    """Regression: bestehende Test-Verzeichnisse bleiben erlaubt."""
    dirs = _loaded_allowed_dirs()
    assert _gate_allows("frontend/tests/x.spec.ts", dirs)
    assert _gate_allows("tests/tdd/test_foo.py", dirs)

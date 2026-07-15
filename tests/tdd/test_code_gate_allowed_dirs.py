"""Issue #948 / #1196: Repo-Garantie fuer die Code-Gate-Whitelist.

Nach dem Hook->Plugin-Umzug lebt die Gate-ENTSCHEIDUNGSLOGIK (edit_gate.py)
nicht mehr im Repo, sondern im Plugin. Dieser Test prueft deshalb bewusst
NUR noch die Repo-eigene Garantie: die Config-Sektion
`strict_code_gate.always_allowed_dirs` in openspec.yaml (geladen mit
PyYAML, wie config_loader es tut) sowie den hier lokal nachgebauten
Komponenten-Match (`d.rstrip('/') in Path(fp).parts`), den das Plugin
fuer diese Liste verwendet. Der Code-Default des Plugins selbst ist
Plugin-Verantwortung und wird hier nicht mehr importiert/geprueft.

Beweist:
1. `frontend/e2e/*.spec.ts` bzw. `e2e/` allgemein ist in der Config
   als always-allowed gelistet (Issue #948).
2. `tests/` bleibt als Test-Verzeichnis gate-frei.
3. `src/**/*.py` bleibt NICHT gate-frei (kein Schutzverlust).
4. Die Config-Sektion existiert und ist nicht leer.
"""
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
OPENSPEC_YAML = REPO_ROOT / "openspec.yaml"


def _loaded_allowed_dirs():
    """Wie config_loader die Liste aus openspec.yaml zieht (PyYAML, gleiche Sektion/Key)."""
    cfg = yaml.safe_load(OPENSPEC_YAML.read_text()) or {}
    return cfg.get("strict_code_gate", {}).get("always_allowed_dirs")


def _gate_allows(file_path: str, allowed_dirs) -> bool:
    """Exakter Komponenten-Match, wie ihn das Gate-Plugin fuer diese Liste verwendet."""
    parts = set(Path(file_path).parts)
    return any(d.rstrip("/") in parts for d in allowed_dirs)


def test_config_defines_allowed_dirs():
    dirs = _loaded_allowed_dirs()
    assert dirs, "strict_code_gate.always_allowed_dirs fehlt in openspec.yaml"


def test_e2e_dir_is_allowed():
    dirs = _loaded_allowed_dirs()
    assert "e2e/" in dirs, "e2e/ muss in always_allowed_dirs stehen (Issue #948)"
    assert _gate_allows("frontend/e2e/foo.spec.ts", dirs), (
        "Playwright-Test unter frontend/e2e/ muss durchgelassen werden (Issue #948)"
    )


def test_tests_dir_is_allowed():
    dirs = _loaded_allowed_dirs()
    assert "tests/" in dirs
    assert _gate_allows("tests/tdd/x.py", dirs)


def test_src_code_is_not_whitelisted():
    """Gegenprobe: echter Produktivcode darf NICHT ueber die Whitelist rutschen."""
    dirs = _loaded_allowed_dirs()
    assert not _gate_allows("src/services/x.py", dirs)

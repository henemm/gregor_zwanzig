"""
TDD RED: E2E-Pfad-Logik konsolidieren + härten (Issue #665).

Mocks sind in diesem Projekt VERBOTEN. Alle Tests laufen gegen die echten Hooks,
das echte gemeinsame Modul `_e2e_paths`, ein echtes temporäres Git-Repo und echte
Dateien. `REPO_DIR`/`CANONICAL_E2E_PATH` werden per monkeypatch auf das Temp-Repo
umgebogen — das ist KEIN Mock, sondern ein realer Pfad auf ein echtes Git-Repo.

Getestete ACs (siehe docs/specs/modules/issue_665_e2e_path_helper.md):
  AC-1: staging_gate und prod_selftest lösen für denselben HEAD DENSELBEN Pfad auf
        (getaggt / nur-Singleton / keine-Datei)
  AC-2: head_sha() liefert bei git-Fehler "UNKNOWN" (nie ""), in beiden Hooks gleich
  AC-3: commit_e2e_path() mit leerem/None-SHA endet auf UNKNOWN.json, nie auf .json
  AC-5: Pfad-Logik nur noch im gemeinsamen Modul (doc-compliance)

In der RED-Phase fehlt `.claude/hooks/_e2e_paths.py` und die Hooks importieren es
nicht → die Tests scheitern (FileNotFoundError beim Modul-Load, Asymmetrie ""
vs "UNKNOWN", kaputter .json-Name, fehlender Import).
"""

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOKS_DIR = REPO_ROOT / ".claude" / "hooks"
STAGING_GATE = HOOKS_DIR / "staging_gate.py"
PROD_SELFTEST = HOOKS_DIR / "prod_selftest.py"
E2E_PATHS = HOOKS_DIR / "_e2e_paths.py"
# sys.path-Einfügung zentral in tests/tdd/conftest.py — nicht hier.


def _load_module(path: Path, name: str):
    """Lädt ein Modul (echte Funktionen, keine Mocks). Raised wenn Datei fehlt."""
    if not path.exists():
        raise FileNotFoundError(f"{path} existiert nicht (RED erwartet)")
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _git(args, cwd):
    return subprocess.run(["git"] + args, capture_output=True, text=True, cwd=str(cwd))


def _init_repo(root: Path) -> str:
    _git(["init", "-q"], root)
    _git(["config", "user.email", "t@example.com"], root)
    _git(["config", "user.name", "Tester"], root)
    (root / "src").mkdir(parents=True, exist_ok=True)
    (root / ".claude").mkdir(parents=True, exist_ok=True)
    (root / "src" / "x.py").write_text("a = 1\n")
    _git(["add", "-A"], root)
    _git(["commit", "-qm", "c1"], root)
    return _git(["rev-parse", "HEAD"], root).stdout.strip()


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    head = _init_repo(root)
    return root, head


def _patch_paths(monkeypatch, mod, root: Path):
    monkeypatch.setattr(mod, "REPO_DIR", root)
    monkeypatch.setattr(mod, "CANONICAL_E2E_PATH", root / ".claude" / "e2e_verified.json")


def _both_hooks():
    return (
        _load_module(STAGING_GATE, "staging_gate"),
        _load_module(PROD_SELFTEST, "prod_selftest"),
    )


# ---------------------------------------------------------------------------
# AC-1: Beide Hooks lösen denselben Default-Pfad auf
# ---------------------------------------------------------------------------
class TestCrossHookConsistency:
    def _resolve_both(self, monkeypatch, root):
        sg, ps = _both_hooks()
        _patch_paths(monkeypatch, sg, root)
        _patch_paths(monkeypatch, ps, root)
        return sg._default_e2e_path(), ps._default_e2e_path()

    def test_tagged_file_exists_same_path(self, monkeypatch, repo):
        root, head = repo
        tagged = root / ".claude" / "e2e_verified" / f"{head}.json"
        tagged.parent.mkdir(parents=True, exist_ok=True)
        tagged.write_text("{}")
        a, b = self._resolve_both(monkeypatch, root)
        assert a == b == tagged

    def test_only_singleton_same_path(self, monkeypatch, repo):
        root, _ = repo
        singleton = root / ".claude" / "e2e_verified.json"
        singleton.write_text("{}")
        a, b = self._resolve_both(monkeypatch, root)
        assert a == b == singleton

    def test_no_file_same_path(self, monkeypatch, repo):
        root, head = repo
        a, b = self._resolve_both(monkeypatch, root)
        # Beide fallen auf den (nicht existenten) getaggten Pfad zurück — identisch.
        assert a == b == root / ".claude" / "e2e_verified" / f"{head}.json"


# ---------------------------------------------------------------------------
# AC-2: head_sha() bei git-Fehler → "UNKNOWN", in beiden Hooks gleich
# ---------------------------------------------------------------------------
class TestHeadShaHardening:
    def test_module_returns_unknown_without_git(self, tmp_path):
        mod = _load_module(E2E_PATHS, "_e2e_paths")
        nogit = tmp_path / "nogit"
        nogit.mkdir()
        assert mod.head_sha(nogit) == "UNKNOWN"

    def test_both_hooks_symmetric_unknown(self, monkeypatch, tmp_path):
        nogit = tmp_path / "nogit"
        nogit.mkdir()
        sg, ps = _both_hooks()
        monkeypatch.setattr(sg, "REPO_DIR", nogit)
        monkeypatch.setattr(ps, "REPO_DIR", nogit)
        # Kern des #665-Befunds: KEINE Asymmetrie "" vs "UNKNOWN" mehr.
        assert sg._head_sha() == ps._head_sha() == "UNKNOWN"


# ---------------------------------------------------------------------------
# AC-3: commit_e2e_path() gegen leeren/None-SHA gehärtet
# ---------------------------------------------------------------------------
class TestCommitPathHardening:
    def test_empty_sha_yields_unknown_json(self, tmp_path):
        mod = _load_module(E2E_PATHS, "_e2e_paths")
        p = mod.commit_e2e_path(tmp_path, "")
        assert p.name == "UNKNOWN.json"

    def test_none_sha_yields_unknown_json(self, tmp_path):
        mod = _load_module(E2E_PATHS, "_e2e_paths")
        p = mod.commit_e2e_path(tmp_path, None)
        assert p.name == "UNKNOWN.json"

    def test_valid_sha_preserved(self, tmp_path):
        mod = _load_module(E2E_PATHS, "_e2e_paths")
        p = mod.commit_e2e_path(tmp_path, "abc123")
        assert p.name == "abc123.json"


# ---------------------------------------------------------------------------
# AC-5: Pfad-Logik nur noch im gemeinsamen Modul (doc-compliance-test)
# ---------------------------------------------------------------------------
class TestPathLogicConsolidated:
    def test_path_logic_only_in_shared_module(self):
        # doc-compliance-test
        """Beide Hooks importieren _e2e_paths und delegieren — keine duplizierte
        git-rev-parse-Logik mehr in beiden Hook-Dateien."""
        assert E2E_PATHS.exists(), "_e2e_paths.py muss existieren"
        sg_src = STAGING_GATE.read_text()
        ps_src = PROD_SELFTEST.read_text()
        for src, name in ((sg_src, "staging_gate"), (ps_src, "prod_selftest")):
            assert "_e2e_paths" in src, f"{name} importiert _e2e_paths nicht"
            # git rev-parse darf nur noch im gemeinsamen Modul stehen, nicht im Hook.
            assert "rev-parse" not in src, f"{name} enthält noch duplizierte rev-parse-Logik"

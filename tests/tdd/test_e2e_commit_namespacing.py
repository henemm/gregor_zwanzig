"""
TDD RED: E2E-Gate Race-Hardening — Attestation pro Commit (Issue #662).

Mocks sind in diesem Projekt VERBOTEN. Alle Tests laufen gegen die echten Hooks,
ein echtes temporäres Git-Repo und echte Dateien. `REPO_DIR`/`CANONICAL_E2E_PATH`
werden per monkeypatch auf das Temp-Repo umgebogen — das ist KEIN Mock, sondern
ein realer Pfad auf ein echtes Git-Repo (verhindert zugleich, dass das echte
Hauptrepo verschmutzt wird).

Getestete ACs (siehe docs/specs/modules/issue_662_e2e_commit_namespacing.md):
  AC-1: Zwei verschiedene Commits → zwei intakte Dateien, keine überschreibt die andere
  AC-2: Commit-getaggte Attestation für HEAD vorhanden → Gate Exit 0 (Default-Pfad)
  AC-3: Nur altes Singleton vorhanden → Fallback Exit 0; getaggte Datei hat Vorrang
  AC-4: Fremd-Commit-Attestation schaltet anderen HEAD NICHT frei → Exit 1
  AC-5: prod_selftest löst denselben Pfad auf wie das Gate
  AC-6: .claude/e2e_verified/ ist gitignored
  AC-7: e2e-verify.md Backend-Pfad schreibt commit-getaggt (doc-compliance)

In der RED-Phase fehlen `_commit_e2e_path` / `_default_e2e_path` und die
Default-Pfad-Verdrahtung → die Tests scheitern (AttributeError / falscher Pfad).
"""

import importlib.util
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
STAGING_GATE = REPO_ROOT / ".claude" / "hooks" / "staging_gate.py"
PROD_SELFTEST = REPO_ROOT / ".claude" / "hooks" / "prod_selftest.py"
E2E_VERIFY_DOC = REPO_ROOT / ".claude" / "commands" / "e2e-verify.md"


def _load_module(path: Path, name: str):
    """Lädt einen Hook als Modul (echte Funktionen, keine Mocks)."""
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _git(args, cwd):
    return subprocess.run(
        ["git"] + args, capture_output=True, text=True, cwd=str(cwd)
    )


def _init_repo(root: Path) -> dict:
    """Echtes Git-Repo mit drei Commits (jeder mit Backend-Datei → Non-docs-Scope)."""
    _git(["init", "-q"], root)
    _git(["config", "user.email", "t@example.com"], root)
    _git(["config", "user.name", "Tester"], root)
    (root / "src").mkdir(parents=True, exist_ok=True)
    (root / ".claude").mkdir(parents=True, exist_ok=True)
    shas = {}
    for i in (1, 2, 3):
        (root / "src" / "x.py").write_text(f"a = {i}\n")
        _git(["add", "-A"], root)
        _git(["commit", "-qm", f"c{i}"], root)
        shas[f"c{i}"] = _git(["rev-parse", "HEAD"], root).stdout.strip()
    return shas


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    shas = _init_repo(root)
    return root, shas


def _patch_paths(monkeypatch, mod, root: Path):
    """Biegt die hartkodierten Pfade auf das Temp-Repo um (reale Pfade, kein Mock)."""
    monkeypatch.setattr(mod, "REPO_DIR", root)
    monkeypatch.setattr(mod, "CANONICAL_E2E_PATH", root / ".claude" / "e2e_verified.json")


def _findings_file(tmp_path) -> Path:
    f = tmp_path / "findings.json"
    f.write_text(json.dumps([{"ac": "AC-1", "status": "PASS", "url": "/", "evidence": "ok"}]))
    return f


# ---------------------------------------------------------------------------
# AC-1: Zwei Sessions / zwei Commits → zwei intakte Dateien
# ---------------------------------------------------------------------------
class TestParallelWritesNoCollision:
    def test_two_commits_yield_two_intact_files(self, repo, tmp_path, monkeypatch):
        """AC-1: write_verdict (Default-Pfad) für zwei verschiedene HEADs schreibt
        zwei separate Dateien — keine überschreibt die andere."""
        root, shas = repo
        sg = _load_module(STAGING_GATE, "staging_gate")
        _patch_paths(monkeypatch, sg, root)
        findings = _findings_file(tmp_path)

        # Session B: HEAD = c3
        rc_b = sg.write_verdict("VERIFIED: Session B", findings, None)
        assert rc_b == 0

        # Session A: HEAD = c2 (auschecken simuliert andere Session auf älterem Commit)
        _git(["checkout", "-q", shas["c2"]], root)
        rc_a = sg.write_verdict("VERIFIED: Session A", findings, None)
        assert rc_a == 0

        file_b = root / ".claude" / "e2e_verified" / f"{shas['c3']}.json"
        file_a = root / ".claude" / "e2e_verified" / f"{shas['c2']}.json"
        assert file_b.exists(), f"Datei für c3 fehlt: {file_b}"
        assert file_a.exists(), f"Datei für c2 fehlt: {file_a}"
        assert json.loads(file_b.read_text())["verified_commit"] == shas["c3"]
        assert json.loads(file_a.read_text())["verified_commit"] == shas["c2"]


# ---------------------------------------------------------------------------
# AC-2: Commit-getaggte Attestation für HEAD → Gate akzeptiert
# ---------------------------------------------------------------------------
class TestGateAcceptsCommitTagged:
    def test_gate_passes_with_commit_tagged_attestation(self, repo, tmp_path, monkeypatch):
        """AC-2: Gate leitet Default-Pfad aus HEAD ab und akzeptiert (Exit 0)."""
        root, shas = repo
        sg = _load_module(STAGING_GATE, "staging_gate")
        _patch_paths(monkeypatch, sg, root)
        findings = _findings_file(tmp_path)

        assert sg.write_verdict("VERIFIED: alle ACs grün", findings, None) == 0
        rc = sg.gate_check(None, None)
        assert rc == 0, "Gate muss den commit-getaggten Default-Pfad finden und akzeptieren"


# ---------------------------------------------------------------------------
# AC-3: Singleton-Fallback + Vorrang der getaggten Datei
# ---------------------------------------------------------------------------
class TestSingletonFallbackAndPrecedence:
    def test_legacy_singleton_is_read_as_fallback(self, repo, monkeypatch):
        """AC-3: Existiert NUR das alte Singleton → Gate liest es (Exit 0)."""
        root, shas = repo
        sg = _load_module(STAGING_GATE, "staging_gate")
        _patch_paths(monkeypatch, sg, root)

        singleton = root / ".claude" / "e2e_verified.json"
        singleton.write_text(json.dumps({
            "verified_commit": shas["c3"],
            "staging_verdict": "VERIFIED: legacy",
            "verified_at": datetime.now(timezone.utc).isoformat(),
            "scope": "backend",
            "environment": "staging",
            "findings": [],
        }))
        assert sg.gate_check(None, None) == 0, "Fallback auf Singleton muss greifen"

    def test_commit_tagged_takes_precedence_over_singleton(self, repo, monkeypatch):
        """AC-3: Existiert beides, gewinnt die commit-getaggte Datei — hier blockiert
        ihre veraltete Attestation, obwohl das Singleton gültig wäre."""
        root, shas = repo
        sg = _load_module(STAGING_GATE, "staging_gate")
        _patch_paths(monkeypatch, sg, root)

        # gültiges Singleton
        (root / ".claude" / "e2e_verified.json").write_text(json.dumps({
            "verified_commit": shas["c3"],
            "staging_verdict": "VERIFIED: legacy gültig",
            "verified_at": datetime.now(timezone.utc).isoformat(),
            "scope": "backend", "environment": "staging", "findings": [],
        }))
        # commit-getaggte Datei mit FALSCHEM Commit (muss Vorrang haben → Block)
        tagged_dir = root / ".claude" / "e2e_verified"
        tagged_dir.mkdir(parents=True, exist_ok=True)
        (tagged_dir / f"{shas['c3']}.json").write_text(json.dumps({
            "verified_commit": "0" * 40,
            "staging_verdict": "VERIFIED: falscher commit",
            "verified_at": datetime.now(timezone.utc).isoformat(),
            "scope": "backend", "environment": "staging", "findings": [],
        }))
        assert sg.gate_check(None, None) == 1, (
            "Commit-getaggte Datei muss Vorrang vor dem Singleton haben"
        )


# ---------------------------------------------------------------------------
# AC-4: Fremd-Commit-Attestation schaltet anderen HEAD nicht frei
# ---------------------------------------------------------------------------
class TestForeignCommitDoesNotUnlock:
    def test_foreign_commit_attestation_blocks(self, repo, tmp_path, monkeypatch):
        """AC-4: Attestation existiert nur für c2, HEAD steht auf c3, kein Singleton
        → Gate blockiert (Exit 1)."""
        root, shas = repo
        sg = _load_module(STAGING_GATE, "staging_gate")
        _patch_paths(monkeypatch, sg, root)

        # Attestation nur für c2 erzeugen
        _git(["checkout", "-q", shas["c2"]], root)
        sg.write_verdict("VERIFIED: c2", _findings_file(tmp_path), None)
        _git(["checkout", "-q", shas["c3"]], root)  # HEAD zurück auf c3

        assert not (root / ".claude" / "e2e_verified.json").exists()
        rc = sg.gate_check(None, None)
        assert rc == 1, "Fremde c2-Attestation darf c3 nicht freischalten"


# ---------------------------------------------------------------------------
# AC-5: prod_selftest löst denselben Pfad auf wie das Gate
# ---------------------------------------------------------------------------
class TestProdSelftestPathResolution:
    def test_prod_selftest_resolves_commit_tagged_path(self, repo, monkeypatch):
        """AC-5: prod_selftest._default_e2e_path() liefert die commit-getaggte Datei
        für HEAD (dieselbe Quelle wie das Gate)."""
        root, shas = repo
        ps = _load_module(PROD_SELFTEST, "prod_selftest")
        _patch_paths(monkeypatch, ps, root)

        tagged = root / ".claude" / "e2e_verified" / f"{shas['c3']}.json"
        tagged.parent.mkdir(parents=True, exist_ok=True)
        tagged.write_text(json.dumps({
            "verified_commit": shas["c3"],
            "staging_verdict": "VERIFIED: x",
            "verified_at": datetime.now(timezone.utc).isoformat(),
            "scope": "backend", "environment": "staging", "findings": [],
        }))

        resolved = ps._default_e2e_path()
        assert resolved == tagged, (
            f"prod_selftest muss den commit-getaggten Pfad auflösen, war: {resolved}"
        )


# ---------------------------------------------------------------------------
# AC-6: .claude/e2e_verified/ ist gitignored
# ---------------------------------------------------------------------------
class TestGitignore:
    def test_e2e_verified_dir_is_gitignored(self):
        """AC-6: Eine Datei unter .claude/e2e_verified/ wird von git ignoriert."""
        probe = ".claude/e2e_verified/deadbeef.json"
        result = _git(["check-ignore", probe], REPO_ROOT)
        assert result.returncode == 0, (
            f"{probe} muss gitignored sein (check-ignore Exit {result.returncode}). "
            "Pattern '.claude/e2e_verified/' fehlt in .gitignore."
        )


# ---------------------------------------------------------------------------
# AC-7: Backend-Pfad in e2e-verify.md schreibt commit-getaggt
# ---------------------------------------------------------------------------
class TestBackendDocPathCommitTagged:
    def test_e2e_verify_backend_snippet_is_commit_tagged(self):
        # doc-compliance-test
        """AC-7: Der inline-Schreibpfad in e2e-verify.md zielt nicht mehr auf das
        Singleton, sondern auf .claude/e2e_verified/<sha> bzw. nutzt write-verdict."""
        text = E2E_VERIFY_DOC.read_text()
        commit_tagged = ("e2e_verified/" in text) or ("staging_gate.py --write-verdict" in text)
        writes_singleton = "open('.claude/e2e_verified.json'" in text or 'open(".claude/e2e_verified.json"' in text
        assert commit_tagged and not writes_singleton, (
            "e2e-verify.md Backend-Pfad muss commit-getaggt schreiben (oder "
            "staging_gate.py --write-verdict nutzen), nicht ins Singleton."
        )

"""
TDD RED: E2E-Verified Retention (Issue #666).

Mocks sind in diesem Projekt VERBOTEN. Alle Tests laufen gegen die echten Hooks,
ein echtes temporäres Git-Repo und echte Dateien auf der Platte. `REPO_DIR` /
`CANONICAL_E2E_PATH` werden per monkeypatch auf das Temp-Repo umgebogen — das ist
KEIN Mock, sondern ein realer Pfad auf ein echtes Git-Repo (verhindert zugleich,
dass das echte Hauptrepo verschmutzt wird).

Getestete ACs (siehe docs/specs/modules/issue_666_e2e_verified_retention.md):
  AC-1: 20 vorhandene Attestationen + neues Verdict → genau 20 Dateien, älteste weg
  AC-2: < 20 Dateien → nichts gelöscht, alle bleiben erhalten
  AC-3: HEAD-Datei wird nie weggeprunt → Gate-Check Exit 0 (auch bei vollem Verzeichnis)
  AC-4: Löschen einer Alt-Datei schlägt real fehl (Verzeichnis statt Datei) →
        write_verdict bleibt erfolgreich (rc 0), neue Attestation existiert

In der RED-Phase fehlt das Pruning in `write_verdict()` → nach dem Schreiben
verbleiben 21 Dateien statt 20 (AC-1 schlägt fehl).
"""

import importlib.util
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
STAGING_GATE = REPO_ROOT / ".claude" / "hooks" / "staging_gate.py"

RETENTION = 20


def _load_module(path: Path, name: str):
    """Lädt einen Hook als Modul (echte Funktionen, keine Mocks)."""
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _git(args, cwd):
    return subprocess.run(["git"] + args, capture_output=True, text=True, cwd=str(cwd))


def _init_repo(root: Path) -> str:
    """Echtes Git-Repo mit zwei Backend-Commits.

    Zwei Commits sind nötig, damit `HEAD~1..HEAD` existiert und
    `_detect_committed_scope()` 'backend' (statt 'docs-only') liefert — nur dann
    wertet `gate_check()` die Attestation echt aus statt früh zu passieren.
    """
    _git(["init", "-q"], root)
    _git(["config", "user.email", "t@example.com"], root)
    _git(["config", "user.name", "Tester"], root)
    (root / "src").mkdir(parents=True, exist_ok=True)
    (root / ".claude").mkdir(parents=True, exist_ok=True)
    for i in (1, 2):
        (root / "src" / "x.py").write_text(f"a = {i}\n")
        _git(["add", "-A"], root)
        _git(["commit", "-qm", f"c{i}"], root)
    return _git(["rev-parse", "HEAD"], root).stdout.strip()


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    head = _init_repo(root)
    return root, head


def _patch_paths(monkeypatch, mod, root: Path):
    """Biegt die hartkodierten Pfade auf das Temp-Repo um (reale Pfade, kein Mock)."""
    monkeypatch.setattr(mod, "REPO_DIR", root)
    monkeypatch.setattr(mod, "CANONICAL_E2E_PATH", root / ".claude" / "e2e_verified.json")


def _findings_file(tmp_path) -> Path:
    f = tmp_path / "findings.json"
    f.write_text(json.dumps([{"ac": "AC-1", "status": "PASS", "url": "/", "evidence": "ok"}]))
    return f


def _prefill(tagged_dir: Path, count: int, base_ts: float) -> list[Path]:
    """Legt `count` ältere Attestationen mit aufsteigenden mtimes an.

    Gibt die Pfade zurück (Index 0 = älteste). Alle mtimes liegen vor `base_ts`,
    damit eine danach geschriebene HEAD-Datei garantiert die jüngste ist.
    """
    tagged_dir.mkdir(parents=True, exist_ok=True)
    created = []
    for i in range(count):
        sha = f"{i:040x}"
        p = tagged_dir / f"{sha}.json"
        p.write_text(json.dumps({"verified_commit": sha, "staging_verdict": "VERIFIED: old"}))
        ts = base_ts - (count - i)  # i=0 → ältest, i=count-1 → jüngst (aber < base_ts)
        os.utime(p, (ts, ts))
        created.append(p)
    return created


# ---------------------------------------------------------------------------
# AC-1: Volles Verzeichnis (20) + neues Verdict → genau 20, älteste gelöscht
# ---------------------------------------------------------------------------
class TestRetentionPrunesOldest:
    def test_full_dir_keeps_exactly_retention_and_drops_oldest(self, repo, tmp_path, monkeypatch):
        root, head = repo
        sg = _load_module(STAGING_GATE, "staging_gate")
        _patch_paths(monkeypatch, sg, root)

        tagged_dir = root / ".claude" / "e2e_verified"
        base_ts = datetime.now(timezone.utc).timestamp() - 1000
        prefilled = _prefill(tagged_dir, RETENTION, base_ts)
        oldest = prefilled[0]

        rc = sg.write_verdict("VERIFIED: neu", _findings_file(tmp_path), None)
        assert rc == 0

        head_file = tagged_dir / f"{head}.json"
        assert head_file.exists(), "Neue HEAD-Attestation muss existieren"

        remaining = sorted(tagged_dir.glob("*.json"))
        assert len(remaining) == RETENTION, (
            f"Verzeichnis muss nach dem Pruning genau {RETENTION} Dateien haben, "
            f"hat aber {len(remaining)}"
        )
        assert not oldest.exists(), "Die älteste Attestation muss geprunt sein"


# ---------------------------------------------------------------------------
# AC-2: < 20 Dateien → nichts gelöscht
# ---------------------------------------------------------------------------
class TestRetentionKeepsWhenUnderLimit:
    def test_under_limit_deletes_nothing(self, repo, tmp_path, monkeypatch):
        root, head = repo
        sg = _load_module(STAGING_GATE, "staging_gate")
        _patch_paths(monkeypatch, sg, root)

        tagged_dir = root / ".claude" / "e2e_verified"
        base_ts = datetime.now(timezone.utc).timestamp() - 1000
        prefilled = _prefill(tagged_dir, 5, base_ts)

        assert sg.write_verdict("VERIFIED: neu", _findings_file(tmp_path), None) == 0

        for p in prefilled:
            assert p.exists(), f"Bestehende Datei darf nicht gelöscht werden: {p.name}"
        assert (tagged_dir / f"{head}.json").exists()
        assert len(list(tagged_dir.glob("*.json"))) == 6


# ---------------------------------------------------------------------------
# AC-3: HEAD-Datei überlebt das Pruning → Gate akzeptiert
# ---------------------------------------------------------------------------
class TestHeadAttestationSurvivesPruning:
    def test_gate_passes_after_pruning_on_full_dir(self, repo, tmp_path, monkeypatch):
        root, head = repo
        sg = _load_module(STAGING_GATE, "staging_gate")
        _patch_paths(monkeypatch, sg, root)

        tagged_dir = root / ".claude" / "e2e_verified"
        base_ts = datetime.now(timezone.utc).timestamp() - 1000
        _prefill(tagged_dir, RETENTION, base_ts)

        assert sg.write_verdict("VERIFIED: HEAD grün", _findings_file(tmp_path), None) == 0
        assert sg.gate_check(None, None) == 0, (
            "HEAD-Attestation darf nie weggeprunt werden → Gate muss Exit 0 liefern"
        )


# ---------------------------------------------------------------------------
# AC-4: Realer Löschfehler (Verzeichnis-Eintrag) → write_verdict bleibt erfolgreich
# ---------------------------------------------------------------------------
class TestPruningErrorDoesNotBreakVerdict:
    def test_undeletable_old_entry_does_not_fail_verdict(self, repo, tmp_path, monkeypatch):
        root, head = repo
        sg = _load_module(STAGING_GATE, "staging_gate")
        _patch_paths(monkeypatch, sg, root)

        tagged_dir = root / ".claude" / "e2e_verified"
        base_ts = datetime.now(timezone.utc).timestamp() - 1000
        _prefill(tagged_dir, RETENTION - 1, base_ts)

        # Der älteste Eintrag ist ein NICHT-leeres Verzeichnis namens "<sha>.json":
        # unlink() darauf wirft real IsADirectoryError (Subklasse von OSError).
        bad = tagged_dir / f"{'f' * 40}.json"
        bad.mkdir()
        (bad / "blocker").write_text("x")
        ts = base_ts - 9999  # ältester Eintrag → landet im Prune-Slice
        os.utime(bad, (ts, ts))

        rc = sg.write_verdict("VERIFIED: trotz Löschfehler", _findings_file(tmp_path), None)
        assert rc == 0, "Löschfehler beim Pruning darf das Verdict nicht kippen"
        assert (tagged_dir / f"{head}.json").exists(), "Neue Attestation muss trotzdem existieren"

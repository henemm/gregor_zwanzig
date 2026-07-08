"""
TDD RED: Tests fuer die Gate-Scope-Selbstvergiftung (Issue #1096).

Mocks sind in diesem Projekt VERBOTEN. Alle Tests laufen gegen echte
Temp-Git-Repos + echte Subprozess-Aufrufe der echten Hook-Skripte. Die
Skripte werden aus dem AKTUELLEN Arbeitsverzeichnis (Worktree) kopiert, nicht
aus dem Hauptrepo hartkodiert — sonst wuerden die Tests den unveraenderten
Hauptrepo-Stand statt der eigenen Fix-Aenderung pruefen. Kein Test beruehrt
das echte Hauptrepo; jeder Test operiert ausschliesslich auf einem tmp_path-
Repo (Muster identisch zu test_issue_916_gate_scope_marker.py::_setup_repo).

Getestete ACs (docs/specs/modules/issue_1096_gate_scope_selfpoison.md):
  AC-1: Zweiter --check-Lauf auf demselben HEAD stuft einen bereits korrekt
        erkannten Scope NICHT auf docs-only herab.
  AC-2: Eine unmittelbar nach einem erfolgreichen Gate-Lauf geschriebene
        Attestation traegt niemals faelschlich scope=docs-only fuer einen
        echten Code-Commit.
  AC-3: prod_selftest.py's Scope-Ermittlung wird durch einen vorherigen
        staging_gate.py-Doppel-Lauf nie auf docs-only vergiftet.
  AC-4: Regressionsschutz — ein echter docs-only-Commit (kein vorheriger
        Marker) skippt weiterhin korrekt mit Exit 0. War VOR dem Fix schon
        gruen und MUSS gruen bleiben.
"""
from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_HOOKS_SRC = _REPO_ROOT / ".claude" / "hooks"


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=repo, check=True,
                           capture_output=True, text=True)


def _head_sha(repo: Path) -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo,
        capture_output=True, text=True, check=True,
    ).stdout.strip()


def _setup_repo(tmp_path: Path) -> Path:
    """Standalone Git-Repo mit eigener .claude/hooks-Kopie (Worktree-sicher)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "t@t.de")
    _git(repo, "config", "user.name", "Test")

    hooks = repo / ".claude" / "hooks"
    hooks.mkdir(parents=True)
    for name in ("staging_gate.py", "prod_selftest.py", "_e2e_paths.py"):
        shutil.copy(_HOOKS_SRC / name, hooks / name)

    (repo / "README.md").write_text("# baseline\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "baseline")
    return repo


def _run_staging_gate(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(repo / ".claude" / "hooks" / "staging_gate.py"), *args],
        cwd=repo, capture_output=True, text=True,
    )


def _write_marker(repo: Path, sha: str) -> Path:
    p = repo / ".claude" / "last_gate_scope.json"
    p.write_text(json.dumps({"gate_scope_sha": sha}))
    return p


def _read_marker(repo: Path) -> dict | None:
    p = repo / ".claude" / "last_gate_scope.json"
    if not p.exists():
        return None
    return json.loads(p.read_text())


def _write_attestation(repo: Path, sha: str, scope: str) -> Path:
    """Gueltige Attestation an den commit-getaggten Default-Pfad
    <repo>/.claude/e2e_verified/<sha>.json (Vorrang vor dem Singleton-Fallback,
    s. _e2e_paths.default_e2e_path)."""
    tagged_dir = repo / ".claude" / "e2e_verified"
    tagged_dir.mkdir(parents=True, exist_ok=True)
    p = tagged_dir / f"{sha}.json"
    p.write_text(json.dumps({
        "verified_commit": sha,
        "staging_verdict": "VERIFIED: alle ACs gruen",
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "environment": "staging",
        "scope": scope,
        "findings": [],
    }))
    return p


def _commit_file(repo: Path, rel_path: str, content: str, message: str) -> None:
    target = repo / rel_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", message)


def _load_prod_selftest_module(repo: Path):
    """Laedt die im Temp-Repo liegende Kopie von prod_selftest.py per
    importlib. Import-sicher: main() liegt hinter `if __name__ == "__main__"`,
    Modul-Konstanten (REPO_DIR etc.) haben keine Seiteneffekte beim Import."""
    mod_path = repo / ".claude" / "hooks" / "prod_selftest.py"
    spec = importlib.util.spec_from_file_location(
        f"_prod_selftest_{repo.name}_{id(repo)}", str(mod_path)
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# AC-1: Doppel-Lauf auf demselben HEAD stuft nicht auf docs-only herab
# ---------------------------------------------------------------------------

def test_double_check_run_does_not_downgrade_to_docs_only(tmp_path):
    """Zwei aufeinanderfolgende staging_gate.py --check-Laeufe auf demselben
    HEAD (Frontend-Commit) muessen beide Male denselben, echten Scope
    (frontend-only) melden — der zweite Lauf darf NICHT wegen eines
    selbstreferenziellen HEAD..HEAD-Diffs auf docs-only herabgestuft werden
    und den Marker damit vergiften (Bug aus #1097-Deploy)."""
    repo = _setup_repo(tmp_path)
    baseline_sha = _head_sha(repo)
    _write_marker(repo, baseline_sha)

    _commit_file(repo, "frontend/App.svelte", "<div>frontend change</div>\n",
                 "frontend change")
    head_sha = _head_sha(repo)
    _write_attestation(repo, head_sha, "frontend-only")

    res1 = _run_staging_gate(repo, "--check")
    assert res1.returncode == 0, (
        f"Lauf 1 (vollstaendige Pruefung mit gueltiger Attestation) muss "
        f"Exit 0 liefern. stdout={res1.stdout!r} stderr={res1.stderr!r}"
    )
    marker_after_1 = _read_marker(repo)
    assert marker_after_1 is not None
    assert marker_after_1.get("gate_scope_sha") == head_sha, (
        f"Marker nach Lauf 1 muss auf HEAD zeigen. marker={marker_after_1!r}"
    )
    assert marker_after_1.get("gate_last_scope") == "frontend-only", (
        f"Marker nach Lauf 1 muss den echten Scope cachen. "
        f"marker={marker_after_1!r}"
    )

    res2 = _run_staging_gate(repo, "--check")
    combined_2 = (res2.stdout + res2.stderr).lower()
    assert "scope 'docs-only'" not in combined_2, (
        f"Lauf 2 auf unveraendertem HEAD darf NICHT mit der docs-only-"
        f"Skip-Meldung uebersprungen werden — das ist die Selbstvergiftung "
        f"aus Issue #1096. stdout={res2.stdout!r} stderr={res2.stderr!r}"
    )
    assert res2.returncode == 0, (
        f"Lauf 2 muss weiterhin Exit 0 liefern (Attestation ist gueltig). "
        f"rc={res2.returncode} stdout={res2.stdout!r} stderr={res2.stderr!r}"
    )

    marker_after_2 = _read_marker(repo)
    assert marker_after_2 is not None
    assert marker_after_2.get("gate_last_scope") == "frontend-only", (
        f"Marker darf nach Lauf 2 NICHT auf docs-only vergiftet werden. "
        f"marker={marker_after_2!r}"
    )


# ---------------------------------------------------------------------------
# AC-2: Attestation traegt nie faelschlich scope=docs-only
# ---------------------------------------------------------------------------

def test_write_verdict_after_check_never_writes_docs_only_scope(tmp_path):
    """Ein staging_gate.py --write-verdict-Aufruf unmittelbar nach einem
    erfolgreichen --check-Lauf fuer denselben Backend-Commit muss den echten
    Scope (backend) in die Attestation schreiben — nicht faelschlich
    docs-only (Folge des selbstreferenziellen HEAD..HEAD-Diffs)."""
    repo = _setup_repo(tmp_path)
    baseline_sha = _head_sha(repo)
    _write_marker(repo, baseline_sha)

    _commit_file(repo, "src/foo.py", "# backend change\n", "backend change")
    head_sha = _head_sha(repo)
    _write_attestation(repo, head_sha, "backend")

    res1 = _run_staging_gate(repo, "--check")
    assert res1.returncode == 0, (
        f"Vorlauf-Check muss bestehen. stdout={res1.stdout!r} "
        f"stderr={res1.stderr!r}"
    )
    marker_after_1 = _read_marker(repo)
    assert marker_after_1 is not None
    assert marker_after_1.get("gate_last_scope") == "backend", (
        f"Vorlauf-Check muss den echten Scope cachen. marker={marker_after_1!r}"
    )

    findings_path = tmp_path / "findings.json"
    findings_path.write_text("[]")
    out_path = tmp_path / "verdict_output.json"

    res2 = subprocess.run(
        [sys.executable, str(repo / ".claude" / "hooks" / "staging_gate.py"),
         "--write-verdict", "VERIFIED: test",
         "--findings-json", str(findings_path),
         "--e2e-path", str(out_path)],
        cwd=repo, capture_output=True, text=True,
    )
    assert res2.returncode == 0, (
        f"write-verdict muss bei VERIFIED Exit 0 liefern. "
        f"stdout={res2.stdout!r} stderr={res2.stderr!r}"
    )
    assert out_path.exists(), "write-verdict muss die Attestation schreiben."
    written = json.loads(out_path.read_text())
    assert written.get("scope") == "backend", (
        f"Attestation darf niemals faelschlich scope=docs-only fuer einen "
        f"echten Backend-Commit tragen (Issue #1096). "
        f"geschrieben={written!r}"
    )


# ---------------------------------------------------------------------------
# AC-3: prod_selftest.py's Scope-Ermittlung wird nie vergiftet
# ---------------------------------------------------------------------------

def test_prod_selftest_scope_never_poisoned_by_gate_double_run(tmp_path):
    """Nach einem staging_gate.py-Doppel-Lauf auf demselben Frontend-Commit
    (der heute den Marker faelschlich auf docs-only vergiftet) darf
    prod_selftest.py's eigene Scope-Ermittlung fuer denselben Commit NIEMALS
    docs-only liefern — der Post-Deploy-Selftest wuerde sonst einen echten
    Code-Deploy stillschweigend uebergehen."""
    repo = _setup_repo(tmp_path)
    baseline_sha = _head_sha(repo)
    _write_marker(repo, baseline_sha)

    _commit_file(repo, "frontend/App.svelte", "<div>frontend change</div>\n",
                 "frontend change")
    head_sha = _head_sha(repo)
    _write_attestation(repo, head_sha, "frontend-only")

    res1 = _run_staging_gate(repo, "--check")
    assert res1.returncode == 0, (
        f"Lauf 1 muss bestehen. stdout={res1.stdout!r} stderr={res1.stderr!r}"
    )
    res2 = _run_staging_gate(repo, "--check")
    assert res2.returncode == 0, (
        f"Lauf 2 muss weiterhin bestehen (gueltige Attestation). "
        f"stdout={res2.stdout!r} stderr={res2.stderr!r}"
    )

    mod = _load_prod_selftest_module(repo)
    detected_scope = mod._detect_committed_scope(repo_dir=repo)
    assert detected_scope != "docs-only", (
        f"prod_selftest.py's Scope-Ermittlung darf nach einem Gate-Doppel-"
        f"Lauf auf einem echten Frontend-Commit NIEMALS docs-only liefern "
        f"(Issue #1096 — Marker wurde durch staging_gate.py vergiftet). "
        f"detected_scope={detected_scope!r}"
    )


# ---------------------------------------------------------------------------
# AC-4: Regressionsschutz — echter docs-only-Commit skippt weiterhin (Exit 0)
# ---------------------------------------------------------------------------

def test_docs_only_commit_without_marker_still_skips(tmp_path):
    """Regressionsschutz — war vor dem Fix schon gruen und muss gruen
    bleiben: ein Commit, der ausschliesslich eine Markdown-Datei aendert
    (kein vorheriger Marker), muss weiterhin mit Exit 0 und der docs-only-
    Skip-Meldung durchlaufen."""
    repo = _setup_repo(tmp_path)
    assert not (repo / ".claude" / "last_gate_scope.json").exists()

    _commit_file(repo, "docs/notes.md", "# nur docs\n", "docs change")

    res = _run_staging_gate(repo, "--check")
    combined = (res.stdout + res.stderr).lower()
    assert res.returncode == 0, (
        f"Echter docs-only-Commit muss weiterhin Exit 0 liefern. "
        f"rc={res.returncode} stdout={res.stdout!r} stderr={res.stderr!r}"
    )
    assert "docs-only" in combined, (
        f"Skip-Meldung muss weiterhin den Scope docs-only nennen. "
        f"stdout={res.stdout!r} stderr={res.stderr!r}"
    )


# ---------------------------------------------------------------------------
# Adversary-Finding F001 (HIGH): Vor-Fix vergifteter Alt-Marker (SHA==HEAD,
# gate_last_scope faelschlich "docs-only" fuer einen echten Code-Commit) darf
# vom Cache-Guard nicht blind uebernommen werden.
# ---------------------------------------------------------------------------

def test_alt_poisoned_docs_only_cache_is_not_trusted(tmp_path):
    """F001: Ein bereits VOR diesem Fix geschriebener Marker mit
    gate_last_scope="docs-only" fuer einen Commit, der tatsaechlich echten
    Backend-Code enthaelt (SHA==HEAD, exakt der reale, aktuell im Hauptrepo
    vorliegende vergiftete Zustand fuer #1085/9b3cba68), darf weder von
    staging_gate.py noch von prod_selftest.py als vertrauenswuerdiger
    Cache-Treffer akzeptiert werden."""
    repo = _setup_repo(tmp_path)
    _commit_file(repo, "src/real.py", "# echter Backend-Code\n", "backend change")
    head_sha = _head_sha(repo)
    # Altlast-Marker: faelschlich VOR dem Fix auf docs-only gesetzt, obwohl
    # HEAD echten Code enthaelt.
    marker_path = repo / ".claude" / "last_gate_scope.json"
    marker_path.write_text(json.dumps({
        "gate_scope_sha": head_sha,
        "gate_last_scope": "docs-only",
    }))

    res = _run_staging_gate(repo, "--detect-scope")
    scope = (res.stdout + res.stderr).strip().lower()
    assert scope != "docs-only", (
        f"staging_gate.py darf einen VOR dem Fix vergifteten docs-only-"
        f"Cache-Eintrag fuer einen echten Backend-Commit nicht blind "
        f"uebernehmen (Finding F001). scope={scope!r} "
        f"stdout={res.stdout!r} stderr={res.stderr!r}"
    )

    mod = _load_prod_selftest_module(repo)
    detected = mod._detect_committed_scope(repo_dir=repo)
    assert detected != "docs-only", (
        f"prod_selftest.py darf denselben Alt-Poison-Marker ebenfalls nicht "
        f"uebernehmen (Finding F001). detected_scope={detected!r}"
    )


# ---------------------------------------------------------------------------
# Adversary-Finding F002 (MEDIUM): Marker im alten #916-Format (kein
# gate_last_scope-Feld), SHA==HEAD -> darf nicht in den selbstreferenziellen,
# immer leeren HEAD..HEAD-Diff hereinfallen.
# ---------------------------------------------------------------------------

def test_old_marker_format_without_scope_field_falls_back_correctly(tmp_path):
    """F002: Ein Marker im alten #916-Format ({"gate_scope_sha": sha}, kein
    gate_last_scope-Feld), dessen SHA zufaellig auf HEAD zeigt und dessen
    HEAD bereits echten Code enthaelt (Selbstreferenz-Fall), darf nicht
    faelschlich docs-only liefern — weder ueber den Cache (der hier
    strukturell None liefert) noch ueber die Diff-Basis (die auf HEAD~1
    statt auf den selbstreferenziellen Marker-SHA ausweichen muss)."""
    repo = _setup_repo(tmp_path)
    _commit_file(repo, "src/real.py", "# echter Backend-Code\n", "backend change")
    head_sha = _head_sha(repo)
    _write_marker(repo, head_sha)  # altes Format: nur gate_scope_sha

    res = _run_staging_gate(repo, "--detect-scope")
    scope = (res.stdout + res.stderr).strip().lower()
    assert scope != "docs-only", (
        f"Alter Marker ohne gate_last_scope-Feld mit SHA==HEAD darf nicht in "
        f"den leeren HEAD..HEAD-Diff hereinfallen (Finding F002). "
        f"scope={scope!r} stdout={res.stdout!r} stderr={res.stderr!r}"
    )

    mod = _load_prod_selftest_module(repo)
    detected = mod._detect_committed_scope(repo_dir=repo)
    assert detected != "docs-only", (
        f"prod_selftest.py muss denselben Selbstreferenz-Fall vermeiden "
        f"(Finding F002). detected_scope={detected!r}"
    )

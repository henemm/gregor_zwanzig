"""TDD RED (Issue #1866, Fix-Workflow fix-1866-claim-freigabeweg):

Der Aktivitaets-Verfall (`_claim_expired_by_activity`) fuer das
Datei-Claim-Gate existiert noch nicht -- ein Claim bleibt aktuell blockierend,
auch wenn die beanspruchte Datei im belegenden Worktree nachweislich
unveraendert und deckungsgleich mit `origin/main` ist (genau der Ausloeser-
Fall aus Issue #1866). Details:
docs/specs/modules/fix_1866_claim_gate_freigabeweg.md.

Kein Mock-Theater: echtes Temp-Git-Repo, echter Commit, echter
`git worktree add`-Linked-Worktree, echte `git`-Subprozessaufrufe --
KEIN Mock von Git-Befehlen oder der Registry-Datei. Vorbild fuer den
Repo+Worktree-Aufbau: tests/tdd/test_validator_log_shared_repo_path.py,
Funktion `_setup_main_with_worktree`.

Pfadregel (#1409): der Pruefling wird relativ zur eigenen Testdatei
aufgeloest (`parents[2]` = Repo-Root bei `tests/unit/<datei>.py`).

Getestete AC: AC-4 (Aktivitaets-Verfall entblockt den Auslöser-Fall),
AC-5 (Gegenprobe -- lokale Aenderung bzw. Abweichung von origin/main
blockiert weiterhin).

Hinweis zur RED-Erwartung: AC-4 ist vor der Implementierung ROT (die
Aktivitaets-Pruefung existiert noch nicht, der Claim blockiert weiterhin).
Die AC-5-Gegenprobe-Tests pruefen ein Verhalten, das schon HEUTE gilt
(unveraenderte Zeit-/Worktree-Logik blockiert immer) UND nach der
Implementierung weiterhin gelten MUSS -- sie sind deshalb bereits vor der
Implementierung gruen (echte Gegenprobe, keine Zementierung von
Bestandsverhalten: sie pruefen genau die Grenze, die AC-4 NICHT
ueberschreiten darf, PO-Regel „Grüner Test in RED zementiert Bestand" gilt
hier nicht, weil AC-5 bewusst als Nicht-Regressions-Schranke fuer AC-4
spezifiziert ist).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = _REPO_ROOT / ".claude" / "hooks" / "file_claim_gate.py"

_CLAIMED_PATH = "some/file.py"
_BASELINE_CONTENT = "content-v1\n"


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True,
    )


def _run(cwd: Path, stdin_text: str) -> subprocess.CompletedProcess:
    """Ruft file_claim_gate.py wie der PreToolUse-Hook auf (stdin-JSON, keine
    CLI-Argumente). `CLAUDE_PROJECT_DIR` wird entfernt, damit
    `_find_main_repo_root()` das isolierte Temp-Repo findet, nicht das echte
    Projekt-Repo."""
    env = os.environ.copy()
    env.pop("CLAUDE_PROJECT_DIR", None)
    return subprocess.run(
        [sys.executable, str(_SCRIPT)],
        cwd=str(cwd),
        input=stdin_text,
        capture_output=True,
        text=True,
        timeout=15,
        env=env,
    )


def _registry_path(main: Path) -> Path:
    return main / ".claude" / "file_claims.json"


def _write_registry(main: Path, data: dict) -> None:
    reg = _registry_path(main)
    reg.parent.mkdir(parents=True, exist_ok=True)
    reg.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


def _setup_main_with_worktree(tmp_path: Path, create_origin_ref: bool = True) -> tuple[Path, Path]:
    """Echtes Hauptrepo mit `refs/remotes/origin/main` + echter Linked-
    Worktree ('session-a') per `git worktree add`. Der Worktree traegt
    dieselbe Datei wie das Hauptrepo (repo-relativ `some/file.py`), Inhalt
    zunaechst identisch mit origin/main -- Tests veraendern den Worktree-
    Zustand danach je nach Szenario (AC-4: unveraendert, AC-5: lokal
    geaendert bzw. committet-aber-abweichend-von-origin).

    `create_origin_ref=False` (Fail-Closed-Test): `refs/remotes/origin/main`
    wird bewusst NICHT angelegt -- `git show origin/main:<pfad>` schlaegt
    dann mit Nicht-Null-Exit fehl und durchlaeuft real den zweiten
    `except Exception:`-Zweig in `_claim_expired_by_activity`."""
    main = tmp_path / "main"
    main.mkdir()
    _git(main, "init", "-b", "main-line")
    _git(main, "config", "user.email", "t@t.de")
    _git(main, "config", "user.name", "Test")

    target = main / _CLAIMED_PATH
    target.parent.mkdir(parents=True)
    target.write_text(_BASELINE_CONTENT)
    (main / "README.md").write_text("# baseline\n")
    _git(main, "add", "-A")
    _git(main, "commit", "-m", "baseline")

    if create_origin_ref:
        head_sha = _git(main, "rev-parse", "HEAD").stdout.strip()
        _git(main, "update-ref", "refs/remotes/origin/main", head_sha)

    wt_parent = tmp_path / "worktrees"
    wt_parent.mkdir(parents=True, exist_ok=True)
    wt = wt_parent / "session-a"
    _git(main, "worktree", "add", str(wt), "-b", "wt-branch")

    return main, wt


def _fresh_collision_registry_entry() -> dict:
    return {
        "session": "session-a",
        "branch": "wt-branch",
        "claimed_at_epoch": time.time(),
        "claimed_at": datetime.now(timezone.utc).isoformat(),
    }


def _stdin_for(main: Path) -> str:
    file_path = str(main / _CLAIMED_PATH)
    return json.dumps({"tool_input": {"file_path": file_path}})


# ---------------------------------------------------------------------------
# AC-4: unveraendert + deckungsgleich mit origin/main -> Claim gilt als
# verfallen, kein Block (Reproduktion des Ausloeser-Falls aus Issue #1866)
# ---------------------------------------------------------------------------

def test_unchanged_and_identical_to_origin_main_does_not_block(tmp_path):
    main, wt = _setup_main_with_worktree(tmp_path)
    # Worktree-Datei bleibt unveraendert (== origin/main), kein lokaler Diff.
    status = _git(wt, "status", "--porcelain", "--", _CLAIMED_PATH).stdout
    assert status == "", (
        f"Testvoraussetzung: Worktree-Datei muss sauber sein (kein lokaler Diff). "
        f"status={status!r}"
    )

    _write_registry(main, {_CLAIMED_PATH: _fresh_collision_registry_entry()})

    result = _run(main, _stdin_for(main))

    assert result.returncode == 0, (
        f"AC-4: unveraenderte, mit origin/main deckungsgleiche Datei im belegenden "
        f"Worktree muss den Claim als verfallen behandeln (kein Block). "
        f"returncode={result.returncode} stderr={result.stderr!r}"
    )
    assert "gerade von einer anderen aktiven Session belegt" not in result.stderr, (
        f"AC-4: darf keine Kollisionsmeldung ausgeben. stderr={result.stderr!r}"
    )


# ---------------------------------------------------------------------------
# AC-5 (Gegenprobe a): lokale, nicht committete Aenderung im belegenden
# Worktree -> weiterhin blockierend
# ---------------------------------------------------------------------------

def test_local_uncommitted_change_still_blocks(tmp_path):
    main, wt = _setup_main_with_worktree(tmp_path)

    (wt / _CLAIMED_PATH).write_text("content-v1-changed-locally\n")
    status = _git(wt, "status", "--porcelain", "--", _CLAIMED_PATH).stdout
    assert status.strip() != "", (
        f"Testvoraussetzung: lokale Aenderung muss git status als schmutzig zeigen. "
        f"status={status!r}"
    )

    _write_registry(main, {_CLAIMED_PATH: _fresh_collision_registry_entry()})

    result = _run(main, _stdin_for(main))

    assert result.returncode == 2, (
        f"AC-5(a): eine lokale unstaged Aenderung im belegenden Worktree darf den "
        f"Aktivitaets-Verfall NICHT ausloesen -- weiterhin blockierend. "
        f"returncode={result.returncode} stderr={result.stderr!r}"
    )
    assert "gerade von einer anderen aktiven Session belegt" in result.stderr, (
        f"AC-5(a): die bestehende Kollisionsmeldung muss weiterhin erscheinen. "
        f"stderr={result.stderr!r}"
    )


# ---------------------------------------------------------------------------
# AC-5 (Gegenprobe b): committete Aenderung im belegenden Worktree, aber
# origin/main zeigt eine aeltere/andere Fassung (kein Push) -> weiterhin
# blockierend
# ---------------------------------------------------------------------------

def test_committed_change_diverging_from_origin_main_still_blocks(tmp_path):
    main, wt = _setup_main_with_worktree(tmp_path)

    (wt / _CLAIMED_PATH).write_text("content-v2-committed-not-pushed\n")
    _git(wt, "add", "-A")
    _git(wt, "commit", "-m", "local change, not pushed")
    status = _git(wt, "status", "--porcelain", "--", _CLAIMED_PATH).stdout
    assert status == "", (
        f"Testvoraussetzung: nach dem Commit muss der Worktree fuer diesen Pfad "
        f"sauber sein. status={status!r}"
    )

    _write_registry(main, {_CLAIMED_PATH: _fresh_collision_registry_entry()})

    result = _run(main, _stdin_for(main))

    assert result.returncode == 2, (
        f"AC-5(b): eine committete, aber gegenueber origin/main abweichende Fassung "
        f"im belegenden Worktree darf den Aktivitaets-Verfall NICHT ausloesen -- "
        f"weiterhin blockierend. returncode={result.returncode} stderr={result.stderr!r}"
    )
    assert "gerade von einer anderen aktiven Session belegt" in result.stderr, (
        f"AC-5(b): die bestehende Kollisionsmeldung muss weiterhin erscheinen. "
        f"stderr={result.stderr!r}"
    )


# ---------------------------------------------------------------------------
# Fail-Closed-Nachweis: fehlende `origin/main`-Ref laesst `git show
# origin/main:<pfad>` real fehlschlagen -> zweiter except-Zweig in
# `_claim_expired_by_activity` wird durchlaufen -> False (nicht verfallen)
# -> Kollisionsfall blockiert weiterhin (Adversary-Finding: Sicherheitsrichtung
# war bislang nicht durch einen Test erzwungen, der den Zweig real erreicht)
# ---------------------------------------------------------------------------

def test_missing_origin_main_ref_still_blocks(tmp_path):
    main, wt = _setup_main_with_worktree(tmp_path, create_origin_ref=False)
    # Worktree-Datei bleibt unveraendert, kein lokaler Diff -- wie AC-4, aber
    # OHNE origin/main-Ref. Ohne den Fail-Closed-Zweig wuerde ein fehlerhafter
    # `git show`-Aufruf sonst faelschlich "identisch" (leerer stdout ==
    # leerer stdout) statt "nicht verfallen" liefern.
    status = _git(wt, "status", "--porcelain", "--", _CLAIMED_PATH).stdout
    assert status == "", (
        f"Testvoraussetzung: Worktree-Datei muss sauber sein (kein lokaler Diff). "
        f"status={status!r}"
    )
    origin_ref = _git(main, "for-each-ref", "refs/remotes/origin/main")
    assert origin_ref.stdout.strip() == "", (
        f"Testvoraussetzung: refs/remotes/origin/main darf NICHT existieren. "
        f"stdout={origin_ref.stdout!r}"
    )

    _write_registry(main, {_CLAIMED_PATH: _fresh_collision_registry_entry()})

    result = _run(main, _stdin_for(main))

    assert result.returncode == 2, (
        f"Fehlende origin/main-Ref muss den Fail-Closed-Zweig in "
        f"_claim_expired_by_activity real durchlaufen (git show origin/main:... "
        f"schlaegt fehl) -> nicht verfallen -> weiterhin blockierend. "
        f"returncode={result.returncode} stderr={result.stderr!r}"
    )
    assert "gerade von einer anderen aktiven Session belegt" in result.stderr, (
        f"die bestehende Kollisionsmeldung muss weiterhin erscheinen. "
        f"stderr={result.stderr!r}"
    )

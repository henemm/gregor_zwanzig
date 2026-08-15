"""TDD RED (Issue #1866, Fix-Workflow fix-1866-claim-freigabeweg):

Der Freigabeweg fuer das Datei-Claim-Gate (`--release <pfad>`,
`--release-session <name>`) existiert noch nicht. Die Blockade-Meldung wirbt
noch fuer `export GZ_FILE_CLAIM_OVERRIDE=1` als Notausgang, der strukturell
unerreichbar ist (Details: docs/specs/modules/fix_1866_claim_gate_freigabeweg.md).

Kein Mock-Theater: `.claude/hooks/file_claim_gate.py` wird per
`subprocess.run()` aufgerufen (nicht importiert/gepatcht), gegen eine echte
temporaere `file_claims.json` in einem echten Temp-Git-Repo. Kern-Schicht
(kein Netz, kein Live-Dienst) -- alle Operationen sind lokal und
deterministisch.

Pfadregel (#1409): der Pruefling wird relativ zur eigenen Testdatei
aufgeloest (`parents[2]` = Repo-Root bei `tests/unit/<datei>.py`), NIE ueber
einen hartcodierten Hauptrepo-Pfad -- sonst testet dieser Test aus einem
Worktree heraus die unveraenderte Hauptrepo-Kopie.

Getestete AC: AC-1, AC-2, AC-3, AC-6 (AC-4/AC-5 in
test_file_claim_gate_activity_expiry.py).
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


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True,
    )


def _run(args: list[str], cwd: Path, stdin_text: str = "") -> subprocess.CompletedProcess:
    """Ruft file_claim_gate.py als echten Subprozess auf. `CLAUDE_PROJECT_DIR`
    wird bewusst entfernt, damit `_find_main_repo_root()` NICHT das echte
    Projekt-Repo statt des isolierten Temp-Repos findet (hook_utils.py prueft
    diese Var vor jeder cwd-basierten Aufloesung)."""
    env = os.environ.copy()
    env.pop("CLAUDE_PROJECT_DIR", None)
    return subprocess.run(
        [sys.executable, str(_SCRIPT), *args],
        cwd=str(cwd),
        input=stdin_text,
        capture_output=True,
        text=True,
        timeout=15,
        env=env,
    )


def _init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main-line")
    _git(repo, "config", "user.email", "t@t.de")
    _git(repo, "config", "user.name", "Test")
    (repo / "README.md").write_text("# baseline\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "baseline")
    return repo


def _registry_path(repo: Path) -> Path:
    return repo / ".claude" / "file_claims.json"


def _write_registry(repo: Path, data: dict) -> None:
    reg = _registry_path(repo)
    reg.parent.mkdir(parents=True, exist_ok=True)
    reg.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


def _load_registry(repo: Path) -> dict:
    return json.loads(_registry_path(repo).read_text(encoding="utf-8"))


def _setup_collision_repo(tmp_path: Path) -> tuple[Path, Path]:
    """Hauptrepo + ein echter, per `git worktree add` angelegter Worktree mit
    dem Ordnernamen 'session-a' -- damit `_worktree_still_exists` (bestehende
    Logik) eine ECHTE, noch existierende fremde Session sieht und der
    Kollisionsfall in main() tatsaechlich (weiterhin) blockiert. AC-6 prueft
    nur den Meldungstext dieses echten Blockadefalls, nicht die
    Blockade-Entscheidung selbst."""
    main = tmp_path / "repo"
    main.mkdir()
    _git(main, "init", "-b", "main-line")
    _git(main, "config", "user.email", "t@t.de")
    _git(main, "config", "user.name", "Test")

    target = main / "some" / "collide.py"
    target.parent.mkdir(parents=True)
    target.write_text("content\n")
    _git(main, "add", "-A")
    _git(main, "commit", "-m", "baseline")

    wt = tmp_path / "worktrees" / "session-a"
    wt.parent.mkdir(parents=True)
    _git(main, "worktree", "add", str(wt), "-b", "wt-branch")

    return main, target


# ---------------------------------------------------------------------------
# AC-1: --release <pfad> entfernt den Eintrag und nennt Session/Branch/Zeit
# ---------------------------------------------------------------------------

def test_release_removes_entry_and_reports_details(tmp_path):
    repo = _init_repo(tmp_path)
    claimed_at = "2026-08-14T10:00:00+00:00"
    _write_registry(repo, {
        "some/file.py": {
            "session": "session-a",
            "branch": "feature-a",
            "claimed_at_epoch": time.time() - 100,
            "claimed_at": claimed_at,
        }
    })

    result = _run(["--release", "some/file.py"], cwd=repo)
    combined = result.stdout + result.stderr

    assert "session-a" in combined, (
        f"AC-1: Ausgabe muss die Session des geloeschten Eintrags nennen. "
        f"combined={combined!r} returncode={result.returncode}"
    )
    assert "feature-a" in combined, (
        f"AC-1: Ausgabe muss den Branch des geloeschten Eintrags nennen. combined={combined!r}"
    )
    assert claimed_at in combined, (
        f"AC-1: Ausgabe muss claimed_at des geloeschten Eintrags nennen. combined={combined!r}"
    )

    registry = _load_registry(repo)
    assert "some/file.py" not in registry, (
        f"AC-1: der Eintrag muss nach --release aus file_claims.json entfernt sein. "
        f"registry={registry!r}"
    )


# ---------------------------------------------------------------------------
# AC-2: --release <pfad> ohne bestehenden Eintrag crasht nicht und taeuscht
# keinen Erfolg vor
# ---------------------------------------------------------------------------

def test_release_without_existing_claim_reports_clearly_without_crash(tmp_path):
    repo = _init_repo(tmp_path)
    _write_registry(repo, {})

    result = _run(["--release", "some/other-file.py"], cwd=repo)
    combined = result.stdout + result.stderr

    assert "Traceback" not in combined, (
        f"AC-2: darf nicht mit unbehandelter Exception abbrechen. combined={combined!r}"
    )
    assert "kein aktiver Claim" in combined, (
        f"AC-2: muss klar melden, dass fuer den Pfad kein aktiver Claim existiert "
        f"('kein aktiver Claim'-Wortlaut aus der Spec). combined={combined!r}"
    )
    assert "some/other-file.py" in combined, (
        f"AC-2: die Meldung muss den angefragten Pfad nennen. combined={combined!r}"
    )
    # Darf NICHT wie die Erfolgsmeldung aus AC-1 aussehen (keine erfundenen
    # Session/Branch-Details einer nicht existierenden Belegung).
    assert "session-a" not in combined and "feature-a" not in combined, (
        f"AC-2: darf keine Belegungs-Details vortaeuschen, wenn keiner existiert. "
        f"combined={combined!r}"
    )

    registry = _load_registry(repo)
    assert registry == {}, f"AC-2: Registry darf unveraendert bleiben. registry={registry!r}"


# ---------------------------------------------------------------------------
# F001 (Adversary-Finding, HIGH): --release auf eine KAPUTTE Registry darf
# NICHT dieselbe "kein aktiver Claim"-Meldung/Exit-Code wie AC-2 liefern --
# beides waere fuer den Aufrufer nicht unterscheidbar (Spec AC-1 verlangt
# explizit eine unterscheidbare Fehlermeldung).
# ---------------------------------------------------------------------------

def test_release_with_corrupt_registry_is_distinguishable_from_no_claim(tmp_path):
    repo = _init_repo(tmp_path)
    reg = _registry_path(repo)
    reg.parent.mkdir(parents=True, exist_ok=True)
    reg.write_text("{ not valid json", encoding="utf-8")

    corrupt_result = _run(["--release", "some/other-file.py"], cwd=repo)

    combined = corrupt_result.stdout + corrupt_result.stderr
    assert "Traceback" not in combined, (
        f"F001: darf nicht mit unbehandelter Exception abbrechen. combined={combined!r}"
    )
    assert "kein aktiver Claim" not in combined, (
        f"F001: darf NICHT wie die 'kein aktiver Claim'-Meldung (AC-2, leere/fehlende Registry) "
        f"aussehen -- eine kaputte Registry ist ein anderer Fall. combined={combined!r}"
    )
    assert "beschaedigt" in combined or "nicht lesbar" in combined, (
        f"F001: muss erkennbar auf eine defekte/unlesbare Registry hinweisen. combined={combined!r}"
    )
    assert corrupt_result.returncode != 1, (
        f"F001: Exit-Code muss sich von AC-2 ('kein aktiver Claim', Exit 1) unterscheiden. "
        f"returncode={corrupt_result.returncode}"
    )
    assert reg.read_text(encoding="utf-8") == "{ not valid json", (
        "F001: die kaputte Registry-Datei darf durch den fehlgeschlagenen --release-Versuch "
        "nicht ueberschrieben werden."
    )


# ---------------------------------------------------------------------------
# AC-3: --release-session X entfernt NUR die X-Eintraege
# ---------------------------------------------------------------------------

def test_release_session_removes_only_matching_entries(tmp_path):
    repo = _init_repo(tmp_path)
    now = time.time()
    _write_registry(repo, {
        "a/one.py": {"session": "sess-x", "branch": "bx", "claimed_at_epoch": now, "claimed_at": "t1"},
        "a/two.py": {"session": "sess-x", "branch": "bx", "claimed_at_epoch": now, "claimed_at": "t2"},
        "b/three.py": {"session": "sess-y", "branch": "by", "claimed_at_epoch": now, "claimed_at": "t3"},
    })

    result = _run(["--release-session", "sess-x"], cwd=repo)
    combined = result.stdout + result.stderr

    assert "2" in combined, (
        f"AC-3: Ausgabe muss die Anzahl der entfernten Eintraege (2) nennen. combined={combined!r}"
    )
    assert "a/one.py" in combined and "a/two.py" in combined, (
        f"AC-3: Ausgabe muss die betroffenen Pfade nennen. combined={combined!r}"
    )

    registry = _load_registry(repo)
    assert set(registry.keys()) == {"b/three.py"}, (
        f"AC-3: nur sess-x-Eintraege duerfen entfernt werden, sess-y bleibt unveraendert. "
        f"registry={registry!r}"
    )
    assert registry["b/three.py"]["session"] == "sess-y", (
        f"AC-3: der verbleibende Eintrag darf nicht veraendert sein. registry={registry!r}"
    )


# ---------------------------------------------------------------------------
# AC-6: Blockade-Meldung wirbt fuer --release, nicht mehr fuer
# GZ_FILE_CLAIM_OVERRIDE als DEN wirksamen Ausweg
# ---------------------------------------------------------------------------

def test_blocking_message_advertises_release_not_env_override(tmp_path):
    main, target = _setup_collision_repo(tmp_path)
    _write_registry(main, {
        "some/collide.py": {
            "session": "session-a",
            "branch": "wt-branch",
            "claimed_at_epoch": time.time(),
            "claimed_at": datetime.now(timezone.utc).isoformat(),
        }
    })

    stdin_json = json.dumps({"tool_input": {"file_path": str(target)}})
    result = _run([], cwd=main, stdin_text=stdin_json)

    assert result.returncode == 2, (
        f"Testvoraussetzung fuer AC-6: ein echter, frischer Kollisionsfall mit "
        f"existierendem Fremd-Worktree muss weiterhin blockieren. "
        f"returncode={result.returncode} stderr={result.stderr!r}"
    )
    assert "--release" in result.stderr, (
        f"AC-6: die Blockade-Meldung muss auf `--release <pfad>` als wirksamen Ausweg "
        f"verweisen. stderr={result.stderr!r}"
    )
    assert "GZ_FILE_CLAIM_OVERRIDE" not in result.stderr, (
        f"AC-6: die Blockade-Meldung darf GZ_FILE_CLAIM_OVERRIDE nicht mehr als "
        f"Haupt-Ausweg bewerben (der env-Check im Code darf bestehen bleiben, nur "
        f"die Meldung nicht mehr dafuer werben). stderr={result.stderr!r}"
    )

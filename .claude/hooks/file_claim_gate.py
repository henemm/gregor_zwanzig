#!/usr/bin/env python3
"""Datei-Claim-Gate (PO-go 2026-08-13): meldet Edit/Write als Belegung, blockiert bei
Kollision mit einer anderen aktiven Session.

Jede Session traegt beim ersten Edit/Write einer Datei automatisch eine Belegung in eine
geteilte Registry ein (.claude/file_claims.json im HAUPTREPO, worktree-uebergreifend
sichtbar ueber find_project_root()/find_main_repo_from_worktree aus hook_utils.py). Ist
die Datei bereits von einer ANDEREN, noch aktiven Session belegt, wird der Edit/Write
blockiert -- Absprache per SendMessage statt stillem Konflikt erst beim Mergen.

Granularitaet: ganze Datei, nicht Zeile/Funktion (PO-Entscheid 2026-08-13). Begruendung:
Memory reference_werkstatt_radar_artifact -- #1200+#1134 kollidierten im selben Modul trotz
unterschiedlicher Funktionen, eine feinere Sperre haette das nicht verhindert.

Session-Kennung: Worktree-Ordnername (Konvention "ein Projektordner = eine Session",
CLAUDE.md -> Parallele Sessions). Verwaiste Belegungen (Worktree existiert laut
`git worktree list` nicht mehr, ODER seit STALE_AFTER_SECONDS nicht aufgefrischt) zaehlen
nicht als belegt.

Notausgang: `export GZ_FILE_CLAIM_OVERRIDE=1` (einmalig pro Session, falls die Belegung
nachweislich ein Irrtum ist).

Regel-Budget: Pruefdatum 2026-11-11 -- danach deaktiviert sich das Gate selbst;
Entscheidung (behalten/entfernen) faellt im Gate-Audit #1197.
Fail-open: JEDER Fehler (Registry nicht lesbar/schreibbar, Locking nicht moeglich,
Worktree-Erkennung schlaegt fehl, Parse-Fehler) blockiert NIE fremde Arbeit.
"""
import fcntl
import json
import os
import subprocess
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path

EXPIRY = date(2026, 11, 11)
STALE_AFTER_SECONDS = 4 * 60 * 60  # 4h ohne Auffrischung gilt als verwaist
OVERRIDE_ENV = "GZ_FILE_CLAIM_OVERRIDE"
REGISTRY_NAME = "file_claims.json"
LOCK_TIMEOUT_S = 2.0


def _find_main_repo_root() -> "Path | None":
    """Bevorzugt die bereits im Projekt vorhandene Worktree-Aufloesung (hook_utils.py) --
    Pruefort=Wirkort: dieselbe Funktion, die /radar und workflow.py fuer geteilten Zustand
    nutzen. Faellt sonst auf reines `git rev-parse --show-toplevel` zurueck (dann NICHT
    geteilt, aber besser als komplett auszufallen)."""
    try:
        sys.path.insert(0, "/home/hem/agent-os-openspec/core/hooks")
        from hook_utils import find_project_root  # type: ignore

        return find_project_root()
    except Exception:
        pass
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=5, check=True,
        )
        return Path(out.stdout.strip())
    except Exception:
        return None


def _session_id() -> str:
    """Worktree-Ordnername als Session-Kennung, sonst Branch, sonst 'unknown'."""
    cwd = Path.cwd()
    if "worktrees" in cwd.parts:
        return cwd.name
    try:
        out = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True, text=True, timeout=5, check=True,
        )
        return out.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def _current_branch() -> str:
    try:
        out = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True, text=True, timeout=5, check=True,
        )
        return out.stdout.strip() or "?"
    except Exception:
        return "?"


def _repo_relative_path(file_path: str, main_root: Path) -> "str | None":
    """Bildet einen absoluten Pfad (egal ob im Hauptrepo oder in einem Worktree) auf den
    repo-relativen Pfad ab, damit dieselbe logische Datei aus verschiedenen Worktrees
    heraus denselben Registry-Schluessel bekommt."""
    try:
        p = Path(file_path).resolve()
    except Exception:
        return None
    parts = p.parts
    if "worktrees" in parts:
        idx = parts.index("worktrees")
        if idx + 2 < len(parts):
            return "/".join(parts[idx + 2:])
        return None
    try:
        return str(p.relative_to(main_root))
    except ValueError:
        return None


def _worktree_still_exists(session: str, main_root: Path) -> bool:
    try:
        out = subprocess.run(
            ["git", "-C", str(main_root), "worktree", "list", "--porcelain"],
            capture_output=True, text=True, timeout=5, check=True,
        )
    except Exception:
        return True  # unsicher -> nicht voreilig als verwaist werten
    for line in out.stdout.splitlines():
        if line.startswith("worktree "):
            path = line[len("worktree "):].strip()
            if Path(path).name == session:
                return True
    return False


def _load_registry(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {}


def _save_registry(path: Path, registry: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(registry, fh, indent=2, sort_keys=True)
    tmp.replace(path)


def _acquire_lock(lock_path: Path):
    try:
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        fh = open(lock_path, "w")
    except Exception:
        return None
    deadline = time.time() + LOCK_TIMEOUT_S
    while True:
        try:
            fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return fh
        except BlockingIOError:
            if time.time() > deadline:
                fh.close()
                return None
            time.sleep(0.05)
        except Exception:
            fh.close()
            return None


def main() -> int:
    if date.today() > EXPIRY:
        return 0  # Pruefdatum erreicht (Regel-Budget) -> Gate inaktiv, Entscheidung: #1197

    if os.environ.get(OVERRIDE_ENV) == "1":
        return 0

    try:
        data = json.load(sys.stdin)
        file_path = (data.get("tool_input") or {}).get("file_path") or ""
    except Exception:
        return 0  # fail-open

    if not file_path:
        return 0

    main_root = _find_main_repo_root()
    if main_root is None:
        return 0

    rel_path = _repo_relative_path(file_path, main_root)
    if rel_path is None:
        return 0

    session = _session_id()
    registry_path = main_root / ".claude" / REGISTRY_NAME
    lock_fh = _acquire_lock(registry_path.with_suffix(".lock"))
    if lock_fh is None:
        return 0  # Lock nicht zu bekommen -> fail-open statt haengen/faelschlich blockieren

    try:
        registry = _load_registry(registry_path)
        now = time.time()
        entry = registry.get(rel_path)

        if entry:
            same_session = entry.get("session") == session
            age = now - entry.get("claimed_at_epoch", 0)
            still_fresh = age < STALE_AFTER_SECONDS
            other_still_active = _worktree_still_exists(entry.get("session", ""), main_root)

            if not same_session and still_fresh and other_still_active:
                sys.stderr.write(
                    "DATEI-CLAIM-GATE (PO-Wunsch 2026-08-13, Kollisionsvermeidung zwischen Sessions):\n"
                    f"{rel_path} ist gerade von einer anderen aktiven Session belegt:\n"
                    f"  Worktree/Branch: {entry.get('session')} ({entry.get('branch', '?')})\n"
                    f"  Belegt seit: {entry.get('claimed_at', '?')}\n"
                    "\n"
                    "-> Erst per SendMessage mit dieser Session abstimmen, dann weitermachen.\n"
                    "-> Falls die Belegung ein Irrtum ist (Datei laengst wieder frei, Registry nur\n"
                    "   nicht aktualisiert): einmalig `export GZ_FILE_CLAIM_OVERRIDE=1` setzen und\n"
                    "   erneut versuchen.\n"
                    f"(Verwaist automatisch nach {STALE_AFTER_SECONDS // 3600}h ohne Auffrischung "
                    f"oder wenn der Worktree weg ist. Pruefdatum dieses Gates: {EXPIRY.isoformat()}.)\n"
                )
                return 2

        registry[rel_path] = {
            "session": session,
            "branch": _current_branch(),
            "claimed_at_epoch": now,
            "claimed_at": datetime.now(timezone.utc).isoformat(),
        }
        _save_registry(registry_path, registry)
        return 0
    except Exception:
        return 0  # fail-open -- ein defekter Wächter darf nie blockieren
    finally:
        try:
            fcntl.flock(lock_fh, fcntl.LOCK_UN)
        except Exception:
            pass
        lock_fh.close()


if __name__ == "__main__":
    sys.exit(main())

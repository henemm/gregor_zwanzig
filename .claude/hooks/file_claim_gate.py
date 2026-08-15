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

Freigabeweg (Issue #1866): `python3 .claude/hooks/file_claim_gate.py --release <pfad>` bzw.
`--release-session <name>` -- der `export GZ_FILE_CLAIM_OVERRIDE=1`-Notausgang ist strukturell
unerreichbar (jeder PreToolUse-Aufruf ist ein eigener Kindprozess) und wird nicht mehr als
Weg beworben; die env-Pruefung bleibt im Code bestehen, schadet nicht.

Aktivitaets-Verfall (#1866): ein sonst blockierender Claim gilt zusaetzlich als beendet, wenn
die Datei im belegenden Worktree byte-identisch mit `origin/main` ist UND `git status
--porcelain` fuer den Pfad dort nichts meldet -- lockert nur zusaetzlich, verschaerft nie
(jeder Fehler beim Zusatz-Check -> nicht verfallen).

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


def _claim_expired_by_activity(entry: dict, rel_path: str, main_root: Path) -> bool:
    """Zusaetzlicher Verfall (#1866): nur relevant, wenn die bestehende Logik den Claim
    ohnehin als blockierend einstufen wuerde -- lockert nur zusaetzlich, verschaerft nie.
    Sicherheitsrichtung: JEDER Fehler (Git-Befehl schlaegt fehl, Worktree nicht auffindbar,
    origin/main nicht aufloesbar, Timeout) -> False (nicht verfallen)."""
    session = entry.get("session", "")
    try:
        out = subprocess.run(
            ["git", "-C", str(main_root), "worktree", "list", "--porcelain"],
            capture_output=True, text=True, timeout=5, check=True,
        )
    except Exception:
        return False

    wt_path = None
    for line in out.stdout.splitlines():
        if line.startswith("worktree "):
            path = line[len("worktree "):].strip()
            if Path(path).name == session:
                wt_path = Path(path)
                break
    if wt_path is None:
        return False

    try:
        status = subprocess.run(
            ["git", "-C", str(wt_path), "status", "--porcelain", "--", rel_path],
            capture_output=True, text=True, timeout=5, check=True,
        )
        if status.stdout.strip():
            return False  # lokale (un)staged Aenderung -> nicht verfallen

        origin = subprocess.run(
            ["git", "-C", str(wt_path), "show", f"origin/main:{rel_path}"],
            capture_output=True, timeout=5, check=True,
        )
        local_content = (wt_path / rel_path).read_bytes()
        return origin.stdout == local_content
    except Exception:
        return False


def _load_registry_strict(path: Path) -> dict:
    """Wie _load_registry, aber OHNE Fail-Open (#1866 F001): eine fehlende Datei bleibt {}
    (unveraendertes Verhalten), eine EXISTIERENDE, aber kaputte Registry wirft weiter --
    _load_registry() selbst bleibt fuer den Haupt-Hook-Pfad bewusst fail-open (Docstring
    dort) und wird hier NICHT angetastet; nur --release/--release-session brauchen laut
    Spec (AC-1) eine von 'kein aktiver Claim' unterscheidbare Fehlermeldung."""
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _handle_release(rel_path: str, main_root: Path) -> int:
    """CLI-Freigabeweg (#1866): entfernt genau einen Registry-Eintrag. Gleiches Locking wie
    der Hook-Pfad. Kein Crash, kein irrefuehrendes "gelöscht" wenn kein Claim existiert."""
    registry_path = main_root / ".claude" / REGISTRY_NAME
    lock_fh = _acquire_lock(registry_path.with_suffix(".lock"))
    if lock_fh is None:
        sys.stderr.write("DATEI-CLAIM-GATE: Lock nicht verfuegbar, --release abgebrochen.\n")
        return 1
    try:
        try:
            registry = _load_registry_strict(registry_path)
        except Exception as exc:
            sys.stderr.write(
                f"DATEI-CLAIM-GATE: Registry beschaedigt/nicht lesbar ({registry_path}): {exc}\n"
            )
            return 2
        entry = registry.pop(rel_path, None)
        if entry is None:
            sys.stdout.write(f"DATEI-CLAIM-GATE: kein aktiver Claim fuer {rel_path}.\n")
            return 1
        _save_registry(registry_path, registry)
        sys.stdout.write(
            f"DATEI-CLAIM-GATE: Belegung fuer {rel_path} entfernt "
            f"(Session: {entry.get('session', '?')}, Branch: {entry.get('branch', '?')}, "
            f"Belegt seit: {entry.get('claimed_at', '?')}).\n"
        )
        return 0
    except Exception as exc:
        sys.stderr.write(f"DATEI-CLAIM-GATE: --release fehlgeschlagen: {exc}\n")
        return 2
    finally:
        try:
            fcntl.flock(lock_fh, fcntl.LOCK_UN)
        except Exception:
            pass
        lock_fh.close()


def _handle_release_session(session: str, main_root: Path) -> int:
    """CLI-Freigabeweg (#1866): entfernt ALLE Eintraege einer Session. Gleiches Locking wie
    der Hook-Pfad. Kein Treffer -> klare "nichts zu tun"-Meldung, kein Fehler."""
    registry_path = main_root / ".claude" / REGISTRY_NAME
    lock_fh = _acquire_lock(registry_path.with_suffix(".lock"))
    if lock_fh is None:
        sys.stderr.write("DATEI-CLAIM-GATE: Lock nicht verfuegbar, --release-session abgebrochen.\n")
        return 1
    try:
        try:
            registry = _load_registry_strict(registry_path)
        except Exception as exc:
            sys.stderr.write(
                f"DATEI-CLAIM-GATE: Registry beschaedigt/nicht lesbar ({registry_path}): {exc}\n"
            )
            return 2
        matched = sorted(p for p, e in registry.items() if e.get("session") == session)
        if not matched:
            sys.stdout.write(
                f"DATEI-CLAIM-GATE: keine Belegungen fuer Session {session} gefunden, nichts zu tun.\n"
            )
            return 0
        for p in matched:
            del registry[p]
        _save_registry(registry_path, registry)
        sys.stdout.write(
            f"DATEI-CLAIM-GATE: {len(matched)} Belegung(en) fuer Session {session} entfernt: "
            f"{', '.join(matched)}.\n"
        )
        return 0
    except Exception as exc:
        sys.stderr.write(f"DATEI-CLAIM-GATE: --release-session fehlgeschlagen: {exc}\n")
        return 2
    finally:
        try:
            fcntl.flock(lock_fh, fcntl.LOCK_UN)
        except Exception:
            pass
        lock_fh.close()


def main() -> int:
    if date.today() > EXPIRY:
        return 0  # Pruefdatum erreicht (Regel-Budget) -> Gate inaktiv, Entscheidung: #1197

    argv = sys.argv[1:]
    if len(argv) >= 2 and argv[0] in ("--release", "--release-session"):
        main_root = _find_main_repo_root()
        if main_root is None:
            sys.stderr.write("DATEI-CLAIM-GATE: Hauptrepo nicht aufloesbar, Freigabe abgebrochen.\n")
            return 1
        if argv[0] == "--release":
            return _handle_release(argv[1], main_root)
        return _handle_release_session(argv[1], main_root)

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

    # #1878: geteilte Referenz-/Feature-Doku wird nie beansprucht. Getrennte
    # Zweige machen eine Doppelaenderung beim Mergen ohnehin als Konflikt
    # sichtbar, und bei Prosa ist der trivial aufzuloesen -- die Sperre kostet
    # dort viel und verhindert wenig. docs/specs/** bleibt beansprucht: eine
    # Spec gehoert waehrend eines laufenden Workflows genau einer Session.
    if rel_path.startswith("docs/") and not rel_path.startswith("docs/specs/"):
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

            if (
                not same_session and still_fresh and other_still_active
                and not _claim_expired_by_activity(entry, rel_path, main_root)
            ):
                sys.stderr.write(
                    "DATEI-CLAIM-GATE (PO-Wunsch 2026-08-13, Kollisionsvermeidung zwischen Sessions):\n"
                    f"{rel_path} ist gerade von einer anderen aktiven Session belegt:\n"
                    f"  Worktree/Branch: {entry.get('session')} ({entry.get('branch', '?')})\n"
                    f"  Belegt seit: {entry.get('claimed_at', '?')}\n"
                    "\n"
                    "-> Erst per SendMessage mit dieser Session abstimmen, dann weitermachen.\n"
                    "-> Falls die Belegung ein Irrtum ist (Datei laengst wieder frei, Registry nur\n"
                    f"   nicht aktualisiert): `python3 .claude/hooks/file_claim_gate.py --release {rel_path}`\n"
                    "   ausfuehren und erneut versuchen.\n"
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

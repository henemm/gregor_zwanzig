#!/usr/bin/env python3
"""Staging-Nachweise von origin holen (Issue #3289, Prod-Deploy per Pull).

Aufruf: python3 e2e_nachweis_holen.py <repo>

``staging_gate.py --write-verdict`` veroeffentlicht jeden Nachweis als Git-Note
unter ``refs/notes/e2e-verified`` am verifizierten Commit. Dieses Skript holt
die Notes-Ref von ``origin`` und legt fuer ``origin/main`` und seine letzten 40
Vorfahren (Fenster der Vorfahren-Regel, #1382) die Note als die gewohnte Datei
``.claude/e2e_verified/<sha>.json`` in die geteilte Ablage (wie staging_gate,
aufgeloest ab ``<repo>``). ``gate_check``, Vorfahren-Regel und
``prod_selftest.py`` bleiben dadurch unveraendert.

Fail-closed je Note: unlesbar, kein JSON-Objekt, ``verified_commit`` fehlt oder
nennt einen anderen Commit -> keine Datei. Eine vorhandene inhaltsgleiche Datei
bleibt unberuehrt. HEAD und Arbeitsbaum von ``<repo>`` werden nicht veraendert
(nur ``git fetch``).

Exit 0: geholt (auch: Notes-Ref existiert auf origin noch nicht).
Exit 1: Git-Fehler (origin nicht erreichbar, origin/main unbekannt).
Exit 2: Aufruffehler.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

NOTES_REF = "refs/notes/e2e-verified"
# origin/main selbst + 40 Vorfahren (Fenster von _e2e_paths._nearest_verified_ancestor)
WINDOW = 41


def _log(msg: str) -> None:
    print(f"[e2e-nachweis-holen] {msg}", file=sys.stderr)


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)


def _ablage(repo: Path) -> Path:
    """Geteilte Ablage wie staging_gate (``_e2e_paths``), ermittelt ab ``repo``."""
    paths_py = repo / ".claude" / "hooks" / "_e2e_paths.py"
    if paths_py.exists():
        spec = importlib.util.spec_from_file_location("_e2e_paths_holen", str(paths_py))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        shared = mod.shared_repo_dir(cwd=repo)
        return mod.commit_e2e_path(shared if shared is not None else repo, "X").parent
    return repo / ".claude" / "e2e_verified"


def _passende_note(text: str, sha: str) -> bool:
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return False
    return isinstance(data, dict) and data.get("verified_commit") == sha


def _gleich(path: Path, text: str) -> bool:
    try:
        vorhanden = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False
    if vorhanden == text:
        return True
    try:
        return json.loads(vorhanden) == json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return False


def _schreiben(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def holen(repo: Path) -> int:
    fetched = _git(repo, "fetch", "-q", "origin")
    if fetched.returncode != 0:
        _log(f"FEHLER: git fetch origin scheiterte: {fetched.stderr.strip()}")
        return 1
    remote = _git(repo, "ls-remote", "--exit-code", "origin", NOTES_REF)
    if remote.returncode == 2:
        _log(f"{NOTES_REF} existiert auf origin (noch) nicht — keine Nachweise zu holen.")
        return 0
    if remote.returncode != 0:
        _log(f"FEHLER: ls-remote {NOTES_REF} scheiterte: {remote.stderr.strip()}")
        return 1
    # Der Server erzeugt selbst keine Notes (write-verdict arbeitet auf einer
    # eigenen Hilfs-Ref) — der lokale Spiegel folgt origin daher per Force.
    notes = _git(repo, "fetch", "-q", "origin", f"+{NOTES_REF}:{NOTES_REF}")
    if notes.returncode != 0:
        _log(f"FEHLER: Holen von {NOTES_REF} scheiterte: {notes.stderr.strip()}")
        return 1
    revs = _git(repo, "rev-list", f"--max-count={WINDOW}", "origin/main")
    if revs.returncode != 0:
        _log(f"FEHLER: origin/main nicht aufloesbar: {revs.stderr.strip()}")
        return 1

    ablage = _ablage(repo)
    geschrieben = 0
    for sha in revs.stdout.split():
        shown = _git(repo, "notes", f"--ref={NOTES_REF}", "show", sha)
        if shown.returncode != 0:
            continue  # keine Note an diesem Commit
        text = shown.stdout
        if not _passende_note(text, sha):
            _log(f"Note an {sha[:8]} verworfen (unlesbar oder verified_commit passt nicht).")
            continue
        ziel = ablage / f"{sha}.json"
        if ziel.exists() and _gleich(ziel, text):
            continue
        _schreiben(ziel, text)
        geschrieben += 1
        _log(f"Nachweis fuer {sha[:8]} abgelegt: {ziel}")
    _log(f"fertig ({geschrieben} Nachweis-Datei(en) neu geschrieben).")
    return 0


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("Aufruf: e2e_nachweis_holen.py <repo>", file=sys.stderr)
        return 2
    repo = Path(argv[1]).resolve()
    if not repo.is_dir():
        print(f"Repo nicht gefunden: {repo}", file=sys.stderr)
        return 2
    return holen(repo)


if __name__ == "__main__":
    sys.exit(main(sys.argv))

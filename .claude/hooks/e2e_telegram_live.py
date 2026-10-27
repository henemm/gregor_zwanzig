"""
e2e_telegram_live.py — Verankerung für funktionale Telegram-Live-Tests (Issue #686).

Dependency-arm: nur stdlib, läuft unter System-python3 ohne App-Deps (siehe #685-Lehre).

Zweck: Wenn ein Change den Telegram-Pfad berührt und GZ_TELEGRAM_TEST_CHAT_ID fehlt,
blockt dieser Hook das Close-Gate (Exit != 0). Ein SKIPPED im Telegram-Live-Pfad
zählt nicht als grün.
"""
from __future__ import annotations

import os
import re
import sys


def gate(scope_touches_telegram: bool, env: dict) -> int:
    """Prüft ob der Telegram-Live-Test als bestanden gewertet werden darf.

    Args:
        scope_touches_telegram: True wenn der Change-Scope Telegram-Code berührt.
        env: Umgebungsvariablen (dict, z.B. dict(os.environ)).

    Returns:
        0  — bestanden oder sauberer Skip (Scope berührt Telegram nicht)
        1  — Nicht-bestanden (Telegram-Scope, aber kein Test-Chat konfiguriert)
    """
    if not scope_touches_telegram:
        # Sauberer Skip: Change berührt Telegram nicht → kein Live-Test nötig
        return 0

    chat_id = env.get("GZ_TELEGRAM_TEST_CHAT_ID", "").strip()
    if not chat_id:
        # Telegram-Scope berührt, aber kein Test-Chat-ID → Nicht-bestanden
        # SKIPPED zählt nicht als grün (AC-5)
        print(
            "ERROR: GZ_TELEGRAM_TEST_CHAT_ID ist nicht gesetzt.\n"
            "Der Change-Scope berührt Telegram. Ein SKIPPED Telegram-Live-Test\n"
            "gilt nicht als grün — bitte GZ_TELEGRAM_TEST_CHAT_ID setzen.",
            file=sys.stderr,
        )
        return 1

    # Token + Chat-ID vorhanden → Live-Test kann laufen (wird via pytest AC-4 ausgeführt)
    return 0


def _scope_touches_telegram(changed_files: list[str] | None = None,
                            diff_reader=None) -> bool:
    """Heuristik: prüft ob geänderte Dateien den Telegram-Pfad berühren.

    Wird vom __main__-Block genutzt wenn keine explizite Liste übergeben wird.
    Liest geänderte Dateien aus argv oder git diff --name-only HEAD~1.
    `diff_reader(pfad)` liefert die +/- Zeilen einer Datei (None = nicht
    lesbar ⇒ zählt als Telegram); ohne ihn unverändertes Verhalten (#2630).
    """
    import subprocess

    if changed_files is None:
        try:
            result = subprocess.run(
                ["git", "diff", "--name-only", "HEAD~1"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            changed_files = result.stdout.splitlines()
        except Exception:
            changed_files = []

    telegram_patterns = ("telegram", "inbound_telegram", "trip_command_processor")
    for f in changed_files:
        if _is_neutral_path(f):
            continue
        f_lower = f.lower()
        if any(p in f_lower for p in telegram_patterns):
            # #2630: reine Dateimodus-Änderung ist kein Telegram-Verhalten.
            if diff_reader is not None:
                lines = diff_reader(f)
                if lines is not None and _is_mode_only_change(lines):
                    continue
            return True
    return False


# Chmod: Ziel nur Bezeichner/Punktpfad, Modus nur fsmode.X, nichts danach.
_CHMOD_RE = re.compile(
    r"^(\w+\s*:?=\s*)?os\.[Cc]hmod\(\s*[\w.]+\s*,\s*fsmode\.\w+\s*\)$")
# Guard um den Chmod-Aufruf — nur die Fehlervariablen werr/err (F-R2-1).
_IF_NIL_RE = re.compile(r"^if (werr|err) == nil \{$")
_MODE_LINE_RES = (
    _CHMOD_RE,
    # Python-Import des fsmode-Moduls.
    re.compile(r"^(import\s+[\w.]*fsmode\w*|from\s+[\w.]+\s+import\s+fsmode)$"),
    # Go-Importpfad (optional mit Alias).
    re.compile(r'^(\w+\s+)?"[\w./-]*fsmode"$'),
)


def _is_comment_or_blank(text: str) -> bool:
    return text == "" or text.startswith("//") or text.startswith("#")


def _is_added_mode_line(text: str, has_chmod: bool) -> bool:
    """Whitelist für HINZUGEFÜGTE Zeilen eines reinen Dateimodus-Diffs (#2630).

    Nur eng verankerte Muster — eine Zeile, die `fsmode.` bloß enthält,
    ist NICHT neutral (F001). Der `if werr == nil {`-Guard nur zusammen
    mit einer Chmod-Zeile (F-R2-1)."""
    if _is_comment_or_blank(text) or text in ("{", "}", ")"):
        return True
    if _IF_NIL_RE.match(text):
        return has_chmod
    return any(r.match(text) for r in _MODE_LINE_RES)


def _is_mode_only_change(lines: list[str]) -> bool:
    """True nur, wenn ALLE +/- Zeilen der Modus-Whitelist entsprechen und
    mindestens eine Zeile `fsmode` nennt. Leere Liste ⇒ False (fail-closed).

    Entfernte Zeilen sind nur neutral, wenn leer oder reiner Kommentar —
    ein gelöschtes `}`/`)` verändert den Kontrollfluss (F-R2-1)."""
    if not lines:
        return False
    if not any("fsmode" in line for line in lines):
        return False
    added = [line[1:].strip() for line in lines if line.startswith("+")]
    removed = [line[1:].strip() for line in lines if not line.startswith("+")]
    if not all(_is_comment_or_blank(text) for text in removed):
        return False
    has_chmod = any(_CHMOD_RE.match(text) for text in added)
    return all(_is_added_mode_line(text, has_chmod) for text in added)


def _is_neutral_path(path: str) -> bool:
    """Doku-/Tooling-Pfade, die NIE den Telegram-Code-Pfad bilden (analog
    staging_gate._detect_committed_scope Neutral-Liste, Issue #728)."""
    return (
        path.startswith("docs/")
        or path.startswith(".claude/")
        or path.endswith(".md")
        or path.startswith("README")
        or path == ".gitignore"
        or path.startswith("tests/")
    )


if __name__ == "__main__":
    # Standalone-Aufruf: python3 e2e_telegram_live.py [file1 file2 ...]
    files = sys.argv[1:] if len(sys.argv) > 1 else None
    touches = _scope_touches_telegram(files)
    rc = gate(scope_touches_telegram=touches, env=dict(os.environ))
    if rc != 0:
        print(f"FAIL: Telegram-Live-Gate nicht bestanden (Exit {rc})", file=sys.stderr)
    sys.exit(rc)

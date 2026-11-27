"""
e2e_telegram_live.py — Verankerung für funktionale Telegram-Live-Tests (Issue #686).

Dependency-arm: nur stdlib, läuft unter System-python3 ohne App-Deps (siehe #685-Lehre).

Zweck: Wenn ein Change den Telegram-Pfad berührt, verlangt dieser Hook einen
commit-gebundenen Nachweis des Telegram-Live-Laufs
(``.claude/e2e_telegram_live/<sha>.json``, geschrieben von
``python3 .claude/tools/staging_telegram_live.py``), sonst blockt er das
Close-Gate (Exit != 0). Ein SKIPPED im Telegram-Live-Pfad zählt nicht als grün;
die bloße Anwesenheit von GZ_TELEGRAM_TEST_CHAT_ID im Environment genügt nicht
(Issue #2541, AC-6). Restrisiko: die Herkunft der Datei wird nicht geprüft.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

#: Ordnername des Nachweises unter ``<repo>/.claude/`` (eigener Ordner, damit
#: prune_old_attestations ihn nicht erfasst).
NACHWEIS_ORDNER = "e2e_telegram_live"
#: Soll-Live-Tests (einzige Quelle; das Werkzeug
#: .claude/tools/staging_telegram_live.py übernimmt diese Liste).
SOLL_TESTS = (
    "test_ac3_all_seven_commands_produce_meaningful_content",
    "test_ac4_live_delivery_and_cleanup",
    "test_ac25_live_menu_entspricht_der_vollstaendigen_ac21_liste",
    "test_ac24_hilfe_bei_trip_und_vergleich_antwortet_sofort_live",
    "test_heute_ohne_namen_bei_trip_und_vergleich_fragt_live_zurueck",
    "test_hilfe_englisch_dann_deutsch_live",
)
WERKZEUG_AUFRUF = "python3 .claude/tools/staging_telegram_live.py"
_SHA_RE = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")


def _ist_null(wert) -> bool:
    return isinstance(wert, int) and not isinstance(wert, bool) and wert == 0


def nachweis_mangel(commit, nachweis_dir) -> "str | None":
    """Prüft den Nachweis für genau ``commit``. None = gültig, sonst Grund."""
    if not isinstance(commit, str) or not _SHA_RE.match(commit):
        return f"verifizierter Commit unbekannt oder ungültig ({commit!r})"
    if nachweis_dir is None:
        return "kein Nachweis-Ordner angegeben"
    pfad = Path(nachweis_dir) / f"{commit}.json"
    try:
        daten = json.loads(pfad.read_text())
    except FileNotFoundError:
        return f"kein Nachweis für Commit {commit} ({pfad})"
    except (OSError, ValueError) as exc:
        return f"Nachweis nicht lesbar ({exc})"
    if not isinstance(daten, dict):
        return "Nachweis ist kein JSON-Objekt"
    if daten.get("commit") != commit:
        return f"Nachweis gehört zu Commit {daten.get('commit')!r}, nicht {commit}"
    for feld in ("skipped", "failures", "errors"):
        if not _ist_null(daten.get(feld)):
            return f"Nachweis meldet {feld}={daten.get(feld)!r} (muss 0 sein)"
    tests = daten.get("tests")
    if not isinstance(tests, list):
        return "Nachweis ohne Testliste"
    fehlend = [t for t in SOLL_TESTS if t not in tests]
    if fehlend:
        return f"Soll-Live-Tests fehlen im Nachweis: {', '.join(fehlend)}"
    passed = daten.get("passed")
    if (not isinstance(passed, int) or isinstance(passed, bool)
            or passed < len(SOLL_TESTS)):
        return f"Nachweis meldet passed={passed!r} (mindestens {len(SOLL_TESTS)})"
    return None


def gate(scope_touches_telegram: bool, commit=None, nachweis_dir=None,
         env=None) -> int:
    """Prüft ob der Telegram-Live-Test als bestanden gewertet werden darf.

    Args:
        scope_touches_telegram: True wenn der Change-Scope Telegram-Code berührt.
        commit: verifizierter Commit (SHA), für den der Nachweis gelten muss.
        nachweis_dir: Ordner mit ``<sha>.json``-Nachweisen.
        env: wird bewusst ignoriert — eine Chat-ID im Environment ersetzt den
            Nachweis nicht (#2541, AC-6).

    Returns:
        0  — bestanden oder sauberer Skip (Scope berührt Telegram nicht)
        1  — Nicht-bestanden (Telegram-Scope, kein gültiger Nachweis)
    """
    del env  # absichtlich ungenutzt
    if not scope_touches_telegram:
        return 0
    mangel = nachweis_mangel(commit, nachweis_dir)
    if mangel is None:
        return 0
    print(
        f"ERROR: Telegram-Live-Nachweis fehlt oder ist ungültig: {mangel}.\n"
        "Der Change-Scope berührt Telegram. Ein SKIPPED Telegram-Live-Test\n"
        f"gilt nicht als grün — bitte auf Staging ausführen: {WERKZEUG_AUFRUF}",
        file=sys.stderr,
    )
    return 1


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

    # #2681: Telegram-Texte kommen aus den Katalogen (src/i18n/).
    telegram_patterns = ("telegram", "inbound_telegram", "trip_command_processor", "src/i18n/")
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
    import subprocess

    files = sys.argv[1:] if len(sys.argv) > 1 else None
    touches = _scope_touches_telegram(files)

    def _git(*args) -> "str | None":
        try:
            r = subprocess.run(["git", *args], capture_output=True, text=True, timeout=10)
        except Exception:  # noqa: BLE001 — fail-closed: kein Commit => kein Nachweis
            return None
        return r.stdout.strip() if r.returncode == 0 else None

    head = _git("rev-parse", "HEAD")
    top = _git("rev-parse", "--show-toplevel")
    ordner = Path(top) / ".claude" / NACHWEIS_ORDNER if top else None
    rc = gate(scope_touches_telegram=touches, commit=head, nachweis_dir=ordner)
    if rc != 0:
        print(f"FAIL: Telegram-Live-Gate nicht bestanden (Exit {rc})", file=sys.stderr)
    sys.exit(rc)

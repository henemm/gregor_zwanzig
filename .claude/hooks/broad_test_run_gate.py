#!/usr/bin/env python3
"""Gate: Breiter Testlauf blockiert (Vorfall 2026-08-03, Telegram an den PO).

PreToolUse:Bash-Hook. Blockiert jeden ``pytest``-Aufruf, der KEINE konkreten
Testdateien benennt — also den vollen Suite-Lauf und Verzeichnis-Laeufe.

## Warum

Am 2026-08-03 haben volle ``uv run pytest``-Laeufe echte Telegram-Nachrichten
an den Produktiv-Chat des Product Owners geschickt. Ursache:
``tests/tdd/test_compare_alert_recipient_settings.py`` (aus #1452) traegt keinen
``live``/``staging``-Marker, laeuft also im Standardlauf mit, und baut sich
seine ``Settings`` selbst zusammen. Nicht gesetzte Telegram-Felder fallen dabei
still auf die ``.env`` im Arbeitsordner zurueck — und die ist eine Kopie der
PRODUKTIV-Datei (EnterWorktree kopiert sie). Ergebnis: echter Bot, echter Chat.

Derselbe Vorfall gab es am 2026-07-05 schon einmal. Damals entstand ein Riegel
(``tests/tdd/_telegram_live_fixture.py``, #1014) — der wirkt aber nur fuer
Tests, die ihn BENUTZEN. Ein Test, der ``Settings`` selbst baut, geht daran
vorbei. Und die Regel dazu stand im Memory, wurde aber nicht gelesen.

**Deshalb dieser Hook statt einer weiteren Notiz:** Was in dieser Sitzung
tatsaechlich Verhalten geaendert hat, waren ausnahmslos Hooks, nie
Dokumentation. Eine Regel, die nur wirkt, wenn ich sie vorher lese, ist keine
Absicherung.

## Regel

Erlaubt ist ein pytest-Aufruf, wenn mindestens eines zutrifft:

1. **Konkrete Testdatei(en) benannt** — z.B. ``uv run pytest tests/tdd/a.py``
   (Node-IDs mit ``::`` sind eingeschlossen). Der Normalfall.
2. **Nichts wird ausgefuehrt** — ``--collect-only`` / ``--co`` / ``--version`` /
   ``--help``.
3. **Netz ist gesperrt** — ``--disable-socket`` (pytest-socket). Dann ist auch
   ein voller Lauf ungefaehrlich; das ist zugleich die Richtung, in die das
   Projekt ohnehin soll (#1337 will genau so einen zentralen Ausgangs-Waechter
   selbst bauen, obwohl es ihn als fertiges Plugin gibt).
4. **Menschliche Freigabe** — gueltiges Einmal-Token aus ``override``. Das kann
   der Agent NICHT selbst erzeugen: ``user_override_token.json`` steht auf der
   Schutzliste des ``bash_gate``, und angelegt wird es nur, wenn der User das
   Wort woertlich tippt.

Verzeichnisse (``pytest tests/``, ``pytest tests/unit/``) gelten NICHT als
konkrete Auswahl — genau so faengt man sich einen ungemarkerten Live-Test ein.

Obfuskations-Fallback wie in ``prod_send_gate.py``: bei ``sh -c``/``eval`` oder
kaputten Quotes wird auf einen Roh-Scan des kompletten Kommandos zurueckgefallen.

Exit-Codes: 0 = erlaubt, 2 = blockiert.
"""
from __future__ import annotations

import json
import re
import shlex
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import hook_utils  # noqa: E402

_OVERRIDE_TTL = timedelta(hours=1)

# Tokens, die "es wird nichts ausgefuehrt" oder "Netz ist zu" bedeuten.
_SAFE_FLAGS = {
    "--collect-only", "--co", "--version", "--help", "-h",
    "--disable-socket",
    "--fixtures", "--markers",
}

# Eine konkrete Testdatei: endet auf .py, optional mit ::node-id.
_TEST_FILE_RE = re.compile(r"[^\s]+\.py(?:::[^\s]*)?$")

_NESTED_SHELL_RE = re.compile(r"\b(?:ba|z|da|k)?sh\s+-c\b|\beval\b")


def _project_root() -> Path:
    try:
        return hook_utils.find_project_root()
    except Exception:
        return Path(__file__).resolve().parents[2]


def _active_workflow_name() -> str:
    try:
        return hook_utils.get_active_workflow_name() or ""
    except Exception:
        return ""


def _has_valid_override(workflow_name: str) -> bool:
    """Gueltiges, nicht abgelaufenes Einmal-Token? (nicht verbrauchend gelesen)

    Bewusst NICHT verbrauchend: ein einzelner Testlauf soll nicht das Token
    fuer den naechsten Gate-Treffer derselben Freigabe wegnehmen. Die TTL
    begrenzt den Zeitraum.
    """
    if not workflow_name:
        return False
    token_path = _project_root() / ".claude" / "user_override_token.json"
    if not token_path.exists():
        return False
    try:
        data = json.loads(token_path.read_text())
    except (OSError, json.JSONDecodeError):
        return False
    entry = (data.get("tokens", {}) if isinstance(data, dict) else {}).get(workflow_name)
    if not isinstance(entry, dict):
        return False
    try:
        created = datetime.fromisoformat(entry.get("created", ""))
    except (TypeError, ValueError):
        return False
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - created <= _OVERRIDE_TTL


def _tokens(command: str) -> list[str] | None:
    """shlex-Tokens; None, wenn nicht verlaesslich zerlegbar."""
    if _NESTED_SHELL_RE.search(command):
        return None
    try:
        return shlex.split(command, posix=True)
    except ValueError:
        return None


_SEGMENT_SEPARATORS = {"&&", "||", ";", "|", "&"}
_TEXT_MATCH_COMMANDS = {
    "grep", "egrep", "fgrep", "rgrep", "zgrep", "pgrep", "rg", "ag", "ack",
}
_LAUNCHER_COMMANDS = {
    "env", "nice", "nohup", "sudo", "doas", "setsid", "timeout", "xargs",
    "time", "ionice", "chrt",
}
_PYTHON_LAUNCHER_RE = re.compile(r"^python3?(\.\d+)?$")


def _basename(token: str) -> str:
    """Letztes Pfadsegment -- 'pytest'-Erkennung soll pfad-qualifizierte
    Launcher (/usr/bin/python3, .venv/bin/python3) genauso treffen wie
    nackte Namen (Issue #1478 Teil 1, Adversary-Runde 3, Finding F007)."""
    return token.rsplit("/", 1)[-1]


def _nearest_non_flag_predecessor(tokens: list[str], index: int) -> "str | None":
    """Naechstes Token VOR `index` im selben Segment, das keine Flag
    (fuehrendes '-') ist. None am Segmentanfang (Trenner erreicht oder
    Listenanfang) -- dann gibt es kein Kommando, das 'pytest' als
    Suchmuster konsumiert haben koennte."""
    j = index - 1
    while j >= 0:
        tok = tokens[j]
        if tok in _SEGMENT_SEPARATORS:
            return None
        if not tok.startswith("-"):
            return tok
        j -= 1
    return None


def _pytest_invocations(tokens: list[str]) -> list[int]:
    """Indizes, an denen ein pytest-Lauf beginnt.

    Default: JEDES 'pytest'-/'*/pytest'-Token zaehlt als Aufrufbeginn.
    Zwei Faelle:

    1. Unmittelbar vorangehendes Flag-Token (fuehrendes '-'): der Vorgaenger
       HINTER ALLEN Flags wird ermittelt (`_nearest_non_flag_predecessor`
       ueberspringt beliebig viele Flags). Ist dieser Vorgaenger ein
       bekannter Prozess-Launcher (`_LAUNCHER_COMMANDS`) oder ein
       Python-Interpreter (`_PYTHON_LAUNCHER_RE` auf den Basename) ->
       'pytest' IST ein Aufruf, egal wie viele Flags dazwischen liegen
       (Issue #1478 Teil 1, Adversary-Runde 3, Finding F006: 'sudo -E
       pytest', 'nice -n10 pytest', 'xargs -I{} pytest' MUESSEN weiterhin
       blockiert werden). Sonst (Vorgaenger ist ein gewoehnliches Wort wie
       'commit', 'log', 'grep') ist 'pytest' dessen Freitext-Flag-Wert,
       kein eigener Aufruf (Finding F005: 'git commit -m pytest', 'git log
       --grep pytest', 'grep -m pytest').
    2. Kein vorangehendes Flag: der naechste Nicht-Flag-Vorgaenger im
       selben Segment wird direkt gegen `_TEXT_MATCH_COMMANDS` geprueft
       (Basename) -- 'pytest' ist dessen Suchmuster (grep -n "pytest"
       datei, pgrep -af "pytest"), sonst Default "ist ein Aufruf" (z.B.
       jeder bare Launcher: 'sudo pytest tests/', F001/AC-6).
    """
    hits: list[int] = []
    for i, tok in enumerate(tokens):
        if tok != "pytest" and not tok.endswith("/pytest"):
            continue
        if i > 0 and tokens[i - 1].startswith("-"):
            launcher = _nearest_non_flag_predecessor(tokens, i)
            launcher_base = _basename(launcher) if launcher is not None else None
            if launcher_base in _LAUNCHER_COMMANDS or (
                launcher_base is not None and _PYTHON_LAUNCHER_RE.match(launcher_base)
            ):
                hits.append(i)
            continue
        predecessor = _nearest_non_flag_predecessor(tokens, i)
        predecessor_base = _basename(predecessor) if predecessor is not None else None
        if predecessor_base in _TEXT_MATCH_COMMANDS:
            continue
        hits.append(i)
    return hits


def _args_after(tokens: list[str], start: int) -> list[str]:
    """Argumente nach dem pytest-Token bis zum naechsten Kommando-Trenner.

    Nutzt dieselbe Trenner-Menge wie `_nearest_non_flag_predecessor()`
    (`_SEGMENT_SEPARATORS`, seit Runde 2 inkl. '&') statt eines eigenen,
    unsynchronisierten Sets -- sonst erkennt `_pytest_invocations()` einen
    Aufruf korrekt an einer Segmentgrenze, aber `_args_after()` sammelt
    Tokens ueber genau diese Grenze hinweg ein (Issue #1478 Teil 1,
    Adversary-Runde 4, Finding F-ADV1: 'pytest tests/ & x.py' lief
    unblockiert durch, weil 'x.py' aus dem NAECHSTEN Segment faelschlich
    als benannte Testdatei des ERSTEN Aufrufs galt)."""
    stop = _SEGMENT_SEPARATORS | {">", ">>"}
    out = []
    for tok in tokens[start + 1:]:
        if tok in stop:
            break
        out.append(tok)
    return out


def _names_concrete_test_files(args: list[str]) -> bool:
    for a in args:
        if a.startswith("-"):
            continue
        if _TEST_FILE_RE.match(a):
            return True
    return False


def _has_safe_flag(args: list[str]) -> bool:
    for a in args:
        base = a.split("=", 1)[0]
        if base in _SAFE_FLAGS:
            return True
    return False


def _block(detail: str) -> None:
    print("=" * 70, file=sys.stderr)
    print("BLOCKED — Breiter Testlauf (Vorfall 2026-08-03)", file=sys.stderr)
    print("=" * 70, file=sys.stderr)
    print(detail, file=sys.stderr)
    print("", file=sys.stderr)
    print(
        "Ein Testlauf ohne benannte Dateien zieht ungemarkerte Live-Tests mit.\n"
        "Am 2026-08-03 gingen dadurch echte Telegram-Nachrichten an den\n"
        "PRODUKTIV-Chat des Product Owners (Test aus #1452, ohne live-Marker,\n"
        "Settings fallen still auf die Prod-.env im Arbeitsordner zurueck).",
        file=sys.stderr,
    )
    print("", file=sys.stderr)
    print("Erlaubte Wege:", file=sys.stderr)
    print("  1. Dateien benennen:  uv run pytest tests/tdd/x.py tests/unit/y.py", file=sys.stderr)
    print("  2. Nur sammeln:       uv run pytest --collect-only ...", file=sys.stderr)
    print("  3. Netz sperren:      uv run pytest --disable-socket ...  (pytest-socket)", file=sys.stderr)
    print("  4. Freigabe des Users: er tippt woertlich 'override' im Chat.", file=sys.stderr)
    print("", file=sys.stderr)
    print(
        "NICHT tun: diesen Hook abschalten, umgehen oder aufweichen, um\n"
        "weiterzukommen. Wenn du eine Gesamtaussage brauchst, frag den User.",
        file=sys.stderr,
    )
    print("=" * 70, file=sys.stderr)
    sys.exit(2)


def main() -> None:
    try:
        tool_input = hook_utils.get_tool_input()
        command = tool_input.get("command", "") if isinstance(tool_input, dict) else ""
    except Exception:
        command = ""
    if not command or "pytest" not in command:
        sys.exit(0)

    tokens = _tokens(command)

    if tokens is None:
        # Verschachtelte Shell / kaputte Quotes: konservativ auf dem Rohstring
        # pruefen. Kein Tokenizing moeglich -> nur die eindeutigen Freigaben.
        if re.search(r"--collect-only|--co\b|--version|--help|--disable-socket", command):
            sys.exit(0)
        if re.search(r"[^\s]+\.py(::[^\s]*)?(\s|$)", command):
            sys.exit(0)
        if _has_valid_override(_active_workflow_name()):
            sys.exit(0)
        _block(
            "Kommando nicht verlaesslich zerlegbar (verschachtelte Shell oder "
            "Quotes) und es sind keine konkreten Testdateien erkennbar."
        )

    starts = _pytest_invocations(tokens)
    if not starts:
        sys.exit(0)  # 'pytest' kam nur als Text vor (grep, Kommentar, Pfad)

    for start in starts:
        args = _args_after(tokens, start)
        if _has_safe_flag(args):
            continue
        if _names_concrete_test_files(args):
            continue
        if _has_valid_override(_active_workflow_name()):
            continue
        shown = " ".join(args[:8]) or "(keine Argumente)"
        _block(f"pytest-Aufruf ohne konkrete Testdateien: pytest {shown}")

    sys.exit(0)


if __name__ == "__main__":
    main()

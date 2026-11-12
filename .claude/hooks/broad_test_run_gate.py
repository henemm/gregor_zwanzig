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
3. **Sicherer Offline-Volllauf** (Issue #1755) — genau diese Zeile,
   einzeilig, woertlich (``--ignore=tests/red/`` darf fehlen, optional
   gefolgt von genau `` > <pfad> 2>&1``)::

       uv run pytest --disable-socket --allow-unix-socket --allow-hosts=127.0.0.1,::1,localhost --loopback-own-ports --ignore=tests/red/

   ``--disable-socket`` allein ist NICHT mehr frei: es sperrt auch lokale
   Test-Doubles (Lauf unbenutzbar), und die naheliegende Reparatur
   ``--allow-hosts=127.0.0.1`` liesse jeden Test Prod/Staging auf Loopback
   erreichen. ``--loopback-own-ports`` (``tests/_loopback_port_guard.py``)
   erlaubt Loopback nur zu selbst gebundenen Ports. Freigegeben wird per
   exaktem Vergleich des Rohstrings (``_offline_form_is_safe``, Fix-Loop 6),
   VOR jeder Zerlegung -- keine Shell-Deutung beteiligt. Fuenf Runden
   Shell-Zerlegung fanden je eine neue Umgehung (zuletzt Zeilenfortsetzung
   ``\\`` + Zeilenumbruch). Jede Abweichung (Zusatz-Flag, Praefix, Pipe,
   ``; echo``, Mehrzeilenform, anderer Leerraum) faellt ins normale Gate.

Ein ``override`` des Users oeffnet dieses Gate NICHT (mehr, Issue #2227): ein
breiter Lauf mit Netz ist genau der Weg des Produktiv-Versands aus #1477.

Verzeichnisse (``pytest tests/``, ``pytest tests/unit/``) gelten NICHT als
konkrete Auswahl — genau so faengt man sich einen ungemarkerten Live-Test ein.

Obfuskations-Fallback wie in ``prod_send_gate.py``: bei ``sh -c``/``eval`` oder
kaputten Quotes wird auf einen Roh-Scan des kompletten Kommandos zurueckgefallen.
Dort zaehlt jedes ``pytest``-Token als eigener Aufruf und wird einzeln mit
denselben Regeln geprueft -- keine Fruehausgaenge auf ``--co``/``.py`` irgendwo
im Kommando. In beiden Pfaden trennen ``; & | ( )`` und Zeilenumbruch die
Aufrufe, auch wenn sie am Wort kleben (Fix-Loop 2). Als benannte Datei zaehlen
keine Optionen (``--ignore=x.py``) und nur fuer BEKANNTE Wert-Optionen
(``_VALUE_OPTIONS``) auch nicht deren Wert in Leerzeichen-Form; unbekannte
Wert-Optionen, ``Verzeichnis/x.py`` und ``python -mpytest`` sind vorbestehende
Grenzen (Issue #2856).

Exit-Codes: 0 = erlaubt, 2 = blockiert.
"""
from __future__ import annotations

import re
import shlex
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import hook_utils  # noqa: E402

# Tokens, die "es wird nichts ausgefuehrt" bedeuten. ``--disable-socket``
# allein ist seit #1755 keine Freigabe mehr (siehe _offline_form_is_safe).
_SAFE_FLAGS = {
    "--collect-only", "--co", "--version", "--help", "-h",
    "--fixtures", "--markers",
}

# Sicherer Offline-Volllauf (#1755): die einzigen freien Zeilen, woertlich.
_OFFLINE_BASE_CALL = (
    "uv run pytest --disable-socket --allow-unix-socket "
    "--allow-hosts=127.0.0.1,::1,localhost --loopback-own-ports"
)
OFFLINE_CALL = _OFFLINE_BASE_CALL + " --ignore=tests/red/"
_OFFLINE_CALLS = (_OFFLINE_BASE_CALL, OFFLINE_CALL)
# Einzig erlaubter Zusatz: genau `` > <pfad> 2>&1``, Pfad ohne Shell-Zeichen.
_OFFLINE_REDIRECT_RE = re.compile(r" > ([A-Za-z0-9_./-]+) 2>&1")

# Eine konkrete Testdatei: endet auf .py, optional mit ::node-id.
_TEST_FILE_RE = re.compile(r"[^\s]+\.py(?:::[^\s]*)?$")

_NESTED_SHELL_RE = re.compile(r"\b(?:ba|z|da|k)?sh\s+-c\b|\beval\b")


def _tokens(command: str) -> list[str] | None:
    """shlex-Tokens; None, wenn nicht verlaesslich zerlegbar.

    Trenner (``; & | ( ) < >`` und Zeilenumbruch) werden eigene Tokens, auch
    wenn sie am Wort kleben -- sonst saehe ``pytest --disable-socket;`` die
    Argumente der Folgeanweisung (Fix-Loop 2). ``#`` ist kein Kommentar
    (mitten im Wort fuer die Shell ein normales Zeichen)."""
    if _NESTED_SHELL_RE.search(command):
        return None
    try:
        lex = shlex.shlex(command, posix=True, punctuation_chars=";&|()<>\n")
        lex.whitespace = lex.whitespace.replace("\n", "")
        lex.whitespace_split = True
        lex.commenters = ""
        return list(lex)
    except ValueError:
        return None


_SEGMENT_SEPARATORS = {"&&", "||", ";", "|", "&"}
_SEPARATOR_CHARS = set(";&|()\n")
_REDIRECT_OP_CHARS = set("<>&|")


def _is_separator(tok: str) -> bool:
    """Kommando-Trenner: Token nur aus ``; & | ( )`` / Zeilenumbruch."""
    return bool(tok) and set(tok) <= _SEPARATOR_CHARS


def _is_redirect(tok: str) -> bool:
    """Umleitungsoperator: nur ``< > & |`` und mindestens ein ``<``/``>``
    (``>``, ``>>``, ``<``, ``>&`` aus ``2>&1``, ``&>``, ``>|``)."""
    return bool(tok) and set(tok) <= _REDIRECT_OP_CHARS and bool(set(tok) & set("<>"))


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
        if tok in _SEGMENT_SEPARATORS or _is_separator(tok):
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
    als benannte Testdatei des ERSTEN Aufrufs galt).

    Umleitungen (``>``, ``>>``, ``<``, ``>&``, ``&>`` ...) beenden die
    Argumente NICHT: die Shell reicht Woerter dahinter an pytest weiter
    (``pytest ... > o.txt -p no:socket``). Operator und sein Ziel werden
    uebersprungen, Ende nur an Befehlstrennern (Fix-Loop 5, F001).

    Ein Token, das mit ``#`` BEGINNT, ist fuer die Shell ein Kommentar: der
    Aufruf wird fail-closed mit leeren Argumenten bewertet, also blockiert
    (Fix-Loop 7, F001). ``#`` mitten im Wort (``x.py#``) bleibt normal."""
    out = []
    skip_target = False
    for tok in tokens[start + 1:]:
        if tok in _SEGMENT_SEPARATORS or _is_separator(tok):
            break
        if tok.startswith("#"):
            return []
        if skip_target:
            skip_target = False
            continue
        if _is_redirect(tok):
            skip_target = True
            continue
        out.append(tok)
    return out


# Optionen, deren Wert in Leerzeichen-Form folgt -- der Wert ist keine
# benannte Testdatei (Fix-Loop 2: ``pytest --ignore x.py``).
_VALUE_OPTIONS = {
    "--ignore", "--ignore-glob", "--deselect", "--rootdir", "--confcutdir",
    "--basetemp", "-c", "-p", "-k", "-m", "-o",
}


def _names_concrete_test_files(args: list[str]) -> bool:
    """Optionen (fuehrendes '-') zaehlen nie; uebersprungen wird zusaetzlich
    nur der Wert BEKANNTER Wert-Optionen in Leerzeichen-Form
    (``_VALUE_OPTIONS``, z. B. ``--ignore x.py``). Vorbestehende Grenzen
    (Issue #2856): Werte unbekannter Wert-Optionen, ``Verzeichnis/x.py`` und
    ``python -mpytest``."""
    skip_value = False
    for a in args:
        if skip_value:
            skip_value = False
            continue
        if a.startswith("-"):
            skip_value = a in _VALUE_OPTIONS
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


def _offline_form_is_safe(command: str) -> bool:
    """Sichere Offline-Form (#1755, Fix-Loop 6): exakter Vergleich.

    Frei nur, wenn ``command.strip(" \\n")`` woertlich eine der Zeilen aus
    ``_OFFLINE_CALLS`` ist, optional gefolgt von genau `` > <pfad> 2>&1``
    (Pfad ``[A-Za-z0-9_./-]+``, nicht mit ``-`` beginnend). Entschieden auf
    dem Rohstring VOR jeder Zerlegung: keine Shell-Deutung (Quotes,
    Zeilenfortsetzung, Umgebung, Trenner) ist beteiligt. Gestrippt werden nur
    ASCII-Leerzeichen und Zeilenumbruch, kein Unicode-Leerraum wie NBSP --
    daran trennt die Shell nicht (Fix-Loop 7, F003)."""
    line = command.strip(" \n")
    for call in _OFFLINE_CALLS:
        if line == call:
            return True
        if not line.startswith(call):
            continue
        m = _OFFLINE_REDIRECT_RE.fullmatch(line[len(call):])
        if m and not m.group(1).startswith("-"):
            return True
    return False


def _invocation_ok(args: list[str]) -> bool:
    """Ein einzelner pytest-Aufruf ist frei: nichts wird ausgefuehrt oder
    konkrete Dateien benannt (Token- und Roh-Pfad gemeinsam). Die
    Offline-Form wird vorher in ``main`` auf dem Rohstring entschieden."""
    return _has_safe_flag(args) or _names_concrete_test_files(args)


def _raw_split(command: str) -> list[str]:
    """Roh-Fallback: Quotes entfernen, an Leerraum zerlegen und Trenner
    (``; & | ( ) < >``, Zeilenumbruch) als eigene Tokens abtrennen. Regex
    statt shlex: ohne Quotes koennte ein ``#`` am Wortanfang den Rest
    als Kommentar verschlucken. Tokens mit fuehrendem ``#`` blockt danach
    ``_args_after`` fail-closed (Fix-Loop 7, F001)."""
    flat = re.sub(r"[\"'\\]", " ", command).replace("\n", " ; ")
    return [t for t in re.split(r"\s+|([;&|()<>]+)", flat) if t]


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
    print("  3. Sicherer Offline-Volllauf (#1755), einzeilig, woertlich:", file=sys.stderr)
    print(f"       {OFFLINE_CALL}", file=sys.stderr)
    print("     optional dahinter genau ' > datei 2>&1'; jede andere Abweichung", file=sys.stderr)
    print("     blockt. (--disable-socket allein reicht NICHT mehr.)", file=sys.stderr)
    print("", file=sys.stderr)
    print(
        "NICHT tun: diesen Hook abschalten, umgehen oder aufweichen, um\n"
        "weiterzukommen. Wenn du eine Gesamtaussage brauchst, frag den User.",
        file=sys.stderr,
    )
    print("=" * 70, file=sys.stderr)
    sys.exit(2)


def _check_raw(command: str) -> None:
    """Verschachtelte Shell / kaputte Quotes: konservativ auf dem Rohstring
    pruefen. JEDES 'pytest'-Token zaehlt als Aufruf, jeder muss fuer sich
    frei sein; keine Fruehausgaenge auf '--co'/'.py' irgendwo im Kommando
    (Fix-Loop 2). Kein 'pytest'-Token -> Block."""
    flat = _raw_split(command)
    starts = [i for i, t in enumerate(flat) if t == "pytest" or t.endswith("/pytest")]
    if starts and all(_invocation_ok(_args_after(flat, s)) for s in starts):
        sys.exit(0)
    _block(
        "Kommando nicht verlaesslich zerlegbar (verschachtelte Shell oder "
        "Quotes) und nicht jeder pytest-Aufruf ist frei."
    )


def main() -> None:
    try:
        tool_input = hook_utils.get_tool_input()
        command = tool_input.get("command", "") if isinstance(tool_input, dict) else ""
    except Exception:
        command = ""
    if not command or "pytest" not in command:
        sys.exit(0)
    if _offline_form_is_safe(command):
        sys.exit(0)  # Rohstring-Vergleich vor jeder Zerlegung (Fix-Loop 6)

    tokens = _tokens(command)
    if tokens is None:
        _check_raw(command)

    starts = _pytest_invocations(tokens)
    if not starts:
        sys.exit(0)  # 'pytest' kam nur als Text vor (grep, Kommentar, Pfad)

    for start in starts:
        args = _args_after(tokens, start)
        if _invocation_ok(args):
            continue
        shown = " ".join(args[:8]) or "(keine Argumente)"
        _block(f"pytest-Aufruf ohne konkrete Testdateien: pytest {shown}")

    sys.exit(0)


if __name__ == "__main__":
    main()

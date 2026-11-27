#!/usr/bin/env python3
"""Gate: Ausgabe-Umleitung nach /tmp blockiert (Issue #1688, Gate-Audit #1197).

PreToolUse:Bash-Hook. Blockiert Schreibziele (``>``, ``>>``, ``tee``, ``--output``,
``--junitxml``, ``--log-file``, ``--html``, ``--report-log``) direkt unter ``/tmp``,
``/var/tmp`` oder ``/dev/shm``, wenn der Pfad NICHT im privaten Sitzungs-Scratchpad
``/tmp/claude-<uid>/...`` (Modus 700) liegt.

## Warum

Testlaeufe wurden per ``uv run pytest ... > /tmp/pytest_full.log`` umgeleitet.
``/tmp`` ist fuer jeden lokalen Serverbenutzer lesbar; fuenf solche Dateien trugen
in #1380 gueltige Zugangsdaten im Klartext. ``secret_egress_guard.py`` sieht das
nicht: im Kommandotext steht kein Geheimwert, nur das ZIEL. Das Ziel ist vor dem
Entstehen der Datei pruefbar.

## Abgrenzung (Fehlalarm-Klasse ist der teure Teil)

Geprueft werden nur SCHREIBZIELE, nie das Wort ``/tmp`` an sich: Lesen
(``cat /tmp/x``), ``< /tmp/x``, ``ls /tmp`` und Ziele in Projekt, Home oder
Scratchpad bleiben frei. ``/dev/null`` und fd-Duplizierung (``2>&1``) ebenso.
Relative Ziele gelten als Projekt. Pfade werden normalisiert (``/tmp/../tmp/x``,
``/tmp/claude-1/../x``). Nicht zerlegbare Kommandos und ``sh -c``/``eval`` fallen
auf einen Roh-Scan zurueck. Nicht erfasst: Ziele, die erst die Shell berechnet
(``$VAR/x``), und Schreiber ausserhalb von Bash.

Exit-Codes: 0 = erlaubt, 2 = blockiert. Eigene Stoerung: fail-open (Exit 0).
"""
from __future__ import annotations

import json
import posixpath
import re
import shlex
import sys

_PUBLIC_ROOTS = ("/tmp", "/var/tmp", "/dev/shm")
# Privates Sitzungs-Scratchpad: /tmp/claude-<uid>/... (Verzeichnis 700).
_PRIVATE_RE = re.compile(r"^/tmp/claude-[A-Za-z0-9_.-]+(?:/|$)")
_OUTPUT_OPTIONS = ("--output", "--junitxml", "--log-file", "--html", "--report-log")
_SEPARATOR_CHARS = set(";&|()\n")
_NESTED_SHELL_RE = re.compile(r"\b(?:ba|z|da|k)?sh\s+-c\b|\beval\b")
_RAW_RE = re.compile(
    r"""(?:>>?\|?|\btee(?:\s+-[A-Za-z-]+)*|--(?:output|junitxml|log-file|html|report-log)[=\s])
        \s*["']?(/(?:tmp|var/tmp|dev/shm)(?:/[^\s"';&|)]*)?)""",
    re.VERBOSE,
)


def _is_public_tmp(path: str) -> bool:
    """True, wenn ``path`` (normalisiert) in einem weltlesbaren Temp-Verzeichnis liegt
    und nicht im privaten Scratchpad."""
    if not path.startswith("/"):
        return False
    norm = posixpath.normpath(path)
    if norm.startswith("//"):  # POSIX: genau zwei fuehrende Slashes bleiben erhalten
        norm = "/" + norm.lstrip("/")
    if _PRIVATE_RE.match(norm + "/"):
        return False
    return any(norm == root or norm.startswith(root + "/") for root in _PUBLIC_ROOTS)


def _tokens(command: str) -> list[str] | None:
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


def _is_separator(tok: str) -> bool:
    return bool(tok) and set(tok) <= _SEPARATOR_CHARS


def _targets_from_tokens(tokens: list[str]) -> list[str]:
    found: list[str] = []
    in_tee = False
    for i, tok in enumerate(tokens):
        if _is_separator(tok):
            in_tee = False
            continue
        nxt = tokens[i + 1] if i + 1 < len(tokens) else ""
        if tok and set(tok) <= set("<>&|") and ">" in tok:
            # ">&1" / ">&-" duplizieren einen fd, ">&datei" und "&>datei" schreiben.
            if nxt and not _is_separator(nxt) and not (tok.endswith("&") and (nxt.isdigit() or nxt == "-")):
                found.append(nxt)
            continue
        if tok == "tee" or tok.endswith("/tee"):
            in_tee = True
            continue
        if in_tee:
            if not tok.startswith("-"):
                found.append(tok)
            continue
        for opt in _OUTPUT_OPTIONS:
            if tok == opt and nxt and not _is_separator(nxt):
                found.append(nxt)
            elif tok.startswith(opt + "="):
                found.append(tok.split("=", 1)[1])
    return found


def blocked_targets(command: str) -> list[str]:
    tokens = _tokens(command)
    if tokens is None:
        candidates = [m.group(1) for m in _RAW_RE.finditer(command)]
    else:
        candidates = _targets_from_tokens(tokens)
    return [c for c in candidates if _is_public_tmp(c)]


def _block(targets: list[str]) -> None:
    err = sys.stderr
    print("=" * 70, file=err)
    print("BLOCKED - Ausgabe nach /tmp (Issue #1688, Leck-Kanal aus #1380)", file=err)
    print("=" * 70, file=err)
    print("Schreibziel: " + ", ".join(targets), file=err)
    print("", file=err)
    print(
        "/tmp ist fuer jeden lokalen Serverbenutzer lesbar. Umgeleitete Testausgaben\n"
        "haben dort Klartext-Zugangsdaten offengelegt (#1380).\n"
        "Richtiges Ziel: das private Sitzungs-Scratchpad (Pfad steht im Systemprompt,\n"
        "Form /tmp/claude-<uid>/<projekt>/<sitzung>/scratchpad/, Modus 700) oder ein\n"
        "Pfad im Projekt. Beispiel:\n"
        "  uv run pytest tests/x.py > <scratchpad>/pytest.log 2>&1",
        file=err,
    )
    sys.exit(2)


def main() -> None:
    try:
        payload = json.load(sys.stdin)
        tool_input = payload.get("tool_input", {}) if isinstance(payload, dict) else {}
        command = tool_input.get("command", "") if isinstance(tool_input, dict) else ""
        if not isinstance(command, str) or not command:
            sys.exit(0)
        targets = blocked_targets(command)
    except SystemExit:
        raise
    except Exception as exc:  # fail-open, aber nicht lautlos (nur der Typ)
        print(f"tmp_redirect_gate: Stoerung {type(exc).__name__}, nicht geprueft", file=sys.stderr)
        sys.exit(0)
    if targets:
        _block(targets)
    sys.exit(0)


if __name__ == "__main__":
    main()

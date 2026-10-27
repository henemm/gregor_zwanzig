# doc-compliance-test
"""Struktur-Waechter: keine unmaskierte Empfaenger-/Chat-Kennung als
``logger.*``-Argument (#2157 AC-f).

Spec: docs/specs/modules/pii_log_masking.md (AC-f, Known Limitations)

Der Waechter parst ``src/`` per ``ast`` (Struktur, keine Textsuche; Vorbild
``tests/test_user_id_default_guard.py``). Gemeldet wird ein Aufruf
``<logger>.<level>(...)``, bei dem einer der kanonischen Namen ``mail_to``,
``empfaenger`` oder ``chat_id`` UNVERPACKT erscheint: als direktes Argument
oder als Platzhalter ``{name}`` in einem f-String. Eingewickelt in einen
Maskierer (``mask_number(chat_id)``) ist er kein Fund. Aliase und andere
Variablennamen entgehen dem Waechter strukturell (Known Limitations) -- er
ist eine Regressionsbremse fuer kuenftigen Code, kein Beweis fuer den
Ist-Code (den fuehren die Verhaltenstests AC-b bis AC-e).

Regel-Budget: neues Gate, Pruefdatum 2026-12-26.
"""
from __future__ import annotations

import ast
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]

_PII_NAMEN = frozenset({"mail_to", "empfaenger", "chat_id"})
_LOGGER_NAMEN = frozenset({"logger", "log", "_logger", "LOGGER", "_log"})
_LOG_METHODEN = frozenset({
    "debug", "info", "warning", "warn", "error", "exception", "critical", "log",
})


def _ist_log_aufruf(knoten: ast.Call) -> bool:
    f = knoten.func
    return (
        isinstance(f, ast.Attribute)
        and f.attr in _LOG_METHODEN
        and isinstance(f.value, ast.Name)
        and f.value.id in _LOGGER_NAMEN
    )


def _unverpackte_pii_namen(argument: ast.AST) -> list[str]:
    if isinstance(argument, ast.Name) and argument.id in _PII_NAMEN:
        return [argument.id]
    if isinstance(argument, ast.JoinedStr):
        return [
            teil.value.id for teil in argument.values
            if isinstance(teil, ast.FormattedValue)
            and isinstance(teil.value, ast.Name)
            and teil.value.id in _PII_NAMEN
        ]
    return []


def finde_unmaskierte_log_argumente(wurzel: Path, unterordner: str) -> set[tuple[str, int, str]]:
    """(Datei relativ zu ``wurzel``, Zeile, Name) je unmaskiertem Fund."""
    funde: set[tuple[str, int, str]] = set()
    for datei in sorted((wurzel / unterordner).rglob("*.py")):
        baum = ast.parse(datei.read_text(encoding="utf-8"), filename=str(datei))
        rel = datei.relative_to(wurzel).as_posix()
        for knoten in ast.walk(baum):
            if not (isinstance(knoten, ast.Call) and _ist_log_aufruf(knoten)):
                continue
            for argument in [*knoten.args, *(k.value for k in knoten.keywords)]:
                for name in _unverpackte_pii_namen(argument):
                    funde.add((rel, knoten.lineno, name))
    return funde


def test_ac_f_waechter_meldet_gepflanzte_fundstelle(tmp_path):
    """Empfindlichkeit: gepflanzte unmaskierte Zeilen werden benannt gemeldet,
    maskierte Gegenproben nicht."""
    paket = tmp_path / "src" / "gepflanzt"
    paket.mkdir(parents=True)
    (paket / "modul.py").write_text(
        "import logging\n"
        "logger = logging.getLogger(__name__)\n"
        "def f(chat_id, empfaenger, mail_to, mask_number, mask_addr_for_pii_log):\n"
        "    logger.info(chat_id)\n"
        "    logger.warning('Versand an %s', empfaenger)\n"
        "    logger.error(f'Fehler fuer {mail_to}: x')\n"
        "    logger.info(f'Chat {mask_number(chat_id)}')\n"
        "    logger.info('an %s', mask_addr_for_pii_log(empfaenger))\n"
        "    print(chat_id)\n",
        encoding="utf-8",
    )

    funde = finde_unmaskierte_log_argumente(tmp_path, "src")

    assert funde == {
        ("src/gepflanzt/modul.py", 4, "chat_id"),
        ("src/gepflanzt/modul.py", 5, "empfaenger"),
        ("src/gepflanzt/modul.py", 6, "mail_to"),
    }, f"Waechter meldet falsch: {sorted(funde)}"


def test_ac_f_src_hat_keine_unmaskierten_log_argumente():
    """Ist-Stand: ``src/`` enthaelt keine unmaskierte Fundstelle."""
    funde = finde_unmaskierte_log_argumente(_REPO, "src")
    assert funde == set(), (
        "#2157 AC-f: unmaskierte Empfaenger-/Chat-Kennung als Log-Argument -- "
        "per mask_addr_for_pii_log() (E-Mail) bzw. mask_number() (Telegram) "
        "maskieren:\n" + "\n".join(f"  {d}:{z} ({n})" for d, z, n in sorted(funde))
    )

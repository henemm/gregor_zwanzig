#!/usr/bin/env python3
"""Playwright-CI-Gate-Auswerter (#1771 Scheibe 2, AC-4).

Liest den JSON-Report des Playwright-Reporters (`stats`: expected/
unexpected/skipped) und prueft DREI Bedingungen statt nur "keine Roten":
1. unexpected == 0
2. skipped == 0
3. expected >= E2E_MIN_EXECUTED (Schwelle aus der Umgebung)

Ohne Bedingung 3 waere ein Lauf gruen, in dem der Stack nie hochkam und
kein Test lief ("0 Tests, 0 rot" ist kein Beweis). Aufruf:
python3 e2e_gate.py <report.json> -- Exit 0 = alle drei erfuellt.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def _lade_report(pfad: Path) -> dict:
    if not pfad.exists():
        raise SystemExit(f"FEHLER: Playwright-Report '{pfad.name}' existiert nicht unter '{pfad}'.")
    try:
        return json.loads(pfad.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"FEHLER: Playwright-Report '{pfad.name}' nicht auswertbar: {exc}") from exc


def _lade_min_executed() -> int:
    """Fail-closed: eine fehlende/unbrauchbare Schwelle ist 'Nachweis nicht
    erbringbar', nicht 'Gate kaputt' -- dieselbe Linie wie das Frontend-
    Browser-Gate (#1558). Der alte Default '0' machte Bedingung 3
    (expected < min_executed) stillschweigend wirkungslos, sobald die
    Variable fehlte (Gegenlese-Fund, Defekt 2)."""
    roh = os.environ.get("E2E_MIN_EXECUTED")
    if roh is None or roh.strip() == "":
        raise SystemExit(
            "FEHLER: E2E_MIN_EXECUTED ist nicht gesetzt -- eine fehlende Schwelle "
            "macht Bedingung 3 wirkungslos und wird deshalb blockiert statt "
            "durchgelassen."
        )
    try:
        wert = int(roh)
    except ValueError as exc:
        raise SystemExit(f"FEHLER: E2E_MIN_EXECUTED='{roh}' ist keine gueltige Ganzzahl.") from exc
    if wert <= 0:
        raise SystemExit(f"FEHLER: E2E_MIN_EXECUTED='{roh}' muss eine positive Ganzzahl sein.")
    return wert


def main() -> int:
    if len(sys.argv) < 2:
        print("FEHLER: kein Report-Pfad uebergeben. Aufruf: e2e_gate.py <report.json>", file=sys.stderr)
        return 2
    report_pfad = Path(sys.argv[1])
    min_executed = _lade_min_executed()
    stats = _lade_report(report_pfad).get("stats", {})
    expected = int(stats.get("expected", 0))
    unexpected = int(stats.get("unexpected", 0))
    skipped = int(stats.get("skipped", 0))

    verstoesse: list[str] = []
    if unexpected != 0:
        verstoesse.append(f"{unexpected} unerwartete (rote) Testfaelle (unexpected != 0).")
    if skipped != 0:
        verstoesse.append(f"{skipped} uebersprungene Testfaelle -- Skip-Budget verbraucht.")
    if expected < min_executed:
        verstoesse.append(f"nur {expected} von mindestens {min_executed} ausgefuehrten Testfaellen (expected < E2E_MIN_EXECUTED).")

    if verstoesse:
        print(f"E2E-GATE ROT ({report_pfad.name}):", file=sys.stderr)
        for zeile in verstoesse:
            print(f"  - {zeile}", file=sys.stderr)
        print(f"Zahlen: expected={expected} unexpected={unexpected} skipped={skipped} "
              f"E2E_MIN_EXECUTED={min_executed}", file=sys.stderr)
        return 1
    print(f"E2E-GATE GRUEN ({report_pfad.name}): expected={expected} "
          f">= E2E_MIN_EXECUTED={min_executed}, keine Roten, keine Skips.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Kostenloser Vorab-Check vor dem Premium-SMS-Live-Nachweis (Issue #1533 S4).

Prueft `report.sms_text` fuer `morning` UND `evening` gegen die reale
Trip-Konfiguration -- Laenge <= 160 Zeichen und GSM-7-Reinheit -- ueber den
bestehenden Vorschau-Pfad (`PreviewService.render_sms_preview`). Kein
Realversand, keine SMS-Kosten.

Warum vorab: der Premium-SMS-Kanal kostet Geld und wird nur vom PO befristet
eingeschaltet (Runbook `docs/runbooks/premium_sms_generalprobe.md`). Alles,
was ohne Aktivierung pruefbar ist, muss VOR dem ersten kostenpflichtigen
Versand geprueft sein.

Usage:
    uv run python3 scripts/premium_sms_preflight_check.py \
        --trip-id <trip-id> --user-id <user-id>
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

# EINE Zeichensatz-Definition fuer alle SMS-Pfade (#1533 S4). Ein eigener
# zweiter Tabellen-Abzug hier koennte von den Waechtern abdriften, ohne dass
# einer der beiden rot wird.
from tests.tdd._gsm7_charset import _GSM7_CHARSET  # noqa: E402

REPORT_TYPES = ("morning", "evening")
MAX_SMS_CHARS = 160


def _check_sms_text(text: str, *, max_chars: int = MAX_SMS_CHARS) -> list[str]:
    """Verstoss-Beschreibungen fuer einen SMS-Text (leer = sauber).

    Nicht-werfende Schwester von `assert_gsm7_clean` -- der Vorab-Check soll
    ALLE Befunde beider Report-Typen zeigen, statt beim ersten abzubrechen.
    """
    verstoesse: list[str] = []
    if len(text) > max_chars:
        verstoesse.append(
            f"Laenge {len(text)} > {max_chars} Zeichen -- der Text wird gekuerzt "
            "oder auf mehrere SMS aufgeteilt."
        )
    for ch in dict.fromkeys(c for c in text if c not in _GSM7_CHARSET):
        verstoesse.append(
            f"Zeichen {ch!r} (U+{ord(ch):04X}) ist nicht im GSM-7-Zeichensatz "
            "(GSM 03.38) -- die SMS wechselt dadurch in UCS-2 (67 statt 153 "
            "Zeichen je Teil) bzw. kostet zwei Septets."
        )
    return verstoesse


def run(
    trip_id: str, user_id: str, *, demo: bool = False, service=None,
) -> dict[str, dict]:
    """Prueft beide Report-Typen und liefert je Typ Text, Laenge und Befunde.

    `service`: fertiger `PreviewService` (Test-Einspeisung). None -> Standard.
    """
    if service is None:
        from services.preview_service import PreviewService
        service = PreviewService()

    ergebnis: dict[str, dict] = {}
    for report_type in REPORT_TYPES:
        _subject, sms = service.render_sms_preview(
            trip_id, user_id=user_id, report_type=report_type, demo=demo,
        )
        ergebnis[report_type] = {
            "text": sms,
            "length": len(sms),
            "violations": _check_sms_text(sms),
        }
    return ergebnis


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trip-id", required=True)
    parser.add_argument("--user-id", required=True)
    parser.add_argument(
        "--demo", action="store_true",
        help="Wetterdaten aus Fixtures statt Live-API (kein Netz).",
    )
    args = parser.parse_args(argv)

    ergebnis = run(args.trip_id, args.user_id, demo=args.demo)
    for report_type, befund in ergebnis.items():
        print(f"\n[{report_type}] {befund['length']} Zeichen")
        print(f"  {befund['text']}")
        for verstoss in befund["violations"]:
            print(f"  VERSTOSS: {verstoss}")
    beanstandet = [rt for rt, b in ergebnis.items() if b["violations"]]
    if beanstandet:
        print(f"\nNICHT aktivieren -- Verstoesse in: {', '.join(beanstandet)}")
        return 1
    print("\nBeide Report-Typen sauber.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

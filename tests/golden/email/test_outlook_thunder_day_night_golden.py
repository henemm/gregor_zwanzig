"""Golden-Snapshot: Ausblick-Gewitterzelle mit Tag UND Nacht (Issue #1653 AC-8).

Die fuenf Profil-Goldens dieser Suite zeigen kein Mehrtages-Ausblick-Gewitter
ab Stufe „mittel" -- die Fehlerklasse „Tageswort mit Nachtstunde gepaart" bzw.
„das schwaechere der beiden Ereignisse verschwindet" konnte deshalb bisher
unbemerkt zurueckkehren. Dieser Snapshot friert HTML-Zelle und Klartext-Zeile
fuer die drei gemessenen Faelle des Issues ein:

  Fall A: kein Tagesgewitter, Nacht „hoch" 00:00
  Fall B: Tag „mittel" 14:00, Nacht „hoch" 00:00
  Fall C: Tag „hoch" 14:00, Nacht „mittel" 22:00

Neu einfrieren nach bewusster Aenderung: ``uv run python3
tests/golden/email/regenerate.py`` deckt diesen Snapshot NICHT ab -- die
erwartete Datei per Hand aus dem neuen Output ersetzen und die Aenderung im
PR begruenden.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from output.renderers.email.outlook import render_outlook_plain, render_outlook_table
from output.tokens.dto import HourlyValue

GOLDEN_PATH = Path(__file__).parent / "outlook-thunder-day-night.txt"


def _stage(weekday: str, name: str, thunder: str, hourly) -> dict:
    return dict(
        weekday=weekday, name=name, temp_lo=12, temp_hi=24,
        precip_mm=1.2, wind_dir="W", wind_kmh=18, thunder=thunder,
        hourly_precip=(), hourly_wind=(), hourly_gust=(),
        hourly_thunder=hourly,
    )


ROWS = [
    _stage("Mo", "Fall A – nur Nacht", "NONE", (HourlyValue(hour=0, value=3.0),)),
    _stage("Di", "Fall B – Tag + Nacht", "MED",
           (HourlyValue(hour=14, value=2.0), HourlyValue(hour=0, value=3.0))),
    _stage("Mi", "Fall C – Tag stärker", "HIGH",
           (HourlyValue(hour=14, value=3.0), HourlyValue(hour=22, value=2.0))),
]


def _render() -> str:
    return (
        render_outlook_table(ROWS)
        + "\n---\n"
        + render_outlook_plain(ROWS)
    )


def test_outlook_thunder_day_night_matches_golden():
    if not GOLDEN_PATH.exists():
        pytest.fail(
            f"Golden fehlt: {GOLDEN_PATH}\n"
            f"Issue #1653 AC-8 verlangt einen versionierten Snapshot mit Tag- "
            f"UND Nachtgewitter ab Stufe 'mittel'."
        )
    assert _render() == GOLDEN_PATH.read_text(encoding="utf-8")

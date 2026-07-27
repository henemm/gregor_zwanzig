"""PARITAETS-WAECHTER — die Trip-Mail darf sich in KEINEM Byte aendern.

SPEC: docs/specs/modules/issue_1361_1368_ausblick_konfigurierbar.md AC-11
KONTEXT: docs/context/fix-1361-1368-ausblick-konfigurierbar.md

Dieser Test ist der EINZIGE dieses Slices, der schon vor der Implementierung
gruen ist — und er muss gruen BLEIBEN. `src/output/renderers/email/outlook.py`
ist der vollstaendig geteilte Ausblick-Baustein von Trip UND Ortsvergleich;
jede Aenderung daran trifft strukturell auch die Trip-Mail (Risiko 2 der Spec).
Die Spec erlaubt ausschliesslich additive, per Default-Parameter abgeschirmte
Erweiterungen: `metrics=None` und der Default-`heading` reproduzieren exakt das
bisherige Verhalten.

Referenz sind aufgezeichnete Golden-Dateien mit dem Stand VOR dem Umbau
(`tests/fixtures/outlook_trip_parity/`), NICHT ein zweiter Aufruf desselben
Codes im selben Lauf — ein Vorher/Nachher-Vergleich innerhalb eines Laufs
aendert sich mit dem Code mit und beweist nichts.

WICHTIG fuer die GREEN-Phase: die Golden-Dateien sind der Beweis. Sie werden
NICHT neu erzeugt, wenn dieser Test rot wird — ein roter Lauf hier heisst, dass
die Trip-Mail sich veraendert hat.

Kern-Schicht, deterministisch: keine Mocks, kein Netz, echte
SegmentWeatherSummary-/ForecastDataPoint-/HourlyValue-Objekte.
"""
from __future__ import annotations

import difflib
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Berlin")
_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "outlook_trip_parity"


def parity_rows() -> list[dict]:
    """Trip-Ausblick-Zeilen wie der Scheduler sie baut
    (`trip_report_scheduler._build_stage_trend` + Anreicherung um
    `name`/`note`, Z.1449-1451) — inklusive einer Zeile MIT Notiz, damit die
    `note`-Ausgabe (`    ↳ ...`) mit im Vergleich steckt.
    """
    from output.tokens.dto import HourlyValue

    def _row(weekday, name, note, temp_lo, temp_hi, precip, wind, thunder, conf, gust):
        return dict(
            weekday=weekday, name=name, note=note,
            temp_lo=temp_lo, temp_hi=temp_hi, precip_mm=precip,
            wind_dir="W", wind_kmh=wind, thunder=thunder,
            rain_probability_pct=55, confidence_pct=conf,
            hourly_precip=(HourlyValue(hour=14, value=2.1),),
            hourly_wind=(HourlyValue(hour=15, value=float(wind)),),
            hourly_gust=(HourlyValue(hour=15, value=float(gust)),),
            hourly_thunder=(HourlyValue(hour=16, value=2.0),),
        )

    return [
        _row("Mo", "Etappe A", "Hütte geschlossen", 9, 21, 2.5, 18, "MED", 82, 44),
        _row("Di", "Etappe B", None, 11, 19, 0.0, 25, "NONE", 55, 31),
    ]


def _diff(expected: str, actual: str) -> str:
    return "\n".join(difflib.unified_diff(
        expected.splitlines(), actual.splitlines(),
        fromfile="aufgezeichnet (vor dem Umbau)", tofile="jetzt", lineterm="",
    ))


def test_trip_outlook_html_is_byte_identical():
    """AC-11 (HTML): Given dieselben Ausblick-Zeilen wie vor dem Umbau / When
    der Trip-Renderpfad `render_outlook_table(rows, show_acc=True)` sie rendert
    / Then ist die Ausgabe byte-identisch zur aufgezeichneten Referenz —
    inklusive Sieben-Spalten-Kopf (Tag/N/D/R/PR/Wind/Böen/Gew) und ACC-Spalte.
    """
    from output.renderers.email.outlook import render_outlook_table

    expected = (_FIXTURES / "trip_outlook_show_acc_true.html").read_text(encoding="utf-8")
    actual = render_outlook_table(parity_rows(), show_acc=True)

    assert actual == expected, (
        "Die HTML-Ausblick-Tabelle der TRIP-Mail hat sich veraendert. Der "
        "Ausblick-Baustein ist mit dem Ortsvergleich geteilt — die neue "
        "Spaltenauswahl darf ausschliesslich additiv und per Default-Parameter "
        "abgeschirmt sein (AC-11, Spec 'Was sich NICHT aendern darf').\n"
        + _diff(expected, actual)
    )


def test_trip_outlook_plain_is_byte_identical():
    """AC-11 (Klartext): Given dieselben Ausblick-Zeilen / When der Trip-
    Renderpfad `render_outlook_plain(rows, show_acc=True)` sie rendert / Then
    ist die Ausgabe byte-identisch zur aufgezeichneten Referenz — inklusive
    Ueberschrift "Nächste Etappen", 26-Zeichen-Etappennamen-Feld und
    Notiz-Zeilen.
    """
    from output.renderers.email.outlook import render_outlook_plain

    expected = (_FIXTURES / "trip_outlook_show_acc_true.txt").read_text(encoding="utf-8")
    actual = render_outlook_plain(parity_rows(), show_acc=True)

    assert actual == expected, (
        "Der Klartext-Ausblick der TRIP-Mail hat sich veraendert. Der neue "
        "`heading`-Parameter muss den Default 'Nächste Etappen' behalten und "
        "das feste Namensfeld darf fuer Aufrufer ohne Auswahl bleiben "
        f"(AC-11).\nErwartet: {expected!r}\nErhalten: {actual!r}\n"
        + _diff(expected, actual)
    )


def test_build_outlook_row_without_selection_is_unchanged():
    """AC-11 (Zeilenbau): Given eine SegmentWeatherSummary + Punktliste / When
    `build_outlook_row(...)` OHNE Auswahl aufgerufen wird (Trip-Aufruf) / Then
    entsteht exakt das bisherige feste Dict — der neue `metrics`-Parameter ist
    rein additiv (Spec Implementation Details Punkt 3).
    """
    from app.models import ForecastDataPoint, SegmentWeatherSummary, ThunderLevel
    from output.renderers.email.outlook import build_outlook_row
    from output.tokens.dto import HourlyValue

    summary = SegmentWeatherSummary(
        temp_min_c=9.4, temp_max_c=21.6, precip_sum_mm=3.5,
        wind_max_kmh=28.0, thunder_level_max=ThunderLevel.MED, pop_max_pct=60,
    )
    points = [
        ForecastDataPoint(ts=datetime(2026, 7, 20, 12, 0, tzinfo=timezone.utc),
                          gust_kmh=42.0, thunder_level=ThunderLevel.MED,
                          precip_1h_mm=1.5, wind10m_kmh=22.0),
        ForecastDataPoint(ts=datetime(2026, 7, 20, 13, 0, tzinfo=timezone.utc),
                          gust_kmh=38.0, thunder_level=ThunderLevel.NONE,
                          precip_1h_mm=0.0, wind10m_kmh=18.0),
    ]

    expected = {
        "weekday": "Mo",
        "temp_lo": 9,
        "temp_hi": 21,
        "precip_mm": 3.5,
        "wind_dir": "",
        "wind_kmh": 28,
        "thunder": "MED",
        "hourly_precip": (HourlyValue(hour=14, value=1.5),
                          HourlyValue(hour=15, value=0.0)),
        "hourly_wind": (HourlyValue(hour=14, value=22.0),
                        HourlyValue(hour=15, value=18.0)),
        "hourly_gust": (HourlyValue(hour=14, value=42.0),
                        HourlyValue(hour=15, value=38.0)),
        "hourly_thunder": (HourlyValue(hour=14, value=1.0),
                           HourlyValue(hour=15, value=0.0)),
        "rain_probability_pct": 60,
    }

    row = build_outlook_row(summary, points, "Mo", TZ)

    assert row == expected, (
        "Der Trip-Zeilenbau `build_outlook_row(...)` ohne Auswahl liefert nicht "
        "mehr das bisherige feste Dict — der `metrics`-Parameter ist damit nicht "
        f"rein additiv (AC-11).\nErwartet: {expected}\nErhalten: {row}"
    )

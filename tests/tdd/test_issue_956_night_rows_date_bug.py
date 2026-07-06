"""TDD RED — Issue #956, Teil D: Nacht-Zeit-Datumsbug in _extract_night_rows().

Root Cause (docs/context/fix-956-email-format.md, Teil D):
`src/formatters/trip_report.py::_extract_night_rows()`, Zeile 298:
    is_next_day = local_dt.date() > first_date
Das ist "größer als", nicht "genau ein Tag später". Liefert das night_weather-
Objekt mehr als einen Folgetag an Stundendaten (z. B. weil der Provider mehrere
Tage liefert), rutschen Datenpunkte von *übermorgen* mit Stunde ≤ 6 fälschlich
als zusätzliche "Nacht"-Zeile in die Tabelle.

Fix-Richtung (NICHT in dieser RED-Phase umsetzen):
    is_next_day = local_dt.date() == first_date + timedelta(days=1)

Diese Tests sind reine Datumslogik ohne visuelles Element — daher ein
klassischer pytest-Test (begründete Ausnahme von der PO-"visuell"-Vorgabe,
siehe Spec-Abschnitt "Sonderfall TDD-RED"). KEINE Mocks: echte
NormalizedTimeseries + ForecastDataPoint Datenobjekte, echte Methode.

Test 4 (AC-3): Ankunftstag + Folgetag + Übermorgen (Stunden ≤ 6)
    → KEINE Zeile darf Übermorgen-Datenpunkte enthalten.
Test 5 (AC-3, Regressionsschutz): Ankunftstag + GENAU ein Folgetag
    → bisheriges korrektes Verhalten bleibt erhalten.
"""

from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from app.metric_catalog import build_default_display_config
from app.models import (
    ForecastDataPoint,
    ForecastMeta,
    NormalizedTimeseries,
    Provider,
)
from output.renderers.trip_report import TripReportFormatter

_UTC = ZoneInfo("UTC")


def _make_meta() -> ForecastMeta:
    return ForecastMeta(
        provider=Provider.OPENMETEO,
        model="icon_d2",
        run=datetime(2026, 7, 15, 0, 0, tzinfo=timezone.utc),
        grid_res_km=2.0,
        interp="nearest",
    )


def _dp(day: int, hour: int, temp: float) -> ForecastDataPoint:
    """Ein Stundendatenpunkt am gegebenen Tag/Stunde (UTC)."""
    return ForecastDataPoint(
        ts=datetime(2026, 7, day, hour, 0, tzinfo=timezone.utc),
        t2m_c=temp,
        wind10m_kmh=10.0,
        gust_kmh=20.0,
        pop_pct=10,
        precip_1h_mm=0.0,
    )


def _formatter_utc() -> TripReportFormatter:
    fmt = TripReportFormatter()
    # _tz wird sonst erst in format_email() gesetzt; für den Direktaufruf
    # von _extract_night_rows() explizit setzen (echte Instanz, kein Mock).
    fmt._tz = _UTC
    return fmt


def test_extract_night_rows_ignores_day_after_next():
    """Test 4 (AC-3): Übermorgen-Stunden ≤ 6 dürfen NICHT in die Nacht-Tabelle.

    GIVEN Stundendaten für Ankunftstag (15.), direkten Folgetag (16.) UND
          Übermorgen (17.) mit Stunden ≤ 6
    WHEN  _extract_night_rows(arrival_hour=20) aufgerufen wird
    THEN  enthält KEINE zurückgegebene Zeile Datenpunkte vom 17. (Übermorgen).

    RED: Aktuell (`> first_date`) landen die 17.-Datenpunkte mit Stunde ≤ 6
    fälschlich in einem eigenen Block und erscheinen als zusätzliche Zeile.
    """
    arrival_hour = 20
    data: list[ForecastDataPoint] = []
    # Ankunftstag ab 20:00 bis 23:00
    for h in range(20, 24):
        data.append(_dp(15, h, 12.0))
    # Folgetag 00:00 bis 06:00
    for h in range(0, 7):
        data.append(_dp(16, h, 10.0))
    # Übermorgen 00:00 bis 06:00 — DARF NICHT auftauchen
    for h in range(0, 7):
        data.append(_dp(17, h, 8.0))

    ts = NormalizedTimeseries(meta=_make_meta(), data=data)
    fmt = _formatter_utc()
    dc = build_default_display_config()

    rows = fmt._extract_night_rows(ts, arrival_hour=arrival_hour, interval=2, dc=dc)

    # Alle vom 17. stammenden Datenpunkt-Zeitstempel
    day_after_next_ts = {
        dp.ts for dp in data if dp.ts.astimezone(_UTC).date().day == 17
    }

    # Kein zurückgegebener Block darf einen 17.-Datenpunkt aggregiert haben.
    # Wir prüfen das strukturell: Ohne den Bug entstehen genau die Blöcke
    # aus 15./16.; mit dem Bug entsteht ein zusätzlicher 00-Block für den 17.
    # Da die Zeilen keine Datum-Info tragen, prüfen wir die Blockanzahl:
    #   Ankunftstag 20-23 -> Blöcke 20, 22            (2)
    #   Folgetag    00-06 -> Blöcke 00, 02, 04, 06    (4)
    #   => korrekt: 6 Zeilen. Mit Bug: zusätzlicher Übermorgen-00-Block wird
    #      mit demselben (date, block_start)-Key separat gruppiert -> 7 Zeilen.
    time_labels = [r["time"] for r in rows]
    # Der Bug erzeugt eine zweite "00"-Zeile (Folgetag-00 + Übermorgen-00).
    assert time_labels.count("00") == 1, (
        "Übermorgen-Datenpunkte (17., Stunde ≤ 6) sind fälschlich als "
        f"zusätzliche '00'-Nacht-Zeile aufgetaucht. time_labels={time_labels}"
    )
    assert len(rows) == 6, (
        "Erwartet 6 Nacht-Blöcke (Ankunftstag 20/22 + Folgetag 00/02/04/06); "
        f"Übermorgen-Daten haben zusätzliche Zeilen erzeugt. rows={time_labels}, "
        f"day_after_next_count={len(day_after_next_ts)}"
    )


def test_extract_night_rows_keeps_full_next_day():
    """Test 5 (AC-3, Regressionsschutz): Ankunftstag + GENAU ein Folgetag.

    GIVEN Stundendaten für Ankunftstag (15.) und GENAU einen Folgetag (16.),
          keine weiteren Tage
    WHEN  _extract_night_rows(arrival_hour=20) aufgerufen wird
    THEN  bleiben alle Folgetag-Stunden ≤ 6 erhalten (Normalfall unverändert).

    Dieser Test muss vor UND nach dem Fix grün sein — er schützt gegen ein
    zu strenges "==", das den Normalfall bricht. In der RED-Phase ist er
    aktuell grün (der Normalfall funktioniert bereits); er dient als
    Regressions-Sicherung. Falls die RED-Suite ihn rot zeigt, wäre das ein
    Setup-Fehler, kein Bug-Nachweis.
    """
    arrival_hour = 20
    data: list[ForecastDataPoint] = []
    for h in range(20, 24):
        data.append(_dp(15, h, 12.0))
    for h in range(0, 7):
        data.append(_dp(16, h, 10.0))

    ts = NormalizedTimeseries(meta=_make_meta(), data=data)
    fmt = _formatter_utc()
    dc = build_default_display_config()

    rows = fmt._extract_night_rows(ts, arrival_hour=arrival_hour, interval=2, dc=dc)

    time_labels = [r["time"] for r in rows]
    # Ankunftstag 20-23 -> 20, 22 ; Folgetag 00-06 -> 00, 02, 04, 06
    assert time_labels == ["20", "22", "00", "02", "04", "06"], (
        f"Normalfall (nur Ankunftstag + ein Folgetag) verändert. rows={time_labels}"
    )

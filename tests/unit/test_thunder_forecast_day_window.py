"""Gewitter-Vorschau der Trip-Mail: Tagesfenster statt Kalendertag (#1498, Fall 2).

Repro aus dem Issue-Kommentar (Staging-Mail vom 2026-08-04): die
„⚡ Gewitter-Vorschau" sagte „05.08.2026: Leichtes Gewitter moeglich ab
02:00", die Nacht-Tabelle DERSELBEN Mail zeigte fuer 02:00 „kein". Beide
Vorschau-Bauwege (Trend-Zeile UND Fallback-Fetch) lasen bisher den vollen
Kalendertag 00-23 — also auch die Nachtstunden, fuer die die Nacht-Tabelle
mit eigener Quelle (``night_weather``) zustaendig ist.

Erwartung nach dem Fix: die Vorschau ist eine TAGES-Aussage und liest nur
das geteilte Tagesfenster (Default 04-19, pro Trip konfigurierbar,
``resolve_configured_window`` — dieselbe Konvention wie SMS/Telegram/
Fusszeile, ADR-0025). Nachtstunden gehoeren der Nacht-Tabelle; die beiden
Aussagen ueberlappen sich nicht mehr.

#1651 (additiv): dieselbe TAGES-Aussage (``level``/``hour``) bleibt
geklemmt, der Fliesstext nennt das Gewitter ausserhalb des Fensters aber
seit dieser Scheibe zusaetzlich mit Uhrzeit — verschwiegen wird es nicht
mehr. Die Erwartungstexte unten tragen den angehaengten Halbsatz deshalb
mit; die eigentliche #1498-Zusicherung sitzt unveraendert in den
``level``/``hour``-Aussagen.

KEINE Mocks: reale Model-Objekte, echte Scheduler-Methoden. Der Stub-Trip
in den Konfigurations-Tests ist ein einfaches Datenobjekt (echte Attribute,
kein Mock()/patch()).
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from app.models import ThunderLevel

_UTC = ZoneInfo("UTC")
_TODAY = date(2026, 7, 3)
_TOMORROW = date(2026, 7, 4)


def _dp(day: date, hour: int, thunder: ThunderLevel = ThunderLevel.NONE):
    from app.models import ForecastDataPoint
    return ForecastDataPoint(
        ts=datetime(day.year, day.month, day.day, hour, 0, tzinfo=timezone.utc),
        thunder_level=thunder,
    )


def _segment(data_points, thunder_level_max=ThunderLevel.NONE):
    from app.models import (
        ForecastMeta, GPXPoint, NormalizedTimeseries, Provider,
        SegmentWeatherData, SegmentWeatherSummary, TripSegment,
    )
    seg = TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=42.2, lon=9.05, elevation_m=400.0, distance_from_start_km=0.0),
        end_point=GPXPoint(lat=42.25, lon=9.09, elevation_m=900.0, distance_from_start_km=6.0),
        start_time=datetime(_TOMORROW.year, _TOMORROW.month, _TOMORROW.day, 6, 0, tzinfo=timezone.utc),
        end_time=datetime(_TOMORROW.year, _TOMORROW.month, _TOMORROW.day, 14, 0, tzinfo=timezone.utc),
        duration_hours=8.0, distance_km=6.0, ascent_m=500.0, descent_m=0.0,
    )
    meta = ForecastMeta(
        provider=Provider.OPENMETEO, model="test",
        run=datetime(_TODAY.year, _TODAY.month, _TODAY.day, 0, 0, tzinfo=timezone.utc),
        grid_res_km=1.3,
    )
    agg = SegmentWeatherSummary(
        temp_min_c=12.0, temp_max_c=18.0, wind_max_kmh=10.0,
        precip_sum_mm=0.0, cloud_avg_pct=20, thunder_level_max=thunder_level_max,
    )
    return SegmentWeatherData(
        segment=seg, timeseries=NormalizedTimeseries(meta=meta, data=data_points),
        aggregated=agg, fetched_at=datetime.now(timezone.utc), provider="openmeteo",
    )


def _tomorrow_points(thunder_by_hour):
    """Voller Kalendertag morgen, Gewitter nur in den genannten Stunden."""
    return [
        _dp(_TOMORROW, h, thunder_by_hour.get(h, ThunderLevel.NONE))
        for h in range(0, 24)
    ]


# ===========================================================================
# Fallback-Fetch-Pfad: _build_thunder_forecast()
# ===========================================================================


def test_fallback_nachtgewitter_ausserhalb_fenster_ist_entwarnung():
    """Given morgen LOW NUR um 02:00 (Nacht), Tagstunden ruhig / When die
    Vorschau gebaut wird / Then 'Kein Gewitter erwartet' — die Nacht gehoert
    der Nacht-Tabelle, nicht der Tages-Vorschau (#1498-Repro)."""
    from services.trip_report_scheduler import TripReportSchedulerService

    seg = _segment(_tomorrow_points({2: ThunderLevel.LOW}),
                   thunder_level_max=ThunderLevel.LOW)
    fc = TripReportSchedulerService()._build_thunder_forecast(seg, _TODAY, tz=_UTC)
    entry = (fc or {}).get("+1")
    assert entry is not None, "Vorschau-Eintrag fuer morgen fehlt ganz"
    assert entry["level"] == ThunderLevel.NONE, (
        f"Nacht-LOW (02:00) darf die Tages-Vorschau nicht setzen: {entry!r}"
    )
    assert entry["hour"] is None, entry
    # #1651: die TAGES-Aussage bleibt die Entwarnung, das Nachtgewitter wird
    # nun aber angehaengt genannt statt verschwiegen.
    assert entry["text"] == (
        "Kein Gewitter erwartet, nachts leichtes Gewitter ab 02:00"
    ), entry["text"]


def test_fallback_ab_stunde_kommt_aus_dem_fenster():
    """Given LOW um 02:00 UND um 04:00 / When gebaut / Then 'ab 04:00' —
    die frueheste Stunde IM Fenster (04 einschliesslich), nicht die
    Nachtstunde."""
    from services.trip_report_scheduler import TripReportSchedulerService

    seg = _segment(
        _tomorrow_points({2: ThunderLevel.LOW, 4: ThunderLevel.LOW}),
        thunder_level_max=ThunderLevel.LOW,
    )
    fc = TripReportSchedulerService()._build_thunder_forecast(seg, _TODAY, tz=_UTC)
    entry = (fc or {}).get("+1")
    assert entry is not None
    assert entry["level"] == ThunderLevel.LOW
    # #1651: "ab 04:00" ist und bleibt die Tages-Aussage; die 02:00 erscheinen
    # ausschliesslich im angehaengten Nacht-Halbsatz.
    assert entry["text"] == (
        "Leichtes Gewitter möglich ab 04:00, nachts leichtes Gewitter ab 02:00"
    ), entry["text"]
    assert entry["hour"] == 4, entry


# ===========================================================================
# Trend-Zeilen-Pfad: _build_thunder_forecast_from_trend_or_fetch() mit
# multi_day_trend (Abend-Default, kein Fetch)
# ===========================================================================


def _trend_row(thunder_by_hour, level_max):
    from output.renderers.email.outlook import build_outlook_row

    points = _tomorrow_points(thunder_by_hour)
    seg = _segment(points, thunder_level_max=level_max)
    row = build_outlook_row(seg.aggregated, points, "Sa", _UTC)
    row["date"] = _TOMORROW
    return row


def test_trend_nachtgewitter_ausserhalb_fenster_ist_entwarnung():
    """Derselbe Repro ueber den PRIMAEREN Bauweg (Trend-Zeile): LOW nur um
    02:00 → 'Kein Gewitter erwartet', kein 'ab 02:00'."""
    from services.trip_report_scheduler import TripReportSchedulerService

    row = _trend_row({2: ThunderLevel.LOW}, ThunderLevel.LOW)
    fc = TripReportSchedulerService()._build_thunder_forecast_from_trend_or_fetch(
        None, _TODAY, _UTC, multi_day_trend=[row],
    )
    entry = (fc or {}).get("+1")
    assert entry is not None, "Trend-Zeile fuer morgen wurde nicht verwendet"
    assert entry["level"] == ThunderLevel.NONE, (
        f"Nacht-LOW (02:00) darf die Tages-Vorschau nicht setzen: {entry!r}"
    )
    assert entry["hour"] is None, entry
    assert entry["text"] == (
        "Kein Gewitter erwartet, nachts leichtes Gewitter ab 02:00"
    ), entry["text"]


def test_trend_ab_stunde_kommt_aus_dem_fenster():
    """LOW um 02:00 UND um 19:00 → 'ab 19:00' (19 einschliesslich — Ende des
    Default-Fensters), Level bleibt LOW."""
    from services.trip_report_scheduler import TripReportSchedulerService

    row = _trend_row({2: ThunderLevel.LOW, 19: ThunderLevel.LOW}, ThunderLevel.LOW)
    fc = TripReportSchedulerService()._build_thunder_forecast_from_trend_or_fetch(
        None, _TODAY, _UTC, multi_day_trend=[row],
    )
    entry = (fc or {}).get("+1")
    assert entry is not None
    assert entry["level"] == ThunderLevel.LOW
    assert entry["text"] == (
        "Leichtes Gewitter möglich ab 19:00, nachts leichtes Gewitter ab 02:00"
    ), entry["text"]


# ===========================================================================
# Konfiguriertes Fenster (Epic #1319 Scheibe B): pro Trip, inkl. Wrap
# ===========================================================================


class _StubReportConfig:
    def __init__(self, start, end):
        self.day_window_start_hour = start
        self.day_window_end_hour = end


class _StubTrip:
    """Echtes Datenobjekt (kein Mock): nur die zwei Zugriffe, die
    _build_thunder_forecast_from_trend_or_fetch auf dem Trip macht."""

    def __init__(self, start, end):
        self.report_config = _StubReportConfig(start, end)

    def get_future_stages(self, target_date):
        return []


def test_konfiguriertes_fenster_wird_beachtet():
    """Given Trip-Fenster 06-18 / When LOW um 05:00 / Then Entwarnung —
    05:00 liegt vor dem konfigurierten Fensterbeginn."""
    from services.trip_report_scheduler import TripReportSchedulerService

    row = _trend_row({5: ThunderLevel.LOW}, ThunderLevel.LOW)
    fc = TripReportSchedulerService()._build_thunder_forecast_from_trend_or_fetch(
        _StubTrip(6, 18), _TODAY, _UTC, multi_day_trend=[row],
    )
    entry = (fc or {}).get("+1")
    assert entry is not None
    assert entry["level"] == ThunderLevel.NONE, entry
    # #1651: das KONFIGURIERTE Fenster bestimmt auch, was "ausserhalb" ist --
    # 05:00 liegt vor Fensterbeginn 06:00 und wird deshalb angehaengt genannt.
    assert entry["text"] == (
        "Kein Gewitter erwartet, nachts leichtes Gewitter ab 05:00"
    ), entry["text"]


def test_mitternachts_fenster_wrap_zaehlt_nachtstunden():
    """Given Trip-Fenster 22-2 (ueber Mitternacht, #1361/#1372 S1b gueltig) /
    When LOW um 23:00, Mittag ruhig / Then 'ab 23:00' — im Wrap-Fenster ist
    die Nachtstunde die konfigurierte Tages-Aussage."""
    from services.trip_report_scheduler import TripReportSchedulerService

    row = _trend_row({23: ThunderLevel.LOW}, ThunderLevel.LOW)
    fc = TripReportSchedulerService()._build_thunder_forecast_from_trend_or_fetch(
        _StubTrip(22, 2), _TODAY, _UTC, multi_day_trend=[row],
    )
    entry = (fc or {}).get("+1")
    assert entry is not None
    assert entry["level"] == ThunderLevel.LOW
    assert entry["text"] == "Leichtes Gewitter möglich ab 23:00", entry["text"]

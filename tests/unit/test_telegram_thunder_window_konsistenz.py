"""Telegram-Bubble: Kurzuebersicht und Fusszeile duerfen sich bei Gewitter
nicht widersprechen (#1498).

Repro aus dem Issue: Segment 08-12 vollstaendig beobachtet und ruhig,
``night_weather`` meldet ``ThunderLevel.LOW`` um 16:00 (nach Ankunft, im
Tagesfenster 04-19), ``has_gap=True``. Vor dem Fix sagte DIESELBE Bubble
zwei Zeilen untereinander Widerspruechliches: Kurzuebersicht ``⚡ ?``
(liest nur die Gehzeit-Stundenreihen), Fusszeile ``⚡ leicht`` (liest das
geteilte Tagesfenster inkl. ``night_weather``).

Erwartung (PO-Vorschlag im Issue): der Gewitter-Zweig der Kurzuebersicht
liest DIESELBE Quelle wie die Fusszeile — ein nach Ankunft aufziehendes
Gewitter (#1317-Szenario) wird sichtbar, und die Bubble traegt genau EINE
Gewitter-Aussage. Alle uebrigen Metriken behalten die Gehzeit als
Bezugsrahmen (bewusste Scheiben-Entscheidung, dokumentiert in #1498).

KEINE Mocks, KEIN Dateiinhalt-Check: reale Model-Objekte, realer
Renderaufruf (``render_telegram_bubbles``), Nutzersicht auf den Bubble-Text.
"""
from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

_TZ = ZoneInfo("Europe/Berlin")


def _make_segment(thunder_level):
    from app.models import (
        ForecastDataPoint, ForecastMeta, GPXPoint, NormalizedTimeseries,
        Provider, SegmentWeatherData, SegmentWeatherSummary, TripSegment,
    )
    seg = TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=42.2, lon=9.05, elevation_m=400.0, distance_from_start_km=0.0),
        end_point=GPXPoint(lat=42.25, lon=9.09, elevation_m=900.0, distance_from_start_km=6.0),
        start_time=datetime(2026, 7, 3, 6, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 7, 3, 10, 0, tzinfo=timezone.utc),
        duration_hours=4.0, distance_km=6.0, ascent_m=500.0, descent_m=0.0,
    )
    meta = ForecastMeta(
        provider=Provider.OPENMETEO, model="arome_france",
        run=datetime(2026, 7, 3, 0, 0, tzinfo=timezone.utc),
        grid_res_km=1.3, interp="point_grid",
    )
    dps = [
        ForecastDataPoint(
            ts=datetime(2026, 7, 3, h, 0, tzinfo=timezone.utc),
            thunder_level=thunder_level,
        )
        for h in (6, 7, 8, 9)
    ]
    agg = SegmentWeatherSummary(
        temp_min_c=12.0, temp_max_c=14.0, wind_max_kmh=8.0,
        precip_sum_mm=0.0, cloud_avg_pct=20, thunder_level_max=thunder_level,
    )
    return SegmentWeatherData(
        segment=seg, timeseries=NormalizedTimeseries(meta=meta, data=dps),
        aggregated=agg, fetched_at=datetime.now(timezone.utc),
        provider="openmeteo",
    )


def _make_night_weather(thunder_level):
    """Zeitreihe am Ziel: 14:00 UTC = 16:00 lokal — nach Ankunft (12:00
    lokal), aber im Tagesfenster 04-19."""
    from app.models import (
        ForecastDataPoint, ForecastMeta, NormalizedTimeseries, Provider,
    )
    meta = ForecastMeta(
        provider=Provider.OPENMETEO, model="arome_france",
        run=datetime(2026, 7, 3, 0, 0, tzinfo=timezone.utc),
        grid_res_km=1.3, interp="point_grid",
    )
    dp = ForecastDataPoint(
        ts=datetime(2026, 7, 3, 14, 0, tzinfo=timezone.utc),
        thunder_level=thunder_level,
    )
    return NormalizedTimeseries(meta=meta, data=[dp])


def _make_dc():
    from app.models import MetricConfig, UnifiedWeatherDisplayConfig
    return UnifiedWeatherDisplayConfig(
        trip_id="test-1498",
        metrics=[MetricConfig(metric_id="thunder", enabled=True, bucket="primary", order=0)],
        updated_at=datetime.now(timezone.utc),
    )


_ROWS = [
    {"time": "08", "temp": 12, "wind": 5, "precip": 0.0, "thunder": "NONE"},
    {"time": "09", "temp": 13, "wind": 6, "precip": 0.0, "thunder": "NONE"},
    {"time": "10", "temp": 14, "wind": 6, "precip": 0.0, "thunder": "NONE"},
    {"time": "11", "temp": 14, "wind": 7, "precip": 0.0, "thunder": "NONE"},
]


def _thunder_statements(*, night_thunder, has_gap):
    """Rendert die Bubbles fuer das Issue-Szenario und liefert alle
    Gewitter-Aussagen (Text nach '⚡ ', vor einem etwaigen ' · ') der
    Kurzuebersicht-Bubble."""
    from app.models import ThunderLevel
    from output.renderers.narrow import render_telegram_bubbles

    night = (
        _make_night_weather(night_thunder) if night_thunder is not None else None
    )
    bubbles = render_telegram_bubbles(
        segments=[_make_segment(ThunderLevel.NONE)],
        seg_tables=[[dict(r) for r in _ROWS]],
        dc=_make_dc(), report_type="evening", tz=_TZ,
        trip_name="Konsistenz 1498", night_weather=night, has_gap=has_gap,
    )
    overview = next(b.text for b in bubbles if "Kurzübersicht" in b.text)
    statements = []
    for line in overview.splitlines():
        if "⚡" not in line:
            continue
        after = line.split("⚡", 1)[1].strip()
        statements.append(after.split(" · ", 1)[0].strip())
    return statements


def test_nachzuegler_gewitter_widerspricht_sich_nicht():
    """Given Gehzeit ruhig + LOW um 16:00 im night_weather + Ziel-Luecke /
    When die Bubble gerendert wird / Then tragen Kurzuebersicht und
    Fusszeile DIESELBE Aussage 'leicht' — kein '?' gegen 'leicht' mehr
    (#1498-Repro; das Nach-Ankunft-Gewitter ist sichtbar, #1317)."""
    from app.models import ThunderLevel

    statements = _thunder_statements(
        night_thunder=ThunderLevel.LOW, has_gap=True,
    )
    assert len(statements) >= 2, (
        f"Erwartet Kurzuebersicht-Zeile UND Fusszeile mit ⚡, war: {statements!r}"
    )
    assert len(set(statements)) == 1, (
        f"Widerspruch in derselben Bubble: {statements!r}"
    )
    assert statements[0] == "leicht", (
        f"Nach-Ankunft-LOW muss 'leicht' zeigen, war: {statements!r}"
    )


def test_ruhiger_tag_mit_luecke_zeigt_ueberall_fragezeichen():
    """Given ueberall NONE beobachtet, aber Ziel-Luecke / When gerendert /
    Then zeigen beide Zeilen '?' (keine Fehl-Entwarnung, #1331/#1491) —
    und weiterhin widerspruchsfrei."""
    from app.models import ThunderLevel

    statements = _thunder_statements(
        night_thunder=ThunderLevel.NONE, has_gap=True,
    )
    assert len(statements) >= 2
    assert set(statements) == {"?"}, f"Erwartet ueberall '?', war: {statements!r}"


def test_ruhiger_tag_ohne_luecke_zeigt_ueberall_kein():
    """Given ueberall NONE beobachtet, keine Luecke / When gerendert / Then
    zeigen beide Zeilen 'kein' — Entwarnung bleibt Entwarnung."""
    from app.models import ThunderLevel

    statements = _thunder_statements(
        night_thunder=ThunderLevel.NONE, has_gap=False,
    )
    assert len(statements) >= 2
    assert set(statements) == {"kein"}, f"Erwartet ueberall 'kein', war: {statements!r}"

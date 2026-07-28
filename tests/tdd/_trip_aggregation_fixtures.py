"""Gemeinsame Fixtures fuer die Auswertungswahl-Tests zu Issue #1357.

Kein Test-Modul (fuehrender Unterstrich -> wird nicht eingesammelt), nur echte
Datenmodell-Objekte. Kein Mock, kein Netz, kein ``patch()``.
Vorbild: tests/tdd/test_issue_912_pill_textformat.py::_dp/_make_segment.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Berlin")


def dp(h_utc: int, *, t2m_c: float = 15.0, wind_chill_c: float | None = None):
    """Echter ``ForecastDataPoint`` fuer die UTC-Stunde ``h_utc``."""
    from app.models import ForecastDataPoint, ThunderLevel
    kwargs = dict(
        ts=datetime(2026, 7, 11, h_utc, 0, tzinfo=timezone.utc),
        t2m_c=float(t2m_c),
        wind10m_kmh=5.0,
        gust_kmh=10.0,
        precip_1h_mm=0.0,
        pop_pct=0,
        cloud_total_pct=60,
        thunder_level=ThunderLevel.NONE,
        visibility_m=10000,
        freezing_level_m=2500,
        humidity_pct=55,
    )
    if wind_chill_c is not None:
        kwargs["wind_chill_c"] = float(wind_chill_c)
    return ForecastDataPoint(**kwargs)


def make_segment(dps, start_h_utc: int = 6, end_h_utc: int = 9):
    """Echtes ``SegmentWeatherData`` um die uebergebenen DataPoints.

    Die Gehzeit-Fensterung (``_collect_hiking_window_dps``) schneidet die
    Zeitreihe auf ``start_h_utc..end_h_utc`` zu — DataPoints ausserhalb dieses
    Fensters bleiben also unberuecksichtigt (wird fuer den Zeitraum-Nachweis in
    AC-4 gebraucht).
    """
    from app.models import (
        ForecastMeta, GPXPoint, NormalizedTimeseries, Provider,
        SegmentWeatherData, SegmentWeatherSummary, ThunderLevel, TripSegment,
    )
    seg = TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=42.13, lon=9.13, elevation_m=400.0,
                             distance_from_start_km=0.0),
        end_point=GPXPoint(lat=42.10, lon=9.18, elevation_m=1200.0,
                           distance_from_start_km=9.0),
        start_time=datetime(2026, 7, 11, start_h_utc, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 7, 11, end_h_utc, 0, tzinfo=timezone.utc),
        duration_hours=float(end_h_utc - start_h_utc),
        distance_km=9.0,
        ascent_m=800.0, descent_m=0.0,
    )
    meta = ForecastMeta(
        provider=Provider.OPENMETEO, model="demo", grid_res_km=1.3,
        run=datetime(2026, 7, 11, 0, 0, tzinfo=timezone.utc),
    )
    agg = SegmentWeatherSummary(
        temp_min_c=15.0, temp_max_c=15.0, temp_avg_c=15.0,
        wind_max_kmh=5.0, gust_max_kmh=10.0,
        precip_sum_mm=0.0, cloud_avg_pct=60, humidity_avg_pct=55,
        thunder_level_max=ThunderLevel.NONE,
    )
    return SegmentWeatherData(
        segment=seg, timeseries=NormalizedTimeseries(meta=meta, data=dps),
        aggregated=agg, fetched_at=datetime.now(timezone.utc), provider="demo",
    )


_NUMBER = re.compile(r"-?\d+(?:[.,]\d+)?")


def shape(text: str) -> str:
    """Darstellungs-Geruest eines Kachel-Textes: Praefix ``gef. `` entfernt,
    alle Zahlen durch ``#`` ersetzt.

    Damit vergleicht AC-4 die FORM zweier Kacheln, ohne Werte oder
    Nachkommastellen festzunageln — genau die Spec-Zusage „Beide Metriken
    laufen durch dieselbe Fallunterscheidung, unterscheiden sich nur in
    Label-Praefix und Nachkommastellen" (Spec Implementation Details §3).
    """
    body = text[len("gef. "):] if text.startswith("gef. ") else text
    return _NUMBER.sub("#", body)


def first_hour(text: str) -> str | None:
    """Erste ``HH:00``-Uhrzeit in einem Kachel-Text (oder ``None``)."""
    m = re.search(r"\d{2}:\d{2}", text)
    return m.group(0) if m else None

"""`LocationWeatherSource`-Implementierung für Compare-Orte.

Issue #1169 — Scheibe 2/3, Epic #1095.

Baut je Ort ein synthetisches Ein-Punkt-`TripSegment` (`start_point ==
end_point`, minimales Zeitfenster) und nutzt
`SegmentWeatherService.fetch_segment_weather()` +
`TripSegmentWeatherAdapter.to_points()` — damit sind der beim Compare-Report-
Versand geschriebene Anker-Snapshot und das beim 15-Min-Alert-Check gefetchte
fresh-Wetter **durch denselben Code-Pfad** erzeugt (Form-/Provider-Mismatch
strukturell ausgeschlossen, Spec-Abschnitt A1). Provider-Wahl über
`get_provider("openmeteo")` (Epic #1301 A2 — Ortsvergleich holt ueberall
openmeteo). `enrich_ensemble=False`
beim Fetch (Bug #288-Analogon — Alert-Checks duerfen kein API-Kontingent
konsumieren).

SPEC: docs/specs/modules/issue_1169_compare_alert_consumer.md
SPEC: docs/specs/modules/fix_1584c_compare_alarm_zeitfenster.md (Tagesfenster)
"""
from __future__ import annotations

import logging
from datetime import date, datetime, time, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from app.models import GPXPoint, TripSegment
from services.point_weather import PointWeatherData, TripSegmentWeatherAdapter
from services.segment_weather import SegmentWeatherService

logger = logging.getLogger("compare_location_weather_source")


def _window_bound(local_day: date, hour: int, tz: ZoneInfo) -> datetime:
    """Ortszeit-Stunde eines lokalen Kalendertags -> UTC. Exakt das Muster aus
    `trip_segments.py:269-273` — kein zweiter Zeitbegriff."""
    return (
        datetime.combine(local_day, time(hour))
        .replace(tzinfo=tz)
        .astimezone(timezone.utc)
    )


class CompareLocationWeatherSource:
    """`LocationWeatherSource`-Protocol-Implementierung für Compare-Orte
    (`services/point_weather.py:67-76`)."""

    def fetch(
        self,
        point_id: str,
        lat: float,
        lon: float,
        start_hour: Optional[int] = None,
        end_hour: Optional[int] = None,
    ) -> PointWeatherData:
        """Issue #1584 Scheibe C: das synthetische Segment deckt das
        TAGESFENSTER des laufenden lokalen Kalendertags am Ort ab, nicht mehr
        eine Stunde bei `now`. Anker (Report-Versand) und Frisch-Abruf
        (15-Min-Alarm-Check) laufen durch denselben Code — mit dem Tagesfenster
        haben sie dadurch **durch Konstruktion** denselben Zuschnitt, statt
        zwei verschiedene Tagesstunden zu vergleichen.

        `start_hour`/`end_hour` kommen vom Aufrufer aus
        `resolve_compare_time_window(preset)` (ADR-0035, EINE Fensterquelle für
        Anzeige und Bewertung). `None` faellt ueber denselben geteilten
        Aufloeser auf den Default 4/19 zurueck.
        """
        from app.day_window import resolve_configured_window
        from providers.base import get_provider
        from utils.timezone import tz_for_coords

        provider = get_provider("openmeteo")
        service = SegmentWeatherService(provider)

        start_hour, end_hour = resolve_configured_window(start_hour, end_hour)
        tz = tz_for_coords(lat, lon)
        now = datetime.now(timezone.utc)
        # Der Kalendertag ist der LOKALE Tag am Ort, nicht der UTC-Tag —
        # sonst verschoebe sich das Fenster bei jedem Ort mit UTC-Versatz
        # (analog `trip_segments.py:264-268`).
        local_today = now.astimezone(tz).date()
        window_start = _window_bound(local_today, start_hour, tz)
        # Obergrenze EXKLUSIV: `end_hour = 19` heisst Fensterende um 19:00,
        # Stunde 19 liegt draussen — genau wie `segment_weather.py` filtert
        # (`< end_floor`, Bug #806) und wie der Trip-Alarmpfad rechnet.
        window_end = _window_bound(local_today, end_hour, tz)

        if window_end <= window_start:
            # Tagesfenster ueber Mitternacht (`start > end`, seit #1361
            # gueltig) — ein einzelnes zusammenhaengendes Segment kann das
            # nicht darstellen. Wie beim Ziel-Segment (`trip_segments.py:275`)
            # wird hier NICHT uebersprungen: ein fehlendes Segment liesse den
            # Ortsvergleich still aus der Ueberwachung fallen (genau der
            # #1584-Fehler). Stattdessen ein minimales, aber gueltiges Fenster.
            logger.warning(
                "Compare-Wetterfenster fuer Ort %s: Tagesfenster %d-%d Uhr laeuft "
                "ueber Mitternacht — minimales Fenster von 1 h ab %s wird verwendet",
                point_id, start_hour, end_hour, now.isoformat(),
            )
            window_start = now.replace(minute=0, second=0, microsecond=0)
            window_end = window_start + timedelta(hours=1)

        point = GPXPoint(lat=lat, lon=lon, elevation_m=None, distance_from_start_km=0.0)
        segment = TripSegment(
            segment_id=point_id,
            start_point=point,
            end_point=point,
            start_time=window_start,
            end_time=window_end,
            duration_hours=(window_end - window_start).total_seconds() / 3600,
            distance_km=0.0,
            ascent_m=0,
            descent_m=0,
        )
        segment_weather = service.fetch_segment_weather(
            segment,
            enrich_ensemble=False,
            enrich_snow=False,
            priority="alert_check",  # Issue #1329 Teil 2
        )
        return TripSegmentWeatherAdapter.to_points([segment_weather])[0]

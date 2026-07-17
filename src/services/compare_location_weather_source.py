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
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.models import GPXPoint, TripSegment
from services.point_weather import PointWeatherData, TripSegmentWeatherAdapter
from services.segment_weather import SegmentWeatherService


class CompareLocationWeatherSource:
    """`LocationWeatherSource`-Protocol-Implementierung für Compare-Orte
    (`services/point_weather.py:67-76`)."""

    def fetch(self, point_id: str, lat: float, lon: float) -> PointWeatherData:
        from providers.base import get_provider

        provider = get_provider("openmeteo")
        service = SegmentWeatherService(provider)

        now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
        point = GPXPoint(lat=lat, lon=lon, elevation_m=None, distance_from_start_km=0.0)
        segment = TripSegment(
            segment_id=point_id,
            start_point=point,
            end_point=point,
            start_time=now,
            end_time=now + timedelta(hours=1),
            duration_hours=1.0,
            distance_km=0.0,
            ascent_m=0,
            descent_m=0,
        )
        segment_weather = service.fetch_segment_weather(
            segment, enrich_ensemble=False, enrich_snow=False
        )
        return TripSegmentWeatherAdapter.to_points([segment_weather])[0]

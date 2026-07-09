"""Location-generisches Wetter-DTO + Beschaffungs-Schnittstelle.

Issue #1168 — Scheibe 1/3, Epic #1095.

`PointWeatherData` ist das Analogon zu `SegmentWeatherData` OHNE
`TripSegment`-Kopplung: statt eines `TripSegment` trägt es nur die generischen
Ortsfelder (id/name/lat/lon). Wird von `DeviationAlertEngine.evaluate()`
konsumiert und über `TripSegmentWeatherAdapter` verlustfrei aus bestehenden
`List[SegmentWeatherData]`-Ergebnissen (`SegmentWeatherService`) gebaut — die
Wetter-Beschaffung selbst wird dabei NICHT verändert.

SPEC: docs/specs/modules/issue_1168_alert_engine_extract.md
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional, Protocol, Set

if TYPE_CHECKING:
    from app.models import (
        NormalizedTimeseries,
        SegmentWeatherData,
        SegmentWeatherSummary,
        UnifiedWeatherDisplayConfig,
    )
    from services.official_alerts.models import OfficialAlert


@dataclass
class PointWeatherData:
    """Wetterdaten für einen einzelnen, generischen Ort (kein Trip-/Stage-/
    Waypoint-Bezug). Analogon zu `SegmentWeatherData`."""

    id: str
    name: str
    lat: float
    lon: float
    timeseries: Optional["NormalizedTimeseries"]
    aggregated: "SegmentWeatherSummary"
    fetched_at: datetime
    provider: str
    official_alerts: List["OfficialAlert"] = field(default_factory=list)


@dataclass
class AlertEvaluationConfig:
    """Reines Daten-Objekt für Alarm-Auswertungs-Parameter — kein Trip-Bezug.

    Bündelt die Werte, die `TripAlertService` heute über `trip.*`-Attribute
    liest. Ein künftiger Compare-Adapter (Scheibe 2/3, #1169) würde dasselbe
    Objekt aus einem `ComparePreset` bauen.
    """

    cooldown_minutes: Optional[int] = 0
    quiet_from: Optional[str] = None
    quiet_to: Optional[str] = None
    metric_alert_levels: Optional[dict] = None
    channels: Set[str] = field(default_factory=set)
    # Issue #1168 F001: Auszug für Detektor-Wahl inkl. #961-„Aktivieren-Lücke"-
    # Backfill (Weather-Tab-aktive Metrik ohne expliziten metric_alert_levels-
    # Eintrag). None = kein Backfill (Abwärtskompatibilität für generische
    # Aufrufer ohne Weather-Tab-Kontext, z. B. reine metric_alert_levels-Nutzung).
    display_config: Optional["UnifiedWeatherDisplayConfig"] = None


class LocationWeatherSource(Protocol):
    """Schmale Beschaffungs-Schnittstelle über `providers.base.get_provider(...)`.

    Künftige Consumer (z. B. Compare) implementieren dieses Protocol, um
    frische `PointWeatherData` für einen Ort zu beschaffen — analog zu dem,
    was `TripSegmentWeatherAdapter` heute für Trip-Segmente leistet.
    """

    def fetch(self, point_id: str, lat: float, lon: float) -> PointWeatherData:
        ...


class TripSegmentWeatherAdapter:
    """Wandelt bestehende `List[SegmentWeatherData]` verlustfrei in
    `List[PointWeatherData]` — reine Umformung, keine Wertänderung."""

    @staticmethod
    def to_points(data: List["SegmentWeatherData"]) -> List[PointWeatherData]:
        return [
            PointWeatherData(
                id=str(d.segment.segment_id),
                name=str(d.segment.segment_id),
                lat=d.segment.start_point.lat,
                lon=d.segment.start_point.lon,
                timeseries=d.timeseries,
                aggregated=d.aggregated,
                fetched_at=d.fetched_at,
                provider=d.provider,
                official_alerts=list(d.official_alerts),
            )
            for d in data
        ]

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
from datetime import date, datetime
from typing import TYPE_CHECKING, List, Optional, Protocol, Set
from zoneinfo import ZoneInfo

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
    # Issue #1661 (B1): der beschriebene KALENDERTAG, additiv und optional.
    # `fetched_at` ist der Schreibzeitpunkt — das ist etwas anderes: der
    # Abend-Versand eines Ortsvergleichs informiert über MORGEN, schrieb den
    # Δ-Anker aber ohne jeden Tagesbezug. `None` heisst "kein Tagesbezug" und
    # verhält sich exakt wie vor dieser Scheibe (Altbestand, Trip-Pfad, der
    # sein eigenes Datums-Schema über Dateinamen hat).
    target_date: Optional[date] = None


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
    # Issue #1971: der Erbauer erklärt, dass `metric_alert_levels` nur eine
    # TEIL-Angabe ist — fehlende Metriken sind auf 'standard' zu ergänzen.
    # Wirkt nur bei `display_config is None` (sonst schließt der #961-Backfill
    # die Lücke bereits). Der Trip-Pfad lässt den Default `False` stehen.
    supplement_missing_levels: bool = False
    # Issue #1726: Ortszone des Gegenstands fuer die Ruhezeit-Pruefung (Trip:
    # `anchor_tz`, Vergleich: `first_resolvable_tz`). `None` = der Erbauer
    # kennt keine; die Engine rechnet dann in Weltzeit statt zu raten.
    zone: Optional[ZoneInfo] = None


class LocationWeatherSource(Protocol):
    """Schmale Beschaffungs-Schnittstelle über `providers.base.get_provider(...)`.

    Künftige Consumer (z. B. Compare) implementieren dieses Protocol, um
    frische `PointWeatherData` für einen Ort zu beschaffen — analog zu dem,
    was `TripSegmentWeatherAdapter` heute für Trip-Segmente leistet.

    Issue #1584 Scheibe C: `start_hour`/`end_hour` sind das Tagesfenster
    (Ortszeit am Ort), über das die Beschaffung aggregiert. `None` heisst
    „Default 4/19 über den geteilten Auflöser" (ADR-0035) — es gibt bewusst
    keinen zweiten Fensterbegriff je Implementierung.

    Issue #1661 (B2): Implementierungen DÜRFEN zusätzlich zwei optionale
    Schlüsselwort-Argumente annehmen, die denselben KALENDERTAG auf zwei
    verschiedene Arten vorgeben — und die sich gegenseitig ausschliessen:
    `target_date` (absoluter, bereits aufgelöster Tag; so liest der
    15-Minuten-Δ-Check den Tag aus dem Anker) und `tage_ab_ortstag` (Versatz
    gegen den lokalen Tag AM ORT; so schreibt der Briefing-Versand den Anker,
    weil sein eigener „heute"-Begriff aus der Server-Zeitzone stammt und für
    Orte mit UTC-Versatz auf einen anderen Ortstag zeigt). Die
    Protocol-Signatur bleibt bewusst ohne beide Argumente: Aufrufer reichen sie
    nur durch, wenn ein Tagesbezug tatsächlich vorliegt — eine bedingungslose
    Übergabe würde jede bestehende Implementierung ohne fachlichen Gewinn
    brechen.
    """

    def fetch(
        self,
        point_id: str,
        lat: float,
        lon: float,
        start_hour: Optional[int] = None,
        end_hour: Optional[int] = None,
    ) -> PointWeatherData:
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

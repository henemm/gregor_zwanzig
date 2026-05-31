"""F12: Großwetterlage / Stabilitäts-Label (Issue #122, refactored #479).

SPEC: docs/specs/modules/issue_479_f12_confidence_refactor.md v1.0

Berechnet das synoptische Stabilitäts-Label (STABIL / WECHSELHAFT / FRAGIL)
aus den bereits vorhandenen `confidence_pct_min`-Werten der Folge-Etappen.
Kein separater Z500-API-Call mehr — die Daten kommen aus dem regulären
Open-Meteo-Ensemble-Spread, der ohnehin pro Trip einmal abgerufen wird.

Label-Mapping (analog C-Token, SMS-Format §3.4b):
- confidence_pct >= 75 -> STABIL
- 50 <= confidence_pct < 75 -> WECHSELHAFT
- confidence_pct < 50 -> FRAGIL
"""
from __future__ import annotations

import logging
from datetime import date
from typing import TYPE_CHECKING, Iterable, Optional

from app.models import StabilityResult

if TYPE_CHECKING:
    from app.models import SegmentWeatherData
    from app.trip import Trip

logger = logging.getLogger("weather_pattern")


def compute_stability(
    values: Iterable[Optional[int]],
) -> Optional[StabilityResult]:
    """Leitet das Stabilitäts-Label aus Konfidenz-Werten ab.

    Args:
        values: Konfidenz-Prozentwerte (typischerweise
            `SegmentWeatherSummary.confidence_pct_min`). `None`-Werte
            werden ignoriert.

    Returns:
        `StabilityResult` mit `label` und `confidence_pct = min(valid)`,
        oder `None` wenn keine gültigen Werte vorhanden sind.
    """
    valid = [v for v in values if v is not None]
    if not valid:
        return None
    agg = min(valid)
    if agg >= 75:
        label = "STABIL"
    elif agg >= 50:
        label = "WECHSELHAFT"
    else:
        label = "FRAGIL"
    return StabilityResult(label=label, confidence_pct=agg)


class WeatherPatternService:
    """Berechnet `StabilityResult` für einen Trip aus vorhandenen Konfidenz-Daten."""

    def compute_for_trip(
        self,
        trip: "Trip",
        target_date: date,
        segment_weather: list["SegmentWeatherData"],
    ) -> Optional[StabilityResult]:
        """Leitet das WL-Label aus Konfidenz-Daten längerer Zeithorizonte ab.

        Der Scheduler fetcht Wetterdaten nur für die heutige Etappe, aber die
        Open-Meteo-Ensemble-Anreicherung liefert stündliche
        `confidence_pct`-Werte bis T+96h/T+120h. DataPoints bei T+24h und
        später repräsentieren implizit die Verlässlichkeit für Folge-Etappen.

        Args:
            trip: Trip-Objekt (für `get_future_stages`).
            target_date: aktuelles Briefing-Datum.
            segment_weather: Bereits berechnete Segment-Daten der Trip-
                Etappen.

        Returns:
            `StabilityResult` oder `None`. Liefert `None` wenn:
            - es keine Folge-Etappen gibt (letzte Etappe), oder
            - keine `confidence_pct`-DataPoints jenseits T+24h vorliegen.
        """
        try:
            future_stages = trip.get_future_stages(from_date=target_date)
            if not future_stages:
                return None

            # Sammle confidence_pct aus DataPoints mit Datum > target_date
            # (entspricht implizit Lead-Time >= 24h).
            from datetime import timezone as _tz

            values: list[Optional[int]] = []
            for seg_data in segment_weather:
                ts = getattr(seg_data, "timeseries", None)
                if ts is None:
                    continue
                for dp in ts.data:
                    if dp.confidence_pct is None:
                        continue
                    dp_ts = dp.ts
                    if dp_ts.tzinfo is None:
                        dp_ts = dp_ts.replace(tzinfo=_tz.utc)
                    if dp_ts.date() > target_date:
                        values.append(dp.confidence_pct)

            return compute_stability(values)
        except Exception as e:  # pragma: no cover — defensive
            logger.debug("WeatherPatternService.compute_for_trip failed: %s", e)
            return None

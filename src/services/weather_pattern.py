"""F12: Großwetterlage / Stabilitäts-Label (Issue #122).

SPEC: docs/specs/modules/weather_pattern.md v1.0

Berechnet synoptisches Stabilitäts-Label (STABIL / WECHSELHAFT / FRAGIL) aus
Z500-Ensemble-Daten der OpenMeteo Ensemble API. Zwei Komponenten:

- Tendenz: Geopotential-Höhen-Änderung über 48 h (0/1/2 Punkte).
- Spread: Mittlere Standardabweichung über die Ensemble-Member bis T+72 h
  (0/1/2 Punkte).

Label-Mapping (Summe der Komponenten 0–4):
- >= 3 -> STABIL
- == 2 -> WECHSELHAFT
- <= 1 -> FRAGIL
"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from statistics import mean, stdev
from typing import TYPE_CHECKING, Optional

from app.models import StabilityResult

if TYPE_CHECKING:
    from app.trip import Trip
    from providers.openmeteo import OpenMeteoProvider

logger = logging.getLogger("weather_pattern")

# Tendenz-Schwellen in geopotential metres (gpm)
TENDENCY_STABLE_THRESHOLD = 15     # < 15 gpm → 2 Punkte
TENDENCY_MODERATE_THRESHOLD = 40   # < 40 gpm → 1 Punkt, sonst 0

# Spread-Schwellen in gpm
SPREAD_TIGHT_THRESHOLD = 40        # < 40 gpm → 2 Punkte
SPREAD_MODERATE_THRESHOLD = 80     # < 80 gpm → 1 Punkt, sonst 0

# Mindestanzahl Member pro Stunde für gültige Spread-Berechnung
MIN_ENSEMBLE_MEMBERS = 5

# Mindestlänge der Z500-Zeitreihe (T+48h muss enthalten sein)
MIN_T48_HOURS = 49

# Spread wird über T+0..T+72h gemittelt (73 Datenpunkte inklusive)
SPREAD_WINDOW_HOURS = 73

# Maximaler Tage-Horizont der zukünftigen Etappen für den Zentroid
MAX_FUTURE_DAYS = 5


class WeatherPatternService:
    """Berechnet synoptisches Stabilitäts-Label aus Z500-Ensemble-Daten."""

    def __init__(self, provider: Optional["OpenMeteoProvider"]):
        """Init mit einem OpenMeteoProvider (oder None für reine Score-Tests).

        Args:
            provider: OpenMeteoProvider-Instanz; None erlaubt für Unit-Tests
                der reinen Scoring-Methoden (kein API-Call).
        """
        self._provider = provider

    def compute_for_trip(
        self,
        trip: "Trip",
        target_date: date,
    ) -> Optional[StabilityResult]:
        """Berechnet StabilityResult für die nächsten Etappen eines Trips.

        Returns None wenn:
        - Keine zukünftigen Etappen (letzte Etappe)
        - Provider ist None
        - API-Fehler oder ungenügende Ensemble-Daten

        Alle internen Exceptions werden abgefangen — diese Methode propagiert
        niemals (Spec AC-7).
        """
        try:
            return self._compute(trip, target_date)
        except Exception as e:
            logger.debug("WeatherPatternService.compute_for_trip failed: %s", e)
            return None

    def _compute(
        self,
        trip: "Trip",
        target_date: date,
    ) -> Optional[StabilityResult]:
        future_stages = trip.get_future_stages(from_date=target_date)
        cutoff = target_date + timedelta(days=MAX_FUTURE_DAYS)
        relevant = [s for s in future_stages if s.date <= cutoff]

        if not relevant:
            return None

        # Zentroid der ersten Wegpunkte der relevanten Etappen
        waypoints = [s.waypoints[0] for s in relevant if s.waypoints]
        if not waypoints:
            return None

        lat = sum(w.lat for w in waypoints) / len(waypoints)
        lon = sum(w.lon for w in waypoints) / len(waypoints)

        if self._provider is None:
            return None

        data = self._provider._fetch_ensemble_with_z500(lat=lat, lon=lon)
        if data is None:
            return None

        z500_members = data.get("z500_members", [])
        if len(z500_members) < MIN_T48_HOURS:
            return None

        tendency_score = self._score_tendency(z500_members)
        spread_score = self._score_spread(z500_members)

        total = tendency_score + spread_score
        label = self._score_to_label(total)

        return StabilityResult(
            label=label,
            score=total,
            component_scores=(tendency_score, spread_score),
        )

    def _score_tendency(self, z500_members: list[list[float]]) -> int:
        """Komponente 1: Z500-Tendenz über 48 h (0/1/2 Punkte).

        Liefert 1 (neutral) bei ungenügenden Daten, damit ein partieller
        Datenausfall den Gesamt-Score nicht künstlich auf FRAGIL zieht.
        """
        if len(z500_members) < MIN_T48_HOURS:
            return 1

        vals_t0 = [v for v in z500_members[0] if v is not None]
        vals_t48 = [v for v in z500_members[48] if v is not None]

        if not vals_t0 or not vals_t48:
            return 1

        z0 = mean(vals_t0)
        z48 = mean(vals_t48)
        delta = abs(z48 - z0)

        if delta < TENDENCY_STABLE_THRESHOLD:
            return 2
        if delta < TENDENCY_MODERATE_THRESHOLD:
            return 1
        return 0

    def _score_spread(self, z500_members: list[list[float]]) -> int:
        """Komponente 2: Ensemble-Spread über T+0..T+72h (0/1/2 Punkte).

        Stunden mit weniger als MIN_ENSEMBLE_MEMBERS validen Membern werden
        aus dem Mittelwert ausgeschlossen. Liefert 1 (neutral) wenn nach
        Filterung keine auswertbaren Stunden übrig sind.
        """
        spread_per_hour: list[float] = []
        for hour_members in z500_members[:SPREAD_WINDOW_HOURS]:
            valid = [v for v in hour_members if v is not None]
            if len(valid) >= MIN_ENSEMBLE_MEMBERS:
                spread_per_hour.append(stdev(valid))

        if not spread_per_hour:
            return 1

        mean_spread = mean(spread_per_hour)

        if mean_spread < SPREAD_TIGHT_THRESHOLD:
            return 2
        if mean_spread < SPREAD_MODERATE_THRESHOLD:
            return 1
        return 0

    def _score_to_label(self, total: int) -> str:
        """Mappt Gesamt-Score (0–4) auf Label.

        - total >= 3 -> STABIL
        - total == 2 -> WECHSELHAFT
        - total <= 1 -> FRAGIL
        """
        if total >= 3:
            return "STABIL"
        if total == 2:
            return "WECHSELHAFT"
        return "FRAGIL"

"""
DayComparisonService — Delta-Berechnung Vortag-Vergleich (Issue #748).

Berechnet pro Segment Deltas zwischen heute und gestern aus SegmentWeatherData.
Ausschliesslich regelbasiert — keine KI.

SPEC: docs/specs/modules/issue_748_day_comparison_service.md v1.0
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Dict, List, Optional

if TYPE_CHECKING:
    from app.models import SegmentWeatherData, ThunderLevel

# Ordinal-Mapping ThunderLevel (NONE < MED < HIGH)
_THUNDER_ORDINAL: Dict[str, int] = {"NONE": 0, "MED": 1, "HIGH": 2}

# Metriken bei denen weniger = BETTER
_LOWER_IS_BETTER = frozenset({"wind_max_kmh", "gust_max_kmh", "precip_sum_mm", "thunder"})

# Metriken die neutral sind (kein inhärentes besser/schlechter)
_NEUTRAL = frozenset({"temp_min_c", "temp_max_c"})

# Floating-point Toleranz für EQUAL-Erkennung
_FLOAT_EPS = 0.01


class ComparisonDirection(str, Enum):
    BETTER = "BETTER"
    WORSE = "WORSE"
    EQUAL = "EQUAL"
    MISSING = "MISSING"


@dataclass
class MetricDelta:
    """Delta für eine einzelne Metrik."""
    delta: Optional[float]          # heute - gestern (None wenn Metrik fehlt)
    direction: ComparisonDirection


@dataclass
class DayComparisonEntry:
    """Vergleich für ein Segment (heute vs. gestern)."""
    segment_id: int
    temp_min: MetricDelta
    temp_max: MetricDelta
    wind_max: MetricDelta
    gust_max: MetricDelta
    precip_sum: MetricDelta
    thunder: MetricDelta


@dataclass
class DayComparison:
    entries: List[DayComparisonEntry] = field(default_factory=list)


def summarize_day_comparison(comparison: Optional["DayComparison"]) -> str:
    """Issue #790: Eine natursprachliche Vortag-Einordnungszeile.

    Temp: Durchschnitt der temp_max.delta über alle Segmente (None überspringen).
        >+1.5 → "wärmer", <-1.5 → "kälter", sonst "ähnlich temperiert".
    Regen: Summe der precip_sum.delta.
        >+1mm → "nasser", <-1mm → "trockener", sonst neutral.

    Rückgabe "" wenn comparison None/keine entries.
    """
    if comparison is None or not comparison.entries:
        return ""

    temp_deltas = [
        e.temp_max.delta for e in comparison.entries
        if e.temp_max.delta is not None
    ]
    precip_deltas = [
        e.precip_sum.delta for e in comparison.entries
        if e.precip_sum.delta is not None
    ]

    temp_word: Optional[str] = None
    if temp_deltas:
        avg_temp = sum(temp_deltas) / len(temp_deltas)
        if avg_temp > 1.5:
            temp_word = "wärmer"
        elif avg_temp < -1.5:
            temp_word = "kälter"
        else:
            temp_word = "ähnlich temperiert"

    rain_word: Optional[str] = None
    if precip_deltas:
        sum_precip = sum(precip_deltas)
        if sum_precip > 1.0:
            rain_word = "nasser"
        elif sum_precip < -1.0:
            rain_word = "trockener"

    temp_neutral = temp_word in (None, "ähnlich temperiert")
    rain_neutral = rain_word is None

    if temp_neutral and rain_neutral:
        return "Vortag: heute ähnliches Wetter wie gestern"

    if not temp_neutral and not rain_neutral:
        return f"Vortag: heute {temp_word} und {rain_word} als gestern"

    only_word = temp_word if not temp_neutral else rain_word
    return f"Vortag: heute {only_word} als gestern"


def _direction(delta: float, key: str) -> ComparisonDirection:
    """Richtung anhand der Metrik-Semantik."""
    if key in _NEUTRAL:
        return ComparisonDirection.EQUAL
    if abs(delta) < _FLOAT_EPS:
        return ComparisonDirection.EQUAL
    if key in _LOWER_IS_BETTER:
        return ComparisonDirection.BETTER if delta < 0 else ComparisonDirection.WORSE
    return ComparisonDirection.EQUAL  # Fallback: unbekannte Metrik neutral


def _float_delta(today_val: Optional[float], yday_val: Optional[float], key: str) -> MetricDelta:
    if today_val is None or yday_val is None:
        return MetricDelta(delta=None, direction=ComparisonDirection.MISSING)
    delta = today_val - yday_val
    return MetricDelta(delta=delta, direction=_direction(delta, key))


def _thunder_delta(
    today_level: Optional["ThunderLevel"],
    yday_level: Optional["ThunderLevel"],
) -> MetricDelta:
    if today_level is None or yday_level is None:
        return MetricDelta(delta=None, direction=ComparisonDirection.MISSING)
    today_ord = _THUNDER_ORDINAL.get(today_level.value if hasattr(today_level, "value") else today_level, 0)
    yday_ord = _THUNDER_ORDINAL.get(yday_level.value if hasattr(yday_level, "value") else yday_level, 0)
    delta = today_ord - yday_ord
    return MetricDelta(delta=float(delta), direction=_direction(float(delta), "thunder"))


def _missing_entry(segment_id: int) -> DayComparisonEntry:
    """Eintrag wenn das Segment gestern nicht existierte."""
    m = MetricDelta(delta=None, direction=ComparisonDirection.MISSING)
    return DayComparisonEntry(
        segment_id=segment_id,
        temp_min=m,
        temp_max=m,
        wind_max=m,
        gust_max=m,
        precip_sum=m,
        thunder=m,
    )


class DayComparisonService:
    """Berechnet Deltas zwischen heutiger und gestriger Wettervorhersage."""

    def compare(
        self,
        today: List["SegmentWeatherData"],
        yesterday: List["SegmentWeatherData"],
    ) -> DayComparison:
        """
        Vergleicht zwei SegmentWeatherData-Listen segment-weise.
        Matching über segment_id. Segmente die gestern fehlen → MISSING.
        """
        yday_by_id: Dict[int, "SegmentWeatherData"] = {
            seg.segment.segment_id: seg for seg in yesterday
        }

        entries: List[DayComparisonEntry] = []
        for seg_today in today:
            sid = seg_today.segment.segment_id
            seg_yday = yday_by_id.get(sid)

            if seg_yday is None:
                entries.append(_missing_entry(sid))
                continue

            t = seg_today.aggregated
            y = seg_yday.aggregated

            entries.append(DayComparisonEntry(
                segment_id=sid,
                temp_min=_float_delta(t.temp_min_c, y.temp_min_c, "temp_min_c"),
                temp_max=_float_delta(t.temp_max_c, y.temp_max_c, "temp_max_c"),
                wind_max=_float_delta(t.wind_max_kmh, y.wind_max_kmh, "wind_max_kmh"),
                gust_max=_float_delta(t.gust_max_kmh, y.gust_max_kmh, "gust_max_kmh"),
                precip_sum=_float_delta(t.precip_sum_mm, y.precip_sum_mm, "precip_sum_mm"),
                thunder=_thunder_delta(t.thunder_level_max, y.thunder_level_max),
            ))

        return DayComparison(entries=entries)

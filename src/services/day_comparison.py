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

# Mapping: metric_id → DayComparisonEntry-Attributname (AC-3/briefing-mail-inhalt)
_METRIC_ID_TO_ENTRY_ATTR: Dict[str, str] = {
    "wind": "wind_max",
    "gust": "gust_max",
    "precipitation": "precip_sum",
    "temperature": "temp_max",
    "wind_chill": "wind_chill_min",
    "thunder": "thunder",
    "cloud_total": "cloud_avg",
    "rain_probability": "pop_max",
    "uv_index": "uv_index_max",
    "sunshine": "sunshine_sum",
    "visibility": "visibility_min",
    "dewpoint": "dewpoint_avg",
    "freezing_level": "freezing_level",
    "humidity": "humidity_avg",
    "pressure": "pressure_avg",
}

# Richtungs-Wörter pro metric_id (höherer Wert → [0], niedrigerer → [1])
_DIRECTION_WORDS: Dict[str, tuple[str, str]] = {
    "wind": ("windiger", "ruhiger"),
    "gust": ("böiger", "ruhiger"),
    "precipitation": ("nasser", "trockener"),
    "temperature": ("wärmer", "kälter"),
    "wind_chill": ("gefühlt wärmer", "gefühlt kälter"),
    "thunder": ("Gewittergefahr", "kein Gewitter mehr"),
    "cloud_total": ("bewölkter", "sonniger"),
    "rain_probability": ("höhere Regenwahrscheinlichkeit", "geringere Regenwahrscheinlichkeit"),
    "uv_index": ("höherer UV", "niedrigerer UV"),
    "sunshine": ("sonniger", "weniger Sonne"),
    "visibility": ("bessere Sicht", "schlechtere Sicht"),
    "dewpoint": ("feuchter", "trockener"),
    "freezing_level": ("höhere Nullgradgrenze", "niedrigere Nullgradgrenze"),
    "humidity": ("feuchter", "trockener"),
    "pressure": ("höherer Luftdruck", "niedrigerer Luftdruck"),
}


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


def _missing_delta() -> "MetricDelta":
    return MetricDelta(delta=None, direction=ComparisonDirection.MISSING)


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
    # AC-3 (briefing-mail-inhalt): neue Felder, Default MISSING
    wind_chill_min: MetricDelta = field(default_factory=_missing_delta)
    cloud_avg: MetricDelta = field(default_factory=_missing_delta)
    uv_index_max: MetricDelta = field(default_factory=_missing_delta)
    sunshine_sum: MetricDelta = field(default_factory=_missing_delta)
    pop_max: MetricDelta = field(default_factory=_missing_delta)
    visibility_min: MetricDelta = field(default_factory=_missing_delta)
    dewpoint_avg: MetricDelta = field(default_factory=_missing_delta)
    freezing_level: MetricDelta = field(default_factory=_missing_delta)
    humidity_avg: MetricDelta = field(default_factory=_missing_delta)
    pressure_avg: MetricDelta = field(default_factory=_missing_delta)


def _scalar_delta(v: Optional[float], lower_is_better: bool = False) -> "MetricDelta":
    """Erzeugt MetricDelta aus skalarem Differenzwert. (#911 Test-Komfort)"""
    if v is None:
        return _missing_delta()
    if v > 0.5:
        direction = ComparisonDirection.WORSE if lower_is_better else ComparisonDirection.BETTER
    elif v < -0.5:
        direction = ComparisonDirection.BETTER if lower_is_better else ComparisonDirection.WORSE
    else:
        direction = ComparisonDirection.EQUAL
    return MetricDelta(delta=v, direction=direction)


@dataclass
class DayComparison:
    entries: List[DayComparisonEntry] = field(default_factory=list)
    # AC-1/2 (#911): optionaler Override-Summary für Test-Komfort-Konstruktor
    _summary_override: Optional[str] = field(default=None, repr=False)

    def __init__(
        self,
        entries: Optional[List[DayComparisonEntry]] = None,
        *,
        wind_delta_kmh: Optional[float] = None,
        gust_delta_kmh: Optional[float] = None,
        precip_delta_mm: Optional[float] = None,
        visibility_delta_m: Optional[float] = None,
        thunder_delta: Optional[float] = None,
        summary: Optional[str] = None,
    ):
        self._summary_override = summary
        if entries is not None:
            self.entries = entries
        elif any(v is not None for v in (
            wind_delta_kmh, gust_delta_kmh, precip_delta_mm, visibility_delta_m, thunder_delta
        )):
            self.entries = [DayComparisonEntry(
                segment_id=1,
                temp_min=_missing_delta(), temp_max=_missing_delta(),
                wind_max=_scalar_delta(wind_delta_kmh, lower_is_better=True),
                gust_max=_scalar_delta(gust_delta_kmh, lower_is_better=True),
                precip_sum=_scalar_delta(precip_delta_mm, lower_is_better=True),
                thunder=_scalar_delta(thunder_delta, lower_is_better=True),
                visibility_min=_scalar_delta(visibility_delta_m, lower_is_better=False),
            )]
        else:
            self.entries = []


def summarize_day_comparison(
    comparison: Optional["DayComparison"],
    *,
    selected_metrics: Optional[List[str]] = None,
) -> str:
    """Issue #790: Natursprachliche Vortag-Einordnungszeile.

    selected_metrics=None  → Backward-Compat (AC-4): temp_max + precip, ohne Schwellen.
    selected_metrics=[...] → AC-3: nur ausgewählte Metriken über Spürbarkeitsschwelle,
                             max. 4–6 Treffer nach |avg_delta| absteigend sortiert.
                             wind_chill verdrängt temperature wenn beide über Schwelle (AC-5).

    Rückgabe "" wenn comparison None/keine entries.
    """
    if comparison is None:
        return ""
    # AC-1/2 (#911): Override-Summary für Test-Komfort-Konstruktor
    if getattr(comparison, "_summary_override", None):
        return comparison._summary_override
    if not comparison.entries:
        return ""

    if not selected_metrics:
        return _summarize_legacy(comparison)

    return _summarize_metric_driven(comparison, selected_metrics)


def _summarize_legacy(comparison: "DayComparison") -> str:
    """Backward-Compat (AC-4): exakt bisherige temp+precip-Logik."""
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
        return "Vergleich zum Vortag: heute ähnliches Wetter wie gestern"

    if not temp_neutral and not rain_neutral:
        return f"Vergleich zum Vortag: heute {temp_word} und {rain_word} als gestern"

    only_word = temp_word if not temp_neutral else rain_word
    return f"Vergleich zum Vortag: heute {only_word} als gestern"


_SALIENCE_FACTOR = 0.6


def _get_threshold(metric_id: str) -> float:
    """Spürbarkeitsschwelle aus MetricCatalog × _SALIENCE_FACTOR; Fallback 3.0.

    Wirkt ausschließlich im Anzeige-Pfad der Vortags-Zeile.
    metric_catalog.default_change_threshold bleibt unverändert (AC-6).
    """
    try:
        from app.metric_catalog import get_metric
        m = get_metric(metric_id)
        if m.default_change_threshold is not None:
            return float(m.default_change_threshold) * _SALIENCE_FACTOR
    except Exception:
        pass
    return 3.0


def _summarize_metric_driven(
    comparison: "DayComparison",
    selected_metrics: List[str],
) -> str:
    """AC-3: metrik-getriebenes, relevanz-gefiltertes Summary."""
    # Durchschnittsdelta pro Metrik über alle Segmente berechnen
    avg_deltas: List[tuple[str, float]] = []
    for mid in selected_metrics:
        attr = _METRIC_ID_TO_ENTRY_ATTR.get(mid)
        if attr is None:
            continue
        vals = [
            getattr(e, attr).delta
            for e in comparison.entries
            if getattr(e, attr, None) is not None
            and getattr(e, attr).delta is not None
        ]
        if not vals:
            continue
        avg = sum(vals) / len(vals)
        avg_deltas.append((mid, avg))

    # Relevanz-Filter: |avg| >= Schwelle
    salient: List[tuple[str, float]] = []
    for mid, avg in avg_deltas:
        if mid == "thunder":
            # Thunder nur bei echter Level-Änderung (ordinal-Delta != 0)
            if abs(avg) >= 0.5:
                salient.append((mid, avg))
        else:
            thr = _get_threshold(mid)
            if abs(avg) >= thr:
                salient.append((mid, avg))

    # AC-5: wind_chill verdrängt temperature wenn beide über Schwelle
    mid_set = {m for m, _ in salient}
    if "wind_chill" in mid_set and "temperature" in mid_set:
        salient = [(m, d) for m, d in salient if m != "temperature"]

    # Nach |delta| absteigend sortieren, max. 6 nehmen
    salient.sort(key=lambda x: abs(x[1]), reverse=True)
    salient = salient[:6]

    if not salient:
        return "Vergleich zum Vortag: heute ähnliches Wetter wie gestern"

    parts: List[str] = []
    for mid, avg in salient:
        words = _DIRECTION_WORDS.get(mid, ("anders", "anders"))
        word = words[0] if avg > 0 else words[1]
        parts.append(word)

    joined = " und ".join(parts) if len(parts) <= 2 else ", ".join(parts[:-1]) + " und " + parts[-1]
    return f"Vergleich zum Vortag: heute {joined} als gestern"


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
                # AC-3: neue Metriken aus SegmentWeatherSummary
                wind_chill_min=_float_delta(t.wind_chill_min_c, y.wind_chill_min_c, "wind_chill_min_c"),
                cloud_avg=_float_delta(
                    float(t.cloud_avg_pct) if t.cloud_avg_pct is not None else None,
                    float(y.cloud_avg_pct) if y.cloud_avg_pct is not None else None,
                    "cloud_avg_pct",
                ),
                uv_index_max=_float_delta(t.uv_index_max, y.uv_index_max, "uv_index_max"),
                sunshine_sum=_float_delta(t.sunny_hours, y.sunny_hours, "sunny_hours"),
                pop_max=_float_delta(
                    float(t.pop_max_pct) if t.pop_max_pct is not None else None,
                    float(y.pop_max_pct) if y.pop_max_pct is not None else None,
                    "pop_max_pct",
                ),
                visibility_min=_float_delta(
                    float(t.visibility_min_m) if t.visibility_min_m is not None else None,
                    float(y.visibility_min_m) if y.visibility_min_m is not None else None,
                    "visibility_min_m",
                ),
                dewpoint_avg=_float_delta(t.dewpoint_avg_c, y.dewpoint_avg_c, "dewpoint_avg_c"),
                freezing_level=_float_delta(
                    float(t.freezing_level_m) if t.freezing_level_m is not None else None,
                    float(y.freezing_level_m) if y.freezing_level_m is not None else None,
                    "freezing_level_m",
                ),
                humidity_avg=_float_delta(
                    float(t.humidity_avg_pct) if t.humidity_avg_pct is not None else None,
                    float(y.humidity_avg_pct) if y.humidity_avg_pct is not None else None,
                    "humidity_avg_pct",
                ),
                pressure_avg=_float_delta(t.pressure_avg_hpa, y.pressure_avg_hpa, "pressure_avg_hpa"),
            ))

        return DayComparison(entries=entries)

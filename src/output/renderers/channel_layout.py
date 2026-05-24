"""Kanal-bewusste Layout-Berechnung (Issue #360, Teil 1 von Epic #331).

SPEC: docs/specs/modules/issue_360_signal_channel_renderer.md §2–§4.

Pure functions: aus einer ``UnifiedWeatherDisplayConfig`` und einem Kanal
wird berechnet, welche Metriken als eigene Tabellen-Spalte erscheinen und
welche in die kompakte Detail-Zeile wandern. Keine I/O, keine Mocks.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - nur fuer Typannotation
    from app.models import MetricConfig, UnifiedWeatherDisplayConfig


# Kanal-Constraints. ``max_table_cols`` zaehlt die GESAMT-Spalten inkl. der
# impliziten Zeit-Spalte (Signal 6 = Zeit + 5 Metriken).
CHANNEL_LIMITS = {
    "email":    {"max_table_cols": None, "max_chars": None},   # unbegrenzt
    "telegram": {"max_table_cols": 8,    "max_chars": 4096},
    "signal":   {"max_table_cols": 6,    "max_chars": 1800},
    "sms":      {"max_table_cols": 0,    "max_chars": 140},
}


# Heuristik-Prioritaet fuer die Auto-Verteilung (Katalog-IDs, nicht #331-JS-IDs).
# Hoeher = wichtiger. Die 5 wichtigsten landen im ``primary``-Bucket.
METRIC_PRIORITY = {
    "temperature": 95, "wind": 90, "gust": 88, "rain_probability": 85,
    "precipitation": 78, "wind_chill": 70, "cloud_total": 65, "thunder": 60,
    "fresh_snow": 55, "visibility": 55, "freezing_level": 50, "uv_index": 45,
    "wind_direction": 40, "snow_depth": 35, "precip_type": 35, "snowfall_limit": 35,
    "cloud_low": 30, "humidity": 25, "sunshine": 25, "dewpoint": 20,
    "pressure": 18, "cape": 15, "cloud_mid": 12, "cloud_high": 10, "confidence": 8,
}

# Anzahl Metriken, die die Auto-Verteilung als ``primary`` markiert
# (= Signal-Limit 6 minus Zeit-Spalte ⇒ Signal-safe).
_PRIMARY_SLOTS = 5


@dataclass(frozen=True)
class ChannelLayout:
    """Ergebnis der Layout-Berechnung fuer einen Kanal."""
    table_columns: list[str]   # metric_ids in Spalten-Reihenfolge (ohne Zeit)
    detail_metrics: list[str]  # metric_ids fuer die Detail-Zeile
    demoted_count: int         # aus primary in Detail verschoben (Logging/Badge)


def render_for_channel(
    channel: str, dc: "UnifiedWeatherDisplayConfig", report_type: str,
) -> ChannelLayout:
    """Berechne das Spalten-/Detail-Layout fuer ``channel``.

    Respektiert die per-Report-Typ-Flags ueber ``get_metrics_for_report_type``.
    """
    enabled = dc.get_metrics_for_report_type(report_type)
    primary = sorted(
        [m for m in enabled if m.bucket == "primary"], key=lambda m: m.order,
    )
    secondary = sorted(
        [m for m in enabled if m.bucket == "secondary"], key=lambda m: m.order,
    )

    limit = CHANNEL_LIMITS[channel]["max_table_cols"]
    if limit is None:                       # Email: kein Limit
        table, overflow = primary, []
    elif limit == 0:                        # SMS: keine Tabelle
        table, overflow = [], primary
    else:                                   # Signal/Telegram: Slot 0 = Zeit
        metric_slots = limit - 1
        table, overflow = primary[:metric_slots], primary[metric_slots:]

    return ChannelLayout(
        table_columns=[m.metric_id for m in table],
        detail_metrics=[m.metric_id for m in (overflow + secondary)],
        demoted_count=len(overflow),
    )


def auto_distribute(enabled_ids: list[str]) -> list["MetricConfig"]:
    """Verteile aktive Metrik-IDs auf primary/secondary (Signal-safe Heuristik).

    Die 5 wichtigsten (nach ``METRIC_PRIORITY``) -> ``primary`` mit order 0..4,
    der Rest -> ``secondary`` mit order 0..n. Reihenfolge stabil: bei gleicher
    Prioritaet bleibt die Eingabe-Reihenfolge erhalten.
    """
    from app.models import MetricConfig

    ranked = sorted(
        enumerate(enabled_ids),
        key=lambda pair: (-METRIC_PRIORITY.get(pair[1], 0), pair[0]),
    )
    ordered_ids = [mid for _, mid in ranked]

    result: list[MetricConfig] = []
    for idx, metric_id in enumerate(ordered_ids):
        if idx < _PRIMARY_SLOTS:
            result.append(MetricConfig(
                metric_id=metric_id, bucket="primary", order=idx,
            ))
        else:
            result.append(MetricConfig(
                metric_id=metric_id, bucket="secondary", order=idx - _PRIMARY_SLOTS,
            ))
    return result

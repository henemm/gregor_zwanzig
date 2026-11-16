"""Altpfad als Test-Orakel fuer den Kanal-Listen-Resolver (Issue #3057, ADR-0121).

Eingefrorene Kopie der Kanal-Aufloesung VOR #3057, aufgebaut nur aus den
bestehenden Primitiven (die nicht geaendert werden). Nach der Umstellung lesen
``UnifiedWeatherDisplayConfig.get_metrics_for_channel`` und
``resolve_compare_render_options`` aus dem neuen Resolver; der Differenztest
``tests/tdd/test_3057_channel_list_resolver.py`` prueft neu = alt gegen diese
Datei. Wird in #3058 zusammen mit den Altpfaden geloescht.

Bewusst KEIN Aufruf von ``get_metrics_for_channel`` oder
``resolve_compare_render_options`` hier -- sonst verglichen die Tests den
neuen Pfad mit sich selbst.
"""
from __future__ import annotations

from typing import Optional

from app.models import (
    MetricConfig,
    UnifiedWeatherDisplayConfig,
    _cascade_source_for_channel,
    _filter_metrics_by_report_type,
    _sorted_by_layout,
)

KANAELE_ORTE = ("email", "telegram", "sms")


def alt_trip_metrics_for_channel(
    dc: UnifiedWeatherDisplayConfig, channel: str, report_type: str,
) -> list[MetricConfig]:
    """Wortgleiche Kopie von ``get_metrics_for_channel`` (Stand vor #3057)."""
    source = _cascade_source_for_channel(
        dc.per_report_layouts, dc.per_channel_layouts, channel, report_type,
    )
    if source == "per_report":
        liste = dc.per_report_layouts[report_type][channel]  # type: ignore[index]
        if len(liste) == 0:
            return []
        gefiltert = _filter_metrics_by_report_type(liste, report_type)
        return _sorted_by_layout(dc._clip_to_global_maximum(gefiltert, report_type))
    if source == "per_channel":
        liste = dc.per_channel_layouts[channel]  # type: ignore[index]
        if len(liste) == 0:
            return []
        gefiltert = _filter_metrics_by_report_type(liste, report_type)
        return _sorted_by_layout(dc._clip_to_global_maximum(gefiltert, report_type))
    return _sorted_by_layout(dc.get_metrics_for_report_type(report_type))


def alt_trip_format(mc: MetricConfig) -> Optional[str]:
    """Format einer Trip-Zeile im Vokabular von ADR-0121 (``raw|simplified|None``).

    ``None`` = Katalog-Standard (``loader._resolve_format_mode``): ein Eintrag
    ohne ``format_mode`` mit ``use_friendly_format=True``. ``False`` ohne
    ``format_mode`` ist ausdruecklich Roh."""
    if mc.format_mode is not None:
        return mc.format_mode
    return None if mc.use_friendly_format else "raw"


def alt_compare_kanaele(preset: dict) -> tuple[
    dict[str, Optional[list[str]]], dict[str, Optional[list[tuple[str, bool]]]],
]:
    """Kanalteil von ``resolve_compare_render_options`` (Stand vor #3057):
    ``(enabled_metrics_by_channel, channel_rows_by_channel)``."""
    from output.renderers.compare_metric_ids import (
        resolve_channel_enabled_metrics,
        resolve_channel_layout_rows,
        resolve_enabled_metrics_report,
    )

    dc = preset.get("display_config") or {}
    global_metrics, _unresolved = resolve_enabled_metrics_report(dc.get("active_metrics"))
    channel_raw = dc.get("channel_active_metrics")
    rows = {
        ch: resolve_channel_layout_rows(global_metrics, dc.get("channel_layouts"), ch)
        for ch in KANAELE_ORTE
    }
    enabled = {
        ch: (
            resolve_channel_enabled_metrics(global_metrics, channel_raw, ch)
            if rows[ch] is None
            else [rid for rid, _einfach in rows[ch]]
        )
        for ch in KANAELE_ORTE
    }
    return enabled, rows


def alt_compare_premium_zeilen(preset: dict) -> Optional[list[str]]:
    """Was eine eigene ``channel_layouts.premium_sms``-Liste nach der heutigen
    Orte-Primitive ergaebe (fuer AC-5, eigene Liste lesbar)."""
    from output.renderers.compare_metric_ids import (
        resolve_channel_layout_rows,
        resolve_enabled_metrics_report,
    )

    dc = preset.get("display_config") or {}
    global_metrics, _ = resolve_enabled_metrics_report(dc.get("active_metrics"))
    rows = resolve_channel_layout_rows(global_metrics, dc.get("channel_layouts"), "premium_sms")
    return None if rows is None else [rid for rid, _ in rows]

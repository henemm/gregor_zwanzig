"""Kanonische Kanal-Liste: ein Lese-Resolver fuer Trip und Orte (Issue #3057, ADR-0121).

``resolve_channel_lists(display_config, surface, report_type)`` beantwortet fuer
die vier Versandkanaele (E-Mail, Telegram, SMS, Premium-SMS) die Frage "welche
Metriken in welcher Folge und Darstellung" -- fuer den Trip ueber die
bestehende Kaskade ``per_report > channel > global`` (ADR-0050), fuer Orte ueber
``channel_layouts`` vor ``channel_active_metrics`` vor Grundauswahl (ADR-0119).
Der Resolver buendelt nur die bestehenden Primitive; er schreibt nie, liest
keine Datei und veraendert die Eingabe nicht.

``format`` einer Zeile: ``raw | simplified | None`` (None = Flaechen-Standard,
Trip Katalog, Orte Roh). Gelesen aus ``format`` vor ``format_mode`` vor
``use_friendly_format`` (Lese-Adapter, der Loader bleibt unveraendert).
"""
from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Optional

from app import models as _models
from app.models import MetricConfig, UnifiedWeatherDisplayConfig

KANAELE = ("email", "telegram", "sms", "premium_sms")
_FORMATE = ("raw", "simplified")


@dataclass(frozen=True)
class ChannelRow:
    metric_id: str
    enabled: bool
    format: Optional[str]
    order: int


Rows = Optional[tuple[ChannelRow, ...]]


@dataclass(frozen=True)
class MailViewModel:
    """Je Kanal ein Tupel von Zeilen in Anzeigefolge; ``None`` = kein Filter
    (nur Orte ohne Grundauswahl und ohne Kanal-Liste). ``layout_channels``:
    Orte-Kanaele, deren Zeilen aus ``channel_layouts`` stammen.

    ``outlook`` (Trip und Orte) und ``hourly`` (nur Orte) tragen Katalog-IDs
    (#3065, ADR-0121 Nachtrag 2b): ``None`` = Renderer-Vorgabemenge, ``()`` =
    Block entfaellt. Orte-``hourly`` ist nie ``None`` (#3096: die Vorgabe "nie
    eingestellt" kommt als konkrete Liste aus ``compare_hourly_metric_ids``);
    Trip-``hourly`` ist immer ``None``. Die Trip-Mail liest ihre Spaltenfolge
    aus ``email`` (Adapter ``email.helpers.email_col_order``, #3096)."""
    email: Rows
    telegram: Rows
    sms: Rows
    premium_sms: Rows
    layout_channels: tuple[str, ...] = ()
    outlook: Rows = None
    hourly: Rows = None


def _area_rows(ids, formats=None) -> Rows:
    """Katalog-IDs -> Zeilen (None bleibt None, [] wird ()). Ausblick-Format
    aus ``{id: bool}``: wahr = Einfach, ausdruecklich falsch = Roh."""
    if ids is None:
        return None
    formats = formats or {}
    return tuple(
        ChannelRow(mid, True, {True: "simplified", False: "raw"}.get(formats.get(mid)), i)
        for i, mid in enumerate(ids)
    )


def resolve_channel_lists(display_config, surface: str, report_type: Optional[str] = None) -> MailViewModel:
    """Reine Funktion: ``display_config`` -> ``MailViewModel`` (ADR-0121)."""
    if surface == "trip":
        return _trip_view(display_config, report_type or "evening")
    if surface == "compare":
        return _compare_view(display_config or {})
    raise ValueError(f"unbekannte Flaeche {surface!r}")


# ---------------------------------------------------------------------------
# Trip
# ---------------------------------------------------------------------------

def trip_channel_metrics(
    dc: UnifiedWeatherDisplayConfig, channel: str, report_type: str,
) -> list[MetricConfig]:
    """Trip-Kaskade je Kanal (ADR-0050): Kanal-Ebenen werden gegen die
    Grundauswahl geschnitten, eine leere Liste bleibt leer. Quelle fuer
    ``UnifiedWeatherDisplayConfig.get_metrics_for_channel``. Primitive werden
    zur Laufzeit am Modul nachgeschlagen (Mutationsproben auf ``app.models``
    wirken so weiter)."""
    source = _models._cascade_source_for_channel(
        dc.per_report_layouts, dc.per_channel_layouts, channel, report_type,
    )
    if source == "global":
        return dc.get_metrics_for_report_type(report_type)
    if source == "per_report":
        liste = dc.per_report_layouts[report_type][channel]  # type: ignore[index]
    else:
        liste = dc.per_channel_layouts[channel]  # type: ignore[index]
    if len(liste) == 0:
        return []
    gefiltert = _models._filter_metrics_by_report_type(liste, report_type)
    return _models._sorted_by_layout(dc._clip_to_global_maximum(gefiltert, report_type))


def _trip_format(mc: MetricConfig) -> Optional[str]:
    """``None`` = Katalog-Standard (kein ``format_mode``, ``use_friendly_format``
    wahr); ``use_friendly_format=False`` ohne ``format_mode`` ist Roh."""
    if mc.format_mode is not None:
        return mc.format_mode
    return None if mc.use_friendly_format else "raw"


def _trip_model(display_config) -> UnifiedWeatherDisplayConfig:
    # #3096: jedes fertige Modell geht durch (auch eine zweite Klassen-
    # Identitaet derselben Klasse, z. B. Import ueber ``src.app.models``);
    # geparst wird nur das rohe Dict.
    if isinstance(display_config, UnifiedWeatherDisplayConfig) or (
        display_config is not None and not isinstance(display_config, dict)
    ):
        return display_config
    from app.loader import _parse_display_config

    roh = copy.deepcopy(display_config or {})
    for eintrag in _trip_entries(roh):
        if eintrag.get("format") in _FORMATE:
            eintrag["format_mode"] = eintrag["format"]
    # #3048: Trip-Pfad -- Altbestand ohne/mit leeren ``metrics`` bekommt den
    # Register-Standardsatz wie im Trip-Loader.
    return _parse_display_config(roh, trip_standard_bei_leer=True)


def _trip_entries(roh: dict):
    """Alle Eintraege der Kanal-Listen (channel_layouts, per Report)."""
    ebenen = [roh.get("channel_layouts")]
    per_report = roh.get("channel_layouts_per_report")
    if isinstance(per_report, dict):
        ebenen.extend(per_report.values())
    for ebene in ebenen:
        if not isinstance(ebene, dict):
            continue
        for liste in ebene.values():
            if isinstance(liste, list):
                yield from (e for e in liste if isinstance(e, dict))


def _trip_view(display_config, report_type: str) -> MailViewModel:
    dc = _trip_model(display_config)
    kanaele = {
        ch: tuple(
            ChannelRow(mc.metric_id, True, _trip_format(mc), i)
            for i, mc in enumerate(trip_channel_metrics(dc, ch, report_type))
        )
        for ch in KANAELE
    }
    eigene_premium = _models._cascade_source_for_channel(
        dc.per_report_layouts, dc.per_channel_layouts, "premium_sms", report_type,
    ) != "global"
    if not eigene_premium:
        kanaele["premium_sms"] = kanaele["sms"]
    from output.renderers.compare_outlook_metric_ids import (
        resolve_trip_outlook_formats, resolve_trip_outlook_metrics,
    )

    outlook = _area_rows(
        resolve_trip_outlook_metrics(dc, report_type), resolve_trip_outlook_formats(dc),
    )
    return MailViewModel(**kanaele, outlook=outlook)


# ---------------------------------------------------------------------------
# Orte
# ---------------------------------------------------------------------------

def _requested_format(entry: dict) -> Optional[str]:
    for key in ("format", "format_mode"):
        if entry.get(key) in _FORMATE:
            return entry[key]
    if "use_friendly_format" in entry:
        return "simplified" if entry["use_friendly_format"] is True else "raw"
    return None


def _normalized_layouts(channel_layouts):
    """Kopie von ``channel_layouts``, in der jede Format-Schreibweise als
    ``use_friendly_format`` steht -- so liest sie die bestehende Primitive."""
    if not isinstance(channel_layouts, dict):
        return channel_layouts
    out = {}
    for ch, entries in channel_layouts.items():
        if not isinstance(entries, list):
            out[ch] = entries
            continue
        out[ch] = [
            {**e, "use_friendly_format": _requested_format(e) == "simplified"}
            if isinstance(e, dict) and _requested_format(e) is not None else e
            for e in entries
        ]
    return out


def _layout_rows(rows: list[tuple[str, bool]], entries: list) -> tuple[ChannelRow, ...]:
    from output.renderers.compare_metric_ids import _renderer_ids_for_kennung

    angegeben: dict[str, Optional[str]] = {}
    for e in entries:
        if not isinstance(e, dict) or e.get("enabled") is False:
            continue
        fmt = None if _requested_format(e) is None else "raw"
        for rid in _renderer_ids_for_kennung(e.get("metric_id")):
            angegeben.setdefault(rid, fmt)
    return tuple(
        ChannelRow(rid, True, "simplified" if einfach else angegeben.get(rid), i)
        for i, (rid, einfach) in enumerate(rows)
    )


def _compare_view(dc: dict) -> MailViewModel:
    from output.renderers.compare_metric_ids import (
        resolve_channel_enabled_metrics, resolve_channel_layout_rows, resolve_enabled_metrics,
    )

    global_metrics = resolve_enabled_metrics(dc.get("active_metrics"))
    layouts = _normalized_layouts(dc.get("channel_layouts"))
    kanaele: dict[str, Rows] = {}
    layout_channels: list[str] = []
    for ch in KANAELE:
        rows = resolve_channel_layout_rows(global_metrics, layouts, ch)
        if rows is not None:
            layout_channels.append(ch)
            kanaele[ch] = _layout_rows(rows, layouts[ch])
        elif ch == "premium_sms":
            kanaele[ch] = kanaele["sms"]
        else:
            ids = resolve_channel_enabled_metrics(
                global_metrics, dc.get("channel_active_metrics"), ch,
            )
            kanaele[ch] = None if ids is None else tuple(
                ChannelRow(rid, True, None, i) for i, rid in enumerate(ids)
            )
    from output.renderers.compare_hourly_metric_ids import resolve_hourly_metric_ids
    from output.renderers.compare_outlook_metric_ids import (
        resolve_compare_outlook_formats, resolve_compare_outlook_metrics,
        resolve_hourly_metric_formats,
    )

    outlook = _area_rows(
        resolve_compare_outlook_metrics(dc.get("outlook_metrics"), global_metrics),
        resolve_compare_outlook_formats(dc.get("outlook_metric_formats")),
    )
    # #3097 (ADR-0121 Nachtrag 3b): Format aus `hourly_metric_formats`, fehlt = Roh.
    hourly = _area_rows(
        resolve_hourly_metric_ids(dc.get("hourly_metrics"), global_metrics),
        resolve_hourly_metric_formats(dc.get("hourly_metric_formats")),
    )
    return MailViewModel(
        **kanaele, layout_channels=tuple(layout_channels), outlook=outlook, hourly=hourly,
    )

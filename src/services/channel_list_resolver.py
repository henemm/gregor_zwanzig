"""Kanonische Kanal-Liste: ein Lese-Resolver fuer Trip und Orte (Issue #3057, ADR-0121).

``resolve_channel_lists(display_config, surface, report_type)`` beantwortet fuer
die vier Versandkanaele (E-Mail, Telegram, SMS, Premium-SMS) die Frage "welche
Metriken in welcher Folge und Darstellung" allein aus der Tabelle
``placements`` (#3122, ADR-0124); ohne Tabelle aus der Grundauswahl (#3237).
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import NamedTuple, Optional, Sequence

from app.models import MetricConfig, UnifiedWeatherDisplayConfig

KANAELE = ("email", "telegram", "sms", "premium_sms")


@dataclass(frozen=True)
class ChannelRow:
    metric_id: str
    enabled: bool
    format: Optional[str]
    order: int
    # Herkunft (Eintrag der Grundauswahl) fuer Adapter; aus der Tabelle None.
    source: Optional[MetricConfig] = field(default=None, compare=False, repr=False)
    # #3101: Auswertung einer Orte-Kanalzeile (``max``/``min``/``sum``/``avg``);
    # ``metric_id`` ist dort die Katalog-ID, das Paar adressiert genau eine
    # Renderer-Zeile (Adapter ``compare_metric_ids.renderer_kennung``). ``None``
    # bei Trip-Zeilen und in Ausblick/Stundenverlauf.
    aggregation: Optional[str] = None


Rows = Optional[tuple[ChannelRow, ...]]


@dataclass(frozen=True)
class MailViewModel:
    """Je Kanal ein Tupel von Zeilen in Anzeigefolge (``layout_channels``: Orte).

    Ein Vokabular (#3101, ADR-0121 Nachtrag 4): alle Listen tragen Katalog-IDs;
    Orte-Kanalzeilen zusaetzlich ``aggregation`` (je Zeile genau eine
    Renderer-Zeile, Teilauswahl und Folge je Kanal bleiben erhalten). Die
    Renderer-Kennung entsteht erst im Adapter vor dem Renderer.
    Nirgends ``None``; ``outlook``/``hourly`` = ``()``: Block entfaellt
    (Trip-``hourly`` immer ``()``); ``premium_sms`` ist ``sms``."""
    email: Rows
    telegram: Rows
    sms: Rows
    premium_sms: Rows
    layout_channels: tuple[str, ...] = ()
    outlook: Rows = None
    hourly: Rows = None
    # #3122: Zeilen der Tabelle "Was steht wo" (Katalog-IDs, je Stelle Zustand
    # und Format, ``services.placements.PlacementRow``) und die aufgeloesten
    # Briefing-Typen mit 3-Tages-Ausblick.
    rows: tuple = ()
    outlook_reports: tuple[str, ...] = ()


def resolve_channel_lists(
    display_config, surface: str, report_type: Optional[str] = None, *,
    enabled_reports: Optional[Sequence[str]] = None,
    hourly_enabled: Optional[bool] = None,
    outlook_enabled: Optional[bool] = None,
) -> MailViewModel:
    """Reine Funktion: ``display_config`` (Dict oder Modell) -> ``MailViewModel``.
    Ohne Tabelle gilt ``placements_aus_grundauswahl`` (#3237); Altfelder wirken
    nicht. ``enabled_reports``/``hourly_enabled``/``outlook_enabled``: Abo."""
    from services.placements import placements_aus_grundauswahl, read_placements

    if surface not in ("trip", "compare"):
        raise ValueError(f"unbekannte Flaeche {surface!r}")
    roh = display_config.get("placements") if isinstance(display_config, dict) else getattr(
        display_config, "placements", None)
    stored = read_placements(roh)
    if stored is None:
        stored = read_placements(placements_aus_grundauswahl(
            display_config, surface, enabled_reports=enabled_reports,
            outlook_enabled=outlook_enabled))
    return placements_view(display_config, surface, report_type, stored,
                           enabled_reports=enabled_reports, hourly_enabled=hourly_enabled)


# ---------------------------------------------------------------------------
# Tabelle "Was steht wo" (#3122)
# ---------------------------------------------------------------------------

class Grundauswahl(NamedTuple):
    """Katalog-IDs der Grundauswahl (Maximum, Nr. 3.1), abgeleitete Groesse
    -> Eltern-Kennung, bei Orten die Renderer-Kennungen der Auswahl.

    Orte (#3122 B1b): ``unaufloesbar`` = gewaehlte Eintraege ohne Renderer-
    Zuordnung (Hinweiszaehler, #1405 S3); ``nie_eingestellt`` = die Auswahl
    fehlt, ``renderer`` ist dann der Standardsatz (Orte-Alarm, #1191)."""
    ids: list
    parents: dict
    renderer: Optional[frozenset]
    unaufloesbar: tuple = ()
    nie_eingestellt: bool = False


def _orte_standard() -> list[str]:
    """Nie eingestellte Orte-Grundauswahl: alle Zeilen der Uebersicht in der
    Standardfolge (CV2-Deklarationsfolge, wie ``_ordered_rows`` bei None)."""
    from output.renderers.email.compare_html import CV2_ZEILEN

    return [z["key"] for z in CV2_ZEILEN if z["key"] != "warn"]


def grundauswahl(display_config, surface: str, report_type: Optional[str]) -> Grundauswahl:
    """Grundauswahl je Flaeche; nie eingestellt = Standardsatz wie im
    bisherigen Pfad (Trip: Register-Standard ueber den Trip-Ladepfad)."""
    from app.metric_catalog import _METRICS_BY_ID

    if surface == "trip":
        from app.loader import _DERIVED_METRIC_RULES

        eltern = {kind: elter for kind, elter, _agg in _DERIVED_METRIC_RULES}
        mcs = _trip_model(display_config).get_metrics_for_report_type(report_type or "evening")
        ids = list(dict.fromkeys(
            mc.metric_id for mc in mcs
            if getattr(_METRICS_BY_ID.get(mc.metric_id), "selectable", False)
        ))
        parents = {mc.metric_id: eltern[mc.metric_id] for mc in mcs
                   if mc.derived and mc.metric_id in eltern}
        return Grundauswahl(ids, parents, None)
    from output.renderers.compare_metric_ids import resolve_enabled_metrics_report
    from output.renderers.compare_outlook_metric_ids import _kennungen_aus_renderer_ids

    renderer, unaufloesbar = resolve_enabled_metrics_report(
        (display_config or {}).get("active_metrics"))
    nie_eingestellt = renderer is None
    if nie_eingestellt:
        renderer = _orte_standard()
    return Grundauswahl(
        list(dict.fromkeys(_kennungen_aus_renderer_ids(renderer))), {}, frozenset(renderer),
        unaufloesbar, nie_eingestellt)


def tabellen_grundauswahl(display_config, surface: str) -> tuple[list[str], dict]:
    """Tabellen-Grundauswahl (IDs, Eltern): Abend, dahinter nur-morgens (#3154)."""
    ids: list[str] = []
    eltern: dict = {}
    for rt in ("evening", "morning"):
        grund = grundauswahl(display_config, surface, rt)
        ids += [m for m in grund.ids if m not in ids]
        eltern = {**grund.parents, **eltern}
    return ids, eltern


def placements_view(
    display_config, surface: str, report_type: Optional[str], stored, *,
    enabled_reports: Optional[Sequence[str]] = None, hourly_enabled: Optional[bool] = None,
) -> MailViewModel:
    """View-Model aus einer gelesenen Tabelle (``StoredPlacements``)."""
    from services.placements import (
        metrics_at, outlook_applies, resolve_outlook_reports, resolve_rows,
    )

    rt = report_type or ("evening" if surface == "trip" else None)
    grund = grundauswahl(display_config, surface, rt)
    rows = resolve_rows(stored.rows, grund.ids, surface, parents=grund.parents)
    reports = resolve_outlook_reports(stored.outlook_reports, enabled_reports)
    # Stellen der Tabelle, keine Versandliste: die Premium-SMS folgt der SMS
    # ohne eigene Spalte bis S9 (ADR-0049, ADR-0124 Nr. 8).
    kanaele = {ch: _kanal_rows(metrics_at(rows, ch), grund) for ch in ("email", "telegram", "sms")}
    outlook = _area_from(metrics_at(rows, "outlook")) if outlook_applies(rows, reports, rt) else ()
    hourly = () if surface == "trip" or hourly_enabled is False else _area_from(
        metrics_at(rows, "hourly"))
    return MailViewModel(
        **kanaele, premium_sms=kanaele["sms"],
        layout_channels=() if surface == "trip" else KANAELE,
        outlook=outlook, hourly=hourly, rows=rows, outlook_reports=reports,
    )


def _area_from(eintraege) -> tuple[ChannelRow, ...]:
    return tuple(ChannelRow(mid, True, fmt, i) for i, (mid, fmt) in enumerate(eintraege))


def _orte_zeilen(eintraege) -> tuple[ChannelRow, ...]:
    """Orte-Kanalzeilen aus ``[(renderer_kennung, format)]``: je Renderer-Zeile
    eine Zeile mit Katalog-ID und Auswertung (#3101), Folge bleibt."""
    from output.renderers.compare_metric_ids import katalog_paar

    zeilen = []
    for rid, fmt in eintraege:
        paar = katalog_paar(rid)
        if paar is not None:
            zeilen.append(ChannelRow(paar[0], True, fmt, len(zeilen), aggregation=paar[1]))
    return tuple(zeilen)


def _kanal_rows(eintraege, grund: Grundauswahl) -> tuple[ChannelRow, ...]:
    """Trip: Katalog-IDs wie heute. Orte: Aufweitung der Katalog-ID auf die
    Auswertungen der Grundauswahl (Nr. 2), Format der Zeile fuer alle."""
    if grund.renderer is None:
        return _area_from(eintraege)
    from output.renderers.compare_metric_ids import _renderer_ids_for_kennung

    return _orte_zeilen([
        (rid, fmt) for cid, fmt in eintraege
        for rid in _renderer_ids_for_kennung(cid) if rid in grund.renderer
    ])


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
    # #3048: Trip-Pfad -- Altbestand ohne/mit leeren ``metrics`` bekommt den
    # Register-Standardsatz wie im Trip-Loader.
    return _parse_display_config(roh, trip_standard_bei_leer=True)


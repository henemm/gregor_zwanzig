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

Issue #3122 (ADR-0124, Spec feat_3122_was_steht_wo Teil A): zweiter Eingang.
Traegt ``display_config`` eine lesbare Tabelle ``placements``, entsteht das
View-Model allein daraus (``services.placements``): eine Reihenfolge fuer alle
Stellen, ``None`` kommt nicht vor, ``()`` heisst "Stelle leer" bzw. "Block
entfaellt". Abos ohne ``placements`` lesen ihre Kanal-Listen bis B3 ueber den
bisherigen Pfad (Schalter ``ALTBESTAND_UEBER_UMRECHNUNG``); ``rows`` und
``outlook_reports`` kommen fuer sie aus der Umrechnung des Altbestands.
"""
from __future__ import annotations

import copy
import dataclasses
from dataclasses import dataclass, field
from typing import NamedTuple, Optional, Sequence

from app import models as _models
from app.models import MetricConfig, UnifiedWeatherDisplayConfig

KANAELE = ("email", "telegram", "sms", "premium_sms")
_FORMATE = ("raw", "simplified")

#: #3122 B1a: Abos ohne ``placements`` lesen ihre Kanal-Listen ueber den
#: bisherigen Pfad (``False``). B3 legt den Schalter um: dann laufen sie ueber
#: die Umrechnung ``placements_from_legacy`` und den neuen Eingang.
ALTBESTAND_UEBER_UMRECHNUNG = False


@dataclass(frozen=True)
class ChannelRow:
    metric_id: str
    enabled: bool
    format: Optional[str]
    order: int
    # #3122: Herkunft einer Trip-Kanal-Zeile im bisherigen Pfad -- genau der
    # Eintrag, den die Kaskade geliefert hat (Kanal-Ebene oder, im Rueckfall
    # und ohne Kanal-Ebene, Grundauswahl). Er traegt, was die Zeile nicht
    # traegt (``horizons``, Position, Format-Schreibweise); die Adapter der
    # Ausgaben reichen ihn durch, statt die Kaskaden-Regeln nachzubilden.
    # ``None`` im neuen Eingang (``placements``) und bei Orten. Kein Teil von
    # Vergleich und Hash der Zeile.
    source: Optional[MetricConfig] = field(default=None, compare=False, repr=False)
    # #3101: Auswertung einer Orte-Kanalzeile (``max``/``min``/``sum``/``avg``);
    # ``metric_id`` ist dort die Katalog-ID, das Paar adressiert genau eine
    # Renderer-Zeile (Adapter ``compare_metric_ids.renderer_kennung``). ``None``
    # bei Trip-Zeilen und in Ausblick/Stundenverlauf.
    aggregation: Optional[str] = None


Rows = Optional[tuple[ChannelRow, ...]]


@dataclass(frozen=True)
class MailViewModel:
    """Je Kanal ein Tupel von Zeilen in Anzeigefolge; ``None`` = kein Filter
    (nur Orte ohne Grundauswahl und ohne Kanal-Liste). ``layout_channels``:
    Orte-Kanaele, deren Zeilen aus ``channel_layouts`` stammen.

    Ein Vokabular (#3101, ADR-0121 Nachtrag 4): alle Listen tragen Katalog-IDs;
    Orte-Kanalzeilen zusaetzlich ``aggregation`` (je Zeile genau eine
    Renderer-Zeile, Teilauswahl und Folge je Kanal bleiben erhalten). Die
    Renderer-Kennung entsteht erst im Adapter vor dem Renderer.

    ``outlook`` (Trip und Orte) und ``hourly`` (nur Orte): ``None`` =
    Renderer-Vorgabemenge, ``()`` =
    Block entfaellt. Orte-``hourly`` ist nie ``None`` (#3096: die Vorgabe "nie
    eingestellt" kommt als konkrete Liste aus ``compare_hourly_metric_ids``);
    Trip-``hourly`` ist im bisherigen Pfad immer ``None``. Die Trip-Mail liest
    ihre Spaltenfolge aus ``email`` (Adapter ``email.helpers.email_col_order``,
    #3096).

    #3122, neuer Eingang (``placements``): nirgends ``None``; ``outlook``/
    ``hourly`` sind ``()``, wenn der Block fuer den Briefing-Typ entfaellt
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


def resolve_channel_lists(
    display_config, surface: str, report_type: Optional[str] = None, *,
    enabled_reports: Optional[Sequence[str]] = None,
    hourly_enabled: Optional[bool] = None,
    report_config: object = None,
    outlook_enabled: Optional[bool] = None,
    with_rows: bool = False,
    ausblick: bool = True,
) -> MailViewModel:
    """Reine Funktion: ``display_config`` -> ``MailViewModel`` (ADR-0121).

    #3122: ``placements`` wird aus dem Roh-Dict UND aus dem geladenen Modell
    gelesen (die Trip-Renderer uebergeben das Modell). ``enabled_reports``
    (eingeschaltete Briefings, Vorbelegung des Ausblicks) und
    ``hourly_enabled`` (Orte; ``False`` = Stundenverlauf entfaellt) wirken im
    neuen Eingang. Im bisherigen Pfad entstehen ``rows``/``outlook_reports``
    nur mit ``with_rows=True`` (Umrechnung des Altbestands; dafuer auch
    ``report_config``/``outlook_enabled``); ohne Anforderung bleiben sie
    ``()`` und der Versandweg rechnet nichts um. ``ausblick=False``: der
    bisherige Pfad loest den Ausblick nicht auf (``outlook`` bleibt ``None``),
    fuer Leser, die nur Kanal-Zeilen brauchen (Alarm-Format, #3122)."""
    from services.placements import legacy_placements, read_placements

    if surface not in ("trip", "compare"):
        raise ValueError(f"unbekannte Flaeche {surface!r}")
    roh = display_config.get("placements") if isinstance(display_config, dict) else getattr(
        display_config, "placements", None)
    stored = read_placements(roh)
    ansicht = {"enabled_reports": enabled_reports, "hourly_enabled": hourly_enabled}
    if stored is not None:
        return placements_view(display_config, surface, report_type, stored, **ansicht)
    bisher = _abo_schalter(
        legacy_view(display_config, surface, report_type, ausblick=ausblick), surface,
        outlook_enabled=outlook_enabled, hourly_enabled=hourly_enabled)
    if not (with_rows or ALTBESTAND_UEBER_UMRECHNUNG):
        return bisher
    umgerechnet = read_placements(legacy_placements(
        display_config, surface, report_config=report_config,
        enabled_reports=enabled_reports, outlook_enabled=outlook_enabled)[0])
    neu = placements_view(display_config, surface, report_type, umgerechnet, **ansicht)
    if ALTBESTAND_UEBER_UMRECHNUNG:
        return neu
    return dataclasses.replace(bisher, rows=neu.rows, outlook_reports=neu.outlook_reports)


def _abo_schalter(view: MailViewModel, surface: str, *, outlook_enabled: Optional[bool],
                  hourly_enabled: Optional[bool]) -> MailViewModel:
    """#3122 B1b: Block-Schalter eines Orte-Abos im bisherigen Pfad -- ``False``
    heisst "Block entfaellt" (``()``); ``None`` (nicht angegeben) laesst die
    Listen unveraendert. Die Ausgaben lesen nur noch das View-Model."""
    if surface != "compare":
        return view
    aus = {k: () for k, an in (("outlook", outlook_enabled), ("hourly", hourly_enabled))
           if an is False}
    return dataclasses.replace(view, **aus) if aus else view


def legacy_view(
    display_config, surface: str, report_type: Optional[str] = None, *, ausblick: bool = True,
) -> MailViewModel:
    """Bisheriger Pfad aus den Altfeldern (ohne ``rows``/``outlook_reports``)."""
    if surface == "trip":
        return _trip_view(display_config, report_type or "evening", ausblick=ausblick)
    return _compare_view(display_config or {})


# ---------------------------------------------------------------------------
# Neuer Eingang: Tabelle "Was steht wo" (#3122)
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


def katalog_id(surface: str, metric_id: str) -> str:
    """Kennung einer View-Model-Zeile -> Katalog-ID. Seit #3101 tragen alle
    Listen beider Flaechen schon die Katalog-ID; ``surface`` bleibt fuer die
    Aufrufer der Umrechnung."""
    return metric_id


def vm_lists(vm: MailViewModel, surface: str, *, paare: bool = False) -> dict[str, list]:
    """Je Stelle ``[(kennung, format)]``; ``None`` des bisherigen Pfads als
    das, was die Ausgabe heute zeigt (Orte-Kanal: Standardfolge, Ausblick:
    feste Vorgabe). Einen Trip-Stundenverlauf gibt es nicht. ``paare=True``:
    Kennung = (Katalog-ID, Aggregation) -- unterscheidet die Zeilen einer
    Katalog-ID mit zwei Auswertungen (#3101, Alt/Neu-Vergleich)."""
    def schluessel(z):
        return (z.metric_id, z.aggregation) if paare else z.metric_id

    out: dict[str, list] = {}
    stellen = KANAELE + ("outlook",) + (() if surface == "trip" else ("hourly",))
    for stelle in stellen:
        zeilen = getattr(vm, stelle)
        if zeilen is None and stelle == "outlook":
            from output.renderers.email.helpers import OUTLOOK_FIXED_METRIC_IDS

            out[stelle] = [((m, None) if paare else m, None) for m in OUTLOOK_FIXED_METRIC_IDS]
        elif zeilen is None:
            out[stelle] = [(schluessel(z), None) for z in _orte_zeilen(
                (rid, None) for rid in _orte_standard())] if stelle in KANAELE else []
        else:
            out[stelle] = [(schluessel(z), z.format) for z in zeilen if z.enabled]
    return out


def legacy_lists(display_config, surface: str, report_type: str) -> dict[str, dict]:
    """Bisheriger Pfad je Stelle als ``{katalog_id: format}`` (erstes
    Vorkommen) -- Quelle der Umrechnung ``placements_from_legacy``."""
    listen = vm_lists(legacy_view(display_config, surface, report_type), surface)
    out: dict[str, dict] = {}
    for stelle, eintraege in listen.items():
        ziel: dict = {}
        for mid, fmt in eintraege:
            ziel.setdefault(katalog_id(surface, mid), fmt)
        out[stelle] = ziel
    return out


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


def _trip_view(display_config, report_type: str, *, ausblick: bool = True) -> MailViewModel:
    dc = _trip_model(display_config)
    kanaele = {
        ch: tuple(
            ChannelRow(mc.metric_id, True, _trip_format(mc), i, source=mc)
            for i, mc in enumerate(trip_channel_metrics(dc, ch, report_type))
        )
        for ch in KANAELE
    }
    eigene_premium = _models._cascade_source_for_channel(
        dc.per_report_layouts, dc.per_channel_layouts, "premium_sms", report_type,
    ) != "global"
    if not eigene_premium:
        kanaele["premium_sms"] = kanaele["sms"]
    if not ausblick:
        return MailViewModel(**kanaele)
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
    return _orte_zeilen(
        (rid, "simplified" if einfach else angegeben.get(rid)) for rid, einfach in rows)


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
            kanaele[ch] = None if ids is None else _orte_zeilen((rid, None) for rid in ids)
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

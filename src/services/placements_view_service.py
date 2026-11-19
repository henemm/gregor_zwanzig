"""Antwort der Tabelle "Was steht wo" fuer die Karte (Issue #3122, B2).

Spec ``docs/specs/modules/feat_3122_was_steht_wo.md`` Teil A Nr. 7/9, Teil B
Nr. 11/12; ADR-0124. Fuer Trip und Orte EIN Weg:

1. Abo DIESES Nutzers laden (``user_id`` aus dem Go-Proxy, nie ``"default"``).
2. Zeilen, Zustaende, Formen und ``outlook_reports`` aus dem Kanal-Listen-
   Resolver (``with_rows=True``: ein Abo ohne gespeicherte Tabelle zeigt das
   Ergebnis der Umrechnung ``placements_from_legacy``).
3. Beispielwerte, SMS-Beispiel und Marken aus DENSELBEN Renderer-Funktionen
   wie der Versand, mit dem festen Datensatz ``services.placements_beispiel``
   (kein Wetterabruf). Gelesen wird die fertige Ausgabe; nichts wird
   nachgebaut. Eine Stelle, die der Renderer heute nicht zeigt, bekommt
   keinen Beispielwert (``None``).

Texte: nur Metrik-Namen und Kuerzel-Bedeutungen aus dem Metrik-Katalog in der
Sprache des Nutzers; alles andere als Kennung (Frontend-Katalog).
"""
from __future__ import annotations

import copy
import dataclasses
import html as _html
import re
from dataclasses import dataclass, field
from typing import Optional

KINDS = ("route", "vergleich")
PASST_NICHT_MEHR = "passt_nicht_mehr"
NUR_TAGESWERT = "nur_tageswert"
WARNUNGEN = {"id": "amtliche_warnungen",
             "position": {"email": "first", "telegram": "first", "sms": "last"}}
_UNTERZEILE = {
    "trip": {"email": "stundentabelle", "telegram": "nachricht", "sms": "und_premium_sms",
             "outlook": "email_und_telegram"},
    "compare": {"email": "uebersicht", "telegram": "nachricht", "sms": "und_premium_sms",
                "hourly": "nur_email", "outlook": "email_und_telegram"},
}


#: Groesste Kennung in Bytes -- gleich ``store.MaxEntityIDBytes`` der Go-API
#: (Dateiname ``<id>.json`` fasst 255 Bytes). Laengere Kennungen benennen
#: keine Datei: "nicht gefunden" statt eines Dateisystemfehlers (500).
MAX_KENNUNG_BYTES = 255 - len(".json")


class AboNichtGefunden(LookupError):
    """Kein Abo dieser Art mit dieser Kennung im Bestand des Nutzers."""


def _kennung_gueltig(entity_id: str) -> bool:
    from app.loader import VALID_ENTITY_ID_RE

    return (len(entity_id.encode("utf-8", "replace")) <= MAX_KENNUNG_BYTES
            and bool(VALID_ENTITY_ID_RE.fullmatch(entity_id)))


@dataclass
class _Muster:
    """Gerenderte Beispiel-Ausgabe: ``beispiele[stelle][metric_id]`` =
    (Text, Ampelstufe|None), SMS-Text und Marken je Katalog-ID."""
    sms: Optional[str]
    beispiele: dict = field(default_factory=dict)
    sms_fehlt: set = field(default_factory=set)
    tageswert: set = field(default_factory=set)
    #: Orte: Rest-Zaehler ``+N`` je gezeigtem Ort (``None`` = keiner); Trip None.
    rest_zaehler: Optional[list] = None


@dataclass
class _Abo:
    surface: str
    display_config: object
    enabled_reports: tuple
    report_config: object = None
    hourly_enabled: Optional[bool] = None
    outlook_enabled: Optional[bool] = None
    warnungen: bool = True
    bloecke: dict = field(default_factory=dict)
    ort_anzahl: Optional[int] = None


def build_placements_view(kind: str, entity_id: str, user_id: str) -> dict:
    """GET-Antwort. ``ValueError`` bei unbekanntem ``kind``,
    ``AboNichtGefunden`` bei fremder/unbekannter Kennung oder anderer Art."""
    from i18n import resolve_user_lang

    if kind not in KINDS:
        raise ValueError(kind)
    if not _kennung_gueltig(entity_id):
        raise AboNichtGefunden(entity_id)
    lang = resolve_user_lang(user_id)
    if kind == "route":
        abo, muster_fn = _trip_abo(entity_id, user_id, lang)
    else:
        abo, muster_fn = _orte_abo(entity_id, user_id, lang)
    report_type = "morning" if abo.enabled_reports == ("morning",) else "evening"
    vm, placements, gespeichert = _tabelle_aufloesen(abo, report_type)
    muster = muster_fn(vm, report_type)
    # Beispielwerte und Marken gelten fuer das gerenderte Briefing; die Zeilen
    # der Tabelle fuer beide Briefing-Typen (#3154).
    tabelle = dataclasses.replace(vm, rows=_tabellen_zeilen(abo, placements))
    return _antwort(kind, abo, tabelle, placements, gespeichert, muster, lang)


def erstanlage_begleitfelder(kind: str, entity_id: str, user_id: str) -> dict:
    """#3154 F002 (Spec Nr. 8, AC-11): was das Speichern der Tabelle JETZT
    neben ``placements`` mitschreiben muss, damit die Ausgabe gleich bleibt.

    Die Aussage kommt allein aus der Umrechnung ``placements_from_legacy``:
    ``show_stability_off`` gilt nur fuer ein Abo ohne lesbare Tabelle (erstes
    Speichern); mit Tabelle ist sie immer ``False``. Der Go-PUT fragt das
    unter der Briefing-Sperre ab und schreibt ``report_config.show_stability
    = false`` im selben Schreibvorgang. Fehler wie ``build_placements_view``."""
    from services.placements import placements_from_legacy

    if kind not in KINDS:
        raise ValueError(kind)
    if not _kennung_gueltig(entity_id):
        raise AboNichtGefunden(entity_id)
    if kind == "route":
        abo, _muster = _trip_abo(entity_id, user_id, "de")
    else:
        abo, _muster = _orte_abo(entity_id, user_id, "de")
    umgerechnet = placements_from_legacy(
        abo.display_config, abo.surface, report_config=abo.report_config,
        enabled_reports=abo.enabled_reports, outlook_enabled=abo.outlook_enabled,
    )
    return {"show_stability_off": umgerechnet.show_stability_off}


# ---------------------------------------------------------------------------
# Aufloesung und Antwort
# ---------------------------------------------------------------------------

def _tabelle_aufloesen(abo: _Abo, report_type: str):
    from services.channel_list_resolver import resolve_channel_lists
    from services.placements import placements_from_legacy, read_placements

    dc = abo.display_config
    vm = resolve_channel_lists(
        dc, abo.surface, report_type, enabled_reports=abo.enabled_reports,
        hourly_enabled=abo.hourly_enabled, report_config=abo.report_config,
        outlook_enabled=abo.outlook_enabled, with_rows=True,
    )
    roh = dc.get("placements") if isinstance(dc, dict) else getattr(dc, "placements", None)
    if read_placements(roh) is not None:
        # Gespeicherter Stand wie gespeichert (nicht normalisiert): die
        # Oberflaeche schreibt ihn vollstaendig zurueck (PUT), unbekannte und
        # reservierte Schluessel (``premium_sms``, kuenftige Felder) gehen so
        # nicht verloren; unlesbare Eintraege wirken weiter nicht (Nr. 1).
        return vm, copy.deepcopy(roh), True
    umgerechnet = placements_from_legacy(
        dc, abo.surface, report_config=abo.report_config,
        enabled_reports=abo.enabled_reports, outlook_enabled=abo.outlook_enabled,
    )
    return vm, umgerechnet.placements, False


def _tabellen_grundauswahl(abo: _Abo) -> tuple[list[str], dict]:
    """Grundauswahl der Tabelle: Abend-Fassung, dahinter, was nur morgens
    gewaehlt ist -- dieselbe Menge wie die Umrechnung (``_legacy_rows``).
    ``morning_enabled``/``evening_enabled`` wirken im Versand je Briefing-Typ,
    die Tabelle hat dafuer keine Bedienung und zeigt jede Metrik (#3154)."""
    from services.channel_list_resolver import grundauswahl

    ids: list[str] = []
    eltern: dict = {}
    for rt in ("evening", "morning"):
        grund = grundauswahl(abo.display_config, abo.surface, rt)
        ids += [m for m in grund.ids if m not in ids]
        eltern = {**grund.parents, **eltern}
    return ids, eltern


def _tabellen_zeilen(abo: _Abo, placements: dict) -> tuple:
    """Zeilen der Tabelle aus demselben ``placements``, das die Antwort traegt."""
    from services.placements import read_placements, resolve_rows

    ids, eltern = _tabellen_grundauswahl(abo)
    gelesen = read_placements(placements)
    gespeichert = gelesen.rows if gelesen is not None else ()
    return resolve_rows(gespeichert, ids, abo.surface, parents=eltern)


def _antwort(kind, abo: _Abo, vm, placements, gespeichert, muster: _Muster, lang) -> dict:
    from app.metric_catalog import get_metric

    eltern = _tabellen_grundauswahl(abo)[1]
    zeilen = [{
        "metric_id": r.metric_id, "name": get_metric(r.metric_id).label(lang),
        "position": r.position, "parent": eltern.get(r.metric_id),
        "cells": {stelle: _zelle(r.metric_id, stelle, c, muster) for stelle, c in r.cells},
    } for r in vm.rows]
    max_laenge = _sms_max_laenge(abo.surface)
    return {
        "kind": kind, "lang": lang, "stored": gespeichert, "placements": placements,
        "location_count": abo.ort_anzahl,
        "columns": _spalten(abo, vm),
        "fixed_rows": [WARNUNGEN] if abo.warnungen else [],
        "rows": zeilen,
        "sms_example": None if muster.sms is None else {
            "text": muster.sms, "length": len(muster.sms), "max_length": max_laenge,
            "overflow": _ueberlauf(muster.rest_zaehler)},
        "outlook_reports": list(vm.outlook_reports),
        "blocks": {**abo.bloecke, "outlook": {
            rt: rt in vm.outlook_reports for rt in ("morning", "evening")}},
        "legend": _legende(zeilen, abo.surface, vm, lang),
        "example_version": _beispiel_version(),
    }


def _ueberlauf(rest_zaehler: Optional[list]) -> Optional[dict]:
    """Orte: ``{locations: <Zahl der Orte mit +N>, per_location: [N|None]}``
    je in der SMS gezeigtem Ort (SMS-Folge); Trip: ``None``."""
    if rest_zaehler is None:
        return None
    return {"locations": sum(1 for n in rest_zaehler if n), "per_location": rest_zaehler}


def _beispiel_version() -> int:
    from services.placements_beispiel import VERSION

    return VERSION


def _sms_max_laenge(surface: str) -> int:
    """Grenze, mit der der Versandweg der Flaeche die SMS kuerzt (SMS und
    Premium-SMS senden denselben Text). Trip: ``format_sms(max_length=...)``
    -- der Trip-Renderer uebergibt dort den Vorgabewert 160 ausdruecklich.
    Orte: ``render_compare_sms`` kuerzt auf ``CHANNEL_LIMITS["sms"]["max_chars"]``
    (verkettungssicheres GSM-7-Budget, #1362)."""
    if surface == "trip":
        import inspect

        from output.renderers.sms_trip import SMSTripFormatter

        return inspect.signature(SMSTripFormatter.format_sms).parameters["max_length"].default
    from output.renderers.channel_layout import CHANNEL_LIMITS

    return CHANNEL_LIMITS["sms"]["max_chars"]


def _zelle(metric_id: str, stelle: str, cell, muster: _Muster) -> dict:
    text, ampel = (None, None)
    if cell.state == "on":
        text, ampel = muster.beispiele.get(stelle, {}).get(metric_id, (None, None))
    mark = None
    if cell.state == "on" and stelle == "sms" and metric_id in muster.sms_fehlt:
        mark = PASST_NICHT_MEHR
    if cell.state == "on" and stelle == "telegram" and metric_id in muster.tageswert:
        mark = NUR_TAGESWERT
    return {"state": cell.state, "format": cell.format, "reason": cell.reason,
            "example": text, "ampel": ampel, "mark": mark}


def _spalten(abo: _Abo, vm) -> list[dict]:
    kurzstil = abo.bloecke.get("telegram_style") == "kurzform"
    block_aus = {"hourly": abo.hourly_enabled is False, "outlook": not vm.outlook_reports}
    return [{
        "stelle": stelle, "subtitle": unterzeile,
        "block_off": block_aus.get(stelle, False),
        "rests": "kurzstil" if stelle == "telegram" and kurzstil else None,
    } for stelle, unterzeile in _UNTERZEILE[abo.surface].items()]


def _sms_kuerzel(metric_id: str, surface: str, vm) -> list[tuple[str, str]]:
    """(Kuerzel, Katalog-ID der Bedeutung) genau so, wie der SMS-Renderer der
    Flaeche sie fuer diese Zeile ausgibt. Trip: Symboltabellen des Trip-SMS-
    Renderers (Doppelpunkt gehoert zur Grammatik, nicht zum Kuerzel). Orte:
    Kuerzel-Kennung je Auswertung der Zeile in der SMS-Liste (Temperatur
    -> Tageshoechst ``D`` / Tagestiefst ``L``), wie ``_sms_metric_cell``."""
    if surface == "trip":
        from output.renderers.sms_trip import SMS_MULTI_SYMBOLS_BY_METRIC, SMS_SYMBOL_BY_METRIC

        symbole = SMS_MULTI_SYMBOLS_BY_METRIC.get(metric_id) or tuple(
            s for s in (SMS_SYMBOL_BY_METRIC.get(metric_id),) if s)
        return [(s.rstrip(":"), metric_id) for s in symbole]
    from app.metric_catalog import kurzform_kuerzel
    from output.renderers.comparison import _RENDERER_TO_CATALOG_METRIC_ID
    from services.report_config_resolver import orte_renderer_ids

    in_sms = set(_orte_sms_liste(orte_renderer_ids(vm.sms)))
    quellen = [_RENDERER_TO_CATALOG_METRIC_ID.get(rid) for rid in _renderer_ids(metric_id)
               if rid in in_sms]
    return [(kurzform_kuerzel(q), q) for q in quellen if q and kurzform_kuerzel(q)]


def _legende(zeilen: list[dict], surface: str, vm, lang: str) -> dict:
    """Spec Nr. 12: die Kuerzel, die der SMS-Renderer fuer die Metriken mit
    SMS-Haken sendet, je mit der Bedeutung aus dem Katalog in der Sprache des
    Nutzers (``None``, wo der Katalog keine fuehrt -- kein erfundener Text);
    dazu die festen Eintraege als Token mit Kennung."""
    from app.metric_catalog import kuerzel_bedeutung
    from output.tokens.builder import UNAVAILABLE_SYMBOL
    from output.tokens.hazard_symbols import (
        HAZARD_SMS_SYMBOLS, LEVEL_LETTERS, alert_entry_token_parts,
    )

    metriken = []
    for z in zeilen:
        if z["cells"]["sms"]["state"] != "on":
            continue
        for kuerzel, quelle in dict.fromkeys(_sms_kuerzel(z["metric_id"], surface, vm)):
            metriken.append({"metric_id": z["metric_id"], "kuerzel": kuerzel,
                             "meaning": kuerzel_bedeutung(quelle, kuerzel, lang)})
    warnung = "!" + "".join(alert_entry_token_parts(
        HAZARD_SMS_SYMBOLS["thunderstorm"], LEVEL_LETTERS[4], 14))
    lawine = "".join(alert_entry_token_parts(HAZARD_SMS_SYMBOLS["avalanche_bulletin"], "4", None))
    fest = [("@14", "zeit_ab_gelb"), (warnung, "amtliche_warnung"),
            (LEVEL_LETTERS[2], "stufe_gelb"), (LEVEL_LETTERS[3], "stufe_orange"),
            (LEVEL_LETTERS[4], "stufe_rot"), (HAZARD_SMS_SYMBOLS["wind_gust"], "warnung_wind"),
            (HAZARD_SMS_SYMBOLS["rain"], "warnung_starkregen"), (lawine, "lawinenstufe"),
            (UNAVAILABLE_SYMBOL, "warnquelle_nicht_erreichbar")]
    return {"metrics": metriken, "fixed": [{"token": t, "key": k} for t, k in fest]}


# ---------------------------------------------------------------------------
# Trip
# ---------------------------------------------------------------------------

def _trip_abo(entity_id: str, user_id: str, lang: str):
    from app.loader import get_data_root, load_trip
    from app.models import UnifiedWeatherDisplayConfig, slot_aktiv
    from services.amtliche_warnungen_schalter import amtliche_warnungen_an_trip

    trip = load_trip(entity_id, data_dir=get_data_root(), user_id=user_id)
    if trip is None:
        raise AboNichtGefunden(entity_id)
    dc = trip.display_config or UnifiedWeatherDisplayConfig(trip_id=trip.id)
    rc = trip.report_config
    abo = _Abo(
        surface="trip", display_config=dc, report_config=rc,
        enabled_reports=tuple(rt for rt in ("morning", "evening") if slot_aktiv(rc, rt)),
        warnungen=amtliche_warnungen_an_trip(trip),
        bloecke={
            "show_stage_stats": getattr(rc, "show_stage_stats", True),
            "show_yesterday_comparison": getattr(rc, "show_yesterday_comparison", True),
            "show_night_block": dc.show_night_block,
            "email_format": getattr(rc, "email_format", "full"),
            "telegram_style": getattr(rc, "telegram_style", "rich"),
        },
    )
    return abo, lambda vm, rt: _trip_muster(trip, dc, vm, rt, lang)


def _trip_muster(trip, dc, vm, report_type: str, lang: str) -> _Muster:
    from app.ampel import resolve_ampel
    from output.renderers.email.outlook import build_outlook_row
    from output.renderers.trip_report import TripReportFormatter
    from services import placements_beispiel as pb
    from services.channel_list_resolver import resolve_channel_lists
    from services.weather_metrics import summarize_points

    ampel = resolve_ampel(trip)
    # Ausblick-Zeilen einmal aufloesen, wie der Renderer es tut (#3122 B1b);
    # Zellen und Spaltenkoepfe lesen dieselben Zeilen.
    outlook_rows = resolve_channel_lists(dc, "trip", report_type).outlook
    trend = [build_outlook_row(summarize_points(p), p, wd, pb.ZONE, trip_display_config=dc,
                               outlook_rows=outlook_rows, report_type=report_type,
                               context="route", ampel=ampel, lang=lang)
             for wd, p in pb.ausblick_tage()]
    stage_name = (trip.stages[0].name if trip.stages else "") or trip.name
    bericht = TripReportFormatter().format_email(
        pb.trip_segmente(), trip.name, report_type, display_config=dc, multi_day_trend=trend,
        report_config=trip.report_config, trip=trip, tz=pb.ZONE, stage_name=stage_name, lang=lang,
    )
    ids = [r.metric_id for r in vm.rows]
    sms_werte = _trip_sms_werte(_trip_sms_rumpf(bericht.sms_text, stage_name), ids)
    return _Muster(
        sms=bericht.sms_text,
        beispiele={
            "email": _html_stundentabelle(bericht.email_html, ids),
            "telegram": _telegram_kurzuebersicht(bericht.telegram_bubbles, ids, lang),
            "sms": {m: (t, None) for m, t in sms_werte.items()},
            "outlook": _trip_ausblick(trend, outlook_rows, ids),
        },
        sms_fehlt=_trip_sms_fehlt(vm, sms_werte),
        tageswert=_trip_nur_tageswert(dc, vm, report_type),
    )


def _trip_sms_symbole() -> dict[str, str]:
    """SMS-Symbol -> Katalog-ID aus den Tabellen des SMS-Renderers."""
    from output.renderers.sms_trip import SMS_MULTI_SYMBOLS_BY_METRIC, SMS_SYMBOL_BY_METRIC

    symbole = {sym: mid for mid, sym in SMS_SYMBOL_BY_METRIC.items()}
    symbole.update({sym: mid for mid, syms in SMS_MULTI_SYMBOLS_BY_METRIC.items() for sym in syms})
    return symbole


def _trip_sms_rumpf(sms: str, etappe: str) -> str:
    """Token-Teil der Trip-SMS hinter dem Kopf ``<Etappe>: ``. Der Kopf wird
    mit denselben zwei Funktionen gebildet wie im Versand (``format_sms`` ->
    ``build_token_line``) und als Ganzes abgetrennt -- nie am ersten ``: ``,
    denn der Etappenname darf selbst ``: `` oder kuerzelartigen Text tragen.
    Passt der Kopf nicht (Renderer geaendert), gilt der letzte ``: `` als
    Trenner: Token enthalten kein ``: ``."""
    from output.renderers.sms_trip import _sms_stage_prefix
    from output.tokens.builder import _sanitize_stage_name

    kopf = f"{_sanitize_stage_name(_sms_stage_prefix(etappe))}: "
    if sms.startswith(kopf):
        return sms[len(kopf):]
    return sms.rpartition(": ")[2]


def _trip_sms_werte(rumpf: str, ids: list[str]) -> dict[str, str]:
    """Katalog-ID -> Token der SMS (laengstes passendes Symbol); ``rumpf`` ist
    der Token-Teil ohne Kopf. Eine Eltern-Metrik ohne eigenes Symbol
    (Temperatur) traegt die Token ihrer abgeleiteten Groessen; der Warnblock
    (``!``) gehoert zu keiner Metrik. Ein Tagestiefstwert, der mit dem
    Hoechstwert zu EINEM Bereichs-Token verschmolzen ist (``D14/18``,
    ``FD12/16``; Trenner ``/`` kommt im Format sonst nicht vor), zeigt dieses
    gemeinsame Token."""
    from app.loader import _DERIVED_METRIC_RULES

    symbole = _trip_sms_symbole()
    eltern = {kind: elter for kind, elter, _agg in _DERIVED_METRIC_RULES}
    werte: dict[str, list[str]] = {}
    for token in rumpf.split(" "):
        treffer = [s for s in symbole if token.startswith(s)]
        if not token or token.startswith("!") or not treffer:
            continue
        mid = symbole[max(treffer, key=len)]
        for ziel in (mid, eltern.get(mid)):
            if ziel in ids:
                werte.setdefault(ziel, []).append(token)
    for tief in (m for m in ids if m.endswith("_day_low") and m not in werte):
        bereich = [t for t in werte.get(f"{tief[:-len('low')]}high", []) if "/" in t]
        if bereich:
            werte[tief] = bereich
    return {mid: " ".join(dict.fromkeys(t)) for mid, t in werte.items()}


def _trip_sms_fehlt(vm, sms_werte: dict) -> set[str]:
    """Die SMS kuerzt von hinten (sms_format.md §6): fehlen ab einer Stelle
    alle folgenden SMS-Metriken mit eigenem Kuerzel, passen sie nicht mehr."""
    from app.loader import _DERIVED_METRIC_RULES

    mit_kuerzel = set(_trip_sms_symbole().values()) | {
        elter for _kind, elter, _agg in _DERIVED_METRIC_RULES}
    sms_an = [r.metric_id for r in vm.rows
              if r.cell("sms").state == "on" and r.metric_id in mit_kuerzel]
    letzte = max((i for i, m in enumerate(sms_an) if m in sms_werte), default=-1)
    return {m for m in sms_an[letzte + 1:] if m not in sms_werte}


def _trip_nur_tageswert(dc, vm, report_type: str) -> set[str]:
    """Telegram-Metriken ohne Spalte in der Stundentabelle -- dieselbe
    Spaltenberechnung wie der Telegram-Renderer (``render_for_channel`` auf
    der Telegram-Liste, Grenze ``CHANNEL_LIMITS``)."""
    from output.renderers.channel_layout import VISIBILITY_GATE_IDS, render_for_channel
    from output.renderers.email.helpers import should_merge_wind_dir, telegram_metric_configs

    tg = dataclasses.replace(dc, metrics=telegram_metric_configs(vm.telegram, dc),
                             per_channel_layouts=None, per_report_layouts=None)
    spalten = set(render_for_channel("telegram", tg, report_type).table_columns)
    ausgenommen = set(VISIBILITY_GATE_IDS)
    if should_merge_wind_dir(tg):
        ausgenommen.add("wind_direction")
    return {mc.metric_id for mc in tg.metrics
            if mc.metric_id not in spalten and mc.metric_id not in ausgenommen}


def _trip_ausblick(trend: list, outlook_rows, ids: list[str]) -> dict:
    """Erste Zeile des Ausblicks, Zellen nach den Spalten des Renderers
    (dieselben View-Model-Zeilen ueber ``outlook_auswahl``, #3122 B1b)."""
    from output.renderers.compare_outlook_metric_ids import outlook_columns
    from output.renderers.email.helpers import outlook_auswahl

    if not trend:
        return {}
    spalten = outlook_columns(*outlook_auswahl(outlook_rows))
    out: dict = {}
    for spalte, text in zip(spalten, trend[0].get("cells") or []):
        if spalte["metric_id"] in ids:
            out.setdefault(spalte["metric_id"], (text, None))
    return out


# ---------------------------------------------------------------------------
# Gerenderte Ausgabe lesen (HTML-Tabellen, Telegram-Kurzuebersicht)
# ---------------------------------------------------------------------------

_TABELLE_RE = re.compile(r"<table\b[^>]*>.*?</table>", re.S)
_TH_RE = re.compile(r"<th\b[^>]*>(.*?)</th>", re.S)
_TR_RE = re.compile(r"<tr\b[^>]*>(.*?)</tr>", re.S)
_TD_RE = re.compile(r"<td\b[^>]*>(.*?)</td>", re.S)


def _text(fragment: str) -> str:
    return _html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", fragment))).strip()


def _ampel(fragment: str) -> Optional[str]:
    """Ampelstufe eines HTML-Ampelpunkts (Farbe aus der Renderer-Tabelle)."""
    from output.renderers.email.helpers import _AMPEL_DOT_COLORS

    if "border-radius:50%" not in fragment:
        return None
    for stufe, (fuellung, _ring) in _AMPEL_DOT_COLORS.items():
        if f"background:{fuellung}" in fragment:
            return stufe
    return None


def _tabellen(html: str) -> list[tuple[list[str], list[list[str]]]]:
    """(Kopfzeilen-Texte, Zeilen als td-Fragmente) jeder innersten Tabelle."""
    out = []
    for m in _TABELLE_RE.finditer(html):
        block = m.group(0)
        kopf = [_text(t) for t in _TH_RE.findall(block)]
        zeilen = [_TD_RE.findall(tr) for tr in _TR_RE.findall(block)]
        out.append((kopf, [z for z in zeilen if z]))
    return out


def _spalten_beispiel(kopf, zeilen, label_zu_id: dict) -> dict:
    """Erste Datenzeile einer Tabelle mit Spaltenkopf je Metrik."""
    if not zeilen:
        return {}
    erste = next((z for z in zeilen if len(z) == len(kopf)), None)
    if erste is None:
        return {}
    out = {}
    for label, fragment in zip(kopf, erste):
        mid = label_zu_id.get(label)
        if mid is not None and mid not in out:
            out[mid] = (_text(fragment) or None, _ampel(fragment))
    return out


def _col_labels(ids: list[str]) -> dict[str, str]:
    from app.metric_catalog import get_metric

    return {get_metric(m).col_label: m for m in reversed(ids)}


def _html_stundentabelle(html: str, ids: list[str]) -> dict:
    """Trip: erste Zeile der ersten Etappen-Stundentabelle der HTML-Mail."""
    m = next((m for m in _TABELLE_RE.finditer(html)
              if 'data-table="resp"' in m.group(0)[:200] and "<thead>" in m.group(0)), None)
    if m is None:
        return {}
    kopf, zeilen = _tabellen(m.group(0))[0]
    return _spalten_beispiel(kopf, zeilen, _col_labels(ids))


def _telegram_kurzuebersicht(bubbles: list[str], ids: list[str], lang: str) -> dict:
    """Trip: Zeile der Kurzuebersicht je Metrik (``<Kuerzel> <Wert>``)."""
    from app.metric_catalog import get_metric
    from i18n import t

    kopf = t("telegram.kopf.zusammenfassung", lang)
    blase = next((b for b in bubbles if b.split("\n", 1)[0] == kopf), "")
    zeilen = [_html.unescape(z) for z in blase.split("\n")[1:]]
    out = {}
    for mid in ids:
        praefix = get_metric(mid).compact_label + " "
        zeile = next((z for z in zeilen if z.startswith(praefix)), None)
        if zeile is not None:
            out[mid] = (zeile, None)
    return out


# ---------------------------------------------------------------------------
# Orte
# ---------------------------------------------------------------------------

def _orte_abo(entity_id: str, user_id: str, lang: str):
    from app.loader import compare_preset_to_dict, get_data_root, load_compare_presets
    from services.amtliche_warnungen_schalter import amtliche_warnungen_an_preset
    from services.compare_slot_scheduler import resolve_preset_slots

    treffer = next((p for p in load_compare_presets(user_id=user_id, data_root=get_data_root())
                    if p.id == entity_id), None)
    if treffer is None:
        raise AboNichtGefunden(entity_id)
    preset = compare_preset_to_dict(treffer)
    slots = resolve_preset_slots(preset)
    dc = preset.get("display_config") or {}
    orte = _orte_des_abos(preset, user_id)
    abo = _Abo(
        surface="compare", display_config=dc,
        enabled_reports=tuple(rt for rt, an in (("morning", slots.morning_enabled),
                                                ("evening", slots.evening_enabled)) if an),
        hourly_enabled=preset.get("hourly_enabled", True) is not False,
        outlook_enabled=preset.get("outlook_enabled"),
        warnungen=amtliche_warnungen_an_preset(preset), ort_anzahl=len(orte),
        bloecke={"hourly": preset.get("hourly_enabled", True) is not False,
                 "telegram_style": dc.get("telegram_style", "rich") or "rich"},
    )
    return abo, lambda vm, rt: _orte_muster(preset, orte, vm, lang)


def _orte_des_abos(preset: dict, user_id: str) -> list:
    from app.loader import load_all_locations
    from services.compare_briefing_aufbau import order_locations_by_ids

    return order_locations_by_ids(load_all_locations(user_id), preset.get("location_ids") or [])


def _orte_muster(preset: dict, orte: list, vm, lang: str) -> _Muster:
    """Versandweg ab dem Wetterlauf (``compare_briefing_aufbau``) mit dem
    Beispiel-Ergebnis statt des Abrufs."""
    if not orte:
        return _Muster(sms=None)
    from app.ampel import profile_for_template, resolve_ampel, template_id_for
    from services import compare_briefing_aufbau as aufbau
    from services import placements_beispiel as pb
    from services.report_config_resolver import resolve_compare_render_options

    kontext = {"preset": preset, "result": pb.orte_ergebnis(orte),
               "profile": profile_for_template(template_id_for(preset)),
               "opts": resolve_compare_render_options(preset), "name": preset.get("name", ""),
               "target_date": pb.TAG}
    email_html, _text_mail = aufbau.compare_email_rendern(kontext, lang=lang)
    sms, telegram = aufbau.compare_kanaltexte_rendern(kontext, lang=lang)
    ids = [r.metric_id for r in vm.rows]
    sms_werte = _orte_sms_werte(sms, kontext, ids)
    return _Muster(
        sms=sms,
        beispiele={
            **_orte_mail_beispiele(email_html, kontext, ids, lang, resolve_ampel(preset)),
            "telegram": _orte_telegram_werte(telegram, ids, lang),
            "sms": {m: (t, None) for m, t in sms_werte.items() if t},
        },
        sms_fehlt={m for m, t in sms_werte.items() if t is None},
        rest_zaehler=_orte_rest_zaehler(sms, kontext),
    )


def _orte_sms_formen(ort, opts) -> list[str]:
    """Formen eines Ortsteils der SMS, von "alle Zellen" (Index 0) bis "keine"
    (Index d = d Zellen verdraengt, Ortsteil endet auf ``+d``) -- dieselbe
    Funktion und dieselben Angaben wie ``render_compare_sms``."""
    from output.renderers.comparison import _sms_location_variants

    return _sms_location_variants(
        ort, opts.enabled_metrics_by_channel["sms"], opts.unresolved_by_channel.get("sms", 0),
        opts.metric_formats("sms"))


def _orte_rest_zaehler(sms: str, kontext: dict) -> list:
    """Je Ort, dessen Teil in der SMS steht (Renderer-Folge), der Rest-Zaehler
    ``+N`` -- abgelesen: die Form des Renderers, die als ganzer Ortsteil in
    der SMS steht, nennt ihn (``None`` = alle Zellen stehen). Ein entfallener
    Ort (``+k Orte``) oder ein hart gekuerzter steht nicht darin."""
    from output.renderers.email.compare_html import location_render_order

    out = []
    for ort in location_render_order(kontext["result"].locations):
        formen = _orte_sms_formen(ort, kontext["opts"])
        d = next((d for d, form in enumerate(formen)
                  if re.search(r"(?:: |; )" + re.escape(form) + r"(?=;|\s|$)", sms)), None)
        if d is not None:
            out.append(d or None)
    return out


def _renderer_ids(metric_id: str) -> list[str]:
    from output.renderers.compare_metric_ids import _renderer_ids_for_kennung

    return list(_renderer_ids_for_kennung(metric_id))


def _orte_sms_liste(liste) -> list[str]:
    """Renderer-Kennungen, die die Orte-SMS fuehrt: die Kanal-Liste, bei
    ``None`` ("nie eingestellt", kein Filter) die Vorgabefolge, die der
    SMS-Renderer selbst dann nimmt (``_sms_location_variants``)."""
    from output.renderers.comparison import _NIE_EINGESTELLT_IDS

    return list(_NIE_EINGESTELLT_IDS if liste is None else liste)


def _orte_sms_werte(sms: str, kontext: dict, ids: list[str]) -> dict:
    """Katalog-ID -> Zellen des ersten Orts in der SMS; ``None`` = die Metrik
    hat Zellen, keine davon steht in der SMS (passt nicht mehr). Metriken der
    SMS-Spalte, die der Renderer nicht zeigt, fehlen.

    Welche Zellen stehen, sagt der Renderer selbst: ``_sms_location_variants``
    liefert fuer den ersten Ort alle Formen von "alle Zellen" bis "keine"
    (Kuerzung vom Listenende); die zellenreichste Form, die in der SMS steht,
    ist die gesendete. Der Ortsname wird dabei nie zerlegt -- er darf ``: ``
    oder ``; `` enthalten."""
    from output.renderers.comparison import _sms_metric_cell
    from output.renderers.email.compare_html import location_render_order

    opts = kontext["opts"]
    ort = location_render_order(kontext["result"].locations)[0]
    sms_liste = list(dict.fromkeys(_orte_sms_liste(opts.enabled_metrics_by_channel["sms"])))
    formen = opts.metric_formats("sms") or {}
    varianten = _orte_sms_formen(ort, opts)
    verdraengt = next((d for d, form in enumerate(varianten) if form in sms), len(varianten) - 1)
    zellen = [(rid, zelle) for rid in sms_liste
              if (zelle := _sms_metric_cell(ort, rid, bool(formen.get(rid))))]
    gezeigt = dict(zellen[:max(len(zellen) - verdraengt, 0)])
    alle = dict(zellen)
    out: dict = {}
    for mid in ids:
        rids = [rid for rid in _renderer_ids(mid) if rid in alle]
        if rids:
            out[mid] = " ".join(gezeigt[rid] for rid in rids if rid in gezeigt) or None
    return out


def _orte_telegram_werte(telegram: str, ids: list[str], lang: str) -> dict:
    """Katalog-ID -> ``Label Wert``-Zellen des ersten Orts im Telegram. Nur
    die eingerueckten Zeilen eines Ortsblocks tragen Zellen; Kopf und
    Ortsnamen (nicht eingerueckt) sind Freitext und werden nie gedeutet."""
    from i18n import t
    from output.renderers.comparison import _PLAIN_ROWS_BY_ID

    teile = [p.strip() for zeile in telegram.split("\n") if zeile.startswith("   ")
             for p in zeile.split(" · ")]
    out = {}
    for mid in ids:
        gefunden = []
        for rid in _renderer_ids(mid):
            # Renderer-Kennung ohne Klartext-Zeile hat im Telegram keine Zelle.
            label_key = (_PLAIN_ROWS_BY_ID.get(rid) or (None, None))[1]
            praefix = f"{t(label_key, lang)} " if label_key else None
            treffer = next((p for p in teile if praefix and p.startswith(praefix)), None)
            if treffer:
                gefunden.append(treffer)
        if gefunden:
            out[mid] = (" · ".join(gefunden), None)
    return out


def _uebersicht_zelle(ziel: dict, mid: str, fragment: str) -> None:
    """Zelle des ersten Orts; eine Metrik mit mehreren Uebersichtszeilen
    (Temperatur Hoechst/Tiefst) traegt ihre Werte mit ``/`` verbunden."""
    text, ampel = _text(fragment) or None, _ampel(fragment)
    if mid not in ziel:
        ziel[mid] = (text, ampel)
        return
    teile = [t for t in (ziel[mid][0], text) if t]
    ziel[mid] = (" / ".join(teile) or None, ziel[mid][1] or ampel)


def _orte_mail_beispiele(html: str, kontext: dict, ids: list[str], lang: str, ampel: dict) -> dict:
    """Uebersicht (Zeile je Metrik, erster Ort), Stundenverlauf und Ausblick
    (Spaltenkopf je Metrik) aus der HTML-Mail; ``ampel`` nur fuer die
    Zeilenbeschriftung der Uebersicht (dieselbe Ableitung wie der Renderer)."""
    from i18n import t
    from output.renderers.email.compare_html import _visible_metrics

    zeilen_labels = {
        m["label"]: m["metric_id"] for m in _visible_metrics(
            kontext["opts"].enabled_metrics_by_channel["email"], lang,
            ampel=ampel)
        if m.get("metric_id") in ids
    }
    tag = t("mail.ausblick.spalte_tag", lang)
    email, hourly, outlook = {}, {}, {}
    for kopf, zeilen in _tabellen(html):
        for zeile in zeilen:
            mid = zeilen_labels.get(_text(zeile[0])) if len(zeile) > 1 else None
            if mid is not None:
                _uebersicht_zelle(email, mid, zeile[1])
        if kopf and kopf[0] == tag and not outlook:
            outlook = _spalten_beispiel(kopf, zeilen, _col_labels(ids))
        elif len(kopf) > 1 and not hourly and kopf[0] != tag and _col_labels(ids).keys() & set(kopf):
            hourly = _spalten_beispiel(kopf, zeilen, _col_labels(ids))
    return {"email": email, "hourly": hourly, "outlook": outlook}

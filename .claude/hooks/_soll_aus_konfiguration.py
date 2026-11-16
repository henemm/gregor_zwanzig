#!/usr/bin/env python3
"""Soll einer Mail aus der gespeicherten Konfiguration (Issue #3047, Spec §6).

Leitet aus dem ROHEN gespeicherten JSON (Trip wie die Go-API es liefert bzw.
Orte-Preset) ab, welche Spalten/Zeilen die zugestellte Mail in welcher Folge
tragen muss: Auswahl, Reihenfolge, Darstellung je Liste, Ein/Aus,
Ortsreihenfolge, Zusatzbloecke. Gelesen werden nur die rohe Datei und das
statische Register (``col_label``/``label`` aus ``app.metric_catalog``, die
Compare-Katalogtabelle, die festen Alias-/Ausschlussmengen) -- NIE ein
``resolve_*`` des Produkts (sonst prueft der Validator das Produkt gegen sich
selbst, Spiegel-Test-Verbot CLAUDE.md).

Die Regeln sind das dokumentierte Produktverhalten:

* Trip-Tabellen: E-Mail-Liste der Kaskade (``channel_layouts_per_report`` >
  ``channel_layouts`` > ``metrics``), Kanal-Ebenen gegen die Grundauswahl
  geschnitten (ADR-0050), sortiert nach ``bucket`` dann ``order`` (#1575).
  Altbestand ohne ``bucket``/``order``: Array-Folge (Annahme, nicht Gegenstand).
  Totalschnitt (nicht leere Kanal-Liste ganz ausserhalb der Grundauswahl) ->
  volle Grundauswahl (AC-10, wie ``_clip_to_global_maximum``); eine bewusst
  leere bzw. ganz ausgeschaltete Liste bleibt leer.
* Trip-Altbestand Fall A (#1394, #3068): ``metrics`` fehlt oder ist ``[]``
  -> Grundauswahl = Register-Standardsatz (``trip_default_rank``, Register-
  Folge, ohne Ableitungen), wie der Loader ihn liest. Bewusst leer (Eintraege
  vorhanden, alle ``enabled: false``): Stundentabellen ohne Metrikspalten,
  der Ausblick entfaellt (Konzept "alle Zeilen abgewaehlt").
* Ausblick: Drei-Werte-Semantik (ADR-0037/0055): ``[]`` = Block aus, nie
  eingestellt = GANZE Grundauswahl in der eingestellten Reihenfolge (AC-4,
  nicht Katalogfolge), sonst Schnitt mit der Grundauswahl, leerer Schnitt =
  Rueckfall auf die volle Grundauswahl (#1848 A3). Orte ohne Grundauswahl
  (``active_metrics`` fehlt) zeigen die sieben festen Spalten, im HTML wie im
  Klartext (AC-21).
* Orte: Vergleichstabelle = ``channel_layouts.email`` (Folge, ``enabled``,
  #3039) vor ``channel_active_metrics.email``, je geschnitten mit
  ``active_metrics`` (#1703 S8), Stundenverlauf = ``hourly_metrics``
  geschnitten mit der Grundauswahl (``_orte_stunden``, Konzept §5.8),
  ``active_metrics: []`` = bewusst leer (keine Metrikzeilen, Stundenverlauf
  und Ausblick entfallen, #3047 N2), Einfach-Zeilen laut
  ``channel_layouts.email`` (``uebersicht_einfach``, N4),
  Ortsfolge = ``location_ids`` (#1359), Namen aus ``--orte``/Huelle, sonst
  ``orte_unpruefbar`` (nie still uebersprungen).
* Darstellung Roh/Einfach je Spalte (Trip, ``formen_*``, Spec §2 Punkt 3).

``None`` an einer Liste heisst "keine Aussage", der Validator prueft sie dann
nicht.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from app.metric_catalog import _METRICS, OUTLOOK_FRIENDLY_CAPABLE, aggregation_label  # noqa: E402
from i18n import t  # noqa: E402
from output.renderers.compare_hourly_metric_ids import (  # noqa: E402
    FRONTEND_TO_HOURLY_METRIC_ID, HOURLY_DEFAULT_METRIC_IDS, HOURLY_EXCLUDED_METRIC_IDS,
    HOURLY_MERGE_ONLY_METRIC_IDS,
)
from output.renderers.compare_metric_catalog import COMPARE_METRIC_CATALOG  # noqa: E402
from output.renderers.email.helpers import (  # noqa: E402
    _AMPEL_CAPABLE_METRIC_IDS, _PILL_CATALOG_ORDER, NO_HOURLY_COLUMN_METRIC_IDS,
)

_REG = {m.id: m for m in _METRICS}
_BUCKET_RANG = {"primary": 0, "secondary": 1}
_REPORTS = ("morning", "evening")
#: Die sieben festen Ausblick-Spalten (Orte-Altbestand), Temperatur als Spanne.
_FEST = ("temperature", "precipitation", "rain_probability", "wind", "gust", "thunder")
#: Trip-Anlege-Standard des Registers (``trip_default_rank``) in Register-Folge
#: -- Grundauswahl eines Trip-Altbestands Fall A (#1394, #3068).
_TRIP_STANDARD = tuple(m.id for m in sorted(
    (m for m in _METRICS if m.trip_default_rank is not None), key=lambda m: m.trip_default_rank))
#: Roh zeigt bereits ein Wort (Gewitter-Stufe, Niederschlagsart), keine Zahl.
_ROH_WORT = frozenset({"thunder", "precip_type"})
#: Zellformen der Darstellung (Spec §2 Punkt 3): Roh = Zahl, Einfach = Symbol/Wort oder Ampelpunkt.
ZAHL, WORT, AMPEL = "zahl", "wort", "ampel"
#: Alle waehlbaren Spaltenkuerzel -- erkennt im Klartext auch eine Spalte zu viel.
#: Das Kompaktformat ist reines ASCII ohne Gradzeichen (``compact._ASCII_MAP``:
#: ``0°Line`` -> ``0Line``); diese Form ist dieselbe Spalte.
_ASCII_KUERZEL = {m.col_label.replace("°", ""): m.col_label for m in _METRICS
                  if m.selectable and "°" in m.col_label}
ALLE_KUERZEL = tuple(dict.fromkeys(
    [m.col_label for m in _METRICS if m.selectable and m.id not in NO_HOURLY_COLUMN_METRIC_IDS]
    + list(_ASCII_KUERZEL)))


#: Breite des Etappennamen-Felds im Trip-Klartext-Ausblick (``f"{name:<26} "``).
_NAMENSFELD = 26


def ausblick_kuerzel(zeile: str, mit_name: bool = False) -> list[tuple[int, str]]:
    """(Position, Kuerzel) der Spalten einer Ausblick-Zeile in Textfolge.

    #3047 F001: vor den Werten stehen der Wochentag (``f"{weekday:<3} "``, EN
    "Sun" ist kein Spaltenkuerzel "Sun") und im Trip-Klartext das 26 Zeichen
    breite Etappennamen-Feld ("Wind Pass", "Sun Valley"). Beides wird vor der
    Suche abgetrennt; ein ueberlanger Name ist bis Feldende sicher abgetrennt."""
    tag = re.match(r"\S+ ", zeile)
    ab = (tag.end() if tag else 0) + (_NAMENSFELD if mit_name else 0)
    return sorted((m.start(), k) for k in ALLE_KUERZEL
                  for m in re.finditer(r"(?<!\S)" + re.escape(k) + r" (?=\S)", zeile)
                  if m.start() >= ab)


def _waehlbar(mid: object) -> bool:
    return isinstance(mid, str) and mid in _REG and _REG[mid].selectable


def _ausblickfaehig(mid: object) -> bool:
    """Hat eine Tagesauswertung im Compare-Katalog (statische Tabelle)."""
    return _waehlbar(mid) and any(e["metric_id"] == mid for e in COMPARE_METRIC_CATALOG)


def _eintraege(liste: object) -> list[dict]:
    return [{"metric_id": e} if isinstance(e, str) else e
            for e in (liste if isinstance(liste, list) else []) if isinstance(e, (str, dict))]


def _an(eintrag: dict, report: str) -> bool:
    eigen = eintrag.get(f"{report}_enabled")
    return eigen if isinstance(eigen, bool) else bool(eintrag.get("enabled", True))


def _sortiert(eintraege: list[dict]) -> list[dict]:
    return sorted(eintraege, key=lambda e: (_BUCKET_RANG.get(e.get("bucket", "primary"), 2),
                                            e.get("order", 0) or 0))


def _modus(e: dict) -> str:
    modus = e.get("format_mode")
    if modus in (None, "scale", "symbol"):
        return _REG[e["metric_id"]].default_format_mode if e.get("use_friendly_format", True) else "raw"
    return modus


# --------------------------------------------------------------------------- #
# Trip
# --------------------------------------------------------------------------- #
def _trip_email_liste(dc: dict, report: str) -> list[dict]:
    """E-Mail-Liste der Kaskade, geschnitten und sortiert (ADR-0050, #1575)."""
    grund = [e for e in _eintraege(dc.get("metrics")) if _waehlbar(e.get("metric_id"))]
    erlaubt = {e["metric_id"] for e in grund if _an(e, report)}
    pro_report = dc.get("channel_layouts_per_report") or {}
    kanal = dc.get("channel_layouts") or {}
    if isinstance(pro_report.get(report), dict) and "email" in pro_report[report]:
        ebene = _eintraege(pro_report[report]["email"])
    elif isinstance(kanal, dict) and "email" in kanal:
        ebene = _eintraege(kanal["email"])
    else:
        return _sortiert([e for e in grund if _an(e, report)])
    ebene = [e for e in ebene if _waehlbar(e.get("metric_id")) and _an(e, report)]
    geschnitten = [e for e in ebene if e["metric_id"] in erlaubt] if grund else ebene
    if ebene and not geschnitten:
        # #3047 AC-10 (N1): eine nicht leere Liste ganz ausserhalb der
        # Grundauswahl (Totalschnitt) -> die volle Grundauswahl. Eine bewusst
        # leere (bzw. ganz ausgeschaltete) Liste bleibt leer.
        return _sortiert([e for e in grund if _an(e, report)])
    return _sortiert(geschnitten)


def _wind_verschmolzen(liste: list[dict]) -> bool:
    """Windrichtung Einfach neben Wind: keine eigene WDir-Spalte, die Richtung
    steht in der Wind-Zelle (#435, ``_should_merge_wind_dir``)."""
    return any(e["metric_id"] == "wind" for e in liste) and any(
        e["metric_id"] == "wind_direction" and _modus(e) == "scale" for e in liste)


def _trip_stundenspalten(liste: list[dict]) -> list[str]:
    ids = [e["metric_id"] for e in liste]
    merge = _wind_verschmolzen(liste)
    spalten: list[str] = []
    for mid in ids:
        if mid in NO_HOURLY_COLUMN_METRIC_IDS or (mid == "wind_direction" and merge):
            continue
        if _REG[mid].col_label not in spalten:
            spalten.append(_REG[mid].col_label)
    return spalten


def _ausblick(gespeichert: object, grundauswahl: list[str] | None) -> list[str] | None:
    """Drei-Werte-Regel; ``None`` = feste Spalten."""
    kennungen = None
    if isinstance(gespeichert, list):
        kennungen = []
        for e in gespeichert:
            mid = e.get("metric_id") if isinstance(e, dict) else e
            if isinstance(mid, str) and mid not in kennungen:
                kennungen.append(mid)
        if kennungen:
            kennungen = [m for m in kennungen if _ausblickfaehig(m)] or None
    if kennungen == [] or grundauswahl == []:
        # #3047 N2: bewusst leere Grundauswahl (bzw. keine ausblickfaehige
        # Groesse darin) -> der Ausblick entfaellt, Trip und Orte gleich.
        return []
    if grundauswahl is None:
        return kennungen
    if kennungen is None:
        return list(grundauswahl)
    return [m for m in kennungen if m in grundauswahl] or list(grundauswahl)


def _formen_stunden(liste: list[dict]) -> dict[str, dict]:
    """Spalte -> erlaubte Zellformen je Teil (``None`` = nicht pruefbar).
    Gewollte Ausnahmen (Spec §2 Punkt 3): Ampel-faehige Groessen zeigen
    Einfach im HTML als Ampelpunkt, im Klartext als Zahl (#814); Gewitter zeigt
    roh schon das Stufenwort (Klartext in beiden Formen gleich); die
    verschmolzene Windrichtung hat keine eigene Spalte (#435)."""
    formen: dict[str, dict] = {}
    for e in liste:
        mid = e["metric_id"]
        if mid == "precip_type" or mid in NO_HOURLY_COLUMN_METRIC_IDS:
            continue
        if mid in _AMPEL_CAPABLE_METRIC_IDS:
            html = (AMPEL,) if e.get("use_friendly_format", True) else (ZAHL,)
            klartext: tuple | None = (ZAHL,)
        elif mid == "thunder":
            html, klartext = ((AMPEL,) if _modus(e) != "raw" else (ZAHL, WORT)), None
        else:
            einfach = _modus(e) != "raw"
            html, klartext = ((WORT, AMPEL), (WORT,)) if einfach else ((ZAHL,), (ZAHL,))
        formen.setdefault(_REG[mid].col_label, {"HTML": html, "Klartext": klartext})
    return formen


def _formen_ausblick(ids: list[str], einfach: dict) -> dict[str, dict]:
    """Ausblick: Einfach nur fuer ``OUTLOOK_FRIENDLY_CAPABLE`` (Visibility,
    Temperatur ohne Einfach-Form, #814 AC-5); Gewitter zeigt roh schon das
    Stufenwort und wird nicht geprueft."""
    formen: dict[str, dict] = {}
    for m in ids:
        if m in _ROH_WORT:
            continue
        an = m in OUTLOOK_FRIENDLY_CAPABLE and einfach.get(m)
        formen[_REG[m].col_label] = ({"HTML": (WORT, AMPEL), "Klartext": (WORT,)} if an
                                     else {"HTML": (ZAHL,), "Klartext": (ZAHL,)})
    return formen


def _ausblick_spalten(ids: list[str] | None, formate: object) -> dict:
    if ids is None:
        temp = _REG["temperature"].col_label
        html = [f"{temp} {aggregation_label(a, 'de')}" for a in ("min", "max")]
        return {"fest": True, "html": html + [_REG[m].col_label for m in _FEST[1:]],
                "klartext": [_REG[m].col_label for m in _FEST], "darstellung": {}, "formen": {}}
    labels = [_REG[m].col_label for m in ids]
    einfach = {m: bool(v) for m, v in (formate or {}).items()} if isinstance(formate, dict) else {}
    return {"fest": False, "html": labels, "klartext": labels,
            "darstellung": {m: "einfach" if einfach.get(m) else "roh" for m in ids},
            "formen": _formen_ausblick(ids, einfach)}


def _trip_display_config(trip: dict) -> dict:
    """Rohe ``display_config``; Fall A (``metrics`` fehlt oder ``[]``) traegt
    den Register-Standardsatz mit ``order``/``bucket`` -- wie der Loader."""
    dc = (trip.get("display_config") if "display_config" in trip else trip) or {}
    if dc.get("metrics"):
        return dc
    return {**dc, "metrics": [{"metric_id": m, "enabled": True, "bucket": "primary", "order": i}
                              for i, m in enumerate(_TRIP_STANDARD)]}


def trip_soll(trip: dict, report: str = "evening") -> dict:
    """Soll eines Trip-Briefings fuer ``report`` (morning/evening)."""
    dc = _trip_display_config(trip)
    rc = trip.get("report_config") or {}
    liste = _trip_email_liste(dc, report)
    grund = _sortiert([e for e in _eintraege(dc.get("metrics"))
                       if _waehlbar(e.get("metric_id")) and _an(e, report)])
    grundauswahl = list(dict.fromkeys(
        e["metric_id"] for e in grund if _ausblickfaehig(e["metric_id"])))
    # Bewusst leer: alle Zeilen abgewaehlt -> der Ausblick entfaellt.
    ids = _ausblick(dc.get("outlook_metrics"), grundauswahl) if grundauswahl else []
    trend_reports = rc.get("multi_day_trend_reports", dc.get("multi_day_trend_reports", ["evening"]))
    return {
        "kontext": "trip", "report": report,
        "stunden": _trip_stundenspalten(liste),
        "darstellung_stunden": {e["metric_id"]: _modus(e) for e in liste},
        "formen_stunden": _formen_stunden(liste),
        # #3047 F004: verschmolzene Windrichtung -> jede Wind-Zelle traegt die Richtung.
        "wind_richtung": _wind_verschmolzen(liste),
        "nacht": bool(dc.get("show_night_block", True)),
        "ausblick_an": ids != [] and rc.get("show_outlook", True) is not False
        and report in (trend_reports or []),
        "ausblick": None if ids == [] else _ausblick_spalten(ids, dc.get("outlook_metric_formats")),
        "email_format": rc.get("email_format", "full"),
        # #3047 N5/F008b: Metriken-Ueberblick nur, wenn eine Groesse der
        # E-Mail-Liste dieses Berichts eine Kachel traegt. Der Renderer
        # kollabiert ``dc.metrics`` vor dem Ueberblick auf die E-Mail-Liste
        # (trip_report.py, ``get_metrics_for_channel``), ``build_metrics_summary_pills``
        # filtert auf die Weisse Liste ``_PILL_CATALOG_ORDER``; ohne Kachel
        # entfaellt die Ueberschrift (html.py/plain.py/compact.py: ``if pills``).
        # Datenabhaengig fehlende Kacheln (keine Werte) sind nicht ableitbar.
        "ueberblick": any(e["metric_id"] in _PILL_CATALOG_ORDER for e in liste),
        "zusatz": {k: rc.get(k, True) for k in ("show_stage_stats", "show_yesterday_comparison")},
    }


# --------------------------------------------------------------------------- #
# Orte
# --------------------------------------------------------------------------- #
_KATALOG = {e["key"]: e for e in COMPARE_METRIC_CATALOG}


def _uebersicht_paare(auswahl: object) -> list[tuple[str, str]] | None:
    """Gespeicherte Auswahl -> (metric_id, aggregation), reihenfolgetreu, ohne Doppel."""
    if not isinstance(auswahl, list):
        return None
    paare: list[tuple[str, str]] = []
    for e in auswahl:
        eintrag = _KATALOG.get(e) if isinstance(e, str) else next(
            (k for k in COMPARE_METRIC_CATALOG if isinstance(e, dict)
             and k["metric_id"] == e.get("metric_id") and k["aggregation"] == e.get("aggregation")), None)
        if eintrag and _waehlbar(eintrag["metric_id"]):
            paar = (eintrag["metric_id"], eintrag["aggregation"])
            if paar not in paare:
                paare.append(paar)
    return paare


def _uebersicht_labels(paare: list[tuple[str, str]], lang: str) -> list[str]:
    basis = [_REG[m].label(lang) for m, _a in paare]
    return [f"{b} {aggregation_label(a, lang)}" if basis.count(b) > 1 else b
            for b, (_m, a) in zip(basis, paare)]


def _orte_layout(eintraege: list, grund: list[tuple[str, str]] | None) -> list[tuple[str, str]]:
    """``channel_layouts.email`` (#3039, ADR-0119): Listenfolge, ``enabled: false``
    fehlt; eine Kennung traegt alle ihre Zeilen der Compare-Katalogtabelle, nur
    die der Grundauswahl; Zeilen der Grundauswahl ohne jeden Eintrag (auch
    keinen ausgeschalteten) folgen hinten (#3039 AC-14)."""
    erfasst: set[tuple[str, str]] = set()
    paare: list[tuple[str, str]] = []
    for e in eintraege:
        if not isinstance(e, dict) or not _waehlbar(e.get("metric_id")):
            continue
        zeilen = [(k["metric_id"], k["aggregation"]) for k in COMPARE_METRIC_CATALOG
                  if k["metric_id"] == e["metric_id"]]
        erfasst.update(zeilen)
        if e.get("enabled") is not False:
            paare += [p for p in zeilen if (grund is None or p in grund) and p not in paare]
    return paare + [p for p in grund or [] if p not in erfasst and p not in paare]


def _orte_uebersicht(dc: dict) -> list[tuple[str, str]] | None:
    grund = _uebersicht_paare(dc.get("active_metrics"))
    layouts = dc.get("channel_layouts")
    if isinstance(layouts, dict) and isinstance(layouts.get("email"), list):
        return _orte_layout(layouts["email"], grund)
    kanal = dc.get("channel_active_metrics")
    if not isinstance(kanal, dict) or "email" not in kanal:
        return grund
    eigen = _uebersicht_paare(kanal.get("email"))
    if eigen is None:
        return grund
    if grund is None:
        return eigen
    # #3047 AC-10: nicht leere Liste ganz ausserhalb -> volle Grundauswahl.
    return [p for p in eigen if p in grund] or (list(grund) if eigen else [])


def _einfach_eintrag(e: dict) -> bool:
    """Einfach laut ``channel_layouts``-Eintrag (``format``/``format_mode``
    vor ``use_friendly_format``); wirkt nur bei mehr als einer Darstellung."""
    fmt = next((e[k] for k in ("format", "format_mode") if e.get(k) in ("raw", "simplified")), None)
    einfach = fmt == "simplified" if fmt else e.get("use_friendly_format") is True
    return einfach and len(_REG[e["metric_id"]].format_modes) > 1


def _orte_einfach(dc: dict, paare: list[tuple[str, str]] | None, lang: str) -> list[str]:
    """#3047 N4: Zeilen der Vergleichstabelle, die laut ``channel_layouts.email``
    Einfach zeigen (Ampelpunkt/Wort statt Zahl) -- dort ist ein fehlendes
    Zahlformat kein FORMAT-Fehler."""
    layouts = dc.get("channel_layouts")
    if not paare or not isinstance(layouts, dict) or not isinstance(layouts.get("email"), list):
        return []
    # erster eingeschaltete Eintrag je Kennung entscheidet (``rows.setdefault``)
    erste: dict[str, bool] = {}
    for e in layouts["email"]:
        if isinstance(e, dict) and _waehlbar(e.get("metric_id")) and e.get("enabled") is not False:
            erste.setdefault(e["metric_id"], _einfach_eintrag(e))
    return [label for label, (m, _a) in zip(_uebersicht_labels(paare, lang), paare) if erste.get(m)]


def _stuendlich(mid: object) -> bool:
    return _waehlbar(mid) and mid not in HOURLY_EXCLUDED_METRIC_IDS


def _orte_stunden(dc: dict, grund: list[tuple[str, str]] | None) -> list[str]:
    """Stundenverlauf (Konzept §5.8 "Jede Liste nimmt nur aus den Metriken
    oben"): gespeichert -> Schnitt mit der Grundauswahl in gespeicherter Folge;
    leerer Schnitt einer nicht leeren Liste -> Vorgabemenge geschnitten mit der
    Grundauswahl, sonst deren stuendlich waehlbare Groessen. Nie eingestellt ->
    Grundauswahl, soweit stuendlich verfuegbar, in deren Folge; ohne
    Grundauswahl die Vorgabemenge."""
    basis = None if grund is None else [m for m in dict.fromkeys(m for m, _a in grund)
                                        if _stuendlich(m)]
    roh = dc.get("hourly_metrics")
    if not isinstance(roh, list):
        # nie eingestellt: Grundauswahl ``[]`` -> leer (#3047 N2); ohne
        # Grundauswahl bzw. ohne eigene Stundenspalte darin die Vorgabemenge.
        eigen = [m for m in basis or [] if m not in HOURLY_MERGE_ONLY_METRIC_IDS]
        ids = [] if grund == [] else (basis if eigen else list(HOURLY_DEFAULT_METRIC_IDS))
    else:
        ids = list(dict.fromkeys(m for m in (FRONTEND_TO_HOURLY_METRIC_ID.get(e, e)
                                             for e in roh if isinstance(e, str)) if _stuendlich(m)))
        if basis is not None and ids:
            ids = ([m for m in ids if m in basis]
                   or [m for m in HOURLY_DEFAULT_METRIC_IDS if m in basis] or basis)
    return [_REG[m].col_label for m in ids if m not in HOURLY_MERGE_ONLY_METRIC_IDS]


def orte_soll(preset: dict, lang: str = "de", ortsnamen: dict | None = None) -> dict:
    """Soll eines Orts-Vergleichs; ``ortsnamen`` (Kennung -> Name) fuer die Ortsfolge."""
    dc = preset.get("display_config") or {}
    paare = _orte_uebersicht(dc)
    grundpaare = _uebersicht_paare(dc.get("active_metrics"))
    grundauswahl = None if grundpaare is None else list(dict.fromkeys(
        m for m, _a in grundpaare if _ausblickfaehig(m)))
    # #3047 N2: ``active_metrics: []`` = bewusst leere Grundauswahl (wie Trip
    # alle ``enabled: false``) -> Ausblick und Stundenverlauf entfallen.
    ids = _ausblick(dc.get("outlook_metrics"), grundauswahl)
    stunden = _orte_stunden(dc, grundpaare)
    stunden_an = preset.get("hourly_enabled", True) is not False and stunden != []
    ids_orte = [i for i in preset.get("location_ids") or [] if isinstance(i, str)]
    return {
        "kontext": "orte",
        "uebersicht": None if paare is None else
        [t("vergleich.zeile.amtliche_warnungen", lang)] + _uebersicht_labels(paare, lang),
        "uebersicht_einfach": _orte_einfach(dc, paare, lang),
        "stunden_an": stunden_an,
        "stunden": stunden if stunden_an else [],
        "ausblick_an": preset.get("outlook_enabled", True) is not False and ids != [],
        "ausblick": None if ids == [] else _ausblick_spalten(ids, dc.get("outlook_metric_formats")),
        **_ortsfolge(ids_orte, ortsnamen),
    }


def _ortsfolge(ids_orte: list[str], ortsnamen: dict | None) -> dict:
    """Ortsfolge = ``location_ids`` (#1359) als Namen. Ohne aufloesbare Namen
    wird sie NICHT still uebersprungen (Nachpruefung #3047 Punkt 4), sondern
    als ``orte_unpruefbar`` gemeldet. Eine Kennung ohne Ort fehlt auch in der
    Mail (geloeschter Ort, ``order_locations_by_ids``) und faellt heraus."""
    if not ids_orte:
        return {"orte": []}
    if not ortsnamen:
        return {"orte": None, "orte_unpruefbar": (
            "das Preset traegt nur Orts-Kennungen, keine Namen -- --orte <Orts-Verzeichnis "
            "data/users/<id>/locations bzw. JSON von /api/locations> oder Huelle "
            "{\"preset\": ..., \"orte\": {\"<id>\": \"<Name>\"}} angeben")}
    namen = [ortsnamen[i] for i in ids_orte if i in ortsnamen]
    if not namen:
        return {"orte": None, "orte_unpruefbar": (
            f"keine der Kennungen {ids_orte} steht in den Ortsnamen ({sorted(ortsnamen)})")}
    return {"orte": namen}


# --------------------------------------------------------------------------- #
# Einstieg
# --------------------------------------------------------------------------- #
def soll_aus_daten(daten: dict, lang: str = "de", ortsnamen: dict | None = None) -> dict:
    """Erkennt Trip bzw. Orte am Inhalt. Orte duerfen als Huelle
    ``{"preset": {...}, "orte": {"<id>": "<Name>"}}`` kommen (Ortsfolge) oder
    als rohes Preset mit ``ortsnamen`` (aus ``lade_ortsnamen``, ``--orte``)."""
    if isinstance(daten.get("preset"), dict):
        return orte_soll(daten["preset"], lang, {**(daten.get("orte") or {}), **(ortsnamen or {})})
    if "location_ids" in daten or daten.get("kind") == "vergleich":
        return orte_soll(daten, lang, ortsnamen)
    return {"kontext": "trip", "je_report": {r: trip_soll(daten, r) for r in _REPORTS}}


def lade_ortsnamen(pfad: str | Path) -> dict[str, str]:
    """Kennung -> Name aus dem Orts-Verzeichnis des Nutzers
    (``data/users/<id>/locations/<id>.json``), aus der Orts-Liste der API
    (``GET /api/locations``: Liste von Objekten mit ``id``/``name``) oder aus
    einer Zuordnung ``{"<id>": "<Name>"}``."""
    pfad = Path(pfad)
    if pfad.is_dir():
        eintraege = [json.loads(f.read_text(encoding="utf-8")) for f in sorted(pfad.glob("*.json"))]
    else:
        daten = json.loads(pfad.read_text(encoding="utf-8"))
        if isinstance(daten, dict) and all(isinstance(v, str) for v in daten.values()):
            return dict(daten)
        eintraege = daten if isinstance(daten, list) else []
    return {e["id"]: e["name"] for e in eintraege if isinstance(e, dict)
            and isinstance(e.get("id"), str) and isinstance(e.get("name"), str)}


def lade_soll(pfad: str | Path, lang: str = "de") -> dict:
    return soll_aus_daten(json.loads(Path(pfad).read_text(encoding="utf-8")), lang)


def abweichung(ist: list[str], soll: list[str]) -> str | None:
    """Beschreibung der ersten Abweichung mit Spaltennamen (``None`` = gleich)."""
    ist = [_ASCII_KUERZEL.get(x, x) for x in ist]
    if ist == soll:
        return None
    fehlt = [s for s in soll if s not in ist]
    zuviel = [x for x in ist if x not in soll]
    teile = []
    if fehlt:
        teile.append("Spalte fehlt: " + ", ".join(f"'{s}'" for s in fehlt))
    if zuviel:
        teile.append("Spalte zu viel: " + ", ".join(f"'{x}'" for x in zuviel))
    if not teile:
        i = next(i for i, (a, b) in enumerate(zip(ist, soll)) if a != b)
        teile.append(f"Reihenfolge: an Position {i + 1} steht '{ist[i]}' statt '{soll[i]}'")
    return f"{'; '.join(teile)} (ist {ist}, soll {soll})"

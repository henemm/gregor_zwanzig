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
* 3-Tages-Ausblick je Briefing (#3155, Spec B4 AC-12): OB der Ausblick im
  Morgen- bzw. Abend-Briefing steht, entscheidet EINE Regel des Produkts --
  bewusst die echten Funktionen aus ``services.placements`` (Tabelle:
  ``resolve_outlook_reports`` + ``outlook_applies``; sonst
  ``_legacy_outlook_reports`` samt Orte-Anlage-Marke), nicht die Altfelder
  ``show_outlook``/``multi_day_trend_reports`` (``ausblick_briefings``). Die
  Spec verlangt diese eine Stelle ausdruecklich (Ausnahme vom resolve-Verbot
  oben); nachgebaut waere sie eine zweite Regel, die still auseinanderlaeuft.
  Gegenstand der Pruefung bleibt die zugestellte Mail (Block da/nicht da,
  Blockname).

``None`` an einer Liste heisst "keine Aussage", der Validator prueft sie dann
nicht.
"""
from __future__ import annotations

import json
import re
import sys
from html import unescape
from pathlib import Path

_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from app.metric_catalog import (  # noqa: E402
    _METRICS, AMPEL_METRIC_IDS, OUTLOOK_FRIENDLY_CAPABLE, aggregation_label,
)
from i18n import t  # noqa: E402
from output.renderers.compare_hourly_metric_ids import (  # noqa: E402
    FRONTEND_TO_HOURLY_METRIC_ID, HOURLY_DEFAULT_METRIC_IDS, HOURLY_EXCLUDED_METRIC_IDS,
    HOURLY_MERGE_ONLY_METRIC_IDS,
)
from output.renderers.channel_layout import _PRIMARY_SLOTS, METRIC_PRIORITY  # noqa: E402
from output.renderers.compare_metric_catalog import COMPARE_METRIC_CATALOG  # noqa: E402
from output.renderers.email.helpers import (  # noqa: E402
    _PILL_CATALOG_ORDER, NO_HOURLY_COLUMN_METRIC_IDS,
)
from app.ampel_templates import AMPEL_TEMPLATES, DEFAULT_TEMPLATE  # noqa: E402

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


def _kuerzel_ab(zeile: str, ab: int) -> list[tuple[int, str]]:
    return sorted((m.start(), k) for k in ALLE_KUERZEL
                  for m in re.finditer(r"(?<!\S)" + re.escape(k) + r" (?=\S)", zeile)
                  if m.start() >= ab)


def _namensende(zeile: str, ab: int, namen: tuple | list) -> int:
    """Ende des Etappennamen-Felds ab ``ab`` (Zeilenanfang hinter dem Wochentag).

    Der Renderer kuerzt den Namen nicht (``f"{name:<26} "``, outlook.py): ein
    Name ueber 26 Zeichen schiebt die Werte nach rechts (#3047 F2). Bekannte
    Namen (``stages[].name`` der Konfiguration) werden exakt abgetrennt, der
    laengste passende zuerst. Sonst entscheidet die Zeilenstruktur: die Werte
    stehen als ``<Kuerzel> <Wert>`` mit ZWEI Leerzeichen dazwischen, der Name
    endet mit EINEM Leerzeichen -- die erste Spalte ist das letzte Kuerzel vor
    dem ersten Doppel-Leerzeichen hinter dem Feldende (ein Kuerzel im
    Namensrest liegt immer davor)."""
    feld = ab + _NAMENSFELD
    for name in sorted({n for n in namen if isinstance(n, str) and n}, key=len, reverse=True):
        if zeile.startswith(name + " ", ab):
            return max(feld, ab + len(name))
    doppel = zeile.find("  ", feld)
    erste = [p for p, _k in _kuerzel_ab(zeile[:len(zeile) if doppel < 0 else doppel], feld)]
    return erste[-1] if erste else feld


def ausblick_kuerzel(zeile: str, mit_name: bool = False, namen: tuple | list = ()) -> list[tuple[int, str]]:
    """(Position, Kuerzel) der Spalten einer Ausblick-Zeile in Textfolge.

    #3047 F001: vor den Werten stehen der Wochentag (``f"{weekday:<3} "``, EN
    "Sun" ist kein Spaltenkuerzel "Sun") und im Trip-Klartext das 26 Zeichen
    breite Etappennamen-Feld ("Wind Pass", "Sun Valley"). Beides wird vor der
    Suche abgetrennt, ein ueberlanger Name ueber ``_namensende`` (F2)."""
    tag = re.match(r"\S+ ", zeile)
    ab = tag.end() if tag else 0
    return _kuerzel_ab(zeile, _namensende(zeile, ab, namen) if mit_name else ab)


def ausblick_zellen(zeilen: list[str], mit_name: bool = False, namen: tuple | list = ()) -> list[list]:
    """Ausblick-Zeilen (Klartext/Kompakt) -> je Zeile [(Kuerzel, Wert), ...]."""
    ausblick = []
    for zeile in zeilen:
        treffer = ausblick_kuerzel(zeile, mit_name, namen)
        grenzen = [p for p, _k in treffer] + [len(zeile)]
        ausblick.append([(k, zeile[p + len(k):grenzen[j + 1]].strip().split("  ")[0])
                         for j, (p, k) in enumerate(treffer)])
    return ausblick


# --------------------------------------------------------------------------- #
# Darstellung Roh/Einfach je Zelle (Spec §2 Punkt 3) -- Trip und Orte (#3047 A3c)
# --------------------------------------------------------------------------- #
_TAG_RE = re.compile(r"<[^>]+>")
_AMPELPUNKT_RE = re.compile(r"<span[^>]*border-radius:\s*50%", re.IGNORECASE)
_FORM_NAME = {ZAHL: "Zahl (Roh)", WORT: "Symbol/Wort (Einfach)", AMPEL: "Ampelpunkt (Einfach)"}


def zelltext(zelle: str, html: bool) -> str:
    """Sichtbarer Text einer Zelle; HTML ohne Tags, Entitaeten aufgeloest (#3047 F1)."""
    return unescape(_TAG_RE.sub("", zelle)).strip() if html else zelle.strip()


def zellform(zelle: str, html: bool) -> str | None:
    """Form einer Zelle: ``ampel`` / ``zahl`` / ``wort``; leer bzw. "–" = None."""
    if html and _AMPELPUNKT_RE.search(zelle):
        return AMPEL
    text = zelltext(zelle, html)
    if not text or text in ("–", "-", "—"):
        return None
    return ZAHL if re.search(r"\d", text) else WORT


def darstellung_meldungen(was: str, tabellen: list, formen: dict, teil: str, html: bool) -> list[str]:
    """``tabellen``: je Tabelle eine Liste Zeilen aus (Spalte, Zelle). Meldet je
    Tabelle und Spalte die erste Zelle in falscher Form, mit Spaltennamen."""
    meldungen = []
    for i, zeilen in enumerate(tabellen):
        gemeldet: set[str] = set()
        for spalte, zelle in (paar for zeile in zeilen for paar in zeile):
            erlaubt = (formen.get(spalte) or {}).get(teil)
            form = zellform(zelle, html)
            if erlaubt is None or form is None or form in erlaubt or spalte in gemeldet:
                continue
            gemeldet.add(spalte)
            soll = " oder ".join(_FORM_NAME[f] for f in erlaubt)
            meldungen.append(f"SOLL: Darstellung {was} ({teil}) {i + 1}: Spalte '{spalte}' soll "
                             f"{soll} zeigen, zeigt {_FORM_NAME[form]} ('{zelltext(zelle, html)}')")
    return meldungen


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
    Gewollte Ausnahmen (Spec §2 Punkt 3): Ampel-faehige Groessen
    (``AMPEL_METRIC_IDS``: Wind, Boeen, Regen, Regen-W.) zeigen im HTML die
    Ampel (``use_friendly_format``, #814), im Klartext folgt die Form dem
    ``format_mode``: Einfach = Wortstufe, Roh = Zahl (#435, #3156); Gewitter zeigt
    roh schon das Stufenwort (Klartext in beiden Formen gleich); die
    verschmolzene Windrichtung hat keine eigene Spalte (#435)."""
    formen: dict[str, dict] = {}
    for e in liste:
        mid = e["metric_id"]
        if mid == "precip_type" or mid in NO_HOURLY_COLUMN_METRIC_IDS:
            continue
        if mid in AMPEL_METRIC_IDS:
            html = (AMPEL,) if e.get("use_friendly_format", True) else (ZAHL,)
            # #3156: Klartext wie ``helpers.fmt_val`` (Einfach -> Wortstufe).
            klartext: tuple | None = (WORT,) if _modus(e) == "simplified" else (ZAHL,)
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


def _altformat_folge(metrics: list) -> list[dict]:
    """#3047 B-L6 (Tech-Lead-Entscheidung Runde 7): Eintraege ohne ``bucket``
    und ``order`` (Altformat: Zeichenkette bzw. Objekt ohne beides) erhalten
    die Register-Prioritaet wie im Loader (``auto_distribute``: die aktiven nach
    ``METRIC_PRIORITY`` absteigend, bei Gleichstand Array-Folge, die ersten
    fuenf ``primary`` 0..4, der Rest ``secondary``); inaktive ``secondary``/0."""
    eintraege = _eintraege(metrics)
    if all("bucket" in e or "order" in e for e in eintraege):
        return eintraege
    aktiv = [e["metric_id"] for e in eintraege if isinstance(e.get("metric_id"), str)
             and e.get("enabled", True)]
    rang = sorted(enumerate(aktiv), key=lambda p: (-METRIC_PRIORITY.get(p[1], 0), p[0]))
    platz = {}
    for i, (_pos, mid) in enumerate(rang):
        platz.setdefault(mid, ("primary", i) if i < _PRIMARY_SLOTS else ("secondary", i - _PRIMARY_SLOTS))
    return [e if ("bucket" in e or "order" in e) else
            {**e, "bucket": platz.get(e.get("metric_id"), ("secondary", 0))[0],
             "order": platz.get(e.get("metric_id"), ("secondary", 0))[1]} for e in eintraege]


def _trip_display_config(trip: dict) -> dict:
    """Rohe ``display_config``; Fall A (``metrics`` fehlt oder ``[]``) traegt
    den Register-Standardsatz mit ``order``/``bucket`` -- wie der Loader;
    Altformat ohne ``order`` die Register-Prioritaet (B-L6)."""
    dc = (trip.get("display_config") if "display_config" in trip else trip) or {}
    if dc.get("metrics"):
        return {**dc, "metrics": _altformat_folge(dc["metrics"])}
    return {**dc, "metrics": [{"metric_id": m, "enabled": True, "bucket": "primary", "order": i}
                              for i, m in enumerate(_TRIP_STANDARD)]}


# --------------------------------------------------------------------------- #
# 3-Tages-Ausblick je Briefing (#3155, Spec B4 Nr. 1/5/6, AC-12)
# --------------------------------------------------------------------------- #
#: Fruehere Namen des Blocks (vor B4), in keiner Ausgabe mehr erlaubt -- als
#: eigenstaendiger Blocktitel (Klartext-Zeile bzw. Element-Text), Gross/klein
#: egal. "Großwetterlage" und Fliesstext mit "Ausblick" bleiben erlaubt (AC-11).
ALTE_AUSBLICK_NAMEN = {
    "de": ("Nächste Etappen", "Naechste Etappen", "Ausblick", "Ausblick · nächste 3 Tage",
           "Mehrtages-Trend", "3-Tages-Vorschau"),
    "en": ("Next stages", "Outlook", "Outlook · next 3 days", "Multi-day trend", "3-day preview"),
}
_ELEMENT_TEXT = re.compile(r">([^<>]+)<")


def ausblick_name(lang: str, ascii_: bool = False) -> str:
    """Der eine Name des Blocks (``mail.ausblick.name``); Kompakt in ASCII."""
    name = t("mail.ausblick.name", lang)
    return _falten(name) if ascii_ else name


def _titel_kandidaten(text: str, html: bool):
    if html:
        return (unescape(m.group(1)).strip() for m in _ELEMENT_TEXT.finditer(text))
    return (z.strip().strip("━=").strip() for z in text.splitlines())


def alte_ausblick_namen(text: str, lang: str, html: bool) -> list[str]:
    """Fruehere Blocknamen, die ``text`` als eigenen Titel traegt: im Klartext
    eine ganze (ggf. mit ``━━``/``==`` umrahmte) Zeile, im HTML der ganze Text
    eines Elements."""
    alte = {n.casefold() for n in ALTE_AUSBLICK_NAMEN.get(lang, ALTE_AUSBLICK_NAMEN["de"])}
    return list(dict.fromkeys(k for k in _titel_kandidaten(text, html) if k and k.casefold() in alte))


def name_im_text(text: str, name: str, html: bool) -> bool:
    """Steht ``name`` als eigener Blocktitel in ``text`` (Zeile bzw. Element-Text)?"""
    return any(k.casefold() == name.casefold() for k in _titel_kandidaten(text, html))


def ausblick_briefings(dc: object, surface: str, *, report_config: object = None,
                       enabled_reports=None, outlook_enabled=None) -> dict[str, bool]:
    """Je Briefing (morning/evening): steht der 3-Tages-Ausblick darin? Die EINE
    Regel des Produkts: mit Tabelle ``resolve_outlook_reports`` +
    ``outlook_applies`` (Briefing in ``outlook_reports`` und mindestens eine
    Metrik an der Stelle "outlook"), sonst ``_legacy_outlook_reports``
    (Trip: ``show_outlook``/Kompakt-Ausnahme/``multi_day_trend_reports``;
    Orte: ``outlook_enabled``, Anlage-Marke ``placements.outlook_reports``)."""
    from services.channel_list_resolver import grundauswahl
    from services.placements import (
        _feld, _legacy_outlook_reports, outlook_applies, read_placements, resolve_outlook_reports,
        resolve_rows,
    )

    stored = read_placements(_feld(dc, "placements"))
    if stored is not None:
        reports = resolve_outlook_reports(stored.outlook_reports, enabled_reports)
        an = {}
        for report in _REPORTS:
            grund = grundauswahl(dc, surface, report)
            rows = resolve_rows(stored.rows, grund.ids, surface, parents=grund.parents)
            an[report] = outlook_applies(rows, reports, report)
        return an
    legacy, _stabilitaet = _legacy_outlook_reports(
        dc, surface, report_config, enabled_reports, outlook_enabled)
    return {report: report in legacy for report in _REPORTS}


def trip_ausblick_briefings(trip: dict) -> tuple[dict[str, bool], bool]:
    """(Ausblick je Briefing, hat Tabelle) eines Trips, gelesen wie der
    Versand: Trip ueber den Loader (``load_trip_from_dict``, Vorgaben der
    Modelle), eingeschaltete Briefings ueber ``trip_enabled_reports``."""
    from app.loader import load_trip_from_dict
    from services.placements import read_placements
    from services.report_config_resolver import trip_enabled_reports

    if "display_config" not in trip:  # nur eine display_config, ohne report_config
        return ausblick_briefings(trip, "trip"), read_placements(trip.get("placements")) is not None
    geladen = load_trip_from_dict(trip)
    rc, dc = geladen.report_config, geladen.display_config
    tabelle = read_placements(getattr(dc, "placements", None)) is not None
    return ausblick_briefings(dc, "trip", report_config=rc,
                              enabled_reports=trip_enabled_reports(rc)), tabelle


def _hat_tabelle(dc: object) -> bool:
    from services.placements import _feld, read_placements

    return read_placements(_feld(dc, "placements")) is not None


def ausblick_im_briefing(soll: dict, briefing: str | None) -> bool:
    """Steht laut Soll ein Ausblick in der Mail des Briefings ``briefing``?
    ``None`` (Typ unbekannt): wie bisher ``ausblick_an`` (irgendein Briefing)."""
    if briefing is None or "ausblick_briefings" not in soll:
        return bool(soll.get("ausblick_an"))
    return bool(soll.get("ausblick_an")) and briefing in soll["ausblick_briefings"]


def orte_ausblick_briefings(preset: dict) -> dict[str, bool]:
    """Ausblick je Briefing eines Orte-Abos; eingeschaltete Briefings ueber
    ``resolve_preset_slots`` wie der Versand (``placements_view_service``)."""
    from services.compare_slot_scheduler import resolve_preset_slots

    slots = resolve_preset_slots(preset)
    an = tuple(r for r, ein in (("morning", slots.morning_enabled),
                                ("evening", slots.evening_enabled)) if ein)
    return ausblick_briefings(preset.get("display_config") or {}, "compare", enabled_reports=an,
                              outlook_enabled=preset.get("outlook_enabled"))


def trip_soll(trip: dict, report: str = "evening") -> dict:
    """Soll eines Trip-Briefings fuer ``report`` (morning/evening)."""
    dc = _trip_display_config(trip)
    liste = _trip_email_liste(dc, report)
    grund = _sortiert([e for e in _eintraege(dc.get("metrics"))
                       if _waehlbar(e.get("metric_id")) and _an(e, report)])
    grundauswahl = list(dict.fromkeys(
        e["metric_id"] for e in grund if _ausblickfaehig(e["metric_id"])))
    rc = trip.get("report_config") or {}
    # Bewusst leer: alle Zeilen abgewaehlt -> der Ausblick entfaellt.
    ids = _ausblick(dc.get("outlook_metrics"), grundauswahl) if grundauswahl else []
    # #3155 (AC-12): Ausblick je Briefing aus der EINEN Regel (Kompakt-Ausnahme
    # inklusive); im Altpfad zusaetzlich nur mit Spalten (bewusst leer).
    briefings, tabelle = trip_ausblick_briefings(trip)
    ausblick_an = briefings[report] and (tabelle or ids != [])
    return {
        "kontext": "trip", "report": report,
        # #3047 F2: Etappennamen trennen den Klartext-Ausblick exakt ab.
        "etappen": [s["name"] for s in trip.get("stages") or []
                    if isinstance(s, dict) and isinstance(s.get("name"), str)],
        "stunden": _trip_stundenspalten(liste),
        "darstellung_stunden": {e["metric_id"]: _modus(e) for e in liste},
        "formen_stunden": _formen_stunden(liste),
        # #3047 F004: verschmolzene Windrichtung -> jede Wind-Zelle traegt die Richtung.
        "wind_richtung": _wind_verschmolzen(liste),
        "nacht": bool(dc.get("show_night_block", True)),
        "ausblick_an": ausblick_an,
        # #3155: Kompakt folgt derselben Regel (die Kompakt-Ausnahme von
        # ``show_outlook``, PO-Entscheidung #722, steckt in ihr).
        "ausblick_an_kompakt": ausblick_an,
        # #3155 (AC-12): in welchen Briefings der Ausblick laut Konfiguration steht.
        "ausblick_briefings": tuple(r for r in _REPORTS if briefings[r]),
        "ausblick": None if ids == [] else _ausblick_spalten(ids, dc.get("outlook_metric_formats")),
        # #3047 Runde 7 (B-V1): Etappendaten verankern die Zahl der Ausblick-
        # Zeilen (``ausblick_zeilen_trip``) am Datum der Mail.
        "etappen_daten": [s["date"] for s in trip.get("stages") or []
                          if isinstance(s, dict) and isinstance(s.get("date"), str)],
        "email_format": rc.get("email_format", "full"),
        # #3047 N5/F008b: Metriken-Ueberblick nur, wenn eine Groesse der
        # E-Mail-Liste dieses Berichts eine Kachel traegt. Der Renderer
        # kollabiert ``dc.metrics`` vor dem Ueberblick auf die E-Mail-Liste
        # (trip_report.py, ``get_metrics_for_channel``), ``build_metrics_summary_pills``
        # filtert auf die Weisse Liste ``_PILL_CATALOG_ORDER``; ohne Kachel
        # entfaellt die Ueberschrift (html.py/plain.py/compact.py: ``if pills``).
        # Datenabhaengig fehlende Kacheln (keine Werte) sind nicht ableitbar.
        "ueberblick": any(e["metric_id"] in _PILL_CATALOG_ORDER for e in liste),
        # #3047 Runde 7 (B-V2): nur ein ausdrueckliches ``false`` ist "aus";
        # "an" bleibt weich (Kennzahlen/Vortag sind datenabhaengig).
        "zusatz": {k: rc.get(k, True) is not False for k in ("show_stage_stats", "show_yesterday_comparison")},
        # #3047 B-L5: Schalter E4, Kachelfolge, Ampel-Grenzen, Stundenband.
        "warnungen": warnungen_an(trip),
        "ueberblick_folge": ueberblick_folge(liste),
        "ampel": ampel_grenzen(dc),
        "stundenband": stundenband(trip),
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


def _orte_formen(dc: dict, paare: list[tuple[str, str]] | None, lang: str) -> dict[str, dict]:
    """#3047 Runde 7 (B-V3): erlaubte Zellform je Zeile der Vergleichstabelle.
    Einfach (``channel_layouts.email``, erster eingeschalteter Eintrag je
    Kennung, nur bei mehr als einer Darstellung): HTML Ampelpunkt bzw.
    Wort, Klartext Wort. Sonst Roh = Zahl. Ausnahmen wie im Trip: Gewitter und
    Niederschlagsart zeigen roh ein Wort, die Windrichtung eine Himmelsrichtung
    -- ungeprueft."""
    if not paare:
        return {}
    einfach = set(_orte_einfach(dc, paare, lang))
    formen: dict[str, dict] = {}
    for label, (m, _a) in zip(_uebersicht_labels(paare, lang), paare):
        if label in einfach:
            html = (AMPEL,) if m in AMPEL_METRIC_IDS else (WORT, AMPEL)
            formen[label] = {"HTML": html, "Klartext": (WORT,)}
        elif m not in _ROH_WORT and m != "wind_direction":
            formen[label] = {"HTML": (ZAHL,), "Klartext": (ZAHL,)}
    return formen


#: Vorgabe-Tagesfenster (``app.day_window.DAY_WINDOW_START_HOUR/END_HOUR``, ADR-0035).
_FENSTER_VORGABE = (4, 19)


def tagesfenster(start: object, ende: object) -> tuple[int, int]:
    """#3047 Runde 7 (B-V5): Tagesfenster nach der dokumentierten Regel
    (ADR-0035): beide Stunden ganzzahlig 0-23 und verschieden, sonst die
    Vorgabe 4-19; ``start > ende`` = Fenster ueber Mitternacht."""
    if type(start) is int and type(ende) is int and 0 <= start <= 23 and 0 <= ende <= 23 and start != ende:
        return start, ende
    return _FENSTER_VORGABE


def im_fenster(stunde: int, fenster: tuple[int, int]) -> bool:
    start, ende = fenster
    return start <= stunde <= ende if start <= ende else (stunde >= start or stunde <= ende)


def ausblick_zeilen_trip(etappen_daten: list[str], maildatum: str | None) -> int | None:
    """#3047 Runde 7 (B-V1): Zahl der Ausblick-Zeilen eines Trip-Briefings =
    folgende Etappen nach der berichteten, hoechstens drei
    (``get_future_stages``, ``future_stages[:3]``). Verankert nur, wenn das
    Mail-Datum (ISO) ein Etappendatum der Konfiguration ist, sonst ``None``."""
    if not maildatum or maildatum not in etappen_daten:
        return None
    return min(3, len({d for d in etappen_daten if d > maildatum}))


def warnungen_an(preset: dict) -> bool:
    """#3047 E4 (PO-Entscheidung Runde 7): Briefing-Schalter
    (``official_alerts_enabled``, nur ``false`` = aus) ODER Alarm-Schalter
    (``official_warnings.enabled``, sonst Altfeld
    ``official_alert_triggers_enabled``) an -> "beides an"; nur beide aus = aus."""
    briefing = preset.get("official_alerts_enabled") is not False
    alarm_neu = preset.get("official_warnings")
    if isinstance(alarm_neu, dict) and "enabled" in alarm_neu:
        alarm = bool(alarm_neu.get("enabled"))
    else:
        alarm = preset.get("official_alert_triggers_enabled") is not False
    return briefing or alarm


# --------------------------------------------------------------------------- #
# Lueckenschluss Runde 7 (#3047 B-L5): Ampel-Grenzen, Kacheln, Warnungen
# --------------------------------------------------------------------------- #
#: Profil -> Vorlage (``app.ampel._PROFIL_ZU_VORLAGE``, Gross-/Kleinschreibung egal).
_PROFIL_VORLAGE = {"summer_trekking": "alpen-trekking"}
_STUFEN = ("green", "yellow", "orange", "red")


def ampel_grenzen(dc: dict, profil: object = None) -> dict[str, dict]:
    """Grenzen je Metrik nach der Rueckfallkette ADR-0106 aus der STATISCHEN
    Vorlagentabelle: ``ampel.template`` > ``preset_name`` > Profil >
    "allgemein"; Abo-Grenzen je Metrik ersetzen die Seite (``null`` = offen)."""
    abo = dc.get("ampel") if isinstance(dc.get("ampel"), dict) else {}
    kandidaten = (abo.get("template"), dc.get("preset_name"),
                  _PROFIL_VORLAGE.get(str(profil or "").lower(), str(profil or "").lower()))
    tid = next((k for k in kandidaten if k in AMPEL_TEMPLATES), DEFAULT_TEMPLATE)
    grenzen = {m: {"upper": dict(e["upper"]), "lower": dict(e["lower"])}
               for m, e in AMPEL_TEMPLATES[tid]["metrics"].items()}
    for mid, e in (abo.get("metrics") or {}).items():
        ziel = grenzen.setdefault(mid, {"upper": {}, "lower": {}})
        for seite in ("upper", "lower"):
            if isinstance(e, dict) and seite in e:
                ziel[seite] = dict(e[seite] or {})
    return grenzen


def ampel_stufe(grenzen: dict, mid: str, wert: float) -> str | None:
    """Stufe wie ``severity_from_thresholds``: oben ``>=``, unten ``<``, die
    schaerfere Seite gewinnt; ohne jede Grenze ``None``."""
    e = grenzen.get(mid) or {}
    oben = {k: v for k, v in (e.get("upper") or {}).items() if v is not None}
    unten = {k: v for k, v in (e.get("lower") or {}).items() if v is not None}
    if not oben and not unten:
        return None
    rang = max([i for i, k in enumerate(_STUFEN) if k in oben and wert >= oben[k]]
               + [i for i, k in enumerate(_STUFEN) if k in unten and wert < unten[k]] + [0])
    return _STUFEN[rang]


def ampel_erlaubt(grenzen: dict, mid: str, text: str) -> set[str] | None:
    """Erlaubte Stufen einer gerundet angezeigten Zahl (halbe letzte Stelle)."""
    zahl = re.search(r"-?\d+(?:\.(\d+))?", text)
    if not zahl:
        return None
    wert, halb = float(zahl.group()), 0.5 * 10 ** -len(zahl.group(1) or "")
    stufen = {ampel_stufe(grenzen, mid, w) for w in (wert - halb, wert, wert + halb - 1e-9)}
    return None if None in stufen else stufen


_FALT = str.maketrans({"·": "-", "—": "-", "–": "-", "°": ""})
#: Katalogtexte der Kacheln je Groesse (``helpers._pill_for_metric``).
_KACHEL_SCHLUESSEL = {
    "precipitation": ("regen_ab", "regen_unbekannt", "regen_gesamt", "kein_regen"),
    "rain_probability": ("regenw_ereignis", "regenw_unbekannt", "regenw_max"),
    "thunder": ("gewitter_stufe", "gewitter_unbekannt", "kein_gewitter"),
    "visibility": ("sicht_ereignis", "sicht_min"), "humidity": ("feuchte_ereignis", "feuchte_bereich"),
    "cloud_low": ("tiefe_wolken",), "freezing_level": ("nullgradlinie",),
    "dewpoint": ("taupunkt",), "sunshine": ("sonne",),
}


def _falten(text: str) -> str:
    from utils.ascii_fold import fold_ascii

    return fold_ascii(unescape(text).translate(_FALT)).strip()


def kachel_metrik(text: str, lang: str) -> str | None:
    """Groesse einer Kachel am Katalogtext (laengster passender Anfang), in
    HTML, Klartext und ASCII-Kompakt gleich; unbekannte Form -> ``None``."""
    text = _falten(text).lstrip("! ")
    anfaenge = [(_falten(t(f"mail.pille.{k}", lang).split("{")[0]), m)
                for m, ks in _KACHEL_SCHLUESSEL.items() for k in ks]
    anfaenge += [(_falten(_REG[m].label(lang)) + " ", m) for m in ("wind", "gust")]
    anfaenge += [("UV max ", "uv_index"), (_falten(t("mail.pille.gefuehlt", lang)), "wind_chill")]
    treffer = sorted(((a, m) for a, m in anfaenge if a and text.startswith(a)), key=lambda p: -len(p[0]))
    if treffer:
        return treffer[0][1]
    if _falten(t("mail.pille.bewoelkt", lang).split("}")[1].split("{")[0]) in text:
        return "cloud_total"
    return "temperature" if re.search(r"C - Max \d\d:00$", text) else None


def ueberblick_folge(liste: list[dict]) -> list[str]:
    """Kachelfolge = Folge der E-Mail-Liste, nur Groessen mit Kachel (#1703 S7)."""
    return list(dict.fromkeys(e["metric_id"] for e in liste if e["metric_id"] in _PILL_CATALOG_ORDER))


def stundenband(trip: dict) -> tuple[int, int] | None:
    """Erlaubte Stunden der Etappentabellen: vom frueheren aus Fensterbeginn
    (ADR-0035) und Etappenstart (Vorgabe 08:00), hoechstens 06, bis zum
    spaeteren aus Fensterende und 22; Fenster ueber Mitternacht -> keine Grenze."""
    rc = trip.get("report_config") or {}
    start, ende = tagesfenster(rc.get("day_window_start_hour"), rc.get("day_window_end_hour"))
    if start > ende:
        return None
    starts = [int(s["start_time"][:2]) for s in trip.get("stages") or [] if isinstance(s, dict)
              and re.match(r"\d{2}:\d{2}", str(s.get("start_time") or ""))] or [8]
    return min(start, *starts, 6), max(ende, 22)


def orte_standardzeilen() -> list[tuple[str, str]]:
    """Grundauswahl nie eingestellt: alle Zeilen der Vergleichstabelle in
    Standardfolge (Struktur ``CV2_ZEILEN``, ohne Warnzeile)."""
    from output.renderers.email.compare_html import CV2_ZEILEN

    return [(z["metric_id"], z["aggregation"]) for z in CV2_ZEILEN if "metric_id" in z]


def zieltag_versatz(preset: dict) -> set[int]:
    """Zieltag ab Erstellungstag je eingeschaltetem Slot: Morgen 0, Abend +1
    (``compare_slot_scheduler``; Vorgabe Morgen an, Abend aus; Alt-Preset
    ohne ``morning_time``: ``schedule == "daily_evening"`` = Abend)."""
    if preset.get("morning_time") is None:
        return {1} if preset.get("schedule") == "daily_evening" else {0}
    return {v for slot, v, vorgabe in (("morning", 0, True), ("evening", 1, False))
            if bool(preset.get(f"{slot}_enabled", vorgabe))}


#: Zeilen der Vergleichstabelle mit Zell-Toenung, die der Validator prueft (Sicht ungeprueft).
_ORTE_AMPEL = frozenset({"temperature", "wind", "gust", "precipitation", "rain_probability", "uv_index"})


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
    if ids is None:
        # #3047 R9: Orte-Altbestand ohne Grundauswahl und ohne Ausblick-Liste
        # rendert die Vorgabemenge wie eine explizite Liste (HTML = Klartext,
        # Temp als eine Spanne) -- kein fester Zweig mehr im Ortsvergleich.
        ids = list(_FEST)
    an = orte_ausblick_briefings(preset)
    briefings = tuple(r for r in _REPORTS if an[r])
    stunden = _orte_stunden(dc, grundpaare)
    stunden_an = preset.get("hourly_enabled", True) is not False and stunden != []
    ids_orte = [i for i in preset.get("location_ids") or [] if isinstance(i, str)]
    # #3047 AC-28: Warnzeile nur bei eingeschalteten amtlichen Warnungen
    # (E4-Regel "beides an", ``warnungen_an``).
    warn = [t("vergleich.zeile.amtliche_warnungen", lang)] if warnungen_an(preset) else []
    fenster = tagesfenster(preset.get("day_window_start_hour"), preset.get("day_window_end_hour"))
    # #3047 B-L5: nie eingestellt (kein ``active_metrics``, keine Kanal-Liste)
    # -> alle Zeilen der Vergleichstabelle in Standardfolge, wie die Mail.
    paare = orte_standardzeilen() if paare is None else paare
    labels = _uebersicht_labels(paare, lang)
    return {
        "kontext": "orte",
        # #3122 B5 (F-V1): Nutzerdaten, die der Namens-Check ausblendet.
        "abo_name": preset.get("name") if isinstance(preset.get("name"), str) else "",
        "uebersicht": warn + labels,
        "warnungen": warnungen_an(preset),
        # Zieltag-Versatz je eingeschaltetem Slot (Morgen 0, Abend +1 Tag).
        "zieltag_versatz": zieltag_versatz(preset),
        "ampel": ampel_grenzen(dc, preset.get("profil")),
        "ampel_zeilen": {lab: m for lab, (m, _a) in zip(labels, paare) if m in _ORTE_AMPEL},
        "warnzeile": bool(warn),
        "uebersicht_einfach": _orte_einfach(dc, paare, lang),
        "uebersicht_formen": _orte_formen(dc, paare, lang),
        "tagesfenster": fenster,
        # B-V1: drei Folgetage (``comparison_engine``, 96-h-Abruf); ein Fenster
        # ueber Mitternacht verschiebt den Ausblick um einen Tag -> 2 oder 3.
        "ausblick_zeilen": (2, 3) if fenster[0] > fenster[1] else (3,),
        "stunden_an": stunden_an,
        "stunden": stunden if stunden_an else [],
        # #3155 (AC-12): Ausblick je Briefing aus der EINEN Regel;
        # ``ausblick_an`` = in irgendeinem Briefing, der Validator setzt es
        # je Briefing der Mail (``ausblick_im_briefing``).
        "ausblick_briefings": briefings,
        "ausblick_an": bool(briefings) and (_hat_tabelle(dc) or ids != []),
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


# --------------------------------------------------------------------------- #
# Ampelfarbe einer HTML-Zelle (#3047 B-L5) -- Trip und Orte
# --------------------------------------------------------------------------- #
def ampel_farbe(attrs: str, inhalt: str) -> str:
    """Ampelstufe einer HTML-Zelle: Ampelpunkt (Fuellfarbe) vor Zell-Toenung;
    ungetoent = gruen (``_ampel_cell_bg``: gruen bleibt ohne Hintergrund)."""
    from output.renderers.email.design_tokens import _TONE_CSS
    from output.renderers.email.helpers import _AMPEL_DOT_COLORS

    punkt = re.search(r"border-radius:\s*50%;\s*background:\s*(#[0-9a-fA-F]{6})", inhalt)
    if punkt:
        return next((k for k, (f, _r) in _AMPEL_DOT_COLORS.items() if f.lower() == punkt.group(1).lower()), "?")
    ton = re.search(r"background:\s*(#[0-9a-fA-F]{6})", attrs)
    farbe = ton.group(1).lower() if ton else ""
    return next((k for k, (bg, _fg) in _TONE_CSS.items() if k != "green" and bg.lower() == farbe), "green")


def ampel_abweichung(grenzen: dict, mid: str, text: str, ist: str) -> str | None:
    """``"<ist> statt <soll>"``, wenn die Farbe nicht zur angezeigten Zahl passt."""
    erlaubt = ampel_erlaubt(grenzen, mid, text)
    if not erlaubt or ist in erlaubt:
        return None
    wert = float(re.search(r"-?\d+(?:\.\d+)?", text).group())
    return f"{ist} statt {ampel_stufe(grenzen, mid, wert)}"

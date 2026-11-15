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
* Ausblick: Drei-Werte-Semantik (ADR-0037/0055): ``[]`` = Block aus, nie
  eingestellt = GANZE Grundauswahl in der eingestellten Reihenfolge (AC-4,
  nicht Katalogfolge), sonst Schnitt mit der Grundauswahl, leerer Schnitt =
  Rueckfall auf die volle Grundauswahl (#1848 A3). Ohne Grundauswahl
  (``metrics``/``active_metrics`` fehlt) die sieben festen Spalten, im HTML
  wie im Klartext (AC-21).
* Orte: Vergleichstabelle = ``channel_layouts.email`` (Folge, ``enabled``,
  #3039) vor ``channel_active_metrics.email``, je geschnitten mit
  ``active_metrics`` (#1703 S8), Stundenverlauf = ``hourly_metrics``,
  Ortsfolge = ``location_ids`` (#1359).

``None`` an einer Liste heisst "keine Aussage" (z. B. nie eingestellter
Stundenverlauf: dessen Vorgabe sichert AC-13), der Validator prueft sie dann
nicht.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from app.metric_catalog import _METRICS, aggregation_label  # noqa: E402
from i18n import t  # noqa: E402
from output.renderers.compare_hourly_metric_ids import (  # noqa: E402
    FRONTEND_TO_HOURLY_METRIC_ID, HOURLY_EXCLUDED_METRIC_IDS, HOURLY_MERGE_ONLY_METRIC_IDS,
)
from output.renderers.compare_metric_catalog import COMPARE_METRIC_CATALOG  # noqa: E402
from output.renderers.email.helpers import NO_HOURLY_COLUMN_METRIC_IDS  # noqa: E402

_REG = {m.id: m for m in _METRICS}
_BUCKET_RANG = {"primary": 0, "secondary": 1}
_REPORTS = ("morning", "evening")
#: Die sieben festen Ausblick-Spalten (Altbestand), Temperatur als Spanne.
_FEST = ("temperature", "precipitation", "rain_probability", "wind", "gust", "thunder")
#: Alle waehlbaren Spaltenkuerzel -- erkennt im Klartext auch eine Spalte zu viel.
ALLE_KUERZEL = tuple(dict.fromkeys(
    m.col_label for m in _METRICS if m.selectable and m.id not in NO_HOURLY_COLUMN_METRIC_IDS))


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
    if grund:
        ebene = [e for e in ebene if e["metric_id"] in erlaubt]
    return _sortiert(ebene)


def _trip_stundenspalten(liste: list[dict]) -> list[str]:
    ids = [e["metric_id"] for e in liste]
    merge = "wind" in ids and any(
        e["metric_id"] == "wind_direction" and _modus(e) == "scale" for e in liste)
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
    if kennungen == []:
        return []
    if not grundauswahl:
        return kennungen
    if kennungen is None:
        return list(grundauswahl)
    return [m for m in kennungen if m in grundauswahl] or list(grundauswahl)


def _ausblick_spalten(ids: list[str] | None, formate: object) -> dict:
    if ids is None:
        temp = _REG["temperature"].col_label
        html = [f"{temp} {aggregation_label(a, 'de')}" for a in ("min", "max")]
        return {"fest": True, "html": html + [_REG[m].col_label for m in _FEST[1:]],
                "klartext": [_REG[m].col_label for m in _FEST], "darstellung": {}}
    labels = [_REG[m].col_label for m in ids]
    einfach = {m: bool(v) for m, v in (formate or {}).items()} if isinstance(formate, dict) else {}
    return {"fest": False, "html": labels, "klartext": labels,
            "darstellung": {m: "einfach" if einfach.get(m) else "roh" for m in ids}}


def trip_soll(trip: dict, report: str = "evening") -> dict:
    """Soll eines Trip-Briefings fuer ``report`` (morning/evening)."""
    dc = trip.get("display_config") if "display_config" in trip else trip
    dc = dc or {}
    rc = trip.get("report_config") or {}
    liste = _trip_email_liste(dc, report)
    grund = _sortiert([e for e in _eintraege(dc.get("metrics"))
                       if _waehlbar(e.get("metric_id")) and _an(e, report)])
    grundauswahl = None if not dc.get("metrics") else list(dict.fromkeys(
        e["metric_id"] for e in grund if _ausblickfaehig(e["metric_id"])))
    ids = _ausblick(dc.get("outlook_metrics"), grundauswahl)
    trend_reports = rc.get("multi_day_trend_reports", dc.get("multi_day_trend_reports", ["evening"]))
    return {
        "kontext": "trip", "report": report,
        "stunden": _trip_stundenspalten(liste) if dc.get("metrics") else None,
        "darstellung_stunden": {e["metric_id"]: _modus(e) for e in liste},
        "nacht": bool(dc.get("show_night_block", True)),
        "ausblick_an": ids != [] and rc.get("show_outlook", True) is not False
        and report in (trend_reports or []),
        "ausblick": None if ids == [] else _ausblick_spalten(ids, dc.get("outlook_metric_formats")),
        "email_format": rc.get("email_format", "full"),
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


def _orte_stunden(dc: dict) -> list[str] | None:
    roh = dc.get("hourly_metrics")
    if not isinstance(roh, list):
        return None
    ids: list[str] = []
    for e in roh:
        mid = FRONTEND_TO_HOURLY_METRIC_ID.get(e, e) if isinstance(e, str) else None
        if (mid in _REG and mid not in HOURLY_EXCLUDED_METRIC_IDS and mid not in ids
                and _REG[mid].selectable):
            ids.append(mid)
    return [_REG[m].col_label for m in ids if m not in HOURLY_MERGE_ONLY_METRIC_IDS]


def orte_soll(preset: dict, lang: str = "de", ortsnamen: dict | None = None) -> dict:
    """Soll eines Orts-Vergleichs; ``ortsnamen`` (Kennung -> Name) fuer die Ortsfolge."""
    dc = preset.get("display_config") or {}
    paare = _orte_uebersicht(dc)
    grundpaare = _uebersicht_paare(dc.get("active_metrics"))
    grundauswahl = None if grundpaare is None else list(dict.fromkeys(
        m for m, _a in grundpaare if _ausblickfaehig(m)))
    ids = _ausblick(dc.get("outlook_metrics"), grundauswahl)
    stunden = _orte_stunden(dc)
    stunden_an = preset.get("hourly_enabled", True) is not False and stunden != []
    ids_orte = [i for i in preset.get("location_ids") or [] if isinstance(i, str)]
    return {
        "kontext": "orte",
        "uebersicht": None if paare is None else
        [t("vergleich.zeile.amtliche_warnungen", lang)] + _uebersicht_labels(paare, lang),
        "stunden_an": stunden_an,
        "stunden": stunden if stunden_an else [],
        "ausblick_an": preset.get("outlook_enabled", True) is not False and ids != [],
        "ausblick": None if ids == [] else _ausblick_spalten(ids, dc.get("outlook_metric_formats")),
        "orte": [ortsnamen[i] for i in ids_orte if i in ortsnamen] if ortsnamen else None,
    }


# --------------------------------------------------------------------------- #
# Einstieg
# --------------------------------------------------------------------------- #
def soll_aus_daten(daten: dict, lang: str = "de") -> dict:
    """Erkennt Trip bzw. Orte am Inhalt. Orte duerfen als Huelle
    ``{"preset": {...}, "orte": {"<id>": "<Name>"}}`` kommen (Ortsfolge)."""
    if isinstance(daten.get("preset"), dict):
        return orte_soll(daten["preset"], lang, daten.get("orte") or None)
    if "location_ids" in daten or daten.get("kind") == "vergleich":
        return orte_soll(daten, lang)
    return {"kontext": "trip", "je_report": {r: trip_soll(daten, r) for r in _REPORTS}}


def lade_soll(pfad: str | Path, lang: str = "de") -> dict:
    return soll_aus_daten(json.loads(Path(pfad).read_text(encoding="utf-8")), lang)


def abweichung(ist: list[str], soll: list[str]) -> str | None:
    """Beschreibung der ersten Abweichung mit Spaltennamen (``None`` = gleich)."""
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

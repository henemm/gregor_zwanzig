"""#3047 Paket D: Editor-Standard = Mail-Standard, PYTHON-Seite (AC-13, AC-4, AC-21).

SPEC: docs/specs/modules/feat_3047_einstellung_gleich_mail_pruefkatalog.md §5, §7
Konzept: docs/context/einstellungen_neu.md §5 Punkt 6 und 8

Je Liste (Trip-Tabellen, Trip-Ausblick, Orte-Vergleichstabelle, Orte-Stundenverlauf,
Orte-Ausblick) laeuft die ECHTE Python-Aufloesung mit der Eingabe aus
``tests/fixtures/einstellung_gleich_mail/editor_standard.json`` bis an die Stelle,
an der die Mail ihre Spalten bzw. Zeilen festlegt (Spaltenkopf des Ausblicks,
``_visible_hour_metrics``, ``_visible_metrics``, ``email_col_order``).
Das Soll steht dort von Hand als Literal-Liste -- es wird hier NICHT aus einem
Resolver berechnet, deshalb ist der Aufruf der Produkt-Resolver kein Spiegel.
Dieselbe Datei liest die Frontend-Seite
(``frontend/.../__tests__/editor_standard_gleich_mail.test.ts``); weicht eine
Seite ab, scheitert genau der Test dieser Seite.

Bekannte, ausgelagerte Abweichungen (N1 -> #3048) laufen als ``ausnahme``:
der Test haelt den Ist-Zustand fest und wird rot, sobald die Behebung wirkt.

Lauf:
    uv run pytest tests/tdd/test_einstellung_gleich_mail_editor_standard.py -q
"""
from __future__ import annotations

import html
import json
import re
from pathlib import Path

import pytest

from app.ampel import resolve_ampel
from app.loader import _parse_display_config
from app.metric_catalog import get_all_metrics
from output.renderers.compare_metric_ids import FRONTEND_TO_RENDERER_METRIC_ID
from output.renderers.email.compare_html import (
    _hour_zeilen,
    _visible_hour_metrics,
    _visible_metrics,
)
from output.renderers.email.helpers import email_col_order
from output.renderers.email.outlook import render_outlook_table
from services.channel_list_resolver import resolve_channel_lists
from services.report_config_resolver import resolve_compare_render_options

FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "fixtures" / "einstellung_gleich_mail" / "editor_standard.json"
)
DATEN = json.loads(FIXTURE.read_text(encoding="utf-8"))
LISTEN = DATEN["listen"]


def _zustand(liste: str, zustand_id: str) -> dict:
    return next(z for z in LISTEN[liste]["zustaende"] if z["id"] == zustand_id)


#: #3237: Faelle, deren Soll ein Schnitt-Rueckfall des Altpfads ist (die
#: gespeicherte Liste liegt ganz ausserhalb der Grundauswahl -> Rueckfall auf
#: die volle Grundauswahl bzw. Vorgabe). Die Tabelle "Was steht wo" kennt
#: keinen Rueckfall (ADR-0124, "Leer bleibt leer"); die Python-Seite prueft
#: diese Faelle nicht mehr. Die Datei bleibt unveraendert (die Frontend-Seite
#: liest sie bis #3276 weiter).
_ALTPFAD_RUECKFALL_3237 = {
    ("trip_tabellen", "gespeichert_totalschnitt"),
    ("trip_ausblick", "gespeichert_totalschnitt"),
    ("orte_stundenverlauf", "gespeichert_totalschnitt"),
}

#: #3237: Python-Soll nach bewussten, dokumentierten Ausgabeaenderungen
#: (Spec #3122); die Frontend-Seite behaelt das Soll der Datei bis #3276.
#: Von Hand, je mit Grund.
_SOLL_3237 = {
    # Spec #3122 Nr. 8 (EINE Zeilenfolge): ohne Tabelle gilt die
    # Grundauswahl-Tabelle; Hoechst- und Tiefstwert der Temperatur sind eine
    # Zeile (Nr. 2), Stundenverlauf und Ausblick folgen der Zeilenfolge.
    ("orte_vergleichstabelle", "nie_eingestellt"): [
        "temp_max_c", "temp_min_c", "wind_max_kmh", "precip_sum_mm", "pop_max_pct",
        "thunder_level_max", "sunny_hours_h", "cloud_avg_pct", "uv_index_max",
        "visibility_min_m", "snow_depth_cm", "snow_new_sum_cm", "gust_max_kmh",
        "freezing_level_m", "wind_direction_deg", "wind_chill_min_c", "wind_chill_max_c",
        "cloud_low_avg_pct", "cloud_mid_avg_pct", "cloud_high_avg_pct", "humidity_avg_pct",
        "dewpoint_avg_c", "pressure_avg_hpa", "precip_type_dominant", "snowfall_limit_m"],
    ("orte_stundenverlauf", "nie_eingestellt"): [
        "temperature", "wind", "precipitation", "rain_probability", "thunder",
        "uv_index", "visibility", "gust", "wind_chill"],
    ("orte_ausblick", "nie_eingestellt"): [
        "temperature", "wind", "precipitation", "rain_probability", "thunder", "gust"],
    # #3122 Fix-Loop B1b: Nacht-/Tagesgroessen der Temperatur haben in der
    # Trip-Stundentabelle keinen eigenen Haken und gehoeren weiter zur Ausgabe
    # (folgen der Grundauswahl), auch wenn die Temperatur-Zeile an der Stelle
    # E-Mail abgewaehlt ist.
    ("trip_tabellen", "gespeichert_ausserhalb_grundauswahl"): [
        "thunder", "gust", "temperature_night", "temperature_day_low",
        "temperature_day_high"],
}


def _gespeicherte(liste: str) -> list:
    return [
        pytest.param(z, id=z["id"])
        for z in LISTEN[liste]["zustaende"]
        if z["id"].startswith("gespeichert") and (liste, z["id"]) not in _ALTPFAD_RUECKFALL_3237
    ]


# ── Uebersetzungen Mail-Vokabular -> Listen-Vokabular (Register, kein Resolver) ──

def _col_key_zu_kennung() -> dict[str, str]:
    abbildung: dict[str, str] = {}
    for m in get_all_metrics():
        assert m.col_key not in abbildung, f"col_key {m.col_key} doppelt im Register"
        abbildung[m.col_key] = m.id
    return abbildung


def _kennung_aus_spaltenkopf(kopf: str) -> str:
    """Spaltenkopf des Ausblicks (``col_label`` ggf. mit Auswertungs-Suffix,
    z. B. ``Temp Min``) -> Kennung; eindeutig ueber das Register."""
    treffer = [m.id for m in get_all_metrics()
               if kopf == m.col_label or kopf.startswith(m.col_label + " ")]
    assert len(treffer) == 1, f"Spaltenkopf {kopf!r} nicht eindeutig: {treffer}"
    return treffer[0]


def _ausblick_spalten(metrics: list[str] | None) -> list[str]:
    """Kennungen in der Folge des HTML-Spaltenkopfs, den die Mail ausgibt
    (``render_outlook_table`` -- fester Zweig bei ``None``, sonst die Auswahl).
    Tief/Hoch derselben Groesse zaehlen als EIN Listeneintrag."""
    tabelle = render_outlook_table(
        [], show_acc=False, metrics=metrics, lang="de", ampel=resolve_ampel({}),
    )
    koepfe = [html.unescape(k) for k in re.findall(r"<th[^>]*>(.*?)</th>", tabelle)][1:]
    folge: list[str] = []
    for kopf in koepfe:
        kennung = _kennung_aus_spaltenkopf(kopf)
        if kennung not in folge:
            folge.append(kennung)
    return folge


# ── Python-Seite je Liste ──────────────────────────────────────────────────────

def _trip_dc(eingabe: dict):
    """#3237: die gespeicherte Einstellung der Eingabe (Altfelder, so schreibt
    der Editor bis #3276) wirkt nur als Tabelle "Was steht wo"; der Test
    druckt sie als Tabelle aus (``trip_wunsch_als_tabelle``), dann Loader."""
    from tests.helpers.tabelle_aus_wunsch import trip_wunsch_als_tabelle

    roh = trip_wunsch_als_tabelle({"display_config": eingabe["display_config"]})
    return _parse_display_config(roh["display_config"], trip_standard_bei_leer=True)


def python_trip_tabellen(eingabe: dict) -> list[str]:
    """E-Mail-Spaltenfolge der Stundentabelle: Loader -> Kanal-Listen-Resolver
    (``resolve_channel_lists(dc, "trip", rt).email``, wie ``trip_report.py``,
    #3096) -> Adapter ``email_col_order`` (geteilt von html.py und plain.py)."""
    dc = _trip_dc(eingabe)
    abbildung = _col_key_zu_kennung()
    zeilen = resolve_channel_lists(dc, "trip", "evening").email
    return [abbildung[k] for k in email_col_order(zeilen)]


def python_trip_ausblick(eingabe: dict) -> list[str]:
    dc = _trip_dc(eingabe)
    # #3237: Ausblick-Spalten aus der Tabelle (ohne Tabelle: Grundauswahl).
    return _ausblick_spalten([z.metric_id for z in resolve_channel_lists(dc, "trip", "evening").outlook])


def _katalog_ids(liste):
    """Alt-Vokabular (``gust_max_kmh``) -> Katalog-ID (``gust``); Katalog-IDs
    bleiben. Nur fuer den Ausdruck als Tabelle (die Tabelle kennt Katalog-IDs)."""
    from output.renderers.compare_metric_ids import katalog_paar

    if not isinstance(liste, list):
        return liste
    out = []
    for e in liste:
        rid = FRONTEND_TO_RENDERER_METRIC_ID.get(e) if isinstance(e, str) else None
        paar = katalog_paar(rid) if rid else None
        out.append(paar[0] if paar else e)
    return list(dict.fromkeys(out))


def _orte_optionen(eingabe: dict):
    """#3237: die Einstellung der Eingabe wirkt nur als Tabelle (s. ``_trip_dc``)."""
    import copy

    from tests.helpers.tabelle_aus_wunsch import orte_wunsch_als_tabelle

    wunsch = copy.deepcopy(eingabe)
    dc = wunsch.get("display_config") or {}
    cam = dc.get("channel_active_metrics")
    if isinstance(cam, dict):
        dc["channel_active_metrics"] = {k: _katalog_ids(v) for k, v in cam.items()}
    preset = orte_wunsch_als_tabelle({"id": "pruef-3047", **wunsch})
    preset["display_config"].pop("channel_active_metrics", None)
    preset["display_config"].update(
        {k: v for k, v in (eingabe.get("display_config") or {}).items()
         if k == "channel_active_metrics"})
    return preset, resolve_compare_render_options(preset)


def python_orte_vergleichstabelle(eingabe: dict) -> list[str]:
    preset, optionen = _orte_optionen(eingabe)
    zeilen = _visible_metrics(
        optionen.enabled_metrics_by_channel["email"], "de", ampel=resolve_ampel(preset),
    )
    katalog_schluessel = {r: k for k, r in FRONTEND_TO_RENDERER_METRIC_ID.items()}
    return [katalog_schluessel[z["key"]] for z in zeilen if z["key"] != "warn"]


def python_orte_stundenverlauf(eingabe: dict) -> list[str]:
    """Spalten des Stundenverlaufs; schaltet die Aufloesung den Block ab
    (``hourly_enabled`` False), zeigt die Mail keine Spalte (#3047 N2)."""
    _preset, optionen = _orte_optionen(eingabe)
    if not optionen.hourly_enabled:
        return []
    return [z["metric_id"] for z in _visible_hour_metrics(optionen.hourly_metrics, _hour_zeilen())]


def python_orte_ausblick(eingabe: dict) -> list[str]:
    """Spalten des Ausblicks; ``outlook_enabled`` False = Block entfaellt (#3047 N2)."""
    _preset, optionen = _orte_optionen(eingabe)
    if not optionen.outlook_enabled:
        return []
    return _ausblick_spalten(optionen.outlook_metrics)


def _pruefe(seite, liste: str, zustand: dict) -> None:
    ist = seite(zustand["eingabe"])
    soll = _SOLL_3237.get((liste, zustand["id"]), zustand["erwartet"])
    assert ist == soll, (
        f"Python-Seite {liste}/{zustand['id']}: Mail liefert {ist}, "
        f"Soll {soll} (editor_standard.json bzw. _SOLL_3237)"
    )


# ── Trip-Tabellen ──────────────────────────────────────────────────────────────

def test_python_seite_trip_tabellen_standard():
    _pruefe(python_trip_tabellen, "trip_tabellen", _zustand("trip_tabellen", "nie_eingestellt"))


def test_python_seite_trip_tabellen_altbestand():
    """N1 (#3047, frueher Ausnahme #3048) -- behoben: Trip ohne gespeicherte
    ``metrics`` liefert auf der Mail-Seite dieselbe Standardfolge wie der
    Editor (``editor_standard.json``, Register-Rangfolge ``trip_default_rank``);
    in der echten Mail belegt durch
    ``test_einstellung_gleich_mail_trip.py::test_n1_altbestand_ohne_metrics``."""
    _pruefe(python_trip_tabellen, "trip_tabellen", _zustand("trip_tabellen", "altbestand_ohne_metrics"))


def test_python_seite_trip_tabellen_leere_liste_altbestand():
    """#3047 H5 (#1394 Fall A): ``metrics: []`` ist Altbestand, nicht bewusst
    leer -- die Mail zeigt denselben Register-Standard wie der Editor
    (``metricsEditor.computeInitialBuckets`` fuer ``[]``)."""
    _pruefe(python_trip_tabellen, "trip_tabellen", _zustand("trip_tabellen", "altbestand_leere_liste"))


def test_python_seite_trip_tabellen_bewusst_leer_alle_aus():
    """#3047 H5 (#1394 Fall B): bewusst leer heisst alle Eintraege
    ``enabled:false`` -- so speichert der Editor eine Leerauswahl. Mail-Liste
    leer, kein Rueckfall auf den Standardsatz."""
    _pruefe(python_trip_tabellen, "trip_tabellen", _zustand("trip_tabellen", "bewusst_leer_alle_aus"))


@pytest.mark.parametrize("zustand", _gespeicherte("trip_tabellen"))
def test_python_seite_trip_tabellen_gespeichert(zustand):
    _pruefe(python_trip_tabellen, "trip_tabellen", zustand)


# ── Trip-Ausblick ──────────────────────────────────────────────────────────────

def test_python_seite_trip_ausblick_standard():
    _pruefe(python_trip_ausblick, "trip_ausblick", _zustand("trip_ausblick", "nie_eingestellt"))


def test_python_seite_trip_ausblick_bewusst_leer_alle_aus():
    """#3047 J4 (Konzept §5 Punkt 8): Grundauswahl bewusst leer (alle
    ``enabled:false``) -> der Ausblick entfaellt; seit J3 liefert die Mail
    keine Ausblick-Spalte -- dasselbe Soll ``[]`` wie der Editor (J1)."""
    _pruefe(python_trip_ausblick, "trip_ausblick", _zustand("trip_ausblick", "bewusst_leer_alle_aus"))


def test_python_seite_trip_ausblick_grundauswahl_ohne_ausblick():
    """#3047 N2: Grundauswahl ohne ausblickfaehige Groesse -> der Ausblick
    entfaellt (keine festen Spalten), dasselbe Soll ``[]`` wie der Editor."""
    _pruefe(python_trip_ausblick, "trip_ausblick", _zustand("trip_ausblick", "grundauswahl_ohne_ausblick"))


@pytest.mark.parametrize("zustand", _gespeicherte("trip_ausblick"))
def test_python_seite_trip_ausblick_gespeichert(zustand):
    _pruefe(python_trip_ausblick, "trip_ausblick", zustand)


# ── Orte-Vergleichstabelle ─────────────────────────────────────────────────────

def test_python_seite_orte_vergleichstabelle_standard():
    _pruefe(python_orte_vergleichstabelle, "orte_vergleichstabelle",
            _zustand("orte_vergleichstabelle", "nie_eingestellt"))


def test_python_seite_orte_vergleichstabelle_grundauswahl_bewusst_leer():
    """#3047 N2: ``active_metrics: []`` ist bewusst leer (wie Trip, alle aus) --
    die Vergleichstabelle hat keine Metrik-Zeile."""
    _pruefe(python_orte_vergleichstabelle, "orte_vergleichstabelle",
            _zustand("orte_vergleichstabelle", "grundauswahl_bewusst_leer"))


@pytest.mark.parametrize("zustand", _gespeicherte("orte_vergleichstabelle"))
def test_python_seite_orte_vergleichstabelle_gespeichert(zustand):
    _pruefe(python_orte_vergleichstabelle, "orte_vergleichstabelle", zustand)


# ── Orte-Stundenverlauf ────────────────────────────────────────────────────────

def test_python_seite_orte_stundenverlauf_standard():
    _pruefe(python_orte_stundenverlauf, "orte_stundenverlauf",
            _zustand("orte_stundenverlauf", "nie_eingestellt"))


def test_python_seite_orte_stundenverlauf_standard_mit_grundauswahl():
    """#3047 H1 (Konzept §5.8): nie eingestellt mit Grundauswahl -> deren
    stuendlich verfuegbare Groessen in deren Folge."""
    _pruefe(python_orte_stundenverlauf, "orte_stundenverlauf",
            _zustand("orte_stundenverlauf", "nie_eingestellt_mit_grundauswahl"))


def test_python_seite_orte_stundenverlauf_grundauswahl_gleich_vorgabe():
    """#3047 J1: gespeicherte Grundauswahl, die genau der Vorgabe gleicht, ist
    gespeichert -- Grundauswahl-Regel (stuendliche Groessen in deren Folge)."""
    _pruefe(python_orte_stundenverlauf, "orte_stundenverlauf",
            _zustand("orte_stundenverlauf", "grundauswahl_gleich_vorgabe"))


def test_python_seite_orte_stundenverlauf_grundauswahl_bewusst_leer():
    """#3047 N2: ``active_metrics: []`` -> der Stundenverlauf entfaellt (keine
    Spalte), wie beim Trip; nicht die Vorgabemenge."""
    _pruefe(python_orte_stundenverlauf, "orte_stundenverlauf",
            _zustand("orte_stundenverlauf", "grundauswahl_bewusst_leer"))


@pytest.mark.parametrize("zustand", _gespeicherte("orte_stundenverlauf"))
def test_python_seite_orte_stundenverlauf_gespeichert(zustand):
    _pruefe(python_orte_stundenverlauf, "orte_stundenverlauf", zustand)


# ── Orte-Ausblick ──────────────────────────────────────────────────────────────

def test_python_seite_orte_ausblick_standard():
    _pruefe(python_orte_ausblick, "orte_ausblick", _zustand("orte_ausblick", "nie_eingestellt"))


def test_python_seite_orte_ausblick_standard_mit_grundauswahl():
    _pruefe(python_orte_ausblick, "orte_ausblick",
            _zustand("orte_ausblick", "nie_eingestellt_mit_grundauswahl"))


def test_python_seite_orte_ausblick_grundauswahl_gleich_vorgabe():
    """#3047 J1: gespeicherte Grundauswahl = Vorgabe -> die ganze Grundauswahl."""
    _pruefe(python_orte_ausblick, "orte_ausblick",
            _zustand("orte_ausblick", "grundauswahl_gleich_vorgabe"))


def test_python_seite_orte_ausblick_grundauswahl_bewusst_leer():
    """#3047 N2 (loest J4/D4 ab): ``active_metrics: []`` ist beim Ortsvergleich
    wie beim Trip bewusst leer -- der Ausblick entfaellt, keine festen Spalten."""
    _pruefe(python_orte_ausblick, "orte_ausblick",
            _zustand("orte_ausblick", "grundauswahl_bewusst_leer"))


@pytest.mark.parametrize("zustand", _gespeicherte("orte_ausblick"))
def test_python_seite_orte_ausblick_gespeichert(zustand):
    _pruefe(python_orte_ausblick, "orte_ausblick", zustand)


# ── Waechter gegen Katalog-Drift (#3047 H4, Nachpruefung Punkt 8) ──────────────
#
# ``editor_standard.json`` traegt unter ``kataloge`` aufgezeichnete Antworten von
# ``GET /api/metrics`` (Trip) und ``GET /api/compare/metrics`` (Orte), gekuerzt auf
# die Felder, die Editor-Seite und Python-Seite lesen. Aendert sich das Register
# (neue Groesse, anderer Rang, anderer Schluessel), rechnen beide Seiten sonst
# still gegen einen veralteten Katalog. Die Live-Antwort kommt aus der ECHTEN
# Router-Funktion (ohne Netz, ohne App-Start); verglichen wird je Gruppe die
# vollstaendige Eintragsfolge, projiziert auf die eingefrorenen Felder.


def katalog_drift(name: str, eingefroren: dict[str, list[dict]],
                  live: dict[str, list[dict]]) -> list[str]:
    """Abweichungen eines eingefrorenen Katalogs (Gruppe -> Eintraege) von der
    Live-Antwort, je als lesbare Zeile; leer = kein Drift. Reine Funktion."""
    fehler: list[str] = []
    for gruppe in sorted(set(eingefroren) | set(live)):
        if gruppe not in live:
            fehler.append(f"{name}: Gruppe {gruppe!r} gibt es in der API nicht mehr")
            continue
        if gruppe not in eingefroren:
            fehler.append(f"{name}: API-Gruppe {gruppe!r} fehlt im eingefrorenen Katalog")
            continue
        alt = eingefroren[gruppe]
        felder = sorted(set().union(*(e.keys() for e in alt))) if alt else ["id"]
        neu = [{f: e.get(f) for f in felder} for e in live[gruppe]]
        if neu == alt:
            continue
        kennung = "key" if "key" in felder else "id"
        ids_alt = [e.get(kennung) for e in alt]
        ids_neu = [e.get(kennung) for e in neu]
        if ids_alt != ids_neu:
            fehler.append(f"{name}[{gruppe}]: Eintragsfolge eingefroren {ids_alt} != API {ids_neu}")
            continue
        for a, n in zip(alt, neu):
            diff = {f: (a.get(f), n.get(f)) for f in felder if a.get(f) != n.get(f)}
            if diff:
                fehler.append(f"{name}[{gruppe}] {a.get(kennung)}: (eingefroren, API) {diff}")
    return fehler


def _live_trip_katalog() -> dict[str, list[dict]]:
    from api.routers.config import get_metrics

    return get_metrics()


def _live_orte_katalog() -> dict[str, list[dict]]:
    from api.routers.compare import get_compare_metrics

    # #2989: ``default_order`` ist eine Schluesselliste, keine Eintragsgruppe;
    # sie bewacht tests/tdd/test_2989_compare_default_order.py (CV2-Folge + Menge).
    antwort = get_compare_metrics(lang=None)
    return {k: v for k, v in antwort.items() if k != "default_order"}


_DRIFT_HINWEIS = ("eingefrorene Kataloge in tests/fixtures/einstellung_gleich_mail/"
                  "editor_standard.json neu aufzeichnen (gleiche Felder) und die "
                  "erwarteten Standardfolgen beider Seiten pruefen")


def test_katalog_drift_trip_api_metrics():
    """Eingefrorener ``/api/metrics``-Katalog == aktuelle Router-Antwort."""
    fehler = katalog_drift("trip_api_metrics", DATEN["kataloge"]["trip_api_metrics"],
                           _live_trip_katalog())
    assert not fehler, "Katalog-Drift:\n  " + "\n  ".join(fehler) + f"\n-> {_DRIFT_HINWEIS}"


def test_katalog_drift_orte_api_compare_metrics():
    """Eingefrorener ``/api/compare/metrics``-Katalog == aktuelle Router-Antwort."""
    fehler = katalog_drift("orte_api_compare_metrics",
                           DATEN["kataloge"]["orte_api_compare_metrics"], _live_orte_katalog())
    assert not fehler, "Katalog-Drift:\n  " + "\n  ".join(fehler) + f"\n-> {_DRIFT_HINWEIS}"


def test_katalog_drift_selbsttest_meldet_klar():
    """Der Waechter schlaegt bei jeder Drift-Art an und nennt Gruppe, Eintrag und
    Feld (synthetische Abweichungen auf Kopien der eingefrorenen Daten)."""
    import copy

    trip = DATEN["kataloge"]["trip_api_metrics"]
    live = _live_trip_katalog()
    rang = copy.deepcopy(trip)
    rang["wind"][1]["trip_default_rank"] = 99
    assert any("[wind] gust" in z and "trip_default_rank" in z
               for z in katalog_drift("t", rang, live))
    weniger = copy.deepcopy(trip)
    weniger["wind"].pop()
    assert any("Eintragsfolge" in z for z in katalog_drift("t", weniger, live))
    ohne_gruppe = copy.deepcopy(trip)
    del ohne_gruppe["winter"]
    assert any("'winter' fehlt" in z for z in katalog_drift("t", ohne_gruppe, live))
    orte = copy.deepcopy(DATEN["kataloge"]["orte_api_compare_metrics"])
    orte["metrics"][0]["hourlyDefault"] = not orte["metrics"][0]["hourlyDefault"]
    assert any("hourlyDefault" in z for z in katalog_drift("o", orte, _live_orte_katalog()))

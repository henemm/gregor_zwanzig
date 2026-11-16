"""#3047 Paket D: Editor-Standard = Mail-Standard, PYTHON-Seite (AC-13, AC-4, AC-21).

SPEC: docs/specs/modules/feat_3047_einstellung_gleich_mail_pruefkatalog.md §5, §7
Konzept: docs/context/einstellungen_neu.md §5 Punkt 6 und 8

Je Liste (Trip-Tabellen, Trip-Ausblick, Orte-Vergleichstabelle, Orte-Stundenverlauf,
Orte-Ausblick) laeuft die ECHTE Python-Aufloesung mit der Eingabe aus
``tests/fixtures/einstellung_gleich_mail/editor_standard.json`` bis an die Stelle,
an der die Mail ihre Spalten bzw. Zeilen festlegt (Spaltenkopf des Ausblicks,
``_visible_hour_metrics``, ``_visible_metrics``, ``resolve_metric_col_order``).
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

import dataclasses
import html
import json
import re
from pathlib import Path

import pytest

from app.ampel import resolve_ampel
from app.loader import _parse_display_config
from app.metric_catalog import get_all_metrics
from output.renderers.compare_metric_ids import FRONTEND_TO_RENDERER_METRIC_ID
from output.renderers.compare_outlook_metric_ids import resolve_trip_outlook_metrics
from output.renderers.email.compare_html import (
    _hour_zeilen,
    _visible_hour_metrics,
    _visible_metrics,
)
from output.renderers.email.helpers import resolve_metric_col_order
from output.renderers.email.outlook import render_outlook_table
from services.report_config_resolver import resolve_compare_render_options

FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "fixtures" / "einstellung_gleich_mail" / "editor_standard.json"
)
DATEN = json.loads(FIXTURE.read_text(encoding="utf-8"))
LISTEN = DATEN["listen"]


def _zustand(liste: str, zustand_id: str) -> dict:
    return next(z for z in LISTEN[liste]["zustaende"] if z["id"] == zustand_id)


def _gespeicherte(liste: str) -> list:
    return [
        pytest.param(z, id=z["id"])
        for z in LISTEN[liste]["zustaende"]
        if z["id"].startswith("gespeichert")
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

def python_trip_tabellen(eingabe: dict) -> list[str]:
    """E-Mail-Spaltenfolge der Stundentabelle: Loader -> Kanal-Kaskade
    (``get_metrics_for_channel``, wie ``trip_report.py:140-157``) ->
    ``resolve_metric_col_order`` (geteilt von html.py und plain.py)."""
    dc = _parse_display_config(eingabe["display_config"])
    email = [dataclasses.replace(mc, enabled=True)
             for mc in dc.get_metrics_for_channel("email", "evening")]
    kollabiert = dataclasses.replace(dc, metrics=email)
    abbildung = _col_key_zu_kennung()
    return [abbildung[k] for k in resolve_metric_col_order(kollabiert)]


def python_trip_ausblick(eingabe: dict) -> list[str]:
    dc = _parse_display_config(eingabe["display_config"])
    return _ausblick_spalten(resolve_trip_outlook_metrics(dc, "evening"))


def _orte_optionen(eingabe: dict):
    preset = {"id": "pruef-3047", **eingabe}
    return preset, resolve_compare_render_options(preset)


def python_orte_vergleichstabelle(eingabe: dict) -> list[str]:
    preset, optionen = _orte_optionen(eingabe)
    zeilen = _visible_metrics(
        optionen.enabled_metrics_by_channel["email"], "de", ampel=resolve_ampel(preset),
    )
    katalog_schluessel = {r: k for k, r in FRONTEND_TO_RENDERER_METRIC_ID.items()}
    return [katalog_schluessel[z["key"]] for z in zeilen if z["key"] != "warn"]


def python_orte_stundenverlauf(eingabe: dict) -> list[str]:
    _preset, optionen = _orte_optionen(eingabe)
    return [z["metric_id"] for z in _visible_hour_metrics(optionen.hourly_metrics, _hour_zeilen())]


def python_orte_ausblick(eingabe: dict) -> list[str]:
    _preset, optionen = _orte_optionen(eingabe)
    return _ausblick_spalten(optionen.outlook_metrics)


def _pruefe(seite, liste: str, zustand: dict) -> None:
    ist = seite(zustand["eingabe"])
    assert ist == zustand["erwartet"], (
        f"Python-Seite {liste}/{zustand['id']}: Mail liefert {ist}, "
        f"editor_standard.json erwartet {zustand['erwartet']}"
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


@pytest.mark.parametrize("zustand", _gespeicherte("trip_ausblick"))
def test_python_seite_trip_ausblick_gespeichert(zustand):
    _pruefe(python_trip_ausblick, "trip_ausblick", zustand)


# ── Orte-Vergleichstabelle ─────────────────────────────────────────────────────

def test_python_seite_orte_vergleichstabelle_standard():
    _pruefe(python_orte_vergleichstabelle, "orte_vergleichstabelle",
            _zustand("orte_vergleichstabelle", "nie_eingestellt"))


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

    return get_compare_metrics(lang=None)


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

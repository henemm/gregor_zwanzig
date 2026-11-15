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
    """N1 -- Ausnahme mit Verweis #3048 (dokumentiert den IST-Zustand).

    Trip ohne gespeicherte ``metrics``: die Mail-Seite liefert heute KEINE
    Wertspalte (in der echten Mail belegt,
    ``test_einstellung_gleich_mail_trip.py::test_n1_altbestand_ohne_metrics``),
    der Editor zeigt die in ``editor_standard.json`` festgelegte Standardfolge.
    Die Behebung betrifft alle Kanaele (Telegram AC-S4-13, #1199) und wird in
    #3048 umgesetzt; wird dieser Test rot, ist #3048 wirksam und der Fall auf
    ``_pruefe`` (Soll = ``erwartet``) zurueckzustellen."""
    zustand = _zustand("trip_tabellen", "altbestand_ohne_metrics")
    assert zustand["erwartet"], "Editor-Soll fuer N1 fehlt in editor_standard.json"
    assert python_trip_tabellen(zustand["eingabe"]) == [], (
        "Ist-Zustand #3048 hat sich geaendert -- Fall auf gruen umstellen")


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


@pytest.mark.parametrize("zustand", _gespeicherte("orte_stundenverlauf"))
def test_python_seite_orte_stundenverlauf_gespeichert(zustand):
    _pruefe(python_orte_stundenverlauf, "orte_stundenverlauf", zustand)


# ── Orte-Ausblick ──────────────────────────────────────────────────────────────

def test_python_seite_orte_ausblick_standard():
    _pruefe(python_orte_ausblick, "orte_ausblick", _zustand("orte_ausblick", "nie_eingestellt"))


def test_python_seite_orte_ausblick_standard_mit_grundauswahl():
    _pruefe(python_orte_ausblick, "orte_ausblick",
            _zustand("orte_ausblick", "nie_eingestellt_mit_grundauswahl"))


@pytest.mark.parametrize("zustand", _gespeicherte("orte_ausblick"))
def test_python_seite_orte_ausblick_gespeichert(zustand):
    _pruefe(python_orte_ausblick, "orte_ausblick", zustand)

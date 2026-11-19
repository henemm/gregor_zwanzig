"""Nachzug zum Lese-Endpoint der Tabelle "Was steht wo" (#3122 B2b).

SPEC: docs/specs/modules/feat_3122_was_steht_wo.md Teil A Nr. 1, 9, Teil B
Nr. 11, 12; AC-14, AC-16, AC-17, AC-31.

* Punkt 2: Abos ohne gespeicherte Tabelle (``stored: false``) bekommen
  dieselbe Guete wie gespeicherte: SMS-Beispielwerte, "passt nicht mehr",
  Legende -- auch Orte, deren Grundauswahl nie eingestellt wurde.
* Punkt 3: ``placements`` im GET ist der gespeicherte Stand; unveraendert
  zurueckgeschrieben verliert er nichts (reservierte und kuenftige Felder).
* Punkt 4: Kuerzel ``NS24+`` hat eine Bedeutung; ``sms_example.overflow``
  entfaellt seit #3172 (ADR-0125) fuer Orte wie fuer Trip -- die Orte-SMS
  kuerzt still vom Listenende, ein Rest-Zaehler ``+N`` existiert nicht mehr.

Kern-Schicht: echte Dateien, echte Renderer, fester Beispiel-Datensatz, kein
Mock. Orakel aus dem Versandweg, nicht aus der Antwort.
"""
from __future__ import annotations

import json
import re

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tests.tdd.test_placements_tabelle_endpoint import (
    NUTZER_A, _ok, _orte, _orte_fehlt_in_sms, _orte_kuerzel_in_sms, _orte_versand_sms,
    _schreibe, _sms_an, _sprache, _trip, _trip_fehlt_in_sms, _trip_kuerzel_in_sms,
    _trip_versand_sms,
)


@pytest.fixture
def client():
    from api.routers import placements

    app = FastAPI()
    app.include_router(placements.router)
    return TestClient(app)


def _markiert(antwort) -> set[str]:
    return {z["metric_id"] for z in antwort["rows"]
            if z["cells"]["sms"]["mark"] == "passt_nicht_mehr"}


def _orte_nie_eingestellt(kennung: str, anzahl: int):
    """Orte-Abo ohne ``active_metrics`` (Grundauswahl nie eingestellt)."""
    pfad = _orte(NUTZER_A, kennung, anzahl=anzahl)
    daten = json.loads(pfad.read_text())
    daten["display_config"] = {}
    pfad.write_text(json.dumps(daten), encoding="utf-8")
    return pfad


# ---------------------------------------------------------------------------
# Punkt 2: stored false -- Marken, SMS-Beispielwerte, Legende
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("anzahl", [3, 1])
@pytest.mark.parametrize("grund", ["gewaehlt", "nie_eingestellt"])
def test_orte_ohne_tabelle_marken_beispiele_und_legende(client, anzahl, grund):
    kennung = f"o-p2-{grund}-{anzahl}"
    if grund == "gewaehlt":
        _orte(NUTZER_A, kennung, anzahl=anzahl)
    else:
        _orte_nie_eingestellt(kennung, anzahl)
    antwort = _ok(client, kennung, "vergleich")
    versand = _orte_versand_sms(NUTZER_A, kennung)

    assert antwort["stored"] is False
    assert antwort["sms_example"]["text"] == versand
    fehlend = {m for m in _sms_an(antwort) if _orte_fehlt_in_sms(versand, m)}
    # #3172: ein Ort passt ohne Namen und Kopf ganz in 160 Zeichen.
    assert fehlend or anzahl == 1, "Datensatz muss die SMS ueberlaufen lassen"
    assert _markiert(antwort) == fehlend
    worte = set(versand.split(" "))
    for zeile in antwort["rows"]:
        sms = zeile["cells"]["sms"]
        if sms["state"] == "on" and zeile["metric_id"] not in fehlend:
            # Temperatur: Tiefst-/Hoechstwert stehen als Bereich ``D15/19`` (#3172)
            assert sms["example"] and set(sms["example"].split(" ")) <= worte, zeile["metric_id"]
    gesendet = _orte_kuerzel_in_sms(versand)
    in_legende = {e["kuerzel"] for e in antwort["legend"]["metrics"]}
    assert gesendet and gesendet <= in_legende, gesendet - in_legende


def test_trip_ohne_tabelle_marken_beispiele_und_legende(client):
    from tests.tdd.test_placements_tabelle_endpoint import TRIP_GRUND

    _trip(NUTZER_A, "t-p2", grund=TRIP_GRUND)
    antwort = _ok(client, "t-p2", "route")
    versand = _trip_versand_sms(NUTZER_A, "t-p2")

    assert antwort["stored"] is False
    assert antwort["sms_example"]["text"] == versand
    fehlend = {m for m in _sms_an(antwort) if _trip_fehlt_in_sms(versand, m)}
    assert fehlend, "Datensatz muss die SMS ueberlaufen lassen"
    assert _markiert(antwort) == fehlend
    for zeile in antwort["rows"]:
        sms = zeile["cells"]["sms"]
        if sms["state"] == "on" and zeile["metric_id"] not in fehlend:
            assert sms["example"] and sms["example"] in versand, zeile["metric_id"]
    gesendet = _trip_kuerzel_in_sms(versand)
    assert gesendet <= {e["kuerzel"] for e in antwort["legend"]["metrics"]}


@pytest.mark.parametrize("kind", ["route", "vergleich"])
def test_ohne_tabelle_gleiche_guete_wie_nach_dem_speichern(client, kind):
    """Dieselbe Tabelle einmal umgerechnet (stored false), einmal gespeichert:
    Beispielwerte, Marken, Legende und SMS-Beispiel sind gleich. (Orte "nie
    eingestellt" nicht: dort ordnet die Umrechnung Tageshoechst/-tiefst
    zusammen -- gemeldete Aenderung ``auswertungen_gekoppelt``, die SMS
    unterscheidet sich also bewusst.)"""
    if kind == "route":
        from tests.tdd.test_placements_tabelle_endpoint import TRIP_GRUND

        pfad = _trip(NUTZER_A, "t-p2g", grund=TRIP_GRUND)
        kennung = "t-p2g"
    else:
        pfad = _orte(NUTZER_A, "o-p2g", anzahl=3)
        kennung = "o-p2g"
    vorher = _ok(client, kennung, kind)
    daten = json.loads(pfad.read_text())
    daten["display_config"]["placements"] = vorher["placements"]
    pfad.write_text(json.dumps(daten), encoding="utf-8")
    nachher = _ok(client, kennung, kind)
    for feld in ("rows", "legend", "sms_example"):
        assert nachher[feld] == vorher[feld], feld


# ---------------------------------------------------------------------------
# Punkt 3: GET -> PUT desselben Objekts verliert nichts
# ---------------------------------------------------------------------------

GESPEICHERT_MIT_UNBEKANNTEM = {
    "version": 1,
    "zukunft_oben": {"a": [1, 2]},
    "rows": [
        {"metric_id": "wind", "places": {"premium_sms": False, "sms": True, "telegram": False},
         "formats": {"email": "raw", "sms": "simplified"}, "zukunft_zeile": "x"},
        {"metric_id": "gibt_es_nicht", "places": {"email": False}},
        "kaputt",
        {"metric_id": "gust", "places": {"premium_sms": True}},
        {"metric_id": "wind", "places": {"email": False}},
    ],
    "outlook_reports": ["evening", "spaeter"],
}


def _go_put(pfad, placements) -> None:
    """``store.SaveBriefingPlacements``: nur ``display_config.placements``."""
    daten = json.loads(pfad.read_text())
    dc = daten.get("display_config") if isinstance(daten.get("display_config"), dict) else {}
    dc["placements"] = placements
    daten["display_config"] = dc
    pfad.write_text(json.dumps(daten), encoding="utf-8")


@pytest.mark.parametrize("kind", ["route", "vergleich"])
def test_get_put_desselben_objekts_ist_wertgleich(client, kind):
    if kind == "route":
        pfad = _trip(NUTZER_A, "t-p3", placements=GESPEICHERT_MIT_UNBEKANNTEM)
        kennung = "t-p3"
    else:
        pfad = _orte(NUTZER_A, "o-p3", placements=GESPEICHERT_MIT_UNBEKANNTEM)
        kennung = "o-p3"
    vorher = json.loads(pfad.read_text())
    antwort = _ok(client, kennung, kind)
    assert antwort["stored"] is True
    _go_put(pfad, antwort["placements"])
    assert json.loads(pfad.read_text()) == vorher
    # unlesbare Eintraege wirken weiter nicht: erste wind-Zeile zaehlt
    wind = next(z for z in antwort["rows"] if z["metric_id"] == "wind")
    assert wind["cells"]["telegram"]["state"] == "off"
    assert wind["cells"]["email"]["state"] == "on"
    assert "gibt_es_nicht" not in {z["metric_id"] for z in antwort["rows"]}


def test_ohne_tabelle_bleibt_placements_die_umrechnung(client):
    from app.loader import get_data_root, load_trip
    from services.placements import placements_from_legacy

    _trip(NUTZER_A, "t-p3u", grund=["wind", "gust"])
    antwort = _ok(client, "t-p3u", "route")
    trip = load_trip("t-p3u", data_dir=get_data_root(), user_id=NUTZER_A)
    assert antwort["stored"] is False
    assert antwort["placements"] == placements_from_legacy(
        trip.display_config, "trip", report_config=trip.report_config,
        enabled_reports=["morning", "evening"]).placements


# ---------------------------------------------------------------------------
# Punkt 4a: Kuerzel NS hat eine Bedeutung
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("lang", ["de", "en"])
def test_orte_legende_mit_neuschnee_hat_jede_bedeutung(client, lang):
    _sprache(NUTZER_A, lang)
    _orte(NUTZER_A, "o-ns", anzahl=1, grund=[
        {"metric_id": "fresh_snow", "aggregation": "sum"},
        {"metric_id": "wind", "aggregation": "max"}],
        placements={"version": 1, "rows": [{"metric_id": "fresh_snow"}]})
    antwort = _ok(client, "o-ns", "vergleich")
    legende = antwort["legend"]["metrics"]
    gesendet = _orte_kuerzel_in_sms(antwort["sms_example"]["text"])
    # #3172 (ADR-0125): dieselben Symbole wie die Trip-SMS (``NS24+0``).
    assert "NS24+" in gesendet, antwort["sms_example"]["text"]
    assert gesendet <= {e["kuerzel"] for e in legende}
    assert all(e["meaning"] for e in legende), legende
    _sprache(NUTZER_A, "de")


@pytest.mark.parametrize("lang", ["de", "en"])
def test_jedes_kuerzel_der_orte_sms_hat_eine_bedeutung(lang):
    """Jede Auswertung, die die Orte-SMS mit Kuerzel sendet (#3172: Symbole der
    Token-Zeile wie im Trip, ``orte_sms.orte_kuerzel_je_metrik``, ohne
    Doppelpunkt), hat im Katalog eine Bedeutung -- nicht nur die Faelle, die
    ein Beispiel-Abo trifft."""
    from app.metric_catalog import kuerzel_bedeutung
    from output.renderers.comparison import _RENDERER_TO_CATALOG_METRIC_ID
    from output.renderers.orte_sms import orte_kuerzel_je_metrik

    je_kuerzel = orte_kuerzel_je_metrik()
    paare = [(rid, cid, sym.rstrip(":")) for rid, cid in _RENDERER_TO_CATALOG_METRIC_ID.items()
             for sym, q in je_kuerzel.items() if q == cid]
    assert len({cid for _rid, cid, _k in paare}) >= 20, paare
    ohne = [p for p in paare if not kuerzel_bedeutung(p[1], p[2], lang)]
    assert not ohne, ohne


# ---------------------------------------------------------------------------
# Punkt 4b (abgeloest durch #3172, ADR-0125): kein Rest-Zaehler mehr
# ---------------------------------------------------------------------------

def _ortsteile(versand: str, orte: list[str]) -> list[str]:
    """Ortsteile der Versand-SMS ``O1 ... O2 ...`` (#3172, PO 2026-11-19: kein
    Kopf, keine Namen); die Nummern sind lueckenlos ``O1, O2, ...`` und
    nie groesser als die Zahl der Orte."""
    from tests.helpers.orte_sms import orte_nummern, orte_teile

    teile = orte_teile(versand)
    assert orte_nummern(versand) == list(range(1, len(teile) + 1)), versand
    assert len(teile) <= len(orte) and not any(n in versand for n in orte), versand
    return teile


@pytest.mark.parametrize("fall", ["drei_ueberlauf", "drei_ohne_ueberlauf", "ein_ort"])
def test_orte_sms_example_meldet_rest_zaehler(client, fall):
    """#3172 (ADR-0125): kein Feld ``overflow`` mehr, wie beim Trip; die
    SMS kuerzt still vom Listenende, kein Ortsteil traegt ``+N``, und alle
    gezeigten Orte tragen gleich viele Token."""
    from tests.tdd.test_placements_tabelle_endpoint import ORTSNAMEN

    if fall == "drei_ohne_ueberlauf":
        _orte(NUTZER_A, "o-p4", anzahl=3, grund=[{"metric_id": "wind", "aggregation": "max"}],
              placements={"version": 1, "rows": []})
        anzahl = 3
    else:
        anzahl = 3 if fall == "drei_ueberlauf" else 1
        _orte(NUTZER_A, "o-p4", anzahl=anzahl, placements={"version": 1, "rows": []})
    antwort = _ok(client, "o-p4", "vergleich")
    versand = antwort["sms_example"]["text"]
    teile = _ortsteile(versand, list(ORTSNAMEN[:anzahl]))
    assert "overflow" not in antwort["sms_example"]
    for teil in teile:
        assert not re.search(r"(?:^| )[+?]\d+(?= |$)", teil), f"Zaehler im Ortsteil: {teil!r}"
    zahl = {len(t.split(" ")) - 1 for t in teile}
    assert len(zahl) == 1, f"ungleiche Zeilenzahl je Ort: {versand!r}"
    if fall == "drei_ohne_ueberlauf":
        assert zahl == {1}, versand


VIELE_ORTE = ("Innsbruck", "Lienz", "Kufstein", "Imst", "Landeck", "Reutte", "Schwaz",
              "Telfs", "Wattens") + tuple(f"Ortschaft{i}" for i in range(10, 31))


@pytest.mark.parametrize("anzahl", [8, 30])
def test_orte_entfallene_orte_zaehlen_nicht_im_rest_zaehler(client, anzahl):
    """Passen nicht alle Orte, endet die SMS auf ``+k Orte`` -- erst wenn je Ort
    nur noch die erste Listenzeile steht (#3172, ADR-0125); gezeigte plus
    entfallene Orte ergeben alle; kein Feld ``overflow``."""
    kennung = f"o-p4-viele-{anzahl}"
    _orte(NUTZER_A, kennung, anzahl=anzahl, namen=VIELE_ORTE,
          placements={"version": 1, "rows": []})
    antwort = _ok(client, kennung, "vergleich")
    versand = antwort["sms_example"]["text"]
    entfallen = re.search(r" \+(\d+) Orte$", versand)
    teile = _ortsteile(versand, list(VIELE_ORTE[:anzahl]))
    assert len(teile) + (int(entfallen.group(1)) if entfallen else 0) == anzahl, versand
    assert "overflow" not in antwort["sms_example"]
    if entfallen:
        assert all(len(t.split(" ")) == 2 for t in teile), versand
    if anzahl == 30:
        # #3172: die Orte-SMS ist kuerzer (keine Namen, 160 Zeichen) -- erst
        # 30 Orte lassen sie ueberlaufen.
        assert entfallen, f"Vorbedingung: 30 Orte passen nicht: {versand!r}"


def test_trip_sms_example_ohne_rest_zaehler(client):
    _trip(NUTZER_A, "t-p4", placements={"version": 1, "rows": []})
    assert "overflow" not in _ok(client, "t-p4", "route")["sms_example"]


def test_orte_ohne_ort_hat_kein_sms_beispiel(client):
    pfad = _orte(NUTZER_A, "o-p4-leer", anzahl=1, placements={"version": 1, "rows": []})
    daten = json.loads(pfad.read_text())
    daten["location_ids"] = []
    _schreibe(NUTZER_A, "briefings", "o-p4-leer", daten)
    assert _ok(client, "o-p4-leer", "vergleich")["sms_example"] is None

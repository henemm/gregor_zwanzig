"""Nachzug zum Lese-Endpoint der Tabelle "Was steht wo" (#3122 B2b).

SPEC: docs/specs/modules/feat_3122_was_steht_wo.md Teil A Nr. 1, 9, Teil B
Nr. 11, 12; AC-14, AC-16, AC-17, AC-31.

* Punkt 2: Abos ohne gespeicherte Tabelle (``stored: false``) bekommen
  dieselbe Guete wie gespeicherte: SMS-Beispielwerte, "passt nicht mehr",
  Legende -- auch Orte, deren Grundauswahl nie eingestellt wurde.
* Punkt 3: ``placements`` im GET ist der gespeicherte Stand; unveraendert
  zurueckgeschrieben verliert er nichts (reservierte und kuenftige Felder).
* Punkt 4: Kuerzel ``NS`` hat eine Bedeutung; ``sms_example.overflow`` sagt,
  bei wie vielen Orten ein Rest-Zaehler ``+N`` steht.

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
    assert fehlend, "Datensatz muss die SMS ueberlaufen lassen"
    assert _markiert(antwort) == fehlend
    worte = set(versand.split(" "))
    for zeile in antwort["rows"]:
        sms = zeile["cells"]["sms"]
        if sms["state"] == "on" and zeile["metric_id"] not in fehlend:
            # Temperatur: D- und L-Zelle stehen bei "nie eingestellt" getrennt
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
    assert "NS" in gesendet, antwort["sms_example"]["text"]
    assert gesendet <= {e["kuerzel"] for e in legende}
    assert all(e["meaning"] for e in legende), legende
    _sprache(NUTZER_A, "de")


@pytest.mark.parametrize("lang", ["de", "en"])
def test_jedes_kuerzel_der_orte_sms_hat_eine_bedeutung(lang):
    """Jede Auswertung, die die Orte-SMS mit Kuerzel sendet (Kuerzel wie
    ``_sms_metric_cell``: ``kurzform_kuerzel`` der Katalog-ID), hat im Katalog
    eine Bedeutung -- nicht nur die Faelle, die ein Beispiel-Abo trifft."""
    from app.metric_catalog import kuerzel_bedeutung, kurzform_kuerzel
    from output.renderers.comparison import _RENDERER_TO_CATALOG_METRIC_ID

    ohne = [(rid, cid, kurzform_kuerzel(cid))
            for rid, cid in _RENDERER_TO_CATALOG_METRIC_ID.items()
            if kurzform_kuerzel(cid) and not kuerzel_bedeutung(cid, kurzform_kuerzel(cid), lang)]
    assert not ohne, ohne


# ---------------------------------------------------------------------------
# Punkt 4b: Rest-Zaehler +N je Ort in sms_example
# ---------------------------------------------------------------------------

def _rest_zaehler_soll(versand: str, orte: list[str]) -> list:
    """Orakel: je Ortsteil der Versand-SMS (Kopf ``Vergleich TT.MM.: ``,
    Trenner ``; ``, die Testnamen enthalten keinen) die Zahl hinter ``+`` als
    eigenes Wort, sonst ``None``."""
    rumpf = re.sub(r" \+\d+ Orte$", "", versand.split(": ", 1)[1])
    out = []
    for teil in rumpf.split("; "):
        assert teil.split(" ")[0] in orte, teil
        treffer = re.findall(r"(?:^| )\+(\d+)(?= |$)", teil)
        out.append(int(treffer[0]) if treffer else None)
    return out


@pytest.mark.parametrize("fall", ["drei_ueberlauf", "drei_ohne_ueberlauf", "ein_ort"])
def test_orte_sms_example_meldet_rest_zaehler(client, fall):
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
    soll = _rest_zaehler_soll(versand, list(ORTSNAMEN[:anzahl]))
    ueberlauf = antwort["sms_example"]["overflow"]
    assert ueberlauf["per_location"] == soll
    assert ueberlauf["locations"] == sum(1 for n in soll if n)
    if fall == "drei_ohne_ueberlauf":
        assert ueberlauf["locations"] == 0
    else:
        assert ueberlauf["locations"] >= 1


def test_trip_sms_example_ohne_rest_zaehler(client):
    _trip(NUTZER_A, "t-p4", placements={"version": 1, "rows": []})
    assert _ok(client, "t-p4", "route")["sms_example"]["overflow"] is None


def test_orte_ohne_ort_hat_kein_sms_beispiel(client):
    pfad = _orte(NUTZER_A, "o-p4-leer", anzahl=1, placements={"version": 1, "rows": []})
    daten = json.loads(pfad.read_text())
    daten["location_ids"] = []
    _schreibe(NUTZER_A, "briefings", "o-p4-leer", daten)
    assert _ok(client, "o-p4-leer", "vergleich")["sms_example"] is None

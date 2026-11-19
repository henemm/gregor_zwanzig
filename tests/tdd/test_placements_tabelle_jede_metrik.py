"""Tabelle "Was steht wo" zeigt jede Metrik der Grundauswahl (#3154, Epic #3122).

SPEC: docs/specs/modules/feat_3122_was_steht_wo.md Teil B Nr. 11 (``rows``:
alle Zeilen der Grundauswahl), AC-16; Grundauswahl je Briefing-Typ
(``morning_enabled``/``evening_enabled``) wird wie heute ausgewertet, hat
aber keine Bedienung in der Tabelle.

Fehler aus Nutzersicht: Golden C fuehrt ``cloud_low`` nur morgens
(``evening_enabled: false``); Telegram und SMS geben es aus, die Tabelle
liess die Zeile weg -- sie las die Grundauswahl nur des Abend-Briefings,
die Umrechnung und das gespeicherte ``placements`` fuehren dagegen beide
Briefing-Typen.

Kern-Schicht: echte Dateien in der isolierten Datenwurzel, echter Router,
eingefrorene Golden-Fixtures und -Erwartungen, kein Mock.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tests.tdd.test_placements_tabelle_endpoint import NUTZER_A, NUTZER_B, _ok, _orte, _schreibe

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "einstellung_auslieferung"
GOLDEN = sorted(p.stem.removeprefix("golden_") for p in FIXTURES.glob("golden_*.json"))


@pytest.fixture
def client():
    from api.routers import placements

    app = FastAPI()
    app.include_router(placements.router)
    return TestClient(app)


def _golden_trip(name: str, user: str) -> tuple[str, Path]:
    daten = json.loads((FIXTURES / f"golden_{name}.json").read_text(encoding="utf-8"))
    kennung = f"golden-{name}-3154"
    daten["id"] = kennung
    return kennung, _schreibe(user, "briefings", kennung, daten)


def _zurueckschreiben(pfad: Path, placements: dict) -> None:
    """Unveraendertes Zurueckschreiben (wie der PUT der Karte): Read-Modify-Write."""
    daten = json.loads(pfad.read_text(encoding="utf-8"))
    daten["display_config"]["placements"] = copy.deepcopy(placements)
    pfad.write_text(json.dumps(daten), encoding="utf-8")


def _zeilen_ids(antwort: dict) -> list[str]:
    return [z["metric_id"] for z in antwort["rows"]]


def _placements_ids(placements: dict) -> set[str]:
    return {r["metric_id"] for r in placements["rows"]}


def test_golden_c_cloud_low_hat_eine_zeile_an_telegram_und_sms(client):
    """Der gemeldete Fall: cloud_low (nur morgens) steht in Telegram und SMS."""
    kennung, _pfad = _golden_trip("c", NUTZER_A)
    antwort = _ok(client, kennung, "route")
    assert "cloud_low" in _zeilen_ids(antwort)
    zeile = next(z for z in antwort["rows"] if z["metric_id"] == "cloud_low")
    assert zeile["cells"]["telegram"]["state"] == "on"
    assert zeile["cells"]["sms"]["state"] == "on"
    # Abends nicht gewaehlt heisst nicht "passt nicht mehr".
    assert zeile["cells"]["sms"]["mark"] is None


@pytest.mark.parametrize("name", GOLDEN)
def test_golden_zeilen_gleich_placements_vor_und_nach_dem_zurueckschreiben(client, name):
    kennung, pfad = _golden_trip(name, NUTZER_A)
    vorher = _ok(client, kennung, "route")
    assert vorher["stored"] is False
    ids = _zeilen_ids(vorher)
    assert len(ids) == len(set(ids)), ids
    assert set(ids) == _placements_ids(vorher["placements"])

    _zurueckschreiben(pfad, vorher["placements"])
    nachher = _ok(client, kennung, "route")
    assert nachher["stored"] is True
    gespeichert = json.loads(pfad.read_text(encoding="utf-8"))["display_config"]["placements"]
    assert set(_zeilen_ids(nachher)) == _placements_ids(gespeichert) == set(ids)
    # Gleiche Zeilen in gleicher Folge; Marken duerfen sich aendern (der
    # Versand liest erst die gespeicherte Tabelle, gemeldete Aenderungen der
    # Umrechnung wie "Reihenfolge wie SMS").
    assert _zeilen_ids(nachher) == ids


@pytest.mark.parametrize("name", [n for n in GOLDEN if (FIXTURES / f"erwartung_golden_{n}.json").exists()])
def test_golden_jede_erwartete_ausgabe_hat_eine_angehakte_zelle(client, name):
    kennung, _pfad = _golden_trip(name, NUTZER_A)
    antwort = _ok(client, kennung, "route")
    zellen = {z["metric_id"]: z["cells"] for z in antwort["rows"]}
    erwartung = json.loads((FIXTURES / f"erwartung_golden_{name}.json").read_text(encoding="utf-8"))
    fehlt = [(stelle, e["metric_id"]) for stelle, liste in erwartung["channels"].items()
             for e in liste
             if zellen.get(e["metric_id"], {}).get(stelle, {}).get("state") != "on"]
    assert not fehlt, fehlt


def test_golden_c_zweiter_nutzer_sieht_nur_sein_abo(client):
    """Mandantentrennung: dieselbe Kennung bei Nutzer B ohne cloud_low."""
    kennung, _pfad = _golden_trip("c", NUTZER_A)
    daten = json.loads((FIXTURES / "golden_c.json").read_text(encoding="utf-8"))
    daten["id"] = kennung
    daten["display_config"]["metrics"] = [
        m for m in daten["display_config"]["metrics"] if m["metric_id"] != "cloud_low"]
    _schreibe(NUTZER_B, "briefings", kennung, daten)
    assert "cloud_low" in _zeilen_ids(_ok(client, kennung, "route", NUTZER_A))
    assert "cloud_low" not in _zeilen_ids(_ok(client, kennung, "route", NUTZER_B))


@pytest.mark.parametrize("abend", [False, True])
def test_orte_zeilen_gleich_placements(client, abend):
    kennung = f"o-3154-{'ma' if abend else 'm'}"
    pfad = _orte(NUTZER_A, kennung, anzahl=1, abend=abend)
    vorher = _ok(client, kennung, "vergleich")
    assert set(_zeilen_ids(vorher)) == _placements_ids(vorher["placements"])
    _zurueckschreiben(pfad, vorher["placements"])
    nachher = _ok(client, kennung, "vergleich")
    assert nachher["stored"] is True
    assert _zeilen_ids(nachher) == _zeilen_ids(vorher)


def test_nur_morgens_gewaehlte_metrik_am_ende_passt_nicht_mehr_nicht(client):
    """Beide Briefings an, Beispiel = Abend-Briefing: eine nur morgens
    gewaehlte Metrik am Ende der SMS hat eine Zeile mit SMS-Haken, aber keine
    Marke "passt nicht mehr" -- sie fehlt abends, weil sie dort nicht gewaehlt
    ist, nicht weil die 160 Zeichen voll sind."""
    from tests.tdd.test_placements_tabelle_endpoint import _trip

    pfad = _trip(NUTZER_A, "t-3154-morgen", grund=["wind", "gust", "cloud_low"])
    daten = json.loads(pfad.read_text(encoding="utf-8"))
    for m in daten["display_config"]["metrics"]:
        if m["metric_id"] == "cloud_low":
            m["evening_enabled"] = False
    pfad.write_text(json.dumps(daten), encoding="utf-8")
    antwort = _ok(client, "t-3154-morgen", "route")
    assert _zeilen_ids(antwort) == ["wind", "gust", "cloud_low"]
    zelle = antwort["rows"][2]["cells"]["sms"]
    assert zelle["state"] == "on"
    assert zelle["mark"] is None

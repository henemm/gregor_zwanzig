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


# ---------------------------------------------------------------------------
# Folge und Typ-Faelle (Adversary F001, #3154)
# ---------------------------------------------------------------------------

def _trip_mit_flags(kennung: str, grund: list[str], flags: dict, *, rc=None) -> Path:
    """Trip mit Grundauswahl ``grund``; ``flags`` = {metric_id: {feld: wert}}."""
    from tests.tdd.test_placements_tabelle_endpoint import _trip

    pfad = _trip(NUTZER_A, kennung, grund=grund, rc=rc)
    daten = json.loads(pfad.read_text(encoding="utf-8"))
    for m in daten["display_config"]["metrics"]:
        m.update(flags.get(m["metric_id"], {}))
    pfad.write_text(json.dumps(daten), encoding="utf-8")
    return pfad


NUR_MORGENS_VORN = ["cloud_low", "wind", "gust", "rain_probability"]
FOLGE_ABEND_ZUERST = ["wind", "gust", "rain_probability", "cloud_low"]


def test_nur_morgens_vorn_ohne_tabelle_steht_hinter_den_abend_metriken(client):
    _trip_mit_flags("t-3154-folge-roh", NUR_MORGENS_VORN, {"cloud_low": {"evening_enabled": False}})
    antwort = _ok(client, "t-3154-folge-roh", "route")
    assert antwort["stored"] is False
    assert _zeilen_ids(antwort) == FOLGE_ABEND_ZUERST


def test_nur_morgens_vorn_mit_tabelle_nur_wind_steht_hinten(client):
    """Metriken ohne Zeile stehen hinten, in der Folge Abend, dann nur morgens."""
    pfad = _trip_mit_flags("t-3154-folge-tab", NUR_MORGENS_VORN,
                           {"cloud_low": {"evening_enabled": False}})
    _zurueckschreiben(pfad, {"version": 1, "rows": [{"metric_id": "wind"}]})
    antwort = _ok(client, "t-3154-folge-tab", "route")
    assert antwort["stored"] is True
    assert _zeilen_ids(antwort) == FOLGE_ABEND_ZUERST


def test_nur_abends_metrik_im_reinen_morgen_abo_hat_eine_zeile(client):
    _trip_mit_flags("t-3154-morgen-abo", ["wind", "gust", "cloud_low"],
                    {"cloud_low": {"morning_enabled": False}},
                    rc={"enabled": True, "morning_enabled": True, "evening_enabled": False})
    from app.loader import get_data_root, load_trip
    from services.channel_list_resolver import resolve_channel_lists

    dc = load_trip("t-3154-morgen-abo", data_dir=get_data_root(), user_id=NUTZER_A).display_config
    # Vorbedingung: das gerenderte Morgen-Briefing fuehrt cloud_low nirgends.
    morgen = resolve_channel_lists(dc, "trip", "morning")
    assert all("cloud_low" not in [r.metric_id for r in getattr(morgen, k)]
               for k in ("email", "telegram", "sms"))
    antwort = _ok(client, "t-3154-morgen-abo", "route")
    assert _zeilen_ids(antwort) == ["wind", "gust", "cloud_low"]
    assert antwort["rows"][2]["cells"]["sms"]["mark"] is None


def test_in_beiden_typen_abgewaehlte_metrik_hat_keine_zeile(client):
    _trip_mit_flags("t-3154-beide-aus", ["wind", "gust", "cloud_low"],
                    {"cloud_low": {"morning_enabled": False, "evening_enabled": False}})
    antwort = _ok(client, "t-3154-beide-aus", "route")
    assert _zeilen_ids(antwort) == ["wind", "gust"]
    assert "cloud_low" not in _placements_ids(antwort["placements"])


def test_abgewaehlter_telegram_haken_an_nur_morgens_zeile_wirkt_im_morgen_briefing(client):
    """Nach dem PUT: morgens Telegram ohne, SMS mit cloud_low; abends unveraendert."""
    from app.loader import get_data_root, load_trip
    from services.channel_list_resolver import resolve_channel_lists

    pfad = _trip_mit_flags("t-3154-haken", ["wind", "gust", "cloud_low"],
                           {"cloud_low": {"evening_enabled": False}})

    def listen(rt):
        dc = load_trip("t-3154-haken", data_dir=get_data_root(), user_id=NUTZER_A).display_config
        vm = resolve_channel_lists(dc, "trip", rt)
        return {k: [r.metric_id for r in getattr(vm, k)] for k in ("email", "telegram", "sms")}

    abend_vorher = listen("evening")
    placements = copy.deepcopy(_ok(client, "t-3154-haken", "route")["placements"])
    zeile = next(r for r in placements["rows"] if r["metric_id"] == "cloud_low")
    zeile.setdefault("places", {})["telegram"] = False
    _zurueckschreiben(pfad, placements)

    morgen = listen("morning")
    assert "cloud_low" not in morgen["telegram"]
    assert "cloud_low" in morgen["sms"]
    assert listen("evening") == abend_vorher
    assert all("cloud_low" not in v for v in abend_vorher.values())
    tabelle = next(z for z in _ok(client, "t-3154-haken", "route")["rows"]
                   if z["metric_id"] == "cloud_low")
    assert tabelle["cells"]["telegram"]["state"] == "off"
    assert tabelle["cells"]["sms"]["state"] == "on"

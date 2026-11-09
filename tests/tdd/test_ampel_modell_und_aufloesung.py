"""Profil-Ampel S1a (#2792): Datenmodell, Vorlagen, Validierung, Aufloesung.

Spec: docs/specs/modules/feat_2792_s1_profil_ampel.md (AC-13, AC-14 Python-
Seite, AC-15 Aufloesung, AC-16 Regeln, AC-18). Kein Mock: echter Katalog,
echter Loader auf ``tmp_path``, echter FastAPI-Router. Fixture relativ zur
Testdatei aufgeloest.
"""

import copy
import json
import logging
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import metric_catalog
from app.ampel import (
    ampel_for,
    deviation_count,
    template_id_for,
    thunder_color,
    validate_ampel,
)
from app.ampel_templates import AMPEL_TEMPLATES
from app.loader import compare_preset_from_dict, load_trip, save_trip
from app.models import ThunderLevel
from output.metric_format import severity_from_thresholds

_HERE = Path(__file__).resolve().parent
FIXTURE = _HERE.parent / "fixtures" / "trip_schema_full.json"


def _trip_dict(display_config: dict) -> dict:
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    data["display_config"] = display_config
    return data


def _gust(yellow, orange, red):
    return {"upper": {"yellow": yellow, "orange": orange, "red": red}}


# --- Vorlagen ---------------------------------------------------------------

def test_sieben_vorlagen_mit_denselben_ids_wie_die_wettervorlagen():
    assert list(AMPEL_TEMPLATES) == list(metric_catalog.WEATHER_TEMPLATES)


@pytest.mark.parametrize("tid", list(AMPEL_TEMPLATES))
def test_jede_vorlage_besteht_die_eigene_validierung(tid):
    assert validate_ampel(AMPEL_TEMPLATES[tid]) == []


def test_allgemein_gleicht_dem_bisherigen_katalog_ausser_cape():
    """AC-18 Paritaets-Ratsche: Vorlage allgemein == display_thresholds (ohne CAPE).

    Verglichen wird gegen den ECHTEN Katalog (alle Groessen inkl. nicht
    waehlbarer), nicht gegen eine Kopie der Zahlen. Nie lockern.
    """
    katalog = {m.id: m.display_thresholds for m in metric_catalog._METRICS
               if m.display_thresholds}
    assert len(katalog) == 10 and "cape" in katalog
    aufgeloest = ampel_for({})
    for mid, erwartet in katalog.items():
        if mid == "cape":
            assert aufgeloest.get("cape", {}) == {}, "CAPE-Farbe entfaellt (P1)"
            continue
        assert aufgeloest[mid] == erwartet, mid


# --- AC-13 Rueckfallkette Trip ----------------------------------------------

def test_trip_ohne_ampel_mit_vorlagenname_liefert_skitouren_grenzen(tmp_path):
    save_trip(load_trip(_trip_dict({"preset_name": "skitouren", "metrics": []}), user_id="anna"), "anna", tmp_path)
    trip = load_trip("drift-gate-trip", data_dir=tmp_path, user_id="anna")
    assert ampel_for(trip)["gust"]["yellow"] == 40


def test_trip_ohne_ampel_und_ohne_vorlagenname_liefert_allgemein():
    trip = load_trip(_trip_dict({"metrics": []}), user_id="anna")
    assert ampel_for(trip)["gust"]["yellow"] == 30


def test_unbekannte_vorlage_liefert_allgemein_mit_warnung(caplog):
    trip = load_trip(_trip_dict({"preset_name": "gibt-es-nicht", "metrics": []}), user_id="anna")
    with caplog.at_level(logging.WARNING, logger="app.ampel"):
        assert ampel_for(trip)["gust"]["yellow"] == 30
    assert any("gibt-es-nicht" in r.getMessage() for r in caplog.records)


def test_abo_ampel_gewinnt_je_metrik_rest_aus_vorlage():
    ampel = {"template": "skitouren", "metrics": {"gust": _gust(42, 55, 70)}}
    trip = load_trip(_trip_dict({"preset_name": "wandern", "ampel": ampel, "metrics": []}), user_id="anna")
    res = ampel_for(trip)
    assert res["gust"] == {"yellow": 42, "orange": 55, "red": 70}
    assert res["temperature"] == {"yellow": 3, "orange": 8, "red": 15,
                                  "yellow_lt": -15, "orange_lt": -20, "red_lt": -30}


def test_form_passt_zu_severity_from_thresholds_beidseitig():
    wind = ampel_for({"display_config": {"ampel": {"template": "wassersport"}}})["wind"]
    assert wind == {"yellow": 30, "orange": 40, "red": 50, "orange_lt": 4, "yellow_lt": 8}
    assert [severity_from_thresholds(wind, v) for v in (3, 6, 15, 41)] == [
        "orange", "yellow", "green", "orange"]


# --- AC-15 Compare-Profil ---------------------------------------------------

@pytest.mark.parametrize("profil, vorlage", [
    ("summer_trekking", "alpen-trekking"), ("WANDERN", "wandern"),
    ("Wintersport", "wintersport"), ("allgemein", "allgemein"), ("radtour", "radtour"),
])
def test_compare_profil_wird_vorlage(profil, vorlage):
    preset = {"profil": profil, "display_config": {}}
    assert template_id_for(preset) == vorlage
    assert template_id_for(compare_preset_from_dict({"id": "c1", **preset})) == vorlage


def test_unbekanntes_compare_profil_wird_allgemein_mit_warnung(caplog):
    with caplog.at_level(logging.WARNING, logger="app.ampel"):
        assert template_id_for({"profil": "bergsteigen", "display_config": {}}) == "allgemein"
    assert any("bergsteigen" in r.getMessage() for r in caplog.records)


def test_gespeicherte_compare_vorlage_schlaegt_profil():
    preset = {"profil": "summer_trekking", "display_config": {"ampel": {"template": "skitouren"}}}
    assert template_id_for(preset) == "skitouren"
    assert ampel_for(preset)["gust"]["yellow"] == 40


# --- Validierung (Regeln fuer AC-16, Python-Seite) --------------------------

#: Dieselben Vektoren liest der Go-Test TestValidateAmpel_GemeinsameVektorenMitPython
#: (internal/handler/ampel_validierung_test.go) -- Regelgleichheit Python/Go.
VEKTOREN = json.loads((_HERE.parent / "fixtures" / "ampel_validierung_vektoren.json")
                      .read_text(encoding="utf-8"))["vektoren"]


@pytest.mark.parametrize("vektor", VEKTOREN, ids=[v["name"] for v in VEKTOREN])
def test_validierung_gleicht_den_gemeinsamen_vektoren(vektor):
    assert (validate_ampel(vektor["ampel"]) == []) is vektor["gueltig"]


def test_ungueltige_compare_ampel_wird_beim_aufloesen_verworfen(caplog):
    """F-F: auch ohne Loader (Compare-Dict direkt an ampel_for) gilt eine
    ungueltige Abo-Ampel nicht -- weder ihre Grenzen noch ihr template."""
    preset = {"profil": "radtour", "display_config": {"ampel": {
        "template": "skitouren", "metrics": {"gust": _gust(99, 50, 60)}}}}
    with caplog.at_level(logging.WARNING, logger="app.ampel"):
        assert ampel_for(preset)["gust"] == {"yellow": 35, "orange": 50, "red": 65}
    assert template_id_for(preset) == "radtour"
    assert any("ungueltig" in r.getMessage() for r in caplog.records)


# --- Abweichungszahl und Gewitter -------------------------------------------

def test_abweichungszahl_zaehlt_grenzen_gewitter_und_alarmstufe():
    # Issue #2794 S3a (AC-28): alarm_ab zaehlt jetzt mit (vorher S1 §1: nicht).
    vorlage_gust = copy.deepcopy(AMPEL_TEMPLATES["skitouren"]["metrics"]["gust"])
    assert deviation_count({"template": "skitouren"}) == 0
    assert deviation_count({"template": "skitouren", "metrics": {"gust": vorlage_gust}}) == 0
    assert deviation_count({"template": "skitouren",
                            "metrics": {"gust": {**vorlage_gust, "alarm_ab": "never"}}}) == 1
    assert deviation_count({"template": "skitouren", "metrics": {"gust": _gust(42, 55, 70)}}) == 1
    assert deviation_count({"template": "skitouren", "metrics": {"gust": _gust(42, 55, 70)},
                            "thunder": {"mittel": "red", "hoch": "red"}}) == 2


def _aufgeloest(abo_ampel):
    """#2792 S1c-4b Fix-Loop 2 Nachtrag (AC-27): ``thunder_color`` liest die
    AUFGELOESTE Ampel (wie ``schwellen_aus_ampel``); das Abo-Ampel-Fragment
    geht deshalb ueber ``resolve_ampel`` -- mechanisch umgestellt."""
    from app.ampel import resolve_ampel
    return resolve_ampel({"ampel": abo_ampel})


@pytest.mark.parametrize("tid", list(AMPEL_TEMPLATES))
def test_gewitter_keins_gruen_leicht_immer_gelb(tid):
    ampel = _aufgeloest({"template": tid})
    assert thunder_color(ThunderLevel.NONE, ampel) == "green"
    assert thunder_color(ThunderLevel.LOW, ampel) == "yellow"
    assert thunder_color(ThunderLevel.HIGH, ampel) in ("orange", "red")


def test_gewitter_mittel_nach_vorlage_und_abo():
    assert thunder_color(ThunderLevel.MED, _aufgeloest({"template": "wassersport"})) == "red"
    assert thunder_color(ThunderLevel.MED, _aufgeloest({"template": "allgemein"})) == "orange"
    assert thunder_color(ThunderLevel.MED, _aufgeloest(
        {"thunder": {"mittel": "yellow", "hoch": "orange"}})) == "yellow"
    assert thunder_color(None, _aufgeloest({"template": "allgemein"})) is None
    # Umgekehrt (Koordinator-Entscheid Fix-Loop 2 Nachtrag, AC-27): fehlende
    # Ampel faellt nicht mehr still auf „allgemein" (frueher MED -> "orange").
    for leer in (None, {}):
        with pytest.raises(ValueError, match="Profil-Ampel leer"):
            thunder_color(ThunderLevel.MED, leer)


# --- Loader: lesen, schreiben, merge-sicher ---------------------------------

def test_python_speichern_behaelt_ampel_und_alle_anderen_felder(tmp_path):
    ampel = {"template": "skitouren", "metrics": {"gust": {**_gust(42, 55, 70), "alarm_ab": "yellow"}},
             "thunder": {"mittel": "orange", "hoch": "red"}}
    dc = {"preset_name": "skitouren", "metrics": [], "theme": "von-go", "ampel": ampel}
    pfad = tmp_path / "users" / "anna" / "briefings" / "drift-gate-trip.json"
    pfad.parent.mkdir(parents=True)
    pfad.write_text(json.dumps(_trip_dict(dc)), encoding="utf-8")

    trip = load_trip("drift-gate-trip", data_dir=tmp_path, user_id="anna")
    assert trip.display_config.ampel == ampel
    save_trip(trip, "anna", tmp_path)

    gespeichert = json.loads(pfad.read_text(encoding="utf-8"))["display_config"]
    assert gespeichert["ampel"] == ampel
    assert gespeichert["theme"] == "von-go"
    assert gespeichert["preset_name"] == "skitouren"


def test_python_speichern_ersetzt_ampel_als_ganzen_unterbaum(tmp_path):
    """F-C (Spec §1): eine entfernte Metrik und eine entfernte Grenze tauchen
    nach dem erneuten Speichern NICHT wieder auf (kein Tief-Merge mit der
    Platte); alle anderen Felder bleiben erhalten."""
    ampel = {"template": "skitouren", "metrics": {
        "gust": _gust(42, 55, 70), "wind": {"upper": {"yellow": 25, "orange": 45, "red": 60}}}}
    pfad = tmp_path / "users" / "anna" / "briefings" / "drift-gate-trip.json"
    pfad.parent.mkdir(parents=True)
    pfad.write_text(json.dumps(_trip_dict({"preset_name": "skitouren", "metrics": [],
                                           "theme": "von-go", "ampel": ampel})), encoding="utf-8")
    trip = load_trip("drift-gate-trip", data_dir=tmp_path, user_id="anna")
    del trip.display_config.ampel["metrics"]["wind"]
    del trip.display_config.ampel["metrics"]["gust"]["upper"]["red"]
    save_trip(trip, "anna", tmp_path)

    dc = json.loads(pfad.read_text(encoding="utf-8"))["display_config"]
    assert dc["ampel"] == {"template": "skitouren",
                           "metrics": {"gust": {"upper": {"yellow": 42, "orange": 55}}}}
    assert dc["theme"] == "von-go" and dc["preset_name"] == "skitouren"


def test_ungueltige_ampel_beim_laden_verworfen_und_protokolliert(tmp_path, caplog):
    kaputt = {"metrics": {"gust": _gust(50, 45, 60)}}
    pfad = tmp_path / "users" / "anna" / "briefings" / "drift-gate-trip.json"
    pfad.parent.mkdir(parents=True)
    pfad.write_text(json.dumps(_trip_dict({"preset_name": "skitouren", "metrics": [],
                                           "ampel": kaputt})), encoding="utf-8")
    with caplog.at_level(logging.WARNING):
        trip = load_trip("drift-gate-trip", data_dir=tmp_path, user_id="anna")
    assert trip.display_config.ampel is None
    assert any("drift-gate-trip" in r.getMessage() and "Ampel" in r.getMessage()
               for r in caplog.records)
    assert ampel_for(trip)["gust"]["yellow"] == 40  # Vorlage skitouren greift
    save_trip(trip, "anna", tmp_path)  # Altdaten gehen dabei nicht verloren
    assert json.loads(pfad.read_text(encoding="utf-8"))["display_config"]["ampel"] == kaputt


# --- GET /templates ---------------------------------------------------------

def test_templates_endpunkt_liefert_ampel_je_vorlage_und_alte_felder_unveraendert():
    from api.routers import config

    app = FastAPI()
    app.include_router(config.router, prefix="/api")
    antwort = TestClient(app).get("/api/templates").json()
    alt = metric_catalog.get_all_templates()
    assert [{k: t[k] for k in ("id", "label", "metrics")} for t in antwort] == alt
    for t in antwort:
        assert t["ampel"]["template"] == t["id"]
        assert validate_ampel(t["ampel"]) == []
    skitouren = next(t for t in antwort if t["id"] == "skitouren")
    assert skitouren["ampel"]["metrics"]["gust"]["upper"]["yellow"] == 40
    assert skitouren["ampel"]["metrics"]["gust"]["alarm_ab"] == "orange"

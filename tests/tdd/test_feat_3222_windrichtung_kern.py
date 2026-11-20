"""Windrichtung bewerten, Scheibe S1 (Fachkern + Modell), Issue #3222.

Spec: docs/specs/modules/feat_3222_windrichtung.md (AC-4, AC-9, AC-10 Python-
Seite), ADR-0126. Kein Mock: echte Geometrie, echter Validator, echte
Vorlagen, echter Loader auf ``tmp_path``. Gemeinsame Faelle mit Go und dem
Frontend-Spiegel: ``tests/fixtures/ampel_windrichtung_cases.json``.

Konvention: ``wind_direction_deg`` ist die Richtung, AUS der der Wind kommt
(0 = N, 90 = O); die Peilung ist die Richtung, IN die gefahren wird.
"""

import copy
import json
from pathlib import Path

import pytest

from app.ampel import deviation_count, resolve_ampel, validate_ampel
from app.ampel_templates import AMPEL_TEMPLATES
from app.loader import load_trip, save_trip
from app.models import GPXPoint
from services.windrichtung import (
    MIN_LUFTLINIE_KM,
    gegenwind_kmh,
    sektor_kmh,
    sektor_von,
    segment_peilung_deg,
    wind_unerwuenscht_kmh,
)
from utils.geo import bearing_deg, haversine_km, mean_direction_deg

_HERE = Path(__file__).resolve().parent
FAELLE = json.loads((_HERE.parent / "fixtures" / "ampel_windrichtung_cases.json")
                    .read_text(encoding="utf-8"))["faelle"]


def _winkelabstand(a: float, b: float) -> float:
    return abs((a - b + 180.0) % 360.0 - 180.0)


# --- Peilung -----------------------------------------------------------------

@pytest.mark.parametrize("ziel, erwartet", [
    ((47.1, 11.0), 0.0),     # nach Norden
    ((47.0, 11.1), 90.0),    # nach Osten (kleine Abweichung durch Grosskreis)
    ((46.9, 11.0), 180.0),   # nach Sueden
    ((47.0, 10.9), 270.0),   # nach Westen
])
def test_peilung_der_vier_haupt_himmelsrichtungen(ziel, erwartet):
    peilung = bearing_deg(47.0, 11.0, *ziel)
    assert 0.0 <= peilung < 360.0
    assert _winkelabstand(peilung, erwartet) < 0.1


def test_peilung_knapp_westlich_von_nord_liegt_bei_359_nicht_negativ():
    peilung = bearing_deg(47.0, 11.0, 47.1, 10.9975)
    assert 358.0 < peilung < 360.0


# --- Winkelmittel ------------------------------------------------------------

def test_vektorielles_mittel_von_350_und_10_ist_nord_nicht_180():
    mittel = mean_direction_deg([350, 10])
    assert _winkelabstand(mittel, 0.0) < 1e-6
    assert 0.0 <= mittel < 360.0


def test_vektorielles_mittel_von_359_und_1_ist_nord():
    assert _winkelabstand(mean_direction_deg([359, 1]), 0.0) < 1e-6


def test_vektorielles_mittel_gewichtet_und_ohne_luecken():
    assert _winkelabstand(mean_direction_deg([90, 180], weights=[3, 1]), 108.43) < 0.01
    assert _winkelabstand(mean_direction_deg([None, 270, 270]), 270.0) < 1e-6


def test_vektorielles_mittel_ohne_richtung_ist_none():
    assert mean_direction_deg([]) is None
    assert mean_direction_deg([None]) is None
    assert mean_direction_deg([0, 180]) is None  # Gegenrichtungen heben sich auf


# --- Gegenwindkomponente -----------------------------------------------------

def test_gegenwind_rueckenwind_seitenwind_bei_fahrt_nach_norden():
    assert gegenwind_kmh(25, 0, 0) == 25.0     # Wind aus N, Fahrt nach N
    assert gegenwind_kmh(25, 180, 0) == 0.0    # Rueckenwind
    assert gegenwind_kmh(25, 90, 0) == 0.0     # Seitenwind von O
    assert gegenwind_kmh(25, 270, 0) == 0.0    # Seitenwind von W
    assert gegenwind_kmh(20, 60, 0) == 10.0    # schraeg: 20 * cos 60


@pytest.mark.parametrize("peilung, herkunft", [(359, 1), (1, 359)])
def test_ac4_wrap_359_und_1_ist_volle_gegenwindkomponente(peilung, herkunft):
    """AC-4: cos 2 Grad, gerundet -> volle Staerke, nicht Seitenwind."""
    assert gegenwind_kmh(25, herkunft, peilung) == 25.0
    assert gegenwind_kmh(25, herkunft, peilung) == gegenwind_kmh(25, 0, 0)


def test_ac4_arithmetisches_mittel_wuerde_die_faerbung_verfehlen():
    """Gegenprobe zu AC-4: aus den Stundenrichtungen 359/1 ergibt das
    vektorielle Mittel Nord und damit volle Gegenwindkomponente."""
    herkunft = mean_direction_deg([359, 1])
    assert gegenwind_kmh(25, herkunft, 0) == 25.0
    assert gegenwind_kmh(25, (359 + 1) / 2, 0) == 0.0


# --- Sektoren ----------------------------------------------------------------

@pytest.mark.parametrize("grad, sektor", [
    (0, "N"), (359, "N"), (1, "N"), (22, "N"), (338, "N"),
    (23, "NO"), (337, "NW"), (90, "O"), (135, "SO"), (180, "S"),
    (225, "SW"), (270, "W"), (315, "NW"), (360, "N"),
])
def test_sektor_zuordnung_8er_mit_wrap(grad, sektor):
    assert sektor_von(grad) == sektor


def test_sektor_wert_volle_staerke_nur_im_markierten_sektor():
    assert sektor_kmh(30, 355, ["N"]) == 30.0
    assert sektor_kmh(30, 5, ["N"]) == 30.0
    assert sektor_kmh(30, 315, ["N", "NO"]) == 0.0
    assert sektor_kmh(30, 315, ["NW", "N", "NO"]) == 30.0
    assert sektor_kmh(30, 180, []) == 0.0


# --- Abgeleitetes Feld -------------------------------------------------------

def test_wind_unerwuenscht_je_modus():
    assert wind_unerwuenscht_kmh("gegenwind", [], 25, 0, 0) == 25.0
    assert wind_unerwuenscht_kmh("gegenwind", [], 25, 180, 0) == 0.0
    assert wind_unerwuenscht_kmh("sektoren", ["N"], 30, 0, None) == 30.0
    assert wind_unerwuenscht_kmh("sektoren", ["S"], 30, 0, None) == 0.0


@pytest.mark.parametrize("modus, sektoren, kmh, herkunft, peilung", [
    ("aus", [], 25, 0, 0),
    (None, [], 25, 0, 0),
    ("rueckenwind", [], 25, 0, 0),
    ("gegenwind", [], 25, 0, None),      # keine Fahrtrichtung
    ("gegenwind", [], None, 0, 0),       # Daten fehlen
    ("gegenwind", [], 25, None, 0),
    ("sektoren", ["N"], None, 0, None),
    ("sektoren", ["N"], 30, None, None),
])
def test_wind_unerwuenscht_nicht_bestimmbar_ist_none(modus, sektoren, kmh, herkunft, peilung):
    assert wind_unerwuenscht_kmh(modus, sektoren, kmh, herkunft, peilung) is None


# --- Segment-Peilung und 300-m-Regel -----------------------------------------

class _Segment:
    def __init__(self, start, end):
        self.start_point, self.end_point = start, end


def test_segment_nach_norden_hat_peilung_nord():
    seg = _Segment(GPXPoint(lat=47.0, lon=11.0), GPXPoint(lat=47.05, lon=11.0))
    assert _winkelabstand(segment_peilung_deg(seg), 0.0) < 0.1


def test_rundkurs_segment_unter_300_m_hat_keine_peilung():
    start = GPXPoint(lat=47.0, lon=11.0)
    ende = GPXPoint(lat=47.0025, lon=11.0)  # rund 278 m Luftlinie
    assert haversine_km(start.lat, start.lon, ende.lat, ende.lon) < MIN_LUFTLINIE_KM
    assert segment_peilung_deg(_Segment(start, ende)) is None
    weiter = GPXPoint(lat=47.0030, lon=11.0)  # rund 334 m
    assert segment_peilung_deg(_Segment(start, weiter)) is not None


def test_ac5_vorbau_rundkurs_ergibt_keinen_wert_auch_bei_starkem_wind():
    seg = _Segment(GPXPoint(lat=47.0, lon=11.0), GPXPoint(lat=47.0001, lon=11.0001))
    assert wind_unerwuenscht_kmh("gegenwind", [], 40, 0, segment_peilung_deg(seg)) is None


def test_segment_ohne_punkte_hat_keine_peilung():
    assert segment_peilung_deg(_Segment(None, GPXPoint(lat=47.0, lon=11.0))) is None


def test_mindest_luftlinie_ist_300_m():
    assert MIN_LUFTLINIE_KM == 0.3


# --- AC-9: Validierung (gemeinsame Faelle mit Go und Frontend) ---------------

@pytest.mark.parametrize("fall", FAELLE, ids=[f["name"] for f in FAELLE])
def test_ac9_validierung_gleicht_den_gemeinsamen_faellen(fall):
    fehler = validate_ampel(fall["ampel"], kontext=fall["kontext"])
    if fall["grund"] is None:
        assert fehler == []
    else:
        assert len(fehler) == 1, fehler
        assert fehler[0].endswith("." + fall["grund"]), fehler


def test_messaufbau_faelle_decken_alle_ablehnungsgruende_ab():
    gruende = {f["grund"] for f in FAELLE}
    assert {"sektor_unbekannt", "sektor_doppelt", "sektoren_keine_liste", "modus_unbekannt",
            "sektoren_ohne_sektormodus", "gegenwind_nur_trip", "nur_windrichtung"} < gruende
    assert any(f["grund"] is None and f["kontext"] == "vergleich" for f in FAELLE)


def test_ac7_gegenwind_nur_im_ortsvergleich_abgelehnt():
    ampel = {"metrics": {"wind_direction": {"modus": "gegenwind"}}}
    assert validate_ampel(ampel) == []
    assert validate_ampel(ampel, kontext="route") == []
    assert validate_ampel(ampel, kontext="vergleich") == ["wind_direction.gegenwind_nur_trip"]


# --- Vorlagen ----------------------------------------------------------------

def test_vorlage_radtour_bewertet_gegenwind_10_20_30_alarm_ab_orange():
    wd = AMPEL_TEMPLATES["radtour"]["metrics"]["wind_direction"]
    assert wd["modus"] == "gegenwind"
    assert wd["upper"] == {"yellow": 10, "orange": 20, "red": 30}
    assert wd["alarm_ab"] == "orange"
    assert validate_ampel(AMPEL_TEMPLATES["radtour"], kontext="route") == []


@pytest.mark.parametrize("tid", [t for t in AMPEL_TEMPLATES if t != "radtour"])
def test_alle_anderen_vorlagen_ohne_richtungsbewertung(tid):
    wd = AMPEL_TEMPLATES[tid]["metrics"]["wind_direction"]
    assert wd.get("modus", "aus") == "aus"
    assert not wd.get("sektoren")
    assert {k: v for k, v in wd["upper"].items() if v is not None} == {}
    assert wd["alarm_ab"] == "never"


# --- Aufloesung (_verschmelzen) ----------------------------------------------

def test_abo_modus_und_sektoren_werden_uebernommen_rest_aus_vorlage():
    res = resolve_ampel({"ampel": {"template": "radtour", "metrics": {
        "wind_direction": {"modus": "sektoren", "sektoren": ["N", "NO"]}}}})
    wd = res["metrics"]["wind_direction"]
    assert wd["modus"] == "sektoren" and wd["sektoren"] == ["N", "NO"]
    assert wd["upper"] == {"yellow": 10, "orange": 20, "red": 30}
    assert wd["alarm_ab"] == "orange" and wd["enabled"] is True
    assert res["metrics"]["gust"] == AMPEL_TEMPLATES["radtour"]["metrics"]["gust"]


def test_abo_ohne_modus_behaelt_vorlagen_modus():
    res = resolve_ampel({"ampel": {"template": "radtour", "metrics": {
        "wind_direction": {"upper": {"yellow": 12, "orange": 22, "red": 32}}}}})
    assert res["metrics"]["wind_direction"]["modus"] == "gegenwind"


def test_bestand_ohne_feld_bleibt_aus_und_vorlage_unveraendert():
    vorher = copy.deepcopy(AMPEL_TEMPLATES)
    res = resolve_ampel({"ampel": {"template": "wandern"}})
    assert res["metrics"]["wind_direction"].get("modus", "aus") == "aus"
    abo = {"ampel": {"template": "radtour", "metrics": {"wind_direction": {"sektoren": None}}}}
    resolve_ampel(abo)["metrics"]["wind_direction"]["modus"] = "aus"
    assert AMPEL_TEMPLATES == vorher, "Aufloesung mutiert die Vorlage"


def test_aufgeloeste_sektorliste_ist_eine_kopie():
    abo = {"ampel": {"metrics": {"wind_direction": {"modus": "sektoren", "sektoren": ["N"]}}}}
    resolve_ampel(abo)["metrics"]["wind_direction"]["sektoren"].append("S")
    assert abo["ampel"]["metrics"]["wind_direction"]["sektoren"] == ["N"]


# --- Abweichungszahl ---------------------------------------------------------

def test_abweichungszahl_modus_und_sektoren():
    assert deviation_count({"template": "radtour", "metrics": {"wind_direction": {"modus": "gegenwind"}}}) == 0
    assert deviation_count({"template": "radtour", "metrics": {"wind_direction": {"modus": "aus"}}}) == 1
    assert deviation_count({"template": "allgemein", "metrics": {"wind_direction": {"modus": "aus"}}}) == 0
    assert deviation_count({"template": "allgemein", "metrics": {
        "wind_direction": {"modus": "sektoren", "sektoren": []}}}) == 1
    assert deviation_count({"template": "allgemein", "metrics": {
        "wind_direction": {"sektoren": []}}}) == 0
    sektoren = {"template": "allgemein", "metrics": {
        "wind_direction": {"modus": "sektoren", "sektoren": ["N", "O"]}}}
    assert deviation_count(sektoren) == 1


ABWEICHUNG = json.loads((_HERE.parent / "fixtures" / "ampel_windrichtung_cases.json")
                        .read_text(encoding="utf-8"))["abweichung"]


@pytest.mark.parametrize("fall", ABWEICHUNG, ids=[f["name"] for f in ABWEICHUNG])
def test_sektoren_vergleich_als_menge_bei_gleichem_modus(fall):
    """Adversary F001: der Sektoren-Zweig allein (modus gleich) entscheidet.
    Keine Vorlage traegt modus=sektoren, daher Zeilenvergleich direkt; derselbe
    Fall laeuft im Frontend ueber ``zaehleAbweichungenGegen``."""
    from app.ampel import _richtung_weicht_ab
    assert _richtung_weicht_ab(fall["abo"], fall["vorlage"]) is fall["abweicht"]


# --- Speichern: Read-Modify-Write, Bestand bleibt ----------------------------

def test_python_speichern_behaelt_modus_sektoren_und_alle_anderen_felder(tmp_path):
    fixture = _HERE.parent / "fixtures" / "trip_schema_full.json"
    ampel = {"template": "radtour", "metrics": {
        "wind_direction": {"modus": "sektoren", "sektoren": ["NW", "N"]},
        "gust": {"upper": {"yellow": 42, "orange": 55, "red": 70}}}}
    data = json.loads(fixture.read_text(encoding="utf-8"))
    data["display_config"] = {"preset_name": "radtour", "metrics": [], "theme": "von-go", "ampel": ampel}
    pfad = tmp_path / "users" / "anna" / "briefings" / "drift-gate-trip.json"
    pfad.parent.mkdir(parents=True)
    pfad.write_text(json.dumps(data), encoding="utf-8")

    trip = load_trip("drift-gate-trip", data_dir=tmp_path, user_id="anna")
    assert trip.display_config.ampel == ampel
    save_trip(trip, "anna", tmp_path)

    gespeichert = json.loads(pfad.read_text(encoding="utf-8"))["display_config"]
    assert gespeichert["ampel"] == ampel
    assert gespeichert["theme"] == "von-go" and gespeichert["preset_name"] == "radtour"


def test_ungueltige_windrichtung_beim_laden_verworfen_datei_behaelt_sie(tmp_path):
    fixture = _HERE.parent / "fixtures" / "trip_schema_full.json"
    kaputt = {"metrics": {"wind_direction": {"modus": "sektoren", "sektoren": ["NNO"]}}}
    data = json.loads(fixture.read_text(encoding="utf-8"))
    data["display_config"] = {"preset_name": "radtour", "metrics": [], "ampel": kaputt}
    pfad = tmp_path / "users" / "anna" / "briefings" / "drift-gate-trip.json"
    pfad.parent.mkdir(parents=True)
    pfad.write_text(json.dumps(data), encoding="utf-8")

    trip = load_trip("drift-gate-trip", data_dir=tmp_path, user_id="anna")
    assert trip.display_config.ampel is None
    assert resolve_ampel(trip)["metrics"]["wind_direction"]["modus"] == "gegenwind"
    save_trip(trip, "anna", tmp_path)
    assert json.loads(pfad.read_text(encoding="utf-8"))["display_config"]["ampel"] == kaputt

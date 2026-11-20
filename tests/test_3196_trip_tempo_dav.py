"""TDD RED: Issue #3196 (Workflow feat-3196-trip-tempo-etappen).

Spec: docs/specs/modules/feat_3196_trip_tempo_etappen.md (AC-2, AC-3, AC-5,
AC-6, AC-12). Python-Seite des Tempo-Modells:

- ``core.naismith.dav_hours`` und ``core.naismith.tempo_speeds`` gegen die
  gemeinsame Falltabelle ``tests/fixtures/naismith_dav_paritaet.json``
  (dieselbe Tabelle lesen Go und TS, AC-6).
- Lazy-Ableitung ``derive_tempo`` aller Altwerte (AC-2), nie MTB oder Ski.
- Loader: Trip ohne ``tempo`` bekommt es beim Lesen abgeleitet (AC-12),
  ``save_trip`` schreibt ``tempo``, laesst ``activity`` stehen und rechnet
  ``arrival_calculated`` nach DAV mit dem gespeicherten Tempo (AC-5).

Kern-Schicht, ohne Netz, ohne Mocks: echter Lade-/Schreibpfad in tmp_path.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.loader import load_trip_from_dict, save_trip
from core.naismith import dav_hours, derive_tempo, tempo_speeds, valid_tempo

_HERE = Path(__file__).resolve().parent
TABELLE = json.loads((_HERE / "fixtures" / "naismith_dav_paritaet.json").read_text(encoding="utf-8"))


def _trip_dict(**extra) -> dict:
    data = {
        "id": "t3196",
        "name": "Tempo-Trip",
        "stages": [
            {
                "id": "S1",
                "name": "Tag 1",
                "date": "2026-07-01",
                "waypoints": [
                    {"id": "A", "name": "A", "lat": 47.0, "lon": 11.0, "elevation_m": 1000,
                     "distance_from_start_km": 0.0},
                    {"id": "B", "name": "B", "lat": 47.0, "lon": 11.0, "elevation_m": 1600,
                     "distance_from_start_km": 4.0},
                    {"id": "C", "name": "C", "lat": 47.0, "lon": 11.0, "elevation_m": 1000,
                     "distance_from_start_km": 8.0},
                ],
            }
        ],
    }
    data.update(extra)
    return data


@pytest.mark.parametrize("fall", TABELLE["faelle"], ids=lambda f: f["name"])
def test_dav_hours_gegen_falltabelle(fall):
    """AC-3/AC-6: DAV-Formel je Fortbewegung, identisch zu Go und TS."""
    trip = load_trip_from_dict(_trip_dict(
        tempo={"fortbewegung": fall["fortbewegung"], "grundtempo_kmh": fall["grundtempo_kmh"]}))
    sp = tempo_speeds(trip)
    got = dav_hours(fall["km"], fall["hm_auf"], fall["hm_ab"], sp) * 60.0
    assert got == pytest.approx(fall["minuten"], abs=1e-6), fall["name"]


@pytest.mark.parametrize("name", sorted(TABELLE["referenz"]))
def test_raten_folgen_dem_grundtempo(name):
    ref = TABELLE["referenz"][name]
    for faktor in (1.0, 1.25, 0.5):
        v = ref["vorschlag_kmh"] * faktor
        trip = load_trip_from_dict(_trip_dict(tempo={"fortbewegung": name, "grundtempo_kmh": v}))
        flat, auf, ab = tempo_speeds(trip)
        assert (flat, auf, ab) == pytest.approx((v, ref["r_auf"] * faktor, ref["r_ab"] * faktor))


@pytest.mark.parametrize("activity", sorted(TABELLE["ableitung_activity"]))
def test_derive_tempo_alle_altwerte(activity):
    """AC-2: fahrrad_15/20/25 -> rad mit Zahl; alles andere -> fuss 4."""
    want = TABELLE["ableitung_activity"][activity]
    assert derive_tempo(activity) == want


def test_ableitung_tabelle_vollstaendig():
    for alt in ("", "wandern", "hiking", "trekking", "hochtour", "klettersteig", "skitour", "mtb",
                "fahrrad_15", "fahrrad_20", "fahrrad_25"):
        assert alt in TABELLE["ableitung_activity"]
    assert all(v["fortbewegung"] in ("fuss", "rad") for v in TABELLE["ableitung_activity"].values())


@pytest.mark.parametrize("activity,want", [
    ("fahrrad_20", {"fortbewegung": "rad", "grundtempo_kmh": 20}),
    ("hochtour", {"fortbewegung": "fuss", "grundtempo_kmh": 4}),
    (None, {"fortbewegung": "fuss", "grundtempo_kmh": 4}),
])
def test_loader_leitet_tempo_beim_lesen_ab(activity, want):
    """AC-12: Trip ohne tempo bekommt es beim Lesen aus activity."""
    extra = {"activity": activity} if activity is not None else {}
    trip = load_trip_from_dict(_trip_dict(**extra))
    assert trip.tempo == want
    assert trip.activity == (activity or "")


def test_loader_behaelt_gespeichertes_tempo():
    trip = load_trip_from_dict(_trip_dict(activity="fahrrad_20",
                                          tempo={"fortbewegung": "ski", "grundtempo_kmh": 2.5}))
    assert trip.tempo == {"fortbewegung": "ski", "grundtempo_kmh": 2.5}


def test_save_trip_schreibt_tempo_und_rechnet_dav(tmp_path):
    """AC-3/AC-5/AC-12: gespeicherte Ankunft nach DAV, tempo auf der Platte, activity bleibt.

    8 km / 600 Hm auf / 600 Hm ab, zu Fuss 4 km/h: 08:00 -> 10:30 -> 12:12
    (4:12 nach DAV statt 5:12 nach der alten Summenformel).
    """
    trip = load_trip_from_dict(_trip_dict(activity="fahrrad_20",
                                          tempo={"fortbewegung": "fuss", "grundtempo_kmh": 4}))
    pfad = save_trip(trip, "u3196", data_dir=tmp_path)
    disk = json.loads(pfad.read_text(encoding="utf-8"))
    assert disk["tempo"] == {"fortbewegung": "fuss", "grundtempo_kmh": 4}
    assert disk["activity"] == "fahrrad_20"
    arrivals = [wp["arrival_calculated"] for wp in disk["stages"][0]["waypoints"]]
    assert arrivals == ["08:00", "10:30", "12:12"]


def test_save_trip_ohne_tempo_rechnet_mit_ableitung(tmp_path):
    """AC-12: alter Schreibpfad ohne tempo -- Rad 20 bleibt Rad 20 (Ableitung)."""
    trip = load_trip_from_dict(_trip_dict(activity="fahrrad_20"))
    pfad = save_trip(trip, "u3196", data_dir=tmp_path)
    disk = json.loads(pfad.read_text(encoding="utf-8"))
    assert disk["activity"] == "fahrrad_20"
    # Rad 20 km/h: R_auf 600, R_ab 1000.
    # A->B 4 km/↑600: t_h 0:12, t_v 1:00 -> 1:06 => 09:06
    # B->C 4 km/↓600: t_h 0:12, t_v 0:36 -> 0:42 => 09:48
    arrivals = [wp["arrival_calculated"] for wp in disk["stages"][0]["waypoints"]]
    assert arrivals == ["08:00", "09:06", "09:48"]


# --- Fix-Loop 2, F001: Untergrenze 0.5 km/h (gleiche Tabelle wie Go und TS) ---

@pytest.mark.parametrize("fall", TABELLE["gueltigkeit"],
                         ids=lambda g: f"{g['fortbewegung']}-{g['grundtempo_kmh']}")
def test_valid_tempo_grenzen(fall):
    tempo = {"fortbewegung": fall["fortbewegung"], "grundtempo_kmh": fall["grundtempo_kmh"]}
    assert valid_tempo(tempo) is fall["gueltig"]


@pytest.mark.parametrize("kmh", [True, False, "4", None])
def test_valid_tempo_kein_zahlwert(kmh):
    """F-A2-5: ein Wahrheitswert (oder Text/None) ist kein Grundtempo -- ``True``
    gaelte sonst als 1 km/h. Nur Python: Go lehnt bool schon beim Dekodieren ab,
    daher nicht in der gemeinsamen Falltabelle."""
    assert valid_tempo({"fortbewegung": "fuss", "grundtempo_kmh": kmh}) is False


@pytest.mark.parametrize("kmh", [1e-320, 0.4])
def test_save_trip_mit_unplausiblem_altwert_crasht_nicht(tmp_path, kmh):
    """F001: ein unplausibles Grundtempo aus Altdaten bricht den Rechner nicht
    (vorher OverflowError in _round(inf)), sondern rechnet wie zu Fuss 4 km/h
    -- wie Go TempoSpeeds und TS tempoSpeeds (AC-6 Paritaet)."""
    trip = load_trip_from_dict(_trip_dict(tempo={"fortbewegung": "ski", "grundtempo_kmh": kmh}))
    pfad = save_trip(trip, "u3196", data_dir=tmp_path)
    disk = json.loads(pfad.read_text(encoding="utf-8"))
    arrivals = [wp["arrival_calculated"] for wp in disk["stages"][0]["waypoints"]]
    assert arrivals == ["08:00", "10:30", "12:12"]


# --- Fix-Loop 2, F005 (AC-11): Etappen-Wetter rechnet mit dem gespeicherten Tempo ---

def test_etappen_wetter_segmente_folgen_dem_gespeicherten_tempo():
    """Etappe OHNE gespeicherte Ankunft, Tempo Rad 20 weicht von der Ableitung
    aus activity (leer -> zu Fuss 4) ab: die Segmentzeiten des Etappen-Wetters
    folgen dem Tempo (09:06/09:48 Ortszeit), nicht der Ableitung (10:30/12:12)."""
    from zoneinfo import ZoneInfo

    from services.stage_weather import _segments_for_stage

    trip = load_trip_from_dict(_trip_dict(tempo={"fortbewegung": "rad", "grundtempo_kmh": 20}))
    stage = trip.stages[0]
    assert all(wp.arrival_calculated is None for wp in stage.waypoints), "Messaufbau: Ankunft schon gespeichert"
    segmente = _segments_for_stage(trip, stage)
    assert len(segmente) >= 2
    ort = ZoneInfo("Europe/Vienna")  # 47 N / 11 E, Juli = UTC+2
    enden = [s.end_time.astimezone(ort).strftime("%H:%M") for s in segmente[:2]]
    assert enden == ["09:06", "09:48"]

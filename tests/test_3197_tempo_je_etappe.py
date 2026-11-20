"""TDD RED: Issue #3197 (Workflow feat-3197-tempo-je-etappe).

Spec: docs/specs/modules/feat_3197_tempo_je_etappe.md (AC-2, AC-3, AC-4,
AC-5, AC-8, AC-9). Python-Seite des Grundtempos je Etappe (ADR-0108):

- ``core.naismith.stage_speeds(trip, stage)`` gegen die gemeinsame
  Falltabelle ``tests/fixtures/naismith_dav_paritaet.json`` Abschnitt
  ``etappen_ueberschreibung`` (dieselbe lesen Go und TS): S2 auf 3 km/h,
  S1 folgt dem Trip-Tempo zu Fuss 4 km/h.
- Loader: ``Stage.grundtempo_kmh`` wird gelesen, geschrieben (nur wenn
  gesetzt), Compute-on-Save rechnet je Etappe; ein ungueltiger Wert wird
  ignoriert; das Zuruecknehmen entfernt das Feld auch gegen den Plattenstand
  (RMW-Merge darf es nicht wiederbeleben).
- Kanal-Quelle (AC-3): alle vier Kanaele bewerten die Stunden je Wegpunkt
  aus denselben Segmentzeiten (``convert_trip_to_segments`` ueber die
  gespeicherten ``arrival_calculated`` bzw. den Self-Heal). Gepruft wird
  dort, wo die Zeiten fuer E-Mail, Telegram, SMS und Premium-SMS entstehen.

Kern-Schicht, ohne Netz, ohne Mocks: echter Lade-/Schreibpfad in tmp_path.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from app.loader import load_trip_from_dict, save_trip

_HERE = Path(__file__).resolve().parent
TABELLE = json.loads((_HERE / "fixtures" / "naismith_dav_paritaet.json").read_text(encoding="utf-8"))
FALL = TABELLE["etappen_ueberschreibung"]
ORT = ZoneInfo("Europe/Vienna")  # 47 N / 11 E, Juli = UTC+2


def _trip_dict(**stage_extra) -> dict:
    """Trip der Falltabelle; ``stage_extra`` ueberschreibt Felder je Etappen-ID."""
    data = {
        "id": "t3197",
        "name": "Etappen-Tempo-Trip",
        "tempo": copy.deepcopy(FALL["tempo"]),
        "stages": copy.deepcopy(FALL["stages"]),
    }
    for st in data["stages"]:
        st.update(stage_extra.get(st["id"], {}))
    return data


def _ohne_ueberschreibung() -> dict:
    data = _trip_dict()
    for st in data["stages"]:
        st.pop("grundtempo_kmh", None)
    return data


def _ankuenfte(disk: dict) -> dict:
    return {st["id"]: [wp["arrival_calculated"] for wp in st["waypoints"]] for st in disk["stages"]}


# --- Aufloesung je Etappe (AC-2, Paritaet mit Go/TS) -------------------------

def test_stage_speeds_gegen_falltabelle():
    from core.naismith import stage_speeds

    trip = load_trip_from_dict(_trip_dict())
    for stage in trip.stages:
        want = FALL["erwartet"][stage.id]
        assert stage_speeds(trip, stage) == pytest.approx(
            (want["flat_kmh"], want["r_auf"], want["r_ab"])), stage.id


def test_loader_liest_etappen_grundtempo():
    trip = load_trip_from_dict(_trip_dict())
    nach_id = {s.id: s for s in trip.stages}
    assert nach_id["S2"].grundtempo_kmh == 3
    assert nach_id["S1"].grundtempo_kmh is None


def test_save_trip_rechnet_nur_die_ueberschriebene_etappe(tmp_path):
    """AC-2: S2 mit 3 km/h -> 11:20/13:36, S1 bleibt beim Trip-Tempo."""
    trip = load_trip_from_dict(_trip_dict())
    disk = json.loads(save_trip(trip, "u3197a", data_dir=tmp_path).read_text(encoding="utf-8"))
    assert _ankuenfte(disk) == {sid: e["ankuenfte"] for sid, e in FALL["erwartet"].items()}


# --- Persistenz / RMW (AC-4, AC-5) ---------------------------------------------

def test_roundtrip_ohne_feldverlust(tmp_path):
    """AC-5: Feld nur an S2 auf der Platte, uebrige Felder bleiben, Reload gleich."""
    trip = load_trip_from_dict(_trip_dict(S1={"start_time": "07:30"}))
    pfad = save_trip(trip, "u3197a", data_dir=tmp_path)
    disk = json.loads(pfad.read_text(encoding="utf-8"))
    nach_id = {st["id"]: st for st in disk["stages"]}
    assert nach_id["S2"]["grundtempo_kmh"] == 3
    assert "grundtempo_kmh" not in nach_id["S1"], "nur gesetzte Werte schreiben (omitempty)"
    assert disk["tempo"] == FALL["tempo"]
    assert nach_id["S1"]["start_time"] == "07:30"
    wieder = load_trip_from_dict(disk)
    assert {s.id: s.grundtempo_kmh for s in wieder.stages} == {"S1": None, "S2": 3}


def test_zuruecknehmen_entfernt_das_feld_gegen_den_plattenstand(tmp_path):
    """AC-4: Plattenstand traegt S2=3; der Trip ohne Ueberschreibung wird
    gespeichert -> Feld weg, S2 rechnet wieder wie das Trip-Tempo. Der
    RMW-Merge darf den alten Wert nicht wiederbeleben."""
    save_trip(load_trip_from_dict(_trip_dict()), "u3197a", data_dir=tmp_path)
    pfad = save_trip(load_trip_from_dict(_ohne_ueberschreibung()), "u3197a", data_dir=tmp_path)
    disk = json.loads(pfad.read_text(encoding="utf-8"))
    nach_id = {st["id"]: st for st in disk["stages"]}
    assert "grundtempo_kmh" not in nach_id["S2"]
    assert _ankuenfte(disk)["S2"] == FALL["erwartet"]["S1"]["ankuenfte"]


def test_zwei_nutzer_getrennt(tmp_path):
    """AC-5: Nutzer A setzt das Etappen-Tempo, Nutzer B (gleiche Trip-ID) bleibt unberuehrt."""
    pfad_b = save_trip(load_trip_from_dict(_ohne_ueberschreibung()), "u3197b", data_dir=tmp_path)
    vorher_b = pfad_b.read_bytes()
    pfad_a = save_trip(load_trip_from_dict(_trip_dict()), "u3197a", data_dir=tmp_path)
    assert pfad_a != pfad_b
    assert pfad_b.read_bytes() == vorher_b
    assert "u3197a" in str(pfad_a) and "default" not in str(pfad_a)


# --- Ungueltige Werte (AC-8) ---------------------------------------------------

@pytest.mark.parametrize("kmh", FALL["ungueltige_werte"] + [True, "3", None])
def test_ungueltiger_etappenwert_wird_ignoriert(tmp_path, kmh):
    """AC-8: Wert ausserhalb 0,5..60 oder kein Zahlwert -> Trip-Tempo, kein Absturz."""
    from core.naismith import stage_speeds

    trip = load_trip_from_dict(_trip_dict(S2={"grundtempo_kmh": kmh}))
    s2 = next(s for s in trip.stages if s.id == "S2")
    s1 = next(s for s in trip.stages if s.id == "S1")
    assert stage_speeds(trip, s2) == pytest.approx(stage_speeds(trip, s1))
    disk = json.loads(save_trip(trip, "u3197a", data_dir=tmp_path).read_text(encoding="utf-8"))
    assert _ankuenfte(disk)["S2"] == FALL["erwartet"]["S1"]["ankuenfte"]


# --- Bestand (AC-9) ------------------------------------------------------------

def test_bestand_ohne_ueberschreibung_unveraendert(tmp_path):
    """AC-9: ohne Etappenwert rechnet jede Etappe exakt wie das Trip-Tempo
    (08:00/10:30/12:12, wie vor #3197) und kein Feld wird hinzugefuegt."""
    from core.naismith import stage_speeds, tempo_speeds

    trip = load_trip_from_dict(_ohne_ueberschreibung())
    for stage in trip.stages:
        assert stage_speeds(trip, stage) == tempo_speeds(trip)
    disk = json.loads(save_trip(trip, "u3197a", data_dir=tmp_path).read_text(encoding="utf-8"))
    assert _ankuenfte(disk) == {"S1": ["08:00", "10:30", "12:12"], "S2": ["08:00", "10:30", "12:12"]}
    assert all("grundtempo_kmh" not in st for st in disk["stages"])


# --- Kanal-Quelle (AC-3) -------------------------------------------------------

def _segment_enden(trip, stage_id):
    from services.trip_segments import convert_trip_to_segments

    stage = next(s for s in trip.stages if s.id == stage_id)
    segmente = convert_trip_to_segments(trip, stage.date)
    return [s.end_time.astimezone(ORT).strftime("%H:%M") for s in segmente[:2]]


def test_kanal_segmente_aus_gespeichertem_trip(tmp_path):
    """AC-3: Nach dem Speichern liefern die Segmente (Quelle der bewerteten
    Stunden in allen vier Kanaelen) fuer S2 die Zeiten des Etappen-Tempos,
    fuer S1 unveraendert die des Trip-Tempos."""
    disk_mit = json.loads(save_trip(load_trip_from_dict(_trip_dict()), "u3197a",
                                    data_dir=tmp_path).read_text(encoding="utf-8"))
    disk_ohne = json.loads(save_trip(load_trip_from_dict(_ohne_ueberschreibung()), "u3197b",
                                     data_dir=tmp_path).read_text(encoding="utf-8"))
    mit, ohne = load_trip_from_dict(disk_mit), load_trip_from_dict(disk_ohne)
    assert _segment_enden(mit, "S2") == ["11:20", "13:36"]
    assert _segment_enden(ohne, "S2") == ["10:30", "12:12"]
    assert _segment_enden(mit, "S1") == _segment_enden(ohne, "S1") == ["10:30", "12:12"]


def test_self_heal_nutzt_etappen_tempo():
    """AC-3: Etappe ohne gespeicherte Ankuenfte (Self-Heal in
    convert_trip_to_segments und im Etappen-Wetter) rechnet mit dem
    Etappen-Tempo, nicht mit dem Trip-Tempo."""
    from services.stage_weather import _segments_for_stage

    trip = load_trip_from_dict(_trip_dict())
    s2 = next(s for s in trip.stages if s.id == "S2")
    assert all(wp.arrival_calculated is None for wp in s2.waypoints), "Messaufbau: Ankunft schon gespeichert"
    assert _segment_enden(trip, "S2") == ["11:20", "13:36"]
    enden = [s.end_time.astimezone(ORT).strftime("%H:%M") for s in _segments_for_stage(trip, s2)[:2]]
    assert enden == ["11:20", "13:36"]

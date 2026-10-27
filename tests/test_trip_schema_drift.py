"""
Trip-Schema-Drift-Gate, Python-Seite (#2058, Spec trip_schema_drift_gate).

Hintergrund: Der Merge beim Speichern ersetzt Listen als Ganzes. Ein
Wegpunkt-/Etappen-/Trip-Schluessel, den nur eines der beiden Modelle (Python
`app.loader` / Go `internal/model`) kennt, ginge beim Speichern still
verloren. Dieses Gate liest dieselbe voll besetzte Fixture wie der Go-Test
(`internal/model/trip_schema_drift_test.go`) und vergleicht die
Schluesselmengen je Ebene (Trip / Etappe / Wegpunkt) in BEIDE Richtungen.

Kein Mock: echter Lade-/Schreibpfad `_parse_trip` -> `_trip_to_dict`.
Die Fixture wird relativ zur Testdatei aufgeloest (Worktree-Falle).
"""

import copy
import json
from pathlib import Path

from app.loader import _parse_trip, _trip_to_dict

_HERE = Path(__file__).resolve().parent
FIXTURE = _HERE / "fixtures" / "trip_schema_full.json"
GATES_DOC = _HERE.parent / "docs" / "reference" / "gates_und_ratschen.md"

# Benannte Allowlist — IDENTISCH im Go-Test. Je Eintrag: Ebene, Seite, Grund.
# Keine Pauschal-Ausnahme; ein Eintrag, der in keinem Modell mehr vorkommt,
# macht den Test rot (keine Karteileichen).
ALLOWLIST = {
    ("trip", "send_premium_sms"): (
        "go_only",
        "in Go aus report_config.send_premium_sms abgeleitet (store/trip.go)",
    ),
    ("trip", "trip"): (
        "python_only",
        "Python-Legacy-Wrapper in KNOWN_TOP_LEVEL, wird nie geschrieben",
    ),
}


def _load_fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _roundtrip(data: dict):
    trip = _parse_trip(copy.deepcopy(data))
    return trip, _trip_to_dict(trip)


def _levels(d: dict) -> dict:
    """Schluesselmengen je Ebene: trip / stage / waypoint."""
    stage = d["stages"][0]
    wp = stage["waypoints"][0]
    return {"trip": set(d), "stage": set(stage), "waypoint": set(wp)}


def _drift(expected: dict, actual: dict) -> list:
    """Befunde `<ebene>: nur in <seite>: <schluessel>` — beide Richtungen."""
    befunde = []
    exp, act = _levels(expected), _levels(actual)
    for ebene in exp:
        for key in sorted(exp[ebene] - act[ebene]):
            befunde.append(f"{ebene}: nur in Fixture (Python verwirft): {key}")
        for key in sorted(act[ebene] - exp[ebene]):
            befunde.append(f"{ebene}: nur in Python-Ausgabe (nicht in Fixture): {key}")
    return befunde


def test_python_roundtrip_schluesselmengen_stimmen_mit_fixture_ueberein():
    """AC-1: Trip-, Etappen- und Wegpunkt-Schluessel sind nach Roundtrip gleich."""
    fixture = _load_fixture()
    trip, out = _roundtrip(fixture)
    assert _drift(fixture, out) == []
    # Unbekannte Top-Level-Schluessel landen in trip.extra und wuerden von
    # _trip_to_dict re-emittiert — ein einseitiges Go-Feld in der Fixture
    # bliebe sonst unsichtbar. Das Modell muss ALLE Fixture-Schluessel kennen.
    assert trip.extra == {}, f"Python kennt diese Trip-Schluessel nicht: {sorted(trip.extra)}"


def test_fixture_ist_voll_besetzt_auf_wegpunkt_ebene():
    """Voraussetzung fuer AC-1/AC-4: suggestion_reason muss in der Fixture stehen."""
    wp = _load_fixture()["stages"][0]["waypoints"][0]
    assert wp.get("suggestion_reason"), "Fixture ohne suggestion_reason macht AC-4 blind"


def test_einseitiges_wegpunktfeld_wird_mit_ebene_und_schluessel_gemeldet():
    """AC-3 (Richtung Fixture->Python): neues Feld nur im anderen Modell wird rot."""
    fixture = _load_fixture()
    fixture["stages"][0]["waypoints"][0]["nur_im_anderen_modell"] = "x"
    _, out = _roundtrip(fixture)
    befunde = _drift(fixture, out)
    assert befunde, "Drift-Vergleich erkennt ein einseitiges Wegpunktfeld nicht"
    assert any("waypoint" in b and "nur_im_anderen_modell" in b for b in befunde)


def test_einseitiges_etappenfeld_wird_mit_ebene_und_schluessel_gemeldet():
    """AC-3: gleiche Probe auf Etappen-Ebene."""
    fixture = _load_fixture()
    fixture["stages"][0]["nur_im_anderen_modell"] = "x"
    _, out = _roundtrip(fixture)
    befunde = _drift(fixture, out)
    assert any("stage" in b and "nur_im_anderen_modell" in b for b in befunde)


def test_einseitiges_tripfeld_wird_vom_extra_pruefer_gemeldet():
    """AC-3: Trip-Ebene — unbekannter Schluessel faellt in trip.extra auf."""
    fixture = _load_fixture()
    fixture["nur_im_anderen_modell"] = "x"
    trip, _ = _roundtrip(fixture)
    assert "nur_im_anderen_modell" in trip.extra


def test_allowlist_eintraege_existieren_noch_und_sind_nicht_in_der_fixture():
    """AC-5: keine Karteileichen, keine Pauschal-Ausnahme."""
    fixture = _load_fixture()
    for (ebene, key), (seite, _grund) in ALLOWLIST.items():
        assert ebene == "trip"
        assert key not in fixture, f"{key} gehoert nicht in die gemeinsame Fixture"
        if seite == "go_only":
            # Python darf den Schluessel nicht kennen: bei Wert in der Datei
            # laeuft er nur ueber das generische extra-Auffangnetz.
            probe = dict(fixture, **{key: True})
            trip, out = _roundtrip(probe)
            assert key in trip.extra, f"{key} ist in Python jetzt modelliert — Allowlist-Eintrag veraltet"
        else:
            # python_only: das Modell muss den Schluessel als bekannt behandeln
            # (KNOWN_TOP_LEVEL), er darf weder in extra noch in der Ausgabe stehen.
            probe = dict(fixture, **{key: {}})
            trip, out = _roundtrip(probe)
            assert key not in trip.extra, f"{key} nicht mehr in KNOWN_TOP_LEVEL — Allowlist-Eintrag veraltet"
            assert key not in out


def test_unlisteter_einseitiger_schluessel_wuerde_rot():
    """AC-5: die Allowlist ist exakt, kein Pauschal-Durchlass."""
    erlaubt = {key for (_e, key) in ALLOWLIST}
    assert "suggestion_reason" not in erlaubt
    assert erlaubt == {"send_premium_sms", "trip"}


def test_gates_doku_fuehrt_das_gate_mit_pruefdatum():  # doc-compliance-test
    """AC-7: Eintrag in gates_und_ratschen.md mit Pruefdatum 2027-01-03."""
    text = GATES_DOC.read_text(encoding="utf-8")
    assert "trip_schema_drift" in text, "Gate fehlt in gates_und_ratschen.md"
    zeilen = [z for z in text.splitlines() if "trip_schema_drift" in z]
    assert any("2027-01-03" in z for z in zeilen), "Pruefdatum 2027-01-03 fehlt beim Gate-Eintrag"

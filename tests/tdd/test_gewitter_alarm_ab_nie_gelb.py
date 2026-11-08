"""Gewitter-„Alarm ab“ nie gelb (#2793 S2a, ADR-0106 P2).

Spec: docs/specs/modules/feat_2793_s2_alarm_stufenwechsel.md §2, AC-8
(Python-Seite): eine Datei mit Gewitter ``alarm_ab: "yellow"`` wird beim Laden
protokolliert und durch die Vorgabe der Vorlage ersetzt. Kein Mock: echter
Loader auf ``tmp_path``, echte Aufloesung. Fixture relativ zur Testdatei.
"""

import json
import logging
from pathlib import Path

import pytest

from app.ampel import resolve_ampel, validate_ampel
from app.ampel_templates import AMPEL_TEMPLATES
from app.loader import load_trip, save_trip

FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "trip_schema_full.json"


def _trip_datei(tmp_path, user, ampel):
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    data["display_config"] = {"preset_name": "wassersport", "metrics": [], "ampel": ampel}
    pfad = tmp_path / "users" / user / "briefings" / "drift-gate-trip.json"
    pfad.parent.mkdir(parents=True)
    pfad.write_text(json.dumps(data), encoding="utf-8")
    return pfad


@pytest.mark.parametrize("stufe, gueltig", [
    ("never", True), ("orange", True), ("red", True), ("yellow", False)])
def test_gewitter_erlaubt_nur_nie_orange_rot(stufe, gueltig):
    fehler = validate_ampel({"metrics": {"thunder": {"alarm_ab": stufe}}})
    assert (fehler == []) is gueltig, fehler
    # andere Metriken duerfen weiter gelb
    assert validate_ampel({"metrics": {"gust": {"alarm_ab": "yellow"}}}) == []


@pytest.mark.parametrize("tid", list(AMPEL_TEMPLATES))
def test_keine_vorlage_setzt_gewitter_auf_gelb(tid):
    assert AMPEL_TEMPLATES[tid]["metrics"]["thunder"]["alarm_ab"] in {"never", "orange", "red"}


def test_ac8_loader_ersetzt_gewitter_gelb_durch_vorlage_und_protokolliert(tmp_path, caplog):
    kaputt = {"template": "wassersport", "metrics": {
        "thunder": {"alarm_ab": "yellow"}, "gust": {"alarm_ab": "red"}}}
    pfad = _trip_datei(tmp_path, "anna", kaputt)
    gut = _trip_datei(tmp_path, "bert", {"template": "wassersport",
                                         "metrics": {"thunder": {"alarm_ab": "red"}}})
    with caplog.at_level(logging.WARNING):
        trip = load_trip("drift-gate-trip", data_dir=tmp_path, user_id="anna")
    assert trip.display_config.ampel is None
    assert any("drift-gate-trip" in r.getMessage() and "thunder.alarm_ab" in r.getMessage()
               for r in caplog.records)
    vorlage = AMPEL_TEMPLATES["wassersport"]["metrics"]
    wirksam = resolve_ampel(trip)["metrics"]
    assert wirksam["thunder"]["alarm_ab"] == vorlage["thunder"]["alarm_ab"]
    assert wirksam["gust"]["alarm_ab"] == vorlage["gust"]["alarm_ab"]  # ganze Ampel verworfen
    save_trip(trip, "anna", tmp_path)  # Datei behaelt die Altdaten (kein Datenverlust)
    assert json.loads(pfad.read_text(encoding="utf-8"))["display_config"]["ampel"] == kaputt
    # zweiter Nutzer mit gueltiger Gewitter-Stufe bleibt unberuehrt
    bert = load_trip("drift-gate-trip", data_dir=tmp_path, user_id="bert")
    assert resolve_ampel(bert)["metrics"]["thunder"]["alarm_ab"] == "red"
    assert json.loads(gut.read_text(encoding="utf-8"))["display_config"]["ampel"]["metrics"] == \
        {"thunder": {"alarm_ab": "red"}}

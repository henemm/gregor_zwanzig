"""Profil-Ampel S1b (#2792): Batch-Migration der Bestandsdaten.

Spec: docs/specs/modules/feat_2792_s1_profil_ampel.md §4, AC-8 bis AC-12,
AC-17. Kein Mock: echter Datenbaum ``<root>/<uid>/briefings/*.json`` in
``tmp_path``, Skript als Subprozess, Pruefung mit echtem Loader, ``ampel_for``
und dem Renderer-Filter der Stundentabelle. Pruefling relativ zur Testdatei.
"""

import copy
import hashlib
import json
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest

from app.ampel import ampel_for
from app.loader import compare_preset_from_dict, load_trip_from_dict
from app.metric_catalog import get_metric
from output.metric_format import severity_from_thresholds
from output.renderers.email.html import _allowed_col_keys_for_horizon

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "migrate_2792_profil_ampel.py"
NUR_HEUTE = {"today": True, "tomorrow": False, "day_after": False}
ALLE = {"today": True, "tomorrow": True, "day_after": True}


def _m(mid, **kw):
    return {"metric_id": mid, "enabled": True, **kw}


def _trip(tid, preset, corridors, metrics=None, **extra):
    dc = {"metrics": metrics or [_m("wind")], "metric_alert_levels": {"wind_gust": "warn"},
          "alert_preset": "standard", "zukunft_dc": {"x": 1}}
    if preset:
        dc["preset_name"] = preset
    return {"id": tid, "name": tid, "kind": "route", "stages": [], "corridors": corridors,
            "alert_rules": [{"id": "r1", "kind": "delta", "metric": "wind_gust", "threshold": 5,
                             "enabled": True, "channels": ["email"]}],
            "display_config": dc, "zukunft_top": "bleibt", **extra}


def _band(metric, von, bis, mark=True, notify=False):
    return {"metric": metric, "range": [von, bis], "notify": notify, "mark": mark}


def _cmp(cid, profil, active, corridors=(), **dc):
    return {"id": cid, "name": cid, "kind": "vergleich", "profil": profil,
            "location_ids": ["a", "b", "c"], "corridors": list(corridors),
            "display_config": {"active_metrics": active, "metric_alert_levels": {"cape": "warn"}, **dc}}


def _wind_hz():
    return _m("wind", horizons=dict(NUR_HEUTE), sms_threshold=20)


def _baum(root: Path) -> None:
    alice = {
        "trip-wandern": _trip("trip-wandern", "wandern", [
            _band("temperature", 0, 20), _band("wind_gust", None, 5, mark=False, notify=True)],
            metrics=[_wind_hz(), _m("cape"), _m("thunder", enabled=False)]),
        "trip-ski": _trip("trip-ski", "skitouren", []),
        "cmp-sommer": _cmp(
            "cmp-sommer", "summer_trekking",
            [{"metric_id": "temperature", "aggregation": "max"}, {"metric_id": "cape", "aggregation": "max"}],
            [_band("temp_max_c", 10, 25)],
            ideal_ranges={"temp_max_c": {"min": 0, "max": 40}, "gust_max_kmh": {"min": None, "max": 40}},
            metrics=[_m("wind", horizons=dict(NUR_HEUTE))]),
    }
    alice["trip-wandern"]["display_config"]["channel_layouts"] = {"sms": [_wind_hz()]}
    alice["trip-wandern"]["display_config"]["channel_layouts_per_report"] = {"morning": {"email": [_wind_hz()]}}
    bob = {
        "trip-bob": _trip("trip-bob", None, [_band("wind_gust", None, 50), _band("thunder_level", None, 2)]),
        "trip-kaputt": _trip("trip-kaputt", None, [_band("temperature", 30, 10)]),
        "trip-fertig": _trip("trip-fertig", None, []),
        # Bereich ohne mark (abgeschaltet) existiert: ideal_ranges darf ihn nicht wiederbeleben.
        "cmp-winter": _cmp("cmp-winter", "wintersport", ["temp_max_c", "cape_max_jkg"],
                           [_band("gust_max_kmh", None, 30, mark=False)],
                           ideal_ranges={"gust_max_kmh": {"min": None, "max": 40}}),
    }
    bob["trip-fertig"]["display_config"]["ampel"] = {"template": "allgemein"}
    for uid, dateien in (("alice", alice), ("bob", bob)):
        (root / uid / "briefings").mkdir(parents=True)
        for name, obj in dateien.items():  # trip-fertig kompakt: ein Neuschreiben fiele auf
            (root / uid / "briefings" / f"{name}.json").write_text(json.dumps(
                obj, indent=None if name == "trip-fertig" else 2, ensure_ascii=False), encoding="utf-8")
    (root / "alice" / "metric_presets.json").write_text(json.dumps(
        [{"id": "mp1", "name": "Mein Gipfel", "is_default": False,
          "metrics": [{"metric_id": "wind", "enabled": True, "horizons": NUR_HEUTE}]}], indent=2))


@pytest.fixture
def root(tmp_path):
    r = tmp_path / "users"
    _baum(r)
    return r


def _lauf(root, *args):
    res = subprocess.run([sys.executable, str(SCRIPT), "--root", str(root),
                          "--backup-dir", str(root.parent / "sicherung"), *args],
                         capture_output=True, text=True, timeout=60)
    assert res.returncode == 0, res.stderr
    return res.stdout


def _summen(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*")) if p.is_file()}


def _lies(root, uid, name):
    return json.loads((root / uid / "briefings" / f"{name}.json").read_text(encoding="utf-8"))


def _abschnitt(out, uid):
    return out.split(f"== Nutzer {uid} ==")[1].split("== Nutzer ")[0]


# --- Ablauf (AC-12) ---------------------------------------------------------

def test_probelauf_schreibt_nichts_und_berichtet_je_nutzer(root):
    vorher = _summen(root)
    out = _lauf(root)
    assert _summen(root) == vorher
    assert not (root.parent / "sicherung").exists()
    assert "== Nutzer alice ==" in out and "== Nutzer bob ==" in out


def test_execute_sichert_je_nutzer_vor_dem_schreiben(root):
    original = {uid: (root / uid / "briefings" / "trip-ski.json").read_bytes() if uid == "alice"
                else (root / uid / "briefings" / "trip-bob.json").read_bytes() for uid in ("alice", "bob")}
    _lauf(root, "--execute")
    archive = sorted((root.parent / "sicherung").glob("*.tar.gz"))
    assert [a.name.split("-")[2] for a in archive] == ["alice", "bob"]
    for archiv, uid, name in ((archive[0], "alice", "trip-ski"), (archive[1], "bob", "trip-bob")):
        with tarfile.open(archiv) as tar:
            namen = tar.getnames()
            assert all(n.startswith(f"{uid}/") for n in namen), namen
            assert tar.extractfile(f"{uid}/briefings/{name}.json").read() == original[uid]
    assert _lies(root, "alice", "trip-ski")["display_config"]["ampel"]["template"] == "skitouren"


def test_zweiter_execute_aendert_keine_datei(root):
    _lauf(root, "--execute")
    nach_erstem = _summen(root)
    out = _lauf(root, "--execute")
    assert _summen(root) == nach_erstem
    assert "Nichts zu tun" in out and "Sicherung geschrieben" not in out


def test_zwei_nutzer_bleiben_getrennt_ohne_default(root):
    out = _lauf(root, "--execute")
    assert not (root / "default").exists()
    assert "trip-bob" not in _abschnitt(out, "alice") and "trip-wandern" not in _abschnitt(out, "bob")
    assert _lies(root, "alice", "trip-wandern")["display_config"]["ampel"]["template"] == "wandern"
    assert _lies(root, "bob", "trip-bob")["display_config"]["ampel"]["template"] == "allgemein"


def test_unberuehrte_felder_und_dateien_bleiben_gleich(root):
    vorher = {n: _lies(root, "alice", n) for n in ("trip-wandern", "cmp-sommer")}
    fertig = (root / "bob" / "briefings" / "trip-fertig.json").read_bytes()
    presets = (root / "alice" / "metric_presets.json").read_bytes()
    out = _lauf(root, "--execute")
    assert (root / "bob" / "briefings" / "trip-fertig.json").read_bytes() == fertig
    assert (root / "alice" / "metric_presets.json").read_bytes() == presets
    assert "Mein Gipfel" in _abschnitt(out, "alice")
    for name, alt in vorher.items():
        neu = _lies(root, "alice", name)
        assert {k: v for k, v in neu.items() if k != "display_config"} == \
            {k: v for k, v in alt.items() if k != "display_config"}
        bewegt = {"ampel", "metrics", "channel_layouts", "channel_layouts_per_report", "active_metrics"}
        assert {k: v for k, v in neu["display_config"].items() if k not in bewegt} == \
            {k: v for k, v in alt["display_config"].items() if k not in bewegt}


# --- Abbildung der Wertebereiche (AC-8, AC-9) --------------------------------

def test_ac8_temperaturband_wird_gruenes_fenster_der_vorlage_wandern(root):
    _lauf(root, "--execute")
    trip = _lies(root, "alice", "trip-wandern")
    t = trip["display_config"]["ampel"]["metrics"]["temperature"]
    assert t == {"lower": {"red": -10, "orange": -5, "yellow": 0},
                 "upper": {"yellow": 20.1, "orange": 30, "red": 33}}
    schwellen = ampel_for(load_trip_from_dict(trip))["temperature"]
    assert severity_from_thresholds(schwellen, 20.0) == "green"
    assert severity_from_thresholds(schwellen, 20.1) == "yellow"
    assert severity_from_thresholds(schwellen, 0) == "green"
    assert severity_from_thresholds(schwellen, -0.1) == "yellow"


def test_klemm_regel_verschiebt_ganze_seite_unbekanntes_bleibt(root):
    out = _abschnitt(_lauf(root, "--execute"), "bob")
    trip = _lies(root, "bob", "trip-bob")
    assert trip["display_config"]["ampel"]["metrics"]["gust"] == \
        {"upper": {"yellow": 51, "orange": 66, "red": 81}}  # allgemein 30/45/60, +21
    assert "verschoben um +21" in out and "nicht zuordenbar: thunder_level" in out
    assert _band("thunder_level", None, 2) in trip["corridors"]


def test_unheilbare_reihenfolge_wird_uebersprungen_altdaten_bleiben(root):
    out = _lauf(root, "--execute")
    trip = _lies(root, "bob", "trip-kaputt")
    assert "temperature" not in trip["display_config"]["ampel"].get("metrics", {})
    assert trip["corridors"] == [_band("temperature", 30, 10)]
    assert "übersprungen: temperature" in _abschnitt(out, "bob")


def test_ac9_delta_bereich_bleibt_erhalten_ohne_ampelgrenze(root):
    out = _lauf(root, "--execute")
    trip = _lies(root, "alice", "trip-wandern")
    assert _band("wind_gust", None, 5, mark=False, notify=True) in trip["corridors"]
    assert "gust" not in trip["display_config"]["ampel"]["metrics"]
    assert "Δ-Bereich wind_gust [None, 5]" in _abschnitt(out, "alice")


def _ein_trip(tmp_path, obj):
    r = tmp_path / "einzel"
    (r / "carla" / "briefings").mkdir(parents=True)
    (r / "carla" / "briefings" / "x.json").write_text(json.dumps(obj), encoding="utf-8")
    out = _lauf(r, "--execute")
    return _lies(r, "carla", "x")["display_config"]["ampel"], out


def test_metrik_zuordnung_der_trip_schluessel(tmp_path):
    ampel, out = _ein_trip(tmp_path, _trip("x", "wandern", [
        _band("precipitation_sum", None, 3), _band("temperature_max", 5, 25),
        _band("snow_line", 1000, None), _band("wind_gust", None, 45)]))
    m = ampel["metrics"]
    assert m["precipitation"] == {"upper": {"yellow": 3.1, "orange": 5, "red": 10}}
    assert m["temperature"] == {"upper": {"yellow": 25.1, "orange": 30, "red": 33}}
    assert m["snowfall_limit"] == {"lower": {"red": -300, "orange": 0, "yellow": 1000}}
    assert m["gust"] == {"upper": {"yellow": 46, "orange": 60, "red": 75}}
    assert "temperature_max" in out and "von=5 nicht übernommen" in out
    ampel_min, out = _ein_trip(tmp_path / "b", _trip("x", "wandern", [_band("temperature_min", 2, 30)]))
    assert ampel_min["metrics"]["temperature"] == {"lower": {"red": -10, "orange": -5, "yellow": 2}}
    assert "bis=30 nicht übernommen" in out


def test_vorhandene_ampel_wird_nie_ueberschrieben_nur_ergaenzt(tmp_path):
    trip = _trip("x", "skitouren", [_band("temperature", 0, 20), _band("wind_gust", None, 45)])
    eigene = {"upper": {"yellow": 5, "orange": 8, "red": 15}}
    trip["display_config"]["ampel"] = {"metrics": {"temperature": copy.deepcopy(eigene)}}
    ampel, _ = _ein_trip(tmp_path, trip)
    assert ampel["template"] == "skitouren"
    assert ampel["metrics"]["temperature"] == eigene
    assert ampel["metrics"]["gust"] == {"upper": {"yellow": 46, "orange": 55, "red": 70}}


def test_compare_bereiche_und_ideal_ranges_nur_als_rueckfall(root):
    _lauf(root, "--execute")
    preset = _lies(root, "alice", "cmp-sommer")
    m = preset["display_config"]["ampel"]["metrics"]
    assert preset["display_config"]["ampel"]["template"] == "alpen-trekking"
    assert m["temperature"] == {"lower": {"red": -10, "orange": -3, "yellow": 10},
                                "upper": {"yellow": 25.1, "orange": 30, "red": 33}}
    assert m["gust"] == {"upper": {"yellow": 41, "orange": 50, "red": 70}}
    assert preset["display_config"]["ideal_ranges"]["temp_max_c"] == {"min": 0, "max": 40}


# --- sms_threshold, horizons, CAPE (AC-10, AC-11) ----------------------------

def test_ac10_sms_threshold_bleibt_an_allen_drei_stellen_ohne_wirkung(root):
    out = _abschnitt(_lauf(root, "--execute"), "alice")
    dc = _lies(root, "alice", "trip-wandern")["display_config"]
    assert dc["metrics"][0]["sms_threshold"] == 20
    assert dc["channel_layouts"]["sms"][0]["sms_threshold"] == 20
    assert dc["channel_layouts_per_report"]["morning"]["email"][0]["sms_threshold"] == 20
    for ort in ("metrics", "channel_layouts.sms", "channel_layouts_per_report.morning.email"):
        assert f"sms_threshold wind=20 in {ort}" in out
    assert "wind" not in dc["ampel"]["metrics"]
    trip = load_trip_from_dict(_lies(root, "alice", "trip-wandern"))
    assert ampel_for(trip)["wind"] == ampel_for({"display_config": {"preset_name": "wandern"}})["wind"]


def test_ac11_alle_tage_und_gewitter_aktiv_stundentabelle_zeigt_alle_tage(root):
    vorher = load_trip_from_dict(_lies(root, "alice", "trip-wandern")).display_config
    wind = get_metric("wind").col_key
    assert wind not in _allowed_col_keys_for_horizon(vorher, "day_after")
    _lauf(root, "--execute")
    data = _lies(root, "alice", "trip-wandern")
    dc = data["display_config"]
    for liste in (dc["metrics"], dc["channel_layouts"]["sms"], dc["channel_layouts_per_report"]["morning"]["email"]):
        assert liste[0]["horizons"] == ALLE
    assert {"metric_id": "thunder", "enabled": True} in dc["metrics"]
    assert any(e["metric_id"] == "cape" for e in dc["metrics"])
    nachher = load_trip_from_dict(data).display_config
    for tag in ("today", "tomorrow", "day_after"):
        assert {wind, get_metric("thunder").col_key} <= _allowed_col_keys_for_horizon(nachher, tag)
    sommer = _lies(root, "alice", "cmp-sommer")["display_config"]
    assert sommer["metrics"][0]["horizons"] == ALLE
    assert {"metric_id": "thunder", "aggregation": "max"} in sommer["active_metrics"]
    assert _lies(root, "bob", "cmp-winter")["display_config"]["active_metrics"] == \
        ["temp_max_c", "cape_max_jkg", "thunder_level_max"]


# --- Vorlage und Alarmfelder (AC-17) ----------------------------------------

def test_ac17_vorlage_gesetzt_und_alarmfelder_unveraendert(root):
    alt_ski, alt_win = _lies(root, "alice", "trip-ski"), _lies(root, "bob", "cmp-winter")
    _lauf(root, "--execute")
    ski, win = _lies(root, "alice", "trip-ski"), _lies(root, "bob", "cmp-winter")
    assert ski["display_config"]["ampel"] == {"template": "skitouren"}
    assert win["display_config"]["ampel"] == {"template": "wintersport"}
    assert ampel_for(load_trip_from_dict(ski)) == ampel_for({"display_config": {"ampel": {"template": "skitouren"}}})
    assert ampel_for(compare_preset_from_dict(win)) == \
        ampel_for({"display_config": {"ampel": {"template": "wintersport"}}})
    for alt, neu in ((alt_ski, ski), (alt_win, win)):
        assert neu.get("alert_rules") == alt.get("alert_rules")
        for k in ("metric_alert_levels", "alert_preset"):
            assert neu["display_config"].get(k) == alt["display_config"].get(k)

"""Alarm nach Stufenwechsel S2a (#2793): Altstufen -> ``ampel.metrics.<id>.alarm_ab``.

Spec: docs/specs/modules/feat_2793_s2_alarm_stufenwechsel.md §5 (ADR-0106 P3),
AC-15, AC-16, AC-17. Kein Mock: echter Datenbaum ``<root>/<uid>/briefings``
in ``tmp_path``, Skript als Subprozess, Nachpruefung mit echtem Loader und
``resolve_ampel``. Pruefling relativ zur Testdatei.
"""

import hashlib
import importlib.util
import json
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest

from app.ampel import resolve_ampel
from app.loader import compare_preset_from_dict, load_trip, save_trip
from app.models import AlertMetric

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "migrate_2793_alarm_ab.py"
AC15 = {"wind_gust": "sensibel", "precipitation_sum": "standard", "thunder_level": "sensibel",
        "temperature_min": "sensibel", "temperature_max": "entspannt", "cape": "sensibel",
        "freezing_level": "entspannt"}


def _trip(tid, levels=None, preset=None, ampel=None):
    dc = {"metrics": [{"metric_id": "gust", "enabled": True}], "alert_preset": "standard",
          "zukunft_dc": {"x": [1, 2]}}
    if levels is not None:
        dc["metric_alert_levels"] = levels
    if preset:
        dc["preset_name"] = preset
    if ampel is not None:
        dc["ampel"] = ampel
    return {"id": tid, "name": tid, "kind": "route", "stages": [], "zukunft_top": "bleibt",
            "alert_rules": [{"id": "r1", "metric": "wind_gust", "enabled": True}], "display_config": dc}


def _cmp(cid, profil, levels):
    return {"id": cid, "name": cid, "kind": "vergleich", "profil": profil, "location_ids": ["a", "b", "c"],
            "display_config": {"active_metrics": ["gust_max_kmh"], "metric_alert_levels": levels}}


def _baum(root: Path) -> None:
    dateien = {
        "alice": {
            "trip-ac15": _trip("trip-ac15", dict(AC15), ampel={"template": "allgemein"}),
            "trip-ohne": _trip("trip-ohne"),
            "cmp-winter": _cmp("cmp-winter", "wintersport",
                               {"fresh_snow": "sensibel", "gust_max_kmh": "off", "precipitation_change": "robust"}),
            "trip-gleich": _trip("trip-gleich", {"fresh_snow": "standard", "wind_gust": "sensibel"}),
        },
        "bob": {
            "trip-ski": _trip("trip-ski", {"fresh_snow": "off", "wind_gust": "entspannt"}, ampel={
                "template": "wintersport", "metrics": {"gust": {"upper": {"yellow": 41, "orange": 55, "red": 70}}}}),
            "cmp-sommer": _cmp("cmp-sommer", "summer_trekking", {
                "thunder_level": "entspannt", "temperature_change": "sensibel", "wind_change": "standard",
                "visibility": "sensibel", "snow_line": "sensibel", "thunder_onset": "standard",
                "precipitation_heavy_onset": "off", "humidity": "sensibel", "wind_chill": "sensibel"}),
            "trip-gleich": _trip("trip-gleich", {"fresh_snow": "standard", "wind_gust": "sensibel"}, "wintersport"),
            "trip-kaputt": _trip("trip-kaputt", {"wind_gust": "off"},
                                 ampel={"metrics": {"gust": {"upper": {"yellow": 50, "orange": 45}}}}),
        },
    }
    for uid, objs in dateien.items():
        (root / uid / "briefings").mkdir(parents=True)
        for name, obj in objs.items():
            (root / uid / "briefings" / f"{name}.json").write_text(
                json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


@pytest.fixture
def root(tmp_path):
    r = tmp_path / "users"
    _baum(r)
    return r


def _lauf(root, *args, code=0):
    res = subprocess.run([sys.executable, str(SCRIPT), "--root", str(root),
                          "--backup-dir", str(root.parent / "sicherung"), *args],
                         capture_output=True, text=True, timeout=60)
    assert res.returncode == code, res.stdout + res.stderr
    return res.stdout


def _lies(root, uid, name):
    return json.loads((root / uid / "briefings" / f"{name}.json").read_text(encoding="utf-8"))


def _alarm_ab(root, uid, name):
    metrics = _lies(root, uid, name)["display_config"].get("ampel", {}).get("metrics", {})
    return {mid: e["alarm_ab"] for mid, e in metrics.items() if "alarm_ab" in e}


def _summen(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*")) if p.is_file()}


def _abschnitt(out, uid):
    return out.split(f"== Nutzer {uid} ==")[1].split("== Nutzer ")[0]


def _modul():
    spec = importlib.util.spec_from_file_location("migrate_2793", SCRIPT)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def test_probelauf_schreibt_nichts_und_berichtet_je_nutzer(root):
    vorher = _summen(root)
    out = _lauf(root)
    assert _summen(root) == vorher and not (root.parent / "sicherung").exists()
    assert "Probelauf" in out and "== Nutzer alice ==" in out and "== Nutzer bob ==" in out


def test_ac15_abbildung_relativ_zur_vorlage_allgemein(root):
    out = _abschnitt(_lauf(root, "--execute"), "alice")
    assert _alarm_ab(root, "alice", "trip-ac15") == {
        "gust": "yellow", "precipitation": "orange", "thunder": "orange", "temperature": "yellow"}
    assert "Konflikt temperature" in out
    assert "nicht abgebildet: cape" in out and "nicht abgebildet: freezing_level" in out


def test_ac15_alle_uebrigen_felder_bleiben_gleich(root):
    vorher = _lies(root, "alice", "trip-ac15")
    _lauf(root, "--execute")
    nachher = _lies(root, "alice", "trip-ac15")
    assert {k: v for k, v in nachher.items() if k != "display_config"} == \
        {k: v for k, v in vorher.items() if k != "display_config"}
    dc_alt, dc_neu = vorher["display_config"], nachher["display_config"]
    assert {k: v for k, v in dc_neu.items() if k not in ("ampel", "alarm_ab_migration")} == dc_alt
    assert json.dumps(dc_neu["metric_alert_levels"]) == json.dumps(dc_alt["metric_alert_levels"])
    assert dc_neu["alarm_ab_migration"] == "2793"
    assert dc_neu["ampel"]["template"] == "allgemein"
    assert all(set(e) == {"alarm_ab"} for e in dc_neu["ampel"]["metrics"].values())


def test_vorhandene_ampel_behaelt_grenzen_und_vorlage(root):
    _lauf(root, "--execute")
    ampel = _lies(root, "bob", "trip-ski")["display_config"]["ampel"]
    assert ampel["template"] == "wintersport"
    assert ampel["metrics"]["gust"] == {"upper": {"yellow": 41, "orange": 55, "red": 70}, "alarm_ab": "red"}
    assert ampel["metrics"]["fresh_snow"] == {"alarm_ab": "never"}


def test_ac16_vorgabe_nie_sensibel_wird_rot_off_wird_nie(root):
    out = _lauf(root, "--execute")
    assert _alarm_ab(root, "alice", "cmp-winter") == {"fresh_snow": "red", "gust": "never"}
    assert "unbekannter Wert: precipitation_change=robust" in _abschnitt(out, "alice")
    assert _alarm_ab(root, "bob", "trip-ski")["fresh_snow"] == "never"


def test_vergleich_delta_metriken_d4_und_vorboten(root):
    out = _abschnitt(_lauf(root, "--execute"), "bob")
    assert _alarm_ab(root, "bob", "cmp-sommer") == {
        "thunder": "red", "temperature": "yellow", "wind": "orange", "visibility": "yellow"}
    for key in ("freezing_level", "thunder_onset", "precipitation_heavy_onset", "humidity", "wind_chill"):
        assert f"nicht abgebildet: {key}" in out, key
    preset = compare_preset_from_dict(_lies(root, "bob", "cmp-sommer"))
    assert preset.display_config["metric_alert_levels"]["snow_line"] == "sensibel"
    assert resolve_ampel(preset)["metrics"]["thunder"]["alarm_ab"] == "red"


def test_ungueltige_ampel_wird_nicht_angefasst(root):
    vorher = (root / "bob" / "briefings" / "trip-kaputt.json").read_bytes()
    out = _abschnitt(_lauf(root, "--execute"), "bob")
    assert (root / "bob" / "briefings" / "trip-kaputt.json").read_bytes() == vorher
    assert "Ampel ungültig" in out


def test_abo_ohne_altstufen_bleibt_byte_gleich(root):
    vorher = (root / "alice" / "briefings" / "trip-ohne.json").read_bytes()
    _lauf(root, "--execute")
    assert (root / "alice" / "briefings" / "trip-ohne.json").read_bytes() == vorher


def test_ac16_zweiter_lauf_nichts_zu_tun(root):
    _lauf(root, "--execute")
    nach_erstem = _summen(root)
    out = _lauf(root, "--execute")
    assert _summen(root) == nach_erstem
    assert "Nichts zu tun" in out and "Sicherung geschrieben" not in out


def test_ac16_ac17_sicherung_je_nutzer_vor_dem_schreiben_nur_eigene_dateien(root):
    original = {uid: {p.name: p.read_bytes() for p in (root / uid / "briefings").glob("*.json")}
                for uid in ("alice", "bob")}
    _lauf(root, "--execute")
    archive = sorted((root.parent / "sicherung").glob("migrate-2793-*.tar.gz"))
    assert [a.name.split("-")[2] for a in archive] == ["alice", "bob"]
    for archiv, uid in zip(archive, ("alice", "bob")):
        with tarfile.open(archiv) as tar:
            namen = [n for n in tar.getnames() if n.endswith(".json")]
            assert namen and all(n.startswith(f"{uid}/briefings/") for n in tar.getnames())
            for n in namen:
                assert tar.extractfile(n).read() == original[uid][Path(n).name]


def test_ac17_zwei_nutzer_je_eigene_vorlage(root):
    _lauf(root, "--execute")
    assert _alarm_ab(root, "alice", "trip-gleich") == {"fresh_snow": "orange", "gust": "yellow"}
    assert _alarm_ab(root, "bob", "trip-gleich") == {"fresh_snow": "never", "gust": "yellow"}
    assert not (root / "default").exists()
    for p in (root / "bob").rglob("*.json"):
        assert "trip-ac15" not in p.read_text(encoding="utf-8") and "cmp-winter" not in p.name


def test_ac16_waehrend_des_laufs_geaenderte_datei_wird_uebersprungen(root):
    mig = _modul()
    pfad = root / "alice" / "briefings" / "trip-ac15.json"
    plaene, _ = mig.planen(root)
    fremd = json.dumps({**_lies(root, "alice", "trip-ac15"), "name": "parallel gespeichert"})
    pfad.write_text(fremd, encoding="utf-8")
    offen = mig.schreiben(plaene)
    assert pfad.read_text(encoding="utf-8") == fremd
    assert offen == [f"{pfad}: seit der Planung geändert, nicht geschrieben"]
    assert _alarm_ab(root, "bob", "trip-ski")["gust"] == "red"


def test_gesperrte_datei_bleibt_offen_exit_1(root, monkeypatch, capsys):
    from services import file_lock

    mig = _modul()
    monkeypatch.setattr(file_lock, "BRIEFING_LOCK_TIMEOUT_SECONDS", 0.1)  # nur die Wartefrist
    pfad = root / "alice" / "briefings" / "trip-ac15.json"
    vorher = pfad.read_bytes()
    with file_lock.exclusive_lock(pfad):
        code = mig.main(["--root", str(root), "--backup-dir", str(root.parent / "s"), "--execute"])
    assert code == 1 and pfad.read_bytes() == vorher
    assert str(pfad) in capsys.readouterr().err


def test_merker_und_alarm_ab_ueberleben_python_laden_und_speichern(root):
    _lauf(root, "--execute")
    pfad = root / "alice" / "briefings" / "trip-gleich.json"
    trip = load_trip("trip-gleich", data_dir=root.parent, user_id="alice")
    assert resolve_ampel(trip)["metrics"]["gust"]["alarm_ab"] == "yellow"
    save_trip(trip, "alice", root.parent)
    dc = json.loads(pfad.read_text(encoding="utf-8"))["display_config"]
    assert dc["alarm_ab_migration"] == "2793"
    assert dc["metric_alert_levels"] == {"fresh_snow": "standard", "wind_gust": "sensibel"}
    assert dc["ampel"]["metrics"]["gust"]["alarm_ab"] == "yellow"


def test_ratsche_jede_alarm_metrik_ist_abgebildet_oder_begruendet():
    mig = _modul()
    abgebildet, nicht = set(mig._ABBILDUNG), set(mig._NICHT_ABGEBILDET)
    assert not abgebildet & nicht
    assert sorted({m.value for m in AlertMetric} - abgebildet - nicht) == []

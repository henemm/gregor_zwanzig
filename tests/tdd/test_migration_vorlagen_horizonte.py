"""Migration der Zeithorizonte eigener Vorlagen auf „alle Tage" (Issue #2794 S3a, AC-26).

Spec: docs/specs/modules/feat_2794_s3a_reiter_wetter.md §6 „Migration"
(``scripts/migrate_2794_preset_horizons.py``), CLI wie migrate_2792/2793:
``--root`` Pflicht (Verzeichnis der Nutzerordner), ``--backup-dir``, ohne
``--execute`` Probelauf, tar.gz je Nutzer vor dem Schreiben, idempotent
(zweiter Lauf „Nichts zu tun"), Bericht je Nutzer/Datei.

Annahme „alle Tage" (konsistent mit dem Go-Modell und AC-22): der Metrik-
Eintrag verliert den Schluessel ``horizons`` ganz. Fehlend heisst beim Lesen
„alle Tage" — Go ``store.migrateMetricPreset`` setzt dann {today, tomorrow,
day_after} = true, der Python-Renderer (``output/renderers/email/helpers.py``)
nimmt True, wenn das Feld fehlt. Alle anderen Felder bleiben byte-gleich im Wert.

Kein Mock: echter Datenbaum ``<root>/<uid>/metric_presets.json`` in
``tmp_path``, Skript als Subprozess, Pruefling relativ zur Testdatei.
"""

import copy
import hashlib
import json
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "migrate_2794_preset_horizons.py"


def _m(mid, horizons=None, friendly=False, enabled=True):
    e = {"metric_id": mid, "enabled": enabled, "use_friendly_format": friendly}
    if horizons is not None:
        e["horizons"] = horizons
    return e


TEIL = {"today": True, "tomorrow": False, "day_after": False}
ALLE = {"today": True, "tomorrow": True, "day_after": True}

BESTAND = {
    "alice": [
        {"id": "p-a1", "name": "Bergtag", "description": "Grat", "is_default": True,
         "metrics": [_m("gust", TEIL), _m("wind", ALLE, friendly=True), _m("thunder")],
         "created_at": "2026-03-01T08:00:00Z",
         "ampel": {"template": "wandern", "metrics": {"gust": {"upper": {"yellow": 42, "orange": 55, "red": 70},
                                                               "alarm_ab": "orange"}}}},
        {"id": "p-a2", "name": "Talweg", "is_default": False, "kind": "vergleich",
         "metrics": [_m("temperature", {"today": False, "tomorrow": False, "day_after": False}, enabled=False)],
         "created_at": "2026-03-02T08:00:00Z", "zukunft": {"bleibt": [1, 2]}},
    ],
    "bob": [
        {"id": "p-b1", "name": "Bergtag", "is_default": False,
         "metrics": [_m("precipitation", {"today": False, "tomorrow": True, "day_after": True})],
         "created_at": "2026-04-01T08:00:00Z"},
    ],
    # bereits ohne Zeithorizonte: nichts zu tun, keine Sicherung
    "carla": [
        {"id": "p-c1", "name": "Schon gut", "is_default": False, "metrics": [_m("wind")],
         "created_at": "2026-05-01T08:00:00Z"},
    ],
}


@pytest.fixture
def root(tmp_path):
    r = tmp_path / "users"
    for uid, presets in BESTAND.items():
        (r / uid).mkdir(parents=True)
        (r / uid / "metric_presets.json").write_text(
            json.dumps(presets, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    # Nutzer ohne Vorlagen-Datei und Nicht-Nutzer-Ordner
    (r / "dora").mkdir()
    for name in (".backups", "_papierkorb"):
        (r / name).mkdir()
        (r / name / "metric_presets.json").write_text(json.dumps(BESTAND["bob"]), encoding="utf-8")
    return r


def _lauf(root, *args, code=0):
    res = subprocess.run([sys.executable, str(SCRIPT), "--root", str(root),
                          "--backup-dir", str(root.parent / "sicherung"), *args],
                         capture_output=True, text=True, timeout=60)
    assert res.returncode == code, res.stdout + res.stderr
    return res.stdout


def _lies(root, uid):
    return json.loads((root / uid / "metric_presets.json").read_text(encoding="utf-8"))


def _summen(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*")) if p.is_file()}


def _abschnitt(out, uid):
    return out.split(f"== Nutzer {uid} ==")[1].split("== Nutzer ")[0]


def _ohne_horizonte(presets):
    out = copy.deepcopy(presets)
    for p in out:
        for e in p["metrics"]:
            e.pop("horizons", None)
    return out


def test_ac26_probelauf_schreibt_nichts_und_berichtet_je_nutzer(root):
    vorher = _summen(root)
    out = _lauf(root)
    assert _summen(root) == vorher
    assert not (root.parent / "sicherung").exists()
    assert "Probelauf" in out
    assert "== Nutzer alice ==" in out and "== Nutzer bob ==" in out
    assert "metric_presets.json" in _abschnitt(out, "alice")


def test_ac26_execute_setzt_horizonte_auf_alle_tage_uebrige_felder_unveraendert(root):
    _lauf(root, "--execute")
    for uid in ("alice", "bob", "carla"):
        nachher = _lies(root, uid)
        assert all("horizons" not in e for p in nachher for e in p["metrics"]), uid
        assert nachher == _ohne_horizonte(BESTAND[uid]), uid


def test_ac26_sicherung_je_nutzer_vor_dem_schreiben_nur_eigene_dateien(root):
    original = {uid: (root / uid / "metric_presets.json").read_bytes() for uid in BESTAND}
    out = _lauf(root, "--execute")
    archive = sorted((root.parent / "sicherung").glob("migrate-2794-*.tar.gz"))
    assert [a.name.split("-")[2] for a in archive] == ["alice", "bob"], out
    for archiv, uid in zip(archive, ("alice", "bob")):
        with tarfile.open(archiv) as tar:
            namen = tar.getnames()
            assert namen and all(n.split("/")[0] == uid for n in namen), namen
            json_namen = [n for n in namen if n.endswith("metric_presets.json")]
            assert json_namen == [f"{uid}/metric_presets.json"]
            assert tar.extractfile(json_namen[0]).read() == original[uid]


def test_ac26_zweiter_lauf_nichts_zu_tun(root):
    _lauf(root, "--execute")
    nach_erstem = _summen(root)
    out = _lauf(root, "--execute")
    assert _summen(root) == nach_erstem
    assert "Nichts zu tun" in out and "Sicherung geschrieben" not in out


def test_ac26_nicht_nutzer_ordner_und_fremde_nutzer_bleiben_unberuehrt(root):
    vorher = _summen(root)
    out = _lauf(root, "--execute")
    for name in (".backups", "_papierkorb"):
        rel = f"{name}/metric_presets.json"
        assert _summen(root)[rel] == vorher[rel]
        assert f"== Nutzer {name} ==" not in out
    assert _summen(root)["carla/metric_presets.json"] == vorher["carla/metric_presets.json"]
    assert not (root / "default").exists()
    assert "Bergtag" not in (root / "carla" / "metric_presets.json").read_text(encoding="utf-8")


def test_ac26_root_ist_pflicht():
    res = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, text=True, timeout=60)
    assert res.returncode == 2 and "--root" in res.stderr, res.stdout + res.stderr

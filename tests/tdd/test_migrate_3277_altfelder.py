"""Datenlauf Altfelder entfernen (#3351, Was steht wo B6b-5).

Spec: docs/specs/modules/feat_3351_altfelder_datenlauf.md, AC-1 bis AC-11.

Kern-Schicht ohne Mock: echter Datenbaum ``<root>/<uid>/briefings/*.json``
und ``<root>/<uid>/compare_presets.json`` in ``tmp_path``, Skript
``scripts/migrate_3277_altfelder.py`` als Subprozess (bzw. fuer den
Schreibkonflikt AC-10 als echtes Modul mit echtem Dateizugriff zwischen
Planung und Schreiben). Die Altnamen kommen aus ``app.loader.ALTFELDER``,
keine Namens-Literale. Nutzerkennungen sind echt und verschieden, nie
``"default"``.
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import re
import stat
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest

from app.loader import ALTFELDER

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "migrate_3277_altfelder.py"
EBENEN = ("display_config", "report_config")

#: Alle zehn Altfelder mit unterscheidbaren Werten.
ALT = {name: {"alt": i} for i, name in enumerate(ALTFELDER)}

TABELLE = {"version": 1, "rows": [
    {"metric_id": "wind", "places": {"email": True, "telegram": True, "sms": True, "outlook": True},
     "formats": {"email": "simplified"}},
    {"metric_id": "temperature", "places": {"email": True, "telegram": False, "sms": True,
                                            "outlook": True}},
], "outlook_reports": ["evening"]}


def _trip(tid: str, uid: str, *, rc_nur_alt: bool = False) -> dict:
    rc = copy.deepcopy(ALT) if rc_nur_alt else {"morning_time": "06:00", **copy.deepcopy(ALT)}
    return {
        "id": tid, "name": f"Trip {tid}", "kind": "route", "user_id": uid,
        "stages": [{"id": "T1", "name": "Etappe 1", "waypoints": [{"lat": 47.1, "lon": 11.2}]}],
        "empfaenger": [f"{uid}@example.invalid"], "schedule": "daily",
        "alert_rules": [{"id": "r1", "metric": "wind_gust", "threshold": 5, "enabled": True}],
        "report_config": rc,
        "display_config": {"placements": copy.deepcopy(TABELLE),
                           "metrics": [{"metric_id": "wind", "enabled": True}],
                           # gleicher Name tiefer verschachtelt: KEINE der drei Ebenen, bleibt
                           "tief": {ALTFELDER[0]: "bleibt"},
                           **copy.deepcopy(ALT)},
        "zukunft_top": {"bleibt": [1, 2]},
        **copy.deepcopy(ALT),
    }


def _vergleich(cid: str, uid: str) -> dict:
    return {
        "id": cid, "name": f"Vergleich {cid}", "kind": "vergleich", "user_id": uid,
        "location_ids": ["ort-a", "ort-b"], "profil": "ALLGEMEIN",
        "empfaenger": [f"{uid}@example.invalid"], "morning_enabled": True,
        "display_config": {"placements": copy.deepcopy(TABELLE),
                           "active_metrics": [{"metric_id": "temperature"}], **copy.deepcopy(ALT)},
        **copy.deepcopy(ALT),
    }


def _sauber() -> dict:
    """Abo ohne Altfelder und ohne Tabelle: nie blockiert, nie angefasst."""
    return {"id": "trip-sauber", "name": "Sauber", "kind": "route", "stages": [],
            "display_config": {"metrics": [{"metric_id": "wind", "enabled": True}]}}


def _presets() -> list:
    eintrag = {"id": "cp-alt", "name": "Alter Vergleich", "location_ids": ["ort-a"],
               "display_config": {"active_metrics": ["wind"], **copy.deepcopy(ALT)},
               **copy.deepcopy(ALT)}  # ohne placements: fuer diese Datei keine Tabellenpruefung
    return [eintrag, {"id": "cp-sauber", "name": "Sauber", "location_ids": ["ort-b"]}]


def _schreibe(pfad: Path, obj) -> None:
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _baum(root: Path) -> None:
    _schreibe(root / "alice" / "briefings" / "trip-a.json", _trip("trip-a", "alice"))
    _schreibe(root / "alice" / "briefings" / "cmp-a.json", _vergleich("cmp-a", "alice"))
    _schreibe(root / "alice" / "compare_presets.json", _presets())
    _schreibe(root / "bob" / "briefings" / "trip-b.json", _trip("trip-b", "bob", rc_nur_alt=True))
    _schreibe(root / "bob" / "briefings" / "cmp-b.json", _vergleich("cmp-b", "bob"))
    _schreibe(root / "bob" / "briefings" / "trip-sauber.json", _sauber())
    (root / "bob" / "briefings" / "trip-b.json.lock").write_text("", encoding="utf-8")


def _blockiert(root: Path, fall: str) -> Path:
    obj = _trip("trip-blockiert", "carla")
    if fall == "ohne_rows":
        del obj["display_config"]["placements"]["rows"]
    elif fall == "ohne_outlook_reports":
        del obj["display_config"]["placements"]["outlook_reports"]
    else:
        del obj["display_config"]["placements"]
    pfad = root / "carla" / "briefings" / "trip-blockiert.json"
    _schreibe(pfad, obj)
    return pfad


@pytest.fixture
def root(tmp_path):
    r = tmp_path / "users"
    _baum(r)
    return r


def _lauf(root: Path, *args: str, code: int = 0) -> str:
    res = subprocess.run([sys.executable, str(SCRIPT), "--root", str(root), *args],
                         capture_output=True, text=True, timeout=60)
    assert res.returncode == code, f"Exit {res.returncode}\n{res.stdout}\n{res.stderr}"
    return res.stdout + res.stderr


def _summen(root: Path) -> dict:
    """Inhalt und Aenderungszeit jeder Datei des Baums (ohne Sicherungsordner)."""
    return {str(p.relative_to(root)): (hashlib.sha256(p.read_bytes()).hexdigest(), p.stat().st_mtime_ns)
            for p in sorted(root.rglob("*")) if p.is_file() and ".backups" not in p.parts}


def _sicherungen(root: Path) -> list[Path]:
    return sorted(root.parent.rglob("*.tar.gz"))


def _lies(pfad: Path):
    return json.loads(pfad.read_text(encoding="utf-8"))


def _briefings(root: Path) -> list[Path]:
    return sorted(root.glob("*/briefings/*.json"))


def _altfunde(obj: dict) -> list[str]:
    funde = [n for n in ALTFELDER if n in obj]
    for ebene in EBENEN:
        teil = obj.get(ebene)
        if isinstance(teil, dict):
            funde += [f"{ebene}.{n}" for n in ALTFELDER if n in teil]
    return funde


def _ohne_alt(obj: dict) -> dict:
    """Erwartung, unabhaengig vom Skript gebaut: drei Ebenen ohne Altfelder."""
    neu = {k: copy.deepcopy(v) for k, v in obj.items() if k not in ALTFELDER}
    for ebene in EBENEN:
        if isinstance(neu.get(ebene), dict):
            neu[ebene] = {k: v for k, v in neu[ebene].items() if k not in ALTFELDER}
    return neu


# --- AC-1: Probelauf ---------------------------------------------------------

def test_ac1_probelauf_berichtet_aggregiert_und_schreibt_nichts(root):
    vorher = _summen(root)
    out = _lauf(root)
    assert _summen(root) == vorher, "Probelauf hat geschrieben"
    assert not _sicherungen(root), "Probelauf hat eine Sicherung angelegt"
    for name in ALTFELDER:
        assert name in out, f"Bericht nennt Feld {name} nicht"
    assert "display_config" in out and "report_config" in out
    assert "top" in out.lower() or "oberste" in out.lower(), "oberste Ebene fehlt im Bericht"
    assert "trip" in out.lower() and "vergleich" in out.lower(), "Abo-Art fehlt im Bericht"
    assert re.search(r"\b2 Nutzer", out), "Nutzeranzahl fehlt im Bericht"


# --- AC-2: Entfernen auf drei Ebenen -----------------------------------------

def test_ac2_ausfuehren_entfernt_alle_altfelder_auf_drei_ebenen(root):
    trip_b = root / "bob" / "briefings" / "trip-b.json"
    trip_b.chmod(0o640)
    _lauf(root, "--ausfuehren")
    dateien = _briefings(root)
    assert {p.parent.parent.name for p in dateien} == {"alice", "bob"}
    for pfad in dateien:
        assert _altfunde(_lies(pfad)) == [], pfad
    assert stat.S_IMODE(trip_b.stat().st_mode) == 0o640, "Dateirechte nicht erhalten"
    assert not list(root.rglob("*.tmp"))


# --- AC-3: Merge, alles andere bleibt ----------------------------------------

def test_ac3_alle_anderen_felder_bleiben_und_leerer_container_bleibt(root):
    vorher = {p: _lies(p) for p in _briefings(root)}
    sauber = root / "bob" / "briefings" / "trip-sauber.json"
    sauber_bytes = sauber.read_bytes()
    _lauf(root, "--ausfuehren")
    for pfad, alt in vorher.items():
        assert _lies(pfad) == _ohne_alt(alt), pfad
    trip_b = _lies(root / "bob" / "briefings" / "trip-b.json")
    assert trip_b["report_config"] == {}, "Nur-Altfeld-Container muss als leeres Objekt stehen bleiben"
    assert _lies(root / "alice" / "briefings" / "trip-a.json")["display_config"]["tief"] == \
        {ALTFELDER[0]: "bleibt"}, "tiefer verschachtelter Schluessel ist keine der drei Ebenen"
    assert sauber.read_bytes() == sauber_bytes, "Abo ohne Altfelder wurde angefasst"


# --- AC-4: Sicherung je Nutzer -----------------------------------------------

def test_ac4_sicherung_je_nutzer_getrennt_mit_originalinhalt(root):
    original = {uid: (root / uid / "briefings" / f"trip-{uid[0]}.json").read_bytes()
                for uid in ("alice", "bob")}
    _lauf(root, "--ausfuehren")
    archive = _sicherungen(root)
    gefunden = {}
    for archiv in archive:
        with tarfile.open(archiv) as tar:
            namen = [n for n in tar.getnames() if tar.getmember(n).isfile()]
            uids = {n.split("/")[0] for n in namen}
            assert len(uids) == 1, f"Sicherung mischt Nutzer: {archiv.name} {namen}"
            uid = uids.pop()
            gefunden[uid] = tar.extractfile(f"{uid}/briefings/trip-{uid[0]}.json").read()
    assert gefunden == original, "je Nutzer eine Sicherung mit dessen Originaldateien"
    assert _altfunde(json.loads(gefunden["alice"])), "Sicherung muss den Stand vor dem Schreiben tragen"
    assert not (root / "default").exists()


def test_ac4_sicherungsfehler_schreibt_keine_datei(root):
    for ort in (root.parent / ".backups", root / ".backups"):
        ort.write_text("kein Ordner", encoding="utf-8")  # mkdir/tar scheitern
    vorher = _summen(root)
    _lauf(root, "--ausfuehren", code=1)
    assert _summen(root) == vorher, "trotz Sicherungsfehler geschrieben"
    assert not _sicherungen(root)


# --- AC-5 / AC-6: fail-closed ------------------------------------------------

@pytest.mark.parametrize("fall", ["ohne_rows", "ohne_outlook_reports", "ohne_placements"])
def test_ac5_blockiertes_abo_bricht_vor_jedem_schreiben_mit_exit_2_ab(root, fall):
    _blockiert(root, fall)
    vorher = _summen(root)
    out = _lauf(root, "--ausfuehren", code=2)
    assert "BLOCKIERT" in out and "trip-blockiert" in out, out
    assert _summen(root) == vorher, "fail-closed verletzt: Datei geschrieben"
    assert not _sicherungen(root), "fail-closed verletzt: Sicherung angelegt"


def test_ac6_blockierte_auslassen_laesst_blockiertes_byte_gleich(root):
    blockiert = _blockiert(root, "ohne_rows")
    bytes_vorher = blockiert.read_bytes()
    out = _lauf(root, "--ausfuehren", "--blockierte-auslassen")
    assert blockiert.read_bytes() == bytes_vorher
    assert "BLOCKIERT" in out and "trip-blockiert" in out, out
    for pfad in _briefings(root):
        if pfad != blockiert:
            assert _altfunde(_lies(pfad)) == [], pfad


# --- AC-7: Idempotenz --------------------------------------------------------

def test_ac7_zweiter_lauf_aendert_nichts(root):
    _lauf(root, "--ausfuehren")
    nach_erstem, archive = _summen(root), _sicherungen(root)
    out = _lauf(root, "--ausfuehren")
    assert _summen(root) == nach_erstem, "zweiter Lauf hat geschrieben"
    assert _sicherungen(root) == archive, "zweiter Lauf hat gesichert"
    assert "Nichts zu tun" in out


# --- AC-8: Nachzaehlen -------------------------------------------------------

def test_ac8_nachzaehlen_exit_1_bei_rest_0_nach_bereinigung_rein_lesend(root):
    vorher = _summen(root)
    _lauf(root, "--nachzaehlen", code=1)
    assert _summen(root) == vorher and not _sicherungen(root), "Nachzaehlen hat geschrieben"
    _lauf(root, "--ausfuehren")
    nachher = _summen(root)
    _lauf(root, "--nachzaehlen", code=0)
    assert _summen(root) == nachher


def test_ac8_nachzaehlen_weist_ausgelassenes_blockiertes_abo_aus(root):
    _blockiert(root, "ohne_placements")
    _lauf(root, "--ausfuehren", "--blockierte-auslassen")
    vorher = _summen(root)
    out = _lauf(root, "--nachzaehlen", code=1)
    assert "BLOCKIERT" in out and "trip-blockiert" in out, out
    assert _summen(root) == vorher


# --- AC-9: compare_presets.json ----------------------------------------------

def test_ac9_compare_presets_ohne_tabellenpruefung_bereinigt(root):
    pfad = root / "alice" / "compare_presets.json"
    vorher = _lies(pfad)
    _lauf(root, "--ausfuehren")
    nachher = _lies(pfad)
    assert len(nachher) == len(vorher) == 2
    assert nachher[0] == _ohne_alt(vorher[0])
    assert nachher[1] == vorher[1]


def test_ac4_ac9_sicherung_enthaelt_presets_und_briefings_byte_genau(root):
    original = {f"alice/{p.relative_to(root / 'alice')}": p.read_bytes()
                for p in [*sorted((root / "alice" / "briefings").glob("*.json")),
                          root / "alice" / "compare_presets.json"]}
    _lauf(root, "--ausfuehren")
    assert (root / "alice" / "compare_presets.json").read_bytes() != original["alice/compare_presets.json"], \
        "Presets-Datei muss bereinigt worden sein (sonst prueft der Test die Sicherung nicht)"
    archive = [a for a in _sicherungen(root) if "-alice-" in a.name]
    assert len(archive) == 1, f"genau eine Sicherung fuer alice erwartet: {archive}"
    with tarfile.open(archive[0]) as tar:
        im_archiv = {n: tar.extractfile(n).read() for n in tar.getnames() if tar.getmember(n).isfile()}
    assert "alice/compare_presets.json" in im_archiv, f"Presets fehlen in der Sicherung: {sorted(im_archiv)}"
    assert im_archiv["alice/compare_presets.json"] == original["alice/compare_presets.json"]
    for name, inhalt in original.items():
        assert im_archiv.get(name) == inhalt, f"{name} nicht byte-gleich in der Sicherung"


# --- AC-10: Schreibkonflikt --------------------------------------------------

def _modul():
    spec = importlib.util.spec_from_file_location("migrate_3277", SCRIPT)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def test_ac10_seit_planung_geaenderte_datei_bleibt_und_wiederholung_bereinigt(root, monkeypatch):
    mig = _modul()
    ziel = root / "alice" / "briefings" / "trip-a.json"
    fremd = json.dumps({**_lies(ziel), "name": "parallel gespeichert"}, indent=2)
    echt = mig.schreiben

    def schreiber_dazwischen(plaene):  # echte zweite Schreibaktion zwischen Planung und Schreiben
        ziel.write_text(fremd, encoding="utf-8")
        return echt(plaene)

    monkeypatch.setattr(mig, "schreiben", schreiber_dazwischen)
    assert mig.main(["--root", str(root), "--ausfuehren"]) == 1
    assert ziel.read_text(encoding="utf-8") == fremd, "fremde Aenderung ueberschrieben"
    assert _altfunde(_lies(root / "bob" / "briefings" / "trip-b.json")) == []
    _lauf(root, "--ausfuehren")
    neu = _lies(ziel)
    assert _altfunde(neu) == [] and neu["name"] == "parallel gespeichert"


# --- AC-11: importierte Liste vollstaendig abgedeckt -------------------------

def test_ac11_jedes_der_zehn_felder_wird_je_ebene_entfernt(root):
    assert len(ALTFELDER) == 10
    pfad = root / "alice" / "briefings" / "trip-a.json"
    erwartet = [n for n in ALTFELDER] + [f"{e}.{n}" for e in EBENEN for n in ALTFELDER]
    assert sorted(_altfunde(_lies(pfad))) == sorted(erwartet), "Testdaten tragen nicht alle Felder"
    _lauf(root, "--ausfuehren")
    assert _altfunde(_lies(pfad)) == []

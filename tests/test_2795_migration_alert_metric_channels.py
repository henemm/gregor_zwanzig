"""TDD RED — #2795 S3b Teil 1a: Migration ``alert_metric_channels`` entfernen.

Spec: docs/specs/modules/feat_2795_s3b_teil1_zustellung.md §4.3, AC-28
(Mandantentrennung: Migration je Nutzerverzeichnis ``data/users/<uid>/``).

────────────────────────────────────────────────────────────────────────────
Erwartete Schnittstelle (GREEN richtet sich danach, Muster
``scripts/migrate_2793_alarm_ab.py`` / ``migrate_2792_profil_ampel.py``)
────────────────────────────────────────────────────────────────────────────
Skript ``scripts/migrate_2795_alert_metric_channels.py``::

    python3 scripts/migrate_2795_alert_metric_channels.py \
        --root <data/users> [--backup-dir <pfad>] [--execute]

* ``--root`` zeigt auf ``data/users``; Nutzer = echte Unterordner (ohne
  ``.``/``_``-Praefix), je Nutzer ``<root>/<uid>/briefings/*.json`` (Trip
  ``kind=route`` UND Ortsvergleich ``kind=vergleich``, beide liegen dort).
* Ohne ``--execute``: Probelauf, schreibt NICHTS (auch keine Sicherung),
  druckt aber das Protokoll.
* Mit ``--execute``: ZUERST Sicherung je betroffenem Nutzer als Datei in
  ``--backup-dir`` (z. B. ``migrate-2795-<uid>-<stempel>.tar.gz`` mit
  ``<uid>/briefings``), DANN je Datei Read-Modify-Write: nur der
  oberste Schluessel ``alert_metric_channels`` wird entfernt, alle anderen
  Felder wertgleich zurueckgeschrieben (atomar, gerne ueber
  ``migrate_2792_profil_ampel.schreiben``).
* Protokoll auf stdout: je Nutzer ein Abschnitt ``== Nutzer <uid> ==``; je
  betroffenem Abo eine Zeile mit Datei/Abo-Kennung und darunter die alte
  Sonderregel je Metrik mit den eingeschalteten Kanaelen (z. B.
  ``gust: email`` oder ``gust -> email``; geprueft wird nur, dass Metrik-ID und
  Kanalnamen im Abschnitt des Nutzers stehen).
* Idempotent: zweiter Lauf schreibt nichts, Exit 0.
* Exit 0 = fertig.

Kein Mock: echter Datenbaum in ``tmp_path``, Skript als Subprozess
(``sys.executable``), Nachpruefung an den Dateien.

RED heute: das Skript existiert nicht (Subprozess Exit 2 „can't open file“).
"""
from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "migrate_2795_alert_metric_channels.py"


def _trip(tid: str, amc=None) -> dict:
    obj = {
        "id": tid, "name": tid, "kind": "route", "stages": [],
        "display_config": {"ampel": {"template": "allgemein",
                                     "metrics": {"gust": {"alarm_ab": "orange"}}},
                           "telegram_style": "compact"},
        "report_config": {"enabled": True, "morning_time": "06:45:00", "evening_time": "18:00:00",
                          "send_email": True, "send_telegram": True},
        "alert_channels": {"email": True, "telegram": True, "sms": False, "premium_sms": False},
        "alert_channel_thresholds": {"email": "LOW", "telegram": "HIGH"},
        "alert_cooldown_minutes": 45, "zukunft_top": {"bleibt": [1, 2]},
    }
    if amc is not None:
        obj["alert_metric_channels"] = amc
    return obj


def _cmp(cid: str, amc=None) -> dict:
    obj = {
        "id": cid, "name": cid, "kind": "vergleich", "location_ids": ["a", "b"],
        "profil": "ALLGEMEIN", "morning_time": "07:00:00", "send_telegram": True,
        "display_config": {"ampel": {"template": "allgemein"}},
        "alert_channels": {"email": True, "telegram": False, "sms": True, "premium_sms": False},
    }
    if amc is not None:
        obj["alert_metric_channels"] = amc
    return obj


BAUM = {
    "alice": {
        "trip-alice": _trip("trip-alice", {"gust": {"email": True, "telegram": False},
                                           "precipitation": {"telegram": True}}),
        "cmp-alice": _cmp("cmp-alice", {"thunder": {"sms": True, "email": False}}),
        "trip-alice-ohne": _trip("trip-alice-ohne"),
    },
    "bob": {
        "trip-bob": _trip("trip-bob", {"wind": {"premium_sms": True}}),
        "cmp-bob-ohne": _cmp("cmp-bob-ohne"),
    },
}


@pytest.fixture
def root(tmp_path):
    r = tmp_path / "users"
    for uid, objs in BAUM.items():
        (r / uid / "briefings").mkdir(parents=True)
        for name, obj in objs.items():
            (r / uid / "briefings" / f"{name}.json").write_text(
                json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return r


def _lauf(root: Path, *args, code: int = 0) -> str:
    res = subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(root),
         "--backup-dir", str(root.parent / "sicherung"), *args],
        capture_output=True, text=True, timeout=60,
    )
    assert res.returncode == code, (
        f"Migration Exit {res.returncode} (erwartet {code}):\n{res.stdout}\n{res.stderr}"
    )
    return res.stdout


def _lies(root: Path, uid: str, name: str) -> dict:
    return json.loads((root / uid / "briefings" / f"{name}.json").read_text(encoding="utf-8"))


def _summen(root: Path) -> dict:
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*")) if p.is_file()}


def _abschnitt(out: str, uid: str) -> str:
    assert f"== Nutzer {uid} ==" in out, f"Protokoll ohne Abschnitt fuer {uid}:\n{out}"
    return out.split(f"== Nutzer {uid} ==")[1].split("== Nutzer ")[0]


def test_ac28_probelauf_schreibt_nichts_und_protokolliert(root):
    """AC-28 Probelauf: ohne ``--execute`` bleibt der Datenbaum byte-gleich,
    es entsteht keine Sicherung, das Protokoll wird trotzdem ausgegeben.
    RED: Skript fehlt."""
    vorher = _summen(root)
    out = _lauf(root)
    assert _summen(root) == vorher, "Probelauf darf nichts schreiben"
    assert not (root.parent / "sicherung").exists(), "Probelauf darf keine Sicherung anlegen"
    assert "trip-alice" in _abschnitt(out, "alice")


def test_ac28_nur_der_schluessel_entfernt_alle_anderen_felder_wertgleich(root):
    """AC-28: Trip und Ortsvergleich mit ``alert_metric_channels`` plus
    ``ampel``, ``report_config``, ``alert_channels`` u. a. — nach der Migration
    fehlt NUR der Schluessel, jedes andere Feld ist wertgleich. Abos ohne den
    Schluessel bleiben byte-gleich. RED: Skript fehlt."""
    vorher = {(u, n): _lies(root, u, n) for u, objs in BAUM.items() for n in objs}
    ohne_vorher = {
        (u, n): (root / u / "briefings" / f"{n}.json").read_bytes()
        for u, n in (("alice", "trip-alice-ohne"), ("bob", "cmp-bob-ohne"))
    }
    _lauf(root, "--execute")
    for (uid, name), alt in vorher.items():
        neu = _lies(root, uid, name)
        assert "alert_metric_channels" not in neu, f"{uid}/{name}: Schluessel noch vorhanden"
        erwartet = copy.deepcopy(alt)
        erwartet.pop("alert_metric_channels", None)
        assert neu == erwartet, (
            f"AC-28: {uid}/{name} — ausser alert_metric_channels darf sich nichts aendern.\n"
            f"vorher (ohne Schluessel): {erwartet}\nnachher: {neu}"
        )
    for (uid, name), roh in ohne_vorher.items():
        assert (root / uid / "briefings" / f"{name}.json").read_bytes() == roh, (
            f"AC-28: {uid}/{name} ohne Altschluessel darf nicht angefasst werden"
        )


def test_ac28_sicherung_besteht_vor_dem_schreiben(root):
    """AC-28: nach ``--execute`` liegt je betroffenem Nutzer eine Sicherung im
    Sicherungsordner, und sie enthaelt den ALTEN Stand (mit Schluessel).
    RED: Skript fehlt."""
    _lauf(root, "--execute")
    sicherung = root.parent / "sicherung"
    archive = sorted(sicherung.glob("*.tar.gz")) if sicherung.exists() else []
    assert archive, "AC-28: keine Sicherung angelegt"
    inhalt: dict[str, dict] = {}
    for a in archive:
        with tarfile.open(a) as tar:
            for m in tar.getmembers():
                if m.isfile() and m.name.endswith(".json"):
                    inhalt[m.name] = json.loads(tar.extractfile(m).read())
    gesichert = {Path(n).stem: obj for n, obj in inhalt.items()}
    for uid, name in (("alice", "trip-alice"), ("alice", "cmp-alice"), ("bob", "trip-bob")):
        assert name in gesichert, f"AC-28: {uid}/{name} fehlt in der Sicherung ({sorted(gesichert)})"
        assert gesichert[name].get("alert_metric_channels") == BAUM[uid][name]["alert_metric_channels"], (
            f"AC-28: Sicherung von {name} muss den alten Stand mit Schluessel enthalten"
        )


def test_ac28_protokoll_nennt_jedes_betroffene_abo_mit_alter_regel_je_nutzer(root):
    """AC-28: das Protokoll nennt je Nutzer jedes betroffene Abo samt alter
    Sonderregel (Metrik und eingeschaltete Kanaele); Abos ohne Schluessel
    werden nicht als Sonderregel gefuehrt; Nutzer werden getrennt berichtet.
    RED: Skript fehlt."""
    out = _lauf(root, "--execute")
    alice, bob = _abschnitt(out, "alice"), _abschnitt(out, "bob")
    for token in ("trip-alice", "gust", "email", "precipitation", "telegram", "cmp-alice", "thunder", "sms"):
        assert token in alice, f"AC-28: Protokoll Abschnitt alice ohne {token!r}:\n{alice}"
    for token in ("trip-bob", "wind", "premium_sms"):
        assert token in bob, f"AC-28: Protokoll Abschnitt bob ohne {token!r}:\n{bob}"
    # Mandantentrennung im Protokoll: keine fremden Abos im falschen Abschnitt.
    assert "trip-bob" not in alice and "trip-alice" not in bob and "cmp-alice" not in bob


def test_ac28_zweiter_lauf_aendert_nichts(root):
    """AC-28: idempotent — der zweite ``--execute``-Lauf laesst jede Datei
    byte-gleich und endet mit Exit 0. RED: Skript fehlt."""
    _lauf(root, "--execute")
    nach_erstem = _summen(root)
    _lauf(root, "--execute")
    assert _summen(root) == nach_erstem, "AC-28: zweiter Lauf hat Dateien veraendert"


def test_ac28_mehrere_nutzer_getrennt(root):
    """AC-28/Mandantentrennung: die Migration arbeitet je Nutzerverzeichnis;
    sie legt keinen Ordner ``default`` an und schreibt keine Datei eines
    Nutzers in den Baum eines anderen. RED: Skript fehlt."""
    _lauf(root, "--execute")
    assert sorted(p.name for p in root.iterdir() if p.is_dir()) == ["alice", "bob"], (
        "AC-28: Migration darf keine weiteren Nutzerordner (z. B. 'default') anlegen"
    )
    for uid, objs in BAUM.items():
        dateien = sorted(p.stem for p in (root / uid / "briefings").glob("*.json"))
        assert dateien == sorted(objs), f"AC-28: Dateien von {uid} veraendert: {dateien}"

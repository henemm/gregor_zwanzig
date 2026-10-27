"""Geteilte Helfer der Schreibsperren-Tests (#2158) -- Fremdprozess-Sperre,
Trip-Fixture aus dem versionierten GR221-Bestand, Compare-Preset-Fixture.

VERTRAG (ADR-0083): Die gemeinsame Sperrdatei ist LITERAL
``<data>/users/<uid>/briefings/<id>.json.lock``. Der Sperrhalter hier ist ein
echter Fremdprozess (nur stdlib ``fcntl``), kein Produktivcode -- so beweist
ein Test den Pfadvertrag ueber die Prozessgrenze, nicht nur "meine eigene
Funktion sperrt sich selbst".

FRIST-VERTRAG (Tests verkuerzen die Frist, siehe ``frist_verkuerzen``):
Produktivcode liest die Frist ZUR AUFRUFZEIT aus dem Modulattribut
``services.file_lock.BRIEFING_LOCK_TIMEOUT_SECONDS`` (Spec: 5.0 s) bzw. dem
bestehenden ``services.file_lock.LOCK_TIMEOUT_SECONDS`` -- NICHT als beim
Import gebundener Default-Parameter.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_USER = _REPO_ROOT / "tests" / "fixtures" / "data_root" / "users" / "default"
GR221_JSON = FIXTURE_USER / "trips" / "gr221-mallorca.json"
GR221_GPX_TAG1 = FIXTURE_USER / "gpx" / "2026-01-17_2753214331_Tag 1_ von Valldemossa nach Deià.gpx"

# Fremdprozess: sperrt, meldet "held", wartet auf eine Zeile von stdin,
# gibt frei, meldet "released". Kein Sleep -- reiner Pipe-Handshake.
_HALTER = (
    "import fcntl, os, sys\n"
    "p = sys.argv[1]\n"
    "os.makedirs(os.path.dirname(p), exist_ok=True)\n"
    "fd = os.open(p, os.O_RDWR | os.O_CREAT, 0o644)\n"
    "fcntl.flock(fd, fcntl.LOCK_EX)\n"
    "sys.stdout.write('held\\n'); sys.stdout.flush()\n"
    "sys.stdin.readline()\n"
    "fcntl.flock(fd, fcntl.LOCK_UN)\n"
    "sys.stdout.write('released\\n'); sys.stdout.flush()\n"
)


class Halter:
    def __init__(self, proc: subprocess.Popen):
        self._proc = proc

    def freigeben(self) -> None:
        if self._proc.poll() is None:
            self._proc.stdin.write("go\n")
            self._proc.stdin.flush()
            assert self._proc.stdout.readline().strip() == "released"

    def beenden(self) -> None:
        if self._proc.poll() is None:
            self._proc.kill()
        self._proc.wait(timeout=10)
        for stream in (self._proc.stdin, self._proc.stdout):
            try:
                stream.close()
            except Exception:
                pass


@contextmanager
def fremde_sperre(lock_path: Path):
    """Ein Fremdprozess haelt ``flock(LOCK_EX)`` auf ``lock_path``."""
    proc = subprocess.Popen(
        [sys.executable, "-c", _HALTER, str(lock_path)],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True,
    )
    halter = Halter(proc)
    try:
        assert proc.stdout.readline().strip() == "held", "Fremdprozess hat die Sperre nicht erhalten"
        yield halter
    finally:
        halter.beenden()


def briefings_dir(user_id: str) -> Path:
    from app.loader import get_data_root

    return get_data_root() / "users" / user_id / "briefings"


def lock_pfad(user_id: str, entity_id: str) -> Path:
    """LITERAL-Pfad aus ADR-0083 -- bewusst NICHT ueber Produktivcode gebaut."""
    return briefings_dir(user_id) / f"{entity_id}.json.lock"


def frist_verkuerzen(monkeypatch, sekunden: float = 0.3) -> None:
    import services.file_lock as fl

    monkeypatch.setattr(fl, "LOCK_TIMEOUT_SECONDS", sekunden, raising=False)
    monkeypatch.setattr(fl, "BRIEFING_LOCK_TIMEOUT_SECONDS", sekunden, raising=False)


def gr221_trip(user_id: str, *, enabled: bool = True, skip_next: bool = False,
               mit_gpx: bool = False):
    """Speichert den echten GR221-Bestandstrip fuer ``user_id`` (echter
    ``save_trip``) und liefert das GELADENE Objekt (= das 'veraltete' Objekt
    der Aufrufer, sobald die Platte danach geaendert wird)."""
    from app.loader import get_data_root, load_trip, load_trip_from_dict, save_trip

    data = json.loads(GR221_JSON.read_text(encoding="utf-8"))
    data["report_config"]["enabled"] = enabled
    data["report_config"]["skip_next"] = skip_next
    trip = load_trip_from_dict(data)
    save_trip(trip, user_id)
    if mit_gpx:
        gpx_dir = get_data_root() / "users" / user_id / "gpx"
        gpx_dir.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(GR221_GPX_TAG1, gpx_dir / GR221_GPX_TAG1.name)
    return load_trip(trip.id, data_dir=get_data_root(), user_id=user_id)


def trip_datei(user_id: str, trip_id: str) -> Path:
    return briefings_dir(user_id) / f"{trip_id}.json"


def browser_aendert(user_id: str, trip_id: str, name: str = "Browser-Name") -> list[str]:
    """Simuliert Go/Browser: Name + Etappenliste auf der Platte aendern (neue
    Etappe 'T9' angehaengt). Liefert die Etappen-IDs des Endstands."""
    pfad = trip_datei(user_id, trip_id)
    data = json.loads(pfad.read_text(encoding="utf-8"))
    data["name"] = name
    neu = json.loads(json.dumps(data["stages"][-1]))
    neu["id"] = "T9"
    neu["name"] = "Browser-Etappe"
    neu["date"] = "2026-03-01"
    data["stages"].append(neu)
    pfad.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return [s["id"] for s in data["stages"]]


def lese(user_id: str, trip_id: str) -> dict:
    return json.loads(trip_datei(user_id, trip_id).read_text(encoding="utf-8"))


def compare_preset(user_id: str, preset_id: str = "vgl-2158", **extra) -> Path:
    pfad = briefings_dir(user_id) / f"{preset_id}.json"
    pfad.parent.mkdir(parents=True, exist_ok=True)
    entry = {"id": preset_id, "name": "Vergleich 2158", "kind": "vergleich",
             "schedule": "daily", "location_ids": ["a", "b"]}
    entry.update(extra)
    pfad.write_text(json.dumps(entry, indent=2, ensure_ascii=False), encoding="utf-8")
    return pfad

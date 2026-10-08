"""AC-8 (Epic #1539, S1a): gleichzeitige Eintraege ins Alarm-Log gehen nicht verloren.

Given N=12 Threads, die ueber eine `threading.Barrier` gleichzeitig mehrere
      Eintraege in das Alarm-Log DESSELBEN Nutzers schreiben (Log vorbefuellt,
      damit Lesen/Parsen/Schreiben der Datei messbar dauert)
When  alle fertig sind
Then  enthaelt `alert_log.json` genau N*K neue Eintraege, jeden genau einmal,
      und die Datei ist gueltiges JSON; die Datei eines zweiten Nutzers bleibt
      davon unberuehrt (kein Uebersprechen).

Echter Dienst auf tmp-Daten: `append_entry()` schreibt ueber `get_data_dir()`
in das vom Autouse-Fixture (tests/conftest.py) umgebogene Datenverzeichnis.
Kein Mock, kein Netz.

RED heute: `_append` macht ungesperrt Read-Modify-Write mit `write_text`
(Verlust durch ueberlappende Schreiber, abgeschnittene Datei beim Lesen).
Der Test macht die Race-Luecke breit (grosses Log, mehrere Eintraege je
Thread), damit er nicht vom Zufall abhaengt.
"""
from __future__ import annotations

import json
import sys
import threading
from pathlib import Path

_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from app.loader import get_data_dir  # noqa: E402
from services import alert_log  # noqa: E402

N_THREADS = 12
PER_THREAD = 4
PREFILL = 1500


def _prefill(user_id: str) -> Path:
    path = get_data_dir(user_id) / "alert_log.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    alt = [
        {"entity_id": f"alt-{i}", "entity_type": "trip", "sent_at": "2026-01-01T00:00:00+00:00",
         "changes_count": 1, "severity": "minor", "metrics": [], "hazards": [],
         "reason": "forecast_change", "channels_sent": ["email"], "channels_not_sent": []}
        for i in range(PREFILL)
    ]
    path.write_text(json.dumps({"entries": alt, "not_delivered": []}, indent=2))
    return path


def _eintrag(user_id: str, marker: str) -> None:
    alert_log.append_entry(
        user_id, entity_id=marker, entity_type="trip", changes_count=1,
        severity="moderate", reason="forecast_change",
        effective_channels=["email"], sent_channels=["email"],
    )


def _lauf(monkeypatch, ziele: list[tuple[str, str]], per_thread: int = PER_THREAD) -> list:
    """Startet je Ziel (nutzer, marker-praefix) einen Thread hinter einer Barrier."""
    fehler: list = []
    monkeypatch.setattr(threading, "excepthook", lambda a: fehler.append(a.exc_value))
    barrier = threading.Barrier(len(ziele))

    def arbeiter(u: str, praefix: str) -> None:
        barrier.wait(timeout=10)
        for k in range(per_thread):
            _eintrag(u, f"{praefix}-k{k}")

    threads = [threading.Thread(target=arbeiter, args=z) for z in ziele]
    for th in threads:
        th.start()
    for th in threads:
        th.join(timeout=60)
    return fehler


def test_gleichzeitige_alarm_eintraege_gehen_nicht_verloren(monkeypatch):
    """AC-8: 12 Threads x 4 Eintraege -> genau 48 neue Eintraege, je einmal,
    gueltiges JSON; zweiter Nutzer bleibt unberuehrt."""
    nutzer, fremder = "ac8-alice", "ac8-bob"
    pfad = _prefill(nutzer)
    pfad_fremd = _prefill(fremder)
    fremd_vorher = pfad_fremd.read_bytes()

    fehler = _lauf(monkeypatch, [(nutzer, f"ac8-t{t}") for t in range(N_THREADS)])

    assert not fehler, f"Thread-Ausnahmen: {fehler!r}"
    try:
        data = json.loads(pfad.read_text())
    except ValueError as e:
        raise AssertionError(f"alert_log.json ist kein gueltiges JSON mehr: {e}")
    neue = [e["entity_id"] for e in data["entries"] if e["entity_id"].startswith("ac8-t")]
    erwartet = {f"ac8-t{t}-k{k}" for t in range(N_THREADS) for k in range(PER_THREAD)}
    assert len(neue) == N_THREADS * PER_THREAD, (
        f"{len(neue)} statt {N_THREADS * PER_THREAD} Eintraegen -- "
        f"verloren: {sorted(erwartet - set(neue))[:5]}..."
    )
    assert set(neue) == erwartet and len(set(neue)) == len(neue), "Eintrag fehlt oder doppelt"
    assert len(data["entries"]) == PREFILL + N_THREADS * PER_THREAD, "Alt-Eintraege beschaedigt"
    assert pfad_fremd.read_bytes() == fremd_vorher, "Datei des zweiten Nutzers veraendert"


def test_zwei_nutzer_schreiben_gleichzeitig_ohne_uebersprechen(monkeypatch):
    """AC-8 (Zwei-Nutzer-Pflicht): je 6 Threads fuer Alice und Bob; jede Datei
    enthaelt ausschliesslich und vollstaendig die eigenen Eintraege."""
    nutzer = ("ac8x-alice", "ac8x-bob")
    pfade = {u: _prefill(u) for u in nutzer}

    ziele = [(nutzer[t % 2], f"{nutzer[t % 2]}-t{t}") for t in range(N_THREADS)]
    fehler = _lauf(monkeypatch, ziele)
    assert not fehler, f"Thread-Ausnahmen: {fehler!r}"

    for idx, u in enumerate(nutzer):
        data = json.loads(pfade[u].read_text())
        neue = [e["entity_id"] for e in data["entries"] if e["entity_id"].startswith(u)]
        erwartet = {f"{u}-t{t}-k{k}" for t in range(idx, N_THREADS, 2) for k in range(PER_THREAD)}
        assert set(neue) == erwartet and len(neue) == len(erwartet), (
            f"{u}: {len(neue)} statt {len(erwartet)} eigenen Eintraegen"
        )
        fremd = [e for e in data["entries"] if e["entity_id"].startswith(nutzer[1 - idx])]
        assert not fremd, f"{u}: enthaelt Eintraege des anderen Nutzers"

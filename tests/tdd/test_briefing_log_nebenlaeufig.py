"""Briefing-Log: gleichzeitige Schreiber verlieren keinen Eintrag (#2281, AC-6).

SPEC: docs/specs/modules/feat_2281_vergleich_versand_historie.md (AC-6, Test 4)

Wirkort: der gemeinsame Schreib-Helfer
``services.briefing_log.append_briefing_log(user_id, entity_type, entity_id,
kind, channels, on_demand, mail_to)`` (Sperre + frisch lesen + atomar
schreiben, Vorlage ``alert_log._append``).

Zwei Formen der Ueberlappung, wie sie im Betrieb vorkommen:

* Threads im selben Prozess (Handversand im FastAPI-Threadpool + Scheduler im
  Python-Core). Start ueber eine ``threading.Barrier``, damit die Schreiber
  wirklich gleichzeitig loslaufen.
* Getrennte Prozesse (``subprocess``; die Datenwurzel wird dem Kind
  ausdruecklich uebergeben -- kein Verlass auf vererbten Modulzustand).

Danach: Datei ist ein JSON-Objekt ``{"entries": [...]}``, enthaelt JEDEN
Eintrag genau einmal (Menge der ``entity_id`` == erwartete Menge, Anzahl exakt).

RED heute: ``services.briefing_log`` existiert nicht (ImportError).
Der Import steht in jeder Testfunktion, damit die Datei sammelbar bleibt.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
import threading
import uuid
from pathlib import Path

from app.loader import get_data_dir, get_data_root

ROOT = Path(__file__).resolve().parents[2]

THREADS = 8
JE_THREAD = 25
PROZESSE = 4
JE_PROZESS = 25


def _uid() -> str:
    uid = f"nebenlauf-{uuid.uuid4().hex[:8]}"
    get_data_dir(uid).mkdir(parents=True, exist_ok=True)
    return uid


def _log_lesen(uid: str) -> list[dict]:
    pfad = get_data_dir(uid) / "briefing_log.json"
    assert pfad.exists(), f"AC-6: {pfad} fehlt nach den Schreibvorgaengen"
    daten = json.loads(pfad.read_text(encoding="utf-8"))  # muss gueltiges JSON sein
    assert isinstance(daten, dict) and isinstance(daten.get("entries"), list), (
        f"AC-6: Format {{'entries': [...]}} erwartet, war {type(daten).__name__}"
    )
    return daten["entries"]


def _pruefen(uid: str, erwartet: set[str]) -> None:
    eintraege = _log_lesen(uid)
    ids = [e.get("entity_id") for e in eintraege]
    assert len(eintraege) == len(erwartet), (
        f"AC-6: {len(erwartet)} Eintraege erwartet, {len(eintraege)} vorhanden "
        f"({len(erwartet - set(ids))} verloren)"
    )
    assert set(ids) == erwartet, f"AC-6: verloren: {sorted(erwartet - set(ids))[:10]}"


def test_parallele_threads_verlieren_keinen_eintrag():
    """AC-6 (Threads).

    GIVEN ein Nutzer ohne Log.
    WHEN  8 Threads gleichzeitig je 25 Eintraege anhaengen (Trip und Compare
          gemischt, Cron und Hand gemischt).
    THEN  alle 200 Eintraege stehen genau einmal in gueltigem JSON.
    """
    from services.briefing_log import append_briefing_log

    uid = _uid()
    start = threading.Barrier(THREADS)
    fehler: list[BaseException] = []

    def schreiber(n: int) -> None:
        try:
            start.wait()
            for i in range(JE_THREAD):
                append_briefing_log(
                    uid, "compare" if (n + i) % 2 else "trip", f"t{n}-{i}",
                    "morning" if i % 2 else "evening", ["email"], bool(n % 2), None,
                )
        except BaseException as exc:  # noqa: BLE001 -- im Haupt-Thread melden
            fehler.append(exc)

    threads = [threading.Thread(target=schreiber, args=(n,)) for n in range(THREADS)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=120)
    assert not any(t.is_alive() for t in threads), "AC-6: Schreiber haengen (Sperre?)"
    assert not fehler, f"AC-6: Schreiber warfen: {fehler[:3]!r}"

    _pruefen(uid, {f"t{n}-{i}" for n in range(THREADS) for i in range(JE_THREAD)})


_KIND_SKRIPT = textwrap.dedent("""
    import sys
    from pathlib import Path
    root, datenwurzel, uid, n, anzahl = sys.argv[1:6]
    for p in (root, root + "/src"):
        sys.path.insert(0, p)
    import app.loader as loader
    loader._DATA_ROOT = datenwurzel
    from services.briefing_log import append_briefing_log
    for i in range(int(anzahl)):
        append_briefing_log(uid, "compare" if i % 2 else "trip", f"p{n}-{i}",
                            "morning", ["email"], False, None)
""")


def test_parallele_prozesse_verlieren_keinen_eintrag():
    """AC-6 (Prozesse).

    GIVEN ein Nutzer ohne Log.
    WHEN  4 getrennte Prozesse gleichzeitig je 25 Eintraege anhaengen.
    THEN  alle 100 Eintraege stehen genau einmal in gueltigem JSON.
    """
    from services.briefing_log import append_briefing_log  # noqa: F401 -- RED-Grund sichtbar

    uid = _uid()
    datenwurzel = str(get_data_root())
    env = dict(os.environ, GZ_DATA_DIR=datenwurzel)
    kinder = [
        subprocess.Popen(
            [sys.executable, "-c", _KIND_SKRIPT, str(ROOT), datenwurzel, uid, str(n), str(JE_PROZESS)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env, cwd=str(ROOT),
        )
        for n in range(PROZESSE)
    ]
    for k in kinder:
        out, err = k.communicate(timeout=180)
        assert k.returncode == 0, f"AC-6: Kindprozess scheiterte ({k.returncode}): {err[-2000:]}"

    _pruefen(uid, {f"p{n}-{i}" for n in range(PROZESSE) for i in range(JE_PROZESS)})

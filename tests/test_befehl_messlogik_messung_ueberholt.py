"""Kern: Ist die Sofort-Weg-Messung von `test_ac1_sms_last_run_sekunden_nach_webhook` noch
gueltig? (#2439, AC-11)

Spec: docs/specs/modules/feat_2439_push_eingang_prod_scharf.md

Ueberholt = der Poll-Lauf nach dem Webhook ist durch einen SPAETEREN `*/5`-Tick
ueberschrieben (zwischen `push.last_received` und `last_run.time` liegt eine
5-Minuten-Grenze UND der Abstand ueberschreitet die Grenze). Dann sagt `last_run` nichts
mehr ueber den Sofort-Weg -> Skip. Liegt dagegen KEINE Tick-Grenze dazwischen und der
Abstand ist trotzdem zu gross, ist das ein echter Verstoss -> NICHT ueberholt, der
Aufrufer wird rot.

Die Job-Form ist die echte Antwort von `/api/scheduler/status` (Prod, 20.10., Zeitstempel
mit Offset `+02:00`); nur Zeitwerte sind je Fall gesetzt.

Vertrag an ``.claude/tools/befehl_messlogik.py``:
  messung_ueberholt(job, grenze_s=60, takt_s=300) -> bool
"""
from __future__ import annotations

import copy
import importlib.util
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[1]

_JOB_ECHT = {
    "id": "premium_sms_poll",
    "last_run": {"duration_s": 0.122, "error": "", "status": "ok",
                 "time": "2026-10-20T10:10:00+02:00"},
    "name": "Premium SMS Poll (every 5min)",
    "next_run": "2026-10-20T10:15:00+02:00",
    "push": {"kicks_coalesced": 0, "last_missed": None, "last_received": None,
             "missed_total": 0, "received_total": 0, "rejected_total": 0},
}


def _messlogik():
    pfad = _REPO / ".claude" / "tools" / "befehl_messlogik.py"
    spec = importlib.util.spec_from_file_location("befehl_messlogik", pfad)
    assert spec and pfad.is_file(), f"{pfad} fehlt"
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def _job(empfangen: str, gelaufen: str) -> dict:
    job = copy.deepcopy(_JOB_ECHT)
    job["push"].update(last_received=f"2026-10-20T{empfangen}+02:00", received_total=1)
    job["last_run"]["time"] = f"2026-10-20T{gelaufen}+02:00"
    return job


@pytest.mark.parametrize("empfangen, gelaufen, erwartet, warum", [
    ("10:01:10", "10:01:13", False, "Poll direkt nach dem Webhook -> gueltig, wird geprueft"),
    ("10:01:10", "10:05:00", True, "spaeterer */5-Tick hat last_run ueberschrieben"),
    ("10:01:10", "10:20:00", True, "mehrere Ticks spaeter gemessen"),
    ("10:01:10", "10:02:20", False, "70 s ohne Tick dazwischen = echter Verstoss, rot bleiben"),
    ("10:01:10", "10:04:59", False, "knapp vor dem Tick = echter Verstoss, rot bleiben"),
    ("10:04:50", "10:05:01", False, "Tick-Grenze dazwischen, aber innerhalb der Grenze"),
    ("10:03:55", "10:00:00", False, "Weckruf ausgefallen: last_run noch VOR dem Webhook -> rot"),
])
def test_ac11_gueltigkeit_der_sofortweg_messung(empfangen, gelaufen, erwartet, warum):
    ml = _messlogik()
    assert ml.messung_ueberholt(_job(empfangen, gelaufen)) is erwartet, warum


def test_ac11_grenze_und_takt_sind_parameter():
    ml = _messlogik()
    job = _job("10:01:10", "10:02:20")
    assert ml.messung_ueberholt(job, grenze_s=60, takt_s=60) is True
    assert ml.messung_ueberholt(job, grenze_s=120) is False


def test_ac11_zeitzonen_werden_verglichen_nicht_die_zeichenketten():
    """`last_received` in UTC, `last_run` mit +02:00 -- derselbe Moment plus 3 s."""
    ml = _messlogik()
    job = _job("10:01:10", "10:01:13")
    job["push"]["last_received"] = "2026-10-20T08:01:10+00:00"
    assert ml.messung_ueberholt(job) is False

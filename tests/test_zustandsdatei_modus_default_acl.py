"""Zustandsdateien entstehen mit 0660 (Issue #2624, AC-10).

Unter einer Default-ACL begrenzt der bei der Anlage uebergebene Modus die
ACL-Maske. ``tempfile.mkstemp`` legt die Temp-Datei mit 0600 an, und
``os.replace`` uebernimmt diesen Modus fuer die Zustandsdatei -- die
Dienstgruppe verliert damit Lese- und Schreibrecht. Geprueft wird am Ort der
Wirkung: der echte oeffentliche Schreibpfad jedes der neun mkstemp-Dienste
laeuft in tmp_path unter Umask 0077, danach wird der Modus der entstandenen
ZUSTANDSdatei (nicht der ``.lock``) gelesen -- keine Quelltext-Pruefung,
keine Mocks.

Ausnahme Inbound-SMS: der oeffentliche Weg ``poll_and_process`` erreicht den
Schreibvorgang nur nach einem echten Journal-Abruf bei seven.io (Netz). Der
Test ruft deshalb den echten Schreibvorgang ``_save_last_seen_id`` direkt
auf -- derselbe Code, den der Poll am Ende ausfuehrt, ohne Ersatzobjekt.
"""
from __future__ import annotations

import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

NOW = datetime(2026, 10, 27, 12, 0, tzinfo=timezone.utc)
UID = "alice"


@pytest.fixture(autouse=True)
def _umask_077_und_datenwurzel(tmp_path, monkeypatch):
    monkeypatch.setenv("GZ_DATA_DIR", str(tmp_path))
    import app.loader as loader
    monkeypatch.setattr(loader, "_DATA_ROOT", tmp_path)
    alt = os.umask(0o077)
    yield
    os.umask(alt)


# Jede Funktion loest den echten Schreibpfad aus und gibt die Dateinamen der
# Zustandsdateien zurueck, die dabei entstehen MUESSEN.

def _forecast_budget(tmp_path):
    from services.forecast_budget import ForecastBudgetGate
    ForecastBudgetGate(UID, data_root=tmp_path).record_call()
    # global (diagnostics/) UND je Nutzer (users/<uid>/diagnostics/)
    return ["forecast_budget.json", "forecast_budget.json"]


def _briefing_slots(tmp_path):
    from services.briefing_slots import BriefingSlotStore
    BriefingSlotStore(UID, data_dir=tmp_path).reserve(
        "trip1", "morning", date(2026, 10, 27), moment=NOW)
    return ["briefing_slots.json"]


def _sms_daily_limit(tmp_path):
    from services.sms_daily_limit import seed_daily_usage
    seed_daily_usage(UID, 1, 0, NOW)
    return ["sms_daily_count.json"]


def _throttle_store(tmp_path):
    from services.throttle_store import ThrottleStore
    ThrottleStore(UID, data_dir=tmp_path).record("scope", "key", NOW)
    return ["throttle_state.json"]


def _alert_check_state(tmp_path):
    from services.alert_check_state import AlertCheckStateStore
    AlertCheckStateStore(UID).record({"t1": NOW}, ["t1"])
    return ["alert_last_checked.json"]


def _alert_daily_limit(tmp_path):
    from services.alert_daily_limit import increment
    increment(UID, NOW, ZoneInfo("Europe/Vienna"), urgency="MODERATE")
    return ["alert_daily_count.json"]


def _position_fix(tmp_path):
    from services.position_fix import record_position_fix
    from tests.helpers.position_fix_fixtures import (
        ECHT_HEUTE_KOORD, gpx_schreiben, heute_track_punkte, ortszeit,
        trip_schreiben,
    )
    gpx_schreiben(UID, "heute", heute_track_punkte())
    trip_schreiben(UID, "gps-trip")
    ergebnis = record_position_fix(UID, *ECHT_HEUTE_KOORD, ortszeit(10))
    assert ergebnis is not None, "Testaufbau: plausibler Fix wurde verworfen"
    return ["position_fix.json"]


def _inbound_sms_reader(tmp_path):
    from services.inbound_sms_reader import InboundSmsReader
    InboundSmsReader()._save_last_seen_id(tmp_path, 42)
    return ["premium_sms_inbound.json"]


# Issue #2266: der MeteoAlarm-Budget-Schreibpfad ist mit dem Rueckbau der
# EDR-Klasse entfallen.
SCHREIBPFADE = [
    _forecast_budget, _briefing_slots, _sms_daily_limit, _throttle_store,
    _alert_check_state, _alert_daily_limit,
    _position_fix, _inbound_sms_reader,
]


@pytest.mark.parametrize("pfad", SCHREIBPFADE, ids=lambda f: f.__name__.lstrip("_"))
def test_zustandsdatei_entsteht_mit_modus_0660_unter_umask_077(pfad, tmp_path):
    erwartet = pfad(tmp_path)
    for name in sorted(set(erwartet)):
        dateien = sorted(tmp_path.rglob(name))
        # Untergrenze gegen Vakuum-Gruen: die Zustandsdatei muss entstanden sein.
        assert len(dateien) >= erwartet.count(name), (
            f"{pfad.__name__}: {name} nicht (vollstaendig) entstanden -- "
            f"gefunden {dateien}; Test waere vakuum")
        for datei in dateien:
            assert not datei.name.endswith(".lock")
            modus = datei.stat().st_mode & 0o777
            assert modus == 0o660, (
                f"{datei.relative_to(tmp_path)}: Modus {oct(modus)}, erwartet 0o660")

"""Sperrdateien entstehen mit 0660 (Issue #2624, AC-6).

Unter einer Default-ACL begrenzt der bei der Anlage uebergebene Modus die
ACL-Maske; 0644 nimmt der Dienstgruppe das Schreibrecht. Geprueft wird am Ort
der Wirkung: die echten oeffentlichen Schreibpfade der acht Stellen laufen in
tmp_path unter Umask 0077, danach wird der Modus der entstandenen *.lock
gelesen -- keine Quelltext-Pruefung.
"""
from __future__ import annotations

import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

NOW = datetime(2026, 10, 27, 12, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def _umask_077_und_datenwurzel(tmp_path, monkeypatch):
    monkeypatch.setenv("GZ_DATA_DIR", str(tmp_path))
    import app.loader as loader
    monkeypatch.setattr(loader, "_DATA_ROOT", tmp_path)
    alt = os.umask(0o077)
    yield
    os.umask(alt)


def _locks(wurzel: Path) -> list[Path]:
    return sorted(wurzel.rglob("*.lock"))


def _file_lock(tmp_path):
    from services.file_lock import exclusive_lock
    with exclusive_lock(tmp_path / "x.json"):
        pass


def _throttle(tmp_path):
    from services.throttle_store import ThrottleStore
    ThrottleStore("alice", data_dir=tmp_path).record("scope", "key", NOW)


def _slots_reserve(tmp_path):
    from services.briefing_slots import BriefingSlotStore
    BriefingSlotStore("alice", data_dir=tmp_path).reserve(
        "trip1", "morning", date(2026, 10, 27), moment=NOW)


def _slots_repair(tmp_path):
    from services.briefing_slots import BriefingSlotStore
    s = BriefingSlotStore("alice", data_dir=tmp_path)
    (tmp_path / "x").mkdir(exist_ok=True)
    s.repair_if_corrupt(NOW)


def _forecast_budget(tmp_path):
    from services.forecast_budget import ForecastBudgetGate
    ForecastBudgetGate("alice", data_root=tmp_path).record_call()


def _alert_check_state(tmp_path):
    from services.alert_check_state import AlertCheckStateStore
    AlertCheckStateStore("alice").record({"t1": NOW}, ["t1"])


def _sms_seed(tmp_path):
    from services.sms_daily_limit import seed_daily_usage
    seed_daily_usage("alice", 1, 0, NOW)


def _sms_release(tmp_path):
    from services.sms_daily_limit import release_reservation, seed_daily_usage
    seed_daily_usage("alice", 1, 0, NOW)
    for p in list(tmp_path.rglob("*.lock")):
        p.unlink()
    release_reservation("alice", "sms", NOW)


def _sms_reserve(tmp_path):
    from services import user_tier
    from services.sms_daily_limit import check_and_reserve
    # Tarif mit Kontingent (free = Cap 0 sperrt VOR der Sperrdatei).
    orig = user_tier.daily_sms_limit
    user_tier.daily_sms_limit = lambda _uid: 10
    try:
        check_and_reserve("alice", "sms", "alert", NOW)
    finally:
        user_tier.daily_sms_limit = orig


# Issue #2266: der MeteoAlarm-Budget-Schreibpfad ist mit dem Rueckbau der
# EDR-Klasse entfallen.
SCHREIBPFADE = [
    _file_lock, _throttle, _slots_reserve, _slots_repair, _forecast_budget,
    _alert_check_state, _sms_seed, _sms_release, _sms_reserve,
]


@pytest.mark.parametrize("pfad", SCHREIBPFADE, ids=lambda f: f.__name__.lstrip("_"))
def test_sperrdatei_entsteht_mit_modus_0660_unter_umask_077(pfad, tmp_path):
    pfad(tmp_path)
    locks = _locks(tmp_path)
    if not locks and pfad.__name__ in ("_slots_repair",):
        pytest.skip("repair_if_corrupt legt ohne beschaedigte Datei keine Sperre an")
    assert locks, f"{pfad.__name__}: keine .lock entstanden -- Test waere vakuum"
    for lock in locks:
        modus = lock.stat().st_mode & 0o777
        assert modus == 0o660, f"{lock.name}: Modus {oct(modus)}, erwartet 0o660"


# Adversary F003 / Known Limitation: eine BESTEHENDE Sperrdatei (Altbestand
# 0644) behaelt ihren Modus, und der Schreibpfad laeuft ohne Fehler durch
# (kein chmod auf fremde/alte Dateien). _sms_release entfernt die Sperren
# absichtlich und ist daher hier ohne Aussage.
@pytest.mark.parametrize(
    "pfad", [p for p in SCHREIBPFADE if p is not _sms_release],
    ids=lambda f: f.__name__.lstrip("_"))
def test_bestehende_sperrdatei_behaelt_modus_0644(pfad, tmp_path):
    pfad(tmp_path)
    locks = _locks(tmp_path)
    if not locks and pfad.__name__ in ("_slots_repair",):
        pytest.skip("repair_if_corrupt legt ohne beschaedigte Datei keine Sperre an")
    assert locks, f"{pfad.__name__}: keine .lock entstanden -- Test waere vakuum"
    for lock in locks:
        os.chmod(lock, 0o644)
    pfad(tmp_path)
    for lock in locks:
        modus = lock.stat().st_mode & 0o777
        assert modus == 0o644, f"{lock.name}: Modus {oct(modus)}, erwartet unveraendert 0o644"

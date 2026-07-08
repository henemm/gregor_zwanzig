"""
TDD RED für Issue #937: Staging hat keinen dauerhaften Test-Trip mit
Zukunftsdatum + gregor-test@henemm.com-Empfänger für briefing_mail_validator.py.

KEINE Mocks — echter HTTP-Call gegen den internen Staging-Scheduler-Port
(localhost:8001, läuft auf demselben Host) für den fest vereinbarten
Rolling-Trip (trip_id "staging-validator-rolling", User validator-issue110).
Weder das Setup-Script noch der Trip existieren vor dem Fix — beide Tests
müssen deshalb JETZT fehlschlagen (RED).
"""
from __future__ import annotations

import importlib

import httpx
import pytest

STAGING_SCHEDULER_URL = "http://localhost:8001"
TEST_TRIP_ID = "staging-validator-rolling"
TEST_USER_ID = "validator-issue110"


def _staging_scheduler_reachable() -> bool:
    try:
        httpx.post(
            f"{STAGING_SCHEDULER_URL}/api/scheduler/trips/__reachability_probe__/send",
            params={"user_id": TEST_USER_ID, "report_type": "evening"},
            timeout=3,
        )
        return True
    except httpx.ConnectError:
        return False


def test_setup_script_exists_and_is_importable():
    """Given #937 / When das Setup-Script importiert wird / Then existiert es (noch nicht -> RED)."""
    try:
        module = importlib.import_module("scripts.setup_staging_validator_trip")
    except ModuleNotFoundError as exc:
        pytest.fail(
            "scripts/setup_staging_validator_trip.py existiert noch nicht — "
            f"das Setup-Script für den Rolling-Staging-Test-Trip fehlt (#937). Original-Fehler: {exc}"
        )
    assert hasattr(module, "main"), "setup_staging_validator_trip.py muss eine main()-Funktion haben"


@pytest.mark.skipif(
    not _staging_scheduler_reachable(),
    reason="Interner Staging-Scheduler-Port 8001 auf diesem Host nicht erreichbar",
)
def test_rolling_trip_send_returns_sent_true():
    """Given der Rolling-Trip / When Versand getriggert wird / Then {'sent': true}."""
    resp = httpx.post(
        f"{STAGING_SCHEDULER_URL}/api/scheduler/trips/{TEST_TRIP_ID}/send",
        params={"user_id": TEST_USER_ID, "report_type": "evening"},
        timeout=30,
    )
    body = resp.json()
    assert resp.status_code == 200 and body.get("sent") is True, (
        f"Erwartet {{'sent': true}} für Trip '{TEST_TRIP_ID}' (User {TEST_USER_ID}), "
        f"bekommen: HTTP {resp.status_code} {body!r}. Der Rolling-Test-Trip aus #937 "
        "existiert noch nicht auf Staging."
    )

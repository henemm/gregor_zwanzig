"""TDD-RED: Issue #448 — Validator-Endpoint für metrics-for-channel-Kaskade.

Spec: docs/specs/modules/issue_448_validator_metrics_for_channel.md

Endpoint: GET /api/_validator/metrics-for-channel
Parameters: trip=<id>, channel=<ch>, report=<morning|evening>, user_id=<id>
Response:   {"source": "per_report|per_channel|global", "metric_ids": [...]}

Sechs ACs decken die dreistufige Kaskade ab:
- AC-1: Kein Kaskaden-Eintrag → source="global"
- AC-2: per_channel_layouts["email"] vorhanden → source="per_channel"
- AC-3: per_report_layouts["morning"]["email"] vorhanden → source="per_report" (schlägt per_channel)
- AC-4: per_report für telegram, nicht für email → Fallback auf global für email
- AC-5: Leere per_report-Liste → source="per_report", metric_ids=[]
- AC-6: Unbekannter Trip → 404

Keine Mocks — echte Trip-Fixtures in data/users/. Tests scheitern in RED,
weil GET /api/_validator/metrics-for-channel noch nicht implementiert ist.
"""

from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def client():
    """FastAPI TestClient für den validator-Router."""
    from api.routers import validator
    app = FastAPI()
    app.include_router(validator.router)
    return TestClient(app)


def _write_trip(user_id: str, trip_id: str, payload: dict) -> None:
    # Issue #1250 Scheibe 7a (Adversary F001): validator.py liest seit dem
    # Cutover briefings/, nicht mehr trips/ (s. test_issue_221 Modul-
    # Docstring fuer die src.app.loader-Isolations-Ausnahme).
    trip_dir = Path("data/users") / user_id / "briefings"
    trip_dir.mkdir(parents=True, exist_ok=True)
    (trip_dir / f"{trip_id}.json").write_text(json.dumps(payload))


@pytest.fixture
def trip_global():
    """AC-1: Trip mit globaler Metrik-Liste, kein per_channel/per_report."""
    user_id = f"test_issue_448_{uuid.uuid4().hex[:8]}"
    trip_id = "trip-global"
    _write_trip(user_id, trip_id, {
        "id": trip_id,
        "name": "Global Metrics Trip",
        "stages": [],
        "display_config": {
            "trip_id": trip_id,
            "metrics": [
                {"metric_id": "temperature", "enabled": True},
                {"metric_id": "wind_speed", "enabled": True},
            ],
        },
    })
    yield user_id, trip_id
    shutil.rmtree(Path("data/users") / user_id, ignore_errors=True)


@pytest.fixture
def trip_per_channel():
    """AC-2: Trip mit channel_layouts["email"], kein per_report."""
    user_id = f"test_issue_448_{uuid.uuid4().hex[:8]}"
    trip_id = "trip-per-channel"
    _write_trip(user_id, trip_id, {
        "id": trip_id,
        "name": "Per-Channel Trip",
        "stages": [],
        "display_config": {
            "trip_id": trip_id,
            "metrics": [
                {"metric_id": "temperature", "enabled": True},
                {"metric_id": "wind_speed", "enabled": True},
            ],
            "channel_layouts": {
                "email": [
                    {"metric_id": "precipitation", "enabled": True},
                    {"metric_id": "humidity", "enabled": True},
                ],
            },
        },
    })
    yield user_id, trip_id
    shutil.rmtree(Path("data/users") / user_id, ignore_errors=True)


@pytest.fixture
def trip_per_report_and_channel():
    """AC-3: Trip mit per_report_layouts["morning"]["email"] UND channel_layouts["email"].

    per_report muss per_channel schlagen.
    """
    user_id = f"test_issue_448_{uuid.uuid4().hex[:8]}"
    trip_id = "trip-per-report-and-channel"
    _write_trip(user_id, trip_id, {
        "id": trip_id,
        "name": "Per-Report-And-Channel Trip",
        "stages": [],
        "display_config": {
            "trip_id": trip_id,
            "metrics": [
                {"metric_id": "temperature", "enabled": True},
            ],
            "channel_layouts": {
                "email": [
                    {"metric_id": "wind_speed", "enabled": True},
                ],
            },
            "channel_layouts_per_report": {
                "morning": {
                    "email": [
                        {"metric_id": "sunshine_hours", "enabled": True},
                    ],
                },
            },
        },
    })
    yield user_id, trip_id
    shutil.rmtree(Path("data/users") / user_id, ignore_errors=True)


@pytest.fixture
def trip_per_report_telegram_only():
    """AC-4: per_report_layouts["morning"]["telegram"] vorhanden, NICHT ["morning"]["email"].

    Für channel=email muss Fallback auf global greifen.
    """
    user_id = f"test_issue_448_{uuid.uuid4().hex[:8]}"
    trip_id = "trip-per-report-telegram-only"
    _write_trip(user_id, trip_id, {
        "id": trip_id,
        "name": "Per-Report Telegram Trip",
        "stages": [],
        "display_config": {
            "trip_id": trip_id,
            "metrics": [
                {"metric_id": "temperature", "enabled": True},
                {"metric_id": "precipitation", "enabled": True},
            ],
            "channel_layouts_per_report": {
                "morning": {
                    "telegram": [
                        {"metric_id": "wind_speed", "enabled": True},
                    ],
                },
            },
        },
    })
    yield user_id, trip_id
    shutil.rmtree(Path("data/users") / user_id, ignore_errors=True)


@pytest.fixture
def trip_per_report_empty_list():
    """AC-5: per_report_layouts["morning"]["email"] = [] (expliziter User-Wunsch).

    Leere Liste = kein Fallback — source bleibt "per_report", metric_ids=[].
    """
    user_id = f"test_issue_448_{uuid.uuid4().hex[:8]}"
    trip_id = "trip-per-report-empty"
    _write_trip(user_id, trip_id, {
        "id": trip_id,
        "name": "Per-Report Empty Trip",
        "stages": [],
        "display_config": {
            "trip_id": trip_id,
            "metrics": [
                {"metric_id": "temperature", "enabled": True},
            ],
            "channel_layouts": {
                "email": [
                    {"metric_id": "wind_speed", "enabled": True},
                ],
            },
            "channel_layouts_per_report": {
                "morning": {
                    "email": [],
                },
            },
        },
    })
    yield user_id, trip_id
    shutil.rmtree(Path("data/users") / user_id, ignore_errors=True)


# ---------------------------------------------------------------------------
# Endpoint Tests: GET /api/_validator/metrics-for-channel
# ---------------------------------------------------------------------------

class TestMetricsForChannelEndpoint:
    """AC-1 bis AC-6: dreistufige Kaskaden-Sichtbarkeit."""

    def test_ac1_no_cascade_config_returns_global(self, client, trip_global):
        """AC-1: Trip ohne Kaskaden-Konfiguration → source='global'."""
        user_id, trip_id = trip_global
        resp = client.get(
            "/api/_validator/metrics-for-channel",
            params={"trip": trip_id, "channel": "email", "report": "morning", "user_id": user_id},
        )
        assert resp.status_code == 200, f"Erwartet 200, got {resp.status_code}: {resp.text[:300]}"
        data = resp.json()
        assert data["source"] == "global", f"source muss 'global' sein, got: {data['source']!r}"
        assert isinstance(data["metric_ids"], list), "metric_ids muss eine Liste sein"
        assert "temperature" in data["metric_ids"], (
            "Globale Metriken müssen in metric_ids erscheinen"
        )

    def test_ac2_per_channel_layout_returns_per_channel(self, client, trip_per_channel):
        """AC-2: per_channel_layouts['email'] vorhanden → source='per_channel'."""
        user_id, trip_id = trip_per_channel
        resp = client.get(
            "/api/_validator/metrics-for-channel",
            params={"trip": trip_id, "channel": "email", "report": "morning", "user_id": user_id},
        )
        assert resp.status_code == 200, f"Erwartet 200, got {resp.status_code}: {resp.text[:300]}"
        data = resp.json()
        assert data["source"] == "per_channel", f"source muss 'per_channel' sein, got: {data['source']!r}"
        assert "precipitation" in data["metric_ids"], (
            "per_channel_layouts['email'] enthält precipitation — muss in metric_ids erscheinen"
        )
        assert "temperature" not in data["metric_ids"], (
            "Globale Metrik temperature darf nicht erscheinen wenn per_channel aktiv ist"
        )

    def test_ac3_per_report_beats_per_channel(self, client, trip_per_report_and_channel):
        """AC-3: per_report_layouts['morning']['email'] schlägt per_channel_layouts['email']."""
        user_id, trip_id = trip_per_report_and_channel
        resp = client.get(
            "/api/_validator/metrics-for-channel",
            params={"trip": trip_id, "channel": "email", "report": "morning", "user_id": user_id},
        )
        assert resp.status_code == 200, f"Erwartet 200, got {resp.status_code}: {resp.text[:300]}"
        data = resp.json()
        assert data["source"] == "per_report", f"source muss 'per_report' sein, got: {data['source']!r}"
        assert "sunshine_hours" in data["metric_ids"], (
            "per_report['morning']['email'] enthält sunshine_hours — muss gewonnen haben"
        )
        assert "wind_speed" not in data["metric_ids"], (
            "wind_speed ist nur in per_channel — darf nicht erscheinen wenn per_report aktiv ist"
        )

    def test_ac4_per_report_telegram_fallback_to_global_for_email(
        self, client, trip_per_report_telegram_only
    ):
        """AC-4: per_report für telegram, nicht für email → Fallback auf global für email."""
        user_id, trip_id = trip_per_report_telegram_only
        resp = client.get(
            "/api/_validator/metrics-for-channel",
            params={"trip": trip_id, "channel": "email", "report": "morning", "user_id": user_id},
        )
        assert resp.status_code == 200, f"Erwartet 200, got {resp.status_code}: {resp.text[:300]}"
        data = resp.json()
        assert data["source"] == "global", (
            f"telegram-Eintrag darf email nicht beeinflussen; source muss 'global' sein, got: {data['source']!r}"
        )
        assert "temperature" in data["metric_ids"], (
            "Globale Metriken (temperature, precipitation) müssen in metric_ids erscheinen"
        )

    def test_ac5_empty_per_report_list_no_fallback(self, client, trip_per_report_empty_list):
        """AC-5: per_report_layouts['morning']['email']=[] → source='per_report', metric_ids=[]."""
        user_id, trip_id = trip_per_report_empty_list
        resp = client.get(
            "/api/_validator/metrics-for-channel",
            params={"trip": trip_id, "channel": "email", "report": "morning", "user_id": user_id},
        )
        assert resp.status_code == 200, f"Erwartet 200, got {resp.status_code}: {resp.text[:300]}"
        data = resp.json()
        assert data["source"] == "per_report", (
            f"Leere Liste ist expliziter User-Wunsch; source muss 'per_report' sein, got: {data['source']!r}"
        )
        assert data["metric_ids"] == [], (
            f"Leere per_report-Liste darf nicht auf per_channel oder global fallen; metric_ids muss [] sein, got: {data['metric_ids']}"
        )

    def test_ac6_unknown_trip_returns_404(self, client):
        """AC-6: Nicht-existierende Trip-ID → HTTP 404."""
        resp = client.get(
            "/api/_validator/metrics-for-channel",
            params={
                "trip": "nonexistent-trip-id-448",
                "channel": "email",
                "report": "morning",
                "user_id": "default",
            },
        )
        assert resp.status_code == 404, (
            f"Unbekannter Trip muss 404 liefern, got {resp.status_code}: {resp.text[:200]}"
        )

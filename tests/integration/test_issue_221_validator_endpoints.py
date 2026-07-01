"""TDD-RED: Issue #221 — Validator-Sichtbarkeits-Endpoints.

Spec: docs/specs/modules/issue_221_validator_observability_endpoints.md

Drei Endpoints für den External Validator:
- GET  /api/_validator/format-metric
- POST /api/trips/{id}/alert-preview
- GET  /api/_validator/detector-thresholds

Keine Mocks — Tests laufen gegen echte Trip-Fixtures aus data/users/. Wo eine
spezifische Trip-Konfiguration im Repo nicht existiert (alert_rules, nur
report_config), legen wir den Test-Trip via fixture als echte JSON-Datei an
und räumen anschließend auf.

In der RED-Phase scheitert bereits der Router-Import — das ist erwartet und
beweist, dass die Funktion noch nicht existiert.
"""

from __future__ import annotations

import copy
import json
import os
import shutil
import time
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
    """FastAPI TestClient für den validator-Router (Modul existiert in RED nicht)."""
    from api.routers import validator  # RED: ImportError erwartet
    app = FastAPI()
    app.include_router(validator.router)
    return TestClient(app)


@pytest.fixture
def trip_with_alert_rules():
    """Test-Trip mit aktivierter Temperature-Delta-AlertRule.

    Wird als echte JSON-Datei unter data/users/test_issue_221/ angelegt
    und nach dem Test wieder entfernt. Kein Mock — der Loader liest sie
    auf demselben Pfad wie Production-Trips.
    """
    user_id = f"test_issue_221_{uuid.uuid4().hex[:8]}"
    trip_dir = Path("data/users") / user_id / "trips"
    trip_dir.mkdir(parents=True, exist_ok=True)
    trip_id = "trip-alert-rules"
    payload = {
        "id": trip_id,
        "name": "AlertRules Test Trip",
        "stages": [],
        "alert_rules": [
            {
                "id": "rule-1",
                "enabled": True,
                "kind": "delta",
                "metric": "temperature_change",
                "threshold": 5.0,
                "severity": "warning",
            }
        ],
    }
    (trip_dir / f"{trip_id}.json").write_text(json.dumps(payload))
    yield user_id, trip_id
    shutil.rmtree(Path("data/users") / user_id, ignore_errors=True)


@pytest.fixture
def trip_with_only_report_config():
    """Test-Trip mit ausschließlich report_config (Legacy-3-Slider-Pfad)."""
    user_id = f"test_issue_221_{uuid.uuid4().hex[:8]}"
    trip_dir = Path("data/users") / user_id / "trips"
    trip_dir.mkdir(parents=True, exist_ok=True)
    trip_id = "trip-report-only"
    payload = {
        "id": trip_id,
        "name": "Legacy Report-Config Trip",
        "stages": [],
        "report_config": {
            "alert_on_changes": True,
            "change_threshold_temp_c": 7.0,
            "change_threshold_wind_kmh": 22.0,
            "change_threshold_precip_mm": 12.0,
            "send_email": True,
        },
    }
    (trip_dir / f"{trip_id}.json").write_text(json.dumps(payload))
    yield user_id, trip_id
    shutil.rmtree(Path("data/users") / user_id, ignore_errors=True)


@pytest.fixture
def trip_with_report_config_alerts_off():
    """Trip mit alert_on_changes=False — Adversary-Finding (AC-11).

    Der Loader injiziert für solche Trips eine Default-Display-Config
    (build_default_display_config_for_profile), wodurch der Detector-Pfad
    auf ``from_display_config`` umspringt, obwohl der User-Intent in der
    rohen JSON ``from_trip_config`` ist. Genau diese Divergenz prüft AC-11.
    """
    user_id = f"test_issue_221_{uuid.uuid4().hex[:8]}"
    trip_dir = Path("data/users") / user_id / "trips"
    trip_dir.mkdir(parents=True, exist_ok=True)
    trip_id = "trip-alerts-off"
    payload = {
        "id": trip_id,
        "name": "Alerts Off Trip",
        "stages": [],
        "report_config": {
            "alert_on_changes": False,
            "change_threshold_temp_c": 7.0,
            "change_threshold_wind_kmh": 22.0,
            "change_threshold_precip_mm": 12.0,
            "send_email": True,
        },
    }
    (trip_dir / f"{trip_id}.json").write_text(json.dumps(payload))
    yield user_id, trip_id
    shutil.rmtree(Path("data/users") / user_id, ignore_errors=True)


# ---------------------------------------------------------------------------
# Endpoint #1: /api/_validator/format-metric (AC-1, AC-2)
# ---------------------------------------------------------------------------

class TestFormatMetricEndpoint:
    """AC-1, AC-2: Pure-Function-Wrapper um format_metric_value."""

    def test_ac1_meter_value_de_thousand_separator(self, client):
        """AC-1: unit=m, value=12240 → '12.240 m' (DE-Tausender-Trenner)."""
        resp = client.get(
            "/api/_validator/format-metric",
            params={"unit": "m", "value": 12240},
        )
        assert resp.status_code == 200, f"Body: {resp.text[:200]}"
        assert resp.json() == {"formatted": "12.240 m"}

    def test_ac2_percent_signed_rounds_to_integer(self, client):
        """AC-2: unit=%, value=33.5, signed=true → '+34 %' (kaufmännisch gerundet)."""
        resp = client.get(
            "/api/_validator/format-metric",
            params={"unit": "%", "value": 33.5, "signed": "true"},
        )
        assert resp.status_code == 200, f"Body: {resp.text[:200]}"
        assert resp.json() == {"formatted": "+34 %"}


# ---------------------------------------------------------------------------
# Endpoint #2: POST /api/trips/{id}/alert-preview (AC-4, AC-5, AC-6)
# ---------------------------------------------------------------------------

ALERT_BODY_VISIBILITY = {
    "changes": [
        {
            "metric": "visibility_min_m",
            "old_value": 12240,
            "new_value": 38440,
            "delta": 26200,
            "threshold": 1000,
            "severity": "moderate",
            "direction": "increase",
            "segment_id": "2",
        }
    ],
    "segment_times": [
        {"segment_id": "2", "start": "14:00", "end": "16:00"}
    ],
}


class TestAlertPreviewEndpoint:
    """AC-4, AC-5, AC-6: Alert-Mail-Render-Preview ohne Versand."""

    def test_ac4_visibility_change_renders_segment_line(self, client):
        """AC-4: Body mit Sichtweite-Change → Plain enthält erwartete Zeile."""
        resp = client.post(
            "/api/trips/gr221-mallorca/alert-preview",
            params={"user_id": "default"},
            json=ALERT_BODY_VISIBILITY,
        )
        assert resp.status_code == 200, f"Body: {resp.text[:200]}"
        data = resp.json()
        assert "email_html" in data and "email_plain" in data
        assert isinstance(data["email_html"], str) and isinstance(data["email_plain"], str)
        # Kanonischer Renderer: Werte müssen in email_plain enthalten sein
        assert "12.240" in data["email_plain"], \
            f"email_plain fehlt '12.240': {data['email_plain'][:300]}"
        assert "38.440" in data["email_plain"], \
            f"email_plain fehlt '38.440': {data['email_plain'][:300]}"
        assert "1.000" in data["email_plain"], \
            f"email_plain fehlt Schwelle '1.000': {data['email_plain'][:300]}"
        assert "12.240" in data["email_html"] and "38.440" in data["email_html"], \
            "HTML muss die Sichtweite-Werte enthalten"

    def test_ac5_no_side_effects_no_smtp_no_throttle_write(self, client):
        """AC-5: Endpoint ändert weder Throttle-File noch Snapshot — seiteneffektfrei."""
        throttle_file = Path("data/users/default/alert_throttle.json")
        before_mtime = throttle_file.stat().st_mtime if throttle_file.exists() else None

        for _ in range(3):
            resp = client.post(
                "/api/trips/gr221-mallorca/alert-preview",
                params={"user_id": "default"},
                json=ALERT_BODY_VISIBILITY,
            )
            assert resp.status_code == 200, f"Body: {resp.text[:200]}"

        after_mtime = throttle_file.stat().st_mtime if throttle_file.exists() else None
        assert before_mtime == after_mtime, \
            f"Throttle-File darf NICHT verändert werden (before={before_mtime}, after={after_mtime})"

    def test_ac6_foreign_user_trip_returns_404(self, client):
        """AC-6: Trip gehört User B, Request mit user_id=A → 404 (kein Datenleak)."""
        resp = client.post(
            "/api/trips/gr221-mallorca/alert-preview",
            params={"user_id": "fremder-user-existiert-nicht-12345"},
            json=ALERT_BODY_VISIBILITY,
        )
        assert resp.status_code == 404, f"Erwarte 404, bekam {resp.status_code}: {resp.text[:200]}"


# ---------------------------------------------------------------------------
# Endpoint #3: /api/_validator/detector-thresholds (AC-7, AC-8, AC-9)
# ---------------------------------------------------------------------------

class TestDetectorThresholdsEndpoint:
    """AC-7, AC-8, AC-9: Detector-Auswahlpfad sichtbar machen."""

    # Issue #946: test_ac7_trip_with_alert_rules_returns_from_alert_rules und
    # test_ac9_trip_with_only_report_config_returns_from_trip_config entfernt —
    # sie assertierten die alten Detector-Routing-Pfade (from_alert_rules über
    # trip.alert_rules bzw. from_trip_config), die #946 zugunsten von
    # metric_alert_levels als einziger Quelle abgeschafft hat.

    def test_ac8_trip_with_display_config_returns_from_display_config(self, client):
        """AC-8: Trip mit display_config (ohne alert_rules) → from_display_config."""
        resp = client.get(
            "/api/_validator/detector-thresholds",
            params={"trip": "gr221-mallorca", "user_id": "default"},
        )
        assert resp.status_code == 200, f"Body: {resp.text[:200]}"
        data = resp.json()
        assert data["config_source"] == "from_display_config", \
            f"Erwarte from_display_config, bekam {data['config_source']}"
        assert data["effective_detector"] == "from_display_config"
        assert isinstance(data["thresholds"], dict)

    def test_ac11_alerts_off_shows_divergence(
        self, client, trip_with_report_config_alerts_off,
    ):
        """AC-11: alert_on_changes=False → config_source vs effective_detector divergieren.

        Adversary-Finding: Der User hat report_config angelegt, aber Alerts
        bewusst deaktiviert. Der Loader injiziert dennoch eine Default-Display-Config,
        wodurch der Detector-Auswahlpfad auf ``from_display_config`` umspringt.
        ``config_source`` (User-Intent) und ``effective_detector`` (was wirklich
        passiert) divergieren — genau diese Sichtbarkeit liefert AC-11.
        """
        user_id, trip_id = trip_with_report_config_alerts_off
        resp = client.get(
            "/api/_validator/detector-thresholds",
            params={"trip": trip_id, "user_id": user_id},
        )
        assert resp.status_code == 200, f"Body: {resp.text[:200]}"
        data = resp.json()
        # User-Intent: hat report_config angelegt
        assert data["config_source"] == "from_trip_config"
        # Effektive Quelle: Loader injiziert Default-Display-Config; AlertRules disabled
        assert data["effective_detector"] == "from_display_config"
        # Thresholds zeigen Catalog-Defaults, nicht User-Werte (das ist genau die Divergenz)
        assert data["thresholds"].get("temp_min_c") != 7.0, \
            "thresholds zeigt Catalog-Default, nicht User-Wert (alert_on_changes=False)"

    def test_unknown_trip_returns_404(self, client):
        """Unbekannte Trip-ID → 404 (User-scoped Loader)."""
        resp = client.get(
            "/api/_validator/detector-thresholds",
            params={"trip": "nope-not-real-12345", "user_id": "default"},
        )
        assert resp.status_code == 404

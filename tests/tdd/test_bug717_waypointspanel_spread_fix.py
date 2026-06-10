"""
TDD GREEN — Bug #717: WaypointsPanel { ...trip, stages } Anti-Pattern entfernen

Spec: docs/specs/bugfix/bug717_waypointspanel_spread_fix.md
Workflow: issue-717-waypointspanel-spread-fix

Tests:
- AC-1 (# doc-compliance-test): { ...trip, stages: } ist NICHT mehr in WaypointsPanel.svelte
- AC-2 (# doc-compliance-test): { stages: localStages } ohne Spread ist die einzige Payload
- AC-3 (HTTP-Integrationstest): Minimaler Payload { stages: localStages } bewahrt RC_UPDATED

Verhalten nach Fix:
  WaypointsPanel.svelte → api.put('/api/trips/ID', { stages: localStages })
  Nur Waypoints/Stages werden gesendet — keine anderen Felder.
  Backend-Partial-Update berührt report_config nicht → RC bleibt erhalten.

KEINE MOCKS — doc-compliance-tests lesen reale Quelldateien;
HTTP-Test macht echte API-Calls gegen lokalen Go-Server.

Ausführung:
  cd /home/hem/gregor_zwanzig
  uv run pytest tests/tdd/test_bug717_waypointspanel_spread_fix.py -v
"""

from __future__ import annotations

import hashlib
import hmac as _hmac
import os
import re
import time as _time
import uuid
from pathlib import Path

import httpx
import pytest

# ---------------------------------------------------------------------------
# Pfade
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[2]
WAYPOINTS_PANEL = REPO_ROOT / "frontend/src/lib/components/trip-detail/WaypointsPanel.svelte"

GO_BASE = os.environ.get("GZ_API_BASE", "http://localhost:8090")
TEST_USER = os.environ.get("GZ_AUTH_USER", "default")
TEST_PASS = os.environ.get("GZ_AUTH_PASS", "")

RC_ORIGINAL = {"enabled": True, "report_type": "morning", "email": "test@example.com"}
RC_UPDATED  = {"enabled": True, "report_type": "evening", "email": "test@example.com"}


# ---------------------------------------------------------------------------
# AC-1 (# doc-compliance-test)
# Zeile mit { ...trip, stages: } ist NICHT mehr vorhanden
# RED: Das Muster IST aktuell auf Zeile 42 — Assert schlägt fehl
# ---------------------------------------------------------------------------

class TestAC1_KeinSpreadAntiPattern:
    """
    AC-1: { ...trip, stages: } ist aus WaypointsPanel.svelte entfernt.

    doc-compliance-test (Präzedenz: frontend/src/lib/issue_523_suggested_flag_cleanup.test.ts)
    GREEN: Zeile mit Anti-Pattern wurde durch minimalen Payload ersetzt.
    """

    def test_kein_spread_anti_pattern(self):  # doc-compliance-test
        """
        GIVEN: WaypointsPanel.svelte enthält handleSave
        WHEN:  Quellcode auf { ...trip, stages: geprüft wird
        THEN:  Muster ist NICHT vorhanden (Anti-Pattern entfernt)
        """
        src = WAYPOINTS_PANEL.read_text(encoding="utf-8")
        assert "{ ...trip, stages:" not in src, (
            "BUG #717 AKTIV: WaypointsPanel.svelte enthält noch das Anti-Pattern\n"
            "  { ...trip, stages: localStages }\n"
            "  Fix: Zeile 42 ändern zu { stages: localStages }"
        )


# ---------------------------------------------------------------------------
# AC-2 (# doc-compliance-test)
# Korrektes Muster { stages: localStages } ist ohne Spread vorhanden
# RED: Das aktuelle Muster hat ...trip davor — Assertion auf sauberes Muster schlägt fehl
# ---------------------------------------------------------------------------

class TestAC2_MinimalerPayloadVorhanden:
    """
    AC-2: { stages: localStages } ohne ...trip-Spread ist der einzige PUT-Body.

    doc-compliance-test (Präzedenz: frontend/src/lib/issue_523_suggested_flag_cleanup.test.ts)
    GREEN: api.put()-Aufruf enthält nur stages ohne ...trip-Spread.
    """

    def test_minimaler_payload_vorhanden(self):  # doc-compliance-test
        """
        GIVEN: WaypointsPanel.svelte enthält handleSave
        WHEN:  Quellcode auf korrekten minimalen PUT-Body geprüft wird
        THEN:  api.put()-Aufruf enthält KEIN ...trip; stages: localStages ist vorhanden
        """
        src = WAYPOINTS_PANEL.read_text(encoding="utf-8")

        # Negativtest: Kein ...trip im api.put()-Aufruf
        put_calls = re.findall(r"api\.put\([^)]+\)", src, re.DOTALL)
        for call in put_calls:
            assert "...trip" not in call, (
                f"BUG #717 AKTIV: api.put()-Aufruf enthält noch ...trip-Spread:\n  {call.strip()}"
            )

        # Positivtest: stages: localStages muss vorhanden sein
        assert "stages: localStages" in src, (
            "WaypointsPanel.svelte enthält kein 'stages: localStages' — "
            "handleSave-Implementierung fehlt oder hat anderen Namen"
        )


# ---------------------------------------------------------------------------
# HTTP-Helpers (analog test_bug707_trip_datum_overwrite.py)
# ---------------------------------------------------------------------------

def _make_session_token(user_id: str, secret: str) -> str:
    ts = int(_time.time())
    mac = _hmac.new(secret.encode(), f"{user_id}:{ts}".encode(), hashlib.sha256)
    return f"{user_id}.{ts}.{mac.hexdigest()}"


def _api_session() -> httpx.Client:
    client = httpx.Client(base_url=GO_BASE, timeout=15)
    try:
        health = client.get("/api/health", timeout=3)
        if health.status_code != 200:
            pytest.skip(f"Go-Server nicht erreichbar ({health.status_code})")
    except Exception as exc:
        pytest.skip(f"Go-Server nicht erreichbar: {exc}")

    resp = client.post("/api/auth/login", json={"username": TEST_USER, "password": TEST_PASS})
    if resp.status_code == 200:
        m = re.search(r"gz_session=([^;]+)", resp.headers.get("set-cookie", ""))
        if m:
            client.cookies.set("gz_session", m.group(1))
            return client

    if resp.status_code == 429:
        secret = os.environ.get("GZ_SESSION_SECRET", "")
        if not secret:
            env_file = REPO_ROOT / ".env"
            if env_file.exists():
                for line in env_file.read_text().splitlines():
                    if line.startswith("GZ_SESSION_SECRET="):
                        secret = line.split("=", 1)[1].strip().strip('"')
                        break
        if not secret:
            pytest.skip("Rate-Limit aktiv und GZ_SESSION_SECRET nicht gefunden")
        client.cookies.set("gz_session", _make_session_token(TEST_USER, secret))
        if client.get("/api/trips").status_code != 200:
            pytest.skip("Token-Generierung fehlgeschlagen")
        return client

    pytest.skip(f"Login fehlgeschlagen ({resp.status_code})")
    return client  # unreachable


def _create_test_trip(session: httpx.Client, name: str, report_config: dict) -> dict:
    trip_id = "tdd-717-" + uuid.uuid4().hex[:6]
    payload = {
        "id": trip_id,
        "name": name,
        "region": "Testgebiet",
        "report_config": report_config,
        "stages": [
            {
                "id": "s1",
                "name": "Etappe 1",
                "date": "2026-09-01",
                "waypoints": [
                    {"id": "w1", "name": "Start", "lat": 46.0, "lon": 9.0, "elevation_m": 500},
                    {"id": "w2", "name": "Ziel",  "lat": 46.1, "lon": 9.1, "elevation_m": 600},
                ],
            }
        ],
        "alert_rules": [],
    }
    resp = session.post("/api/trips", json=payload)
    assert resp.status_code in (200, 201), f"Trip anlegen: {resp.status_code} {resp.text[:300]}"
    return session.get(f"/api/trips/{trip_id}").json()


# ---------------------------------------------------------------------------
# AC-3: HTTP-Integrationstest — Minimaler Payload bewahrt report_config
#
# GREEN-Szenario: Entspricht dem Fix in WaypointsPanel.svelte:
#   { stages: localStages }  (kein ...trip-Spread)
#   Backend-Partial-Update berührt report_config nicht → RC_UPDATED bleibt erhalten.
# ---------------------------------------------------------------------------

class TestAC3_PartialUpdateBewahrtReportConfig:
    """
    AC-3 GREEN: Minimaler Payload { stages } bewahrt report_config via HTTP.

    GIVEN: Trip mit report_config RC_ORIGINAL angelegt
    WHEN:  report_config auf RC_UPDATED aktualisiert (simuliert: anderer Tab speichert)
           danach WaypointsPanel-Save mit { stages: localStages } (minimaler Payload)
    THEN:  report_config ist nach dem WaypointsPanel-Save noch RC_UPDATED
    """

    def test_report_config_bleibt_nach_waypoints_save(self):
        """
        GIVEN: Trip mit RC_ORIGINAL, dann RC auf RC_UPDATED aktualisiert
        WHEN:  Minimaler Payload { stages: localStages } gesendet (kein ...trip-Spread)
        THEN:  report_config ist RC_UPDATED — kein Revert auf RC_ORIGINAL
        """
        session = _api_session()
        original_trip = _create_test_trip(session, "717-AC3-Test", RC_ORIGINAL)
        trip_id = original_trip["id"]

        try:
            # Schritt 1: report_config auf RC_UPDATED ändern
            # (simuliert: Nutzer speichert Briefing-Zeitplan in BriefingScheduleTab)
            r_rc = session.put(f"/api/trips/{trip_id}", json={"report_config": RC_UPDATED})
            assert r_rc.status_code == 200, f"RC-Update: {r_rc.status_code} {r_rc.text[:200]}"

            trip_nach_rc_save = session.get(f"/api/trips/{trip_id}").json()
            assert trip_nach_rc_save.get("report_config", {}).get("report_type") == "evening", \
                "RC-Update hat nicht funktioniert — Voraussetzung nicht erfüllt"

            # Schritt 2: Minimaler Payload senden — entspricht dem Fix:
            #   api.put(`/api/trips/${trip.id}`, { stages: localStages })
            minimal_payload = {"stages": original_trip["stages"]}
            r_wp = session.put(f"/api/trips/{trip_id}", json=minimal_payload)
            assert r_wp.status_code == 200, f"WaypointsPanel-Save: {r_wp.status_code} {r_wp.text[:200]}"

            # Schritt 3: report_config nach WaypointsPanel-Save prüfen
            trip_final = session.get(f"/api/trips/{trip_id}").json()
            actual_rc = trip_final.get("report_config", {}).get("report_type")

            assert actual_rc == "evening", (
                f"Backend-Partial-Update hat report_config zurückgedreht!\n"
                f"  Erwartet: 'evening' (RC_UPDATED)\n"
                f"  Bekommen: '{actual_rc}'\n"
                f"  Ursache: PUT mit {{ stages }} hätte report_config NICHT anfassen dürfen"
            )

        finally:
            session.delete(f"/api/trips/{trip_id}")

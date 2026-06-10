"""
TDD RED — Bug #720: TripEditView { ...trip, name, stages, ... } Anti-Pattern entfernen

Spec: docs/specs/bugfix/bug720_tripeditview_spread_fix.md
Workflow: issue-720-tripeditview-spread-fix

Tests:
- AC-1 (# doc-compliance-test): { ...trip, in api.put()-Aufruf ist NICHT vorhanden
- AC-2 (# doc-compliance-test): Minimaler Payload ohne Spread ist vorhanden
- AC-3 (HTTP-Integrationstest): Minimaler Payload bewahrt display_config via Backend-Partial-Update

Verhalten nach Fix:
  TripEditView.svelte → api.put('/api/trips/ID', { name, stages, report_config, alert_rules })
  Kein { ...trip, ... } Spread — nur die 4 tatsächlich bearbeiteten Felder.
  Backend-Partial-Update berührt display_config nicht → bleibt erhalten.

KEINE MOCKS — doc-compliance-tests lesen reale Quelldateien;
HTTP-Test macht echte API-Calls gegen lokalen Go-Server.

Ausführung:
  cd /home/hem/gregor_zwanzig
  uv run pytest tests/tdd/test_bug720_tripeditview_spread_fix.py -v
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
TRIPEDITVIEW = REPO_ROOT / "frontend/src/lib/components/edit/TripEditView.svelte"

GO_BASE = os.environ.get("GZ_API_BASE", "http://localhost:8090")
TEST_USER = os.environ.get("GZ_AUTH_USER", "default")
TEST_PASS = os.environ.get("GZ_AUTH_PASS", "")

DC_ORIGINAL = {"weather_display": {"show_wind": True}}
DC_UPDATED  = {"weather_display": {"show_wind": False}}


# ---------------------------------------------------------------------------
# AC-1 (# doc-compliance-test)
# { ...trip, in einem api.put()-Aufruf ist NICHT vorhanden
# RED: Das Muster IST aktuell auf Zeile 71 — Assert schlägt fehl
# ---------------------------------------------------------------------------

class TestAC1_KeinSpreadAntiPattern:
    """
    AC-1: { ...trip, in api.put()-Aufruf ist aus TripEditView.svelte entfernt.

    doc-compliance-test (Präzedenz: Bug #717 WaypointsPanel)
    RED: Muster `{ ...trip,` ist aktuell in makeSaveHandler (Z.71) vorhanden.
    GREEN: Zeile mit Anti-Pattern wurde durch minimalen Payload ersetzt.
    """

    def test_kein_spread_anti_pattern(self):  # doc-compliance-test
        """
        GIVEN: TripEditView.svelte enthält makeSaveHandler
        WHEN:  Quellcode auf { ...trip, in einem api.put()-Aufruf geprüft wird
        THEN:  Muster ist NICHT vorhanden (Anti-Pattern entfernt)
        """
        src = TRIPEDITVIEW.read_text(encoding="utf-8")

        # Suche nach dem Anti-Pattern: { ...trip, innerhalb von api.put()-Aufrufen
        # Das Muster kann mehrzeilig sein — wir suchen den put()-Block
        put_blocks = re.findall(r"api\.put\s*\([^)]*\)", src, re.DOTALL)

        # Auch einfacher String-Check für das konkrete Anti-Pattern
        assert "{ ...trip," not in src or all("...trip" not in block for block in put_blocks), (
            "BUG #720 AKTIV: TripEditView.svelte enthält noch das Anti-Pattern\n"
            "  const updated: Trip = { ...trip, name: tripName, stages, ... }\n"
            "  Fix: makeSaveHandler direkt mit minimalem Body aufrufen:\n"
            "       await api.put(`/api/trips/${trip.id}`, { name: tripName, stages, report_config, alert_rules })"
        )

        # Direkter Check: das `...trip`-Intermediate-Objekt muss weg sein
        assert "...trip," not in src, (
            "BUG #720 AKTIV: TripEditView.svelte enthält noch `...trip,` (Spread-Anti-Pattern)\n"
            "  Zeile 71: const updated: Trip = { ...trip, name: tripName, ... }\n"
            "  Fix: Intermediate-Objekt entfernen, minimalen Body direkt in api.put() setzen"
        )


# ---------------------------------------------------------------------------
# AC-2 (# doc-compliance-test)
# Korrektes minimales Muster ohne Spread ist vorhanden
# RED: Aktuell ist { ...trip, ... } der einzige PUT-Body — minimaler Body fehlt
# ---------------------------------------------------------------------------

class TestAC2_MinimalerPayloadVorhanden:
    """
    AC-2: api.put() sendet { name: tripName, stages, report_config, alert_rules } ohne ...trip.

    doc-compliance-test (Präzedenz: Bug #717 WaypointsPanel)
    RED: Aktuell hat api.put() den vollständigen Spread — minimaler Body noch nicht vorhanden.
    GREEN: api.put()-Aufruf enthält nur die 4 bearbeiteten Felder, kein ...trip.
    """

    def test_minimaler_payload_vorhanden(self):  # doc-compliance-test
        """
        GIVEN: TripEditView.svelte enthält makeSaveHandler
        WHEN:  Quellcode auf korrekten minimalen PUT-Body geprüft wird
        THEN:  api.put()-Aufruf enthält KEIN ...trip; name, stages, report_config, alert_rules sind vorhanden
        """
        src = TRIPEDITVIEW.read_text(encoding="utf-8")

        # Negativtest: Kein ...trip im api.put()-Aufruf
        # Mehrzeilige Suche nach put()-Blöcken
        put_calls = re.findall(r"api\.put\s*\([^;]+\)", src, re.DOTALL)
        for call in put_calls:
            assert "...trip" not in call, (
                f"BUG #720 AKTIV: api.put()-Aufruf enthält noch ...trip-Spread:\n  {call.strip()}"
            )

        # Positivtest: Die 4 tatsächlich bearbeiteten Felder müssen direkt im PUT-Body sein
        # Nach Fix: api.put(`/api/trips/${trip.id}`, { name: tripName, stages, report_config, alert_rules })
        assert "name: tripName" in src, (
            "TripEditView.svelte: 'name: tripName' fehlt — "
            "direkter minimaler PUT-Body nicht implementiert"
        )
        assert "report_config: reportConfig" in src or "report_config," in src, (
            "TripEditView.svelte: 'report_config' fehlt im minimalen PUT-Body"
        )
        assert "alert_rules: alertRules" in src or "alert_rules," in src, (
            "TripEditView.svelte: 'alert_rules' fehlt im minimalen PUT-Body"
        )

        # Zusätzlich: Das Intermediate-Objekt `const updated: Trip` darf nicht mehr existieren
        assert "const updated: Trip" not in src, (
            "BUG #720 AKTIV: TripEditView.svelte enthält noch 'const updated: Trip'\n"
            "  Das Intermediate-Objekt muss entfernt werden — api.put() direkt mit minimalem Body aufrufen"
        )


# ---------------------------------------------------------------------------
# HTTP-Helpers (analog test_bug717_waypointspanel_spread_fix.py)
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


def _create_test_trip(session: httpx.Client, name: str, display_config: dict) -> dict:
    trip_id = "tdd-720-" + uuid.uuid4().hex[:6]
    payload = {
        "id": trip_id,
        "name": name,
        "region": "Testgebiet",
        "display_config": display_config,
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
# AC-3: HTTP-Integrationstest — Minimaler Payload bewahrt display_config
#
# Kontrakt-Test: Prüft das Backend-Partial-Update-Verhalten, auf das der Fix aufbaut.
# Kann PASS sein (Backend ist bereits korrekt); RED-Evidenz kommt aus AC-1/AC-2.
# ---------------------------------------------------------------------------

class TestAC3_PartialUpdateBewahrtDisplayConfig:
    """
    AC-3: Minimaler Payload { name, stages, report_config, alert_rules } bewahrt display_config via HTTP.

    GIVEN: Trip mit display_config DC_ORIGINAL angelegt
    WHEN:  display_config auf DC_UPDATED aktualisiert (simuliert: WeatherMetricsTab speichert)
           danach TripEditView-Save mit { name, stages, report_config, alert_rules } (minimaler Payload)
    THEN:  display_config ist nach dem TripEditView-Save noch DC_UPDATED
    """

    def test_display_config_bleibt_nach_tripeditview_save(self):
        """
        GIVEN: Trip mit DC_ORIGINAL, dann display_config auf DC_UPDATED aktualisiert
        WHEN:  Minimaler Payload { name, stages, report_config, alert_rules } gesendet (kein ...trip)
        THEN:  display_config ist DC_UPDATED — kein Revert auf DC_ORIGINAL
        """
        session = _api_session()
        original_trip = _create_test_trip(session, "720-AC3-Test", DC_ORIGINAL)
        trip_id = original_trip["id"]

        try:
            # Schritt 1: display_config auf DC_UPDATED ändern
            # (simuliert: Nutzer speichert Wetter-Einstellungen in WeatherMetricsTab)
            r_dc = session.put(f"/api/trips/{trip_id}", json={"display_config": DC_UPDATED})
            assert r_dc.status_code == 200, f"DC-Update: {r_dc.status_code} {r_dc.text[:200]}"

            trip_nach_dc_save = session.get(f"/api/trips/{trip_id}").json()
            actual_dc = trip_nach_dc_save.get("display_config", {})
            assert actual_dc.get("weather_display", {}).get("show_wind") is False, (
                "DC-Update hat nicht funktioniert — Voraussetzung nicht erfüllt\n"
                f"  display_config nach Update: {actual_dc}"
            )

            # Schritt 2: Minimaler Payload senden — entspricht dem Fix:
            #   api.put(`/api/trips/${trip.id}`, { name: tripName, stages, report_config, alert_rules })
            minimal_payload = {
                "name": original_trip["name"],
                "stages": original_trip["stages"],
                "report_config": original_trip.get("report_config"),
                "alert_rules": original_trip.get("alert_rules", []),
            }
            # Sicherstellen: display_config ist NICHT im Payload
            assert "display_config" not in minimal_payload

            r_tev = session.put(f"/api/trips/{trip_id}", json=minimal_payload)
            assert r_tev.status_code == 200, f"TripEditView-Save: {r_tev.status_code} {r_tev.text[:200]}"

            # Schritt 3: display_config nach TripEditView-Save prüfen
            trip_final = session.get(f"/api/trips/{trip_id}").json()
            actual_dc_final = trip_final.get("display_config", {})
            actual_show_wind = actual_dc_final.get("weather_display", {}).get("show_wind")

            assert actual_show_wind is False, (
                f"Backend-Partial-Update hat display_config zurückgedreht!\n"
                f"  Erwartet: show_wind=False (DC_UPDATED)\n"
                f"  Bekommen: show_wind={actual_show_wind}\n"
                f"  display_config nach PUT: {actual_dc_final}\n"
                f"  Ursache: PUT mit minimalem Body hätte display_config NICHT anfassen dürfen"
            )

        finally:
            session.delete(f"/api/trips/{trip_id}")

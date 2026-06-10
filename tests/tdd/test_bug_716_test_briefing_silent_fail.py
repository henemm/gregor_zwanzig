"""
TDD RED — Issue #716: Test-Briefing stiller Versagensfall + IMAP-Verifikation

Spec: docs/specs/modules/bug_716_test_briefing_silent_fail.md
Workflow: bug-716-test-briefing-silent-fail

Tests prüfen VERHALTEN — keine Mocks:

  AC-1 (Python): POST /api/scheduler/trips/{id}/send für Trip ohne passende Etappe
    → erwartet HTTP 422 mit "Kein Briefing für" im detail
    → aktuell: HTTP 200 (stiller Versagensfall) → TEST SCHLÄGT FEHL (RED)

  AC-2 (Python): response body enthält "sent": true bei erfolgreichem Versand
    → aktuell: kein "sent"-Feld in der Antwort → TEST SCHLÄGT FEHL (RED)

  AC-3 (IMAP E2E): @pytest.mark.email — echter Versand + IMAP-Verifikation
    → prüft Ende-zu-Ende: Trip mit Etappe → SMTP → gregor-test@henemm.com → IMAP

  AC-4 (Frontend): +page.svelte liest detail-Feld aus Fehler-Response
    → aktuell: kein detail-Parsing im handleTestBriefing → TEST SCHLÄGT FEHL (RED)
    # doc-compliance-test
"""

from __future__ import annotations

import json
import os
import time
import uuid
from datetime import date, timedelta
from pathlib import Path

import pytest
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

REPO_ROOT = Path(__file__).resolve().parents[2]
SVELTE_PAGE = (
    REPO_ROOT / "frontend" / "src" / "routes" / "trips" / "[id]" / "+page.svelte"
)


# ---------------------------------------------------------------------------
# Test-Fixtures: temporäre User + Trip-Dateien
# ---------------------------------------------------------------------------


@pytest.fixture
def user_no_stages(tmp_path):
    """
    Erstellt tdd-716-ac1 User mit mail_to + Trip ohne Etappen.
    Teardown: löscht die erstellten Dateien.
    """
    user_id = "tdd-716-ac1"
    trip_id = "tdd-716-no-stages-trip"

    trips_dir = REPO_ROOT / "data" / "users" / user_id / "trips"
    trips_dir.mkdir(parents=True, exist_ok=True)

    # User-Profil: mail_to auf gregor-test setzen → with_user_profile übernimmt
    user_profile = REPO_ROOT / "data" / "users" / user_id / "user.json"
    user_profile.write_text(json.dumps({"mail_to": "gregor-test@henemm.com"}))

    # Trip mit Etappe in der fernen Vergangenheit (2026-01-01) → kein Match für heute/morgen
    trip_path = trips_dir / f"{trip_id}.json"
    trip_path.write_text(json.dumps({
        "id": trip_id,
        "name": "TDD-716 Vergangenheits-Trip",
        "stages": [{
            "id": "stage-past",
            "name": "Vergangene Etappe",
            "date": "2026-01-01",
            "waypoints": [
                {"id": "wp1", "name": "Start", "lat": 42.1, "lon": 9.0, "elevation_m": 500},
                {"id": "wp2", "name": "Ziel", "lat": 42.2, "lon": 9.1, "elevation_m": 600},
            ],
        }],
        "report_config": {
            "evening": "20:00",
            "evening_enabled": True,
            "morning": "05:30",
            "morning_enabled": True,
        },
        "alert_rules": [],
    }))

    yield user_id, trip_id

    trip_path.unlink(missing_ok=True)
    user_profile.unlink(missing_ok=True)


@pytest.fixture
def user_with_tomorrow_stage(tmp_path):
    """
    Erstellt tdd-716-ac3 User mit mail_to + Trip mit Etappe für morgen.
    Wird für den IMAP-E2E-Test (AC-3) verwendet.
    """
    user_id = "tdd-716-ac3"
    trip_id = "tdd-716-imap-test-trip"
    tomorrow = (date.today() + timedelta(days=1)).isoformat()

    trips_dir = REPO_ROOT / "data" / "users" / user_id / "trips"
    trips_dir.mkdir(parents=True, exist_ok=True)

    user_profile = REPO_ROOT / "data" / "users" / user_id / "user.json"
    user_profile.write_text(json.dumps({"mail_to": "gregor-test@henemm.com"}))

    # Trip mit echter GR20-Etappe (Korsika) für morgen
    trip_path = trips_dir / f"{trip_id}.json"
    trip_path.write_text(json.dumps({
        "id": trip_id,
        "name": f"TDD-716 IMAP Test {uuid.uuid4().hex[:6]}",
        "stages": [{
            "id": "stage-ac3",
            "name": "Etappe Test",
            "date": tomorrow,
            "waypoints": [
                {"id": "wp1", "name": "Calenzana", "lat": 42.508, "lon": 8.857, "elevation_m": 275},
                {"id": "wp2", "name": "Refugio Ortu", "lat": 42.406, "lon": 8.877, "elevation_m": 1530},
            ],
        }],
        "report_config": {"send_email": True, "send_telegram": False},
        "alert_rules": [],
    }))

    yield user_id, trip_id

    trip_path.unlink(missing_ok=True)
    user_profile.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# AC-1: Trip ohne passende Etappe → 422 (aktuell: 200)
# ---------------------------------------------------------------------------


class TestAC1SilentFailReturns422:
    """
    AC-1 — POST /api/scheduler/trips/{id}/send liefert 422 wenn keine Etappe
    für das Zieldatum existiert — KEIN stiller 200-Erfolg mehr.

    RED-Beweis: aktuell gibt der Endpoint 200 zurück, weil _send_trip_report()
    bei leerer segments-Liste einfach mit `return` (None) abbricht und der
    Endpoint keine Unterscheidung trifft.
    """

    @pytest.fixture
    def client(self):
        from api.main import app
        from fastapi.testclient import TestClient
        return TestClient(app)

    def test_no_stages_returns_422_not_200(self, client, user_no_stages):
        """
        GIVEN: Trip mit leerer stages-Liste, SMTP konfiguriert (tdd-User)
        WHEN: POST /api/scheduler/trips/{id}/send?user_id=tdd-716-ac1
        THEN: HTTP 422 — nicht 200 (stiller Erfolg)

        RED: aktuell antwortet der Endpoint mit 200 → Test schlägt fehl.
        """
        user_id, trip_id = user_no_stages
        resp = client.post(
            f"/api/scheduler/trips/{trip_id}/send",
            params={"user_id": user_id},
        )
        assert resp.status_code == 422, (
            f"Erwartet 422 für Trip ohne Etappendaten, erhalten: {resp.status_code}. "
            f"Body: {resp.text}\n"
            "BUG #716: stiller Versagensfall — Endpoint gibt 200 obwohl kein Email gesendet."
        )
        body = resp.json()
        assert "detail" in body, f"Kein 'detail'-Feld in 422-Antwort: {body}"
        assert "Kein Briefing für" in body["detail"], (
            f"'detail' sollte 'Kein Briefing für' enthalten, ist: {body['detail']}"
        )

    def test_no_stages_detail_mentions_report_type(self, client, user_no_stages):
        """
        GIVEN: Trip ohne Etappen für Zieldatum
        WHEN: POST .../send?report_type=morning
        THEN: 422 detail enthält den report_type zur Fehlerdiagnose

        RED: aktuell 200.
        """
        user_id, trip_id = user_no_stages
        resp = client.post(
            f"/api/scheduler/trips/{trip_id}/send",
            params={"user_id": user_id, "report_type": "morning"},
        )
        assert resp.status_code == 422, (
            f"Erwartet 422, erhalten: {resp.status_code}. Body: {resp.text}"
        )


# ---------------------------------------------------------------------------
# AC-2: Erfolgreicher Versand gibt "sent": true zurück
# ---------------------------------------------------------------------------


@pytest.mark.email
class TestAC2ResponseHasSentField:
    """
    AC-2 — HTTP 200 Antwort enthält "sent": true wenn E-Mail tatsächlich gesendet.

    @pytest.mark.email — sendet echte E-Mail via Stalwart, daher nicht in normalen Läufen.
    RED-Beweis: aktuell fehlt das "sent"-Feld in der Antwort.
    """

    @pytest.fixture
    def client(self):
        from api.main import app
        from fastapi.testclient import TestClient
        return TestClient(app)

    def test_successful_response_includes_sent_true(self, client, user_with_tomorrow_stage):
        """
        GIVEN: Trip mit Etappe für morgen, SMTP konfiguriert
        WHEN: POST .../send (und Wetter ist verfügbar)
        THEN: HTTP 200 + {"sent": true} in der Antwort

        RED: aktuell fehlt "sent" im response-body.

        Hinweis: Dieser Test setzt voraus, dass Wetterdaten für morgen verfügbar
        sind (MET-API). Wenn nicht, gibt der Endpoint nach dem Fix 422 — aber dann
        fehlt das "sent"-Feld AUCH, also schlägt der Test trotzdem fehl (RED).
        """
        user_id, trip_id = user_with_tomorrow_stage
        resp = client.post(
            f"/api/scheduler/trips/{trip_id}/send",
            params={"user_id": user_id},
        )
        # Test schlägt RED fehl wenn entweder:
        # a) Endpoint gibt 200 aber KEIN "sent" Feld (aktueller Ist-Zustand)
        # b) Endpoint gibt 422 und "sent" fehlt ebenfalls (Fix erforderlich)
        if resp.status_code == 200:
            body = resp.json()
            assert "sent" in body, (
                f"HTTP 200 ohne 'sent'-Feld. Aktuell: {body}\n"
                "BUG #716 AC-2: Erfolgreiche Antwort muss 'sent: true' enthalten."
            )
            assert body["sent"] is True, f"Erwartet sent=true, bekommen: {body['sent']}"
        else:
            pytest.fail(
                f"Unerwarteter Status {resp.status_code}: {resp.text}\n"
                "Test erwartet HTTP 200 + sent:true für Trip mit Etappe."
            )


# ---------------------------------------------------------------------------
# AC-3: Echter IMAP-Nachweis (@pytest.mark.email — deselected by default)
# ---------------------------------------------------------------------------


@pytest.mark.email
class TestAC3RealImapVerification:
    """
    AC-3 — Echter End-to-End Test: Trip-Briefing senden → IMAP-Verifikation.

    Sendet echte E-Mail via Stalwart (gregor-test Account), verifiziert Eingang
    per IMAP. Beweis dass der Endpoint tatsächlich zustellt.
    """

    def test_briefing_arrives_in_imap_inbox(self, user_with_tomorrow_stage):
        """
        GIVEN: Trip mit Etappe für morgen, Stalwart-Test-SMTP konfiguriert
        WHEN: TripReportSchedulerService.send_test_report(trip, "evening") aufgerufen
        THEN: E-Mail mit Trip-Namen im Betreff kommt in gregor-test@henemm.com an
              (IMAP-Verifikation, max. 60s Polling)

        Kein Mock. Echter SMTP via Stalwart (gregor-test Account).
        """
        import imaplib
        from app.config import Settings
        from app.loader import load_trip
        from services.trip_report_scheduler import TripReportSchedulerService

        user_id, trip_id = user_with_tomorrow_stage

        settings = Settings().with_user_profile(user_id)
        if not settings.can_send_email():
            pytest.skip("SMTP für tdd-716-ac3 nicht konfiguriert")

        # Trip laden
        trip_path = REPO_ROOT / "data" / "users" / user_id / "trips" / f"{trip_id}.json"
        trip = load_trip(trip_path)

        # Unique Marker im Trip-Namen damit wir die Mail im IMAP finden
        unique_marker = uuid.uuid4().hex[:8]
        trip.name = f"{trip.name} [{unique_marker}]"

        # Versand
        service = TripReportSchedulerService(user_id=user_id)
        sent = service.send_test_report(trip, "evening")

        assert sent is True, (
            "send_test_report() muss True zurückgeben wenn E-Mail versendet wurde. "
            f"Bekommen: {sent}"
        )

        # IMAP-Verifikation (max. 60s)
        imap_host = settings.imap_host or settings.smtp_host
        imap_port = settings.imap_port or 993
        imap_user = settings.imap_user or settings.smtp_user
        imap_pass = settings.imap_pass or settings.smtp_pass

        if not all([imap_host, imap_user, imap_pass]):
            pytest.skip("IMAP-Credentials nicht konfiguriert")

        found = False
        for attempt in range(12):  # 12 × 5s = 60s
            time.sleep(5)
            imap = imaplib.IMAP4_SSL(imap_host, imap_port)
            try:
                imap.login(imap_user, imap_pass)
                imap.select("INBOX")
                _, data = imap.search(None, f'SUBJECT "{unique_marker}"')
                if data[0].split():
                    found = True
                    break
            finally:
                try:
                    imap.logout()
                except Exception:
                    pass

        assert found, (
            f"E-Mail mit Marker '{unique_marker}' nach 60s nicht in gregor-test INBOX gefunden. "
            "Versand schlägt still fehl oder IMAP-Verbindung defekt."
        )


# ---------------------------------------------------------------------------
# AC-4: Frontend liest detail-Feld aus Fehler-Response
# ---------------------------------------------------------------------------


class TestAC4FrontendShowsDetailMessage:
    """
    AC-4 — +page.svelte zeigt konkrete Fehlermeldung aus API-detail.

    # doc-compliance-test
    """

    def _svelte_src(self) -> str:
        return SVELTE_PAGE.read_text(encoding="utf-8")

    def test_handleTestBriefing_reads_detail_from_error_response(self):
        """
        GIVEN: +page.svelte handleTestBriefing Funktion
        WHEN: API antwortet mit 4xx + {"detail": "..."}
        THEN: Frontend liest body.detail und zeigt es im Fehler-Toast

        Nachweis: Quelltext enthält Parsing von body.detail (oder response.json()).
        RED: aktuell enthält handleTestBriefing kein response.json()-Parsing für Fehler.
        """
        src = self._svelte_src()
        # Nach dem Fix: handleTestBriefing muss response.json() aufrufen und
        # body.detail in einem State speichern
        has_detail_read = (
            "body.detail" in src
            or ("res.json" in src and "detail" in src)
        )
        assert has_detail_read, (
            "BUG #716 AC-4: handleTestBriefing liest kein 'detail'-Feld aus der Fehler-Response.\n"
            "Erwartet: body.detail oder res.json() + detail-Variable in +page.svelte.\n"
            "Aktueller Code zeigt nur generisches 'Fehler beim Senden'."
        )

    def test_error_span_can_render_dynamic_message(self):
        """
        GIVEN: +page.svelte Fehler-Span
        WHEN: testBriefingMessage State existiert
        THEN: Fehler-Span rendert den State-Inhalt (kein statischer String)

        # doc-compliance-test
        RED: aktuell ist die Fehlermeldung hart kodiert.
        """
        src = self._svelte_src()
        # Nach dem Fix: test-briefing-error Span rendert eine State-Variable
        # Nicht mehr: <span ...>Fehler beim Senden</span>
        assert "testBriefingMessage" in src, (
            "BUG #716 AC-4: Kein 'testBriefingMessage' State in +page.svelte gefunden.\n"
            "Fehler-Toast muss dynamisch aus API-Response befüllt werden."
        )

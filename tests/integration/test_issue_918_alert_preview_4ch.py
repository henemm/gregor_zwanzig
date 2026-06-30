"""TDD-RED: Issue #918 — Alert-Vorschau alle vier Kanäle (Slice 3 von #914).

Spec: docs/specs/modules/issue_918_alert_preview_4ch.md
ADR: ADR-0011 (kein zweiter Renderer im Frontend)

Kein Mock. Tests laufen gegen echten FastAPI-Router + Trip-Fixture
data/users/default/trips/gr221-mallorca.json.

In der RED-Phase schlägt jeder Test fehl, weil:
- Der Endpunkt noch `{html, plain}` zurückgibt statt `{subject, email_html, ...}`.
- Die Renderer-Ausgabe noch den alten TripReportFormatter nutzt.

Scope: nur Backend (AC-1..AC-5). AC-6 (Frontend) = Playwright gegen Staging,
läuft im E2E-Schritt nach Push.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


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

ALERT_BODY_WIND = {
    "changes": [
        {
            "metric": "gust_max_kmh",
            "old_value": 25.0,
            "new_value": 72.0,
            "delta": 47.0,
            "threshold": 60.0,
            "severity": "major",
            "direction": "increase",
            "segment_id": "1",
        }
    ],
    "segment_times": [
        {"segment_id": "1", "start": "08:00", "end": "12:00"}
    ],
}


@pytest.fixture
def client():
    from api.routers import validator
    app = FastAPI()
    app.include_router(validator.router)
    return TestClient(app)


class TestAC1_FourChannelFields:
    """AC-1: Antwort enthält alle 5 Felder subject/email_html/email_plain/telegram/sms."""

    def test_response_contains_all_four_channel_fields(self, client):
        resp = client.post(
            "/api/trips/gr221-mallorca/alert-preview",
            params={"user_id": "default"},
            json=ALERT_BODY_WIND,
        )
        assert resp.status_code == 200, f"Body: {resp.text[:200]}"
        data = resp.json()
        for field in ("subject", "email_html", "email_plain", "telegram", "sms"):
            assert field in data, f"Feld '{field}' fehlt in der Antwort; Keys: {list(data)}"
            assert isinstance(data[field], str), f"'{field}' muss ein String sein"
            assert data[field], f"'{field}' darf nicht leer sein"

    def test_old_html_plain_shape_no_longer_sole_response(self, client):
        """Kontrakt-Test: {html, plain} allein ist nicht mehr die vollständige Antwort."""
        resp = client.post(
            "/api/trips/gr221-mallorca/alert-preview",
            params={"user_id": "default"},
            json=ALERT_BODY_WIND,
        )
        assert resp.status_code == 200
        data = resp.json()
        # Neuer Vertrag: subject MUSS vorhanden sein
        assert "subject" in data, (
            "Endpunkt gibt noch altes {html,plain}-Format zurück. "
            f"Keys: {list(data)}"
        )


class TestAC2_CanonicalRenderer:
    """AC-2: Texte stammen nachweislich aus dem kanonischen Slice-2-Renderer."""

    def test_subject_starts_with_trip_bracket(self, client):
        """render_subject erzeugt '[<trip_short>] km...' — altes Format tut das nicht."""
        resp = client.post(
            "/api/trips/gr221-mallorca/alert-preview",
            params={"user_id": "default"},
            json=ALERT_BODY_WIND,
        )
        assert resp.status_code == 200
        subject = resp.json().get("subject", "")
        assert subject.startswith("["), (
            f"Betreff muss mit '[<trip_short>]' beginnen (kanonischer Renderer). "
            f"Aktuell: {subject!r}"
        )

    def test_email_html_is_html_document(self, client):
        """render_email liefert vollständiges HTML-Dokument."""
        resp = client.post(
            "/api/trips/gr221-mallorca/alert-preview",
            params={"user_id": "default"},
            json=ALERT_BODY_WIND,
        )
        assert resp.status_code == 200
        html = resp.json().get("email_html", "")
        assert "<html>" in html.lower(), (
            f"email_html muss ein HTML-Dokument sein. Got: {html[:120]!r}"
        )

    def test_sms_is_ascii_max_140_chars(self, client):
        """render_sms erzeugt reines ASCII ≤140 Zeichen."""
        resp = client.post(
            "/api/trips/gr221-mallorca/alert-preview",
            params={"user_id": "default"},
            json=ALERT_BODY_WIND,
        )
        assert resp.status_code == 200
        sms = resp.json().get("sms", "")
        assert len(sms) <= 140, f"SMS zu lang: {len(sms)} Zeichen"
        try:
            sms.encode("ascii")
        except UnicodeEncodeError as e:
            pytest.fail(f"SMS enthält Nicht-ASCII-Zeichen: {e}")

    def test_telegram_is_non_empty_string(self, client):
        """render_telegram liefert einen nicht-leeren String."""
        resp = client.post(
            "/api/trips/gr221-mallorca/alert-preview",
            params={"user_id": "default"},
            json=ALERT_BODY_WIND,
        )
        assert resp.status_code == 200
        telegram = resp.json().get("telegram", "")
        assert telegram, "telegram darf nicht leer sein"


class TestAC3_VisibilityValues:
    """AC-3: Sichtweite-Change liefert korrekte Werte in email_plain + email_html."""

    def test_email_plain_contains_formatted_visibility_values(self, client):
        """Plain-Text muss die kanonischen Rendering-Werte enthalten."""
        resp = client.post(
            "/api/trips/gr221-mallorca/alert-preview",
            params={"user_id": "default"},
            json=ALERT_BODY_VISIBILITY,
        )
        assert resp.status_code == 200, f"Body: {resp.text[:200]}"
        plain = resp.json().get("email_plain", "")
        # Kanonischer Renderer: Werte mit Tausenderpunkt (12.240 m, 38.440 m)
        assert "12.240" in plain, f"email_plain fehlt '12.240': {plain[:300]}"
        assert "38.440" in plain, f"email_plain fehlt '38.440': {plain[:300]}"
        # Schwelle 1.000 m
        assert "1.000" in plain, f"email_plain fehlt Schwelle '1.000': {plain[:300]}"

    def test_email_html_contains_formatted_visibility_values(self, client):
        """HTML-Version muss dieselben formatierten Werte enthalten."""
        resp = client.post(
            "/api/trips/gr221-mallorca/alert-preview",
            params={"user_id": "default"},
            json=ALERT_BODY_VISIBILITY,
        )
        assert resp.status_code == 200
        html = resp.json().get("email_html", "")
        assert "12.240" in html, f"email_html fehlt '12.240': {html[:300]}"
        assert "38.440" in html, f"email_html fehlt '38.440': {html[:300]}"


class TestAC4_SideEffectFree:
    """AC-4: Endpunkt ist strikt seiteneffektfrei (kein SMTP, kein Throttle-Write)."""

    def test_no_throttle_file_written_after_three_calls(self, client):
        throttle_file = Path("data/users/default/alert_throttle.json")
        before_mtime = throttle_file.stat().st_mtime if throttle_file.exists() else None

        for _ in range(3):
            resp = client.post(
                "/api/trips/gr221-mallorca/alert-preview",
                params={"user_id": "default"},
                json=ALERT_BODY_VISIBILITY,
            )
            assert resp.status_code == 200

        after_mtime = throttle_file.stat().st_mtime if throttle_file.exists() else None
        assert before_mtime == after_mtime, (
            f"Throttle-File darf NICHT verändert werden "
            f"(before={before_mtime}, after={after_mtime})"
        )


class TestAC5_MandantenTrennung:
    """AC-5: Fremder User → 404, kein Datenleck."""

    def test_foreign_user_returns_404(self, client):
        resp = client.post(
            "/api/trips/gr221-mallorca/alert-preview",
            params={"user_id": "fremder-user-918-test"},
            json=ALERT_BODY_VISIBILITY,
        )
        assert resp.status_code == 404, (
            f"Fremder User muss 404 erhalten, bekam {resp.status_code}: "
            f"{resp.text[:200]}"
        )

    def test_foreign_user_response_contains_no_renderer_data(self, client):
        """404-Antwort darf keine gerenderten Texte enthalten."""
        resp = client.post(
            "/api/trips/gr221-mallorca/alert-preview",
            params={"user_id": "fremder-user-918-test"},
            json=ALERT_BODY_VISIBILITY,
        )
        body = resp.text
        for field in ("subject", "email_html", "telegram", "sms"):
            assert f'"{field}"' not in body, (
                f"404-Antwort enthält Feld '{field}' — mögliches Datenleck"
            )

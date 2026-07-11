"""TDD: Epic #140 — Preview-Endpoints für Email + SMS (Option C Hybrid).

Spec: docs/specs/modules/epic_140_output_vorschau.md
Epic: #140

Keine Mocks. Echte Trip-Fixtures aus data/users/default. Wetter-Provider-Calls
werden im Test toleriert (HTTP 200 bei Erfolg, HTTP 503 bei API-Fehler — beides OK).
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Issue #1133: die gesamte Datei liest das echte, committete Trip-Fixture
# data/users/default/trips/gr221-mallorca.json über PreviewService (echter
# get_trips_dir()-Pfad) — bewusstes Opt-out aus der autouse-Isolation für
# das gesamte Modul statt pro Test (Datei-Docstring: "Echte Trip-Fixtures aus
# data/users/default").
pytestmark = pytest.mark.real_data_root


@pytest.fixture
def client():
    """Test-App mit dem Preview-Router."""
    from api.routers import preview
    app = FastAPI()
    app.include_router(preview.router)
    return TestClient(app)


@pytest.fixture
def service():
    """PreviewService mit Default-Settings (für direkte Unit-Tests)."""
    from src.app.config import Settings
    from src.services.preview_service import PreviewService
    return PreviewService(Settings())


# ---------- T1: PreviewService-Logik (ohne Wetter-Call) -------------


class TestT1PreviewService:
    """Unit-Tests für PreviewService-Hilfsfunktionen."""

    def test_load_trip_existing_user_returns_trip(self, service):
        """Existierender Trip wird geladen."""
        trip = service._load_trip("gr221-mallorca", user_id="default")
        assert trip is not None
        assert trip.id == "gr221-mallorca"

    def test_load_trip_unknown_id_raises(self, service):
        """Unbekannte Trip-ID → FileNotFoundError oder None."""
        with pytest.raises((FileNotFoundError, KeyError, ValueError)):
            service._load_trip("nope-not-real-12345", user_id="default")

    def test_resolve_target_date_returns_first_future_stage(self, service):
        """Wenn kein Datum gegeben, liefert _resolve_target_date das nächste Stage-Datum."""
        trip = service._load_trip("gr221-mallorca", user_id="default")
        target = service._resolve_target_date(trip, given_date=None)
        # Muss ein ISO-Datum-String sein oder ein date-Objekt
        assert target is not None


# ---------- T2: Endpoint /api/preview/{trip_id}/email --------------


class TestT2EmailEndpoint:
    """AC-1, AC-2, AC-3: Email-Preview-Endpoint."""

    def test_email_endpoint_returns_html_or_503(self, client):
        """AC-1: Existierender Trip → HTML zurück (200) ODER 503 bei Wetter-API-Fehler.

        Bei 200: muss text/html sein und den Trip-Namen enthalten.
        """
        resp = client.get(
            "/api/preview/gr221-mallorca/email",
            params={"type": "morning", "user_id": "default"},
        )
        # Wetter-API kann ausfallen — beide Status akzeptabel
        assert resp.status_code in (200, 503), \
            f"Erwarte 200 oder 503, bekam {resp.status_code}: {resp.text[:200]}"
        if resp.status_code == 200:
            assert "text/html" in resp.headers.get("content-type", "").lower()
            assert "GR221" in resp.text or "Mallorca" in resp.text, \
                "HTML muss Trip-Namen enthalten"

    def test_email_endpoint_unknown_trip_returns_404(self, client):
        """AC-2: Unbekannter Trip → 404."""
        resp = client.get(
            "/api/preview/nope-not-real-12345/email",
            params={"type": "morning", "user_id": "default"},
        )
        assert resp.status_code == 404, \
            f"Erwarte 404 für unbekannten Trip, bekam {resp.status_code}"

    def test_email_endpoint_invalid_type_returns_422_or_400(self, client):
        """AC-1: Ungültiger Report-Type → 422 oder 400."""
        resp = client.get(
            "/api/preview/gr221-mallorca/email",
            params={"type": "wrong-type", "user_id": "default"},
        )
        assert resp.status_code in (400, 422), \
            f"Erwarte 400/422 bei ungültigem type, bekam {resp.status_code}"


# ---------- T3: Endpoint /api/preview/{trip_id}/sms ----------------


class TestT3SmsEndpoint:
    """AC-4: SMS-Preview-Endpoint."""

    def test_sms_endpoint_returns_json_or_503(self, client):
        """AC-4: SMS-Endpoint liefert JSON mit subject, token_line, char_count."""
        resp = client.get(
            "/api/preview/gr221-mallorca/sms",
            params={"type": "morning", "user_id": "default"},
        )
        assert resp.status_code in (200, 503), \
            f"Erwarte 200 oder 503, bekam {resp.status_code}: {resp.text[:200]}"
        if resp.status_code == 200:
            data = resp.json()
            assert "subject" in data
            assert "token_line" in data
            assert "char_count" in data
            assert isinstance(data["token_line"], str)
            assert isinstance(data["char_count"], int)

    def test_sms_token_line_within_160_chars(self, client):
        """AC-4: token_line muss <= 160 Zeichen sein (GSM-7-Limit)."""
        resp = client.get(
            "/api/preview/gr221-mallorca/sms",
            params={"type": "morning", "user_id": "default"},
        )
        if resp.status_code == 200:
            data = resp.json()
            assert len(data["token_line"]) <= 160, \
                f"Token-Zeile darf max 160 Zeichen sein, war {len(data['token_line'])}: {data['token_line']!r}"
            assert data["char_count"] == len(data["token_line"]), \
                "char_count muss len(token_line) entsprechen"

    def test_sms_endpoint_unknown_trip_returns_404(self, client):
        """AC-2 analog für SMS."""
        resp = client.get(
            "/api/preview/nope-not-real-12345/sms",
            params={"type": "morning", "user_id": "default"},
        )
        assert resp.status_code == 404


# ---------- T4: PreviewService-Import + Strukturtests --------------


class TestT4Structure:
    """Sicherstellen dass Module + Klassen existieren."""

    def test_preview_service_module_importable(self):
        from src.services import preview_service
        assert hasattr(preview_service, "PreviewService")

    def test_preview_router_module_importable(self):
        from api.routers import preview
        assert hasattr(preview, "router")

    def test_preview_service_has_two_render_methods(self):
        from src.services.preview_service import PreviewService
        assert hasattr(PreviewService, "render_email_preview")
        assert hasattr(PreviewService, "render_sms_preview")


# ---------- T5: Issue #188 — SMS-Token-Pipeline ----------------------


class TestT5SmsTokenPipeline:
    """Issue #188 — SMS-Vorschau muss echtes Spec-Format liefern.

    Spec: docs/specs/modules/issue_188_sms_preview_token_pipeline.md

    Vor #188: render_sms_preview() gibt email_subject[:160] zurück.
    Nach #188: render_sms_preview() gibt 'StageName: N8 D24 ...' zurück.

    Wetter-API-Ausfälle → pytest.skip (wie im Rest dieser Datei).
    """

    def test_ac1_token_line_not_email_subject_format(self, client):
        """AC-1/AC-5: token_line darf nicht im Email-Subject-Format sein.

        Altes Verhalten: token_line = '[GR221 Mallorca] ...' (Subject-Format)
        Neues Verhalten: token_line = 'Tag 1: N8 D24 ...' (Spec-Format)
        """
        resp = client.get(
            "/api/preview/gr221-mallorca/sms",
            params={"type": "morning", "user_id": "default"},
        )
        assert resp.status_code in (200, 503), \
            f"Erwarte 200 oder 503, bekam {resp.status_code}: {resp.text[:300]}"
        if resp.status_code == 200:
            data = resp.json()
            token_line = data["token_line"]
            assert not token_line.startswith("["), (
                f"token_line darf NICHT im Email-Subject-Format beginnen (mit '['), "
                f"war: {token_line!r}"
            )

    def test_ac1_token_line_contains_stage_colon_prefix(self, client):
        """AC-1: token_line enthält 'StageName: ' gefolgt von Forecast-Token.

        Spec §3.1: Header ist '{Name}: '. Danach folgt min. ein Forecast-Token
        (N, D, R, PR, W, G, TH:, TH+:).
        """
        resp = client.get(
            "/api/preview/gr221-mallorca/sms",
            params={"type": "morning", "user_id": "default"},
        )
        assert resp.status_code in (200, 503)
        if resp.status_code == 200:
            data = resp.json()
            token_line = data["token_line"]
            assert ": " in token_line, (
                f"token_line muss 'Name: '-Prefix enthalten (sms_format.md §3.1), "
                f"war: {token_line!r}"
            )
            after_prefix = token_line.split(": ", 1)[1] if ": " in token_line else ""
            has_forecast = any(
                after_prefix.startswith(tok)
                for tok in ("N", "D", "R", "PR", "W", "G", "TH", "C")
            )
            assert has_forecast, (
                f"Nach dem Stage-Prefix muss ein Forecast-Token stehen "
                f"(N/D/R/PR/W/G/TH/C), Rest war: {after_prefix!r}"
            )

    def test_ac2_token_line_max_160_chars_via_service(self, service):
        """AC-2: render_sms_preview liefert token_line mit ≤ 160 Zeichen."""
        try:
            _, token_line = service.render_sms_preview(
                "gr221-mallorca", user_id="default", report_type="morning",
            )
        except RuntimeError:
            pytest.skip("Wetter-API nicht erreichbar")
        assert len(token_line) <= 160, (
            f"token_line muss ≤ 160 Zeichen sein (sms_format.md §1), "
            f"war {len(token_line)} Zeichen: {token_line!r}"
        )

    def test_ac4_deterministic_two_calls(self, service):
        """AC-4: Gleiche Eingaben → bit-identische token_line."""
        try:
            _, token_line_1 = service.render_sms_preview(
                "gr221-mallorca", user_id="default", report_type="morning",
            )
            _, token_line_2 = service.render_sms_preview(
                "gr221-mallorca", user_id="default", report_type="morning",
            )
        except RuntimeError:
            pytest.skip("Wetter-API nicht erreichbar")
        assert token_line_1 == token_line_2, (
            "Determinismus verletzt: zwei identische render_sms_preview-Aufrufe "
            f"lieferten verschiedene Ergebnisse:\n  {token_line_1!r}\n  {token_line_2!r}"
        )

    def test_ac5_subject_differs_from_token_line(self, service):
        """AC-5: subject ≠ token_line (altes Verhalten: beide waren identisch).

        Alte Impl: subject = token_line[:160] — immer gleich.
        Neue Impl: subject = Email-Subject, token_line = Spec-Token-Zeile.
        """
        try:
            subject, token_line = service.render_sms_preview(
                "gr221-mallorca", user_id="default", report_type="morning",
            )
        except RuntimeError:
            pytest.skip("Wetter-API nicht erreichbar")
        assert subject != token_line, (
            "subject und token_line dürfen NICHT identisch sein — "
            "token_line muss das Spec-Token-Format sein, subject der Email-Betreff.\n"
            f"  subject={subject!r}\n  token_line={token_line!r}"
        )

    def test_ac5_char_count_equals_token_line_length(self, client):
        """AC-5: char_count im JSON muss exakt len(token_line) entsprechen."""
        resp = client.get(
            "/api/preview/gr221-mallorca/sms",
            params={"type": "morning", "user_id": "default"},
        )
        assert resp.status_code in (200, 503)
        if resp.status_code == 200:
            data = resp.json()
            assert data["char_count"] == len(data["token_line"]), (
                f"char_count {data['char_count']} ≠ len(token_line) {len(data['token_line'])}"
            )


# ---------- T6: Demo-Modus (Issue #483) ------------------------------------


class TestT6DemoMode:
    """TDD RED: Issue #483 — Demo-Modus via ?demo=1.

    Spec: docs/specs/modules/issue_483_demo_mode_preview.md

    Diese Tests MÜSSEN FEHLSCHLAGEN bis die Implementierung existiert:
    - render_email_preview/render_sms_preview akzeptieren noch kein `demo`-Kwarg
    - _fetch_weather akzeptiert noch keinen `provider`-Parameter
    """

    def test_ac3_render_email_preview_accepts_demo_flag(self, service):
        """AC-3: render_email_preview muss `demo=True` akzeptieren und HTML zurückgeben.

        ERWARTET FEHLSCHLAG: TypeError — `demo` ist noch kein gültiger Parameter.
        """
        html = service.render_email_preview(
            "gr221-mallorca",
            user_id="default",
            report_type="morning",
            demo=True,
        )
        assert isinstance(html, str), "render_email_preview muss HTML-String zurückgeben"
        assert len(html) > 100, f"HTML zu kurz: {len(html)} Zeichen"

    def test_ac3_render_sms_preview_accepts_demo_flag(self, service):
        """AC-3: render_sms_preview muss `demo=True` akzeptieren.

        ERWARTET FEHLSCHLAG: TypeError — `demo` ist noch kein gültiger Parameter.
        """
        subject, token_line = service.render_sms_preview(
            "gr221-mallorca",
            user_id="default",
            report_type="morning",
            demo=True,
        )
        assert isinstance(subject, str)
        assert isinstance(token_line, str)

    def test_ac3_fetch_weather_accepts_provider_injection(self, service):
        """AC-3: _fetch_weather muss einen optionalen `provider`-Parameter akzeptieren.

        ERWARTET FEHLSCHLAG: TypeError — `provider` ist noch kein gültiger Parameter.
        """
        from providers.fixture import FixtureProvider
        from pathlib import Path
        fixture_dir = str(Path(__file__).resolve().parents[2] / "fixtures" / "openmeteo")
        fixture_provider = FixtureProvider(fixture_dir)

        from services.trip_report_scheduler import TripReportSchedulerService
        from app.config import Settings
        scheduler = TripReportSchedulerService(Settings())
        trip = service._load_trip("gr221-mallorca", user_id="default")
        from datetime import date
        target = date.today()
        segments = scheduler._convert_trip_to_segments(trip, target)
        if not segments:
            pytest.skip("Keine Segmente für heute — Trip in der Vergangenheit")

        # Dies muss fehlschlagen bis provider-Param implementiert ist:
        result = scheduler._fetch_weather(segments, provider=fixture_provider)
        assert isinstance(result, list), "_fetch_weather mit provider muss Liste zurückgeben"
        assert len(result) > 0

    def test_ac3_demo_endpoint_email_returns_200(self, client):
        """AC-3: GET /api/preview/{trip_id}/email?demo=1 muss immer HTTP 200 zurückgeben.

        ERWARTET FEHLSCHLAG: Endpoint verarbeitet demo-Param noch nicht —
        Service wirft TypeError bei demo=True.
        """
        resp = client.get(
            "/api/preview/gr221-mallorca/email",
            params={"type": "morning", "user_id": "default", "demo": "1"},
        )
        assert resp.status_code == 200, (
            f"Demo-Endpoint muss 200 zurückgeben, war: {resp.status_code}\n{resp.text[:300]}"
        )
        assert len(resp.text) > 100, "Demo-HTML darf nicht leer sein"

    def test_ac3_demo_endpoint_sms_returns_200(self, client):
        """AC-3: GET /api/preview/{trip_id}/sms?demo=1 muss immer HTTP 200 zurückgeben."""
        resp = client.get(
            "/api/preview/gr221-mallorca/sms",
            params={"type": "morning", "user_id": "default", "demo": "1"},
        )
        assert resp.status_code == 200, (
            f"Demo-SMS-Endpoint muss 200 zurückgeben, war: {resp.status_code}\n{resp.text[:300]}"
        )
        data = resp.json()
        assert "token_line" in data
        assert "char_count" in data


# ---------- T5: Issue #990 — Vorschau bei wegpunktlosen Etappen -----


def _make_waypoint990(id_: str, lat: float = 47.10, lon: float = 9.20):
    from app.trip import Waypoint
    return Waypoint(id=id_, name=f"Punkt {id_}", lat=lat, lon=lon, elevation_m=800)


def _make_stage990(stage_id: str, stage_date, num_waypoints: int):
    from app.trip import Stage
    waypoints = [
        _make_waypoint990(f"{stage_id}-wp{i}", 47.10 + i * 0.01, 9.20 + i * 0.01)
        for i in range(num_waypoints)
    ]
    return Stage(id=stage_id, name=f"Etappe {stage_id}", date=stage_date, waypoints=waypoints)


def _make_trip990(stages, trip_id: str = "test-990"):
    from app.trip import Trip
    return Trip(id=trip_id, name="Test Trip #990", stages=stages)


class TestIssue990WaypointSkip:
    """AC-1 bis AC-5 aus docs/specs/modules/fix_990_preview_empty_waypoints.md.

    Keine Mocks, keine Wetter-API-Calls: bei leeren Segments wirft
    _build_report bereits vor dem Wetter-Fetch (siehe preview_service.py:96-100).
    """

    def test_ac1_auto_resolve_skips_stage_without_waypoints(self, service):
        """AC-1: Auto-Resolve überspringt die wegpunktlose frühere Etappe
        zugunsten der nächsten renderbaren Etappe."""
        from datetime import date, timedelta
        today = date.today()
        stage_empty = _make_stage990("empty", today, num_waypoints=0)
        stage_ok = _make_stage990("ok", today + timedelta(days=1), num_waypoints=2)
        trip = _make_trip990([stage_empty, stage_ok])

        target = service._resolve_target_date(trip, given_date=None)

        assert target == stage_ok.date, (
            f"Erwartet: nächste renderbare Etappe ({stage_ok.date}), "
            f"war: {target} (wegpunktlose Etappe wurde gewählt)"
        )

    def test_ac2_explicit_date_on_empty_stage_error_contains_waypoint(self, service):
        """AC-2: Explizites target_date auf eine wegpunktlose Etappe liefert
        einen Fehlertext mit dem Wort 'waypoint' (matcht Frontend-Regex #421)."""
        from datetime import date
        stage_empty = _make_stage990("empty", date(2026, 8, 1), num_waypoints=1)
        trip = _make_trip990([stage_empty])

        with pytest.raises(LookupError) as exc_info:
            service._build_report(trip, stage_empty.date, "morning", demo=True)

        assert "waypoint" in str(exc_info.value).lower(), (
            f"Fehlertext muss 'waypoint' enthalten, war: {exc_info.value!r}"
        )

    def test_ac3_explicit_date_without_any_stage_stays_generic(self, service):
        """AC-3: Explizites target_date ohne jede Etappe bleibt generisch
        (kein 'waypoint' im Text) — Regressionsschutz gegen Fehlklassifikation."""
        from datetime import date
        stage_ok = _make_stage990("ok", date(2026, 8, 1), num_waypoints=2)
        trip = _make_trip990([stage_ok])
        no_stage_date = date(2026, 9, 15)

        with pytest.raises(LookupError) as exc_info:
            service._build_report(trip, no_stage_date, "morning", demo=True)

        assert "waypoint" not in str(exc_info.value).lower(), (
            f"Generischer 'keine Stage'-Fall darf 'waypoint' nicht enthalten, "
            f"war: {exc_info.value!r}"
        )

    def test_ac4_all_stages_without_waypoints_error_contains_waypoint(self, service):
        """AC-4: Kein Stage im Trip ist renderbar (weder Zukunft noch
        Fallback) — Fehlertext muss trotzdem 'waypoint' enthalten."""
        from datetime import date, timedelta
        today = date.today()
        stage_past = _make_stage990("past", today - timedelta(days=10), num_waypoints=1)
        stage_future = _make_stage990("future", today + timedelta(days=5), num_waypoints=0)
        trip = _make_trip990([stage_past, stage_future])

        with pytest.raises((LookupError, ValueError)) as exc_info:
            service._resolve_target_date(trip, given_date=None)

        assert "waypoint" in str(exc_info.value).lower(), (
            f"Fehlertext bei komplett wegpunktlosem Trip muss 'waypoint' "
            f"enthalten, war: {exc_info.value!r}"
        )

    def test_ac5_fully_renderable_trip_selection_unchanged(self, service):
        """AC-5: Regressionsschutz — Trip mit ausschließlich renderbaren
        Etappen liefert weiterhin die erste (chronologisch früheste) Etappe."""
        from datetime import date
        stage_first = _make_stage990("first", date(2026, 8, 1), num_waypoints=3)
        stage_second = _make_stage990("second", date(2026, 8, 2), num_waypoints=4)
        trip = _make_trip990([stage_second, stage_first])  # bewusst unsortiert

        target = service._resolve_target_date(trip, given_date=None)

        assert target == stage_first.date, (
            f"Erwartet: früheste renderbare Etappe ({stage_first.date}), war: {target}"
        )

    def test_ac4b_trip_with_zero_stages_raises_value_error_not_waypoint_text(self, service):
        """F001 (Adversary-Fund): Trip ganz ohne Etappen ist ein anderer Fall
        als 'Etappen ohne genug Wegpunkte' — muss weiterhin ValueError (422)
        liefern, NICHT LookupError mit 'waypoint' im Text (Frontend würde sonst
        fälschlich zum Wegpunkt-Editor verweisen, obwohl keine Etappe existiert)."""
        trip = _make_trip990([])

        with pytest.raises(ValueError) as exc_info:
            service._resolve_target_date(trip, given_date=None)

        assert not isinstance(exc_info.value, LookupError), (
            "Trip ohne jede Etappe darf NICHT als LookupError/waypoint-Fall behandelt werden"
        )
        assert "waypoint" not in str(exc_info.value).lower()

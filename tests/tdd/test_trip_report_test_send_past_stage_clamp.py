"""
TDD — Issue #1325: Test-Sendepfad klemmt vergangene Etappen-Termine auf heute.

Spec: docs/specs/modules/staging_selftest_stage_clamp.md
Workflow: fix-1325-staging-e2e-selftest

Verhaltenstests — KEINE Mocks im Sinne von Mock-Theater. Ein datums-
sensitiver Provider-Double bildet das reale Open-Meteo-Forecast-Verhalten
nach (Fehler fuer Vergangenheits-Zeitraeume, echte, real aufgezeichnete
Innsbruck-Struktur `fixtures/openmeteo/innsbruck.json` fuer "heute") --
der global aktive FixtureProvider ist datumsblind und kann den Bug NICHT
reproduzieren (Spec "Known Limitations"). Der SMTP-Transport wird analog
per `monkeypatch.setattr` durch einen No-Op ersetzt (reines Netzgrenze-
Substitut, damit dieser Kern-Test netzfrei bleibt -- Rendering, Klemm-
Logik und Outcome-Ableitung laufen unveraendert echt).
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import pytest
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

REPO_ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# Fixture: Trip mit zwei ausschliesslich vergangenen Etappen
# ---------------------------------------------------------------------------


def _data_users(user_id: str) -> Path:
    """Issue #1265 Teil C: get_data_dir() statt hartkodiertem Repo-Pfad --
    respektiert die pytest-Isolation (tests/conftest.py, #1133/#1265)."""
    from app.loader import get_data_dir
    return get_data_dir(user_id)


def _innsbruck_waypoints() -> list[dict]:
    return [
        {"id": "wp1", "name": "Innsbruck", "lat": 47.2692, "lon": 11.4041, "elevation_m": 574},
        {"id": "wp2", "name": "Hafelekar", "lat": 47.3103, "lon": 11.3844, "elevation_m": 2269},
    ]


def _write_trip(user_id: str, trip_id: str, stages: list[dict]) -> Path:
    """Schreibt Trip + Nutzerprofil in den (isolierten) briefings/-Baum --
    Issue #1250 Scheibe 7a Cutover: `load_all_trips()`/der Router lesen NUR
    noch `briefings/*.json`, nicht mehr `trips/*.json`."""
    from app.loader import get_briefings_dir
    briefings_dir = get_briefings_dir(user_id)
    briefings_dir.mkdir(parents=True, exist_ok=True)
    profile = _data_users(user_id) / "user.json"
    profile.write_text(json.dumps({"mail_to": "gregor-test@henemm.com"}))
    trip_path = briefings_dir / f"{trip_id}.json"
    trip_path.write_text(json.dumps({
        "id": trip_id,
        "name": "TDD-1325 Past-Only Trip",
        "kind": "route",
        "stages": stages,
        # official_alerts_enabled=False: strukturell kein MeteoAlarm-Fetch
        # (Kern-Test bleibt netzfrei, s. trip_report_scheduler.py:751).
        "official_alerts_enabled": False,
        "report_config": {"send_email": True, "send_telegram": False, "send_sms": False},
        "alert_rules": [],
    }))
    return trip_path


def _load_trip(user_id: str, trip_id: str):
    from app.loader import load_trip
    return load_trip(_data_users(user_id) / "briefings" / f"{trip_id}.json")


@pytest.fixture
def past_only_trip():
    """Zwei Etappen, beide < heute -- select_test_stage (#768) faellt auf die
    chronologisch frueheste zurueck, deren Datum ungeklemmt in einen toten
    Open-Meteo-Vergangenheits-Request laeuft (Issue #1325 Root Cause)."""
    user_id = "tdd-1325-past"
    trip_id = "tdd-1325-past-trip"
    early = (date.today() - timedelta(days=10)).isoformat()
    late = (date.today() - timedelta(days=3)).isoformat()
    trip_path = _write_trip(
        user_id, trip_id,
        [
            {"id": "st-late", "name": "Spaetere Vergangenheit", "date": late,
             "waypoints": _innsbruck_waypoints()},
            {"id": "st-early", "name": "Frueheste", "date": early,
             "waypoints": _innsbruck_waypoints()},
        ],
    )
    yield user_id, trip_id, early
    trip_path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Datums-sensitiver Provider-Double (Netzgrenze-Substitut, kein Mock-Theater)
# ---------------------------------------------------------------------------


class _DateSensitiveOpenMeteoDouble:
    """Bildet das reale Open-Meteo-Forecast-Endpoint-Verhalten nach: kein
    historischer Forecast fuer Vergangenheits-Zeitraeume (ProviderRequestError,
    identisch zum echten Provider bei openmeteo.py), echte, real aufgezeichnete
    Innsbruck-Struktur fuer "heute" (delegiert an den bestehenden
    `FixtureProvider`, der real aufgezeichnete Go-Fixture-Daten laedt)."""

    name = "openmeteo"

    def __init__(self, fail_for_today: bool = False) -> None:
        from providers.fixture import FixtureProvider
        self._fail_for_today = fail_for_today
        self._fixture = FixtureProvider(str(REPO_ROOT / "fixtures" / "openmeteo"))

    def fetch_forecast(self, location, start=None, end=None,
                        enrich_ensemble=True, enrich_snow=True):
        from providers.base import ProviderRequestError
        today = date.today()
        if self._fail_for_today or start is None or start.date() != today:
            raise ProviderRequestError(
                "openmeteo",
                "kein historischer Forecast fuer vergangene Zeitraeume "
                "(datumssensitiver Provider-Double, Issue #1325)",
                status_code=400,
            )
        return self._fixture.fetch_forecast(
            location, start=start, end=end,
            enrich_ensemble=enrich_ensemble, enrich_snow=enrich_snow,
        )


def _patch_provider(monkeypatch, fail_for_today: bool = False) -> None:
    double = _DateSensitiveOpenMeteoDouble(fail_for_today=fail_for_today)
    monkeypatch.setattr("providers.base.get_provider", lambda name: double)


def _patch_email_transport(monkeypatch) -> None:
    """Netzgrenze-Substitut fuer den SMTP-Transport (kein Mock-Theater an der
    unter Test stehenden Logik): ersetzt NUR den ausgehenden Netzwerk-Call,
    damit dieser Kern-Test (tests/tdd/, netzfrei-Pflicht) keine echte
    Stalwart-SMTP-Verbindung aufbaut. Rendering, Klemm-Logik und
    Outcome-Ableitung bleiben unveraendert der echte Code."""
    monkeypatch.setattr(
        "services.notification_service.NotificationService._send_email",
        lambda self, report: None,
    )


# ---------------------------------------------------------------------------
# AC-1: Test-Fallback-Pfad klemmt die vergangene Etappe auf heute -> "sent"
# ---------------------------------------------------------------------------


class TestAC1PastStageClampedToToday:
    def test_test_fallback_send_clamps_past_stage_to_real_forecast(
        self, past_only_trip, monkeypatch,
    ):
        """GIVEN: Trip, dessen saemtliche Etappen ein Datum < heute tragen
        WHEN: der Test-Sendepfad (allow_test_fallback=True) ein Briefing baut
        THEN: der Wetter-Abruf laeuft gegen "heute" (Klemme) -> Outcome "sent"

        Vor Fix: die frueheste Etappe (vor 10 Tagen) rutscht ungeklemmt in
        den Wetter-Abruf, der Double liefert dafuer ProviderRequestError fuer
        ALLE Segmente -> error_ratio ueberschreitet die #1113-Schwelle ->
        Outcome "no_weather" (Bug-Reproduktion, RED).
        """
        from services.trip_report_scheduler import TripReportSchedulerService

        user_id, trip_id, _ = past_only_trip
        _patch_provider(monkeypatch, fail_for_today=False)
        _patch_email_transport(monkeypatch)

        trip = _load_trip(user_id, trip_id)
        service = TripReportSchedulerService(user_id=user_id)
        outcome = service._send_trip_report_outcome(
            trip, "morning", allow_test_fallback=True,
        )
        assert outcome == "sent", (
            "Erwartet 'sent' (Wetter-Abruf muss auf heute geklemmt werden, "
            f"damit ein echter Forecast vorliegt). Bekommen: {outcome!r}"
        )


# ---------------------------------------------------------------------------
# AC-2: regulaerer Scheduler-Pfad (allow_test_fallback=False) bleibt unberuehrt
# ---------------------------------------------------------------------------


class TestAC2RegularPathUnclamped:
    def test_regular_path_without_test_fallback_stays_no_stage(
        self, past_only_trip, monkeypatch,
    ):
        """GIVEN: derselbe Past-Only-Trip
        WHEN: _send_trip_report_outcome OHNE Test-Fallback (regulaerer Pfad)
        THEN: Outcome bleibt 'no_stage' -- unveraendert zum Bestandsverhalten,
              die Klemme wirkt AUSSCHLIESSLICH im Test-Fallback-Pfad.
        """
        from services.trip_report_scheduler import TripReportSchedulerService

        user_id, trip_id, _ = past_only_trip
        _patch_provider(monkeypatch, fail_for_today=False)
        _patch_email_transport(monkeypatch)

        trip = _load_trip(user_id, trip_id)
        service = TripReportSchedulerService(user_id=user_id)
        outcome = service._send_trip_report_outcome(
            trip, "morning", allow_test_fallback=False,
        )
        assert outcome == "no_stage", (
            "Regulaerer Pfad darf NICHT klemmen -- erwartet 'no_stage', "
            f"bekommen {outcome!r}"
        )


# ---------------------------------------------------------------------------
# AC-3: genuiner No-Weather-Fall bekommt eine ehrliche, unterscheidbare
# Meldung/Outcome statt der irrefuehrenden No-Stage-Meldung
# ---------------------------------------------------------------------------


class TestAC3GenuineNoWeatherHonestOutcome:
    def test_service_outcome_is_no_weather_when_today_also_fails(
        self, past_only_trip, monkeypatch,
    ):
        """GIVEN: Provider-Double scheitert auch fuer 'heute' (genuiner Ausfall)
        WHEN: send_test_report_outcome(trip, 'morning')
        THEN: Outcome 'no_weather' -- ehrlich benannt, kein 'no_stage'.
        """
        from services.trip_report_scheduler import TripReportSchedulerService

        user_id, trip_id, _ = past_only_trip
        _patch_provider(monkeypatch, fail_for_today=True)
        _patch_email_transport(monkeypatch)

        trip = _load_trip(user_id, trip_id)
        service = TripReportSchedulerService(user_id=user_id)
        outcome = service.send_test_report_outcome(trip, "morning")
        assert outcome == "no_weather", (
            f"Erwartet ehrliches 'no_weather', bekommen {outcome!r}"
        )

    def test_router_returns_422_with_honest_no_weather_message(
        self, past_only_trip, monkeypatch,
    ):
        """GIVEN: dieselbe Situation ueber die echte HTTP-Route
        WHEN: POST /api/scheduler/trips/{trip_id}/send
        THEN: HTTP 422, Body enthaelt die NEUE ehrliche Meldung -- NICHT mehr
              die irrefuehrende 'keine Etappendaten fuer das aktuelle Datum'.
        """
        from fastapi.testclient import TestClient

        from api.main import app

        user_id, trip_id, _ = past_only_trip
        _patch_provider(monkeypatch, fail_for_today=True)
        _patch_email_transport(monkeypatch)

        client = TestClient(app)
        resp = client.post(
            f"/api/scheduler/trips/{trip_id}/send",
            params={"user_id": user_id, "report_type": "morning"},
        )
        assert resp.status_code == 422, (
            f"Erwartet 422, bekommen {resp.status_code}: {resp.text}"
        )
        detail = resp.json().get("detail", "")
        assert "keine Etappendaten für das aktuelle Datum" not in detail, (
            "Alte irrefuehrende No-Stage-Meldung darf fuer den No-Weather-Fall "
            f"NICHT mehr erscheinen: {detail!r}"
        )
        assert "wetterdaten" in detail.lower(), (
            f"Neue Meldung muss 'Wetterdaten' erwaehnen: {detail!r}"
        )

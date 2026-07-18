"""
TDD RED -- Slice R1 (#1212): Python-Endpoint fuer Etappen-Wetter + Risiko.

Spec: docs/specs/modules/stage_weather_python_endpoint.md

Diese Datei prueft den HTTP-Endpoint `GET /api/_internal/trips/{id}/stages-weather`
gegen einen echten `TestClient(api.main.app)` (kein Mock). Trips werden via
`app.loader.save_trip` in einem isolierten Test-Datenverzeichnis persistiert
(conftest.py::_isolate_data_root, autouse) und ueber `user_id` als Query-Param
geladen (Muster `api/routers/internal.py`, existierender `/loaded`-Endpoint).

ANNAHME zum Provider-Injektionspunkt (Teil des RED-Contracts, s. Auftrag):
Der neue Endpoint injiziert seinen WeatherProvider ueber eine FastAPI-Dependency
`api.routers.internal.get_stage_weather_provider` (Depends(...)), analog zum
etablierten `_build_service`-Muster in `api/routers/preview.py`. Diese
Dependency existiert noch nicht -- der Zugriff auf
`internal_router.get_stage_weather_provider` loest AttributeError aus, was
Teil des erwarteten RED-Fehlschlags ist. Tests, die keine przise Kontrolle
ueber die Wetter-Rohdaten benoetigen (AC-5/6/7/8), nutzen stattdessen den
Standard-FixtureProvider (GZ_TEST_FIXTURE_DIR, von tests/conftest.py fuer
jeden Test automatisch aktiviert) mit echten Innsbruck/Stubai-Koordinaten aus
fixtures/openmeteo/.

RED-Phase: Route `/api/_internal/trips/{id}/stages-weather` existiert noch
nicht -> FastAPI liefert 404 `{"detail": "Not Found"}` fuer JEDE Anfrage, was
gegen die erwarteten Bodies/Statuscodes fehlschlaegt.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Optional

from fastapi.testclient import TestClient

from app.loader import save_trip
from app.models import ForecastDataPoint, ForecastMeta, NormalizedTimeseries, Provider
from app.trip import Stage, Trip, Waypoint
from providers.base import ProviderRequestError

# Echte, im Repo vorhandene Fixture-Koordinaten (fixtures/openmeteo/*.json) --
# siehe src/providers/fixture.py::_FIXTURE_LOCATIONS.
_INNSBRUCK = (47.2692, 11.4041)
_STUBAI = (47.1015, 11.2958)


class _KeyedFakeProvider:
    """Reale WeatherProvider-Implementierung fuer Tests (KEIN unittest.mock).

    Siehe tests/tdd/test_stage_weather_parity.py fuer die identische
    Konstruktion -- hier dupliziert, damit beide RED-Dateien unabhaengig
    voneinander lauffaehig/lesbar bleiben.
    """

    name = "keyed-fake"

    def __init__(self, by_coord: dict[tuple[float, float], dict]) -> None:
        self._by_coord = by_coord

    def fetch_forecast(
        self,
        location,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        enrich_ensemble: bool = True,
        enrich_snow: bool = True,
    ) -> NormalizedTimeseries:
        key = (location.latitude, location.longitude)
        if key not in self._by_coord:
            raise ProviderRequestError("keyed-fake", f"No fixture for {key}")

        spec = self._by_coord[key]
        day = (start or datetime.now(timezone.utc)).date()
        data = []
        for hour in range(24):
            ts = datetime(day.year, day.month, day.day, hour, tzinfo=timezone.utc)
            data.append(
                ForecastDataPoint(
                    ts=ts,
                    t2m_c=spec.get("t2m_c", 10.0),
                    wind10m_kmh=spec.get("wind10m_kmh"),
                    gust_kmh=spec.get("gust_kmh", spec.get("wind10m_kmh")),
                    precip_1h_mm=spec.get("precip_1h_mm", 0.0),
                    wmo_code=spec.get("wmo_code", 1),
                    is_day=spec.get("is_day", 1),
                )
            )
        return NormalizedTimeseries(
            meta=ForecastMeta(provider=Provider.OPENMETEO, model="keyed-fake", grid_res_km=1.0),
            data=data,
        )


def _two_wp_stage(stage_id: str, lat0, lon0, lat1, lon1, elevation_m=600):
    return Stage(
        id=stage_id, name=stage_id, date=date.today(),
        waypoints=[
            Waypoint(id="g1", name="g1", lat=lat0, lon=lon0, elevation_m=elevation_m),
            Waypoint(id="g2", name="g2", lat=lat1, lon=lon1, elevation_m=elevation_m),
        ],
    )


# ---------------------------------------------------------------------------
# AC-1: Response-Vertrag 1:1 (JSON-Struktur + echte null-Serialisierung)
# ---------------------------------------------------------------------------

def test_ac1_endpoint_response_contract_and_null_field():
    """AC-1: HTTP 200, Body {"results": {...}}, Feldnamen exakt wie Spec,
    fehlender Wert (hier: Wind) wird als JSON `null` serialisiert (nicht
    weggelassen)."""
    from api.main import app
    from api.routers import internal as internal_router

    user_id = "stage-weather-ac1-user"
    stage = _two_wp_stage("s1", 20.0, -30.0, 21.0, -30.0, elevation_m=100)
    trip = Trip(id="ac1-trip", name="AC1", stages=[stage])
    save_trip(trip, user_id=user_id)

    provider = _KeyedFakeProvider({
        (20.0, -30.0): {"wind10m_kmh": None, "t2m_c": 5.0, "precip_1h_mm": 2.0, "wmo_code": 61},
        (21.0, -30.0): {"wind10m_kmh": None, "t2m_c": 6.0, "precip_1h_mm": 1.0, "wmo_code": 61},
    })

    override_key = getattr(internal_router, "get_stage_weather_provider", None)
    app.dependency_overrides[override_key] = lambda: provider
    try:
        client = TestClient(app)
        resp = client.get(
            "/api/_internal/trips/ac1-trip/stages-weather",
            params={"user_id": user_id},
        )
    finally:
        app.dependency_overrides.pop(override_key, None)

    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"].startswith("application/json")
    body = resp.json()
    assert "results" in body
    result = body["results"]["s1"]
    assert result is not None
    assert set(result.keys()) == {"weather_summary", "risk"}
    ws = result["weather_summary"]
    assert set(ws.keys()) == {
        "temp_min_c", "temp_max_c", "wind_max_kmh", "precip_mm", "wmo_code", "is_day",
    }
    assert "wind_max_kmh" in ws
    assert ws["wind_max_kmh"] is None, "Fehlendes Feld muss als JSON null erscheinen, nicht fehlen"
    assert result["risk"] in ("green", "yellow", "red")


# ---------------------------------------------------------------------------
# AC-5: Fail-soft pro Etappe -> HTTP 200, betroffene Etappe null
# ---------------------------------------------------------------------------

def test_ac5_fail_soft_returns_http_200_with_null_result():
    """AC-5: Eine Etappe ohne Waypoints liefert null, die gueltige Etappe
    bleibt unberuehrt, der Request scheitert NICHT (kein 5xx)."""
    from api.main import app

    user_id = "stage-weather-ac5-user"
    ok_stage = _two_wp_stage("ok", *_INNSBRUCK, *_STUBAI)
    broken_stage = Stage(id="broken", name="broken", date=date.today(), waypoints=[])
    trip = Trip(id="ac5-trip", name="AC5", stages=[ok_stage, broken_stage])
    save_trip(trip, user_id=user_id)

    client = TestClient(app)
    resp = client.get(
        "/api/_internal/trips/ac5-trip/stages-weather",
        params={"user_id": user_id},
    )

    assert resp.status_code == 200, f"Fail-soft darf kein 5xx ausloesen, sah {resp.status_code}: {resp.text}"
    body = resp.json()
    assert body["results"]["broken"] is None
    assert body["results"]["ok"] is not None
    assert body["results"]["ok"]["risk"] in ("green", "yellow", "red")


# ---------------------------------------------------------------------------
# AC-6: Leere Stage-ID fehlt im HTTP-Ergebnis
# ---------------------------------------------------------------------------

def test_ac6_empty_stage_id_missing_key_in_http_response():
    """AC-6: Eine Etappe ohne ID erscheint NICHT als Schluessel in results."""
    from api.main import app

    user_id = "stage-weather-ac6-user"
    empty_id_stage = _two_wp_stage("", *_INNSBRUCK, *_STUBAI)
    valid_stage = _two_wp_stage("valid", *_INNSBRUCK, *_STUBAI)
    trip = Trip(id="ac6-trip", name="AC6", stages=[empty_id_stage, valid_stage])
    save_trip(trip, user_id=user_id)

    client = TestClient(app)
    resp = client.get(
        "/api/_internal/trips/ac6-trip/stages-weather",
        params={"user_id": user_id},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert "" not in body["results"], "Etappe ohne ID darf keinen Schluessel erzeugen"
    assert "valid" in body["results"]


# ---------------------------------------------------------------------------
# AC-7: Fehlerfaelle -- 404 unbekannter Trip / 500 Ladefehler
# ---------------------------------------------------------------------------

def test_ac7_unknown_trip_returns_404_not_found():
    """AC-7a: Unbekannte trip_id -> HTTP 404, Body exakt {"error":"not_found"}."""
    from api.main import app

    client = TestClient(app)
    resp = client.get(
        "/api/_internal/trips/does-not-exist-xyz/stages-weather",
        params={"user_id": "stage-weather-ac7-user"},
    )
    assert resp.status_code == 404
    assert resp.json() == {"error": "not_found"}


def test_ac7_store_error_returns_500(monkeypatch):
    """AC-7b: Ein echter Ladefehler -> HTTP 500, Body exakt {"error":"store_error"}.

    Fault-Injection ueber monkeypatch.setattr auf die reale Modul-Funktion
    (etabliertes Muster, siehe
    tests/tdd/test_issue_572_multi_user_routing.py:435) -- kein
    Mock()/MagicMock, nur ein echter, werfender Funktions-Stub.
    """
    from api.main import app
    from api.routers import internal as internal_router

    def _raise(user_id="default", include_archived=False):
        raise RuntimeError("simulated store failure")

    monkeypatch.setattr(internal_router, "load_all_trips", _raise)

    client = TestClient(app)
    resp = client.get(
        "/api/_internal/trips/whatever/stages-weather",
        params={"user_id": "stage-weather-ac7b-user"},
    )
    assert resp.status_code == 500
    assert resp.json() == {"error": "store_error"}


# ---------------------------------------------------------------------------
# AC-8: Nutzer-Isolation -- niemals fremde Trip-Daten
# ---------------------------------------------------------------------------

def test_ac8_user_isolation_no_cross_user_leak():
    """AC-8: Zwei Nutzer, je ein Trip MIT DERSELBEN trip_id -- User A sieht
    nur A's Etappen, User B nur B's; kein Cross-User-Leck."""
    from api.main import app

    def _mk_trip(stage_id: str) -> Trip:
        return Trip(
            id="shared-trip-id",
            name="Shared",
            stages=[_two_wp_stage(stage_id, *_INNSBRUCK, *_STUBAI)],
        )

    save_trip(_mk_trip("only-a"), user_id="stage-weather-userA")
    save_trip(_mk_trip("only-b"), user_id="stage-weather-userB")

    client = TestClient(app)

    resp_a = client.get(
        "/api/_internal/trips/shared-trip-id/stages-weather",
        params={"user_id": "stage-weather-userA"},
    )
    resp_b = client.get(
        "/api/_internal/trips/shared-trip-id/stages-weather",
        params={"user_id": "stage-weather-userB"},
    )

    assert resp_a.status_code == 200
    assert resp_b.status_code == 200
    results_a = resp_a.json()["results"]
    results_b = resp_b.json()["results"]

    assert "only-a" in results_a
    assert "only-b" not in results_a, "User A darf niemals Etappen von User B sehen"
    assert "only-b" in results_b
    assert "only-a" not in results_b, "User B darf niemals Etappen von User A sehen"


# ---------------------------------------------------------------------------
# F001 (Adversary, Issue #1212): Last-Resort-Guard -- eine unerwartete
# Exception AUSSERHALB der Pro-Stage-Schleife (hier via Fault-Injection auf
# compute_stage_weather selbst simuliert) darf am Router nicht zu einem
# ungefangenen 500 fuehren, sondern muss zum etablierten store_error-Body.
# ---------------------------------------------------------------------------

def test_f001_unexpected_compute_error_returns_500_store_error(monkeypatch):
    """F001: compute_stage_weather wirft (Fault-Injection, echter werfender
    Funktions-Stub -- kein Mock) -> Router faengt es via Last-Resort-Guard
    ab, HTTP 500, Body exakt {"error":"store_error"}."""
    from api.main import app
    from api.routers import internal as internal_router

    user_id = "stage-weather-f001-user"
    stage = _two_wp_stage("s1", *_INNSBRUCK, *_STUBAI)
    trip = Trip(id="f001-trip", name="F001", stages=[stage])
    save_trip(trip, user_id=user_id)

    def _raise(trip, provider):
        raise RuntimeError("simulated unexpected compute failure")

    monkeypatch.setattr(internal_router, "compute_stage_weather", _raise)

    client = TestClient(app)
    resp = client.get(
        "/api/_internal/trips/f001-trip/stages-weather",
        params={"user_id": user_id},
    )
    assert resp.status_code == 500, resp.text
    assert resp.json() == {"error": "store_error"}

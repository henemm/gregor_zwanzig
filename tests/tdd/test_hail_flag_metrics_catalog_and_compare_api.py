"""TDD RED — Issue #1475 Scheibe S5a (Epic #1419), AC-9/AC-10.

AC-9: Hagel ist keine waehlbare Trip-Editor-Metrik (analog `confidence_pct`,
Issue #710) -- `GET /api/metrics` darf keinen Hagel-Eintrag zeigen. Dieser
Test ist ein VORWAERTS-WAECHTER: er ist bereits HEUTE gruen (der Katalog
kennt noch gar kein Hagel-Feld) und muss es NACH der Implementierung
bleiben -- er beweist deshalb keine neue Funktionalitaet, sondern eine
Invariante, die die Implementierung nicht brechen darf. Siehe Bericht an
den Orchestrator fuer die Einordnung dieses Sonderfalls.

AC-10: `api/routers/compare.py` reicht `hail_flag` im selben `hourly`-
Eintrag durch wie `wmo_code` -- kein stiller Feldverlust beim Serialisieren
(Praezedenzfall #1265/#1349).

RED-Ursache AC-10 (heute): `ForecastDataPoint` kennt kein `hail_flag`
(TypeError bei Fixture-Konstruktion); selbst nach Ergaenzung des Feldes
serialisiert `run_comparison()` es NICHT in den `hourly`-Eintrag (fehlender
Schluessel -> AssertionError).

Keine Mocks/patch()/MagicMock im Sinn von Verhaltens-Attrappen --
`monkeypatch.setattr(...)` ersetzt hier echte Datenquellen (Orte-Liste,
Vergleichsergebnis) durch echte, lokal konstruierte DTOs, analog zum
projektweiten Muster, `BASE_HOST` auf einen lokalen Fixture-Server
umzubiegen.
"""
from __future__ import annotations

import sys
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from api.main import app
    return TestClient(app)


@pytest.fixture
def metrics_client():
    """Eigenstaendiger config-Router mit /api-Prefix (Muster aus
    test_issue_715_confidence_not_selectable.py — dort liegt /api/metrics
    tatsaechlich, `api.main.app` bindet config.router OHNE Prefix unter
    /metrics)."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from api.routers import config

    app = FastAPI()
    app.include_router(config.router, prefix="/api")
    return TestClient(app)


# =============================================================================
# AC-9 — kein wählbarer Hagel-Eintrag im Metrik-Katalog (Vorwaerts-Waechter)
# =============================================================================

def test_ac9_metrics_endpoint_zeigt_keinen_hagel_eintrag(metrics_client):
    resp = metrics_client.get("/api/metrics")
    assert resp.status_code == 200
    data = resp.json()

    alle_ids = [m["id"] for kategorie in data.values() for m in kategorie]
    hagel_treffer = [
        mid for mid in alle_ids
        if "hail" in mid.lower() or "hagel" in mid.lower()
    ]
    assert not hagel_treffer, (
        f"GET /api/metrics zeigt eine waehlbare Hagel-Metrik ({hagel_treffer!r}) "
        "-- Hagel ist gemaess Spec AC-9 (analog #710 confidence_pct) NICHT "
        "waehlbar, es erscheint nur automatisch neben der Gewitterstufe"
    )


# =============================================================================
# AC-10 — Compare-API reicht hail_flag im hourly-Eintrag durch
# =============================================================================

def test_ac10_compare_api_serialisiert_hail_flag_im_hourly_eintrag(client, monkeypatch):
    from app.models import ForecastDataPoint
    from app.user import ComparisonResult, LocationResult, SavedLocation
    from services.comparison_engine import ComparisonEngine
    import app.loader as loader_mod

    ort = SavedLocation(id="hagel-testort", name="Hagel-Testort", lat=42.0, lon=9.0, elevation_m=800)
    hagel_punkt = ForecastDataPoint(
        ts=datetime(2026, 8, 4, 14, 0, tzinfo=timezone.utc),
        wmo_code=96, hail_flag=True,
    )
    fixture_ergebnis = ComparisonResult(
        locations=[LocationResult(location=ort, hourly_data=[hagel_punkt])],
        time_window=(9, 16), target_date=date(2026, 8, 4),
    )

    monkeypatch.setattr(loader_mod, "load_all_locations", lambda *a, **kw: [ort])
    monkeypatch.setattr(ComparisonEngine, "run", staticmethod(lambda **kwargs: fixture_ergebnis))

    resp = client.get("/api/compare?location_ids=hagel-testort&user_id=hagel-tester")
    assert resp.status_code == 200
    data = resp.json()

    orte = data.get("locations") or []
    assert orte, f"Keine Orte in der Compare-Antwort: {data!r}"
    stunden = orte[0].get("hourly") or []
    assert stunden, f"Kein hourly-Eintrag fuer den Testort: {orte[0]!r}"

    treffer = [h for h in stunden if h.get("wmo_code") == 96]
    assert treffer, f"Kein hourly-Eintrag mit wmo_code=96 gefunden: {stunden!r}"
    assert treffer[0].get("hail_flag") is True, (
        f"Der hourly-Eintrag mit wmo_code=96 traegt kein 'hail_flag': true "
        f"-- stiller Feldverlust beim Serialisieren (Praezedenz #1265/#1349), "
        f"bekam: {treffer[0]!r}"
    )

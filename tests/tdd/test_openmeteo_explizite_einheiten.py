"""TDD (Issue #1994, Audit B-04): explizite Einheiten an ALLEN Open-Meteo-Requests.

Spec: docs/specs/modules/fix_1994_openmeteo_units.md (AC-1 .. AC-5, AC-7)

Jede produktive Open-Meteo-Anfrage muss `wind_speed_unit=kmh`,
`temperature_unit=celsius`, `precipitation_unit=mm` jeweils genau einmal
senden, statt sich auf API-Defaults zu verlassen. MOCK-FREI: der Pruefling
setzt einen ECHTEN `httpx.Request` ab, der Test liest dessen kodierte Query
(Vorbild tests/tdd/test_wegpunkt_hoehe_im_request.py).

AC-Test-Mapping:
| AC   | Testfunktion                                         |
|------|------------------------------------------------------|
| AC-1 | test_hauptvorhersage_traegt_alle_drei_einheiten      |
| AC-2 | test_fallback_modell_anfrage_traegt_einheiten        |
| AC-3 | test_ensemble_anfrage_traegt_einheiten               |
| AC-4 | test_probe_und_uv_anfrage_tragen_einheiten           |
| AC-5 | test_wolken_und_nowcast_anfrage_tragen_einheiten     |
"""
from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import List
from urllib.parse import parse_qs

import httpx
import tenacity

from app.config import Location
from providers.geosphere import GeoSphereProvider
from providers.openmeteo import OpenMeteoProvider

EINHEITEN = {
    "wind_speed_unit": ["kmh"],
    "temperature_unit": ["celsius"],
    "precipitation_unit": ["mm"],
}

_ORT = Location(latitude=47.0614, longitude=11.1211, name="Schaufelspitze", elevation_m=3333)
_OM_ALL_MODEL_IDS = ["meteofrance_arome", "icon_d2", "metno_nordic", "icon_eu", "ecmwf_ifs04"]
_GEOSPHERE_NWP_FIXTURE = (
    Path(__file__).resolve().parents[1] / "fixtures" / "geosphere_nwp_innsbruck.json"
)


def _query(request: httpx.Request) -> dict:
    return parse_qs(request.url.query.decode(), keep_blank_values=True)


def _assert_einheiten(request: httpx.Request, wo: str) -> None:
    query = _query(request)
    for key, want in EINHEITEN.items():
        assert query.get(key) == want, (
            f"{wo}: {key} muss genau einmal {want[0]!r} sein, war {query.get(key)!r} "
            f"(Host {request.url.host}{request.url.path})"
        )


def _prepare_provider(monkeypatch, tmp_path, unavailable=None) -> OpenMeteoProvider:
    cache_path = tmp_path / "model_availability.json"
    cache_path.write_text(json.dumps({
        "probe_date": date.today().isoformat(),
        "models": {
            # Primaermodell (icon_d2) meldet Luecken, alle anderen Modelle
            # haben diese Parameter -> Fallback-Request wird ausgeloest.
            mid: (
                {"available": [], "unavailable": list(unavailable or [])}
                if mid == "icon_d2"
                else {"available": list(unavailable or []), "unavailable": []}
            )
            for mid in _OM_ALL_MODEL_IDS
        },
    }))
    monkeypatch.setattr("providers.openmeteo.AVAILABILITY_CACHE_PATH", cache_path)
    monkeypatch.setattr("providers.openmeteo.DIAGNOSTICS_PATH", tmp_path / "calls.jsonl")
    monkeypatch.setattr(OpenMeteoProvider._request.retry, "wait", tenacity.wait_none())
    monkeypatch.setattr(
        OpenMeteoProvider._request.retry, "stop", tenacity.stop_after_attempt(1)
    )
    return OpenMeteoProvider()


def _handler(seen: List[httpx.Request]):
    def _respond(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={
            "hourly": {"time": ["2026-10-08T12:00"], "temperature_2m": [5.0],
                       "uv_index": [1.0]}
        })
    return _respond


def _provider_mit_transport(monkeypatch, tmp_path, unavailable=None):
    provider = _prepare_provider(monkeypatch, tmp_path, unavailable)
    seen: List[httpx.Request] = []
    provider._client = httpx.Client(transport=httpx.MockTransport(_handler(seen)))
    return provider, seen


def test_hauptvorhersage_traegt_alle_drei_einheiten(monkeypatch, tmp_path):
    provider, seen = _provider_mit_transport(monkeypatch, tmp_path)
    provider.fetch_forecast(_ORT, enrich_ensemble=False)
    main = [r for r in seen if r.url.host == "api.open-meteo.com"]
    assert main, "kein Hauptvorhersage-Request beobachtet"
    _assert_einheiten(main[0], "AC-1 Hauptvorhersage")


def test_fallback_modell_anfrage_traegt_einheiten(monkeypatch, tmp_path):
    provider, seen = _provider_mit_transport(
        monkeypatch, tmp_path, unavailable=["wind_gusts_10m"]
    )
    provider.fetch_forecast(_ORT, enrich_ensemble=False)
    main = [r for r in seen if r.url.host == "api.open-meteo.com"]
    fallback = [r for r in main if _query(r).get("hourly") == ["wind_gusts_10m"]]
    assert fallback, (
        "AC-2: kein Fallback-Request (hourly=nur fehlende Parameter) beobachtet: "
        f"{[(r.url.path, _query(r).get('hourly')) for r in main]}"
    )
    _assert_einheiten(fallback[0], "AC-2 Fallback")


def test_ensemble_anfrage_traegt_einheiten(monkeypatch, tmp_path):
    provider, seen = _provider_mit_transport(monkeypatch, tmp_path)
    start = datetime(2026, 10, 8, 6, tzinfo=timezone.utc)
    end = datetime(2026, 10, 8, 18, tzinfo=timezone.utc)
    provider.fetch_forecast(_ORT, start=start, end=end, enrich_ensemble=True)
    ens = [r for r in seen if r.url.host == "ensemble-api.open-meteo.com"]
    assert ens, "AC-3: kein Ensemble-Request beobachtet"
    _assert_einheiten(ens[0], "AC-3 Ensemble")


def test_probe_und_uv_anfrage_tragen_einheiten(monkeypatch, tmp_path):
    provider, seen = _provider_mit_transport(monkeypatch, tmp_path)
    provider.probe_model_availability()
    probe = [r for r in seen if r.url.host == "api.open-meteo.com"]
    assert probe, "AC-4: kein Probe-Request beobachtet"
    for r in probe:
        _assert_einheiten(r, "AC-4 Probe")

    seen.clear()
    start = datetime(2026, 10, 8, 6, tzinfo=timezone.utc)
    end = datetime(2026, 10, 8, 18, tzinfo=timezone.utc)
    provider.fetch_forecast(_ORT, start=start, end=end, enrich_ensemble=False)
    uv = [r for r in seen if r.url.host == "air-quality-api.open-meteo.com"]
    assert uv, "AC-4: kein UV-Request beobachtet"
    _assert_einheiten(uv[0], "AC-4 UV")


def test_wolken_und_nowcast_anfrage_tragen_einheiten(monkeypatch):
    # Wolken-Abruf ueber GeoSphere
    seen: List[httpx.Request] = []
    nwp_payload = json.loads(_GEOSPHERE_NWP_FIXTURE.read_text())

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.host == "api.open-meteo.com":
            return httpx.Response(200, json={"hourly": {
                "time": [], "cloud_cover_low": [], "cloud_cover_mid": [],
                "cloud_cover_high": []}})
        if "snowgrid" in request.url.path:
            return httpx.Response(200, json={"features": []})
        return httpx.Response(200, json=nwp_payload)

    provider = GeoSphereProvider(client=httpx.Client(transport=httpx.MockTransport(handler)))
    provider.fetch_forecast(_ORT)
    wolken = [r for r in seen if r.url.host == "api.open-meteo.com"]
    assert wolken, "AC-5: kein Wolken-Request beobachtet"
    _assert_einheiten(wolken[0], "AC-5 Wolken")

    # Nowcast (radar_service): httpx.Client wird durch einen echten Client mit
    # MockTransport ersetzt; der Pruefling baut und sendet die URL selbst.
    from services.radar_service import RadarNowcastService

    nowcast_seen: List[httpx.Request] = []
    real_client = httpx.Client

    def nowcast_handler(request: httpx.Request) -> httpx.Response:
        nowcast_seen.append(request)
        return httpx.Response(200, json={"minutely_15": {
            "time": [], "precipitation": [], "weather_code": []}})

    def client_factory(*a, **kw):
        kw.pop("transport", None)
        return real_client(*a, transport=httpx.MockTransport(nowcast_handler), **kw)

    monkeypatch.delenv("GZ_TEST_FIXTURE_DIR", raising=False)
    monkeypatch.setattr(httpx, "Client", client_factory)
    RadarNowcastService()._fetch_openmeteo_15(47.0614, 11.1211, elevation_m=3333)
    assert nowcast_seen, "AC-5: kein Nowcast-Request beobachtet"
    _assert_einheiten(nowcast_seen[0], "AC-5 Nowcast")

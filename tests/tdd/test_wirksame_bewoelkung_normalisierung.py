"""Wirksame Bewölkung wirkt am Ausgang der Normalisierung (Issue #3106, ADR-0122).

SPEC: docs/specs/modules/feat_3106_wirksame_bewoelkung.md (Design "Wo die Regel
angewendet wird", AC-1/AC-4/AC-6)

Kern-Schicht, netzfrei, ohne Mock-Theater: Der ECHTE ``OpenMeteoProvider``
setzt echte ``httpx``-Requests ab; die Antworten kommen aus einem
``httpx.MockTransport`` mit aufgezeichnetem Open-Meteo-Format (Muster
``tests/tdd/test_openmeteo_explizite_einheiten.py``). Geprüft wird jeder
Rückgabeweg von ``fetch_forecast`` (regulär, Modell-Rückfall, Anbieter-
Totalausfall) sowie der Offline-Spiegel ``FixtureProvider``: ``cloud_total_pct``
trägt danach die wirksame Bewölkung, ``cloud_total_model_pct`` den Modellwert.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from app.config import Location
from app.models import ForecastDataPoint, ForecastMeta, NormalizedTimeseries, Provider
from tests.tdd._wirksame_bewoelkung_fixtures import (
    GEMISCHT, NUR_TIEF, SCHLEIER, open_meteo_antwort, provider_mit_antwort,
)

#: Vier Stunden: Schleierwolken, dichte Mittelschicht (AC-2), gemischt (AC-3),
#: nur tiefe Wolken (AC-4 in der Hochlage).
_DICHT_MITTEL = {"cloud_cover": 100, "cloud_cover_low": 0, "cloud_cover_mid": 100,
                 "cloud_cover_high": 100}
_STUNDEN = ["2026-11-17T08:00", "2026-11-17T09:00", "2026-11-17T10:00", "2026-11-17T11:00"]
_WOLKEN = [SCHLEIER, _DICHT_MITTEL, GEMISCHT, NUR_TIEF]
_GESAMT = [w["cloud_cover"] for w in _WOLKEN]
_HOCH = [w["cloud_cover_high"] for w in _WOLKEN]

#: Aabenraa (Daenemark, PO-Meldung) liegt in der DE-Box der Totalausfall-Weiche.
_TAL = Location(latitude=55.04, longitude=9.42, name="Aabenraa", elevation_m=20)
#: Hochlage in den Alpen, >= 2500 m.
_BERG = Location(latitude=47.06, longitude=11.12, name="Schaufelspitze", elevation_m=3200)


def _provider(monkeypatch, tmp_path, status_je_pfad: dict | None = None):
    antwort = open_meteo_antwort(_STUNDEN, _WOLKEN, temperature_2m=5.0)
    return provider_mit_antwort(monkeypatch, tmp_path, antwort, status_je_pfad)


def _wirksam(ts) -> list:
    return [dp.cloud_total_pct for dp in ts.data]


def _modell(ts) -> list:
    return [dp.cloud_total_model_pct for dp in ts.data]


def test_regulaerer_abruf_liefert_wirksame_bewoelkung(monkeypatch, tmp_path):
    ts = _provider(monkeypatch, tmp_path).fetch_forecast(
        _TAL, enrich_ensemble=False, enrich_snow=False,
    )
    assert _wirksam(ts) == [50, 100, 52, 100], "AC-1/AC-2/AC-3 im Tal"
    assert _modell(ts) == _GESAMT
    # Schichten bleiben die Rohwerte des Modells (eigene Metriken CL/CM/CH).
    assert [dp.cloud_high_pct for dp in ts.data] == _HOCH


def test_regulaerer_abruf_nutzt_die_standorthoehe(monkeypatch, tmp_path):
    ts = _provider(monkeypatch, tmp_path).fetch_forecast(
        _BERG, enrich_ensemble=False, enrich_snow=False,
    )
    # Hochlage: tiefe Wolken unter dem Standort zählen nicht (AC-4), dichte
    # mittelhohe Schicht voll (AC-5), Schleier halb.
    assert _wirksam(ts) == [50, 100, 40, 0]
    assert _modell(ts) == _GESAMT


def test_modell_rueckfall_liefert_wirksame_bewoelkung(monkeypatch, tmp_path):
    # Primärmodell für Aabenraa ist das dichteste abdeckende; alle außer ECMWF
    # fallen mit 503 aus -> Modell-Rückfall auf den globalen Endpoint.
    ausfall = {p: 503 for p in ("/v1/meteofrance", "/v1/dwd-icon", "/v1/metno")}
    ts = _provider(monkeypatch, tmp_path, ausfall).fetch_forecast(
        _TAL, enrich_ensemble=False, enrich_snow=False,
    )
    assert ts.meta.fallback_reason == "model_5xx", "Vorbedingung: Rückfallweg"
    assert _wirksam(ts) == [50, 100, 52, 100]
    assert _modell(ts) == _GESAMT


class _DirektAnbieter:
    """Echter Ersatzanbieter (erfüllt das Provider-Protokoll) mit Schichten."""

    name = "de_direct"

    def fetch_forecast(self, location, start=None, end=None, enrich_ensemble=True):
        t0 = datetime(2026, 11, 17, 8, 0, tzinfo=timezone.utc)
        data = [
            ForecastDataPoint(ts=t0, cloud_total_pct=100, cloud_low_pct=0,
                              cloud_mid_pct=0, cloud_high_pct=100),
            ForecastDataPoint(ts=t0 + timedelta(hours=1), cloud_total_pct=64),
        ]
        meta = ForecastMeta(provider=Provider.OPENMETEO, model="direkt", grid_res_km=2.0)
        return NormalizedTimeseries(meta=meta, data=data)


def test_anbieter_totalausfall_liefert_wirksame_bewoelkung(monkeypatch, tmp_path):
    import providers.base as registry

    if not registry._PROVIDER_FACTORIES:
        registry._load_providers()
    monkeypatch.setitem(registry._PROVIDER_FACTORIES, "de_direct", _DirektAnbieter)
    ausfall = {p: 503 for p in ("/v1/meteofrance", "/v1/dwd-icon", "/v1/metno", "/v1/ecmwf")}
    ts = _provider(monkeypatch, tmp_path, ausfall).fetch_forecast(
        _TAL, enrich_ensemble=False, enrich_snow=False,
    )
    assert ts.meta.fallback_reason == "cross_provider_total_outage", "Vorbedingung"
    # Schleier halb; Ersatzanbieter ohne Schichten -> Gesamtwert (AC-6).
    assert _wirksam(ts) == [50, 64]
    assert _modell(ts) == [100, 64]


def _fixture_ordner(tmp_path, punkt: dict):
    ordner = tmp_path / "fixtures"
    ordner.mkdir()
    daten = [dict(punkt, t2m_c=5.0) for _ in range(72)]
    (ordner / "innsbruck.json").write_text(json.dumps({"data": daten}))
    return ordner


@pytest.mark.parametrize("hoehe, erwartet", [(574, 50), (2800, 50), (None, 50)])
def test_fixture_provider_spiegelt_die_normalisierung(tmp_path, hoehe, erwartet):
    from providers.fixture import FixtureProvider

    ordner = _fixture_ordner(tmp_path, dict(
        cloud_total_pct=100, cloud_low_pct=0, cloud_mid_pct=0, cloud_high_pct=100,
    ))
    ort = Location(latitude=47.27, longitude=11.40, name="Innsbruck", elevation_m=hoehe)
    ts = FixtureProvider(str(ordner)).fetch_forecast(ort)
    assert {dp.cloud_total_pct for dp in ts.data} == {erwartet}
    assert {dp.cloud_total_model_pct for dp in ts.data} == {100}


def test_fixture_provider_hochlage_blendet_tiefe_wolken_aus(tmp_path):
    from providers.fixture import FixtureProvider

    ordner = _fixture_ordner(tmp_path, dict(
        cloud_total_pct=100, cloud_low_pct=100, cloud_mid_pct=0, cloud_high_pct=0,
    ))
    tal = Location(latitude=47.27, longitude=11.40, elevation_m=574)
    berg = Location(latitude=47.27, longitude=11.40, elevation_m=2800)
    assert FixtureProvider(str(ordner)).fetch_forecast(tal).data[0].cloud_total_pct == 100
    assert FixtureProvider(str(ordner)).fetch_forecast(berg).data[0].cloud_total_pct == 0


# ── Sonnenstunden-Rückfall ohne DNI liest die wirksame Bewölkung ─────────────

def test_sonnenstunden_ohne_dni_beruhen_auf_der_wirksamen_bewoelkung(monkeypatch, tmp_path):
    """Ohne Einstrahlung (DNI) rechnen die Sonnenstunden aus der Bewölkung --
    aus der WIRKSAMEN: vier Stunden nur Schleierwolken sind je eine halbe
    Sonnenstunde (2,0 h), nicht null wie aus dem Modellwert 100 %."""
    from services.weather_metrics import WeatherMetricsService

    antwort = open_meteo_antwort(_STUNDEN, [SCHLEIER] * 4, temperature_2m=5.0)
    ts = provider_mit_antwort(monkeypatch, tmp_path, antwort).fetch_forecast(
        _TAL, enrich_ensemble=False, enrich_snow=False,
    )
    assert all(dp.dni_wm2 is None for dp in ts.data), "Vorbedingung: ohne DNI"
    assert _modell(ts) == [100] * 4, "Vorbedingung: Modellwert voll bewölkt"
    assert WeatherMetricsService.calculate_sunny_hours(ts.data) == 2.0


# ── Schnappschüsse speichern nur die wirksame Bewölkung ──────────────────────

def _trip_segment(ts):
    from app.models import GPXPoint, SegmentWeatherData, SegmentWeatherSummary, TripSegment

    punkt = GPXPoint(lat=_TAL.latitude, lon=_TAL.longitude)
    return SegmentWeatherData(
        segment=TripSegment(
            segment_id=1, start_point=punkt, end_point=punkt,
            start_time=datetime(2026, 11, 17, 8, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 11, 17, 12, 0, tzinfo=timezone.utc),
            duration_hours=4.0, distance_km=5.0, ascent_m=100.0, descent_m=100.0,
        ),
        timeseries=ts, aggregated=SegmentWeatherSummary(temp_avg_c=5.0),
        fetched_at=datetime(2026, 11, 17, 6, 0, tzinfo=timezone.utc), provider="openmeteo",
    )


def _stunden_auf_platte(pfad) -> list[dict]:
    daten = json.loads(pfad.read_text())
    stunden = daten["hourly"] if "hourly" in daten else daten["segments"][0]["hourly"]
    assert stunden, "Vorbedingung: Stundenwerte stehen im Schnappschuss"
    return stunden


def test_trip_schnappschuss_speichert_den_modellwert_nicht(monkeypatch, tmp_path):
    """Der Modellwert ist nur Transparenz im Speicher: auf der Platte steht
    allein die wirksame Bewölkung (ein zurückgerollter Stand kennt das neue
    Feld nicht und könnte den Schnappschuss sonst nicht laden)."""
    from datetime import date

    from app.loader import get_snapshots_dir
    from services.weather_snapshot import WeatherSnapshotService

    ts = _provider(monkeypatch, tmp_path).fetch_forecast(
        _TAL, enrich_ensemble=False, enrich_snow=False,
    )
    assert _modell(ts) == _GESAMT, "Vorbedingung: Modellwert im Speicher gesetzt"
    dienst = WeatherSnapshotService(user_id="tdd-3106-a")
    dienst.save("tdd-3106-trip", [_trip_segment(ts)], date(2026, 11, 17))

    stunden = _stunden_auf_platte(get_snapshots_dir("tdd-3106-a") / "tdd-3106-trip.json")
    assert all("cloud_total_model_pct" not in h for h in stunden)
    assert [h["cloud_total_pct"] for h in stunden] == [50, 100, 52, 100]

    geladen = dienst.load("tdd-3106-trip")
    assert _wirksam(geladen[0].timeseries) == [50, 100, 52, 100]


def test_vergleichs_schnappschuss_speichert_den_modellwert_nicht(monkeypatch, tmp_path):
    from app.loader import get_data_dir
    from app.models import SegmentWeatherSummary
    from services.compare_weather_snapshot import CompareWeatherSnapshotService
    from services.point_weather import PointWeatherData

    ts = _provider(monkeypatch, tmp_path).fetch_forecast(
        _TAL, enrich_ensemble=False, enrich_snow=False,
    )
    assert _modell(ts) == _GESAMT, "Vorbedingung: Modellwert im Speicher gesetzt"
    dienst = CompareWeatherSnapshotService("tdd-3106-b")
    dienst.save("cp-3106", "aabenraa", PointWeatherData(
        id="aabenraa", name="Aabenraa", lat=_TAL.latitude, lon=_TAL.longitude,
        timeseries=ts, aggregated=SegmentWeatherSummary(temp_avg_c=5.0),
        fetched_at=datetime(2026, 11, 17, 6, 0, tzinfo=timezone.utc), provider="openmeteo",
    ))

    pfad = get_data_dir("tdd-3106-b") / "compare_weather_snapshots" / "cp-3106__aabenraa.json"
    stunden = _stunden_auf_platte(pfad)
    assert all("cloud_total_model_pct" not in h for h in stunden)
    assert [h["cloud_total_pct"] for h in stunden] == [50, 100, 52, 100]

    geladen = dienst.load("cp-3106", "aabenraa")
    assert _wirksam(geladen[0].timeseries) == [50, 100, 52, 100]

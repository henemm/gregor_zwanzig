"""TDD RED — Issue #1345: Provider-Zeitstempel-Normalisierung.

Spec: docs/specs/modules/provider_tz_normalization.md v2.0 (AC-1..AC-5)
Context: docs/context/fix-1345-geosphere-tz-normalisierung.md

Root Cause (v2.0, korrigiert gegenueber v1.0): `ForecastDataPoint.ts` wird
nur als `datetime` typisiert, ohne naive/aware zu erzwingen. Der echte
Prod-Crash sitzt NICHT am GeoSphere-Fallback (der liefert durchgehend aware
Zeitstempel und crasht heute nicht), sondern am PRIMAEREN Open-Meteo-Pfad:
Open-Meteo liefert naive `ForecastDataPoint.ts`; `TripSegment.start_time`/
`.end_time` sind ueber `_validate_segment` zwingend aware UTC.
`SegmentWeatherService._aggregate_for_segment` (`segment_weather.py:246-258`)
vergleicht seit Commit `f0310cac` (#1331/#1334) volle `datetime`-Werte
(`start_floor <= dp.ts < end_floor`) statt nur Stunden — naive `dp.ts` gegen
aware `start_floor`/`end_floor` loest `TypeError: can't compare
offset-naive and offset-aware datetimes` aus.

MOCK-FREI (kein Mock()/patch()/MagicMock): HTTP-Grenzen werden ueber
`httpx.MockTransport` (Test-Doppelgaenger auf Transport-Ebene, keine
Business-Logik) oder echte, EINMALIG aufgezeichnete GeoSphere-API-Fixtures
(`tests/fixtures/geosphere_nwp_innsbruck.json`) gestubbt. Retry-Zeiten
werden ueber tenacity's eigene `.retry.wait`/`.retry.stop`-Attribute
neutralisiert (Vorbild `tests/tdd/test_issue_1142_geosphere_direct_fallback.py`),
nicht die Entscheidungslogik selbst.

AC-Test-Mapping:
| AC   | Testfunktion                                                          |
|------|------------------------------------------------------------------------|
| AC-1 | test_ac1_forecast_datapoint_normalizes_aware_timestamp_to_naive        |
| AC-2 | test_ac2_openmeteo_primary_path_naive_ts_crashes_against_aware_segment |
| AC-3 | test_ac3_geosphere_cloud_layer_summer_dst_offset                       |
| AC-4 | test_ac4_retry_succeeds_after_two_transient_errors                     |
| AC-5 | test_ac5_geosphere_fallback_regression_stays_green                     |
"""
from __future__ import annotations

import json
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import httpx
import tenacity

from app.config import Location
from app.models import (
    ForecastDataPoint,
    ForecastMeta,
    GPXPoint,
    NormalizedTimeseries,
    Provider,
    TripSegment,
)
from providers.base import ProviderRequestError
from providers.geosphere import GeoSphereProvider
from providers.openmeteo import OpenMeteoProvider
from services.segment_weather import SegmentWeatherService
from services.trip_report_scheduler import TripReportSchedulerService

_FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
_GEOSPHERE_NWP_FIXTURE = _FIXTURES_DIR / "geosphere_nwp_innsbruck.json"

# Innsbruck: bekannte AT-Koordinate (liegt in der AT-Router-Box aus
# providers/region_routing.py: 46.3-49.1 lat, 9.5-17.2 lon; deckt zugleich
# ICON-D2 ab: 43-56 lat, 2-18 lon).
_INNSBRUCK = Location(latitude=47.26, longitude=11.39, name="Innsbruck")

# Alle bekannten Open-Meteo-Modell-IDs (Vorbild
# tests/tdd/test_issue_1142_geosphere_direct_fallback.py), fuer eine
# vorausgefuellte Availability-Cache-Datei, die den Auto-Probe-Seitenpfad in
# `fetch_forecast` (WEATHER-05b) ueberspringt.
_OM_ALL_MODEL_IDS = [
    "meteofrance_arome", "icon_d2", "metno_nordic", "icon_eu", "ecmwf_ifs04",
]


def _write_all_available_cache(path: Path) -> None:
    path.write_text(json.dumps({
        "probe_date": date.today().isoformat(),
        "models": {
            mid: {"available": [], "unavailable": []} for mid in _OM_ALL_MODEL_IDS
        },
    }))


# ---------------------------------------------------------------------------
# AC-1 — Guard: ForecastDataPoint.__post_init__ normalisiert aware -> naive UTC.
# ---------------------------------------------------------------------------

def test_ac1_forecast_datapoint_normalizes_aware_timestamp_to_naive():
    """AC-1: Given ein `ForecastDataPoint` wird mit einem timezone-aware
    Zeitstempel in einer Nicht-UTC-Zone konstruiert (+02:00, nicht bloss
    UTC-aware, um echte Konvertierung statt reinem tzinfo-Strip zu
    beweisen), When das Objekt erzeugt wird, Then ist `ts.tzinfo is None`
    und der UTC-Zeitwert bleibt korrekt erhalten (14:00+02:00 -> 12:00 naiv).

    RED heute: `ForecastDataPoint.__post_init__` (src/app/models.py:144)
    normalisiert nur `wind_dir_deg` -> `wind_direction_deg`, fasst `ts` gar
    nicht an — `dp.ts.tzinfo` bleibt die uebergebene `+02:00`-Zone statt
    `None`.
    """
    aware_cest = datetime(2026, 7, 22, 14, 0, tzinfo=timezone(timedelta(hours=2)))

    dp = ForecastDataPoint(ts=aware_cest)

    assert dp.ts.tzinfo is None, (
        f"AC-1: ts.tzinfo muss nach Konstruktion None sein (naive UTC) — "
        f"war {dp.ts.tzinfo!r}."
    )
    assert dp.ts == datetime(2026, 7, 22, 12, 0), (
        "AC-1: 14:00+02:00 (CEST) muss als 12:00 UTC (naiv) ankommen — "
        f"echte Konvertierung, kein reiner tzinfo-Strip. War {dp.ts!r}."
    )


# ---------------------------------------------------------------------------
# AC-2 — Bug-Repro (deterministischer Kern): primaerer Open-Meteo-Pfad
# liefert naive Zeitstempel, `_aggregate_for_segment` vergleicht sie gegen
# aware Segment-Fenstergrenzen -> TypeError (der echte Prod-Crash).
# ---------------------------------------------------------------------------

# Erfolgreiche Open-Meteo-Antwort mit NAIVEN Zeitstempeln (kein "Z"-Suffix) —
# genau das Format, das Open-Meteo bei `timezone=UTC`-Requests tatsaechlich
# liefert (`providers/openmeteo.py:857`, `_parse_response` Zeile 725 parst
# `time_str` unveraendert -> `datetime.fromisoformat` bleibt naiv).
_OPENMETEO_SUCCESS_PAYLOAD = {
    "hourly": {
        "time": ["2026-07-22T14:00", "2026-07-22T15:00"],
        "temperature_2m": [18.5, 17.9],
        "wind_speed_10m": [12.0, 14.5],
    }
}


def _openmeteo_success_transport(request: httpx.Request) -> httpx.Response:
    """Beantwortet NUR den ICON-D2-Forecast-Endpoint (primaeres Modell fuer
    Innsbruck, `/v1/dwd-icon`) mit einer erfolgreichen, naiv-zeitgestempelten
    Antwort; alle anderen Endpoints (u.a. `/v1/air-quality` fuer UV) liefern
    404 — `_fetch_uv_data` faengt das intern ab (kein Verhaltensbruch fuer
    diesen Test, s. `providers/openmeteo.py:680-685`)."""
    if request.url.path == "/v1/dwd-icon":
        return httpx.Response(200, json=_OPENMETEO_SUCCESS_PAYLOAD)
    return httpx.Response(404, json={"detail": "not found (test seam)"})


def test_ac2_openmeteo_primary_path_naive_ts_crashes_against_aware_segment(
    monkeypatch, tmp_path
):
    """AC-2 (Bug-Repro, ersetzt v1.0-Fallback-Test): Given Open-Meteo
    antwortet erfolgreich (HTTP 200) mit naiven Datenpunkten fuer den
    primaeren Provider-Pfad UND ein regulaeres `TripSegment` hat aware UTC
    `start_time`/`end_time` (wie von `_validate_segment` erzwungen), When
    `SegmentWeatherService.fetch_segment_weather` fuer dieses Segment laeuft,
    Then liefert der Service Wetterdaten OHNE `TypeError`
    ("can't compare offset-naive and offset-aware datetimes").

    ROT heute: `_aggregate_for_segment` (`segment_weather.py:246-247`)
    berechnet `start_floor`/`end_floor` direkt aus dem aware
    `segment.start_time`/`.end_time` OHNE `.replace(tzinfo=None)` und
    vergleicht sie gegen `dp.ts`, das vom primaeren Open-Meteo-Pfad naiv
    ankommt (`_parse_response` normalisiert `ts` nicht auf aware) — der
    Vergleich `start_floor <= dp.ts < end_floor` wirft `TypeError`, BEVOR
    er von `fetch_segment_weather`s `except ProviderRequestError`-Block
    (der nur den Provider-Aufruf selbst umschliesst, nicht die
    Aggregation danach) abgefangen werden koennte. Genau dieser Crash war
    der Prod-Vorfall aus Issue #1345 — kein Retry greift, das Briefing
    zeigt "Wetterdaten nicht verfuegbar" trotz technisch erreichbarem und
    liefernden primaeren Provider.
    """
    cache_path = tmp_path / "model_availability.json"
    _write_all_available_cache(cache_path)
    monkeypatch.setattr("providers.openmeteo.AVAILABILITY_CACHE_PATH", cache_path)
    monkeypatch.setattr(
        "providers.openmeteo.DIAGNOSTICS_PATH", tmp_path / "openmeteo_calls.jsonl"
    )
    # Tenacity-Backoff neutralisieren (Verteidigung gegen unerwartete
    # Retry-Pfade, aendert nur Timing, nicht die Retry-Entscheidung selbst).
    monkeypatch.setattr(OpenMeteoProvider._request.retry, "wait", tenacity.wait_none())
    monkeypatch.setattr(
        OpenMeteoProvider._request.retry, "stop", tenacity.stop_after_attempt(1)
    )

    om_provider = OpenMeteoProvider()
    om_provider._client = httpx.Client(
        transport=httpx.MockTransport(_openmeteo_success_transport)
    )

    # Segment-Fenster exakt an die beiden naiven Zeitstempel der Fixture-
    # Antwort angelegt, aber als AWARE UTC (wie `_validate_segment` verlangt).
    segment = TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=_INNSBRUCK.latitude, lon=_INNSBRUCK.longitude, elevation_m=800),
        end_point=GPXPoint(lat=_INNSBRUCK.latitude, lon=_INNSBRUCK.longitude, elevation_m=800),
        start_time=datetime(2026, 7, 22, 14, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 7, 22, 15, 0, tzinfo=timezone.utc),
        duration_hours=1.0,
        distance_km=2.0,
        ascent_m=100,
        descent_m=0,
    )

    service = SegmentWeatherService(om_provider)

    # KEIN pytest.raises hier: AC-2 beschreibt das GEWUENSCHTE Verhalten
    # (Wetterdaten ohne TypeError). Vor dem Fix crasht dieser Aufruf mit
    # `TypeError: can't compare offset-naive and offset-aware datetimes`
    # direkt in `_aggregate_for_segment` -- pytest meldet das als Fehler
    # (ROT) mit genau dieser Meldung im Traceback. Nach dem Fix liefert der
    # Aufruf regulaer ein `SegmentWeatherData` mit gefuellten Metriken.
    result = service.fetch_segment_weather(
        segment, enrich_ensemble=False, enrich_snow=False
    )

    assert result.has_error is False, (
        "AC-2: der primaere Open-Meteo-Pfad muss Wetterdaten liefern, kein "
        f"Fehler-Platzhalter — error_message={result.error_message!r}."
    )
    assert result.aggregated.temp_min_c is not None, (
        "AC-2: aggregierte Metriken (mind. temp_min_c) muessen aus der "
        "Open-Meteo-Antwort befuellt sein — Briefing darf NICHT "
        "'Wetterdaten nicht verfuegbar' zeigen."
    )


# ---------------------------------------------------------------------------
# AC-3 — GeoSphere Cloud-Layer: Sommerzeit (CEST) korrekt statt hartkodiert UTC+1.
# ---------------------------------------------------------------------------

def test_ac3_geosphere_cloud_layer_summer_dst_offset(monkeypatch, tmp_path):
    """AC-3: Given eine GeoSphere-Cloud-Layer-Antwort (Open-Meteo, ueber
    `_fetch_openmeteo_clouds`) im Sommer (CEST = UTC+2) mit lokaler Wiener
    Zeit "14:00", When die Zeit in UTC umgerechnet wird, Then ist das
    Ergebnis "12:00 UTC" (nicht "13:00 UTC", wie es die hartkodierte
    UTC+1-Annahme in `src/providers/geosphere.py:397-400` liefern wuerde).

    RED heute: `_fetch_openmeteo_clouds` haengt IMMER
    `timezone(timedelta(hours=1))` an naive Wiener Zeiten an (Sommer-CEST
    ignoriert) — `.astimezone(timezone.utc)` auf das Ergebnis liefert daher
    13:00 statt 12:00.
    """
    monkeypatch.setattr(
        "providers.call_log.DIAGNOSTICS_PATH", tmp_path / "openmeteo_calls.jsonl"
    )
    summer_local_time_str = "2026-07-15T14:00"  # Sommer, Wien lokal (CEST = UTC+2)
    response_payload = {
        "hourly": {
            "time": [summer_local_time_str],
            "cloud_cover_low": [40],
            "cloud_cover_mid": [20],
            "cloud_cover_high": [10],
        }
    }

    def _clouds_transport(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=response_payload)

    provider = GeoSphereProvider(
        client=httpx.Client(transport=httpx.MockTransport(_clouds_transport))
    )
    result = provider._fetch_openmeteo_clouds(47.26, 11.39, hours=1)

    assert result, (
        "AC-3 Vorbedingung: _fetch_openmeteo_clouds muss mindestens einen "
        "Eintrag liefern, sonst beweist der Offset-Vergleich unten nichts."
    )
    [raw_ts] = result.keys()
    utc_ts = raw_ts.astimezone(timezone.utc)

    assert utc_ts.hour == 12, (
        "AC-3: Sommer-Lokalzeit 14:00 (CEST = UTC+2) muss zu 12:00 UTC "
        f"werden — war {utc_ts.isoformat()} (Rohwert vor Konvertierung: "
        f"{raw_ts.isoformat()}, hartkodierte UTC+1-Annahme liefert 13:00)."
    )


# ---------------------------------------------------------------------------
# AC-4 — Regressionstest: 503->503->200-Retry bleibt unveraendert (darf GRUEN sein).
# ---------------------------------------------------------------------------

class _FlakyFakeProvider:
    """Test-lokaler Fake-Provider (kein Mock()/patch()/MagicMock): liefert
    ueber ein echtes Zaehler-Attribut deterministisch 503 fuer die ersten
    `fail_times` Aufrufe, danach echte Erfolgsdaten. Testet die ECHTE
    Retry-Schleife in `TripReportSchedulerService._fetch_weather`, nicht
    deren Nachbau."""

    def __init__(self, fail_times: int) -> None:
        self._fail_times = fail_times
        self.calls = 0

    @property
    def name(self) -> str:
        return "fake"

    def fetch_forecast(self, location, start=None, end=None, enrich_ensemble=True, enrich_snow=True):
        self.calls += 1
        if self.calls <= self._fail_times:
            raise ProviderRequestError(
                "fake", "503 Service Unavailable (test seam)", status_code=503
            )
        dp = ForecastDataPoint(ts=start, t2m_c=12.0, wind10m_kmh=8.0)
        return NormalizedTimeseries(
            meta=ForecastMeta(
                provider=Provider.OPENMETEO,
                model="fake",
                run=datetime.now(timezone.utc),
                grid_res_km=1.0,
            ),
            data=[dp],
        )


def test_ac4_retry_succeeds_after_two_transient_errors(monkeypatch):
    """AC-4 (Regressionsschutz): Given der Wetter-Fetch schlaegt zweimal mit
    einem transienten 503-Fehler fehl und gelingt beim dritten Versuch,
    When `TripReportSchedulerService._fetch_weather` mit der bestehenden
    Retry-Schleife (`FETCH_RETRY_ATTEMPTS=2`, also 3 Versuche gesamt)
    aufgerufen wird, Then wird das Segment nach den ersten beiden
    transienten Fehlversuchen erfolgreich mit Wetterdaten befuellt
    (has_error=False), OHNE dass sich das Retry-Verhalten selbst aendert.

    Dieser Test darf bereits GRUEN sein: die Retry-Logik
    (`_is_transient_fetch_error`, `FETCH_RETRY_ATTEMPTS`) existiert
    unveraendert und ist von der Timestamp-Normalisierung (AC-1..AC-3)
    unabhaengig — er dient als Regressionsschutz, damit der #1345-Fix das
    bestehende Retry-Verhalten nicht versehentlich veraendert.
    """
    monkeypatch.setattr(time, "sleep", lambda seconds: None)

    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    segment = TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=47.26, lon=11.39, elevation_m=800),
        end_point=GPXPoint(lat=47.27, lon=11.40, elevation_m=900),
        start_time=now + timedelta(hours=2),
        end_time=now + timedelta(hours=3),
        duration_hours=1.0,
        distance_km=2.0,
        ascent_m=100,
        descent_m=0,
    )

    fake_provider = _FlakyFakeProvider(fail_times=2)
    result = TripReportSchedulerService._fetch_weather(
        None, [segment], provider=fake_provider
    )

    assert fake_provider.calls == 3, (
        "AC-4: der Fake-Provider muss genau 3x aufgerufen werden (2 "
        f"transiente Fehlversuche + 1 Erfolg) — war {fake_provider.calls}x."
    )
    assert len(result) == 1
    assert result[0].has_error is False, (
        "AC-4: nach dem erfolgreichen dritten Versuch darf kein "
        f"Fehler-Platzhalter zurueckkommen — error_message="
        f"{result[0].error_message!r}."
    )


# ---------------------------------------------------------------------------
# AC-5 — Regressionsschutz: GeoSphere-AT-Fallback bleibt gruen (Issue #1142).
# ---------------------------------------------------------------------------

def _openmeteo_total_outage_transport(request: httpx.Request) -> httpx.Response:
    """Jede Open-Meteo-Modellanfrage (AROME/ICON-D2/ICON-EU/ECMWF) schlaegt
    mit 503 fehl — simuliert den in #1141 verdrahteten Totalausfall-Seam."""
    return httpx.Response(503, json={"error": True, "reason": "Service Unavailable"})


def _geosphere_fixture_transport(request: httpx.Request) -> httpx.Response:
    """Beantwortet NUR den NWP-Endpoint mit der echten, aufgezeichneten
    GeoSphere-Antwort (`geosphere_nwp_innsbruck.json`); der SNOWGRID-Endpoint
    liefert 404 (fetch_snowgrid faengt httpx.HTTPStatusError intern ab und
    liefert (None, None) — kein Verhaltensbruch fuer diesen Test)."""
    if "nwp-v1-1h-2500m" in request.url.path:
        payload = json.loads(_GEOSPHERE_NWP_FIXTURE.read_text())
        return httpx.Response(200, json=payload)
    return httpx.Response(404, json={"detail": "not found (test seam)"})


def test_ac5_geosphere_fallback_regression_stays_green(monkeypatch, tmp_path):
    """AC-5 (Regressionsschutz, neu in v2.0): Given Open-Meteo hat einen
    Totalausfall (alle Modelle 503) UND GeoSphere liefert am
    Fallback-Seam (`at_direct`, #1142) eine echte, aufgezeichnete Antwort
    fuer eine AT-Koordinate (aware Zeitstempel), When ein Segment fuer
    diese Koordinate abgerufen wird, Then liefert
    `SegmentWeatherService.fetch_segment_weather` vollstaendige Wetterdaten
    (has_error=False, aggregierte Metriken gesetzt) statt eines
    Fehler-Platzhalters ("Wetterdaten nicht verfuegbar").

    Dieser Pfad ist HEUTE bereits GRUEN (`TripSegment.start_time`/`.end_time`
    sind ueber `_validate_segment` immer aware UTC; GeoSphere liefert
    ebenfalls aware `ts` — beide Seiten von `start_floor <= dp.ts <
    end_floor` sind aware/aware und vergleichen sich klaglos). Der Test
    stellt sicher, dass die Normalisierung aus AC-2 (naive UTC als
    einheitliche Provider-Grenze in `ForecastDataPoint.__post_init__` PLUS
    `.replace(tzinfo=None)` auf `start_floor`/`end_floor` in
    `_aggregate_for_segment`) diesen bereits funktionierenden Fallback-Pfad
    NICHT bricht — GeoSphere's aware `ts` wird durch den AC-1-Fix ebenfalls
    naiv, muss aber weiterhin gegen die (dann ebenfalls naiven)
    Fensterrenzen vergleichbar bleiben. Bleibt Abnahme-Vorlage fuer
    #1143/#1144.
    """
    om_provider = OpenMeteoProvider()
    om_provider._client = httpx.Client(
        transport=httpx.MockTransport(_openmeteo_total_outage_transport)
    )
    monkeypatch.setattr(OpenMeteoProvider._request.retry, "wait", tenacity.wait_none())
    monkeypatch.setattr(
        OpenMeteoProvider._request.retry, "stop", tenacity.stop_after_attempt(1)
    )
    monkeypatch.setattr(
        "providers.openmeteo.DIAGNOSTICS_PATH", tmp_path / "openmeteo_calls.jsonl"
    )

    def _fixture_geosphere_provider():
        return GeoSphereProvider(
            client=httpx.Client(transport=httpx.MockTransport(_geosphere_fixture_transport))
        )

    monkeypatch.setattr(
        "providers.regional_stubs.GeoSphereProvider", _fixture_geosphere_provider
    )

    fixture_payload = json.loads(_GEOSPHERE_NWP_FIXTURE.read_text())
    ts_start = datetime.fromisoformat(fixture_payload["timestamps"][1])
    ts_end = datetime.fromisoformat(fixture_payload["timestamps"][3])

    segment = TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=_INNSBRUCK.latitude, lon=_INNSBRUCK.longitude, elevation_m=800),
        end_point=GPXPoint(lat=_INNSBRUCK.latitude, lon=_INNSBRUCK.longitude, elevation_m=800),
        start_time=ts_start,
        end_time=ts_end,
        duration_hours=2.0,
        distance_km=4.0,
        ascent_m=200,
        descent_m=0,
    )

    service = SegmentWeatherService(om_provider)
    result = service.fetch_segment_weather(segment, enrich_ensemble=False)

    assert result.has_error is False, (
        "AC-5: der Fallback muss Wetterdaten liefern, kein "
        f"Fehler-Platzhalter — error_message={result.error_message!r}."
    )
    assert result.aggregated.temp_min_c is not None, (
        "AC-5: aggregierte Metriken (mind. temp_min_c) muessen aus der "
        "GeoSphere-Fixture befuellt sein — Briefing darf NICHT "
        "'Wetterdaten nicht verfuegbar' zeigen."
    )


# ---------------------------------------------------------------------------
# F001 — Fix-Loop-Guard: Adversary-Fund aus dem #1345-Review. Der
# Cache-Hit-Pfad (`fetch_segment_weather` Zeile 143-149) erreicht
# `_validate_segment` NIE -- ein Segment kann daher mit aware
# Fenstergrenzen in einer Nicht-UTC-Zone (z.B. +02:00) bei
# `_aggregate_for_segment` ankommen. Ein reines `.replace(tzinfo=None)`
# (ohne vorherige `.astimezone(timezone.utc)`) missdeutet die lokale
# Uhrzeit als UTC und trifft die falsche Stunde.
# ---------------------------------------------------------------------------

def test_f001_aggregate_for_segment_converts_non_utc_offset_before_flooring():
    """F001: Given ein Segment mit AWARE Fenstergrenzen in einer
    Nicht-UTC-Zone (+02:00) -- wie es der Cache-Hit-Pfad liefern kann, der
    `_validate_segment` nie durchlaeuft --, When
    `_aggregate_for_segment` die Stundenfenster berechnet, Then werden
    `start_floor`/`end_floor` ECHT nach UTC konvertiert (nicht nur
    tzinfo-gestrippt), sodass die Aggregation den korrekten UTC-Datenpunkt
    trifft statt eines falschen.

    ROT vor dem Fix: ein reines `.replace(tzinfo=None)` deutet
    "16:00+02:00" als "16:00 UTC" statt korrekt als "14:00 UTC" -- die
    Aggregation greift dann den falschen (Sentinel-)Datenpunkt (99.0 statt
    5.0 Grad).
    """
    aware_offset = timezone(timedelta(hours=2))
    segment = TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=47.26, lon=11.39, elevation_m=800),
        end_point=GPXPoint(lat=47.27, lon=11.40, elevation_m=900),
        start_time=datetime(2026, 7, 22, 16, 0, tzinfo=aware_offset),  # == 14:00 UTC
        end_time=datetime(2026, 7, 22, 17, 0, tzinfo=aware_offset),    # == 15:00 UTC
        duration_hours=1.0,
        distance_km=2.0,
        ascent_m=100,
        descent_m=0,
    )

    # Naive UTC Datenpunkte: der KORREKTE Treffer liegt bei 14:00 (temp=5.0);
    # ein Stundenfehlgriff durch reines Tzinfo-Strippen (16:00 statt 14:00
    # UTC) wuerde stattdessen den Sentinel-Wert 99.0 aggregieren.
    correct_point = ForecastDataPoint(ts=datetime(2026, 7, 22, 14, 0), t2m_c=5.0)
    wrong_sentinel_point = ForecastDataPoint(ts=datetime(2026, 7, 22, 16, 0), t2m_c=99.0)
    timeseries = NormalizedTimeseries(
        meta=ForecastMeta(
            provider=Provider.OPENMETEO,
            model="fake",
            run=datetime.now(timezone.utc),
            grid_res_km=1.0,
        ),
        data=[correct_point, wrong_sentinel_point],
    )

    service = SegmentWeatherService(OpenMeteoProvider())
    result = service._aggregate_for_segment(
        segment, timeseries, fetched_at=datetime.now(timezone.utc)
    )

    assert result.aggregated.temp_min_c == 5.0, (
        "F001: aware +02:00-Fenstergrenzen muessen ECHT nach UTC konvertiert "
        "werden (16:00+02:00 -> 14:00 UTC), bevor tzinfo gestrippt wird -- "
        f"war {result.aggregated.temp_min_c!r} (Sentinel-Wert 99.0 zeigt "
        "Strip-ohne-Konvertierung)."
    )

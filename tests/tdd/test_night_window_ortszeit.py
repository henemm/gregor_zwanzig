"""Fix #2223: Das Nachtfenster am Ziel endet um 06:00 ORTSZEIT (nicht UTC).

Kein Mock-Theater: ``_RecordingProvider`` ist ein echter Provider-Stellvertreter,
der die vom Dienst angefragten Fenster (start/end) festhält und stündliche
Daten zurückgibt. Geprüft wird, was beim Provider tatsächlich ankommt, also
dort, wo die Zusicherung wirkt (Kontingent = angefragte Stunden).

Jeder Test nutzt eigene Koordinaten, damit der geteilte Wetter-Cache keine
Anfrage eines anderen Tests bedient.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from app.models import (
    ForecastDataPoint, ForecastMeta, GPXPoint, NormalizedTimeseries, Provider,
    SegmentWeatherData, SegmentWeatherSummary, ThunderLevel, TripSegment,
)
from services.segment_weather import fetch_night_weather

UTC = timezone.utc


class _RecordingProvider:
    name = "recording-test-double"

    def __init__(self):
        self.requests: list[tuple[datetime, datetime]] = []

    def fetch_forecast(self, location, start=None, end=None,
                       enrich_ensemble=True, enrich_snow=True):
        self.requests.append((start, end))
        meta = ForecastMeta(
            provider=Provider.OPENMETEO, model="test", run=start,
            grid_res_km=1.0, interp="point_grid",
        )
        data = []
        ts = start.replace(minute=0, second=0, microsecond=0)
        while ts <= end:
            data.append(ForecastDataPoint(
                ts=ts, t2m_c=12.0, wind10m_kmh=5.0, gust_kmh=5.0,
                precip_1h_mm=0.0, pop_pct=0, cloud_total_pct=50,
                thunder_level=ThunderLevel.NONE, humidity_pct=55,
            ))
            ts += timedelta(hours=1)
        return NormalizedTimeseries(meta=meta, data=data)


def _last_segment(lat: float, lon: float, arrival_utc: datetime) -> SegmentWeatherData:
    seg = TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=lat, lon=lon, elevation_m=100.0),
        end_point=GPXPoint(lat=lat, lon=lon, elevation_m=100.0),
        start_time=arrival_utc - timedelta(hours=4), end_time=arrival_utc,
        duration_hours=4.0, distance_km=8.0, ascent_m=200.0, descent_m=0.0,
    )
    meta = ForecastMeta(
        provider=Provider.OPENMETEO, model="test", run=arrival_utc,
        grid_res_km=1.0, interp="point_grid",
    )
    return SegmentWeatherData(
        segment=seg, timeseries=NormalizedTimeseries(meta=meta, data=[]),
        aggregated=SegmentWeatherSummary(temp_min_c=10.0, temp_max_c=20.0),
        fetched_at=arrival_utc, provider="openmeteo",
    )


def _requested_end(seg: SegmentWeatherData) -> tuple[datetime, _RecordingProvider]:
    prov = _RecordingProvider()
    fetch_night_weather(seg, provider=prov, user_id="nutzer_nacht_a")
    assert prov.requests, "Der Provider wurde nie angefragt"
    return prov.requests[-1][1], prov


def test_ac1_utc_minus_5_ortsabend_endet_um_sechs_uhr_ortszeit():
    # Bogotá (UTC−5), Ankunft 20:00 Ortszeit = 01:00 UTC des Folgetags
    arrival = datetime(2026, 7, 21, 1, 0, tzinfo=UTC)
    end, prov = _requested_end(_last_segment(4.71, -74.07, arrival))
    start = prov.requests[-1][0]
    hours = (end - start).total_seconds() / 3600
    assert end == datetime(2026, 7, 21, 11, 0, tzinfo=UTC), f"Ende {end}"
    assert 9 <= hours <= 11, f"{hours} h angefragt, erwartet ca. 10 (nicht ca. 29)"


@pytest.mark.parametrize("lat,lon,tzname,arrival,expected_end_utc", [
    (39.65, 2.91, "Europe/Madrid", datetime(2026, 7, 20, 15, 0, tzinfo=UTC),
     datetime(2026, 7, 21, 4, 0, tzinfo=UTC)),   # Mallorca Sommer UTC+2
    (39.66, 2.92, "Europe/Madrid", datetime(2026, 12, 10, 15, 0, tzinfo=UTC),
     datetime(2026, 12, 11, 5, 0, tzinfo=UTC)),  # Mallorca Winter UTC+1
    (42.03, 9.03, "Europe/Paris", datetime(2026, 7, 20, 15, 0, tzinfo=UTC),
     datetime(2026, 7, 21, 4, 0, tzinfo=UTC)),   # Korsika Sommer
    (42.04, 9.04, "Europe/Paris", datetime(2026, 12, 10, 15, 0, tzinfo=UTC),
     datetime(2026, 12, 11, 5, 0, tzinfo=UTC)),  # Korsika Winter
])
def test_ac2_europa_endet_um_sechs_uhr_ortszeit(lat, lon, tzname, arrival, expected_end_utc):
    end, _ = _requested_end(_last_segment(lat, lon, arrival))
    local = end.astimezone(ZoneInfo(tzname))
    assert (local.hour, local.minute) == (6, 0), f"Ende in Ortszeit {local}"
    assert end == expected_end_utc


def test_ac3_sommerzeit_umstellung_endet_exakt_sechs_uhr_ortszeit():
    # Madrid, Umstellung 28.03.2027 (CET -> CEST); Ankunft Vorabend 20:00 CET
    arrival = datetime(2027, 3, 27, 19, 0, tzinfo=UTC)
    end, _ = _requested_end(_last_segment(40.41, -3.70, arrival))
    local = end.astimezone(ZoneInfo("Europe/Madrid"))
    assert (local.year, local.month, local.day, local.hour, local.minute) == (2027, 3, 28, 6, 0)


def test_ac4_nicht_aufloesbare_zone_behaelt_utc_rueckfall():
    # (0, 0): Zeitzone nicht auflösbar bzw. UTC-gleich -> altes Ende 06:00 UTC am UTC-Datum+1
    arrival = datetime(2026, 7, 20, 15, 0, tzinfo=UTC)
    end, _ = _requested_end(_last_segment(0.0, 0.0, arrival))
    assert end == datetime(2026, 7, 21, 6, 0, tzinfo=UTC)


def test_ac5_versand_und_vorschau_liefern_dasselbe_fenster(monkeypatch):
    import providers.base as pbase
    from services.trip_report_scheduler import TripReportSchedulerService

    arrival = datetime(2026, 7, 21, 1, 0, tzinfo=UTC)
    seg_a = _last_segment(4.80, -74.10, arrival)
    seg_b = _last_segment(4.81, -74.11, arrival)

    versand_prov = _RecordingProvider()
    monkeypatch.setattr(pbase, "get_provider", lambda name: versand_prov)
    TripReportSchedulerService._fetch_night_weather(
        SimpleNamespace(_user_id="nutzer_nacht_a"), seg_a,
    )
    vorschau_end, _ = _requested_end(seg_b)

    assert versand_prov.requests, "Versand-Delegator hat den Provider nicht angefragt"
    assert versand_prov.requests[-1][1] == vorschau_end == datetime(2026, 7, 21, 11, 0, tzinfo=UTC)

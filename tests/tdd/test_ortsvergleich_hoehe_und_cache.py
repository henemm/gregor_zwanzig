"""TDD RED — Issue #1991: Ortsvergleichs-Höhe + höhenblinder Wetter-Cache.

Spec: docs/specs/modules/wegpunkt_hoehe_provider.md (AC-6, AC-7)
Context: docs/context/fix-1991-wegpunkt-hoehe.md

AC-6-Root-Cause: `CompareLocationWeatherSource.fetch()`
(compare_location_weather_source.py:150) baut das synthetische Segment mit
`GPXPoint(..., elevation_m=None)` HARTKODIERT — der Ortsvergleich verliert
die Höhe eines Orts (`SavedLocation.elevation_m`, Pflichtfeld) vor dem
Provider, unabhängig davon, ob AC-1 bereits implementiert ist.

AC-7-Root-Cause: `WeatherCacheService._bucket_key()` (weather_cache.py:226)
bildet den Cache-Schlüssel nur aus `{lat}_{lon}_{model_id}_{ens}_{snow}` —
OHNE Höhe. Ein Trip-Wegpunkt und ein Ortsvergleichs-Ort an DERSELBEN
Koordinate, aber mit unterschiedlicher Höhe, teilen sich deshalb denselben
Cache-Eintrag; wer zuerst fragt, bestimmt für die TTL-Dauer, was der andere
sieht.

MOCK-FREI: `httpx.MockTransport` (Vorbild test_provider_tz_normalization.py)
für AC-7; `monkeypatch.setattr("providers.base.get_provider", ...)` ersetzt
NUR die Netz-Werkseite durch einen echten, MockTransport-gestützten
`OpenMeteoProvider` (Vorbild `tests/tdd/test_compare_endpoint_user_id_mandantentrennung.py`
für den Zwei-Nutzer-Aufbau via `SavedLocation`).

AC-Test-Mapping:
| AC   | Testfunktion                                                              |
|------|-----------------------------------------------------------------------------|
| AC-6 | test_ac6_ortsvergleich_ort_traegt_seine_hoehe_fuer_zwei_nutzer            |
| AC-7 | test_ac7_gleiche_koordinate_unterschiedliche_hoehe_liefert_unterschiedliche_werte |
"""
from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import List
from urllib.parse import parse_qs

import httpx
import tenacity

from app.models import GPXPoint, TripSegment
from app.user import SavedLocation
from providers.openmeteo import OpenMeteoProvider
from services.compare_location_weather_source import CompareLocationWeatherSource
from services.segment_weather import SegmentWeatherService
from services.weather_cache import get_shared_weather_cache, reset_shared_weather_cache_for_tests
from utils.timezone import local_dt, tz_for_coords

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


def _prepare_availability(monkeypatch, tmp_path) -> None:
    cache_path = tmp_path / "model_availability.json"
    _write_all_available_cache(cache_path)
    monkeypatch.setattr("providers.openmeteo.AVAILABILITY_CACHE_PATH", cache_path)
    monkeypatch.setattr(
        "providers.openmeteo.DIAGNOSTICS_PATH", tmp_path / "openmeteo_calls.jsonl"
    )
    monkeypatch.setattr(OpenMeteoProvider._request.retry, "wait", tenacity.wait_none())
    monkeypatch.setattr(
        OpenMeteoProvider._request.retry, "stop", tenacity.stop_after_attempt(1)
    )


def _mittag_heute_am_ort(lat: float, lon: float) -> str:
    """N3-Nachbesserung: Kalendertag AM ORT, Mittagsstunde -- dieselbe
    Zeitzonen-Aufloesung wie `CompareLocationWeatherSource.fetch()`
    (`tz_for_coords` + `local_dt(datetime.now(timezone.utc), tz)`), damit der
    Zeitstempel IMMER im Default-Tagesfenster 4-19 Uhr liegt, unabhaengig
    davon, an welchem Kalendertag/zu welcher Uhrzeit der Testlauf startet.
    Ein fest verdrahtetes Datum (z. B. "2026-08-21") liegt ausserhalb dieses
    real-clock-basierten Fensters, sobald der Testlauf an einem anderen Tag
    stattfindet -- die Zeitreihe waere dann leer (ValueError) statt die
    Hoehe zu pruefen."""
    tz = tz_for_coords(lat, lon)
    heute = local_dt(datetime.now(timezone.utc), tz).date()
    return f"{heute.isoformat()}T12:00"


def _handler(seen: List[httpx.Request], lat: float, lon: float):
    def _respond(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={
            "hourly": {"time": [_mittag_heute_am_ort(lat, lon)], "temperature_2m": [5.0]}
        })
    return _respond


# ---------------------------------------------------------------------------
# AC-6
# ---------------------------------------------------------------------------


def test_ac6_ortsvergleich_ort_traegt_seine_hoehe_fuer_zwei_nutzer(monkeypatch, tmp_path):
    """AC-6: Given ein Ort im Ortsvergleich mit hinterlegter Höhe / When für
    diesen Ort Wetterdaten geholt werden / Then trägt die Anfrage dessen
    Höhe. Zwei verschiedene Nutzer mit je eigenem Ort + eigener Höhe, damit
    die Mandantentrennung mitgeprüft wird (Vorbild
    tests/tdd/test_compare_endpoint_user_id_mandantentrennung.py).

    ROT heute (fehlender Parameter): `CompareLocationWeatherSource.fetch()`
    kennt noch kein `elevation_m`-Schlüsselwort — der Aufruf bricht mit
    `TypeError` ab, BEVOR die hartkodierte `GPXPoint(elevation_m=None)`
    (compare_location_weather_source.py:150) überhaupt relevant wird.
    """
    _prepare_availability(monkeypatch, tmp_path)

    orte = {
        "alice": SavedLocation(
            id="alice-huette", name="Alice-Huette",
            lat=47.0614, lon=11.1211, elevation_m=3333,
            timezone="Europe/Vienna",
        ),
        "bob": SavedLocation(
            id="bob-tal", name="Bob-Tal",
            lat=47.26, lon=11.39, elevation_m=650,
            timezone="Europe/Vienna",
        ),
    }

    for user_id, loc in orte.items():
        seen: List[httpx.Request] = []

        def _fake_get_provider(name, _seen=seen, _loc=loc):
            assert name == "openmeteo"
            provider = OpenMeteoProvider()
            provider._client = httpx.Client(
                transport=httpx.MockTransport(_handler(_seen, _loc.lat, _loc.lon))
            )
            return provider

        monkeypatch.setattr("providers.base.get_provider", _fake_get_provider)

        source = CompareLocationWeatherSource()
        source.fetch(
            loc.id, loc.lat, loc.lon,
            elevation_m=loc.elevation_m,
        )

        main = [r for r in seen if r.url.host == "api.open-meteo.com"]
        assert main, f"kein Open-Meteo-Request fuer Nutzer {user_id} beobachtet"
        query = parse_qs(main[0].url.query.decode(), keep_blank_values=True)
        assert query.get("elevation") == [str(loc.elevation_m)], (
            f"AC-6 Nutzer {user_id}: Anfrage traegt nicht Hoehe {loc.elevation_m} "
            f"(war {query.get('elevation')!r}) -- "
            "compare_location_weather_source.py:150 setzt elevation_m hart auf None."
        )


def test_ac6_alarmlauf_ueber_compare_alert_service_traegt_hoehe(monkeypatch, tmp_path):
    """F005-Nachbesserung (Adversary Runde 2): AC-6 verlangt woertlich einen
    Test "ueber den Ortsvergleichs-Einstieg" -- der obige Test rief nur
    `CompareLocationWeatherSource.fetch()` DIREKT auf. Dieser Test steigt am
    ECHTEN Alarmlauf-Einstieg ein: `CompareAlertService._evaluate_one_location()`
    (compare_alert.py:435) -- dem einzigen produktiven Aufrufer des
    15-Minuten-Delta-Checks.

    ROT bei Mutation: wird `zusatz["elevation_m"]` aus compare_alert.py:435
    entfernt, traegt die abgesetzte Anfrage kein `elevation` mehr.
    """
    _prepare_availability(monkeypatch, tmp_path)
    from services.compare_alert import CompareAlertService
    from services.point_weather import AlertEvaluationConfig

    uid = "tdd-1991-f005-alarm"
    _clean_user(uid)
    try:
        loc = SavedLocation(
            id="alarm-ort", name="Alarm-Ort", lat=47.0614, lon=11.1211,
            elevation_m=3333, timezone="Europe/Vienna",
        )

        seen: List[httpx.Request] = []

        def _fake_get_provider(name, _seen=seen, _loc=loc):
            assert name == "openmeteo"
            provider = OpenMeteoProvider()
            provider._client = httpx.Client(
                transport=httpx.MockTransport(_handler(_seen, _loc.lat, _loc.lon))
            )
            return provider

        monkeypatch.setattr("providers.base.get_provider", _fake_get_provider)

        service = CompareAlertService(user_id=uid)
        service._evaluate_one_location(
            "cp-f005-alarm", loc.id, loc, AlertEvaluationConfig(), (4, 19),
        )

        main = [r for r in seen if r.url.host == "api.open-meteo.com"]
        assert main, "kein Open-Meteo-Request ueber den Alarmlauf-Einstieg beobachtet"
        query = parse_qs(main[0].url.query.decode(), keep_blank_values=True)
        assert query.get("elevation") == [str(loc.elevation_m)], (
            f"F005/AC-6 (Alarmlauf): Anfrage traegt nicht Hoehe {loc.elevation_m} "
            f"(war {query.get('elevation')!r}) -- compare_alert.py:435 reicht "
            "elevation_m nicht mehr durch."
        )
    finally:
        _clean_user(uid)


def test_ac6_versand_anker_ueber_scheduler_dispatch_traegt_hoehe(monkeypatch, tmp_path):
    """F005-Nachbesserung: der zweite echte Aufrufer von
    `CompareLocationWeatherSource.fetch()` ist `_write_compare_alert_snapshots()`
    (scheduler_dispatch_service.py:690-693) -- der Delta-Anker-Schreibpfad
    beim Report-Versand.

    ROT bei Mutation: wird `zusatz["elevation_m"]` aus
    scheduler_dispatch_service.py:690-693 entfernt, traegt die abgesetzte
    Anfrage kein `elevation` mehr.
    """
    _prepare_availability(monkeypatch, tmp_path)
    from services.scheduler_dispatch_service import _write_compare_alert_snapshots

    uid = "tdd-1991-f005-versand"
    _clean_user(uid)
    try:
        loc = SavedLocation(
            id="versand-ort", name="Versand-Ort", lat=47.26, lon=11.39,
            elevation_m=650, timezone="Europe/Vienna",
        )

        seen: List[httpx.Request] = []

        def _fake_get_provider(name, _seen=seen, _loc=loc):
            assert name == "openmeteo"
            provider = OpenMeteoProvider()
            provider._client = httpx.Client(
                transport=httpx.MockTransport(_handler(_seen, _loc.lat, _loc.lon))
            )
            return provider

        monkeypatch.setattr("providers.base.get_provider", _fake_get_provider)

        _write_compare_alert_snapshots(
            "cp-f005-versand", [loc], uid, {}, tage_ab_ortstag=0,
        )

        main = [r for r in seen if r.url.host == "api.open-meteo.com"]
        assert main, "kein Open-Meteo-Request ueber den Versand-Anker-Einstieg beobachtet"
        query = parse_qs(main[0].url.query.decode(), keep_blank_values=True)
        assert query.get("elevation") == [str(loc.elevation_m)], (
            f"F005/AC-6 (Versand-Anker): Anfrage traegt nicht Hoehe {loc.elevation_m} "
            f"(war {query.get('elevation')!r}) -- scheduler_dispatch_service.py:690-693 "
            "reicht elevation_m nicht mehr durch."
        )
    finally:
        _clean_user(uid)


def _clean_user(user_id: str) -> None:
    import shutil
    d = Path(__file__).resolve().parents[2] / "data" / "users" / user_id
    if d.exists():
        shutil.rmtree(d)


# ---------------------------------------------------------------------------
# AC-7
# ---------------------------------------------------------------------------


def test_ac7_gleiche_koordinate_unterschiedliche_hoehe_liefert_unterschiedliche_werte(
    monkeypatch, tmp_path
):
    """AC-7: Given ein Trip-Wegpunkt und ein Ortsvergleichs-Ort liegen auf
    derselben Koordinate, haben aber unterschiedliche Höhen / When beide
    nacheinander im selben Prozess abgefragt werden / Then bekommt jeder die
    Werte seiner eigenen Höhe.

    Der geteilte Prozess-Cache wird bewusst NUR EINMAL vor beiden Abrufen
    zurückgesetzt (nicht dazwischen) — die Kollision, die dieser Test zeigen
    soll, wäre sonst verdeckt (`reset_shared_weather_cache_for_tests`
    existiert, wird zwischen den beiden `fetch_segment_weather()`-Aufrufen
    ABSICHTLICH NICHT erneut aufgerufen).

    ROT heute: `weather_cache.py:226 (_bucket_key)` bildet den Schlüssel nur
    aus lat/lon/model_id/enrich-Flags — OHNE Höhe. Der zweite Abruf trifft
    denselben Bucket wie der erste (identische Koordinate, identisches
    Zeitfenster) und wird deshalb als Cache-HIT aus dem ersten Ergebnis
    bedient, statt einen eigenen Request abzusetzen.
    """
    reset_shared_weather_cache_for_tests()
    _prepare_availability(monkeypatch, tmp_path)

    seen: List[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        query = parse_qs(request.url.query.decode(), keep_blank_values=True)
        elevation = query.get("elevation", [None])[0]
        # Temperatur haengt (nach der Implementierung) sichtbar von der
        # Hoehe ab -- ohne Hoehe im Request bleibt sie beim Sentinelwert.
        temp = 20.0 if not elevation else (100.0 - float(elevation) / 100.0)
        return httpx.Response(200, json={
            "hourly": {"time": ["2026-08-21T12:00"], "temperature_2m": [temp]}
        })

    provider = OpenMeteoProvider()
    provider._client = httpx.Client(transport=httpx.MockTransport(handler))
    # BEWUSST kein explizites `cache=` -- SegmentWeatherService greift ohne
    # Angabe auf den GETEILTEN Prozess-Cache zurueck (Issue #1329-Default),
    # genau der Cache, den Trip- und Compare-Pfad sich in Produktion teilen.
    service = SegmentWeatherService(provider)

    lat, lon = 47.0614, 11.1211
    start = datetime(2026, 8, 21, 12, tzinfo=timezone.utc)
    end = datetime(2026, 8, 21, 13, tzinfo=timezone.utc)

    segment_trip = TripSegment(
        segment_id="trip-seg",
        start_point=GPXPoint(lat=lat, lon=lon, elevation_m=3333),
        end_point=GPXPoint(lat=lat, lon=lon, elevation_m=3333),
        start_time=start, end_time=end, duration_hours=1.0,
        distance_km=0.0, ascent_m=0, descent_m=0,
    )
    segment_compare = TripSegment(
        segment_id="compare-seg",
        start_point=GPXPoint(lat=lat, lon=lon, elevation_m=650),
        end_point=GPXPoint(lat=lat, lon=lon, elevation_m=650),
        start_time=start, end_time=end, duration_hours=1.0,
        distance_km=0.0, ascent_m=0, descent_m=0,
    )

    result_trip = service.fetch_segment_weather(
        segment_trip, enrich_ensemble=False, enrich_snow=False
    )
    result_compare = service.fetch_segment_weather(
        segment_compare, enrich_ensemble=False, enrich_snow=False
    )

    haupt_requests = [r for r in seen if r.url.host == "api.open-meteo.com"]
    assert len(haupt_requests) == 2, (
        f"AC-7: erwartet 2 echte Open-Meteo-Hauptvorhersage-Requests (eine je "
        f"Hoehe), beobachtet {len(haupt_requests)} -- der zweite Abruf wurde "
        "aus dem hoehenblinden Cache-Eintrag des ersten bedient statt einen "
        "eigenen Request abzusetzen (weather_cache.py:226 ignoriert die Hoehe "
        "im Bucket-Key)."
    )
    assert result_trip.aggregated.temp_max_c != result_compare.aggregated.temp_max_c, (
        f"AC-7: beide Ergebnisse sind identisch ({result_trip.aggregated.temp_max_c} °C) "
        "obwohl 3333 m (Trip) und 650 m (Ortsvergleich) angefragt wurden — "
        "der zweite Abruf hat das Ergebnis des ersten geerbt."
    )

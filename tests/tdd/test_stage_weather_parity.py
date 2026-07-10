"""
TDD RED -- Slice R1 (#1212): Python-Endpoint fuer Etappen-Wetter + Risiko.

Spec: docs/specs/modules/stage_weather_python_endpoint.md

Diese Datei prueft die SERVICE-Schicht `compute_stage_weather(trip, provider)`
direkt (kein HTTP), mit einem echten Test-Provider-Objekt (KEIN Mock!), der
je nach angefragter Koordinate eine vorab konstruierte NormalizedTimeseries
liefert. So durchlaufen die ECHTEN Bausteine (convert_trip_to_segments,
SegmentWeatherService, WindExpositionService, RiskEngine, aggregate_stage)
unveraendert -- nur die Wetter-Rohdaten sind Fixtures. Kein Mock-Theater:
_KeyedFakeProvider ist eine echte WeatherProvider-Implementierung (Protocol-
Erfuellung), analog zu RecordingProvider in
tests/tdd/test_issue_1005_trip_forecast_ssot.py.

RED-Phase: `src/services/stage_weather.py` existiert noch nicht.
Erwarteter Fehlschlag: ModuleNotFoundError / ImportError bei
`from services.stage_weather import compute_stage_weather`.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Optional

from app.models import ForecastDataPoint, ForecastMeta, NormalizedTimeseries, Provider
from app.trip import Stage, Trip, Waypoint
from providers.base import ProviderRequestError

TARGET_DATE = date(2026, 7, 15)

# Ocean-Koordinaten: tz_for_coords() findet dort keine Zeitzone und faellt
# fail-soft auf UTC zurueck (verifiziert), das erspart TZ-Arithmetik bei der
# Konstruktion der Segment-Zeitfenster.
_LOW_ELEV = 100.0        # unterhalb der Expositions-Schwelle (default 1500m)
_HIGH_ELEV = 1800.0      # oberhalb der Expositions-Schwelle


class _KeyedFakeProvider:
    """Reale WeatherProvider-Implementierung fuer Tests (KEIN unittest.mock).

    ``by_coord`` mappt exakte (lat, lon)-Paare auf ein Spezifikations-Dict fuer
    eine 24-Stunden-Tagesserie (konstante Werte ueber alle Stunden -- die
    Segment-Filterung in SegmentWeatherService arbeitet stundenbasiert, nicht
    datumsbasiert). Fehlt ein Key, wird ein echter ProviderRequestError
    geworfen -- simuliert einen echten Fetch-Fehler (AC-5).
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


def _wp(id_, lat, lon, elevation_m, arrival):
    return Waypoint(
        id=id_, name=id_, lat=lat, lon=lon, elevation_m=elevation_m,
        arrival_calculated=arrival,
    )


def _stage(id_, d, waypoints):
    return Stage(id=id_, name=id_, date=d, waypoints=waypoints)


def _trip(id_, stages):
    return Trip(id=id_, name=id_, stages=stages)


# ---------------------------------------------------------------------------
# AC-1: Response-Vertrag (Service-Ebene: dict-Struktur + explizites None)
# ---------------------------------------------------------------------------

def test_ac1_service_result_shape_and_explicit_none_field():
    """AC-1: Ergebnis-Dict traegt exakt weather_summary+risk; weather_summary
    traegt alle 6 Felder; ein fehlender Wert (hier: kein Wind) bleibt
    explizit None statt weggelassen zu werden."""
    from services.stage_weather import compute_stage_weather

    provider = _KeyedFakeProvider({
        (16.0, -30.0): {"wind10m_kmh": None, "t2m_c": 12.0, "precip_1h_mm": 1.0, "wmo_code": 3},
        (17.0, -30.0): {"wind10m_kmh": None, "t2m_c": 14.0, "precip_1h_mm": 0.5, "wmo_code": 2},
    })
    stage = _stage("s1", TARGET_DATE, [
        _wp("g1", 16.0, -30.0, _LOW_ELEV, "08:35"),
        _wp("g2", 17.0, -30.0, _LOW_ELEV, "10:35"),
    ])
    trip = _trip("trip-ac1", [stage])

    results = compute_stage_weather(trip, provider)

    result = results["s1"]
    assert result is not None
    assert set(result.keys()) == {"weather_summary", "risk"}, result.keys()
    ws = result["weather_summary"]
    assert set(ws.keys()) == {
        "temp_min_c", "temp_max_c", "wind_max_kmh", "precip_mm", "wmo_code", "is_day",
    }, ws.keys()
    assert "wind_max_kmh" in ws
    assert ws["wind_max_kmh"] is None, "Fehlender Wind-Wert muss explizit None sein, nicht weggelassen"
    assert ws["temp_min_c"] is not None
    assert result["risk"] in ("green", "yellow", "red")


# ---------------------------------------------------------------------------
# AC-2: Risiko = max ueber Segmente (Briefing-Paritaet)
# ---------------------------------------------------------------------------

def test_ac2_stage_risk_is_max_over_segments():
    """AC-2: genau ein Segment HIGH (>70 km/h Wind), das andere green -> die
    Etappe ist 'red' (das Maximum ueber die Segmente)."""
    from services.stage_weather import compute_stage_weather

    wp0 = _wp("g1", 0.0, -30.0, _LOW_ELEV, "08:00")   # Leg-Segment: Wind 100 -> HIGH
    wp1 = _wp("g2", 1.0, -30.0, _LOW_ELEV, "10:00")   # Ziel-Segment: Wind 5 -> LOW
    stage = _stage("s1", TARGET_DATE, [wp0, wp1])
    trip = _trip("trip-ac2", [stage])

    provider = _KeyedFakeProvider({
        (0.0, -30.0): {"wind10m_kmh": 100.0},
        (1.0, -30.0): {"wind10m_kmh": 5.0},
    })

    results = compute_stage_weather(trip, provider)

    assert "s1" in results
    assert results["s1"] is not None
    assert results["s1"]["risk"] == "red", (
        f"Erwartete 'red' (max ueber Segmente), sah {results['s1']}"
    )


# ---------------------------------------------------------------------------
# AC-3: Grenzwert 70,0 -> gelb (Python-Semantik '> high')
# ---------------------------------------------------------------------------

def test_ac3_wind_exactly_70_is_yellow_not_red():
    """AC-3: Wind/Boe exakt 70,0 km/h -> 'yellow' (nicht 'red'), weil Python
    '> high' verlangt (Go war '>= high')."""
    from services.stage_weather import compute_stage_weather

    wp0 = _wp("g1", 2.0, -30.0, _LOW_ELEV, "08:05")
    wp1 = _wp("g2", 3.0, -30.0, _LOW_ELEV, "10:05")
    stage = _stage("s1", TARGET_DATE, [wp0, wp1])
    trip = _trip("trip-ac3", [stage])

    provider = _KeyedFakeProvider({
        (2.0, -30.0): {"wind10m_kmh": 70.0, "gust_kmh": 70.0},
        (3.0, -30.0): {"wind10m_kmh": 70.0, "gust_kmh": 70.0},
    })

    results = compute_stage_weather(trip, provider)

    assert results["s1"] is not None
    assert results["s1"]["risk"] == "yellow", (
        f"Bei exakt 70,0 km/h muss 'yellow' gelten (nicht 'red'), sah {results['s1']}"
    )


# ---------------------------------------------------------------------------
# AC-4: Wind-Exposition (Regel 9) escaliert gegenueber identischem
# nicht-exponierten Segment
# ---------------------------------------------------------------------------

def test_ac4_wind_exposition_escalates_vs_non_exposed():
    """AC-4: Exponiertes Segment (Hoehe >= 1500m) + Wind im Expositions-Band
    (30-50 km/h) wird hoeher eingestuft als ein identisches, nicht-exponiertes
    Segment mit demselben Wind."""
    from services.stage_weather import compute_stage_weather

    provider = _KeyedFakeProvider({
        (4.0, -30.0): {"wind10m_kmh": 35.0},
        (5.0, -30.0): {"wind10m_kmh": 35.0},
        (6.0, -30.0): {"wind10m_kmh": 35.0},
        (7.0, -30.0): {"wind10m_kmh": 35.0},
    })

    exposed_stage = _stage("exposed", TARGET_DATE, [
        _wp("g1", 4.0, -30.0, _HIGH_ELEV, "08:10"),
        _wp("g2", 5.0, -30.0, _HIGH_ELEV, "10:10"),
    ])
    non_exposed_stage = _stage("plain", TARGET_DATE, [
        _wp("g1", 6.0, -30.0, _LOW_ELEV, "08:15"),
        _wp("g2", 7.0, -30.0, _LOW_ELEV, "10:15"),
    ])
    trip = _trip("trip-ac4", [exposed_stage, non_exposed_stage])

    results = compute_stage_weather(trip, provider)

    assert results["plain"] is not None
    assert results["plain"]["risk"] == "green", (
        f"Nicht-exponiert bei 35 km/h muss green bleiben, sah {results['plain']}"
    )
    assert results["exposed"] is not None
    assert results["exposed"]["risk"] != "green", (
        f"Exponiert bei 35 km/h muss ueber green liegen (Regel 9), sah {results['exposed']}"
    )
    assert results["exposed"]["risk"] != results["plain"]["risk"], (
        "Exposition (Regel 9) muss das exponierte Segment hoeher einstufen als das "
        "identische, nicht-exponierte Segment"
    )


# ---------------------------------------------------------------------------
# AC-5: Fail-soft pro Etappe
# ---------------------------------------------------------------------------

def test_ac5_fail_soft_per_stage():
    """AC-5: Etappen ohne Datum / ohne Waypoints / mit fehlschlagendem Fetch
    werden einzeln zu None, ohne dass gueltige Etappen betroffen sind."""
    from services.stage_weather import compute_stage_weather

    provider = _KeyedFakeProvider({
        (8.0, -30.0): {"wind10m_kmh": 10.0},
        (9.0, -30.0): {"wind10m_kmh": 10.0},
    })

    ok_stage = _stage("ok", TARGET_DATE, [
        _wp("g1", 8.0, -30.0, _LOW_ELEV, "08:20"),
        _wp("g2", 9.0, -30.0, _LOW_ELEV, "10:20"),
    ])
    # Stage ohne Datum (date=None) -- Python erzwingt den Typehint nicht, dies
    # bildet den in der Spec beschriebenen Fail-soft-Trigger "date fehlt" ab.
    no_date_stage = Stage(
        id="no_date", name="no_date", date=None,  # type: ignore[arg-type]
        waypoints=[
            _wp("g1", 8.0, -30.0, _LOW_ELEV, "08:20"),
            _wp("g2", 9.0, -30.0, _LOW_ELEV, "10:20"),
        ],
    )
    zero_wp_stage = _stage("zero_wp", TARGET_DATE, [])
    # Koordinaten ohne Fixture-Eintrag -> echter ProviderRequestError bei jedem Segment.
    fetch_fails_stage = _stage("fetch_fails", TARGET_DATE, [
        _wp("g1", 10.0, -30.0, _LOW_ELEV, "08:20"),
        _wp("g2", 11.0, -30.0, _LOW_ELEV, "10:20"),
    ])

    trip = _trip("trip-ac5", [ok_stage, no_date_stage, zero_wp_stage, fetch_fails_stage])

    results = compute_stage_weather(trip, provider)

    assert results["ok"] is not None
    assert results["ok"]["risk"] in ("green", "yellow", "red")
    assert results["no_date"] is None
    assert results["zero_wp"] is None
    assert results["fetch_fails"] is None


# ---------------------------------------------------------------------------
# AC-6: Leere Stage-ID wird komplett uebersprungen
# ---------------------------------------------------------------------------

def test_ac6_empty_stage_id_skipped():
    """AC-6: Eine Etappe mit leerer ID erzeugt KEINEN Schluessel im Ergebnis."""
    from services.stage_weather import compute_stage_weather

    provider = _KeyedFakeProvider({
        (12.0, -30.0): {"wind10m_kmh": 10.0},
        (13.0, -30.0): {"wind10m_kmh": 10.0},
        (14.0, -30.0): {"wind10m_kmh": 10.0},
        (15.0, -30.0): {"wind10m_kmh": 10.0},
    })

    empty_id_stage = _stage("", TARGET_DATE, [
        _wp("g1", 12.0, -30.0, _LOW_ELEV, "08:25"),
        _wp("g2", 13.0, -30.0, _LOW_ELEV, "10:25"),
    ])
    valid_stage = _stage("valid", TARGET_DATE, [
        _wp("g1", 14.0, -30.0, _LOW_ELEV, "08:30"),
        _wp("g2", 15.0, -30.0, _LOW_ELEV, "10:30"),
    ])
    trip = _trip("trip-ac6", [empty_id_stage, valid_stage])

    results = compute_stage_weather(trip, provider)

    assert "" not in results, "Etappe mit leerer ID darf keinen Schluessel im Ergebnis erzeugen"
    assert "valid" in results
    assert len(results) == 1, f"Erwartete genau 1 Ergebnis-Eintrag, sah {list(results.keys())}"


# ---------------------------------------------------------------------------
# F001 (Adversary, Issue #1212): eine kaputte Segmentbildung darf nicht die
# gesamte Antwort (alle Etappen) mit einer ungefangenen Exception reissen.
# ---------------------------------------------------------------------------

def test_f001_broken_segment_build_does_not_crash_other_stages():
    """F001: Stage B hat einen Waypoint mit lat=None/lon=None -- die
    Segmentbildung (convert_trip_to_segments -> haversine_km) wirft dort
    einen TypeError. Erwartet: results['B'] ist None, results['A'] bleibt
    unberuehrt, KEINE Exception propagiert aus compute_stage_weather."""
    from services.stage_weather import compute_stage_weather

    provider = _KeyedFakeProvider({
        (18.0, -30.0): {"wind10m_kmh": 10.0},
        (19.0, -30.0): {"wind10m_kmh": 10.0},
    })

    stage_a = _stage("A", TARGET_DATE, [
        _wp("g1", 18.0, -30.0, _LOW_ELEV, "08:40"),
        _wp("g2", 19.0, -30.0, _LOW_ELEV, "10:40"),
    ])
    stage_b = _stage("B", TARGET_DATE, [
        _wp("g1", None, None, _LOW_ELEV, "08:45"),  # type: ignore[arg-type]
        _wp("g2", 19.5, -30.0, _LOW_ELEV, "10:45"),
    ])
    trip = _trip("trip-f001", [stage_a, stage_b])

    results = compute_stage_weather(trip, provider)

    assert results["B"] is None, f"Kaputte Segmentbildung muss die Stage auf None setzen, sah {results['B']}"
    assert results["A"] is not None, "Eine kaputte Stage darf andere Stages nicht mitreissen"
    assert results["A"]["risk"] in ("green", "yellow", "red")

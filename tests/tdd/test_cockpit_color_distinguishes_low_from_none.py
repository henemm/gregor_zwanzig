"""TDD RED -- Issue #1474b (Folge-Scheibe zu #1474 S3), Haelfte B.

SPEC: docs/specs/modules/fix_1474b_gewitterschwelle_cockpit.md, Abschnitt
"Haelfte B" + AC-2/AC-3/AC-4.

`services/stage_weather.py::_compute_one_stage()` faerbt eine Etappe heute
nur nach der HOECHSTEN Risikostufe (`RiskLevel`). `get_max_risk_level()`
liefert bei einer LEEREN Risikoliste ebenfalls `RiskLevel.LOW`
(`risk_engine.py:113-116`) -- "kein Risiko vorhanden" und "Risiko der Stufe
leicht" (Gewitter LOW, seit #1474) sind auf Etappen-Ebene deshalb heute NICHT
unterscheidbar, beide werden gruen. Diese Datei belegt: die risikofreie
Etappe bleibt gruen (AC-2, Regression, Waechter gegen die naive
Ein-Zeilen-Loesung `_RISK_TO_COLOR[RiskLevel.LOW] = "yellow"`), eine Etappe
mit ausschliesslich `ThunderLevel.LOW` muss kuenftig gelb werden (AC-3, rot),
MED/HIGH bleiben unveraendert gelb/rot (AC-4, muss gruen sein).

Keine Mocks: `_KeyedThunderFakeProvider` ist eine echte
`WeatherProvider`-Implementierung (Protocol-Erfuellung, analog
`_KeyedFakeProvider` in `tests/tdd/test_stage_weather_parity.py`), die
ECHTEN Bausteine (convert_trip_to_segments, SegmentWeatherService,
WindExpositionService, RiskEngine, aggregate_stage) durchlaufen unveraendert
-- nur die Wetter-Rohdaten sind Fixtures. Kein Netz.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Optional

from app.models import (
    ForecastDataPoint,
    ForecastMeta,
    NormalizedTimeseries,
    Provider,
    ThunderLevel,
)
from app.trip import Stage, Trip, Waypoint

TARGET_DATE = date(2026, 7, 15)
_LOW_ELEV = 100.0  # unterhalb der Expositions-Schwelle (default 1500m)


class _KeyedThunderFakeProvider:
    """Reale WeatherProvider-Implementierung (KEIN unittest.mock).

    ``by_coord`` mappt exakte (lat, lon)-Paare auf ein Spezifikations-Dict.
    Alle 24 Stunden des angefragten Tages tragen konstant dieselben Werte
    (Wind/Boe niedrig, kein Niederschlag -- ausser dem gezielt gesetzten
    ``thunder_level``), damit ausschliesslich Gewitter das Risikobild einer
    Etappe bestimmt.
    """

    name = "keyed-thunder-fake"

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
        spec = self._by_coord[key]
        day = (start or datetime.now(timezone.utc)).date()
        data = []
        for hour in range(24):
            ts = datetime(day.year, day.month, day.day, hour, tzinfo=timezone.utc)
            data.append(
                ForecastDataPoint(
                    ts=ts,
                    t2m_c=10.0,
                    wind10m_kmh=spec.get("wind10m_kmh", 10.0),
                    gust_kmh=spec.get("gust_kmh", 10.0),
                    precip_1h_mm=0.0,
                    wmo_code=1,
                    is_day=1,
                    thunder_level=spec.get("thunder_level"),
                )
            )
        return NormalizedTimeseries(
            meta=ForecastMeta(provider=Provider.OPENMETEO, model="keyed-thunder-fake", grid_res_km=1.0),
            data=data,
        )


def _wp(id_, lat, lon, arrival):
    return Waypoint(
        id=id_, name=id_, lat=lat, lon=lon, elevation_m=_LOW_ELEV,
        arrival_calculated=arrival,
    )


def _stage_with_thunder(stage_id: str, lat: float, lon: float, thunder_level) -> tuple:
    """Baut eine Ein-Segment-Etappe + den passenden Provider-Eintrag."""
    stage = Stage(
        id=stage_id, name=stage_id, date=TARGET_DATE,
        waypoints=[_wp("g1", lat, lon, "08:00"), _wp("g2", lat + 0.1, lon, "10:00")],
    )
    provider = _KeyedThunderFakeProvider({
        (lat, lon): {"thunder_level": thunder_level},
        (lat + 0.1, lon): {"thunder_level": thunder_level},
    })
    return stage, provider


# ---------------------------------------------------------------------------
# AC-2 (Regression, PFLICHT, muss gruen bleiben): eine Etappe ganz ohne
# Risiken (kein Gewitter, kein Wind-/Regen-/Sicht-Risiko) bleibt "green".
# Waechter: wuerde eine naive Loesung _RISK_TO_COLOR[RiskLevel.LOW]="yellow"
# setzen, faerbt sie JEDE risikofreie Etappe faelschlich gelb -- dieser Test
# faengt das.
# ---------------------------------------------------------------------------

def test_ac2_risikofreie_etappe_bleibt_gruen():
    from services.stage_weather import compute_stage_weather

    stage, provider = _stage_with_thunder("s_none", 40.0, 8.0, thunder_level=None)
    trip = Trip(id="trip-ac2", name="trip-ac2", stages=[stage])

    results = compute_stage_weather(trip, provider)

    assert results["s_none"] is not None
    assert results["s_none"]["risk"] == "green", (
        f"AC-2: eine Etappe ohne jedes Risiko muss 'green' bleiben, sah "
        f"{results['s_none']}"
    )


# ---------------------------------------------------------------------------
# AC-3 (rot): eine Etappe, deren einziges Risiko ThunderLevel.LOW ist, muss
# kuenftig "yellow" liefern -- heute liefert sie faelschlich "green".
# ---------------------------------------------------------------------------

def test_ac3_nur_leichtes_gewitter_faerbt_die_etappe_gelb():
    from services.stage_weather import compute_stage_weather

    stage, provider = _stage_with_thunder("s_low", 41.0, 8.0, thunder_level=ThunderLevel.LOW)
    trip = Trip(id="trip-ac3", name="trip-ac3", stages=[stage])

    results = compute_stage_weather(trip, provider)

    assert results["s_low"] is not None
    assert results["s_low"]["risk"] == "yellow", (
        "AC-3: eine Etappe mit ausschliesslich ThunderLevel.LOW muss 'yellow' "
        f"liefern (nicht mehr 'green' wie vor dieser Aenderung), sah "
        f"{results['s_low']}"
    )


# ---------------------------------------------------------------------------
# AC-4 (muss gruen sein): mittleres/hohes Gewitter-Risiko bleiben unveraendert
# gelb bzw. rot.
# ---------------------------------------------------------------------------

def test_ac4_mittleres_gewitter_bleibt_gelb():
    from services.stage_weather import compute_stage_weather

    stage, provider = _stage_with_thunder("s_med", 42.0, 8.0, thunder_level=ThunderLevel.MED)
    trip = Trip(id="trip-ac4-med", name="trip-ac4-med", stages=[stage])

    results = compute_stage_weather(trip, provider)

    assert results["s_med"] is not None
    assert results["s_med"]["risk"] == "yellow", (
        f"AC-4: ThunderLevel.MED muss weiterhin 'yellow' liefern, sah {results['s_med']}"
    )


def test_ac4_hohes_gewitter_bleibt_rot():
    from services.stage_weather import compute_stage_weather

    stage, provider = _stage_with_thunder("s_high", 43.0, 8.0, thunder_level=ThunderLevel.HIGH)
    trip = Trip(id="trip-ac4-high", name="trip-ac4-high", stages=[stage])

    results = compute_stage_weather(trip, provider)

    assert results["s_high"] is not None
    assert results["s_high"]["risk"] == "red", (
        f"AC-4: ThunderLevel.HIGH muss weiterhin 'red' liefern, sah {results['s_high']}"
    )

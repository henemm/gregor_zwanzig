"""Gemeinsame Bausteine der `/strecke`-Kommando-Tests (Issue #2051 S4).

SPEC: docs/specs/modules/feat_2051_s4_strecke_kommando.md

Mock-frei: echte `Trip`/`Stage`/`Waypoint`-Objekte, echte
`convert_trip_to_segments()`/`resolve_current_segment()` (kein Nachbau von
`TripSegment` von Hand fuer die Kommando-Ebene — die Tests durchlaufen die
echte Segment-Aufloesung). Die Aequator-Geometrie (Muster
`test_regen_ausdehnung_messpunkte.py::_aequator_segment`) macht km-Werte
analytisch nachrechenbar (`haversine_km` == lineare Laengengrad-Distanz).

Zwei Fixture-Familien:

* `future_two_point_trip()` — EIN zukuenftiges Segment (Preview-Zweig von
  `resolve_current_segment`, `position_at_time()` liefert dadurch GARANTIERT
  `active.start_point` exakt, `p=0`) fuer die `points_along_remaining_route`-
  Familie (AC-4/5/6/7/19/21/22).
* `active_three_point_trip()` — ein ECHT zeitaktives ZWEITES Segment einer
  Drei-Wegpunkt-Etappe fuer die `points_from_km`-Familie (AC-13/14/15/16):
  `active.start_point`/`end_point` tragen dort ungleich-null km-Werte, was
  eine Stage mit >= 3 Wegpunkten UND echter Zeit-Aktivitaet braucht (der
  Preview-Zweig liefert immer nur das ERSTE Segment des Tages).

Beide Familien setzen `distance_from_start_km` auf jedem Wegpunkt exakt auf
den geometrisch konstruierten Wert -- das erfuellt
`trip_segments.stage_measured_distances()` (`span >= luftlinie`) und macht
die Etappe `distance_measured=True`.
"""
from __future__ import annotations

import math
import uuid
from datetime import timedelta

from app.models import TripReportConfig
from app.trip import Stage, Trip, Waypoint
from utils.geo import haversine_km

from tests.helpers.arrival_window_fixtures import active_window_offsets, stage_date

# Muss zu `utils.geo._EARTH_KM` passen (Muster S2a-Messpunkte-Test) — nur zur
# Konstruktion, die tatsaechliche Distanz wird unten per `haversine_km()`
# gegengeprueft, nicht als zweite Quelle der Wahrheit angenommen.
_EARTH_KM = 6371.0088

LAT, LON = 0.0, 0.0  # Aequator -- Grosskreis-Distanz == lineare Laengengrad-Interpolation


def _lon_at(km: float, lon0: float = LON) -> float:
    return lon0 + math.degrees(km / _EARTH_KM)


def _waypoint(idx: int, km: float, arrival: str, *, lat: float = LAT, lon0: float = LON) -> Waypoint:
    return Waypoint(
        id=f"WP{idx}", name=f"WP{idx}", lat=lat, lon=_lon_at(km, lon0),
        elevation_m=1000.0, arrival_calculated=arrival,
        distance_from_start_km=km,
    )


def _report_config(trip_id: str) -> TripReportConfig:
    return TripReportConfig(trip_id=trip_id, send_email=True, send_telegram=False)


def fresh_trip_id(tag: str) -> str:
    return f"tdd-2051-s4-{tag}-{uuid.uuid4().hex[:6]}"


def future_two_point_trip(
    trip_id: str, distance_km: float, *, lat: float = LAT, lon: float = LON,
) -> Trip:
    """Ein-Segment-Etappe, VOLLSTAENDIG in der Zukunft (Preview-Zweig).

    `resolve_current_segment()` liefert damit garantiert
    `(segment, heute)` mit `position_at_time() == active.start_point`
    (p=0 exakt, kein Zeit-Rundungsrisiko) und `_remaining_km() ==
    distance_km` exakt -- dieselbe Eigenschaft, die
    `test_regen_ausdehnung_messpunkte.py::_aequator_segment` fuer die
    rohe `TripSegment`-Ebene nutzt, hier ueber den vollen Trip-Pfad.
    """
    tag = stage_date(lat, lon)
    ankunft0, ankunft1 = active_window_offsets(lat, lon, 60, 180)
    wp0 = _waypoint(0, 0.0, ankunft0, lat=lat, lon0=lon)
    wp1 = _waypoint(1, distance_km, ankunft1, lat=lat, lon0=lon)
    gemessen = haversine_km(wp0.lat, wp0.lon, wp1.lat, wp1.lon)
    assert abs(gemessen - distance_km) < 1e-6, (
        f"Testvoraussetzung: die konstruierte Strecke muss {distance_km} km "
        f"messen, misst tatsaechlich {gemessen} km"
    )
    stage = Stage(id="S1", name="Tag 1", date=tag, waypoints=[wp0, wp1])
    trip = Trip(id=trip_id, name="Strecke-Testtrip", stages=[stage])
    trip.report_config = _report_config(trip_id)
    return trip


def active_three_point_trip(
    trip_id: str, km_mid: float, km_end: float, *, lat: float = LAT, lon: float = LON,
) -> Trip:
    """Drei-Wegpunkt-Etappe, deren ZWEITES Segment (WP1->WP2) ECHT
    zeitaktiv ist ("jetzt" liegt innerhalb seines Zeitfensters, nicht nur
    im Preview-Zweig -- der liefert immer nur das erste Segment des Tages).

    `active.start_point.distance_from_start_km == km_mid`,
    `active.end_point.distance_from_start_km == km_end`.
    """
    tag = stage_date(lat, lon)
    # Segment 0 (WP0->WP1) liegt VOLLSTAENDIG in der Vergangenheit, Segment 1
    # (WP1->WP2) umschliesst "jetzt".
    a0, a1, a2 = active_window_offsets(lat, lon, -120, -30, 60)
    wp0 = _waypoint(0, 0.0, a0, lat=lat, lon0=lon)
    wp1 = _waypoint(1, km_mid, a1, lat=lat, lon0=lon)
    wp2 = _waypoint(2, km_end, a2, lat=lat, lon0=lon)
    stage = Stage(id="S1", name="Tag 1", date=tag, waypoints=[wp0, wp1, wp2])
    trip = Trip(id=trip_id, name="Strecke-Testtrip-Argument", stages=[stage])
    trip.report_config = _report_config(trip_id)
    return trip


def unmeasured_future_trip(trip_id: str, *, lat: float = LAT, lon: float = LON) -> Trip:
    """Wie `future_two_point_trip()`, aber OHNE `distance_from_start_km` auf
    den Wegpunkten -- die Etappe bleibt `distance_measured=False`, auch nach
    einem (hier wirkungslosen, weil GPX-losen) Backfill-Versuch."""
    tag = stage_date(lat, lon)
    ankunft0, ankunft1 = active_window_offsets(lat, lon, 60, 180)
    wp0 = Waypoint(
        id="WP0", name="WP0", lat=lat, lon=lon, elevation_m=1000.0,
        arrival_calculated=ankunft0,
    )
    wp1 = Waypoint(
        id="WP1", name="WP1", lat=lat, lon=_lon_at(5.0, lon), elevation_m=1000.0,
        arrival_calculated=ankunft1,
    )
    stage = Stage(id="S1", name="Tag 1", date=tag, waypoints=[wp0, wp1])
    trip = Trip(id=trip_id, name="Strecke-Testtrip-Unvermessen", stages=[stage])
    trip.report_config = _report_config(trip_id)
    return trip


def no_active_segment_trip(trip_id: str, *, lat: float = LAT, lon: float = LON) -> Trip:
    """Etappe an einem Tag, der weder "heute" noch "gestern" trifft --
    `resolve_current_segment()` liefert `None` (analog zur `/jetzt`-
    Situation `test_ac18`)."""
    tag = stage_date(lat, lon) + timedelta(days=5)
    wp0 = Waypoint(id="WP0", name="WP0", lat=lat, lon=lon, elevation_m=1000.0, arrival_calculated="08:00")
    wp1 = Waypoint(id="WP1", name="WP1", lat=lat, lon=_lon_at(5.0, lon), elevation_m=1000.0, arrival_calculated="10:00")
    stage = Stage(id="S1", name="Tag X", date=tag, waypoints=[wp0, wp1])
    trip = Trip(id=trip_id, name="Strecke-Testtrip-Ohne-Segment", stages=[stage])
    trip.report_config = _report_config(trip_id)
    return trip


# ---------------------------------------------------------------------------
# Aufzeichnender Radar-Dienst (Muster test_jetzt_misst_am_aufenthaltsort.py)
# ---------------------------------------------------------------------------

def recording_radar_service_type(calls: list, *, script) -> type:
    """Echte `RadarNowcastService`-Unterklasse (kein `Mock()`/`patch()`), die
    jeden `get_nowcast()`-Aufruf mitschreibt (`lat`/`lon`/`elevation_m`/
    `priority`) und danach `script(index)` befragt: liefert das ein
    `NowcastResult`, wird es zurueckgegeben (ohne Netz, ohne echten Cache-
    Unterbau -- reine Fake-Antwort); liefert es eine `Exception`-Instanz,
    wird sie GEWORFEN (Fail-soft-Pruefung der Aufrufer).

    Injektion via `monkeypatch.setattr("services.radar_service.
    RadarNowcastService", ...)` -- `_show_strecke` importiert die Klasse
    lokal an ihrem Wohnort, hat keinen Konstruktor-DI-Seam (wie `_show_now`,
    s. `tests/unit/test_radar_budget_and_priority.py:243-248`).
    """
    from services.radar_service import RadarNowcastService

    class _Aufzeichnend(RadarNowcastService):
        def __init__(self, *_a, **_kw) -> None:
            pass  # kein echter Unterbau noetig -- get_nowcast() ist ueberschrieben

        def get_nowcast(self, lat, lon, elevation_m=None, priority="user_briefing"):
            idx = len(calls)
            calls.append({
                "lat": lat, "lon": lon,
                "elevation_m": elevation_m, "priority": priority,
            })
            ergebnis = script(idx)
            if isinstance(ergebnis, Exception):
                raise ergebnis
            return ergebnis

    return _Aufzeichnend


def wrapping_radar_service_type(calls: list, frame_source) -> type:
    """Wie `recording_radar_service_type()`, aber mit ECHTER
    `RadarNowcastService`-Ableitungslogik dahinter (Muster
    `test_jetzt_misst_am_aufenthaltsort.py::_aufzeichnender_typ`) --
    fuer Faelle, die das ECHTE Budget-/Drosselungsverhalten von
    `get_nowcast()` brauchen (AC-4), nicht nur eine kontrollierte
    Fake-Antwort. Speichert zusaetzlich das ERGEBNIS jedes Aufrufs unter
    `calls[i]['result']`."""
    from services.radar_cache import RadarNowcastCacheService
    from services.radar_service import RadarNowcastService

    class _Aufzeichnend(RadarNowcastService):
        def __init__(self, *_a, **_kw) -> None:
            super().__init__(
                frame_source=frame_source, cache=RadarNowcastCacheService(),
            )

        def get_nowcast(self, lat, lon, elevation_m=None, priority="user_briefing"):
            eintrag = {
                "lat": lat, "lon": lon,
                "elevation_m": elevation_m, "priority": priority,
            }
            calls.append(eintrag)
            ergebnis = super().get_nowcast(
                lat, lon, elevation_m=elevation_m, priority=priority,
            )
            eintrag["result"] = ergebnis
            return ergebnis

    return _Aufzeichnend


def nass(onset_minutes: int, event_end_minutes: int | None = None, *, source: str = "radar") -> object:
    from services.radar_service import INTENSITY_MODERATE, NowcastResult

    return NowcastResult(
        onset_minutes=onset_minutes, intensity_label=INTENSITY_MODERATE,
        source=source, event_end_minutes=event_end_minutes,
    )


def trocken() -> object:
    from services.radar_service import INTENSITY_DRY, NowcastResult

    return NowcastResult(onset_minutes=None, intensity_label=INTENSITY_DRY, source="radar")

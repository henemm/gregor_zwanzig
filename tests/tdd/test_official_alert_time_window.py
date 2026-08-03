"""TDD RED — Issue #1460 Teil 1, Paket P4: amtliche Warnungen bekommen Ort UND
Zeit gemeinsam (Tour UND Ortsvergleich).

SPEC: docs/specs/modules/rework_1460_t1_relevanzfilter.md (AC-24 .. AC-33)

Heute wird jede irgendwann gueltige Warnung an jeder Etappen-Koordinate sofort
gemeldet — unabhaengig davon, ob der Nutzer zu ihrer Gueltigkeitszeit dort
ueberhaupt ist. Ab dieser Scheibe bekommt JEDES Segment der Restroute sein
eigenes Zeitfenster (`[max(jetzt, start), ende]`), der Ortsvergleich das
heutige Tagesfenster des jeweiligen Ortes.

Die Pruefreichweite bleibt bewusst die GESAMTE Restroute (anders als der
Nowcast-Pfad) — AC-25/AC-27/AC-28 sichern genau das ab.

RED-Ursache (heute, vor der Implementierung):
- `trip_alert.py:1151` ruft `get_official_alerts_for_location(*coord)` ohne
  Fenster -> eine Warnung in drei Tagen wird dem HEUTIGEN Segment zugeschlagen
  (AC-24 rot) und ein laengst beendetes Segment wird weiter ausgewertet
  (AC-29 rot).
- Der Dedup-Schluessel ist die blosse Koordinate (`trip_alert.py:1140-1148`) —
  zwei Segmente an derselben Koordinate zu verschiedenen Zeiten kollabieren
  (AC-25b rot).
- `compare_official_alert.py:176` ruft ebenfalls ohne Fenster -> eine Warnung,
  die erst morgen frueh beginnt, wird heute gemeldet (AC-31 rot).

Keine Mocks: echte Quellen ueber `register_official_alert_source()`
(strukturelles Subtyping), echte Schnappschuss-/Preset-Persistenz, echte
Auswertungsfunktionen (`check_official_alert_triggers()` / `_detect()`) —
beide liefern eine Liste zurueck, ohne zu versenden. Kein Netz.
"""
from __future__ import annotations

import shutil
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from app.models import (
    ForecastMeta,
    GPXPoint,
    NormalizedTimeseries,
    Provider,
    SegmentWeatherData,
    SegmentWeatherSummary,
    TripReportConfig,
    TripSegment,
)
from app.trip import Stage, Trip, Waypoint
from services.official_alerts.models import OfficialAlert

# Pfadregel #1409: Pruefling relativ zur Testdatei, nicht ueber den Hauptrepo-Pfad.
DATA_ROOT = Path(__file__).resolve().parents[2] / "data" / "users"

# Klar getrennte Koordinaten (Toleranz der Testquelle: 0.05 Grad).
COORD_HEUTE = (47.00, 11.00)
COORD_MORGEN = (47.50, 11.50)
COORD_SPAETER = (48.00, 12.00)

NOW = datetime.now(timezone.utc)


def _clean_user(uid: str) -> None:
    d = DATA_ROOT / uid
    if d.exists():
        shutil.rmtree(d, ignore_errors=True)


def _fresh_user(prefix: str) -> str:
    return f"tdd-1460-p4-{prefix}-{uuid.uuid4().hex[:6]}"


def _segment(segment_id: str, coord: tuple[float, float],
             start: datetime, end: datetime) -> TripSegment:
    lat, lon = coord
    return TripSegment(
        segment_id=segment_id,
        start_point=GPXPoint(lat=lat, lon=lon, elevation_m=1000, distance_from_start_km=0.0),
        end_point=GPXPoint(lat=lat + 0.01, lon=lon + 0.01, elevation_m=1500,
                           distance_from_start_km=8.0),
        start_time=start,
        end_time=end,
        duration_hours=(end - start).total_seconds() / 3600.0,
        distance_km=8.0,
        ascent_m=500,
        descent_m=0,
    )


def _data(segment_id: str, coord: tuple[float, float],
          start: datetime, end: datetime) -> SegmentWeatherData:
    return SegmentWeatherData(
        segment=_segment(segment_id, coord, start, end),
        timeseries=NormalizedTimeseries(
            meta=ForecastMeta(provider=Provider.OPENMETEO, model="test", grid_res_km=1.0),
            data=[],
        ),
        aggregated=SegmentWeatherSummary(gust_max_kmh=20.0),
        fetched_at=datetime.now(timezone.utc),
        provider="openmeteo",
    )


def _trip(trip_id: str) -> Trip:
    lat, lon = COORD_HEUTE
    stage = Stage(
        id="T1", name="Tag 1", date=date.today(),
        waypoints=[Waypoint(id="G1", name="Start", lat=lat, lon=lon, elevation_m=1000.0)],
    )
    trip = Trip(id=trip_id, name="Zeitfenster-Trip", stages=[stage], official_warnings=None)
    trip.report_config = TripReportConfig(trip_id=trip_id, send_email=True)
    return trip


def _save_cached(user_id: str, trip_id: str, cached: list[SegmentWeatherData]) -> None:
    from services.weather_snapshot import WeatherSnapshotService

    WeatherSnapshotService(user_id=user_id).save_dated(trip_id, date.today(), cached)


def _alert(label: str, valid_from: datetime | None, valid_to: datetime | None,
           *, region: str = "Testregion", level: int = 3) -> OfficialAlert:
    return OfficialAlert(
        source="tdd-1460-p4", hazard="thunderstorm", level=level, label=label,
        region_label=region, valid_from=valid_from, valid_to=valid_to,
    )


class _PointSource:
    """Echte Quelle (kein Mock): zustaendig fuer einen Punkt (0.05-Toleranz),
    liefert die uebergebenen Warnungen, zaehlt jeden Abruf."""

    def __init__(self, coord: tuple[float, float], alerts: list[OfficialAlert],
                 name: str = "tdd-1460-p4-source") -> None:
        self._lat, self._lon = coord
        self._alerts = alerts
        self._name = name
        self.fetch_calls = 0

    property
    def name(self) -> str:
        return self._name

    def covers(self, lat: float, lon: float) -> bool:
        return abs(lat - self._lat) < 0.05 and abs(lon - self._lon) < 0.05

    def fetch(self, lat: float, lon: float) -> list[OfficialAlert]:
        self.fetch_calls += 1
        return list(self._alerts)


def _sources_backup():
    import services.official_alerts.base as b

    return b, list(b._REGISTERED_SOURCES)


def _labels(result: list) -> list[str]:
    return [a.label for a, _segment_ids in result]


def _segments_for(result: list, label: str) -> list[str]:
    for a, segment_ids in result:
        if a.label == label:
            return list(segment_ids)
    return []


# ═══════════════════════════ Tour (AC-24 .. AC-30) ═══════════════════════════

def test_ac24_warnung_in_drei_tagen_gilt_nicht_fuer_die_heutige_etappe():
    """AC-24.

    GIVEN eine Tour mit einer Etappe, auf der der Nutzer HEUTE ist (endet in
          2 Stunden), und eine amtliche Warnung an DEREN Koordinate, die erst
          in 3 Tagen beginnt
    WHEN  die amtlichen Warnungen der Tour geprueft werden
    THEN  wird die Warnung fuer DIESE Etappe NICHT gemeldet — ihr Beginn liegt
          nach dem Ende von deren Zeitfenster.
    """
    from services.official_alerts import register_official_alert_source
    from services.trip_alert import TripAlertService

    user_id = _fresh_user("ac24")
    _clean_user(user_id)
    b, backup = _sources_backup()
    b._REGISTERED_SOURCES.clear()
    try:
        trip = _trip("trip-1460-ac24")
        _save_cached(user_id, trip.id, [
            _data("heute", COORD_HEUTE, NOW - timedelta(hours=1), NOW + timedelta(hours=2)),
        ])
        register_official_alert_source(_PointSource(COORD_HEUTE, [
            _alert("Warnung erst in drei Tagen",
                   NOW + timedelta(days=3), NOW + timedelta(days=3, hours=6)),
        ]))

        result = TripAlertService(user_id=user_id).check_official_alert_triggers(trip)

        assert result == [], (
            "Eine Warnung, die nach dem Ende der heutigen Etappe beginnt, darf "
            f"dieser Etappe nicht zugeschlagen werden, erhalten: {_labels(result)!r}"
        )
    finally:
        b._REGISTERED_SOURCES.clear()
        b._REGISTERED_SOURCES.extend(backup)
        _clean_user(user_id)


def test_ac25_warnung_fuer_eine_spaetere_etappe_geht_nicht_verloren():
    """AC-25 (wichtigstes AC dieses Pakets).

    GIVEN dieselbe Tour hat eine SPAETERE Etappe, auf der der Nutzer in 3 Tagen
          sein wird, und die amtliche Warnung liegt an DEREN Koordinate
          innerhalb von deren Zeitfenster
    WHEN  die amtlichen Warnungen der Tour geprueft werden
    THEN  WIRD die Warnung gemeldet — zugeordnet zu dieser spaeteren Etappe.
    """
    from services.official_alerts import register_official_alert_source
    from services.trip_alert import TripAlertService

    user_id = _fresh_user("ac25")
    _clean_user(user_id)
    b, backup = _sources_backup()
    b._REGISTERED_SOURCES.clear()
    try:
        trip = _trip("trip-1460-ac25")
        _save_cached(user_id, trip.id, [
            _data("heute", COORD_HEUTE, NOW - timedelta(hours=1), NOW + timedelta(hours=2)),
            _data("etappe5", COORD_SPAETER,
                  NOW + timedelta(days=3), NOW + timedelta(days=3, hours=8)),
        ])
        register_official_alert_source(_PointSource(COORD_SPAETER, [
            _alert("Vorwarnung fuer Etappe 5",
                   NOW + timedelta(days=3), NOW + timedelta(days=3, hours=6)),
        ]))

        result = TripAlertService(user_id=user_id).check_official_alert_triggers(trip)

        assert _labels(result) == ["Vorwarnung fuer Etappe 5"], (
            "Die Vorwarnung fuer die spaetere Etappe darf nicht verloren gehen, "
            f"erhalten: {_labels(result)!r}"
        )
        assert _segments_for(result, "Vorwarnung fuer Etappe 5") == ["etappe5"], (
            "Die Warnung muss der spaeteren Etappe zugeordnet sein, erhalten: "
            f"{_segments_for(result, 'Vorwarnung fuer Etappe 5')!r}"
        )
    finally:
        b._REGISTERED_SOURCES.clear()
        b._REGISTERED_SOURCES.extend(backup)
        _clean_user(user_id)


def test_ac25b_gleiche_koordinate_an_zwei_tagen_faellt_nicht_zusammen():
    """AC-25 (Dedup-Schluessel).

    GIVEN ein Ort, der an ZWEI verschiedenen Tagen der Route liegt (gleiche
          Koordinate, verschiedene Zeitfenster), und eine amtliche Warnung, die
          nur im Fenster der SPAETEREN Etappe gueltig ist
    WHEN  die amtlichen Warnungen der Tour geprueft werden
    THEN  wird die Warnung genau der spaeteren Etappe zugeordnet — die beiden
          Segmente duerfen nicht ueber die blosse Koordinate zusammenfallen.
    """
    from services.official_alerts import register_official_alert_source
    from services.trip_alert import TripAlertService

    user_id = _fresh_user("ac25b")
    _clean_user(user_id)
    b, backup = _sources_backup()
    b._REGISTERED_SOURCES.clear()
    try:
        trip = _trip("trip-1460-ac25b")
        _save_cached(user_id, trip.id, [
            _data("hin", COORD_HEUTE, NOW - timedelta(hours=1), NOW + timedelta(hours=2)),
            _data("rueck", COORD_HEUTE,
                  NOW + timedelta(days=2), NOW + timedelta(days=2, hours=8)),
        ])
        register_official_alert_source(_PointSource(COORD_HEUTE, [
            _alert("Nur am Rueckweg gueltig",
                   NOW + timedelta(days=2, hours=1), NOW + timedelta(days=2, hours=5)),
        ]))

        result = TripAlertService(user_id=user_id).check_official_alert_triggers(trip)

        assert _labels(result) == ["Nur am Rueckweg gueltig"], (
            f"Die Warnung muss gemeldet werden, erhalten: {_labels(result)!r}"
        )
        assert _segments_for(result, "Nur am Rueckweg gueltig") == ["rueck"], (
            "Die Warnung darf nur der spaeteren Etappe zugeordnet sein — heute "
            "kollabieren beide Etappen ueber die blosse Koordinate, erhalten: "
            f"{_segments_for(result, 'Nur am Rueckweg gueltig')!r}"
        )
    finally:
        b._REGISTERED_SOURCES.clear()
        b._REGISTERED_SOURCES.extend(backup)
        _clean_user(user_id)


def test_ac26_warnung_innerhalb_der_naechsten_zwei_stunden_wird_gemeldet():
    """AC-26.

    GIVEN dieselbe heutige Etappe (endet in 2 Stunden) und eine amtliche
          Warnung an deren Koordinate, die in 1 Stunde beginnt
    WHEN  die amtlichen Warnungen der Tour geprueft werden
    THEN  WIRD sie fuer diese Etappe gemeldet.
    """
    from services.official_alerts import register_official_alert_source
    from services.trip_alert import TripAlertService

    user_id = _fresh_user("ac26")
    _clean_user(user_id)
    b, backup = _sources_backup()
    b._REGISTERED_SOURCES.clear()
    try:
        trip = _trip("trip-1460-ac26")
        _save_cached(user_id, trip.id, [
            _data("heute", COORD_HEUTE, NOW - timedelta(hours=1), NOW + timedelta(hours=2)),
        ])
        register_official_alert_source(_PointSource(COORD_HEUTE, [
            _alert("Akute Warnung", NOW + timedelta(hours=1), NOW + timedelta(hours=4)),
        ]))

        result = TripAlertService(user_id=user_id).check_official_alert_triggers(trip)

        assert _labels(result) == ["Akute Warnung"], (
            f"Die akute Warnung muss gemeldet werden, erhalten: {_labels(result)!r}"
        )
        assert _segments_for(result, "Akute Warnung") == ["heute"]
    finally:
        b._REGISTERED_SOURCES.clear()
        b._REGISTERED_SOURCES.extend(backup)
        _clean_user(user_id)


def test_ac27_ruhetag_schliesst_die_kuenftigen_etappen_nicht_aus():
    """AC-27.

    GIVEN ein Ruhetag ohne Etappe fuer HEUTE, aber mit regulaeren KUENFTIGEN
          Etappen (morgen und uebermorgen) im Schnappschuss
    WHEN  die amtlichen Warnungen der Tour geprueft werden
    THEN  werden die kuenftigen Etappen unveraendert mit ihren eigenen Fenstern
          geprueft — ein Ruhetag schliesst spaetere Etappen nicht aus.
    """
    from services.official_alerts import register_official_alert_source
    from services.trip_alert import TripAlertService

    user_id = _fresh_user("ac27")
    _clean_user(user_id)
    b, backup = _sources_backup()
    b._REGISTERED_SOURCES.clear()
    try:
        trip = _trip("trip-1460-ac27")
        _save_cached(user_id, trip.id, [
            _data("morgen", COORD_MORGEN,
                  NOW + timedelta(days=1), NOW + timedelta(days=1, hours=8)),
            _data("uebermorgen", COORD_SPAETER,
                  NOW + timedelta(days=2), NOW + timedelta(days=2, hours=8)),
        ])
        source = _PointSource(COORD_MORGEN, [
            _alert("Warnung fuer morgen",
                   NOW + timedelta(days=1, hours=2), NOW + timedelta(days=1, hours=6)),
        ])
        register_official_alert_source(source)

        result = TripAlertService(user_id=user_id).check_official_alert_triggers(trip)

        assert source.fetch_calls >= 1, (
            "Die kuenftige Etappe muss weiterhin abgefragt werden"
        )
        assert _labels(result) == ["Warnung fuer morgen"], (
            f"Die Warnung fuer morgen darf nicht verloren gehen, erhalten: {_labels(result)!r}"
        )
        assert _segments_for(result, "Warnung fuer morgen") == ["morgen"]
    finally:
        b._REGISTERED_SOURCES.clear()
        b._REGISTERED_SOURCES.extend(backup)
        _clean_user(user_id)


def test_ac28_etappen_pause_schliesst_spaetere_etappen_nicht_aus():
    """AC-28.

    GIVEN der aktuelle Zeitpunkt liegt zwischen dem Ende von Etappe 1 und dem
          Start von Etappe 2 desselben Tages (eine Pause)
    WHEN  die amtlichen Warnungen der Tour geprueft werden
    THEN  bleibt Etappe 2 mit ihrem eigenen Zeitfenster pruefbar — die Pause
          schliesst nachfolgende Etappen NICHT aus (anders als der
          Nowcast-Pfad, bewusste Abweichung).
    """
    from services.official_alerts import register_official_alert_source
    from services.trip_alert import TripAlertService

    user_id = _fresh_user("ac28")
    _clean_user(user_id)
    b, backup = _sources_backup()
    b._REGISTERED_SOURCES.clear()
    try:
        trip = _trip("trip-1460-ac28")
        _save_cached(user_id, trip.id, [
            _data("vormittag", COORD_HEUTE, NOW - timedelta(hours=5), NOW - timedelta(hours=1)),
            _data("nachmittag", COORD_MORGEN, NOW + timedelta(hours=1), NOW + timedelta(hours=5)),
        ])
        register_official_alert_source(_PointSource(COORD_MORGEN, [
            _alert("Warnung fuer den Nachmittag",
                   NOW + timedelta(hours=2), NOW + timedelta(hours=4)),
        ]))

        result = TripAlertService(user_id=user_id).check_official_alert_triggers(trip)

        assert _labels(result) == ["Warnung fuer den Nachmittag"], (
            "Die Pause zwischen zwei Etappen darf die nachfolgende Etappe nicht "
            f"ausschliessen, erhalten: {_labels(result)!r}"
        )
        assert _segments_for(result, "Warnung fuer den Nachmittag") == ["nachmittag"]
    finally:
        b._REGISTERED_SOURCES.clear()
        b._REGISTERED_SOURCES.extend(backup)
        _clean_user(user_id)


def test_ac29_beendete_tour_wertet_keine_amtliche_warnung_mehr_aus():
    """AC-29.

    GIVEN der letzte Tourtag, die letzte Etappe ist bereits beendet und es gibt
          keine weitere Etappe
    WHEN  die amtlichen Warnungen der Tour geprueft werden
    THEN  wird kein amtlicher Alarm mehr ausgewertet — das Ergebnis ist leer.
    """
    from services.official_alerts import register_official_alert_source
    from services.trip_alert import TripAlertService

    user_id = _fresh_user("ac29")
    _clean_user(user_id)
    b, backup = _sources_backup()
    b._REGISTERED_SOURCES.clear()
    try:
        trip = _trip("trip-1460-ac29")
        _save_cached(user_id, trip.id, [
            _data("letzte", COORD_HEUTE, NOW - timedelta(hours=5), NOW - timedelta(hours=1)),
        ])
        register_official_alert_source(_PointSource(COORD_HEUTE, [
            _alert("Warnung nach Tourende", NOW - timedelta(hours=1), NOW + timedelta(hours=6)),
        ]))

        result = TripAlertService(user_id=user_id).check_official_alert_triggers(trip)

        assert result == [], (
            "Eine bereits beendete Etappe darf nicht mehr ausgewertet werden, "
            f"erhalten: {_labels(result)!r}"
        )
    finally:
        b._REGISTERED_SOURCES.clear()
        b._REGISTERED_SOURCES.extend(backup)
        _clean_user(user_id)


def test_ac30_warnung_ohne_zeitangabe_bleibt_erhalten():
    """AC-30 (fail-safe unveraendert).

    GIVEN eine amtliche Warnung ohne Beginn und ohne Ende
    WHEN  das neue Zeitfenster auf die heutige Etappe angewendet wird
    THEN  bleibt sie trotzdem erhalten — eine fehlende Zeitangabe darf nie als
          "abgelaufen" gelten.
    """
    from services.official_alerts import register_official_alert_source
    from services.trip_alert import TripAlertService

    user_id = _fresh_user("ac30")
    _clean_user(user_id)
    b, backup = _sources_backup()
    b._REGISTERED_SOURCES.clear()
    try:
        trip = _trip("trip-1460-ac30")
        _save_cached(user_id, trip.id, [
            _data("heute", COORD_HEUTE, NOW - timedelta(hours=1), NOW + timedelta(hours=2)),
        ])
        register_official_alert_source(_PointSource(COORD_HEUTE, [
            _alert("Warnung ohne Zeitangabe", None, None),
        ]))

        result = TripAlertService(user_id=user_id).check_official_alert_triggers(trip)

        assert _labels(result) == ["Warnung ohne Zeitangabe"], (
            "Eine Warnung ohne Zeitangabe muss erhalten bleiben, erhalten: "
            f"{_labels(result)!r}"
        )
    finally:
        b._REGISTERED_SOURCES.clear()
        b._REGISTERED_SOURCES.extend(backup)
        _clean_user(user_id)


# ═══════════════════════ Ortsvergleich (AC-31 .. AC-33) ══════════════════════

# Kandidaten quer ueber die Zeitzonen: der Test waehlt den Ort, dessen ORTSZEIT
# bequem im Tagesfenster 4-19 Uhr liegt. So haengt das Ergebnis nicht davon ab,
# zu welcher Uhrzeit die Suite laeuft (kein Mock, keine Zeit-Manipulation).
_TZ_CANDIDATES = [
    (47.00, 11.00),    # Europe/Vienna
    (40.70, -74.00),   # America/New_York
    (35.70, 139.70),   # Asia/Tokyo
    (-33.90, 151.20),  # Australia/Sydney
    (21.30, -157.80),  # Pacific/Honolulu
    (55.75, 37.60),    # Europe/Moscow
    (28.60, 77.20),    # Asia/Kolkata
    (-23.50, -46.60),  # America/Sao_Paulo
    (37.77, -122.40),  # America/Los_Angeles
    (-1.29, 36.82),    # Africa/Nairobi
    (64.15, -21.94),   # Atlantic/Reykjavik
]

_DAY_WINDOW_START, _DAY_WINDOW_END = 4, 19


def _daytime_location() -> tuple[tuple[float, float], object]:
    """Waehlt einen Ort, dessen Ortszeit mit Abstand im Tagesfenster 4-19 Uhr
    liegt (Stunde 6..16). Ohne diese Wahl waere das Ergebnis von der Uhrzeit
    des Testlaufs abhaengig."""
    from utils.timezone import tz_for_coords

    for coord in _TZ_CANDIDATES:
        tz = tz_for_coords(*coord)
        if tz is None:
            continue
        if 6 <= datetime.now(tz).hour <= 16:
            return coord, tz
    raise AssertionError(
        "Keiner der Kandidaten liegt in seiner Ortszeit im Tagesfenster — "
        "die Kandidatenliste deckt nicht alle Zeitzonen ab"
    )


def _compare_preset(preset_id: str, location_ids: list[str]) -> dict:
    return {
        "id": preset_id, "name": preset_id, "user_id": "default",
        "location_ids": location_ids, "schedule": "daily", "weekday": 4,
        "profil": "ALLGEMEIN", "hour_from": 9, "hour_to": 16,
        "day_window_start_hour": _DAY_WINDOW_START,
        "day_window_end_hour": _DAY_WINDOW_END,
        "empfaenger": ["ex.invalid"], "created_at": "2026-08-02T00:00:00Z",
    }


def _write_preset(user_id: str, preset: dict) -> None:
    from tests.helpers.compare_briefings import write_compare_briefings

    write_compare_briefings(DATA_ROOT / user_id, [preset])


def _compare_detect(user_id: str, preset_id: str, locs: list) -> list:
    from services.compare_official_alert import CompareOfficialAlertService

    tagged, _per_location = CompareOfficialAlertService(
        user_id=user_id
    )._detect(preset_id, locs, None)
    return tagged


def _saved_location(loc_id: str, coord: tuple[float, float]):
    from app.user import SavedLocation

    lat, lon = coord
    return SavedLocation(id=loc_id, name=loc_id, lat=lat, lon=lon, elevation_m=1000)


def test_ac31_warnung_ab_morgen_frueh_wird_heute_nicht_gemeldet():
    """AC-31.

    GIVEN ein Ortsvergleich mit Tagesfenster 4-19 Uhr Ortszeit und eine
          amtliche Warnung, die morgen um 3 Uhr Ortszeit beginnt
    WHEN  der Ortsvergleich heute geprueft wird
    THEN  wird sie NICHT gemeldet — sie liegt ausserhalb "jetzt bis Ende des
          heutigen Tagesfensters".
    """
    from app.loader import save_location
    from services.official_alerts import register_official_alert_source

    user_id = _fresh_user("ac31")
    _clean_user(user_id)
    b, backup = _sources_backup()
    b._REGISTERED_SOURCES.clear()
    try:
        coord, tz = _daytime_location()
        loc = _saved_location("loc-a", coord)
        save_location(loc, user_id=user_id)
        _write_preset(user_id, _compare_preset("cp-1460-ac31", ["loc-a"]))

        morgen = datetime.now(tz).date() + timedelta(days=1)
        vf = datetime.combine(morgen, datetime.min.time(), tzinfo=tz).replace(hour=3)
        register_official_alert_source(_PointSource(coord, [
            _alert("Warnung ab morgen frueh", vf, vf + timedelta(hours=2)),
        ]))

        result = _compare_detect(user_id, "cp-1460-ac31", [loc])

        assert result == [], (
            "Eine Warnung ausserhalb des heutigen Tagesfensters darf nicht "
            f"gemeldet werden, erhalten: {_labels(result)!r}"
        )
    finally:
        b._REGISTERED_SOURCES.clear()
        b._REGISTERED_SOURCES.extend(backup)
        _clean_user(user_id)


def test_ac32_warnung_im_heutigen_tagesfenster_wird_gemeldet():
    """AC-32.

    GIVEN derselbe Ortsvergleich und eine amtliche Warnung, die noch HEUTE
          innerhalb des Tagesfensters beginnt
    WHEN  der Ortsvergleich geprueft wird
    THEN  WIRD sie gemeldet.
    """
    from app.loader import save_location
    from services.official_alerts import register_official_alert_source

    user_id = _fresh_user("ac32")
    _clean_user(user_id)
    b, backup = _sources_backup()
    b._REGISTERED_SOURCES.clear()
    try:
        coord, tz = _daytime_location()
        loc = _saved_location("loc-a", coord)
        save_location(loc, user_id=user_id)
        _write_preset(user_id, _compare_preset("cp-1460-ac32", ["loc-a"]))

        now_local = datetime.now(tz)
        vf = now_local + timedelta(minutes=30)
        assert vf.hour < _DAY_WINDOW_END, (
            "Vorbedingung: der Warnbeginn muss im heutigen Tagesfenster liegen"
        )
        register_official_alert_source(_PointSource(coord, [
            _alert("Warnung heute im Tagesfenster", vf, vf + timedelta(hours=1)),
        ]))

        result = _compare_detect(user_id, "cp-1460-ac32", [loc])

        assert _labels(result) == ["Warnung heute im Tagesfenster"], (
            "Eine Warnung im heutigen Tagesfenster muss gemeldet werden, "
            f"erhalten: {_labels(result)!r}"
        )
    finally:
        b._REGISTERED_SOURCES.clear()
        b._REGISTERED_SOURCES.extend(backup)
        _clean_user(user_id)


def test_ac33_ortsvergleich_prueft_weiterhin_alle_orte():
    """AC-33.

    GIVEN ein Ortsvergleich mit drei Orten, von denen nur einer eine im
          Tagesfenster liegende Warnung hat
    WHEN  der Ortsvergleich geprueft wird
    THEN  werden weiterhin ALLE drei Orte abgefragt (kein "aktiver Ort" wie
          beim Trip-Segment), gemeldet wird genau die eine Warnung.
    """
    from app.loader import save_location
    from services.official_alerts import register_official_alert_source

    user_id = _fresh_user("ac33")
    _clean_user(user_id)
    b, backup = _sources_backup()
    b._REGISTERED_SOURCES.clear()
    try:
        coord, tz = _daytime_location()
        loc_a = _saved_location("loc-a", coord)
        loc_b = _saved_location("loc-b", COORD_MORGEN)
        loc_c = _saved_location("loc-c", COORD_SPAETER)
        for loc in (loc_a, loc_b, loc_c):
            save_location(loc, user_id=user_id)
        _write_preset(user_id, _compare_preset("cp-1460-ac33", ["loc-a", "loc-b", "loc-c"]))

        vf = datetime.now(tz) + timedelta(minutes=30)
        src_a = _PointSource(coord, [
            _alert("Warnung nur an Ort A", vf, vf + timedelta(hours=1)),
        ], name="tdd-1460-p4-a")
        src_b = _PointSource(COORD_MORGEN, [], name="tdd-1460-p4-b")
        src_c = _PointSource(COORD_SPAETER, [], name="tdd-1460-p4-c")
        for src in (src_a, src_b, src_c):
            register_official_alert_source(src)

        result = _compare_detect(user_id, "cp-1460-ac33", [loc_a, loc_b, loc_c])

        assert src_a.fetch_calls >= 1 and src_b.fetch_calls >= 1 and src_c.fetch_calls >= 1, (
            "Alle drei Orte muessen weiterhin abgefragt werden: "
            f"a={src_a.fetch_calls} b={src_b.fetch_calls} c={src_c.fetch_calls}"
        )
        assert _labels(result) == ["Warnung nur an Ort A"], (
            f"Genau die eine Warnung muss gemeldet werden, erhalten: {_labels(result)!r}"
        )
        assert result[0][1] == ["loc-a"], (
            f"Die Warnung muss Ort A zugeordnet sein, erhalten: {result[0][1]!r}"
        )
    finally:
        b._REGISTERED_SOURCES.clear()
        b._REGISTERED_SOURCES.extend(backup)
        _clean_user(user_id)

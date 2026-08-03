"""TDD RED — Issue #1460 Teil 1, Paket P1a: der Wertebereich (`corridors[].notify`)
faellt als eigener Alarm-Ausloeser weg.

SPEC: docs/specs/modules/rework_1460_t1_relevanzfilter.md (AC-1 .. AC-3)

Der Wertebereich ist eine ABSOLUTE Grenze und widerspricht damit ADR-0009
(Alarme sind Abweichungs-Waechter) / ADR-0013. Ab dieser Scheibe steuert
ausschliesslich die Empfindlichkeitsstufe. `Corridor.notify` bleibt im
Datenmodell und in der Persistenz erhalten (kein Datenverlust), verliert aber
seine Wirkung.

RED-Ursache (heute, vor der Implementierung):
- `trip_alert.py:248` ruft `_evaluate_corridors()` und meldet jeden gerissenen
  Wertebereich (AC-1 rot: es geht eine Mail raus und `check_and_send_alerts()`
  liefert True).
- `has_corridors` (`trip_alert.py:188`/`:485`) zaehlt Wertebereiche als eigene
  aktive Alarmquelle, sodass eine Tour ohne jede Empfindlichkeitsstufe
  trotzdem geprueft und alarmiert wird (AC-1 rot auch ueber `check_all_trips()`).

Keine Mocks: echte `TripAlertService`-Laeufe, echte Trip-/Snapshot-Persistenz,
echtes Alarm-Protokoll; ersetzt wird ausschliesslich der SMTP-Transport ueber
die vorhandene `mail_sink`-DI-Naht (Projektkonvention, Vorbild
`test_issue_1088_official_alert_triggers.py`).
"""
from __future__ import annotations

import json
import shutil
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from app.models import (
    Corridor,
    ForecastMeta,
    GPXPoint,
    MetricConfig,
    NormalizedTimeseries,
    Provider,
    SegmentWeatherData,
    SegmentWeatherSummary,
    TripReportConfig,
    TripSegment,
    UnifiedWeatherDisplayConfig,
)
from app.trip import Stage, Trip, Waypoint

# Pfadregel #1409: Pruefling relativ zur Testdatei, nicht ueber den Hauptrepo-Pfad.
DATA_ROOT = Path(__file__).resolve().parents[2] / "data" / "users"

LAT, LON = 47.0, 11.0


def _clean_user(uid: str) -> None:
    d = DATA_ROOT / uid
    if d.exists():
        shutil.rmtree(d, ignore_errors=True)


def _fresh_user(prefix: str) -> str:
    return f"tdd-1460-p1a-{prefix}-{uuid.uuid4().hex[:6]}"


def _segment(segment_id: int | str = 1) -> TripSegment:
    """Etappe im aktiven Fenster: beginnt heute, endet in der Zukunft."""
    now = datetime.now(timezone.utc)
    return TripSegment(
        segment_id=segment_id,
        start_point=GPXPoint(lat=LAT, lon=LON, elevation_m=1000, distance_from_start_km=12.0),
        end_point=GPXPoint(lat=LAT + 0.1, lon=LON + 0.1, elevation_m=1500,
                           distance_from_start_km=18.0),
        start_time=now - timedelta(hours=1),
        end_time=now + timedelta(hours=3),
        duration_hours=4.0,
        distance_km=6.0,
        ascent_m=500,
        descent_m=0,
    )


def _data(segment_id: int | str = 1, **summary_kwargs) -> SegmentWeatherData:
    return SegmentWeatherData(
        segment=_segment(segment_id),
        timeseries=NormalizedTimeseries(
            meta=ForecastMeta(provider=Provider.OPENMETEO, model="test", grid_res_km=1.0),
            data=[],
        ),
        aggregated=SegmentWeatherSummary(**summary_kwargs),
        fetched_at=datetime.now(timezone.utc),
        provider="openmeteo",
    )


def _corridor_only_trip(trip_id: str) -> Trip:
    """Tour, deren EINZIGE eingestellte Alarmquelle ein Wertebereich ist:
    keine Empfindlichkeitsstufen, keine Voreinstellung, keine Regeln,
    `alert_on_changes=False`."""
    stage = Stage(
        id="T1", name="Tag 1", date=date.today(),
        waypoints=[Waypoint(id="G1", name="Start", lat=LAT, lon=LON, elevation_m=1000.0)],
    )
    trip = Trip(
        id=trip_id, name="Wertebereich-Trip", stages=[stage],
        official_warnings=None,
        corridors=[Corridor(metric="wind_gust", range=[None, 20.0], notify=True)],
    )
    trip.report_config = TripReportConfig(
        trip_id=trip_id, send_email=True, alert_on_changes=False,
    )
    trip.alert_cooldown_minutes = 0
    trip.official_alert_triggers_enabled = False
    return trip


def _corridor_plus_level_trip(trip_id: str) -> Trip:
    """Dieselbe Tour, zusaetzlich mit Empfindlichkeitsstufe fuer Boeen."""
    trip = _corridor_only_trip(trip_id)
    trip.display_config = UnifiedWeatherDisplayConfig(
        trip_id=trip_id,
        # Katalog-Kennung fuer Boeen ist "gust" (nicht "wind" -- das ist der
        # mittlere Wind). Mit der falschen Kennung gilt wind_gust auf dem
        # Wetter-Tab als nicht aktiv, die Empfindlichkeitsstufe wird still
        # verworfen und der Test waere gruen ohne je die Stufe zu pruefen.
        metrics=[MetricConfig(metric_id="gust", enabled=True)],
        metric_alert_levels={"wind_gust": "standard"},
    )
    trip.report_config = TripReportConfig(
        trip_id=trip_id, send_email=True, alert_on_changes=True,
    )
    return trip


def _service(user_id: str, sink: list):
    from services.trip_alert import TripAlertService

    return TripAlertService(
        user_id=user_id,
        mail_sink=lambda subject, body: sink.append((subject, body)),
    )


def _save_cached(user_id: str, trip_id: str, cached: list[SegmentWeatherData]) -> None:
    from services.weather_snapshot import WeatherSnapshotService

    WeatherSnapshotService(user_id=user_id).save_dated(trip_id, date.today(), cached)


def _read_alert_log(user_id: str) -> list:
    from app.loader import get_data_dir

    path = get_data_dir(user_id) / "alert_log.json"
    if not path.exists():
        return []
    raw = json.loads(path.read_text())
    if isinstance(raw, dict):
        return list(raw.get("entries") or [])
    return list(raw or [])


# ───────────────── AC-1 — Wertebereich alleine loest nichts mehr aus ─────────

def test_ac1_wertebereich_als_einzige_quelle_loest_keinen_alarm_aus():
    """AC-1.

    GIVEN eine Tour, deren EINZIGE eingestellte Alarmquelle ein Wertebereich
          mit "melden" ist (Boeen hoechstens 20 km/h)
    WHEN  die Vorhersage mit 25 km/h diese Grenze reisst und der Alarm-Lauf
          die Tour prueft
    THEN  geht KEINE Meldung raus — die Tour gilt als "keine aktive
          Alarmquelle" (Zustand vor Issue #1444 S1).
    """
    user_id = _fresh_user("ac1")
    _clean_user(user_id)
    try:
        trip = _corridor_only_trip("trip-1460-ac1")
        cached = [_data(1, gust_max_kmh=25.0)]
        fresh = [_data(1, gust_max_kmh=25.0)]
        _save_cached(user_id, trip.id, cached)

        mail_calls: list = []
        svc = _service(user_id, mail_calls)
        sent = svc.check_and_send_alerts(trip, cached, fresh_weather=fresh)

        assert sent is False, (
            "Ein gerissener Wertebereich darf keinen Alarm mehr ausloesen"
        )
        assert mail_calls == [], (
            f"Es darf keine Meldung rausgehen, erhalten: {len(mail_calls)}"
        )
        assert _read_alert_log(user_id) == [], (
            "Es darf auch kein Protokoll-Eintrag entstehen: "
            f"{_read_alert_log(user_id)!r}"
        )
    finally:
        _clean_user(user_id)


def test_ac1b_tour_mit_nur_wertebereich_wird_im_gesamtlauf_nicht_alarmiert():
    """AC-1 (Gesamtlauf).

    GIVEN dieselbe Tour, gespeichert auf Platte
    WHEN  der regulaere Alarm-Lauf ueber alle Touren laeuft
    THEN  wird kein Alarm versendet — der Wertebereich zaehlt nicht mehr als
          aktive Alarmquelle.
    """
    from app.loader import save_trip

    user_id = _fresh_user("ac1b")
    _clean_user(user_id)
    try:
        trip = _corridor_only_trip("trip-1460-ac1b")
        save_trip(trip, user_id=user_id)
        _save_cached(user_id, trip.id, [_data(1, gust_max_kmh=25.0)])

        mail_calls: list = []
        result = _service(user_id, mail_calls).check_all_trips()

        assert result.alerts_sent == 0, (
            f"Erwartet 0 versendete Alarme, erhalten: {result.alerts_sent}"
        )
        assert mail_calls == [], (
            f"Es darf keine Meldung rausgehen, erhalten: {len(mail_calls)}"
        )
    finally:
        _clean_user(user_id)


# ───── AC-2 — Empfindlichkeitsstufe bleibt vom wirkungslosen Feld unberuehrt ──

def test_ac2_empfindlichkeitsstufe_feuert_weiterhin_neben_dem_wertebereich():
    """AC-2 (Regressionsschutz).

    GIVEN dieselbe Tour zusaetzlich mit Empfindlichkeitsstufe "standard" fuer
          Boeen (Schwelle 20 km/h)
    WHEN  sich die Boeen seit dem Briefing-Stand um 25 km/h aendern
    THEN  feuert der Alarm wie vor dieser Scheibe — die Stufe ist vom
          (nun wirkungslosen) Wertebereichs-Feld unbeeinflusst.
    """
    user_id = _fresh_user("ac2")
    _clean_user(user_id)
    try:
        trip = _corridor_plus_level_trip("trip-1460-ac2")
        cached = [_data(1, gust_max_kmh=10.0)]
        fresh = [_data(1, gust_max_kmh=35.0)]  # Δ = 25 > 20
        _save_cached(user_id, trip.id, cached)

        mail_calls: list = []
        svc = _service(user_id, mail_calls)
        sent = svc.check_and_send_alerts(trip, cached, fresh_weather=fresh)

        assert sent is True, "Die Empfindlichkeitsstufe muss weiterhin ausloesen"
        assert len(mail_calls) == 1, (
            f"Erwartet genau 1 Meldung, erhalten: {len(mail_calls)}"
        )
    finally:
        _clean_user(user_id)


# ─────────────── AC-3 — Bestandsdaten bleiben unveraendert erhalten ──────────

def test_ac3_gespeicherter_wertebereich_ueberlebt_laden_und_erneutes_speichern(tmp_path):
    """AC-3.

    GIVEN eine Bestands-Tour mit gespeichertem Wertebereich ("melden" gesetzt)
    WHEN  die Tour geladen und ohne Aenderung an den Wertebereichen erneut
          gespeichert wird
    THEN  steht das Feld unveraendert in der Datei — kein Datenverlust trotz
          Wirkungslosigkeit (Read-Modify-Write).
    """
    from app.loader import load_trip, save_trip

    user_id = "tdd-1460-ac3-roundtrip"
    trip = _corridor_only_trip("trip-1460-ac3")
    trip.corridors = [
        Corridor(metric="wind_gust", range=[None, 20.0], notify=True, mark=True, prio="hoch"),
        Corridor(metric="thunder_level", range=[None, 0.0], notify=True),
    ]

    save_trip(trip, user_id=user_id, data_dir=str(tmp_path))
    trip_file = tmp_path / "users" / user_id / "briefings" / f"{trip.id}.json"
    before = json.loads(trip_file.read_text()).get("corridors")
    assert before, f"Vorbedingung: Wertebereiche muessen persistiert sein ({trip_file})"

    loaded = load_trip(trip.id, data_dir=str(tmp_path), user_id=user_id)
    assert loaded is not None
    assert [c.notify for c in loaded.corridors] == [True, True], (
        f"Das Feld 'melden' ging beim Laden verloren: {loaded.corridors!r}"
    )
    save_trip(loaded, user_id=user_id, data_dir=str(tmp_path))

    after = json.loads(trip_file.read_text()).get("corridors")
    assert after == before, (
        "Das Wertebereichs-Array darf sich durch Laden+Speichern nicht "
        f"veraendern.\nvorher: {before!r}\nnachher: {after!r}"
    )

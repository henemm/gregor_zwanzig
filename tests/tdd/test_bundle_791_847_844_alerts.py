"""
TDD RED — Alert-Bundle #791 / #847 / #844

AC-1 (#791): Radar-Alert zeigt Lokalzeit, nicht UTC-Zeit
AC-2 (#847): Ziel-Segment-Label enthält Etappen-Angabe (z. B. "Ziel, Etappe 2")
AC-3 (#844): _fetch_fresh_weather überspringt zukünftige Segmente

Mock-Regel: KEIN Mock()/patch()/MagicMock.
- AC-1: RadarNowcastService(frame_source=_wet_frames) — DI-Seam mit echten Frames
- AC-1: TripAlertService(mail_sink=...) — DI-Seam statt SMTP
- AC-2: render_deviation_alert direkt aufrufen (pure function, kein API)
- AC-3: _fetch_fresh_weather direkt aufrufen, echter Open-Meteo-Call erlaubt

SPEC: docs/specs/modules/bundle_791_847_844_alert_fixes.md
"""
from __future__ import annotations

import shutil
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from app.models import (
    ChangeSeverity,
    GPXPoint,
    SegmentWeatherData,
    SegmentWeatherSummary,
    TripReportConfig,
    TripSegment,
    WeatherChange,
)
from app.trip import Stage, Trip, Waypoint

DATA_ROOT = Path(__file__).resolve().parents[2] / "data" / "users"


# ---------------------------------------------------------------------------
# Frame-Factory: echte RadarFrames via DI-Seam (kein Mock)
# ---------------------------------------------------------------------------

def _wet_frames(lat: float, lon: float) -> list:
    """Liefert Regen-Frames ab Minute 5 — triggert Radar-Alert.

    Nutzt dokumentierten DI-Seam frame_source Callable(lat,lon)->frames.
    """
    from providers.brightsky import RadarFrame
    now = datetime.now(timezone.utc)
    return [
        RadarFrame(timestamp=now + timedelta(minutes=5),  precip_mm_h=6.0),
        RadarFrame(timestamp=now + timedelta(minutes=20), precip_mm_h=8.0),
        RadarFrame(timestamp=now + timedelta(minutes=35), precip_mm_h=3.0),
    ]


# ---------------------------------------------------------------------------
# Trip-Helpers
# ---------------------------------------------------------------------------

def _make_waypoint(name: str, lat: float, lon: float, arrival_hhmm: str) -> Waypoint:
    return Waypoint(id=name, name=name, lat=lat, lon=lon,
                    elevation_m=500.0, arrival_calculated=arrival_hhmm)


def _save_trip_direct(trip: Trip, user_id: str) -> None:
    """Schreibt Trip-JSON direkt — umgeht Naismith-Compute-on-Save."""
    import json
    trips_dir = DATA_ROOT / user_id / "trips"
    trips_dir.mkdir(parents=True, exist_ok=True)

    def _wp_dict(wp: Waypoint) -> dict:
        d: dict = {"id": wp.id, "name": wp.name, "lat": wp.lat, "lon": wp.lon}
        if wp.elevation_m is not None:
            d["elevation_m"] = wp.elevation_m
        if wp.arrival_calculated is not None:
            d["arrival_calculated"] = wp.arrival_calculated
        return d

    def _stage_dict(s: Stage) -> dict:
        return {
            "id": s.id, "name": s.name,
            "date": s.date.isoformat(),
            "waypoints": [_wp_dict(w) for w in s.waypoints],
        }

    data: dict = {
        "id": trip.id, "name": trip.name,
        "stages": [_stage_dict(s) for s in trip.stages],
    }
    if trip.report_config is not None:
        rc = trip.report_config
        data["report_config"] = {
            "trip_id": rc.trip_id,
            "send_email": getattr(rc, "send_email", True),
            "send_telegram": getattr(rc, "send_telegram", False),
        }
    trips_dir.joinpath(f"{trip.id}.json").write_text(json.dumps(data, indent=2))


def _clean_user(uid: str) -> None:
    d = DATA_ROOT / uid
    if d.exists():
        shutil.rmtree(d)


def _make_segment(
    segment_id,
    lat: float,
    lon: float,
    start_offset_min: int,
    duration_min: int = 90,
) -> SegmentWeatherData:
    """Erstellt ein minimales SegmentWeatherData-Objekt für Tests."""
    now_utc = datetime.now(timezone.utc)
    start_time = now_utc + timedelta(minutes=start_offset_min)
    end_time = start_time + timedelta(minutes=duration_min)
    seg = TripSegment(
        segment_id=segment_id,
        start_point=GPXPoint(lat=lat, lon=lon, distance_from_start_km=0.0),
        end_point=GPXPoint(lat=lat + 0.05, lon=lon + 0.05, distance_from_start_km=5.0),
        start_time=start_time,
        end_time=end_time,
        duration_hours=duration_min / 60,
        distance_km=5.0,
        ascent_m=200.0,
        descent_m=50.0,
    )
    return SegmentWeatherData(
        segment=seg,
        timeseries=None,
        aggregated=SegmentWeatherSummary(),
        fetched_at=now_utc,
        provider="openmeteo",
    )


# ---------------------------------------------------------------------------
# AC-1: #791 — Radar-Alert zeigt Lokalzeit, nicht UTC
# ---------------------------------------------------------------------------

def test_ac1_radar_alert_onset_in_local_time():
    """
    AC-1: Given Radar-Alert für Trip in Europe/Paris (UTC+2) mit Onset in ~5 Min,
          When check_radar_alerts via mail_sink ausgeführt wird,
          Then enthält der Alert-Body die Lokalzeit (UTC+Offset), nicht UTC-Zeit.

    Regression-Test: Verifiziert den Fix aus Issue #822.
    RED-Kriterium: Wenn tz=tz in check_radar_alerts fehlt, wird onset_time
    in UTC formatiert → expected_local_hhmm != utc_hhmm → Test schlägt fehl.
    """
    from services.trip_alert import TripAlertService
    from services.radar_service import RadarNowcastService
    from utils.timezone import tz_for_coords

    # Corsica / GR20 → Europe/Paris (CEST = UTC+2 im Sommer, CET = UTC+1 im Winter)
    lat, lon = 42.387, 8.932
    tz = tz_for_coords(lat, lon)
    now_utc = datetime.now(timezone.utc)
    utc_offset = now_utc.astimezone(tz).utcoffset()
    offset_hours = int(utc_offset.total_seconds() / 3600)

    # Corsica gibt immer UTC+1 oder UTC+2 → dieser Check sollte nie greifen
    if offset_hours == 0:
        pytest.skip("tz_for_coords gibt UTC+0 zurück — Test kann UTC vs. Lokal nicht unterscheiden")

    # Onset: erster nasser Frame ist +5 Min → onset_minutes ≈ 5
    onset_minutes = 5
    onset_utc = now_utc + timedelta(minutes=onset_minutes)
    expected_local_hhmm = onset_utc.astimezone(tz).strftime("%H:%M")
    utc_hhmm = onset_utc.strftime("%H:%M")

    uid = f"tdd-791-{uuid.uuid4().hex[:6]}"
    _clean_user(uid)
    try:
        today = now_utc.date()
        wp0 = _make_waypoint("WP0", lat, lon,
                             (now_utc - timedelta(hours=1)).astimezone(tz).strftime("%H:%M"))
        wp1 = _make_waypoint("WP1", lat + 0.1, lon + 0.1,
                             (now_utc + timedelta(hours=3)).astimezone(tz).strftime("%H:%M"))
        stage = Stage(id="S1", name="Etappe 1", date=today, waypoints=[wp0, wp1])
        trip_id = f"tdd-791-trip-{uuid.uuid4().hex[:6]}"
        trip = Trip(id=trip_id, name="GR20 Test", stages=[stage])
        trip.report_config = TripReportConfig(
            trip_id=trip_id, send_email=True,
            send_telegram=False, alert_on_changes=False,
        )
        _save_trip_direct(trip, uid)

        captured: list[dict] = []

        def mail_sink(subject: str, body: str) -> None:
            captured.append({"subject": subject, "body": body})

        svc = TripAlertService(
            throttle_hours=0,
            user_id=uid,
            radar_service=RadarNowcastService(frame_source=_wet_frames),
            mail_sink=mail_sink,
        )
        svc.clear_radar_throttle(trip_id)
        svc.check_radar_alerts()

        assert len(captured) >= 1, (
            "AC-1: Kein Radar-Alert ausgelöst — check_radar_alerts hat nichts gesendet."
        )
        body = captured[0]["body"]

        # Lokalzeit muss im Body stehen
        assert expected_local_hhmm in body, (
            f"AC-1 FAIL: Lokalzeit '{expected_local_hhmm}' nicht im Body.\n"
            f"UTC wäre '{utc_hhmm}' (Offset: UTC+{offset_hours}h).\n"
            f"Body (Anfang): {body[:300]}"
        )

        # UTC-Zeit darf NICHT im Body stehen (wenn Offset ≠ 0)
        assert utc_hhmm not in body, (
            f"AC-1 FAIL: UTC-Zeit '{utc_hhmm}' im Body — Lokalzeit-Fix fehlt!\n"
            f"Erwartet: '{expected_local_hhmm}'. Body: {body[:300]}"
        )

    finally:
        _clean_user(uid)


# ---------------------------------------------------------------------------
# AC-2: #847 — Ziel-Segment-Label enthält Etappen-Angabe
# ---------------------------------------------------------------------------

def test_ac2_ziel_segment_label_includes_stage():
    """
    AC-2: Given Wetteränderungs-Alert mit Ziel-Segment von Etappe 2,
          When render_deviation_alert aufgerufen wird,
          Then enthält die Plain-Text-Ausgabe "Ziel, Etappe 2".

    RED-Kriterium: render_deviation_alert übergibt stage_label NICHT an _line()
    → build_segment_label für Ziel gibt nur "🏁 Ziel (HH:MM)" zurück.
    → "Etappe 2" fehlt im plain-Text → AssertionError.
    """
    from output.renderers.alert.render import render_deviation_alert

    now_utc = datetime.now(timezone.utc)

    # Ziel-Segment: minimal aber korrekt
    ziel_seg = TripSegment(
        segment_id="Ziel",
        start_point=GPXPoint(lat=42.387, lon=8.932, distance_from_start_km=0.0),
        end_point=GPXPoint(lat=42.387, lon=8.932, distance_from_start_km=0.0),
        start_time=now_utc + timedelta(hours=3),
        end_time=now_utc + timedelta(hours=4),
        duration_hours=1.0,
        distance_km=0.0,
        ascent_m=0.0,
        descent_m=0.0,
    )
    ziel_data = SegmentWeatherData(
        segment=ziel_seg,
        timeseries=None,
        aggregated=SegmentWeatherSummary(),
        fetched_at=now_utc,
        provider="openmeteo",
    )

    # Wetteränderung am Ziel-Segment
    change = WeatherChange(
        metric="temp_max_c",
        old_value=18.0,
        new_value=28.0,
        delta=10.0,
        threshold=5.0,
        severity=ChangeSeverity.MODERATE,
        direction="increase",
        segment_id="Ziel",
    )

    _html, plain = render_deviation_alert(
        changes=[change],
        segments=[ziel_data],
        trip_name="GR20",
        tz=ZoneInfo("Europe/Paris"),
        stage_label="Etappe 2",
    )

    # Vor Fix: "🏁 Ziel (15:02)" — kein "Etappe 2"
    # Nach Fix: "🏁 Ziel, Etappe 2 (15:02)"
    assert "Ziel, Etappe 2" in plain, (
        f"AC-2 FAIL: 'Ziel, Etappe 2' nicht im Plain-Text.\n"
        f"stage_label wird nicht an _line()/build_segment_label weitergegeben.\n"
        f"Plain-Text: {plain!r}"
    )


# ---------------------------------------------------------------------------
# AC-3: #844 — Zukünftige Segmente werden nicht gefetcht
# ---------------------------------------------------------------------------

def test_ac3_no_fetch_for_future_segments():
    """
    AC-3: Given Trip mit 2 Segmenten — Segment 3 (aktiv, heute) und Segment 4 (beginnt morgen),
          When _fetch_fresh_weather aufgerufen wird,
          Then enthält das Ergebnis kein Segment-4-Element.

    Korrekte Logik: absolvierte Segmente UND Segmente an zukünftigen Tagen werden
    übersprungen. Heutige Zukunftssegmente werden gefetcht (Alerts für den Rest des Tages).
    Echter Open-Meteo-API-Call für Segment 3 ist erlaubt und erwartet.
    """
    from services.trip_alert import TripAlertService

    uid = f"tdd-844-{uuid.uuid4().hex[:6]}"
    _clean_user(uid)
    try:
        # Corsica-Koordinaten für realistische API-Anfrage
        lat, lon = 42.387, 8.932

        # Segment 3: begann vor 30 Minuten (aktiv/vergangen)
        seg3 = _make_segment(3, lat, lon, start_offset_min=-30)

        # Segment 4: beginnt erst morgen (zukünftiger Tag — soll übersprungen werden)
        seg4 = _make_segment(4, lat + 0.1, lon + 0.1, start_offset_min=60 * 24 + 60)  # morgen

        svc = TripAlertService(throttle_hours=0, user_id=uid)

        result = svc._fetch_fresh_weather([seg3, seg4])

        result_segment_ids = {str(w.segment.segment_id) for w in result}

        # Kernbehauptung: Segment 4 darf nicht gefetcht worden sein
        assert "4" not in result_segment_ids, (
            f"AC-3 FAIL: Segment 4 (startet morgen) wurde gefetcht — "
            f"_fetch_fresh_weather filtert zukünftige Tage nicht.\n"
            f"Gefundene segment_ids: {result_segment_ids}"
        )

        # Positiv-Check: aktives Segment 3 muss gefetcht worden sein
        assert "3" in result_segment_ids, (
            f"AC-3 FAIL: Segment 3 (aktiv) wurde nicht gefetcht — "
            f"API-Fehler oder Filter zu restriktiv.\n"
            f"Gefundene segment_ids: {result_segment_ids}"
        )

    finally:
        _clean_user(uid)


# ---------------------------------------------------------------------------
# AC-3b: #844 (Re-Open) — Vergangene Segmente werden nicht gefetcht
# ---------------------------------------------------------------------------

def test_ac3b_no_fetch_for_past_segments():
    """
    AC-3b: Given Trip mit 2 Segmenten — Segment X endete vor 60 Minuten (absolviert)
           und Segment Y läuft aktuell (aktiv),
           When _fetch_fresh_weather aufgerufen wird,
           Then enthält das Ergebnis kein Segment-X-Element.

    RED-Kriterium: Der bisherige Filter prüft nur `start_time > now_utc` (Zukunft).
    Vergangene Segmente (end_time < now_utc) passieren diesen Filter —
    sie werden gefetcht und lösen Alerts aus.
    Nach korrektem Fix (`not (start <= now <= end)`): X wird übersprungen.

    Echter Open-Meteo-API-Call für das aktive Segment Y ist erlaubt.
    """
    from services.trip_alert import TripAlertService

    uid = f"tdd-844b-{uuid.uuid4().hex[:6]}"
    _clean_user(uid)
    try:
        lat, lon = 42.387, 8.932

        # Segment X: startete vor 2h, dauerte 60 Min → endete vor 60 Min (ABSOLVIERT)
        seg_past = _make_segment("X", lat, lon, start_offset_min=-120, duration_min=60)

        # Segment Y: startete vor 30 Min, dauert 90 Min → endet in 60 Min (AKTIV)
        seg_active = _make_segment("Y", lat + 0.1, lon + 0.1, start_offset_min=-30, duration_min=90)

        svc = TripAlertService(throttle_hours=0, user_id=uid)

        result = svc._fetch_fresh_weather([seg_past, seg_active])

        result_segment_ids = {str(w.segment.segment_id) for w in result}

        # Kernbehauptung: Segment X (absolviert) darf nicht gefetcht worden sein
        assert "X" not in result_segment_ids, (
            f"AC-3b FAIL: Segment X (end_time vor 60 Min) wurde gefetcht — "
            f"_fetch_fresh_weather filtert vergangene Segmente nicht.\n"
            f"Gefundene segment_ids: {result_segment_ids}"
        )

        # Aktives Segment Y muss gefetcht worden sein
        assert "Y" in result_segment_ids, (
            f"AC-3b FAIL: Segment Y (aktiv) fehlt im Ergebnis — "
            f"nur aktive Segmente sollen gefetcht werden.\n"
            f"Gefundene segment_ids: {result_segment_ids}"
        )

    finally:
        _clean_user(uid)

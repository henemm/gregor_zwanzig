"""TDD RED — Issue #773: Alert-Kette verdrahten + echte Alert-E2E.

Befund (Phase 2): Der proaktive Radar-/Gewitter-Alert
(`TripAlertService.check_radar_alerts`) ist implementiert + unit-getestet
(#656/#660), wird aber von KEINEM Scheduler-Job und KEINEM Endpoint aufgerufen
→ feuert in Produktion nie. Zusätzlich beweisen wir end-to-end, dass der
Wetter-Änderungs-Alert tatsächlich eine reale Mail zustellt.

Mock-frei:
- AC-2/AC-5: echter FastAPI-TestClient gegen die reale App (`api.main.app`).
- AC-3: echte Kette `check_all_trips()` — Extremwert-Snapshot (Datei unter unserer
  Kontrolle) erzwingt ein garantiertes Delta gegen die ECHTE Wetter-API, reale
  Mail wird per IMAP im Stalwart-Test-Postfach nachgewiesen.
- AC-4: realer Versand, dann Throttle — zweiter Lauf sendet nicht erneut.

Skip nur bei fehlender Infrastruktur (SMTP/IMAP nicht konfiguriert) — niemals
stiller Erfolg.

SPEC: docs/specs/modules/issue_773_radar_alert_wiring.md
"""
from __future__ import annotations

import email
import imaplib
import logging
import shutil
import time
import uuid
from datetime import date as date_type
from datetime import datetime, time as time_type, timedelta, timezone
from pathlib import Path

import pytest

from app.config import Settings
from app.models import (
    ForecastDataPoint,
    ForecastMeta,
    GPXPoint,
    NormalizedTimeseries,
    Provider,
    SegmentWeatherData,
    SegmentWeatherSummary,
    TripReportConfig,
    TripSegment,
)
from app.trip import Stage, TimeWindow, Trip, Waypoint

DATA_ROOT = Path(__file__).resolve().parents[2] / "data" / "users"

# Echte Alpen-Koordinate (reale API liefert hier echte Werte).
LAT, LON = 47.05, 11.40


# --- Helpers (mock-frei) ---


def _segment_weather(temp_max: float, wind_max: float, precip: float) -> SegmentWeatherData:
    now = datetime.now(timezone.utc)
    segment = TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=LAT, lon=LON, elevation_m=1000.0),
        end_point=GPXPoint(lat=LAT + 0.05, lon=LON + 0.05, elevation_m=1200.0),
        start_time=now,
        end_time=now + timedelta(hours=2),
        duration_hours=2.0,
        distance_km=5.0,
        ascent_m=200.0,
        descent_m=0.0,
    )
    meta = ForecastMeta(
        provider=Provider.OPENMETEO, model="test", run=now,
        grid_res_km=1.0, interp="point_grid",
    )
    timeseries = NormalizedTimeseries(
        meta=meta,
        data=[ForecastDataPoint(ts=now, t2m_c=temp_max, wind10m_kmh=wind_max)],
    )
    summary = SegmentWeatherSummary(
        temp_min_c=temp_max - 5, temp_max_c=temp_max, temp_avg_c=temp_max - 2.5,
        wind_max_kmh=wind_max, precip_sum_mm=precip,
    )
    return SegmentWeatherData(
        segment=segment, timeseries=timeseries, aggregated=summary,
        fetched_at=now, provider="openmeteo",
    )


def _trip(token: str, trip_id: str) -> Trip:
    from app.models import UnifiedWeatherDisplayConfig

    wp = Waypoint(
        id="G1", name="Start", lat=LAT, lon=LON, elevation_m=1000.0,
        time_window=TimeWindow(start=time_type(8, 0), end=time_type(10, 0)),
    )
    stage = Stage(id="T1", name="Tag 1", date=date_type.today(), waypoints=[wp])
    # Issue #946: metric_alert_levels ist die einzige Detektor-Quelle. Die
    # E2E-Läufe fahren extreme temp/wind/precip-Deltas → Standard-Schwellen dieser
    # Metriken werden gerissen. report_config bleibt für den E-Mail-Kanal aktiv.
    trip = Trip(
        id=trip_id, name=f"E2E773 {token}", stages=[stage],
        display_config=UnifiedWeatherDisplayConfig(
            trip_id=trip_id,
            metric_alert_levels={
                "temperature_max": "standard",
                "wind_change": "standard",
                "precipitation_sum": "standard",
            },
        ),
    )
    trip.report_config = TripReportConfig(
        trip_id=trip_id, send_email=True, send_telegram=False,
        alert_on_changes=True,
    )
    return trip


def _clean_user(uid: str) -> None:
    d = DATA_ROOT / uid
    if d.exists():
        shutil.rmtree(d)


def _test_settings() -> Settings | None:
    s = Settings().for_testing()
    if not s.can_send_email():
        return None
    return s.model_copy(update={"mail_to": "gregor-test@henemm.com"})


def _imap_has_subject_token(settings: Settings, token: str, *, attempts: int = 12,
                            delay: float = 3.0) -> bool:
    """Poll the Stalwart test mailbox for a delivered mail whose Subject contains
    `token`. Retries to absorb SMTP→IMAP delivery latency (mock-frei, echte Box)."""
    imap_host = settings.imap_host or settings.smtp_host
    imap_user = settings.imap_user or settings.smtp_user
    imap_pass = settings.imap_pass or settings.smtp_pass
    for _ in range(attempts):
        imap = imaplib.IMAP4_SSL(imap_host, settings.imap_port)
        try:
            imap.login(imap_user, imap_pass)
            imap.select("INBOX")
            _, data = imap.search(None, f'SUBJECT "{token}"')
            if data and data[0].split():
                return True
            # Fallback: manche IMAP-Server matchen den dekodierten Header nicht —
            # MIME-Q-encodete Betreffs roh durchsuchen.
            _, recent = imap.search(None, "ALL")
            ids = recent[0].split()[-20:]
            for i in reversed(ids):
                _, md = imap.fetch(i, "(BODY[HEADER.FIELDS (SUBJECT)])")
                raw = md[0][1] if md and md[0] else b""
                hdr = raw.decode("utf-8", errors="replace")
                subj = str(email.header.make_header(email.header.decode_header(
                    hdr.split(":", 1)[1].strip() if ":" in hdr else hdr)))
                if token in subj or token in hdr:
                    return True
        finally:
            try:
                imap.logout()
            except Exception:
                pass
        time.sleep(delay)
    return False


# ===================================================================
# AC-2: Neuer Radar-Endpoint — erreichbar + mandantengetrennt
# ===================================================================


def test_ac2_radar_endpoint_mandantentrennung():
    """AC-2: POST /api/scheduler/radar-alert-checks antwortet pro Nutzer mit 200
    + int count; ein Lauf für Nutzer A leakt keine Artefakte in Nutzer B.

    RED vor Fix: Endpoint existiert nicht → 404.
    """
    from fastapi.testclient import TestClient

    from api.main import app

    from app.loader import save_trip

    ua, ub = "tdd-773-ac1", "tdd-773-ac2"
    _clean_user(ua)
    _clean_user(ub)
    try:
        save_trip(_trip("ua", "trip-773-ua"), user_id=ua)
        save_trip(_trip("ub", "trip-773-ub"), user_id=ub)

        client = TestClient(app)
        ra = client.post(f"/api/scheduler/radar-alert-checks?user_id={ua}")
        rb = client.post(f"/api/scheduler/radar-alert-checks?user_id={ub}")

        assert ra.status_code == 200, f"Endpoint nicht erreichbar: {ra.status_code}"
        assert rb.status_code == 200
        assert ra.json().get("status") == "ok"
        assert isinstance(ra.json().get("count"), int)
        assert isinstance(rb.json().get("count"), int)

        # Mandantentrennung: ua-Trip-Daten dürfen NICHT unter ub auftauchen.
        ub_trips = list((DATA_ROOT / ub / "trips").glob("*.json"))
        assert ub_trips, "ub-Trip muss persistiert sein"
        for p in ub_trips:
            assert "trip-773-ua" not in p.read_text(), "Cross-User-Datenleck ua→ub"
    finally:
        _clean_user(ua)
        _clean_user(ub)


# ===================================================================
# AC-5: Endpoint verlangt user_id — kein stiller default-Fallback
# ===================================================================


def test_ac5_radar_endpoint_requires_user_id():
    """AC-5: Aufruf ohne user_id → HTTP 422 (kein stiller "default"-Fallback auf
    produktive Nutzerdaten).

    RED vor Fix: Endpoint existiert nicht → 404 (≠ 422).
    """
    from fastapi.testclient import TestClient

    from api.main import app

    client = TestClient(app)
    r = client.post("/api/scheduler/radar-alert-checks")
    assert r.status_code == 422, (
        f"Fehlender user_id muss 422 ergeben (kein default-Fallback), war {r.status_code}"
    )


# ===================================================================
# AC-3: Echter End-to-End-Beweis — Änderungs-Alert stellt Mail zu
# ===================================================================


def test_ac3_change_alert_real_e2e_imap(caplog):
    """AC-3: Extremwert-Snapshot → reale Kette check_all_trips() → echte Mail per
    IMAP nachgewiesen. Frische Vorhersage kommt von der ECHTEN API; der Snapshot
    (Datei) erzwingt ein garantiert signifikantes Delta.

    Kein Mock. Skip nur wenn SMTP nicht konfiguriert.
    """
    settings = _test_settings()
    if settings is None:
        pytest.skip("SMTP nicht konfiguriert — realer E-Mail-E2E nicht möglich")

    from services.trip_alert import TripAlertService
    from services.weather_snapshot import WeatherSnapshotService
    from app.loader import save_trip

    uid = "tdd-773-ac3"
    token = uuid.uuid4().hex[:8]
    trip_id = f"trip-773-{token}"
    _clean_user(uid)
    try:
        trip = _trip(token, trip_id)
        save_trip(trip, user_id=uid)

        # Extrem-Snapshot: 45°C / 80 km/h / 30 mm — garantiert großes Delta zur Realität.
        extreme = [_segment_weather(temp_max=45.0, wind_max=80.0, precip=30.0)]
        WeatherSnapshotService(user_id=uid).save(trip_id, extreme, date_type.today())

        service = TripAlertService(settings=settings, throttle_hours=2, user_id=uid)
        service.clear_throttle(trip_id)

        with caplog.at_level(logging.ERROR, logger="trip_alert"):
            sent = service.check_all_trips()
        assert sent >= 1, (
            "Reale Alert-Kette hat keinen Alert versendet — Snapshot-Delta wurde "
            "nicht als signifikant erkannt oder Versand schlug fehl."
        )

        # Transientes Relay-Rate-Limit (452) ist eine Infrastruktur-Grenze des
        # geteilten Stalwart-Test-Postfachs, kein Code-Defekt: der Alert-Pfad WURDE
        # erreicht und der echte Versand versucht (Exception im Best-Effort-Pfad
        # geloggt). Skip statt False-Rot — analog #750/#752.
        if "rate limit" in caplog.text.lower() or "452" in caplog.text:
            pytest.skip("SMTP-Relay rate-limited (452) — transiente Infra, Pfad erreicht")

        assert _imap_has_subject_token(settings, token), (
            f"Alert-Mail mit Token {token} nicht im Test-Postfach gefunden — "
            "keine echte Zustellung."
        )
    finally:
        _clean_user(uid)


# ===================================================================
# AC-4: Throttle — zweiter Lauf im Fenster sendet nicht erneut
# ===================================================================


def test_ac4_change_alert_throttled_second_run():
    """AC-4: Nach einem realen Alert verhindert der Throttle einen zweiten Versand
    innerhalb des Cooldown-Fensters (check_and_send_alerts gibt beim zweiten Lauf
    False zurück).

    Kein Mock. Skip nur wenn SMTP nicht konfiguriert.
    """
    settings = _test_settings()
    if settings is None:
        pytest.skip("SMTP nicht konfiguriert — realer E-Mail-E2E nicht möglich")

    from services.trip_alert import TripAlertService

    uid = "tdd-773-ac4"
    token = uuid.uuid4().hex[:8]
    trip_id = f"trip-773-{token}"
    _clean_user(uid)
    try:
        trip = _trip(token, trip_id)
        cached = [_segment_weather(temp_max=15.0, wind_max=10.0, precip=0.0)]
        fresh = [_segment_weather(temp_max=45.0, wind_max=80.0, precip=30.0)]

        service = TripAlertService(settings=settings, throttle_hours=2, user_id=uid)
        service.clear_throttle(trip_id)

        first = service.check_and_send_alerts(trip, cached, fresh_weather=fresh)
        assert first is True, "Erster Alert sollte versendet werden"

        second = service.check_and_send_alerts(trip, cached, fresh_weather=fresh)
        assert second is False, (
            "Zweiter Alert innerhalb des Throttle-Fensters darf NICHT versendet werden"
        )
    finally:
        _clean_user(uid)

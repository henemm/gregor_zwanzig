"""TDD RED — Issue #1948 (Scheibe S1): ``alert_log.append_entry``/
``append_suppressed_entry`` bekommen ein optionales ``capture_id``-Feld;
Alt-Eintraege ohne das Feld bleiben unveraendert lesbar; Zweig-b/c-
Korrelation ueber ``alert_input_capture.latest_capture_id()``.

SPEC: docs/specs/modules/alarm_eingangsprotokoll.md (AC-4)

RED-Grund: ``append_entry()``/``append_suppressed_entry()`` kennen den
Parameter ``capture_id`` noch nicht -- ein Aufruf mit diesem Keyword
scheitert heute mit ``TypeError: unexpected keyword argument``.
``services.alert_input_capture`` existiert nicht.

Mock-frei: ``append_entry``/``append_suppressed_entry`` sind bereits die
geteilten, direkt aufgerufenen Bausteine (Vorbild
``tests/unit/test_alert_log_premium_sms_channel.py``); ``alert_log.json``
wird danach als echte Datei gelesen.

Nachtrag (Adversary-Findings F001/F002, Runde nach GREEN): die vier
Tests oben pruefen ``append_entry``/``append_suppressed_entry`` bzw. den
Capture-Lookup je fuer sich -- keiner davon laeuft ueber die tatsaechliche
Verdrahtungsstelle in ``trip_alert.py`` (Zweig a: Z. ~401, Zweig c:
Z. ~1373). Eine Mutation ``capture_id=capture_id`` -> ``capture_id=None``
an diesen Stellen blieb dadurch ungefangen. Die beiden End-to-End-Tests am
Dateiende schliessen genau diese Luecke: echter ``check_and_send_alerts()``-
bzw. ``check_radar_alerts()``-Lauf, danach Gleichheit zwischen dem
geschriebenen ``alert_log``-Eintrag und dem zuvor geschriebenen
Eingangs-Datensatz geprueft (nicht nur "Feld vorhanden").
"""
from __future__ import annotations

import json
import uuid

from services import alert_log


def _uid(prefix: str) -> str:
    return f"tdd-1948-log-{prefix}-{uuid.uuid4().hex[:6]}"


def _read_log(user_id: str) -> dict:
    from app.loader import get_data_dir

    path = get_data_dir(user_id) / "alert_log.json"
    data = json.loads(path.read_text())
    data.setdefault("entries", [])
    data.setdefault("not_delivered", [])
    return data


def test_ac4_append_entry_schreibt_capture_id_feld():
    """AC-4: GIVEN ein Eingangs-Datensatz mit einer bestimmten
    ``capture_id`` wurde erzeugt, WHEN ``alert_log.append_entry()`` mit
    diesem ``capture_id``-Argument aufgerufen wird, THEN traegt der
    geschriebene Eintrag ein ``capture_id``-Feld mit genau diesem Wert."""
    uid = _uid("entry")
    alert_log.append_entry(
        uid, entity_id="trip-cap-1", entity_type="trip", changes_count=1,
        severity="moderate", reason=alert_log.REASON_FORECAST_CHANGE,
        effective_channels=["email"], sent_channels=["email"],
        capture_id="cap-abcdef123456",
    )
    entry = _read_log(uid)["entries"][-1]
    assert entry.get("capture_id") == "cap-abcdef123456", (
        f"capture_id fehlt oder falsch im Eintrag: {entry!r}"
    )


def test_ac4_append_suppressed_entry_schreibt_capture_id_feld():
    """AC-4: dieselbe Zusicherung fuer den Unterdrueckungs-Pfad
    ``append_suppressed_entry()``."""
    uid = _uid("suppressed")
    alert_log.append_suppressed_entry(
        uid, entity_id="trip-cap-2", entity_type="trip",
        reason=alert_log.REASON_NOWCAST, gate_reason="quiet_hours",
        effective_channels=["email"], capture_id="cap-fedcba654321",
    )
    entry = _read_log(uid)["not_delivered"][-1]
    assert entry.get("capture_id") == "cap-fedcba654321", (
        f"capture_id fehlt oder falsch im Unterdrueckungs-Eintrag: {entry!r}"
    )


def test_ac4_alt_eintraege_ohne_capture_id_bleiben_unveraendert_lesbar():
    """AC-4 (Bestandsschutz): GIVEN ein alter Eintrag ohne ``capture_id``-
    Feld liegt bereits in ``alert_log.json``, WHEN ein neuer Eintrag MIT
    ``capture_id`` dazukommt, THEN bleibt der alte Eintrag strukturell
    unveraendert (kein ``capture_id``-Schluessel wird nachtraeglich
    eingefuegt)."""
    from app.loader import get_data_dir

    uid = _uid("legacy")
    path = get_data_dir(uid) / "alert_log.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    legacy_entry = {
        "entity_id": "trip-legacy", "entity_type": "trip",
        "sent_at": "2026-01-01T00:00:00+00:00", "changes_count": 1,
        "severity": "minor", "metrics": [], "hazards": [],
        "reason": "forecast_change", "channels_sent": ["email"],
        "channels_not_sent": [],
    }
    path.write_text(json.dumps({"entries": [legacy_entry], "not_delivered": []}))

    alert_log.append_entry(
        uid, entity_id="trip-new", entity_type="trip", changes_count=1,
        severity="moderate", reason=alert_log.REASON_FORECAST_CHANGE,
        effective_channels=["email"], sent_channels=["email"],
        capture_id="cap-neu",
    )

    entries = _read_log(uid)["entries"]
    assert entries[0] == legacy_entry, f"Alt-Eintrag wurde veraendert: {entries[0]!r}"
    assert entries[1].get("capture_id") == "cap-neu", (
        f"Neuer Eintrag traegt keine capture_id: {entries[1]!r}"
    )


def test_ac4_latest_capture_id_lookup_liefert_korrelierbare_id():
    """AC-4 (Zweig b/c-Korrelation): GIVEN ein Eingangs-Datensatz wurde fuer
    einen bestimmten (branch, source_key) geschrieben, WHEN der zugehoerige
    alert_log-Eintrag ueber ``latest_capture_id()`` nach demselben Branch/
    Quell-Schluessel und einem ausreichenden Zeitfenster sucht, THEN
    liefert der Lookup dieselbe ``capture_id`` wie der Eingangs-Datensatz,
    und der damit geschriebene alert_log-Eintrag traegt sie."""
    from services import alert_input_capture

    uid = _uid("lookup")
    written_id = alert_input_capture.capture_system(
        branch="official_alert", source_key="AT-lookup-1948",
        payload={
            "body": {"features": []}, "service": "meteoalarm", "host": "x",
            "cache_key": "AT-lookup-1948",
        },
    )
    assert written_id, "capture_system() lieferte keine capture_id."

    found_id = alert_input_capture.latest_capture_id(
        "official_alert", "AT-lookup-1948", max_age=60.0,
    )
    assert found_id == written_id, (
        f"latest_capture_id() fand nicht dieselbe capture_id: "
        f"{found_id!r} != {written_id!r}"
    )

    alert_log.append_entry(
        uid, entity_id="trip-lookup", entity_type="trip", changes_count=1,
        severity="moderate", reason=alert_log.REASON_OFFICIAL_ALERT,
        effective_channels=["email"], sent_channels=["email"],
        capture_id=found_id,
    )
    entry = _read_log(uid)["entries"][-1]
    assert entry.get("capture_id") == written_id, (
        f"alert_log-Eintrag traegt nicht dieselbe capture_id: {entry!r}"
    )


# ══════════════ End-to-End (Adversary F001/F002-Gegenprobe) ═══════════════


def test_ac4_e2e_zweig_a_alert_log_capture_id_matches_written_input_record():
    """AC-4 (E2E, F001): GIVEN ein echter Delta-Alarm-Lauf
    (``check_and_send_alerts``) schreibt sowohl einen Eingangs-Datensatz
    (Zweig a) als auch einen ``alert_log``-Eintrag, WHEN beide gelesen
    werden, THEN tragen sie DIESELBE ``capture_id`` -- nicht nur je fuer
    sich ein gefuelltes Feld. Faengt die Mutation ``capture_id=capture_id``
    -> ``capture_id=None`` in ``trip_alert.py`` (Zeile ~401), die von den
    isolierten Tests oben ungefangen blieb."""
    from app.loader import get_data_dir
    from services.trip_alert import TripAlertService

    from tests.helpers.alert_log_fixtures import (
        fresh_user, gust_alert_trip, settings_email_only, weather,
    )

    uid = fresh_user("ac4-e2e-a")
    trip = gust_alert_trip("trip-ac4-e2e-a")
    mails: list = []
    svc = TripAlertService(
        settings=settings_email_only(), user_id=uid, throttle_hours=0,
        mail_sink=lambda subject, body: mails.append((subject, body)),
    )

    sent = svc.check_and_send_alerts(
        trip, [weather(1, gust_max_kmh=20.0)],
        fresh_weather=[weather(1, gust_max_kmh=60.0)],
    )
    assert sent is True and mails, "Voraussetzung: der Alarm muss verschickt werden."

    capture_files = sorted((get_data_dir(uid) / "alert_input").glob("*.json"))
    assert capture_files, "Kein Eingangs-Datensatz unter alert_input/ gefunden."
    written_capture_id = json.loads(capture_files[-1].read_text())["capture_id"]
    assert written_capture_id, "Eingangs-Datensatz traegt keine capture_id."

    log_entry = _read_log(uid)["entries"][-1]
    assert log_entry.get("capture_id") == written_capture_id, (
        f"alert_log-Eintrag traegt eine ANDERE capture_id als der "
        f"Eingangs-Datensatz: log={log_entry.get('capture_id')!r} != "
        f"input={written_capture_id!r}"
    )


def test_ac4_e2e_zweig_c_alert_log_capture_id_matches_written_input_record():
    """AC-4 (E2E, F002): GIVEN ein echter Nowcast-Alarm-Lauf
    (``check_radar_alerts``, echter ``RadarNowcastService`` ueber die
    ``frame_source``-DI-Naht -- KEIN Subklassen-Override von
    ``get_nowcast()``, sonst liefe der Capture-Mount-Punkt gar nicht mit)
    schreibt sowohl einen Eingangs-Datensatz (Zweig c, unter
    ``data/debug/alert_input/nowcast/``) als auch einen ``alert_log``-
    Eintrag (``REASON_NOWCAST``), WHEN beide gelesen werden, THEN tragen
    sie DIESELBE ``capture_id``. Faengt die Mutation
    ``capture_id=_nowcast_capture_id`` -> ``capture_id=None`` in
    ``trip_alert.py`` (Zeile ~1373)."""
    from datetime import datetime, timedelta, timezone
    from datetime import time as time_type

    from app.config import Settings
    from app.loader import get_data_root, save_trip
    from app.models import TripReportConfig
    from app.trip import Stage, TimeWindow, Trip, Waypoint
    from providers.brightsky import RadarFrame
    from services.radar_cache import RadarNowcastCacheService
    from services.radar_service import RadarNowcastService, _nowcast_source_key
    from services.trip_alert import TripAlertService

    from tests.helpers.alert_log_fixtures import fresh_user
    from tests.helpers.arrival_window_fixtures import active_window_offsets, stage_date

    uid = fresh_user("ac4-e2e-c")
    trip_id = "trip-ac4-e2e-c"
    lat, lon = 42.20, 9.10

    # Wanduhr-robustes aktives Segment (#1940/#1667 S1): rohe
    # (now +/- timedelta).strftime()-Arithmetik wird von
    # tests/tdd/test_fixture_wallclock_ratchet.py verboten -- sie wird
    # zwischen ~22:00 und 00:00 UTC reproduzierbar rot (Bezugstag-Bruch).
    start_str, end_str = active_window_offsets(lat, lon, -60, 180)
    wp0 = Waypoint(
        id="G1", name="Start", lat=lat, lon=lon, elevation_m=1000.0,
        time_window=TimeWindow(start=time_type(0, 0), end=time_type(23, 57)),
        arrival_override=start_str,
    )
    wp1 = Waypoint(
        id="G2", name="Ziel", lat=lat + 0.05, lon=lon + 0.05, elevation_m=1200.0,
        time_window=TimeWindow(start=time_type(23, 58), end=time_type(23, 59)),
        arrival_override=end_str,
    )
    stage = Stage(id="T1", name="Tag 1", date=stage_date(lat, lon), waypoints=[wp0, wp1])
    trip = Trip(id=trip_id, name="AC4-E2E-C", stages=[stage])
    trip.report_config = TripReportConfig(
        trip_id=trip_id, send_email=True, send_telegram=False, send_sms=False,
        alert_on_changes=True,
    )
    save_trip(trip, user_id=uid)

    now_utc = datetime.now(timezone.utc)
    frames = [
        RadarFrame(timestamp=now_utc + timedelta(minutes=i), precip_mm_h=(2.5 if i >= 5 else 0.0))
        for i in range(0, 60, 5)
    ]
    radar_svc = RadarNowcastService(
        frame_source=lambda _lat, _lon: frames, cache=RadarNowcastCacheService(),
    )
    mails: list = []
    settings = Settings().model_copy(update={
        "smtp_host": "smtp.test.invalid", "smtp_user": "alert@test.invalid",
        "smtp_pass": "secret", "mail_to": "gregor-test@henemm.com",
        "smtp_port": 587, "is_test_mode": False,
        "telegram_bot_token": "", "telegram_chat_id": "",
    })
    svc = TripAlertService(
        settings=settings, throttle_hours=0, user_id=uid,
        radar_service=radar_svc,
        mail_sink=lambda subject, body: mails.append((subject, body)),
    )

    result = svc.check_radar_alerts()
    assert result == 1 and mails, (
        f"check_radar_alerts() sollte 1 Alert liefern und eine Mail senden, "
        f"war result={result!r}, mails={mails!r}"
    )

    capture_dir = get_data_root() / "debug" / "alert_input" / "nowcast"
    capture_files = sorted(capture_dir.glob(f"{_nowcast_source_key(lat, lon)}_*.json"))
    assert capture_files, "Kein Eingangs-Datensatz unter data/debug/alert_input/nowcast/ gefunden."
    written_capture_id = json.loads(capture_files[-1].read_text())["capture_id"]
    assert written_capture_id, "Eingangs-Datensatz traegt keine capture_id."

    log_entry = _read_log(uid)["entries"][-1]
    assert log_entry.get("reason") == alert_log.REASON_NOWCAST
    assert log_entry.get("capture_id") == written_capture_id, (
        f"alert_log-Eintrag (Zweig c) traegt eine ANDERE capture_id als der "
        f"Eingangs-Datensatz: log={log_entry.get('capture_id')!r} != "
        f"input={written_capture_id!r}"
    )

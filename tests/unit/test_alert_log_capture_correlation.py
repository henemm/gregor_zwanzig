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


def _erwarteter_messpunkt(trip, now_utc):
    """``(lat, lon)``, an denen ``check_radar_alerts()`` seit Issue #2017
    abfragt: die zur Mitte des Vorwarnfensters interpolierte Position auf dem
    aktiven Segment.

    ANALYTISCH aus den Segmentgrenzen gerechnet — bewusst OHNE
    ``position_at_time()``: der Erwartungswert darf nicht aus dem Pruefling
    stammen, sonst machte er jede Verfaelschung mit.

    Der Zieloffset kommt ueber die MODUL-Referenz auf
    ``RADAR_ONSET_THRESHOLD_MIN``, nie als ``from ... import`` gebunden — der
    Laufzeit-Drift-Waechter aus #2009 setzt die Konstante zur Laufzeit um.
    """
    from datetime import timedelta

    from services import radar_service as radar_service_mod
    from services.trip_day import trip_local_today
    from services.trip_segments import resolve_current_segment

    aufgeloest = resolve_current_segment(trip, now_utc, trip_local_today(trip, now_utc))
    assert aufgeloest is not None, "Testvoraussetzung: aktives Segment noetig"
    active, _segment_date = aufgeloest
    at = now_utc + timedelta(
        minutes=radar_service_mod.RADAR_ONSET_THRESHOLD_MIN // 2
    )
    spanne = (active.end_time - active.start_time).total_seconds()
    p = max(0.0, min(1.0, (at - active.start_time).total_seconds() / spanne))
    sp, ep = active.start_point, active.end_point
    return (sp.lat + p * (ep.lat - sp.lat), sp.lon + p * (ep.lon - sp.lon))


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
    ``trip_alert.py`` (Zeile ~1373).

    #1948 AC-4 -> #2017: Die Zusicherung ist unveraendert "der geschriebene
    Eingangs-Datensatz gehoert zu GENAU DIESEM Abruf". Bis #2017 wurde sie
    ueber den Korrelations-Schluessel des Segment-STARTPUNKTS geprueft
    (``_nowcast_source_key(42.20, 9.10)``, die Wegpunkt-Koordinate). Seit
    #2017 fragt ``check_radar_alerts()`` an der zur Mitte des Vorwarnfensters
    interpolierten Position ab und legt den Datensatz folglich unter DEREN
    Schluessel ab.

    🔴 Nachgezogen, nicht gelockert: Geprueft wird weiterhin, dass der
    Datensatz zu genau diesem Abruf gehoert — nur wird der erwartete Ort
    jetzt ANALYTISCH aus den Segmentgrenzen gerechnet
    (``_erwarteter_messpunkt()``, ohne Aufruf von ``position_at_time()``,
    sonst pruefte der Test den Pruefling gegen sich selbst). Ein "irgendeine
    Capture-Datei existiert" waere die Aufweichung, die hier ausdruecklich
    NICHT stattfindet: der Fall verlangt genau eine Datei, deren
    ``source_key`` auf den interpolierten Punkt zeigt UND messbar vom
    Startpunkt abweicht. Wird der Messpunkt verfaelscht, reisst er.

    #2017 -> #2051 S2a: Die #2017-Zusicherung "genau EIN Abruf je Lauf"
    (AC-12) ist im ALARM-Pfad bewusst abgeloest (Spec
    ``docs/specs/modules/feat_2051_s2a_raeumliche_ausdehnung.md``, Abschnitt
    "Abgeloeste Zusicherung"): fuer die raeumliche Ausdehnung des
    Regenereignisses wird an mehreren Punkten entlang der Reststrecke
    abgefragt. Im /jetzt-Pfad und im Briefing-Kurzfristhinweis gilt der eine
    Abruf unveraendert weiter — deren Waechter liegen woanders.

    Der Waechter hier zieht deshalb um, statt sich aufzuweichen:
    (1) das BUDGET bleibt gedeckelt (``RADAR_ZONE_MAX_POINTS``, ueber die
    Modul-Referenz gelesen, damit eine Laufzeit-Umstellung der Konstante
    nicht an einer beim Import gebundenen Kopie vorbeilaeuft);
    (2) der AUSLOESENDE Datensatz wird ueber die Naehe seines ``source_key``
    zum analytisch gerechneten #2017-Messpunkt identifiziert — nicht ueber
    ``sorted(...)[0]``, denn dass der lexikografisch erste Dateiname der
    Messpunkt ist, gilt nur fuer eine nach Nordosten laufende Route;
    (3) die ``capture_id`` im ``alert_log`` gehoert zu GENAU DIESEM
    Datensatz und zu keinem der Folgepunkte."""
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
    # Modul-Referenz, KEIN `from ... import RADAR_ZONE_MAX_POINTS`: eine beim
    # Import gebundene Kopie liefe am Laufzeit-Drift-Schutz vorbei (dasselbe
    # Muster wie in `src/services/trip_alert.py`).
    from services import trip_segments as trip_segments_mod

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

    # #2017: Der Datensatz liegt unter dem Schluessel des INTERPOLIERTEN
    # Punktes, nicht mehr unter dem des Wegpunkts. Gelesen wird der
    # `source_key` aus dem Datensatz selbst (der Dateiname laeuft durch
    # `_safe_key()`), und der erwartete Ort wird analytisch gerechnet.
    soll_lat, soll_lon = _erwarteter_messpunkt(trip, now_utc)
    assert abs(soll_lat - lat) > 0.005 and abs(soll_lon - lon) > 0.005, (
        f"Testvoraussetzung: interpolierter Punkt ({soll_lat:.5f}, "
        f"{soll_lon:.5f}) und Segment-Startpunkt ({lat}, {lon}) muessen sich "
        f"messbar unterscheiden — sonst kann der Fall den Messpunkt nicht "
        f"unterscheiden und waere trivial wahr"
    )

    capture_dir = get_data_root() / "debug" / "alert_input" / "nowcast"
    capture_files = sorted(capture_dir.glob("*.json"))
    assert capture_files, (
        "Kein Eingangs-Datensatz unter data/debug/alert_input/nowcast/ gefunden."
    )
    datensaetze = [json.loads(f.read_text()) for f in capture_files]

    def _koordinaten(ds: dict) -> tuple:
        return tuple(float(x) for x in ds["source_key"].split("_")[:2])

    # (1) Budget-Deckel: die Zonen-Abfrage darf sich nicht zu einer offenen
    # Schleife auswachsen. Die Obergrenze kommt aus dem Produktivmodul.
    deckel = trip_segments_mod.RADAR_ZONE_MAX_POINTS
    assert len(datensaetze) <= deckel, (
        f"Die Zonen-Abfrage hat ihr Budget gesprengt: {len(datensaetze)} "
        f"Eingangs-Datensaetze unter data/debug/alert_input/nowcast/, erlaubt "
        f"sind hoechstens RADAR_ZONE_MAX_POINTS={deckel} (#2051 S2a). "
        f"Gefunden: {[f.name for f in capture_files]!r}"
    )

    # (2) Der AUSLOESENDE Datensatz wird ueber den Ort identifiziert, nicht
    # ueber die Dateinamen-Reihenfolge: der erste Punkt der Reststrecke ist
    # unveraendert der #2017-Messpunkt, die uebrigen liefern nur die Zonen.
    ausloesende = [
        ds for ds in datensaetze
        if abs(_koordinaten(ds)[0] - soll_lat) < 5e-4
        and abs(_koordinaten(ds)[1] - soll_lon) < 5e-4
    ]
    assert len(ausloesende) == 1, (
        f"Genau EIN Eingangs-Datensatz muss auf den zur Fenstermitte "
        f"interpolierten Messpunkt ({soll_lat:.5f}, {soll_lon:.5f}) zeigen — "
        f"er traegt die Ausloeseregel. Gefunden wurden {len(ausloesende)} "
        f"passende unter den source_keys "
        f"{[ds['source_key'] for ds in datensaetze]!r}. ({lat}, {lon}) waere "
        f"der Segment-Startpunkt, also der Messpunkt VOR #2017."
    )
    datensatz = ausloesende[0]
    ist_lat, ist_lon = _koordinaten(datensatz)
    assert datensatz is min(datensaetze, key=lambda ds: ds["captured_at"]), (
        f"Der Messpunkt-Datensatz ist nicht der ZUERST geschriebene: #2051 S2a "
        f"sichert zu, dass der erste abgefragte Punkt der #2017-Messpunkt "
        f"bleibt. Reihenfolge war "
        f"{[(ds['source_key'], ds['captured_at']) for ds in datensaetze]!r}"
    )
    assert datensatz["source_key"] == _nowcast_source_key(ist_lat, ist_lon), (
        f"source_key {datensatz['source_key']!r} folgt nicht der geteilten "
        f"Formel `_nowcast_source_key()` — Schreib- und Lesepfad liefen "
        f"auseinander (#1948 AC-4)"
    )
    written_capture_id = datensatz["capture_id"]
    assert written_capture_id, "Eingangs-Datensatz traegt keine capture_id."
    folgepunkt_ids = {
        ds["capture_id"] for ds in datensaetze if ds is not datensatz
    }
    assert written_capture_id not in folgepunkt_ids, (
        f"Vorbedingung: jeder Abruf braucht eine EIGENE capture_id, sonst "
        f"kann der Fall unten Messpunkt und Folgepunkt nicht unterscheiden. "
        f"capture_ids: {[ds['capture_id'] for ds in datensaetze]!r}"
    )

    # (3) Der alert_log-Eintrag zeigt auf den AUSLOESENDEN Datensatz — nicht
    # auf einen der Zonen-Folgepunkte.
    log_entry = _read_log(uid)["entries"][-1]
    assert log_entry.get("reason") == alert_log.REASON_NOWCAST
    assert log_entry.get("capture_id") == written_capture_id, (
        f"alert_log-Eintrag (Zweig c) traegt eine ANDERE capture_id als der "
        f"ausloesende Eingangs-Datensatz: log={log_entry.get('capture_id')!r} "
        f"!= input={written_capture_id!r}"
        + (
            " — er zeigt auf einen Zonen-Folgepunkt statt auf den "
            "#2017-Messpunkt."
            if log_entry.get("capture_id") in folgepunkt_ids else ""
        )
    )

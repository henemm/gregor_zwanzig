"""TDD RED — Issue #1461 Scheibe S3a: Alarm-Dringlichkeit wird wahr.

SPEC: docs/specs/modules/feat_1461_s3a_alarm_dringlichkeit.md (AC-1..AC-16)

Kernaussage: Radar/Nowcast schreibt heute immer die Konstante ``"HIGH"``,
amtliche Warnungen immer ``"MODERATE"`` -- unabhaengig vom tatsaechlichen
Geschehen. Diese Datei belegt je AC, dass eine geteilte Ableitung
(``src/services/alert_urgency.py``, NEU) die echte Dringlichkeit ins
Protokoll schreibt, waehrend Δ-Wetter (E4) und der Versand selbst (E6)
unveraendert bleiben.

RED-Grund heute: ``src/services/alert_urgency.py`` existiert nicht und die
Konstanten ``INTENSITY_*`` fehlen in ``radar_service.py`` -- betroffene
Importe/Attribute schlagen fehl. Einzelne Tests (v.a. AC-5, AC-8, AC-14,
AC-15) pruefen bereits heute korrektes Verhalten und bleiben deshalb gruen
(Regressionswaechter, s. Kommentare je Test).

Mock-frei: echte ``TripAlertService``/``CompareRadarAlertService``/
``CompareOfficialAlertService``-Laeufe, echte Persistenz ueber die
pytest-isolierte ``get_data_dir()``-Basis (#1133), Transport ueber die
vorhandenen ``mail_sink``/``radar_service``-DI-Naehte bzw. einen echten
lokalen Telegram-Bot-API-HTTP-Stub (kein Netz, kein ``Mock``/``patch``).

Pfadregel #1409: alle Pruefling-Pfade laufen ueber ``get_data_dir()`` bzw.
werden relativ zur Testdatei aufgeloest -- nie ueber einen festen
Hauptrepo-Pfad.
"""
from __future__ import annotations

import http.server
import json
import socket
import threading
from datetime import datetime, timedelta, timezone

from app.loader import get_data_dir, get_briefings_dir, save_location
from app.models import ChangeSeverity, TripReportConfig, WeatherChange
from app.trip import Trip
from app.user import SavedLocation

from tests.helpers.alert_log_fixtures import (
    LAT, LON, clean_compare_user, compare_data_root, fresh_user, gust_alert_trip,
    read_log, settings_email_only, weather,
)
from tests.helpers.arrival_window_fixtures import active_window_offsets, stage_date
from tests.helpers.briefing_zeiten import briefing_zeiten_fuer_trip
from tests.helpers.compare_briefings import write_compare_briefings

_GUST_STANDARD_THRESHOLD_KMH = 20.0


def _service(user_id: str, sink: list, **kwargs):
    from services.trip_alert import TripAlertService

    return TripAlertService(
        settings=settings_email_only(), user_id=user_id, throttle_hours=0,
        mail_sink=lambda subject, body: sink.append((subject, body)), **kwargs,
    )


def _latest_entry(user_id: str) -> dict:
    entries = read_log(user_id)["entries"]
    assert entries, "Es wurde ueberhaupt kein Protokoll-Eintrag geschrieben."
    return entries[-1]


def _official_alert(*, level: int, region_label: str = "Testregion"):
    from services.official_alerts.models import OfficialAlert

    now = datetime.now(timezone.utc)
    return OfficialAlert(
        source="tdd-1461", hazard="thunderstorm", level=level, label=f"Stufe {level}",
        valid_from=now - timedelta(hours=1), valid_to=now + timedelta(hours=6),
        region_label=region_label,
    )


# ═══════════════════════════ E2 — Amtliche Warnung ═══════════════════════

def test_official_red_level_logs_high():
    """AC-1 GIVEN eine rote amtliche Warnung (level=4) loest fuer eine Tour
    einen Standalone-Alarm aus WHEN protokolliert wird THEN steht 'HIGH' im
    neuesten Eintrag -- vorher stand dort fest 'MODERATE'."""
    uid = fresh_user("ac1461-1")
    mails: list = []
    trip = gust_alert_trip("trip-ac1")

    sent = _service(uid, mails)._send_official_alert_only(
        trip, [(_official_alert(level=4), ["1"])]
    )

    assert sent is True and mails, "Voraussetzung: die amtliche Meldung muss rausgehen."
    entry = _latest_entry(uid)
    assert entry.get("severity") == "HIGH", (
        f"Rote amtliche Warnung (level=4) muss 'HIGH' tragen, erhalten: "
        f"{entry.get('severity')!r}"
    )


def test_official_yellow_level_logs_low():
    """AC-2 GIVEN eine gelbe amtliche Warnung (level=2) loest denselben
    Standalone-Alarm aus WHEN protokolliert wird THEN steht 'LOW' im Eintrag."""
    uid = fresh_user("ac1461-2")
    mails: list = []
    trip = gust_alert_trip("trip-ac2")

    sent = _service(uid, mails)._send_official_alert_only(
        trip, [(_official_alert(level=2), ["1"])]
    )

    assert sent is True and mails, "Voraussetzung: die amtliche Meldung muss rausgehen."
    entry = _latest_entry(uid)
    assert entry.get("severity") == "LOW", (
        f"Gelbe amtliche Warnung (level=2) muss 'LOW' tragen, erhalten: "
        f"{entry.get('severity')!r}"
    )


def test_official_unknown_level_falls_back_to_high():
    """AC-3 (konservative Fallback-Richtung) GIVEN eine amtliche Warnung mit
    einer Stufe ausserhalb des bekannten Katalogs (level=5, fehlerhafte
    Provider-Daten) loest einen Standalone-Alarm aus WHEN protokolliert wird
    THEN steht 'HIGH' im Eintrag, NICHT 'LOW' -- dieselbe konservative
    Fallback-Richtung wie im bestehenden Vorbild official_alerts.py:395
    (LEVEL_LETTERS.get(alert.level, "H")): ein falsch-hoher Alarm ist
    unbequem, ein falsch-niedriger verschluckt eine echte Warnung."""
    uid = fresh_user("ac1461-3")
    mails: list = []
    trip = gust_alert_trip("trip-ac3")

    sent = _service(uid, mails)._send_official_alert_only(
        trip, [(_official_alert(level=5), ["1"])]
    )

    assert sent is True and mails, "Voraussetzung: die amtliche Meldung muss rausgehen."
    entry = _latest_entry(uid)
    assert entry.get("severity") == "HIGH", (
        "Eine Stufe ausserhalb 1-4 muss konservativ als 'HIGH' eingestuft "
        f"werden (nicht 'LOW'), erhalten: {entry.get('severity')!r}"
    )


def test_official_boundary_follows_level_letters_patch():
    """AC-4 (LEVEL_LETTERS-Ableitung ist live) GIVEN
    hazard_symbols.LEVEL_LETTERS[3] wird per Monkeypatch von 'M' auf 'L'
    gesetzt, eine amtliche Warnung der Stufe 3 (orange) liegt vor WHEN
    protokolliert wird THEN steht 'LOW' statt 'MODERATE' im Eintrag -- der
    Beweis, dass die Grenze aus der bestehenden Abbildung LEVEL_LETTERS
    gelesen wird, nicht aus einer zweiten, eigenen Zahlenreihe im neuen
    Modul."""
    import output.tokens.hazard_symbols as hazard_symbols

    uid = fresh_user("ac1461-4")
    mails: list = []
    trip = gust_alert_trip("trip-ac4")

    original = hazard_symbols.LEVEL_LETTERS[3]
    hazard_symbols.LEVEL_LETTERS[3] = "L"
    try:
        sent = _service(uid, mails)._send_official_alert_only(
            trip, [(_official_alert(level=3), ["1"])]
        )
    finally:
        hazard_symbols.LEVEL_LETTERS[3] = original

    assert sent is True and mails, "Voraussetzung: die amtliche Meldung muss rausgehen."
    entry = _latest_entry(uid)
    assert entry.get("severity") == "LOW", (
        "Nach dem Patch von LEVEL_LETTERS[3] auf 'L' muss die Stufe 3 als "
        f"'LOW' protokolliert werden, erhalten: {entry.get('severity')!r} -- "
        "die Ableitung liest die Grenze offenbar nicht live aus LEVEL_LETTERS."
    )


# ═══════════════════════════ E3 — Radar/Nowcast ═══════════════════════════

def _save_radar_trip(user_id: str, trip_id: str) -> None:
    """1:1 Muster aus tests/tdd/test_alert_log_metrics.py::_save_radar_trip."""
    briefings = get_briefings_dir(user_id)
    briefings.mkdir(parents=True, exist_ok=True)
    # #1667 S1: Ankunftszeiten aus dem wanduhr-robusten Helfer statt aus roher
    # now+Nh-Arithmetik — genau diese Fixture kippte ab 23:00 UTC nach
    # "alle Segmente vorbei" und liess check_radar_alerts() 0 statt 1 liefern.
    arr0, arr1 = active_window_offsets(LAT, LON, 60, 240)
    (briefings / f"{trip_id}.json").write_text(json.dumps({
        "id": trip_id, "name": "Radar-Trip",
        "stages": [{
            "id": "S1", "name": "Tag 1", "date": stage_date(LAT, LON).isoformat(),
            "waypoints": [
                {"id": "W0", "name": "Start", "lat": LAT, "lon": LON,
                 "elevation_m": 1000.0,
                 "arrival_calculated": arr0},
                {"id": "W1", "name": "Ziel", "lat": LAT + 0.1, "lon": LON + 0.1,
                 "elevation_m": 1500.0,
                 "arrival_calculated": arr1},
            ],
        }],
        "report_config": {"trip_id": trip_id, "send_email": True, "send_telegram": False},
    }))


def _frames_with_rate(rate: float, *, is_convective: bool = False):
    from providers.brightsky import RadarFrame

    now = datetime.now(timezone.utc)
    return lambda lat, lon: [
        RadarFrame(timestamp=now + timedelta(minutes=5), precip_mm_h=rate,
                   is_convective=is_convective),
        RadarFrame(timestamp=now + timedelta(minutes=15), precip_mm_h=rate,
                   is_convective=is_convective),
    ]


def _run_radar(uid: str, *, frame_source) -> dict:
    from services.radar_service import RadarNowcastService

    _save_radar_trip(uid, "trip-radar")
    mails: list = []
    svc = _service(uid, mails, radar_service=RadarNowcastService(frame_source=frame_source))
    assert svc.check_radar_alerts() == 1, "Voraussetzung: der Radar-Alarm muss feuern."
    return _latest_entry(uid)


def test_convective_radar_logs_high():
    """AC-5 GIVEN ein Radar-Alarm mit is_convective=True fuer eine Tour WHEN
    protokolliert wird THEN steht 'HIGH' im Eintrag -- weiterhin, aber jetzt
    aus is_convective abgeleitet statt aus einer Konstante.

    Bleibt heute schon GRUEN (Regressionswaechter): die heutige Konstante
    'HIGH' trifft diesen Fall zufaellig -- kein Beweis der Ableitung, aber
    ein Beweis, dass sie ihn NICHT bricht."""
    entry = _run_radar(fresh_user("ac1461-5"), frame_source=_frames_with_rate(5.0, is_convective=True))
    assert entry.get("severity") == "HIGH", (
        f"Konvektiver Radar-Alarm muss 'HIGH' tragen, erhalten: {entry.get('severity')!r}"
    )


def test_moderate_rain_radar_logs_moderate():
    """AC-6 GIVEN ein Radar-Alarm mit is_convective=False und Label
    'Maessiger Regen' (2.5 mm/h) fuer eine Tour WHEN protokolliert wird THEN
    steht 'MODERATE' im Eintrag -- vorher stand dort fest 'HIGH'."""
    entry = _run_radar(fresh_user("ac1461-6"), frame_source=_frames_with_rate(2.5, is_convective=False))
    assert entry.get("severity") == "MODERATE", (
        f"Maessiger Regen (nicht-konvektiv) muss 'MODERATE' tragen, erhalten: "
        f"{entry.get('severity')!r}"
    )


def test_light_rain_radar_logs_low():
    """AC-7 GIVEN ein Radar-Alarm mit Label 'Leichter Regen' (0.5 mm/h,
    is_convective=False) fuer eine Tour WHEN protokolliert wird THEN steht
    'LOW' im Eintrag -- exakt der in der Analyse benannte Fall (Nieselregen
    in 19 Minuten, bisher faelschlich HIGH)."""
    entry = _run_radar(fresh_user("ac1461-7"), frame_source=_frames_with_rate(0.5, is_convective=False))
    assert entry.get("severity") == "LOW", (
        f"Leichter Regen muss 'LOW' tragen, erhalten: {entry.get('severity')!r}"
    )


def _delta_change_trip_run(uid: str, *, fresh_gust_kmh: float) -> str:
    """Boeen-Aenderung von 20 -> fresh_gust_kmh km/h, gibt die protokollierte
    severity zurueck. Gebraucht von AC-11 (E5-Buendelung) -- NICHT von AC-8,
    s. dortiger Docstring: die Trip-Route liefert Δ-Wetter-Severity heute
    baulich IMMER 'MODERATE', unabhaengig vom Ausmass."""
    mails: list = []
    trip = gust_alert_trip(f"trip-{uid}")
    sent = _service(uid, mails).check_and_send_alerts(
        trip, [weather(1, gust_max_kmh=_GUST_STANDARD_THRESHOLD_KMH)],
        fresh_weather=[weather(1, gust_max_kmh=fresh_gust_kmh)],
    )
    assert sent is True and mails, "Voraussetzung: der Boeen-Alarm muss rausgehen."
    return _latest_entry(uid).get("severity")


# ═══════════════════════ E4 — Δ-Wetter bleibt unveraendert ════════════════

def _changes(*severities: "ChangeSeverity") -> list:
    """Direkt konstruierte WeatherChange-Liste (kein Mock: echte Modelle) --
    noetig, weil die Trip-Route (expand_per_metric_levels) JEDER Δ-Regel
    unabhaengig vom Ausmass severity=AlertSeverity.WARNING fest zuweist
    (alert_preset.py:129/210) und damit MINOR/MAJOR ueber die echte Pipeline
    (check_and_send_alerts) baulich NICHT erzeugbar sind -- s. Rueckmeldung
    an den Product Owner."""
    return [
        WeatherChange(
            metric="gust_max_kmh", old_value=20.0, new_value=20.0 + i, delta=float(i),
            threshold=20.0, severity=sev, direction="increase", segment_id="1",
        )
        for i, sev in enumerate(severities, start=1)
    ]


def test_delta_severity_unchanged_by_urgency_module():
    """AC-8 (E4, Δ-Wetter unveraendert) GIVEN drei Δ-Konstellationen (nur
    MINOR / bis MODERATE / mit MAJOR) WHEN ueber urgency_from_changes()
    zusammengefasst wird THEN liefert sie 'LOW' / 'MODERATE' / 'HIGH' --
    identisch zu DeviationAlertEngine._highest_severity() (Spec v1.2 E4:
    'die Umleitung ... darf das Ergebnis ... nicht veraendern').

    ABWEICHUNG von der spec-vorgeschlagenen Test-Form ('drei Fixtures ... je
    ein Lauf' durch check_and_send_alerts()): das ist mit der heutigen
    Trip-Route nicht herstellbar (s. Docstring von _changes()) -- jede
    Δ-Regel bekommt severity=WARNING fest zugewiesen, unabhaengig vom
    Ausmass. AC-8 selbst markiert das Prinzip ('Umleitung darf Ergebnis
    nicht veraendern') als Zweck, nicht als Pruefbedingung -- deshalb hier
    als direkter Funktionsvergleich, der genau dieses Prinzip belegt, ohne
    sich auf einen in der Praxis nicht erreichbaren Zustand zu stuetzen.
    Bitte gegenpruefen -- ich melde es zusaetzlich an den Product Owner."""
    import services.alert_urgency as alert_urgency
    from services.deviation_alert_engine import DeviationAlertEngine

    only_minor = _changes(ChangeSeverity.MINOR)
    up_to_moderate = _changes(ChangeSeverity.MINOR, ChangeSeverity.MODERATE)
    with_major = _changes(ChangeSeverity.MINOR, ChangeSeverity.MODERATE, ChangeSeverity.MAJOR)

    for changes, expected in (
        (only_minor, "LOW"), (up_to_moderate, "MODERATE"), (with_major, "HIGH"),
    ):
        via_urgency = alert_urgency.urgency_from_changes(changes)
        via_engine = DeviationAlertEngine._highest_severity(changes)
        assert via_urgency == expected == via_engine, (
            f"Erwartet {expected!r} von BEIDEN Wegen, erhalten "
            f"urgency_from_changes={via_urgency!r}, _highest_severity={via_engine!r}"
        )


# ═══════════════════════ Direkte Ableitungs-Funktionen ════════════════════

def test_radar_label_case_insensitive_classifies_same():
    """AC-9 (Case-Robustheit, Known-Bug der Ableitungsquelle) GIVEN zwei
    fachlich identische Labels -- Original-Title-Case aus intensity_to_text()
    ('Mäßiger Regen') und die im Trip-Pfad uebliche Kleinschreibung des
    ersten Buchstabens ('mäßiger Regen', trip_alert.py:826-827) WHEN beide
    durch urgency_from_radar() laufen THEN liefern beide 'MODERATE' --
    identisch, unabhaengig von der Schreibweise des Aufrufers."""
    import services.alert_urgency as alert_urgency

    title_case = alert_urgency.urgency_from_radar(
        is_convective=False, intensity_label="Mäßiger Regen"
    )
    trip_case = alert_urgency.urgency_from_radar(
        is_convective=False, intensity_label="mäßiger Regen"
    )
    assert title_case == "MODERATE" and trip_case == "MODERATE", (
        f"Beide Schreibweisen muessen 'MODERATE' liefern, erhalten: "
        f"title_case={title_case!r}, trip_case={trip_case!r}"
    )
    assert title_case == trip_case, (
        "Case-sensitiver Vergleich wuerde im Trip-Pfad strukturell nie "
        f"treffen: {title_case!r} != {trip_case!r}"
    )


def test_radar_label_rename_at_source_still_classifies_correctly():
    """AC-10 (Label-Umbenennung an der Quelle bleibt korrekt eingestuft)
    GIVEN radar_service.INTENSITY_HEAVY wird testweise per Monkeypatch auf
    einen anderen Text gesetzt (simuliert eine kuenftige Umbenennung des
    Labels an seiner Quelle) WHEN intensity_to_text() das umbenannte Label
    liefert und dieses durch urgency_from_radar() laeuft THEN liefert die
    Funktion weiterhin 'HIGH' -- die Ableitung folgt der lebenden Konstante,
    nicht einem im neuen Modul hartkodierten Zeichenketten-Duplikat."""
    import services.radar_service as radar_service
    import services.alert_urgency as alert_urgency

    original = radar_service.INTENSITY_HEAVY
    radar_service.INTENSITY_HEAVY = "Kräftiger Regen"
    try:
        svc = radar_service.RadarNowcastService()
        renamed_label = svc.intensity_to_text(5.0, is_convective=False)
        assert renamed_label == "Kräftiger Regen", (
            "Voraussetzung: intensity_to_text() muss die umbenannte Konstante "
            f"zurueckgeben, erhalten: {renamed_label!r}"
        )
        result = alert_urgency.urgency_from_radar(
            is_convective=False, intensity_label=renamed_label
        )
    finally:
        radar_service.INTENSITY_HEAVY = original

    assert result == "HIGH", (
        "Nach der Umbenennung an der Quelle muss urgency_from_radar() "
        f"weiterhin 'HIGH' liefern, erhalten: {result!r} -- die Ableitung "
        "vergleicht offenbar gegen ein hartkodiertes Zeichenketten-Duplikat "
        "statt gegen die lebende Konstante."
    )


# ═══════════════════════ E5 — mehrere Quellen, EIN Eintrag ════════════════

def test_bundled_official_and_minor_delta_logs_highest():
    """AC-11 (E5, Trip-Buendelung Δ + amtlich) GIVEN ein Alarm-Lauf, in dem
    eine Δ-Aenderung UND eine rote amtliche Warnung (level=4) im selben
    Durchlauf in EINE Nachricht gebuendelt werden
    (check_and_send_alerts(..., official_notices=...), Muster #1088) WHEN
    protokolliert wird THEN traegt der EINE entstehende Eintrag
    severity='HIGH' -- die hoechste beteiligte Dringlichkeit gewinnt, nicht
    die der Δ-Aenderung allein.

    Hinweis (gemessen, weicht von der AC-Formulierung 'MINOR-Δ-Aenderung' ab):
    die Trip-Route liefert fuer JEDE Δ-Regel severity=AlertSeverity.WARNING
    fest (alert_preset.py:129/210, s. AC-8-Docstring) -- die Δ-Aenderung
    allein waere also schon heute 'MODERATE', nie 'MINOR'. Der Beweis der
    Buendelung bleibt trotzdem intakt: 'MODERATE' (Δ) + 'HIGH' (amtlich,
    level=4) muss 'HIGH' ergeben, nicht 'MODERATE'."""
    uid = fresh_user("ac1461-11")
    mails: list = []
    trip = gust_alert_trip("trip-ac11")

    sent = _service(uid, mails).check_and_send_alerts(
        trip, [weather(1, gust_max_kmh=_GUST_STANDARD_THRESHOLD_KMH)],
        fresh_weather=[weather(1, gust_max_kmh=45.0)],
        official_notices=[(_official_alert(level=4), ["1"])],
    )

    assert sent is True and mails, "Voraussetzung: die gebuendelte Meldung muss rausgehen."
    entries = read_log(uid)["entries"]
    assert len(entries) == 1, (
        f"Δ-Aenderung und amtliche Warnung muessen EINEN Eintrag ergeben, "
        f"erhalten: {len(entries)}"
    )
    assert entries[0].get("severity") == "HIGH", (
        "Die gebuendelte Meldung muss die hoechste beteiligte Dringlichkeit "
        f"tragen ('HIGH'), erhalten: {entries[0].get('severity')!r} -- die "
        "Δ-Aenderung allein liefert heute 'MODERATE' (s. Docstring)."
    )


def _setup_two_locations(uid: str) -> tuple:
    save_location(
        SavedLocation(id="loc-a", name="Ort A", lat=LAT, lon=LON, elevation_m=1000),
        user_id=uid,
    )
    save_location(
        SavedLocation(id="loc-b", name="Ort B", lat=LAT + 1.0, lon=LON, elevation_m=1000),
        user_id=uid,
    )
    return "loc-a", "loc-b"


def test_compare_radar_two_locations_convective_and_moderate_logs_highest():
    """Regressionswaechter (KEINE eigene AC, s. Spec v1.3 Korrektur zu AC-12):
    GIVEN ein Ortsvergleich-Radar-Alarm mit zwei getriggerten Orten -- einer
    konvektiv (Gewitter), einer mit maessigem Regen (is_convective=False)
    WHEN protokolliert wird THEN steht im EINEN Log-Eintrag severity='HIGH'.

    Dieser exakte Fall (konvektiv + maessig) trifft zufaellig denselben Wert
    wie die heutige feste Konstante 'HIGH' und beweist die Buendelungs-
    Mechanik NICHT (RED-Phase-Befund, Spec-Korrektur v1.3) -- der echte
    Beweis ist `test_compare_radar_two_non_convective_locations_logs_the_higher_one`
    direkt darunter (jetzt AC-12)."""
    from services.compare_radar_alert import CompareRadarAlertService
    from services.radar_service import RadarNowcastService

    uid = fresh_user("ac1461-12")
    clean_compare_user(uid)
    try:
        loc_a, loc_b = _setup_two_locations(uid)
        write_compare_briefings(compare_data_root() / uid, [{
            "id": "cp-ac12", "name": "Vergleich AC12", "user_id": uid,
            "location_ids": [loc_a, loc_b], "schedule": "daily", "weekday": 4,
            "profil": "ALLGEMEIN", "hour_from": 9, "hour_to": 16,
            "empfaenger": ["dummy@example.com"], "created_at": "2026-08-01T00:00:00Z",
            "radar_alert_enabled": True, "alert_cooldown_minutes": 0,
        }])

        def frame_source(lat, lon):
            from providers.brightsky import RadarFrame

            now = datetime.now(timezone.utc)
            is_convective = (lat == LAT)  # loc-a konvektiv, loc-b maessig
            rate = 5.0 if is_convective else 2.5
            return [RadarFrame(timestamp=now + timedelta(minutes=5), precip_mm_h=rate,
                                is_convective=is_convective)]

        mails: list = []
        sent = CompareRadarAlertService(
            settings=settings_email_only(), user_id=uid,
            radar_service=RadarNowcastService(frame_source=frame_source),
            mail_sink=lambda subject, body: mails.append((subject, body)),
        ).check_all_compare_presets()

        assert sent == 1 and mails, "Voraussetzung: der gebuendelte Radar-Alarm muss rausgehen."
        entry = _latest_entry(uid)
        assert entry.get("changes_count") == 2, (
            f"Beide Orte muessen im EINEN Eintrag gebuendelt sein: {entry!r}"
        )
        assert entry.get("severity") == "HIGH", (
            f"Konvektiv+maessig muss 'HIGH' ergeben, erhalten: {entry.get('severity')!r}"
        )
    finally:
        clean_compare_user(uid)


def test_compare_radar_two_non_convective_locations_logs_the_higher_one():
    """AC-12 (E5, Ortsvergleich-Radar, mehrere Orte, Spec v1.3-Korrektur)
    GIVEN ein Ortsvergleich-Radar-Alarm mit zwei getriggerten Orten, BEIDE
    nicht konvektiv, einer mit leichtem und einer mit maessigem Regen WHEN
    protokolliert wird THEN steht 'MODERATE' im EINEN Log-Eintrag -- die
    schaerfste beteiligte Einstufung.

    Dieser Fall kann NICHT zufaellig mit der heutigen festen Konstante
    'HIGH' uebereinstimmen und ist damit der echte Beweis, dass die
    Buendelung tatsaechlich rechnet statt eine Konstante zu setzen (der
    urspruengliche AC-12-Fall 'konvektiv + maessig -> HIGH' war strukturell
    wertlos, s. Regressionswaechter oben)."""
    from services.compare_radar_alert import CompareRadarAlertService
    from services.radar_service import RadarNowcastService

    uid = fresh_user("ac1461-12b")
    clean_compare_user(uid)
    try:
        loc_a, loc_b = _setup_two_locations(uid)
        write_compare_briefings(compare_data_root() / uid, [{
            "id": "cp-ac12b", "name": "Vergleich AC12b", "user_id": uid,
            "location_ids": [loc_a, loc_b], "schedule": "daily", "weekday": 4,
            "profil": "ALLGEMEIN", "hour_from": 9, "hour_to": 16,
            "empfaenger": ["dummy@example.com"], "created_at": "2026-08-01T00:00:00Z",
            "radar_alert_enabled": True, "alert_cooldown_minutes": 0,
        }])

        def frame_source(lat, lon):
            from providers.brightsky import RadarFrame

            now = datetime.now(timezone.utc)
            rate = 0.5 if lat == LAT else 2.5  # loc-a leicht, loc-b maessig
            return [RadarFrame(timestamp=now + timedelta(minutes=5), precip_mm_h=rate,
                                is_convective=False)]

        mails: list = []
        sent = CompareRadarAlertService(
            settings=settings_email_only(), user_id=uid,
            radar_service=RadarNowcastService(frame_source=frame_source),
            mail_sink=lambda subject, body: mails.append((subject, body)),
        ).check_all_compare_presets()

        assert sent == 1 and mails, "Voraussetzung: der gebuendelte Radar-Alarm muss rausgehen."
        entry = _latest_entry(uid)
        assert entry.get("severity") == "MODERATE", (
            f"Leicht+maessig muss 'MODERATE' ergeben (die hoehere der beiden "
            f"beteiligten Einstufungen), erhalten: {entry.get('severity')!r}"
        )
    finally:
        clean_compare_user(uid)


def test_compare_official_two_warnings_logs_highest():
    """AC-13 (E5, Ortsvergleich amtlich, mehrere Warnungen) GIVEN ein
    Ortsvergleich-amtlich-Alarm mit zwei getaggten Warnungen unterschiedlicher
    Orte, level=2 (gelb) und level=4 (rot) WHEN protokolliert wird THEN steht
    severity='HIGH' im EINEN Eintrag."""
    import services.official_alerts.base as base
    from services.compare_official_alert import CompareOfficialAlertService
    from services.official_alerts import register_official_alert_source

    class _TwoLevelSource:
        @property
        def name(self) -> str:
            return "tdd-1461-source"

        def covers(self, lat, lon) -> bool:
            return True

        def fetch(self, lat, lon):
            level = 2 if lat == LAT else 4
            region = "Region-A" if lat == LAT else "Region-B"
            return [_official_alert(level=level, region_label=region)]

    uid = fresh_user("ac1461-13")
    clean_compare_user(uid)
    quellen = list(base._REGISTERED_SOURCES)
    base._REGISTERED_SOURCES.clear()
    try:
        loc_a, loc_b = _setup_two_locations(uid)
        register_official_alert_source(_TwoLevelSource())
        write_compare_briefings(compare_data_root() / uid, [{
            "id": "cp-ac13", "name": "Vergleich AC13", "user_id": uid,
            "location_ids": [loc_a, loc_b], "schedule": "daily", "weekday": 4,
            "profil": "ALLGEMEIN", "hour_from": 9, "hour_to": 16,
            "empfaenger": ["dummy@example.com"], "created_at": "2026-08-01T00:00:00Z",
        }])

        mails: list = []
        sent = CompareOfficialAlertService(
            settings=settings_email_only(), user_id=uid,
            mail_sink=lambda subject, body: mails.append((subject, body)),
        ).check_all_compare_presets()

        assert sent == 1 and mails, "Voraussetzung: der gebuendelte amtliche Alarm muss rausgehen."
        entry = _latest_entry(uid)
        assert entry.get("changes_count") == 2, (
            f"Beide Warnungen muessen im EINEN Eintrag gebuendelt sein: {entry!r}"
        )
        assert entry.get("severity") == "HIGH", (
            f"gelb+rot muss 'HIGH' ergeben, erhalten: {entry.get('severity')!r}"
        )
    finally:
        base._REGISTERED_SOURCES.clear()
        base._REGISTERED_SOURCES.extend(quellen)
        clean_compare_user(uid)


# ═══════════════════════════ E6 — Versand unveraendert ════════════════════

def _free_port() -> int:
    s = socket.socket()
    s.bind(("", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class _TelegramStub:
    """Lokaler HTTP-Stub fuer die Telegram-Bot-API (1:1 Muster aus
    tests/tdd/test_telegram_kurzstil_trip_alert.py::_TelegramStub) -- zeichnet
    jede sendMessage-Nutzlast auf, kein Mock/patch des Verhaltens."""

    def __init__(self) -> None:
        self.sent: list[dict] = []
        sent = self.sent
        counter = {"mid": 3000}

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):  # noqa: N802
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length)
                try:
                    payload = json.loads(body.decode())
                except ValueError:
                    payload = {}
                sent.append(payload)
                counter["mid"] += 1
                resp = json.dumps(
                    {"ok": True, "result": {"message_id": counter["mid"]}}
                ).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(resp)

            def log_message(self, *args):  # noqa: D401
                pass

        self.port = _free_port()
        self._server = http.server.HTTPServer(("127.0.0.1", self.port), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def stop(self) -> None:
        self._server.shutdown()


def _settings_email_and_telegram():
    from app.config import Settings

    return Settings(
        smtp_host="dummy.invalid", smtp_user="dummy", smtp_pass="dummy",
        mail_to="dummy@example.com",
        telegram_bot_token="tdd-1461-bot", telegram_chat_id="4711",
    )


def _make_change() -> WeatherChange:
    return WeatherChange(
        metric="gust_max_kmh", old_value=20.0, new_value=45.0, delta=25.0,
        threshold=20.0, severity=ChangeSeverity.MINOR, direction="increase",
        segment_id="1",
    )


def _telegram_trip(trip_id: str) -> Trip:
    trip = gust_alert_trip(trip_id)
    # Issue #1594: dieses `report_config` ERSETZT das von `gust_alert_trip`
    # gesetzte — ohne die Zeiten laege der Trip wieder im Vorlauf-Fenster und
    # die Sperre schnitte den Versand vor der Kanal-Pruefung ab.
    morgen, abend = briefing_zeiten_fuer_trip(trip)
    trip.report_config = TripReportConfig(
        trip_id=trip_id, send_email=True, send_telegram=True, send_sms=False,
        alert_on_changes=True, morning_time=morgen, evening_time=abend,
    )
    trip.alert_cooldown_minutes = 0
    return trip


def test_channel_dispatch_unaffected_by_severity_change(monkeypatch):
    """AC-14 (E6, Verhaltensneutralitaet des Versands) GIVEN eine Tour mit
    aktivem E-Mail- und Telegram-Kanal und einer Δ-Aenderung, die einen
    Alarm ausloest WHEN der Alarm laeuft THEN wird die E-Mail-Senke GENAU
    EINMAL und die Telegram-Senke GENAU EINMAL aufgerufen, die SMS-Senke
    KEIN MAL, und NotificationResult.sent_channels ist exakt
    {'email','telegram'}. Zusatz-Pruefung: derselbe Lauf mit einer roten
    amtlichen Warnung (level=4) statt der Δ-Aenderung liefert dieselben
    Zaehler -- die geaenderte Einstufung verschiebt nichts am Versand.

    Bleibt heute schon GRUEN (Regressionswaechter): die Kanalwahl
    (_effective_alert_channels) liest 'severity' an keiner Stelle -- dieser
    Test beweist genau das bleibt so."""
    import output.channels.telegram as tg_module
    from services.trip_alert import TripAlertService

    # Herkunftssperre (#1476) auf 'production' gepinnt: gemessen wird die
    # Kanalwahl-Neutralitaet von _send_alert; ohne Pin bricht die
    # Herkunftsschicht den Telegram-Versand in jedem Nicht-Server-Checkout
    # mangels Test-Chat-ID ab, bevor der lokale Stub etwas sieht (eigene
    # Tests der Schicht: test_telegram_origin_guard.py).
    monkeypatch.setattr(tg_module, "running_origin", lambda module_file: "production")

    settings = _settings_email_and_telegram()

    # Variante 1: Δ-Aenderung
    tg_stub_1 = _TelegramStub()
    try:
        monkeypatch.setattr(tg_module, "TELEGRAM_API_BASE", tg_stub_1.base_url)
        mails_1: list = []
        svc_1 = TripAlertService(
            settings=settings, user_id="tdd-1461-ac14a", throttle_hours=0,
            mail_sink=lambda subject, body: mails_1.append((subject, body)),
        )
        result_1 = svc_1._send_alert(
            _telegram_trip("trip-ac14a"), [weather(1)], [_make_change()],
        )
    finally:
        tg_stub_1.stop()

    assert len(mails_1) == 1, f"E-Mail-Senke muss genau einmal laufen: {len(mails_1)}"
    assert len(tg_stub_1.sent) == 1, (
        f"Telegram-Senke muss genau einmal laufen: {len(tg_stub_1.sent)}"
    )
    assert set(result_1.sent_channels) == {"email", "telegram"}, (
        f"sent_channels muss exakt {{'email','telegram'}} sein, erhalten: "
        f"{result_1.sent_channels!r}"
    )

    # Variante 2: rote amtliche Warnung statt Δ-Aenderung -- dieselben Zaehler
    tg_stub_2 = _TelegramStub()
    try:
        monkeypatch.setattr(tg_module, "TELEGRAM_API_BASE", tg_stub_2.base_url)
        mails_2: list = []
        svc_2 = TripAlertService(
            settings=settings, user_id="tdd-1461-ac14b", throttle_hours=0,
            mail_sink=lambda subject, body: mails_2.append((subject, body)),
        )
        sent_2 = svc_2._send_official_alert_only(
            _telegram_trip("trip-ac14b"), [(_official_alert(level=4), ["1"])],
        )
    finally:
        tg_stub_2.stop()

    assert sent_2 is True, "Voraussetzung: die amtliche Warnung muss rausgehen."
    assert len(mails_2) == 1, f"E-Mail-Senke muss genau einmal laufen: {len(mails_2)}"
    assert len(tg_stub_2.sent) == 1, (
        f"Telegram-Senke muss genau einmal laufen: {len(tg_stub_2.sent)}"
    )


# ═══════════════════════════ E7 — D4 bleibt gewahrt ════════════════════════

def test_entries_count_and_target_list_unchanged_when_severity_changes():
    """AC-15 (E7, D4 -- Eintragszahl und Ziel-Liste unveraendert) GIVEN eine
    Tour hat vor dieser Scheibe N Eintraege in 'entries' WHEN zusaetzlich ein
    amtlicher Alarm (level=4) protokolliert wird, der vor dieser Scheibe als
    'MODERATE' in 'entries' gelandet waere THEN liegt der neue Eintrag
    weiterhin in 'entries' (nicht 'not_delivered'), die Anzahl steigt um
    genau 1 auf N+1, und 'not_delivered' bleibt unveraendert -- nur der
    severity-Wert im neuen Eintrag aendert sich ('MODERATE' -> 'HIGH'),
    nicht die Ziel-Liste.

    Bleibt heute schon GRUEN (Regressionswaechter): die Ziel-Listen-Logik
    (entries vs. not_delivered, #1459 D4) haengt nicht an severity."""
    from services import alert_log

    uid = fresh_user("ac1461-15")
    alert_log.append_entry(
        uid, entity_id="trip-ac15", entity_type="trip", changes_count=1,
        severity="MODERATE", metrics=[("gust", "max")], reason="forecast_change",
        effective_channels={"email"}, sent_channels=["email"],
    )
    alert_log.append_entry(
        uid, entity_id="trip-ac15", entity_type="trip", changes_count=2,
        severity="HIGH", metrics=[("gust", "max")], reason="forecast_change",
        effective_channels={"email"}, sent_channels=["email"],
    )
    vorher = read_log(uid)
    n_vorher, not_delivered_vorher = len(vorher["entries"]), len(vorher["not_delivered"])
    assert n_vorher == 2, f"Voraussetzung: zwei Bestands-Eintraege, erhalten {n_vorher}."

    mails: list = []
    trip = gust_alert_trip("trip-ac15")
    sent = _service(uid, mails)._send_official_alert_only(
        trip, [(_official_alert(level=4), ["1"])]
    )

    assert sent is True and mails, "Voraussetzung: die amtliche Meldung muss rausgehen."
    nachher = read_log(uid)
    assert len(nachher["entries"]) == n_vorher + 1, (
        f"'entries' muss um genau 1 wachsen: {n_vorher} -> {len(nachher['entries'])}"
    )
    assert len(nachher["not_delivered"]) == not_delivered_vorher, (
        f"'not_delivered' darf sich nicht aendern: {not_delivered_vorher} -> "
        f"{len(nachher['not_delivered'])}"
    )
    assert nachher["entries"][-1].get("severity") == "HIGH", (
        f"Der neue Eintrag muss 'HIGH' tragen: {nachher['entries'][-1]!r}"
    )


# ═══════════════════════════ Mandantentrennung ═════════════════════════════

def test_two_users_official_alert_severity_isolated():
    """AC-16 (Mandantentrennung, zwei Nutzer) GIVEN zwei Nutzer A und B,
    jeweils mit einer eigenen Tour und je einer roten amtlichen Warnung
    (level=4) im selben Testlauf, isoliert ueber app.loader.get_data_dir
    (kein gemeinsamer data_dir) WHEN beide Alarme protokolliert werden THEN
    traegt Nutzer As alert_log.json einen Eintrag mit severity='HIGH' fuer
    seine eigene Tour, Nutzer Bs eigene, getrennt gescopte Datei traegt
    ebenfalls 'HIGH' fuer seine eigene Tour -- keine Vermischung von Werten
    oder Dateien zwischen den beiden data/users/<user_id>/-Verzeichnissen,
    kein Rueckfall auf 'default'."""
    alice, bob = fresh_user("ac1461-16-alice"), fresh_user("ac1461-16-bob")
    assert alice != "default" and bob != "default" and alice != bob

    mails_alice: list = []
    mails_bob: list = []
    sent_alice = _service(alice, mails_alice)._send_official_alert_only(
        gust_alert_trip("trip-alice"), [(_official_alert(level=4), ["1"])]
    )
    sent_bob = _service(bob, mails_bob)._send_official_alert_only(
        gust_alert_trip("trip-bob"), [(_official_alert(level=4), ["1"])]
    )

    assert sent_alice is True and mails_alice, "Voraussetzung: Alarm fuer Alice muss rausgehen."
    assert sent_bob is True and mails_bob, "Voraussetzung: Alarm fuer Bob muss rausgehen."

    log_alice = read_log(alice)
    log_bob = read_log(bob)
    assert len(log_alice["entries"]) == 1 and len(log_bob["entries"]) == 1, (
        f"Je Nutzer genau ein Eintrag erwartet: alice={log_alice}, bob={log_bob}"
    )
    assert log_alice["entries"][0].get("entity_id") == "trip-alice", (
        f"Alice' Protokoll muss nur ihre eigene Tour zeigen: {log_alice!r}"
    )
    assert log_bob["entries"][0].get("entity_id") == "trip-bob", (
        f"Bobs Protokoll muss nur seine eigene Tour zeigen: {log_bob!r}"
    )
    assert log_alice["entries"][0].get("severity") == "HIGH", (
        f"Alice' Eintrag muss 'HIGH' tragen: {log_alice!r}"
    )
    assert log_bob["entries"][0].get("severity") == "HIGH", (
        f"Bobs Eintrag muss 'HIGH' tragen: {log_bob!r}"
    )
    assert get_data_dir(alice) != get_data_dir(bob), (
        "Alice und Bob duerfen NICHT dasselbe Datenverzeichnis teilen "
        f"(Rueckfall auf 'default'?): {get_data_dir(alice)} == {get_data_dir(bob)}"
    )

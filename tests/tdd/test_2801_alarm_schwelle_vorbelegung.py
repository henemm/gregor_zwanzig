"""TDD RED -- Issue #2801 (Epic #2791 S9): Alarm-Dringlichkeit je Kanal,
Vorbelegung E-Mail/Telegram "gering", SMS "mittel", Premium-SMS "hoch".

SPEC: docs/specs/modules/feat_2801_alarm_schwelle_vorbelegung_je_kanal.md
Test Plan T1-T8 und T11 (Python-Seite). T9/T10/T11 (Frontend)/T12 stehen in
``frontend/src/lib/components/shared/alarme-tab/alertChannelVorbelegung.test.ts``.

Kern: ohne gesetzte ``alert_channel_thresholds`` gilt je Kanal
``{email: LOW, telegram: LOW, sms: MODERATE, premium_sms: HIGH}`` -- fuer ALLE
Alarmarten ueber ``split_by_threshold`` (Trip-Wetter/-amtlich/-Radar,
Vergleich-Wetter/-amtlich/-Radar) und fuer die SMS-Schwelle der amtlichen
Warnungen im Trip-SMS-Briefing (``trip_report.py``). Telegram-Briefing bleibt
LOW. Ein gesetzter Wert (auch ausdruecklich LOW) bleibt unveraendert.

RED-Grund heute: ``alert_channel_threshold.DEFAULT_CHANNEL_THRESHOLD = "LOW"``
fuer alle Kanaele, ``trip_report.py`` faellt auf ``"LOW"`` zurueck.

Testpolitik (CLAUDE.md "Test-Politik: Zwei Schichten", Kern-Schicht): kein
``Mock()``/``patch()``/``MagicMock``. SMS und Premium-SMS laufen ueber einen
ECHTEN lokalen seven.io-HTTP-Stub (127.0.0.1), E-Mail ueber den bestehenden
``mail_sink``-DI-Seam; Persistenz unter der pytest-isolierten Datenwurzel
(#1133). Die einzige ``monkeypatch``-Nutzung ist die Herkunftssperre des
SMS-Kanals (#1476, Muster ``test_compare_alert_channel_threshold.py``) --
gemessen wird die Kanal-Schwelle, nicht die Herkunftsschicht.
"""
from __future__ import annotations

import json
import shutil
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest
from zoneinfo import ZoneInfo

from app.config import Settings
from app.loader import get_data_root, save_location
from app.models import ChangeSeverity, TripReportConfig, WeatherChange
from app.trip import Stage, Trip, Waypoint
from app.user import SavedLocation
from services.alert_channel_threshold import split_by_threshold
from services.official_alerts import OfficialAlert

from tests.helpers.alert_log_fixtures import read_log
from tests.helpers.sms_empfaenger import profil_rueckadresse, profil_sms
from tests.unit.test_alert_channel_threshold_premium_sms import (
    _SevenIoStub,
    _weather_segment,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
#: T11: die EINE Paritaets-Fixture, die auch der Frontend-Test liest.
VORBELEGUNG_FIXTURE = REPO_ROOT / "tests" / "fixtures" / "alarm_schwelle_vorbelegung_2801.json"

ALLE = {"email", "telegram", "sms", "premium_sms"}
STUFEN = ("LOW", "MODERATE", "HIGH")
ERWARTET = {"email": "LOW", "telegram": "LOW", "sms": "MODERATE", "premium_sms": "HIGH"}

SMS_A = "+49000000111"
SMS_B = "+49000000222"
PREMIUM_A = "+4915799912345"
PREMIUM_B = "+4915799954321"
LAT, LON = 47.07, 15.44


# ══════════════════════════ T1-T4: split_by_threshold ═════════════════════


def test_t1_ohne_wert_mittel_erreicht_email_telegram_sms_nicht_premium():
    """T1 / AC-1.

    GIVEN ein Trip ohne ``alert_channel_thresholds`` (None).
    WHEN  ``split_by_threshold`` mit allen vier Kanaelen fuer "mittel".
    THEN  erlaubt = email, telegram, sms; unterdrueckt = premium_sms.
    """
    trip = Trip(id="t-2801-t1", name="T1", stages=[])
    assert trip.alert_channel_thresholds is None, "Voraussetzung: kein Wert gesetzt"

    erlaubt, unterdrueckt = split_by_threshold(set(ALLE), "MODERATE", trip.alert_channel_thresholds)

    assert erlaubt == {"email", "telegram", "sms"}, (
        "T1: ohne gesetzten Wert muss ein 'mittel'-Alarm E-Mail, Telegram und "
        f"SMS erreichen. erlaubt={erlaubt!r}"
    )
    assert unterdrueckt == {"premium_sms"}, (
        "T1: ohne gesetzten Wert gilt fuer die Premium-SMS die Vorbelegung "
        f"'hoch' -- ein 'mittel'-Alarm muss unterdrueckt sein. unterdrueckt={unterdrueckt!r}"
    )


def test_t2_ohne_wert_hoch_erreicht_alle_gering_nur_email_telegram():
    """T2 / AC-2: "hoch" erreicht alle vier, "gering" nur E-Mail und Telegram
    (auch bei leerem Dict statt None)."""
    erlaubt_hoch, unterdrueckt_hoch = split_by_threshold(set(ALLE), "HIGH", None)
    assert erlaubt_hoch == ALLE and unterdrueckt_hoch == set(), (
        f"T2: 'hoch' muss alle vier erreichen: erlaubt={erlaubt_hoch!r}"
    )

    for leer in (None, {}):
        erlaubt, unterdrueckt = split_by_threshold(set(ALLE), "LOW", leer)
        assert erlaubt == {"email", "telegram"}, (
            f"T2: 'gering' ohne gesetzten Wert ({leer!r}) darf nur E-Mail und "
            f"Telegram erreichen. erlaubt={erlaubt!r}"
        )
        assert unterdrueckt == {"sms", "premium_sms"}, (
            f"T2: SMS (Vorbelegung mittel) und Premium-SMS (hoch) muessen bei "
            f"'gering' unterdrueckt sein. unterdrueckt={unterdrueckt!r}"
        )


def test_t3_explizit_sms_low_bleibt_low_andere_behalten_vorbelegung():
    """T3 / AC-4: ``{sms: LOW}`` gesetzt -> SMS erreicht "gering", die
    Premium-SMS (nicht gesetzt) behaelt ihre Vorbelegung "hoch"."""
    erlaubt, unterdrueckt = split_by_threshold(set(ALLE), "LOW", {"sms": "LOW"})
    assert erlaubt == {"email", "telegram", "sms"}, (
        f"T3: ausdruecklich gesetztes LOW fuer SMS muss gelten. erlaubt={erlaubt!r}"
    )
    assert unterdrueckt == {"premium_sms"}, (
        "T3: Premium-SMS ist nicht gesetzt und faellt auf ihre Vorbelegung "
        f"'hoch'. unterdrueckt={unterdrueckt!r}"
    )


def test_t4_explizit_premium_low_und_email_high():
    """T4 / AC-4: ``{premium_sms: LOW}`` erreicht Premium bei "gering";
    ``{email: HIGH}`` unterdrueckt E-Mail bei "mittel"."""
    erlaubt, _ = split_by_threshold({"premium_sms"}, "LOW", {"premium_sms": "LOW"})
    assert erlaubt == {"premium_sms"}, f"T4: gesetztes LOW fuer Premium muss gelten: {erlaubt!r}"

    erlaubt, unterdrueckt = split_by_threshold(set(ALLE), "MODERATE", {"email": "HIGH"})
    assert unterdrueckt == {"email", "premium_sms"}, (
        "T4: E-Mail (gesetzt HIGH) und Premium (Vorbelegung HIGH) muessen bei "
        f"'mittel' unterdrueckt sein. unterdrueckt={unterdrueckt!r}"
    )
    assert erlaubt == {"telegram", "sms"}, f"T4: erlaubt={erlaubt!r}"


def test_t4b_unbekannter_wert_gilt_wie_nicht_gesetzt():
    """Implementation Details Nr. 2: leere oder unbekannte Werte fallen auf
    die Vorbelegung des Kanals, nicht auf LOW."""
    _, unterdrueckt = split_by_threshold({"sms", "premium_sms"}, "LOW", {"sms": "", "premium_sms": None})
    assert unterdrueckt == {"sms", "premium_sms"}, (
        f"leerer/None-Wert muss wie 'nicht gesetzt' wirken: unterdrueckt={unterdrueckt!r}"
    )


def test_ac13_eine_quelle_default_threshold_je_kanal():
    """AC-13 (Implementation Details Nr. 1): die Python-Quelle der
    Vorbelegung ist ``alert_channel_threshold.default_threshold(channel)``.

    Neues Symbol laut Spec -- heute fehlt es (bewusster RED-Grund)."""
    import services.alert_channel_threshold as act

    assert hasattr(act, "default_threshold"), (
        "AC-13: services.alert_channel_threshold.default_threshold(channel) fehlt "
        "(Spec 'Implementation Details' Nr. 1: eine Quelle je Sprache)"
    )
    assert {k: act.default_threshold(k) for k in ERWARTET} == ERWARTET


# ═══════════════════════════ T11: Paritaet (Python) ═══════════════════════


def _wirksame_vorbelegung() -> dict[str, str]:
    """Vorbelegung aus dem VERHALTEN abgeleitet: die niedrigste Dringlichkeit,
    die einen Kanal ohne gesetzten Wert erreicht."""
    out = {}
    for kanal in sorted(ALLE):
        for stufe in STUFEN:
            if kanal in split_by_threshold({kanal}, stufe, None)[0]:
                out[kanal] = stufe
                break
    return out


def test_t11_python_vorbelegung_gleich_paritaets_fixture():
    """T11 / AC-13: die Python-Vorbelegung ist dieselbe wie in der
    Paritaets-Fixture, die auch der Frontend-Test gegen
    ``resolveAlertChannelThresholds(undefined)`` prueft."""
    fixture = json.loads(VORBELEGUNG_FIXTURE.read_text(encoding="utf-8"))  # doc-compliance-test
    assert fixture == ERWARTET, f"Fixture weicht von der Spec ab: {fixture!r}"
    assert _wirksame_vorbelegung() == fixture, (
        "T11: Python-Vorbelegung (aus split_by_threshold abgeleitet) "
        f"{_wirksame_vorbelegung()!r} != Paritaets-Fixture {fixture!r}"
    )


# ═══════════════════════════ T5: echte Alarm-Pfade ════════════════════════

_AMPEL_NIEDERSCHLAG = {
    "template": "allgemein",
    "metrics": {"precipitation": {
        "upper": {"yellow": 10, "orange": 20, "red": 29}, "alarm_ab": "yellow",
    }},
}


def _pin_sms_herkunft(monkeypatch) -> None:
    import output.channels.sms as sms_module

    monkeypatch.setattr(sms_module, "running_origin", lambda module_file: "production")


def _uid(prefix: str) -> str:
    return f"tdd-2801-{prefix}-{uuid.uuid4().hex[:6]}"


def _clean_user(user_id: str) -> None:
    d = get_data_root() / "users" / user_id
    if d.exists():
        shutil.rmtree(d, ignore_errors=True)


def _profil(user_id: str, sms: str, premium: str) -> None:
    profil_sms(user_id, sms, tier="premium")
    profil_rueckadresse(user_id, premium)


def _settings(port: int, user_id: str, sms: str) -> Settings:
    """JEDES versandrelevante Feld ausdruecklich gesetzt (#1477)."""
    return Settings().with_user_profile(user_id).model_copy(update={
        "sms_gateway_url": f"http://127.0.0.1:{port}/api/sms",
        "seven_api_key": "test-stub-key", "seven_sandbox_key": "test-stub-key",
        "sms_to": sms, "sms_from": None,
        "smtp_host": "dummy.invalid", "smtp_user": "dummy", "smtp_pass": "dummy",
        "mail_to": "dummy@example.com",
        "telegram_bot_token": "", "telegram_chat_id": "",
    })


def _change(severity: ChangeSeverity) -> WeatherChange:
    return WeatherChange(
        metric="gust_max_kmh", old_value=20.0, new_value=45.0, delta=25.0,
        threshold=20.0, severity=severity, direction="increase", segment_id="1",
    )


def _alarm_trip(trip_id: str, thresholds: dict | None = None) -> Trip:
    """Trip mit E-Mail, SMS und Premium-SMS als Alarm-Kanal (Bestand ohne
    Schwelle, wenn ``thresholds`` None)."""
    stage = Stage(
        id="T1", name="Tag 1", date=date.today(),
        waypoints=[Waypoint(id="W1", name="Start", lat=LAT, lon=LON, elevation_m=1000.0)],
    )
    trip = Trip(id=trip_id, name="Vorbelegung-Trip", stages=[stage], official_warnings=None)
    trip.report_config = TripReportConfig(trip_id=trip_id, send_email=False, alert_on_changes=True)
    trip.alert_channels = {"email": True, "telegram": False, "sms": True, "premium_sms": True}
    trip.alert_cooldown_minutes = 0
    trip.official_alert_triggers_enabled = False
    trip.alert_channel_thresholds = thresholds
    return trip


def _not_sent(entry: dict) -> dict[str, str]:
    return {i["channel"]: i["reason"] for i in entry.get("channels_not_sent", [])}


def _trip_alarm(monkeypatch, uid: str, trip: Trip, severity: ChangeSeverity, stub, sms: str):
    from services.trip_alert import TripAlertService

    _pin_sms_herkunft(monkeypatch)
    mails: list = []
    result = TripAlertService(
        settings=_settings(stub.port, uid, sms), user_id=uid, throttle_hours=0,
        mail_sink=lambda subject, body: mails.append((subject, body)),
    )._send_alert(trip, [_weather_segment(1)], [_change(severity)])
    return result, mails


#: Boeen-Ampel des Trips (Muster der Orts-Vergleich-Niederschlags-Ampel):
#: 40 km/h gelb = "gering", 45 orange = "mittel", 60 rot = "hoch" gegen 20 km/h.
_AMPEL_BOEEN = {"template": "allgemein", "metrics": {"gust": {
    "upper": {"yellow": 30, "orange": 44, "red": 59}, "alarm_ab": "yellow"}}}
BOE_GERING, BOE_MITTEL, BOE_HOCH = 40.0, 45.0, 60.0


def _trip_lauf(monkeypatch, uid: str, thresholds: dict | None, boe: float, stub, sms: str) -> str:
    """Echter Alarmlauf ``check_and_send_alerts`` (schreibt das Protokoll) fuer
    einen Boeen-Trip mit SMS und Premium-SMS als Alarm-Kanal."""
    from services.trip_alert import TripAlertService
    from tests.helpers.alert_log_fixtures import gust_alert_trip, weather

    trip = gust_alert_trip(
        f"trip-2801-{uuid.uuid4().hex[:6]}",
        alert_channels={"email": False, "telegram": False, "sms": True, "premium_sms": True},
    )
    trip.display_config.ampel = _AMPEL_BOEEN
    trip.alert_channel_thresholds = thresholds
    _pin_sms_herkunft(monkeypatch)
    TripAlertService(
        settings=_settings(stub.port, uid, sms), user_id=uid, throttle_hours=0,
        mail_sink=lambda subject, body: None,
    ).check_and_send_alerts(
        trip, [weather(1, gust_max_kmh=20.0)], fresh_weather=[weather(1, gust_max_kmh=boe)],
    )
    return trip.id


def _protokoll(uid: str, entity_id: str) -> dict:
    """Der EINE Protokolleintrag des Laufs -- unter ``entries`` (teilweise
    zugestellt) oder ``not_delivered`` (alles unter der Schwelle, #638)."""
    log = read_log(uid)
    treffer = [e for e in log["entries"] + log["not_delivered"] if e.get("entity_id") == entity_id]
    assert len(treffer) == 1, f"genau ein Protokolleintrag erwartet: {log!r}"
    return treffer[0]


def test_t5_trip_wetteralarm_mittel_ohne_wert_zustellung(monkeypatch):
    """T5 / AC-1 (Zustellung, ``_send_alert``): Trip ohne Wert, Wetter-Alarm
    "mittel" -> E-Mail und SMS zugestellt, Premium-SMS nicht."""
    uid = _uid("t5-trip")
    _clean_user(uid)
    _profil(uid, SMS_A, PREMIUM_A)
    stub = _SevenIoStub()
    try:
        trip = _alarm_trip(f"trip-t5-{uuid.uuid4().hex[:6]}")
        result, mails = _trip_alarm(monkeypatch, uid, trip, ChangeSeverity.MODERATE, stub, SMS_A)
    finally:
        stub.stop()
        _clean_user(uid)
    assert mails, "T5 Voraussetzung: E-Mail muss zugestellt werden"
    assert len(stub.to(SMS_A)) == 1, f"T5: SMS muss bei 'mittel' ankommen: {stub.received!r}"
    assert stub.to(PREMIUM_A) == [], (
        "T5: Premium-SMS hat ohne gesetzten Wert die Vorbelegung 'hoch' -- "
        f"ein 'mittel'-Alarm darf sie nicht erreichen. Gesendet: {stub.to(PREMIUM_A)!r}"
    )
    assert set(result.delivered_channels) == {"email", "sms"}, result.delivered_channels


def test_t5_trip_wetteralarm_mittel_ohne_wert_protokoll(monkeypatch):
    """T5 / AC-1 (Protokoll, echter Lauf): premium_sms steht als rohes Opt-in
    mit Grund ``below_channel_threshold`` im Protokoll (#638), SMS zugestellt."""
    uid = _uid("t5-log")
    _clean_user(uid)
    _profil(uid, SMS_A, PREMIUM_A)
    stub = _SevenIoStub()
    try:
        trip_id = _trip_lauf(monkeypatch, uid, None, BOE_MITTEL, stub, SMS_A)
        eintrag = _protokoll(uid, trip_id)
    finally:
        stub.stop()
        _clean_user(uid)
    assert eintrag.get("severity") == "MODERATE", f"Voraussetzung 'mittel': {eintrag!r}"
    assert stub.to(PREMIUM_A) == [], f"T5: keine Premium-SMS bei 'mittel': {stub.received!r}"
    assert "sms" in eintrag["channels_sent"], eintrag
    assert _not_sent(eintrag).get("premium_sms") == "below_channel_threshold", (
        f"T5: premium_sms muss mit Grund below_channel_threshold protokolliert sein: {eintrag!r}"
    )


def test_t5_trip_wetteralarm_hoch_ohne_wert_erreicht_premium(monkeypatch):
    """T5 / AC-2 Gegenprobe: derselbe Trip, Alarm "hoch" -> Premium-SMS kommt an."""
    uid = _uid("t5-hoch")
    _clean_user(uid)
    _profil(uid, SMS_A, PREMIUM_A)
    stub = _SevenIoStub()
    try:
        trip = _alarm_trip(f"trip-t5h-{uuid.uuid4().hex[:6]}")
        _trip_alarm(monkeypatch, uid, trip, ChangeSeverity.MAJOR, stub, SMS_A)
    finally:
        stub.stop()
        _clean_user(uid)
    assert len(stub.to(SMS_A)) == 1, f"T5: SMS bei 'hoch': {stub.received!r}"
    assert len(stub.to(PREMIUM_A)) == 1, f"T5: Premium-SMS bei 'hoch': {stub.received!r}"


def test_t5_ac5_bestand_trip_gering_sms_und_premium_unterdrueckt_email_bleibt(monkeypatch):
    """T5 / AC-5 (Zustellung): Bestand-Trip ohne Feld, Alarm "gering" ->
    E-Mail geht wie bisher, SMS und Premium-SMS bleiben aus."""
    uid = _uid("t5-bestand")
    _clean_user(uid)
    _profil(uid, SMS_A, PREMIUM_A)
    stub = _SevenIoStub()
    try:
        trip = _alarm_trip(f"trip-t5b-{uuid.uuid4().hex[:6]}")
        result, mails = _trip_alarm(monkeypatch, uid, trip, ChangeSeverity.MINOR, stub, SMS_A)
    finally:
        stub.stop()
        _clean_user(uid)
    assert mails, "AC-5: E-Mail muss wie bisher ankommen"
    assert stub.received == [], (
        "AC-5: SMS (Vorbelegung mittel) und Premium-SMS (hoch) muessen bei "
        f"'gering' unterdrueckt sein. Gesendet: {stub.received!r}"
    )
    assert set(result.delivered_channels) == {"email"}, result.delivered_channels


def test_t5_ac5_bestand_trip_gering_protokoll_nennt_beide_mit_grund(monkeypatch):
    """T5 / AC-5 (Protokoll, echter Lauf): SMS und Premium-SMS stehen mit
    Grund ``below_channel_threshold`` im Protokoll (rohes Opt-in, #638)."""
    uid = _uid("t5-blog")
    _clean_user(uid)
    _profil(uid, SMS_A, PREMIUM_A)
    stub = _SevenIoStub()
    try:
        trip_id = _trip_lauf(monkeypatch, uid, None, BOE_GERING, stub, SMS_A)
        eintrag = _protokoll(uid, trip_id)
    finally:
        stub.stop()
        _clean_user(uid)
    assert eintrag.get("severity") == "LOW", f"Voraussetzung 'gering': {eintrag!r}"
    assert stub.received == [], f"AC-5: weder SMS noch Premium-SMS: {stub.received!r}"
    grund = _not_sent(eintrag)
    assert grund.get("sms") == "below_channel_threshold", eintrag
    assert grund.get("premium_sms") == "below_channel_threshold", eintrag


def _radar_trip(trip_id: str) -> Trip:
    from tests.helpers.arrival_window_fixtures import active_window_offsets, stage_date

    arr0, arr1 = active_window_offsets(LAT, LON, -60, 120)
    stage = Stage(id="S1", name="Tag 1", date=stage_date(LAT, LON), waypoints=[
        Waypoint(id="WP0", name="Start", lat=LAT, lon=LON, elevation_m=500.0, arrival_calculated=arr0),
        Waypoint(id="WP1", name="Ziel", lat=LAT + 0.1, lon=LON + 0.1, elevation_m=600.0,
                 arrival_calculated=arr1),
    ])
    trip = Trip(id=trip_id, name="Radar-Trip 2801", stages=[stage])
    trip.report_config = TripReportConfig(trip_id=trip_id, send_email=False, send_telegram=False, send_sms=False)
    trip.alert_channels = {"email": True, "telegram": False, "sms": True, "premium_sms": True}
    trip.alert_cooldown_minutes = 0
    return trip


def _maessiger_regen(lat: float, lon: float) -> list:
    """Nicht-konvektiver Regen 2 mm/h -> INTENSITY_MODERATE -> 'mittel'."""
    from providers.brightsky import RadarFrame

    now = datetime.now(timezone.utc)
    return [RadarFrame(timestamp=now + timedelta(minutes=5), precip_mm_h=2.0),
            RadarFrame(timestamp=now + timedelta(minutes=15), precip_mm_h=2.2)]


def test_t5_trip_radar_mittel_ohne_wert_premium_unterdrueckt(monkeypatch):
    """T5 / AC-1 (Radar-Pfad ``trip_alert.py`` check_radar_alerts)."""
    from app.loader import save_trip
    from services.radar_service import RadarNowcastService
    from services.trip_alert import TripAlertService

    uid = _uid("t5-radar")
    _clean_user(uid)
    _profil(uid, SMS_A, PREMIUM_A)
    trip = _radar_trip(f"trip-t5r-{uuid.uuid4().hex[:6]}")
    save_trip(trip, user_id=uid)
    _pin_sms_herkunft(monkeypatch)
    stub = _SevenIoStub()
    try:
        mails: list = []
        sent = TripAlertService(
            settings=_settings(stub.port, uid, SMS_A), user_id=uid, throttle_hours=0,
            radar_service=RadarNowcastService(frame_source=_maessiger_regen),
            mail_sink=lambda subject, body: mails.append((subject, body)),
        ).check_radar_alerts()
    finally:
        stub.stop()
        _clean_user(uid)
    assert sent >= 1, f"T5 Voraussetzung: Radar-Alarm muss ausgeloest sein, sent={sent}"
    assert len(stub.to(SMS_A)) == 1, f"T5 Radar: SMS bei 'mittel': {stub.received!r}"
    assert stub.to(PREMIUM_A) == [], (
        f"T5 Radar: Premium-SMS (Vorbelegung hoch) darf 'mittel' nicht bekommen: {stub.received!r}"
    )


def test_t5_trip_amtlich_mittel_ohne_wert_premium_unterdrueckt(monkeypatch):
    """T5 / AC-1 (eigenstaendiger amtlicher Alarm ``_send_official_alert_only``),
    Stufe 3 (orange) -> 'mittel'."""
    from services.official_alerts import register_official_alert_source
    from services.trip_alert import TripAlertService
    from tests.helpers.briefing_zeiten import briefing_zeiten_fuer_trip
    from tests.helpers.ortstag import ortstag
    from tests.tdd.test_issue_1088_official_alert_triggers import (
        LAT as LAT_1088, LON as LON_1088, _CountingOfficialAlertSource,
        _data, _registered_sources_backup, _save_cached,
    )

    uid = _uid("t5-amtl")
    _clean_user(uid)
    _profil(uid, SMS_A, PREMIUM_A)
    oa_base, backup = _registered_sources_backup()
    oa_base._REGISTERED_SOURCES.clear()
    stub = _SevenIoStub()
    try:
        stage = Stage(id="T1", name="Tag 1", date=ortstag(LAT_1088, LON_1088), waypoints=[
            Waypoint(id="G1", name="Start", lat=LAT_1088, lon=LON_1088, elevation_m=1000.0)])
        trip = Trip(id=f"trip-t5o-{uuid.uuid4().hex[:6]}", name="Amtlich 2801",
                    stages=[stage], official_warnings=None)
        morgen, abend = briefing_zeiten_fuer_trip(trip)
        trip.report_config = TripReportConfig(
            trip_id=trip.id, send_email=False, send_telegram=False, send_sms=False,
            morning_time=morgen, evening_time=abend)
        trip.alert_channels = {"email": True, "telegram": False, "sms": True, "premium_sms": True}
        trip.alert_cooldown_minutes = 0
        _save_cached(uid, trip.id, [_data(1, precip_sum_mm=2.0)])
        register_official_alert_source(_CountingOfficialAlertSource(
            LAT_1088, LON_1088,
            OfficialAlert(source="test-2801", hazard="thunderstorm", level=3, label="Orange"),
        ))
        _pin_sms_herkunft(monkeypatch)
        svc = TripAlertService(
            settings=_settings(stub.port, uid, SMS_A), user_id=uid, throttle_hours=0,
            mail_sink=lambda subject, body: None,
        )
        notices = svc.check_official_alert_triggers(trip)
        assert notices, "T5 Voraussetzung: die orange Warnung muss erkannt werden"
        svc._send_official_alert_only(trip, notices)
    finally:
        stub.stop()
        oa_base._REGISTERED_SOURCES.clear()
        oa_base._REGISTERED_SOURCES.extend(backup)
        _clean_user(uid)
    assert len(stub.to(SMS_A)) == 1, f"T5 amtlich: SMS bei 'mittel': {stub.received!r}"
    assert stub.to(PREMIUM_A) == [], (
        f"T5 amtlich: Premium-SMS (Vorbelegung hoch) darf 'mittel' nicht bekommen: {stub.received!r}"
    )


# ── Orts-Vergleich: drei getrennte Dispatcher ──────────────────────────────


def _compare_preset(preset_id: str, loc_id: str, **extra) -> dict:
    from tests.unit.test_compare_alert_premium_sms import _compare_preset as basis

    return basis(preset_id, [loc_id], send_sms=True, send_premium_sms=True, **extra)


def _compare_setup(uid: str, preset: dict, loc_id: str) -> None:
    from tests.unit.test_compare_alert_premium_sms import _write_presets

    _profil(uid, SMS_A, PREMIUM_A)
    save_location(SavedLocation(id=loc_id, name="Testort", lat=LAT, lon=LON, elevation_m=353), user_id=uid)
    _write_presets(uid, [preset])


def _pruefe_vergleich_mittel(uid: str, preset_id: str, stub, art: str) -> None:
    assert len(stub.to(SMS_A)) == 1, f"T5 Vergleich {art}: SMS bei 'mittel': {stub.received!r}"
    assert stub.to(PREMIUM_A) == [], (
        f"T5 Vergleich {art}: Premium-SMS hat ohne Wert die Vorbelegung 'hoch' und "
        f"darf einen 'mittel'-Alarm nicht bekommen. Gesendet: {stub.received!r}"
    )
    entries = [e for e in read_log(uid)["entries"] if e["entity_id"] == preset_id]
    assert len(entries) == 1, f"T5 Vergleich {art}: Protokolleintrag fehlt: {read_log(uid)!r}"
    assert _not_sent(entries[0]).get("premium_sms") == "below_channel_threshold", entries[0]


def test_t5_vergleich_wetteralarm_mittel_ohne_wert(monkeypatch):
    """T5 / AC-3 (``compare_alert``): Niederschlag 22 mm gegen Anker 2 mm,
    Abo-Ampel orange (20) -> 'mittel'."""
    from services.compare_alert import CompareAlertService
    from services.compare_weather_snapshot import CompareWeatherSnapshotService
    from tests.unit.test_compare_alert_premium_sms import (
        _ScriptedWeatherSource, _preset_briefing_zeiten, _pwd,
    )

    uid, loc_id = _uid("t5-cmp"), "loc-1"
    preset_id = f"cp-t5-{uuid.uuid4().hex[:6]}"
    _clean_user(uid)
    morgen, abend = _preset_briefing_zeiten()
    _compare_setup(uid, _compare_preset(
        preset_id, loc_id, morning_time=morgen, evening_time=abend,
        display_config={"ampel": _AMPEL_NIEDERSCHLAG}), loc_id)
    CompareWeatherSnapshotService(user_id=uid).save(preset_id, loc_id, _pwd(loc_id, "Testort", LAT, LON, 2.0))
    _pin_sms_herkunft(monkeypatch)
    stub = _SevenIoStub()
    try:
        mails: list = []
        CompareAlertService(
            settings=_settings(stub.port, uid, SMS_A), user_id=uid,
            weather_source=_ScriptedWeatherSource({loc_id: 22.0}),
            mail_sink=lambda subject, body: mails.append((subject, body)),
        ).check_all_compare_presets()
    finally:
        stub.stop()
    try:
        assert mails, "T5 Vergleich Wetter Voraussetzung: E-Mail muss ankommen"
        _pruefe_vergleich_mittel(uid, preset_id, stub, "Wetter")
    finally:
        _clean_user(uid)


def test_t5_vergleich_amtlich_mittel_ohne_wert(monkeypatch):
    """T5 / AC-3 (``compare_official_alert``): Stufe 3 (orange) -> 'mittel'."""
    from services.compare_official_alert import CompareOfficialAlertService
    from services.official_alerts import register_official_alert_source
    from tests.unit.test_compare_alert_premium_sms import (
        _FakeOfficialAlertSource, _official_alert, _preset_briefing_zeiten, _sources_backup,
    )

    uid, loc_id = _uid("t5-cmpo"), "loc-a"
    preset_id = f"cp-t5o-{uuid.uuid4().hex[:6]}"
    _clean_user(uid)
    b, backup = _sources_backup()
    b._REGISTERED_SOURCES.clear()
    morgen, abend = _preset_briefing_zeiten()
    _compare_setup(uid, _compare_preset(preset_id, loc_id, morning_time=morgen, evening_time=abend), loc_id)
    alert = _official_alert()
    assert alert.level == 3, "Voraussetzung: Stufe 3 -> 'mittel'"
    register_official_alert_source(_FakeOfficialAlertSource(LAT, LON, [alert]))
    _pin_sms_herkunft(monkeypatch)
    stub = _SevenIoStub()
    try:
        CompareOfficialAlertService(
            settings=_settings(stub.port, uid, SMS_A), user_id=uid,
            mail_sink=lambda subject, body: None,
        ).check_all_compare_presets()
    finally:
        stub.stop()
        b._REGISTERED_SOURCES.clear()
        b._REGISTERED_SOURCES.extend(backup)
    try:
        _pruefe_vergleich_mittel(uid, preset_id, stub, "amtlich")
    finally:
        _clean_user(uid)


def test_t5_vergleich_radar_mittel_ohne_wert(monkeypatch):
    """T5 / AC-3 (``compare_radar_alert``): maessiger Regen 2 mm/h -> 'mittel'."""
    from services.compare_radar_alert import CompareRadarAlertService
    from services.radar_service import RadarNowcastService
    from tests.unit.test_compare_alert_premium_sms import _CoordFrameSource

    uid, loc_id = _uid("t5-cmpr"), "loc-1"
    preset_id = f"cp-t5r-{uuid.uuid4().hex[:6]}"
    _clean_user(uid)
    _compare_setup(uid, _compare_preset(preset_id, loc_id, radar_alert_enabled=True), loc_id)
    _pin_sms_herkunft(monkeypatch)
    stub = _SevenIoStub()
    try:
        sent = CompareRadarAlertService(
            settings=_settings(stub.port, uid, SMS_A), user_id=uid,
            radar_service=RadarNowcastService(
                frame_source=_CoordFrameSource({(LAT, LON): _maessiger_regen(LAT, LON)})),
            mail_sink=lambda subject, body: None,
        ).check_all_compare_presets()
    finally:
        stub.stop()
    try:
        assert sent == 1, f"T5 Vergleich Radar Voraussetzung: sent={sent}"
        _pruefe_vergleich_mittel(uid, preset_id, stub, "Radar")
    finally:
        _clean_user(uid)


# ═══════════════════════════ T6: Briefing-Renderer ════════════════════════


def _gelb_alert() -> OfficialAlert:
    now = datetime.now(timezone.utc)
    return OfficialAlert(
        source="tdd-2801-t6", hazard="flood", level=2, label="Hochwasser Stufe 2",
        region_label="Region", valid_from=now - timedelta(hours=1), valid_to=now + timedelta(hours=8),
    )


def _briefing_trip(thresholds: dict | None) -> Trip:
    stage = Stage(id="T1", name="Tag 1", date=date.today(), waypoints=[
        Waypoint(id="G1", name="Start", lat=42.20, lon=9.05, elevation_m=1000.0, arrival_calculated="08:00"),
        Waypoint(id="G2", name="Ziel", lat=42.25, lon=9.10, elevation_m=1200.0, arrival_calculated="12:00"),
    ])
    return Trip(id="trip-2801-t6", name="Briefing-Trip", stages=[stage], alert_channel_thresholds=thresholds)


def _briefing(thresholds: dict | None, alerts: list | None = None, segmente: int = 1):
    from output.renderers.trip_report import TripReportFormatter
    from tests.unit.test_renderers_email import _make_segment_weather

    segs = []
    for i in range(1, segmente + 1):
        sw = _make_segment_weather(i)
        sw.official_alerts = list(alerts if alerts is not None else [_gelb_alert()])
        segs.append(sw)
    trip = _briefing_trip(thresholds)
    return TripReportFormatter().format_email(
        segments=segs, trip_name=trip.name, report_type="evening", trip=trip, tz=ZoneInfo("UTC"),
    )


def test_t6_ohne_sms_wert_gelbe_warnung_fehlt_in_sms_und_premium():
    """T6 / AC-11: ohne gesetzte SMS-Schwelle (Vorbelegung mittel) fehlt eine
    amtliche Warnung Stufe gering im SMS- und im Premium-SMS-Briefing."""
    report = _briefing(None)
    assert "FO:" not in report.sms_text, (
        "T6: ohne gesetzte SMS-Schwelle gilt 'mittel' -- die gelbe Warnung "
        f"(Kuerzel FO) darf nicht im SMS-Briefing stehen: {report.sms_text!r}"
    )
    assert "FO:" not in (report.premium_sms_text or ""), (
        f"T6: dasselbe fuer die Premium-SMS: {report.premium_sms_text!r}"
    )


def test_t6_sms_wert_low_gelbe_warnung_in_sms_und_premium():
    """T6 / AC-11: mit gesetzter SMS-Schwelle 'gering' enthalten beide sie."""
    report = _briefing({"sms": "LOW"})
    assert "FO:" in report.sms_text, f"T6: SMS mit LOW muss FO zeigen: {report.sms_text!r}"
    assert "FO:" in (report.premium_sms_text or ""), (
        f"T6: Premium mit SMS-LOW muss FO zeigen: {report.premium_sms_text!r}"
    )


def _lange_warnliste() -> list:
    """Elf orange Warnungen (bei jeder Vorbelegung sichtbar) plus eine gelbe
    Hochwasserwarnung, verankert am Tag der Testsegmente (@10 statt @h der
    Wanduhr): der SMS-Text wird laenger als 153 Zeichen."""
    von = datetime(2026, 7, 11, 10, 0, tzinfo=timezone.utc)
    bis = datetime(2026, 7, 11, 20, 0, tzinfo=timezone.utc)
    orange = ("thunderstorm", "rain", "wind_gust", "snow", "black_ice", "extreme_heat",
              "extreme_cold", "wildfire_risk", "avalanche", "access_ban", "avalanche_bulletin")
    return [
        OfficialAlert(source="tdd-2801-f001", hazard=h, level=lvl, label=h, region_label="Region",
                      valid_from=von, valid_to=bis)
        for h, lvl in [(h, 3) for h in orange] + [("flood", 2)]
    ]


def test_f001_premium_neuaufbau_ueber_153_zeichen_haelt_die_sms_schwelle():
    """Fix-Loop F001 / AC-11: ist der SMS-Text laenger als 153 Zeichen, baut
    trip_report den Premium-Text neu (format_sms mit max_length=153). Auch
    dieser Neuaufbau nutzt die SMS-Schwelle: ohne gesetzten Wert (mittel)
    fehlt die gelbe Warnung (FO:L), mit SMS 'gering' steht sie drin."""
    from output.renderers.channel_layout import CHANNEL_LIMITS

    grenze = CHANNEL_LIMITS["premium_sms"]["max_chars"]
    for thresholds, gelb_erwartet in ((None, False), ({"sms": "LOW"}, True)):
        report = _briefing(thresholds, alerts=_lange_warnliste(), segmente=4)
        sms, premium = report.sms_text, report.premium_sms_text or ""
        assert len(sms) > grenze and premium != sms and len(premium) <= grenze, (
            f"Voraussetzung: Neuaufbau-Zweig erreicht ({thresholds!r}): "
            f"sms={len(sms)} {sms!r} premium={len(premium)} {premium!r}"
        )
        assert ("FO:L" in premium) is gelb_erwartet, (
            f"F001: Premium-Neuaufbau mit {thresholds!r} muss die gelbe Warnung "
            f"{'zeigen' if gelb_erwartet else 'weglassen'}: {premium!r}"
        )


@pytest.mark.parametrize("kanal", sorted(ALLE))
@pytest.mark.parametrize("gesetzt", STUFEN)
def test_f005_gesetzter_wert_gilt_unveraendert_je_kanal_und_stufe(kanal, gesetzt):
    """Fix-Loop F005 / AC-4: jeder gesetzte Wert (LOW, MODERATE, HIGH) kommt
    auf jedem Kanal unveraendert aus resolve_threshold zurueck, auch wenn er
    von der Vorbelegung abweicht, und split_by_threshold filtert danach:
    eine Meldung erreicht den Kanal genau ab der gesetzten Stufe."""
    from services.alert_channel_threshold import resolve_threshold

    assert resolve_threshold(kanal, {kanal: gesetzt}) == gesetzt
    rang = STUFEN.index(gesetzt)
    for stufe in STUFEN:
        erlaubt, unterdrueckt = split_by_threshold({kanal}, stufe, {kanal: gesetzt})
        if STUFEN.index(stufe) >= rang:
            assert (erlaubt, unterdrueckt) == ({kanal}, set()), (kanal, gesetzt, stufe)
        else:
            assert (erlaubt, unterdrueckt) == (set(), {kanal}), (kanal, gesetzt, stufe)


def test_f002_unbekannter_kanal_faellt_auf_low():
    """Fix-Loop F002: ein Kanal ohne Eintrag in der Vorbelegung wird nie
    still unterdrueckt -- er faellt auf 'LOW'."""
    import services.alert_channel_threshold as act

    assert act.default_threshold("unbekannt") == "LOW"
    assert split_by_threshold({"unbekannt"}, "LOW", None) == ({"unbekannt"}, set())


def test_t6_telegram_briefing_zeigt_gelbe_warnung_ohne_wert_weiterhin():
    """T6 / AC-11 / AC-13: das Telegram-Briefing nutzt die Telegram-Schwelle
    (Vorbelegung gering) und zeigt die gelbe Warnung weiterhin."""
    from output.renderers.narrow import _official_alert_bubble
    from tests.unit.test_renderers_email import _make_segment_weather

    sw = _make_segment_weather()
    sw.official_alerts = [_gelb_alert()]
    bubble = _official_alert_bubble([sw], ZoneInfo("UTC"), trip=_briefing_trip(None))
    assert bubble is not None and "Amtliche Warnung" in bubble.text, (
        f"T6: Telegram ohne Wert muss die gelbe Warnung zeigen: {bubble!r}"
    )


# ═══════════════════════════ T7: Premium = SMS-Inhalt ═════════════════════


def test_t7_trip_premium_ist_sms_text_gekuerzt_warnung_bleibt():
    """T7 / AC-10 (Trip): Premium-Briefing = SMS-Text; ist die SMS laenger als
    153 Zeichen, kuerzt derselbe Formatter vom Listenende, die amtliche
    Warnung (hier Stufe 3, bei jeder Vorbelegung sichtbar) bleibt stehen."""
    from output.renderers.channel_layout import CHANNEL_LIMITS

    grenze = CHANNEL_LIMITS["premium_sms"]["max_chars"]
    assert grenze == 153
    now = datetime.now(timezone.utc)
    orange = OfficialAlert(
        source="tdd-2801-t7", hazard="flood", level=3, label="Hochwasser Stufe 3",
        region_label="Region", valid_from=now - timedelta(hours=1), valid_to=now + timedelta(hours=8),
    )
    for segmente in (1, 4):
        report = _briefing(None, alerts=[orange], segmente=segmente)
        sms, premium = report.sms_text, report.premium_sms_text or ""
        assert len(premium) <= grenze, (len(premium), premium)
        if len(sms) <= grenze:
            assert premium == sms, (premium, sms)
        assert "FO:" in sms, f"Voraussetzung: orange Warnung im SMS-Text: {sms!r}"
        assert "FO:" in premium, f"T7: Warnung muss zuletzt gekuerzt werden: {premium!r}"


def test_t7_vergleich_premium_ist_sms_text_gekuerzt_warnung_bleibt():
    """T7 / AC-10 (Orts-Vergleich): ``compare_premium_sms_rendern`` liefert
    hoechstens 153 Zeichen, der gewarnte Ort bleibt sichtbar."""
    from tests.tdd.test_3172_orte_sms_token_zeile import (
        AC1_AUSWAHL, PREMIUM_MAX, _kontext, _sms, _vergleich, _viele_orte,
    )
    from services import compare_briefing_aufbau as aufbau

    kontext = _kontext(_vergleich(_viele_orte(16, warnung_bei=15)), {"active_metrics": AC1_AUSWAHL})
    sms = _sms(kontext)
    premium = aufbau.compare_premium_sms_rendern(kontext, sms)
    assert len(premium) <= PREMIUM_MAX == 153, (len(premium), premium)
    assert "!" in sms, f"Voraussetzung: Warnung in der SMS: {sms!r}"
    assert "!" in premium, f"T7: Warnung muss in der Premium-SMS bleiben: {premium!r}"


# ═══════════════════════════ T8: zwei Nutzer ══════════════════════════════


def test_t8_zwei_nutzer_eigener_sms_wert_ohne_vermischung(monkeypatch):
    """T8 / AC-12: Nutzer A hat ``{sms: LOW}``, Nutzer B nichts; derselbe
    'gering'-Alarm (echter Lauf) erreicht bei A die SMS, bei B nicht. Jeder
    Nutzer hat nur sein eigenes Protokoll, kein Schreiben unter ``default``."""
    uid_a, uid_b = _uid("t8-a"), _uid("t8-b")
    assert uid_a != uid_b and "default" not in (uid_a, uid_b)
    for uid in (uid_a, uid_b):
        _clean_user(uid)
    _profil(uid_a, SMS_A, PREMIUM_A)
    _profil(uid_b, SMS_B, PREMIUM_B)
    default_log_vorher = read_log("default")
    stub = _SevenIoStub()
    try:
        trip_a = _trip_lauf(monkeypatch, uid_a, {"sms": "LOW"}, BOE_GERING, stub, SMS_A)
        trip_b = _trip_lauf(monkeypatch, uid_b, None, BOE_GERING, stub, SMS_B)
        eintrag_a, eintrag_b = _protokoll(uid_a, trip_a), _protokoll(uid_b, trip_b)
        log_a, log_b = read_log(uid_a), read_log(uid_b)
    finally:
        stub.stop()
        for uid in (uid_a, uid_b):
            _clean_user(uid)
    assert len(stub.to(SMS_A)) == 1, f"T8: A (SMS LOW) muss die SMS bekommen: {stub.received!r}"
    assert stub.to(SMS_B) == [], (
        "T8: B hat keinen Wert (Vorbelegung mittel) -- 'gering' darf seine "
        f"SMS nicht erreichen: {stub.received!r}"
    )
    assert stub.to(PREMIUM_A) == stub.to(PREMIUM_B) == [], stub.received
    assert "sms" in eintrag_a["channels_sent"], eintrag_a
    assert _not_sent(eintrag_b).get("sms") == "below_channel_threshold", eintrag_b
    ids_a = {e["entity_id"] for e in log_a["entries"] + log_a["not_delivered"]}
    ids_b = {e["entity_id"] for e in log_b["entries"] + log_b["not_delivered"]}
    assert ids_a == {trip_a} and ids_b == {trip_b}, (ids_a, ids_b)
    assert read_log("default") == default_log_vorher, "kein Schreiben unter Nutzer 'default'"

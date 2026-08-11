"""RED — Issue #1701 (#1676 Scheibe S2b): Premium-SMS im Trip-Alarmpfad.

Spec: docs/specs/modules/feat_1701_alarm_premium_sms.md
Abgedeckt: AC-1, AC-2, AC-3, AC-5 (Trip-Teil), AC-6.

TESTPOLITIK (CLAUDE.md "Test-Politik: Zwei Schichten", Kern-Schicht): kein
Mock-Theater -- kein ``Mock()``/``patch()``/``MagicMock``. Der Versandweg
wird gegen einen ECHTEN lokalen HTTP-Server geprueft (Vorbild
``tests/unit/test_premium_sms_versand.py::_SevenIoStub``), kein Test-Double
der Transport-Klasse. SMS und Premium-SMS teilen sich denselben lokalen
Stub -- beide Kanaele lesen dieselbe ``sms_gateway_url``
(``SevenIoChannelBase``, Spec D1 der Vorgaenger-Scheibe S2a) und werden ueber
den ``to``-Empfaenger unterschieden.

PRUEFORT = WIRKORT (CLAUDE.md): AC-1/AC-2 pruefen sowohl die Rueckgabe der
Aufloesungsfunktion (``_effective_alert_channels``/``_briefing_channels``)
ALS AUCH die End-zu-Ende-Zustellung am Stub -- ein Test, der nur eine Seite
trifft, laesst die andere Haelfte unbewacht (genau der in mehreren Issues
wiederholte Fehler, den die Spec ausdruecklich benennt).

Pfadregel #1409: kein fester Hauptrepo-Pfad -- alle Zugriffe laufen ueber
``get_data_dir()`` (pytest-isolierte Datenwurzel, #1133).
"""
from __future__ import annotations

import http.server
import json
import socket
import threading
import urllib.parse
import uuid
from datetime import date, datetime, timedelta, timezone

from app.config import Settings
from app.models import (
    ChangeSeverity,
    ForecastMeta,
    GPXPoint,
    NormalizedTimeseries,
    Provider,
    SegmentWeatherData,
    SegmentWeatherSummary,
    TripReportConfig,
    TripSegment,
    WeatherChange,
)
from app.trip import Stage, Trip, Waypoint
from services.official_alerts import OfficialAlert

from tests.helpers.arrival_window_fixtures import active_window_offsets, stage_date

# Feste seven.io-Dienstnummer (S2a, ADR-0049) -- der Premium-Absender.
PREMIUM_SMS_SENDER = "4916092172595"
# Von Garmin gelernte Rueckadresse (S1).
LEARNED_REPLY_TO = "+4915799912345"
# Settings.sms_to -- darf den Premium-Kanal nie erreichen.
CONFIG_SMS_TO = "+49000000111"
LAT, LON = 47.0, 11.0


# ---------------------------------------------------------------------------
# Lokaler seven.io-Stub (echter HTTP-Server, kein Mock) -- bedient SMS UND
# Premium-SMS, weil beide Kanaele dieselbe `sms_gateway_url` lesen.
# ---------------------------------------------------------------------------

def _free_port() -> int:
    s = socket.socket()
    s.bind(("", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class _SevenIoStub:
    def __init__(self) -> None:
        self.received: list[dict] = []
        received = self.received

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):  # noqa: N802
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length)
                data = urllib.parse.parse_qs(body.decode())
                received.append({k: v[0] for k, v in data.items()})
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"100")

            def log_message(self, *args):  # noqa: D401
                pass

        self.port = _free_port()
        self._server = http.server.HTTPServer(("127.0.0.1", self.port), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._server.shutdown()

    def to(self, number: str) -> list[dict]:
        return [e for e in self.received if e.get("to") == number]


class _TelegramStub:
    def __init__(self) -> None:
        self.sent: list[dict] = []
        sent = self.sent
        counter = {"mid": 6000}

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


def _pin_telegram_stub(monkeypatch, stub: "_TelegramStub") -> None:
    """Herkunftssperre (#1476) auf 'production' pinnen -- Vorbild
    ``tests/tdd/test_alert_channel_threshold.py::_pin_telegram_stub``."""
    import output.channels.telegram as tg_module

    monkeypatch.setattr(tg_module, "running_origin", lambda module_file: "production")
    monkeypatch.setattr(tg_module, "TELEGRAM_API_BASE", stub.base_url)


# ---------------------------------------------------------------------------
# Fixture-Bausteine
# ---------------------------------------------------------------------------

def _uid(prefix: str) -> str:
    return f"tdd-1701-{prefix}-{uuid.uuid4().hex[:6]}"


def _write_profile(
    user_id: str, *, tier: str, reply_to: str | None = None,
    reply_age: timedelta = timedelta(minutes=5),
) -> None:
    """Echtes ``user.json`` -- Feldnamen wie S1 sie ablegt
    (``premium_sms_reply_to``/``premium_sms_reply_at``, RFC3339-UTC)."""
    from app.loader import get_data_dir

    path = get_data_dir(user_id)
    path.mkdir(parents=True, exist_ok=True)
    profile: dict = {"id": user_id, "tier": tier}
    if reply_to is not None:
        stamp = datetime.now(timezone.utc) - reply_age
        profile["premium_sms_reply_to"] = reply_to
        profile["premium_sms_reply_at"] = stamp.isoformat().replace("+00:00", "Z")
    (path / "user.json").write_text(json.dumps(profile), encoding="utf-8")


def _settings(port: int, user_id: str, *, telegram_port: int | None = None) -> Settings:
    """JEDES versandrelevante Feld ausdruecklich gesetzt (#1477) -- kein
    stiller Ruecksprung auf die Prod-.env des Worktrees."""
    update = {
        "sms_gateway_url": f"http://127.0.0.1:{port}/api/sms",
        "seven_api_key": "test-stub-key",
        "seven_sandbox_key": "test-stub-key",
        "sms_to": CONFIG_SMS_TO,
        "sms_from": None,
    }
    if telegram_port is not None:
        # Test-Modus-Guards (#1288/#1363): im Test-Modus (via tdd-Praefix in
        # with_user_profile() erzwungen) ist NUR der konfigurierte
        # Test-Bot-Token/-Chat erlaubt -- Prod- und Test-Wert identisch
        # gesetzt, analog dem Sandbox-Key-Muster fuer seven.io oben.
        update["telegram_bot_token"] = "tdd-1701-bot-token"
        update["telegram_test_bot_token"] = "tdd-1701-bot-token"
        update["telegram_chat_id"] = "4711"
        update["telegram_test_chat_id"] = "4711"
    base = Settings().with_user_profile(user_id)
    return base.model_copy(update=update)


def _weather_segment(segment_id: int | str = 1, **summary_kwargs) -> SegmentWeatherData:
    now = datetime.now(timezone.utc)
    seg = TripSegment(
        segment_id=segment_id,
        start_point=GPXPoint(lat=LAT, lon=LON, elevation_m=1000),
        end_point=GPXPoint(lat=LAT + 0.1, lon=LON + 0.1, elevation_m=1500),
        start_time=now - timedelta(hours=1), end_time=now + timedelta(hours=3),
        duration_hours=4.0, distance_km=6.0, ascent_m=500, descent_m=0,
    )
    return SegmentWeatherData(
        segment=seg,
        timeseries=NormalizedTimeseries(
            meta=ForecastMeta(provider=Provider.OPENMETEO, model="test", grid_res_km=1.0),
            data=[],
        ),
        aggregated=SegmentWeatherSummary(**summary_kwargs),
        fetched_at=now, provider="openmeteo",
    )


def _change() -> WeatherChange:
    return WeatherChange(
        metric="gust_max_kmh", old_value=20.0, new_value=45.0, delta=25.0,
        threshold=20.0, severity=ChangeSeverity.MODERATE, direction="increase",
        segment_id="1",
    )


def _base_trip(trip_id: str, *, alert_channels: dict | None = None,
                report_config: TripReportConfig | None = None) -> Trip:
    stage = Stage(
        id="T1", name="Tag 1", date=date.today(),
        waypoints=[Waypoint(id="W1", name="Start", lat=LAT, lon=LON, elevation_m=1000.0)],
    )
    trip = Trip(id=trip_id, name="Premium-Alarm-Trip", stages=[stage], official_warnings=None)
    trip.report_config = report_config or TripReportConfig(
        trip_id=trip_id, send_email=False, alert_on_changes=True,
    )
    trip.alert_cooldown_minutes = 0
    trip.official_alert_triggers_enabled = False
    if alert_channels is not None:
        trip.alert_channels = alert_channels
    return trip


def _radar_trip(trip_id: str, *, send_premium_sms: bool) -> Trip:
    arr0, arr1 = active_window_offsets(LAT, LON, -60, 120)
    wp0 = Waypoint(
        id="WP0", name="Start", lat=LAT, lon=LON, elevation_m=500.0, arrival_calculated=arr0,
    )
    wp1 = Waypoint(
        id="WP1", name="Ziel", lat=LAT + 0.1, lon=LON + 0.1, elevation_m=600.0,
        arrival_calculated=arr1,
    )
    stage = Stage(id="S1", name="Tag 1", date=stage_date(LAT, LON), waypoints=[wp0, wp1])
    trip = Trip(id=trip_id, name="AC-1 Radar-Trip", stages=[stage])
    trip.report_config = TripReportConfig(
        trip_id=trip_id, send_email=False, send_sms=False, send_telegram=False,
        send_premium_sms=send_premium_sms,
    )
    trip.alert_cooldown_minutes = 0
    return trip


def _light_wet_frames(lat, lon):
    """DI-Seam (RadarNowcastService.frame_source): leichter, nicht
    konvektiver Regen mit Onset in 5 Minuten (Vorbild
    ``tests/tdd/test_alert_channel_threshold.py::_light_wet_frames``)."""
    from providers.brightsky import RadarFrame

    now = datetime.now(timezone.utc)
    return [
        RadarFrame(timestamp=now + timedelta(minutes=5), precip_mm_h=0.5),
        RadarFrame(timestamp=now + timedelta(minutes=15), precip_mm_h=0.6),
    ]


def _official_alert() -> OfficialAlert:
    return OfficialAlert(
        source="test-vigilance", hazard="thunderstorm", level=3,
        label="Gewitter", valid_from=datetime.now(timezone.utc),
        valid_to=datetime.now(timezone.utc) + timedelta(hours=6),
        region_label="Testregion",
    )


# ═══════════════════════════════ AC-1 ═════════════════════════════════════

def test_deviation_alert_reaches_premium_sms_when_opted_in():
    """AC-1: Given ein Premium-Tier-Nutzer hat ``alert_channels.premium_sms
    = true`` UND eine gueltige, frische gelernte Rueckadresse / When ein
    Abweichungsalarm fuer diesen Trip ausgeloest wird / Then geht eine
    Premium-SMS mit dem Alarmtext an das Geraet hinaus.

    ROT-Grund (gemessen): ``_effective_alert_channels()`` kennt nur das
    Kanal-Tupel ``("email", "telegram", "sms")`` (``trip_alert.py:1492-1494``)
    -- ``alert_channels.premium_sms`` wird komplett ignoriert, das
    Kanal-Set bleibt leer, der Stub bekommt nie einen POST.
    """
    from services.trip_alert import TripAlertService

    uid = _uid("ac1-dev")
    _write_profile(uid, tier="premium", reply_to=LEARNED_REPLY_TO)
    trip = _base_trip(
        f"trip-ac1-dev-{uuid.uuid4().hex[:6]}", alert_channels={"premium_sms": True},
    )

    stub = _SevenIoStub()
    try:
        svc = TripAlertService(
            settings=_settings(stub.port, uid), user_id=uid, throttle_hours=0,
            mail_sink=lambda subject, body: None,
        )
        result = svc._send_alert(trip, [_weather_segment(1)], [_change()])
    finally:
        stub.stop()

    hits = stub.to(LEARNED_REPLY_TO)
    assert len(hits) == 1, (
        "AC-1: erwartet GENAU EINE Premium-SMS an die gelernte Rueckadresse, "
        f"erhalten: {hits!r} (voller Stub: {stub.received!r})"
    )
    assert hits[0].get("from") == PREMIUM_SMS_SENDER, (
        f"Absender falsch: {hits[0].get('from')!r}, erwartet {PREMIUM_SMS_SENDER!r}"
    )
    assert hits[0].get("text"), "Alarmtext darf nicht leer sein"
    assert "premium_sms" in result.delivered_channels, (
        f"'premium_sms' fehlt in delivered_channels: {result.delivered_channels!r}"
    )


def test_radar_alert_reaches_premium_sms_when_opted_in(monkeypatch):
    """AC-1 (Radar): Given ein Premium-Tier-Nutzer hat im Trip-Briefing
    ``send_premium_sms=true`` aktiv UND eine frische gelernte Rueckadresse /
    When ein Regenradar-Alarm ausgeloest wird / Then geht ebenfalls eine
    Premium-SMS hinaus -- derselbe Kanal, ein STRUKTURELL getrennter
    Ansatzpunkt (Issue #1467 S3, ``trip_alert.py:825-846``).

    ROT-Grund (gemessen): ``_radar_effective_channels()`` hat keinen
    ``premium_sms``-Zweig -- die Inline-Kopie kennt nur email/telegram/sms.
    """
    import app.loader as loader
    from services.radar_service import RadarNowcastService
    from services.trip_alert import TripAlertService

    uid = _uid("ac1-radar")
    _write_profile(uid, tier="premium", reply_to=LEARNED_REPLY_TO)
    trip = _radar_trip(f"trip-ac1-radar-{uuid.uuid4().hex[:6]}", send_premium_sms=True)
    monkeypatch.setattr(loader, "load_all_trips", lambda **kw: [trip])

    stub = _SevenIoStub()
    try:
        svc = TripAlertService(
            settings=_settings(stub.port, uid), user_id=uid, throttle_hours=0,
            radar_service=RadarNowcastService(frame_source=_light_wet_frames),
            mail_sink=lambda subject, body: None,
        )
        sent = svc.check_radar_alerts()
    finally:
        stub.stop()

    assert sent >= 1, f"Voraussetzung: der Radar-Alarm muss ausgeloest sein, sent={sent}"
    hits = stub.to(LEARNED_REPLY_TO)
    assert len(hits) == 1, (
        f"AC-1 (Radar): erwartet GENAU EINE Premium-SMS, erhalten: {hits!r} "
        f"(voller Stub: {stub.received!r})"
    )


# ═══════════════════════════════ AC-2 ═════════════════════════════════════

def test_legacy_trip_inherits_premium_sms_from_briefing_config():
    """AC-2: Given ein Trip hat KEIN scharfes ``alert_channels``-Set (None)
    UND im Trip-Briefing ist ``send_premium_sms=true`` aktiv / When ein
    Alarm ausgeloest wird / Then erbt der Alarmpfad den Premium-SMS-Kanal
    automatisch mit -- genauso wie es heute fuer die drei bestehenden
    Kanaele gilt.

    ROT-Grund (gemessen): ``_briefing_channels()`` liest nur send_email/
    send_telegram/send_sms -- ``send_premium_sms`` wird nicht abgefragt.
    """
    from services.trip_alert import TripAlertService

    uid = _uid("ac2")
    _write_profile(uid, tier="premium", reply_to=LEARNED_REPLY_TO)
    trip_id = f"trip-ac2-{uuid.uuid4().hex[:6]}"
    trip = _base_trip(
        trip_id,
        report_config=TripReportConfig(
            trip_id=trip_id, send_email=False, send_telegram=False, send_sms=False,
            send_premium_sms=True, alert_on_changes=True,
        ),
    )
    assert trip.alert_channels is None, "Voraussetzung: kein scharfes Kanal-Set gesetzt"

    stub = _SevenIoStub()
    try:
        svc = TripAlertService(
            settings=_settings(stub.port, uid), user_id=uid, throttle_hours=0,
            mail_sink=lambda subject, body: None,
        )
        briefing_channels = svc._briefing_channels(trip.report_config)
        result = svc._send_alert(trip, [_weather_segment(1)], [_change()])
    finally:
        stub.stop()

    assert "premium_sms" in briefing_channels, (
        f"_briefing_channels() vererbt 'premium_sms' nicht: {briefing_channels!r}"
    )
    hits = stub.to(LEARNED_REPLY_TO)
    assert len(hits) == 1, (
        f"AC-2: die Vererbung muss End-zu-Ende wirken, erhalten: {hits!r}"
    )
    assert "premium_sms" in result.delivered_channels, (
        f"'premium_sms' fehlt in delivered_channels: {result.delivered_channels!r}"
    )


# ═══════════════════════════════ AC-3 ═════════════════════════════════════

def test_official_trip_alert_reaches_premium_sms():
    """AC-3: Given Premium-SMS ist im effektiven Kanal-Set eines Trips fuer
    amtliche Warnungen enthalten / When eine amtliche Warnung eintrifft /
    Then wird auch dafuer eine Premium-SMS mit dem amtlichen Kurztext
    versendet -- ``send_official_alert()`` ist eine von
    ``_dispatch_alert_message`` UNABHAENGIGE Funktion und waere sonst der
    stille vierte blinde Fleck.

    ROT-Grund (gemessen): ``send_official_alert()`` hat nur drei
    Kanal-Zweige (email/telegram/sms, ``notification_service.py:845-894``).
    """
    from services.notification_service import NotificationService

    uid = _uid("ac3")
    _write_profile(uid, tier="premium", reply_to=LEARNED_REPLY_TO)
    trip = _base_trip(f"trip-ac3-{uuid.uuid4().hex[:6]}")

    stub = _SevenIoStub()
    try:
        svc = NotificationService(settings=_settings(stub.port, uid), user_id=uid)
        result = svc.send_official_alert(
            trip=trip, notices=[(_official_alert(), ["1"])],
            effective_channels={"email", "premium_sms"},
            mail_sink=lambda subject, body: None,
        )
    finally:
        stub.stop()

    hits = stub.to(LEARNED_REPLY_TO)
    assert len(hits) == 1, (
        f"AC-3: die amtliche Warnung muss auch per Premium-SMS gehen, "
        f"erhalten: {hits!r} (voller Stub: {stub.received!r})"
    )
    assert "premium_sms" in result.sent_channels, (
        f"'premium_sms' fehlt in sent_channels: {result.sent_channels!r}"
    )


# ═══════════════════════════════ AC-5 (Trip) ══════════════════════════════

_CONTROL_REPLY_TO = "+4915799954321"


def test_standard_tier_never_reaches_premium_sms_via_alerts(monkeypatch):
    """AC-5 (Trip): Given ZWEI Nutzer mit identisch konfiguriertem
    Premium-SMS-Opt-in in allen drei Alarmpfaden (Abweichung, Radar,
    amtlich) -- Nutzer A hat Tier ``standard``, Nutzer B (Kontrolle) hat
    Tier ``premium`` / When bei BEIDEN dieselben drei Alarmpfade ausgeloest
    werden / Then bleibt Premium-SMS bei Nutzer A in JEDEM der drei Pfade
    inaktiv, waehrend Nutzer B sie in mindestens einem Pfad bekommt --
    ``premium_sms_allowed()`` (NICHT ``sms_allowed()``, das ``standard``
    durchlaesst) entscheidet an jeder Ansatzstelle.

    Warum beide Seiten in EINEM Test stehen (Projektregel, s.
    ``tests/tdd/test_compare_alert_channel_delivery.py`` Moduldocstring):
    die stumme Seite (Nutzer A) ist bereits HEUTE gruen, weil Premium-SMS
    noch NIRGENDS verdrahtet ist (AC-1/AC-2/AC-3 sind rot) -- ein Test nur
    mit Nutzer A wuerde die Nicht-Implementierung feiern statt das Tier-Gate
    zu pruefen. Erst die Kontroll-Seite (Nutzer B, MUSS mindestens einmal
    ankommen) macht den Test scharf und damit heute ROT.
    """
    import app.loader as loader
    from services.trip_alert import TripAlertService
    from services.user_tier import premium_sms_allowed, sms_allowed

    uid = _uid("ac5-trip")
    uid_control = _uid("ac5-trip-control")
    _write_profile(uid, tier="standard", reply_to=LEARNED_REPLY_TO)
    _write_profile(uid_control, tier="premium", reply_to=_CONTROL_REPLY_TO)
    assert sms_allowed(uid) is True and premium_sms_allowed(uid) is False, (
        "Testvoraussetzung: 'standard' darf normale SMS, aber NICHT Premium-SMS"
    )
    assert premium_sms_allowed(uid_control) is True, (
        "Testvoraussetzung Kontrolle: 'premium' darf Premium-SMS"
    )

    stub = _SevenIoStub()
    try:
        settings = _settings(stub.port, uid)
        settings_control = _settings(stub.port, uid_control)

        for user_id, current_settings in ((uid, settings), (uid_control, settings_control)):
            trip_dev = _base_trip(
                f"trip-ac5-dev-{user_id}-{uuid.uuid4().hex[:6]}",
                alert_channels={"premium_sms": True},
            )
            TripAlertService(
                settings=current_settings, user_id=user_id, throttle_hours=0,
                mail_sink=lambda subject, body: None,
            )._send_alert(trip_dev, [_weather_segment(1)], [_change()])

            trip_off = _base_trip(
                f"trip-ac5-off-{user_id}-{uuid.uuid4().hex[:6]}",
                alert_channels={"premium_sms": True},
            )
            TripAlertService(
                settings=current_settings, user_id=user_id, throttle_hours=0,
                mail_sink=lambda subject, body: None,
            )._send_official_alert_only(trip_off, [(_official_alert(), ["1"])])
    finally:
        stub.stop()

    hits_standard = stub.to(LEARNED_REPLY_TO)
    hits_control = stub.to(_CONTROL_REPLY_TO)
    assert hits_standard == [], (
        "AC-5: ein Nutzer mit Tier 'standard' darf in KEINEM der Alarmpfade "
        f"eine Premium-SMS bekommen, erhalten: {hits_standard!r}"
    )
    assert len(hits_control) >= 1, (
        "AC-5 (Kontrolle): ein Nutzer mit Tier 'premium' MUSS bei identischer "
        "Konfiguration Premium-SMS bekommen -- sonst beweist die stumme Seite "
        "oben nur, dass Premium-SMS ueberhaupt nicht verdrahtet ist, nicht "
        f"dass das Tier-Gate entscheidet. Erhalten: {hits_control!r} "
        f"(voller Stub: {stub.received!r})"
    )


# ═══════════════════════════════ AC-6 ═════════════════════════════════════

def test_failed_premium_sms_does_not_abort_remaining_channels(monkeypatch):
    """AC-6: Given ein Alarm geht an mehrere Kanaele gleichzeitig, darunter
    Premium-SMS, UND der Premium-Versand schlaegt fehl (keine gelernte
    Rueckadresse) / When der Alarm verarbeitet wird / Then erreichen die
    uebrigen konfigurierten Kanaele (E-Mail/Telegram/SMS) den Nutzer
    trotzdem UND der Aufruf selbst bricht NICHT mit einer unbehandelten
    Ausnahme ab.

    D4-Fund: ``_log_error()`` (``notification_service.py:1301``) indiziert
    hart in ein Label-Dict ohne 'premium_sms'-Eintrag -- ein gescheiterter
    Premium-Versand loest dort einen ``KeyError`` INNERHALB der
    Fehlerbehandlung des ersten Fehlers aus, der Aufruf bricht komplett ab
    und das Ergebnis (inkl. Protokollierung durch den Aufrufer) geht
    verloren -- aus einem Teilausfall wird ein Totalausfall.

    ROT-Grund heute (vor JEDER Implementierung): ``_dispatch_alert_message()``
    kennt 'premium_sms' in effective_channels ueberhaupt nicht -- der Kanal
    wird nie in ``blocked_channels``/``blocked_reason_codes`` gefuehrt, weil
    er nie versucht wird. Nach der Implementierung mit zurueckgenommenem
    D4-Fix wuerde stattdessen die Ausnahme selbst dieses Testergebnis
    hervorbringen (Mutations-Gegenprobe).
    """
    from services.notification_service import NotificationService

    uid = _uid("ac6")
    _write_profile(uid, tier="premium", reply_to=None)  # keine Rueckadresse -> Sperre

    stub = _SevenIoStub()
    tg_stub = _TelegramStub()
    try:
        _pin_telegram_stub(monkeypatch, tg_stub)
        settings = _settings(stub.port, uid, telegram_port=tg_stub.port)
        svc = NotificationService(settings=settings, user_id=uid)
        trip = _base_trip(f"trip-ac6-{uuid.uuid4().hex[:6]}")
        mails: list[tuple[str, str]] = []

        try:
            result = svc.send_deviation_alert(
                trip=trip, weather=[_weather_segment(1)], changes=[_change()],
                effective_channels={"email", "telegram", "sms", "premium_sms"},
                mail_sink=lambda subject, body: mails.append((subject, body)),
            )
        except Exception as e:  # noqa: BLE001 -- genau das ist der D4-Befund
            import pytest

            pytest.fail(
                "AC-6: der Versandaufruf darf bei einem gescheiterten "
                "Premium-SMS-Versand NICHT mit einer unbehandelten Ausnahme "
                f"abbrechen (Totalausfall-Risiko, Spec D4) -- erhalten: "
                f"{type(e).__name__}: {e}"
            )
    finally:
        stub.stop()
        tg_stub.stop()

    assert mails, "AC-6: E-Mail muss trotz gescheitertem Premium-Versand ankommen"
    assert tg_stub.sent, "AC-6: Telegram muss trotz gescheitertem Premium-Versand ankommen"
    assert stub.to(CONFIG_SMS_TO), (
        "AC-6: SMS muss trotz gescheitertem Premium-Versand ankommen"
    )
    assert stub.to(LEARNED_REPLY_TO) == [], (
        "AC-6 Voraussetzung: ohne gelernte Rueckadresse darf KEIN "
        f"Premium-SMS-POST hinausgehen, erhalten: {stub.to(LEARNED_REPLY_TO)!r}"
    )
    assert result.blocked_channels.get("premium_sms"), (
        "AC-6: der gescheiterte Premium-Versand muss als Grund in "
        f"blocked_channels stehen, gefunden: {result.blocked_channels!r} -- "
        "heute wird 'premium_sms' in effective_channels ueberhaupt nicht "
        "erkannt, deshalb bleibt das Feld leer."
    )

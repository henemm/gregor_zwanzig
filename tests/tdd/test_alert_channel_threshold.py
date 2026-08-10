"""TDD RED — Issue #1461 Scheibe S3b-2a: einstellbare Dringlichkeits-Schwelle
je Alarm-Kanal (Trips).

SPEC: docs/specs/modules/feat_1461_s3b2a_kanal_schwelle.md (AC-2, AC-3, AC-4,
AC-5, AC-8, AC-12 — die sechs Kriterien, die HEUTE fehlschlagen; AC-1, AC-9,
AC-11, AC-13 sind Invarianten, die bereits gruen sind; AC-6/AC-7 (Go) und
AC-10 (Oberflaeche) sind nicht Teil dieser Python-Testdatei).

RED-Grund heute (gemessen, s. docs/context/feat-1461-s3b2-kanal-schwelle.md):
die Dringlichkeit ('LOW'/'MODERATE'/'HIGH', seit S3a vorhanden) steuert
NIRGENDS eine Kanalentscheidung. Es fehlen:

* ``services.alert_channel_threshold.split_by_threshold()`` — der neue
  geteilte Baustein (Modul existiert nicht).
* die Auswertung von ``trip.alert_channel_thresholds`` an den ZWEI
  Trip-Auflösungsstellen (``TripAlertService._effective_alert_channels()``
  UND der Inline-Kopie im Radar-Zweig, ``trip_alert.py:852-860``).
* ``alert_log.append_entry(below_threshold_channels=...)`` — der Parameter
  existiert nicht, der Protokoll-Grund ``below_channel_threshold`` wird nie
  geschrieben.
* das deutsche Label fuer diesen Grund in
  ``output/renderers/email/undelivered_hint.py`` (``_REASON_LABELS``).
* der Schwellen-Parameter an ``official_alerts_to_sms_entries()`` fuer die
  Trip-Kurznachricht (heute hart ``MIN_SMS_LEVEL = 3``, Startwert 'gering'
  muesste ab Stufe 2 zeigen).

Testpolitik (CLAUDE.md „Test-Politik: Zwei Schichten"): kein Mock-Theater
— kein ``Mock()``/``patch()``/``MagicMock``. Telegram-Zustellung wird ueber
einen ECHTEN lokalen HTTP-Stub (``127.0.0.1``, Muster
``tests/tdd/test_alert_urgency.py::_TelegramStub`` — dieselbe Testfamilie,
selbe Kanalwahl-Naht) beobachtet, nicht ueber ein Test-Double der Klasse.
E-Mail laeuft ueber den bestehenden ``mail_sink``-DI-Seam (kein Netz). Radar-
Frames kommen ueber den bestehenden ``frame_source``-DI-Seam
(``RadarNowcastService``). Reale Persistenz unter der pytest-isolierten
``app.loader.get_data_dir()``-Basis (#1133).

Pfadregel #1409: keine Datei dieses Moduls referenziert einen festen
Hauptrepo-Pfad — alle Zugriffe laufen ueber ``get_data_dir()`` bzw. die
bestehenden DI-Naehte.
"""
from __future__ import annotations

import http.server
import json
import socket
import threading
import uuid
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app.config import Settings
from app.loader import save_location
from app.models import (
    ChangeSeverity,
    MetricConfig,
    TripReportConfig,
    UnifiedWeatherDisplayConfig,
    WeatherChange,
)
from app.trip import Stage, Trip, Waypoint

from tests.helpers.alert_log_fixtures import (
    LAT,
    LON,
    gust_alert_trip,
    read_log,
    weather,
)
from tests.helpers.arrival_window_fixtures import active_window_offsets, stage_date

# ═══════════════════════════ Telegram-Stub (echtes 127.0.0.1) ═════════════
#
# 1:1 Muster aus tests/tdd/test_alert_urgency.py::_TelegramStub — derselbe
# Alarm-Dispatch-Pfad, dieselbe Beobachtungstechnik: ein echter lokaler
# HTTP-Server zeichnet die tatsaechlich gesendete Nutzlast auf, kein
# Test-Double der Transport-Klasse.


def _free_port() -> int:
    s = socket.socket()
    s.bind(("", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class _TelegramStub:
    def __init__(self) -> None:
        self.sent: list[dict] = []
        sent = self.sent
        counter = {"mid": 5000}

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
    """Herkunftssperre (#1476) auf 'production' pinnen (Muster
    test_alert_urgency.py) — gemessen wird die Kanal-Schwelle, nicht die
    Herkunftsschicht; ohne Pin bricht der Test-Chat-Guard in jedem
    Nicht-Server-Checkout vor dem Stub ab."""
    import output.channels.telegram as tg_module

    monkeypatch.setattr(tg_module, "running_origin", lambda module_file: "production")
    monkeypatch.setattr(tg_module, "TELEGRAM_API_BASE", stub.base_url)


# ═══════════════════════════ Gemeinsame Fixtures ═══════════════════════════


def _uid(prefix: str) -> str:
    return f"tdd-1461-s3b2a-{prefix}-{uuid.uuid4().hex[:6]}"


def _settings_email_and_telegram() -> Settings:
    """``can_send_email()`` UND ``can_send_telegram()`` == True. Telegram
    laeuft ueber den lokalen Stub (kein echtes Bot-API-Konto noetig)."""
    return Settings(
        smtp_host="dummy.invalid", smtp_user="dummy", smtp_pass="dummy",
        mail_to="dummy@example.com",
        telegram_bot_token="tdd-1461-s3b2a-bot", telegram_chat_id="4711",
    )


def _change(severity: ChangeSeverity) -> WeatherChange:
    """Δ-Aenderung mit steuerbarer Severity (-> Dringlichkeit via
    ``alert_urgency.urgency_from_changes``: MINOR -> 'LOW')."""
    return WeatherChange(
        metric="gust_max_kmh", old_value=20.0, new_value=45.0, delta=25.0,
        threshold=20.0, severity=severity, direction="increase", segment_id="1",
    )


def _telegram_trip(trip_id: str) -> Trip:
    """Tour mit scharfer Boeen-Delta-Regel (gust_alert_trip) UND
    eingeschaltetem Telegram-Kanal — Vorbild
    ``test_alert_urgency.py::_telegram_trip``."""
    trip = gust_alert_trip(trip_id)
    trip.report_config = TripReportConfig(
        trip_id=trip_id, send_email=True, send_telegram=True, send_sms=False,
        alert_on_changes=True,
    )
    trip.alert_cooldown_minutes = 0
    return trip


def _ac4_trip(trip_id: str) -> Trip:
    """Tour mit ZWEI Wegpunkten (fuer den echten Briefing-Renderpfad, Vorbild
    ``test_alert_undelivered_hint.py::_trip``) UND scharfer Boeen-Delta-Regel
    (fuer den echten Alarm-Auslosepfad, Vorbild ``gust_alert_trip``).

    PO-Korrektur (2026-08-05): die Briefing-Kanaele bleiben wie beim Vorbild
    ``test_alert_undelivered_hint.py::_trip`` auf ``False`` -- der echte
    Briefing-Renderpfad (``_run_trip_briefing``) baut die Mail unabhaengig
    vom tatsaechlichen Versand (``_ReportRecorder`` faengt sie ab, Outcome
    ``no_channels`` ist erlaubt). Die Alarm-Kanaele kommen NICHT ueber die
    Vererbung aus ``report_config``, sondern EXPLIZIT ueber
    ``trip.alert_channels`` -- das ist ohnehin der praezisere Test: er prueft
    die Schwelle, nicht die Kanal-Vererbung (Issue #638 D2)."""
    stage = Stage(
        id="T1", name="Tag 1", date=date.today(),
        waypoints=[
            Waypoint(id="G1", name="Start", lat=LAT, lon=LON, elevation_m=1000.0),
            Waypoint(id="G2", name="Ziel", lat=LAT + 0.1, lon=LON + 0.1, elevation_m=1500.0),
        ],
    )
    trip = Trip(
        id=trip_id, name="Schwellen-Trip", stages=[stage], official_warnings=None,
        display_config=UnifiedWeatherDisplayConfig(
            trip_id=trip_id,
            metrics=[MetricConfig(metric_id="gust", enabled=True)],
            metric_alert_levels={"wind_gust": "standard"},
        ),
    )
    trip.report_config = TripReportConfig(
        trip_id=trip_id, send_email=False, send_telegram=False, send_sms=False,
        alert_on_changes=True,
    )
    trip.alert_channels = {"email": True, "telegram": True, "sms": False}
    trip.alert_cooldown_minutes = 0
    trip.official_alert_triggers_enabled = False
    return trip


def _radar_trip(trip_id: str) -> Trip:
    """Tour im aktiven Segmentfenster JETZT — Vorbild
    ``test_issue_827_radar_throttle_recording.py::_make_trip``."""
    # #1667 S1: wanduhr-robustes Ankunftsfenster statt roher now+Nh-Arithmetik
    # (ab 22:00 UTC lief die +2h/+4h-Folge steigend ueber Mitternacht).
    arr0, arr1 = active_window_offsets(LAT, LON, 120, 240)
    wp0 = Waypoint(
        id="WP0", name="Start", lat=LAT, lon=LON, elevation_m=500.0,
        arrival_calculated=arr0,
    )
    wp1 = Waypoint(
        id="WP1", name="Ziel", lat=LAT + 0.1, lon=LON + 0.1, elevation_m=600.0,
        arrival_calculated=arr1,
    )
    stage = Stage(id="S1", name="Tag 1", date=stage_date(), waypoints=[wp0, wp1])
    trip = Trip(id=trip_id, name="AC3 Radar-Trip", stages=[stage])
    trip.report_config = TripReportConfig(
        trip_id=trip_id, send_email=True, send_telegram=True, send_sms=False,
    )
    trip.alert_cooldown_minutes = 0
    return trip


def _light_wet_frames(lat: float, lon: float) -> list:
    """DI-Seam (RadarNowcastService.frame_source): leichter, NICHT
    konvektiver Regen mit Onset in 5 Minuten -> 'LOW'-Dringlichkeit
    (``alert_urgency.urgency_from_radar``, 0.1 <= mm/h < 1.0 =
    ``INTENSITY_LIGHT``)."""
    from providers.brightsky import RadarFrame

    now = datetime.now(timezone.utc)
    return [
        RadarFrame(timestamp=now + timedelta(minutes=5), precip_mm_h=0.5),
        RadarFrame(timestamp=now + timedelta(minutes=15), precip_mm_h=0.6),
    ]


# ══════════════════════════════════ AC-2 ══════════════════════════════════


def test_ac2_erhoehte_schwelle_blockt_nur_diesen_kanal_bei_geringer_dringlichkeit(
    monkeypatch,
):
    """AC-2.

    GIVEN ein Nutzer hat fuer Telegram eine erhoehte Schwelle ('HIGH')
          eingestellt, E-Mail ist unveraendert (Startwert 'gering').
    WHEN  ein per Vorhersage-Aenderung ausgeloester Alarm mit geringer
          Dringlichkeit auftritt (Δ-Severity MINOR -> 'LOW').
    THEN  erreicht die Meldung Telegram NICHT, E-Mail weiterhin.

    Heute (RED): 'trip.alert_channel_thresholds' wird an keiner Stelle
    ausgewertet -- Telegram bekommt die Meldung trotz erhoehter Schwelle.
    """
    from services.trip_alert import TripAlertService

    uid = _uid("ac2")
    trip = _telegram_trip(f"trip-ac2-{uuid.uuid4().hex[:6]}")
    trip.alert_channel_thresholds = {"telegram": "HIGH"}

    stub = _TelegramStub()
    try:
        _pin_telegram_stub(monkeypatch, stub)
        mails: list = []
        svc = TripAlertService(
            settings=_settings_email_and_telegram(), user_id=uid, throttle_hours=0,
            mail_sink=lambda subject, body: mails.append((subject, body)),
        )
        result = svc._send_alert(
            trip, [weather(1)], [_change(ChangeSeverity.MINOR)],
        )
    finally:
        stub.stop()

    assert mails, "AC-2 Voraussetzung: E-Mail (unveraenderter Kanal) muss ankommen"
    assert not stub.sent, (
        "AC-2: Telegram hat eine erhoehte Schwelle (HIGH), die Meldung ist "
        f"nur gering-dringlich -- sie darf Telegram NICHT erreichen. "
        f"Tatsaechlich gesendet: {stub.sent!r}"
    )
    assert "telegram" not in result.delivered_channels, (
        f"AC-2: 'telegram' darf nicht in delivered_channels stehen: "
        f"{result.delivered_channels!r}"
    )
    assert "email" in result.delivered_channels


# ══════════════════════════════════ AC-3 ══════════════════════════════════


def test_ac3_regenradar_pfad_respektiert_dieselbe_schwelle(monkeypatch):
    """AC-3.

    GIVEN dieselbe erhoehte Telegram-Schwelle wie AC-2.
    WHEN  ein durch Regenradar (Nowcast) ausgeloester Alarm mit geringer
          Dringlichkeit auftritt.
    THEN  bleibt Telegram ebenso stumm wie beim Vorhersage-Aenderungs-Alarm.

    Deckt die INLINE-KOPIE ``trip_alert.py:852-860`` ab, die die reguläre
    Auflösung NICHT aufruft (Kontext-Risiko 5). Heute (RED): dieselbe
    Ungefiltertheit wie AC-2, unabhaengig vom Pfad.
    """
    import app.loader as loader
    from services.radar_service import RadarNowcastService
    from services.trip_alert import TripAlertService

    uid = _uid("ac3")
    trip = _radar_trip(f"trip-ac3-{uuid.uuid4().hex[:6]}")
    trip.alert_channel_thresholds = {"telegram": "HIGH"}
    monkeypatch.setattr(loader, "load_all_trips", lambda **kw: [trip])

    stub = _TelegramStub()
    try:
        _pin_telegram_stub(monkeypatch, stub)
        mails: list = []
        svc = TripAlertService(
            settings=_settings_email_and_telegram(), throttle_hours=0, user_id=uid,
            radar_service=RadarNowcastService(frame_source=_light_wet_frames),
            mail_sink=lambda subject, body: mails.append((subject, body)),
        )
        sent = svc.check_radar_alerts()
    finally:
        stub.stop()

    assert sent >= 1, (
        f"AC-3 Voraussetzung: der Radar-Alarm muss ausgeloest worden sein, "
        f"erhalten sent={sent}"
    )
    assert mails, "AC-3 Voraussetzung: E-Mail muss zugestellt worden sein"
    assert not stub.sent, (
        "AC-3: Der Regenradar-Pfad ist eine eigene Inline-Auflösung "
        "(trip_alert.py:852-860), die die reguläre Kanal-Schwelle bislang "
        f"NICHT anwendet -- Telegram wurde trotz erhoehter Schwelle erreicht: "
        f"{stub.sent!r}"
    )


# ══════════════════════════════════ AC-4 ══════════════════════════════════


def test_ac4_alle_kanaele_unter_schwelle_landet_im_protokoll_und_briefing(
    monkeypatch,
):
    """AC-4.

    GIVEN E-Mail UND Telegram haben beide eine hohe Schwelle ('HIGH').
    WHEN  ein Alarm mit geringer Dringlichkeit ausgeloest wird (alle
          eingeschalteten Kanaele liegen darunter).
    THEN  ``check_and_send_alerts()`` liefert False (keine echte
          Zustellung), das Protokoll erhaelt GENAU EINEN Eintrag unter
          'not_delivered' (NICHT unter 'entries' -- fuer Go unsichtbar, D4),
          und das naechste Briefing weist die Meldung als nicht zugestellt
          aus (S3b-1-Sichtbarkeit).

    Heute (RED): keine Schwellen-Filterung -> beide Kanaele werden
    tatsaechlich erreicht, der Eintrag landet unter 'entries', das Briefing
    zeigt nichts.
    """
    from services.alert_briefing_anchor import record_briefing_sent
    from services.trip_alert import TripAlertService
    from tests.tdd.test_alert_undelivered_hint import (
        _hint_lines,
        _ReportRecorder,
        _run_trip_briefing,
    )

    uid = _uid("ac4")
    trip = _ac4_trip(f"trip-ac4-{uuid.uuid4().hex[:6]}")
    trip.alert_channel_thresholds = {"email": "HIGH", "telegram": "HIGH"}

    anchor_zeit = datetime.now(timezone.utc) - timedelta(hours=6)
    record_briefing_sent(
        user_id=uid, entity_id=trip.id, entity_type="trip", at=anchor_zeit,
    )

    stub = _TelegramStub()
    try:
        _pin_telegram_stub(monkeypatch, stub)
        mails: list = []
        svc = TripAlertService(
            settings=_settings_email_and_telegram(), user_id=uid, throttle_hours=0,
            mail_sink=lambda subject, body: mails.append((subject, body)),
        )
        sent = svc.check_and_send_alerts(
            trip, [weather(1, gust_max_kmh=20.0)],
            fresh_weather=[weather(1, gust_max_kmh=45.0)],
        )
    finally:
        stub.stop()

    assert sent is False, (
        "AC-4: bei komplett unterdrueckter Meldung darf check_and_send_alerts "
        f"nicht True liefern (keine echte Zustellung), erhalten sent={sent}"
    )
    assert not mails and not stub.sent, (
        "AC-4 Voraussetzung: BEIDE Kanaele haben eine hohe Schwelle -- weder "
        f"E-Mail ({mails!r}) noch Telegram ({stub.sent!r}) duerfen ankommen"
    )

    log = read_log(uid)
    assert log["entries"] == [], (
        "AC-4: bei Totalausfall darf KEIN Eintrag unter 'entries' stehen "
        f"(das waere fuer Go sichtbar, D4) -- gefunden: {log['entries']!r}"
    )
    assert len(log["not_delivered"]) == 1, (
        "AC-4: die vollstaendig unterdrueckte Meldung muss GENAU EINEN "
        f"Eintrag im Protokoll unter 'not_delivered' erzeugen, gefunden "
        f"{len(log['not_delivered'])}: {log['not_delivered']!r}"
    )

    recorder = _ReportRecorder()
    recorder.install(monkeypatch)
    report = _run_trip_briefing(recorder, uid, trip)
    zeilen = _hint_lines(report.email_plain)
    assert len(zeilen) == 1, (
        "AC-4: das naechste Briefing muss die unterdrueckte Meldung als "
        f"nicht zugestellt ausweisen, gefunden {zeilen!r}\n"
        f"--- Klartext-Mail ---\n{report.email_plain}"
    )


# ══════════════════════════════════ AC-5 ══════════════════════════════════


def test_ac5_grund_ist_deutscher_klartext_kein_interner_bezeichner(monkeypatch):
    """AC-5.

    GIVEN eine Meldung wurde wegen der Kanal-Schwelle unterdrueckt -- das
          Protokoll traegt den neuen Grund ``below_channel_threshold``
          (Spec-Konstante, Dependencies-Tabelle) fuer einen sonst
          eingeschalteten Kanal.
    WHEN  das naechste Briefing erzeugt wird.
    THEN  nennt die Vorfall-Zeile einen deutschen, lesbaren Grund -- NICHT
          den rohen internen Bezeichner ``below_channel_threshold``.

    Heute (RED): ``undelivered_hint._REASON_LABELS`` kennt nur
    ``delivery_failed``/``quiet_hours``/``daily_limit``/``cooldown`` -- der
    Fallback ``_REASON_LABELS.get(r, r)`` zeigt den rohen String.
    """
    from tests.tdd.test_alert_undelivered_hint import (
        _entry,
        _hint_lines,
        _ReportRecorder,
        _run_trip_briefing,
        _seed,
    )
    from tests.tdd.test_alert_undelivered_hint import _trip as _hint_trip

    uid = _uid("ac5")
    trip = _hint_trip(f"trip-ac5-{uuid.uuid4().hex[:6]}")

    jetzt = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    vorfall = jetzt - timedelta(hours=2)
    _seed(
        uid, entity_id=trip.id, letztes_briefing=jetzt - timedelta(hours=6),
        not_delivered=[_entry(
            entity_id=trip.id, sent_at=vorfall, metrics=(("gust", "max"),),
            reason="forecast_change", channels_sent=("email",),
            not_sent=(("telegram", "below_channel_threshold"),),
        )],
    )

    recorder = _ReportRecorder()
    recorder.install(monkeypatch)
    report = _run_trip_briefing(recorder, uid, trip)

    zeilen = _hint_lines(report.email_plain)
    assert len(zeilen) == 1, (
        f"AC-5 Voraussetzung: genau eine Vorfall-Zeile erwartet, gefunden "
        f"{zeilen!r}\n--- Klartext-Mail ---\n{report.email_plain}"
    )
    zeile = zeilen[0]
    assert "below_channel_threshold" not in zeile, (
        "AC-5: Der interne Bezeichner 'below_channel_threshold' darf NICHT "
        f"im Klartext der Mail stehen: {zeile!r}"
    )
    assert "Schwelle" in zeile, (
        "AC-5: Die Zeile muss einen deutschen, lesbaren Grund fuer die "
        f"Kanal-Schwelle nennen (z.B. 'Schwelle'), gefunden: {zeile!r}"
    )


# ══════════════════════════════════ AC-8 ══════════════════════════════════


def test_ac8_zwei_nutzer_je_eigene_schwelle_ohne_vermischung(monkeypatch):
    """AC-8.

    GIVEN zwei verschiedene Nutzer mit je eigenem Trip: Nutzer A hat
          Telegram auf 'HIGH' gesetzt, Nutzer B hat Telegram unveraendert
          bei 'LOW' (Startwert) belassen.
    WHEN  bei BEIDEN im selben Testlauf ein Alarm mit geringer Dringlichkeit
          ausgeloest wird.
    THEN  wirkt bei jedem Nutzer NUR seine eigene Einstellung: A bekommt
          keinen Telegram-Alarm, B bekommt ihn weiterhin.

    Heute (RED): keine Schwellen-Filterung -> BEIDE Nutzer bekommen den
    Telegram-Alarm, unabhaengig von der (wirkungslosen) Einstellung.
    """
    from services.trip_alert import TripAlertService

    uid_hoch = _uid("ac8-hoch")
    uid_gering = _uid("ac8-gering")

    trip_hoch = _telegram_trip(f"trip-ac8-hoch-{uuid.uuid4().hex[:6]}")
    trip_hoch.alert_channel_thresholds = {"telegram": "HIGH"}

    trip_gering = _telegram_trip(f"trip-ac8-gering-{uuid.uuid4().hex[:6]}")
    trip_gering.alert_channel_thresholds = {"telegram": "LOW"}

    stub_hoch = _TelegramStub()
    stub_gering = _TelegramStub()
    try:
        _pin_telegram_stub(monkeypatch, stub_hoch)
        mails_hoch: list = []
        svc_hoch = TripAlertService(
            settings=_settings_email_and_telegram(), user_id=uid_hoch,
            throttle_hours=0,
            mail_sink=lambda subject, body: mails_hoch.append((subject, body)),
        )
        result_hoch = svc_hoch._send_alert(
            trip_hoch, [weather(1)], [_change(ChangeSeverity.MINOR)],
        )

        _pin_telegram_stub(monkeypatch, stub_gering)
        mails_gering: list = []
        svc_gering = TripAlertService(
            settings=_settings_email_and_telegram(), user_id=uid_gering,
            throttle_hours=0,
            mail_sink=lambda subject, body: mails_gering.append((subject, body)),
        )
        result_gering = svc_gering._send_alert(
            trip_gering, [weather(1)], [_change(ChangeSeverity.MINOR)],
        )
    finally:
        stub_hoch.stop()
        stub_gering.stop()

    assert not stub_hoch.sent, (
        "AC-8: Nutzer mit HOHER Telegram-Schwelle darf bei geringer "
        f"Dringlichkeit keinen Telegram-Alarm bekommen. Erhalten: "
        f"{stub_hoch.sent!r}"
    )
    assert stub_gering.sent, (
        "AC-8: Nutzer mit GERINGER (Startwert-)Telegram-Schwelle muss "
        "denselben Alarm weiterhin auf Telegram bekommen -- seine "
        f"Einstellung darf durch den anderen Nutzer NICHT beeinflusst "
        f"werden. Erhalten: {stub_gering.sent!r}"
    )
    assert "telegram" not in result_hoch.delivered_channels, (
        f"AC-8: Nutzer A: 'telegram' darf nicht in delivered_channels "
        f"stehen: {result_hoch.delivered_channels!r}"
    )
    assert "telegram" in result_gering.delivered_channels, (
        f"AC-8: Nutzer B: 'telegram' MUSS in delivered_channels stehen: "
        f"{result_gering.delivered_channels!r}"
    )


# ══════════════════════════════════ AC-12 ═════════════════════════════════


_SMS_TZ = ZoneInfo("Europe/Berlin")
_SMS_LAT, _SMS_LON = 43.7102, 7.2620


def _sms_segment(segment_id: int, *, alerts=None):
    """Echtes SegmentWeatherData fuer den SMS-Renderer — Vorbild
    ``test_sms_trip_unavailable_marker.py::_make_segment``."""
    from app.models import (
        ForecastDataPoint,
        ForecastMeta,
        GPXPoint,
        NormalizedTimeseries,
        Provider,
        SegmentWeatherData,
        SegmentWeatherSummary,
        ThunderLevel,
        TripSegment,
    )

    dp = ForecastDataPoint(
        ts=datetime(2026, 7, 11, 10, 0, tzinfo=timezone.utc),
        t2m_c=22.0, wind10m_kmh=15.0, gust_kmh=25.0, precip_1h_mm=0.0,
        pop_pct=10, cloud_total_pct=30, thunder_level=ThunderLevel.NONE,
        wind_chill_c=20.0, cape_jkg=100.0, visibility_m=20000.0,
    )
    seg = TripSegment(
        segment_id=segment_id,
        start_point=GPXPoint(lat=_SMS_LAT, lon=_SMS_LON, elevation_m=400.0),
        end_point=GPXPoint(
            lat=_SMS_LAT + 0.05, lon=_SMS_LON + 0.04, elevation_m=800.0,
        ),
        start_time=datetime(2026, 7, 11, 8, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 7, 11, 12, 0, tzinfo=timezone.utc),
        duration_hours=4.0, distance_km=8.0, ascent_m=400.0, descent_m=0.0,
    )
    meta = ForecastMeta(
        provider=Provider.OPENMETEO, model="arome_france",
        run=datetime(2026, 7, 11, 0, 0, tzinfo=timezone.utc),
        grid_res_km=1.3, interp="point_grid",
    )
    ts = NormalizedTimeseries(meta=meta, data=[dp])
    agg = SegmentWeatherSummary(
        temp_min_c=14.0, temp_max_c=24.0, temp_avg_c=19.0,
        wind_max_kmh=15.0, gust_max_kmh=25.0, precip_sum_mm=0.0,
        cloud_avg_pct=30, humidity_avg_pct=55,
        thunder_level_max=ThunderLevel.NONE, wind_chill_min_c=20.0,
    )
    return SegmentWeatherData(
        segment=seg, timeseries=ts, aggregated=agg,
        fetched_at=datetime.now(timezone.utc), provider="openmeteo",
        official_alerts=list(alerts or []),
    )


def test_ac12_kurznachricht_zeigt_gelbe_amtliche_warnung_bei_startschwelle():
    """AC-12.

    GIVEN ein Trip hat fuer den SMS-/Telegram-Kanal die Startschwelle
          'gering' unveraendert gelassen (== ab amtlicher Stufe 2, gelb).
    WHEN  sein reguläres Briefing eine amtliche Warnung genau dieser Stufe
          (2, gelb) enthaelt.
    THEN  erscheint diese Warnung jetzt im Kurznachrichten-Bericht des
          Trips -- vorher war der Eintrag dort leer.

    Heute (RED): ``official_alerts_to_sms_entries()`` filtert hart auf
    ``MIN_SMS_LEVEL = 3`` (orange/rot) -- Stufe 2 (gelb) erscheint nie im
    SMS-Trip-Report, unabhaengig von der (heute nicht existierenden)
    Kanal-Schwellen-Einstellung.
    """
    from output.renderers.sms_trip import SMSTripFormatter
    from services.official_alerts import OfficialAlert

    alert = OfficialAlert(
        source="test-vigilance", hazard="wind_gust", level=2,
        label="Windwarnung Stufe Gelb",
    )
    segment = _sms_segment(1, alerts=[alert])

    out = SMSTripFormatter().format_sms(
        [segment], max_length=160, tz=_SMS_TZ, report_type="evening",
        stage_name="Etappe 1",
    )

    assert "W:L" in out, (
        "AC-12: Beim Startwert 'gering' (Stufe 2, gelb) muss die amtliche "
        f"Warnung jetzt in der Trip-Kurznachricht erscheinen (Kuerzel 'W:L' "
        f"-- Wind-Symbol 'W', Stufenbuchstabe 'L' fuer Stufe 2). War: {out!r}"
    )


# ══════════════════════════════════ AC-1 ══════════════════════════════════
# Invariante, war bereits vor der Implementierung gruen (kein RED-Kriterium
# der urspruenglichen sechs) -- hier ergaenzt, weil sie in der Spec explizit
# als eigenes AC steht und noch von keinem Test bewacht wurde.


def test_ac1_ohne_gesetzte_schwelle_erreicht_die_meldung_alle_konfigurierten_kanaele(
    monkeypatch,
):
    """AC-1.

    GIVEN ein Trip hat fuer KEINEN Kanal eine Schwelle eingestellt
          (``trip.alert_channel_thresholds`` bleibt ``None``).
    WHEN  ein Alarm mit geringer Dringlichkeit ausgeloest wird.
    THEN  erreicht die Meldung GENAU die Kanaele, die sie auch vor dieser
          Aenderung erreicht haette -- kein Kanal wird stiller. Startwert
          'gering' <= 'gering' (Dringlichkeit) -> beide konfigurierten
          Kanaele bleiben erreichbar.
    """
    from services.trip_alert import TripAlertService

    uid = _uid("ac1")
    trip = _telegram_trip(f"trip-ac1-{uuid.uuid4().hex[:6]}")
    assert trip.alert_channel_thresholds is None, (
        "AC-1 Voraussetzung: keine Schwelle gesetzt"
    )

    stub = _TelegramStub()
    try:
        _pin_telegram_stub(monkeypatch, stub)
        mails: list = []
        svc = TripAlertService(
            settings=_settings_email_and_telegram(), user_id=uid, throttle_hours=0,
            mail_sink=lambda subject, body: mails.append((subject, body)),
        )
        result = svc._send_alert(
            trip, [weather(1)], [_change(ChangeSeverity.MINOR)],
        )
    finally:
        stub.stop()

    assert mails, "AC-1: E-Mail muss unveraendert ankommen"
    assert stub.sent, (
        "AC-1: Telegram hat KEINE Schwelle gesetzt -- eine gering-dringliche "
        f"Meldung muss unveraendert ankommen. Tatsaechlich gesendet: {stub.sent!r}"
    )
    assert set(result.delivered_channels) == {"email", "telegram"}, (
        f"AC-1: beide konfigurierten Kanaele muessen zugestellt sein, "
        f"gefunden: {result.delivered_channels!r}"
    )


# ══════════════════════════════════ AC-9 ══════════════════════════════════


def test_ac9_kachel_und_archiv_quelle_entries_unveraendert_bei_normalem_alarm(
    monkeypatch,
):
    """AC-9.

    GIVEN ein Alarm-Lauf, bei dem KEINE Kanal-Schwelle etwas unterdrueckt
          (Startwert 'gering' <= Dringlichkeit der Meldung).
    WHEN  die fuer Cockpit-Kachel und Archiv-Statistik massgebliche
          Protokoll-Quelle (``entries``, D4 aus #1459) danach gelesen wird.
    THEN  zeigt sie exakt EINEN Eintrag -- dieselbe Zahl wie vor dieser
          Aenderung. ``not_delivered`` bleibt leer (kein Vorfall).
    """
    from services.trip_alert import TripAlertService

    uid = _uid("ac9")
    trip = _ac4_trip(f"trip-ac9-{uuid.uuid4().hex[:6]}")
    # Keine Schwelle gesetzt -- trip.alert_channel_thresholds bleibt None.

    stub = _TelegramStub()
    try:
        _pin_telegram_stub(monkeypatch, stub)
        mails: list = []
        svc = TripAlertService(
            settings=_settings_email_and_telegram(), user_id=uid, throttle_hours=0,
            mail_sink=lambda subject, body: mails.append((subject, body)),
        )
        sent = svc.check_and_send_alerts(
            trip, [weather(1, gust_max_kmh=20.0)],
            fresh_weather=[weather(1, gust_max_kmh=45.0)],
        )
    finally:
        stub.stop()

    assert sent is True, (
        f"AC-9 Voraussetzung: ohne Schwellen-Wirkung muss der Alarm normal "
        f"zugestellt werden, erhalten sent={sent}"
    )
    log = read_log(uid)
    assert len(log["entries"]) == 1, (
        "AC-9: ein normaler, nicht durch die Schwelle betroffener Alarm muss "
        f"GENAU EINEN Eintrag unter 'entries' erzeugen (Cockpit-/Archiv-Quelle), "
        f"gefunden {len(log['entries'])}: {log['entries']!r}"
    )
    assert log["not_delivered"] == [], (
        "AC-9: kein Vorfall erwartet, gefunden: "
        f"{log['not_delivered']!r}"
    )


# ══════════════════════════════════ AC-11 ═════════════════════════════════


def test_ac11_ortsvergleich_alarm_unveraendert_trotz_trip_kanal_schwellen(monkeypatch):
    """AC-11.

    GIVEN ein Ortsvergleich ist von dieser Aenderung nicht betroffen -- der
          DEMSELBEN Nutzer gehoerende Trip hat gleichzeitig fuer Telegram
          eine erhoehte Schwelle ('HIGH') gesetzt.
    WHEN  im Ortsvergleich ein amtlicher Alarm mit geringer Dringlichkeit
          (Stufe 2, gelb) ausgeloest wird, mit allen drei Kanaelen (E-Mail,
          Telegram, SMS) eingeschaltet.
    THEN  erreichen alle drei Kanaele die Meldung unveraendert -- der
          Ortsvergleich kennt gar kein ``alert_channel_thresholds``-Feld und
          wird von der Trip-Einstellung desselben Nutzers nicht beeinflusst
          (Mandantentrennung UND Compare/Trip-Isolation).

    Wiederverwendet die Fixtures aus ``test_compare_official_alert.py``
    (dieselbe Testfamilie, dieselbe Kanal-Aufloesungs-Naht,
    ``CompareOfficialAlertService``).
    """
    from services.compare_official_alert import CompareOfficialAlertService
    from services.official_alerts import register_official_alert_source
    from services.trip_alert import TripAlertService
    from tests.tdd.test_compare_official_alert import (
        LAT_A,
        LON_A,
        _alert as _compare_alert,
        _clean_user,
        _FakeOfficialAlertSource,
        _location as _compare_location,
        _preset,
        _settings_all_channels,
        _sources_backup,
        _write_presets,
        _write_user_tier,
    )

    uid = _uid("ac11")
    _clean_user(uid)
    b, backup = _sources_backup()
    b._REGISTERED_SOURCES.clear()
    try:
        _write_user_tier(uid, "premium")
        save_location(_compare_location("loc-ac11", "Hermagor", LAT_A, LON_A), user_id=uid)
        _write_presets(uid, [_preset(
            "p-ac11", ["loc-ac11"], ["e@x.invalid"], send_telegram=True, send_sms=True,
        )])
        register_official_alert_source(
            _FakeOfficialAlertSource(LAT_A, LON_A, [_compare_alert(level=2)])
        )

        # Derselbe Nutzer hat einen TRIP mit erhoehter Telegram-Schwelle --
        # darf den Ortsvergleich-Versand NICHT beeinflussen.
        trip = _telegram_trip(f"trip-ac11-{uuid.uuid4().hex[:6]}")
        trip.alert_channel_thresholds = {"telegram": "HIGH"}
        trip_stub = _TelegramStub()
        _pin_telegram_stub(monkeypatch, trip_stub)
        TripAlertService(
            settings=_settings_email_and_telegram(), user_id=uid, throttle_hours=0,
            mail_sink=lambda subject, body: None,
        )._send_alert(trip, [weather(1)], [_change(ChangeSeverity.MINOR)])
        trip_stub.stop()
        assert not trip_stub.sent, (
            "AC-11 Voraussetzung: der Trip selbst bleibt bei HIGH-Schwelle "
            "auf Telegram stumm (Kontrollmessung fuer diesen Test)."
        )

        mail_calls, sms_calls, tg_calls = [], [], []
        svc = CompareOfficialAlertService(
            settings=_settings_all_channels(), user_id=uid,
            mail_sink=lambda subject, body: mail_calls.append(body),
            sms_sink=lambda text: sms_calls.append(text),
            telegram_sink=lambda text: tg_calls.append(text),
        )
        svc.check_all_compare_presets()

        assert len(mail_calls) == 1, f"AC-11: E-Mail (Compare): {mail_calls!r}"
        assert len(tg_calls) == 1, (
            "AC-11: Telegram (Compare) darf von der Trip-Kanal-Schwelle "
            f"desselben Nutzers NICHT beeinflusst werden: {tg_calls!r}"
        )
        assert len(sms_calls) == 1, f"AC-11: SMS (Compare): {sms_calls!r}"
    finally:
        b._REGISTERED_SOURCES.clear()
        b._REGISTERED_SOURCES.extend(backup)
        _clean_user(uid)


# ══════════════════════════════════ AC-13 ═════════════════════════════════


def test_ac13_gelbe_amtliche_warnung_loest_alarm_unveraendert_aus(monkeypatch):
    """AC-13.

    GIVEN ein Nutzer hat fuer einen Kanal keine Schwelle ueber 'gering'
          gesetzt (Startwert).
    WHEN  eine amtliche Warnung der niedrigsten wirksamen Stufe (2, gelb --
          Dringlichkeit 'LOW') einen Alarm ausloest.
    THEN  wird die Alarm-Meldung genauso verschickt wie vor dieser Aenderung
          -- 'LOW' erfuellt die Startschwelle 'LOW' auf jedem Kanal.

    Die amtliche Warnung wird -- wie im echten Versandpfad
    (``check_and_send_alerts``) -- zusammen mit einer Wetter-Delta-Aenderung
    in dieselbe Nachricht gebuendelt (Issue #1088); eine reine
    Standalone-Nachricht ohne jede Aenderung ist kein durch ``_send_alert()``
    abgedeckter Pfad (das ist ``_send_official_alert_only()``).
    """
    from services.official_alerts import OfficialAlert
    from services.trip_alert import TripAlertService

    uid = _uid("ac13")
    trip = _telegram_trip(f"trip-ac13-{uuid.uuid4().hex[:6]}")
    assert trip.alert_channel_thresholds is None, (
        "AC-13 Voraussetzung: keine Schwelle ueber 'gering' gesetzt"
    )
    alert = OfficialAlert(
        source="test-vigilance", hazard="wind_gust", level=2,
        label="Windwarnung Stufe Gelb",
    )

    stub = _TelegramStub()
    try:
        _pin_telegram_stub(monkeypatch, stub)
        mails: list = []
        svc = TripAlertService(
            settings=_settings_email_and_telegram(), user_id=uid, throttle_hours=0,
            mail_sink=lambda subject, body: mails.append((subject, body)),
        )
        result = svc._send_alert(
            trip, [weather(1)], [_change(ChangeSeverity.MINOR)],
            official_notices=[(alert, ["1"])],
        )
    finally:
        stub.stop()

    assert mails, "AC-13: E-Mail muss unveraendert ankommen"
    assert stub.sent, (
        "AC-13: eine gelbe amtliche Warnung (Stufe 2, Dringlichkeit LOW) "
        f"muss beim Startwert 'gering' unveraendert versendet werden. "
        f"Tatsaechlich gesendet: {stub.sent!r}"
    )
    assert set(result.delivered_channels) == {"email", "telegram"}, (
        f"AC-13: beide konfigurierten Kanaele muessen zugestellt sein, "
        f"gefunden: {result.delivered_channels!r}"
    )


# ═══════════════════════ F001 (Adversary Runde 2, M6) ═════════════════════
#
# check_and_send_alerts() reicht below_threshold_channels ueber eine
# Instanzvariablen-Bruecke (self._last_below_threshold_channels) an
# append_entry() weiter -- KEIN vorhandener Test lief bisher ueber DIESEN
# echten Δ-Wetter-Dispatch-Pfad mit TEILunterdrueckung (mind. ein Kanal
# erreicht, mind. einer schwellen-unterdrueckt). AC-5 konstruiert den
# Log-Eintrag von Hand (_seed()); AC-4 unterdrueckt ALLE Kanaele, wo das
# Ziel (entries/not_delivered) gar nicht vom Grund abhaengt. Mutation
# `below_threshold_channels=self._last_below_threshold_channels` ->
# `below_threshold_channels=None` in trip_alert.py liess bisher alle 11
# Tests unveraendert gruen -- dieser Test schliesst genau diese Luecke.


def test_f001_below_threshold_grund_im_echten_delta_wetter_dispatch(monkeypatch):
    """F001.

    GIVEN Telegram hat eine hohe Schwelle (HIGH), E-Mail bleibt beim
          Startwert (LOW) -- TEILunterdrueckung, nicht Totalausfall.
    WHEN  ein Alarm mit geringer Dringlichkeit ueber den ECHTEN
          Δ-Wetter-Dispatch-Pfad ``check_and_send_alerts()`` ausgeloest wird
          (NICHT ``_send_alert()`` direkt, NICHT von Hand konstruiert).
    THEN  der Protokoll-Eintrag traegt fuer telegram den Grund
          ``below_channel_threshold`` -- NICHT ``delivery_failed`` -- und
          das naechste Briefing zeigt im Wortlaut "unter Schwelle", nicht
          "Versand fehlgeschlagen".
    """
    from services.alert_briefing_anchor import record_briefing_sent
    from services.trip_alert import TripAlertService
    from tests.tdd.test_alert_undelivered_hint import (
        _hint_lines,
        _ReportRecorder,
        _run_trip_briefing,
    )

    uid = _uid("f001")
    trip = _ac4_trip(f"trip-f001-{uuid.uuid4().hex[:6]}")
    trip.alert_channel_thresholds = {"telegram": "HIGH"}  # email bleibt LOW

    anchor_zeit = datetime.now(timezone.utc) - timedelta(hours=6)
    record_briefing_sent(
        user_id=uid, entity_id=trip.id, entity_type="trip", at=anchor_zeit,
    )

    stub = _TelegramStub()
    try:
        _pin_telegram_stub(monkeypatch, stub)
        mails: list = []
        svc = TripAlertService(
            settings=_settings_email_and_telegram(), user_id=uid, throttle_hours=0,
            mail_sink=lambda subject, body: mails.append((subject, body)),
        )
        sent = svc.check_and_send_alerts(
            trip, [weather(1, gust_max_kmh=20.0)],
            fresh_weather=[weather(1, gust_max_kmh=45.0)],
        )
    finally:
        stub.stop()

    assert sent is True, (
        "F001 Voraussetzung: E-Mail bleibt zugestellt (Teilunterdrueckung, "
        f"kein Totalausfall), erhalten sent={sent}"
    )
    assert mails, "F001 Voraussetzung: E-Mail muss ankommen"
    assert not stub.sent, (
        "F001 Voraussetzung: Telegram muss durch die Schwelle unterdrueckt "
        f"sein, tatsaechlich gesendet: {stub.sent!r}"
    )

    log = read_log(uid)
    assert len(log["entries"]) == 1, (
        "F001: Teilunterdrueckung (mind. ein Kanal erreichbar) landet unter "
        f"'entries', gefunden: {log['entries']!r}"
    )
    not_sent = {item["channel"]: item["reason"] for item in log["entries"][0]["channels_not_sent"]}
    assert not_sent.get("telegram") == "below_channel_threshold", (
        "F001: telegram muss im Protokoll den Grund 'below_channel_threshold' "
        f"tragen -- NICHT 'delivery_failed'. Gefunden: {not_sent!r}"
    )

    recorder = _ReportRecorder()
    recorder.install(monkeypatch)
    report = _run_trip_briefing(recorder, uid, trip)
    zeilen = _hint_lines(report.email_plain)
    assert len(zeilen) == 1, (
        f"F001: genau eine Vorfall-Zeile im naechsten Briefing erwartet, "
        f"gefunden {zeilen!r}\n--- Klartext-Mail ---\n{report.email_plain}"
    )
    assert "unter Schwelle" in zeilen[0], (
        "F001: die Briefing-Zeile muss den WORTLAUT 'unter Schwelle' zeigen "
        f"(nicht den technischen Ersatzgrund 'Versand fehlgeschlagen'): "
        f"{zeilen[0]!r}"
    )
    assert "Versand fehlgeschlagen" not in zeilen[0], (
        f"F001: 'Versand fehlgeschlagen' waere die falsche technische "
        f"Fehlermeldung fuer eine bewusste Kanal-Schwelle: {zeilen[0]!r}"
    )


# ═══════════════════════ F002 (Adversary Runde 2, M13/M14) ════════════════
#
# Realer Produktionsweg: Go schreibt die Trip-JSON-Datei -> app.loader liest
# sie -> TripAlertService nutzt trip.alert_channel_thresholds. Alle bisherigen
# Tests dieser Suite konstruieren Trip(...)-Objekte DIREKT in Python und
# setzen das Attribut per Hand -- app.loader._parse_trip()/_trip_to_dict()
# laufen dabei NIE. Mutationen, die die Lese- ODER die Schreibzeile in
# app/loader.py entfernen, blieben deshalb bisher unbemerkt (M13, M14).


def _go_shaped_trip_dict(trip_id: str, thresholds: dict) -> dict:
    """Minimaler Trip-Dict GENAU in der Form, wie Go ihn ueber
    internal/handler/trip.go + internal/store schreiben wuerde: die JSON-Keys
    entsprechen 1:1 den `json:"..."`-Tags in internal/model/trip.go
    (``AlertChannelThresholdsConfig``: email/telegram/sms als String-Werte,
    fehlende Kanaele einfach nicht im Objekt -- ``omitempty``). KEIN
    Python-``Trip``-Objekt wird hier von Hand konstruiert."""
    return {
        "id": trip_id, "name": "F002 Go-Schreib-Test",
        "stages": [{
            "id": "S1", "name": "Tag 1", "date": "2026-07-15",
            "waypoints": [
                {"id": "G1", "name": "Start", "lat": LAT, "lon": LON, "elevation_m": 1000.0},
                {"id": "G2", "name": "Ziel", "lat": LAT + 0.1, "lon": LON + 0.1, "elevation_m": 1500.0},
            ],
        }],
        "display_config": {
            "trip_id": trip_id,
            "metrics": [{"metric_id": "gust", "enabled": True}],
            "metric_alert_levels": {"wind_gust": "standard"},
        },
        "report_config": {
            "trip_id": trip_id, "send_email": False, "send_telegram": False,
            "send_sms": False, "alert_on_changes": True,
        },
        "alert_channels": {"email": True, "telegram": True, "sms": False},
        "alert_channel_thresholds": thresholds,
        "alert_cooldown_minutes": 0,
        "official_alert_triggers_enabled": False,
    }


def test_f002_go_geschriebene_json_wird_gelesen_und_wirkt_im_alarm_dispatch(
    monkeypatch,
):
    """F002 (Lesen, M14).

    GIVEN eine Trip-JSON-Datei liegt EXAKT so vor, wie Go sie schreiben
          wuerde (Schluessel ``alert_channel_thresholds``, Werte als Strings
          ``"LOW"``/``"MODERATE"``/``"HIGH"``) -- KEIN Python-``Trip``-Objekt
          wird von Hand konstruiert.
    WHEN  ``app.loader.load_all_trips()`` (der ECHTE Produktions-Lesepfad)
          die Datei laedt UND darauf ein Alarm ueber ``_send_alert()``
          ausgeloest wird.
    THEN  die geladene Schwelle WIRKT tatsaechlich im Versand: Telegram
          (HIGH) bleibt bei geringer Dringlichkeit stumm, E-Mail
          (Startwert LOW, im Dict gar nicht gesetzt) kommt an.
    """
    from app.loader import get_briefings_dir, load_all_trips
    from services.trip_alert import TripAlertService

    uid = _uid("f002-read")
    trip_id = f"trip-f002-read-{uuid.uuid4().hex[:6]}"
    briefings_dir = get_briefings_dir(uid)
    briefings_dir.mkdir(parents=True, exist_ok=True)
    raw = _go_shaped_trip_dict(trip_id, {"telegram": "HIGH"})
    (briefings_dir / f"{trip_id}.json").write_text(json.dumps(raw), encoding="utf-8")

    loaded = load_all_trips(user_id=uid)
    assert len(loaded) == 1, (
        f"F002 Voraussetzung: genau ein Trip aus der Go-geschriebenen JSON "
        f"geladen, gefunden {loaded!r}"
    )
    trip = loaded[0]
    assert trip.alert_channel_thresholds == {"telegram": "HIGH"}, (
        "F002 (Lesen): app.loader._parse_trip() muss 'alert_channel_thresholds' "
        f"aus der Go-geschriebenen JSON lesen, gefunden: "
        f"{trip.alert_channel_thresholds!r}"
    )

    stub = _TelegramStub()
    try:
        _pin_telegram_stub(monkeypatch, stub)
        mails: list = []
        svc = TripAlertService(
            settings=_settings_email_and_telegram(), user_id=uid, throttle_hours=0,
            mail_sink=lambda subject, body: mails.append((subject, body)),
        )
        result = svc._send_alert(trip, [weather(1)], [_change(ChangeSeverity.MINOR)])
    finally:
        stub.stop()

    assert mails, "F002: E-Mail muss unveraendert ankommen (Startwert 'gering')"
    assert not stub.sent, (
        "F002: die aus der Go-geschriebenen JSON geladene HIGH-Schwelle muss "
        f"Telegram tatsaechlich unterdruecken -- sonst ist das Feld live "
        f"wirkungslos, obwohl alle Unit-Tests gruen sind. Gesendet: {stub.sent!r}"
    )
    assert "telegram" not in result.delivered_channels, (
        f"F002: 'telegram' darf nicht in delivered_channels stehen: "
        f"{result.delivered_channels!r}"
    )


def test_f002_python_seitiges_speichern_erhaelt_die_schwelle_ohne_datenverlust():
    """F002 (Schreiben, M13).

    GIVEN ein Trip traegt bereits eine gesetzte Kanal-Schwelle.
    WHEN  ein PYTHON-seitiger Resave laeuft -- echte Aufrufer:
          ``trip_command_processor.py``, ``gpx_processing.py``,
          ``trip_report_scheduler.py`` -- hier ueber den ECHTEN
          ``app.loader.save_trip()``-Pfad reproduziert (kein von Hand
          gebauter Dict-Roundtrip).
    THEN  bleibt die Schwelle nach dem Speichern UND einem erneuten Laden
          ueber ``load_all_trips()`` unveraendert -- kein stiller
          Datenverlust (BUG-DATALOSS-GR221 / #102-Klasse, CLAUDE.md
          "Daten-Schema-Reworks").
    """
    from app.loader import load_all_trips, save_trip

    uid = _uid("f002-write")
    trip = _telegram_trip(f"trip-f002-write-{uuid.uuid4().hex[:6]}")
    trip.alert_channel_thresholds = {"email": "MODERATE", "telegram": "HIGH"}

    save_trip(trip, user_id=uid)
    reloaded = load_all_trips(user_id=uid)
    assert len(reloaded) == 1, (
        f"F002 Voraussetzung: genau ein Trip nach dem Speichern geladen, "
        f"gefunden {reloaded!r}"
    )
    assert reloaded[0].alert_channel_thresholds == {
        "email": "MODERATE", "telegram": "HIGH",
    }, (
        "F002 (Schreiben): app.loader._trip_to_dict()/save_trip() muss "
        "'alert_channel_thresholds' persistieren -- sonst geht eine ueber "
        "die Oberflaeche gesetzte Kanal-Schwelle beim naechsten "
        f"Python-seitigen Resave (z.B. GPX-Neu-Upload) still verloren. "
        f"Gefunden: {reloaded[0].alert_channel_thresholds!r}"
    )


# ═══════════════ Dritte Naht-Stelle: eigenstaendiger amtlicher Alarm ══════
#
# split_by_threshold() wirkt an DREI Stellen, nicht zwei: _send_alert()
# (AC-2), die Radar-Inline-Kopie (AC-3) UND _send_official_alert_only()
# (:1155) -- der eigenstaendige Pfad fuer eine EINZELN auftretende amtliche
# Warnung OHNE begleitende Wetter-Delta-Aenderung, erreicht ueber
# check_official_alert_triggers(). AC-13 deckt bewusst nur den GEBUENDELTEN
# Pfad ab (amtliche Warnung + Δ-Wetter in derselben Nachricht, s. dortiger
# Docstring) -- der Standalone-Pfad war bislang unbewacht.


def test_einzeln_auftretende_amtliche_warnung_ohne_wetter_delta_respektiert_kanal_schwelle(
    monkeypatch,
):
    """Dritte Naht-Stelle: ``_send_official_alert_only()``.

    GIVEN ein Nutzer hat fuer Telegram eine erhoehte Schwelle (HIGH)
          eingestellt, E-Mail bleibt beim Startwert (LOW).
    WHEN  eine EINZELN auftretende amtliche Warnung mit geringer
          Dringlichkeit (Stufe 2, gelb -> LOW) OHNE begleitende
          Wetter-Delta-Aenderung ueber den echten Trigger-Erkennungspfad
          ``check_official_alert_triggers()`` erkannt und ueber
          ``_send_official_alert_only()`` verschickt wird -- GENAU der Pfad,
          den ``check_all_trips()`` bei fehlendem Wetter-Delta-Alarm nimmt
          (Issue #1088).
    THEN  erreicht die Meldung Telegram NICHT, E-Mail weiterhin.
    """
    from services.official_alerts import OfficialAlert, register_official_alert_source
    from services.trip_alert import TripAlertService
    from tests.tdd.test_issue_1088_official_alert_triggers import (
        LAT as LAT_1088,
        LON as LON_1088,
        _CountingOfficialAlertSource,
        _clean_user as _clean_1088_user,
        _data,
        _registered_sources_backup,
        _save_cached,
    )

    uid = _uid("standalone-official")
    _clean_1088_user(uid)
    oa_base, backup = _registered_sources_backup()
    oa_base._REGISTERED_SOURCES.clear()
    try:
        stage = Stage(
            id="T1", name="Tag 1", date=date.today(),
            waypoints=[
                Waypoint(id="G1", name="Start", lat=LAT_1088, lon=LON_1088, elevation_m=1000.0),
            ],
        )
        trip = Trip(
            id=f"trip-standalone-official-{uuid.uuid4().hex[:6]}", name="Standalone-Official-Trip",
            stages=[stage], official_warnings=None,
        )
        trip.report_config = TripReportConfig(
            trip_id=trip.id, send_email=False, send_telegram=False, send_sms=False,
        )
        trip.alert_channels = {"email": True, "telegram": True, "sms": False}
        trip.alert_channel_thresholds = {"telegram": "HIGH"}  # email bleibt LOW
        trip.alert_cooldown_minutes = 0

        _save_cached(uid, trip.id, [_data(1, precip_sum_mm=2.0)])

        alert = OfficialAlert(
            source="test-standalone-official", hazard="thunderstorm", level=2,
            label="Gelbe Warnung, kein begleitendes Wetter-Delta",
        )
        source = _CountingOfficialAlertSource(LAT_1088, LON_1088, alert)
        register_official_alert_source(source)

        stub = _TelegramStub()
        try:
            _pin_telegram_stub(monkeypatch, stub)
            mails: list = []
            svc = TripAlertService(
                settings=_settings_email_and_telegram(), user_id=uid, throttle_hours=0,
                mail_sink=lambda subject, body: mails.append((subject, body)),
            )
            official_notices = svc.check_official_alert_triggers(trip)
            assert source.fetch_calls >= 1, (
                "Voraussetzung: check_official_alert_triggers() muss die "
                "registrierte Fake-Quelle tatsaechlich abfragen"
            )
            assert official_notices, (
                "Voraussetzung: die gelbe Warnung muss als neu/eskaliert "
                f"erkannt werden, erhalten: {official_notices!r}"
            )
            sent = svc._send_official_alert_only(trip, official_notices)
        finally:
            stub.stop()
    finally:
        oa_base._REGISTERED_SOURCES.clear()
        oa_base._REGISTERED_SOURCES.extend(backup)
        _clean_1088_user(uid)

    assert sent is True, (
        f"Voraussetzung: mindestens ein Kanal (E-Mail) muss erreichbar "
        f"sein, erhalten sent={sent}"
    )
    assert mails, "E-Mail (Startwert 'gering') muss unveraendert ankommen"
    assert not stub.sent, (
        "Der eigenstaendige amtliche Alarm (ohne Wetter-Delta) muss dieselbe "
        f"Kanal-Schwelle respektieren wie der gebuendelte Pfad -- Telegram "
        f"hat HIGH, die Warnung ist nur LOW-dringlich. Tatsaechlich "
        f"gesendet: {stub.sent!r}"
    )

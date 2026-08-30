"""TDD RED — Issue #2122: die Etappen-Nummer der Tour als Praefix in jeder
Alarm-Kurzform (SMS, Premium-SMS, Telegram-Kurzform) der Trip-Flaeche.

SPEC:    docs/specs/modules/fix_2122_etappen_praefix_kurzform.md (AC-1..AC-12)
KONTEXT: docs/context/fix_2122_etappen_praefix_kurzform.md

RED-VERTRAG: `stage_number` existiert heute auf KEINEM der vier
Ereignis-Datenmodelle (`AlertEvent`, `OnsetEvent`, `CorridorEvent`,
`OnsetShiftEvent`, `RadarAlertRequest`), der Kopfbau in `render.py` kennt kein
Praefix. Jede Konstruktion/jeder Aufruf mit diesem Schluesselwort schlaegt mit
`TypeError` fehl; wo der Text ohne das Schluesselwort auskommt (AC-8/AC-9),
schlaegt stattdessen eine Text-Assertion fehl (der Bestand traegt kein
Praefix). Beides IST der ROT-Zustand.

TESTPOLITIK (CLAUDE.md, Kern-Schicht): kein `Mock()`/`patch()`/`MagicMock`.
Als Naht dienen echte lokale HTTP-Stubs (seven.io- und Telegram-Bot-API,
Loopback-Socket, 1:1 das Muster aus `test_alert_sms_location_positions.py`
und `test_telegram_kurzstil_trip_alert.py`) sowie echte `Trip`/`Stage`/
`AlertEvent`-DTOs und echte Produktions-Projektionsfunktionen
(`to_alert_message`, `to_multi_point_alert_message`, `to_corridor_events`).
Kein Netz, kein echter Versand — jeder Kanal ist entweder ein lokaler Stub
oder eine reine Aufzeichnungs-Senke.

Pfadregel: `WeatherSnapshotService`/`get_data_dir()` loesen `user_id` relativ
zum Arbeitsverzeichnis auf (nicht ueber einen festen Hauptrepo-Pfad); jeder
Test, der schreibt, nutzt eine per-Testlauf eindeutige `user_id` und raeumt im
`finally` auf.

AC-12 (Mutations-Gegenprobe) hat bewusst KEINEN eigenen Testfall in dieser
Datei: sie verlangt eine String-Ersetzungs-Mutation an bereits existierendem
Produktivcode (Spec: "String-Ersetzung mit externer Sicherungskopie") — das
ist eine Adversary-Aktivitaet der GREEN-Phase (`/50-implement`), nicht der
RED-Phase, in der `_stage_prefix` noch gar nicht existiert. Die zwoelf
Verhaltens-Tests dieser Datei SIND die Zusicherungen, gegen die die
Mutations-Gegenprobe spaeter antritt.
"""
from __future__ import annotations

import http.server
import json
import socket
import threading
import urllib.parse
import uuid
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from app.config import Settings
from app.models import (
    ChangeSeverity, GPXPoint, SegmentWeatherData, SegmentWeatherSummary,
    TripSegment, WeatherChange,
)
from app.trip import Stage, Trip, Waypoint
from output.renderers.alert.model import AlertEvent, AlertMessage
from output.renderers.alert.project import to_multi_point_alert_message
from output.renderers.alert.render import render_sms
from services.corridor_threshold import CorridorHit
from services.notification_service import NotificationService, RadarAlertRequest
from services.official_alerts.models import OfficialAlert
from services.weather_snapshot import WeatherSnapshotService

UTC = timezone.utc
TZ = ZoneInfo("Europe/Vienna")


# ---------------------------------------------------------------------------
# Echte lokale Aufzeichnungs-Server (kein Mock, kein Netz)
# ---------------------------------------------------------------------------

def _free_port() -> int:
    s = socket.socket()
    s.bind(("", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class _SevenIoStub:
    """Lokaler HTTP-Stub fuer die seven.io-API — nimmt SMS UND Premium-SMS
    entgegen (1:1 das Muster aus `test_alert_addendum_sms.py::_SevenIoStub`).
    """

    def __init__(self) -> None:
        self.received: list[dict] = []
        received = self.received

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):  # noqa: N802
                length = int(self.headers.get("Content-Length", 0))
                data = urllib.parse.parse_qs(self.rfile.read(length).decode())
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


class _TelegramStub:
    """Lokaler HTTP-Stub fuer die Telegram-Bot-API (1:1 das Muster aus
    `test_telegram_kurzstil_trip_alert.py::_TelegramStub`)."""

    def __init__(self) -> None:
        self.sent: list[dict] = []
        sent = self.sent
        counter = {"mid": 3000}

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):  # noqa: N802
                length = int(self.headers.get("Content-Length", 0))
                try:
                    payload = json.loads(self.rfile.read(length).decode())
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


def _clean_user(user_id: str) -> None:
    import shutil

    from app.loader import get_data_dir

    d = get_data_dir(user_id)
    if d.exists():
        shutil.rmtree(d)


# ---------------------------------------------------------------------------
# Settings — jedes versandrelevante Feld ausdruecklich gesetzt (Issue #1477)
# ---------------------------------------------------------------------------

def _settings_sms_only(sms_port: int) -> Settings:
    return Settings(
        smtp_host="", smtp_user="", smtp_pass="", mail_to="",
        telegram_bot_token="", telegram_chat_id="",
        sms_gateway_url=f"http://127.0.0.1:{sms_port}/api/sms",
        seven_api_key="tdd-2122-stub-key", seven_sandbox_key="tdd-2122-stub-key",
        sms_to="+49000000000", sms_from=None,
    )


def _settings_all_short_channels(sms_port: int) -> Settings:
    """SMS + Premium-SMS (beide ueber denselben seven.io-Stub) + Telegram.

    `telegram_test_chat_id` MUSS explizit auf denselben Wert wie
    `telegram_chat_id` gesetzt werden (Issue #1477-Kommentar oben) --
    ohne ihn greift die Herkunftssperre (#1476,
    `TelegramOutput._guard_code_origin`) in JEDER Umgebung, die
    `running_origin()` als "test" erkennt (z.B. CI-Checkouts), findet
    keine konfigurierte Test-Chat-ID und bricht den Versand mit
    `OutputConfigError` ab -- lokal (Worktree, andere Herkunft) unsichtbar,
    in CI ein stiller `count == 0` (Zustellbilanz statt Entscheidung).
    """
    return Settings(
        smtp_host="", smtp_user="", smtp_pass="", mail_to="",
        telegram_bot_token="tdd-2122-bot-token", telegram_chat_id="99999",
        telegram_test_chat_id="99999",
        sms_gateway_url=f"http://127.0.0.1:{sms_port}/api/sms",
        seven_api_key="tdd-2122-stub-key", seven_sandbox_key="tdd-2122-stub-key",
        sms_to="+49000000000", sms_from=None,
        premium_sms_reply_to="+4915799912345",
        premium_sms_reply_at=datetime.now(UTC),
    )


# ---------------------------------------------------------------------------
# Fixture-Daten (echte DTOs, kein Netz)
# ---------------------------------------------------------------------------

def _multi_stage_trip(trip_id: str = "tdd-2122-trip", *, today_index: int = 2, n: int = 5) -> Trip:
    """Trip mit `n` Etappen, deren Daten SYMMETRISCH um `date.today()` liegen
    (relative Offsets, keine absoluten Kalenderdaten — laeuft an jedem
    Kalendertag gleich). `date.today()` traegt die Etappe an Listenposition
    `today_index` (0-basiert): mit den Defaults ist 'heute' die DRITTE von
    fuenf Etappen (`stage_number == 3`) — bewusst NICHT die erste, damit eine
    kaputte Ableitung (z.B. immer 1 oder immer die Listenposition ohne
    Sortierung) nicht zufaellig durchrutscht.
    """
    today = date.today()
    stages = []
    for i in range(n):
        d = today + timedelta(days=i - today_index)
        stages.append(Stage(
            id=f"ST{i + 1}", name=f"Etappe {i + 1}", date=d,
            # Haertung gegen tests/tdd/test_fixture_wallclock_ratchet.py
            # (Anti-Muster #1709): ein Wanduhr-Etappendatum (`date.today()`
            # o.) mit >=2 Wegpunkten OHNE jede Ankunftszeit ist verwundbar
            # gegen Mitternachts-Rollover. Diese Trips lesen keine
            # Ankunftszeiten (Stage-Position genuegt fuer die Etappen-
            # Nummer) -- ein fester `start_time` genuegt zur Immunisierung,
            # ohne echte Zeitfenster zu erfinden.
            start_time=time(8, 0),
            waypoints=[
                Waypoint(id=f"W{i + 1}a", name="Start", lat=47.0 + i * 0.01,
                          lon=11.0 + i * 0.01, elevation_m=1000),
                Waypoint(id=f"W{i + 1}b", name="Ziel", lat=47.05 + i * 0.01,
                          lon=11.05 + i * 0.01, elevation_m=1500),
            ],
        ))
    return Trip(id=trip_id, name="TDD 2122 Trip", stages=stages)


def _trip_segment(segment_id="1") -> TripSegment:
    start = datetime(2026, 5, 1, 8, 0, tzinfo=UTC)
    end = datetime(2026, 5, 1, 12, 0, tzinfo=UTC)
    return TripSegment(
        segment_id=segment_id,
        start_point=GPXPoint(lat=47.0, lon=11.0, elevation_m=1000, distance_from_start_km=12.0),
        end_point=GPXPoint(lat=47.1, lon=11.1, elevation_m=1500, distance_from_start_km=18.0),
        start_time=start, end_time=end, duration_hours=4.0, distance_km=6.0,
        ascent_m=500, descent_m=0,
    )


def _segment_weather_data(segment_id="1") -> SegmentWeatherData:
    return SegmentWeatherData(
        segment=_trip_segment(segment_id), timeseries=None,
        aggregated=SegmentWeatherSummary(),
        fetched_at=datetime.now(UTC), provider="openmeteo",
    )


def _change(segment_id="1", new_value: float = 30.0) -> WeatherChange:
    return WeatherChange(
        metric="precip_sum_mm", old_value=2.0, new_value=new_value,
        delta=new_value - 2.0, threshold=5.0, severity=ChangeSeverity.MODERATE,
        direction="increase", segment_id=segment_id,
    )


def _gpx(lat: float, lon: float) -> GPXPoint:
    return GPXPoint(lat=lat, lon=lon, elevation_m=500.0)


def _gust_event(km_from: float, km_to: float, segment_id: str, occurred_at: str,
                 **extra) -> AlertEvent:
    """Ein `AlertEvent`, DIREKT konstruiert (kein `to_alert_message`-Umweg) —
    fuer Tests, die den Renderer isoliert pruefen (AC-7/AC-8/AC-9/AC-10)."""
    return AlertEvent(
        metric_id="gust", value_from=30.0, value_to=80.0, threshold=20.0,
        cmp="über", occurred_at=occurred_at, km_from=km_from, km_to=km_to,
        segment_id=segment_id, **extra,
    )


# ═══════════════════════ AC-1 — Naht-Test (Abweichungsalarm) ════════════════

def test_ac1_deviation_alert_prefix_derived_from_trip_stage_position():
    """AC-1: der Abweichungs-Alarm traegt das Etappen-Praefix der HEUTIGEN
    Etappe, ABGELEITET aus dem echten Trip ueber den echten Ausloesepfad
    (`NotificationService.send_deviation_alert`) — die Zahl 3 steht NIRGENDS
    als Literal im Testaufbau, sie ergibt sich allein aus der Position von
    `date.today()` unter den 5 Etappen-Daten von `_multi_stage_trip()`.
    """
    trip = _multi_stage_trip()
    stub = _SevenIoStub()
    try:
        svc = NotificationService(
            settings=_settings_sms_only(stub.port),
            user_id=f"tdd-2122-ac1-{uuid.uuid4().hex[:6]}",
        )
        svc.send_deviation_alert(
            trip=trip, weather=[_segment_weather_data()], changes=[_change()],
            effective_channels={"sms"},
        )
        assert len(stub.received) == 1, (
            f"Setup-Kontrolle: erwartet genau eine SMS, erhalten: {stub.received!r}"
        )
        text = stub.received[0]["text"]
        assert text.startswith("S3 "), (
            "AC-1: der Abweichungs-Alarm muss mit dem Praefix der heutigen "
            "Etappe beginnen (3. von 5 Etappen, aus dem Trip abgeleitet, "
            f"nicht literal gesetzt). Gemessen: {text!r}"
        )
        # Nachweis, dass NUR das Praefix neu ist: der Rest bleibt der
        # gemessene Bestandstext des Abweichungs-Alarms. GEMESSEN (nicht aus
        # einem Nachbartest abgeschrieben) am 2026-08-30 ueber denselben
        # Ausloesepfad mit einem Trip OHNE Etappe an `date.today()`
        # (`_stage_number_for_date()` liefert dann `None` -> kein Praefix):
        # `'Seg 1: R2->30'`. Die fruehere Erwartung `'Segment 1: R2->30'`
        # (volles Wort) war seit Commit e9885f08 (#1948 S5, 2026-08-20 --
        # `_ascii_alert_location()` faltet "Segment " -> "Seg " im SMS-Kopf)
        # veraltet; der gleichlautende Bestandstest
        # `test_alert_sms_location_positions.py::test_regression_trip_
        # deviation_alert_sms_text_unchanged` traegt denselben stalen String
        # und ist separat zu buchen (nicht Teil dieses Tickets).
        assert text[len("S3 "):] == "Seg 1: R2->30", (
            f"AC-1: hinter dem Praefix muss der unveraenderte (gemessene) "
            f"Bestandstext stehen, gemessen: {text!r}"
        )
    finally:
        stub.stop()


# ═══════════════════════ AC-2 — Radar traegt dasselbe Praefix ═══════════════

def test_ac2_radar_alert_shares_same_stage_prefix_as_deviation_alert():
    """AC-2: ein Radar-/Nowcast-Alarm DERSELBEN (heutigen) Etappe traegt
    dasselbe Etappen-Praefix wie der Abweichungs-Alarm."""
    trip = _multi_stage_trip()
    stub = _SevenIoStub()
    try:
        uid = f"tdd-2122-ac2-{uuid.uuid4().hex[:6]}"
        svc = NotificationService(settings=_settings_sms_only(stub.port), user_id=uid)
        svc.send_deviation_alert(
            trip=trip, weather=[_segment_weather_data()], changes=[_change()],
            effective_channels={"sms"},
        )
        try:
            req = RadarAlertRequest(
                onset_minutes=12, onset_time="14:35", km_from=5.0, km_to=18.0,
                is_convective=False, intensity_label="leichter Regen",
                source_label="Radar (DWD)", tz=TZ, segment_date=date.today(),
            )
        except TypeError as exc:
            raise AssertionError(
                "RadarAlertRequest traegt kein additives 'segment_date'-Feld "
                f"(Spec, notification_service.py). Ursprungsfehler: {exc}"
            ) from exc
        svc.send_radar_alert(
            trip=trip, request=req, source="Radar (DWD)",
            cooldown_display="2 Stunden", effective_channels={"sms"},
        )
        assert len(stub.received) == 2, (
            f"Setup-Kontrolle: erwartet je eine SMS je Alarm, erhalten: {stub.received!r}"
        )
        prefix_dev = stub.received[0]["text"].split(" ", 1)[0]
        prefix_radar = stub.received[1]["text"].split(" ", 1)[0]
        assert prefix_dev == "S3", f"Abweichungs-Alarm traegt nicht 'S3': {stub.received[0]['text']!r}"
        assert prefix_radar == "S3", (
            f"AC-2: Radar-Alarm derselben Etappe muss ebenfalls 'S3' tragen, "
            f"gemessen: {stub.received[1]['text']!r}"
        )
    finally:
        stub.stop()


# ═══════════════════════ AC-3 — Onset-Shift (Beginn-Verschiebung) ═══════════

def test_ac3_onset_shift_alert_carries_stage_prefix():
    """AC-3: eine Beginn-Verschiebung (`OnsetShiftEvent`, ueber den echten
    Onset-Zweig von `to_alert_message`) traegt das Etappen-Praefix."""
    trip = _multi_stage_trip()
    now = datetime.now(UTC)
    later = now + timedelta(hours=2)
    change = WeatherChange(
        metric="thunder_onset_utc", old_value=now.timestamp(),
        new_value=later.timestamp(), delta=(later - now).total_seconds(),
        threshold=1800.0, severity=ChangeSeverity.MODERATE, direction="increase",
        segment_id="1", occurred_at=later,
    )
    stub = _SevenIoStub()
    try:
        svc = NotificationService(
            settings=_settings_sms_only(stub.port),
            user_id=f"tdd-2122-ac3-{uuid.uuid4().hex[:6]}",
        )
        svc.send_deviation_alert(
            trip=trip, weather=[_segment_weather_data()], changes=[change],
            effective_channels={"sms"},
        )
        assert len(stub.received) == 1
        text = stub.received[0]["text"]
        assert text.startswith("S3 "), (
            f"AC-3: die Beginn-Verschiebung muss das Etappen-Praefix tragen, "
            f"gemessen: {text!r}"
        )
    finally:
        stub.stop()


# ═══════════════════════ AC-4 — Korridor (Schwellen-Treffer) ════════════════

def test_ac4_corridor_alert_carries_stage_prefix():
    """AC-4: ein reiner Schwellen-Treffer (`CorridorEvent`, ueber
    `to_corridor_events`/`corridor_hits`) traegt das Etappen-Praefix VOR der
    Ortsangabe. Der Korridor-Kopf traegt (anders als der Δ-Kopf) zusaetzlich
    den Trip-Namen (`_render_sms_corridor_only`, `render.py:1613-1615`) — die
    Spec verlangt nur "vor der Ortsangabe" (AC-4-Wortlaut), nicht zwingend am
    Textanfang. Geprueft wird deshalb die relative Position ('S3' VOR der
    Ortsangabe 'Seg 1:'), nicht `startswith`.
    """
    trip = _multi_stage_trip()
    hit = CorridorHit(
        metric="wind_gust", value=90.0, bound=70.0, direction="above",
        segment_id="1", occurred_at=datetime.now(UTC),
    )
    stub = _SevenIoStub()
    try:
        svc = NotificationService(
            settings=_settings_sms_only(stub.port),
            user_id=f"tdd-2122-ac4-{uuid.uuid4().hex[:6]}",
        )
        svc.send_deviation_alert(
            trip=trip, weather=[_segment_weather_data()], changes=[],
            corridor_hits=[hit], effective_channels={"sms"},
        )
        assert len(stub.received) == 1
        text = stub.received[0]["text"]
        assert "S3" in text and "Seg 1:" in text, (
            f"AC-4: der Korridor-Alarm muss das Etappen-Praefix 'S3' UND die "
            f"gewohnte Ortsangabe 'Seg 1:' tragen, gemessen: {text!r}"
        )
        assert text.index("S3") < text.index("Seg 1:"), (
            "AC-4: 'S3' muss VOR der Ortsangabe 'Seg 1:' stehen, gemessen: "
            f"{text!r}"
        )
    finally:
        stub.stop()


# ═══════════════════════ AC-5 — Amtliche Warnung ════════════════════════════

def test_ac5_official_alert_carries_stage_prefix_from_rolling_anchor():
    """AC-5: eine amtliche Warnung ueber `send_official_alert` traegt das
    Etappen-Praefix des Tages, dem der TATSAECHLICH verwendete rollierende
    Anker entstammt (`WeatherSnapshotService.alarm_anchor_target_date`) —
    hier der heutige Tag, ueber einen echten gespeicherten Anker."""
    trip = _multi_stage_trip()
    uid = f"tdd-2122-ac5-{uuid.uuid4().hex[:6]}"
    _clean_user(uid)
    stub = _SevenIoStub()
    try:
        weather = [_segment_weather_data()]
        snap_svc = WeatherSnapshotService(user_id=uid)
        # Anker fuer mehrere plausible Kanalnamen hinterlegen — welchen genau
        # `send_official_alert` liest, legt die Implementierung fest (Spec
        # nennt nur "des tatsaechlich verwendeten Ankers").
        for channel in ("sms", "email", "telegram", "premium_sms"):
            snap_svc.save_alarm_anchor(trip.id, date.today(), weather, channel)

        alert = OfficialAlert(
            source="geosphere_warn", hazard="thunderstorm", level=2,
            label="Gewitter", valid_from=datetime.now(UTC),
            valid_to=datetime.now(UTC) + timedelta(hours=3),
            region_label="Test-Region",
        )
        svc = NotificationService(settings=_settings_sms_only(stub.port), user_id=uid)
        svc.send_official_alert(
            trip=trip, notices=[(alert, ["1"])], effective_channels={"sms"},
        )
        assert len(stub.received) == 1, (
            f"Setup-Kontrolle: erwartet genau eine SMS, erhalten: {stub.received!r}"
        )
        text = stub.received[0]["text"]
        assert text.startswith("S3 "), (
            "AC-5: die amtliche Warnung muss mit dem Etappen-Praefix des "
            f"verwendeten Ankertags beginnen, gemessen: {text!r}"
        )
    finally:
        stub.stop()
        _clean_user(uid)


# ═══════════════════════ AC-6 — Radar nennt das Datum des Segments ══════════

def test_ac6_radar_alert_uses_segment_date_not_wall_clock_today():
    """AC-6: ein Radar-Alarm, dessen Segment aus der Nacht des VORTAGS stammt,
    nennt die Etappe des Vortags — nicht die von heute. Gegenprobe im selben
    Test: derselbe Trip, aber `segment_date=today`, nennt die heutige Etappe.
    """
    trip = _multi_stage_trip()  # heute = 3. Etappe, Vortag = 2. Etappe
    vortag = date.today() - timedelta(days=1)
    stub = _SevenIoStub()
    try:
        uid = f"tdd-2122-ac6-{uuid.uuid4().hex[:6]}"
        svc = NotificationService(settings=_settings_sms_only(stub.port), user_id=uid)

        def _req(segment_date):
            try:
                return RadarAlertRequest(
                    onset_minutes=12, onset_time="14:35", km_from=5.0, km_to=18.0,
                    is_convective=False, intensity_label="leichter Regen",
                    source_label="Radar (DWD)", tz=TZ, segment_date=segment_date,
                )
            except TypeError as exc:
                raise AssertionError(
                    "RadarAlertRequest traegt kein additives 'segment_date'-Feld. "
                    f"Ursprungsfehler: {exc}"
                ) from exc

        svc.send_radar_alert(
            trip=trip, request=_req(vortag), source="Radar (DWD)",
            cooldown_display="2 Stunden", effective_channels={"sms"},
        )
        svc.send_radar_alert(
            trip=trip, request=_req(date.today()), source="Radar (DWD)",
            cooldown_display="2 Stunden", effective_channels={"sms"},
        )
        assert len(stub.received) == 2, (
            f"Setup-Kontrolle: erwartet zwei SMS, erhalten: {stub.received!r}"
        )
        text_vortag, text_today = stub.received[0]["text"], stub.received[1]["text"]
        assert text_vortag.startswith("S2 "), (
            "AC-6: ein Radar-Alarm mit Segment-Datum = Vortag muss die "
            f"Vortags-Etappe (S2) nennen, gemessen: {text_vortag!r}"
        )
        assert text_today.startswith("S3 "), (
            "AC-6 Gegenprobe: derselbe Trip mit Segment-Datum = heute muss "
            f"die heutige Etappe (S3) nennen, gemessen: {text_today!r}"
        )
    finally:
        stub.stop()


# ═══════════════════════ AC-7 — Aggregation zweier Etappen ══════════════════

def test_ac7_message_spanning_two_stages_shows_range_then_list():
    """AC-7: Bausteine zweier Etappen in EINER Nachricht — benachbart wird
    als Bereich (`S5-6`), nicht benachbart als Aufzaehlung (`S5,7`)
    dargestellt; nie eine einzelne (falsche) Etappe."""
    try:
        e1 = _gust_event(1.0, 2.0, "1", "11:00", stage_number=5)
        e2 = _gust_event(3.0, 4.0, "2", "11:30", stage_number=6)
    except TypeError as exc:
        raise AssertionError(
            f"AlertEvent traegt kein additives 'stage_number'-Feld: {exc}"
        ) from exc
    msg_adjacent = AlertMessage(trip_short="X", stand_at="10:00", events=(e1, e2), source=None)
    text_adjacent = render_sms(msg_adjacent)
    assert text_adjacent.startswith("S5-6 "), (
        f"AC-7: zwei benachbarte Etappen muessen als Bereich 'S5-6' "
        f"erscheinen, gemessen: {text_adjacent!r}"
    )

    e3 = _gust_event(1.0, 2.0, "1", "11:00", stage_number=5)
    e4 = _gust_event(3.0, 4.0, "2", "11:30", stage_number=7)
    msg_gap = AlertMessage(trip_short="X", stand_at="10:00", events=(e3, e4), source=None)
    text_gap = render_sms(msg_gap)
    assert text_gap.startswith("S5,7 "), (
        f"AC-7: zwei NICHT benachbarte Etappen muessen aufgezaehlt werden "
        f"('S5,7'), gemessen: {text_gap!r}"
    )


# ═══════════════════════ AC-8 — Fehlende Etappe unterdrueckt ALLES ══════════

def test_ac8_missing_stage_on_one_event_suppresses_the_whole_prefix():
    """AC-8: fehlt bei MINDESTENS EINEM Ereignis die Etappen-Nummer, erscheint
    GAR KEIN Praefix — der Text bleibt byte-identisch zum Bestand.

    BESTAND (gemessen PRE-FIX am 2026-08-30 mit dem aktuellen `render_sms()`,
    zwei `AlertEvent`s ohne `stage_number`-Kenntnis, Segmente '1' und '2'):
        'Seg 1-2: G30->80@11 G30->80@11'

    Positivkontrolle im selben Testkoerper: tragen BEIDE Ereignisse
    (benachbart) eine Etappe, ERSCHEINT das Praefix 'S5-6 ' VOR demselben,
    sonst unveraenderten Bestandstext — das AUSBLEIBEN oben ist also
    nachweislich keine tote/wirkungslose Pruefung.
    """
    BESTAND = "Seg 1-2: G30->80@11 G30->80@11"

    e1_no_stage = _gust_event(1.0, 2.0, "1", "11:00")
    e2_no_stage = _gust_event(3.0, 4.0, "2", "11:30")
    msg_none = AlertMessage(
        trip_short="X", stand_at="10:00", events=(e1_no_stage, e2_no_stage), source=None,
    )
    text_none = render_sms(msg_none)
    assert text_none == BESTAND, (
        f"Setup-Kontrolle: ohne jede Etappen-Nummer bleibt der Bestandstext "
        f"unveraendert, gemessen: {text_none!r}"
    )

    try:
        e1_with_stage = _gust_event(1.0, 2.0, "1", "11:00", stage_number=5)
    except TypeError as exc:
        raise AssertionError(
            f"AlertEvent traegt kein additives 'stage_number'-Feld: {exc}"
        ) from exc
    e2_missing_stage = _gust_event(3.0, 4.0, "2", "11:30")  # bewusst OHNE Etappe
    msg_mixed = AlertMessage(
        trip_short="X", stand_at="10:00",
        events=(e1_with_stage, e2_missing_stage), source=None,
    )
    text_mixed = render_sms(msg_mixed)
    assert text_mixed == BESTAND, (
        "AC-8: fehlt bei EINEM von zwei Ereignissen die Etappe, darf GAR KEIN "
        f"Praefix erscheinen — Text muss byte-identisch zum Bestand bleiben, "
        f"gemessen: {text_mixed!r}"
    )

    # Positivkontrolle: BEIDE Ereignisse tragen eine (benachbarte) Etappe.
    e1_both = _gust_event(1.0, 2.0, "1", "11:00", stage_number=5)
    e2_both = _gust_event(3.0, 4.0, "2", "11:30", stage_number=6)
    msg_both = AlertMessage(
        trip_short="X", stand_at="10:00", events=(e1_both, e2_both), source=None,
    )
    text_both = render_sms(msg_both)
    assert text_both == f"S5-6 {BESTAND}", (
        "Positivkontrolle: tragen BEIDE Ereignisse eine Etappe, MUSS "
        f"'S5-6 ' vor dem unveraenderten Bestandstext stehen, gemessen: "
        f"{text_both!r}"
    )


# ═══════════════════════ AC-9 — Ortsvergleich bleibt ohne Praefix ═══════════

def test_ac9_compare_alert_never_carries_a_stage_prefix():
    """AC-9: ein Alarm aus dem ECHTEN Ortsvergleich-Pfad
    (`to_multi_point_alert_message`) traegt NIE ein Etappen-Praefix — Text
    byte-identisch zum gemessenen Bestand.

    Positivkontrolle im selben Testkoerper: derselbe Renderer zeigt bei einem
    direkt mit `stage_number` konstruierten Ereignis sehr wohl ein Praefix —
    das Ausbleiben oben liegt also am Ortsvergleich-Pfad, nicht an einem toten
    Renderer.
    """
    groups = [
        ("Graz", [_change(new_value=30.0)], _gpx(47.07, 15.44)),
        ("Wien", [_change(new_value=45.0)], _gpx(48.21, 16.37)),
    ]
    msg = to_multi_point_alert_message(groups, tz=TZ, stand_at="04.08. 08:00")
    for e in msg.events:
        assert getattr(e, "stage_number", None) is None, (
            "AC-9 Setup-Kontrolle: der Ortsvergleich-Pfad darf NIE eine "
            f"Etappen-Nummer setzen, gefunden: {getattr(e, 'stage_number', 'FEHLT')!r}"
        )
    text = render_sms(msg, location_positions={"Graz": 1, "Wien": 2})
    assert text == "2:+R45 1:+R30", (
        "AC-9: byte-identisch zum gemessenen Bestand (PRE-FIX, gemessen "
        f"2026-08-30 ueber `to_multi_point_alert_message`), gemessen: {text!r}"
    )

    try:
        e_with_stage = _gust_event(1.0, 2.0, "1", "11:00", stage_number=5)
    except TypeError as exc:
        raise AssertionError(
            f"AlertEvent traegt kein additives 'stage_number'-Feld: {exc}"
        ) from exc
    msg_with_stage = AlertMessage(
        trip_short="X", stand_at="10:00", events=(e_with_stage,), source=None,
    )
    text_with_stage = render_sms(msg_with_stage)
    assert text_with_stage.startswith("S5 "), (
        f"Positivkontrolle: mit gesetzter Etappe MUSS ein Praefix erscheinen, "
        f"gemessen: {text_with_stage!r}"
    )


# ═══════════════════════ AC-10 — Praefix ueberlebt die Kuerzung ═════════════

def test_ac10_prefix_survives_truncation_and_length_budget_holds():
    """AC-10: bei einem kuenstlich kleinen Laengenlimit (harter
    Sicherungsschnitt) bleibt das (zweistellige) Etappen-Praefix VOLLSTAENDIG
    erhalten, und `len(text) <= limit` gilt weiterhin."""
    try:
        events = tuple(
            _gust_event(float(i), float(i + 1), str(i + 1), f"{11 + i}:00", stage_number=12)
            for i in range(5)
        )
    except TypeError as exc:
        raise AssertionError(
            f"AlertEvent traegt kein additives 'stage_number'-Feld: {exc}"
        ) from exc
    msg = AlertMessage(trip_short="X", stand_at="10:00", events=events, source=None)
    limit = 30
    text = render_sms(msg, limit=limit)

    assert len(text) <= limit, (
        f"AC-10: Laengenbudget verletzt — {len(text)} > {limit} Zeichen: {text!r}"
    )
    assert text.startswith("S12 "), (
        "AC-10: das (zweistellige) Etappen-Praefix muss die Kuerzung "
        f"VOLLSTAENDIG ueberleben, gemessen: {text!r}"
    )


# ═══════════════════════ AC-11 — Kanal-Paritaet ═════════════════════════════

def test_ac11_all_three_short_channels_carry_the_same_stage_prefix(monkeypatch):
    """AC-11: SMS, Premium-SMS und Telegram-Kurzform desselben Alarms tragen
    denselben Text — inklusive Etappen-Praefix. Geprueft an einem echten
    `send_deviation_alert`-Aufruf mit allen drei Kurz-Kanaelen aktiv."""
    import output.channels.telegram as tg_module

    trip = _multi_stage_trip()
    sms_stub = _SevenIoStub()
    tg_stub = _TelegramStub()
    try:
        monkeypatch.setattr(tg_module, "TELEGRAM_API_BASE", tg_stub.base_url)
        svc = NotificationService(
            settings=_settings_all_short_channels(sms_stub.port),
            user_id=f"tdd-2122-ac11-{uuid.uuid4().hex[:6]}",
        )
        svc.send_deviation_alert(
            trip=trip, weather=[_segment_weather_data()], changes=[_change()],
            effective_channels={"sms", "telegram", "premium_sms"},
            telegram_style="kurzform",
        )
        assert len(sms_stub.received) == 2, (
            "Setup-Kontrolle: erwartet je eine SMS- und eine "
            f"Premium-SMS-Anfrage, erhalten: {sms_stub.received!r}"
        )
        assert len(tg_stub.sent) == 1, (
            f"Setup-Kontrolle: erwartet genau eine Telegram-Nachricht, "
            f"erhalten: {tg_stub.sent!r}"
        )
        sms_texts = {r["text"] for r in sms_stub.received}
        telegram_text = tg_stub.sent[0].get("text")
        assert len(sms_texts) == 1, (
            f"Setup-Kontrolle: SMS und Premium-SMS muessen denselben Text "
            f"tragen, gemessen: {sms_texts!r}"
        )
        assert sms_texts == {telegram_text}, (
            "AC-11: SMS/Premium-SMS und Telegram-Kurzform muessen "
            f"byte-identisch sein — SMS/Premium={sms_texts!r}, "
            f"Telegram={telegram_text!r}"
        )
        assert telegram_text.startswith("S3 "), (
            f"AC-11: der gemeinsame Text muss das Etappen-Praefix tragen, "
            f"gemessen: {telegram_text!r}"
        )
    finally:
        sms_stub.stop()
        tg_stub.stop()


# ═══════════════ Adversary-Haertung (Runde 2, Verdict BROKEN) ═══════════════
#
# Drei Befunde aus docs/artifacts/fix_2122_etappen_praefix_kurzform/
# adversary-dialog.md. F001/F002 sind Korrektheits-Luecken in der
# Datumsableitung, F003 ist eine Testabdeckungs-Luecke (Mutations-Gegenprobe
# M8 blieb unbewacht).

from freezegun import freeze_time  # noqa: E402

from tests.tdd.conftest import _anker, trip_two_zones  # noqa: E402

# 22:30 UTC am 20.08.2026 = 00:30 Ortszeit auf Korsika am 21.08. -- NACH der
# ORTS-, VOR der WELTZEIT-Mitternacht (dasselbe Zeitfenster wie
# test_befehlspfade_folgen_ortszone.py::NACHTS_UTC).
_F001_NACHTS_UTC = datetime(2026, 8, 20, 22, 30, tzinfo=UTC)
_F001_D20 = date(2026, 8, 20)
_F001_D21 = date(2026, 8, 21)


def test_f001_deviation_alert_prefix_follows_trip_local_day_not_server_clock():
    """Adversary F001 (CRITICAL): die Etappen-Nummer MUSS aus dem ORTSTAG der
    Tour (ADR-0044, `services.trip_day.trip_local_today`) abgeleitet werden,
    nicht aus der Server-/Weltzeit-Wanduhr (`date.today()` waere ein
    `ambient_clock`-Rueckfall, Issue #1402 -- Waechter:
    `tests/test_output_timezone_guard.py`).

    GIVEN eine Zwei-Zonen-Tour (Etappe 0 Neuseeland 20.08., Etappe 1 Korsika
          21.08.) und ein Sendezeitpunkt 22:30 UTC am 20.08. = 00:30 Ortszeit
          auf Korsika am 21.08. -- nach der Orts-, vor der Weltzeit-
          Mitternacht,
    WHEN  der Abweichungs-Alarm gerendert wird,
    THEN  traegt er das Praefix der Korsika-Etappe (S2), NICHT das der
          Neuseeland-Etappe (S1) -- S1 waere exakt der Wert, den eine
          `date.today()`-Ableitung an diesem Zeitpunkt lieferte (der
          Weltzeit-Tag ist an diesem Moment noch der 20.08., der Server-
          Kalendertag unter `freeze_time` ebenfalls -- gemessen ueber
          `_anker()`).
    """
    with freeze_time(_F001_NACHTS_UTC):
        _anker(_F001_NACHTS_UTC, "Europe/Paris", _F001_D21)
        trip = trip_two_zones(_F001_D20, trip_id="tdd-2122-f001")
        stub = _SevenIoStub()
        try:
            svc = NotificationService(
                settings=_settings_sms_only(stub.port),
                user_id=f"tdd-2122-f001-{uuid.uuid4().hex[:6]}",
            )
            svc.send_deviation_alert(
                trip=trip, weather=[_segment_weather_data()], changes=[_change()],
                effective_channels={"sms"},
            )
            assert len(stub.received) == 1, (
                f"Setup-Kontrolle: erwartet genau eine SMS, erhalten: {stub.received!r}"
            )
            text = stub.received[0]["text"]
            assert text.startswith("S2 "), (
                "F001: das Praefix muss die Korsika-Etappe (S2, Ortstag "
                "21.08.) nennen, nicht die Neuseeland-Etappe (S1, Weltzeit-/"
                f"Servertag 20.08.). Gemessen: {text!r}"
            )
        finally:
            stub.stop()


def test_f002_official_alert_omits_prefix_when_anchor_is_stale():
    """Adversary F002 (HIGH): ein mehrere Tage alter, fuer die Routen-
    GEOMETRIE noch gueltiger Ankertag (`trip_alert.py` nutzt ihn dort absichtlich
    ohne Alters-/Tagespruefung, s. `_kanal_anker_kandidat`-Docstring) darf die
    Etappen-NUMMER nicht mehr liefern -- eine falsche Nummer ist schlechter als
    keine (dieselbe Linie wie AC-8: reproduziert zeigte der Anker vor dem Fix
    `S1` statt der tatsaechlich aktuellen `S3`).

    Gegenprobe im selben Testkoerper: derselbe Trip mit einem FRISCHEN Anker
    (heute) zeigt weiterhin das Praefix -- das Ausbleiben oben liegt also an
    der Staleness-Pruefung, nicht an einem toten Codepfad.
    """
    trip = _multi_stage_trip()  # heute = 3. von 5 Etappen
    uid = f"tdd-2122-f002-{uuid.uuid4().hex[:6]}"
    _clean_user(uid)
    stub = _SevenIoStub()
    try:
        weather = [_segment_weather_data()]
        snap_svc = WeatherSnapshotService(user_id=uid)
        stale = date.today() - timedelta(days=2)
        for channel in ("sms", "email", "telegram", "premium_sms"):
            snap_svc.save_alarm_anchor(trip.id, stale, weather, channel)

        alert = OfficialAlert(
            source="geosphere_warn", hazard="thunderstorm", level=2,
            label="Gewitter", valid_from=datetime.now(UTC),
            valid_to=datetime.now(UTC) + timedelta(hours=3),
            region_label="Test-Region",
        )
        svc = NotificationService(settings=_settings_sms_only(stub.port), user_id=uid)
        svc.send_official_alert(
            trip=trip, notices=[(alert, ["1"])], effective_channels={"sms"},
        )
        assert len(stub.received) == 1, (
            f"Setup-Kontrolle: erwartet genau eine SMS, erhalten: {stub.received!r}"
        )
        text_stale = stub.received[0]["text"]
        assert not text_stale.startswith(("S1 ", "S2 ", "S3 ", "S4 ", "S5 ")), (
            "F002: ein 2 Tage alter Anker darf KEINE Etappen-Nummer erzwingen "
            f"(insbesondere nicht die falsche 'S1 '), gemessen: {text_stale!r}"
        )

        # Positivkontrolle: FRISCHER Anker (heute) -> Praefix erscheint.
        stub.received.clear()
        for channel in ("sms", "email", "telegram", "premium_sms"):
            snap_svc.save_alarm_anchor(trip.id, date.today(), weather, channel)
        svc.send_official_alert(
            trip=trip, notices=[(alert, ["1"])], effective_channels={"sms"},
        )
        assert len(stub.received) == 1, (
            f"Setup-Kontrolle Gegenprobe: erwartet genau eine SMS, erhalten: "
            f"{stub.received!r}"
        )
        text_fresh = stub.received[0]["text"]
        assert text_fresh.startswith("S3 "), (
            "Positivkontrolle: ein FRISCHER Anker (heute) muss weiterhin das "
            f"Praefix zeigen, gemessen: {text_fresh!r}"
        )
    finally:
        stub.stop()
        _clean_user(uid)


def test_f003_radar_alert_prefix_reaches_the_real_trigger_path():
    """Adversary F003 (HIGH, Mutations-Gegenprobe M8): das Etappen-Praefix
    muss auch dann erscheinen, wenn `RadarAlertRequest` NICHT von Hand gebaut
    wird, sondern aus dem ECHTEN Ausloesepfad
    (`TripAlertService.check_radar_alerts()` -> `_resolve_alert_segment` ->
    Bau von `RadarAlertRequest(..., segment_date=segment_date, ...)` in
    `trip_alert.py:2220-2227`). AC-2/AC-6 dieser Datei pruefen ausschliesslich
    die KONSUMIERENDE Seite (`NotificationService.send_radar_alert` mit
    handgebautem `RadarAlertRequest`) -- die reale Verdrahtungsstelle blieb
    dadurch unbewacht (M8: Entfernen von `segment_date=segment_date` an
    dieser Stelle liess 0 von ueber 100 gepruefte Tests rot werden).

    Kein Mock: echter `TripAlertService.check_radar_alerts()`, echter Trip auf
    Platte (`app.loader.save_trip`), echte `RadarNowcastService` ueber die
    DI-Naht `radar_service=` mit `CountingFrameSource` (Vorbild
    `tests/helpers/nowcast_gate_fixtures.py`, `test_radar_alert_follows_
    ortstag.py`), echter lokaler seven.io-HTTP-Stub.
    """
    from app.loader import save_trip as loader_save_trip
    from services.trip_alert import TripAlertService
    from tests.helpers.nowcast_gate_fixtures import (
        TRIP_LAT, TRIP_LON, CountingFrameSource, clean_uid, fresh_uid,
        frozen_active_window, make_trip, radar_service, reset_radar_cache,
        write_user_tier,
    )

    reset_radar_cache()
    uid = fresh_uid("f003-2122")
    trip_id = "tdd-2122-f003-trip"
    clean_uid(uid)
    try:
        # SMS ist ein Tier-Merkmal (`user_tier.sms_allowed`) -- ohne
        # "standard"/"premium" wuerde `_effective_alert_channels()` "sms"
        # wieder herausfiltern, unabhaengig vom Trip-Kanal-Wunsch.
        write_user_tier(uid, "standard")
        trip = make_trip(trip_id, lat=TRIP_LAT, lon=TRIP_LON)
        # Nur SMS aktiv -- die Zusicherung liest den zugestellten SMS-Text.
        # `TripReportConfig` ist ein einfaches (nicht-pydantic) `@dataclass`
        # -- Attribute direkt setzen statt `model_copy()`.
        trip.report_config.send_email = False
        trip.report_config.send_sms = True
        stub = _SevenIoStub()
        try:
            with frozen_active_window(hour_utc=12):
                loader_save_trip(trip, user_id=uid)
                svc = TripAlertService(
                    settings=_settings_sms_only(stub.port),
                    throttle_hours=0, user_id=uid,
                    radar_service=radar_service(CountingFrameSource(onset_minutes=8)),
                )
                result = svc.check_radar_alerts()
            assert result == 1, (
                f"Setup-Kontrolle: check_radar_alerts() sollte 1 Alarm "
                f"ausloesen, war {result}"
            )
            assert len(stub.received) == 1, (
                f"Setup-Kontrolle: erwartet genau eine SMS, erhalten: "
                f"{stub.received!r}"
            )
            text = stub.received[0]["text"]
            assert text.startswith("S1 "), (
                "F003: das Praefix muss auch ueber den ECHTEN Radar-"
                f"Ausloesepfad erscheinen (Trip mit 1 Etappe), gemessen: {text!r}"
            )
        finally:
            stub.stop()
    finally:
        clean_uid(uid)

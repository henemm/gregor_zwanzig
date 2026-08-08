"""TDD RED — Issue #1070: Alert-Tages-Obergrenze nach Nutzerlevel (Epic #1067 Slice 3).

SPEC: docs/specs/modules/alert_daily_limit.md

Abgedeckt in dieser Datei (KEINE Mocks — echte Dateien, echter lokaler HTTP-Sink
für Radar/Deviation-Alerts, kein Mock()/patch()/MagicMock):

- Modul-Ebene (`services.alert_daily_limit.load/is_allowed/increment`):
  * Free-Tier: Limit 2/Tag, `now` wird injiziert (kein Zeit-Mock).
  * Standard-Tier: Limit 4/Tag.
  * Premium-Tier: kein Limit (`is_allowed` immer True).
  * Vienna- statt UTC-Mitternachts-Reset (AC-4).
  * `load()` ist reine Lese-Semantik bei veraltetem Datum — kein Schreibzugriff.
- Wiring Radar-Pfad (AC-1): `TripAlertService.check_radar_alerts()` unterdrückt
  einen fälligen Alert, wenn das Free-Tageslimit bereits erreicht ist — kein
  `mail_sink`-Aufruf, Zähler bleibt unverändert, kein neuer `alert_log`-Eintrag.
- Wiring Cross-Path (AC-5): Zähler wird über zwei echte Radar-Läufe auf das
  Free-Limit gebracht; ein anschließender Deviation-Alert
  (`check_and_send_alerts`) für denselben `user_id` wird ebenfalls
  unterdrückt — beide Pfade teilen denselben Zähler (`self._user_id`).
- F001-Symmetrie (AC-6): Das Tageslimit-Gate wird passiert (count < limit),
  aber der Alert scheitert an einem anderen bestehenden Filter (alle Kanäle
  deaktiviert, `delivered` bleibt falsy) → der Tageszähler bleibt unverändert.

RED-Ursache (heute, vor der Implementierung):
- `src/services/alert_daily_limit.py` existiert noch nicht → ImportError für
  alle Modul-Ebene-Tests und für den F001-Test (der `load()` direkt nutzt).
- `trip_alert.py` prüft an keiner der beiden Alert-Sende-Stellen ein
  Tageslimit-Gate und erhöht keinen Tageszähler → AC-1/AC-5-Wiring-Tests
  schlagen fehl, weil der Alert trotz ausgeschöpftem Free-Limit versendet wird
  (`mail_calls`/`telegram_sink` sind gefüllt statt leer).
"""
from __future__ import annotations

import json
import shutil
import threading
import uuid
from datetime import date as date_type
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from app.config import Settings
from app.models import (
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
from app.loader import get_data_dir
from app.trip import Stage, Trip, Waypoint

# Koordinaten im GR20-Gebiet (Korsika) — identisch zu test_issue_827
LAT, LON = 42.20, 9.10


# ═══════════════════════════ Gemeinsame Helper ═══════════════════════════════

def _clean_user(uid: str) -> None:
    d = get_data_dir(uid)
    if d.exists():
        shutil.rmtree(d)


def _write_user_tier(uid: str, tier: str) -> None:
    d = get_data_dir(uid)
    d.mkdir(parents=True, exist_ok=True)
    (d / "user.json").write_text(json.dumps({"id": uid, "tier": tier}))


def _counter_path(uid: str) -> Path:
    # Issue #1213: alert_daily_limit._counter_path() nutzt jetzt get_data_dir()
    # (isolierter `_DATA_ROOT`-Pfad, #1133) statt der hartkodierten
    # "data/users/..."-Konstruktion — dieser Test-Helper muss demselben Pfad
    # folgen, sonst schreibt/liest er am produktiven Modul vorbei.
    from app.loader import get_data_dir
    return get_data_dir(uid) / "alert_daily_count.json"


def _today_vienna_date_str() -> str:
    return datetime.now(timezone.utc).astimezone(ZoneInfo("Europe/Vienna")).date().isoformat()


def _seed_daily_counter(uid: str, count: int) -> None:
    path = _counter_path(uid)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"date": _today_vienna_date_str(), "count": count}))


# ═══════════════════ Modul-Ebene: services.alert_daily_limit ════════════════

class TestModuleFreeTierLimitAndViennaReset:
    def test_free_tier_limit_two_per_day_and_vienna_reset(self):
        """AC-1/AC-4 (Modul): Free-Limit=2, dritter Alert am selben Tag
        unterdrückt; nach dem Vienna-Mitternachts-Übergang (nicht UTC) ist
        das Budget wieder frei."""
        from services.alert_daily_limit import increment, is_allowed

        uid = f"tdd-1070-free-{uuid.uuid4().hex[:6]}"
        _clean_user(uid)
        try:
            _write_user_tier(uid, "free")
            day1 = datetime(2026, 7, 7, 10, 0, tzinfo=timezone.utc)

            assert is_allowed(uid, day1) is True, "1. Alert am Tag muss erlaubt sein"
            increment(uid, day1)
            assert is_allowed(uid, day1) is True, "2. Alert (Free-Limit 2) muss noch erlaubt sein"
            increment(uid, day1)
            assert is_allowed(uid, day1) is False, (
                "3. Alert am selben Tag muss unterdrückt werden (Free-Limit 2 erreicht)"
            )

            data = json.loads(_counter_path(uid).read_text())
            assert data == {"date": "2026-07-07", "count": 2}, (
                f"Zählerdatei nach 2 Increments unerwartet: {data}"
            )

            # AC-4: Vienna-Mitternachts-Reset, NICHT UTC.
            # 2026-07-07 23:30 UTC == 2026-07-08 01:30 Vienna (Sommerzeit UTC+2).
            day1_late_utc = datetime(2026, 7, 7, 23, 30, tzinfo=timezone.utc)
            assert is_allowed(uid, day1_late_utc) is True, (
                "Nach dem Vienna-Mitternachts-Übergang (23:30 UTC == 01:30 Vienna) "
                "muss das volle Tagesbudget wieder verfügbar sein — Reset ist "
                "Vienna-, nicht UTC-basiert"
            )
            increment(uid, day1_late_utc)
            data2 = json.loads(_counter_path(uid).read_text())
            assert data2 == {"date": "2026-07-08", "count": 1}, (
                f"Nach Vienna-Reset erwartete Zählerdatei date=2026-07-08 count=1, got {data2}"
            )
        finally:
            _clean_user(uid)


class TestModuleStandardTierLimit:
    def test_standard_tier_limit_four_per_day(self):
        """AC-2 (Modul): Standard-Limit=4, fünfter Alert am selben Tag
        unterdrückt, vierter noch zulässig."""
        from services.alert_daily_limit import increment, is_allowed

        uid = f"tdd-1070-std-{uuid.uuid4().hex[:6]}"
        _clean_user(uid)
        try:
            _write_user_tier(uid, "standard")
            now = datetime(2026, 7, 7, 10, 0, tzinfo=timezone.utc)
            for i in range(4):
                assert is_allowed(uid, now) is True, (
                    f"Standard-Nutzer: Alert Nr. {i + 1} muss noch erlaubt sein (Limit 4)"
                )
                increment(uid, now)
            assert is_allowed(uid, now) is False, (
                "Standard-Nutzer: 5. Alert am selben Tag muss unterdrückt werden (Limit 4)"
            )
        finally:
            _clean_user(uid)


class TestModulePremiumTierNoLimit:
    def test_premium_tier_never_limited(self):
        """AC-3 (Modul): Premium hat kein Tageslimit — auch bei count=6 immer erlaubt."""
        from services.alert_daily_limit import increment, is_allowed

        uid = f"tdd-1070-prem-{uuid.uuid4().hex[:6]}"
        _clean_user(uid)
        try:
            _write_user_tier(uid, "premium")
            now = datetime(2026, 7, 7, 10, 0, tzinfo=timezone.utc)
            for _ in range(6):
                increment(uid, now)
            assert is_allowed(uid, now) is True, (
                "Premium-Nutzer darf trotz count=6 nie durch das Tageslimit blockiert werden"
            )
        finally:
            _clean_user(uid)


class TestModuleLoadResetSemantics:
    def test_load_returns_zero_for_stale_date_without_writing(self):
        """`load()` liefert bei veraltetem Datum 0 zurück, schreibt aber NICHT
        (reine Lese-Semantik bei Reset)."""
        from services.alert_daily_limit import load

        uid = f"tdd-1070-load-{uuid.uuid4().hex[:6]}"
        _clean_user(uid)
        try:
            counter_path = _counter_path(uid)
            counter_path.parent.mkdir(parents=True, exist_ok=True)
            counter_path.write_text(json.dumps({"date": "2020-01-01", "count": 5}))
            before_mtime = counter_path.stat().st_mtime_ns

            now = datetime(2026, 7, 7, 10, 0, tzinfo=timezone.utc)
            result = load(uid, now)

            assert result == 0, "load() muss bei veraltetem Datum 0 liefern (Reset-Semantik)"
            after_mtime = counter_path.stat().st_mtime_ns
            assert after_mtime == before_mtime, (
                "load() darf bei reinem Reset-Lesen die Zählerdatei nicht anfassen"
            )
        finally:
            _clean_user(uid)


# ═══════════════════ Wiring: Radar-Pfad (AC-1) ═══════════════════════════════

def _wet_frames(lat: float, lon: float) -> list:
    """DI-Seam (Vorbild test_issue_827): liefert Regen-Frames mit Onset <= 20 min
    -> Alert fällig."""
    from providers.brightsky import RadarFrame

    now = datetime.now(timezone.utc)
    return [
        RadarFrame(timestamp=now + timedelta(minutes=5), precip_mm_h=5.0),
        RadarFrame(timestamp=now + timedelta(minutes=15), precip_mm_h=8.0),
    ]


def _make_trip(trip_id: str, send_email: bool, send_telegram: bool) -> Trip:
    today = date_type.today()
    now_utc = datetime.now(timezone.utc)
    arrival_now = (now_utc + timedelta(hours=2)).strftime("%H:%M")
    wp0 = Waypoint(id="WP0", name="Start", lat=LAT, lon=LON, elevation_m=500.0,
                   arrival_calculated=arrival_now)
    wp1 = Waypoint(id="WP1", name="End", lat=LAT + 0.1, lon=LON + 0.1, elevation_m=600.0,
                   arrival_calculated=(now_utc + timedelta(hours=4)).strftime("%H:%M"))
    stage = Stage(id="S1", name="Tag 1", date=today, waypoints=[wp0, wp1])
    trip = Trip(id=trip_id, name="1070 Test", stages=[stage])
    trip.report_config = TripReportConfig(
        trip_id=trip_id,
        send_email=send_email,
        send_telegram=send_telegram,
    )
    return trip


def _save_trip(trip: Trip, user_id: str) -> None:
    # Issue #1133: TripAlertService liest Trips über app.loader.load_all_trips()
    # (isoliert via autouse-Fixture) — get_briefings_dir() folgt demselben Root.
    # Seit #1265 lesen user_tier/alert_daily_limit ebenfalls über get_data_dir(),
    # daher folgen alle Test-Helfer demselben isolierten Root.
    # Issue #1250 Scheibe 7a: load_all_trips liest briefings/, nicht trips/.
    from app.loader import get_briefings_dir
    trips_dir = get_briefings_dir(user_id)
    trips_dir.mkdir(parents=True, exist_ok=True)
    data = {
        "id": trip.id,
        "name": trip.name,
        "stages": [
            {
                "id": s.id,
                "name": s.name,
                "date": s.date.isoformat(),
                "waypoints": [
                    {
                        "id": w.id, "name": w.name,
                        "lat": w.lat, "lon": w.lon,
                        "elevation_m": w.elevation_m,
                        "arrival_calculated": w.arrival_calculated,
                    }
                    for w in s.waypoints
                ],
            }
            for s in trip.stages
        ],
        "report_config": {
            "trip_id": trip.report_config.trip_id,
            "send_email": trip.report_config.send_email,
            "send_telegram": getattr(trip.report_config, "send_telegram", False),
        },
    }
    with open(trips_dir / f"{trip.id}.json", "w") as f:
        json.dump(data, f)


def _make_settings_with_email() -> Settings:
    """Echte Settings-Instanz, bei der can_send_email()=True gilt."""
    return Settings(
        smtp_host="smtp.test.invalid",
        smtp_user="test@test.invalid",
        smtp_pass="testpass",
        mail_to="to@test.invalid",
    )


def test_ac1_radar_alert_suppressed_when_free_daily_limit_reached():
    """AC-1 (Wiring, Radar-Pfad): Free-Nutzer hat heute (Vienna) bereits 2
    Alerts erhalten — ein dritter fälliger Radar-Alert wird unterdrückt: kein
    `mail_sink`-Aufruf, Zähler bleibt bei 2, kein neuer `alert_log`-Eintrag.

    RED: `check_radar_alerts()` prüft an der Recording-Stelle (~Zeile 832 ff.)
    noch kein Tageslimit-Gate — der Alert wird trotz ausgeschöpftem Free-Limit
    tatsächlich versendet (`mail_calls` wird gefüllt statt leer zu bleiben).
    """
    from services.radar_service import RadarNowcastService
    from services.trip_alert import TripAlertService

    uid = f"tdd-1070-ac1-{uuid.uuid4().hex[:6]}"
    trip_id = f"trip-{uuid.uuid4().hex[:6]}"
    _clean_user(uid)
    try:
        _write_user_tier(uid, "free")
        _seed_daily_counter(uid, 2)

        trip = _make_trip(trip_id, send_email=True, send_telegram=False)
        _save_trip(trip, uid)

        mail_calls: list = []
        settings = _make_settings_with_email()
        # throttle_hours=0: cooldown_min=0 -> _is_radar_throttled ist immer False,
        # damit isoliert das Tageslimit geprüft wird (nicht der Cooldown).
        svc = TripAlertService(
            settings=settings,
            throttle_hours=0,
            user_id=uid,
            radar_service=RadarNowcastService(frame_source=_wet_frames),
            mail_sink=lambda subject, body: mail_calls.append((subject, body)),
        )
        result = svc.check_radar_alerts()

        assert result == 0, (
            f"AC-1: Tageslimit erreicht (count=2, Free-Limit=2) — check_radar_alerts() "
            f"soll 0 liefern (kein Versand), got {result}"
        )
        assert not mail_calls, (
            "AC-1: mail_sink wurde trotz ausgeschöpftem Free-Tageslimit aufgerufen"
        )

        data = json.loads(_counter_path(uid).read_text())
        assert data["count"] == 2, (
            f"AC-1: Zähler darf bei unterdrücktem Alert nicht erhöht werden, got {data}"
        )

        alert_log_path = get_data_dir(uid) / "alert_log.json"
        assert not alert_log_path.exists(), (
            "AC-1: alert_log.json wurde geschrieben, obwohl das Tageslimit erreicht war"
        )
    finally:
        _clean_user(uid)


# ═══════════════════ Wiring: Cross-Path (AC-5) ═══════════════════════════════
# Echter Telegram-Socket-Sink (kein Mock) — Vorbild test_issue_816_alert_deviation.py

class _TelegramSink:
    """Echter HTTP-Server, der Telegram-Bot-API-Aufrufe protokolliert."""

    def __init__(self) -> None:
        self.requests: list[dict] = []
        sink = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):  # noqa: D401
                pass

            def do_POST(self):  # noqa: N802
                length = int(self.headers.get("Content-Length", 0) or 0)
                raw = self.rfile.read(length) if length else b"{}"
                try:
                    payload = json.loads(raw or b"{}")
                except Exception:
                    payload = {"_raw": raw.decode(errors="replace")}
                sink.requests.append({"path": self.path, "payload": payload})
                body = json.dumps(
                    {"ok": True, "result": {"message_id": len(sink.requests)}}
                ).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.port = self._server.server_address[1]
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    @property
    def base(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def send_count(self) -> int:
        return sum(1 for r in self.requests if r["path"].endswith("/sendMessage"))

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()


@pytest.fixture()
def telegram_sink(monkeypatch):
    import output.channels.telegram as telegram_mod

    sink = _TelegramSink()
    monkeypatch.setattr(telegram_mod, "TELEGRAM_API_BASE", sink.base)
    monkeypatch.setenv("GZ_TELEGRAM_TEST_CHAT_ID", "1070-fixture-test-chat")
    yield sink
    sink.stop()


def _settings_telegram_only() -> Settings:
    return Settings(telegram_bot_token="test-token", telegram_chat_id="test-chat")


def _segment(segment_id: int | str = 1) -> TripSegment:
    start = datetime(2026, 4, 5, 8, 0, tzinfo=timezone.utc)
    end = datetime(2026, 4, 5, 12, 0, tzinfo=timezone.utc)
    return TripSegment(
        segment_id=segment_id,
        start_point=GPXPoint(lat=47.0, lon=11.0, elevation_m=1000, distance_from_start_km=12.0),
        end_point=GPXPoint(lat=47.1, lon=11.1, elevation_m=1500, distance_from_start_km=18.0),
        start_time=start,
        end_time=end,
        duration_hours=4.0,
        distance_km=6.0,
        ascent_m=500,
        descent_m=0,
    )


def _weather_data(segment_id: int | str = 1, **summary_kwargs) -> SegmentWeatherData:
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


def _deviation_trip(trip_id: str) -> Trip:
    """Trip mit Telegram-Briefing-Kanal und aktiver Δ-Erkennung (Vorbild
    test_issue_816_alert_deviation.py `_trip`)."""
    stage = Stage(
        id="T1", name="Tag 1", date=date_type(2026, 4, 5),
        waypoints=[Waypoint(id="G1", name="Start", lat=47.0, lon=11.0, elevation_m=1000.0)],
    )
    trip = Trip(
        id=trip_id, name="1070 Deviation-Trip", stages=[stage],
        display_config=UnifiedWeatherDisplayConfig(
            trip_id=trip_id,
            metrics=[MetricConfig(metric_id="precipitation", enabled=True)],
            metric_alert_levels={"precipitation_sum": "standard"},
        ),
    )
    trip.report_config = TripReportConfig(
        trip_id=trip_id, send_email=False, send_telegram=True, alert_on_changes=True,
    )
    trip.alert_cooldown_minutes = 0
    return trip


def test_ac5_cross_path_daily_limit_shared_between_radar_and_deviation(telegram_sink):
    """AC-5 (Wiring, Cross-Path): Der Tageszähler wird über zwei echte,
    erfolgreiche Radar-Alert-Läufe auf das Free-Limit (2) gebracht. Ein
    anschließender Deviation-Alert (`check_and_send_alerts`) für denselben
    `user_id` wird ebenfalls unterdrückt — beide Pfade teilen denselben
    Zähler (`self._user_id`), kein Umgehungspfad zwischen Radar- und
    Deviation-Alerts.

    RED: Ohne Verdrahtung schreibt `check_radar_alerts()` den Tageszähler gar
    nicht fort (Vorbedingung schlägt fehl / Datei fehlt), UND selbst wenn die
    Vorbedingung übersprungen würde, würde der Deviation-Pfad trotz
    ausgeschöpftem Kontingent normal über Telegram versenden.
    """
    from services.radar_service import RadarNowcastService
    from services.trip_alert import TripAlertService

    uid = f"tdd-1070-ac5-{uuid.uuid4().hex[:6]}"
    _clean_user(uid)
    try:
        _write_user_tier(uid, "free")

        # Zähler über zwei echte Radar-Läufe (throttle_hours=0, unterschiedliche
        # Trips) auf count=2 bringen.
        email_settings = _make_settings_with_email()
        for i in range(2):
            trip_id = f"trip-radar-{uid}-{i}"
            trip = _make_trip(trip_id, send_email=True, send_telegram=False)
            _save_trip(trip, uid)
            svc = TripAlertService(
                settings=email_settings,
                throttle_hours=0,
                user_id=uid,
                radar_service=RadarNowcastService(frame_source=_wet_frames),
                mail_sink=lambda subject, body: None,
            )
            result = svc.check_radar_alerts()
            assert result == 1, (
                f"Vorbedingung: Radar-Lauf {i + 1} muss zunächst erfolgreich sein "
                f"(count noch unter Free-Limit 2), got {result}"
            )

        counter_data = json.loads(_counter_path(uid).read_text())
        assert counter_data["count"] == 2, (
            f"Vorbedingung: Zähler muss nach 2 erfolgreichen Radar-Alerts bei 2 "
            f"stehen, got {counter_data}"
        )

        alert_log_path = get_data_dir(uid) / "alert_log.json"
        entries_before = json.loads(alert_log_path.read_text())["entries"]

        # Deviation-Pfad für DENSELBEN Nutzer, anderer Trip: muss unterdrückt werden.
        dev_trip = _deviation_trip(f"trip-dev-{uid}")
        cached = [_weather_data(precip_sum_mm=2.0)]
        fresh = [_weather_data(precip_sum_mm=18.0)]

        dev_svc = TripAlertService(
            settings=_settings_telegram_only(), throttle_hours=0, user_id=uid,
        )
        dev_result = dev_svc.check_and_send_alerts(dev_trip, cached, fresh_weather=fresh)

        assert dev_result is False, (
            "AC-5: Deviation-Alert muss unterdrückt werden — Free-Tageslimit "
            "bereits über den Radar-Pfad ausgeschöpft (gemeinsamer Zähler)"
        )
        assert telegram_sink.send_count() == 0, (
            "AC-5: Telegram-Sink wurde trotz ausgeschöpftem Tageslimit für den "
            "Deviation-Pfad aufgerufen"
        )

        entries_after = json.loads(alert_log_path.read_text())["entries"]
        assert len(entries_after) == len(entries_before), (
            "AC-5: kein neuer alert_log-Eintrag darf durch den unterdrückten "
            "Deviation-Alert entstehen"
        )
    finally:
        _clean_user(uid)


# ═══════════════════ F001-Symmetrie (AC-6) ═══════════════════════════════════

def test_ac6_radar_gate_passes_but_no_channel_delivered_leaves_counter_unchanged():
    """AC-6/F001 (Radar-Pfad): Das Tageslimit-Gate wird passiert (count=1 <
    Free-Limit 2), aber der Alert scheitert an einem anderen bestehenden Filter
    (alle Kanäle auf Trip-Ebene deaktiviert, `delivered` bleibt falsy). Der
    Tageszähler darf NICHT erhöht werden — nur tatsächlicher Versand zählt
    (F001-Symmetrie)."""
    from services.alert_daily_limit import load
    from services.radar_service import RadarNowcastService
    from services.trip_alert import TripAlertService

    uid = f"tdd-1070-ac6-{uuid.uuid4().hex[:6]}"
    trip_id = f"trip-{uuid.uuid4().hex[:6]}"
    _clean_user(uid)
    try:
        _write_user_tier(uid, "free")
        _seed_daily_counter(uid, 1)  # unter dem Free-Limit von 2 -> Gate passiert

        # Alle Kanäle deaktiviert (Vorbild test_issue_827 AC-1) -> delivered bleibt falsy.
        trip = _make_trip(trip_id, send_email=False, send_telegram=False)
        _save_trip(trip, uid)

        mail_calls: list = []
        settings = _make_settings_with_email()
        svc = TripAlertService(
            settings=settings,
            throttle_hours=0,
            user_id=uid,
            radar_service=RadarNowcastService(frame_source=_wet_frames),
            mail_sink=lambda subject, body: mail_calls.append((subject, body)),
        )
        result = svc.check_radar_alerts()

        assert result == 0, "Kein Kanal konfiguriert -> kein Versand"
        assert not mail_calls

        now = datetime.now(timezone.utc)
        after_count = load(uid, now)
        assert after_count == 1, (
            f"F001: Zähler darf bei delivered=False nicht erhöht werden, "
            f"erwartet 1 (unverändert), got {after_count}"
        )
    finally:
        _clean_user(uid)


# ═══════════════════ Issue #1081 Adversary-Follow-Up ══════════════════════════
# AC-2/AC-3 müssen laut Spec auf Wiring-Level (mail_sink) getestet werden.
# AC-6 muss zusätzlich für den Deviation-Pfad getestet werden.


def test_ac2_wiring_standard_limit_allows_fourth_blocks_fifth():
    """AC-2 (Wiring, Radar-Pfad): Standard-Nutzer (Limit 4) mit count=3 darf
    den vierten Alert noch versenden; mit count=4 wird der fünfte unterdrückt.
    """
    from services.alert_daily_limit import load
    from services.radar_service import RadarNowcastService
    from services.trip_alert import TripAlertService

    uid = f"tdd-1081-ac2-{uuid.uuid4().hex[:6]}"
    _clean_user(uid)
    try:
        _write_user_tier(uid, "standard")

        # count=3 -> 4. Alert noch erlaubt
        _seed_daily_counter(uid, 3)
        trip_id_4th = f"trip-{uuid.uuid4().hex[:6]}"
        trip_4th = _make_trip(trip_id_4th, send_email=True, send_telegram=False)
        _save_trip(trip_4th, uid)

        mail_calls: list = []
        svc = TripAlertService(
            settings=_make_settings_with_email(),
            throttle_hours=0,
            user_id=uid,
            radar_service=RadarNowcastService(frame_source=_wet_frames),
            mail_sink=lambda subject, body: mail_calls.append((subject, body)),
        )
        result = svc.check_radar_alerts()

        assert result == 1, f"AC-2: 4. Alert für Standard muss noch erlaubt sein, got {result}"
        assert len(mail_calls) == 1, "AC-2: 4. Alert muss per E-Mail versendet werden"
        assert load(uid, datetime.now(timezone.utc)) == 4, "AC-2: Zähler muss auf 4 steigen"

        # count=4 -> 5. Alert blockiert
        trip_id_5th = f"trip-{uuid.uuid4().hex[:6]}"
        trip_5th = _make_trip(trip_id_5th, send_email=True, send_telegram=False)
        _save_trip(trip_5th, uid)

        mail_calls_5th: list = []
        svc_5th = TripAlertService(
            settings=_make_settings_with_email(),
            throttle_hours=0,
            user_id=uid,
            radar_service=RadarNowcastService(frame_source=_wet_frames),
            mail_sink=lambda subject, body: mail_calls_5th.append((subject, body)),
        )
        result_5th = svc_5th.check_radar_alerts()

        assert result_5th == 0, f"AC-2: 5. Alert für Standard muss blockiert sein, got {result_5th}"
        assert not mail_calls_5th, "AC-2: 5. Alert darf keinen E-Mail-Versand auslösen"
        assert load(uid, datetime.now(timezone.utc)) == 4, "AC-2: Zähler darf nicht steigen"
    finally:
        _clean_user(uid)


def test_ac3_wiring_premium_no_limit():
    """AC-3 (Wiring, Radar-Pfad): Premium-Nutzer hat kein Tageslimit —
    count=6 wird bei erfolgreichem Alert auf 7 erhöht."""
    from services.alert_daily_limit import load
    from services.radar_service import RadarNowcastService
    from services.trip_alert import TripAlertService

    uid = f"tdd-1081-ac3-{uuid.uuid4().hex[:6]}"
    _clean_user(uid)
    try:
        _write_user_tier(uid, "premium")
        _seed_daily_counter(uid, 6)

        trip_id = f"trip-{uuid.uuid4().hex[:6]}"
        trip = _make_trip(trip_id, send_email=True, send_telegram=False)
        _save_trip(trip, uid)

        mail_calls: list = []
        svc = TripAlertService(
            settings=_make_settings_with_email(),
            throttle_hours=0,
            user_id=uid,
            radar_service=RadarNowcastService(frame_source=_wet_frames),
            mail_sink=lambda subject, body: mail_calls.append((subject, body)),
        )
        result = svc.check_radar_alerts()

        assert result == 1, f"AC-3: Premium-Alert trotz count=6 muss erlaubt sein, got {result}"
        assert len(mail_calls) == 1, "AC-3: Premium-Alert muss versendet werden"
        assert load(uid, datetime.now(timezone.utc)) == 7, "AC-3: Zähler muss weiter steigen"
    finally:
        _clean_user(uid)


def test_ac6_deviation_gate_passes_but_no_channel_delivered_leaves_counter_unchanged():
    """AC-6/F001 (Deviation-Pfad): Das Tageslimit-Gate wird passiert
    (count=1 < Free-Limit 2), aber kein Kanal ist konfiguriert (`delivered`
    bleibt falsy). Der Tageszähler darf NICHT erhöht werden."""
    from services.alert_daily_limit import load
    from services.trip_alert import TripAlertService

    uid = f"tdd-1081-ac6-dev-{uuid.uuid4().hex[:6]}"
    _clean_user(uid)
    try:
        _write_user_tier(uid, "free")
        _seed_daily_counter(uid, 1)

        # Deviation-Trip mit aktiver Δ-Erkennung, aber KEINEM zustellbaren Kanal.
        trip = _deviation_trip(f"trip-dev-{uid}")
        trip.report_config.send_email = False
        trip.report_config.send_telegram = False
        trip.report_config.alert_on_changes = True

        cached = [_weather_data(precip_sum_mm=2.0)]
        fresh = [_weather_data(precip_sum_mm=18.0)]

        svc = TripAlertService(
            settings=_make_settings_with_email(),
            throttle_hours=0,
            user_id=uid,
        )
        result = svc.check_and_send_alerts(trip, cached, fresh_weather=fresh)

        assert result is False, "Kein Kanal konfiguriert -> delivered=False"
        assert load(uid, datetime.now(timezone.utc)) == 1, (
            "F001 (Deviation): Zähler darf bei delivered=False nicht erhöht werden"
        )
    finally:
        _clean_user(uid)


# ═══════════════════ Issue #1555: NowCast-Reserve im Tagesbudget ═════════════
#
# `alert_daily_limit.is_allowed()` bekommt einen optionalen `reason`-Parameter.
# `reason="forecast_change"` UND endliches `limit` -> Prüfung gegen
# `limit - RESERVE` (Free 2->1, Standard 4->2) statt gegen das volle `limit`.
# `reason=None`/jeder andere Wert (u.a. "nowcast") -> unverändertes
# Altverhalten (volles `limit`). Premium (`limit=None`) bleibt unbegrenzt.
#
# RED-Status je Test (Mutations-Gegenprobe-Vorgabe, Spec Abschnitt "Wo die
# Zusicherung tatsächlich WIRKT"): AC-1/AC-4/AC-5 sind an ihrer eigenen
# Grenze nicht diskriminierend (der Reserve-Effekt greift dort inhärent
# nicht bzw. noch nicht) und bleiben deshalb sowohl heute als auch nach der
# Implementierung GRÜN — sie sind Regressionsschutz, kein RED-Beweis (analog
# AC-5/AC-6 in `test_compare_alert_quiet_hours_precedes_fetch.py`). AC-2,
# AC-3 und AC-6 treffen exakt die Reserve-Grenze und sind heute ROT, weil
# `trip_alert.py:221/761` und `compare_alert.py:145` `is_allowed()` noch
# ohne `reason=` aufrufen (Altverhalten = volles Limit statt Reserve).

_COMPARE_DATA_ROOT = Path(__file__).resolve().parents[2] / "data" / "users"
# Pfadregel #1409: compare_alert.py::_load_presets() ruft load_compare_presets()
# OHNE data_root auf -> Default "data" (bewusster Bypass der _DATA_ROOT-
# Testisolation, dokumentiert in app.loader.get_data_root()). ComparePreset-
# Dateien müssen deshalb -- anders als der Rest dieser Datei (get_data_dir(),
# isolierte _DATA_ROOT) -- unter dem ECHTEN, relativ zu dieser Testdatei
# aufgelösten "data/users/"-Baum liegen (Vorbild:
# test_compare_alert_quiet_hours_precedes_fetch.py::DATA_ROOT).


def _clean_compare_preset_dir(uid: str) -> None:
    d = _COMPARE_DATA_ROOT / uid
    if d.exists():
        shutil.rmtree(d)


def _compare_preset_active(preset_id: str, location_ids: list[str], empfaenger: list[str]) -> dict:
    """Minimaler, aktiver (nicht stillgelegter) Compare-Preset-Dict --
    1:1 aus `test_compare_alert_quiet_hours_precedes_fetch.py::_preset_multi`."""
    return {
        "id": preset_id, "name": preset_id, "user_id": "default",
        "location_ids": location_ids, "schedule": "daily", "weekday": 4,
        "profil": "ALLGEMEIN", "hour_from": 0, "hour_to": 23,
        "empfaenger": empfaenger, "letzter_versand": None,
        "top_ort_letzter_versand": None, "created_at": "2026-08-07T00:00:00Z",
    }


class _ScriptedComparePointSource:
    """Kein Mock: echter `LocationWeatherSource`-Seam, liefert ein festes
    `PointWeatherData` mit vorgegebenem `precip_sum_mm` ohne Netzzugriff."""

    def __init__(self, precip_sum_mm: float) -> None:
        self._precip = precip_sum_mm

    def fetch(
        self, point_id: str, lat: float, lon: float,
        start_hour: int | None = None, end_hour: int | None = None,
    ):
        from services.point_weather import PointWeatherData

        return PointWeatherData(
            id=point_id, name=point_id, lat=lat, lon=lon, timeseries=None,
            aggregated=SegmentWeatherSummary(precip_sum_mm=self._precip),
            fetched_at=datetime.now(timezone.utc), provider="test-scripted",
        )


def test_ac1_1555_free_tier_first_forecast_change_alert_delivered_at_reduced_boundary(
    telegram_sink,
):
    """AC-1 (#1555): Free-Nutzer (`limit=2`) ohne Alarm heute (`count=0`) --
    ein `forecast_change`-Alarm wird zugestellt, weil `count=0 < 1` (reduzierte
    Obergrenze). GRÜN heute wie nach der Implementierung (Regressionsschutz):
    bei `count=0` liefert sowohl das volle Limit (0<2) als auch die reduzierte
    Obergrenze (0<1) `True` -- diese Grenze ist an sich nicht diskriminierend,
    RED-Beweis kommt von AC-2/AC-3/AC-6 weiter unten."""
    from services.alert_daily_limit import load
    from services.trip_alert import TripAlertService

    uid = f"tdd-1555-ac1-{uuid.uuid4().hex[:6]}"
    _clean_user(uid)
    try:
        _write_user_tier(uid, "free")

        dev_trip = _deviation_trip(f"trip-dev-{uid}")
        cached = [_weather_data(precip_sum_mm=2.0)]
        fresh = [_weather_data(precip_sum_mm=18.0)]

        svc = TripAlertService(settings=_settings_telegram_only(), throttle_hours=0, user_id=uid)
        result = svc.check_and_send_alerts(dev_trip, cached, fresh_weather=fresh)

        assert result is True, (
            f"AC-1: erster forecast_change-Alarm bei count=0 muss zugestellt werden, got {result}"
        )
        assert telegram_sink.send_count() == 1, "AC-1: Telegram-Sink muss genau 1 Versand zeigen"
        assert load(uid, datetime.now(timezone.utc)) == 1, "AC-1: Zähler muss auf 1 steigen"
    finally:
        _clean_user(uid)


def test_ac2_1555_free_tier_forecast_change_suppressed_but_nowcast_still_delivered():
    """AC-2 (#1555, RED heute): Free-Nutzer mit `count=1` -- ein weiterer
    `forecast_change`-Alarm wird unterdrückt (Reserve: `count=1` ist nicht
    `< 1`), aber ein `nowcast`-Alarm im selben Zustand wird trotzdem
    zugestellt (`count=1 < 2`, volles Limit).

    RED-Grund (heute): `trip_alert.py:221` ruft `is_allowed(uid, now)` OHNE
    `reason=` auf -- bei count=1/Limit=2 ist 1<2=True, der Deviation-Alarm
    wird heute FÄLSCHLICH zugestellt statt unterdrückt.
    """
    from services.alert_daily_limit import load
    from services.radar_service import RadarNowcastService
    from services.trip_alert import TripAlertService

    uid = f"tdd-1555-ac2-{uuid.uuid4().hex[:6]}"
    _clean_user(uid)
    try:
        _write_user_tier(uid, "free")
        _seed_daily_counter(uid, 1)

        # forecast_change (Deviation, Telegram) -- muss unterdrückt bleiben.
        # Kein telegram_sink-Fixture noetig: TripAlertService versendet ohne
        # erreichbaren TELEGRAM_API_BASE nicht wirklich, aber `is_allowed()`
        # entscheidet VOR dem Versandversuch -- ein unterdrückter Alarm ruft
        # den Kanal gar nicht erst auf.
        dev_trip = _deviation_trip(f"trip-dev-{uid}")
        cached = [_weather_data(precip_sum_mm=2.0)]
        fresh = [_weather_data(precip_sum_mm=18.0)]
        dev_svc = TripAlertService(settings=_settings_telegram_only(), throttle_hours=0, user_id=uid)
        dev_result = dev_svc.check_and_send_alerts(dev_trip, cached, fresh_weather=fresh)

        assert dev_result is False, (
            f"AC-2: forecast_change muss bei count=1 (Reserve-Grenze 1) "
            f"unterdrückt werden, got {dev_result}"
        )
        assert load(uid, datetime.now(timezone.utc)) == 1, (
            "AC-2: Zähler darf durch den unterdrückten forecast_change-Alarm nicht steigen"
        )

        # nowcast (Radar, E-Mail) -- muss trotzdem noch zugestellt werden.
        trip_id = f"trip-radar-{uid}"
        radar_trip = _make_trip(trip_id, send_email=True, send_telegram=False)
        _save_trip(radar_trip, uid)
        mail_calls: list = []
        radar_svc = TripAlertService(
            settings=_make_settings_with_email(),
            throttle_hours=0,
            user_id=uid,
            radar_service=RadarNowcastService(frame_source=_wet_frames),
            mail_sink=lambda subject, body: mail_calls.append((subject, body)),
        )
        radar_result = radar_svc.check_radar_alerts()

        assert radar_result == 1, (
            f"AC-2: nowcast muss bei count=1 gegen das volle Limit (2) noch "
            f"erlaubt sein, got {radar_result}"
        )
        assert len(mail_calls) == 1, "AC-2: nowcast-Alarm muss tatsächlich versendet werden"
        assert load(uid, datetime.now(timezone.utc)) == 2, "AC-2: Zähler muss nach nowcast auf 2 steigen"
    finally:
        _clean_user(uid)


def test_ac3_1555_standard_tier_forecast_change_suppressed_but_nowcast_still_delivered():
    """AC-3 (#1555, RED heute): Standard-Nutzer (`limit=4`) mit `count=2` --
    ein dritter `forecast_change`-Alarm wird unterdrückt (Reserve: `count=2`
    ist nicht `< 2`), aber ein `nowcast`-Alarm wird trotzdem zugestellt
    (`count=2 < 4`).

    RED-Grund: analog AC-2 -- `is_allowed(uid, now)` ohne `reason=` prüft
    heute 2<4=True, der Deviation-Alarm wird fälschlich zugestellt.
    """
    from services.alert_daily_limit import load
    from services.radar_service import RadarNowcastService
    from services.trip_alert import TripAlertService

    uid = f"tdd-1555-ac3-{uuid.uuid4().hex[:6]}"
    _clean_user(uid)
    try:
        _write_user_tier(uid, "standard")
        _seed_daily_counter(uid, 2)

        dev_trip = _deviation_trip(f"trip-dev-{uid}")
        cached = [_weather_data(precip_sum_mm=2.0)]
        fresh = [_weather_data(precip_sum_mm=18.0)]
        dev_svc = TripAlertService(settings=_settings_telegram_only(), throttle_hours=0, user_id=uid)
        dev_result = dev_svc.check_and_send_alerts(dev_trip, cached, fresh_weather=fresh)

        assert dev_result is False, (
            f"AC-3: forecast_change muss bei count=2 (Standard, Reserve-Grenze 2) "
            f"unterdrückt werden, got {dev_result}"
        )
        assert load(uid, datetime.now(timezone.utc)) == 2, (
            "AC-3: Zähler darf durch den unterdrückten forecast_change-Alarm nicht steigen"
        )

        trip_id = f"trip-radar-{uid}"
        radar_trip = _make_trip(trip_id, send_email=True, send_telegram=False)
        _save_trip(radar_trip, uid)
        mail_calls: list = []
        radar_svc = TripAlertService(
            settings=_make_settings_with_email(),
            throttle_hours=0,
            user_id=uid,
            radar_service=RadarNowcastService(frame_source=_wet_frames),
            mail_sink=lambda subject, body: mail_calls.append((subject, body)),
        )
        radar_result = radar_svc.check_radar_alerts()

        assert radar_result == 1, (
            f"AC-3: nowcast muss bei count=2 gegen das volle Limit (4) noch "
            f"erlaubt sein, got {radar_result}"
        )
        assert len(mail_calls) == 1, "AC-3: nowcast-Alarm muss tatsächlich versendet werden"
        assert load(uid, datetime.now(timezone.utc)) == 3, "AC-3: Zähler muss nach nowcast auf 3 steigen"
    finally:
        _clean_user(uid)


def test_ac4_1555_premium_tier_unlimited_for_both_forecast_change_and_nowcast(telegram_sink):
    """AC-4 (#1555): Premium-Nutzer (`limit=None`) mit `count=6` -- sowohl
    `forecast_change` als auch `nowcast` werden zugestellt, kein Deckel
    greift. GRÜN heute wie nach der Implementierung (Regressionsschutz):
    Premium kurzschließt `is_allowed()` unabhängig von `reason` immer auf
    `True` (Spec: "keine Reserve, is_allowed liefert weiterhin sofort True
    ohne Zähler-Load") -- dieses Verhalten ist per Definition der AC in
    keinem der beiden Regime unterscheidbar."""
    from services.alert_daily_limit import load
    from services.radar_service import RadarNowcastService
    from services.trip_alert import TripAlertService

    uid = f"tdd-1555-ac4-{uuid.uuid4().hex[:6]}"
    _clean_user(uid)
    try:
        _write_user_tier(uid, "premium")
        _seed_daily_counter(uid, 6)

        dev_trip = _deviation_trip(f"trip-dev-{uid}")
        cached = [_weather_data(precip_sum_mm=2.0)]
        fresh = [_weather_data(precip_sum_mm=18.0)]
        dev_svc = TripAlertService(settings=_settings_telegram_only(), throttle_hours=0, user_id=uid)
        dev_result = dev_svc.check_and_send_alerts(dev_trip, cached, fresh_weather=fresh)

        assert dev_result is True, f"AC-4: Premium forecast_change trotz count=6 muss zugestellt werden, got {dev_result}"
        assert telegram_sink.send_count() == 1
        assert load(uid, datetime.now(timezone.utc)) == 7, "AC-4: Zähler steigt weiter (kein Deckel)"

        trip_id = f"trip-radar-{uid}"
        radar_trip = _make_trip(trip_id, send_email=True, send_telegram=False)
        _save_trip(radar_trip, uid)
        mail_calls: list = []
        radar_svc = TripAlertService(
            settings=_make_settings_with_email(),
            throttle_hours=0,
            user_id=uid,
            radar_service=RadarNowcastService(frame_source=_wet_frames),
            mail_sink=lambda subject, body: mail_calls.append((subject, body)),
        )
        radar_result = radar_svc.check_radar_alerts()

        assert radar_result == 1, f"AC-4: Premium nowcast trotz count=7 muss zugestellt werden, got {radar_result}"
        assert len(mail_calls) == 1
        assert load(uid, datetime.now(timezone.utc)) == 8
    finally:
        _clean_user(uid)


def test_ac5_1555_is_allowed_without_reason_argument_uses_full_limit_backward_compat():
    """AC-5 (#1555): ein bestehender Aufruf `is_allowed(user_id, now)` OHNE
    `reason`-Argument verhält sich exakt wie vor dieser Änderung -- geprüft
    gegen das volle `limit`, nicht gegen die reduzierte `forecast_change`-
    Obergrenze. GRÜN heute wie danach (das IST die Rückwärtskompatibilitäts-
    Garantie, keine RED-Grenze): bei count=1/Free ist 1<2=True unabhängig
    von der Implementierung dieses Fixes. Der bestehende Wiring-Vorbild-Test
    `test_ac5_cross_path_daily_limit_shared_between_radar_and_deviation`
    (oben in dieser Datei) bleibt unverändert grün und verankert dieselbe
    Garantie an der Aufrufstelle."""
    from services.alert_daily_limit import is_allowed

    uid = f"tdd-1555-ac5-{uuid.uuid4().hex[:6]}"
    _clean_user(uid)
    try:
        _write_user_tier(uid, "free")
        _seed_daily_counter(uid, 1)
        now = datetime.now(timezone.utc)

        assert is_allowed(uid, now) is True, (
            "AC-5: is_allowed(uid, now) ohne reason muss bei count=1/Free "
            "gegen das volle Limit (2) prüfen -> True, nicht gegen die "
            "reduzierte forecast_change-Obergrenze (1)"
        )
    finally:
        _clean_user(uid)


def test_ac6_1555_compare_forecast_change_suppressed_at_reserve_boundary():
    """AC-6 (#1555, RED heute): Compare-Pfad im selben Zählerstand wie AC-2
    (Free, `count=1`) -- ein weiterer Compare-`forecast_change`-Alarm wird
    ebenso unterdrückt wie im Trip-Pfad, dieselbe Reserve-Regel gilt
    identisch für Compare.

    RED-Grund (heute): `compare_alert.py:145` ruft `is_allowed(uid, now)`
    OHNE `reason=` auf -- bei count=1/Limit=2 ist 1<2=True, der Alarm wird
    heute FÄLSCHLICH zugestellt statt unterdrückt.
    """
    from app.loader import save_location
    from app.user import SavedLocation
    from services import alert_daily_limit
    from services.compare_alert import CompareAlertService
    from services.compare_weather_snapshot import CompareWeatherSnapshotService

    from tests.helpers.compare_briefings import write_compare_briefings

    uid = f"tdd-1555-ac6-{uuid.uuid4().hex[:6]}"
    preset_id = f"cp-1555-ac6-{uuid.uuid4().hex[:6]}"
    _clean_user(uid)
    _clean_compare_preset_dir(uid)
    try:
        _write_user_tier(uid, "free")
        _seed_daily_counter(uid, 1)

        loc = SavedLocation(id="loc-1555", name="ReserveOrt", lat=46.9, lon=10.9, elevation_m=900)
        save_location(loc, user_id=uid)
        write_compare_briefings(
            _COMPARE_DATA_ROOT / uid,
            [_compare_preset_active(preset_id, ["loc-1555"], ["gregor-test@henemm.com"])],
        )
        CompareWeatherSnapshotService(user_id=uid).save(
            preset_id, "loc-1555",
            _ScriptedComparePointSource(2.0).fetch("loc-1555", loc.lat, loc.lon),
        )

        sent_subjects: list[str] = []
        svc = CompareAlertService(
            settings=_make_settings_with_email(), user_id=uid,
            weather_source=_ScriptedComparePointSource(30.0),  # Δ=28, weit über jeder Schwelle
            mail_sink=lambda subject, body: sent_subjects.append(subject),
        )
        sent = svc.check_all_compare_presets()

        assert sent == 0, (
            f"AC-6: Reserve muss den 2. Compare-forecast_change-Alarm bei "
            f"count=1 (Free, Reserve-Grenze 1) unterdrücken, got sent={sent}"
        )
        assert sent_subjects == [], "AC-6: mail_sink wurde trotz Reserve aufgerufen"
        assert alert_daily_limit.load(uid, datetime.now(timezone.utc)) == 1, (
            "AC-6: Zähler darf bei unterdrücktem Compare-Alarm nicht steigen"
        )
    finally:
        _clean_user(uid)
        _clean_compare_preset_dir(uid)

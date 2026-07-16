"""TDD RED — Issue #638: Alerts-Tab Karten-Modell + Severity-Falle + Kanal pro Alert.

Backend-Verhaltenstests (NO MOCKS — CLAUDE.md):
- Echter lokaler Telegram-HTTP-Sink (echtes Socket) beobachtet, WELCHER Kanal sendet.
- Echter Fast-Fail-SMTP-Greeter (echtes Socket): bietet kein STARTTLS an → smtplib wirft
  SMTPNotSupportedError sofort (kein 50s-Retry), so dass ein fälschlicher E-Mail-Versand
  schnell scheitert statt zu hängen.
- Echte Trip-/Snapshot-Persistenz über save_trip/load_trip in tmp-Verzeichnis.

Diese Tests schlagen HEUTE fehl:
- AC-1: Ein aktiver Alert mit (alt) severity=info wird durch den MODERATE-Filter
        still verschluckt → kein Versand.
- AC-2: Pro-Alert-Kanal-Override existiert nicht — Versand folgt nur report_config.
- AC-3/AC-4/AC-5: AlertRule hat noch kein `channels`-Feld → wird nicht persistiert.

SPEC: docs/specs/modules/issue_638_alerts_redesign.md
"""
from __future__ import annotations

import json
import socket
import threading
from datetime import date, datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from app.config import Settings
from app.loader import load_trip, save_trip
from app.models import (
    AlertMetric,
    AlertRule,
    AlertRuleKind,
    AlertSeverity,
    ForecastMeta,
    GPXPoint,
    NormalizedTimeseries,
    Provider,
    SegmentWeatherData,
    SegmentWeatherSummary,
    TripReportConfig,
    TripSegment,
    UnifiedWeatherDisplayConfig,
)
from app.trip import Stage, Trip, Waypoint
import output.channels.telegram as telegram_mod


def _reset_alert_state(user_id: str) -> None:
    """State-Bereinigung für Idempotenz (Issue #816: alert_state persistiert;
    alert_daily_count.json zusaetzlich seit #1070). Issue #1265 Teil C:
    get_data_dir() statt hartkodiertem "data/users/..." -- respektiert die
    pytest-Isolation (tests/conftest.py, #1133/#1265)."""
    import shutil
    from app.loader import get_data_dir

    udir = get_data_dir(user_id)
    for fname in ("alert_state", "alert_throttle.json", "alert_log.json", "alert_daily_count.json"):
        p = udir / fname
        if p.is_dir():
            shutil.rmtree(p, ignore_errors=True)
        elif p.exists():
            p.unlink(missing_ok=True)


# ───────────────────────── echte Socket-Sinks (keine Mocks) ─────────────────

class _TelegramSink:
    """Echter HTTP-Server, der Telegram-Bot-API-Aufrufe entgegennimmt und protokolliert."""

    def __init__(self) -> None:
        self.requests: list[dict] = []
        sink = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):  # noqa: D401 - silence
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


class _SMTPRefuse:
    """Echter SMTP-Greeter: begrüßt, bietet aber kein STARTTLS an → schneller SMTPException-Fail."""

    def __init__(self) -> None:
        self.attempts = 0
        self._running = True
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind(("127.0.0.1", 0))
        self._sock.listen(5)
        self.port = self._sock.getsockname()[1]
        threading.Thread(target=self._serve, daemon=True).start()

    def _serve(self) -> None:
        while self._running:
            try:
                conn, _ = self._sock.accept()
            except OSError:
                return
            threading.Thread(target=self._handle, args=(conn,), daemon=True).start()

    def _handle(self, conn: socket.socket) -> None:
        self.attempts += 1
        try:
            conn.sendall(b"220 sink ready\r\n")
            f = conn.makefile("rb")
            for raw in f:
                cmd = raw.decode(errors="replace").strip().upper()
                if cmd.startswith("EHLO") or cmd.startswith("HELO"):
                    conn.sendall(b"250 sink\r\n")  # keine STARTTLS-Extension
                elif cmd.startswith("QUIT"):
                    conn.sendall(b"221 bye\r\n")
                    break
                else:
                    conn.sendall(b"502 not implemented\r\n")
        except OSError:
            pass
        finally:
            conn.close()

    def stop(self) -> None:
        self._running = False
        try:
            self._sock.close()
        except OSError:
            pass


# ───────────────────────── Fixtures & Builder ───────────────────────────────

@pytest.fixture()
def telegram_sink(monkeypatch):
    sink = _TelegramSink()
    monkeypatch.setattr(telegram_mod, "TELEGRAM_API_BASE", sink.base)
    yield sink
    sink.stop()


@pytest.fixture()
def smtp_refuse():
    sink = _SMTPRefuse()
    yield sink
    sink.stop()


def _settings(smtp_port: int) -> Settings:
    """Settings mit erfüllter can_send_email()/can_send_telegram(), E-Mail aber Fast-Fail."""
    return Settings(
        smtp_host="127.0.0.1",
        smtp_port=smtp_port,
        smtp_user="sink-user",
        smtp_pass="sink-pass",
        # Issue #1235: Empfaenger muss lokal (@henemm.com) sein, sonst blockt
        # der neue Nicht-Resend-Empfaenger-Guard VOR dem Sink-Zustellversuch,
        # den dieser Test eigentlich prueft (example.com ist RFC-2606-reserviert).
        mail_to="sink@henemm.com",
        mail_from="alerts@example.com",
        telegram_bot_token="test-token",
        telegram_chat_id="test-chat",
    )


def _segment() -> TripSegment:
    now = datetime.now(timezone.utc)
    return TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=47.0, lon=11.0, elevation_m=1000),
        end_point=GPXPoint(lat=47.1, lon=11.1, elevation_m=1500),
        start_time=now,
        end_time=now,
        duration_hours=2.0,
        distance_km=5.0,
        ascent_m=500,
        descent_m=0,
    )


def _data(**summary_kwargs) -> SegmentWeatherData:
    return SegmentWeatherData(
        segment=_segment(),
        timeseries=NormalizedTimeseries(
            meta=ForecastMeta(
                provider=Provider.GEOSPHERE,
                model="test",
                run=datetime.now(timezone.utc),
                grid_res_km=1.0,
                interp="test",
            ),
            data=[],
        ),
        aggregated=SegmentWeatherSummary(**summary_kwargs),
        fetched_at=datetime.now(timezone.utc),
        provider="geosphere",
    )


def _alert_display_config(trip_id: str) -> "UnifiedWeatherDisplayConfig":
    """Issue #946: metric_alert_levels ist die einzige Detektor-Quelle.

    wind_gust='standard' → Δ-Schwelle 20; die Testläufe fahren gust 25→60 (Δ=35),
    also feuert der Detektor. Die alert_rules bleiben für Kanal-/Severity-Routing
    erhalten (channels-Override etc.), steuern aber nicht mehr die Change-Erkennung.

    Issue #961 (Fixture-Korrektur): Weather-Tab-Metrik 'gust' aktiv setzen, sonst
    greift die Deaktivieren-Lücke und der wind_gust-Alarm feuert nicht mehr.
    """
    from app.models import MetricConfig, UnifiedWeatherDisplayConfig
    return UnifiedWeatherDisplayConfig(
        trip_id=trip_id,
        metrics=[MetricConfig(metric_id="gust", enabled=True)],
        metric_alert_levels={"wind_gust": "standard"},
    )


def _trip(rule: AlertRule, report_config: TripReportConfig | None = None) -> Trip:
    stage = Stage(
        id="T1", name="Tag 1", date=date.today(),
        waypoints=[Waypoint(id="G1", name="Start", lat=47.0, lon=11.0, elevation_m=1000.0)],
    )
    trip = Trip(
        id="tdd-638-trip", name="Alert Test Trip", stages=[stage],
        display_config=_alert_display_config("tdd-638-trip"),
    )
    trip.alert_rules = [rule]
    trip.report_config = report_config
    return trip


def _wind_rule(severity: AlertSeverity, channels: list[str]) -> AlertRule:
    return AlertRule(
        id="r-gust",
        kind=AlertRuleKind.ABSOLUTE,
        metric=AlertMetric.WIND_GUST,
        threshold=50.0,
        severity=severity,
        enabled=True,
        unit="km/h",
        channels=channels,
    )


def _run_alert(trip: Trip, settings: Settings, user_id: str):
    """Führt einen Alert-Lauf durch. Bereinigt alert_state + alert_throttle vor
    dem Lauf (Idempotenz — Wiederholte Testläufe liefern konsistente Ergebnisse).

    Issue #816: Alert-Pfad nutzt jetzt symmetrische Δ-Erkennung.
    gust_max_kmh Δ=35 (25→60) liegt sicher über MetricCatalog-Default 20.
    """
    from services.trip_alert import TripAlertService

    # State-Bereinigung für Idempotenz. alert_daily_count.json zusaetzlich seit
    # #1070 (Alert-Tages-Obergrenze): die fixe Test-User-ID ohne diese Bereinigung
    # wuerde nach mehreren Testlaeufen am selben Vienna-Kalendertag das Free-Limit
    # (2) erreichen und der Testfall wuerde faelschlich fehlschlagen.
    _reset_alert_state(user_id)

    service = TripAlertService(settings=settings, user_id=user_id)
    cached = [_data(gust_max_kmh=25.0)]   # Δ=35 > MetricCatalog-Schwelle 20
    fresh = [_data(gust_max_kmh=60.0)]
    return service.check_and_send_alerts(trip, cached, fresh_weather=fresh)


# ───────────────────────── AC-1: Severity-Falle ─────────────────────────────

def test_ac1_info_severity_alert_is_no_longer_silently_swallowed(
    telegram_sink, smtp_refuse, tmp_path
):
    """AC-1: Aktiver Alert (alt severity=info), Schwelle überschritten → MUSS versenden.

    Heute: info → ChangeSeverity.MINOR → vom MODERATE-Filter verschluckt → kein Versand.
    """
    rule = _wind_rule(AlertSeverity.INFO, channels=["telegram"])
    trip = _trip(rule, report_config=None)

    result = _run_alert(trip, _settings(smtp_refuse.port), user_id="tdd-638-ac1")

    assert result is True, "Alert sollte versendet werden (kein stilles Verschlucken)"
    assert telegram_sink.send_count() == 1, (
        "Info-Alert wurde nicht über Telegram zugestellt — Severity-Falle aktiv"
    )


# ───────────────────────── AC-2: Pro-Alert-Kanal-Override ────────────────────

def test_ac2_per_alert_channel_override_beats_briefing_channel(
    telegram_sink, smtp_refuse, tmp_path
):
    """AC-2: rule.channels=[telegram] gewinnt über report_config (email an, telegram aus)."""
    rule = _wind_rule(AlertSeverity.WARNING, channels=["telegram"])
    report_config = TripReportConfig(
        trip_id="tdd-638-trip",
        send_email=True,
        send_telegram=False,
        alert_on_changes=True,
    )
    trip = _trip(rule, report_config=report_config)

    result = _run_alert(trip, _settings(smtp_refuse.port), user_id="tdd-638-ac2")

    assert result is True
    assert telegram_sink.send_count() == 1, "Override-Kanal Telegram hat nicht zugestellt"
    assert smtp_refuse.attempts == 0, (
        "E-Mail wurde trotz Telegram-Override versucht — Routing folgt noch report_config"
    )


# ───────────────────────── AC-3: Kanal-Vererbung ────────────────────────────

def test_ac3_empty_channels_inherit_briefing_channels(
    telegram_sink, smtp_refuse, tmp_path
):
    """AC-3: rule.channels leer → erbt aktive Briefing-Kanäle (hier: Telegram)."""
    rule = _wind_rule(AlertSeverity.WARNING, channels=[])
    report_config = TripReportConfig(
        trip_id="tdd-638-trip",
        send_email=False,
        send_telegram=True,
        alert_on_changes=True,
    )
    trip = _trip(rule, report_config=report_config)

    result = _run_alert(trip, _settings(smtp_refuse.port), user_id="tdd-638-ac3")

    assert result is True
    assert telegram_sink.send_count() == 1, "Geerbter Telegram-Kanal hat nicht zugestellt"
    assert smtp_refuse.attempts == 0, "E-Mail versucht, obwohl Briefing-E-Mail aus ist"


# ───────────────────────── AC-4: Persistenz-Roundtrip ───────────────────────

def test_ac4_channels_survive_save_load_roundtrip(tmp_path):
    """AC-4: alert_rules[].channels überleben save_trip → load_trip ohne Datenverlust."""
    rule = _wind_rule(AlertSeverity.WARNING, channels=["telegram", "email"])
    trip = _trip(rule, report_config=None)

    path = save_trip(trip, user_id="tdd-638-ac4", data_dir=tmp_path)
    loaded = load_trip(path)

    assert loaded is not None
    assert len(loaded.alert_rules) == 1
    assert loaded.alert_rules[0].channels == ["telegram", "email"], (
        "channels-Feld wurde nicht persistiert/geladen"
    )


def test_ac4_legacy_rule_without_channels_defaults_to_empty(tmp_path):
    """AC-4: Bestands-Alert ohne channels-Feld lädt fehlerfrei mit leerer Liste (kein Datenverlust)."""
    legacy = {
        "id": "tdd-638-legacy",
        "name": "Legacy Trip",
        "stages": [],
        "alert_rules": [
            {
                "id": "r-legacy",
                "kind": "absolute",
                "metric": "wind_gust",
                "threshold": 50.0,
                "unit": "km/h",
                "severity": "warning",
                "enabled": True,
            }
        ],
    }

    loaded = load_trip(legacy)

    assert loaded is not None
    assert len(loaded.alert_rules) == 1
    assert loaded.alert_rules[0].channels == [], "Bestands-Alert sollte channels=[] defaulten"


# ───────────────────────── AC-5: Mandantentrennung ──────────────────────────

def test_ac5_per_user_alert_channels_are_isolated(tmp_path):
    """AC-5: Zwei Nutzer mit je eigenem Trip + eigenen Alert-Kanälen — keine Vermischung."""
    rule_a = _wind_rule(AlertSeverity.WARNING, channels=["telegram"])
    trip_a = _trip(rule_a, report_config=None)
    trip_a.id = "trip-user-a"

    rule_b = _wind_rule(AlertSeverity.WARNING, channels=["email"])
    trip_b = _trip(rule_b, report_config=None)
    trip_b.id = "trip-user-b"

    path_a = save_trip(trip_a, user_id="tdd-638-userA", data_dir=tmp_path)
    path_b = save_trip(trip_b, user_id="tdd-638-userB", data_dir=tmp_path)

    loaded_a = load_trip(path_a)
    loaded_b = load_trip(path_b)

    assert loaded_a.alert_rules[0].channels == ["telegram"]
    assert loaded_b.alert_rules[0].channels == ["email"]


# ───────────────────────── Mixed-Rule-Fall ───────────────────────────────────

def test_mixed_rules_union_both_channels(telegram_sink, smtp_refuse, tmp_path):
    """Mixed-Rule: Regel-A=[telegram] + Regel-B=[]/briefing-email → BEIDE Kanäle bedient.

    Ohne Union-Semantik würde _effective_alert_channels bei has_any_override auf {"telegram"}
    short-circuiten und den geerbten E-Mail-Kanal von Regel-B still verwerfen.
    """
    from app.trip import Stage, Trip, Waypoint

    rule_a = AlertRule(
        id="r-gust-a",
        kind=AlertRuleKind.ABSOLUTE,
        metric=AlertMetric.WIND_GUST,
        threshold=50.0,
        severity=AlertSeverity.WARNING,
        enabled=True,
        unit="km/h",
        channels=["telegram"],  # expliziter Override
    )
    rule_b = AlertRule(
        id="r-gust-b",
        kind=AlertRuleKind.ABSOLUTE,
        metric=AlertMetric.WIND_GUST,
        threshold=50.0,
        severity=AlertSeverity.WARNING,
        enabled=True,
        unit="km/h",
        channels=[],  # leer → erbt Briefing-Kanäle
    )
    report_config = TripReportConfig(
        trip_id="tdd-638-mixed",
        send_email=True,
        send_telegram=False,  # Telegram als Briefing-Kanal AUS
        alert_on_changes=True,
    )
    stage = Stage(
        id="T1", name="Tag 1", date=date.today(),
        waypoints=[Waypoint(id="G1", name="Start", lat=47.0, lon=11.0, elevation_m=1000.0)],
    )
    trip = Trip(
        id="tdd-638-mixed", name="Mixed Rule Trip", stages=[stage],
        display_config=_alert_display_config("tdd-638-mixed"),
    )
    trip.alert_rules = [rule_a, rule_b]
    trip.report_config = report_config

    from services.trip_alert import TripAlertService

    # State-Bereinigung für Idempotenz (Issue #816: alert_state persistiert;
    # alert_daily_count.json zusaetzlich seit #1070, siehe Kommentar oben).
    _reset_alert_state("tdd-638-mixed")

    service = TripAlertService(settings=_settings(smtp_refuse.port), user_id="tdd-638-mixed")
    cached = [_data(gust_max_kmh=25.0)]   # Δ=35 > MetricCatalog-Schwelle 20
    fresh = [_data(gust_max_kmh=60.0)]
    result = service.check_and_send_alerts(trip, cached, fresh_weather=fresh)

    assert result is True
    assert telegram_sink.send_count() == 1, (
        "Regel-A=[telegram] hat nicht über Telegram zugestellt"
    )
    assert smtp_refuse.attempts >= 1, (
        "Regel-B=[]/briefing-email hätte E-Mail versuchen müssen — Union-Semantik fehlt"
    )


# ───────────────────────── Legacy-Pfad: kein alert_rules ────────────────────

def test_channel_inheritance_no_alert_rules_uses_report_config(
    telegram_sink, smtp_refuse, tmp_path
):
    """Kanal-Vererbung: Trip OHNE alert_rules, MIT report_config (telegram=True).

    Issue #946: Die Change-Erkennung läuft jetzt über metric_alert_levels (einzige
    Quelle) statt über den früheren from_trip_config-Legacy-Pfad. Die eigentliche
    Zusicherung bleibt unverändert: hat der Trip keine aktiven alert_rules, erbt
    _effective_alert_channels die Briefing-Kanäle aus report_config (hier Telegram),
    statt ein leeres Set zurückzugeben.
    """
    from app.models import MetricConfig, UnifiedWeatherDisplayConfig
    report_config = TripReportConfig(
        trip_id="tdd-638-legacy-trip",
        send_email=False,
        send_telegram=True,
        alert_on_changes=True,
    )
    stage = Stage(
        id="T1", name="Tag 1", date=date.today(),
        waypoints=[Waypoint(id="G1", name="Start", lat=47.0, lon=11.0, elevation_m=1000.0)],
    )
    trip = Trip(
        id="tdd-638-legacy-trip", name="Legacy Alert Trip", stages=[stage],
        display_config=UnifiedWeatherDisplayConfig(
            trip_id="tdd-638-legacy-trip",
            # Issue #961 (Fixture-Korrektur): Weather-Tab-Metrik 'gust' aktiv setzen.
            metrics=[MetricConfig(metric_id="gust", enabled=True)],
            metric_alert_levels={"wind_gust": "standard"},
        ),
    )
    trip.alert_rules = []  # keine alert_rules → Kanäle werden aus report_config geerbt
    trip.report_config = report_config

    from services.trip_alert import TripAlertService

    # State-Bereinigung für Idempotenz (Issue #816: alert_state persistiert;
    # alert_daily_count.json zusaetzlich seit #1070, siehe Kommentar oben).
    _reset_alert_state("tdd-638-legacy")

    service = TripAlertService(settings=_settings(smtp_refuse.port), user_id="tdd-638-legacy")
    # Delta=30 km/h > Standard-Schwelle 20 km/h → Change wird erkannt
    cached = [_data(gust_max_kmh=30.0)]
    fresh = [_data(gust_max_kmh=60.0)]
    result = service.check_and_send_alerts(trip, cached, fresh_weather=fresh)

    assert result is True, (
        "Legacy-Pfad: check_and_send_alerts muss True liefern wenn report_config aktiv ist"
    )
    assert telegram_sink.send_count() == 1, (
        "Telegram wurde nicht zugestellt — _effective_alert_channels gibt leeres Set zurück"
    )
    assert smtp_refuse.attempts == 0, (
        "E-Mail versucht, obwohl send_email=False in report_config"
    )


# ───────────────────────── F001: SMTP-Guard ──────────────────────────────────

def test_telegram_only_user_without_smtp_still_gets_alert(telegram_sink, tmp_path):
    """F001: Telegram-only-Nutzer ohne SMTP-Konfiguration bekommt seinen Alert.

    Früher: can_send_email()==False → sofortiges return False (SMTP-Guard).
    Nach Fix: Guard prüft BEIDE Kanäle; Telegram-only ist ein gültiger Pfad.
    """
    # Settings NUR mit Telegram — kein smtp_host → can_send_email() == False
    settings = Settings(
        smtp_host="",
        smtp_user="",
        smtp_pass="",
        mail_to="",
        mail_from="",
        telegram_bot_token="test-token",
        telegram_chat_id="test-chat",
    )
    rule = _wind_rule(AlertSeverity.WARNING, channels=["telegram"])
    trip = _trip(rule, report_config=None)

    # State-Bereinigung für Idempotenz (Issue #816: alert_state persistiert;
    # alert_daily_count.json zusaetzlich seit #1070, siehe Kommentar oben).
    _reset_alert_state("tdd-638-f001")

    from services.trip_alert import TripAlertService
    service = TripAlertService(settings=settings, user_id="tdd-638-f001")
    cached = [_data(gust_max_kmh=25.0)]   # Δ=35 > MetricCatalog-Schwelle 20
    fresh = [_data(gust_max_kmh=60.0)]
    result = service.check_and_send_alerts(trip, cached, fresh_weather=fresh)

    assert result is True, (
        "Telegram-only-Nutzer: check_and_send_alerts muss True liefern — SMTP-Guard zu früh"
    )
    assert telegram_sink.send_count() == 1, (
        "Telegram-Nachricht wurde nicht zugestellt"
    )


# ───────────────────────── F001: Alle Kanäle abgeschaltet ────────────────────

def test_f001_all_channels_off_sends_nothing(telegram_sink, smtp_refuse, tmp_path):
    """F001: report_config existiert mit send_email=False, send_telegram=False (alle Kanäle aus).

    Trip hat KEINE aktiven alert_rules (Legacy-Pfad).
    Schwelle wird gerissen → _effective_alert_channels darf KEINEN Alert versenden.

    Vor dem Fix: briefing={} → "briefing if briefing else {'email'}" → {'email'}
                 → SMTPRefuse wird kontaktiert (attempts >= 1) → Test SCHLÄGT FEHL.
    Nach dem Fix: report_config is not None → kein E-Mail-Default →
                  → kein SMTP-Versuch, kein Telegram-Versand.
    """
    report_config = TripReportConfig(
        trip_id="tdd-638-alloff-trip",
        send_email=False,
        send_telegram=False,
        alert_on_changes=True,
    )
    stage = Stage(
        id="T1", name="Tag 1", date=date.today(),
        waypoints=[Waypoint(id="G1", name="Start", lat=47.0, lon=11.0, elevation_m=1000.0)],
    )
    trip = Trip(id="tdd-638-alloff-trip", name="All Channels Off Trip", stages=[stage])
    trip.alert_rules = []  # keine aktiven Regeln → Legacy-Pfad
    trip.report_config = report_config

    from services.trip_alert import TripAlertService
    service = TripAlertService(settings=_settings(smtp_refuse.port), user_id="tdd-638-alloff")
    # Delta gross genug → Change wird erkannt (Legacy-Detektor)
    cached = [_data(gust_max_kmh=30.0)]
    fresh = [_data(gust_max_kmh=60.0)]
    service.check_and_send_alerts(trip, cached, fresh_weather=fresh)

    assert smtp_refuse.attempts == 0, (
        "E-Mail-Default feuerte obwohl report_config existiert mit send_email=False — "
        "E-Mail-Default darf nur bei report_config=None greifen"
    )
    assert telegram_sink.send_count() == 0, (
        "Telegram-Alert versendet obwohl send_telegram=False — alle Kanäle sollten aus sein"
    )

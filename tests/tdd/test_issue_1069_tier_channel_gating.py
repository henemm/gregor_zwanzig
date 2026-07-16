"""TDD RED — Issue #1069: Channel-Gating nach Nutzerlevel (Slice 2, Epic #1067).

SPEC: docs/specs/modules/issue_1069_tier_channel_gating.md

Abgedeckt in dieser Datei (KEINE Mocks — echte Objekte, echter lokaler
HTTP-Sink statt seven.io, echte Staging-HTTP-/Playwright-Calls):

- AC-1: Nutzer mit Level `free` (kein tier-Feld) + `send_sms=True` -> keine
  SMS wird tatsächlich verschickt (lokaler SMS-Stub bleibt leer).
- AC-2: Nutzer mit Level `standard` + `send_sms=True` -> SMS wird wie gewohnt
  verschickt (Zwei-Nutzer-Regressionsschutz gegen Generalsperre). Diese
  Assertion ist bereits vor der Implementierung erfüllt (Altverhalten war nie
  restriktiv) — sie dient als Guard, nicht als RED-Beweis.
- AC-7: Bestandsnutzer ganz ohne tier-Feld verhält sich wie `free`.
- Direkter Unit-Test für das neue Modul `services.user_tier` (`sms_allowed`).
- AC-3 (Profile-API `sms_allowed`-Feld) ist bereits durch den Go-Test
  `internal/handler/profile_test.go::TestGetProfileHandlerSmsAllowedField`
  abgedeckt — hier nicht dupliziert.
- AC-4/AC-5/AC-6 (Frontend-Hinweistext-Priorität, Premium-SMS-Slot):
  Playwright gegen Staging, mit den bereits aus Slice 1 (#1068) bestehenden
  Testnutzern `tdd-1068-free` / `tdd-1068-std`.

RED-Ursache:
- `src.services.user_tier` existiert noch nicht (ImportError).
- `trip_report_scheduler.py` prüft an beiden Enforcement-Stellen
  (Zeilen ~623, ~835) nur `config.send_sms`, ohne Tier-Kenntnis.
- Frontend zeigt weder Level-Hinweis noch Premium-SMS-Slot.
"""
from __future__ import annotations

import http.server
import json
import shutil
import threading
import time
import urllib.parse
import uuid
from datetime import datetime, timedelta, date, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
import pytest

from app.loader import get_data_dir
from tests.helpers.staging_auth import httpx_auth, playwright_http_credentials, staging_base_url

STAGING = staging_base_url()
API = STAGING


# ---------------------------------------------------------------------------
# Lokaler SMS-Stub (kein Mock — echter HTTP-Server, Vorbild: test_issue_936_sms_stub.py)
# ---------------------------------------------------------------------------

class _SMSStub:
    """Lokaler HTTP-Stub für seven.io — empfängt den echten HTTP-POST von SMSOutput.send()."""

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

        import socket
        s = socket.socket()
        s.bind(("", 0))
        self.port = s.getsockname()[1]
        s.close()
        self._server = http.server.HTTPServer(("127.0.0.1", self.port), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._server.shutdown()

    def sms_sent(self) -> bool:
        return len(self.received) > 0


@pytest.fixture()
def sms_stub():
    stub = _SMSStub()
    yield stub
    stub.stop()


@pytest.fixture()
def clean_user_dirs():
    """Räumt echte data/users/tdd-1069-*-Verzeichnisse vor und nach dem Test."""
    created: list[str] = []

    def _register(user_id: str) -> str:
        created.append(user_id)
        path = get_data_dir(user_id)
        if path.exists():
            shutil.rmtree(path)
        return user_id

    yield _register

    for user_id in created:
        path = get_data_dir(user_id)
        if path.exists():
            shutil.rmtree(path)


def _write_user_json(user_id: str, tier: str | None) -> None:
    path = get_data_dir(user_id)
    path.mkdir(parents=True, exist_ok=True)
    data = {"id": user_id}
    if tier is not None:
        data["tier"] = tier
    (path / "user.json").write_text(json.dumps(data))


def _stub_settings(port: int, user_id: str):
    from app.config import Settings
    return Settings().with_user_profile(user_id).model_copy(update={
        "sms_gateway_url": f"http://127.0.0.1:{port}/api/sms",
        "seven_api_key": "test-stub-key",
        "sms_to": "+49000000000",
        "sms_from": None,
    })


def _make_segment_data():
    from app.models import (
        ForecastDataPoint, ForecastMeta, GPXPoint, NormalizedTimeseries,
        Provider, SegmentWeatherData, SegmentWeatherSummary, TripSegment,
    )
    points = [
        ForecastDataPoint(
            ts=datetime(2026, 5, 1, 9 + h, 0, tzinfo=timezone.utc),
            t2m_c=15.0 + h, wind10m_kmh=10.0 + h, gust_kmh=22.0 + h,
            pop_pct=40, precip_1h_mm=0.4, wind_chill_c=12.0 + h, cloud_total_pct=55,
        )
        for h in range(6)
    ]
    meta = ForecastMeta(
        provider=Provider.OPENMETEO, model="icon_d2",
        run=datetime(2026, 5, 1, 0, 0, tzinfo=timezone.utc),
        grid_res_km=2.0, interp="point_grid",
    )
    ts = NormalizedTimeseries(meta=meta, data=points)
    seg = TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=42.2, lon=9.05, elevation_m=400.0),
        end_point=GPXPoint(lat=42.25, lon=9.09, elevation_m=1200.0),
        start_time=datetime(2026, 5, 1, 9, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 5, 1, 13, 0, tzinfo=timezone.utc),
        duration_hours=4.0, distance_km=8.0, ascent_m=800.0, descent_m=0.0,
    )
    agg = SegmentWeatherSummary(
        temp_min_c=15.0, temp_max_c=20.0, temp_avg_c=17.5,
        wind_max_kmh=16.0, gust_max_kmh=28.0, precip_sum_mm=2.4, cloud_avg_pct=55,
    )
    return SegmentWeatherData(
        segment=seg, timeseries=ts, aggregated=agg,
        fetched_at=datetime.now(timezone.utc), provider="openmeteo",
    )


def _make_trip(trip_id: str, send_sms: bool):
    from app.trip import Stage, Trip, Waypoint
    from app.models import TripReportConfig
    stage = Stage(
        id="S1", name="Etappe 1", date=date.today() + timedelta(days=1),
        waypoints=[
            Waypoint(id="W1", name="Start", lat=42.2, lon=9.05, elevation_m=400),
            Waypoint(id="W2", name="Ziel", lat=42.25, lon=9.09, elevation_m=1200),
        ],
    )
    return Trip(
        id=trip_id, name=f"Test1069 {trip_id}", stages=[stage],
        report_config=TripReportConfig(
            trip_id=trip_id, send_email=False, send_sms=send_sms, send_telegram=False,
        ),
    )


def _build_request_and_send(user_id: str, send_sms_config: bool, stub_port: int):
    """Ruft die echte Scheduler-Builder-Methode auf und versendet über den echten
    NotificationService-Pfad (SMS via lokalem Stub, E-Mail/Telegram deaktiviert)."""
    from services.trip_report_scheduler import TripReportSchedulerService
    from services.notification_service import NotificationService

    settings = _stub_settings(stub_port, user_id)
    scheduler = TripReportSchedulerService(settings=settings, user_id=user_id)
    trip = _make_trip(f"trip-{user_id}", send_sms=send_sms_config)
    seg = _make_segment_data()

    request = scheduler._build_trip_report_request(
        trip=trip,
        report_type="evening",
        segment_weather=[seg],
        trip_tz=ZoneInfo("Europe/Vienna"),
        stage_name=None,
        stage_stats=None,
        night_weather=None,
        thunder_forecast=None,
        multi_day_trend=None,
        stability_result=None,
        daylight_window=None,
        day_comparison=None,
        exposed_sections=[],
        allow_test_fallback=False,
        on_demand=False,
        catchup_prefix=None,
    )

    notifier = NotificationService(settings=settings, user_id=user_id)
    notifier.send_trip_report(request)
    return request


# ---------------------------------------------------------------------------
# AC-1: Free-Tier (kein tier-Feld) blockiert SMS serverseitig
# ---------------------------------------------------------------------------

class TestAC1FreeTierBlocksSms:
    """
    GIVEN: Trip mit send_sms=True, Besitzer ohne tier-Feld (= free)
    WHEN:  Report-Versand ausgelöst (echter Aufruf von
           TripReportSchedulerService._build_trip_report_request +
           NotificationService.send_trip_report)
    THEN:  Es wird KEINE SMS tatsächlich verschickt (lokaler Stub bleibt leer)
    """

    def test_free_tier_user_gets_no_sms(self, clean_user_dirs, sms_stub) -> None:
        user_id = clean_user_dirs("tdd-1069-free")
        _write_user_json(user_id, tier=None)  # kein tier-Feld -> Default free

        request = _build_request_and_send(user_id, send_sms_config=True, stub_port=sms_stub.port)

        assert request.send_sms is False, (
            "RED: Enforcement fehlt — _build_trip_report_request liefert send_sms=True "
            "trotz Level 'free'. src/services/trip_report_scheduler.py muss den Tier-Check "
            "einbauen (Zeile ~835)."
        )
        assert not sms_stub.sms_sent(), (
            "RED: Trotz Level 'free' wurde tatsächlich eine SMS an den Versandpfad "
            "übergeben und beim lokalen SMS-Stub empfangen."
        )


# ---------------------------------------------------------------------------
# AC-2: Standard-Tier bleibt funktionsfähig (Regressionsschutz)
# ---------------------------------------------------------------------------

class TestAC2StandardTierKeepsSms:
    """
    GIVEN: Trip mit send_sms=True, Besitzer mit tier="standard"
    WHEN:  Derselbe Versand-Trigger wie AC-1
    THEN:  SMS wird verschickt — die AC-1-Sperre darf nicht generalisieren
    """

    def test_standard_tier_user_still_gets_sms(self, clean_user_dirs, sms_stub) -> None:
        user_id = clean_user_dirs("tdd-1069-std")
        _write_user_json(user_id, tier="standard")

        request = _build_request_and_send(user_id, send_sms_config=True, stub_port=sms_stub.port)

        assert request.send_sms is True
        assert sms_stub.sms_sent(), (
            "Standard-Nutzer muss weiterhin SMS bekommen können — keine Generalsperre."
        )


# ---------------------------------------------------------------------------
# AC-7: Bestandsnutzer ohne tier-Feld verhält sich exakt wie free
# ---------------------------------------------------------------------------

class TestAC7MissingTierFieldBehavesAsFree:
    """
    GIVEN: user.json ganz ohne tier-Feld (Alt-Account vor Epic #1067)
    WHEN:  Report-Versand + sms_allowed()-Lookup
    THEN:  Verhalten identisch zu explizitem tier="free" — kein impliziter
           Premium-Zugriff durch das fehlende Feld
    """

    def test_missing_tier_field_equals_free(self, clean_user_dirs, sms_stub) -> None:
        user_id = clean_user_dirs("tdd-1069-notier")
        path = get_data_dir(user_id)
        path.mkdir(parents=True, exist_ok=True)
        (path / "user.json").write_text(json.dumps({"id": user_id}))  # explizit ohne "tier"

        from services.user_tier import sms_allowed
        assert sms_allowed(user_id) is False, (
            "RED: services/user_tier.py existiert noch nicht oder liefert True für "
            "fehlendes tier-Feld."
        )

        request = _build_request_and_send(user_id, send_sms_config=True, stub_port=sms_stub.port)
        assert request.send_sms is False
        assert not sms_stub.sms_sent()


# ---------------------------------------------------------------------------
# Direkter Unit-Test: services.user_tier.sms_allowed()
# ---------------------------------------------------------------------------

class TestUserTierModule:
    """Reines Datei-basiertes Verhalten des neuen Moduls, ohne Versandpfad."""

    def test_sms_allowed_matches_tier_table(self, clean_user_dirs) -> None:
        from services.user_tier import sms_allowed

        free_id = clean_user_dirs("tdd-1069-tier-free")
        std_id = clean_user_dirs("tdd-1069-tier-std")
        prem_id = clean_user_dirs("tdd-1069-tier-prem")
        unknown_id = clean_user_dirs("tdd-1069-tier-nofile")

        _write_user_json(free_id, tier="free")
        _write_user_json(std_id, tier="standard")
        _write_user_json(prem_id, tier="premium")
        # unknown_id: bewusst KEIN user.json angelegt (Datei fehlt komplett)

        assert sms_allowed(free_id) is False
        assert sms_allowed(std_id) is True
        assert sms_allowed(prem_id) is True
        assert sms_allowed(unknown_id) is False, (
            "Fehlende user.json darf nicht versehentlich SMS erlauben."
        )


# ---------------------------------------------------------------------------
# AC-8 (Nachtrag, Adversary-Fund F001): Tier-Gate auch im Alert-Dispatch-Pfad
# (src/services/trip_alert.py) — nicht nur im Scheduler-Report-Pfad.
# ---------------------------------------------------------------------------

def _make_alert_trip(trip_id: str, send_sms: bool, rule_channels: list[str] | None = None):
    """Trip fuer TripAlertService._effective_alert_channels() — reine
    Kanal-Berechnung, braucht KEIN aktives Zeitfenster/Wetter (pure-ish Methode,
    liest nur trip.report_config + trip.alert_rules)."""
    from app.trip import Stage, Trip, Waypoint
    from app.models import AlertRule, AlertRuleKind, AlertMetric, AlertSeverity, TripReportConfig

    stage = Stage(
        id="S1", name="Etappe 1", date=date.today() + timedelta(days=1),
        waypoints=[
            Waypoint(id="W1", name="Start", lat=42.2, lon=9.05, elevation_m=400),
            Waypoint(id="W2", name="Ziel", lat=42.25, lon=9.09, elevation_m=1200),
        ],
    )
    rules = []
    if rule_channels is not None:
        rules.append(AlertRule(
            id="r1", kind=AlertRuleKind.ABSOLUTE, metric=AlertMetric.WIND_GUST,
            threshold=50.0, severity=AlertSeverity.WARNING, enabled=True,
            channels=rule_channels,
        ))
    return Trip(
        id=trip_id, name=f"AlertTrip {trip_id}", stages=[stage], alert_rules=rules,
        report_config=TripReportConfig(trip_id=trip_id, send_email=False, send_sms=send_sms, send_telegram=False),
    )


class TestAC8AlertChannelsRespectTier:
    """
    GIVEN: Trip mit send_sms=True (Briefing-Vererbung) BZW. einer Alert-Regel
           mit explizitem channels=["sms"], Besitzer mit Level free
    WHEN:  TripAlertService._effective_alert_channels(trip) berechnet wird
    THEN:  "sms" ist NICHT im zurückgegebenen Kanal-Set — weder über die
           geerbten Briefing-Kanäle noch über die explizite Regel
    """

    def test_free_tier_briefing_inherited_sms_is_stripped(self, clean_user_dirs) -> None:
        from services.trip_alert import TripAlertService
        from app.config import Settings

        user_id = clean_user_dirs("tdd-1069-alert-free")
        _write_user_json(user_id, tier=None)
        trip = _make_alert_trip("trip-alert-free", send_sms=True)

        svc = TripAlertService(settings=Settings().with_user_profile(user_id), user_id=user_id)
        channels = svc._effective_alert_channels(trip)

        assert "sms" not in channels, (
            "RED: free-Tier — 'sms' darf nicht im Alert-Kanal-Set stehen, obwohl "
            "report_config.send_sms=True (Briefing-Vererbung). "
            "_effective_alert_channels() in trip_alert.py prüft noch keinen Tier-Gate."
        )

    def test_free_tier_explicit_rule_channel_sms_is_stripped(self, clean_user_dirs) -> None:
        """Direkterer Bypass: Regel setzt channels=['sms'] explizit, unabhängig
        von report_config.send_sms."""
        from services.trip_alert import TripAlertService
        from app.config import Settings

        user_id = clean_user_dirs("tdd-1069-alert-free-rule")
        _write_user_json(user_id, tier="free")
        trip = _make_alert_trip("trip-alert-free-rule", send_sms=False, rule_channels=["sms"])

        svc = TripAlertService(settings=Settings().with_user_profile(user_id), user_id=user_id)
        channels = svc._effective_alert_channels(trip)

        assert "sms" not in channels, (
            "RED: explizites alert_rules[].channels=['sms'] umgeht den Tier-Gate komplett — "
            "muss auch bei free-Tier gefiltert werden."
        )

    def test_standard_tier_keeps_sms_in_both_paths(self, clean_user_dirs) -> None:
        """Regressions-Guard: standard-Tier bleibt in beiden Pfaden funktionsfähig."""
        from services.trip_alert import TripAlertService
        from app.config import Settings

        user_id = clean_user_dirs("tdd-1069-alert-std")
        _write_user_json(user_id, tier="standard")

        trip_briefing = _make_alert_trip("trip-alert-std-briefing", send_sms=True)
        trip_rule = _make_alert_trip("trip-alert-std-rule", send_sms=False, rule_channels=["sms"])

        svc = TripAlertService(settings=Settings().with_user_profile(user_id), user_id=user_id)

        assert "sms" in svc._effective_alert_channels(trip_briefing)
        assert "sms" in svc._effective_alert_channels(trip_rule)


def _active_window_now(lat: float, lon: float):
    """Lokales Zeitfenster, das jetzt aktiv ist (Vorbild: test_952_onset_alert_fidelity.py
    ``_active_window`` — verhindert, dass das Segment zur Testlaufzeit inaktiv ist)."""
    from datetime import time as time_type
    from utils.timezone import tz_for_coords

    tz = tz_for_coords(lat, lon)
    now_local = datetime.now(tz)
    start = now_local - timedelta(hours=1)
    end = now_local + timedelta(hours=3)
    day_start = now_local.replace(hour=2, minute=0, second=0, microsecond=0)
    day_end = now_local.replace(hour=22, minute=0, second=0, microsecond=0)
    if start < day_start:
        start = day_start
    if end > day_end:
        end = day_end
    if start > now_local:
        start = now_local
    if end <= now_local:
        end = now_local + timedelta(hours=1)
    return start.strftime("%H:%M"), end.strftime("%H:%M"), time_type(start.hour, start.minute)


def _make_radar_trip(trip_id: str, send_sms: bool):
    """Trip mit garantiert aktivem Segment JETZT (Vorbild:
    test_952_onset_alert_fidelity.py ``_trip_with_active_segment``)."""
    from datetime import time as time_type
    from app.trip import Stage, TimeWindow, Trip, Waypoint
    from app.models import TripReportConfig

    lat, lon = 42.20, 9.10
    start_str, end_str, start_time = _active_window_now(lat, lon)
    wp0 = Waypoint(
        id="G1", name="Start", lat=lat, lon=lon, elevation_m=1000.0,
        time_window=TimeWindow(start=time_type(0, 0), end=time_type(23, 57)),
        arrival_override=start_str,
    )
    wp1 = Waypoint(
        id="G2", name="Ziel", lat=42.25, lon=9.15, elevation_m=1200.0,
        time_window=TimeWindow(start=time_type(23, 58), end=time_type(23, 59)),
        arrival_override=end_str,
    )
    stage = Stage(id="T1", name="Tag 1", date=date.today(), start_time=start_time, waypoints=[wp0, wp1])
    trip = Trip(id=trip_id, name="Radar-Tier-Trip", stages=[stage])
    trip.report_config = TripReportConfig(
        trip_id=trip_id, send_email=False, send_sms=send_sms, send_telegram=False,
    )
    return trip


class TestAC8RadarAlertRespectsTier:
    """
    GIVEN: Trip mit send_sms=True, garantiert-nassem Radar-Nowcast (Fake-Seam,
           kein Mock), Besitzer mit Level free bzw. standard
    WHEN:  TripAlertService.check_radar_alerts() läuft (echter Dispatch-Pfad)
    THEN:  free-Tier -> keine SMS beim lokalen Stub; standard-Tier -> SMS beim Stub
    """

    def _run(self, user_id: str, tier: str | None, sms_stub) -> bool:
        from services.trip_alert import TripAlertService
        from services.radar_service import NowcastResult, RadarNowcastService
        from app.loader import save_trip

        class _GuaranteedWetRadar(RadarNowcastService):
            def __init__(self) -> None:
                super().__init__()
                self._fixed = NowcastResult(
                    onset_minutes=12, intensity_label="leichter Regen",
                    source="radar", is_convective=False,
                )

            def get_nowcast(self, lat: float, lon: float) -> NowcastResult:
                return self._fixed

        _write_user_json(user_id, tier=tier)
        trip = _make_radar_trip(f"trip-radar-{user_id}", send_sms=True)
        save_trip(trip, user_id=user_id)

        settings = _stub_settings(sms_stub.port, user_id)
        svc = TripAlertService(
            settings=settings, user_id=user_id, radar_service=_GuaranteedWetRadar(),
        )
        svc.check_radar_alerts()
        return sms_stub.sms_sent()

    def test_free_tier_radar_alert_gets_no_sms(self, clean_user_dirs, sms_stub) -> None:
        user_id = clean_user_dirs("tdd-1069-radar-free")
        assert self._run(user_id, tier=None, sms_stub=sms_stub) is False, (
            "RED: free-Tier bekommt trotz Level-Sperre eine Radar-Alert-SMS — "
            "check_radar_alerts() prüft an der inline effective_channels-Stelle "
            "(trip_alert.py ~Zeile 810) noch keinen Tier-Gate."
        )

    def test_standard_tier_radar_alert_still_gets_sms(self, clean_user_dirs, sms_stub) -> None:
        user_id = clean_user_dirs("tdd-1069-radar-std")
        assert self._run(user_id, tier="standard", sms_stub=sms_stub) is True, (
            "standard-Tier muss weiterhin Radar-Alert-SMS bekommen (Regressionsschutz)."
        )


# ---------------------------------------------------------------------------
# AC-4/5/6: Frontend-Hinweistext-Priorität + Premium-SMS-Slot (Playwright/Staging)
# ---------------------------------------------------------------------------

TEST_PASS = "tdd1068testpass"  # identisch zu Slice 1 (#1068) — Testnutzer bereits vorhanden
USER_FREE = "tdd-1068-free"
USER_STANDARD = "tdd-1068-std"


def _login(username: str, password: str) -> httpx.Client:
    client = httpx.Client(base_url=API, timeout=15, follow_redirects=True, auth=httpx_auth())
    resp = client.post("/api/auth/login", json={"username": username, "password": password})
    if resp.status_code != 200:
        pytest.skip(f"Login {username!r} fehlgeschlagen ({resp.status_code}) — Staging nicht erreichbar")
    import re
    sc = resp.headers.get("set-cookie", "")
    m = re.search(r"gz_session=([^;]+)", sc)
    if m:
        client.cookies.set("gz_session", m.group(1))
    return client


def _login_playwright(page, username: str, password: str) -> None:
    import re
    page.goto(f"{STAGING}/login", wait_until="networkidle")
    time.sleep(1)
    page.fill("input[name='username']", username)
    page.fill("input[type='password']", password)
    page.click("button[type='submit']")
    page.wait_for_url(re.compile(rf"^{re.escape(STAGING)}(?!/login)"), timeout=20_000)


def _create_trip(client: httpx.Client, prefix: str) -> str:
    trip_id = f"tdd-1069-{prefix}-" + uuid.uuid4().hex[:6]
    payload = {
        "id": trip_id,
        "name": f"1069 {prefix}",
        "region": "Testgebiet",
        "stages": [{
            "id": "s1", "name": "Etappe 1", "date": "2026-09-01",
            "waypoints": [
                {"id": "w1", "name": "Start", "lat": 46.0, "lon": 9.0, "elevation_m": 500},
                {"id": "w2", "name": "Ziel", "lat": 46.1, "lon": 9.1, "elevation_m": 600},
            ],
        }],
        "alert_rules": [],
    }
    resp = client.post("/api/trips", json=payload)
    assert resp.status_code in (200, 201), f"Trip anlegen: {resp.status_code} {resp.text[:300]}"
    return trip_id


@pytest.fixture(scope="module")
def ensure_frontend_test_fixtures():
    """Setzt Kontaktdaten passend zu AC-4/AC-5: free-Nutzer MIT Handynummer,
    standard-Nutzer OHNE Handynummer — damit der Level-Hinweis bzw. der
    Kontakt-Hinweis jeweils eindeutig geprüft werden kann.

    NICHT autouse: gilt nur für die Playwright/Staging-Testklassen unten
    (als expliziter Fixture-Parameter), sonst würde ein Staging-Login-
    Fehlschlag (z.B. Rate-Limit) auch die rein lokalen Tests überspringen."""
    try:
        client_free = _login(USER_FREE, TEST_PASS)
        client_std = _login(USER_STANDARD, TEST_PASS)
    except httpx.ConnectError:
        pytest.skip("Staging nicht erreichbar — Tests uebersprungen")

    client_free.put("/api/auth/profile", json={"sms_to": "+49123456789"})
    client_std.put("/api/auth/profile", json={"sms_to": None})


class TestAC4LevelHintTakesPriorityOverContactHint:
    """
    GIVEN: free-Nutzer MIT hinterlegter Handynummer
    WHEN:  Trip-Bearbeitungsseite geöffnet wird
    THEN:  SMS-Checkbox deaktiviert, Hinweis "ab Standard verfügbar"
           (NICHT "Handynummer fehlt")
    """

    def test_free_user_sees_level_hint_not_contact_hint(self, ensure_frontend_test_fixtures) -> None:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            pytest.skip("playwright nicht installiert")

        client = _login(USER_FREE, TEST_PASS)
        trip_id = _create_trip(client, "ac4")

        with sync_playwright() as p:
            browser = p.chromium.launch()
            ctx = browser.new_context(http_credentials=playwright_http_credentials())
            page = ctx.new_page()
            try:
                _login_playwright(page, USER_FREE, TEST_PASS)
                page.goto(f"{STAGING}/trips/{trip_id}?tab=briefings", wait_until="networkidle")
                time.sleep(1)

                hint = page.get_by_test_id("channel-sms-hint")
                hint.wait_for(timeout=10_000)
                text = hint.inner_text()
                assert "standard" in text.lower(), (
                    f"RED: erwartet Level-Hinweis ('ab Standard verfügbar'), bekommen: {text!r}"
                )
                assert "handynummer" not in text.lower(), (
                    f"RED: Level-Hinweis muss Vorrang vor Kontakt-Hinweis haben, bekommen: {text!r}"
                )
            finally:
                browser.close()


class TestAC5ContactHintUnchangedForAllowedTier:
    """
    GIVEN: standard-Nutzer OHNE hinterlegte Handynummer
    WHEN:  Trip-Bearbeitungsseite geöffnet wird
    THEN:  Hinweis bleibt "Handynummer fehlt" (Altverhalten unveraendert)
    """

    def test_standard_user_without_contact_sees_contact_hint(self, ensure_frontend_test_fixtures) -> None:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            pytest.skip("playwright nicht installiert")

        client = _login(USER_STANDARD, TEST_PASS)
        trip_id = _create_trip(client, "ac5")

        with sync_playwright() as p:
            browser = p.chromium.launch()
            ctx = browser.new_context(http_credentials=playwright_http_credentials())
            page = ctx.new_page()
            try:
                _login_playwright(page, USER_STANDARD, TEST_PASS)
                page.goto(f"{STAGING}/trips/{trip_id}?tab=briefings", wait_until="networkidle")
                time.sleep(1)

                hint = page.get_by_test_id("channel-sms-hint")
                hint.wait_for(timeout=10_000)
                text = hint.inner_text()
                assert "handynummer" in text.lower(), (
                    f"erwartet unveraendertes 'Handynummer fehlt', bekommen: {text!r}"
                )
            finally:
                browser.close()


class TestAC6PremiumSmsSlotVisibleButDisabled:
    """
    GIVEN: Beliebiger eingeloggter Nutzer
    WHEN:  Trip-Bearbeitungsseite geöffnet wird
    THEN:  Ein sichtbarer, dauerhaft deaktivierter "Premium-SMS"-Menüpunkt ist erkennbar
    """

    def test_premium_sms_slot_visible_and_disabled(self, ensure_frontend_test_fixtures) -> None:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            pytest.skip("playwright nicht installiert")

        client = _login(USER_FREE, TEST_PASS)
        trip_id = _create_trip(client, "ac6")

        with sync_playwright() as p:
            browser = p.chromium.launch()
            ctx = browser.new_context(http_credentials=playwright_http_credentials())
            page = ctx.new_page()
            try:
                _login_playwright(page, USER_FREE, TEST_PASS)
                page.goto(f"{STAGING}/trips/{trip_id}?tab=briefings", wait_until="networkidle")
                time.sleep(1)

                slot = page.get_by_text("Premium-SMS", exact=False)
                assert slot.count() > 0 and slot.first.is_visible(), (
                    "RED: kein sichtbarer 'Premium-SMS'-Menüpunkt gefunden."
                )
                checkbox = page.locator('[data-testid="channel-premium-sms"] input')
                if checkbox.count() > 0:
                    assert checkbox.first.is_disabled(), (
                        "Premium-SMS-Checkbox muss dauerhaft deaktiviert sein."
                    )
            finally:
                browser.close()

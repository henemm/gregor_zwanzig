"""TDD RED — Issue #1169: Ortsvergleich als zweiter Consumer der
Deviation-Alert-Engine (Scheibe 2/3, Epic #1095).

Baut auf Scheibe 1 (#1168, live) auf: `DeviationAlertEngine`,
`PointWeatherData`/`AlertEvaluationConfig`/`LocationWeatherSource` existieren
bereits. Diese Scheibe verdrahtet den Orts-Vergleich (`ComparePreset`) als
zweiten Consumer. Alle Tests folgen der Projektregel „keine Mocks" (CLAUDE.md):

- Echte Preset-/Snapshot-/State-Dateien unter `data/users/<user_id>/`
  (eindeutige tdd-1169-* IDs, Cleanup per try/finally — Vorbild test_773).
- Echte IMAP-Zustellung ins Stalwart-Test-Postfach `gregor-test@henemm.com`
  (Vorbild `test_773_alert_e2e.py::_imap_has_subject_token`).
- Echter lokaler Telegram-HTTP-Sink (echtes Socket, kein `unittest.mock`) —
  beweist, dass Compare-Alerts NIE Telegram bedienen (E-Mail-only, B2).
- Wo Determinismus für zwei aufeinanderfolgende Läufe (AC-2/AC-6) nötig ist,
  wird ein `weather_source`-Konstruktor-Seam auf `CompareAlertService`
  angenommen (analog zum bestehenden `radar_service`-/`mail_sink`-Seam auf
  `TripAlertService`, `trip_alert.py:59-84`) und mit einer selbst gebauten
  Klasse bedient, die das `LocationWeatherSource`-Protocol
  (`services/point_weather.py:67-76`) erfüllt und echte `PointWeatherData`
  zurückgibt — kein `Mock()`/`patch()`, sondern ein Konfigurations-Seam
  analog zu `monkeypatch.setattr(telegram_mod, "TELEGRAM_API_BASE", ...)`
  (siehe `test_issue_816_alert_deviation.py` Docstring-Begründung).

RED-Grund: Die Module `services.compare_alert`,
`services.compare_location_weather_source`, `services.compare_weather_snapshot`
sowie `NotificationService.send_location_deviation_alert()` und
`output.renderers.alert.project.to_point_alert_message()` existieren noch
nicht → ImportError/AttributeError. AC-8 (Python-Teil) schlägt fehl, weil der
Endpoint `POST /api/scheduler/compare-alert-checks` noch nicht registriert
ist (404 statt 200). Der Go-Teil von AC-8 ("7 jobs") wird separat in Phase 6
verifiziert, nicht hier.

SPEC: docs/specs/modules/issue_1169_compare_alert_consumer.md
"""
from __future__ import annotations

import imaplib
import email
import json
import logging
import shutil
import threading
import time
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from app.config import Settings
from app.models import (
    ChangeSeverity,
    GPXPoint,
    SegmentWeatherData,
    SegmentWeatherSummary,
    TripSegment,
    WeatherChange,
)
from app.user import SavedLocation
import output.channels.telegram as telegram_mod

DATA_ROOT = Path(__file__).resolve().parents[2] / "data" / "users"


@pytest.fixture(autouse=True)
def _freeze_deployed_commit(monkeypatch):
    """Issue #1241: Die Herkunfts-Fußzeile (Zeile 2) trägt den Commit-Hash aus
    `helpers._DEPLOYED_COMMIT`. Für den Byte-Gleichheits-Golden in
    `test_ac7_trip_alert_rendering_unchanged` auf einen festen Platzhalter
    einfrieren, sonst bricht die Erwartung nach jedem Commit (analog
    tests/golden/email/conftest.py). Der Renderer liest das Attribut zur Laufzeit
    über `src.output.renderers.email.helpers` — genau dieses Modulobjekt wird
    gepatcht. Für die übrigen Tests ist der Patch wirkungslos."""
    from src.output.renderers.email import helpers as helpers_mod

    monkeypatch.setattr(helpers_mod, "_DEPLOYED_COMMIT", "gitrev0")


# ───────────────────────── echter Telegram-Socket-Sink (kein Mock) ──────────
# 1:1 aus test_issue_1168_alert_engine_extract.py / test_issue_816 übernommen.

class _TelegramSink:
    """Echter HTTP-Server, der Telegram-Bot-API-Aufrufe protokolliert."""

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


@pytest.fixture()
def telegram_sink(monkeypatch):
    sink = _TelegramSink()
    monkeypatch.setattr(telegram_mod, "TELEGRAM_API_BASE", sink.base)
    yield sink
    sink.stop()


# ───────────────────────── Fixtures & Builder ───────────────────────────────

def _clean_user(user_id: str) -> None:
    d = DATA_ROOT / user_id
    if d.exists():
        shutil.rmtree(d)


def _test_settings_email() -> Settings | None:
    """Echte Stalwart-Test-SMTP/IMAP-Settings; None wenn nicht konfiguriert
    (Skip-Grund, kein stiller Erfolg — Vorbild test_773._test_settings)."""
    s = Settings().for_testing()
    if not s.can_send_email():
        return None
    return s


def _settings_email_capable_dummy() -> Settings:
    """`can_send_email() == True` ohne echten Netzwerkzugriff — ausschließlich
    für `mail_sink`-Captures (der mail_sink-Zweig in
    `NotificationService._dispatch_alert_message` ersetzt den SMTP-Versand
    vollständig, siehe notification_service.py:475-489; die dummy-Creds
    werden nie dial't)."""
    return Settings(
        smtp_host="dummy.invalid", smtp_user="dummy", smtp_pass="dummy",
        mail_to="dummy@example.com",
    )


def _location(loc_id: str, name: str, lat: float, lon: float, elevation_m: int = 1000) -> SavedLocation:
    return SavedLocation(id=loc_id, name=name, lat=lat, lon=lon, elevation_m=elevation_m)


def _point(point_id: str, name: str, lat: float, lon: float, precip_sum_mm: float = 0.0,
           provider: str = "test-scripted"):
    """Echtes `PointWeatherData`-DTO (kein Mock) — analog zu `_data()` in
    test_issue_1168/test_issue_816."""
    from services.point_weather import PointWeatherData

    return PointWeatherData(
        id=point_id, name=name, lat=lat, lon=lon, timeseries=None,
        aggregated=SegmentWeatherSummary(precip_sum_mm=precip_sum_mm),
        fetched_at=datetime.now(timezone.utc), provider=provider,
    )


class _ScriptedWeatherSource:
    """Deterministischer `LocationWeatherSource`-Impl (Protocol aus
    `services/point_weather.py:67-76`) — liefert echte `PointWeatherData` aus
    einer vorab festgelegten Werte-Tabelle. KEIN `Mock()`/`patch()`: ein
    Konfigurations-Seam analog zum `_TelegramSink` oben (echtes Objekt,
    reale Rückgabewerte), nötig um AC-2/AC-6 zwei aufeinanderfolgende Läufe
    mit exakt kontrollierten Δ-Werten zu geben (reale Wetter-API liefert
    keine reproduzierbaren Deltas innerhalb eines Testlaufs)."""

    def __init__(self, values: dict[str, float]) -> None:
        self._values = dict(values)

    def fetch(self, point_id: str, lat: float, lon: float):
        return _point(point_id, point_id, lat, lon, precip_sum_mm=self._values.get(point_id, 0.0))

    def set_value(self, point_id: str, precip_sum_mm: float) -> None:
        self._values[point_id] = precip_sum_mm


def _preset(preset_id: str, location_ids: list[str], empfaenger: list[str],
            cooldown_minutes: int | None = 0, name: str | None = None) -> dict:
    """Direktes Compare-Preset-Dict (kein Wrapper) — Vorbild
    `test_issue_461_compare_preset_dispatch.py::_make_preset`. Alarm-Override-
    Felder (`cooldown_minutes`) sind vorwärtskompatibel via `preset.get(feld,
    DEFAULT)` gedacht (Spec B2) — cooldown_minutes=None lässt das Feld weg,
    damit der interne Default (120) greift (AC-6)."""
    preset = {
        "id": preset_id,
        "name": name or preset_id,
        "user_id": "default",
        "location_ids": location_ids,
        "schedule": "manual",
        "weekday": 4,
        "profil": "ALLGEMEIN",
        "hour_from": 9,
        "hour_to": 16,
        "empfaenger": empfaenger,
        "letzter_versand": None,
        "top_ort_letzter_versand": None,
        "created_at": "2026-07-09T00:00:00Z",
    }
    if cooldown_minutes is not None:
        preset["cooldown_minutes"] = cooldown_minutes
    return preset


def _write_preset_file(user_id: str, presets: list[dict]) -> Path:
    path = DATA_ROOT / user_id / "compare_presets.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(presets, ensure_ascii=False), encoding="utf-8")
    return path


def _segment(segment_id: int | str = 1) -> TripSegment:
    """1:1 aus test_issue_1168/test_issue_816 — für den Trip-Regressionstest (AC-7)."""
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


def _imap_has_subject_token(settings: Settings, token: str, *, attempts: int = 12,
                             delay: float = 3.0) -> bool:
    """Poll das Stalwart-Test-Postfach nach einer zugestellten Mail mit `token`
    im Betreff. 1:1 aus `test_773_alert_e2e.py::_imap_has_subject_token`
    übernommen (retries, um SMTP→IMAP-Zustell-Latenz abzufedern)."""
    imap_host = settings.imap_host or settings.smtp_host
    imap_user = settings.imap_user or settings.smtp_user
    imap_pass = settings.imap_pass or settings.smtp_pass
    for _ in range(attempts):
        imap = imaplib.IMAP4_SSL(imap_host, settings.imap_port)
        try:
            imap.login(imap_user, imap_pass)
            imap.select("INBOX")
            _, data = imap.search(None, f'SUBJECT "{token}"')
            if data and data[0].split():
                return True
            _, recent = imap.search(None, "ALL")
            ids = recent[0].split()[-20:]
            for i in reversed(ids):
                _, md = imap.fetch(i, "(BODY[HEADER.FIELDS (SUBJECT)])")
                raw = md[0][1] if md and md[0] else b""
                hdr = raw.decode("utf-8", errors="replace")
                subj = str(email.header.make_header(email.header.decode_header(
                    hdr.split(":", 1)[1].strip() if ":" in hdr else hdr)))
                if token in subj or token in hdr:
                    return True
        finally:
            try:
                imap.logout()
            except Exception:
                pass
        time.sleep(delay)
    return False


# ═══════════════════════════════ AC-1 ════════════════════════════════════════

def test_ac1_compare_deviation_alert_delivered_end_to_end():
    """AC-1: Ort A (Δ ≥ Standard-Schwelle) alarmiert real per Mail an die
    Preset-Empfänger, per IMAP im Stalwart-Test-Postfach nachweisbar; Ort B
    (keine relevante Abweichung) im selben Preset bleibt stumm.

    RED: `services.compare_alert` / `services.compare_weather_snapshot` /
    `services.compare_location_weather_source` existieren noch nicht
    (ImportError).
    """
    settings = _test_settings_email()
    if settings is None:
        pytest.skip("SMTP nicht konfiguriert — realer E-Mail-E2E nicht möglich")

    from services.compare_alert import CompareAlertService
    from services.compare_weather_snapshot import CompareWeatherSnapshotService

    uid = "tdd-1169-ac1"
    _clean_user(uid)
    token = uuid.uuid4().hex[:8]
    preset_id = f"cp-1169-{token}"
    try:
        from app.loader import save_location

        loc_a = _location("loc-a", f"OrtAlarm-{token}", 47.05, 11.40)
        loc_b = _location("loc-b", f"OrtStumm-{token}", 47.10, 11.45)
        save_location(loc_a, user_id=uid)
        save_location(loc_b, user_id=uid)

        _write_preset_file(uid, [_preset(preset_id, ["loc-a", "loc-b"], ["gregor-test@henemm.com"])])

        snap_svc = CompareWeatherSnapshotService(user_id=uid)
        snap_svc.save(preset_id, "loc-a", _point("loc-a", loc_a.name, loc_a.lat, loc_a.lon, precip_sum_mm=2.0))
        snap_svc.save(preset_id, "loc-b", _point("loc-b", loc_b.name, loc_b.lat, loc_b.lon, precip_sum_mm=2.0))

        # Ort A: Δ=16 ≥ Standard-Schwelle 10 (identisches Regen-Szenario wie
        # test_issue_1168/test_issue_816). Ort B: Δ=0 → stumm.
        weather_source = _ScriptedWeatherSource({"loc-a": 18.0, "loc-b": 2.0})

        service = CompareAlertService(settings=settings, user_id=uid, weather_source=weather_source)
        sent = service.check_all_compare_presets()

        assert sent == 1, f"Erwartete genau 1 Alarm (Ort A), erhalten: {sent}"
        assert _imap_has_subject_token(settings, token), (
            f"Deviation-Alert-Mail mit Token {token!r} nicht im Test-Postfach gefunden — "
            "keine echte Zustellung."
        )
    finally:
        _clean_user(uid)


# ═══════════════════════════════ AC-2 ════════════════════════════════════════

def test_ac2_identical_absolute_value_does_not_alarm():
    """AC-2 (ADR-0009): frisches Wetter mit hohem ABSOLUTWERT, das aber
    WERTGLEICH zum Anker ist, löst keinen Alarm aus; erst eine tatsächliche
    Änderung gegenüber dem Anker löst einen Alarm aus.

    RED: `services.compare_alert` / `services.compare_weather_snapshot`
    existieren noch nicht (ImportError).
    """
    from services.compare_alert import CompareAlertService
    from services.compare_weather_snapshot import CompareWeatherSnapshotService
    from app.loader import save_location

    uid = "tdd-1169-ac2"
    _clean_user(uid)
    try:
        loc = _location("loc-x", "Vergleichsort", 47.0, 11.0)
        save_location(loc, user_id=uid)
        preset_id = "cp-1169-ac2"
        _write_preset_file(uid, [_preset(preset_id, ["loc-x"], ["gregor-test@henemm.com"])])

        # Anker: hoher Absolutwert (25 mm) — Δ-Modell (ADR-0009): ein hoher
        # Absolutwert allein darf NIE auslösen.
        CompareWeatherSnapshotService(user_id=uid).save(
            preset_id, "loc-x", _point("loc-x", loc.name, loc.lat, loc.lon, precip_sum_mm=25.0)
        )

        settings = _settings_email_capable_dummy()
        sent_subjects: list[str] = []

        def _sink(subject, body):
            sent_subjects.append(subject)

        # Lauf 1: fresh == Anker (25.0 mm) → kein Alarm trotz hohem Absolutwert.
        ws1 = _ScriptedWeatherSource({"loc-x": 25.0})
        svc1 = CompareAlertService(settings=settings, user_id=uid, weather_source=ws1, mail_sink=_sink)
        first = svc1.check_all_compare_presets()
        assert first == 0, "Wertgleicher Absolutwert darf keinen Alarm auslösen (ADR-0009)"
        assert sent_subjects == []

        # Lauf 2: fresh weicht tatsächlich ab (Δ=16 ≥ Schwelle 10) → Alarm.
        ws2 = _ScriptedWeatherSource({"loc-x": 41.0})
        svc2 = CompareAlertService(settings=settings, user_id=uid, weather_source=ws2, mail_sink=_sink)
        second = svc2.check_all_compare_presets()
        assert second == 1, "Tatsächliche Abweichung vom Anker muss einen Alarm auslösen"
        assert len(sent_subjects) == 1
    finally:
        _clean_user(uid)


# ═══════════════════════════════ AC-3 ════════════════════════════════════════

def test_ac3_two_users_isolated_recipients_and_files():
    """AC-3: zwei Nutzer mit je eigenem Preset/Empfänger/Anker — ein Alarm für
    Nutzer A geht ausschließlich an A's Empfänger; Snapshot-/State-Dateien
    liegen ausschließlich unter `data/users/A/...` bzw. `data/users/B/...`,
    nie ein Fallback auf `"default"`.

    RED: `services.compare_alert` / `services.compare_weather_snapshot`
    existieren noch nicht (ImportError).
    """
    settings = _test_settings_email()
    if settings is None:
        pytest.skip("SMTP nicht konfiguriert — realer E-Mail-E2E nicht möglich")

    from services.compare_alert import CompareAlertService
    from services.compare_weather_snapshot import CompareWeatherSnapshotService
    from app.loader import save_location

    user_a, user_b = "tdd-1169-ac3-a", "tdd-1169-ac3-b"
    _clean_user(user_a)
    _clean_user(user_b)
    token_a, token_b = uuid.uuid4().hex[:8], uuid.uuid4().hex[:8]
    preset_a_id, preset_b_id = f"cp-a-{token_a}", f"cp-b-{token_b}"
    try:
        loc_a = _location("loc-a", f"OrtA-{token_a}", 47.0, 11.0)
        loc_b = _location("loc-b", f"OrtB-{token_b}", 47.2, 11.2)
        save_location(loc_a, user_id=user_a)
        save_location(loc_b, user_id=user_b)

        _write_preset_file(user_a, [_preset(preset_a_id, ["loc-a"], ["gregor-test@henemm.com"])])
        _write_preset_file(user_b, [_preset(preset_b_id, ["loc-b"], ["gregor-test@henemm.com"])])

        CompareWeatherSnapshotService(user_id=user_a).save(
            preset_a_id, "loc-a", _point("loc-a", loc_a.name, loc_a.lat, loc_a.lon, precip_sum_mm=2.0)
        )
        CompareWeatherSnapshotService(user_id=user_b).save(
            preset_b_id, "loc-b", _point("loc-b", loc_b.name, loc_b.lat, loc_b.lon, precip_sum_mm=2.0)
        )

        ws_a = _ScriptedWeatherSource({"loc-a": 18.0})  # Δ=16 → Alarm
        ws_b = _ScriptedWeatherSource({"loc-b": 2.0})   # Δ=0 → kein Alarm

        svc_a = CompareAlertService(settings=settings, user_id=user_a, weather_source=ws_a)
        svc_b = CompareAlertService(settings=settings, user_id=user_b, weather_source=ws_b)
        sent_a = svc_a.check_all_compare_presets()
        sent_b = svc_b.check_all_compare_presets()

        assert sent_a == 1, "Nutzer A muss einen Alarm auslösen (Δ ≥ Schwelle)"
        assert sent_b == 0, "Nutzer B darf keinen Alarm auslösen (Δ=0)"

        assert _imap_has_subject_token(settings, token_a), (
            f"Alarm-Mail für Nutzer A (Token {token_a!r}) nicht zugestellt"
        )
        assert not _imap_has_subject_token(settings, token_b, attempts=2, delay=2.0), (
            f"Cross-User-Leck: Token von Nutzer B ({token_b!r}) wurde zugestellt, "
            "obwohl B keinen Alarm auslösen sollte"
        )

        # Datei-Isolation: A hat einen Alert-State-Eintrag, B nicht — und keine
        # Datei eines Nutzers referenziert die Preset-ID des jeweils anderen.
        a_state_dir = DATA_ROOT / user_a / "alert_state"
        assert a_state_dir.exists() and any(preset_a_id in p.name for p in a_state_dir.iterdir()), (
            "alert_state für Nutzer A wurde nicht geschrieben"
        )
        b_state_dir = DATA_ROOT / user_b / "alert_state"
        if b_state_dir.exists():
            assert not any(preset_b_id in p.name for p in b_state_dir.iterdir()), (
                "Nutzer B hat einen alert_state-Eintrag trotz Δ=0 — falscher Alarm"
            )
        b_snap_dir = DATA_ROOT / user_b / "compare_weather_snapshots"
        if b_snap_dir.exists():
            for p in b_snap_dir.rglob("*"):
                assert preset_a_id not in p.name, "Cross-User-Datenleck A→B im Snapshot-Store"
        a_snap_dir = DATA_ROOT / user_a / "compare_weather_snapshots"
        if a_snap_dir.exists():
            for p in a_snap_dir.rglob("*"):
                assert preset_b_id not in p.name, "Cross-User-Datenleck B→A im Snapshot-Store"
    finally:
        _clean_user(user_a)
        _clean_user(user_b)


# ═══════════════════════════════ AC-4 ════════════════════════════════════════

def test_ac4_snapshot_written_on_report_send_matches_fresh_form():
    """AC-4: ein echter Report-Versand (`send_one_compare_preset()`) schreibt
    je Ort im Preset einen frischen Anker-Snapshot in identischer
    `PointWeatherData`-Form/Provider wie der später gefetchte Fresh-Wert
    (A1: derselbe `LocationWeatherSource`-Impl für Write und Fresh-Fetch) —
    der direkt anschließende Alert-Check schlägt NICHT an (kein künstlicher
    Form-Mismatch-Alarm).

    RED: der Snapshot-Write-Hook in `send_one_compare_preset()` existiert
    noch nicht (`scheduler_dispatch_service.py`) und
    `services.compare_weather_snapshot`/`services.compare_alert` existieren
    noch nicht (ImportError).
    """
    settings = _test_settings_email()
    if settings is None:
        pytest.skip("SMTP nicht konfiguriert — realer E-Mail-E2E nicht möglich")

    from services.compare_alert import CompareAlertService
    from services.compare_weather_snapshot import CompareWeatherSnapshotService
    from services.scheduler_dispatch_service import send_one_compare_preset

    uid = "tdd-1169-ac4"
    _clean_user(uid)
    preset_id = "cp-1169-ac4"
    try:
        # Alpen-Koordinate (GeoSphere-Box) — reale API liefert hier echte Werte.
        loc = _location("loc-alps", "Alpenort", 47.05, 11.40)

        preset = _preset(preset_id, ["loc-alps"], ["gregor-test@henemm.com"])
        settings_report = settings.model_copy(update={"mail_to": "gregor-test@henemm.com"})

        send_one_compare_preset(preset, settings_report, uid, "data", all_locations_cache=[loc])

        snap = CompareWeatherSnapshotService(user_id=uid).load(preset_id, "loc-alps")
        assert snap, "Kein Anker-Snapshot nach Report-Versand geschrieben"
        point = snap[0]
        assert point.id == "loc-alps"
        assert point.timeseries is not None, (
            "Snapshot fehlt eine Zeitreihe — Form-Mismatch zum fresh-Fetch-Pfad "
            "(A1 verlangt denselben LocationWeatherSource-Impl für beide Seiten)"
        )
        assert point.aggregated is not None
        assert point.provider in ("geosphere", "openmeteo"), (
            f"Unerwarteter Provider im Anker-Snapshot: {point.provider!r}"
        )

        # Direkt danach: Alert-Check ohne künstliche Änderung, echter Fresh-Fetch
        # über denselben LocationWeatherSource-Impl (kein weather_source-Override).
        service = CompareAlertService(settings=settings, user_id=uid)
        sent = service.check_all_compare_presets()
        assert sent == 0, (
            "Form- oder Provider-Mismatch zwischen Anker-Snapshot und frischem "
            "Fetch hat einen künstlichen Alarm ausgelöst"
        )
    finally:
        _clean_user(uid)


# ═══════════════════════════════ AC-5 ════════════════════════════════════════

def test_ac5_bootstrap_no_snapshot_no_alarm_no_crash(caplog):
    """AC-5: ein neu angelegtes Preset ohne jemals versendeten Report (kein
    Anker-Snapshot vorhanden) löst beim ersten Alert-Check keinen Alarm aus
    und terminiert ohne Fehler.

    RED: `services.compare_alert` existiert noch nicht (ImportError).
    """
    from services.compare_alert import CompareAlertService
    from app.loader import save_location

    uid = "tdd-1169-ac5"
    _clean_user(uid)
    try:
        loc = _location("loc-new", "Neuer Ort", 47.0, 11.0)
        save_location(loc, user_id=uid)
        preset_id = "cp-1169-ac5"
        _write_preset_file(uid, [_preset(preset_id, ["loc-new"], ["gregor-test@henemm.com"])])
        # KEIN Snapshot geschrieben — Bootstrap-Fall.

        settings = _settings_email_capable_dummy()
        sent_subjects: list[str] = []
        ws = _ScriptedWeatherSource({"loc-new": 99.0})  # hoher Absolutwert, aber kein Anker vorhanden

        service = CompareAlertService(
            settings=settings, user_id=uid, weather_source=ws,
            mail_sink=lambda subject, body: sent_subjects.append(subject),
        )

        with caplog.at_level(logging.ERROR):
            sent = service.check_all_compare_presets()

        assert sent == 0, "Bootstrap (kein Anker-Snapshot) darf keinen Alarm auslösen"
        assert sent_subjects == []
        assert not any(r.levelno >= logging.ERROR for r in caplog.records), (
            f"Unbehandelter Fehler im Bootstrap-Lauf: {[r.getMessage() for r in caplog.records]}"
        )
    finally:
        _clean_user(uid)


# ═══════════════════════════════ AC-6 ════════════════════════════════════════

def test_ac6_cooldown_and_state_dedup_suppress_repeat_email_only_channel(telegram_sink):
    """AC-6: nach einem ausgelösten Alarm (Default-Cooldown 120 Min)
    unterdrückt ein zweiter Lauf innerhalb des Cooldown-Fensters den
    erneuten Versand; Alert-State-Dedup ist zusätzlich belegt; zu keinem
    Zeitpunkt wird Telegram/SMS bedient (E-Mail-only, B2), obwohl Telegram
    technisch konfiguriert ist.

    RED: `services.compare_alert` / `services.compare_weather_snapshot`
    existieren noch nicht (ImportError).
    """
    from services.compare_alert import CompareAlertService
    from services.compare_weather_snapshot import CompareWeatherSnapshotService
    from services.alert_state import AlertStateService
    from app.loader import save_location

    uid = "tdd-1169-ac6"
    _clean_user(uid)
    preset_id = "cp-1169-ac6"
    try:
        loc = _location("loc-cd", "Cooldown-Ort", 47.0, 11.0)
        save_location(loc, user_id=uid)
        # cooldown_minutes bewusst NICHT gesetzt -> interner Default (120) greift.
        _write_preset_file(uid, [_preset(preset_id, ["loc-cd"], ["gregor-test@henemm.com"],
                                          cooldown_minutes=None)])
        CompareWeatherSnapshotService(user_id=uid).save(
            preset_id, "loc-cd", _point("loc-cd", loc.name, loc.lat, loc.lon, precip_sum_mm=2.0)
        )

        settings = _settings_email_capable_dummy().model_copy(update={
            "telegram_bot_token": "test-token", "telegram_chat_id": "test-chat",
        })
        sent_subjects: list[str] = []

        def _sink(subject, body):
            sent_subjects.append(subject)

        ws = _ScriptedWeatherSource({"loc-cd": 18.0})  # Δ=16 ≥ Schwelle 10

        svc1 = CompareAlertService(settings=settings, user_id=uid, weather_source=ws, mail_sink=_sink)
        first = svc1.check_all_compare_presets()
        assert first == 1, "Erster Lauf (kein Cooldown aktiv) muss alarmieren"
        assert len(sent_subjects) == 1

        # Zweiter Lauf mit frischer Service-Instanz (lädt Cooldown-Store von
        # Platte) — liegt real innerhalb des 120-Minuten-Fensters.
        svc2 = CompareAlertService(settings=settings, user_id=uid, weather_source=ws, mail_sink=_sink)
        second = svc2.check_all_compare_presets()
        assert second == 0, "Zweiter Lauf innerhalb des Cooldown-Fensters darf nicht erneut versenden"
        assert len(sent_subjects) == 1, "Cooldown hätte den zweiten Versand unterdrücken müssen"

        # Alert-State-Dedup unabhängig belegt (entity_id = f"{preset_id}:{location_id}").
        state = AlertStateService(user_id=uid).load(f"{preset_id}:loc-cd")
        assert state, "alert_state-Eintrag fehlt nach dem ersten Alarm"

        # Zu keinem Zeitpunkt Telegram bedient, obwohl technisch konfiguriert.
        assert telegram_sink.send_count() == 0, (
            "Compare-Alerts sind E-Mail-only (B2-Default) — Telegram wurde dennoch bedient"
        )
    finally:
        _clean_user(uid)


# ═══════════════════════════════ AC-7 ════════════════════════════════════════

def test_ac7_point_alert_shows_location_name_not_km_zero():
    """AC-7: `to_point_alert_message()` zeigt in Betreff/E-Mail/Telegram den
    Ortsnamen statt der sinnlosen "km 0–0"-Spanne (Punkt hat keinen
    km-Kontext).

    RED: `output.renderers.alert.project.to_point_alert_message` existiert
    noch nicht (AttributeError/ImportError).
    """
    from output.renderers.alert.project import to_point_alert_message
    from output.renderers.alert.render import render_email, render_subject, render_telegram
    from services.point_weather import PointWeatherData

    location_name = "Refuge de Ciottulu"
    point = PointWeatherData(
        id="loc-a", name=location_name, lat=42.3, lon=8.9,
        timeseries=None, aggregated=SegmentWeatherSummary(precip_sum_mm=18.0),
        fetched_at=datetime.now(timezone.utc), provider="openmeteo",
    )
    change = WeatherChange(
        metric="precip_sum_mm", old_value=2.0, new_value=18.0, delta=16.0,
        threshold=10.0, severity=ChangeSeverity.MODERATE, direction="increase",
        segment_id="loc-a",
    )

    msg = to_point_alert_message(
        [change], [point], location_name, tz=ZoneInfo("UTC"), stand_at="14:00",
    )

    subject = render_subject(msg)
    html, plain = render_email(msg)
    telegram_text = render_telegram(msg)

    for text, label in ((subject, "Betreff"), (plain, "E-Mail-Plain"), (telegram_text, "Telegram")):
        assert "km 0" not in text, f"{label} zeigt 'km 0' statt Ortsname:\n{text}"
        assert location_name in text, f"{label} zeigt den Ortsnamen nicht:\n{text}"


def test_ac7_trip_alert_rendering_unchanged():
    """AC-7 Regressions-Schutz (Golden Master, analog test_issue_1168's
    Charakterisierungstests): der Trip-Pfad über `to_alert_message()` setzt
    `location_label` nie und liefert exakt dieselbe Ausgabe wie vor dieser
    Scheibe. Erwartungswerte sind das HEUTIGE (vor #1169), tatsächlich
    ausgeführte Rendering-Ergebnis — dieser Test ist bereits heute grün und
    MUSS es nach der Implementierung bleiben.
    """
    from output.renderers.alert.project import to_alert_message
    from output.renderers.alert.render import render_email, render_subject, render_telegram

    seg = _segment(1)
    seg_data = SegmentWeatherData(
        segment=seg, timeseries=None, aggregated=SegmentWeatherSummary(),
        fetched_at=datetime.now(timezone.utc), provider="openmeteo",
    )
    change = WeatherChange(
        metric="precip_sum_mm", old_value=2.0, new_value=18.0, delta=16.0,
        threshold=10.0, severity=ChangeSeverity.MODERATE, direction="increase",
        segment_id="1",
    )

    msg = to_alert_message([change], [seg_data], "GR20", tz=ZoneInfo("UTC"), stand_at="14:00")
    assert getattr(msg, "location_label", None) is None, (
        "Trip-Pfad darf location_label nie setzen (Regressions-Invariante, AC-7)"
    )

    subject = render_subject(msg)
    html, plain = render_email(msg)
    telegram_text = render_telegram(msg)

    assert subject == "[GR20] km 12–18 · ↑ Niedersch: 2,0 mm→18,0 mm", subject
    assert plain == (
        "Niedersch +800% seit dem Briefing\n\n"
        "↑ +800 % · Änderung über deiner Alarm-Schwelle (10,0 mm)\n\n"
        "Niedersch · mm: 2,0 mm ↑ 18,0 mm +800 %\n"
        "Alarm-Schwelle 10,0 mm: Änderung über ✗\n"
        "Wo & wann: km 12–18\n\n"
        "Stand: heute 14:00 · verglichen mit dem letzten Briefing"
        # Issue #1241: geteilte Herkunfts-Fußzeile (deviation-alert), Commit eingefroren.
        "\n\nAbweichungs-Alarm · alert/render.py · gitrev0"
    ), plain
    assert telegram_text == (
        "<b>GR20 · km 12–18 · ↑ Niedersch</b>\n"
        "Niedersch · Schwelle 10,0 mm · 2,0 mm ↑ 18,0 mm · Änderung über"
    ), telegram_text


# ═══════════════════════════════ AC-8 (Python-Teil) ══════════════════════════

def test_ac8_scheduler_endpoint_scoped_to_user_and_job_registered():
    """AC-8 (Python-Teil): `POST /api/scheduler/compare-alert-checks`
    wertet ausschließlich die Compare-Presets des übergebenen `user_id` aus
    (kein Cross-User-Leck). Der Go-Teil ("7 statt 6 registrierte Jobs") wird
    separat in Phase 6 gegen das laufende Go-Binary verifiziert, nicht hier.

    RED: der Endpoint existiert noch nicht → 404 statt 200.
    """
    from fastapi.testclient import TestClient

    from api.main import app
    from app.loader import save_location

    ua, ub = "tdd-1169-ac8-a", "tdd-1169-ac8-b"
    _clean_user(ua)
    _clean_user(ub)
    try:
        loc_a = _location("loc-a", "Ort-A", 47.0, 11.0)
        loc_b = _location("loc-b", "Ort-B", 47.2, 11.2)
        save_location(loc_a, user_id=ua)
        save_location(loc_b, user_id=ub)
        _write_preset_file(ua, [_preset("cp-a", ["loc-a"], ["gregor-test@henemm.com"])])
        _write_preset_file(ub, [_preset("cp-b", ["loc-b"], ["gregor-test@henemm.com"])])

        client = TestClient(app)
        ra = client.post(f"/api/scheduler/compare-alert-checks?user_id={ua}")
        rb = client.post(f"/api/scheduler/compare-alert-checks?user_id={ub}")

        assert ra.status_code == 200, f"Endpoint nicht erreichbar: {ra.status_code}"
        assert rb.status_code == 200
        assert ra.json().get("status") == "ok"
        assert isinstance(ra.json().get("count"), int)
        assert isinstance(rb.json().get("count"), int)

        # Mandantentrennung: keine Artefakt-Datei unter user_id=ub referenziert
        # das Preset von user_id=ua (kein Cross-User-Datenleck ua→ub).
        b_dir = DATA_ROOT / ub
        if b_dir.exists():
            for p in b_dir.rglob("*"):
                if p.is_file():
                    assert "cp-a" not in p.name, f"Cross-User-Datenleck ua→ub in {p}"
    finally:
        _clean_user(ua)
        _clean_user(ub)

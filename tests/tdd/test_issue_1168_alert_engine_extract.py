"""TDD RED — Issue #1168: Deviation-Alert-Engine location-generisch extrahieren
(Scheibe 1/3, Epic #1095).

Reiner Umbau ohne Verhaltensänderung: `TripAlertService` wird zum dünnen
Adapter, der eine neue, location-generische `DeviationAlertEngine` aufruft.
Diese Testdatei zerfällt in zwei Sorten (KEINE Mocks, CLAUDE.md):

A) Genuin RED — schlagen HEUTE fehl, weil Code/Artefakt fehlt:
   - test_ac3_engine_evaluates_generic_point_data_without_trip:
     `services.deviation_alert_engine` / `services.point_weather` existieren
     noch nicht (ImportError).
   - test_ac5_adr_file_present_and_accepted_by_guard (doc-compliance-test):
     `docs/adr/0021-shared-deviation-alert-engine.md` existiert noch nicht.

B) Charakterisierung / Golden-Master — fixieren das HEUTIGE
   Trip-Alarm-Verhalten über den bestehenden `TripAlertService`-Pfad
   (Vorbild: tests/tdd/test_issue_816_alert_deviation.py: echter lokaler
   Telegram-HTTP-Sink, echter Dateisystem-State). Diese Tests sind schon
   HEUTE grün — ihr Zweck ist, nach der Extraktion weiterhin grün zu
   BLEIBEN (Beweis für bit-identisches Verhalten, AC-1/AC-2/AC-4).

SPEC: docs/specs/modules/issue_1168_alert_engine_extract.md
"""
from __future__ import annotations

import json
import shutil
import threading
from datetime import date, datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from app.config import Settings
from app.models import (
    ForecastMeta,
    GPXPoint,
    NormalizedTimeseries,
    Provider,
    SegmentWeatherData,
    SegmentWeatherSummary,
    TripReportConfig,
    TripSegment,
)
from app.trip import Stage, Trip, Waypoint
import output.channels.telegram as telegram_mod


# ───────────────────────── echter Telegram-Socket-Sink (kein Mock) ──────────

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


# ───────────────────────── Fixtures & Builder ───────────────────────────────

@pytest.fixture()
def telegram_sink(monkeypatch):
    sink = _TelegramSink()
    monkeypatch.setattr(telegram_mod, "TELEGRAM_API_BASE", sink.base)
    yield sink
    sink.stop()


@pytest.fixture()
def clean_user_dirs():
    """Räumt das echte data/users/tdd-1168-*-Verzeichnis vor und nach dem Test."""
    created: list[str] = []

    def _register(user_id: str) -> str:
        created.append(user_id)
        path = Path(f"data/users/{user_id}")
        if path.exists():
            shutil.rmtree(path)
        return user_id

    yield _register

    for user_id in created:
        path = Path(f"data/users/{user_id}")
        if path.exists():
            shutil.rmtree(path)


def _settings_telegram_only() -> Settings:
    """Settings mit Telegram-Kanal (erfüllt can_send_telegram), kein SMTP."""
    return Settings(
        telegram_bot_token="test-token",
        telegram_chat_id="test-chat",
    )


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


def _data(segment_id: int | str = 1, **summary_kwargs) -> SegmentWeatherData:
    return SegmentWeatherData(
        segment=_segment(segment_id),
        timeseries=NormalizedTimeseries(
            meta=ForecastMeta(
                provider=Provider.OPENMETEO,
                model="test",
                grid_res_km=1.0,
            ),
            data=[],
        ),
        aggregated=SegmentWeatherSummary(**summary_kwargs),
        fetched_at=datetime.now(timezone.utc),
        provider="openmeteo",
    )


def _trip(trip_id: str, cooldown_minutes: int = 0) -> Trip:
    """Trip mit Telegram-Briefing-Kanal und aktiver Δ-Regel (precip 'standard').

    1:1 aus test_issue_816_alert_deviation.py::_trip übernommen, damit der
    Golden-Master exakt dasselbe Alarm-Szenario abbildet, das vor dem Umbau
    bereits nachweislich feuert (AC-1).
    """
    from app.models import MetricConfig, UnifiedWeatherDisplayConfig

    stage = Stage(
        id="T1", name="Tag 1", date=date(2026, 4, 5),
        waypoints=[Waypoint(id="G1", name="Start", lat=47.0, lon=11.0, elevation_m=1000.0)],
    )
    trip = Trip(
        id=trip_id, name="Abweichungs-Trip", stages=[stage],
        display_config=UnifiedWeatherDisplayConfig(
            trip_id=trip_id,
            metrics=[MetricConfig(metric_id="precipitation", enabled=True)],
            metric_alert_levels={"precipitation_sum": "standard"},
        ),
    )
    trip.report_config = TripReportConfig(
        trip_id=trip_id,
        send_email=False,
        send_telegram=True,
        alert_on_changes=True,
    )
    trip.alert_cooldown_minutes = cooldown_minutes
    return trip


def _save_briefing_snapshot(user_id: str, trip_id: str, cached: list[SegmentWeatherData]) -> Path:
    """Speichert einen Briefing-Snapshot (Referenz) wie der Scheduler es täte."""
    from services.weather_snapshot import WeatherSnapshotService

    svc = WeatherSnapshotService(user_id=user_id)
    svc.save(trip_id, cached, date(2026, 4, 5))
    return svc._snapshots_dir / f"{trip_id}.json"


# ═══════════════════════ AC-1 (Sorte B: Charakterisierung) ══════════════════
# Bit-identisches Trip-Alarm-Verhalten VOR und NACH der Extraktion — echter
# Trip-Alarm-Durchlauf über TripAlertService.check_and_send_alerts().

def test_ac1_trip_alarm_fires_identically_after_extraction(telegram_sink, clean_user_dirs):
    """AC-1: Regen-Δ reißt die 'standard'-Schwelle (10 mm) → Alarm mit
    identischer Metrik/Severity/Kanal wird versendet. Golden-Master: dieser
    Test ist HEUTE grün und MUSS es nach der Engine-Extraktion bleiben.
    """
    from services.trip_alert import TripAlertService

    user_id = clean_user_dirs("tdd-1168-ac1-fires")
    trip = _trip("trip-1168-ac1-fires")

    cached = [_data(precip_sum_mm=2.0)]
    _save_briefing_snapshot(user_id, trip.id, cached)
    fresh = [_data(precip_sum_mm=18.0)]  # Δ=16 ≥ Schwelle 10 → MAJOR

    service = TripAlertService(settings=_settings_telegram_only(), user_id=user_id)
    sent = service.check_and_send_alerts(trip, cached, fresh_weather=fresh)

    assert sent is True, "Δ=16 ≥ Schwelle 10 muss einen Alarm auslösen"
    assert telegram_sink.send_count() == 1, "genau ein Telegram-Versand erwartet"

    log_path = Path(f"data/users/{user_id}/alert_log.json")
    log = json.loads(log_path.read_text())
    last_entry = log["entries"][-1]
    assert last_entry["trip_id"] == trip.id
    assert last_entry["changes_count"] == 1
    assert last_entry["severity"] == "MODERATE", (
        f"erwartete Severity MODERATE (Δ=16 ist 60% über Schwelle 10, "
        f"1.5x-2.0x-Band), war: {last_entry['severity']}"
    )

    payload = telegram_sink.requests[-1]["payload"]
    text = payload.get("text", "")
    assert "18" in text and "2" in text, (
        f"Alert-Text sollte Vorher/Jetzt-Werte enthalten: {text!r}"
    )


def test_ac1_trip_alarm_stays_silent_identically_after_extraction(telegram_sink, clean_user_dirs):
    """AC-1: Regen-Δ bleibt unter der 'standard'-Schwelle (10 mm) → kein
    Alarm. Golden-Master: dieser Test ist HEUTE grün und MUSS es nach der
    Engine-Extraktion bleiben.
    """
    from services.trip_alert import TripAlertService

    user_id = clean_user_dirs("tdd-1168-ac1-silent")
    trip = _trip("trip-1168-ac1-silent")

    cached = [_data(precip_sum_mm=2.0)]
    _save_briefing_snapshot(user_id, trip.id, cached)
    fresh = [_data(precip_sum_mm=5.0)]  # Δ=3 < Schwelle 10 → kein Alarm

    service = TripAlertService(settings=_settings_telegram_only(), user_id=user_id)
    sent = service.check_and_send_alerts(trip, cached, fresh_weather=fresh)

    assert sent is False, "Δ=3 < Schwelle 10 darf keinen Alarm auslösen"
    assert telegram_sink.send_count() == 0, "kein Telegram-Versand erwartet"


# ═══════════════════════ AC-2 (Sorte B: Charakterisierung) ══════════════════
# Cooldown + Ruhezeiten (inkl. Mitternachts-Wrap) unterdrücken Alarme exakt
# wie vor dem Umbau.

def test_ac2_cooldown_suppresses_second_alert(telegram_sink, clean_user_dirs):
    """AC-2: Zwei echte, unmittelbar aufeinanderfolgende Auswertungsläufe
    innerhalb des konfigurierten Cooldown-Fensters (alert_cooldown_minutes=5)
    → der zweite Lauf löst KEINEN weiteren Versand aus. Kein Zeit-Mock nötig:
    zwei reale Läufe in derselben Test-Ausführung liegen zwangsläufig
    innerhalb eines 5-Minuten-Fensters.
    """
    from services.trip_alert import TripAlertService

    user_id = clean_user_dirs("tdd-1168-ac2-cooldown")
    trip = _trip("trip-1168-ac2-cooldown", cooldown_minutes=5)

    cached = [_data(precip_sum_mm=2.0)]
    _save_briefing_snapshot(user_id, trip.id, cached)
    fresh = [_data(precip_sum_mm=18.0)]  # Δ=16 ≥ Schwelle 10

    service = TripAlertService(settings=_settings_telegram_only(), user_id=user_id)
    first = service.check_and_send_alerts(trip, cached, fresh_weather=fresh)
    assert first is True, "Erster Lauf (kein Cooldown aktiv) muss alerten"
    assert telegram_sink.send_count() == 1

    # Zweiter Lauf, gleicher Service (in-memory Throttle-State), Sekundenbruchteile
    # später — liegt real innerhalb des 5-Minuten-Cooldown-Fensters.
    second = service.check_and_send_alerts(trip, cached, fresh_weather=fresh)
    assert second is False, (
        "Zweiter Lauf innerhalb des Cooldown-Fensters darf keinen Alarm auslösen"
    )
    assert telegram_sink.send_count() == 1, (
        "Cooldown: kein zweiter Telegram-Versand innerhalb des Fensters"
    )

    # Auch ein frischer Service-Instanz (lädt Throttle-Datei von Platte) bleibt
    # innerhalb des Cooldown-Fensters stumm — echter Disk-State, kein Mock.
    service2 = TripAlertService(settings=_settings_telegram_only(), user_id=user_id)
    third = service2.check_and_send_alerts(trip, cached, fresh_weather=fresh)
    assert third is False
    assert telegram_sink.send_count() == 1


def test_ac2_quiet_hours_midnight_wrap_suppresses_alert(telegram_sink, clean_user_dirs):
    """AC-2: Ruhezeiten mit Mitternachts-Wrap (22:00–06:00) unterdrücken den
    Alarm exakt wie vor dem Umbau.

    Teil 1 prüft die reale Entscheidungsfunktion `_is_quiet_hours(trip, now)`
    direkt mit einer festen Uhrzeit im Wrap-Bereich (23:30) — dieselbe
    Methode, die `check_and_send_alerts()` intern mit
    `datetime.now(timezone.utc)` aufruft (kein Mock: echte Methode, echter
    Parameter, den sie bereits entgegennimmt — Vorbild:
    tests/tdd/test_alert_cooldown_quiet.py AC-4/AC-5/AC-6).

    Teil 2 beweist die Unterdrückung End-to-End über den echten
    `check_and_send_alerts()`-Pfad: ein Ruhezeitfenster wird dynamisch um die
    tatsächliche aktuelle Wanduhrzeit gelegt (kein Zeit-Mock), sodass der
    reale Lauf garantiert innerhalb der Ruhezeit stattfindet.
    """
    from services.trip_alert import TripAlertService

    user_id = clean_user_dirs("tdd-1168-ac2-quiet")
    trip = _trip("trip-1168-ac2-quiet")
    trip.alert_quiet_from = "22:00"
    trip.alert_quiet_to = "06:00"

    service = TripAlertService(settings=_settings_telegram_only(), user_id=user_id)

    # Teil 1: reale Entscheidungsfunktion, Mitternachts-Wrap-Zeitpunkt fix.
    wrap_now = datetime(2026, 4, 5, 23, 30, tzinfo=timezone.utc)
    assert service._is_quiet_hours(trip, wrap_now) is True, (
        "23:30 muss innerhalb der Ruhezeit 22:00–06:00 (Mitternachts-Wrap) liegen"
    )

    # Teil 2: End-to-End über check_and_send_alerts(), Ruhezeitfenster dynamisch
    # um die echte aktuelle Uhrzeit gelegt (±1h), kein Zeit-Mock.
    now = datetime.now(timezone.utc)
    quiet_from = (now.replace(second=0, microsecond=0) - timedelta(hours=1)).time()
    quiet_to = (now.replace(second=0, microsecond=0) + timedelta(hours=1)).time()
    trip.alert_quiet_from = quiet_from.strftime("%H:%M")
    trip.alert_quiet_to = quiet_to.strftime("%H:%M")

    cached = [_data(precip_sum_mm=2.0)]
    _save_briefing_snapshot(user_id, trip.id, cached)
    fresh = [_data(precip_sum_mm=18.0)]  # Δ=16 ≥ Schwelle 10 — würde ohne Ruhezeit alerten

    sent = service.check_and_send_alerts(trip, cached, fresh_weather=fresh)
    assert sent is False, "Alarm während konfigurierter Ruhezeit muss unterdrückt werden"
    assert telegram_sink.send_count() == 0, "kein Telegram-Versand während Ruhezeit"


# ═══════════════════════ AC-4 (Sorte B: Charakterisierung) ══════════════════
# Bestehende <trip_id>.json-alert_state-Dateien bleiben nach dem Umbau lesbar.

def test_ac4_legacy_alert_state_file_still_readable(telegram_sink, clean_user_dirs):
    """AC-4: Eine Alt-State-Datei im `<trip_id>.json`-Format (Schema von vor
    dem Umbau) wird nach der Umstellung auf `entity_id` weiterhin korrekt
    gelesen — dieselbe Abweichung gilt als bereits gemeldet, kein erneuter
    Versand.
    """
    from services.trip_alert import TripAlertService

    user_id = clean_user_dirs("tdd-1168-ac4-legacy")
    trip = _trip("trip-1168-ac4-legacy")

    cached = [_data(precip_sum_mm=2.0)]
    _save_briefing_snapshot(user_id, trip.id, cached)

    # Alt-State-Datei manuell ablegen — exakt das Schema, das
    # AlertStateService.save() vor dem Umbau bereits schreibt
    # (data/users/<user_id>/alert_state/<trip_id>.json).
    state_dir = Path(f"data/users/{user_id}/alert_state")
    state_dir.mkdir(parents=True, exist_ok=True)
    legacy_state = {
        "precip_sum_mm:1": {
            "last_reported_value": 18.0,
            "reported_at": datetime.now(timezone.utc).isoformat(),
        }
    }
    (state_dir / f"{trip.id}.json").write_text(json.dumps(legacy_state, indent=2))

    # Frischer Wert identisch zum bereits gemeldeten Wert (18.0) → keine
    # Eskalation (|18-18|=0 < Schwelle 10) → kein erneuter Versand.
    fresh = [_data(precip_sum_mm=18.0)]
    service = TripAlertService(settings=_settings_telegram_only(), user_id=user_id)
    sent = service.check_and_send_alerts(trip, cached, fresh_weather=fresh)

    assert sent is False, (
        "Abweichung, die bereits in der Alt-State-Datei als gemeldet steht, "
        "darf keinen erneuten Alarm auslösen"
    )
    assert telegram_sink.send_count() == 0, (
        "kein Telegram-Versand — die Alt-State-Datei muss als bereits gemeldet erkannt werden"
    )


# ═══════════════════════ AC-3 (Sorte A: Genuin RED) ═════════════════════════
# Die location-generische Engine existiert noch nicht.

def test_ac3_engine_evaluates_generic_point_data_without_trip():
    """AC-3: `DeviationAlertEngine.evaluate()` liefert dieselbe korrekte
    Alarm-Entscheidung wie der äquivalente Trip-Aufruf — direkt mit
    handgebauten `PointWeatherData`/`AlertEvaluationConfig`-Objekten, OHNE
    dass ein `Trip`-Objekt existiert.

    RED: `services.deviation_alert_engine` und `services.point_weather`
    existieren noch nicht → ImportError. Das ist die zentrale RED-Evidenz
    dieser Scheibe (Extraktion location-generischer Kern).
    """
    from services.deviation_alert_engine import DeviationAlertEngine  # noqa: F401 (RED: ImportError)
    from services.point_weather import AlertEvaluationConfig, PointWeatherData  # noqa: F401

    # Generischer Wetterpunkt — Name/Koordinate + Zeitreihe, KEIN Trip-/Stage-/
    # Waypoint-Bezug. Dasselbe Regen-Szenario wie AC-1 (Δ=16 ≥ Schwelle 10).
    cached_point = PointWeatherData(
        id="p1",
        name="Refuge de Ciottulu",
        lat=42.3,
        lon=8.9,
        timeseries=None,
        aggregated=SegmentWeatherSummary(precip_sum_mm=2.0),
        fetched_at=datetime.now(timezone.utc),
        provider="openmeteo",
    )
    fresh_point = PointWeatherData(
        id="p1",
        name="Refuge de Ciottulu",
        lat=42.3,
        lon=8.9,
        timeseries=None,
        aggregated=SegmentWeatherSummary(precip_sum_mm=18.0),
        fetched_at=datetime.now(timezone.utc),
        provider="openmeteo",
    )

    config = AlertEvaluationConfig(
        cooldown_minutes=0,
        quiet_from=None,
        quiet_to=None,
        metric_alert_levels={"precipitation_sum": "standard"},
        channels={"telegram"},
    )

    engine = DeviationAlertEngine()
    result = engine.evaluate(
        cached=[cached_point],
        fresh=[fresh_point],
        config=config,
        alert_state={},
    )

    assert result.triggered is True, (
        "Δ=16 ≥ Schwelle 10 muss auch generisch (ohne Trip) auslösen"
    )
    assert "telegram" in result.channels
    assert any(c.metric == "precip_sum_mm" for c in result.changes)


def test_ac3_engine_evaluates_generic_activation_gap_without_explicit_levels():
    """AC-3 (verschärft, F001-Fix, Adversary Runde 2.2): generischer
    `DeviationAlertEngine.evaluate()`-Aufruf OHNE Trip UND OHNE expliziten
    `metric_alert_levels`-Eintrag, aber mit `display_config`-Auszug in der
    Weather-Tab-„Aktivieren-Lücke"-Konstellation (Issue #961: Metrik ist im
    Weather-Tab aktiv, aber kein `metric_alert_levels`-Eintrag gesetzt) — muss
    identisch zum Trip-Pfad feuern (Δ=16 ≥ Schwelle 10, Regen 2.0→18.0mm).

    War VOR dem F001-Fix rot: `AlertEvaluationConfig` hatte kein
    `display_config`-Feld → der #961-Backfill griff nur Trip-seitig über einen
    `detector=`-Override, NICHT im generischen Engine-Standalone-Pfad →
    `triggered=False` statt `True`.
    """
    from app.models import MetricConfig, UnifiedWeatherDisplayConfig
    from services.deviation_alert_engine import DeviationAlertEngine
    from services.point_weather import AlertEvaluationConfig, PointWeatherData

    cached_point = PointWeatherData(
        id="p1", name="Refuge de Ciottulu", lat=42.3, lon=8.9,
        timeseries=None, aggregated=SegmentWeatherSummary(precip_sum_mm=2.0),
        fetched_at=datetime.now(timezone.utc), provider="openmeteo",
    )
    fresh_point = PointWeatherData(
        id="p1", name="Refuge de Ciottulu", lat=42.3, lon=8.9,
        timeseries=None, aggregated=SegmentWeatherSummary(precip_sum_mm=18.0),
        fetched_at=datetime.now(timezone.utc), provider="openmeteo",
    )

    # Weather-Tab-aktive Metrik OHNE expliziten metric_alert_levels-Eintrag —
    # exakt die #961-„Aktivieren-Lücke"-Konstellation.
    display_config = UnifiedWeatherDisplayConfig(
        trip_id="",
        metrics=[MetricConfig(metric_id="precipitation", enabled=True)],
    )
    config = AlertEvaluationConfig(
        cooldown_minutes=0,
        quiet_from=None,
        quiet_to=None,
        metric_alert_levels=None,  # KEIN expliziter Level-Eintrag
        channels={"telegram"},
        display_config=display_config,
    )

    engine = DeviationAlertEngine()
    result = engine.evaluate(
        cached=[cached_point],
        fresh=[fresh_point],
        config=config,
        alert_state={},
    )

    assert result.triggered is True, (
        "Aktivieren-Lücke (#961): Weather-Tab-aktive Metrik ohne expliziten "
        "metric_alert_levels-Eintrag muss auch generisch (ohne Trip) feuern — "
        "identisch zum äquivalenten Trip-Pfad (TripAlertService.check_and_send_alerts())"
    )
    assert any(c.metric == "precip_sum_mm" for c in result.changes)


# ═══════════════════════ AC-5 (Sorte A: Genuin RED) ══════════════════════════
# doc-compliance-test — prüft ein Artefakt (die ADR-Datei selbst), keine
# Verhaltens-Assertion. Ausnahme laut CLAUDE.md.

def test_ac5_adr_file_present_and_accepted_by_guard():  # doc-compliance-test
    """AC-5: `docs/adr/0021-shared-deviation-alert-engine.md` existiert und
    trägt die ADR-Grundstruktur (Status/Bezug/Kontext/Entscheidung/
    Verworfene Alternativen/Konsequenzen).

    RED: die Datei existiert heute noch nicht.
    """
    adr_path = Path("docs/adr/0021-shared-deviation-alert-engine.md")
    assert adr_path.exists(), f"ADR-Datei fehlt: {adr_path}"

    text = adr_path.read_text()
    assert text.startswith("# ADR-0021"), "ADR muss mit '# ADR-0021' beginnen"
    for required_heading in (
        "## Kontext",
        "## Entscheidung",
        "## Verworfene Alternativen",
        "## Konsequenzen",
    ):
        assert required_heading in text, f"ADR-Abschnitt fehlt: {required_heading}"
    assert "- **Status:**" in text, "ADR-Status-Zeile fehlt"
    assert "#1168" in text, "ADR muss auf Issue #1168 verweisen"

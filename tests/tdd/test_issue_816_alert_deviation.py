"""TDD RED — Issue #816: Alert-Abweichungs-Kern (Epic #813 Slice 1).

Der Forecast-Alert (`check_and_send_alerts`) meldet künftig **Abweichungen
gegenüber dem letzten verschickten Briefing** statt absoluter Schwellen. Diese
Tests beweisen das Verhalten aus Nutzersicht (KEINE Mocks, CLAUDE.md):

- Echter Dateisystem-State unter `data/users/<user_id>/` (eindeutige tdd-816-* IDs,
  Cleanup in Fixture).
- Echter lokaler Telegram-HTTP-Sink (echtes Socket) zählt tatsächliche Versand-Aufrufe
  — kein `unittest.mock`. Monkeypatch von `TELEGRAM_API_BASE` ist ein
  Konfigurations-Seam, kein Mock (Vorbild: test_issue_638_alerts_redesign.py).
- Echte Service-Aufrufe (`TripAlertService`, `WeatherChangeDetectionService`,
  `WeatherSnapshotService`, `AlertStateService`).
- Echtes `build_mime_message`-MIME-Objekt serialisieren und Plain-Part prüfen.

Diese Tests schlagen HEUTE fehl (RED), weil:
- AC-1: `trip_alert.py:160-168` überschreibt den Snapshot nach jedem Alert.
- AC-2/3/4/5: `AlertStateService` (`src/services/alert_state.py`) existiert noch nicht
  (ImportError) und ist nicht in den Alert-/Briefing-Pfad verdrahtet.
- AC-6/7: Der knappe `render_deviation_alert`-Renderer
  (`src/output/renderers/email/alert_compact.py`) und die km-Erweiterung von
  `build_segment_label` existieren noch nicht.
- AC-8: `detect_changes(..., include_absolute=False)` existiert noch nicht.

SPEC: docs/specs/modules/issue_816_alert_deviation_core.md
Test-Manifest: docs/specs/tests/issue_816_alert_deviation_tests.md
"""
from __future__ import annotations

import json
import shutil
import threading
from datetime import date, datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

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
import outputs.telegram as telegram_mod


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
    """Räumt das echte data/users/tdd-816-*-Verzeichnis vor und nach dem Test."""
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


def _trip(trip_id: str) -> Trip:
    """Trip mit Telegram-Briefing-Kanal und aktiver Änderungs-Meldung (kein
    alert_rule → Δ-Detektor aus report_config/Katalog)."""
    stage = Stage(
        id="T1", name="Tag 1", date=date(2026, 4, 5),
        waypoints=[Waypoint(id="G1", name="Start", lat=47.0, lon=11.0, elevation_m=1000.0)],
    )
    trip = Trip(id=trip_id, name="Abweichungs-Trip", stages=[stage])
    trip.report_config = TripReportConfig(
        trip_id=trip_id,
        send_email=False,
        send_telegram=True,
        alert_on_changes=True,
    )
    return trip


def _save_briefing_snapshot(user_id: str, trip_id: str, cached: list[SegmentWeatherData]) -> Path:
    """Speichert einen Briefing-Snapshot (Referenz) wie der Scheduler es täte."""
    from services.weather_snapshot import WeatherSnapshotService

    svc = WeatherSnapshotService(user_id=user_id)
    svc.save(trip_id, cached, date(2026, 4, 5))
    return svc._snapshots_dir / f"{trip_id}.json"


# ═════════════════════════════ AC-1 ═════════════════════════════════════════
# Alert überschreibt den Briefing-Snapshot NICHT mehr.

def test_ac1_alert_does_not_overwrite_briefing_snapshot(
    telegram_sink, clean_user_dirs
):
    """AC-1: Zwei Alert-Läufe lassen den Briefing-Snapshot byte-gleich +
    mtime unverändert. HEUTE überschreibt trip_alert.py:160-168 den Snapshot.
    """
    from services.trip_alert import TripAlertService

    user_id = clean_user_dirs("tdd-816-ac1")
    trip = _trip("trip-ac1")
    trip.alert_cooldown_minutes = 0

    # Briefing-Snapshot = Referenz (Regen 2 mm)
    cached = [_data(precip_sum_mm=2.0)]
    snap_path = _save_briefing_snapshot(user_id, trip.id, cached)
    before_bytes = snap_path.read_bytes()
    before_mtime = snap_path.stat().st_mtime_ns

    # Frischer Wert weicht stark ab (Regen 18 mm, Δ=16 > Katalog-Schwelle 10)
    fresh = [_data(precip_sum_mm=18.0)]
    service = TripAlertService(settings=_settings_telegram_only(), user_id=user_id)
    service.check_and_send_alerts(trip, cached, fresh_weather=fresh)
    service.check_and_send_alerts(trip, cached, fresh_weather=fresh)

    after_bytes = snap_path.read_bytes()
    after_mtime = snap_path.stat().st_mtime_ns

    assert after_bytes == before_bytes, (
        "Briefing-Snapshot wurde im Alert-Pfad überschrieben — Referenz wandert "
        "(trip_alert.py:160-168 muss raus)"
    )
    assert after_mtime == before_mtime, (
        "Snapshot-mtime änderte sich — der Alert-Pfad schreibt den Snapshot noch"
    )


# ═════════════════════════════ AC-2 ═════════════════════════════════════════
# alert_state unterdrückt Wiederholung.

def test_ac2_repeated_same_deviation_is_suppressed(telegram_sink, clean_user_dirs):
    """AC-2: Erster Lauf → Alert + alert_state angelegt. Zweiter Lauf mit
    gleichem frischen Wert → KEIN zweiter Versand (Spam unterdrückt).
    """
    from services.alert_state import AlertStateService  # RED: Modul fehlt
    from services.trip_alert import TripAlertService

    user_id = clean_user_dirs("tdd-816-ac2")
    trip = _trip("trip-ac2")
    # Throttle abschalten, sonst maskiert der Throttle die alert_state-Logik
    trip.alert_cooldown_minutes = 0

    cached = [_data(precip_sum_mm=2.0)]
    _save_briefing_snapshot(user_id, trip.id, cached)
    fresh = [_data(precip_sum_mm=18.0)]

    service = TripAlertService(settings=_settings_telegram_only(), user_id=user_id)
    first = service.check_and_send_alerts(trip, cached, fresh_weather=fresh)
    assert first is True, "Erster Alert sollte versendet werden"
    assert telegram_sink.send_count() == 1, "Erster Lauf: genau ein Telegram-Versand"

    state = AlertStateService(user_id=user_id).load(trip.id)
    assert state, "alert_state wurde nach erstem Alert nicht angelegt"

    # Zweiter Lauf, gleiche Abweichung, frischer Service (lädt alert_state von Platte)
    service2 = TripAlertService(settings=_settings_telegram_only(), user_id=user_id)
    second = service2.check_and_send_alerts(trip, cached, fresh_weather=fresh)

    assert second is False, "Zweiter Alert mit gleicher Δ darf nicht versendet werden"
    assert telegram_sink.send_count() == 1, (
        "Wiederholungs-Spam: zweiter Telegram-Versand trotz unveränderter Abweichung"
    )


# ═════════════════════════════ AC-3 ═════════════════════════════════════════
# Eskalation löst erneut aus + aktualisiert alert_state.

def test_ac3_escalation_triggers_new_alert_and_updates_state(
    telegram_sink, clean_user_dirs
):
    """AC-3: alert_state mit last_reported_value=10 (Regen, Threshold 10).
    Frischer Wert 20 → Δ=10 ≥ Threshold → erneuter Alert, last_reported_value=20.
    """
    from services.alert_state import AlertStateService  # RED: Modul fehlt
    from services.trip_alert import TripAlertService

    user_id = clean_user_dirs("tdd-816-ac3")
    trip = _trip("trip-ac3")
    trip.alert_cooldown_minutes = 0

    # Briefing-Referenz Regen 0 mm
    cached = [_data(precip_sum_mm=0.0)]
    _save_briefing_snapshot(user_id, trip.id, cached)

    # alert_state: zuletzt gemeldet 10 mm für precip_sum_mm auf Segment 1
    state_svc = AlertStateService(user_id=user_id)
    state_svc.save(trip.id, {
        "precip_sum_mm:1": {
            "last_reported_value": 10.0,
            "reported_at": datetime.now(timezone.utc).isoformat(),
        }
    })

    # Frischer Wert 20 → |20 - 10| = 10 ≥ Threshold (Katalog-Default precip 10)
    fresh = [_data(precip_sum_mm=20.0)]
    service = TripAlertService(settings=_settings_telegram_only(), user_id=user_id)
    result = service.check_and_send_alerts(trip, cached, fresh_weather=fresh)

    assert result is True, "Eskalation (Δ ≥ Threshold zum zuletzt gemeldeten Wert) muss alerten"
    assert telegram_sink.send_count() == 1, "Eskalation: genau ein neuer Telegram-Versand"

    updated = AlertStateService(user_id=user_id).load(trip.id)
    assert "precip_sum_mm:1" in updated, "alert_state-Eintrag fehlt nach Eskalation"
    assert updated["precip_sum_mm:1"]["last_reported_value"] == pytest.approx(20.0), (
        "last_reported_value wurde bei Eskalation nicht auf den neuen Wert (20) aktualisiert"
    )


# ═════════════════════════════ AC-4 ═════════════════════════════════════════
# Mandantentrennung: user_a-Alert lässt user_b unberührt.

def test_ac4_alert_state_is_tenant_isolated(telegram_sink, clean_user_dirs):
    """AC-4: Alert für user_a schreibt alert_state NUR unter user_a;
    data/users/user_b/alert_state bleibt unberührt.
    """
    from services.trip_alert import TripAlertService

    user_a = clean_user_dirs("tdd-816-usera")
    user_b = clean_user_dirs("tdd-816-userb")

    trip_a = _trip("trip-a")
    trip_a.alert_cooldown_minutes = 0
    cached = [_data(precip_sum_mm=2.0)]
    _save_briefing_snapshot(user_a, trip_a.id, cached)
    fresh = [_data(precip_sum_mm=18.0)]

    service_a = TripAlertService(settings=_settings_telegram_only(), user_id=user_a)
    service_a.check_and_send_alerts(trip_a, cached, fresh_weather=fresh)

    state_dir_a = Path(f"data/users/{user_a}/alert_state")
    state_dir_b = Path(f"data/users/{user_b}/alert_state")

    assert state_dir_a.exists() and any(state_dir_a.iterdir()), (
        "alert_state für user_a wurde nicht geschrieben"
    )
    assert not (state_dir_b.exists() and any(state_dir_b.iterdir())), (
        "Cross-User-Leck: alert_state für user_b wurde geschrieben"
    )


# ═════════════════════════════ AC-5 ═════════════════════════════════════════
# Briefing-Versand resettet alert_state des Trips.

def test_ac5_briefing_send_resets_alert_state(clean_user_dirs):
    """AC-5: Der Briefing-Versand-Pfad (Snapshot-Save-Block,
    trip_report_scheduler.py:628-633) setzt alert_state des Trips zurück.

    Wir prüfen das beobachtbare Ergebnis: nach dem Briefing-Reset-Hook ist
    AlertStateService.load(trip_id) leer / die Datei nicht vorhanden.
    """
    from services.alert_state import AlertStateService  # RED: Modul fehlt
    from services.trip_report_scheduler import TripReportSchedulerService

    user_id = clean_user_dirs("tdd-816-ac5")
    trip_id = "trip-ac5"

    # Vorbedingung: alert_state mit Eintrag
    state_svc = AlertStateService(user_id=user_id)
    state_svc.save(trip_id, {
        "precip_sum_mm:1": {
            "last_reported_value": 18.0,
            "reported_at": datetime.now(timezone.utc).isoformat(),
        }
    })
    assert AlertStateService(user_id=user_id).load(trip_id), "Vorbedingung nicht erfüllt"

    # Der Reset-Hook hängt am Snapshot-Save-Block des Briefing-Versands. Wir rufen
    # den Reset-Pfad des Schedulers direkt auf (kein echtes SMTP/Provider nötig):
    # nach dem Briefing-Reset MUSS alert_state weg sein.
    scheduler = TripReportSchedulerService(settings=Settings(), user_id=user_id)
    scheduler._reset_alert_state_after_briefing(trip_id)  # RED: Methode fehlt

    after = AlertStateService(user_id=user_id).load(trip_id)
    assert not after, (
        "alert_state wurde beim Briefing-Versand nicht zurückgesetzt"
    )


# ═════════════════════════════ AC-6 ═════════════════════════════════════════
# Knappe Alert-Mail: Kopf, sortierte Vorher→Jetzt-Zeilen mit km, Fußzeile,
# KEINE Briefing-Bestandteile.

def _change(metric: str, old: float, new: float, threshold: float, seg: str = "1") -> WeatherChange:
    delta = new - old
    return WeatherChange(
        metric=metric,
        old_value=old,
        new_value=new,
        delta=delta,
        threshold=threshold,
        severity=ChangeSeverity.MAJOR if abs(delta) >= 2 * threshold else ChangeSeverity.MODERATE,
        direction="increase" if delta > 0 else "decrease",
        segment_id=seg,
    )


def _build_alert_mime(changes, segments, trip_name):
    """Rendert die knappe Abweichungs-Alert-Mail und serialisiert sie als MIME.

    RED: alert_compact.render_deviation_alert existiert noch nicht.
    """
    from output.renderers.alert.render import render_deviation_alert
    from outputs.email import build_mime_message

    html, plain = render_deviation_alert(
        changes=changes,
        segments=segments,
        trip_name=trip_name,
        tz=ZoneInfo("UTC"),
    )
    msg = build_mime_message(
        subject=f"[{trip_name}] Wetter ändert sich seit dem Briefing",
        body=html,
        from_addr="alerts@example.com",
        to_header="hiker@example.com",
        reply_to=None,
        html=True,
        plain_text_body=plain,
        mail_type="deviation-alert",
    )
    return msg


def _plain_part(msg) -> str:
    for part in msg.walk():
        if part.get_content_type() == "text/plain":
            return part.get_payload(decode=True).decode("utf-8")
    raise AssertionError("Keine text/plain-Part in der MIME-Nachricht gefunden")


def test_ac6_deviation_alert_plain_content_sorted_with_km():
    """AC-6: Plain-Part enthält Kopfzeile, Vorher→Jetzt-Zeilen mit km-Angabe,
    Fußzeile; sortiert nach Stärke (|delta|/threshold) — UND KEINE Briefing-Blöcke.
    """
    seg_strong = _segment(segment_id=1)  # km 12–18
    # zweites Segment km 18–24 für die schwächere Abweichung
    seg_weak_segment = TripSegment(
        segment_id=2,
        start_point=GPXPoint(lat=47.1, lon=11.1, elevation_m=1500, distance_from_start_km=18.0),
        end_point=GPXPoint(lat=47.2, lon=11.2, elevation_m=1600, distance_from_start_km=24.0),
        start_time=datetime(2026, 4, 5, 16, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 4, 5, 18, 0, tzinfo=timezone.utc),
        duration_hours=2.0, distance_km=6.0, ascent_m=100, descent_m=0,
    )
    seg_strong_data = SegmentWeatherData(
        segment=seg_strong, timeseries=None,
        aggregated=SegmentWeatherSummary(), fetched_at=datetime.now(timezone.utc),
        provider="openmeteo",
    )
    seg_weak_data = SegmentWeatherData(
        segment=seg_weak_segment, timeseries=None,
        aggregated=SegmentWeatherSummary(), fetched_at=datetime.now(timezone.utc),
        provider="openmeteo",
    )

    # Regen: |delta|/threshold = 16/10 = 1.6 (stärker)
    strong = _change("precip_sum_mm", 2.0, 18.0, 10.0, seg="1")
    # Temp: |delta|/threshold = 6/5 = 1.2 (schwächer)
    weak = _change("temp_max_c", 22.0, 16.0, 5.0, seg="2")

    # Reihenfolge bewusst "schwach zuerst" übergeben → Renderer muss sortieren.
    msg = _build_alert_mime(
        changes=[weak, strong],
        segments=[seg_strong_data, seg_weak_data],
        trip_name="GR20",
    )
    plain = _plain_part(msg)

    # Kopfzeile + Fußzeile
    assert "Wetter ändert sich seit dem Briefing" in plain, "Kopfzeile fehlt"
    assert "verglichen mit dem letzten Briefing" in plain, "Orientierungs-Fußzeile fehlt"
    assert "Stand:" in plain, "Fußzeile ohne 'Stand:'-Zeitangabe"

    # km-Angabe muss in der Segment-Zeile auftauchen
    assert "km 12" in plain, (
        f"km-Bereich der stärksten Abweichung (km 12–18) fehlt:\n{plain}"
    )

    # Sortierung nach Stärke: stärkere Regen-Zeile steht vor der schwächeren Temp-Zeile
    idx_strong = plain.find("18")  # neuer Regenwert
    idx_weak = plain.find("16")    # neuer Temp-Wert
    assert idx_strong != -1 and idx_weak != -1, "Vorher→Jetzt-Werte fehlen im Plain-Text"
    assert idx_strong < idx_weak, (
        "Nicht nach Stärke sortiert: schwächere Abweichung steht vor der stärkeren"
    )

    # KEINE Stundentabelle, KEINE Briefing-Bestandteile
    import re
    assert not re.search(r"\b\d{2}:00\b[^\n]*\b\d{2}:00\b[^\n]*\b\d{2}:00\b", plain), (
        f"Stundentabellen-Muster (mehrere HH:00-Zeilen) in der Alert-Mail:\n{plain}"
    )
    for forbidden in (
        "Nächste Etappen", "Nacht am Ziel", "Vergleich zum Vortag",
        "== Metriken-Ueberblick ==", "Gewitter möglich",
    ):
        assert forbidden not in plain, (
            f"Briefing-Bestandteil '{forbidden}' darf nicht in der Alert-Mail stehen"
        )


def test_ac6_km_fallback_when_distance_zero():
    """AC-6 (km-Fallback): distance_from_start_km == 0.0 → Zeile ohne km,
    aber Etappe + Zeit bleiben erhalten.
    """
    seg = TripSegment(
        segment_id=3,
        start_point=GPXPoint(lat=47.0, lon=11.0, elevation_m=1000, distance_from_start_km=0.0),
        end_point=GPXPoint(lat=47.1, lon=11.1, elevation_m=1500, distance_from_start_km=0.0),
        start_time=datetime(2026, 4, 5, 14, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 4, 5, 16, 0, tzinfo=timezone.utc),
        duration_hours=2.0, distance_km=0.0, ascent_m=0, descent_m=0,
    )
    seg_data = SegmentWeatherData(
        segment=seg, timeseries=None, aggregated=SegmentWeatherSummary(),
        fetched_at=datetime.now(timezone.utc), provider="openmeteo",
    )
    change = _change("precip_sum_mm", 2.0, 18.0, 10.0, seg="3")

    msg = _build_alert_mime(changes=[change], segments=[seg_data], trip_name="GR20")
    plain = _plain_part(msg)

    assert "km 0" not in plain, (
        f"km-Angabe trotz distance_from_start_km == 0.0 gerendert:\n{plain}"
    )
    # Zeit muss bleiben (14:00 als Segment-Start)
    assert "14:00" in plain, (
        f"Segment-Zeit fehlt im km-Fallback-Pfad:\n{plain}"
    )


def test_ac6b_km_shown_when_start_is_zero_but_end_positive():
    """AC-6b (F002-Fix): Tag-1-Start-Segment (km 0→6) zeigt 'km 0' im Label.

    distance_from_start_km=0.0 am Start-Waypoint (Etappe beginnt am Depot)
    ist ein echter Wert, nicht 'unbekannt'. Die falsy-Prüfung `if start_km and
    end_km` verwarf 0.0 als 'kein km'. Korrekt: wenn end_km > 0, km anzeigen.
    """
    seg = TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=47.0, lon=11.0, elevation_m=1000, distance_from_start_km=0.0),
        end_point=GPXPoint(lat=47.1, lon=11.1, elevation_m=1500, distance_from_start_km=6.0),
        start_time=datetime(2026, 4, 5, 8, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 4, 5, 12, 0, tzinfo=timezone.utc),
        duration_hours=4.0, distance_km=6.0, ascent_m=500, descent_m=0,
    )
    seg_data = SegmentWeatherData(
        segment=seg, timeseries=None, aggregated=SegmentWeatherSummary(),
        fetched_at=datetime.now(timezone.utc), provider="openmeteo",
    )
    change = _change("precip_sum_mm", 2.0, 18.0, 10.0, seg="1")

    msg = _build_alert_mime(changes=[change], segments=[seg_data], trip_name="GR20")
    plain = _plain_part(msg)

    assert "km 0" in plain, (
        f"Tag-1-Start-Segment (km 0→6) zeigt 'km 0' nicht im Label:\n{plain}"
    )
    assert "km 0–6" in plain, (
        f"Tag-1-Start-Segment (km 0→6): vollständiges 'km 0–6' fehlt:\n{plain}"
    )


# ═════════════════════════════ AC-7 ═════════════════════════════════════════
# Header X-GZ-Mail-Type: deviation-alert + Validator-No-Op.

def test_ac7_header_set_and_validator_noop():
    """AC-7: Die Mail trägt X-GZ-Mail-Type: deviation-alert und der
    briefing_mail_validator macht für diesen Typ ein No-Op (ok=True).
    """
    seg = _segment(1)
    seg_data = SegmentWeatherData(
        segment=seg, timeseries=None, aggregated=SegmentWeatherSummary(),
        fetched_at=datetime.now(timezone.utc), provider="openmeteo",
    )
    change = _change("precip_sum_mm", 2.0, 18.0, 10.0, seg="1")

    msg = _build_alert_mime(changes=[change], segments=[seg_data], trip_name="GR20")
    assert msg["X-GZ-Mail-Type"] == "deviation-alert", (
        "Marker-Header X-GZ-Mail-Type: deviation-alert fehlt"
    )

    # briefing_mail_validator muss für fremden Typ sauber No-Op machen (ok=True).
    import importlib.util
    validator_path = (
        Path(__file__).resolve().parents[2] / ".claude" / "hooks" / "briefing_mail_validator.py"
    )
    spec = importlib.util.spec_from_file_location("briefing_mail_validator", validator_path)
    validator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(validator)

    ok, _errors = validator.validate_message(msg)
    assert ok is True, (
        "briefing_mail_validator muss für X-GZ-Mail-Type: deviation-alert No-Op "
        "(ok=True) liefern — er ist nur für trip-briefing zuständig"
    )


# ═════════════════════════════ AC-8 ═════════════════════════════════════════
# Im Alert-Pfad werden absolute Regeln NICHT ausgewertet (Δ-only).

def test_ac8_delta_only_detection_excludes_absolute_rules():
    """AC-8: detect_changes(include_absolute=False) liefert KEINE absolute-Rule-
    Changes (direction in {"above","below"}), selbst wenn eine absolute Regel
    den frischen Wert verletzt. RED: das Flag existiert noch nicht.
    """
    from app.models import AlertMetric, AlertRule, AlertRuleKind, AlertSeverity
    from services.weather_change_detection import WeatherChangeDetectionService

    # Absolute Regel: Böen > 50 km/h → würde im Briefing-Pfad feuern.
    abs_rule = AlertRule(
        id="r-gust",
        kind=AlertRuleKind.ABSOLUTE,
        metric=AlertMetric.WIND_GUST,
        threshold=50.0,
        severity=AlertSeverity.WARNING,
        enabled=True,
        unit="km/h",
    )
    service = WeatherChangeDetectionService(absolute_rules=[abs_rule])

    # Cached vs fresh: Böen unverändert auf 60 (verletzt absolute Regel),
    # keine Δ (60 → 60, delta 0). Im Δ-only-Pfad darf KEIN Change entstehen.
    old = _data(gust_max_kmh=60.0)
    new = _data(gust_max_kmh=60.0)

    delta_only = service.detect_changes(old, new, include_absolute=False)

    absolute_markers = [c for c in delta_only if c.direction in ("above", "below")]
    assert not absolute_markers, (
        "Absolute-Rule-Changes wurden im Δ-only-Alert-Pfad nicht ausgeschlossen: "
        f"{absolute_markers}"
    )
    assert delta_only == [], (
        "Δ-only-Erkennung bei unveränderten Werten muss leer sein (keine absoluten Treffer)"
    )


# ═════════════════════════════ AC-8b ════════════════════════════════════════
# Trips mit REINEN Absolute-Regeln (#809-SyncAlertRules) bekommen weiter
# symmetrische Δ-Alerts (Invariante aus Fix-Loop 1).

def test_ac8b_absolute_rule_trip_still_gets_delta_alert(telegram_sink, clean_user_dirs):
    """AC-8b (Regression): Trip mit NUR einer absoluten WIND_GUST-Regel
    (wie SyncAlertRules/#809 sie erzeugt) bekommt einen Alert, wenn der frische
    Wert um ≥ MetricCatalog-Default (20 km/h) vom Briefing-Snapshot abweicht.

    Fix-Loop-1-Invariante: from_alert_rules trägt für ABSOLUTE-Regeln die
    MetricCatalog-Δ-Schwelle in _thresholds ein, damit include_absolute=False
    symmetrische Δ-Changes produziert — ohne absolute-Rule-Semantik.
    """
    from app.models import AlertMetric, AlertRule, AlertRuleKind, AlertSeverity
    from app.trip import Stage, Trip, Waypoint
    from services.trip_alert import TripAlertService

    user_id = clean_user_dirs("tdd-816-ac8b")

    # Exakt das Muster das SyncAlertRules (#809) erzeugt: ABSOLUTE-Regel
    abs_rule = AlertRule(
        id="r-gust-absolute",
        kind=AlertRuleKind.ABSOLUTE,
        metric=AlertMetric.WIND_GUST,
        threshold=50.0,
        severity=AlertSeverity.WARNING,
        enabled=True,
        unit="km/h",
        channels=["telegram"],
    )
    stage = Stage(
        id="T1", name="Tag 1", date=date(2026, 4, 5),
        waypoints=[Waypoint(id="G1", name="Start", lat=47.0, lon=11.0, elevation_m=1000.0)],
    )
    trip = Trip(id="trip-ac8b", name="SyncAlertRules-Trip", stages=[stage])
    trip.alert_rules = [abs_rule]
    trip.report_config = None
    trip.alert_cooldown_minutes = 0

    # Briefing-Snapshot: Böen 20 km/h
    cached = [_data(gust_max_kmh=20.0)]
    _save_briefing_snapshot(user_id, trip.id, cached)

    # Frischer Wert: Böen 45 km/h → Δ=25 ≥ MetricCatalog-Default 20 → Alert MUSS fallen
    fresh = [_data(gust_max_kmh=45.0)]
    service = TripAlertService(settings=_settings_telegram_only(), user_id=user_id)
    result = service.check_and_send_alerts(trip, cached, fresh_weather=fresh)

    assert result is True, (
        "Trip mit reiner ABSOLUTE-Regel (#809-SyncAlertRules-Muster) hat keinen "
        "Δ-Alert bekommen — from_alert_rules liefert leere _thresholds für den "
        "include_absolute=False-Pfad (Fix-Loop 1 Invariante)"
    )
    assert telegram_sink.send_count() == 1, (
        "Kein Telegram-Versand trotz Δ=25 ≥ MetricCatalog-Default 20 km/h"
    )

"""TDD RED — Issue #1370: Telegram-Sendedrossel, 429-Wiederholung, sichtbarer
„Briefing unvollständig"-Hinweis.

SPEC: docs/specs/modules/telegram_send_pacing.md (AC-1 … AC-8)

Heute feuert `TelegramOutput` sieben ungebremste `httpx.post`; HTTP 429 gilt im
`else`-Zweig (`telegram.py:257`) als Dauerfehler, und die Bubble-Schleife bricht
mit `break` ab (`notification_service.py:356`) — halbes Briefing, keine Meldung.

Testansatz (kein Mock-Theater): echte lokale HTTP-Gegenstelle `_TelegramStub`
(`http.server` im Thread, Vorbild `test_issue_936_sms_stub.py`), die die Bot-API
nachspricht — echter httpx-Aufruf, echter Statuscode, echtes JSON. Umgelenkt
wird nur die Modulkonstante `TELEGRAM_API_BASE` (Vorbild
`test_telegram_kurzstil_trip_briefing.py:218`): Transport-Umlenkung auf einen
realen Server, kein Patch des geprüften Verhaltens.

Vertrag an die Implementierung (Spec §2/§3) — drei `Settings`-Felder (GZ_),
über die die Kern-Tests die Grenzwerte auf Millisekunden schrumpfen (AC-8: kein
Test-Sonderpfad im Produktivcode):
    telegram_rate_limit_max_per_window : int   (Default 18)
    telegram_rate_limit_window_seconds : float (Default 60)
    telegram_retry_after_cap_seconds   : float (Default 45)

RED erwartet für AC-1…AC-5, AC-7, AC-8. AC-6 ist GRÜN erwartet — der
Egress-Guard (#1288/#1363) existiert; reiner Regressionsschutz gegen die
Konsolidierung auf einen POST-Helfer, KEIN RED-Nachweis.
"""
from __future__ import annotations

import http.server
import json
import re
import socket
import threading
import time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest

import output.channels.telegram as tg_module
from app.config import Settings
from app.models import (
    ForecastDataPoint, ForecastMeta, GPXPoint, NormalizedTimeseries,
    Provider, SegmentWeatherData, SegmentWeatherSummary, TripSegment,
)
from app.trip import Stage, Trip, Waypoint
from output.channels.base import OutputConfigError
from output.channels.telegram import TelegramOutput
from services.notification_service import NotificationService, TripReportRequest

# AC-8: schärfer als der globale 30-s-Timeout (pyproject.toml:63).
pytestmark = pytest.mark.timeout(20)


# --------------------------------------------------------------------------
# Lokale Telegram-Gegenstelle (echter HTTP-Server)
# --------------------------------------------------------------------------

class _Req:
    __slots__ = ("method", "payload", "ts", "status")

    def __init__(self, method, payload, ts, status):
        self.method, self.payload, self.ts, self.status = method, payload, ts, status

    def __repr__(self):
        return f"<{self.method} {self.status} {str(self.payload.get('text', ''))[:40]!r}>"


class _TelegramStub:
    """Spricht die Bot-API nach. `policy(stub, method, payload) -> (status, body)`;
    `body=None` erzeugt die passende Erfolgsantwort. Protokolliert jede Anfrage
    mit Zeitstempel/Methode/Nutzlast/Status."""

    def __init__(self, policy=None):
        self.requests: list[_Req] = []
        self._policy = policy or (lambda s, m, p: (200, None))
        self._mid = 1000
        stub = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):  # noqa: N802
                method = self.path.rsplit("/", 1)[-1]
                raw = self.rfile.read(int(self.headers.get("Content-Length", 0)))
                try:
                    payload = json.loads(raw.decode())
                except ValueError:
                    payload = {}
                status, body = stub._policy(stub, method, payload)
                if body is None:
                    stub._mid += 1
                    body = ({"ok": True, "result": True} if method == "deleteMessage"
                            else {"ok": True, "result": {"message_id": stub._mid}})
                stub.requests.append(_Req(method, payload, time.monotonic(), status))
                data = json.dumps(body).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *args):
                pass

        sock = socket.socket()
        sock.bind(("", 0))
        self.port = sock.getsockname()[1]
        sock.close()
        self._server = http.server.HTTPServer(("127.0.0.1", self.port), Handler)
        threading.Thread(target=self._server.serve_forever, daemon=True).start()

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def stop(self) -> None:
        self._server.shutdown()

    def accepted(self, method: str = "sendMessage") -> list[_Req]:
        return [r for r in self.requests if r.method == method and r.status == 200]

    def delivered(self) -> list[str]:
        return [str(r.payload.get("text", "")) for r in self.accepted()]

    def attempted(self) -> list[str]:
        out: list[str] = []
        for r in self.requests:
            text = str(r.payload.get("text", ""))
            if r.method == "sendMessage" and text not in out:
                out.append(text)
        return out

    @property
    def throttled(self) -> list[_Req]:
        return [r for r in self.requests if r.status == 429]


def _limiter(limit: int, window_s: float, retry_after: int = 30):
    """Drosselt wie Telegram: mehr als `limit` angenommene Schreibzugriffe je
    `window_s` → 429 mit `parameters.retry_after` im JSON-Rumpf (Form belegt in
    `tests/tdd/_telegram_live_fixture.py:53-79`)."""
    def policy(stub, method, payload):
        now = time.monotonic()
        recent = [r for r in stub.requests if r.status == 200 and now - r.ts < window_s]
        if len(recent) >= limit:
            return 429, {"ok": False, "error_code": 429,
                         "description": f"Too Many Requests: retry after {retry_after}",
                         "parameters": {"retry_after": retry_after}}
        return 200, None
    return policy


def _one_shot_429(retry_after: int):
    """Nur die erste Anfrage wird gedrosselt, danach Normalbetrieb."""
    state = {"fired": False}

    def policy(stub, method, payload):
        if state["fired"]:
            return 200, None
        state["fired"] = True
        return 429, {"ok": False, "error_code": 429,
                     "description": f"Too Many Requests: retry after {retry_after}",
                     "parameters": {"retry_after": retry_after}}
    return policy


def _one_shot_429_for(marker: str, retry_after: int):
    """Genau die erste Anfrage, deren Text `marker` enthält, wird gedrosselt."""
    state = {"fired": False}

    def policy(stub, method, payload):
        if state["fired"] or marker not in str(payload.get("text", "")):
            return 200, None
        state["fired"] = True
        return 429, {"ok": False, "error_code": 429,
                     "description": f"Too Many Requests: retry after {retry_after}",
                     "parameters": {"retry_after": retry_after}}
    return policy


def _permanent_failure(ordinal: int, status: int = 500):
    """Die `ordinal`-te (0-basiert) VERSCHIEDENE Nachricht scheitert dauerhaft —
    auch bei Wiederholung; alle anderen laufen durch. Text- statt zählerbasiert,
    damit ein Retry derselben Nachricht ebenfalls scheitert."""
    seen: list[str] = []

    def policy(stub, method, payload):
        if method != "sendMessage":
            return 200, None
        text = str(payload.get("text", ""))
        if text not in seen:
            seen.append(text)
        if seen.index(text) == ordinal:
            return status, {"ok": False, "error_code": status,
                            "description": "stub: permanenter Fehlschlag"}
        return 200, None
    return policy


# --------------------------------------------------------------------------
# Settings-Vertrag
# --------------------------------------------------------------------------

_PACING_FIELDS = ("telegram_rate_limit_max_per_window",
                  "telegram_rate_limit_window_seconds",
                  "telegram_retry_after_cap_seconds")

_HINT = (
    f"Diagnose: die Testkonfiguration schrumpft die Grenzwerte über {_PACING_FIELDS} "
    '(Präfix GZ_, Spec §2/§3). Heißen sie anders, verwirft pydantic sie still '
    '(extra="ignore") und die Bremse läuft mit den Produktiv-Voreinstellungen.'
)


def _require_pacing_settings(s: Settings) -> None:
    """Vertrag aus Spec §2/§3. Wird bewusst NACH den Verhaltens-Zusicherungen
    geprüft, damit der RED-Beleg echtes Fehlverhalten zeigt."""
    missing = [f for f in _PACING_FIELDS if not hasattr(s, f)]
    assert not missing, (
        f"RED (Spec §2/§3): Settings fehlen die Drossel-Felder {missing!r} "
        "(Präfix GZ_). Ohne sie sind die Grenzwerte im Kern-Test nicht auf "
        "Millisekunden schrumpfbar — AC-8 verbietet einen Test-Sonderpfad."
    )


def _settings(chat_id: str, **pacing) -> Settings:
    """Nicht gesetzte Drossel-Werte bleiben auf den Produktiv-Defaults.

    Issue #1476: telegram_test_chat_id == chat_id, sonst schaltet die
    Herkunftssperre aus einem Testlauf auf eine andere ID um und die
    Drossel-Tests zaehlen am falschen Chat.
    """
    return Settings(
        telegram_bot_token="stub-bot-token", telegram_chat_id=chat_id,
        telegram_test_chat_id=chat_id, is_test_mode=False,
        **{k: v for k, v in pacing.items() if v is not None}, _env_file=None,
    )


def _chat(tag: str) -> str:
    """Eigene Chat-ID je Test — die Drossel zählt laut Spec pro Chat UND
    prozessweit; sonst bremsen sich Tests gegenseitig aus."""
    return f"9{abs(hash((tag, time.monotonic_ns()))) % 10**8:08d}"


# --------------------------------------------------------------------------
# AC-1 — Normalfall 5–13 Bubbles bleibt vollständig, geordnet und schnell
# --------------------------------------------------------------------------

@pytest.mark.parametrize("count", [5, 13])
def test_normal_briefing_series_is_not_slowed_down(count, monkeypatch):
    """AC-1: Given ein Tagesbriefing im real üblichen Umfang (5–13 Bubbles) geht
    an denselben Chat / When der Versand läuft / Then kommen alle Teile in
    unveränderter Reihenfolge und Anzahl an, ohne Zusatznachricht und ohne
    spürbare Zusatzverzögerung.

    Die 1,5-s-Schranke lässt eine naive feste Pause je Nachricht auffliegen
    (13 × 3,5 s aus dem Live-Fixture wären 45 s). Zusätzlich muss die
    Default-Obergrenze über dem realen Briefing-Umfang liegen — sonst wäre die
    Schnelligkeit des Normalfalls Zufall statt Zusicherung.
    """
    stub = _TelegramStub()
    try:
        monkeypatch.setattr(tg_module, "TELEGRAM_API_BASE", stub.base_url)
        settings = _settings(_chat(f"ac1-{count}"))
        texts = [f"Bubble {i + 1} von {count}" for i in range(count)]

        started = time.monotonic()
        for text in texts:
            # Frische Instanz je Nachricht — so arbeitet notification_service.py:344.
            TelegramOutput(settings).send("Briefing", text, parse_mode="HTML",
                                          suppress_subject_line=True)
        elapsed = time.monotonic() - started

        assert stub.delivered() == texts, (
            f"Reihenfolge/Anzahl verändert.\n  erwartet: {texts}\n  ist: {stub.delivered()}")
        assert len(stub.requests) == count, (
            f"{len(stub.requests)} Anfragen statt {count} — im Normalfall darf KEINE "
            f"Zusatznachricht entstehen: {stub.requests}")
        assert elapsed < 1.5, (
            f"{count} Bubbles brauchten {elapsed:.2f}s gegen einen lokalen Stub — das "
            "verlangsamt den heutigen Normalfall (feste Pause je Nachricht ist als "
            "Lösung ausgeschlossen, Spec §2).")
        assert hasattr(settings, _PACING_FIELDS[0]), (
            f"RED (Spec §2): {_PACING_FIELDS[0]} fehlt — ohne konfigurierte Obergrenze "
            "ist AC-1 (Normalfall bleibt ungebremst) nicht abgesichert.")
        assert settings.telegram_rate_limit_max_per_window >= 13, (
            "Die Default-Obergrenze muss über dem real üblichen Briefing-Umfang "
            "(bis 13 Bubbles, Kontext-Analyse) liegen, sonst bremst der Fix den "
            f"Normalfall aus. Gefunden: {settings.telegram_rate_limit_max_per_window}")
    finally:
        stub.stop()


# --------------------------------------------------------------------------
# AC-2 — 20 Teile gegen eine drosselnde Gegenstelle
# --------------------------------------------------------------------------

def test_twenty_part_briefing_survives_throttling_gateway(monkeypatch):
    """AC-2: Given ein Briefing besteht aus 20 Teilen an denselben Chat / When
    der Versand läuft und die Gegenstelle ab ihrer Schwelle mit HTTP 429
    antwortet / Then kommen alle 20 Teile an und der Versand schlägt nicht fehl.

    Die Gegenstelle drosselt echt (5 angenommene Zugriffe je 0,4 s) und nennt
    retry_after=30 s; die Wiederholung ist per Konfiguration auf 50 ms gedeckelt
    — bloßes „einmal nachfassen" rettet hier NICHTS. Bestehen kann der Test nur,
    wenn der Sender selbst unter der Schwelle bleibt (Bremse, Spec §2). Jede
    Nachricht geht über eine FRISCHE Instanz: der Zähler muss prozessweit pro
    Chat greifen, nicht je Objekt (notification_service.py:344).
    """
    stub = _TelegramStub(_limiter(limit=5, window_s=0.4))
    try:
        monkeypatch.setattr(tg_module, "TELEGRAM_API_BASE", stub.base_url)
        settings = _settings(_chat("ac2"), telegram_rate_limit_max_per_window=3,
                             telegram_rate_limit_window_seconds=0.4,
                             telegram_retry_after_cap_seconds=0.05)
        texts = [f"Teil {i + 1}/20" for i in range(20)]

        failures = []
        for text in texts:
            try:
                TelegramOutput(settings).send("Lange Etappe", text, parse_mode="HTML",
                                              suppress_subject_line=True)
            except Exception as exc:  # noqa: BLE001 — Fehlerbild soll sichtbar sein
                failures.append(f"{text}: {exc!r}")

        assert not failures, (
            "Versand an der Drosselung gescheitert — heute gilt HTTP 429 als "
            "Dauerfehler (telegram.py:257) und der Sender bremst sich nicht selbst:\n  "
            + "\n  ".join(failures) + f"\n{_HINT}")
        assert stub.delivered() == texts, (
            f"Nicht alle 20 Teile angekommen ({len(stub.delivered())}/20). Fehlend: "
            f"{[t for t in texts if t not in stub.delivered()]}\n{_HINT}")
        _require_pacing_settings(settings)
    finally:
        stub.stop()


# --------------------------------------------------------------------------
# AC-3 — einmaliges 429 mit retry_after wird nachgereicht (und gedeckelt)
# --------------------------------------------------------------------------

def test_single_429_with_retry_after_is_retried_and_delivered(monkeypatch):
    """AC-3: Given die Gegenstelle antwortet einmalig mit HTTP 429 und einem
    `retry_after`-Wert im JSON-Rumpf / When der Sender diese Antwort erhält /
    Then wird die Nachricht nach der gedeckelten Wartezeit erneut gesendet und
    gilt als zugestellt, statt dass die Serie mit einem Fehler abbricht.

    Genannt wird retry_after=30 s, gedeckelt ist auf 50 ms: bestehen kann der
    Test nur, wenn der Wert aus dem JSON-Rumpf gelesen UND auf
    telegram_retry_after_cap_seconds gedeckelt wird (Spec §3).
    """
    stub = _TelegramStub(_one_shot_429(retry_after=30))
    try:
        monkeypatch.setattr(tg_module, "TELEGRAM_API_BASE", stub.base_url)
        settings = _settings(_chat("ac3"), telegram_retry_after_cap_seconds=0.05)
        text = "Einzelne Bubble mit Drossel-Antwort"

        started, mid, error = time.monotonic(), None, None
        try:
            mid = TelegramOutput(settings).send("Briefing", text, parse_mode="HTML",
                                                suppress_subject_line=True)
        except Exception as exc:  # noqa: BLE001
            error = exc
        elapsed = time.monotonic() - started

        assert error is None, (
            "Die Drossel-Antwort hat den Versand abgebrochen statt einen "
            "Wiederholversuch auszulösen — der else-Zweig in telegram.py:257 wertet "
            f"jeden Nicht-200 als Dauerfehler: {error!r}\n{_HINT}")
        assert mid is not None, "Nach dem 429 muss der zweite Versuch eine message_id liefern."
        attempts = [r for r in stub.requests if r.method == "sendMessage"]
        assert len(attempts) == 2, (
            f"Erwartet genau ein Wiederholversuch; die Gegenstelle sah: {attempts}")
        assert attempts[0].status == 429 and attempts[1].status == 200
        assert stub.delivered() == [text]
        assert elapsed < 2.0, (
            f"{elapsed:.2f}s gewartet — retry_after (30 s) muss auf "
            "telegram_retry_after_cap_seconds (hier 0,05 s) gedeckelt werden, sonst "
            "sprengt ein einzelner Retry das 120-s-Budget des Scheduler-Laufs (§3).")
        _require_pacing_settings(settings)
    finally:
        stub.stop()


def test_retry_after_429_is_capped_even_when_the_window_is_saturated(monkeypatch):
    """AC-3 (Gegenprüfungs-Befund F001): Given das Sendefenster ist im Moment der
    Drossel-Antwort ausgeschöpft / When die Gegenstelle mit HTTP 429 antwortet /
    Then wartet der Sender NUR die gedeckelte Zeit und sendet erneut — nicht
    zusätzlich eine volle, UNGEDECKELTE Fensterlänge.

    Genau dieser Fall ist der Regelfall, nicht der Rand: die eigene Bremse lässt
    eine Nachricht durch und bucht sie bis an die Grenze — der Sendemoment ist
    konstruktionsbedingt der Moment, in dem der Zähler an der Obergrenze steht,
    also der Moment, in dem Telegram am wahrscheinlichsten wirklich drosselt.

    Gemessen wird die Spanne zwischen der 429-Antwort (Zeitstempel der
    Gegenstelle) und dem Ende des Sendeaufrufs. Sie muss beim Deckel (0,05 s)
    liegen, nicht bei der Fensterlänge (1 s). Sonst addieren sich in Produktion
    gedeckelte 45 s + ungedeckelte 60 s und sprengen mit der Serie das
    120-s-Budget des Zeitplaners (internal/scheduler/scheduler.go:82).
    """
    window, cap = 1.0, 0.05
    stub = _TelegramStub(_one_shot_429_for("Zweite", retry_after=30))
    try:
        monkeypatch.setattr(tg_module, "TELEGRAM_API_BASE", stub.base_url)
        settings = _settings(_chat("f001"), telegram_rate_limit_max_per_window=1,
                             telegram_rate_limit_window_seconds=window,
                             telegram_retry_after_cap_seconds=cap)

        # Erste Nachricht sättigt das Fenster (1 Zugriff je Sekunde).
        TelegramOutput(settings).send("Briefing", "Erste Bubble", parse_mode="HTML",
                                      suppress_subject_line=True)
        mid = TelegramOutput(settings).send("Briefing", "Zweite Bubble", parse_mode="HTML",
                                            suppress_subject_line=True)
        finished = time.monotonic()

        assert mid is not None, "Nach dem 429 muss der zweite Versuch eine message_id liefern."
        assert stub.delivered() == ["Erste Bubble", "Zweite Bubble"]
        assert len(stub.throttled) == 1, f"Setup: genau ein 429 erwartet, waren {stub.throttled}"
        assert len([r for r in stub.requests if r.method == "sendMessage"]) == 3

        extra = finished - stub.throttled[0].ts
        assert extra < cap + 0.35, (
            f"Nach der Drossel-Antwort vergingen {extra:.2f}s bis zur Zustellung, "
            f"gedeckelt sind {cap:.2f}s. Der Wiederholversuch darf KEINEN zweiten "
            "Sendeplatz reservieren — die abgelehnte Nachricht zählt nicht als "
            "zugestellt, ihr Platz gilt weiter (telegram.py::_post). Sonst hängt an "
            "der gedeckelten Wartezeit die ungedeckelte Fensterlänge "
            f"({window:.2f}s) dran.")
    finally:
        stub.stop()


def test_rate_limit_bookkeeping_forgets_silent_chats(monkeypatch):
    """Gegenprüfungs-Befund F002: Die Fenster-Buchführung ist prozessweit und
    klassenlebenslang. Ein Chat, der nichts mehr sendet, darf keinen Eintrag
    zurücklassen — sonst wächst die Buchführung über die Prozesslaufzeit
    unbegrenzt (ein Eintrag je jemals bedientem Chat).
    """
    window = 0.05
    stub = _TelegramStub()
    try:
        monkeypatch.setattr(tg_module, "TELEGRAM_API_BASE", stub.base_url)
        quiet_chat = _chat("f002-quiet")
        for chat in (quiet_chat, _chat("f002-active")):
            settings = _settings(chat, telegram_rate_limit_max_per_window=5,
                                 telegram_rate_limit_window_seconds=window)
            time.sleep(window * 2)  # Fenster des vorigen Chats sicher abgelaufen
            TelegramOutput(settings).send("Briefing", f"Text {chat}", parse_mode="HTML",
                                          suppress_subject_line=True)

        assert quiet_chat not in TelegramOutput._rate_limit_stamps, (
            "Der still gewordene Chat steht immer noch in der Fenster-Buchführung — "
            "leere Zeitstempel-Listen müssen beim Aufräumen verschwinden.")
    finally:
        stub.stop()


# --------------------------------------------------------------------------
# Briefing-Fixture für AC-4/AC-5 (echter Versandpfad, kein Netz)
# --------------------------------------------------------------------------

def _segment(seg_id: int) -> SegmentWeatherData:
    h0 = 6 + seg_id * 3
    points = [ForecastDataPoint(
        ts=datetime(2026, 5, 1, h0 + h, 0, tzinfo=timezone.utc),
        t2m_c=15.0 + h, wind10m_kmh=10.0 + h, gust_kmh=22.0 + h, pop_pct=40,
        precip_1h_mm=0.4, wind_chill_c=12.0 + h, cloud_total_pct=55) for h in range(4)]
    meta = ForecastMeta(provider=Provider.OPENMETEO, model="icon_d2",
                        run=datetime(2026, 5, 1, 0, 0, tzinfo=timezone.utc),
                        grid_res_km=2.0, interp="point_grid")
    seg = TripSegment(
        segment_id=seg_id,
        start_point=GPXPoint(lat=42.2 + seg_id * 0.05, lon=9.05, elevation_m=400.0),
        end_point=GPXPoint(lat=42.25 + seg_id * 0.05, lon=9.09, elevation_m=1200.0),
        start_time=datetime(2026, 5, 1, h0, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 5, 1, h0 + 3, 0, tzinfo=timezone.utc),
        duration_hours=3.0, distance_km=8.0, ascent_m=800.0, descent_m=0.0)
    agg = SegmentWeatherSummary(temp_min_c=15.0, temp_max_c=20.0, temp_avg_c=17.5,
                                wind_max_kmh=16.0, gust_max_kmh=28.0,
                                precip_sum_mm=2.4, cloud_avg_pct=55)
    return SegmentWeatherData(segment=seg, timeseries=NormalizedTimeseries(meta=meta, data=points),
                              aggregated=agg, fetched_at=datetime.now(timezone.utc),
                              provider="openmeteo")


def _run_briefing(stub: _TelegramStub, tag: str, monkeypatch) -> None:
    from app.models import TripReportConfig

    monkeypatch.setattr(tg_module, "TELEGRAM_API_BASE", stub.base_url)
    stage = Stage(id="S1", name="Etappe 1", date=datetime(2026, 5, 1).date(), waypoints=[
        Waypoint(id="W1", name="Start", lat=42.2, lon=9.05, elevation_m=400),
        Waypoint(id="W2", name="Mitte", lat=42.25, lon=9.09, elevation_m=1200),
        Waypoint(id="W3", name="Ziel", lat=42.3, lon=9.13, elevation_m=900)])
    rc = TripReportConfig(trip_id="trip-1370-pacing", send_email=False,
                          send_sms=False, send_telegram=True)
    trip = Trip(id="trip-1370-pacing", name="Pacing-Trip", stages=[stage], report_config=rc)
    request = TripReportRequest(
        trip=trip, report_type="morning", segment_weather=[_segment(i) for i in (1, 2, 3)],
        trip_tz=ZoneInfo("Europe/Vienna"), report_config=rc,
        send_email=False, send_sms=False, send_telegram=True)
    NotificationService(settings=_settings(_chat(tag)),
                        user_id="tdd-1370-pacing").send_trip_report(request)


def _baseline_bubble_count(monkeypatch) -> int:
    """Bubble-Zahl dieses Briefings bei störungsfreiem Versand."""
    stub = _TelegramStub()
    try:
        _run_briefing(stub, "baseline", monkeypatch)
        count = len(stub.accepted())
    finally:
        stub.stop()
    assert count >= 4, f"Setup: Briefing muss mehrere Bubbles erzeugen, waren {count}."
    return count


# --------------------------------------------------------------------------
# AC-4 — endgültiger Fehlschlag in der Mitte stoppt die Serie NICHT
# --------------------------------------------------------------------------

def test_series_continues_after_one_permanently_failing_message(monkeypatch):
    """AC-4: Given eine einzelne Nachricht der Serie scheitert endgültig (die
    Gegenstelle antwortet für genau diese dauerhaft mit HTTP 500) / When noch
    weitere Nachrichten ausstehen / Then werden diese trotzdem gesendet, statt
    dass die Serie an dieser Stelle abbricht.

    Gefahren wird der ECHTE Versandpfad `NotificationService.send_trip_report` —
    dort steht heute das `break` (notification_service.py:356).
    """
    total, failing = _baseline_bubble_count(monkeypatch), 2
    stub = _TelegramStub(_permanent_failure(failing, status=500))
    try:
        _run_briefing(stub, "ac4", monkeypatch)
        attempted, delivered = stub.attempted(), stub.delivered()

        assert len(attempted) >= total, (
            f"Nur {len(attempted)} von {total} Bubbles überhaupt versucht — die Serie "
            "bricht beim Fehlschlag ab (notification_service.py:356 `break`).")
        after = attempted[failing + 1: total]
        assert after, "Setup: nach der scheiternden Bubble muss noch etwas folgen."
        lost = [t for t in after if t not in delivered]
        assert not lost, (
            f"{len(lost)} Bubble(s) NACH dem Fehlschlag kamen nie an — genau der stille "
            "Verlust aus #1370:\n  " + "\n  ".join(t[:60] for t in lost))
    finally:
        stub.stop()


# --------------------------------------------------------------------------
# AC-5 — sichtbarer „Briefing unvollständig"-Hinweis am Ende der Serie
# --------------------------------------------------------------------------

_INCOMPLETE_WORDS = ("unvollständig", "unvollstaendig", "fehlt", "fehlen", "fehlend",
                     "nicht gesendet", "nicht zugestellt", "konnte nicht",
                     "konnten nicht", "nicht angekommen")


def test_incomplete_briefing_hint_is_sent_after_failed_part(monkeypatch):
    """AC-5: Given mindestens eine Nachricht der Serie ist endgültig
    fehlgeschlagen / When die Serie fertig gesendet ist / Then erhält der Nutzer
    eine zusätzliche, deutlich sichtbare Nachricht darüber, dass das Briefing
    unvollständig ist und wie viele Teile fehlen.

    Geprüft wird Verständlichkeit für den Nutzer (deutscher Klartext, der die
    Anzahl nennt), nicht ein technisches Codewort.
    """
    total, failing = _baseline_bubble_count(monkeypatch), 2
    stub = _TelegramStub(_permanent_failure(failing, status=500))
    try:
        _run_briefing(stub, "ac5", monkeypatch)
        delivered = stub.delivered()
        assert delivered, "Es kam gar nichts an — Setup kaputt."
        assert len(delivered) == total, (
            f"Erwartet {total - 1} gelungene Bubbles + 1 Unvollständig-Hinweis = "
            f"{total} zugestellte Nachrichten, zugestellt: {len(delivered)} — heute "
            "gibt es keinen Hinweis (und die Serie bricht zusätzlich ab).")

        hint = delivered[-1]
        assert len(hint) >= 20, f"Hinweistext zu knapp, um verständlich zu sein: {hint!r}"
        assert any(w in hint.lower() for w in _INCOMPLETE_WORDS), (
            "Die letzte Nachricht sagt dem Nutzer nicht in verständlichem Deutsch, dass "
            f"das Briefing unvollständig ist:\n  {hint!r}")
        assert re.search(r"(?<!\d)1(?!\d)", hint), (
            f"Der Hinweis nennt die Anzahl der fehlenden Teile nicht (hier: 1):\n  {hint!r}")
    finally:
        stub.stop()


# --------------------------------------------------------------------------
# AC-6 — REGRESSIONSSCHUTZ (GRÜN erwartet): Test-Modus bleibt fail-closed
# --------------------------------------------------------------------------

def test_test_mode_guard_still_blocks_every_write_before_transport(monkeypatch):
    """AC-6 (REGRESSIONSSCHUTZ, kein RED-Nachweis): Given der Test-Modus ist
    aktiv, aber Bot-Token/Chat-ID weichen von den konfigurierten Test-Zugangs-
    daten ab / When eine schreibende Telegram-Funktion aufgerufen wird / Then
    verlässt KEINE Nachricht den Server und der Aufruf wird mit einem
    Konfigurationsfehler abgewiesen.

    Der Schutz existiert bereits (#1288/#1363); dieser Test sichert ihn gegen die
    Konsolidierung auf einen POST-Helfer (Spec §1: der Helfer darf die Guards
    NICHT übernehmen, sie müssen VOR ihm laufen).
    """
    stub = _TelegramStub()
    try:
        monkeypatch.setattr(tg_module, "TELEGRAM_API_BASE", stub.base_url)
        out = TelegramOutput(Settings(
            telegram_bot_token="prod-bot-token-abc123",
            telegram_test_bot_token="staging-bot-token-xyz789",
            telegram_chat_id="777000111", telegram_test_chat_id="424242",
            is_test_mode=True, _env_file=None))

        with pytest.raises(OutputConfigError):
            out.send("Betreff", "Testtext")
        with pytest.raises(OutputConfigError):
            out.delete_message("777000111", 123)
        with pytest.raises(OutputConfigError):
            out.edit_message_text("777000111", 123, "Neuer Text")

        assert stub.requests == [], (
            f"Trotz Test-Modus-Guard hat eine Anfrage den Server verlassen: {stub.requests}")
    finally:
        stub.stop()


# --------------------------------------------------------------------------
# AC-7 — Mischserie: Lade-Nachricht + Bubbles + Löschen/Bearbeiten, ein Chat
# --------------------------------------------------------------------------

def test_mixed_write_series_to_same_chat_is_fully_delivered(monkeypatch):
    """AC-7: Given ein Chat bekommt im selben Zeitraum eine Lade-Nachricht,
    mehrere Briefing-Teile sowie ein Löschen und ein Bearbeiten / When diese
    zusammen die Drosselschwelle überschreiten / Then kommen trotzdem alle
    Vorgänge durch — obwohl die Briefing-Teile allein die Schwelle nie erreicht
    hätten.

    Die Gegenstelle nimmt 5 Zugriffe je 0,3 s an. Die 4 Bubbles allein lägen
    darunter; erst Lade-Nachricht + Löschen + Bearbeiten (7 Zugriffe) reißen die
    Schwelle. Ein Pacing, das nur die Bubble-Schleife umfasst, fällt hier durch
    (Kontext-Risiko 2: delete/edit zählen auf dasselbe Chat-Limit).
    """
    stub = _TelegramStub(_limiter(limit=5, window_s=0.3))
    try:
        monkeypatch.setattr(tg_module, "TELEGRAM_API_BASE", stub.base_url)
        chat_id = _chat("ac7")
        settings = _settings(chat_id, telegram_rate_limit_max_per_window=3,
                             telegram_rate_limit_window_seconds=0.3,
                             telegram_retry_after_cap_seconds=0.05)

        loading_id = TelegramOutput(settings).send(
            "Bitte warten", "⏳ Briefing wird erstellt …", parse_mode="HTML",
            suppress_subject_line=True)
        assert loading_id is not None, "Lade-Nachricht wurde nicht zugestellt."
        for i in range(4):
            TelegramOutput(settings).send("Briefing", f"Bubble {i + 1}",
                                          parse_mode="HTML", suppress_subject_line=True)
        deleted = TelegramOutput(settings).delete_message(chat_id, loading_id)
        TelegramOutput(settings).edit_message_text(chat_id, loading_id + 1, "Korrektur")

        assert not stub.throttled, (
            f"Die Gegenstelle musste {len(stub.throttled)} Mal drosseln — der Sender "
            "bremst sich nicht selbst. Die Bremse gehört in den Kanal (alle "
            f"Schreibzugriffe pro Chat), nicht in die Bubble-Schleife: {stub.throttled}\n{_HINT}")
        assert deleted is True, (
            "delete_message ist an der Drosselung gescheitert (fail-soft False) — "
            "Löschungen zählen auf dasselbe Chat-Limit und müssen mitgebremst werden.")
        assert len(stub.accepted("sendMessage")) == 5
        assert len(stub.accepted("deleteMessage")) == 1
        assert len(stub.accepted("editMessageText")) == 1
        _require_pacing_settings(settings)
    finally:
        stub.stop()


# --------------------------------------------------------------------------
# AC-8 — Grenzwerte aus der Konfiguration, nicht aus einem Test-Sonderpfad
# --------------------------------------------------------------------------

def test_pacing_limits_come_from_configuration_with_production_defaults():
    """AC-8: Given die Kern-Tests decken lange Sendeserien und Drossel-Antworten
    ab / When sie ohne Netzzugriff laufen / Then stammen die Grenzwerte aus der
    normalen Konfiguration (Settings, Präfix GZ_) statt aus einer Test-Erkennung
    im Produktivcode — nur so bleibt die Suite im Millisekundenbereich, ohne die
    Produktiv-Voreinstellungen zu verbiegen (Spec §2/§3: 18 je 60 s, Deckel 45 s).
    """
    settings = Settings(_env_file=None)
    _require_pacing_settings(settings)
    assert settings.telegram_rate_limit_max_per_window == 18
    assert settings.telegram_rate_limit_window_seconds == 60
    assert settings.telegram_retry_after_cap_seconds == 45

    tuned = Settings(telegram_rate_limit_max_per_window=3,
                     telegram_rate_limit_window_seconds=0.2,
                     telegram_retry_after_cap_seconds=0.05, _env_file=None)
    assert tuned.telegram_rate_limit_max_per_window == 3
    assert tuned.telegram_rate_limit_window_seconds == pytest.approx(0.2)
    assert tuned.telegram_retry_after_cap_seconds == pytest.approx(0.05), (
        "Die Grenzwerte müssen überschreibbar sein — sonst prüfen Kern-Tests lange "
        "Serien nur mit echten Wartezeiten (AC-8 verbietet das).")

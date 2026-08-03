"""TDD RED — Issue #1467 Scheibe S2, Arbeitsgang AG3a: Telegram sendet einen
gebuendelten Ortsvergleich-Aenderungsalarm als EIGENE Nachricht je Ort statt
einer einzigen Sammel-Nachricht.

Spec: docs/specs/modules/rework_1467_s2_aenderungsalarm.md — AC-8, AC-9,
AC-24, AC-25, AC-26 (AG3, "Darstellung der Kurznachrichten").
Kontext: docs/context/feat-1467-ag3-kurznachrichten.md

Weg (gemessen, siehe Kontext-Dokument): `compare_alert.py:197` →
`NotificationService.send_multi_location_deviation_alert()`
(`notification_service.py:516-552`) → `to_multi_point_alert_message()`
(`output/renderers/alert/project.py:179-221`) → `_dispatch_alert_message()`
(`notification_service.py:1026-1154`), Telegram-Zweig `:1122-1141`. Dieser
Zweig sendet HEUTE genau EINEN `TelegramOutput(...).send(...)`-Aufruf,
unabhaengig davon, wie viele Orte in der `AlertMessage` gebuendelt sind.

RED-Grund: `_dispatch_alert_message()` faechert Telegram noch nicht je Ort
auf — AC-8/AC-24/AC-25 schlagen fehl, weil an der Senke nur 1 statt 3/10
Nachrichten ankommen (bzw. `telegram_fully_sent` nie auf False gesetzt wird).
AC-9 und die drei AC-26-Tests sind Regressions-Waechter und muessen bereits
JETZT gruen sein — sie bleiben es nach der Umsetzung.

Testpolitik (CLAUDE.md, Kern-Schicht): kein `Mock()`/`patch()`. Als Naht dient
ein echter lokaler HTTP-Stub, der `TELEGRAM_API_BASE` per `monkeypatch`
umlenkt (1:1 das bereits bestehende, unmarkierte Muster aus
`test_telegram_kurzstil_trip_alert.py` — anders als
`test_issue_1169_compare_alert_consumer.py::_TelegramSink`, dessen Datei
`pytest.mark.email` traegt, weil sie zusaetzlich echtes IMAP nutzt). Hier: nur
Loopback-Sockets, kein SMTP, kein echtes Telegram, kein IMAP.
"""
from __future__ import annotations

import http.server
import json
import socket
import threading
import urllib.parse
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import output.channels.telegram as tg_module
from app.config import Settings
from app.models import (
    ChangeSeverity, GPXPoint, SegmentWeatherData, SegmentWeatherSummary,
    TripSegment, WeatherChange,
)
from app.trip import Stage, Trip, Waypoint
from app.user import SavedLocation
from services.notification_service import NotificationService, RadarAlertRequest
from services.radar_service import NowcastResult


# ---------------------------------------------------------------------------
# Echte lokale Aufzeichnungs-Server (kein Mock, kein Netz) — Vorbild
# test_telegram_kurzstil_trip_alert.py (unmarkiert, kein SMTP/IMAP).
# ---------------------------------------------------------------------------

def _free_port() -> int:
    s = socket.socket()
    s.bind(("", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class _TelegramStub:
    """Lokaler HTTP-Stub fuer die Telegram-Bot-API. Zeichnet jede
    sendMessage-Nutzlast auf; `fail_at` (1-basierte Aufrufnummern) laesst die
    N-te Anfrage mit HTTP 500 scheitern — simuliert AC-25 (Teilfehler in der
    Fan-out-Serie), ohne echtes Netz oder echte Telegram-Infrastruktur."""

    def __init__(self, *, fail_at: set[int] | None = None) -> None:
        self.sent: list[dict] = []
        fail_at_local = fail_at or set()
        sent = self.sent
        counter = {"mid": 4000, "n": 0}

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):  # noqa: N802
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length)
                try:
                    payload = json.loads(body.decode())
                except ValueError:
                    payload = {}
                counter["n"] += 1
                call_no = counter["n"]
                ok = call_no not in fail_at_local
                sent.append({"payload": payload, "ok": ok, "call_no": call_no})
                if not ok:
                    resp = json.dumps(
                        {"ok": False, "description": "simulated failure (AC-25)"}
                    ).encode()
                    self.send_response(500)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(resp)
                    return
                counter["mid"] += 1
                resp = json.dumps(
                    {"ok": True, "result": {"message_id": counter["mid"]}}
                ).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(resp)

            def log_message(self, *args):  # noqa: D401 - silence
                pass

        self.port = _free_port()
        self._server = http.server.HTTPServer(("127.0.0.1", self.port), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def successful_texts(self) -> list[str]:
        """Texte aller ERFOLGREICH beantworteten sendMessage-Aufrufe."""
        return [r["payload"].get("text", "") for r in self.sent if r["ok"]]

    def stop(self) -> None:
        self._server.shutdown()


class _SMSStub:
    """Lokaler HTTP-Stub fuer seven.io — empfaengt den echten POST von
    SMSOutput. 1:1 aus test_telegram_kurzstil_trip_alert.py uebernommen."""

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


# ---------------------------------------------------------------------------
# Fixture-Daten (echte DTOs, kein Netz)
# ---------------------------------------------------------------------------

def _settings_telegram() -> Settings:
    """`can_send_telegram() == True`, kein E-Mail/SMS konfiguriert — reicht
    fuer alle Telegram-Fan-out-Tests (Transport laeuft ueber den lokalen
    `_TelegramStub`, nie echtes Netz)."""
    return Settings(telegram_bot_token="test-bot-token", telegram_chat_id="99999")


def _settings_email_sms(sms_port: int) -> Settings:
    """`can_send_email()`/`can_send_sms() == True` ohne echten Netzwerkzugriff
    — E-Mail laeuft ueber `mail_sink` (DI-Seam), SMS ueber den lokalen
    `_SMSStub`."""
    return Settings(
        smtp_host="smtp.test.invalid", smtp_user="t@test.invalid",
        smtp_pass="x", mail_to="to@test.invalid",
        sms_gateway_url=f"http://127.0.0.1:{sms_port}/api/sms",
        seven_api_key="test-stub-key", sms_to="+49000000000", sms_from=None,
    )


def _point(lat: float, lon: float) -> GPXPoint:
    return GPXPoint(lat=lat, lon=lon, elevation_m=500.0)


def _change() -> WeatherChange:
    return WeatherChange(
        metric="temp_max_c", old_value=18.0, new_value=26.0, delta=8.0,
        threshold=5.0, severity=ChangeSeverity.MODERATE, direction="increase",
        segment_id="1",
    )


def _entities(names: list[str]) -> list[tuple[str, list, list]]:
    """`entities`-Form von `send_multi_location_deviation_alert`:
    `list[(location_name, points, changes)]` — je Ort ein eigener Punkt (fuer
    die Zeitzonen-Ableitung) und eine eigene Aenderung."""
    return [
        (name, [_point(46.0 + i * 0.3, 7.0 + i * 0.3)], [_change()])
        for i, name in enumerate(names)
    ]


def _trip_segment() -> TripSegment:
    start = datetime(2026, 5, 1, 8, 0, tzinfo=timezone.utc)
    end = datetime(2026, 5, 1, 12, 0, tzinfo=timezone.utc)
    return TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=47.0, lon=11.0, elevation_m=1000, distance_from_start_km=12.0),
        end_point=GPXPoint(lat=47.1, lon=11.1, elevation_m=1500, distance_from_start_km=18.0),
        start_time=start, end_time=end, duration_hours=4.0, distance_km=6.0,
        ascent_m=500, descent_m=0,
    )


def _segment_weather_data() -> SegmentWeatherData:
    return SegmentWeatherData(
        segment=_trip_segment(), timeseries=None, aggregated=SegmentWeatherSummary(),
        fetched_at=datetime.now(timezone.utc), provider="openmeteo",
    )


def _trip() -> Trip:
    stage = Stage(
        id="S1", name="Etappe 1", date=datetime(2026, 5, 1).date(),
        waypoints=[
            Waypoint(id="W1", name="Start", lat=47.0, lon=11.0, elevation_m=1000),
            Waypoint(id="W2", name="Ziel", lat=47.1, lon=11.1, elevation_m=1500),
        ],
    )
    return Trip(id="trip-ag3a", name="AG3a-Trip", stages=[stage])


# ═══════════════════════════════ AC-8 ════════════════════════════════════════

def test_ac8_three_locations_get_three_separate_telegram_messages(monkeypatch):
    """AC-8: ein gebuendelter Aenderungsalarm fuer DREI Orte liefert an der
    Telegram-Senke GENAU DREI einzelne Nachrichten, jede mit dem
    ausgeschriebenen Namen genau EINES der drei Orte.

    RED: `_dispatch_alert_message()` sendet fuer Telegram heute EINEN
    einzigen Aufruf mit dem gebuendelten Text — erwartet werden 3 Sends,
    tatsaechlich kommt 1 an.
    """
    stub = _TelegramStub()
    try:
        monkeypatch.setattr(tg_module, "TELEGRAM_API_BASE", stub.base_url)
        svc = NotificationService(settings=_settings_telegram(), user_id="tdd-ag3a-ac8")

        names = ["Zermatt", "Chamonix", "Innsbruck"]
        svc.send_multi_location_deviation_alert(
            entities=_entities(names), effective_channels={"telegram"},
        )

        texts = stub.successful_texts()
        assert len(texts) == 3, (
            f"AC-8: erwartet 3 einzelne Telegram-Nachrichten (eine je Ort), "
            f"erhalten: {len(texts)} -- {texts!r}"
        )
        for name in names:
            matching = [t for t in texts if name in t]
            assert len(matching) == 1, (
                f"AC-8: Ort {name!r} muss in GENAU einer Nachricht auftauchen, "
                f"gefunden in {len(matching)} von {texts!r}"
            )
        for t in texts:
            hits = [name for name in names if name in t]
            assert len(hits) == 1, (
                f"AC-8: eine Nachricht darf nur EINEN Ortsnamen tragen, "
                f"gefunden {hits!r} in: {t!r}"
            )
    finally:
        stub.stop()


# ═══════════════════════════════ AC-9 (Nicht-Regression) ════════════════════

def test_ac9_email_and_sms_stay_bundled_into_one_send_each():
    """AC-9: derselbe gebuendelte Alarm fuer drei Orte bleibt fuer E-Mail UND
    SMS unveraendert EIN Versand — der Telegram-Fan-out (AC-8) darf die
    anderen Kanaele nicht beeinflussen. Muss vor UND nach der Umsetzung
    gruen bleiben."""
    sms_stub = _SMSStub()
    try:
        svc = NotificationService(
            settings=_settings_email_sms(sms_stub.port), user_id="tdd-ag3a-ac9",
        )

        mail_calls: list[tuple[str, str]] = []
        names = ["Ort-A", "Ort-B", "Ort-C"]
        svc.send_multi_location_deviation_alert(
            entities=_entities(names), effective_channels={"email", "sms"},
            mail_sink=lambda subject, body: mail_calls.append((subject, body)),
        )

        assert len(mail_calls) == 1, (
            f"AC-9: E-Mail muss EINE gebuendelte Mail mit allen Orten bleiben, "
            f"erhalten: {len(mail_calls)} Sends"
        )
        _, body = mail_calls[0]
        for name in names:
            assert name in body, f"AC-9: Ort {name!r} fehlt in der gebuendelten Mail:\n{body}"

        assert len(sms_stub.received) == 1, (
            f"AC-9: SMS muss EIN gebuendelter Versand bleiben, erhalten: "
            f"{len(sms_stub.received)} Sends"
        )
    finally:
        sms_stub.stop()


# ═══════════════════════════════ AC-24 ═══════════════════════════════════════

def test_ac24_ten_locations_get_ten_telegram_messages_no_upper_bound(monkeypatch):
    """AC-24: zehn betroffene Orte liefern ZEHN einzelne Telegram-Nachrichten
    — es gibt keine Buendelungsgrenze, ab der wieder gebuendelt wird
    (PO-Entscheidung E-AG3-1).

    RED: heute genau 1 Nachricht statt 10.
    """
    stub = _TelegramStub()
    try:
        monkeypatch.setattr(tg_module, "TELEGRAM_API_BASE", stub.base_url)
        svc = NotificationService(settings=_settings_telegram(), user_id="tdd-ag3a-ac24")

        names = [f"Ort-{i}" for i in range(10)]
        svc.send_multi_location_deviation_alert(
            entities=_entities(names), effective_channels={"telegram"},
        )

        texts = stub.successful_texts()
        assert len(texts) == 10, (
            f"AC-24: erwartet 10 einzelne Telegram-Nachrichten ohne Obergrenze, "
            f"erhalten: {len(texts)} -- {texts!r}"
        )
    finally:
        stub.stop()


# ═══════════════════════════════ AC-25 ═══════════════════════════════════════

def test_ac25_second_telegram_failure_does_not_stop_the_series(monkeypatch):
    """AC-25: bei DREI Orten, deren ZWEITE Telegram-Zustellung fehlschlaegt,
    (a) wird die dritte Nachricht trotzdem zugestellt (kein Abbruch der
    Serie), (b) geht zusaetzlich ein Hinweis auf die unvollstaendige
    Zustellung raus, (c) `telegram_fully_sent` ist False.

    RED: heute existiert kein Fan-out — es gibt nur EINEN Telegram-Aufruf
    fuer den gesamten gebuendelten Alarm. Ein Fehlschlag dieses einzigen
    Aufrufs setzt `failed_channels=["telegram"]`, aber `telegram_fully_sent`
    bleibt beim Default `True` (in `_dispatch_alert_message` nie gesetzt),
    und es gibt keine dritte Nachricht, weil es nie eine Serie gab.
    """
    stub = _TelegramStub(fail_at={2})
    try:
        monkeypatch.setattr(tg_module, "TELEGRAM_API_BASE", stub.base_url)
        svc = NotificationService(settings=_settings_telegram(), user_id="tdd-ag3a-ac25")

        names = ["Ort-Eins", "Ort-Zwei", "Ort-Drei"]
        result = svc.send_multi_location_deviation_alert(
            entities=_entities(names), effective_channels={"telegram"},
        )

        # Primaeres RED-Signal: ohne Fan-out gibt es nur EINEN Sendeversuch
        # insgesamt statt mindestens 4 (3 Orte + 1 Hinweis auf unvollstaendige
        # Zustellung) — der simulierte Fehlschlag bei Aufruf #2 trifft dann
        # nie, weil es nie einen zweiten Aufruf gibt.
        total_attempts = len(stub.sent)
        assert total_attempts >= 4, (
            "AC-25: erwartet mindestens 4 Sendeversuche (3 Orte + 1 Hinweis "
            f"auf unvollstaendige Zustellung), erhalten: {total_attempts} "
            "-- kein Fan-out, nur EIN gebuendelter Aufruf fuer alle Orte"
        )

        texts = stub.successful_texts()

        # (a) dritte Nachricht trotzdem zugestellt.
        assert any("Ort-Drei" in t for t in texts), (
            "AC-25a: die dritte Nachricht muss trotz des Fehlschlags bei "
            f"Nachricht 2 zugestellt werden -- erfolgreiche Texte: {texts!r}"
        )
        # Setup-Kontrolle: die zweite (simuliert fehlgeschlagene) Nachricht
        # darf NICHT unter den erfolgreichen auftauchen.
        assert not any("Ort-Zwei" in t for t in texts), (
            "Setup-Kontrolle fehlgeschlagen: die zweite Nachricht war "
            f"trotz simuliertem Fehlschlag erfolgreich: {texts!r}"
        )

        # (b) zusaetzlicher Hinweis: mehr erfolgreiche Sends als erfolgreich
        # zugestellte Orte (2 Orte -> Hinweis macht daraus mindestens 3).
        assert len(texts) > 2, (
            "AC-25b: es fehlt der zusaetzliche Hinweis auf die unvollstaendige "
            f"Zustellung -- erfolgreiche Sends: {texts!r}"
        )

        # (c) Protokoll-Flag.
        assert result.telegram_fully_sent is False, (
            "AC-25c: telegram_fully_sent muss False sein, wenn ein Teil der "
            f"Fan-out-Serie fehlgeschlagen ist (tatsaechlich: "
            f"{result.telegram_fully_sent!r})"
        )
    finally:
        stub.stop()


# ═══════════════════════════════ AC-26 (Invarianten) ═════════════════════════
# Diese drei Tests sichern ab, dass der Fan-out AUSSCHLIESSLICH den
# Ortsvergleich-Aenderungspfad betrifft. Sie sind Regressions-Waechter und
# muessen VOR UND NACH der AG3a-Umsetzung gruen sein (kein RED-Test).

def test_ac26_trip_deviation_alert_stays_single_telegram_message(monkeypatch):
    """AC-26: ein Trip-Aenderungsalarm (`send_deviation_alert`) bleibt bei
    EINER Telegram-Nachricht — der Fan-out darf nicht ueber
    `_dispatch_alert_message()` auf den Trip-Pfad durchschlagen."""
    stub = _TelegramStub()
    try:
        monkeypatch.setattr(tg_module, "TELEGRAM_API_BASE", stub.base_url)
        svc = NotificationService(settings=_settings_telegram(), user_id="tdd-ag3a-ac26-trip")

        svc.send_deviation_alert(
            trip=_trip(), weather=[_segment_weather_data()], changes=[_change()],
            effective_channels={"telegram"},
        )

        texts = stub.successful_texts()
        assert len(texts) == 1, (
            f"AC-26: Trip-Aenderungsalarm muss bei EINER Telegram-Nachricht "
            f"bleiben, erhalten: {len(texts)} -- {texts!r}"
        )
    finally:
        stub.stop()


def test_ac26_trip_radar_alert_stays_single_telegram_message(monkeypatch):
    """AC-26: ein Trip-Radar-Alarm (`send_radar_alert`) bleibt bei EINER
    Telegram-Nachricht."""
    stub = _TelegramStub()
    try:
        monkeypatch.setattr(tg_module, "TELEGRAM_API_BASE", stub.base_url)
        svc = NotificationService(settings=_settings_telegram(), user_id="tdd-ag3a-ac26-radar")

        req = RadarAlertRequest(
            onset_minutes=12, onset_time="14:35", km_from=5.0, km_to=18.0,
            is_convective=False, intensity_label="leichter Regen",
            source_label="Radar (DWD)", tz=ZoneInfo("Europe/Zurich"),
        )
        svc.send_radar_alert(
            trip=_trip(), request=req, source="Radar (DWD)",
            cooldown_display="2 Stunden", effective_channels={"telegram"},
        )

        texts = stub.successful_texts()
        assert len(texts) == 1, (
            f"AC-26: Trip-Radar-Alarm muss bei EINER Telegram-Nachricht "
            f"bleiben, erhalten: {len(texts)} -- {texts!r}"
        )
    finally:
        stub.stop()


# ═══════════════════════════ Haertung F001/F002 ══════════════════════════
# Adversary-Befunde aus dem AG3a-Dialog
# (docs/artifacts/feat-1467-ag3-kurznachrichten/adversary-dialog.md):
# F001 (LOW) — Sende-Reihenfolge an der Senke war ungetestet.
# F002 (MEDIUM) — Rendering-Fehler bei EINEM Ort riss die gesamte Fan-out-
# Serie mit, weil `to_multi_point_alert_message()`/`render_alert_telegram()`
# ausserhalb des Pro-Ort-try/except lagen (nur `.send()` war geschuetzt).

def test_f001_telegram_messages_arrive_in_configured_location_order(monkeypatch):
    """F001: die Sende-REIHENFOLGE an der Senke muss der konfigurierten
    Ortsreihenfolge entsprechen, nicht nur die Anwesenheit der Namen.

    Waere die Fan-out-Schleife umgedreht (`for group in
    reversed(telegram_groups)`), bliebe AC-8 gruen (alle drei Namen kommen
    vor), aber die Reihenfolge an der Senke waere falsch -- genau das
    faengt dieser Test.
    """
    stub = _TelegramStub()
    try:
        monkeypatch.setattr(tg_module, "TELEGRAM_API_BASE", stub.base_url)
        svc = NotificationService(settings=_settings_telegram(), user_id="tdd-ag3a-f001")

        names = ["Zermatt", "Chamonix", "Innsbruck"]
        svc.send_multi_location_deviation_alert(
            entities=_entities(names), effective_channels={"telegram"},
        )

        texts = stub.successful_texts()
        assert len(texts) == 3, f"Setup: erwartet 3 Nachrichten, erhalten {texts!r}"

        arrival_order = []
        for t in texts:
            hits = [name for name in names if name in t]
            assert len(hits) == 1, f"eine Nachricht muss genau einen Ort tragen: {t!r}"
            arrival_order.append(hits[0])

        assert arrival_order == names, (
            f"F001: die Sende-Reihenfolge an der Senke ({arrival_order!r}) muss "
            f"der konfigurierten Ortsreihenfolge entsprechen ({names!r})"
        )
    finally:
        stub.stop()


def test_f002_rendering_failure_for_one_location_does_not_abort_the_series(monkeypatch):
    """F002: schlaegt das AUFBEREITEN (nicht der Versand) fuer den ERSTEN
    Ort fehl, muessen die beiden uebrigen Orte trotzdem zugestellt werden,
    ein Hinweis auf die unvollstaendige Zustellung geht raus, und
    `telegram_fully_sent` ist False.

    RED (vor der Haertung): `to_multi_point_alert_message()`/
    `render_alert_telegram()` liegen ausserhalb des Pro-Ort-try/except --
    eine Ausnahme dort reisst die GESAMTE Serie mit (0 statt 2 Nachrichten
    kommen an), kein Hinweis geht raus, `telegram_fully_sent` bleibt
    faelschlich True.
    """
    import services.notification_service as notif_module

    stub = _TelegramStub()
    real_to_multi_point_alert_message = notif_module.to_multi_point_alert_message
    call_count = {"n": 0}

    def _flaky(groups, *, tz, stand_at):
        call_count["n"] += 1
        # Aufruf 1 = der gebuendelte Aufruf in
        # send_multi_location_deviation_alert() (baut die AlertMessage fuer
        # alle drei Orte). Aufruf 2 = die ERSTE Fan-out-Iteration -- genau
        # der laut Adversary-Dialog demonstrierte Fehlerfall.
        if call_count["n"] == 2:
            raise RuntimeError("simuliertes Rendering-Problem (F002)")
        return real_to_multi_point_alert_message(groups, tz=tz, stand_at=stand_at)

    try:
        monkeypatch.setattr(tg_module, "TELEGRAM_API_BASE", stub.base_url)
        monkeypatch.setattr(notif_module, "to_multi_point_alert_message", _flaky)
        svc = NotificationService(settings=_settings_telegram(), user_id="tdd-ag3a-f002")

        names = ["Ort-Eins", "Ort-Zwei", "Ort-Drei"]
        result = svc.send_multi_location_deviation_alert(
            entities=_entities(names), effective_channels={"telegram"},
        )

        texts = stub.successful_texts()

        # (a) die beiden UEBRIGEN Orte kommen trotzdem an -- keine
        # abgebrochene Serie.
        assert any("Ort-Zwei" in t for t in texts), (
            f"F002a: Ort-Zwei muss trotz Rendering-Fehler bei Ort-Eins "
            f"zugestellt werden -- erfolgreiche Texte: {texts!r}"
        )
        assert any("Ort-Drei" in t for t in texts), (
            f"F002a: Ort-Drei muss trotz Rendering-Fehler bei Ort-Eins "
            f"zugestellt werden -- erfolgreiche Texte: {texts!r}"
        )
        # Setup-Kontrolle: Ort-Eins darf NICHT auftauchen (Rendering ist
        # dort gescheitert, bevor ueberhaupt gesendet wurde).
        assert not any("Ort-Eins" in t for t in texts), (
            f"Setup-Kontrolle fehlgeschlagen: Ort-Eins wurde trotz "
            f"simuliertem Rendering-Fehler zugestellt: {texts!r}"
        )

        # (b) zusaetzlicher Hinweis auf die unvollstaendige Zustellung.
        assert len(texts) > 2, (
            f"F002b: es fehlt der Hinweis auf die unvollstaendige "
            f"Zustellung -- erfolgreiche Sends: {texts!r}"
        )

        # (c) Protokoll-Flag.
        assert result.telegram_fully_sent is False, (
            f"F002c: telegram_fully_sent muss False sein, wenn das "
            f"Aufbereiten fuer einen Ort scheiterte (tatsaechlich: "
            f"{result.telegram_fully_sent!r})"
        )
    finally:
        stub.stop()


def test_ac26_compare_radar_alert_stays_single_telegram_message(monkeypatch):
    """AC-26: ein Ortsvergleich-Radar-Alarm (`send_multi_location_radar_alert`)
    bleibt trotz MEHRERER Orte bei EINER gebuendelten Telegram-Nachricht — der
    Fan-out greift ausschliesslich im Aenderungs-(Deviation-)Pfad, nicht im
    Nowcast-Pfad."""
    stub = _TelegramStub()
    try:
        monkeypatch.setattr(tg_module, "TELEGRAM_API_BASE", stub.base_url)
        svc = NotificationService(
            settings=_settings_telegram(), user_id="tdd-ag3a-ac26-cmp-radar",
        )

        loc_a = SavedLocation(id="loc-a", name="Zermatt", lat=46.02, lon=7.75, elevation_m=1600)
        loc_b = SavedLocation(id="loc-b", name="Chamonix", lat=45.92, lon=6.87, elevation_m=1000)
        nc_a = NowcastResult(
            onset_minutes=8, intensity_label="leichter Regen", source="radar",
            is_convective=False,
        )
        nc_b = NowcastResult(
            onset_minutes=15, intensity_label="maessiger Regen", source="radar",
            is_convective=False,
        )

        svc.send_multi_location_radar_alert(
            [("Zermatt", loc_a, nc_a), ("Chamonix", loc_b, nc_b)], {"telegram"},
        )

        texts = stub.successful_texts()
        assert len(texts) == 1, (
            "AC-26: Ortsvergleich-Radar-Alarm (Nowcast) muss trotz mehrerer "
            f"Orte bei EINER gebuendelten Telegram-Nachricht bleiben, "
            f"erhalten: {len(texts)} -- {texts!r}"
        )
    finally:
        stub.stop()

"""TDD RED — Issue #1914: Radar-Alarm folgt dem konfigurierten Telegram-Stil
(Trip-Pfad).

Deckt AC-1/AC-2 der Spec `docs/specs/modules/fix_1914_radar_telegram_style.md`
ab: `TripAlertService.check_radar_alerts()` -> `send_radar_alert()` reicht
heute `telegram_style` NICHT durch — die Telegram-Nachricht eines
Radar-/Nowcast-Alarms kommt deshalb immer im reichen HTML-Format an, auch
wenn `trip.report_config.telegram_style == "kurzform"` gesetzt ist.

Pflicht (Lehre #1467): der Test laeuft ueber die tatsaechliche Aufrufstelle
(`TripAlertService.check_radar_alerts()`), NICHT nur direkt gegen
`NotificationService.send_radar_alert(telegram_style=...)` — sonst beweist er
nur den Baustein, nicht die Verdrahtung ueber `trip_alert.py`.

RED-Ursache: `send_radar_alert()`/`_dispatch_alert_message()`-Aufruf darin
kennen `telegram_style` noch nicht (AC-1 schlaegt fehl: die Telegram-Nachricht
kommt trotz `"kurzform"` als reiche HTML-Bubble an). AC-2 ist der
Regressionsschutz fuer den unveraenderten Bestandsfall (rich/Default) und
darf bereits heute gruen sein.

Wiederverwendete Fixtures/Helfer (Vorbild `test_952_onset_alert_e2e.py`, das
denselben Import-Weg bereits nutzt): `_GuaranteedWetRadar` (echter
`RadarNowcastService`-DI-Seam, kein Mock), `_trip_with_active_segment`
(garantiert aktives Segment JETZT), `_clean_user` — alle aus
`test_952_onset_alert_fidelity.py`. Der lokale Telegram-HTTP-Stub ist die aus
`test_telegram_kurzstil_trip_alert.py` bekannte `_TelegramStub`-Bauart (echter
lokaler HTTP-Server, `monkeypatch.setattr(telegram_mod, "TELEGRAM_API_BASE",
...)`) — kein `Mock()`/`patch()` des Verhaltens selbst.

SPEC: docs/specs/modules/fix_1914_radar_telegram_style.md
"""
from __future__ import annotations

import http.server
import json
import socket
import threading

from app.config import Settings
from app.models import TripReportConfig

import output.channels.telegram as tg_module

from tests.tdd.test_952_onset_alert_fidelity import (
    _GuaranteedWetRadar,
    _clean_user,
    _trip_with_active_segment,
)


# ---------------------------------------------------------------------------
# Echter lokaler Telegram-Bot-API-Stub (kein Mock) — Vorbild
# test_telegram_kurzstil_trip_alert.py::_TelegramStub.
# ---------------------------------------------------------------------------


def _free_port() -> int:
    s = socket.socket()
    s.bind(("", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class _TelegramStub:
    """Lokaler HTTP-Stub für die Telegram-Bot-API. Zeichnet jede sendMessage-
    Nutzlast (text/parse_mode/reply_markup) auf und antwortet mit ok:true."""

    def __init__(self) -> None:
        self.sent: list[dict] = []
        sent = self.sent
        counter = {"mid": 3000}

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


def _telegram_only_settings() -> Settings:
    """Nur Telegram sendebereit (kein E-Mail-/SMS-Versuch — vereinfacht die
    Assertions auf den einen relevanten Kanal).

    `telegram_test_chat_id` ist BEWUSST identisch zu `telegram_chat_id`
    gesetzt: die Herkunftssperre (`TelegramOutput._guard_code_origin()`,
    Issue #1476, `src/app/origin_guard.py`) verlangt aus jedem
    Nicht-Prod-/Staging-Checkout (jeder Worktree UND jeder CI-Runner) eine
    konfigurierte Test-Chat-ID, sonst `OutputConfigError` — VOR jedem HTTP-
    Request, ausserhalb des `try`/`except` in `send()`. Ohne dieses Feld lief
    der Test hier nur, weil das lokale Dev-`.env` zufaellig
    `GZ_TELEGRAM_TEST_CHAT_ID` setzt (per `env_file=".env"` in
    `Settings.model_config`) -- der GitHub-Actions-Runner hat kein `.env` und
    die leere Default-Chat-ID liess die Guard-Ausnahme silent in
    `_dispatch_alert_message()`s breitem `except Exception` verschwinden
    (`sent_channels.append("telegram")` steht VOR dem `try`, also zaehlte der
    Kanal trotzdem als "zugestellt")."""
    return Settings().model_copy(update={
        "smtp_host": None, "smtp_user": None, "smtp_pass": None, "mail_to": None,
        "telegram_bot_token": "test-token-1914", "telegram_chat_id": "99999",
        "telegram_test_chat_id": "99999",
        "sms_gateway_url": None, "seven_api_key": None, "sms_to": None,
    })


def _trip_with_telegram_style(trip_id: str, telegram_style: str):
    config = TripReportConfig(
        trip_id=trip_id, send_email=False, send_sms=False, send_telegram=True,
        alert_on_changes=True, telegram_style=telegram_style,
    )
    return _trip_with_active_segment(trip_id, config)


# ===========================================================================
# AC-1: telegram_style="kurzform" am Trip-Radar-Pfad -> Kurzstil-Telegram
# ===========================================================================


class TestAC1RadarAlertTelegramKurzstil:
    def test_kurzform_trip_radar_path_sends_plaintext_no_parse_mode(self, monkeypatch) -> None:
        """RED: `check_radar_alerts()` reicht `telegram_style` noch nicht bis
        zu `send_radar_alert()`/`_dispatch_alert_message()` durch — die
        Telegram-Nachricht kommt trotz `"kurzform"` als reiche HTML-Bubble
        (parse_mode="HTML") an statt als Plaintext ohne parse_mode."""
        uid = "tdd-1914-ac1"
        trip_id = "trip-1914-ac1"
        _clean_user(uid)
        tg_stub = _TelegramStub()
        try:
            monkeypatch.setattr(tg_module, "TELEGRAM_API_BASE", tg_stub.base_url)

            trip = _trip_with_telegram_style(trip_id, "kurzform")
            from app.loader import save_trip
            save_trip(trip, user_id=uid)

            from services.trip_alert import TripAlertService
            svc = TripAlertService(
                settings=_telegram_only_settings(), throttle_hours=0, user_id=uid,
                radar_service=_GuaranteedWetRadar(
                    onset_minutes=12, intensity_label="leichter Regen",
                    is_convective=False,
                ),
            )

            result = svc.check_radar_alerts()

            assert result == 1, f"check_radar_alerts() sollte 1 Alert liefern, war {result}"
            assert len(tg_stub.sent) == 1, (
                f"Erwartete genau 1 Telegram-Nachricht, erhalten: {len(tg_stub.sent)}"
            )
            payload = tg_stub.sent[0]
            assert "parse_mode" not in payload, (
                "RED: Kurzstil-Redirect muss parse_mode=None nutzen (kein "
                f"Schluessel im Payload); gefunden parse_mode="
                f"{payload.get('parse_mode')!r} — die Verdrahtung von "
                "telegram_style durch check_radar_alerts() -> send_radar_alert() "
                "-> _dispatch_alert_message() fehlt noch."
            )
            assert "reply_markup" not in payload, (
                "RED: Kurzstil darf keine Inline-Knoepfe (reply_markup) senden."
            )
            assert "<b>" not in (payload.get("text") or ""), (
                "RED: Kurzstil-Body enthaelt HTML-Tags — es ist noch die reiche "
                f"Telegram-Radar-Warnung: {payload.get('text')!r}"
            )
        finally:
            tg_stub.stop()
            _clean_user(uid)


# ===========================================================================
# AC-2: telegram_style="rich"/Default am Trip-Radar-Pfad -> Regressionsschutz
# ===========================================================================


class TestAC2RadarAlertTelegramRichRegression:
    def test_rich_trip_radar_path_still_sends_html(self, monkeypatch) -> None:
        """Regressionsschutz — darf bereits vor der Implementierung gruen
        sein: der heutige (fehlerhafte) Default-Pfad rendert IMMER rich."""
        uid = "tdd-1914-ac2"
        trip_id = "trip-1914-ac2"
        _clean_user(uid)
        tg_stub = _TelegramStub()
        try:
            monkeypatch.setattr(tg_module, "TELEGRAM_API_BASE", tg_stub.base_url)

            trip = _trip_with_telegram_style(trip_id, "rich")
            from app.loader import save_trip
            save_trip(trip, user_id=uid)

            from services.trip_alert import TripAlertService
            svc = TripAlertService(
                settings=_telegram_only_settings(), throttle_hours=0, user_id=uid,
                radar_service=_GuaranteedWetRadar(
                    onset_minutes=12, intensity_label="leichter Regen",
                    is_convective=False,
                ),
            )

            result = svc.check_radar_alerts()

            assert result == 1, f"check_radar_alerts() sollte 1 Alert liefern, war {result}"
            assert len(tg_stub.sent) == 1
            assert tg_stub.sent[0].get("parse_mode") == "HTML", (
                "Regression: rich/Default muss den reichen HTML-Radar-Alarm "
                f"unveraendert senden; gefunden parse_mode="
                f"{tg_stub.sent[0].get('parse_mode')!r}."
            )
        finally:
            tg_stub.stop()
            _clean_user(uid)

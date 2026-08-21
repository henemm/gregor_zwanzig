"""Alarm-Prüfstrecke (Scheibe S1, Issue #2050).

Mehrere Prüfläufe gegen die ECHTE Auslöseentscheidung, mit stellbarer Uhr,
vorbelegbarem Zustand und Abgriff aller vier Kanäle ohne echten Versand.
`TripAlertService` wird PRO LAUF neu gebaut — Kontinuität kommt ausschließlich
vom Datenträger unter `get_data_dir(user_id)`, wie in Produktion, wo jeder
Cron-Tick eine frische Instanz erzeugt.

`now_utc=` wird bewusst NICHT als Steuerparameter angeboten:
`check_official_alert_triggers` verwirft ihn bedingungslos (`trip_alert.py:
1811`) — Zeitsteuerung läuft ausschließlich über die gestellte Uhr
(`freeze_time`).

SPEC: docs/specs/modules/alarm_pruefstrecke.md
"""
from __future__ import annotations

import json
import threading
import urllib.parse
from dataclasses import dataclass, field
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Literal, Optional

from freezegun import freeze_time

from app.config import Settings
from output.channels import telegram as telegram_mod
from output.channels.telegram import reset_telegram_rate_limit_for_tests
from output.channels.premium_sms import PREMIUM_SMS_SENDER
from providers.thunder_window_cache import reset_thunder_window_cache_for_tests
from services.radar_cache import reset_shared_radar_cache_for_tests
from services.trip_alert import TripAlertService
from services.weather_cache import reset_shared_weather_cache_for_tests

Zweig = Literal["deviation", "official", "radar"]


@dataclass
class AlarmPruefstreckeLauf:
    """Ergebnis eines einzelnen Prüflaufs — Auslösezähler + gerenderter
    Inhalt der vier Kanäle (leer, wenn nichts ausgelöst wurde)."""

    triggered_count: int
    mail: list = field(default_factory=list)
    telegram: list = field(default_factory=list)
    sms: list = field(default_factory=list)
    premium_sms: list = field(default_factory=list)


def _start_json_stub(received: list) -> tuple[HTTPServer, int]:
    """Lokaler HTTP-Stub für die Telegram-Bot-API (JSON-Body, Vorbild
    `test_952_onset_alert_fidelity.py::_make_fake_bot_handler`)."""

    class _Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_POST(self):  # noqa: N802
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length) if length else b"{}"
            received.append(json.loads(raw or b"{}"))
            body = json.dumps({"ok": True, "result": {"message_id": len(received)}}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = HTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, server.server_address[1]


def _start_seven_io_stub(received: list) -> tuple[HTTPServer, int]:
    """Lokaler HTTP-Stub für das seven.io-Gateway (form-urlencoded,
    Vorbild `test_issue_936_sms_stub.py::_SMSStub`). SMS UND Premium-SMS
    teilen `settings.sms_gateway_url` (`seven_io_base.py`) — EIN Stub genügt,
    die Trennung passiert über das Absenderfeld (`from`), das Premium-SMS
    fest auf `PREMIUM_SMS_SENDER` setzt und normale SMS nicht."""

    class _Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_POST(self):  # noqa: N802
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length) if length else b""
            data = urllib.parse.parse_qs(raw.decode())
            received.append({k: v[0] for k, v in data.items()})
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"100")

    server = HTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, server.server_address[1]


class AlarmPruefstrecke:
    """Baut für einen `user_id` mehrere Prüfläufe gegen die echte
    Auslöseentscheidung — der Datenträger unter `get_data_dir(user_id)` trägt
    die Kontinuität zwischen den Läufen, nicht diese Instanz."""

    def __init__(
        self, *, user_id: str, settings: Optional[Settings] = None,
        throttle_hours: int = 2,
    ) -> None:
        self._user_id = user_id
        self._throttle_hours = throttle_hours
        self._telegram_received: list[dict] = []
        self._seven_received: list[dict] = []
        _, telegram_port = _start_json_stub(self._telegram_received)
        _, seven_port = _start_seven_io_stub(self._seven_received)
        self._telegram_url = f"http://127.0.0.1:{telegram_port}"
        base = settings if settings is not None else Settings()
        # Wie in Produktion (`TripAlertService(settings=None, ...)` baut sich
        # intern `Settings().with_user_profile(user_id)`, Vorbild
        # `trip_alert.py:198`): `premium_sms_reply_to`/`_at` sind KEIN
        # direkter `user.json`-Lookup im Kanal (`premium_sms.py:71-72`),
        # sondern Felder auf `Settings`, die NUR `with_user_profile()`
        # befuellt (`app/config.py:355-401`). Ohne diesen Schritt wuerde die
        # Pruefstrecke Premium-SMS strukturell NIE erreichen, unabhaengig
        # davon, was vorbelegt wurde -- bitte NICHT als ueberfluessig
        # entfernen.
        profiled = base.with_user_profile(user_id)
        self._settings = profiled.model_copy(update={
            "sms_gateway_url": f"http://127.0.0.1:{seven_port}/api/sms",
        })

    def lauf(
        self, *, at: datetime, zweig: Zweig, trip: "Trip",
        cached_weather: Optional[list] = None, fresh_weather: Optional[list] = None,
        official_notices: Optional[list] = None, radar_service: Optional[object] = None,
    ) -> AlarmPruefstreckeLauf:
        """Ein Prüflauf: vier Cache-Resets -> gestellte Uhr -> frische
        `TripAlertService`-Instanz -> passender Entscheidungs-Einstiegspunkt.

        `now_utc=` wird bewusst nirgends durchgereicht (s. Moduldoku).
        """
        # Schritt 1: Cache-Reset -- jeder Lauf beginnt mit leeren
        # Singleton-Caches, unabhängig davon, was ein vorheriger Lauf im
        # selben Testprozess gefüllt hat (AC-3).
        reset_shared_radar_cache_for_tests()
        reset_shared_weather_cache_for_tests()
        reset_thunder_window_cache_for_tests()
        reset_telegram_rate_limit_for_tests()
        self._telegram_received.clear()
        self._seven_received.clear()

        # `TELEGRAM_API_BASE` ist eine Modulkonstante -- nur für die Dauer
        # DIESES Laufs umgebogen, damit kein Zustand über die Instanz hinaus
        # in andere Tests durchschlägt.
        original_base = telegram_mod.TELEGRAM_API_BASE
        telegram_mod.TELEGRAM_API_BASE = self._telegram_url
        try:
            with freeze_time(at):
                mail_calls: list[tuple[str, str]] = []
                svc = TripAlertService(
                    settings=self._settings, throttle_hours=self._throttle_hours,
                    user_id=self._user_id, radar_service=radar_service,
                    mail_sink=lambda subject, body: mail_calls.append((subject, body)),
                )
                if zweig == "deviation":
                    raw = svc.check_and_send_alerts(
                        trip, cached_weather or [], fresh_weather=fresh_weather,
                        official_notices=official_notices,
                    )
                elif zweig == "official":
                    raw = svc._send_official_alert_only(trip, official_notices or [])
                elif zweig == "radar":
                    raw = svc.check_radar_alerts()
                else:
                    raise ValueError(f"Unbekannter Zweig: {zweig!r}")
        finally:
            telegram_mod.TELEGRAM_API_BASE = original_base

        telegram_msgs = [p.get("text", "") for p in self._telegram_received]
        sms_msgs = [e.get("text", "") for e in self._seven_received if e.get("from") != PREMIUM_SMS_SENDER]
        premium_msgs = [e.get("text", "") for e in self._seven_received if e.get("from") == PREMIUM_SMS_SENDER]
        return AlarmPruefstreckeLauf(
            triggered_count=int(raw), mail=list(mail_calls),
            telegram=telegram_msgs, sms=sms_msgs, premium_sms=premium_msgs,
        )

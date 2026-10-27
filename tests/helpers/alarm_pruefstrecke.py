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
from typing import TYPE_CHECKING, Literal, Optional

from freezegun import freeze_time

if TYPE_CHECKING:
    from app.trip import Trip

from app.config import Settings
from app.loader import get_data_dir
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


#: CI-Rot 2026-10-22 (Familie B): jeder Stub laeuft in einem eigenen
#: ``serve_forever``-Thread. Bislang wurde keiner je beendet -- der CI-
#: Thread-Dump von pytest-timeout zeigte >= 56 lebende Stub-Threads spaet im
#: Lauf. Ein solcher Thread, dessen Socket unbrauchbar geworden ist, dreht in
#: ``serve_forever`` leer (``select`` meldet sofort "bereit", ``accept``
#: scheitert) und frisst den GIL: ein CPU-gebundener Repo-Scan lief mit 56
#: solcher Threads 4x langsamer (3,4 s -> 13 s gemessen) und im CI in die
#: 30-s-Schranke. Deshalb: jeder Server wird hier registriert und von der
#: autouse-Fixture ``_pruefstrecken_server_beenden`` (tests/conftest.py) nach
#: jedem Test sauber heruntergefahren. ``poll_interval`` klein, damit
#: ``shutdown()`` nicht bis zu 0,5 s je Server wartet.
_OFFENE_SERVER: list[tuple[HTTPServer, threading.Thread]] = []
_STUB_THREAD_NAME = "gz-pruefstrecke-stub"
_POLL_INTERVAL_S = 0.05


def _server_starten(server: HTTPServer) -> None:
    thread = threading.Thread(
        target=server.serve_forever, kwargs={"poll_interval": _POLL_INTERVAL_S},
        name=_STUB_THREAD_NAME, daemon=True,
    )
    thread.start()
    _OFFENE_SERVER.append((server, thread))


def offene_server_beenden() -> int:
    """Alle noch laufenden Stub-Server dieses Prozesses beenden.

    Liefert die Zahl der beendeten Server. ``shutdown()`` stoppt die
    ``serve_forever``-Schleife (und kehrt sofort zurueck, falls sie schon zu
    Ende ist), ``server_close()`` gibt den Socket frei."""
    beendet = 0
    while _OFFENE_SERVER:
        server, thread = _OFFENE_SERVER.pop()
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        beendet += 1
    return beendet


def lebende_stub_threads() -> int:
    """Zahl der noch lebenden Stub-Threads (Nachweisgroesse fuer den Selbsttest)."""
    return sum(
        1 for t in threading.enumerate() if t.name == _STUB_THREAD_NAME and t.is_alive()
    )


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
    _server_starten(server)
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
    _server_starten(server)
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
        # Issue #2144 AC-2: `with_user_profile()` ueberschreibt mail_to/
        # sms_to jetzt IMMER (auch auf None), wenn das Profil das Feld nicht
        # traegt -- unconditional, bewusst OHNE force_test-Ausnahme (anders
        # als telegram_chat_id, AC-3). Die Pruefstrecke simuliert einen
        # Nutzer mit vollstaendig konfigurierten Kanaelen; das Profil muss
        # diese Felder deshalb selbst tragen (Read-Modify-Write, damit
        # `_write_tier()`/`_write_premium_profile()`-Aufrufe vor oder nach
        # dieser Konstruktion nichts verlieren), sonst wischt
        # `with_user_profile()` die hier uebergebenen Kanal-Ziele weg.
        profile_path = get_data_dir(user_id) / "user.json"
        try:
            profile = json.loads(profile_path.read_text())
        except (json.JSONDecodeError, OSError):
            profile = {"id": user_id}
        profile.setdefault("mail_to", base.mail_to)
        profile.setdefault("sms_to", base.sms_to)
        # Issue #2406: seit der Fail-closed-Sperre in `with_user_profile()`
        # erreicht eine Nummer `Settings.sms_to` nur mit passendem
        # `sms_verified_number`. Die Pruefstrecke simuliert einen Nutzer mit
        # vollstaendig konfigurierten Kanaelen — die Nummer gilt hier also als
        # bewiesen, sonst verschwaende der SMS-Zweig strukturell.
        if profile.get("sms_to"):
            profile.setdefault("sms_verified_number", profile["sms_to"])
        profile.setdefault("telegram_chat_id", base.telegram_chat_id)
        profile_path.parent.mkdir(parents=True, exist_ok=True)
        profile_path.write_text(json.dumps(profile))
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

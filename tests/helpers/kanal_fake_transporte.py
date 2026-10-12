"""Steuerbare Versandwege fuer die ECHTEN vier Kanal-Ausgaenge (Issue #1405 S1).

Die vier Ausgabe-Klassen (``EmailOutput``, ``TelegramOutput``, ``SMSOutput``,
``PremiumSmsOutput``) bleiben unangetastet -- inklusive Herkunftssperren,
Empfaenger-Guards, Retry-Logik und Tageslimit-Gate. Ersetzt wird nur, was am
Ende des Drahts steht:

* **Telegram und seven.io (SMS + Premium-SMS):** echte lokale HTTP-Server auf
  127.0.0.1 (Muster ``tests/helpers/alarm_pruefstrecke.py``), deren Antwort je
  Kanal zur Laufzeit umschaltbar ist (``"ok"``/``"fehler"``).
* **SMTP:** ``smtplib.SMTP`` im Modul ``output.channels.email`` wird durch eine
  skriptbare Gegenstelle ersetzt (Muster
  ``tests/tdd/test_mail_message_id_traceability.py``). Ein echter Loopback-
  SMTP-Server entfaellt bewusst: ``EmailOutput`` erzwingt STARTTLS + Login, im
  Projekt gibt es weder ``aiosmtpd`` noch ``cryptography``, und ``smtpd`` ist
  seit Python 3.12 entfernt. Die Ablehnung kommt als permanenter 5xx-Fehler
  (``SMTPResponseException(554)``) -- der echte ``EmailOutput`` wiederholt ihn
  nicht intern, ein Alarm-Versuch ist also genau ein Einlieferungsversuch.

Kein ``Mock()``/``patch()``/``MagicMock``. Gezaehlt wird am Draht: jeder
Einlieferungsversuch und jede Annahme je Kanal.
"""
from __future__ import annotations

import json
import smtplib
import threading
import urllib.parse
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Callable, Optional

from app.config import Settings
from output.channels.premium_sms import PREMIUM_SMS_SENDER

KANAELE = ("email", "telegram", "sms", "premium_sms")

#: Empfaenger-Defaults; die Herkunftssperren (Worktree = Testlauf) schalten
#: ohnehin auf Test-Ziele um -- die Gegenstuecke werden deshalb deckungsgleich
#: gesetzt, sonst sperren die Waechter (#1476/#1288/#1336) vor dem Draht.
_MAIL_TO = "gregor-test@henemm.com"
_TELEGRAM_CHAT = "4405"
_SMS_TO = "+41790001405"
_PREMIUM_TO = "+41790002405"
_SEVEN_KEY = "rig-1405-key"
_TELEGRAM_TOKEN = "rig-1405-token"


class KanalRig:
    """Vier steuerbare Versandwege. ``modus[kanal]`` ist ``"ok"`` oder
    ``"fehler"``; ``telegram_fehler_bei`` (1-basierte Nummern innerhalb der
    seit dem letzten ``zaehler_leeren()`` eingegangenen Telegram-Anfragen)
    laesst gezielt einzelne Sprechblasen scheitern.

    ``email_modus_je_host`` erlaubt verschiedene Ausgaenge je Nutzer
    (Mandantentrennung): der Schluessel ist ``settings.smtp_host``.
    """

    def __init__(self, monkeypatch) -> None:
        self.modus: dict[str, str] = {k: "ok" for k in KANAELE}
        self.email_modus_je_host: dict[str, str] = {}
        self.telegram_fehler_bei: Optional[set[int]] = None
        self.versuche: dict[str, list] = {k: [] for k in KANAELE}
        self.angenommen: dict[str, list] = {k: [] for k in KANAELE}
        self._lock = threading.Lock()
        self._telegram_nr = 0

        self._telegram_server = self._starte_telegram()
        self._seven_server = self._starte_seven()
        self.telegram_base = f"http://127.0.0.1:{self._telegram_server.server_address[1]}"
        self.seven_url = f"http://127.0.0.1:{self._seven_server.server_address[1]}/api/sms"
        self._installiere_smtp(monkeypatch)

        from output.channels import telegram as telegram_mod

        monkeypatch.setattr(telegram_mod, "TELEGRAM_API_BASE", self.telegram_base)

    # ------------------------------------------------------------------ Zaehler

    def zaehler_leeren(self) -> None:
        with self._lock:
            self.versuche = {k: [] for k in KANAELE}
            self.angenommen = {k: [] for k in KANAELE}
            self._telegram_nr = 0

    def anzahl_versuche(self, kanal: str) -> int:
        return len(self.versuche[kanal])

    def anzahl_angenommen(self, kanal: str) -> int:
        return len(self.angenommen[kanal])

    def alle_versuche(self) -> int:
        return sum(len(v) for v in self.versuche.values())

    def alle_angenommen(self) -> int:
        return sum(len(v) for v in self.angenommen.values())

    def __repr__(self) -> str:  # erscheint in Fehlermeldungen
        return (
            "KanalRig(modus=%r, versuche=%r, angenommen=%r)" % (
                self.modus,
                {k: len(v) for k, v in self.versuche.items() if v},
                {k: len(v) for k, v in self.angenommen.items() if v},
            )
        )

    # ---------------------------------------------------------------- Settings

    def settings(
        self, *, smtp_host: str = "smtp.rig-1405.test",
        premium_reply_at: Optional[datetime] = None,
    ) -> Settings:
        """Vollstaendig konfigurierte Kanaele, alle Draehte zeigen auf diese
        Rig. Ob ein Kanal BENUTZT wird, entscheidet die Kanalwahl des Trips/
        Presets bzw. ``effective_channels`` -- nicht diese Settings.

        ``imap_*`` = ``None``: sonst wiche ``EmailOutput`` nach einem
        Fehlschlag auf den Ersatz-Postausgang aus, der an dieselbe Gegenstelle
        geht -- und der Totalausfall waere keiner.
        """
        reply_at = premium_reply_at or (datetime.now(timezone.utc) - timedelta(minutes=5))
        return Settings().model_copy(update={
            "is_test_mode": False,
            "smtp_host": smtp_host, "smtp_port": 2525,
            "smtp_user": "rig", "smtp_pass": "rig",
            "mail_to": _MAIL_TO, "mail_from": "gregor_zwanzig@henemm.com",
            "inbound_address": None,
            "imap_host": None, "imap_user": None, "imap_pass": None,
            "telegram_bot_token": _TELEGRAM_TOKEN, "telegram_chat_id": _TELEGRAM_CHAT,
            "telegram_test_bot_token": _TELEGRAM_TOKEN,
            "telegram_test_chat_id": _TELEGRAM_CHAT,
            "telegram_rate_limit_max_per_window": 10_000,
            "sms_gateway_url": self.seven_url, "seven_api_key": _SEVEN_KEY,
            "seven_sandbox_key": _SEVEN_KEY, "sms_to": _SMS_TO, "sms_from": None,
            "premium_sms_reply_to": _PREMIUM_TO, "premium_sms_reply_at": reply_at,
        })

    # ------------------------------------------------------------------- SMTP

    def _installiere_smtp(self, monkeypatch) -> None:
        from output.channels import email as email_module

        rig = self

        class _Socket:
            def settimeout(self, _t) -> None:
                pass

        class _Gegenstelle:
            def __init__(self, host, port, timeout=None) -> None:
                self._host = host
                self.sock = _Socket()

            def __enter__(self):
                return self

            def __exit__(self, *exc) -> bool:
                return False

            def starttls(self) -> None:
                pass

            def login(self, user, password) -> None:
                pass

            def sendmail(self, from_addr, to_addrs, msg) -> None:
                modus = rig.email_modus_je_host.get(self._host, rig.modus["email"])
                eintrag = {"host": self._host, "an": list(to_addrs), "roh": msg}
                with rig._lock:
                    rig.versuche["email"].append(eintrag)
                if modus != "ok":
                    raise smtplib.SMTPResponseException(554, b"5.0.0 rig-1405: abgelehnt")
                with rig._lock:
                    rig.angenommen["email"].append(eintrag)

        monkeypatch.setattr(email_module.smtplib, "SMTP", _Gegenstelle)
        # Nur Sicherheitsnetz: ein permanenter 5xx-Fehler wird ohnehin nicht
        # wiederholt; ein versehentlich transienter Fehler soll keine 14 s
        # Wartezeit kosten.
        monkeypatch.setattr(email_module.time, "sleep", lambda _s: None)

    # ---------------------------------------------------------------- Telegram

    def _starte_telegram(self) -> HTTPServer:
        rig = self

        class _Handler(BaseHTTPRequestHandler):
            def log_message(self, *_a) -> None:
                pass

            def do_POST(self) -> None:  # noqa: N802
                laenge = int(self.headers.get("Content-Length", 0))
                roh = self.rfile.read(laenge) if laenge else b"{}"
                try:
                    payload = json.loads(roh or b"{}")
                except ValueError:
                    payload = {"roh": roh.decode(errors="replace")}
                with rig._lock:
                    rig._telegram_nr += 1
                    nr = rig._telegram_nr
                    rig.versuche["telegram"].append(payload)
                    if rig.telegram_fehler_bei is not None:
                        scheitert = nr in rig.telegram_fehler_bei
                    else:
                        scheitert = rig.modus["telegram"] != "ok"
                    if not scheitert:
                        rig.angenommen["telegram"].append(payload)
                if scheitert:
                    body = json.dumps({"ok": False, "description": "rig-1405"}).encode()
                    self.send_response(500)
                else:
                    body = json.dumps({"ok": True, "result": {"message_id": nr}}).encode()
                    self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        server = HTTPServer(("127.0.0.1", 0), _Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        return server

    # ----------------------------------------------------------------- seven.io

    def _starte_seven(self) -> HTTPServer:
        rig = self

        class _Handler(BaseHTTPRequestHandler):
            def log_message(self, *_a) -> None:
                pass

            def do_POST(self) -> None:  # noqa: N802
                laenge = int(self.headers.get("Content-Length", 0))
                roh = self.rfile.read(laenge) if laenge else b""
                daten = {k: v[0] for k, v in urllib.parse.parse_qs(roh.decode()).items()}
                kanal = "premium_sms" if daten.get("from") == PREMIUM_SMS_SENDER else "sms"
                with rig._lock:
                    rig.versuche[kanal].append(daten)
                    scheitert = rig.modus[kanal] != "ok"
                    if not scheitert:
                        rig.angenommen[kanal].append(daten)
                if scheitert:
                    body = b"rig-1405: Gateway-Fehler"
                    self.send_response(500)
                else:
                    body = b"100"
                    self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        server = HTTPServer(("127.0.0.1", 0), _Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        return server

    def stoppen(self) -> None:
        for server in (self._telegram_server, self._seven_server):
            server.shutdown()
            server.server_close()


def kanal_auswahl(*kanaele: str) -> dict[str, bool]:
    """``alert_channels``-Override (Trip wie Ortsvergleich): genau diese Kanaele."""
    return {k: (k in kanaele) for k in KANAELE}


def premium_profil_schreiben(user_id: str, *, reply_at: datetime) -> None:
    """``user.json`` mit Tarif ``premium`` (SMS-Tageslimit 10, Premium-SMS 15,
    kein Alarm-Tagesdeckel) und frisch gelernter Garmin-Rueckadresse.

    Read-Modify-Write: Felder, die ein anderer Baustein schon geschrieben hat,
    bleiben erhalten.
    """
    from app.loader import get_data_dir

    pfad = get_data_dir(user_id) / "user.json"
    pfad.parent.mkdir(parents=True, exist_ok=True)
    try:
        profil = json.loads(pfad.read_text())
    except (OSError, ValueError):
        profil = {}
    profil.update({
        "id": user_id, "tier": "premium",
        "mail_to": _MAIL_TO, "sms_to": _SMS_TO, "sms_verified_number": _SMS_TO,
        "telegram_chat_id": _TELEGRAM_CHAT,
        "premium_sms_reply_to": _PREMIUM_TO,
        "premium_sms_reply_at": reply_at.isoformat().replace("+00:00", "Z"),
    })
    pfad.write_text(json.dumps(profil))


def wiederholungs_eintraege(user_id: str) -> dict[str, dict]:
    """Alle Backoff-Eintraege des Nutzers: Scopes ``<scope>:retry`` aus
    ``throttle_state.json``. Bewusst ohne Annahme ueber den Schluessel
    (Ereignis-Fingerabdruck) -- nur: gibt es einen laufenden Fehlversuchs-
    Backoff?"""
    from app.loader import get_data_dir

    pfad = get_data_dir(user_id) / "throttle_state.json"
    if not pfad.exists():
        return {}
    try:
        daten = json.loads(pfad.read_text())
    except ValueError:
        return {}
    return {
        scope: eintraege for scope, eintraege in daten.items()
        if isinstance(scope, str) and scope.endswith(":retry") and eintraege
    }


Lauf = Callable[..., object]

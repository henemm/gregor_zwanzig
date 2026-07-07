"""
Inbound Telegram Reader — Bot API long-polling for trip commands.

Polls getUpdates for new messages, extracts commands (free-text, no ### prefix),
delegates to TripCommandProcessor, and sends confirmations via NotificationService.

SPEC: docs/specs/modules/inbound_telegram_reader.md v1.0
"""
from __future__ import annotations

import logging
import re
from datetime import date, datetime, timezone

import httpx

from app.config import Settings
from app.loader import load_all_trips
from app.trip import Trip
from services.notification_service import NotificationService
from services.trip_command_processor import (
    CommandResult,
    InboundMessage,
    TripCommandProcessor,
    _BARE_KEYWORD_MAP,
)

logger = logging.getLogger(__name__)

TELEGRAM_API_BASE = "https://api.telegram.org"

_VALID_COMMANDS = {"ruhetag", "startdatum", "report", "abbruch", "status", "hilfe",
                   "glance", "heute", "morgen", "heute_gewitter",
                   "timeline_heute", "timeline_morgen", "now"}

_SHORTCUT_MAP = {
    "/s": "glance",
    "/status": "glance",  # AC-1: /status (mit Slash) ist Glance-Alias; nacktes "status" bleibt Etappenliste
    "/h": "heute",
    "/m": "morgen",
    "/hg": "heute_gewitter",
    "/th": "timeline_heute",
    "/tm": "timeline_morgen",
    # Slash-Varianten der Menü-Befehle (Telegram sendet getappte Befehle mit führendem Slash)
    "/glance": "glance",
    "/heute": "heute",
    "/morgen": "morgen",
    "/now": "now",
    "/n": "now",
    "/jetzt": "now",
    "/heute_gewitter": "heute_gewitter",
    "/gewitter": "heute_gewitter",
    "/timeline_heute": "timeline_heute",
    "/timeline_morgen": "timeline_morgen",
    "/hilfe": "hilfe",
}


_CALLBACK_QUERY_MAP = {
    "tl_today": "### query: timeline_heute",
    "tl_tomorrow": "### query: timeline_morgen",
    "glance": "### query: glance",
    "heute": "### query: heute",
    "morgen": "### query: morgen",
    "now": "### now",
    # Issue #1001: Aktionen-Bubble-Callbacks (act_*). "act_columns" hatte
    # ursprünglich bewusst kein Mapping (Spalten-Aenderung ist ein Frontend-
    # Trip-Editor-Flow, kein Text-Befehl-Aequivalent), was aber zu einem toten
    # Button ohne jedes Feedback führte (Adversary-Finding F002). Fix: statt
    # eines stillen No-Ops liefert der Klick jetzt einen informativen Hinweis
    # über TripCommandProcessor._show_columns_info() (kein Trip-Zustand wird
    # geändert).
    "act_overview": "### query: glance",
    "act_pause": "### pause",
    "act_skip": "### skip",
    "act_columns": "### columns",
    "act_help": "### hilfe",
}

_CALLBACK_DRILLDOWN_PATTERN = re.compile(r"^dd_(thunder|wind|precip|hours)_(today|tomorrow)$")


class InboundTelegramReader:
    """Polls Telegram Bot API and processes trip commands from messages."""

    def __init__(self) -> None:
        self._offset: int = 0
        self.sent_message_ids: list[int] = []  # Issue #686: collected for observability + cleanup
        self._notification_service = NotificationService()

    def poll_and_process(self, settings: Settings) -> int:
        """Long-polling: holt neue Updates, verarbeitet Befehle.

        Returns: Anzahl verarbeiteter Befehle.
        Gibt 0 zurück und macht keinen API-Call wenn settings.can_send_telegram() False ist.
        """
        if not settings.can_send_telegram():
            return 0

        token = settings.telegram_bot_token
        updates = self._get_updates(token)
        if not updates:
            return 0

        processed = 0
        max_update_id = self._offset - 1
        for update in updates:
            update_id = update.get("update_id", 0)
            if update_id > max_update_id:
                max_update_id = update_id
            try:
                if self._process_update(update, settings):
                    processed += 1
            except Exception as e:
                logger.error(f"Error processing update {update_id}: {e}")

        self._offset = max_update_id + 1
        return processed

    def _get_updates(self, token: str) -> list[dict]:
        """GET getUpdates with offset and timeout=30.

        Returns empty list on any error (fail-soft).
        """
        url = f"{TELEGRAM_API_BASE}/bot{token}/getUpdates"
        params = {"offset": self._offset, "timeout": 30}
        try:
            response = httpx.get(url, params=params, timeout=35)
            if response.status_code == 200:
                data = response.json()
                return data.get("result", [])
            logger.error(
                "getUpdates returned status %d: %s",
                response.status_code,
                response.text[:200],
            )
        except Exception as e:
            logger.error("getUpdates failed: %s", e)
        return []

    def _process_update(self, update: dict, settings: Settings) -> bool:
        """Verarbeitet ein einzelnes Update.

        Returns True wenn Update verarbeitet (nicht: ob Befehl erfolgreich).
        """
        callback = update.get("callback_query")
        if callback:
            return self._process_callback_query(callback, settings)

        message = update.get("message")
        if not message:
            return False

        text = message.get("text", "").strip()
        chat_id = str(message.get("chat", {}).get("id", ""))
        if not text or not chat_id:
            return False

        # /start TOKEN Handling — VOR user-resolve (user noch nicht bekannt)
        if text.startswith("/start "):
            token = text[len("/start "):].strip()
            if token:
                return self._process_start_command(token=token, chat_id=chat_id, settings=settings)

        # Resolve user-scoped settings for this chat_id
        user_id, user_settings = self._resolve_user_for_chat(chat_id, settings)

        # #1019: unbekannter Absender (kein User-Match) erhaelt Registrierungs-Hinweis,
        # KEINE Trip-/Wetterdaten. Betreiber-Account faellt hier nie hinein, da
        # `henning` regulaer per telegram_chat_id registriert ist.
        if user_id == "default":
            mid = self._notification_service.send_telegram_message(
                chat_id=chat_id,
                subject="Registrierung erforderlich",
                body=(
                    "Dieser Chat ist noch nicht mit einem Gregor-Zwanzig-Konto "
                    "verknuepft. Sende /start gefolgt von deinem Token (zu finden "
                    "im Account-Bereich auf gregor20.henemm.com)."
                ),
                settings=settings,
            )
            if mid is not None:
                self.sent_message_ids.append(mid)
            return True

        # Aktiven Trip ermitteln (user-scoped)
        trip = self._find_active_trip(user_id)
        if not trip:
            mid = self._notification_service.send_telegram_message(
                chat_id=chat_id,
                subject="Fehler",
                body="Kein aktiver Trip gefunden. Erstelle oder aktiviere einen Trip auf gregor20.henemm.com",
                settings=user_settings,
            )
            if mid is not None:
                self.sent_message_ids.append(mid)
            return True

        # Befehl parsen
        key, value = self._parse_command(text)
        if key is None:
            mid = self._notification_service.send_telegram_message(
                chat_id=chat_id,
                subject="Unbekannter Befehl",
                body="Bekannte Befehle: heute, morgen, jetzt, gewitter, ruhetag, status, stop, weiter, hilfe",
                settings=user_settings,
            )
            if mid is not None:
                self.sent_message_ids.append(mid)
            return True

        # InboundMessage bauen und verarbeiten
        # Query-Keys werden als "### query: <key>" kodiert
        from services.trip_command_processor import _QUERY_KEYS
        if key in _QUERY_KEYS:
            body = f"### query: {key}"
        elif value:
            body = f"### {key}: {value}"
        else:
            body = f"### {key}"

        inbound = InboundMessage(
            channel="telegram",
            trip_name=trip.name,
            body=body,
            sender=chat_id,
            received_at=datetime.now(tz=timezone.utc),
            user_id=user_id,
        )

        if key in _QUERY_KEYS:
            # Loading-Message senden, dann Wetterdaten on-demand holen,
            # dann in-place ersetzen (AC-4)
            loading_mid = self._notification_service.send_telegram_message(
                chat_id=chat_id,
                subject="⏳",
                body="⏳ Wetter wird geladen...",
                settings=user_settings,
            )
            result: CommandResult = TripCommandProcessor().process(inbound)
            # Issue #1007: heute/morgen haben bereits das volle Briefing per
            # Bubbles verschickt — die Lade-Nachricht braucht keine separate
            # Bestätigung mehr, nur noch das Aufräumen.
            if result.suppress_email_reply:
                if loading_mid is not None:
                    self._notification_service.delete_telegram_message(
                        chat_id=chat_id,
                        message_id=loading_mid,
                        settings=user_settings,
                    )
            elif loading_mid is not None:
                self._notification_service.edit_telegram_message_text(
                    chat_id=chat_id,
                    message_id=loading_mid,
                    text=f"[{result.confirmation_subject}]\n\n{result.confirmation_body}",
                    settings=user_settings,
                    reply_markup=result.reply_markup,
                )
                self.sent_message_ids.append(loading_mid)
            else:
                mid = self._notification_service.send_command_reply_telegram(
                    result=result,
                    chat_id=chat_id,
                    settings=user_settings,
                )
                if mid is not None:
                    self.sent_message_ids.append(mid)
        else:
            result = TripCommandProcessor().process(inbound)
            mid = self._notification_service.send_command_reply_telegram(
                result=result,
                chat_id=chat_id,
                settings=user_settings,
            )
            if mid is not None:
                self.sent_message_ids.append(mid)
        return True

    def _process_callback_query(self, callback: dict, settings: Settings) -> bool:
        """Verarbeitet einen Button-Klick (callback_query) — Zoom-Navigation.

        editMessageText ersetzt die Nachricht in-place; answerCallbackQuery wird
        IMMER aufgerufen (AC-2: Spinner beenden, auch im Fehlerpfad).
        Returns True (Update verarbeitet).
        """
        cq_id = callback.get("id")
        data = (callback.get("data") or "").strip()
        msg = callback.get("message") or {}
        chat_id = str(msg.get("chat", {}).get("id", ""))
        message_id = msg.get("message_id")

        user_id, user_settings = self._resolve_user_for_chat(chat_id, settings)
        try:
            # #1019: unbekannter Absender (kein User-Match) erhaelt auch beim
            # Button-Klick nur den Registrierungs-Hinweis, KEINE Trip-/Wetter-
            # daten. Die angeklickte Nachricht wird in-place ersetzt;
            # answer_telegram_callback_query laeuft weiterhin im finally.
            if user_id == "default":
                if message_id is not None and chat_id:
                    self._notification_service.edit_telegram_message_text(
                        chat_id=chat_id,
                        message_id=message_id,
                        text=(
                            "Dieser Chat ist noch nicht mit einem Gregor-Zwanzig-Konto "
                            "verknuepft. Sende /start gefolgt von deinem Token (zu finden "
                            "im Account-Bereich auf gregor20.henemm.com)."
                        ),
                        settings=settings,
                    )
                return True

            body = self._callback_to_body(data)  # None bei unbekannt
            if body and message_id is not None and chat_id:
                trip = self._find_active_trip(user_id)
                if trip:
                    inbound = InboundMessage(
                        channel="telegram",
                        trip_name=trip.name,
                        body=body,
                        sender=chat_id,
                        received_at=datetime.now(tz=timezone.utc),
                        user_id=user_id,
                    )
                    result: CommandResult = TripCommandProcessor().process(inbound)
                    # Issue #1007: heute/morgen per Button haben bereits das
                    # volle Briefing per Bubbles verschickt — keine separate
                    # Bestätigung mehr in die alte Nachricht editieren.
                    if not result.suppress_email_reply:
                        self._notification_service.edit_telegram_message_text(
                            chat_id=chat_id,
                            message_id=message_id,
                            text=f"[{result.confirmation_subject}]\n\n{result.confirmation_body}",
                            settings=user_settings,
                            reply_markup=result.reply_markup,
                        )
        finally:
            if cq_id:
                self._notification_service.answer_telegram_callback_query(
                    callback_query_id=cq_id,
                    settings=user_settings,
                )
        return True

    def _callback_to_body(self, data: str) -> str | None:
        """Mappt callback_data auf einen Processor-Body. None bei unbekanntem Wert."""
        if data in _CALLBACK_QUERY_MAP:
            return _CALLBACK_QUERY_MAP[data]
        if _CALLBACK_DRILLDOWN_PATTERN.match(data):
            return f"### {data}"
        return None

    def _find_active_trip(self, user_id: str = "default") -> Trip | None:
        """Aktiver Trip = erster Trip mit Datum-Overlap.

        Fallback: nächster zukünftiger Trip.
        Gibt None zurück wenn keine Trips existieren.
        """
        today = date.today()
        trips = load_all_trips(user_id)
        if not trips:
            return None

        # 1. Overlap: stage[0].date <= heute <= stage[-1].date
        for trip in trips:
            if not trip.stages:
                continue
            if trip.stages[0].date <= today <= trip.stages[-1].date:
                return trip

        # 2. Fallback: frühester zukünftiger Trip
        future = [t for t in trips if t.stages and t.stages[0].date > today]
        if future:
            return min(future, key=lambda t: t.stages[0].date)

        return None

    def _resolve_user_for_chat(
        self, chat_id: str, base_settings: Settings, data_dir: str = "data"
    ) -> tuple[str, Settings]:
        """Resolve user_id and user-scoped Settings for an incoming Telegram chat ID.

        Args:
            chat_id: Telegram chat ID (as string)
            base_settings: Base Settings object to derive user profile from
            data_dir: Root data directory (default: "data")

        Returns:
            (user_id, user_scoped_settings) — user_id is "default" if no match
        """
        from app.loader import lookup_user_by_telegram_chat_id
        user_id = lookup_user_by_telegram_chat_id(chat_id, data_dir=data_dir) or "default"
        return user_id, base_settings.with_user_profile(user_id)

    def _process_start_command(self, token: str, chat_id: str, settings: Settings) -> bool:
        """Verarbeitet /start TOKEN — registriert chat_id beim Go-Backend."""
        try:
            resp = httpx.post(
                "http://localhost:8090/api/internal/telegram-connect",
                json={"token": token, "chat_id": chat_id},
                timeout=5,
            )
            if resp.status_code == 200:
                logger.info(f"Telegram chat_id {chat_id} via token registriert")
                try:
                    confirm_settings = settings.model_copy(update={"telegram_chat_id": chat_id})
                    self._notification_service.send_telegram_message(
                        chat_id=chat_id,
                        subject="Verbunden",
                        body="✓ Du bist jetzt mit Gregor verbunden! Sende 'hilfe' für verfügbare Befehle.",
                        settings=confirm_settings,
                    )
                except Exception as ce:
                    logger.warning(f"Bestätigungsnachricht fehlgeschlagen: {ce}")
            else:
                logger.warning(f"telegram-connect returned {resp.status_code}")
        except Exception as e:
            logger.error(f"telegram-connect Fehler: {e}")
        return True

    def _parse_command(self, text: str) -> tuple[str | None, str | None]:
        """Parst ersten nicht-leeren Satz: 'ruhetag 2' → ('ruhetag', '2').

        Immer lowercase. Unbekannte Befehle → (None, None).
        Auflösungs-Reihenfolge:
          1. Slash-Shortcuts (_SHORTCUT_MAP): /h, /m, /s, /hg, /jetzt, ...
          2. Bare Keywords (_BARE_KEYWORD_MAP, channel-agnostisch wie E-Mail):
             heute, morgen, jetzt, gewitter, stop, weiter, hilfe, status, ...
             stop→abbruch, jetzt→now, gewitter→heute_gewitter etc.
          3. _VALID_COMMANDS-Fallback: startdatum, report (nicht in _BARE_KEYWORD_MAP).
        Kein '### ' Prefix nötig — Freitext.
        """
        first_line = next(
            (line.strip() for line in text.splitlines() if line.strip()),
            "",
        )
        if not first_line:
            return None, None

        # Kurzbefehl-Mapping: /s /h /m /hg
        lower_first = first_line.lower()
        if lower_first in _SHORTCUT_MAP:
            return _SHORTCUT_MAP[lower_first], None

        parts = lower_first.split(None, 1)
        key = parts[0]
        value = parts[1].strip() if len(parts) > 1 else None

        # Bare keyword → resolve via shared _BARE_KEYWORD_MAP (channel-agnostic)
        if key in _BARE_KEYWORD_MAP:
            return _BARE_KEYWORD_MAP[key], value or None

        if key not in _VALID_COMMANDS:
            return None, None

        return key, value or None


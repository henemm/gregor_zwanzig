"""Telegram output channel via Bot API."""
import logging
import re

import httpx

from app.config import Settings
from output.channels.base import OutputError

logger = logging.getLogger(__name__)

TELEGRAM_API_BASE = "https://api.telegram.org"
MAX_MESSAGE_LENGTH = 4096

# Telegram-Bot-API erlaubt in parse_mode=HTML eine begrenzte Menge an Tags.
# Wir tracken nur Paare von öffnenden/schließenden Tags; self-closing Tags werden
# ignoriert, weil sie keine Balance benötigen.
_HTML_TAG_RE = re.compile(r"<(/?)([a-zA-Z][a-zA-Z0-9_]*)[^>]*>")


def _truncate_html(message: str, max_len: int) -> str:
    """Kürze message auf max_len Zeichen, ohne HTML-Tags mittig abzuschneiden.

    Offene Tags am Ende werden automatisch geschlossen. Plaintext wird wie bisher
    hart gekürzt.
    """
    if len(message) <= max_len:
        return message

    open_tags: list[str] = []
    result_parts: list[str] = []
    pos = 0

    for match in _HTML_TAG_RE.finditer(message):
        # Text vor dem Tag
        text = message[pos:match.start()]
        pos = match.end()

        # So viel Text wie möglich unter Berücksichtigung der noch zu schließenden Tags
        closing_overhead = sum(len(f"</{tag}>") for tag in open_tags)
        available = max_len - sum(len(p) for p in result_parts) - closing_overhead
        if available > 0:
            result_parts.append(text[:available])

        if sum(len(p) for p in result_parts) + closing_overhead >= max_len:
            break

        slash, tag = match.group(1), match.group(2)
        tag_key = tag.lower()
        current_len = sum(len(p) for p in result_parts)

        if slash:
            # Schließendes Tag: IMMER den kanonischen </tag> emittieren statt des
            # rohen Match-Texts (Adversary-Finding F001) — dessen Länge ist die,
            # mit der closing_overhead reserviert wurde, egal wie viel Rauschen
            # (Whitespace/Attribute) im echten Tag steckt. Tag-Namen werden beim
            # Vergleichen/Poppen case-insensitiv normalisiert (Finding F002),
            # damit z.B. </B> das offene <b> schließt statt eine Waise zu bilden.
            if open_tags and open_tags[-1].lower() == tag_key:
                closing_tag = f"</{open_tags[-1]}>"
                open_tags.pop()
                result_parts.append(closing_tag)
        else:
            # Öffnendes Tag: nur anhängen, wenn danach noch Platz für das Tag
            # SELBST plus alle (inkl. dieses neuen) noch offenen Schließ-Tags bleibt.
            # Sonst Tag nicht öffnen und Schleife sauber beenden (Issue #976).
            new_closing_overhead = closing_overhead + len(f"</{tag}>")
            if current_len + len(match.group(0)) + new_closing_overhead > max_len:
                break
            result_parts.append(match.group(0))
            open_tags.append(tag)

        if sum(len(p) for p in result_parts) + sum(len(f"</{t}>") for t in open_tags) >= max_len:
            break

    else:
        # Kein weiteres Tag mehr: Resttext ggf. anhängen.
        closing_overhead = sum(len(f"</{tag}>") for tag in open_tags)
        available = max_len - sum(len(p) for p in result_parts) - closing_overhead
        if available > 0:
            result_parts.append(message[pos:pos + available])

    # Offene Tags in umgekehrter Reihenfolge schließen.
    for tag in reversed(open_tags):
        result_parts.append(f"</{tag}>")

    return "".join(result_parts)

BOT_COMMANDS = [
    {"command": "glance", "description": "🌤️ Wetter-Überblick (heute & morgen)"},
    {"command": "heute", "description": "📅 Nur heute"},
    {"command": "morgen", "description": "📅 Nur morgen"},
    {"command": "now", "description": "🌂 Nowcast — Regen/Gewitter in den nächsten 2h"},
    {"command": "heute_gewitter", "description": "⛈️ Gewitter-Fokus heute"},
    {"command": "timeline_heute", "description": "🕐 Timeline heute"},
    {"command": "timeline_morgen", "description": "🕐 Timeline morgen"},
    {"command": "hilfe", "description": "ℹ️ Verfügbare Befehle"},
]


def _api_ok(response: httpx.Response) -> bool:
    """True wenn die Bot-API-Antwort ein ok:true-JSON ist (HTTP 200 garantiert kein Erfolg)."""
    try:
        return bool(response.json().get("ok"))
    except ValueError:
        return False


class TelegramOutput:
    """Sends messages via the Telegram Bot API.

    Implements the OutputChannel protocol: send(subject, body).
    Uses fire-and-forget semantics — one attempt with a 10s timeout.
    On failure, logs the error; the next scheduled run is the implicit retry.
    """

    # Issue #1007 (Observability, "Kein Job ohne Observability"): der
    # Scheduler-Versand (send_on_demand_report → Briefing-Bubbles) läuft ohne
    # Reader-Instanz ab und ist sonst von außen nicht beobachtbar/aufräumbar.
    # Klassen-Register über alle Instanzen, gedeckelt auf die letzten 50 IDs.
    recent_message_ids: list[int] = []
    _RECENT_MESSAGE_IDS_MAX = 50

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings if settings else Settings()
        self._timeout = 10
        self.sent_message_ids: list[int] = []

    @property
    def name(self) -> str:
        return "telegram"

    def send(
        self, subject: str, body: str, reply_markup: dict | None = None,
        *, parse_mode: str | None = None, suppress_subject_line: bool = False,
    ) -> int | None:
        """Send a Telegram message via Bot API.

        Args:
            subject: Message subject shown as header.
            body: Message body text.
            reply_markup: Optional Inline-Keyboard dict (Telegram Bot API format).
                          If None, payload is identical to the legacy format (no key added).
            parse_mode: Optional Bot-API parse mode (e.g. "HTML"). None (default)
                        omits the field — legacy behavior (Issue #952).
            suppress_subject_line: True omits the "[{subject}]\\n\\n" prefix, sending
                                    body verbatim. False (default) is legacy behavior.

        Returns:
            message_id (int) on success (HTTP 200 + ok:true), None otherwise.
            Backward-compatible: existing callers that ignore the return value are unaffected.
        """
        token = self._settings.telegram_bot_token
        chat_id = self._settings.telegram_chat_id
        url = f"{TELEGRAM_API_BASE}/bot{token}/sendMessage"

        message = body if suppress_subject_line else f"[{subject}]\n\n{body}"
        if len(message) > MAX_MESSAGE_LENGTH:
            is_html = parse_mode == "HTML"
            message = _truncate_html(message, MAX_MESSAGE_LENGTH) if is_html else message[:MAX_MESSAGE_LENGTH]
            logger.warning("Telegram message truncated to %d chars", MAX_MESSAGE_LENGTH)

        payload: dict = {"chat_id": chat_id, "text": message}
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup
        if parse_mode is not None:
            payload["parse_mode"] = parse_mode

        try:
            response = httpx.post(url, json=payload, timeout=self._timeout)
            if response.status_code == 200 and _api_ok(response):
                logger.info("Telegram message sent (subject=%r)", subject)
                try:
                    mid = int(response.json()["result"]["message_id"])
                except (KeyError, TypeError, ValueError):
                    return None
                self.sent_message_ids.append(mid)
                TelegramOutput.recent_message_ids.append(mid)
                del TelegramOutput.recent_message_ids[:-self._RECENT_MESSAGE_IDS_MAX]
                return mid
            else:
                logger.error(
                    "Telegram API returned status %d: %s",
                    response.status_code,
                    response.text[:200],
                )
                raise OutputError("telegram", f"Telegram API returned status {response.status_code}")
        except httpx.TimeoutException:
            logger.error("Telegram send timed out after %ds (subject=%r)", self._timeout, subject)
            raise OutputError("telegram", f"Telegram send timed out after {self._timeout}s")
        except httpx.HTTPError as exc:
            logger.error("Telegram send failed: %s", exc)
            raise OutputError("telegram", f"Telegram send failed: {exc}") from exc

    def delete_message(self, chat_id, message_id) -> bool:
        """Delete a message via deleteMessage.

        fail-soft: returns False on any error (non-200, API rejection, network issues).
        Used by the test fixture for cleanup after delivering test messages.

        Args:
            chat_id: Telegram chat ID (str or int).
            message_id: ID of the message to delete (int).

        Returns:
            True on HTTP 200 + ok:true, False otherwise.
        """
        token = self._settings.telegram_bot_token
        url = f"{TELEGRAM_API_BASE}/bot{token}/deleteMessage"
        payload: dict = {"chat_id": chat_id, "message_id": message_id}

        try:
            response = httpx.post(url, json=payload, timeout=self._timeout)
            if response.status_code == 200 and _api_ok(response):
                logger.info("Telegram deleteMessage ok (message_id=%r)", message_id)
                # Issue #1007: recent_message_ids trackt NUR noch existierende
                # Nachrichten — sonst würde ein Aufräum-Durchlauf dieselbe ID
                # ein zweites Mal löschen wollen (z.B. eine bereits vom Reader
                # selbst geräumte Lade-Nachricht) und Telegram meldet 400.
                try:
                    TelegramOutput.recent_message_ids.remove(message_id)
                except ValueError:
                    pass
                return True
            logger.warning(
                "deleteMessage returned status %d: %s",
                response.status_code,
                response.text[:200],
            )
            return False
        except httpx.HTTPError as exc:
            logger.warning("deleteMessage failed (fail-soft): %s", exc)
            return False

    def edit_message_text(
        self, chat_id, message_id, text: str, reply_markup: dict | None = None
    ) -> None:
        """Edit an existing message in-place via editMessageText (Zoom-Navigation).

        fail-soft: a non-200 / HTTPError / Timeout is only logged, never raised —
        "message is not modified" and stale messages must not crash the webhook.
        """
        token = self._settings.telegram_bot_token
        url = f"{TELEGRAM_API_BASE}/bot{token}/editMessageText"

        message = text
        if len(message) > MAX_MESSAGE_LENGTH:
            message = _truncate_html(message, MAX_MESSAGE_LENGTH)
            logger.warning("Telegram edit message truncated to %d chars", MAX_MESSAGE_LENGTH)

        payload: dict = {"chat_id": chat_id, "message_id": message_id, "text": message}
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup

        try:
            response = httpx.post(url, json=payload, timeout=self._timeout)
            if response.status_code != 200:
                logger.warning(
                    "editMessageText returned status %d: %s",
                    response.status_code,
                    response.text[:200],
                )
        except httpx.HTTPError as exc:
            logger.warning("editMessageText failed (fail-soft): %s", exc)

    def answer_callback_query(self, callback_query_id, text: str | None = None) -> None:
        """Acknowledge a callback_query via answerCallbackQuery (stop loading spinner).

        fail-soft: errors are only logged, never raised.
        """
        token = self._settings.telegram_bot_token
        url = f"{TELEGRAM_API_BASE}/bot{token}/answerCallbackQuery"

        payload: dict = {"callback_query_id": callback_query_id}
        if text is not None:
            payload["text"] = text

        try:
            response = httpx.post(url, json=payload, timeout=self._timeout)
            if response.status_code != 200:
                logger.warning(
                    "answerCallbackQuery returned status %d: %s",
                    response.status_code,
                    response.text[:200],
                )
        except httpx.HTTPError as exc:
            logger.warning("answerCallbackQuery failed (fail-soft): %s", exc)

    def set_my_commands(self, commands: list[dict] | None = None) -> None:
        """Register Bot-Menü commands via setMyCommands.

        Args:
            commands: List of command dicts with 'command' and 'description' keys.
                      Defaults to BOT_COMMANDS when None.
        """
        token = self._settings.telegram_bot_token
        url = f"{TELEGRAM_API_BASE}/bot{token}/setMyCommands"
        payload = {"commands": commands if commands is not None else BOT_COMMANDS}

        try:
            response = httpx.post(url, json=payload, timeout=self._timeout)
            if response.status_code != 200:
                raise OutputError("telegram", f"setMyCommands returned status {response.status_code}")
            # Bot-API kann HTTP 200 mit ok:false liefern → als Fehler behandeln.
            if not _api_ok(response):
                raise OutputError("telegram", f"setMyCommands rejected: {response.text[:200]}")
            logger.info("Telegram setMyCommands succeeded (%d commands)", len(payload["commands"]))
        except httpx.TimeoutException:
            raise OutputError("telegram", f"setMyCommands timed out after {self._timeout}s")
        except httpx.HTTPError as exc:
            raise OutputError("telegram", f"setMyCommands failed: {exc}") from exc

    def get_my_commands(self) -> list[dict]:
        """Fetch the currently registered Bot-Menü commands via getMyCommands.

        Returns:
            List of command dicts as returned by the Telegram Bot API.
        """
        token = self._settings.telegram_bot_token
        url = f"{TELEGRAM_API_BASE}/bot{token}/getMyCommands"

        try:
            response = httpx.post(url, json={}, timeout=self._timeout)
            if response.status_code != 200:
                raise OutputError("telegram", f"getMyCommands returned status {response.status_code}")
            try:
                data = response.json()
            except ValueError as exc:  # nicht-JSON-Body → sauberer OutputError statt rohem Decode-Fehler
                raise OutputError("telegram", f"getMyCommands returned non-JSON body: {exc}") from exc
            if not data.get("ok"):
                raise OutputError("telegram", f"getMyCommands rejected: {response.text[:200]}")
            return data.get("result", [])
        except httpx.TimeoutException:
            raise OutputError("telegram", f"getMyCommands timed out after {self._timeout}s")
        except httpx.HTTPError as exc:
            raise OutputError("telegram", f"getMyCommands failed: {exc}") from exc

"""
Inbound Telegram Reader — verarbeitet Trip-Befehle aus Telegram-Updates.

Updates kommen ausschliesslich ueber den Webhook (api/routers/webhook.py, #637);
der fruehere Poll-Pfad ist entfernt (#1369). Extrahiert Befehle (Freitext, kein
### Praefix), delegiert an TripCommandProcessor und sendet Antworten ueber
NotificationService.

SPEC: docs/specs/modules/inbound_telegram_reader.md v1.0
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from urllib.parse import urlsplit

from app.config import Settings, resolve_public_host
from app.loader import compare_preset_to_dict, load_all_trips, load_compare_presets
from app.trip import Trip
from i18n import Lang, resolve_user_lang, t
from lib.go_internal import post_internal
from output.channels.recipient import _current_inbound_sender
from output.channels.seven_io_base import mask_number
from services.notification_service import NotificationService
from services.trip_command_processor import TripCommandProcessor as _ParseNurProcessor
from services.trip_command_processor import (
    CommandResult,
    InboundMessage,
    TripCommandProcessor,
    befehl_markieren,
    befehl_messung,
    ganzzeilen_befehl,
    _BARE_KEYWORD_MAP,
    _erste_zeile,
    _erstes_wort,
    _metric_id_for_word,
    _ohne_praefix,
    _ohne_zitat,
    _QUERY_KEYS,
    _VALID_COMMANDS as _PROCESSOR_COMMANDS,
    match_leading_name,
    telegram_englisch,
    unknown_command_body,
)
from services.trip_selection import (
    ZIELLOS_SCHLUESSEL,
    pick_active_trip,
    resolve_active_target,
    resolve_command_target,
    resolve_trip_only_target,
)

logger = logging.getLogger(__name__)


def _registrierungs_hinweis(host: str | None) -> str:
    """Hinweis fuer einen Chat ohne Konto (#1019) -- deutsch, denn ohne Konto
    gibt es keine Kontosprache (#2673 Annahme 4)."""
    if host:
        return t("inbound.telegram.registrierung.text_host", "de", host=host)
    return t("inbound.telegram.registrierung.text", "de")

def _bare_public_host(settings: Settings) -> str | None:
    """Blosser Host ohne Schema — fuer die Fliesstext-Erwaehnung in Chat-Antworten."""
    full = resolve_public_host(settings)
    return urlsplit(full).netloc or None if full else None


# Issue #2134: keine eigene (achte) Befehlsliste mehr — der Reader kennt genau
# das, was der Prozessor ausfuehrt (Steuerbefehle) plus die lesenden
# Abfrage-Schluessel, die er selbst als `### query: <key>` kodiert.
_VALID_COMMANDS = _PROCESSOR_COMMANDS | _QUERY_KEYS
_VERGLEICH_LADE_KEYS = frozenset({"report", "heute", "morgen"})  # #2282 S2

_SHORTCUT_MAP = {
    "/s": "glance",
    # Issue #2417 AC-28: der fruehere "/status"->"glance"-Alias entfaellt --
    # /status fuehrt jetzt wie das nackte "status" die Etappenliste aus
    # (Tech-Lead-Entscheidung, Spec-Abschnitt "BOT_COMMANDS — Merge, nicht
    # Ersatz"). Ohne eigenen Eintrag faellt "/status" durch _ohne_praefix auf
    # "status" zurueck, das direkt in _BARE_KEYWORD_MAP steht.
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
    "/strecke": "strecke",  # Issue #2051 S4
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

# Issue #2417 AC-20: unsichtbare Zeichen, die ein Befehlswort umgeben koennen
# (BOM am Anfang eines Copy-Paste-Texts, Zero-Width-Space als App-Artefakt) --
# ``str.strip()`` faengt bereits NBSP und regulaeren Leerraum (beide zaehlen
# als ``str.isspace()``), aber NICHT diese beiden Zeichen (kein Leerraum im
# Unicode-Sinn).
_UNSICHTBARE_ZEICHEN = ("﻿", "​")
#: Satzzeichen UNMITTELBAR am Befehlswort (".", "!", "?", ",") — bewusst NUR
#: diese vier, kein pauschales alphanumerisches Trimmen: sonst wuerde ein
#: echtes Fremdwort wie "Hilfen" faelschlich zu "Hilfe" (Praefix-Ausartung,
#: Gegenprobe der Spec).
_BEFEHLSWORT_SATZZEICHEN = ".!?,"


def _ohne_unsichtbare_zeichen(text: str) -> str:
    """Entfernt BOM/ZWSP ueberall im Text (AC-20) — beide sind unsichtbar,
    ihre Position im Freitext ist deshalb ohne Belang."""
    for zeichen in _UNSICHTBARE_ZEICHEN:
        text = text.replace(zeichen, "")
    return text


def _ohne_satzzeichen_am_wortende(word: str) -> str:
    """Streift Satzzeichen, die UNMITTELBAR am Ende eines Befehlsworts
    haengen (AC-20, z.B. 'hilfe.', 'pause!') — ``rstrip`` nur mit den vier
    definierten Zeichen, kein generisches alphanumerisches Trimmen."""
    return word.rstrip(_BEFEHLSWORT_SATZZEICHEN)


class InboundTelegramReader:
    """Processes trip commands from Telegram webhook updates."""

    def __init__(self) -> None:
        self.sent_message_ids: list[int] = []  # Issue #686: collected for observability + cleanup
        self._notification_service: NotificationService | None = None

    def _ensure_notification_service(self, settings: Settings) -> None:
        """#2151 Scheibe C: den Versanddienst erst mit den vorliegenden
        ``settings`` bauen -- nie nutzerlos (kein ``with_user_profile("default")``).
        Die genutzten Methoden lesen ohnehin nur die explizit uebergebenen
        Nutzer-Settings."""
        if self._notification_service is None:
            self._notification_service = NotificationService(settings=settings)

    def _process_update(self, update: dict, settings: Settings) -> bool:
        """Verarbeitet ein einzelnes Update.

        Returns True wenn Update verarbeitet (nicht: ob Befehl erfolgreich).
        """
        self._ensure_notification_service(settings)
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
        # Issue #1412 S4a: Herkunftsbeleg "Absender des laufenden Updates" --
        # nur innerhalb dieses Updates darf an chat_id geantwortet werden.
        token = _current_inbound_sender.set(chat_id)
        try:
            with befehl_messung("telegram"):
                return self._process_message(text, chat_id, settings)
        finally:
            _current_inbound_sender.reset(token)

    def _process_message(self, text: str, chat_id: str, settings: Settings) -> bool:
        """Verarbeitet eine geparste Textnachricht (innerhalb des Belegs)."""
        # /start TOKEN Handling — VOR user-resolve (user noch nicht bekannt)
        if text.startswith("/start "):
            token = text[len("/start "):].strip()
            if token:
                return self._process_start_command(token=token, chat_id=chat_id, settings=settings)

        # Resolve user-scoped settings for this chat_id
        user_id, user_settings = self._resolve_user_for_chat(chat_id, settings)
        if self._ist_gesperrt(user_id, chat_id):
            return True

        # #1019: unbekannter Absender (kein User-Match) erhaelt Registrierungs-Hinweis,
        # KEINE Trip-/Wetterdaten. Betreiber-Account faellt hier nie hinein, da
        # `henning` regulaer per telegram_chat_id registriert ist.
        if user_id is None:
            host = _bare_public_host(settings)
            mid = self._notification_service.send_telegram_message(
                chat_id=chat_id,
                subject=t("inbound.telegram.registrierung.betreff", "de"),
                body=_registrierungs_hinweis(host),
                # #2168/#1412 S4a: Antwort an den fragenden Chat (inbound_reply).
                settings=settings,
            )
            if mid is not None:
                self.sent_message_ids.append(mid)
            return True

        # Aktiven Trip/Ortsvergleich ermitteln (user-scoped)
        # #1727 S5a: EIN Zeitpunkt fuer Auswahl UND Nachrichtenstempel --
        # vorher zwei knapp versetzte datetime.now()-Aufrufe, die an der
        # Tagesgrenze auf verschiedene Ortstage fallen konnten.
        now_utc = datetime.now(tz=timezone.utc)
        # #2673: Kontosprache EINMAL je Nachricht, aus dem Konto dieses Chats.
        lang = resolve_user_lang(user_id)
        trips = load_all_trips(user_id)
        presets = [compare_preset_to_dict(p) for p in load_compare_presets(user_id)]

        # Issue #2282 Abschnitt 2/4: ein vorangestellter Name hat Vorrang vor
        # der aktiven Auswahl — Namensgleichheit/Kollision loest `process()`
        # selbst auf (Abschnitt 4/AC-7).
        named = match_leading_name(text, trips, presets)
        if named is not None:
            name_prefix, rest, name_kind, name_ziel = named
            key, body = self._command_body(rest)
            if key is None:
                befehl_markieren(None)
                self._send_unknown_command(chat_id, user_settings, lang)
                return True
            # Adversary F001-Nachtrag (#2282 Fix-Loop 2): match_leading_name
            # kennt Kind/Objekt des Treffers bereits -- direkt uebernehmen,
            # keine zweite Suche. Bei Namensgleichheit (name_kind is None)
            # bleibt resolved_kind unveraendert None (process() loest die
            # Rueckfrage selbst auf); die Lade-Nachricht ist in BEIDEN
            # Nicht-Trip-Faellen (Vergleich ODER Namensgleichheit) falsch.
            resolved_kind = "vergleich" if name_kind == "vergleich" else None
            resolved_preset_id = name_ziel.get("id") if name_kind == "vergleich" else None
            inbound = InboundMessage(
                channel="telegram", trip_name=name_prefix, body=body,
                sender=chat_id, received_at=now_utc, user_id=user_id,
                resolved_kind=resolved_kind, resolved_preset_id=resolved_preset_id,
                # #2417 AC-5: Stil des benannten Ziels; bei Namensgleichheit
                # (kein eindeutiges Ziel) das gesendete Wort.
                englisch=telegram_englisch(ziel=name_ziel, wort=_erstes_wort(rest)),
            )
            self._dispatch_and_reply(
                key, inbound, chat_id, user_settings,
                ladehinweis_erlaubt=(name_kind == "route"), lang=lang,
            )
            return True

        # Befehl parsen UND kodieren — ein Einstieg, damit ein Test denselben
        # Weg nimmt wie der Produktivpfad (Issue #2134). Issue #2417: die
        # Klassifizierung entscheidet VOR jeder Zielaufloesung, ob ueberhaupt
        # ein Trip/Vergleich geladen werden muss (AC-15/AC-16/AC-17) — vorher
        # lief `resolve_active_target` unklassifiziert fuer JEDEN Befehl und
        # blockierte z.B. "hilfe" bei Trip+Vergleich mit einer Rueckfrage (B1).
        key, body = self._command_body(text)
        if key is None:
            befehl_markieren(None)
            self._send_unknown_command(chat_id, user_settings, lang)
            return True

        # #2417 AC-5/Abschnitt H: ohne eindeutiges Ziel folgt die Sprache dem
        # gesendeten Wort, mit Ziel dessen telegram_style.
        englisch = telegram_englisch(wort=_erstes_wort(text))
        if key in ZIELLOS_SCHLUESSEL:
            # AC-15: "hilfe"/"columns"/"kuerzel" brauchen keine Trip-/Vergleichswahl.
            trip_name, resolved_kind, resolved_preset_id = "", None, None
            ladehinweis_erlaubt = False
        else:
            ziel = resolve_command_target(
                key, trips, presets, now_utc, channel="telegram", englisch=englisch,
                lang=lang,
            )
            if ziel.kind is None:
                befehl_markieren(key)
                # Issue #2282 AC-5: identischer Text wie Premium-SMS, kein
                # Host-Zusatz mehr (der wuerde die Kanalgleichheit brechen).
                mid = self._notification_service.send_telegram_message(
                    chat_id=chat_id,
                    subject=t("inbound.antwort.intern.betreff", "en" if englisch else lang),
                    body=ziel.text, settings=user_settings,
                )
                if mid is not None:
                    self.sent_message_ids.append(mid)
                return True

            englisch = telegram_englisch(ziel=ziel.target)
            if ziel.kind == "route":
                trip_name, resolved_kind, resolved_preset_id = ziel.target.name, None, None
            else:
                preset = ziel.target
                trip_name = preset.get("name", "")
                resolved_kind, resolved_preset_id = "vergleich", preset.get("id")
            ladehinweis_erlaubt = (ziel.kind == "route")

        inbound = InboundMessage(
            channel="telegram",
            trip_name=trip_name,
            body=body,
            sender=chat_id,
            received_at=now_utc,
            user_id=user_id,
            resolved_kind=resolved_kind,
            resolved_preset_id=resolved_preset_id,
            englisch=englisch,
        )
        self._dispatch_and_reply(
            key, inbound, chat_id, user_settings,
            ladehinweis_erlaubt=ladehinweis_erlaubt, lang=lang,
        )
        return True

    def _send_unknown_command(self, chat_id: str, user_settings: Settings,
                              lang: Lang = "de") -> None:
        mid = self._notification_service.send_telegram_message(
            chat_id=chat_id,
            subject=t("inbound.unbekannt.betreff", lang),
            # Issue #2134: derselbe abgeleitete Text wie im Prozessor —
            # vorher war das die achte, eigenstaendig gepflegte Liste.
            # #2417 AC-19: weder Ziel noch Wort -> Kontosprache; deutsch mit
            # englischem Hinweis (#2673: der Hinweis entfaellt fuer en).
            body=unknown_command_body(t("inbound.unbekannt.telegram", lang), lang=lang)
            + ("\nEnglish: send HELP" if lang == "de" else ""),
            settings=user_settings,
        )
        if mid is not None:
            self.sent_message_ids.append(mid)

    def _dispatch_and_reply(
        self, key: str, inbound: InboundMessage, chat_id: str, user_settings: Settings,
        *, ladehinweis_erlaubt: bool = True, lang: Lang = "de",
    ) -> None:
        """Fuehrt `process()` aus und schickt die Antwort — Query-Keys mit
        Lade-Zwischennachricht (AC-4), sonst direkt. Extrahiert aus
        `_process_update` (Issue #2282), Verhalten fuer den Trip-Pfad
        unveraendert.

        Adversary F001 (#2282 Fix-Loop 1/2): die Lade-Nachricht darf nur fuer
        ein echtes Trip-Ziel erscheinen. Der Aufrufer entscheidet das VORHER
        (``ladehinweis_erlaubt``) statt hier nur an ``resolved_kind`` zu
        pruefen: beim vorangestellten Namen gibt es neben "eindeutig
        Vergleich" (`resolved_kind=="vergleich"`) noch den
        Namensgleichheits-Fall (Trip<->Vergleich identisch benannt,
        `resolved_kind` bleibt `None`, `process()` antwortet nur mit einer
        Rueckfrage) — auch dort waere die Lade-Nachricht irrefuehrend, ein
        reiner ``resolved_kind`` -Vergleich saehe das nicht.
        """
        # #2282 S2 (AC-14): am Ortsvergleich laden report/heute/morgen echtes
        # Wetter -- dort ebenfalls Ladehinweis (Trip-report bleibt ohne).
        if inbound.resolved_kind == "vergleich":
            ladehinweis_erlaubt = key in _VERGLEICH_LADE_KEYS
        elif key not in _QUERY_KEYS:
            ladehinweis_erlaubt = False
        if ladehinweis_erlaubt:
            # Loading-Message senden, dann Wetterdaten on-demand holen,
            # dann in-place ersetzen (AC-4)
            # #2417 AC-4/AC-19: die Sprache ist bereits ermittelt
            # (inbound.englisch) -- auf Kurzform-Kanaelen ist JEDE Antwort
            # englisch, auch diese Zwischennachricht.
            loading_body = t("inbound.telegram.laden", "en" if inbound.englisch else lang)
            loading_mid = self._notification_service.send_telegram_message(
                chat_id=chat_id,
                subject="⏳",
                body=loading_body,
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

    def _process_callback_query(self, callback: dict, settings: Settings) -> bool:
        """Setzt den Herkunftsbeleg (Issue #1412 S4a) fuer den Button-Klick."""
        msg = callback.get("message") or {}
        token = _current_inbound_sender.set(str(msg.get("chat", {}).get("id", "")))
        try:
            with befehl_messung("telegram"):
                return self._handle_callback_query(callback, settings)
        finally:
            _current_inbound_sender.reset(token)

    def _handle_callback_query(self, callback: dict, settings: Settings) -> bool:
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
        if self._ist_gesperrt(user_id, chat_id):
            # Nur den Lade-Spinner beenden, nichts editieren/senden.
            try:
                if cq_id:
                    self._notification_service.answer_telegram_callback_query(
                        callback_query_id=cq_id, settings=settings,
                    )
            except Exception as e:
                logger.warning(f"answerCallbackQuery fehlgeschlagen: {e}")  # i18n-log
            return True
        try:
            # #1019: unbekannter Absender (kein User-Match) erhaelt auch beim
            # Button-Klick nur den Registrierungs-Hinweis, KEINE Trip-/Wetter-
            # daten. Die angeklickte Nachricht wird in-place ersetzt;
            # answer_telegram_callback_query laeuft weiterhin im finally.
            if user_id is None:
                if message_id is not None and chat_id:
                    host = _bare_public_host(settings)
                    self._notification_service.edit_telegram_message_text(
                        chat_id=chat_id,
                        message_id=message_id,
                        text=_registrierungs_hinweis(host),
                        settings=settings,
                    )
                return True

            body = self._callback_to_body(data)  # None bei unbekannt
            if body and message_id is not None and chat_id:
                # #1727 S5a: ein Zeitpunkt fuer Auswahl und Stempel (s. oben).
                now_utc = datetime.now(tz=timezone.utc)
                self._antworte_auf_knopf(
                    data, body, now_utc, user_id, chat_id, message_id, user_settings,
                )
        finally:
            if cq_id:
                self._notification_service.answer_telegram_callback_query(
                    callback_query_id=cq_id,
                    settings=user_settings,
                )
        return True

    def _antworte_auf_knopf(
        self, data: str, body: str, now_utc: datetime, user_id: str,
        chat_id: str, message_id: int, user_settings: Settings,
    ) -> None:
        """Issue #2417 (U4/AC-8/AC-9/AC-22): dieselbe klassifizierte
        Zielaufloesung wie beim Text-Eingang, angewendet auf einen
        Knopf-Klick — ersetzt die vergleichsblinde ``_find_active_trip``, die
        bei "nur Vergleich aktiv" oder Mehrdeutigkeit stillschweigend gar
        nichts tat (der Spinner endete ohne jeden sichtbaren Inhalt).

        ``act_help``/``act_columns`` sind ziellos (AC-15, keine Trip-
        /Vergleichsladung); ``act_pause`` bleibt die einzige verbleibende
        Mehrdeutigkeits-Lage (``resolve_active_target``); alle anderen
        Knoepfe (inkl. der ``dd_*``-Drilldowns) adressieren ausschliesslich
        den aktiven Trip (``resolve_trip_only_target``).
        """
        englisch = False
        if data in ("act_help", "act_columns"):
            trip_name = ""
        else:
            trips = load_all_trips(user_id)
            presets = [compare_preset_to_dict(p) for p in load_compare_presets(user_id)]
            lang = resolve_user_lang(user_id)  # #2673: Kontosprache dieses Chats
            if data == "act_pause":
                ziel = resolve_active_target(trips, presets, now_utc, channel="telegram",
                                             lang=lang)
            else:
                ziel = resolve_trip_only_target(trips, presets, now_utc, lang=lang)
            if ziel.kind is None:
                befehl_markieren(*_ParseNurProcessor()._parse_command(body))
                # AC-22: sichtbare Antwort statt stillem No-Op.
                self._notification_service.edit_telegram_message_text(
                    chat_id=chat_id, message_id=message_id, text=ziel.text,
                    settings=user_settings,
                )
                return
            trip_name = ziel.target.name if ziel.kind == "route" else ziel.target.get("name", "")
            # #2417 Abschnitt H: Knopf-Antworten folgen dem Stil des Ziels.
            englisch = telegram_englisch(ziel=ziel.target)

        inbound = InboundMessage(
            channel="telegram", trip_name=trip_name, body=body,
            sender=chat_id, received_at=now_utc, user_id=user_id, englisch=englisch,
        )
        result: CommandResult = TripCommandProcessor().process(inbound)
        # Issue #1007: heute/morgen per Button haben bereits das volle
        # Briefing per Bubbles verschickt — keine separate Bestaetigung mehr
        # in die alte Nachricht editieren.
        if result.suppress_email_reply:
            return
        if data == "act_help":
            # AC-9: NEUE Nachricht -- die Aktionen-Bubble (``message_id``)
            # bleibt dadurch unveraendert und bedienbar, statt vom Hilfetext
            # ueberschrieben zu werden.
            mid = self._notification_service.send_telegram_message(
                chat_id=chat_id, subject=result.confirmation_subject,
                body=result.confirmation_body, settings=user_settings,
                reply_markup=result.reply_markup,
            )
            if mid is not None:
                self.sent_message_ids.append(mid)
            return
        self._notification_service.edit_telegram_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=f"[{result.confirmation_subject}]\n\n{result.confirmation_body}",
            settings=user_settings,
            reply_markup=result.reply_markup,
        )

    def _callback_to_body(self, data: str) -> str | None:
        """Mappt callback_data auf einen Processor-Body. None bei unbekanntem Wert."""
        if data in _CALLBACK_QUERY_MAP:
            return _CALLBACK_QUERY_MAP[data]
        if _CALLBACK_DRILLDOWN_PATTERN.match(data):
            return f"### {data}"
        return None

    def _find_active_trip(
        self, now_utc: datetime, user_id: str,
    ) -> Trip | None:
        """Aktiver Trip = erster Trip mit Datum-Overlap, sonst frühester
        zukünftiger Trip; None wenn keine Trips existieren.

        Issue #2184: die Auswahlregel selbst liegt seit Scheibe S4 als
        geteilter Baustein in ``services.trip_selection.pick_active_trip`` —
        der Premium-SMS-Reader braucht sie genauso. ``load_all_trips`` bleibt
        hier (Begründung im Modul-Docstring von ``trip_selection``).

        Args:
            now_utc: Zeitpunkt der eingehenden Nachricht. Pflichtparameter --
                ein Default auf die Systemuhr wuerde genau die Umgebungsuhr
                wieder einfuehren, die ADR-0051 Regel 3 verbietet.
            user_id: Mandant, dessen Touren durchsucht werden.
        """
        trips = load_all_trips(user_id)
        return pick_active_trip(trips, now_utc)

    @staticmethod
    def _ist_gesperrt(user_id: str | None, chat_id: str) -> bool:
        """Issue #2155 S3 (AC-13): gesperrtes Konto -- stumm verwerfen (loggen)."""
        from app.loader import is_user_disabled
        if user_id is None or not is_user_disabled(user_id):
            return False
        logger.warning(f"Konto gesperrt (disabled), Update verworfen: chat {mask_number(chat_id)}")
        return True

    def _resolve_user_for_chat(
        self, chat_id: str, base_settings: Settings, data_dir: str | None = None
    ) -> tuple[str | None, Settings]:
        """Resolve user_id and user-scoped Settings for an incoming Telegram chat ID.

        Args:
            chat_id: Telegram chat ID (as string)
            base_settings: Base Settings object to derive user profile from
            data_dir: Root data directory (default: get_data_root())

        Returns:
            (user_id, user_scoped_settings) — user_id is None if no match
            (#2151: kein stiller Rueckfall auf "default"; ein echtes Konto
            "default" mit verknuepftem Chat gilt als bekannt)
        """
        from app.loader import get_data_root, lookup_user_by_telegram_chat_id
        if data_dir is None:
            data_dir = str(get_data_root())
        user_id = lookup_user_by_telegram_chat_id(chat_id, data_dir=data_dir)
        if user_id is None:
            return None, base_settings
        return user_id, base_settings.with_user_profile(user_id)

    def _process_start_command(self, token: str, chat_id: str, settings: Settings) -> bool:
        """Verarbeitet /start TOKEN — registriert chat_id beim Go-Backend."""
        self._ensure_notification_service(settings)
        try:
            resp = post_internal(
                "/api/internal/telegram-connect",
                json={"token": token, "chat_id": chat_id},
                timeout=5,
            )
            if resp.status_code == 200:
                logger.info(f"Telegram chat_id {mask_number(chat_id)} via token registriert")
                try:
                    # /start: das Konto entsteht erst jetzt -- deutsch (Annahme 4).
                    self._notification_service.send_telegram_message(
                        chat_id=chat_id,
                        subject=t("inbound.telegram.verbunden.betreff", "de"),
                        body=t("inbound.telegram.verbunden.text", "de"),
                        settings=settings,
                    )
                except Exception as ce:
                    logger.warning(f"Bestätigungsnachricht fehlgeschlagen: {ce}")  # i18n-log
            elif resp.status_code == 409:
                # Issue #2141: die Chat-ID gehört bereits einem anderen Konto.
                # Ohne Rückmeldung wäre das aus Nutzersicht ein Stillstand.
                logger.warning(
                    f"telegram-connect: chat_id {mask_number(chat_id)} bereits mit einem anderen Konto verknüpft"  # i18n-log
                )
                try:
                    self._notification_service.send_telegram_message(
                        chat_id=chat_id,
                        subject=t("inbound.telegram.konflikt.betreff", "de"),
                        body=t("inbound.telegram.konflikt.text", "de"),
                        settings=settings,
                    )
                except Exception as ce:
                    logger.warning(f"Konflikt-Nachricht fehlgeschlagen: {ce}")  # i18n-log
            elif resp.status_code in (401, 503):
                logger.error(f"telegram-connect abgelehnt (HTTP {resp.status_code}) -- Core-Geheimnis prüfen")  # i18n-log
            else:
                logger.warning(f"telegram-connect returned {resp.status_code}")
        except Exception as e:
            logger.error(f"telegram-connect Fehler: {e}")
        return True

    def _command_body(self, text: str) -> tuple[str | None, str | None]:
        """Getippter Text -> ``(interner Schluessel, Prozessor-Body)``.

        Der EINE Einstieg des Telegram-Drahts: Erkennen und Kodieren stehen
        beieinander, damit ein Test genau den Weg nimmt, den auch
        ``_process_update`` nimmt. Vorher lag die Kodierung offen im
        Update-Handler zwischen zwei Netz-Aufrufen und war damit ausserhalb
        eines Live-Laufs nicht pruefbar — genau die Luecke, durch die
        ``/strecke 5`` unbemerkt am Prozessor vorbeilief (Issue #2134).

        ``(None, None)``, wenn kein Befehl erkannt wurde.
        """
        key, value = self._parse_command(text)
        if key is None:
            return None, None
        # Query-Keys werden als "### query: <key>" kodiert
        if key in _QUERY_KEYS:
            return key, f"### query: {key}"
        if value:
            return key, f"### {key}: {value}"
        return key, f"### {key}"

    def _parse_command(self, text: str) -> tuple[str | None, str | None]:
        """Parst ersten nicht-leeren Satz: 'ruhetag 2' → ('ruhetag', '2').

        Immer lowercase. Unbekannte Befehle → (None, None).
        Auflösungs-Reihenfolge:
          0. Zitat-Praefix ab (``_ohne_zitat``, #2137) — der Slash bleibt noch
             stehen, er traegt hier Bedeutung.
          1. Slash-Shortcuts (_SHORTCUT_MAP): /h, /m, /s, /hg, /jetzt, ...
             GANZE Zeile UND erstes Token, sonst faellt '/strecke 5' durch
             (#2120: genau der gemeldete Fall).
          2. Slash ab (``_ohne_praefix``), dann Bare Keywords
             (_BARE_KEYWORD_MAP, channel-agnostisch wie E-Mail): heute, morgen,
             jetzt, gewitter, stop, weiter, hilfe, status, ...
             stop→abbruch, jetzt→now, gewitter→heute_gewitter etc.
          3. _VALID_COMMANDS-Fallback: startdatum, report (nicht in _BARE_KEYWORD_MAP).
        Kein '### ' Prefix nötig — Freitext.

        Issue #2417 AC-28: '/status' ist KEIN Sondereintrag mehr in
        _SHORTCUT_MAP -- es faellt durch Schritt 2 (Slash ab, dann Bare
        Keyword) genauso wie das nackte 'status' auf die Etappenliste. Der
        fruehere Glance-Alias verletzte die Kanalgleichheit (E-Mail/Premium-
        SMS/nacktes Telegram-Wort STATUS lieferten die Etappenliste, nur
        '/status' etwas anderes) und ist deshalb aufgeloest; der
        Wetter-Ueberblick bleibt ueber '/glance' erreichbar. Die
        Praefix-Behandlung selbst kommt aus DERSELBEN Quelle wie im
        Prozessor (Issue #2134), nur in zwei Stufen aufgerufen.
        """
        # AC-20: BOM/ZWSP sind unsichtbar und tragen keinen Leerraum-Status im
        # Unicode-Sinn (anders als NBSP) — VOR dem Lowering entfernen, sonst
        # bliebe z.B. "﻿hilfe" als eigenes, nie in einer Map stehendes
        # Wort stehen.
        first_line = _ohne_unsichtbare_zeichen(_ohne_zitat(_erste_zeile(text))).lower()
        if not first_line:
            return None, None

        # Kurzbefehl-Mapping: /s /h /m /hg — vor dem Slash-Streifen
        if first_line in _SHORTCUT_MAP:
            return _SHORTCUT_MAP[first_line], None
        teile = first_line.split(None, 1)
        if teile[0] in _SHORTCUT_MAP:
            rest = teile[1].strip() if len(teile) > 1 else None
            return _SHORTCUT_MAP[teile[0]], rest or None

        parts = _ohne_praefix(first_line).split(None, 1)
        if not parts:
            return None, None
        # AC-20: Satzzeichen UNMITTELBAR am Befehlswort tolerieren ("hilfe.",
        # "pause!") — NUR am erkannten Schluesselwort, nie am Wert (sonst
        # koennte z.B. eine Distanzangabe verstuemmelt werden).
        key = _ohne_satzzeichen_am_wortende(parts[0])
        value = parts[1].strip() if len(parts) > 1 else None

        # #2673 F001: ABBRUCH/CANCEL nur als ganze Zeile -- als erstes Wort
        # eines Satzes ("abbruch der pause bitte") kein Befehl.
        ganz = ganzzeilen_befehl(first_line)
        if ganz is not None:
            return ganz, None
        if key in ("abbruch", "cancel"):
            return None, None

        # Bare keyword → resolve via shared _BARE_KEYWORD_MAP (channel-agnostic)
        if key in _BARE_KEYWORD_MAP:
            return _BARE_KEYWORD_MAP[key], value or None

        if key not in _VALID_COMMANDS:
            # Issue #2134: ein getipptes Katalog-Kuerzel (`Visib`, `FZ`, ...)
            # wird durchgereicht — der Prozessor loest es gegen denselben
            # Katalog auf. Steuerbefehle sind oben bereits abgearbeitet, ein
            # Metrikwort kann sie deshalb nicht verdraengen (AC-20).
            if _metric_id_for_word(key):
                return key, value or None
            return None, None

        return key, value or None


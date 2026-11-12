"""
Inbound Email Reader — IMAP polling for trip commands.

Polls IMAP inbox for unread emails, extracts trip context from Subject,
delegates to TripCommandProcessor, and sends confirmation reply on
the same channel (email).

SPEC: docs/specs/modules/inbound_command_channels.md v1.1
"""
from __future__ import annotations

import email
import email.utils
import imaplib
import ssl
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from email.header import decode_header, make_header
from html.parser import HTMLParser

from app.config import Settings
from app.loader import load_all_trips
from i18n import resolve_user_lang, t
from utils.pii_masking import mask_addr_for_pii_log
from services.inbound_reply_limit import fehlerantwort_erlaubt
from services.notification_service import NotificationService
from services.trip_command_processor import (
    CommandResult,
    InboundMessage,
    TripCommandProcessor,
    befehl_markieren,
    befehl_messung,
)

logger = logging.getLogger(__name__)


def _norm(s: str) -> str:
    """Normalisiert Trip-Namen: Leerzeichen↔Unterstrich, Mehrfach-WS, lowercase."""
    return re.sub(r"\s+", " ", s.replace("_", " ")).strip().lower()


@dataclass(frozen=True)
class AuthResultSegment:
    """Ein Ergebnis-Segment eines Authentication-Results-Headers (RFC 8601)."""

    method: str
    result: str
    props: dict[str, str]


def _tokenize_auth_results(text: str) -> list[list[str]] | None:
    """Zustandsautomat (#2252, Spec 5a): zerlegt den Header in Abschnitte
    (``;`` nur auf oberster Ebene) aus Woertern (Leerraum-getrennt).
    quoted-strings werden entpackt (``\\``-Escapes aufgeloest), Kommentare
    (verschachtelt) entfernt. Unbalancierte Quotes/Klammern ⇒ ``None``."""
    sections: list[list[str]] = [[]]
    word: list[str] = []
    depth, in_quote, i = 0, False, 0

    def flush() -> None:
        if word:
            sections[-1].append("".join(word))
            word.clear()

    while i < len(text):
        ch = text[i]
        if (in_quote or depth) and ch == "\\":
            if i + 1 >= len(text):
                return None
            if in_quote:
                word.append(text[i + 1])
            i += 2
            continue
        if in_quote:
            in_quote = ch != '"'
            if in_quote:
                word.append(ch)
        elif depth:
            depth += {"(": 1, ")": -1}.get(ch, 0)
        elif ch == '"':
            in_quote = True
        elif ch == "(":
            flush()
            depth = 1
        elif ch == ")":
            return None
        elif ch == ";" or ch.isspace():
            flush()
            if ch == ";":
                sections.append([])
        else:
            word.append(ch)
        i += 1
    if in_quote or depth:
        return None
    flush()
    return sections


def _segment_from_words(words: list[str]) -> AuthResultSegment | None:
    """Erstes Wort ``method=result``, danach Properties ``ptype.property=value``
    (Trennung am ERSTEN ``=``). Ohne ``method=result`` ⇒ ``None``."""
    if not words or "=" not in words[0]:
        return None
    method, result = words[0].split("=", 1)
    if not method or not result:
        return None
    props: dict[str, str] = {}
    for word in words[1:]:
        if "=" in word:
            key, value = word.split("=", 1)
            props.setdefault(key.lower(), value)
    return AuthResultSegment(method.lower(), result.lower(), props)


def _has_duplicate_property(words: list[str]) -> bool:
    """F002 (#2252): derselbe ``ptype.property``-Schluessel zweimal in einem
    Abschnitt ist mehrdeutig ⇒ der ganze Header gilt als unlesbar (fail-closed,
    nie "erster/letzter gewinnt")."""
    keys = [w.split("=", 1)[0].lower() for w in words[1:] if "=" in w]
    return len(keys) != len(set(keys))


def parse_authentication_results_segments(
    header_value: str,
) -> tuple[str | None, list[AuthResultSegment]] | None:
    """RFC-8601-Parsing (#2252): ``(authserv-id, [Segment, ...])`` oder
    ``None`` bei Parse-Fehler (fail-closed beim Aufrufer)."""
    sections = _tokenize_auth_results(header_value)
    if sections is None or any(_has_duplicate_property(w) for w in sections[1:]):
        return None
    authserv_id = " ".join(sections[0]) or None
    segments = [seg for words in sections[1:] if (seg := _segment_from_words(words))]
    return authserv_id, segments


def parse_authentication_results(header_value: str) -> tuple[str | None, dict[str, str]]:
    """Duenner Wrapper: liefert (authserv-id, {method: result, ...}).

    Mehrere Segmente einer Methode mit GLEICHEM Ergebnis ⇒ dieses Ergebnis;
    widerspruechliche Ergebnisse ⇒ kein Eintrag (nie "das letzte gewinnt").
    Parse-Fehler ⇒ ``(None, {})``. Trifft keine Annahme-Entscheidung.
    """
    parsed = parse_authentication_results_segments(header_value)
    if parsed is None:
        return None, {}
    authserv_id, segments = parsed
    by_method: dict[str, set[str]] = {}
    for seg in segments:
        by_method.setdefault(seg.method, set()).add(seg.result)
    results = {m: next(iter(r)) for m, r in by_method.items() if len(r) == 1}
    return authserv_id, results


def _norm_domain(domain: str) -> str:
    """Kleinschreibung, abschliessender Punkt entfernt."""
    domain = domain.strip().lower()
    return domain[:-1] if domain.endswith(".") else domain


def _domain_aligned(domain: str, from_domain: str) -> bool:
    """``domain`` ist ``from_domain`` oder eine Subdomain davon (nie umgekehrt)."""
    domain = _norm_domain(domain)
    return domain == from_domain or domain.endswith("." + from_domain)


def _alignment_accepts(segments: list[AuthResultSegment], from_domain: str) -> bool:
    """Annahmeregel V3 (Spec 5a): (a) genau ein dmarc-Segment, pass,
    ``header.from == from_domain``; (b) genau ein spf-Segment mit
    ``smtp.mailfrom``, pass, ausgerichtet; (c) irgendein ausgerichtetes dkim=pass."""
    dmarcs = [s for s in segments if s.method == "dmarc"]
    if (len(dmarcs) == 1 and dmarcs[0].result == "pass"
            and "header.from" in dmarcs[0].props
            and _norm_domain(dmarcs[0].props["header.from"]) == from_domain):
        return True
    mailfroms = [s for s in segments if s.method == "spf" and "smtp.mailfrom" in s.props]
    if (len(mailfroms) == 1 and mailfroms[0].result == "pass"
            and _domain_aligned(mailfroms[0].props["smtp.mailfrom"].rpartition("@")[2], from_domain)):
        return True
    return any(
        s.method == "dkim" and s.result == "pass" and "header.d" in s.props
        and _domain_aligned(s.props["header.d"], from_domain)
        for s in segments
    )


class _BefehlsHtmlParser(HTMLParser):
    """Reduziert eine Befehls-Antwortmail (nur ``text/html``) auf reinen
    Text (AC-19, #2417) — bricht ENDGUELTIG ab, sobald das erste Zitat
    (``<blockquote type="cite">``) oder die Signatur (Element mit
    ``id="lineBreakAtBeginningOfSignature"``, ein leeres ``<br>`` bei Apple
    Mail) beginnt. Reiner Stdlib-Parser, keine neue Abhaengigkeit.

    Der Signatur-Marker ist ein LEERES ``<br>`` ohne Kinder — ein Handler,
    der nur die Kinder dieses Tags unterdrueckt, schneidet nichts ab. Der
    Abbruch muss deshalb JEDE weitere Ausgabe sperren, nicht nur innerhalb
    des Marker-Elements.
    """

    _BLOCKTAGS = ("br", "div", "p")

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._teile: list[str] = []
        self._abgebrochen = False

    def _pruefe_marker(self, tag: str, attrs: dict[str, str | None]) -> None:
        if tag == "blockquote" and attrs.get("type") == "cite":
            self._abgebrochen = True
        elif attrs.get("id") == "lineBreakAtBeginningOfSignature":
            self._abgebrochen = True

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self._abgebrochen:
            return
        self._pruefe_marker(tag, dict(attrs))
        if not self._abgebrochen and tag in self._BLOCKTAGS:
            self._teile.append("\n")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)

    def handle_data(self, data: str) -> None:
        if not self._abgebrochen:
            self._teile.append(data)

    def text(self) -> str:
        return "".join(self._teile)


def _html_zu_befehlstext(html_text: str) -> str:
    """Wandelt den ``text/html``-Teil einer Befehlsmail in Text (AC-19) —
    Zitat/Signatur werden dabei abgeschnitten (s. ``_BefehlsHtmlParser``)."""
    parser = _BefehlsHtmlParser()
    parser.feed(html_text)
    parser.close()
    return parser.text()


# #2961: Zeitgrenze je IMAP-Operation (Verbindungsaufbau und jede Antwort).
IMAP_TIMEOUT_SECONDS = 30.0
# #2961: je Lauf hoechstens so viele Mails; groessere Mails werden nicht geladen.
MAX_MAILS_PER_RUN = 50
MAX_MAIL_BYTES = 2 * 1024 * 1024
# Kopfzeilen samt Groesse, ohne das Gelesen-Flag zu setzen.
_HEADER_FETCH = "(RFC822.SIZE BODY.PEEK[HEADER])"
_SIZE_RE = re.compile(rb"RFC822\.SIZE (\d+)")
_AUTO_PRECEDENCE = frozenset({"bulk", "junk", "auto_reply", "list"})


def _is_automatic(msg: email.message.Message) -> bool:
    """#2961: Abwesenheitsnotizen, Verteiler und andere Automaten (RFC 3834)."""
    auto = str(msg.get("Auto-Submitted") or "").split(";")[0].strip().lower()
    if auto and auto != "no":
        return True
    if str(msg.get("Precedence") or "").strip().lower() in _AUTO_PRECEDENCE:
        return True
    return msg.get("X-Autoreply") is not None or msg.get("X-Auto-Response-Suppress") is not None


def _fetch_message(imap, uid: bytes, spec: str) -> tuple[bytes, int | None]:
    """Erster Literal-Inhalt einer FETCH-Antwort plus ``RFC822.SIZE``, falls genannt."""
    _, data = imap.fetch(uid, spec)
    inhalt, groesse = b"", None
    for item in data or []:
        teile = item if isinstance(item, tuple) else (item,)
        for i, teil in enumerate(teile):
            if not isinstance(teil, bytes):
                continue
            if isinstance(item, tuple) and i == 1 and not inhalt:
                inhalt = teil
            elif groesse is None and (m := _SIZE_RE.search(teil)):
                groesse = int(m.group(1))
    return inhalt, groesse


class InboundEmailReader:
    """Polls IMAP inbox and processes trip commands from email replies."""

    DEFAULT_IMAP_PORT = 993

    _SUBJECT_TRIP_RE = re.compile(r"\[(.+?)\]")
    _REPLY_PREFIXES = re.compile(
        r"^(Re|Fwd|AW|WG|Antwort|SV):\s*", re.IGNORECASE,
    )

    def __init__(self) -> None:
        self._notification_service: NotificationService | None = None
        # Issue #1405 S4b: Fehlschlaege des letzten Laufs (Router -> failed).
        self.last_failed_count = 0

    def _ensure_notification_service(self, settings: Settings) -> None:
        """#2151 Scheibe C: den Versanddienst erst mit den vorliegenden
        ``settings`` bauen -- nie nutzerlos (kein ``with_user_profile("default")``).
        Die genutzten Methoden lesen ohnehin nur die explizit uebergebenen
        Nutzer-Settings."""
        if self._notification_service is None:
            self._notification_service = NotificationService(settings=settings)

    def poll_and_process(self, settings: Settings) -> int:
        """
        Read UNSEEN emails, process commands, send confirmations.
        Returns: number of processed commands.

        Issue #1405 S4b: die Fehlschlaege des Laufs (nicht erreichbares
        Postfach, gescheiterte Verarbeitung, nicht zugestellte Befehlsantwort)
        stehen danach in ``self.last_failed_count`` (Muster
        ``InboundSmsReader``); der Router meldet sie als ``failed``. Fehlende
        Zugangsdaten sind kein Fehler.
        """
        self.last_failed_count = 0
        imap_user = settings.imap_user or settings.smtp_user
        imap_pass = settings.imap_pass or settings.smtp_pass
        if not imap_user or not imap_pass:
            return 0

        processed, self.last_failed_count = self._poll_inbox(settings, imap_user, imap_pass)
        return processed

    def _poll_inbox(
        self, settings: Settings, imap_user: str, imap_pass: str,
    ) -> tuple[int, int]:
        """Ein IMAP-Durchgang; liefert ``(processed, failed)``."""
        imap = None
        processed = failed = 0
        try:
            imap_host = settings.imap_host or settings.smtp_host
            imap_port = settings.imap_port
            # #2961: Zertifikat pruefen und Zeitgrenze setzen (ohne Kontext
            # prueft imaplib nicht, ohne Timeout haengt ein stummer Server).
            imap = imaplib.IMAP4_SSL(
                imap_host, imap_port,
                ssl_context=ssl.create_default_context(),
                timeout=IMAP_TIMEOUT_SECONDS,
            )
            imap.login(imap_user, imap_pass)
            imap.select("INBOX")

            # Use TO filter if inbound_address is configured (plus-addressing)
            inbound = settings.get_inbound_address()
            if inbound and inbound != settings.smtp_user:
                _, data = imap.search(None, "UNSEEN", "TO", inbound)
            else:
                _, data = imap.search(None, "UNSEEN")
            uids = data[0].split()[:MAX_MAILS_PER_RUN]

            for uid in uids:
                try:
                    done, gescheitert = self._process_single(imap, uid, settings)
                    processed += done
                    failed += gescheitert
                except Exception as e:
                    logger.error(f"Error processing email uid={uid}: {e}")
                    failed += 1
        except imaplib.IMAP4.error as e:
            logger.error(f"IMAP error: {e}")
            failed += 1
        except OSError as e:
            logger.error(f"Network error: {e}")
            failed += 1
        finally:
            if imap:
                try:
                    imap.logout()
                except Exception:
                    pass
        return processed, failed

    def _process_single(
        self,
        imap: imaplib.IMAP4_SSL,
        uid: bytes,
        settings: Settings,
    ) -> tuple[int, int]:
        """Process one email. Returns ``(processed, failed)`` -- je 0 oder 1.
        #2439: umspannt die Verarbeitung mit der Befehls-Messung (Dauer-Zeile).
        Issue #1405 S4b: ``failed`` = Verarbeitung gescheitert oder
        Befehlsantwort nicht zugestellt (die Mail ist trotzdem gelesen)."""
        with befehl_messung("email"):
            return self._process_single_inner(imap, uid, settings)

    def _process_single_inner(
        self,
        imap: imaplib.IMAP4_SSL,
        uid: bytes,
        settings: Settings,
    ) -> tuple[int, int]:
        self._ensure_notification_service(settings)
        # #2961: zuerst nur die Kopfzeilen; der Rumpf folgt erst nach der
        # Autorisierung des Absenders.
        kopf, groesse = _fetch_message(imap, uid, _HEADER_FETCH)
        msg = email.message_from_bytes(kopf)
        if _is_automatic(msg):
            logger.info("Automatisch erzeugte Mail verworfen (uid=%s)", uid)
            imap.store(uid, "+FLAGS", "\\Seen")
            return 0, 0

        # 1. Resolve user-scoped settings for sender, then authorize
        from_addr = self._parse_sender(msg.get("From", ""))
        _user_id, user_settings = self._resolve_settings_for_sender(from_addr, settings)
        if _user_id is None:
            logger.warning(f"Unresolved/ambiguous sender: {mask_addr_for_pii_log(from_addr)!r}")
            imap.store(uid, "+FLAGS", "\\Seen")
            return 0, 0
        from app.loader import is_user_disabled
        if is_user_disabled(_user_id):
            # Issue #2155 S3 (AC-13): gesperrtes Konto -- stumm verwerfen.
            logger.warning(f"Konto gesperrt (disabled), Mail verworfen: {mask_addr_for_pii_log(from_addr)!r}")
            imap.store(uid, "+FLAGS", "\\Seen")
            return 0, 0
        if not self._authorize(from_addr, user_settings, msg):
            imap.store(uid, "+FLAGS", "\\Seen")
            return 0, 0
        if (groesse if groesse is not None else len(kopf)) > MAX_MAIL_BYTES:
            logger.warning("Mail ueber %d Bytes uebersprungen (uid=%s)", MAX_MAIL_BYTES, uid)
            imap.store(uid, "+FLAGS", "\\Seen")
            return 0, 0
        voll, _ = _fetch_message(imap, uid, "(RFC822)")
        msg = email.message_from_bytes(voll)

        # 2. Extract trip name from Subject — error reply if missing
        subject = msg.get("Subject", "")
        trip_name = self._extract_trip_name(subject)
        if not trip_name:
            logger.debug(f"Ignoring email without trip brackets: {subject!r}")
            imap.store(uid, "+FLAGS", "\\Seen")
            return 0, 0

        # 3. Find trip — error reply if not found
        # #2673: Kontosprache des aufgeloesten Absenders (nie "default").
        lang = resolve_user_lang(_user_id)
        trip_id = self._find_trip_id(trip_name, _user_id)
        if not trip_id:
            befehl_markieren(None)
            result = CommandResult(
                success=False, command="trip_not_found",
                confirmation_subject=t("inbound.antwort.trip_nicht_gefunden.betreff", lang,
                                       trip_name=trip_name),
                confirmation_body=(
                    t("inbound.antwort.trip_nicht_gefunden.text", lang, trip_name=trip_name)
                    + "\n" + t("inbound.antwort.trip_nicht_gefunden.pruefen", lang)
                ),
                trip_name=trip_name,
            )
            # Issue #1405 S4b: nicht zugestellte Antwort = Fehler des Laufs;
            # kein Versand eingerichtet = kein Versuch = kein Fehler.
            zugestellt = True
            if user_settings.can_send_email() and fehlerantwort_erlaubt(_user_id):
                zugestellt = self._notification_service.send_command_reply_email(
                    result, user_settings, lang=lang,
                )
            imap.store(uid, "+FLAGS", "\\Seen")
            return 0, 0 if zugestellt else 1

        # 4. Extract body
        body = self._extract_plain_body(msg)

        # 5. Delegate to processor + 6. Reply — beide unter einem gemeinsamen
        # try/except/finally, damit "Seen" in jedem Fall gesetzt wird (#1009).
        # Antwort auf gleichem Kanal — ALWAYS send (success und error), AUSSER
        # das Kommando hat bereits das volle Briefing verschickt (Issue #1007:
        # heute/morgen) — dann IST das Briefing die Antwort, keine Doppel-Mail.
        inbound = InboundMessage(
            trip_name=trip_name,
            body=body,
            sender=from_addr,
            channel="email",
            received_at=datetime.now(tz=timezone.utc),
            user_id=_user_id,
        )
        try:
            processor = TripCommandProcessor()
            result = processor.process(inbound)
            zugestellt = True
            if (user_settings.can_send_email() and not result.suppress_email_reply
                    and self._reply_allowed(result, _user_id)):
                zugestellt = self._notification_service.send_command_reply_email(
                    result, user_settings, lang=lang,
                )
            # Issue #1405 S4b: der Befehl ist verarbeitet; eine nicht
            # zugestellte Antwort zaehlt zusaetzlich als Fehler des Laufs.
            return 1, 0 if zugestellt else 1
        except Exception:
            logger.exception(f"Fehler bei Verarbeitung/Versand fuer trip_id={trip_id!r}")
            return 0, 1
        finally:
            imap.store(uid, "+FLAGS", "\\Seen")

    @staticmethod
    def _reply_allowed(result: CommandResult, user_id: str) -> bool:
        """#2961: Fehlerantworten je Nutzer gedrosselt, Erfolgsantworten nie."""
        if result.success:
            return True
        if fehlerantwort_erlaubt(user_id):
            return True
        logger.info("Fehlerantwort gedrosselt (Stundengrenze erreicht)")
        return False

    def _strip_reply_prefixes(self, subject: str) -> str:
        """Recursively remove Re:, AW:, Fwd:, WG: etc."""
        while True:
            cleaned = self._REPLY_PREFIXES.sub("", subject).strip()
            if cleaned == subject:
                return cleaned
            subject = cleaned

    def _extract_trip_name(self, subject: str) -> str | None:
        """Extract trip name from '[Trip Name] Morning/Evening Report'.

        RFC-2047-dekodiert den Betreff zuerst (Bug #775: Em-Dash → Q-Encoding,
        Leerzeichen→Underscore, Klammern→=5B/=5D).
        """
        decoded = str(make_header(decode_header(subject)))
        clean = self._strip_reply_prefixes(decoded)
        match = self._SUBJECT_TRIP_RE.search(clean)
        return match.group(1) if match else None

    def _parse_sender(self, from_header: str) -> str:
        """Extract email address from 'Name <addr>' format."""
        _, addr = email.utils.parseaddr(from_header)
        return addr.lower()

    def _authorize(
        self, sender: str, settings: Settings, msg: email.message.Message,
    ) -> bool:
        """Absender muss die ``mail_to`` des Nutzers sein; System-Adressen
        (``mail_from``, Eingangsadresse, Postfach-Login) nie (#2961).

        #2143: zusaetzlich zur bestehenden Adress-Logik muss der Absender
        verifiziert sein (email_verified_at) und der Transport SPF/DKIM
        bestehen -- beides fail-closed.
        """
        # #2961: Schleifenschutz -- Absender-, Eingangs- und Postfachadresse
        # des Systems sind nie Befehlsgeber (die Eingangsadresse steht als
        # Reply-To in jeder ausgehenden Mail).
        eigene = {
            a.strip().lower()
            for a in (settings.mail_from, settings.get_inbound_address(), settings.smtp_user)
            if a and "@" in a
        }
        if sender in eigene:
            return False
        if not settings.mail_to:
            return False
        authorized = sender == settings.mail_to.lower()
        if not authorized:
            logger.debug(f"Ignoring email from: {mask_addr_for_pii_log(sender)!r}")
            return False

        if not settings.email_verified_at:
            logger.warning(f"Sender not verified: {mask_addr_for_pii_log(sender)!r}")
            return False
        # #2252 (AC-14): genau ein From:-Header mit genau einer Adresse.
        if not self._single_from_address(msg):
            logger.warning(f"Ambiguous From header: {mask_addr_for_pii_log(sender)!r}")
            return False
        from_domain = sender.rpartition("@")[2]
        if not self._spf_dkim_pass(msg, settings.mail_server_hostname, from_domain):
            logger.warning(f"SPF/DKIM check failed: {mask_addr_for_pii_log(sender)!r}")
            return False
        return True

    def _single_from_address(self, msg: email.message.Message) -> bool:
        """#2252 (AC-14): genau ein ``From:``-Header mit genau einer Adresse;
        ein Komma im quoted Anzeigenamen ist keine zweite Adresse."""
        froms = msg.get_all("From") or []
        if len(froms) != 1:
            return False
        addresses = email.utils.getaddresses([str(froms[0])])
        return len(addresses) == 1 and bool(addresses[0][1])

    def _spf_dkim_pass(
        self, msg: email.message.Message, expected_authserv_id: str | None,
        from_domain: str,
    ) -> bool:
        """Nur der ERSTE Authentication-Results-Header zaehlt (msg.get(), NIE
        get_all() -- Stalwart prependt seinen echten Header, ein Angreifer
        koennte einen zweiten gefaelschten Header mit pass anhaengen, AC-5).

        #2252 (Spec 5a): Quote-Sperre, Tokenizer (Parse-Fehler ⇒ ablehnen),
        authserv-id-Vergleich, dann Annahmeregel V3 mit Ausrichtung zur
        ``from_domain`` -- alles fail-closed."""
        from_domain = _norm_domain(from_domain or "")
        if not expected_authserv_id or not from_domain:
            return False
        header_value = msg.get("Authentication-Results")
        if not header_value:
            return False
        header_value = str(header_value)
        if '"' in header_value:
            return False
        parsed = parse_authentication_results_segments(header_value)
        if parsed is None:
            return False
        authserv_id, segments = parsed
        if authserv_id != expected_authserv_id:
            return False
        return _alignment_accepts(segments, from_domain)

    def _extract_plain_body(self, msg: email.message.Message) -> str:
        """Extract plain-text body. Multipart: first text/plain part; fehlt
        er, wird der erste text/html-Teil dekodiert und auf Text reduziert
        (AC-19, #2417) -- ohne diesen Fallback liefert eine Apple-Mail-
        Antwort (nur text/html, Standardstruktur beim Antworten auf dem
        iPhone) IMMER "" und damit "Unbekannter Befehl" (B2)."""
        if msg.is_multipart():
            html_teil = None
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    payload = part.get_payload(decode=True)
                    charset = part.get_content_charset() or "utf-8"
                    return payload.decode(charset, errors="replace")
                if html_teil is None and part.get_content_type() == "text/html":
                    html_teil = part
            if html_teil is not None:
                payload = html_teil.get_payload(decode=True)
                charset = html_teil.get_content_charset() or "utf-8"
                return _html_zu_befehlstext(payload.decode(charset, errors="replace"))
        else:
            payload = msg.get_payload(decode=True)
            if payload:
                charset = msg.get_content_charset() or "utf-8"
                text = payload.decode(charset, errors="replace")
                if msg.get_content_type() == "text/html":
                    return _html_zu_befehlstext(text)
                return text
        return ""

    def _resolve_settings_for_sender(
        self, from_addr: str, base_settings: Settings, data_dir: str | None = None
    ) -> tuple[str | None, Settings]:
        """Resolve user_id and user-scoped Settings for an incoming sender address.

        Args:
            from_addr: Sender email address (lowercase expected)
            base_settings: Base Settings object to derive user profile from
            data_dir: Root data directory (default: get_data_root())

        Returns:
            (user_id, user_scoped_settings) — user_id is None if there is no
            unambiguous match on a confirmed effective address; there is no
            fallback to an account "default" (Issue #2147 Scheibe B2, AC-14).
            In that case the base settings are returned unchanged.
        """
        from app.loader import get_data_root, lookup_user_by_email
        if data_dir is None:
            data_dir = str(get_data_root())
        user_id = lookup_user_by_email(from_addr, data_dir=data_dir)
        if user_id is None:
            return None, base_settings
        return user_id, base_settings.with_user_profile(user_id)

    def _find_trip_id(self, trip_name: str, user_id: str) -> str | None:
        """Trip-Lookup: primär über GZ#-Shortcode, Fallback toleranter Namensvergleich."""
        trips = load_all_trips(user_id)
        # Shortcode-Routing: "GZ#HERM ..." → erstes Token ist der Code
        first_token = trip_name.split()[0].upper() if trip_name.strip() else ""
        if first_token.startswith("GZ#"):
            for trip in trips:
                if trip.shortcode.upper() == first_token:
                    return trip.id
        # Toleranter Namensvergleich (Leerzeichen ↔ Unterstrich, case-insensitiv)
        query = _norm(trip_name)
        for trip in trips:
            if _norm(trip.name) == query:
                return trip.id
        # Issue #2282 Abschnitt 4: der [Name]-Betreff findet jetzt auch
        # Ortsvergleiche, nicht nur Trips.
        from app.loader import load_compare_presets

        for preset in load_compare_presets(user_id):
            if _norm(preset.name) == query:
                return preset.id
        logger.warning(f"No trip found for name: {trip_name!r} (user={user_id!r})")
        return None

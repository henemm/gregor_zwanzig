"""
Email output channel.

Sends weather reports via SMTP email (HTML or plain text).
"""
from __future__ import annotations

import json
import logging
import re
import smtplib
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formatdate, getaddresses, parseaddr
from pathlib import Path
from typing import TYPE_CHECKING

from app.origin_guard import running_origin
from output.channels.base import OutputConfigError, OutputError

if TYPE_CHECKING:
    from app.config import Settings

logger = logging.getLogger(__name__)

# Issue #1448 S1: Zeitgrenzen fuer den SMTP-Versand -- Vorbild
# FETCH_DEADLINE_SECONDS in src/providers/dwd.py/meteofrance.py. Ohne
# Grenze blockiert ein haengender Postausgang (egal ob bei connect,
# starttls(), login() oder sendmail()) unbegrenzt, ebenso die
# Wiederhol-Schleife in send(). Belegrechnung/Details: Spec
# docs/specs/modules/fix_1448_s1_mail_zeitgrenze.md.
SMTP_OP_TIMEOUT_SECONDS = 10.0
SEND_BUDGET_SECONDS = 50.0
FALLBACK_RESERVE_SECONDS = 12.0
# Ersetzt die bisher an zwei Stellen (Ersatzweg-Aufrufe) nackte Zahl 587
# (Fund aus der RED-Phase, s. Spec) -- Verhalten identisch.
FALLBACK_SMTP_PORT = 587


def _phase_timeout_or_raise(deadline_at: float) -> float:
    """Issue #1448 S1: Restzeit bis `deadline_at`, gekappt auf
    `SMTP_OP_TIMEOUT_SECONDS` -- fuer `smtplib.SMTP(..., timeout=...)` bzw.
    `server.sock.settimeout(...)` vor jeder Phase (Verbindungsaufbau samt
    Begruessung, starttls, login, sendmail).

    Ist die Restzeit bereits <= 0, wird direkt ein `TimeoutError` geworfen,
    OHNE `settimeout(0)` zu versuchen -- das schaltet den Socket laut
    `socket`-Doku in den nicht-blockierenden statt in den sofort-
    abbrechenden Modus (Spec, "Wichtiger Randfall"). `TimeoutError` ist
    Unterklasse von `OSError` und faellt damit ohne neuen except-Zweig in
    die bestehende Behandlung in `send()` (`:702`).
    """
    remaining = deadline_at - time.monotonic()
    if remaining <= 0:
        raise TimeoutError("SMTP-Zeitbudget vor Phasenbeginn erschöpft")
    return min(SMTP_OP_TIMEOUT_SECONDS, remaining)


# Issue #1147 (historisch): dritte, empfängerseitige Guard-Linie. Seit Issue
# #1219 funktional durch eine positive Allowlist (_load_resend_allowlist)
# ABGELÖST: gregor-test@/gregor-staging@henemm.com gehören zu keinem echten
# Nutzerprofil und werden daher automatisch NICHT in die Allowlist
# aufgenommen — der Guard @send() referenziert TEST_MAILBOXES nicht mehr
# direkt. Konstante bleibt zu Dokumentationszwecken/für ältere Kommentare
# erhalten.
TEST_MAILBOXES = frozenset({"gregor-test@henemm.com", "gregor-staging@henemm.com"})

# Issue #1476 (AC-6): Ziel der Herkunftssperre bei Testlauf-Herkunft --
# Mitglied von TEST_MAILBOXES, hier als eigene Konstante fuer eine
# DETERMINISTISCHE Umschaltung (kein iter() ueber ein frozenset).
_ORIGIN_GUARD_TEST_RECIPIENT = "gregor-test@henemm.com"

# Issue #1235: Domains, die Stalwart LOKAL zustellt (kein Relay an Resend).
# henemm.com ist die einzige von Stalwart bediente Domain -- Empfaenger
# dieser Domain (inkl. gregor-test@/gregor-staging@ und Plus-Adressen)
# sind auf dem Nicht-Resend-Pfad ausdruecklich erlaubt, weil die Zustellung
# lokal bleibt und nicht extern relayt wird (vgl. infra#114).
LOCAL_MAIL_DOMAINS = frozenset({"henemm.com"})

# Fix-Loop 4 (F005): rohes, PARSER-UNABHÄNGIGES Fangnetz. Statt jeden
# Zerlege-/Normalisierungs-Trick einzeln zu stopfen (Semikolon→F003,
# gequoteter Name→F004, Steuerzeichen→F005), scannt dieser Layer den
# rohen, UNGEPARSTEN Empfänger-String direkt nach den Test-Postfach-
# Literalen (plus-tolerant) — er ist dadurch immun gegen jede künftige
# Zerlege-Umgehung, weil er nichts zerlegt.
_CONTROL_CHARS_RE = re.compile(r"[\r\n\x0b\x0c\x00]")
_TEST_MAILBOX_RAW_PATTERN = re.compile(
    r"(?:gregor-test|gregor-staging)(?:\+[^@]*)?@henemm\.com", re.IGNORECASE
)


def _extract_addr(recipient: str) -> str:
    """Reduziert eine ggf. `"Name" <addr>`-Form auf die reine Adresse."""
    _, addr = parseaddr(recipient)
    return addr or recipient


def _normalize_addr_for_guard(raw: str, cap_plus: bool = True) -> str:
    """Reduziert `raw` auf eine lowercased, getrimmte Adresse -- per Default
    zusaetzlich plus-adressierungs-gekappt (`gregor-test+foo@…` ->
    `gregor-test@…`), fuer den Vergleich gegen TEST_MAILBOXES.

    Issue #1412 S2b (N1): der Strip MUSS nach `_extract_addr` stehen --
    `parseaddr("henning@henemm.com ")` liefert die Adresse MIT Randzeichen
    (z.B. NBSP) zurueck, ein Strip davor wuerde eingeholt.

    Issue #1412 S2b (D5, Variante C): `cap_plus=False` liefert die
    ungekappte, aber weiterhin getrimmte Form -- fuer den zusaetzlichen
    Allowlist-Vergleich im Resend-Guard, OHNE die gespeicherte Allowlist
    selbst zu veraendern."""
    addr = _extract_addr(raw).strip().lower()
    if not cap_plus:
        return addr
    local, sep, domain = addr.partition("@")
    if sep:
        addr = local.split("+", 1)[0] + sep + domain
    return addr


def _normalized_addrs_for_guard(recipient: str, cap_plus: bool = True) -> list[str]:
    """Issue #1147 Fix-Loop 1 (F001/F002a) + Fix-Loop 2 (F003): zerlegt einen
    Empfänger-Eintrag an der TRENNZEICHEN-KLASSE Komma UND Semikolon (nicht
    nur Komma — ein Frontend-Freitextfeld splittet selbst nur an Komma, ein
    Element mit eingebettetem Semikolon würde also unverändert bei `send()`
    ankommen) und kappt pro Teil den lokalen Adressteil am ersten `+`
    (Plus-Addressing), bevor gegen TEST_MAILBOXES verglichen wird.

    F003-Zusatz: scheitert `parseaddr()` an einem Teil (z.B. zwei nur durch
    Leerzeichen statt Komma/Semikolon getrennte Adressen in einem Element),
    wird zusätzlich an Whitespace roh gesplittet — aber NUR für Fragmente,
    die selbst ein `@` enthalten, damit `"Name" <addr>`-Formen (die
    parseaddr() weiterhin korrekt auflöst) nicht zerrissen werden.

    F004-Zusatz (Fix-Loop 3): der reine Trennzeichen-Split oben zerreißt eine
    gequotete Anzeigename-Form MIT eingebettetem Komma/Semikolon (z.B.
    `'"Foo; Bar" <addr>'`) VOR dem Parsen — das Semikolon im Anzeigenamen
    zählt dann fälschlich als Empfänger-Trenner und die eigentliche Adresse
    verschwindet aus dem Ergebnis. Deshalb wird zusätzlich
    `email.utils.getaddresses()` als quote-bewusste Strategie herangezogen
    (RFC5322-konform, respektiert Quotes) und mit der bestehenden
    Separator-Pipeline VEREINIGT (Union, nicht Entweder-Oder). Der Guard ist
    bewusst deny-orientiert: mehr extrahierte Kandidaten sind unkritisch —
    ein Treffer setzt voraus, dass der Test-Postfach-String tatsächlich im
    Empfängerfeld steckt; Junk-Fragmente aus zerrissenen Anzeigenamen (z.B.
    'foo', 'bar') matchen TEST_MAILBOXES nie.

    Reine Guard-Normalisierung — der tatsächliche Versand bleibt
    unverändert."""
    normalized: list[str] = []

    # Strategie 1 (quote-bewusst, F004): RFC5322-konformes Parsen der
    # gesamten Empfänger-Zeichenkette respektiert Quotes und zerlegt
    # Komma-Listen korrekt, auch mit Semikolon im Anzeigenamen.
    for _, addr in getaddresses([recipient]):
        if addr:
            normalized.append(_normalize_addr_for_guard(addr, cap_plus=cap_plus))

    for part in re.split(r"[,;]", recipient):
        part = part.strip()
        if not part:
            continue
        _, addr = parseaddr(part)
        if addr:
            normalized.append(_normalize_addr_for_guard(part, cap_plus=cap_plus))
            continue
        whitespace_parts = [p for p in part.split() if "@" in p]
        if whitespace_parts:
            normalized.extend(
                _normalize_addr_for_guard(p, cap_plus=cap_plus) for p in whitespace_parts
            )
        else:
            normalized.append(_normalize_addr_for_guard(part, cap_plus=cap_plus))
    return normalized


def _raw_contains_test_mailbox(raw: str) -> bool:
    """Fix-Loop 4 (F005): parser-unabhängiges Fangnetz. Entfernt zuerst
    Steuerzeichen (`\\r \\n \\x0b \\x0c \\x00`) aus dem rohen Empfänger-
    String — Steuerzeichen in einer Adresse sind nie legitim, werden aber
    genutzt, um Trennzeichen-/Quote-Parser zu verwirren (F005: ein
    eingebetteter CRLF im Anzeigenamen). Nach dem Strippen wird der
    rohe (NICHT zerlegte) String direkt gegen die Test-Postfach-Literale
    gescannt (plus-tolerant). Diese Reihenfolge — erst strippen, dann
    scannen — ist bewusst gewählt: ein legitimer Empfänger mit kaputtem
    Anzeigenamen (z.B. `'"Weird\\r\\nName" <real@example.com>'`) enthält
    nach dem Strippen kein Test-Postfach-Literal und bleibt unblockiert
    (AC-4-Regressionsschutz) — nur wenn nach dem Strippen tatsächlich
    `gregor-test@henemm.com`/`gregor-staging@henemm.com` (ggf. plus-
    adressiert) im String auftaucht, greift der Guard."""
    stripped = _CONTROL_CHARS_RE.sub("", raw)
    return bool(_TEST_MAILBOX_RAW_PATTERN.search(stripped))


_RESERVED_TEST_DOMAINS = frozenset({"example.com", "example.net", "example.org"})
# Issue #1412 S2b (D3): faengt Subdomains der reservierten Second-Level-
# Domains ab (analog Go reservedTestDomainSuffixes, sender.go:122) --
# sub.example.com ist ebenso reserviert wie example.com selbst. Fuehrender
# Punkt ist Absicht -- "myexample.com" endet NICHT auf ".example.com" und
# bleibt daher unblockiert.
_RESERVED_TEST_DOMAIN_SUFFIXES = (".example.com", ".example.net", ".example.org")
_RESERVED_TEST_TLDS = (".test", ".invalid", ".localhost", ".example")
_RESERVED_BARE_TLDS = frozenset({"test", "invalid", "localhost", "example"})


def _is_reserved_test_domain(addr: str) -> bool:
    """Issue #1219 Scheibe 1 (AC-4): RFC-2606-reservierte Test-Domains werden
    IMMER geblockt, unabhängig vom Verifikationsstatus des Profils. Exakte
    Domains `example.com/.net/.org` ODER Domain endet auf `.test`/`.invalid`/
    `.localhost`/`.example` (case-insensitive, nach Normalisierung).

    Adversary F002: ein Trailing-Dot-FQDN (`example.com.`) wird vor dem
    Vergleich gekürzt, sonst würde der Suffix-Check fälschlich durchrutschen.
    Eine BARE-TLD ohne Subdomain-Label (`user@localhost`, `user@test`) wird
    zusätzlich per EXAKTEM Vergleich erkannt — NICHT als Substring/Suffix,
    damit legitime Domains wie `mytest.de`/`example.company` nicht
    fälschlich gesperrt werden."""
    domain = _extract_addr(addr).strip().lower().rpartition("@")[2]
    domain = domain.rstrip(".")
    if not domain:
        return False
    if domain in _RESERVED_TEST_DOMAINS or domain in _RESERVED_BARE_TLDS:
        return True
    if domain.endswith(_RESERVED_TEST_DOMAIN_SUFFIXES):
        return True
    return domain.endswith(_RESERVED_TEST_TLDS)


def _is_local_mail_domain(addr: str) -> bool:
    """Issue #1235: True, wenn die Domain von `addr` (nach Normalisierung:
    Trailing-Dot gestrippt, lowercase) exakt in LOCAL_MAIL_DOMAINS liegt.
    Exakter Vergleich, kein Suffix-/Substring-Match (Bypass-Haertung
    analog _is_reserved_test_domain)."""
    domain = _extract_addr(addr).strip().lower().rpartition("@")[2]
    domain = domain.rstrip(".")
    return domain in LOCAL_MAIL_DOMAINS


def _load_resend_allowlist(data_dir: str | None = None) -> frozenset[str]:
    """Issue #1219 Scheibe 1: positive Empfänger-Allowlist, Eignungskriterium
    umgestellt von der Namens-Heuristik (`is_test_user_id`) auf das explizite
    Profilfeld `email_verified_at`.

    Sammelt normalisierte `mail_to`-/`email`-Adressen aller Nutzerprofile
    unter `<data_dir>/users/<id>/user.json`, die ein GESETZTES
    `email_verified_at` haben. Profile ohne (leeres/fehlendes)
    `email_verified_at` werden konservativ ausgeschlossen — im Zweifel nicht
    in die Allowlist aufnehmen. Reservierte Test-Domains (siehe
    `_is_reserved_test_domain()`) werden hier zusätzlich ausgeschlossen, auch
    bei gesetztem `email_verified_at` (AC-4). Plus-Adressierung wird auf
    Allowlist-Einträgen NICHT gekappt (echte Nutzeradressen werden 1:1
    verglichen, nur lowercase/trim via `parseaddr`).

    Fail-soft: ein fehlendes `<data_dir>/users`-Verzeichnis liefert eine
    leere Allowlist; eine fehlende/kaputte `user.json` überspringt nur das
    betroffene Profil — nie ein Crash des Sendepfads.
    """
    allowed: set[str] = set()
    if data_dir is None:
        # Lokaler Import wie beim Aufrufer weiter unten (Adversary F002,
        # #1219): NICHT direkt GZ_DATA_DIR lesen — get_data_root() honoriert
        # zuerst app.loader._DATA_ROOT und damit die Test-Isolation (#1133).
        from app.loader import get_data_root

        data_dir = str(get_data_root())
    users_root = Path(data_dir) / "users"
    try:
        user_ids = [d.name for d in users_root.iterdir() if d.is_dir()]
    except OSError:
        return frozenset()

    for user_id in user_ids:
        profile_path = users_root / user_id / "user.json"
        try:
            profile = json.loads(profile_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        # Adversary F001: gültiges JSON, das aber kein Objekt ist (z.B. `[]`
        # oder `null`), darf NICHT crashen — .get() existiert nur auf dict.
        # Fail-soft: dieses eine Profil überspringen, alle anderen normal
        # weiterladen (kein einzelnes kaputtes Profil legt den Sendepfad lahm).
        if not isinstance(profile, dict):
            continue
        if not profile.get("email_verified_at"):
            continue
        for field in ("mail_to", "email"):
            raw = profile.get(field)
            if raw:
                addr = _extract_addr(raw).strip().lower()
                if addr and not _is_reserved_test_domain(addr):
                    allowed.add(addr)
    return frozenset(allowed)


def _mask_addr_for_log(raw: str) -> str:
    """Issue #1219 AC-6: reduziert eine Adresse auf die Domain für Log-/
    Fehlermeldungen — verhindert, dass eine volle Empfängeradresse im
    Klartext geloggt bzw. in einer Exception-Message ausgegeben wird."""
    addr = _extract_addr(raw)
    _, sep, domain = addr.partition("@")
    return f"***@{domain.lower()}" if sep else "***"


def build_mime_message(
    subject: str,
    body: str,
    from_addr: str,
    to_header: str,
    reply_to: str | None,
    html: bool,
    plain_text_body: str | None,
    mail_type: str | None = None,
    mail_format: str | None = None,
    compare_hourly_enabled: bool | None = None,
):
    """Issue #722: Build a MIME message. Pure function, no SMTP side-effects.

    html=True  → MIMEMultipart("alternative") with plain + html parts (full path).
    html=False → single MIMEText("plain"), us-ascii/7bit for ASCII bodies.

    Issue #733: Optionale Marker-Header X-GZ-Mail-Type / X-GZ-Format für den
    kanonischen Briefing-Mail-Validator. Backward-Compat: ohne die Params bleibt
    die Message header-frei.

    Issue #1107: Optionaler Marker-Header X-GZ-Compare-Hourly-Enabled für den
    Compare-Mail-Validator (email_spec_validator.py).
    """
    if html:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = from_addr
        msg["To"] = to_header
        # Issue #1247: RFC-2822-Date-Header im MIME-Envelope.
        msg["Date"] = formatdate(localtime=True)
        if reply_to:
            msg["Reply-To"] = reply_to
        if mail_type is not None:
            msg["X-GZ-Mail-Type"] = mail_type
        if mail_format is not None:
            msg["X-GZ-Format"] = mail_format
        if compare_hourly_enabled is not None:
            msg["X-GZ-Compare-Hourly-Enabled"] = "true" if compare_hourly_enabled else "false"
        if plain_text_body:
            plain_text = plain_text_body
        else:
            plain_text = re.sub(r'<style[^>]*>.*?</style>', '', body, flags=re.DOTALL | re.IGNORECASE)
            plain_text = re.sub(r'<head[^>]*>.*?</head>', '', plain_text, flags=re.DOTALL | re.IGNORECASE)
            plain_text = re.sub(r'<[^>]+>', '', plain_text)
            plain_text = plain_text.replace('&nbsp;', ' ').replace('&deg;', '°')
            plain_text = re.sub(r'\n\s*\n\s*\n', '\n\n', plain_text)
            plain_text = plain_text.strip()
        msg.attach(MIMEText(plain_text, "plain", "utf-8"))
        msg.attach(MIMEText(body, "html", "utf-8"))
    else:
        charset = "us-ascii" if body.isascii() else "utf-8"
        msg = MIMEText(body, "plain", charset)
        msg["Subject"] = subject
        msg["From"] = from_addr
        msg["To"] = to_header
        # Issue #1247: RFC-2822-Date-Header im MIME-Envelope.
        msg["Date"] = formatdate(localtime=True)
        if reply_to:
            msg["Reply-To"] = reply_to
        if mail_type is not None:
            msg["X-GZ-Mail-Type"] = mail_type
        if mail_format is not None:
            msg["X-GZ-Format"] = mail_format
        if compare_hourly_enabled is not None:
            msg["X-GZ-Compare-Hourly-Enabled"] = "true" if compare_hourly_enabled else "false"
    return msg


class EmailOutput:
    """
    Email output channel using SMTP.

    Sends HTML emails with plain-text fallback.
    Requires complete SMTP configuration in Settings.

    Example:
        >>> output = EmailOutput(settings)
        >>> output.send("Evening Report", "<h1>Weather</h1><p>5C</p>")
    """

    def __init__(self, settings: "Settings") -> None:
        """
        Initialize email output with settings.

        Args:
            settings: Application settings with SMTP configuration

        Raises:
            OutputConfigError: If SMTP configuration is incomplete
        """
        if not settings.can_send_email():
            raise OutputConfigError(
                "email",
                "Incomplete SMTP configuration. "
                "Required: smtp_host, smtp_user, smtp_pass, mail_to",
            )

        # Hard-Guard: Staging darf NIEMALS über Resend senden — unabhängig von is_test_mode.
        # Issue #924: verhindert neue Code-Pfade, die for_testing() vergessen.
        if (getattr(settings, "env", "") or "").lower() == "staging" and "resend" in (settings.smtp_host or "").lower():
            raise OutputConfigError(
                "email",
                "Staging darf NICHT über Resend senden! "
                "GZ_SMTP_HOST muss auf mail.henemm.com zeigen. "
                "Prüfe /home/hem/gregor_zwanzig_staging/.env (Issue #924).",
            )
        if getattr(settings, "is_test_mode", False) and "resend" in (settings.smtp_host or "").lower():
            raise OutputConfigError(
                "email",
                "Test-Versand über Resend ist gesperrt. "
                "Test-Mails MÜSSEN über Stalwart gehen — siehe Settings.for_testing(). "
                "Konfiguriere GZ_TEST_SMTP_USER/PASS oder verwende einen Test-User "
                "(User-ID enthält 'test' oder 'tdd').",
            )

        self._host = settings.smtp_host
        self._port = settings.smtp_port
        self._user = settings.smtp_user
        self._password = settings.smtp_pass
        self._to = settings.mail_to
        self._from = settings.mail_from or settings.smtp_user
        self._reply_to = settings.get_inbound_address()
        self._fallback_host = getattr(settings, 'imap_host', None)
        self._fallback_user = getattr(settings, 'imap_user', None)
        self._fallback_pass = getattr(settings, 'imap_pass', None)

    @property
    def name(self) -> str:
        """Channel identifier."""
        return "email"

    def _fallback_recipients_blocked(self, recipients: list[str]) -> bool:
        """Guard-Wiederholung gegen den Ersatz-Postausgang (`self._fallback_host`,
        Issue #1412 S1): erlaubt ist die VEREINIGUNG aus Allowlist der
        bestätigten Profil-Adressen UND lokaler Zustellbarkeit — lockerer als
        die primäre, host-abhängige Regel, aber reservierte Test-Domains
        bleiben bedingungslos gesperrt. Heute verhaltensneutral (jeder primär
        durchgekommene Empfänger erfüllt bereits eine Teilmenge dieser Regel);
        schließt die Lücke dauerhaft, falls `_fallback_host` künftig auf
        einen externen Relay zeigt (Spec „Scope-Korrektur nach RED")."""
        from app.loader import get_data_root

        allowlist = _load_resend_allowlist(data_dir=str(get_data_root()))
        for r in recipients:
            candidates = [a for a in _normalized_addrs_for_guard(r) if "@" in a]
            if not candidates or any(_is_reserved_test_domain(a) for a in candidates):
                return True
            if any(a not in allowlist and not _is_local_mail_domain(a) for a in candidates):
                return True
        return False

    def _dial_and_send(
        self,
        host: str,
        port: int,
        user: str,
        password: str,
        recipients: list[str],
        msg,
        from_addr: str,
        deadline_at: float,
    ) -> None:
        """Issue #1412 S3a: der EINE Ort, an dem eine SMTP-Verbindung entsteht.

        Reiner Transport — die Empfänger-Guards bleiben in `send()`, vor der
        Retry-Schleife (Spec, Entscheidung E1: `_dial_and_send` hat genau
        einen Aufrufer-Kontext, der bereits einmal prüft).

        Issue #1426: alle drei Versandwege (Primärweg und beide Ersatzwege)
        fassen jeden Empfänger einzeln ein — die frühere Asymmetrie
        (`isolate_per_recipient`, #1412 S3a E2) ist damit aufgelöst. Lehnt der
        Postausgang ALLE Empfänger ab, wird `OutputError` geworfen; vorher
        meldete `send()` in diesem Fall fälschlich Erfolg.

        Issue #1448 S1: `deadline_at` (`time.monotonic()`-Zeitpunkt) begrenzt
        jede Phase -- Verbindungsaufbau samt Begrüßung, `starttls()`,
        `login()`, jeder `sendmail()`-Aufruf -- auf
        `min(SMTP_OP_TIMEOUT_SECONDS, Restzeit)`. `_phase_timeout_or_raise()`
        wirft `TimeoutError` statt `settimeout(0)`, falls die Restzeit vor
        Erreichen einer Phase bereits erschöpft ist.
        """
        with smtplib.SMTP(
            host, port, timeout=_phase_timeout_or_raise(deadline_at)
        ) as server:
            server.sock.settimeout(_phase_timeout_or_raise(deadline_at))
            server.starttls()
            server.sock.settimeout(_phase_timeout_or_raise(deadline_at))
            server.login(user, password)
            if len(recipients) == 1:
                server.sock.settimeout(_phase_timeout_or_raise(deadline_at))
                server.sendmail(from_addr, recipients, msg.as_string())
            else:
                fehler: list[tuple[str, Exception]] = []
                for recipient in recipients:
                    server.sock.settimeout(_phase_timeout_or_raise(deadline_at))
                    try:
                        server.sendmail(from_addr, [recipient], msg.as_string())
                    except smtplib.SMTPServerDisconnected:
                        # Adversary-Fund F001 zu #1448 S1: ein
                        # Transportabbruch (z.B. weil die neue
                        # Zeitgrenze waehrend DIESES sendmail()
                        # zuschlaegt, s. `_phase_timeout_or_raise()`)
                        # ist KEIN empfaengerspezifisches Problem wie
                        # `SMTPRecipientsRefused` -- der Socket ist tot,
                        # ein weiterer Versuch beim naechsten Empfaenger
                        # waere sinnlos und wuerde denselben Fehler
                        # erneut (still) verschlucken. Deshalb NICHT wie
                        # eine Empfaenger-Ablehnung schlucken, sondern
                        # durchreichen -- landet in send()s eigenem
                        # `SMTPServerDisconnected`-Zweig (Retry +
                        # Ersatzweg, s.u.). Muss VOR dem generischen
                        # `SMTPException`-Zweig stehen (dessen Oberklasse).
                        raise
                    except smtplib.SMTPException as exc:
                        logger.error(
                            "SMTP-Fehler für Empfänger %s: %s", recipient, exc
                        )
                        fehler.append((recipient, exc))
                if len(fehler) == len(recipients):
                    raise OutputError(
                        "email",
                        f"Alle {len(recipients)} Empfaenger abgelehnt: "
                        f"{[str(e) for _, e in fehler]}",
                    )

    def _handle_transient_dial_failure(
        self,
        e: BaseException,
        attempt: int,
        max_attempts: int,
        versuch_dauer: float,
        primaer_deadline: float,
        backoff_base: float,
        recipients: list[str],
        msg,
        from_addr: str,
    ) -> bool:
        """Issue #1448 S1: gemeinsame Behandlung für vorübergehende
        Transportfehler (`OSError`, `smtplib.SMTPServerDisconnected`) in
        `send()`s Wiederhol-Schleife -- beide Aufrufer (s. dort) unterscheiden
        sich nur in der Exception-Klasse, nicht in der Reaktion.

        `primaer_deadline` ist bereits um `FALLBACK_RESERVE_SECONDS`
        VERKÜRZT (s. `send()`, Team-Lead-Entscheidung 2026-08-01) -- die
        Reserve ist damit STRUKTURELL geschützt: der Primärweg kann sie
        gar nicht mehr anknabbern, unabhängig davon, wie das Gate unten
        schätzt. Das Gate ist deshalb reine OPTIMIERUNG ("keinen
        aussichtslosen Versuch mehr starten"), keine Sicherheitsgrenze --
        als Schätzwert für die Kosten eines weiteren Versuchs dient die
        GEMESSENE Dauer des gerade gescheiterten Versuchs (nicht die
        pessimistische `SMTP_OP_TIMEOUT_SECONDS`-Konstante, die bei knapp
        bemessenem Gesamtbudget das Gate nie öffnen würde, s. AC-5).

        Rückgabe `True`: der Ersatzweg hat zugestellt, der Aufrufer soll aus
        `send()` zurückkehren. Rückgabe `False`: entweder wurde geschlafen
        (Aufrufer macht mit dem nächsten Schleifendurchlauf weiter) oder es
        wurde bereits `OutputError` geworfen.
        """
        restzeit_primaer = primaer_deadline - time.monotonic()
        if attempt < max_attempts - 1 and restzeit_primaer > versuch_dauer:
            # Retry with exponential backoff: 2s, 4s, 8s
            # Formula: backoff_base * (1, 2, 4) = (2, 4, 8)
            wait_multiplier = [1, 2, 4][attempt]
            wait = min(backoff_base * wait_multiplier, max(restzeit_primaer, 0))
            logger.warning(
                f"Email send failed (attempt {attempt + 1}/{max_attempts}): {e}. "
                f"Retrying in {wait}s..."
            )
            time.sleep(wait)
            return False

        # Last attempt failed — try fallback SMTP if configured
        logger.error(f"Email send failed after {max_attempts} attempts: {e}")
        # Issue #1412 S1: Empfänger-Guard erneut gegen den Ersatz-Postausgang
        # auswerten, bevor auf ihn ausgewichen wird.
        if self._fallback_host and not self._fallback_recipients_blocked(recipients):
            try:
                self._dial_and_send(
                    self._fallback_host,
                    FALLBACK_SMTP_PORT,
                    self._fallback_user,
                    self._fallback_pass,
                    recipients,
                    msg,
                    from_addr,
                    # Issue #1448 S1: eigene, garantierte Deadline statt des
                    # (evtl. bereits aufgebrauchten) Rests des Primärbudgets.
                    deadline_at=time.monotonic() + FALLBACK_RESERVE_SECONDS,
                )
                logger.info("[SMTP-FALLBACK] sent via fallback SMTP")
                return True
            except Exception as fb_err:
                raise OutputError("email", f"Connection error: {e} (fallback also failed: {fb_err})")
        raise OutputError("email", f"Connection error: {e}")

    def send(
        self,
        subject: str,
        body: str,
        html: bool = True,
        plain_text_body: str | None = None,
        to: list[str] | str | None = None,
        mail_type: str | None = None,
        mail_format: str | None = None,
        compare_hourly_enabled: bool | None = None,
    ) -> None:
        """
        Send email via SMTP with automatic retry on network errors.

        Automatically retries up to 3 times with exponential backoff (5s, 15s, 30s)
        on temporary network errors (DNS, connection issues). Permanent errors
        (authentication) fail immediately without retry.

        SPEC: docs/specs/compare_email.md v4.2 - Multipart Email
        SPEC: docs/specs/bugfix/email_retry_mechanism_spec.md v1.0 - Retry Mechanism

        Args:
            subject: Email subject line
            body: Email body (HTML or plain text)
            html: If True, send as HTML email with plain-text fallback
            plain_text_body: Optional explicit plain-text version.
                             If not provided, plain-text is auto-generated from HTML.

        Raises:
            OutputError: If sending fails after all retry attempts
        """
        # Build message once (outside retry loop)
        # Use inbound address as From if set (Gmail supports plus-addresses)
        from_addr = self._reply_to or self._from

        # Issue #252: per-call recipient override.
        # `to` may be a list of addresses; falsy/empty falls back to settings.mail_to.
        # Issue #1147 Fix-Loop 1 (F002b): `to` als roher String (statt Liste)
        # darf NICHT zeichenweise iteriert werden — als Ein-Element-Liste
        # interpretieren.
        if isinstance(to, str):
            recipients: list[str] = [to] if to else [self._to]
        else:
            recipients = list(to) if to else [self._to]

        # Issue #1476 (AC-6, Vorbild telegram.py::_guard_code_origin): dieselbe
        # Herkunftssperre wie beim Telegram-Kanal. Bei Testlauf-Herkunft wird
        # auf eine Test-Mailbox umgeschaltet -- der bestehende #1219-Allowlist-
        # Guard (unten) blockiert sie zusaetzlich auf dem Resend-Pfad, auf
        # Stalwart wirkt die Umschaltung.
        if running_origin(Path(__file__)) == "test" and recipients != [_ORIGIN_GUARD_TEST_RECIPIENT]:
            logger.warning(
                "Herkunftssperre (Issue #1476): Testlauf-Herkunft erkannt -- "
                "E-Mail-Empfaenger von %s auf %s umgeschaltet.",
                [_mask_addr_for_log(r) for r in recipients], _ORIGIN_GUARD_TEST_RECIPIENT,
            )
            recipients = [_ORIGIN_GUARD_TEST_RECIPIENT]
        to_header = ", ".join(recipients)

        # Issue #1219 (löst die #1147-Denylist ab): dritte Guard-Linie —
        # empfängerseitig, direkt nach der finalen Empfänger-Auflösung, VOR
        # MIME-Bau/Dial. Greift auch bei per-Aufruf-Override (to=...), der
        # die Init-Guards umgeht. Statt einer 2-Adressen-Denylist wird jeder
        # Empfänger jetzt gegen eine POSITIVE Allowlist geprüft (echte
        # mail_to/email-Adressen angelegter, nicht als Test erkannter
        # Nutzerprofile). gregor-test@/gregor-staging@henemm.com gehören zu
        # keinem echten Profil und bleiben so automatisch blockiert
        # (Regressionsschutz für die abgelöste Denylist).
        # Fix-Loop 4 (F005): der rohe Substring-Scan (Fangnetz, s.o.) bleibt
        # ZUSÄTZLICH aktiv (kein Ersatz für die Allowlist-Prüfung) — er
        # greift unabhängig davon, ob die Parser-Pipeline den Empfänger
        # korrekt zerlegt.
        if "resend" in (self._host or "").lower():
            # Adversary F002 (Issue #1219): NICHT direkt GZ_DATA_DIR lesen —
            # das umgeht app.loader._DATA_ROOT, die autouse-Test-Isolation
            # aus tests/conftest.py (Issue #1133). get_data_root() honoriert
            # _DATA_ROOT zuerst, dann GZ_DATA_DIR, dann den Default "data" —
            # im echten Betrieb unverändert, in Tests korrekt isoliert.
            from app.loader import get_data_root

            allowlist = _load_resend_allowlist(data_dir=str(get_data_root()))
            blocked = []
            for r in recipients:
                # Nur candidates, die tatsaechlich wie eine Adresse aussehen
                # (enthalten "@"), gehen in die Allowlist-Pruefung ein --
                # die bewusst permissive Multi-Strategie-Extraktion von
                # _normalized_addrs_for_guard (Union aus getaddresses() +
                # Trennzeichen-Split, urspruenglich fuer die #1147-DENYLIST
                # gebaut) liefert bei kaputt gequoteten Anzeigenamen auch
                # reine Text-Fragmente ohne "@" (z.B. "foo"/"bar"), die nie
                # eine echte Adresse sein koennen und sonst die ALLOWLIST-
                # Pruefung (Allow-Logik: ALLE candidates muessen matchen)
                # faelschlich zum Blockieren echter Empfaenger bringen wuerden.
                candidates = [
                    a for a in _normalized_addrs_for_guard(r) if "@" in a
                ]
                # Issue #1412 S2b (D5, Variante C): zusaetzlich zur
                # plus-gekappten Form wird die ungekappte, getrimmte Form
                # gegen dieselbe, UNVERAENDERTE Allowlist geprueft (ODER,
                # nicht UND) -- eine bestaetigte Plus-Adresse erreicht sich
                # selbst, ohne dass Basisadresse oder ein anderer Zusatz
                # derselben Basisadresse dadurch mit-freigeschaltet wird.
                uncapped_candidates = [
                    a for a in _normalized_addrs_for_guard(r, cap_plus=False) if "@" in a
                ]
                if (
                    not candidates
                    or any(
                        a not in allowlist and u not in allowlist
                        for a, u in zip(candidates, uncapped_candidates)
                    )
                    or any(_is_reserved_test_domain(a) for a in candidates)
                    or _raw_contains_test_mailbox(r)
                ):
                    blocked.append(r)
            if blocked:
                masked = [_mask_addr_for_log(r) for r in blocked]
                logger.warning(
                    "Resend-Allowlist-Guard blockiert %d Empfänger, die "
                    "keinem echten Nutzerprofil zugeordnet werden konnten "
                    "(Issue #1147/#1219): %s",
                    len(blocked),
                    masked,
                )
                raise OutputConfigError(
                    "email",
                    f"{len(blocked)} Empfänger nicht in der Resend-Allowlist "
                    f"bei Host {self._host!r} — Versand blockiert (Issue "
                    "#1147/#1219). Nur mail_to/email echter, angelegter "
                    f"(Nicht-Test-)Nutzerprofile dürfen über Resend erreicht "
                    f"werden. Betroffene Domains: {masked}",
                )
        else:
            # Issue #1235: Nicht-Resend-Pfad (praktisch immer Stalwart, s.
            # #1122-Default-Deny) hatte bisher KEINEN Empfänger-Guard --
            # Stalwart relayt extern an Resend (infra#114), wodurch externe
            # Fake-Empfänger aus Alt-Presets/Tests durchgeleakt wurden.
            # Strenger als der Resend-Pfad (kein Allowlist-Bypass): nur
            # lokale @henemm.com-Empfänger (inkl. gregor-test@/
            # gregor-staging@ und Plus-Adressen) sind erlaubt, reservierte
            # Test-Domains blocken immer. Bewusst OHNE
            # _raw_contains_test_mailbox() -- der wuerde gerade die hier
            # gewollte lokale Zustellung an gregor-test@/gregor-staging@
            # blockieren.
            blocked = []
            for r in recipients:
                candidates = [
                    a for a in _normalized_addrs_for_guard(r) if "@" in a
                ]
                if (
                    not candidates
                    or any(_is_reserved_test_domain(a) for a in candidates)
                    or any(not _is_local_mail_domain(a) for a in candidates)
                ):
                    blocked.append(r)
            if blocked:
                masked = [_mask_addr_for_log(r) for r in blocked]
                logger.warning(
                    "Lokal-Guard blockiert %d Empfaenger ausserhalb von "
                    "LOCAL_MAIL_DOMAINS bzw. mit reservierter Test-Domain "
                    "(Issue #1235) bei Host %r: %s",
                    len(blocked), self._host, masked,
                )
                raise OutputConfigError(
                    "email",
                    f"{len(blocked)} Empfänger nicht lokal zustellbar "
                    f"bei Host {self._host!r} — Versand blockiert (Issue "
                    "#1235). Auf dem Nicht-Resend-Pfad sind ausschließlich "
                    f"lokale @henemm.com-Empfänger erlaubt. Betroffene "
                    f"Domains: {masked}",
                )

        msg = build_mime_message(
            subject=subject,
            body=body,
            from_addr=from_addr,
            to_header=to_header,
            reply_to=self._reply_to,
            html=html,
            plain_text_body=plain_text_body,
            mail_type=mail_type,
            mail_format=mail_format,
            compare_hourly_enabled=compare_hourly_enabled,
        )

        # Retry logic with exponential backoff
        # max_attempts includes the first try, so 4 attempts = 3 retries
        max_attempts = 4
        # Issue #1448 S1: 2s/4s/8s statt bisher 5s/15s/30s -- kuerzere
        # Wartepausen, damit realistisch mehrere Versuche plus Ersatzweg ins
        # Gesamtbudget SEND_BUDGET_SECONDS passen (Belegrechnung s. Spec).
        backoff_base = 2

        # Issue #1448 S1: Gesamtbudget der gesamten send()-Operation, einmalig
        # gesetzt (Vorbild ALERT_RUN_DEADLINE_SECONDS, #1447 S1).
        deadline_at = time.monotonic() + SEND_BUDGET_SECONDS

        # Team-Lead-Entscheidung 2026-08-01 (Runde 2, Fix zur AC-5/AC-2-
        # Gate-Lücke): der Primärweg bekommt eine EIGENE, um
        # FALLBACK_RESERVE_SECONDS VERKÜRZTE Deadline -- damit kann er die
        # Ersatzweg-Reserve strukturell nicht mehr anknabbern, unabhängig
        # davon, wie gut/schlecht das Gate unten schätzt (s.
        # `_handle_transient_dial_failure()`). Der Ersatzweg selbst nutzt
        # weiterhin seine eigene, frische Deadline (`FALLBACK_RESERVE_SECONDS`
        # ab dem Zeitpunkt seines Aufrufs, s.u.).
        primaer_deadline = deadline_at - FALLBACK_RESERVE_SECONDS
        # Randfall (nur in stark geschrumpften Testkonfigurationen denkbar,
        # FALLBACK_RESERVE_SECONDS >= SEND_BUDGET_SECONDS): ohne diese
        # Untergrenze bekäme der Primärweg gar keine reale Chance mehr --
        # `primaer_deadline` läge bereits in der Vergangenheit, und der
        # allererste Phasen-Timeout würde sofort mit Restzeit <= 0 abbrechen.
        # Bewusst NUR bei ECHTER Erschöpfung (<=jetzt) greifend, NICHT schon
        # wenn die verkürzte Deadline unter SMTP_OP_TIMEOUT_SECONDS liegt --
        # sonst würde ein groß bemessenes SMTP_OP_TIMEOUT_SECONDS bei knapp
        # geschrumpftem Testbudget die Deadline wieder aufblähen (genau der
        # Fehler, der AC-5 zuvor brach). Ein einzelner voller
        # SMTP_OP_TIMEOUT_SECONDS-Versuch ist in diesem Rand fall garantiert,
        # auch wenn das die Reserve knapp anschneidet -- besser als ein
        # Postausgang, der nie probiert wird.
        if primaer_deadline <= time.monotonic():
            primaer_deadline = time.monotonic() + SMTP_OP_TIMEOUT_SECONDS

        for attempt in range(max_attempts):
            # Issue #1448 S1: tatsächlich gemessene Dauer DIESES Versuchs --
            # dient in den Fehlerzweigen unten als realistischer Schätzwert
            # dafür, wie teuer ein weiterer Versuch würde (statt pessimistisch
            # immer mit dem vollen SMTP_OP_TIMEOUT_SECONDS zu rechnen, das ein
            # sofort scheiternder Versuch, z.B. ein 4xx-Gruß, gar nicht
            # verbraucht hat).
            versuch_start = time.monotonic()
            try:
                self._dial_and_send(
                    self._host,
                    self._port,
                    self._user,
                    self._password,
                    recipients,
                    msg,
                    from_addr,
                    deadline_at=primaer_deadline,
                )

                # Success - log if this was after retry
                if attempt > 0:
                    logger.info(f"Email send succeeded after {attempt + 1} attempt(s)")
                return

            except smtplib.SMTPAuthenticationError as e:
                # Auth failure (535 etc.) is permanent — never retry. Must be
                # caught BEFORE SMTPResponseException (it's a subclass with a
                # 5xx-ish code we still don't want to treat as transient).
                raise OutputError("email", f"SMTP authentication error: {e}")

            except smtplib.SMTPResponseException as e:
                # Issue #766: distinguish temporary 4xx (rate-limit 452,
                # service-busy 421) from permanent 5xx errors.
                if e.smtp_code >= 500:
                    raise OutputError(
                        "email",
                        f"SMTP permanent error {e.smtp_code}: {e.smtp_error}",
                    )
                # 4xx = temporary — retry with the same backoff schedule as OSError.
                # Issue #1448 S1 (AC-2/AC-5): `primaer_deadline` ist bereits um
                # FALLBACK_RESERVE_SECONDS verkürzt (s.o.) -- die Reserve ist
                # damit strukturell geschützt, das Gate hier ist reine
                # Optimierung ("keinen aussichtslosen Versuch mehr starten").
                # Als Schätzwert für die Kosten eines weiteren Versuchs dient
                # die GEMESSENE Dauer des gerade gescheiterten Versuchs (nicht
                # die pessimistische SMTP_OP_TIMEOUT_SECONDS-Konstante) -- ein
                # sofort abgelehnter Versuch (wie hier ein 4xx-Gruß) hat kaum
                # Budget verbraucht.
                versuch_dauer = time.monotonic() - versuch_start
                restzeit_primaer = primaer_deadline - time.monotonic()
                if (
                    attempt < max_attempts - 1
                    and restzeit_primaer > versuch_dauer
                ):
                    wait_multiplier = [1, 2, 4][attempt]
                    wait = min(
                        backoff_base * wait_multiplier,
                        max(restzeit_primaer, 0),
                    )
                    logger.warning(
                        f"SMTP temporary error {e.smtp_code} "
                        f"(attempt {attempt + 1}/{max_attempts}): "
                        f"{e.smtp_error}. Retrying in {wait}s..."
                    )
                    time.sleep(wait)
                else:
                    # Issue #1412 S1: Empfänger-Guard erneut gegen den
                    # Ersatz-Postausgang auswerten, bevor auf ihn ausgewichen
                    # wird — nicht bloß gegen self._host (Primärhost).
                    if self._fallback_host and not self._fallback_recipients_blocked(recipients):
                        try:
                            self._dial_and_send(
                                self._fallback_host,
                                FALLBACK_SMTP_PORT,
                                self._fallback_user,
                                self._fallback_pass,
                                recipients,
                                msg,
                                from_addr,
                                # Issue #1448 S1: eigene, garantierte Deadline
                                # statt des (evtl. bereits aufgebrauchten)
                                # Rests des Primärbudgets.
                                deadline_at=time.monotonic() + FALLBACK_RESERVE_SECONDS,
                            )
                            logger.info("[SMTP-FALLBACK] sent via fallback SMTP")
                            return
                        except Exception as fb_err:
                            raise OutputError(
                                "email",
                                f"SMTP temporary error {e.smtp_code} after {max_attempts} attempts (fallback also failed: {fb_err})",
                            )
                    raise OutputError(
                        "email",
                        f"SMTP temporary error {e.smtp_code} after "
                        f"{max_attempts} attempts: {e.smtp_error}",
                    )

            except smtplib.SMTPServerDisconnected as e:
                # RED-Phase-Fund (Issue #1448 S1): `smtplib.SMTP(...,
                # timeout=...)` wandelt einen bei der Begrüßung
                # (`getreply()` in `connect()`) zeitüberschrittenen
                # Verbindungsaufbau NICHT in ein `OSError` um, sondern in
                # `smtplib.SMTPServerDisconnected` -- smtplib-internes
                # Verhalten (`getreply()` fängt jedes `OSError` beim Lesen
                # ab und wirft stattdessen `SMTPServerDisconnected`, eine
                # reine `SMTPException`-Unterklasse, KEINE `OSError`-
                # Unterklasse trotz des Namens). Ohne einen eigenen,
                # spezifischeren Zweig VOR dem generischen
                # `smtplib.SMTPException`-Zweig würde ein hängender Primär-
                # Postausgang dort landen (kein Retry, kein Ersatzweg) --
                # AC-3/AC-4 verlangen aber genau hier Retry+Ersatzweg. Die
                # vom Team-Lead benannte Reihenfolge (Auth vor Response,
                # 5xx vor 4xx) bleibt davon unberührt; dies ist ein
                # zusätzlicher, spezifischerer Zweig für einen bislang
                # unerreichbaren Fall, kein Umbau bestehender Zweige.
                #
                # WICHTIG: `smtplib.SMTPException` selbst ist eine
                # `OSError`-Unterklasse (u.a. `SMTPRecipientsRefused` wäre
                # sonst faelschlich hier gelandet) -- deshalb NICHT einfach
                # mit dem `OSError`-Zweig zusammenlegen, sondern beide über
                # denselben Helper `_handle_transient_dial_failure()` an
                # ihrer jeweils korrekten Position aufrufen.
                #
                # Verhaltensänderung (Team-Lead-Hinweis 2026-08-01): dieser
                # Fall war VORHER schon erreichbar (ein Postausgang, der die
                # Verbindung ohne Timeout-Ursache abbricht), landete aber im
                # generischen "kein Retry"-Zweig. Jetzt wird er wiederholt --
                # sachlich richtig (ein vorübergehender Netzwerkfehler wie
                # jeder andere) und durch `primaer_deadline`/
                # FALLBACK_RESERVE_SECONDS gedeckelt statt unbegrenzt.
                versuch_dauer = time.monotonic() - versuch_start
                if self._handle_transient_dial_failure(
                    e, attempt, max_attempts, versuch_dauer, primaer_deadline,
                    backoff_base, recipients, msg, from_addr,
                ):
                    return

            except smtplib.SMTPException as e:
                # Other SMTP errors (e.g. SMTPRecipientsRefused) - no retry
                raise OutputError("email", f"SMTP error: {e}")

            except OSError as e:
                # Temporary network error (Issue #1448 S1: inkl. TimeoutError
                # aus _phase_timeout_or_raise()/_dial_and_send(), Unterklasse
                # von OSError -- kein neuer except-Zweig nötig für DIESEN
                # Fall). AC-2/AC-5: s. `_handle_transient_dial_failure()`.
                versuch_dauer = time.monotonic() - versuch_start
                if self._handle_transient_dial_failure(
                    e, attempt, max_attempts, versuch_dauer, primaer_deadline,
                    backoff_base, recipients, msg, from_addr,
                ):
                    return

# test
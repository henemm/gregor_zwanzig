---
entity_id: inbound_command_channels
type: module
created: 2026-02-17
updated: 2026-09-08
status: draft
version: "1.5"
tags: [f6, inbound, email, sms, premium-sms, imap, polling, channel, shortcode]
---

# Inbound Command Channels

## Approval

- [x] Approved

## Purpose

Abstrakte Inbound-Channel-Schicht fuer Trip-Befehle. Pollt verschiedene Eingangs-Kanaele
(Email/IMAP, spaeter SMS), extrahiert Trip-Kontext und Befehlstext, delegiert an den
channel-agnostischen `TripCommandProcessor` und sendet die Bestaetigung auf dem gleichen
Kanal zurueck.

## Source

- **File:** `src/services/inbound_email_reader.py` (NEW)
- **Integration:** `src/web/scheduler.py` (MODIFY)
- **Identifier:** `InboundEmailReader`, `run_inbound_command_poll()`

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `trip_shortcode_routing.md` | spec | Shortcode-generierung, RFC-2047-Dekodierung, toleranter Trip-Lookup (Bug #775) |
| `src/services/trip_command_processor.py` | module | Verarbeitet geparste Befehle, gibt CommandResult zurueck |
| `src/app/config.py` | module | Settings: SMTP_USER, SMTP_PASS, MAIL_TO, `email_verified_at` (#2143) |
| `src/app/loader.py` | module | `load_all_trips()` fuer Trip-Name -> Trip-ID Lookup; `lookup_user_by_email()` fuer Sender-Autorisierung (#2143) |
| `src/app/shortcode.py` | module | generate_shortcode(trip_name, user_id) -> GZ#-Code mit Kollisions-Guard |
| `src/outputs/email.py` | module | EmailOutput fuer Bestaetigungs-Email (Reply) |
| `src/web/scheduler.py` | module | APScheduler-Registrierung des Poll-Jobs |
| `imaplib` (stdlib) | module | IMAP4_SSL Client |
| `email` (stdlib) | module | email.message_from_bytes(), email.header.decode_header() für RFC-2047 (Bug #775), `Authentication-Results`-Header-Parsing (#2143) |
| `re` (stdlib) | module | Subject-Regex fuer Trip-Name-Extraktion, Whitespace-Normalisierung |

## Architecture

```
                     ┌──────────────────────┐
                     │   APScheduler        │
                     │   (alle 5 min)       │
                     └──────────┬───────────┘
                                │
               ┌────────────────┼────────────────┐
               v                                  v
  ┌────────────────────┐             ┌────────────────────┐
  │ InboundEmailReader │             │ (InboundSmsReader) │
  │ polls IMAP Inbox   │             │ polls SMS Gateway  │
  └────────┬───────────┘             │ (future, F1)       │
           │                         └────────────────────┘
           │ extracts:
           │  - trip_name (from Subject)
           │  - body (plain-text)
           │  - sender (From header)
           │
           v
  ┌────────────────────────────┐
  │ InboundMessage DTO         │
  │ (channel-agnostic)         │
  └────────────┬───────────────┘
               │
               v
  ┌────────────────────────────┐
  │ TripCommandProcessor       │
  │ .process(msg) → Result     │
  └────────────┬───────────────┘
               │
               v
  ┌────────────────────────────┐
  │ CommandResult              │
  │ .confirmation_subject      │
  │ .confirmation_body         │
  └────────────┬───────────────┘
               │
     ┌─────────┴──────────┐
     v                    v
  Email Reply          SMS Reply
  (EmailOutput)        (SmsOutput, future)
```

**Prinzip: Antwort auf gleichem Kanal.** Kommt der Befehl per Email, geht die
Bestaetigung per Email. Kommt er per SMS, geht sie per SMS.

## Implementation Details

### 1. InboundEmailReader

```python
class InboundEmailReader:
    """Pollt IMAP Inbox und verarbeitet Trip-Befehle aus Email-Replies."""

    IMAP_HOST = "imap.gmail.com"
    IMAP_PORT = 993
    _SUBJECT_TRIP_RE = re.compile(r"\[(.+?)\]")
    _REPLY_PREFIXES = re.compile(
        r"^(Re|Fwd|AW|WG|Antwort|SV):\s*", re.IGNORECASE,
    )

    def poll_and_process(self, settings: Settings) -> int:
        """
        Liest UNSEEN Emails, verarbeitet Befehle, sendet Bestaetigungen.
        Returns: Anzahl verarbeiteter Befehle.
        """
        if not settings.smtp_user or not settings.smtp_pass:
            return 0

        imap = None
        processed = 0
        try:
            imap = imaplib.IMAP4_SSL(self.IMAP_HOST, self.IMAP_PORT)
            imap.login(settings.smtp_user, settings.smtp_pass)
            imap.select("INBOX")
            _, data = imap.search(None, "UNSEEN")
            uids = data[0].split()

            for uid in uids:
                try:
                    processed += self._process_single(imap, uid, settings)
                except Exception as e:
                    logger.error(f"Error processing email uid={uid}: {e}")
        except imaplib.IMAP4.error as e:
            logger.error(f"IMAP error: {e}")
        except OSError as e:
            logger.error(f"Network error: {e}")
        finally:
            if imap:
                try:
                    imap.logout()
                except Exception:
                    pass
        return processed
```

### 2. Einzelne Email verarbeiten

```python
def _process_single(
    self,
    imap: imaplib.IMAP4_SSL,
    uid: bytes,
    settings: Settings,
) -> int:
    """Verarbeitet eine Email. Returns 1 wenn Befehl verarbeitet, sonst 0."""
    _, msg_data = imap.fetch(uid, "(RFC822)")
    msg = email.message_from_bytes(msg_data[0][1])

    # 1. Sender pruefen (stumm bei Fehler — Sicherheit)
    from_addr = self._parse_sender(msg.get("From", ""))
    if not self._authorize(from_addr, settings, msg):
        imap.store(uid, "+FLAGS", "\\Seen")
        return 0

    # 2. Trip aus Subject extrahieren — Fehler-Email bei fehlendem [Trip Name]
    subject = msg.get("Subject", "")
    trip_name = self._extract_trip_name(subject)
    if not trip_name:
        result = CommandResult(
            success=False, command="parse_error",
            confirmation_subject="Befehl nicht erkannt",
            confirmation_body=(
                "Kein Trip-Name im Betreff gefunden.\n"
                "Betreff muss [Trip Name] enthalten, z.B.:\n"
                "  Re: [GR221 Mallorca] Morning Report\n\n"
                "Befehlsformat im Text:\n"
                "  ### ruhetag\n"
                "  ### startdatum 2026-03-01"
            ),
        )
        if settings.can_send_email():
            self._send_email_reply(result, settings)
        imap.store(uid, "+FLAGS", "\\Seen")
        return 0

    # 3. Trip-ID nachschlagen — Fehler-Email wenn nicht gefunden
    trip_id = self._find_trip_id(trip_name)
    if not trip_id:
        result = CommandResult(
            success=False, command="trip_not_found",
            confirmation_subject=f"[{trip_name}] Trip nicht gefunden",
            confirmation_body=(
                f"Kein Trip mit Name '{trip_name}' gefunden.\n"
                "Bitte pruefen ob der Trip-Name korrekt ist."
            ),
            trip_name=trip_name,
        )
        if settings.can_send_email():
            self._send_email_reply(result, settings)
        imap.store(uid, "+FLAGS", "\\Seen")
        return 0

    # 4. Body extrahieren
    body = self._extract_plain_body(msg)

    # 5. An Processor delegieren
    inbound = InboundMessage(
        trip_name=trip_name,
        body=body,
        sender=from_addr,
        channel="email",
        received_at=datetime.now(tz=timezone.utc),
    )
    processor = TripCommandProcessor()
    result = processor.process(inbound)

    # 6. Bestaetigung auf gleichem Kanal (Email) — IMMER senden (auch bei Fehler)
    if settings.can_send_email():
        self._send_email_reply(result, settings)

    # 7. Als gelesen markieren
    imap.store(uid, "+FLAGS", "\\Seen")
    return 1
```

### 3. Bestaetigungs-Email (Reply auf gleichem Kanal)

```python
def _send_email_reply(self, result: CommandResult, settings: Settings) -> None:
    """Sendet Bestaetigung als Email zurueck an den Absender."""
    email_output = EmailOutput(settings)
    email_output.send(
        subject=result.confirmation_subject,
        body=result.confirmation_body,
        html=False,  # Plain-text fuer maximale Kompatibilitaet unterwegs
    )
    logger.info(
        f"Confirmation sent: {result.confirmation_subject}"
    )
```

### 4. Subject-Parsing (Trip-Identifikation)

```python
def _strip_reply_prefixes(self, subject: str) -> str:
    """Entfernt Re:, AW:, Fwd:, WG: etc. rekursiv."""
    while True:
        cleaned = self._REPLY_PREFIXES.sub("", subject).strip()
        if cleaned == subject:
            return cleaned
        subject = cleaned

def _extract_trip_name(self, subject: str) -> str | None:
    """Extrahiert Trip-Name aus '[Trip Name] Morning/Evening Report'."""
    clean = self._strip_reply_prefixes(subject)
    match = self._SUBJECT_TRIP_RE.search(clean)
    return match.group(1) if match else None
```

### 5. Sender-Authentifizierung (v1.5, SECURITY-FIX #2143)

**Vorher (bis v1.4, tautologisch):** Der Absender wurde per `lookup_user_by_email()`
aus dem `From:`-Header aufgeloest und danach exakt gegen `mail_to` desselben,
aus demselben Header aufgeloesten Profils geprueft — ein gefaelschter `From:`-Header
mit einer bekannten `mail_to`-Adresse genuegte, um Trip-Kommandos jedes beliebigen
Nutzers auszuloesen.

**Jetzt (Hybrid B+A, analog Telegram-Pattern #2141/#1019):**

1. **B — Identitaets-Basis:** `lookup_user_by_email()` (`src/app/loader.py`) ist
   analog `lookup_user_by_telegram_chat_id()` umgebaut: trennt echte von
   Test-Nutzern, gibt bei **Mehrfachtreffer `None`** zurueck (nie den ersten
   Treffer). `_resolve_settings_for_sender()` loest damit weiterhin
   `user_id = lookup_user_by_email(...) or "default"` auf ("kein Treffer" UND
   "mehrdeutig" fallen so einheitlich auf `"default"`). Direkt danach, in
   `_process_single()` (NICHT in `_authorize()` — Identitaetsaufloesung und
   Autorisierungspruefung sind zwei getrennte Zustaendigkeiten, analog dem
   Telegram-Reader, wo der Gate ebenfalls im Reader steht), greift ein
   explizites Gate: `user_id == "default"` bedeutet unbekannter/nicht
   eindeutiger Absender — das Kommando wird NICHT verarbeitet, es geht **kein
   Reply** (kein Adress-Leak, anders als beim Telegram-Reader, der einen
   Registrierungs-Hinweis sendet), analog ADR-0003 („kein ungeschuetzter
   `default`-Fallback in einem authentifizierten Pfad").
2. Das gefundene Nutzerprofil muss `email_verified_at` gesetzt haben
   (Truthy-Check auf einen RFC3339-String, analog dem bestehenden Outbound-Check
   in `src/output/channels/email.py:291`) — sonst ablehnen. **Voraussetzung:**
   `email_verified_at` muss dafuer explizit als `Settings`-Feld deklariert sein
   (analog `premium_sms_reply_to`/`_at`) — sonst wird es beim Laden des
   Nutzerprofils durch `extra="ignore"` (`config.py:117`) stillschweigend
   verworfen und der gesamte Check ist wirkungslos, obwohl er im Code steht.
3. **A — Transport-Authentifizierung:** der **erste** `Authentication-Results`-Header
   der Nachricht wird geparst (`msg.get(...)`, NICHT `get_all()` — Stalwart
   prependt seinen echten Header immer zuoberst, ein Angreifer koennte einen
   zweiten gefaelschten Header mit `pass` anhaengen). `authserv-id` muss dem
   eigenen Mailserver-Hostnamen entsprechen — Quelle und exakter Feldname
   (unten als `user_settings.mail_server_hostname` bezeichnet) sind mit der
   Implementierung festzulegen, nicht hartkodiert. Gefordert: `spf=pass` UND
   `dkim=pass` (oder `dmarc=pass` als Alignment-Ersatz). Fehlt der Header
   komplett, ist `authserv-id` fremd, oder liefert er `fail`/`none`/`softfail`
   -> **fail-closed ablehnen**.
4. Der bestehende Sender==`mail_to`-Vergleich (Loop-Guard) bleibt zusaetzlich
   bestehen.

```python
def _parse_sender(self, from_header: str) -> str:
    """Extrahiert Email-Adresse aus 'Name <addr>' Format."""
    _, addr = email.utils.parseaddr(from_header)
    return addr.lower()

# In _process_single(), NACH dem Aufloesen von user_id/user_settings:
if _user_id == "default":
    logger.warning(f"Unresolved/ambiguous sender: {from_addr!r}")
    imap.store(uid, "+FLAGS", "\\Seen")
    return 0
if not self._authorize(from_addr, user_settings, msg):
    imap.store(uid, "+FLAGS", "\\Seen")
    return 0

def _authorize(
    self, sender: str, settings: Settings, msg: email.message.Message,
) -> bool:
    """Multi-User (#2143): bestehende Adress-Logik (mail_from/mail_to/
    inbound_address, unveraendert) + NEU email_verified_at + SPF/DKIM-Pass.
    `settings` ist HIER bereits die user-scoped Settings aus
    `_resolve_settings_for_sender()` -- kein eigener Lookup mehr in
    `_authorize` selbst (der sitzt im Gate oben, in `_process_single`)."""
    mail_from_lower = (settings.mail_from or "").lower()
    if mail_from_lower and sender == mail_from_lower:
        return False
    if not settings.mail_to:
        return False
    allowed = {settings.mail_to.lower()}
    inbound = settings.get_inbound_address()
    if inbound and inbound.lower() != mail_from_lower:
        allowed.add(inbound.lower())
    if sender not in allowed:
        logger.debug(f"Ignoring email from: {sender!r}")
        return False

    if not settings.email_verified_at:
        logger.warning(f"Sender not verified: {sender!r}")
        return False
    if not self._spf_dkim_pass(msg, settings.mail_server_hostname):
        logger.warning(f"SPF/DKIM check failed: {sender!r}")
        return False
    return True

def _spf_dkim_pass(self, msg: email.message.Message, expected_authserv_id: str) -> bool:
    """Nur der ERSTE Authentication-Results-Header zaehlt (Stalwart prependt).
    parse_authentication_results() ist eine NEU zu bauende Helper-Funktion
    (RFC-8601-Parsing von authserv-id + method=result-Paaren)."""
    header_value = msg.get("Authentication-Results")  # get(), NIE get_all()
    if not header_value:
        return False
    authserv_id, results = parse_authentication_results(header_value)  # NEW helper
    if authserv_id != expected_authserv_id:
        return False
    return results.get("spf") == "pass" and (
        results.get("dkim") == "pass" or results.get("dmarc") == "pass"
    )
```

### 6. Body-Extraktion

```python
def _extract_plain_body(self, msg: email.message.Message) -> str:
    """Extrahiert Plain-Text-Body. Multipart: ersten text/plain Part."""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                payload = part.get_payload(decode=True)
                charset = part.get_content_charset() or "utf-8"
                return payload.decode(charset, errors="replace")
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or "utf-8"
            return payload.decode(charset, errors="replace")
    return ""
```

### 7. Trip-ID Lookup

```python
def _find_trip_id(self, trip_name: str) -> str | None:
    """Case-insensitive Name → Trip-ID Lookup."""
    for trip in load_all_trips():
        if trip.name.lower() == trip_name.lower():
            return trip.id
    logger.warning(f"No trip found for name: {trip_name!r}")
    return None
```

### 8. Scheduler-Integration

```python
# In src/web/scheduler.py:

def run_inbound_command_poll() -> None:
    """Poll inbound channels for trip commands."""
    from src.services.inbound_email_reader import InboundEmailReader
    from src.app.config import Settings

    settings = Settings()
    if not settings.smtp_user or not settings.smtp_pass:
        return

    reader = InboundEmailReader()
    count = reader.poll_and_process(settings)
    if count > 0:
        logger.info(f"Inbound commands processed: {count}")


# In init_scheduler():
_scheduler.add_job(
    run_inbound_command_poll,
    CronTrigger(minute="*/5", timezone=TIMEZONE),
    id="inbound_command_poll",
    name="Inbound Command Poll (every 5min)",
)
```

### 9. Erweiterbarkeit: SMS-Channel (Future)

Der SMS-Channel folgt dem gleichen Muster — nur die Polling-Quelle und der
Reply-Mechanismus aendern sich:

```python
# Zukunft (F1 + F6):
class InboundSmsReader:
    """Pollt SMS-Gateway API (z.B. Seven.io) auf eingehende Befehle."""

    def poll_and_process(self, settings: Settings) -> int:
        # 1. SMS-API abfragen (wie weather_email_autobot SMSPollingClient)
        # 2. Trip-Name aus Kontext (z.B. letzte SMS-Konversation, oder explizit)
        # 3. InboundMessage(channel="sms") erstellen
        # 4. TripCommandProcessor.process(msg)
        # 5. SmsOutput.send(result.confirmation_body)  ← SMS Reply
        ...
```

Beide Reader nutzen denselben `TripCommandProcessor` und dieselben DTOs.
Der einzige Unterschied: Polling-Quelle und Reply-Output.

> **Hinweis (Issue #1676, Scheibe S1, 2026-08-10):** Der oben skizzierte
> `InboundSmsReader` ist NICHT der ursprünglich gebaute. Der reale
> `src/services/inbound_sms_reader.py` (Spec:
> `docs/specs/modules/feat_1676_s1_premium_sms_rueckkanal.md`) verarbeitete zu
> diesem Zeitpunkt **keine Trip-Befehle** und rief `TripCommandProcessor` nicht
> auf — er pollte das seven.io-Journal ausschließlich, um für Premium-Nutzer die
> Garmin-inReach-Rückadresse (Kennzeichen `inreachlink.com`) zu lernen und in
> `user.json` zu speichern.
>
> **Nachtrag (Issue #2184, Scheibe S4 Epic #2133, 2026-09-08):** Das hat sich
> geändert. Derselbe Poll-Durchlauf verarbeitet jetzt zusätzlich den vor dem
> Kennzeichen stehenden Nachrichtentext als Befehl: nach dem unveränderten
> Lernaufruf, in einem eigenen nachgelagerten `try/except` (darf den F001-
> Dedup-Zeiger nicht beeinflussen), wird `InboundMessage(channel="premium_sms",
> ...)` gebaut und an `TripCommandProcessor.process()` delegiert; die Antwort
> geht per `NotificationService.send_command_reply_premium_sms` an die soeben
> gelernte Rückadresse zurück. Premium-SMS ist damit — nach Email und Telegram —
> der **dritte Erzeuger** von `InboundMessage` und ein vollwertiger
> Ad-hoc-Abrufkanal, auf demselben `TripCommandProcessor` wie oben beschrieben.
> Es gibt weiterhin **keinen** generischen SMS-Kanal (nur Premium-SMS über den
> Garmin-inReach-Rückkanal); die Trip-Auswahl bei fehlendem Trip-Namen im Text
> läuft über den neuen geteilten Baustein `pick_active_trip`
> (`src/services/trip_selection.py`). Details:
> `docs/specs/modules/feat_2184_s4_premium_sms_kommandoverarbeiter.md`.

## Configuration

| Parameter | Quelle | Beschreibung |
|-----------|--------|-----------|
| IMAP Host | Hardcoded `imap.gmail.com` | MVP: Gmail only |
| IMAP Port | Hardcoded `993` | SSL |
| IMAP User | `GZ_SMTP_USER` | Gleiche Credentials wie SMTP |
| IMAP Pass | `GZ_SMTP_PASS` | Gleiche Credentials wie SMTP |
| Inbound-Adresse | `GZ_INBOUND_ADDRESS` | Plus-Adresse fuer Befehle (z.B. `user+gregor@gmail.com`). Default: `GZ_SMTP_USER` |
| Sender-Whitelist | pro Nutzer `mail_to` in `user.json` (#2143) | Multi-User: `mail_to` UND `email_verified_at` gesetzt UND SPF/DKIM-Pass (`Authentication-Results`) sind alle drei Pflicht, nicht nur `mail_to`-Gleichheit |
| Authentication-Results `authserv-id` | Settings/Config (Mailserver-Hostname, Feldname mit Implementierung festzulegen) | Muss dem eigenen Hostnamen entsprechen — verhindert, dass ein von fremdem Server gesetzter Header akzeptiert wird |
| Poll-Intervall | `*/5` (CronTrigger) | Alle 5 Minuten |
| Bestaetigung | Immer aktiv | Reply auf gleichem Kanal |

### Plus-Adress-Feature (GZ_INBOUND_ADDRESS)

Wenn `GZ_INBOUND_ADDRESS` gesetzt (z.B. `henning.emmrich+gregor-zwanzig@gmail.com`):
- IMAP-Suche filtert nach `TO <inbound_address>` statt alle UNSEEN zu lesen
- Persoenliche Emails werden nie angefasst
- Report-Emails werden mit `Reply-To: <inbound_address>` gesendet
- Report-Emails werden FROM `<inbound_address>` gesendet (Gmail unterstuetzt Plus-Adressen als Absender)
- User-Replies landen automatisch bei der richtigen Adresse

## Expected Behavior

- **Input:** Ungelesene Email in IMAP Inbox
  - Subject: `Re: [GR221 Mallorca] Morning Report - 17.02.2026`
  - From: verifizierte `mail_to`-Adresse eines eindeutig aufloesbaren Nutzers, mit
    `Authentication-Results: spf=pass; dkim=pass` vom eigenen Mailserver
  - Body: `### ruhetag`

- **Output:**
  - Befehl wird an TripCommandProcessor delegiert
  - Bestaetigungs-Email an Absender gesendet (gleicher Kanal)
  - Email als SEEN markiert

- **Side effects:**
  - IMAP-Verbindung zu imap.gmail.com:993
  - Emails werden als SEEN markiert (nicht geloescht)
  - Bestaetigungs-Email via SMTP
  - Alle Trip-Modifikationen durch TripCommandProcessor, gescoped auf `user_id` des
    aufgeloesten Absenders

### Filterlogik

| Bedingung | Verhalten |
|-----------|-----------|
| Absender != mail_to | SEEN markieren, debug-log, **kein Reply** (Sicherheit: kein Adress-Leak) |
| `lookup_user_by_email` liefert Mehrfachtreffer (`None`) oder `user_id == "default"` (#2143) | SEEN markieren, **kein Reply**, **WARNING-log** |
| `email_verified_at` fehlt/nicht gesetzt (#2143) | SEEN markieren, **kein Reply**, **WARNING-log** |
| `Authentication-Results` fehlt, `authserv-id` fremd, oder `spf`/`dkim`/`dmarc` != `pass` (#2143) | SEEN markieren, **kein Reply**, **WARNING-log** (Haertung: vormals nur DEBUG — Auth-Fehler muessen in Produktion sichtbar sein) |
| Kein `[Trip Name]` im Betreff | **Fehler-Email senden**, SEEN markieren |
| Trip-Name nicht gefunden | **Fehler-Email senden**, SEEN markieren |
| IMAP-Verbindungsfehler | Poll-Zyklus abbrechen, error-log |
| Fehler bei einzelner Email | Diese Email ueberspringen, error-log |

### Fehler-Antworten (Gate-Fehler) — NEU in v1.1

Wenn ein autorisierter Absender eine Email schickt die nicht verarbeitet werden kann,
bekommt er eine hilfreiche Fehler-Email zurueck (statt stiller Verwerfung).

| Gate-Fehler | confirmation_subject | confirmation_body (Auszug) |
|-------------|---------------------|---------------------------|
| Kein `[Trip Name]` im Betreff | `Befehl nicht erkannt` | Kein Trip-Name im Betreff gefunden. Betreff muss [Trip Name] enthalten. |
| Trip nicht gefunden | `[Name] Trip nicht gefunden` | Kein Trip mit Name 'X' gefunden. |

**Ausnahme:** Autorisierungsfehler (unbekannter Absender, fehlende Verifizierung,
fehlgeschlagener SPF/DKIM-Check, Mehrfachtreffer) bleiben stumm — Sicherheit
hat Vorrang (kein Leak dass die Adresse existiert/aktiv ist).

**Bestaetigungen bei Processor-Fehlern:** Auch wenn `TripCommandProcessor.process()`
ein `CommandResult(success=False)` zurueckgibt (z.B. "Unbekannter Befehl", "Ungueltiges Datum"),
wird die Fehler-Antwort an den User gesendet. Der User erhaelt IMMER eine Rueckmeldung
wenn er autorisiert ist.

### Bestaetigungs-Beispiel (Email-Kanal):

```
Eingang:
  From: wanderer@gmail.com
  Subject: Re: [GR221 Mallorca] Morning Report - 17.02.2026
  Body: ### ruhetag: 2

Antwort (Email):
  To: wanderer@gmail.com
  Subject: [GR221 Mallorca] Ruhetag bestaetigt
  Body:
    Ruhetag eingetragen: +2 Tage.

    Verschobene Etappen:
      Tag 3: 18.02.2026 -> 20.02.2026
      Tag 4: 19.02.2026 -> 21.02.2026

    Naechster Report kommt planmaessig.
```

## Acceptance Criteria

- **AC-1:** Given eine Email mit gefaelschtem `From:`-Header auf die `mail_to`-Adresse eines echten Nutzers, aber ohne passenden `Authentication-Results: spf=pass; dkim=pass`-Header vom eigenen Mailserver / When die Email verarbeitet wird / Then wird das Kommando NICHT verarbeitet, kein Trip wird geaendert, kein Reply wird gesendet.
  - Test: `test_bug_inbound_email_loop.py` / neue Adversary-Testdatei — Assertion auf unveraenderten Trip-Zustand nach Verarbeitung der gespooften Mail.

- **AC-2:** Given zwei verschiedene, jeweils eindeutig verifizierte Nutzer A und B mit eigenen Trips / When ein Kommando per Email von Nutzer A eingeht / Then wird niemals ein Trip von Nutzer B veraendert (Zwei-Nutzer-Pflicht laut CLAUDE.md).
  - Test: neue Kern-Testdatei, zwei `user.json`-Fixtures + zwei Trips, Kommando von A, Assertion dass Trip von B unveraendert bleibt.

- **AC-3:** Given ein Nutzerprofil ohne gesetztes `email_verified_at` / When eine Email mit korrektem SPF/DKIM-Pass und passendem `mail_to` von diesem Absender eingeht / Then wird kein Kommando ausgeloest und kein Reply gesendet.
  - Test: `_authorize()`-Unit-Test mit `email_verified_at=None`, sonst vollstaendig gueltige Eingabe.

- **AC-4:** Given zwei Nutzerprofile mit identischer `mail_to`-Adresse (Mehrfachtreffer) / When `lookup_user_by_email()` fuer diese Adresse aufgerufen wird / Then liefert der Lookup `None` statt eines der beiden Profile, und die zugehoerige Email wird abgelehnt statt einem der Profile zugeordnet.
  - Test: `lookup_user_by_email`-Unit-Test mit zwei kollidierenden Fixtures.

- **AC-5:** Given eine Email mit zwei `Authentication-Results`-Headern, wobei der erste (von Stalwart gesetzte) `fail`/`none` liefert und ein zweiter, vom Angreifer eingefuegter Header `pass` behauptet / When die Email verarbeitet wird / Then wird nur der erste Header ausgewertet und die Email fail-closed abgelehnt.
  - Test: Adversary-Test mit versionierter Zwei-Header-Fixture, Assertion auf `_spf_dkim_pass()`-Rueckgabe `False`.

- **AC-6:** Given eine Email mit korrektem SPF/DKIM-Pass vom eigenen Mailserver, gesetztem `email_verified_at` und eindeutigem Lookup-Ergebnis / When die Email verarbeitet wird / Then wird das Kommando wie zuvor am bestehenden `TripCommandProcessor` verarbeitet und die Bestaetigung an den Absender gesendet (Regressions-AC, bestehendes Verhalten bleibt erhalten).
  - Test: bestehende Integrationstests (`test_issue_1009_1019_inbound_robustness.py`) weiterhin gruen, ergaenzt um die versionierte gueltige `Authentication-Results`-Fixture.

## Files to Create/Modify

| File | Action | LOC |
|------|--------|-----|
| `src/services/inbound_email_reader.py` | NEW | ~120 |
| `src/web/scheduler.py` | MODIFY | ~15 |

## Testing Strategy

### Integration Tests (Real IMAP — No Mocks!)

```python
def test_poll_finds_reply_email()
def test_strip_german_reply_prefix()
def test_strip_multiple_prefixes()
def test_unauthorized_sender_ignored()
def test_email_marked_seen_after_processing()
def test_confirmation_email_sent_on_same_channel()
def test_unknown_command_sends_help_reply()
def test_imap_failure_does_not_crash_scheduler()
```

### Kern-Tests (#2143, deterministisch, kein Live-Netz)

- Versionierte, aus echten (anonymisierten) Stalwart-Logs abgeleitete
  `Authentication-Results`-Header-Fixture fuer die Parse-/Validierungslogik
  (`_spf_dkim_pass()`), inkl. `pass`/`fail`/`none`/fremder-`authserv-id`-Faellen.
- Adversary-Test: zweiter gefaelschter `Authentication-Results`-Header mit `pass`
  wird ignoriert — nur der erste (von Stalwart gesetzte) Header zaehlt (AC-5).
- Zwei-Nutzer-Test: Mail mit `From: a@…` aendert nie einen Trip von Nutzer b (AC-2).
- Bestehender Submission-Loopback-Test (`test_issue_1009_1019_inbound_robustness.py`)
  bleibt fuer die uebrigen ACs bestehen, wird um einen Kommentar ergaenzt, warum er
  den `Authentication-Results`-Pfad strukturell nicht abdeckt (authentifizierte
  SMTP-Submission durchlaeuft nicht die anonyme Port-25-Pipeline, die den Header
  setzt).

### Live-E2E-Test (separat, Marker `live`/`email`)

- Statt eines externen Testaccounts liefert `_deliver_mail_anonymous()`
  (`tests/tdd/test_issue_1009_1019_inbound_robustness.py:205`) unauthentifiziert
  von diesem Server selbst per Rohverbindung an `mail.henemm.com:25` aus —
  autorisiert durch den `a:mail.henemm.com`-Mechanismus im SPF-Record von
  henemm.com. Die Mail durchlaeuft dadurch die echte anonyme Port-25-Pipeline
  (nicht die authentifizierte Port-587-Submission), Stalwart prependt einen
  echten `Authentication-Results`-Header. Zielpostfach bleibt das bestehende
  `gregor-test@henemm.com`, keine Staging-Adresse oder externer Account noetig.
- `test_live_authorized_sender_over_real_anonymous_pipeline_is_processed`
  bestaetigt den autorisierten Erfolgspfad, `test_live_spoofed_envelope_over_real_anonymous_pipeline_is_rejected`
  die Fail-Closed-Ablehnung bei gefaelschtem Envelope-Absender — beide ueber
  die reale Pipeline, nicht ueber eine Fixture.

## Known Limitations

- Gmail-only IMAP (imap.gmail.com hardcoded)
- 5-Minuten-Verzoegerung (kein IMAP IDLE / Push)
- SMS-Channel noch nicht implementiert (benoetigt F1)
- Kein Retry bei IMAP-Fehler (naechster Poll-Zyklus versucht erneut)
- App-Passwort erforderlich bei Gmail mit 2FA
- Reply-Token-Verfahren (Out-of-Band-Bestaetigung analog Telegram `/start TOKEN`,
  Option C aus der #2143-Analyse) wurde bewusst NICHT gebaut — SPF/DKIM-Pass via
  `Authentication-Results` in Kombination mit `email_verified_at` gilt als
  ausreichende Transport- und Identitaets-Absicherung fuer diesen Kanal.
- `parse_authentication_results()` (`src/services/inbound_email_reader.py:37-58`)
  fuehrt mehrere `spf=`-Segmente in einem Header (HELO- vs. MAILFROM-Scope)
  positionsbasiert zusammen (letztes Vorkommen gewinnt) statt scope-bewusst —
  heute empirisch korrekt, weil Stalwart MAILFROM nach HELO schreibt, aber
  nicht vertraglich zugesichert (Adversary-Finding F006). Follow-up-Issue
  #2252.

## Error Handling

| Fehlertyp | Behandlung |
|-----------|-----------|
| `imaplib.IMAP4.error` | error-log, Poll abbrechen, 0 zurueck |
| `OSError` (Netzwerk) | error-log, Poll abbrechen, 0 zurueck |
| Exception bei einzelner Email | error-log, ueberspringen, weiter |
| `imap.logout()` fehlschlag | Exception schlucken (Cleanup) |
| `EmailOutput.send()` fehlschlag | error-log, Befehl trotzdem als verarbeitet zaehlen |

Kein Fehler darf den APScheduler-Thread zum Absturz bringen.

> **Hinweis (Issue #1009):** Eine unbehandelte Exception bei der Kommando-Verarbeitung oder beim Antwortversand würde eine Mail in einem undefinierten Zustand hinterlassen. Seit Issue #1009 werden Verarbeitung und Antwortversand unter einem gemeinsamen `try/except/finally` durchgeführt, mit `\Seen`-Markierung **im finally-Block** — damit wird die Mail in jedem Fall (auch bei Fehler) als gelesen markiert, was ein Reprocessing beim nächsten Poll-Zyklus verhindert.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0003 (kein neues ADR noetig)
- **Rationale:** ADR-0003 verbietet einen ungeschuetzten `"default"`-Fallback in
  einem authentifizierten Pfad. Der Email-Inbound-Kanal war bisher die einzige
  Ausnahme davon — Sender-Autorisierung wurde tautologisch aus demselben `From:`-
  Header abgeleitet, den sie eigentlich pruefen sollte, ohne Transport-Auth
  (SPF/DKIM), ohne `email_verified_at`-Pflicht und ohne `user_id == "default"`-
  Gate. Dieser Fix setzt ADR-0003 konsequent fuer den Mail-Kanal um, analog dem
  bereits ADR-0003-konformen Telegram-Reader (#2141/#1019) — kein neues
  Grundsatzdokument noetig, nur die konsequente Anwendung des bestehenden.

## Changelog

- 2026-09-08: v1.5 SECURITY-FIX (#2143): Sender-Authentifizierung war tautologisch
  (Absender wurde aus From: aufgeloest und gegen dasselbe Profil geprueft) —
  SPF/DKIM/DMARC via Authentication-Results-Header (fail-closed, nur erster
  Header, authserv-id-Check) + email_verified_at-Pflicht + Eindeutigkeits-Fix bei
  lookup_user_by_email (analog #2141) + user_id=="default"-Gate (ADR-0003)
  ergaenzt. Abschnitt 5, Configuration-Tabelle, Filterlogik-Tabelle, Known
  Limitations, Testing Strategy aktualisiert; Acceptance Criteria und
  Architektur-Entscheidung (ADR) neu ergaenzt (schließt bestehende Spec-Drift zum
  Code, der Single-User-Stand war bereits vor diesem Fix veraltet).
- 2026-09-08: v1.4 HINWEIS: Abschnitt 9 um Nachtrag zu Issue #2184 (Epic #2133,
  Scheibe S4) ergänzt — Premium-SMS ist seit dieser Scheibe der dritte
  Erzeuger von `InboundMessage` und ein vollwertiger Ad-hoc-Abrufkanal (zuvor
  lernte der Reader nur die Rückadresse, ohne Befehle zu verarbeiten). Kein
  Code in dieser Spec geändert.
- 2026-08-10: v1.3 HINWEIS: Abschnitt 9 (SMS-Channel Future) um Klarstellung
  ergänzt — der reale `InboundSmsReader` aus Issue #1676 Scheibe S1 ist kein
  Trip-Befehlskanal, sondern lernt ausschließlich die Garmin-inReach-
  Rückadresse für Premium-Nutzer. Kein Code in dieser Spec geändert.
- 2026-04-12: v1.2 BUGFIX (BUG-IMAP-01): `inbound_email_reader.py` nutzt jetzt `imap_user`/`imap_pass` aus config statt `smtp_user`/`smtp_pass`. `config.py` und `scheduler.py` entsprechend angepasst. Siehe `docs/project/known_issues.md` → BUG-IMAP-01.
- 2026-02-19: v1.1 BUGFIX: Fehler-Antworten statt stiller Verwerfung bei fehlendem [Trip Name] und unbekanntem Trip. Filterlogik-Tabelle aktualisiert. Bestaetigungen auch bei Processor-Fehlern (success=False) senden.
- 2026-02-17: v1.0 Initial spec — Email-Channel mit Reply-Bestaetigung, SMS vorbereitet

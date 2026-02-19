---
entity_id: inbound_command_channels
type: module
created: 2026-02-17
updated: 2026-02-19
status: draft
version: "1.1"
tags: [f6, inbound, email, sms, imap, polling, channel]
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
| `src/services/trip_command_processor.py` | module | Verarbeitet geparste Befehle, gibt CommandResult zurueck |
| `src/app/config.py` | module | Settings: SMTP_USER, SMTP_PASS, MAIL_TO |
| `src/app/loader.py` | module | load_all_trips() fuer Trip-Name → Trip-ID Lookup |
| `src/outputs/email.py` | module | EmailOutput fuer Bestaetigungs-Email (Reply) |
| `src/web/scheduler.py` | module | APScheduler-Registrierung des Poll-Jobs |
| `imaplib` (stdlib) | module | IMAP4_SSL Client |
| `email` (stdlib) | module | email.message_from_bytes(), Header-Parsing |
| `re` (stdlib) | module | Subject-Regex fuer Trip-Name-Extraktion |

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
    if not self._authorize(from_addr, settings):
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

### 5. Sender-Authentifizierung

```python
def _parse_sender(self, from_header: str) -> str:
    """Extrahiert Email-Adresse aus 'Name <addr>' Format."""
    _, addr = email.utils.parseaddr(from_header)
    return addr.lower()

def _authorize(self, sender: str, settings: Settings) -> bool:
    """Single-User: Sender muss mail_to oder smtp_user sein."""
    allowed = {settings.mail_to.lower()}
    if settings.smtp_user:
        allowed.add(settings.smtp_user.lower())
    authorized = sender in allowed
    if not authorized:
        logger.debug(f"Ignoring email from: {sender!r}")
    return authorized
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

## Configuration

| Parameter | Quelle | Beschreibung |
|-----------|--------|--------------|
| IMAP Host | Hardcoded `imap.gmail.com` | MVP: Gmail only |
| IMAP Port | Hardcoded `993` | SSL |
| IMAP User | `GZ_SMTP_USER` | Gleiche Credentials wie SMTP |
| IMAP Pass | `GZ_SMTP_PASS` | Gleiche Credentials wie SMTP |
| Inbound-Adresse | `GZ_INBOUND_ADDRESS` | Plus-Adresse fuer Befehle (z.B. `user+gregor@gmail.com`). Default: `GZ_SMTP_USER` |
| Sender-Whitelist | `GZ_MAIL_TO` | Single-User: eigene Adresse |
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
  - From: konfigurierte `GZ_MAIL_TO` Adresse
  - Body: `### ruhetag`

- **Output:**
  - Befehl wird an TripCommandProcessor delegiert
  - Bestaetigungs-Email an Absender gesendet (gleicher Kanal)
  - Email als SEEN markiert

- **Side effects:**
  - IMAP-Verbindung zu imap.gmail.com:993
  - Emails werden als SEEN markiert (nicht geloescht)
  - Bestaetigungs-Email via SMTP
  - Alle Trip-Modifikationen durch TripCommandProcessor

### Filterlogik

| Bedingung | Verhalten |
|-----------|-----------|
| Absender != mail_to | SEEN markieren, debug-log, **kein Reply** (Sicherheit: kein Adress-Leak) |
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

**Ausnahme:** Autorisierungsfehler (unbekannter Absender) bleiben stumm — Sicherheit
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

## Known Limitations

- Gmail-only IMAP (imap.gmail.com hardcoded)
- 5-Minuten-Verzoegerung (kein IMAP IDLE / Push)
- Single-User: Sender-Auth ueber mail_to
- SMS-Channel noch nicht implementiert (benoetigt F1)
- Kein Retry bei IMAP-Fehler (naechster Poll-Zyklus versucht erneut)
- App-Passwort erforderlich bei Gmail mit 2FA
- Bestaetigungen gehen immer an `GZ_MAIL_TO`, nicht an den konkreten Absender-Header. Bei Single-User-Setup (GZ_MAIL_TO == Absender) kein Problem.

## Error Handling

| Fehlertyp | Behandlung |
|-----------|-----------|
| `imaplib.IMAP4.error` | error-log, Poll abbrechen, 0 zurueck |
| `OSError` (Netzwerk) | error-log, Poll abbrechen, 0 zurueck |
| Exception bei einzelner Email | error-log, ueberspringen, weiter |
| `imap.logout()` fehlschlag | Exception schlucken (Cleanup) |
| `EmailOutput.send()` fehlschlag | error-log, Befehl trotzdem als verarbeitet zaehlen |

Kein Fehler darf den APScheduler-Thread zum Absturz bringen.

## Changelog

- 2026-02-19: v1.1 BUGFIX: Fehler-Antworten statt stiller Verwerfung bei fehlendem [Trip Name] und unbekanntem Trip. Filterlogik-Tabelle aktualisiert. Bestaetigungen auch bei Processor-Fehlern (success=False) senden.
- 2026-02-17: v1.0 Initial spec — Email-Channel mit Reply-Bestaetigung, SMS vorbereitet

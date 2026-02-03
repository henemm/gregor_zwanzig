# Context: Bugfix - Email Retry Mechanism

**Workflow:** Bugfix: Email Retry Mechanism
**Phase:** Analysis
**Date:** 2026-02-03

## Problem Statement

E-Mail-Versand schlägt bei temporären Netzwerk-Fehlern (DNS-Fehler, Connection Timeouts) komplett fehl. Ein einzelner Fehler führt zum sofortigen Abbruch ohne Wiederholungsversuche.

**Konkreter Incident:**
- 02.02.2026 07:00 - Morning Subscription fehlgeschlagen
- Fehler: `[email] Connection error: [Errno -5] No address associated with hostname`
- DNS-Problem war temporär (~5 Minuten), aber E-Mail wurde nie versendet

## Analysis

### Affected Files (with changes)

| File | Change Type | Description |
|------|-------------|-------------|
| `src/outputs/email.py` | MODIFY | Add retry decorator and apply to send() method |
| `tests/tdd/test_html_email.py` | MODIFY | Add retry scenario tests |

### Current Implementation

**src/outputs/email.py:117-125**
```python
try:
    with smtplib.SMTP(self._host, self._port) as server:
        server.starttls()
        server.login(self._user, self._password)
        server.sendmail(self._from, [self._to], msg.as_string())
except smtplib.SMTPException as e:
    raise OutputError("email", f"SMTP error: {e}")
except OSError as e:
    raise OutputError("email", f"Connection error: {e}")
```

**Problem:**
- Ein Fehler → sofortiger Abbruch
- Keine Unterscheidung zwischen temporären (DNS, Timeout) und permanenten Fehlern (Auth)
- Keine Retry-Logik

### Dependencies

**Direct:**
- `smtplib` - Standard Library SMTP client
- `time` - Für sleep() zwischen Retries (Standard Library)
- `logging` - Für Retry-Logging (bereits importiert in scheduler.py)

**Indirect:**
- `src/web/scheduler.py:_execute_subscription()` - Ruft EmailOutput.send() auf
- `src/outputs/base.py:OutputError` - Exception wird geworfen

**Call Chain:**
```
scheduler.py:run_morning_subscriptions()
  └─> _run_subscriptions_by_schedule()
       └─> _execute_subscription()
            └─> EmailOutput.send()  ← HIER findet der Fehler statt
```

### Technical Approach

**1. Retry-Decorator mit Exponential Backoff**

```python
import time
import logging

logger = logging.getLogger(__name__)

def retry_on_network_error(max_retries: int = 3, backoff_base: int = 5):
    """
    Decorator für automatische Wiederholungsversuche bei Netzwerk-Fehlern.

    Args:
        max_retries: Maximale Anzahl Versuche (Standard: 3)
        backoff_base: Basis für exponentielles Backoff in Sekunden (Standard: 5)

    Retry bei:
        - OSError (DNS, Connection, Timeout)

    Kein Retry bei:
        - SMTPException (Auth-Fehler, permanente Fehler)
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except OSError as e:
                    if attempt < max_retries - 1:
                        wait = backoff_base * (2 ** attempt)
                        logger.warning(
                            f"Email send failed (attempt {attempt + 1}/{max_retries}): {e}. "
                            f"Retrying in {wait}s..."
                        )
                        time.sleep(wait)
                    else:
                        logger.error(f"Email send failed after {max_retries} attempts: {e}")
                        raise
                except smtplib.SMTPException:
                    # Auth-Fehler = permanent, kein Retry
                    raise
        return wrapper
    return decorator
```

**2. Anwenden auf send() Methode**

```python
@retry_on_network_error(max_retries=3, backoff_base=5)
def send(self, subject: str, body: str, html: bool = True, plain_text_body: str | None = None) -> None:
    # Bestehende Implementierung bleibt unverändert
    ...
```

**3. Logging erweitern**

- Retry-Versuche loggen (WARNING-Level)
- Erfolg nach Retry loggen (INFO-Level)
- Finale Fehler loggen (ERROR-Level)

### Scope Assessment

- **Files to modify:** 2
  - `src/outputs/email.py` - Retry-Decorator + Anwendung
  - `tests/tdd/test_html_email.py` - Neue Test-Klasse für Retry-Szenarien

- **Estimated LoC:** +80/-0
  - Retry-Decorator: ~30 LoC
  - Tests: ~50 LoC

- **Risk Level:** LOW
  - Änderung isoliert in EmailOutput-Klasse
  - Kein Breaking Change (Interface bleibt gleich)
  - Nur bei Netzwerk-Fehlern aktiv
  - Auth-Fehler bleiben sofort erkennbar
  - Keine Änderungen in scheduler.py notwendig

### Error Classification

**Temporäre Fehler (Retry):**
- `OSError` mit `-5` (EAI_NODATA) - DNS resolution failed
- `OSError` mit `-2` (EAI_NONAME) - Name resolution failed
- `OSError` mit `ETIMEDOUT` - Connection timeout
- `OSError` mit `ECONNREFUSED` - Connection refused (Server restart)

**Permanente Fehler (Kein Retry):**
- `smtplib.SMTPAuthenticationError` - Falsches Passwort
- `smtplib.SMTPServerDisconnected` - Auth-Fehler
- `smtplib.SMTPException` - Andere SMTP-Fehler

### Retry Strategy

**Exponential Backoff:**
- Versuch 1: Sofort
- Versuch 2: Nach 5s
- Versuch 3: Nach 15s (5 * 2^1)
- Versuch 4: Nach 30s (5 * 2^2)

**Total:** Max 50s für alle Retries (5 + 15 + 30)

**Rationale:**
- DNS-Probleme lösen sich meist in 10-30 Sekunden
- Zu kurze Wartezeiten (1-2s) helfen nicht bei DNS-Caching
- Zu lange Wartezeiten (>60s) blockieren Scheduler zu lange

### Test Strategy

**Neue Test-Klasse:** `TestEmailRetryMechanism`

**Test-Szenarien:**
1. **Temporary DNS Error** - 2 Fehlversuche, dann Erfolg
2. **Permanent Auth Error** - Sofortiger Abbruch, keine Retries
3. **Connection Timeout** - 3 Retries mit exponential backoff
4. **Max Retries Exceeded** - Nach 3 Versuchen OutputError
5. **Success on First Try** - Kein Retry, keine Verzögerung

**Mock-Strategie:**
- Mock `smtplib.SMTP` mit kontrolliertem Fehlerverhalten
- Mock `time.sleep` um Tests zu beschleunigen
- Verify Logging-Aufrufe

### Open Questions

- [x] Soll max_retries konfigurierbar sein? → Nein, hardcoded 3 ist ausreichend
- [x] Logging-Level für Retries? → WARNING (nicht ERROR, da Retry läuft)
- [x] Soll backoff_base konfigurierbar sein? → Nein, hardcoded 5s ist ausreichend
- [x] Sollen alle OSErrors Retry auslösen? → Ja, alle OSErrors sind potentiell temporär

### Implementation Order

1. **TDD RED Phase:**
   - Test für temporären DNS-Fehler mit Retry
   - Test für permanenten Auth-Fehler ohne Retry
   - Test für exponential backoff timing

2. **Implementation Phase:**
   - Retry-Decorator implementieren
   - Auf send() anwenden
   - Logging hinzufügen

3. **Validation Phase:**
   - Unit-Tests laufen durch
   - Manueller Test mit simuliertem DNS-Fehler
   - Verify Logging-Output

### Related Documentation

- Bug Report: `docs/specs/bugfix/email_retry_mechanism.md`
- Monitoring Log: `/opt/gregor_zwanziger/subscription_monitor.log`
- Scheduler Spec: `docs/specs/modules/scheduler.md`

### Rollback Strategy

Falls Probleme auftreten:
1. Decorator entfernen (@retry_on_network_error)
2. send() Methode bleibt unverändert (nur Decorator weg)
3. Keine Breaking Changes

### Performance Impact

**Negligible:**
- Normal case: Keine Verzögerung (Decorator overhead ~µs)
- Error case: Wartezeiten sind intentional (Netzwerk-Problem beheben)
- Worst case: +50s für 3 Retries (akzeptabel für Background-Job)

### Security Considerations

**None:**
- Keine neuen Security-Risiken
- SMTP-Credentials bleiben gleich behandelt
- Retry offenbart keine zusätzlichen Informationen

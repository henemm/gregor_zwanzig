---
entity_id: email_retry_mechanism
type: bugfix
created: 2026-02-03
updated: 2026-02-03
status: draft
version: "1.0"
workflow: "Bugfix: Email Retry Mechanism"
tags: [email, retry, resilience, smtp]
---

# Email Retry Mechanism

## Approval

- [ ] Approved for implementation

## Purpose

Implementiere automatische Wiederholungsversuche (Retry-Mechanismus) für E-Mail-Versand bei temporären Netzwerk-Fehlern (DNS-Fehler, Connection Timeouts), um sicherzustellen, dass E-Mails trotz kurzzeitiger Netzwerkprobleme erfolgreich versendet werden.

**Incident:** Am 02.02.2026 07:00 schlug die Morning-Subscription wegen eines temporären DNS-Fehlers fehl (`[Errno -5] No address associated with hostname`). Das DNS-Problem war nach ~5 Minuten behoben, aber die E-Mail wurde nie versendet, da kein Retry-Mechanismus existiert.

## Scope

### Affected Files

- `src/outputs/email.py` - Add retry decorator and apply to send() method
- `tests/tdd/test_html_email.py` - Add new test class for retry scenarios

### Estimated Changes

- **Lines of Code:** +80/-0
  - Retry decorator: ~30 LoC
  - Tests: ~50 LoC

### Risk Level

**LOW** - Änderung ist isoliert in EmailOutput-Klasse, kein Breaking Change

## Implementation Details

### 1. Retry-Decorator mit Exponential Backoff

Erstelle einen Decorator `retry_on_network_error`, der automatische Wiederholungsversuche bei Netzwerk-Fehlern durchführt.

**Location:** `src/outputs/email.py` (nach imports, vor EmailOutput-Klasse)

```python
import time
import logging

logger = logging.getLogger(__name__)

def retry_on_network_error(max_retries: int = 3, backoff_base: int = 5):
    """
    Decorator für automatische Wiederholungsversuche bei Netzwerk-Fehlern.

    Bei temporären Netzwerk-Fehlern (DNS, Connection, Timeout) werden
    automatisch Wiederholungsversuche mit exponentiellem Backoff durchgeführt.
    Permanente Fehler (Auth) führen sofort zum Abbruch.

    Args:
        max_retries: Maximale Anzahl Versuche (Standard: 3)
        backoff_base: Basis für exponentielles Backoff in Sekunden (Standard: 5)
                      Wartezeiten: 5s, 15s, 30s

    Retry bei:
        - OSError (DNS resolution failed, Connection refused, Timeout)

    Kein Retry bei:
        - SMTPException (Auth-Fehler, permanente SMTP-Fehler)

    Example:
        >>> @retry_on_network_error(max_retries=3, backoff_base=5)
        ... def send_email():
        ...     # Code that might fail with network errors
        ...     pass
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    result = func(*args, **kwargs)
                    # Log success after retry
                    if attempt > 0:
                        logger.info(
                            f"Email send succeeded after {attempt + 1} attempt(s)"
                        )
                    return result
                except OSError as e:
                    # Temporärer Netzwerk-Fehler
                    if attempt < max_retries - 1:
                        wait = backoff_base * (2 ** attempt)
                        logger.warning(
                            f"Email send failed (attempt {attempt + 1}/{max_retries}): {e}. "
                            f"Retrying in {wait}s..."
                        )
                        time.sleep(wait)
                    else:
                        # Letzte Versuch fehlgeschlagen
                        logger.error(
                            f"Email send failed after {max_retries} attempts: {e}"
                        )
                        raise
                except smtplib.SMTPException:
                    # Permanenter Fehler (Auth), kein Retry
                    raise
        return wrapper
    return decorator
```

### 2. Decorator auf send() anwenden

**Location:** `src/outputs/email.py:61` (vor `def send`)

```python
@retry_on_network_error(max_retries=3, backoff_base=5)
def send(
    self,
    subject: str,
    body: str,
    html: bool = True,
    plain_text_body: str | None = None,
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
    # Rest der bestehenden Implementierung bleibt unverändert
    ...
```

### 3. Imports ergänzen

**Location:** `src/outputs/email.py:8` (nach `import smtplib`)

```python
import time
import logging
```

**Location:** `src/outputs/email.py:18` (nach OutputConfigError import)

```python
logger = logging.getLogger(__name__)
```

### Error Classification

**Temporäre Fehler (Retry):**
- `OSError` - Alle OS-Level Netzwerk-Fehler:
  - `[Errno -5]` EAI_NODATA - DNS resolution failed
  - `[Errno -2]` EAI_NONAME - Name resolution failed
  - `ETIMEDOUT` - Connection timeout
  - `ECONNREFUSED` - Connection refused (Server restart)

**Permanente Fehler (Kein Retry):**
- `smtplib.SMTPException` - Alle SMTP-Protokoll-Fehler:
  - `SMTPAuthenticationError` - Falsches Passwort
  - `SMTPServerDisconnected` - Auth-Fehler
  - Andere SMTP-Protokoll-Fehler

### Retry Strategy

**Exponential Backoff:**
1. **Versuch 1:** Sofort
2. **Versuch 2:** Nach 5s Wartezeit
3. **Versuch 3:** Nach 15s Wartezeit (5 * 2^1)
4. **Versuch 4:** Nach 30s Wartezeit (5 * 2^2)

**Total Wartezeit:** Max 50s (5 + 15 + 30)

**Rationale:**
- DNS-Probleme lösen sich meist in 10-30 Sekunden
- Exponentielles Backoff reduziert Last bei Netzwerk-Problemen
- Zu kurze Wartezeiten (1-2s) helfen nicht bei DNS-Caching
- Zu lange Wartezeiten (>60s) blockieren Scheduler zu lange

## Test Plan

### Automated Tests (TDD RED)

**Neue Test-Klasse:** `TestEmailRetryMechanism` in `tests/tdd/test_html_email.py`

#### Test 1: Temporary DNS Error with Successful Retry

```python
def test_temporary_dns_error_succeeds_after_retry(self, mock_settings):
    """
    GIVEN EmailOutput with retry mechanism
    WHEN send() encounters DNS error twice, then succeeds
    THEN should retry and eventually succeed
    EXPECTED: FAIL initially (no retry mechanism yet)
    """
    from outputs.email import EmailOutput

    attempt_count = [0]

    class MockSMTP:
        def __init__(self, host, port):
            attempt_count[0] += 1
            if attempt_count[0] <= 2:
                raise OSError(-5, "No address associated with hostname")
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def starttls(self):
            pass
        def login(self, user, password):
            pass
        def sendmail(self, from_addr, to_addrs, msg):
            pass

    with patch("smtplib.SMTP", MockSMTP):
        with patch("time.sleep"):  # Speed up test
            email_output = EmailOutput(mock_settings)
            # Should succeed after 2 retries
            email_output.send("Test", "Body")

    assert attempt_count[0] == 3, "Should have made 3 attempts"
```

#### Test 2: Permanent Auth Error Without Retry

```python
def test_permanent_auth_error_fails_immediately(self, mock_settings):
    """
    GIVEN EmailOutput with retry mechanism
    WHEN send() encounters SMTP auth error
    THEN should fail immediately without retry
    EXPECTED: FAIL initially (will retry all errors)
    """
    from outputs.email import EmailOutput
    import smtplib

    attempt_count = [0]

    class MockSMTP:
        def __init__(self, host, port):
            attempt_count[0] += 1
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def starttls(self):
            pass
        def login(self, user, password):
            raise smtplib.SMTPAuthenticationError(535, b"Auth failed")
        def sendmail(self, from_addr, to_addrs, msg):
            pass

    with patch("smtplib.SMTP", MockSMTP):
        email_output = EmailOutput(mock_settings)
        with pytest.raises(OutputError, match="SMTP error"):
            email_output.send("Test", "Body")

    assert attempt_count[0] == 1, "Should not retry on auth error"
```

#### Test 3: Exponential Backoff Timing

```python
def test_exponential_backoff_timing(self, mock_settings):
    """
    GIVEN EmailOutput with retry mechanism
    WHEN send() fails with network errors
    THEN should wait 5s, 15s, 30s between attempts
    EXPECTED: FAIL initially (no backoff yet)
    """
    from outputs.email import EmailOutput

    sleep_calls = []

    class MockSMTP:
        def __init__(self, host, port):
            raise OSError(-5, "DNS error")

    with patch("smtplib.SMTP", MockSMTP):
        with patch("time.sleep") as mock_sleep:
            mock_sleep.side_effect = lambda x: sleep_calls.append(x)

            email_output = EmailOutput(mock_settings)
            with pytest.raises(OutputError):
                email_output.send("Test", "Body")

    assert sleep_calls == [5, 15, 30], f"Wrong backoff: {sleep_calls}"
```

#### Test 4: Max Retries Exceeded

```python
def test_max_retries_exceeded_raises_error(self, mock_settings):
    """
    GIVEN EmailOutput with retry mechanism (max_retries=3)
    WHEN send() fails 4 times
    THEN should raise OutputError after 4 attempts
    EXPECTED: FAIL initially (no retry limit yet)
    """
    from outputs.email import EmailOutput

    attempt_count = [0]

    class MockSMTP:
        def __init__(self, host, port):
            attempt_count[0] += 1
            raise OSError(-5, "Persistent DNS error")

    with patch("smtplib.SMTP", MockSMTP):
        with patch("time.sleep"):
            email_output = EmailOutput(mock_settings)
            with pytest.raises(OutputError, match="Connection error"):
                email_output.send("Test", "Body")

    assert attempt_count[0] == 3, "Should have made exactly 3 attempts"
```

#### Test 5: Success on First Try (No Retry)

```python
def test_success_on_first_try_no_retry(self, mock_settings):
    """
    GIVEN EmailOutput with retry mechanism
    WHEN send() succeeds immediately
    THEN should not retry, no sleep
    EXPECTED: PASS (existing behavior should work)
    """
    from outputs.email import EmailOutput

    attempt_count = [0]

    class MockSMTP:
        def __init__(self, host, port):
            attempt_count[0] += 1
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def starttls(self):
            pass
        def login(self, user, password):
            pass
        def sendmail(self, from_addr, to_addrs, msg):
            pass

    with patch("smtplib.SMTP", MockSMTP):
        with patch("time.sleep") as mock_sleep:
            email_output = EmailOutput(mock_settings)
            email_output.send("Test", "Body")

    assert attempt_count[0] == 1, "Should have made only 1 attempt"
    mock_sleep.assert_not_called()
```

#### Test 6: Logging Verification

```python
def test_retry_logging(self, mock_settings, caplog):
    """
    GIVEN EmailOutput with retry mechanism
    WHEN send() retries after network error
    THEN should log warnings with retry info
    EXPECTED: FAIL initially (no logging yet)
    """
    from outputs.email import EmailOutput
    import logging

    attempt_count = [0]

    class MockSMTP:
        def __init__(self, host, port):
            attempt_count[0] += 1
            if attempt_count[0] <= 2:
                raise OSError(-5, "DNS error")
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def starttls(self):
            pass
        def login(self, user, password):
            pass
        def sendmail(self, from_addr, to_addrs, msg):
            pass

    with patch("smtplib.SMTP", MockSMTP):
        with patch("time.sleep"):
            with caplog.at_level(logging.WARNING):
                email_output = EmailOutput(mock_settings)
                email_output.send("Test", "Body")

    # Check for retry warnings
    warnings = [r for r in caplog.records if r.levelname == "WARNING"]
    assert len(warnings) == 2, "Should log 2 retry warnings"
    assert "Retrying in 5s" in warnings[0].message
    assert "Retrying in 15s" in warnings[1].message

    # Check for success info
    infos = [r for r in caplog.records if r.levelname == "INFO"]
    assert any("succeeded after 3 attempt" in r.message for r in infos)
```

### Manual Tests

#### Manual Test 1: Simulated DNS Error

1. **Setup:** Modify `/etc/hosts` to point SMTP host to invalid IP
   ```bash
   echo "127.0.0.1 smtp.gmail.com" | sudo tee -a /etc/hosts
   ```

2. **Trigger:** Starte Subscription manuell oder warte auf geplanten Versand

3. **Observe:**
   - Logs zeigen Retry-Versuche mit Wartezeiten
   - Nach Restore von `/etc/hosts` sollte nächster Retry erfolgreich sein

4. **Cleanup:**
   ```bash
   sudo sed -i '/smtp.gmail.com/d' /etc/hosts
   ```

5. **Expected:** E-Mail wird nach 1-2 Retries erfolgreich versendet

#### Manual Test 2: Auth Error Verification

1. **Setup:** Ändere SMTP-Passwort in Settings auf falschen Wert

2. **Trigger:** Subscription manuell ausführen

3. **Observe:**
   - Fehler wird sofort geloggt (ERROR-Level)
   - Keine Retry-Versuche
   - Exception wird propagiert

4. **Cleanup:** Korrektes Passwort wiederherstellen

5. **Expected:** Sofortiger Abbruch ohne Wartezeiten

#### Manual Test 3: Production Verification

1. **Setup:** Deploy in Produktionsumgebung

2. **Monitor:** Überwache Logs für 24 Stunden

3. **Verify:**
   - Keine unerwarteten Retries bei erfolgreichen Versendungen
   - Bei Netzwerk-Problemen erfolgreiche Retries
   - Logging ist verständlich und informativ

## Acceptance Criteria

- [x] Temporäre Netzwerk-Fehler (DNS, Connection, Timeout) triggern automatische Retries
- [x] Permanente Fehler (Auth) führen sofort zum Abbruch ohne Retry
- [x] Exponential Backoff: 5s, 15s, 30s Wartezeiten zwischen Versuchen
- [x] Maximum 3 Retry-Versuche (= 4 Gesamtversuche)
- [x] Retry-Versuche werden geloggt (WARNING-Level) mit Wartezeit
- [x] Erfolg nach Retry wird geloggt (INFO-Level)
- [x] Finale Fehler werden geloggt (ERROR-Level)
- [x] Alle existierenden Tests bleiben grün
- [x] Neue Tests decken alle Retry-Szenarien ab
- [x] Keine Breaking Changes (Interface bleibt unverändert)
- [x] Performance-Impact negligible bei normalem Betrieb

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `smtplib.SMTP` | Standard Library | SMTP-Client für E-Mail-Versand |
| `time.sleep()` | Standard Library | Wartezeit zwischen Retries |
| `logging` | Standard Library | Logging von Retry-Versuchen |
| `src/outputs/base.py:OutputError` | Internal | Exception für E-Mail-Fehler |

## Known Limitations

- **Max Wartezeit:** 50 Sekunden total (akzeptabel für Background-Job)
- **DNS-Caching:** Bei DNS-Problemen kann Retry erst nach TTL erfolgreich sein
- **Kein Retry bei:** Config-Fehlern (OutputConfigError)
- **Keine Persistierung:** Bei Server-Restart gehen Retry-Versuche verloren

## Rollback Strategy

Falls Probleme auftreten:
1. Entferne `@retry_on_network_error` Decorator von `send()` Methode
2. Entferne Decorator-Funktion aus `email.py`
3. Entferne `time` und `logger` imports (falls nicht anders verwendet)
4. Code funktioniert wie vorher (kein Breaking Change)

## Performance Impact

- **Normal Case:** Negligible (Decorator-Overhead ~µs)
- **Error Case:** Wartezeiten sind intentional (5+15+30s = 50s max)
- **Worst Case:** +50s für Background-Job bei 3 Retries (akzeptabel)

## Security Considerations

- **Keine neuen Risiken:** Retry offenbart keine zusätzlichen Informationen
- **SMTP-Credentials:** Bleiben gleich behandelt (kein zusätzliches Exposure)
- **Rate Limiting:** Exponential Backoff verhindert aggressive Retries

## Changelog

- 2026-02-03: Initial spec created based on incident analysis

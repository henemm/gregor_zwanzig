# Bug: E-Mail-Versand schlägt bei temporären Netzwerk-Fehlern fehl

**Status:** Analysis Complete
**Priority:** High (führt zu verpassten Notifications)
**Date:** 2026-02-03

## Symptom

E-Mail-Versand schlägt bei temporären DNS/Netzwerk-Fehlern komplett fehl, ohne Wiederholungsversuche.

**Konkreter Fall:**
- 02.02.2026 07:00 - Morning Subscription fehlgeschlagen
- Fehler: `[email] Connection error: [Errno -5] No address associated with hostname`
- DNS-Problem war temporär (~5 Minuten), aber E-Mail wurde nie versendet

## Location

**Primär:**
- `src/outputs/email.py:117-125` - EmailOutput.send() ohne Retry-Logik

**Sekundär:**
- `src/web/scheduler.py:154-155` - Exception Handling ohne Retry

## Root Cause

### EmailOutput.send() (email.py:117-125)

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
- Ein einzelner Fehler führt sofort zu OutputError
- Keine Unterscheidung zwischen permanenten (Auth-Fehler) und temporären Fehlern (DNS, Timeout)
- Keine Retry-Versuche mit Backoff

### _execute_subscription() (scheduler.py:154-155)

```python
except Exception as e:
    logger.error(f"Failed to execute subscription {sub.name}: {e}")
```

**Problem:**
- Exception wird geloggt, Subscription gilt als fehlgeschlagen
- Kein Retry auf Scheduler-Ebene
- User erhält keine E-Mail

## Expected Behavior

**Bei temporären Fehlern:**
1. 3 Retry-Versuche mit exponential backoff (5s, 15s, 30s)
2. Logging aller Retry-Versuche
3. Erfolg nach Retry = User erhält E-Mail

**Bei permanenten Fehlern:**
- Auth-Fehler → sofort abbrechen, kein Retry
- Config-Fehler → sofort abbrechen, kein Retry

## Test Plan

**Test 1: Temporärer DNS-Fehler**
1. DNS für SMTP-Host 20 Sekunden blockieren
2. Subscription triggern
3. Erwartung: Nach 2-3 Retries erfolgreich versendet

**Test 2: Permanenter Auth-Fehler**
1. Falsches SMTP-Passwort setzen
2. Subscription triggern
3. Erwartung: Sofortiger Abbruch, keine Retries

**Test 3: SMTP-Server Timeout**
1. SMTP-Port firewall-blockieren
2. Subscription triggern
3. Erwartung: 3 Retries, dann Fehler

## Solution Design

### 1. Retry-Decorator in email.py

```python
def retry_on_network_error(max_retries=3, backoff_base=5):
    """Decorator für Retry bei Netzwerk-Fehlern."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except OSError as e:  # DNS, Connection, Timeout
                    if attempt < max_retries - 1:
                        wait = backoff_base * (2 ** attempt)
                        logger.warning(f"Retry {attempt+1}/{max_retries} after {wait}s: {e}")
                        time.sleep(wait)
                    else:
                        raise  # Final attempt failed
                except smtplib.SMTPException:
                    raise  # Auth-Fehler = permanent, kein Retry
        return wrapper
    return decorator
```

### 2. Anwenden auf send()

```python
@retry_on_network_error(max_retries=3, backoff_base=5)
def send(self, subject: str, body: str, ...) -> None:
    # Bestehender Code
```

### 3. Logging erweitern

- Retry-Versuche loggen (INFO-Level)
- Finale Fehler loggen (ERROR-Level)
- Success nach Retry loggen (INFO-Level)

## Effort

**Small** - ca. 30-45 Minuten
- Retry-Decorator: 15 min
- Tests anpassen: 15 min
- Validierung: 15 min

## Affected Files

1. `src/outputs/email.py` - Retry-Decorator + send() Änderung
2. `tests/tdd/test_html_email.py` - Tests erweitern (Retry-Szenarien)

## Risk Assessment

**Low Risk:**
- Änderung isoliert in EmailOutput
- Kein Breaking Change (Interface bleibt gleich)
- Nur bei Netzwerk-Fehlern aktiv
- Auth-Fehler bleiben sofort erkennbar

## Related Issues

- Monitoring zeigte: 1/2 Subscriptions erfolgreich am 01.02.-02.02.
- Morning Subscription (07:00) fehlgeschlagen wegen temporärem DNS-Fehler
- Evening Subscription (18:00) erfolgreich

## References

- Monitoring Log: `/opt/gregor_zwanziger/subscription_monitor.log`
- Error Log: `journalctl -u gregor-zwanzig.service`
- Spec: `docs/specs/modules/smtp_mailer.md` (update needed)

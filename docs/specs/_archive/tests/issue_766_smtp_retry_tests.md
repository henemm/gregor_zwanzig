---
entity_id: issue_766_smtp_retry_tests
type: tests
created: 2026-06-20
updated: 2026-06-20
status: draft
version: "1.0"
tags: [tests, smtp, retry, rate-limit, issue-766]
parent: issue_766_smtp_retry
phase: phase5_tdd_red
---

# Issue #766 — SMTP 452 Retry / Sammelversand (Tests)

## Approval

- [x] Approved

## Purpose

Test-Manifest für den Fast-Track-Fix #766: temporäre 4xx-SMTP-Fehler (452
rate-limit, 421 service unavailable) werden retried, permanente 5xx und
Auth-Fehler brechen sofort ab. Jeder pytest-Test belegt einen Zweig der
Fehlerklassifikation in `EmailOutput.send()`.

Parent-Bug: Issue #766.

## Source

- **File:** `tests/tdd/test_issue_766_smtp_retry.py` (NEU)

## Test Inventory

### Python (`tests/tdd/test_issue_766_smtp_retry.py`)

| Test-Funktion | Was geprüft wird |
|---|---|
| `test_452_rate_limit_is_retried` | 452 (rate limit, SMTPSenderRefused) wird retried; 3 Fehlversuche + 1 Erfolg → 4 sendmail-Calls, 3 sleeps. |
| `test_452_exhausts_retries_then_raises` | 452 dauerhaft → nach 4 Versuchen OutputError, 3 sleeps. |
| `test_535_auth_error_is_not_retried` | 535 (SMTPAuthenticationError) bricht ohne Retry ab, 0 sleeps. |
| `test_550_response_exception_is_not_retried` | 5xx SMTPResponseException (550 via SMTPDataError) bricht ohne Retry ab, 0 sleeps. |
| `test_recipients_refused_is_not_retried` | SMTPRecipientsRefused (keine SMTPResponseException) → allgemeiner Catch, 0 sleeps. |
| `test_421_service_unavailable_is_retried` | 421 (service not available) ist temporär → 1 Retry, 1 sleep, dann Erfolg. |

## Implementation Details

Die Tests simulieren ausschließlich SMTP-Antwort-Codes (Netzwerk-Antworten),
keine Geschäftslogik — die SMTP-Verbindung selbst wird nicht aufgebaut. Damit
prüfen sie den Fehlerbehandlungs-Code-Pfad, nicht das SMTP-Protokoll. Markiert
als `doc-compliance-test` im Datei-Header.

Reihenfolge der `except`-Zweige in `EmailOutput.send()` (kritisch, da
Unterklassen):
1. `SMTPAuthenticationError` → kein Retry
2. `SMTPResponseException` → `smtp_code >= 500` permanent, sonst Retry
3. `SMTPException` → kein Retry (inkl. SMTPRecipientsRefused)

## Expected Behavior

- **Input:** SMTP-Exception-Objekte mit definierten Codes als sendmail/login
  side-effects.
- **Output:** Assertions über `sendmail.call_count`, `sleep.call_count` und
  OutputError-Raising.
- **Side effects:** keine echten Netzwerk-Calls.

## Acceptance Criteria

- **AC-T1:** Given die Test-Datei existiert /
  When `pytest tests/tdd/test_issue_766_smtp_retry.py -v` nach dem Fix läuft /
  Then sind alle 6 Tests grün.

- **AC-T2:** Given 452/421 (4xx) treten auf /
  When `EmailOutput.send()` sie behandelt /
  Then wird mit Backoff retried statt sofort abzubrechen.

- **AC-T3:** Given 535/5xx/SMTPRecipientsRefused treten auf /
  When `EmailOutput.send()` sie behandelt /
  Then wird sofort OutputError geworfen ohne Retry.

## Changelog

- 2026-06-20: Initial — Test-Manifest für Issue #766 (SMTP 452 Retry).

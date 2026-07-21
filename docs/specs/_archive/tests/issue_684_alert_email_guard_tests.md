---
entity_id: issue_684_alert_email_guard_tests
type: tests
created: 2026-06-09
updated: 2026-06-09
status: approved
version: "1.0"
tags: [alert, deliverability, email-guard, multi-channel]
---

# TDD-RED-Tests: Issue #684 symmetrischer `can_send_email()`-Guard

## Approval

- [x] Approved

## Purpose

Mock-freie Verhaltenstests für den False-Positive-Fix im Alert-Versand:
Throttle + Alert-Log dürfen nur bei mindestens einem tatsächlich
zustellbaren (konfigurierten) effektiven Kanal geschrieben werden. Der
E-Mail-Pfad erhält denselben `can_send_email()`-Guard wie Telegram/Radar.
Beobachtung über echte Settings, echte Datei-Zustände, echte Socket-Sinks
(SMTP-Disconnect, Telegram-HTTP-Stub) und realen SMTP-Versand.

## Source

- **File:** `tests/tdd/test_issue_684_alert_email_guard.py`
- **Implementation under test:** `src/services/trip_alert.py`
  (`TripAlertService._send_alert`, `TripAlertService.check_and_send_alerts`)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| TripAlertService | module | Alert-Detektion + kanalbewusster Versand + Recording |
| Settings.can_send_email/telegram | function | Deliverability-Check pro Kanal |
| EmailOutput | module | Realer SMTP-Versand bzw. Disconnect-Fehlerpfad |
| TelegramOutput | module | Realer HTTP-Versand gegen lokalen Stub |

## Test Cases

| # | Test | Erwartetes Verhalten |
|---|------|---------------------|
| 1 | `test_ac1_email_only_unconfigured_smtp_no_false_positive` | email-only effektiver Kanal + SMTP nicht konfiguriert (Telegram schon): `check_and_send_alerts` gibt False zurück, KEIN Alert-Log-Eintrag, KEINE Throttle-Sperrzeit (RED vor Fix: gibt True zurück + schreibt Log/Throttle) |
| 2 | `test_ac2_email_configured_sends_and_records` | E-Mail-Kanal + konfiguriertes SMTP (`for_testing`): realer Versand, return True, Alert-Log + Throttle gesetzt (skip wenn SMTP nicht konfiguriert) |
| 3 | `test_ac3_configured_smtp_transient_failure_still_records` | SMTP konfiguriert aber Server bricht Verbindung ab (lokaler Accept-and-Close-Socket → echter SMTPServerDisconnected): Recording bleibt erhalten, return True, Log + Throttle gesetzt (kein #656-Anti-Pattern, Recording nicht an Send-Erfolg gekoppelt) |
| 4 | `test_ac4_telegram_only_unchanged` | telegram-only effektiver Kanal + konfiguriertes Telegram (echter HTTP-Roundtrip gegen lokalen Stub): return True, Log + Throttle gesetzt (Regressionsfreiheit Telegram-Pfad) |

## Expected Behavior

- **Input:** Synthetische Trips mit großen cached/fresh-Deltas (garantiert
  signifikante Changes), echte Settings mit gezielt gesetzten Kanal-Feldern.
- **Output:** RED vor Fix (AC-1: False-Positive True+Recording), GREEN nach Fix.
- **Side effects:** Schreibt Throttle/Snapshot/Alert-Log in das Test-User-
  Verzeichnis `data/users/issue684tdduser/` (Fixture räumt vor/nach auf).

## Known Limitations

- AC-2 verifiziert realen SMTP-Versand (return True + Recording); die
  inhaltliche IMAP-Verifikation bleibt der Staging-Acceptance
  (`email_spec_validator`) vorbehalten.
- AC-3/AC-4 nutzen lokale Socket-Sinks (echte Sockets, kein Mock), um
  Send-Fehler bzw. Erfolg deterministisch und ohne Außenwirkung zu erzeugen.

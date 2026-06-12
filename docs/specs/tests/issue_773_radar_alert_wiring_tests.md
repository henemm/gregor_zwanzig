---
entity_id: issue_773_radar_alert_wiring_tests
type: tests
created: 2026-06-12
updated: 2026-06-12
status: draft
version: 1.0
spec: docs/specs/modules/issue_773_radar_alert_wiring.md
---

# Test-Manifest: #773 Radar-Alert-Verdrahtung + echte Alert-E2E

Mock-frei. Reale HTTP-Calls (FastAPI TestClient), echte Wetter-API (OpenMeteo),
echter SMTP→IMAP-Roundtrip (Stalwart-Test-Postfach). Skip nur bei fehlender
Infrastruktur-Konfiguration (kein stiller Erfolg).

## AC-Test-Mapping

| AC | Test | Datei | Beweis |
|----|------|-------|--------|
| AC-1 | `TestRadarAlertJobRegistered` | `internal/scheduler/scheduler_radar_test.go` | `Status()` listet Job `radar_alert_checks` mit `last_run`-Feld |
| AC-2 | `test_ac2_radar_endpoint_mandantentrennung` | `tests/tdd/test_773_alert_e2e.py` | Endpoint 200 + zwei isolierte Nutzer, kein Cross-User |
| AC-3 | `test_ac3_change_alert_real_e2e_imap` | `tests/tdd/test_773_alert_e2e.py` | Extrem-Snapshot → reale Kette `check_all_trips` → Mail per IMAP nachgewiesen |
| AC-4 | `test_ac4_change_alert_throttled_second_run` | `tests/tdd/test_773_alert_e2e.py` | Zweiter Lauf im Throttle-Fenster sendet keine zweite Mail |
| AC-5 | `test_ac5_radar_endpoint_requires_user_id` | `tests/tdd/test_773_alert_e2e.py` | Aufruf ohne `user_id` → HTTP 422, kein `default`-Fallback |

## RED-Erwartung

- AC-1 (Go): RED — Job `radar_alert_checks` ist noch nicht registriert.
- AC-2/AC-5 (Python): RED — Endpoint `/api/scheduler/radar-alert-checks` existiert nicht (404 statt 200/422).
- AC-3/AC-4 (Python): E2E-Charakterisierung des bestehenden Änderungs-Alert-Pfads
  (`check_all_trips`). Beweisen, dass die reale Kette tatsächlich zustellt. Grün =
  Pfad funktioniert (bestätigt: Ursache liegt in Radar-Lücke + seltenem Delta);
  Rot = zweiter Bug im Änderungs-Pfad.

---
entity_id: issue_637_telegram_webhook_tests
type: tests
created: 2026-06-07
updated: 2026-06-07
status: draft
version: "1.0"
tags: [tests, telegram, webhook, inbound, multi-user, idempotency, issue-637]
parent: telegram_webhook_inbound
phase: phase5_tdd_red
---

# Issue #637 — Telegram Inbound Webhook-Migration (Tests)

## Approval

- [x] Approved

## Purpose

Test-Manifest für die Webhook-Migration aus
`docs/specs/modules/telegram_webhook_inbound.md`. Jeder Test mappt 1:1 auf ein
Acceptance Criterion. Kein Mock der Logik unter Test — echte HTTP-POSTs gegen die
reale FastAPI-App, echte Go-`httptest`-Server, echte temporäre Nutzer-Dateien.

Parent-Spec: `docs/specs/modules/telegram_webhook_inbound.md` v1.0

## Source

- **File (Python):** `tests/tdd/test_issue_637_telegram_webhook.py` (NEU)
- **File (Go-Handler):** `internal/handler/telegram_webhook_test.go` (NEU)
- **File (Go-Scheduler):** `internal/scheduler/telegram_poll_removed_test.go` (NEU)

## Test Inventory

### Python (`tests/tdd/test_issue_637_telegram_webhook.py`)

| Test-Funktion | AC | Was geprüft wird |
|---|---|---|
| `webhook_router_registered` | AC-2 | `POST /api/internal/telegram-webhook` ist in der FastAPI-App registriert. |
| `webhook_processes_status_command` | AC-2 | Echter HTTP-POST eines Update-JSON mit „status": der bestehende `TripCommandProcessor` wird mit `channel='telegram'` und `body` mit „status" aufgerufen, Antwort 200. |
| `webhook_multi_user_routing_no_cross_leak` | AC-3 | Zwei echte temporäre Nutzer (alice chat=111, bob chat=222); Update von alice lädt ausschließlich alice's Trips, niemals bob's; unbekannter chat_id → nur `default`. |
| `webhook_idempotent_duplicate_update` | AC-5 | Zweimal dasselbe Update (update_id=200): Befehl wird nur EINMAL verarbeitet, beide Antworten 200. |

### Go (`internal/handler/telegram_webhook_test.go`)

| Test-Funktion | AC | Was geprüft wird |
|---|---|---|
| `TestTelegramWebhookHandler_ValidSecretForwardsAndReturns200` | AC-1 | Korrekter Header `X-Telegram-Bot-Api-Secret-Token` → 200 + roher Body wird an `/api/internal/telegram-webhook` der Python-Core (httptest-Backend) weitergeleitet. |
| `TestTelegramWebhookHandler_WrongSecretReturns403NoForward` | AC-1 | Falscher/fehlender Header → 403, KEIN Forwarding an Python. |

### Go (`internal/scheduler/telegram_poll_removed_test.go`)

| Test-Funktion | AC | Was geprüft wird |
|---|---|---|
| `TestScheduler_NoInboundTelegramPollJob` | AC-4 | Der reale Scheduler (`New(cfg, store)`) registriert keinen Job mit id `inbound_telegram_poll` mehr (`Status()`-Prüfung). |

## Expected Behavior

- **Input:** Realistische Telegram-Update-JSONs; echte temporäre `user.json`-Dateien; reale Go-/Python-Server.
- **Output:** Assertions über HTTP-Status, weitergeleiteten Body, geladene user_id, Processor-Aufrufzahl, registrierte Job-IDs.
- **Side effects:** Schreibvorgänge ausschließlich in temporäre Nutzer-Verzeichnisse (in `finally` entfernt) bzw. `t.TempDir()`.

## Acceptance Criteria

- **AC-T1:** Given die Test-Dateien existieren und Implementierung fehlt /
  When die Tests laufen / Then schlagen alle fehl (RED erfolgreich):
  Python-Endpoint fehlt (404/Routenliste), Go-Handler kompiliert nicht,
  Scheduler-Job noch vorhanden.

- **AC-T2:** Given GREEN-Phase abgeschlossen /
  When alle Tests laufen / Then alle grün, keine Mocks der Logik unter Test.

## Known Limitations

- Boundary-Capture von `TelegramOutput.send` und (für AC-2/AC-5) `load_all_trips`
  ist kein Mock der Verarbeitung, sondern Beobachtung an der Netzwerk-/Daten-Grenze
  — Muster aus `tests/tdd/test_inbound_telegram_reader.py`.
- AC-3 nutzt das reale `data/users/`-Verzeichnis (namespaced `zz_test637_*`,
  Cleanup in `finally`), da `_resolve_user_for_chat` `data_dir="data"` auflöst.

## Changelog

- 2026-06-07: Initial — Test-Manifest für Issue #637 (Telegram Webhook-Migration).

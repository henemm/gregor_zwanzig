---
entity_id: telegram_webhook_inbound
type: module
created: 2026-06-07
updated: 2026-06-07
status: draft
version: "1.0"
tags: [telegram, webhook, inbound, security, scheduler]
---

# Telegram Inbound — Webhook-Migration (Issue #637)

## Approval

- [x] Approved (PO 'go', 2026-06-07)

## Purpose

Migriert den Telegram-Eingang vom 30-Sekunden-Polling (`getUpdates`) auf eine
push-basierte Webhook-Architektur. Telegram pusht eingehende Nachrichten an einen
öffentlichen Go-Endpoint, der sie nach Secret-Prüfung an die interne Python-Logik
weiterreicht. Ergebnis: Antwortzeit ~1 s statt bis zu 30 s, kein Dauer-Polling.

## Source

- **Go-Handler (öffentlich):** `internal/handler/telegram_webhook.go` (neu) — Route `POST /api/webhooks/telegram/{secret}`
- **Go-Route-Registrierung:** `cmd/server/main.go`
- **Go-Auth-Exemption:** `internal/middleware/auth.go`
- **Go-Scheduler-Cleanup:** `internal/scheduler/scheduler.go` (Job `inbound_telegram_poll` entfernen)
- **Python-Router (intern):** `api/routers/webhook.py` (neu) — Endpoint `POST /api/internal/telegram-webhook`
- **Python-Router-Registrierung:** `api/main.py`
- **Python-Verarbeitung (wiederverwendet):** `src/services/inbound_telegram_reader.py` → `InboundTelegramReader._process_update`
- **Setup-Utility:** `scripts/telegram_set_webhook.sh` (neu)
- **Infra (separates Repo `henemm-infra`, via MQ):** Nginx — IP-Allowlist + Rate-Limit auf `/api/webhooks/telegram/`

## Estimated Scope

- **LoC:** ~220 (Go ~90, Python ~80, Idempotenz/Setup ~50) — Code in `src/`/`internal/`/`cmd/`/`api/`. Doku/Scripts/Specs zählen nicht.
- **Files:** ~7 Code-Dateien + 1 Setup-Script + Runbook-Doku
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `InboundTelegramReader._process_update` | Python | Bestehende Befehlsverarbeitung (wiederverwendet, entkoppelt von Poll-Schleife) |
| `lookup_user_by_telegram_chat_id` | Python | Multi-User-Routing chat_id → user_id (unverändert) |
| `TripCommandProcessor` | Python | Befehls-Parsing + CommandResult |
| `config.PythonCoreURL` | Go | Interne Forwarding-Ziel-URL (Default `http://localhost:8000`) |
| Telegram Bot API `setWebhook` | extern | Webhook-Registrierung mit `secret_token` |

## Implementation Details

### 1. Sicherheit & Konfiguration

- Neuer ENV `TELEGRAM_WEBHOOK_SECRET` (Go-Prozess).
- **Secret-Validierung über HTTP-Header `X-Telegram-Bot-Api-Secret-Token`** (Tech-Lead-Abweichung von der Ticket-Vorgabe „Secret in URL" — verhindert Secret-Leak in Nginx-Access-Logs). `setWebhook` wird mit `secret_token=<TELEGRAM_WEBHOOK_SECRET>` registriert; Telegram sendet den Header bei jedem Request.
- Der URL-Pfad `{secret}` bleibt als Routing-Segment erhalten, ist aber **nicht** der Auth-Träger (Defense-in-Depth, nicht primärer Schutz).
- **Staging-Isolation:** Eigener Test-Bot-Token auf Staging (Webhook-Exklusivität: ein Bot = eine URL). ENV-getrennt `TELEGRAM_BOT_TOKEN` Prod vs. Staging.

### 2. Go Gateway (öffentlicher Eingang)

```
POST /api/webhooks/telegram/{secret}
  1. Header X-Telegram-Bot-Api-Secret-Token == TELEGRAM_WEBHOOK_SECRET? Nein → 403 (+ Zähler erhöhen)
  2. ENV nicht gesetzt → 503 (fail-closed, kein offener Endpoint ohne Secret)
  3. Body (rohes JSON) an PythonCoreURL + /api/internal/telegram-webhook POSTen
     - fire-and-forget / kurzes Timeout: Antwort an Telegram NICHT von Python-Dauer abhängig
  4. Sofort 200 OK an Telegram (verhindert Retry-Sturm), unabhängig vom Python-Ergebnis
  5. Pfad in middleware.AuthMiddleware exempten (öffentlich, unauthentifiziert)
```

- Abgewiesene Requests (403) werden gezählt (Prozess-Counter, via Log/Status sichtbar) → Monitoring-Alert-Grundlage.

### 3. Python Core (interne Logik)

```
POST /api/internal/telegram-webhook
  - Body = ein Telegram-Update (JSON)
  - Idempotenz: update_id gegen High-Watermark prüfen (persistent, vgl. bug-599-telegram-persistent-offset)
      - update_id <= zuletzt verarbeitete → verwerfen (Replay/Doppel-Delivery), 200 ok
      - sonst Watermark hochsetzen, verarbeiten
  - Verarbeitung via InboundTelegramReader._process_update(update, settings) (refactored: schleifen-unabhängig)
  - Multi-User-Routing über _resolve_user_for_chat → lookup_user_by_telegram_chat_id bleibt intakt
  - Antwort an Nutzer via bestehender TelegramOutput-Pfad
```

- `InboundTelegramReader` wird so refactored, dass `_process_update` ohne `poll_and_process`/`_offset`-Schleife aufrufbar ist. Die High-Watermark wird persistent gehalten (bestehende Persistenz-Mechanik aus #599 wiederverwenden), damit sie Prozess-Restarts überlebt.

### 4. Cleanup & Migration

- Scheduler-Job `inbound_telegram_poll` (`@every 30s`) aus `internal/scheduler/scheduler.go` entfernen; Job-Zähler-Log „5 jobs" anpassen.
- `poll_and_process`/`_get_updates` als deprecated markieren (nicht löschen — Notfall-Fallback), nicht mehr vom Scheduler getriggert.
- Setup-Script `scripts/telegram_set_webhook.sh`: registriert/aktualisiert Webhook (`setWebhook` mit `url` + `secret_token`), unterstützt `deleteWebhook` für Rollback, druckt `getWebhookInfo`.

### 5. Monitoring & Betrieb

- **Webhook-Healthcheck:** periodischer `getWebhookInfo`-Check (Prod) → wertet `last_error_message` + `pending_update_count` aus → BetterStack-Alert bei Fehler/Stau. (Liveness-Ersatz für den entfallenden `last_run` des Poll-Jobs.)
- **403-Alert:** abgewiesene Webhook-Requests sichtbar/alertbar (Anomalie-Erkennung Angriffsvektor).
- **Nginx (henemm-infra, via MQ):** IP-Allowlist auf Telegram-Ranges (`149.154.160.0/20`, `91.108.4.0/22` — zur Umsetzung gegen offizielle Telegram-Doku verifizieren) + `limit_req`-Rate-Limit auf dem Webhook-Pfad.
- **Runbook** (`docs/`): Webhook registrieren, Rollback (`deleteWebhook` + Poll-Job reaktivieren), Token-Rotation, Staging-Bot-Setup.

## Expected Behavior

- **Input:** HTTP POST von Telegram an `/api/webhooks/telegram/{secret}` mit Update-JSON + Secret-Header.
- **Output:** Sofort `200 OK` an Telegram; Nutzer erhält Befehlsantwort via Telegram (z.B. „status").
- **Side effects:** chat_id-scoped Trip-Daten gelesen/geändert (Befehl), Bestätigungsnachricht gesendet, High-Watermark fortgeschrieben.

## Acceptance Criteria

**AC-1:** Sichere Endpoint-Freigabe
Given der öffentliche Go-Endpoint `/api/webhooks/telegram/{secret}`, When ein POST mit korrektem Header `X-Telegram-Bot-Api-Secret-Token` eingeht, Then wird es mit `200 OK` akzeptiert; bei fehlendem/falschem Header antwortet der Endpoint `403 Forbidden` und verarbeitet nichts.
- Test: Echter HTTP-POST gegen die laufende Go-API mit (a) korrektem Header → 200 + Forwarding erfolgt, (b) falschem Header → 403 + kein Forwarding an Python.

**AC-2:** Nahtlose Befehls-Weiterleitung
Given ein gültiges Telegram-Webhook-Payload mit Befehl „status", When Go es an Python weiterleitet, Then parst der bestehende `TripCommandProcessor` den Befehl korrekt und es wird eine Antwort über den Telegram-Pfad ausgelöst (CommandResult mit erwartetem Subject/Body).
- Test: Echter POST eines realistischen Update-JSON an den internen Python-Endpoint; Assertion auf das erzeugte `CommandResult` (kein Mock, echte Verarbeitung).

**AC-3:** Multi-User-Integrität
Given eine eingehende Telegram-Nachricht von einer bekannten chat_id, When das System sie verarbeitet, Then wird die korrekte `user_id` aus der chat_id aufgelöst und die nutzer-spezifischen Trip-Daten geladen — kein Cross-User-Leak. Eine unbekannte chat_id fällt nicht auf fremde Nutzerdaten zurück.
- Test: Zwei verschiedene Nutzer mit je eigener chat_id; Update von chat_id A lädt ausschließlich Trips von Nutzer A; Update von unbekannter chat_id erhält keine fremden Daten.

**AC-4:** Polling-Deaktivierung
Given die migrierte Anwendung, When der Go-Scheduler läuft, Then existiert kein `inbound_telegram_poll`-Job mehr und es erfolgen keine periodischen `getUpdates`-Aufrufe.
- Test: Scheduler-Job-Liste enthält `inbound_telegram_poll` nicht; Scheduler-Status zeigt den Job nicht mehr.

**AC-5:** Idempotenz gegen Doppel-Zustellung
Given ein bereits verarbeitetes Update (update_id N), When dasselbe Update (oder eines mit update_id ≤ N) erneut zugestellt wird, Then wird es verworfen (keine zweite Befehlsausführung, keine doppelte Bestätigung), Antwort bleibt `200 OK`.
- Test: Zweimaliger POST desselben Update-JSON; Befehl wird nur **einmal** ausgeführt (z.B. „ruhetag 2" einmal angewendet, eine Bestätigung).

## Test Mapping (AC → Test)

| AC | Test-Funktion | Datei |
|----|---------------|-------|
| AC-1 | `TestTelegramWebhookHandler_ValidSecretForwardsAndReturns200`, `TestTelegramWebhookHandler_WrongSecretReturns403NoForward` | `internal/handler/telegram_webhook_test.go` |
| AC-2 | `webhook_router_registered`, `webhook_processes_status_command` | `tests/tdd/test_issue_637_telegram_webhook.py` |
| AC-3 | `webhook_multi_user_routing_no_cross_leak` | `tests/tdd/test_issue_637_telegram_webhook.py` |
| AC-4 | `TestScheduler_NoInboundTelegramPollJob` | `internal/scheduler/telegram_poll_removed_test.go` |
| AC-5 | `webhook_idempotent_duplicate_update` | `tests/tdd/test_issue_637_telegram_webhook.py` |

## Known Limitations

- Kein sanfter Parallelbetrieb Polling↔Webhook (Telegram: ein Bot = eine URL; `getUpdates` liefert `409` solange Webhook gesetzt). Umstellung ist Big-Bang; Rollback nur via `deleteWebhook` + Poll-Job-Reaktivierung (Runbook).
- IP-Allowlist hängt an Telegrams veröffentlichten Ranges; ändern sie sich, greift ersatzweise der Secret-Header (Defense-in-Depth).
- Webhook setzt öffentliche Erreichbarkeit + gültiges TLS voraus (Let's-Encrypt-Renewal). Bei Ausfall queued Telegram bis 24 h und retryt.

## Changelog

- 2026-06-07: Initial spec created (Issue #637)

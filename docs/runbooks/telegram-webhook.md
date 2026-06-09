# Runbook — Telegram Inbound Webhook (Issue #637)

Der Telegram-Eingang läuft **push-basiert** über einen Webhook statt 30-Sekunden-Polling.

## Architektur (Kurzfassung)

```
Telegram  --POST-->  Go (öffentlich)                         -->  Python Core (intern)
                     /api/webhooks/telegram/{secret}              /api/internal/telegram-webhook
                     Secret-Header-Check + sofort 200             Idempotenz + Befehlsverarbeitung
```

- **Auth-Träger** ist der HTTP-Header `X-Telegram-Bot-Api-Secret-Token`
  (== ENV `TELEGRAM_WEBHOOK_SECRET` des Go-Prozesses). Der `{secret}`-Pfad ist nur
  Defense-in-Depth-Routing, kein Schutz (verhindert Secret-Leak in Nginx-Logs).
- Go antwortet Telegram **sofort 200** (fire-and-forget Forwarding) → kein Retry-Sturm.
- Python dedupliziert `update_id` (in-memory Seen-Set) → keine Doppelausführung.

## Voraussetzungen / ENV

| ENV | Prozess | Zweck |
|-----|---------|-------|
| `TELEGRAM_BOT_TOKEN` | beide | Bot-Token. **Prod und Staging strikt getrennt!** |
| `TELEGRAM_WEBHOOK_SECRET` | Go | Secret-Header-Prüfung. Muss == `secret_token` in `setWebhook`. |
| `GZ_PUBLIC_BASE_URL` | Setup-Script | z.B. `https://gregor20.henemm.com` |

Webhook setzt öffentliche Erreichbarkeit + gültiges TLS (Let's-Encrypt) voraus.

## Webhook registrieren

```bash
export TELEGRAM_BOT_TOKEN=...        # Prod-Bot
export TELEGRAM_WEBHOOK_SECRET=...   # identisch zur Go-ENV
export GZ_PUBLIC_BASE_URL=https://gregor20.henemm.com
scripts/telegram_set_webhook.sh set
scripts/telegram_set_webhook.sh info   # Status prüfen: url gesetzt, last_error_message leer
```

`getWebhookInfo` (`info`) liefert `pending_update_count` und `last_error_message` —
Basis für den BetterStack-Healthcheck (Alert bei Fehler/Stau).

## Rollback (Webhook → Polling)

Telegram erlaubt **kein** Parallelbetrieb (ein Bot = eine URL; `getUpdates` liefert
`409` solange ein Webhook gesetzt ist). Rollback ist Big-Bang:

1. **Webhook entfernen:**
   ```bash
   export TELEGRAM_BOT_TOKEN=...
   scripts/telegram_set_webhook.sh delete
   ```
2. **Poll-Job reaktivieren:** in `internal/scheduler/scheduler.go` die mit Issue #637
   entfernte Job-Zeile wiederherstellen
   (`{"@every 30s", s.inboundTelegram, "inbound_telegram_poll", ...}`) plus die Methode
   `inboundTelegram()` (triggert `/api/scheduler/inbound-telegram`), Job-Zähler-Log auf
   „5 jobs" zurücksetzen, Go-Binary neu bauen + Service restarten.
   Der Python-Trigger-Endpoint `/api/scheduler/inbound-telegram` ist als Notfall-Fallback
   erhalten geblieben und sofort wieder nutzbar.

## Token-Rotation

1. Neues `TELEGRAM_WEBHOOK_SECRET` erzeugen, Go-ENV aktualisieren, Go-Service restarten.
2. `scripts/telegram_set_webhook.sh set` erneut ausführen (registriert neues `secret_token`).
3. `info` prüfen. Bei Inkonsistenz (alter Secret-Header) → 403-Zähler steigt; siehe Logs
   `[telegram-webhook] 403 rejected`.

## Staging-Bot-Setup

- **Eigener Test-Bot-Token** auf Staging — niemals den Prod-Bot teilen
  (Webhook-Exklusivität: ein Bot kann nur auf eine URL zeigen).
- ENV `TELEGRAM_BOT_TOKEN` + `TELEGRAM_WEBHOOK_SECRET` für den Staging-Prozess separat setzen.
- `GZ_PUBLIC_BASE_URL=https://staging.gregor20.henemm.com` beim Setup-Script.

## Bot-Menü (Slash-Befehle)

Telegram-Bots können ein Menü mit 6–7 Befehlen anzeigen, die Nutzer per Tap auswählen.
Das Menü wird **automatisch beim Service-Start** aus `BOT_COMMANDS` gesetzt (Issue #671,
2026-06-09).

**Automatisches Setup (Produktions-Standard):**

- FastAPI-Lifespan-Hook (`api/main.py`) ruft beim Service-Start `TelegramOutput.set_my_commands()` auf
- `setMyCommands`-Payload nutzt `BOT_COMMANDS` aus `src/outputs/telegram.py` (7 Befehle)
- Idempotent: jeder Deploy/Service-Restart stellt das Menü sicher
- Fail-soft: fehlender Token blockt den Service-Start nicht

**Manuelle Verwaltung (nur Notfall, normalerweise nicht nötig):**

```bash
# Befehl-Menü gegen echten Bot setzen (nur nötig bei lokalem Debugging)
export TELEGRAM_BOT_TOKEN=...
scripts/telegram_set_commands.sh set

# Aktuelles Menü prüfen
scripts/telegram_set_commands.sh get

# Menü zurücksetzen (beide Bots)
scripts/telegram_set_commands.sh reset
```

**Verifikation:** Nach Deploy prüft der Post-Deploy-Selftest das Live-Menü gegen
den Prod-Bot via `getMyCommands` (AC-4 in Issue #671). Abweichung vom erwarteten
Menü meldet FAIL und blockiert Issue-Close.

**Häufige Probleme:**
- Alte Worktrees/Workspaces mit altem Code können das Menü temporär überschreiben,
  wenn dort manuell `telegram_set_commands.sh set` läuft. Der nächste Prod-Deploy heilt das.
- Staging-Bot-Token liegt in `gregor_zwanzig_staging/.env` (separater Bot, nicht mit Prod teilen).

## Monitoring

- **403-Zähler:** abgewiesene Requests im Go-Log (`[telegram-webhook] 403 rejected (count=N)`),
  exponiert über `handler.RejectedTelegramWebhookCount()` → Anomalie-/Angriffs-Alert.
- **Healthcheck:** periodischer `getWebhookInfo` → `last_error_message`/`pending_update_count`
  → BetterStack (Liveness-Ersatz für den entfallenen `last_run` des Poll-Jobs).
- **Bot-Menü-Selftest:** Nach Deploy `getMyCommands` gegen Prod-Bot → Regression-Alert
  wenn Live-Menü nicht mit `BOT_COMMANDS` übereinstimmt (Issue #671).
- **Nginx (henemm-infra):** IP-Allowlist auf Telegram-Ranges + `limit_req` auf dem
  Webhook-Pfad (gegen offizielle Telegram-Doku verifizieren).

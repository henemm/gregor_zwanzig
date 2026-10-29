# Runbook — Telegram Inbound Webhook (Issue #637)

Der Telegram-Eingang läuft **push-basiert** über einen Webhook statt 30-Sekunden-Polling.

## Architektur (Kurzfassung)

```
Telegram  --POST-->  Go (öffentlich)                         -->  Python Core (intern)
                     /api/webhooks/telegram/inbound               /api/internal/telegram-webhook
                     Secret-Header-Check + sofort 200             Idempotenz + Befehlsverarbeitung
```

- **Registrierte URL** ist `/api/webhooks/telegram/inbound` — ohne Secret im Pfad (#1814).
- **Einziger Auth-Träger** ist der HTTP-Header `X-Telegram-Bot-Api-Secret-Token`
  (== ENV `TELEGRAM_WEBHOOK_SECRET` des Go-Prozesses). Der URL-Pfad wird nie gelesen.
- **Übergang:** Die Alt-Route `/api/webhooks/telegram/{secret}` nimmt bis zur
  Neuregistrierung beider Umgebungen weiter Updates an; sie wird danach entfernt und das
  Secret rotiert (altes Secret lag im Pfad und steht ggf. in Logs).
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
scripts/telegram_set_webhook.sh info   # Auswertung ja/nein: URL endet auf /inbound, last_error_message leer
```

`set` und `info` geben weder das Secret noch eine URL mit Secret aus. `info` gibt die
`getWebhookInfo`-Antwort **nicht roh** aus, sondern nur eine ja/nein-Auswertung (URL endet auf
`/api/webhooks/telegram/inbound`, URL frei von Secret, `last_error_message` leer). Die rohe
Antwort nie ins Ticket kopieren — eine Alt-Registrierung enthält das Secret in der URL.
`info` endet auch bei „nein"-Zeilen mit Exit 0: Deploy und Betrieb müssen die ja/nein-Zeilen
lesen und dürfen nicht auf den Exit-Code vertrauen. Ist `TELEGRAM_WEBHOOK_SECRET` nicht gesetzt,
steht bei „URL frei von Secret" `übersprungen` — dann ist diese Prüfung nicht erfolgt.

`getWebhookInfo` liefert `pending_update_count` und `last_error_message` — Basis für den
BetterStack-Healthcheck (`henemm-infra/scripts/check-gregor20.sh`, eigener API-Aufruf; Alert bei
Fehler/Stau).

## Rollback (Webhook → Polling)

Gibt es nicht mehr. Der Poll-Pfad (`InboundTelegramReader.poll_and_process`/
`_get_updates`) und der Trigger-Endpoint `/api/scheduler/inbound-telegram` sind mit
#1369 entfernt, weil sie mit rohem Bot-Token an den Egress-Guards vorbeiliefen.
Bei Webhook-Störungen: Webhook neu registrieren (`scripts/telegram_set_webhook.sh`),
`getWebhookInfo` prüfen; Telegram puffert Updates bis 24 h. Soll Polling je
wiederkommen, braucht es eine neue Spec mit Egress-Guard von Anfang an.

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

Telegram-Bots zeigen ein Menü mit den per Tap auswählbaren Befehlen.
Das Menü wird **automatisch beim Service-Start** aus `BOT_COMMANDS` gesetzt (Issue #671,
2026-06-09; seit Issue #2417 AC-21 vollständig alle `_COMMAND_SPECS`-Wörter, 17 Befehle
statt vormals 7 — Details `docs/features/architecture.md`).

**Automatisches Setup (Produktions-Standard):**

- FastAPI-Lifespan-Hook (`api/main.py`) ruft beim Service-Start `TelegramOutput.set_my_commands()` auf
- `setMyCommands`-Payload nutzt `BOT_COMMANDS` aus `src/output/channels/telegram.py` (17 Befehle)
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

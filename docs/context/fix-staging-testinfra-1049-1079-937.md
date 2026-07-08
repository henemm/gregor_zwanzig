# Context: Staging-Test-Infrastruktur (#1049, #1079, #937)

## Request Summary
Drei unabhängige Bugs verhindern zuverlässige, Prod-isolierte Verifikation auf Staging:
(1) Prod/Staging teilen sich die Inbound-Mail-Inbox, (2) der Staging-Telegram-Webhook
antwortet 401 wegen Basic-Auth, (3) es fehlt ein dauerhafter Staging-Test-Trip mit
Zukunftsdatum für den `briefing_mail_validator`.

## Related Files

| File | Relevance |
|------|-----------|
| `internal/scheduler/scheduler.go:94-95,207` | `inbound_command_poll`-Cron (*/5min), liest UNSEEN-Mails aus der per `GZ_IMAP_USER`/`GZ_INBOUND_ADDRESS` konfigurierten Inbox — läuft in Prod UND Staging gegen dieselbe Inbox (#1049). Kommentar Z.95 bestätigt: `inbound_telegram_poll` wurde in #637 entfernt, Telegram-Inbound läuft NUR noch über Webhook |
| `internal/handler/telegram_webhook.go` | Go-Webhook-Gateway `POST /api/webhooks/telegram/{secret}`. Auth läuft über Header `X-Telegram-Bot-Api-Secret-Token`, NICHT über das URL-Pfadsegment — das Pfadsegment ist nur Defense-in-Depth-Routing. Fail-closed wenn Secret fehlt |
| `internal/router/router.go:71` | Registriert `/api/webhooks/telegram/{secret}` |
| `/home/hem/henemm-infra/nginx/staging.gregor20.henemm.com.conf` | **Anderes Repo!** Globale `auth_basic` für die ganze Staging-Domain. Bereits ein Präzedenzfall vorhanden: `location = /api/health` nimmt sich explizit von Basic-Auth aus (Kommentar referenziert #1030) — exaktes Vorbild für den #1079-Fix |
| `scripts/telegram_set_webhook.sh` | Verwaltet den Telegram-Webhook (set/delete/info) — bestätigt: Staging nutzt Webhook, kein Rollback auf Polling nötig |
| `scripts/setup-validator-user.sh` | Idempotentes Vorbild für Test-User-Setup via `/api/auth/register` + Login-Verifikation — Muster für #937 |
| `data/users/validator-issue110/` (Staging: `/home/hem/gregor_zwanzig_staging/data/users/validator-issue110/`) | Bereits existierender Test-User mit >60 Trips aus diversen E2E-Läufen, aber **kein** Trip mit Rolling-Zukunftsdatum + `gregor-test@henemm.com`-Empfänger |
| `.claude/hooks/briefing_mail_validator.py:30-102,393` | Heuristik verlangt >=2 distinct `HH:00`-Treffer (Stundentabelle) — schlägt bei Trips mit Vergangenheits-Etappen strukturell fehl, weil dann kein Forecast existiert |
| `tests/tdd/test_bug_inbound_email_loop.py`, `test_issue_1009_1019_inbound_robustness.py` | Bestehende Tests zu `GZ_INBOUND_ADDRESS`-Handling — Referenz für Testmuster bei #1049 |

## Existing Patterns
- **Nginx-Auth-Ausnahme pro Location:** `/api/health` zeigt das etablierte Muster (`auth_basic off;` in einer spezifischen `location =`-Direktive, mit Begründungskommentar + Issue-Referenz) — für #1079 identisch anwendbar, da der Go-Handler bereits eigenständig per Secret-Header authentifiziert (Nginx-Basic-Auth ist hier zusätzliche, nicht die tragende Schicht)
- **Idempotente Setup-Scripts unter `scripts/`:** `setup-validator-user.sh`, `seed_validator_archive.py` — Muster für einen neuen Cron/Setup-Script-Ansatz bei #937 (Rolling-Trip-Datum)
- **Getrennte Test-/Prod-Kanäle bereits etabliert für Telegram:** #1077 hat `GZ_TELEGRAM_TEST_CHAT_ID` von Prod-Chat getrennt und einen `is_test_user`-Flag im Scheduler eingeführt — #1049 ist die Mail-Analogie dazu (geteilte Inbox statt geteilter Chat)

## Dependencies
- **Upstream:** Stalwart Mail-Server (neues Postfach für #1049 nötig — Admin-UI https://mail.henemm.com), Nginx/Certbot auf dem Server (#1079 — liegt im Repo `henemm-infra`, NICHT `gregor_zwanzig`), Telegram Bot API (`getWebhookInfo`/`setWebhook`, #1079)
- **Downstream:** `briefing_mail_validator.py` (#937 — Pflicht-Gate vor jeder Mail-Renderer-Änderung), Inbound-E2E-Tests (#1049), Live-Telegram-Inbound-Tests (#1079)

## Existing Specs
- `docs/specs/modules/telegram_webhook_inbound.md` — Spec zum bestehenden Webhook-Gateway (#637)
- `docs/specs/modules/issue_1077_telegram_test_chat_isolation.md` — verwandtes Muster (Test-Chat-Isolation)
- Keine bestehende Spec zu Inbound-Mail-Postfach-Trennung oder Staging-Test-Trip-Rolling

## Risks & Considerations
- **#1079 ist repo-übergreifend:** Der eigentliche Fix (Nginx-Location-Ausnahme) liegt in `henemm-infra`, nicht in `gregor_zwanzig`. Laut globaler Konvention (`~/.claude/CLAUDE.md`) gehören Infrastruktur-Änderungen dort committet — dieser Workflow kann die ACs nur bis zur Grenze "Änderung spezifiziert + an `infra`-Instanz per Claude-MQ gemeldet" erfüllen, nicht bis zum tatsächlichen Nginx-Commit. Muss in der Spec als Abhängigkeit/Grenze explizit gemacht werden
- **#1049 erfordert externe Stalwart-Aktion:** Neues Postfach kann nicht per Code-Change entstehen, sondern nur über Stalwart-Admin-UI/API — ebenfalls ein Schritt außerhalb des reinen Code-Workflows, aber innerhalb dieses Repos liegt die `.env`-Änderung + ggf. Verifikationstest
- **#937 "Rolling"-Mechanismus:** Reines einmaliges Anlegen eines Trips mit Zukunftsdatum verfällt nach Ablauf wieder in "Vergangenheit ohne Forecast" — die Spec braucht einen echten Wiederhol-Mechanismus (Cron/Script), nicht nur einen einmaligen Datensatz
- **Kein Prod-Code betroffen:** Alle drei Fixe sind auf Staging/Infra/Config beschränkt — Blast Radius bleibt trotz Cross-Repo-Anteil überschaubar
- **IMAP-`\Seen`-Falle (#1049):** Laut Issue-Text setzt selbst eine reine Inspektion via `FETCH RFC822` (ohne `BODY.PEEK`) das `\Seen`-Flag und zerstört den Test — bei der Verifikation von #1049 zwingend `BODY.PEEK` verwenden (siehe auch Memory `reference_imap_fetch_implicit_seen`)
- **Crontab ist nicht repo-versioniert:** Bestehende Cron-Einträge (`crontab -l`) verweisen zwar auf Scripts in `henemm-infra/scripts/`, liegen selbst aber nur als Host-Zustand vor (kein Tracking-File, README erwähnt nur `crontab -l` zur Inspektion). Ein neuer Rolling-Trip-Cron für #937 ist damit eine reine Host-Operation, kein Commit in einem der beiden Repos — Script selbst gehört nach `gregor_zwanzig/scripts/`

## Analysis

### Type
Bug (alle drei: bestehendes, erwartetes Verhalten — Prod/Staging-Isolation bzw. Validator-Ausführbarkeit — ist verletzt)

### Affected Files (with changes)

| File | Change Type | Description |
|------|-------------|-------------|
| Staging-`.env` (Server, nicht im Repo) | MODIFY | `GZ_INBOUND_ADDRESS`/`GZ_IMAP_USER` auf neues Staging-Postfach umstellen (#1049) |
| Stalwart Admin (extern) | CREATE | Neues Postfach `gregor-staging@henemm.com` (#1049) |
| `tests/tdd/test_issue_1049_staging_inbox_isolation.md` bzw. `.py` | CREATE | Beweis: Kommando an Staging-Adresse landet NUR auf Staging (count>=1), Prod bleibt leer |
| `/home/hem/henemm-infra/nginx/staging.gregor20.henemm.com.conf` (anderes Repo) | MODIFY | `location = /api/webhooks/telegram/...` von `auth_basic` ausnehmen, analog `/api/health` (#1079) — **wird per Claude-MQ an `infra` delegiert, nicht in diesem Workflow committet** |
| Verifikation #1079 | — | `telegram_set_webhook.sh info` gegen Staging-Bot nach Infra-Fix — `pending_update_count` muss auf 0 fallen, kein `last_error_message` mehr |
| `scripts/setup_staging_validator_trip.py` (Name vorläufig) | CREATE | Idempotentes Script nach Vorbild `setup-validator-user.sh`: legt/aktualisiert für `validator-issue110` einen Trip mit Etappe `heute+1`/`heute+2`, bekannter Koordinate (z.B. Innsbruck), `report_config.send_email` → `gregor-test@henemm.com`, `report_type=evening` (#937) |
| Crontab (Host, kein Repo) | CREATE | Wöchentlicher Aufruf des Scripts, damit das Datum rollend aktuell bleibt (#937) |
| BetterStack Heartbeat | CREATE | Für den neuen Cron, gemäß globaler Pflicht bei neuen Scripts/Cronjobs |

### Scope Assessment
- Dateien in `gregor_zwanzig`: ~2-3 (1 neues Setup-Script, 1-2 Testdateien)
- Geschätzte LoC: ~80-150 (überwiegend #937-Script + Tests), kein Produktionscode-Pfad (`src/`) betroffen
- Risk Level: MEDIUM — nicht wegen Code-Komplexität, sondern weil zwei der drei Fixe außerhalb des Repos (Stalwart, henemm-infra) liegen und nur indirekt (Config/Messaging) durch diesen Workflow abgedeckt werden können

### Technical Approach
1. **#1049:** Staging-`.env` auf eigenes Postfach umstellen, nachdem es in Stalwart existiert. Verifikation: Kommando-Mail an neue Staging-Adresse senden, per `BODY.PEEK`-IMAP-Fetch auf Staging-Seite Empfang nachweisen, Prod-Inbox parallel auf Nicht-Empfang prüfen.
2. **#1079:** Fix-Vorschlag (Nginx-Location-Ausnahme) als konkreten Diff an `infra`-Instanz per Claude-MQ senden (Datei + genaue Zeilen benennen). Nach Bestätigung durch `infra`: `getWebhookInfo` gegen Staging-Bot verifizieren.
3. **#937:** Setup-Script analog `setup-validator-user.sh`, nutzt bestehende `validator-issue110`-Identität, ruft interne API (Port 8001 auf Staging) für Trip-Create/Update auf. Cron wöchentlich, Heartbeat Pflicht.

### Dependencies
- #1079-Fix ist blockiert auf Mitwirkung der `infra`-Instanz (anderes Repo) — kann in diesem Workflow nur bis zur Übergabe fortschreiten, das tatsächliche Grün-Verdict für die AC hängt von deren Umsetzung ab
- #937 hängt an der bestehenden internen Scheduler-API (Port 8001) und am `validator-issue110`-User, beide bereits vorhanden
- #1049 hängt an Stalwart-Postfach-Anlage (Admin-UI/API), danach reine `.env`-Änderung + Scheduler-Neustart

### Open Questions (PO-entschieden 2026-07-08)
- [x] #937: Testort = Innsbruck
- [x] #1079: Fix-Diff per Claude-MQ an `infra` melden; AC gilt erst nach deren Bestätigung (sauberes `getWebhookInfo`) als erfüllt — Workflow wartet, schließt #1079 nicht vorzeitig
- [x] #1049: Postfach-Name = `gregor-staging@henemm.com`

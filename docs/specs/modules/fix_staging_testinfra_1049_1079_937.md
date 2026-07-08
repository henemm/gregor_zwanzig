---
entity_id: fix_staging_testinfra_1049_1079_937
type: module
created: 2026-07-08
updated: 2026-07-08
status: draft
version: "1.0"
tags: [staging, testinfra, bugfix, telegram, imap, cron]
---

# Staging-Test-Infrastruktur: Mail-Postfach-Isolation, Telegram-Webhook-401, Rolling Test-Trip (#1049, #1079, #937)

## Approval

- [ ] Approved

## Purpose

Drei unabhängige Bugs verhindern eine zuverlässige, Prod-isolierte Verifikation auf Staging: (1) Prod und Staging lesen dieselbe Inbound-Mail-Inbox und können sich gegenseitig Kommandos "stehlen" bzw. deren `\Seen`-Status verfälschen, (2) der Staging-Telegram-Webhook wird von Nginx-Basic-Auth blockiert (401) obwohl der Go-Handler bereits eigenständig per Secret-Header authentifiziert, (3) es fehlt ein dauerhafter, datumsrollender Staging-Test-Trip, gegen den der `briefing_mail_validator.py` überhaupt laufen kann. Diese Spec bündelt alle drei Fixe, weil sie gemeinsam die Grundlage für zuverlässige Staging-E2E-Verifikation (Pflicht-Gate vor jedem Prod-Deploy) bilden.

## Source

### Teilproblem 1 — #1049 (Inbox-Isolation)

- **File:** `internal/scheduler/scheduler.go:94` (Cron `inbound_command_poll`, */5min)
- **File:** `api/routers/scheduler.py:70-84` (`POST /api/scheduler/inbound-commands` → `InboundEmailReader.poll_and_process`)
- **File:** `src/app/config.py:120-135,206-208` (`inbound_address`, `imap_host`, `imap_user`, `imap_pass` — Settings-Felder, ENV-Namen `GZ_INBOUND_ADDRESS`/`GZ_IMAP_HOST`/`GZ_IMAP_USER`/`GZ_IMAP_PASS`)
- **File:** Staging-`.env` (Server, `/home/hem/gregor_zwanzig_staging/.env` — NICHT im Repo)
- **Identifier:** Stalwart Admin-UI (https://mail.henemm.com) — neues Postfach `gregor-staging@henemm.com`

### Teilproblem 2 — #1079 (Telegram-Webhook-401)

- **File:** `internal/handler/telegram_webhook.go:37-51` (`TelegramWebhookHandler` — Secret-Auth über Header `X-Telegram-Bot-Api-Secret-Token`, fail-closed)
- **File:** `internal/router/router.go:71` (Route-Registrierung `/api/webhooks/telegram/{secret}`)
- **File:** `scripts/telegram_set_webhook.sh` (set/delete/info gegen Telegram Bot API)
- **File (anderes Repo, NICHT gregor_zwanzig):** `/home/hem/henemm-infra/nginx/staging.gregor20.henemm.com.conf:9-19` — Präzedenzfall `location = /api/health { auth_basic off; ... }`

### Teilproblem 3 — #937 (Rolling Test-Trip)

- **File:** `scripts/setup-validator-user.sh` (Vorbild: idempotentes Setup-Script)
- **File:** `api/routers/scheduler.py:179-216` (`POST /api/scheduler/trips/{trip_id}/send`)
- **File:** `src/app/loader.py` (`load_all_trips`, `save_trip`)
- **File:** `src/app/config.py:243-278` (`with_user_profile` — `mail_to`-Override aus `data/users/{user_id}/user.json`, auf Staging automatisch `force_test=True` → Stalwart statt Resend)
- **File:** `data/users/validator-issue110/user.json` (bestehender Test-User, Feld `mail_to` fehlt noch)
- **File (neu):** `scripts/setup_staging_validator_trip.py`
- **File:** `.claude/hooks/briefing_mail_validator.py:30-102,393` (verlangt >=2 distinct `HH:00`-Treffer — braucht Zukunfts-Etappen)
- **Identifier (Host, kein Repo):** Crontab-Eintrag (wöchentlich) + BetterStack-Heartbeat

> **Schicht-Hinweis:** Alle drei Fixe berühren Config/Infra-Ebene, keine Frontend- oder Go-API-Business-Logik. #1049/#937 betreffen Python-Core (`api/`, `src/app/`), #1079 betrifft ausschließlich Go-Handler-Doku (bereits korrekt implementiert) + externe Nginx-Config.

## Estimated Scope

- **LoC:** ~80-150 (überwiegend `scripts/setup_staging_validator_trip.py` + Tests; kein `src/`-Produktionscode betroffen)
- **Files:** ~3 in `gregor_zwanzig` (1 neues Script, 1-2 Testdateien) + 1 externe Nginx-Config-Änderung (anderes Repo, nicht in diesem Workflow committet) + 1 Stalwart-Postfach (extern) + 1 `user.json`-Feld (Daten, kein Code) + 1 Crontab-Zeile (Host-Zustand)
- **Effort:** medium (Code-Umfang klein, aber drei getrennte Verifikationswege außerhalb des reinen Python-Testlaufs: IMAP-PEEK-Fetch, Telegram-Bot-API-Call, interner Scheduler-Trigger)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| Stalwart Mail-Server | external service | Neues Postfach `gregor-staging@henemm.com` anlegen (#1049) |
| `henemm-infra` Repo/Instanz | external repo | Nginx-Location-Ausnahme für `/api/webhooks/telegram/*` (#1079) — Fix liegt dort, nicht hier |
| Telegram Bot API | external service | `getWebhookInfo`/`setWebhook` zur Verifikation (#1079) |
| `validator-issue110` User + interne Scheduler-API (Port 8001, Staging) | internal | Trägt den Rolling-Test-Trip (#937) |
| BetterStack Heartbeats | external service | Pflicht-Monitoring für neuen Cron (#937) — Quota-Limit 10 aktive Heartbeats beachten |

## Implementation Details

**#1049:** Nach Anlage von `gregor-staging@henemm.com` in Stalwart wird die Staging-`.env` auf `GZ_INBOUND_ADDRESS=gregor-staging@henemm.com` und `GZ_IMAP_USER=gregor-staging` (analog bestehendem Muster `GZ_IMAP_USER=gregor-test` für den Validator-Test-Account) umgestellt, danach `gregor-python-staging` neu gestartet, damit `Settings()` die neuen Werte lädt. Der Cron `inbound_command_poll` liest danach ausschließlich aus dem neuen Postfach.

**#1079:** Der Go-Handler ist bereits korrekt (Secret-Header-Auth, fail-closed) — kein Code-Fix in `gregor_zwanzig` nötig. Der Fix ist eine reine Nginx-Config-Ergänzung in `henemm-infra` nach dem Muster der bestehenden `/api/health`-Ausnahme:

```
location = /api/webhooks/telegram/<secret-placeholder> {
    auth_basic off;
    proxy_pass http://127.0.0.1:8091;
    ...gleiche proxy_set_header wie /api/ ...
}
```

Da der Secret-Wert selbst im Pfad steht, muss die `location`-Direktive entweder mit einer Regex auf `/api/webhooks/telegram/` (Präfix, kein `=`) oder mit dem konkreten aktuellen Secret-Wert erfolgen. Dieser Workflow liefert den vorgeschlagenen Diff als Claude-MQ-Nachricht an die `infra`-Instanz; die eigentliche AC-Erfüllung hängt von deren Umsetzung + Bestätigung ab (siehe AC-6/AC-7).

**#937:** `scripts/setup_staging_validator_trip.py` (Vorbild `setup-validator-user.sh`, aber in Python für JSON-Handling): idempotent für `validator-issue110`
1. `user.json` um `"mail_to": "gregor-test@henemm.com"` ergänzen (Read-Modify-Write, kein Replace — bestehende Felder wie `password_hash` bleiben erhalten)
2. Trip mit fester ID (z.B. `staging-validator-rolling`) anlegen/aktualisieren: eine Etappe mit `date = heute+1`, eine mit `date = heute+2`, Koordinate Innsbruck (47.2692, 11.4041), `report_config.send_email=True`
3. Aufruf via bestehende interne API (`load_all_trips`/`save_trip` direkt, oder HTTP gegen Port 8001 auf Staging analog `setup-validator-user.sh`)

Crontab (Host, wöchentlich, z.B. `0 5 * * 1`): ruft das Script erneut auf, damit die Etappen-Daten rollend `heute+1`/`heute+2` bleiben. Heartbeat-Ping nur nach erfolgreichem Lauf (Exit 0), gemäß globaler Heartbeat-Pflicht-Regel — Quota-Limit von 10 aktiven BetterStack-Heartbeats vorher prüfen (`curl .../heartbeats` zählen), ggf. Integration in bestehenden Heartbeat statt Neuanlage.

## Expected Behavior

- **Input:** Kommando-Mail an Staging-Adresse (#1049); Telegram-Update an Staging-Bot-Webhook (#1079); Scheduler-Trigger `POST /api/scheduler/trips/{id}/send` (#937)
- **Output:** #1049 — Mail landet ausschließlich in der Staging-Verarbeitung, Prod bleibt unberührt. #1079 — Webhook liefert 200 statt 401, `getWebhookInfo` zeigt keinen `last_error_message`. #937 — Versand liefert `{"sent": true}`, `briefing_mail_validator.py` läuft grün gegen eine real zugestellte Mail mit Stundentabelle
- **Side effects:** #1049 — Staging-Prozess muss nach `.env`-Änderung neu gestartet werden. #937 — `user.json` von `validator-issue110` bekommt zusätzliches Feld, Crontab bekommt neuen Eintrag (Host-Zustand)

## Acceptance Criteria

### #1049 — Inbound-Mail-Postfach-Isolation

- **AC-1:** Given das neue Stalwart-Postfach `gregor-staging@henemm.com` existiert und die Staging-`.env` ist auf `GZ_INBOUND_ADDRESS=gregor-staging@henemm.com`/`GZ_IMAP_USER=gregor-staging` umgestellt (Prozess neu gestartet) / When eine Kommando-Mail (z.B. `PAUSE`) an `gregor-staging@henemm.com` gesendet und danach `POST /api/scheduler/inbound-commands` auf Staging getriggert wird / Then der Rückgabewert zeigt `count >= 1` (die Mail wurde verarbeitet).
  - Test: Echte Mail per SMTP an `gregor-staging@henemm.com` senden, echten internen Scheduler-Endpoint auf Staging aufrufen, Response-JSON auf `count >= 1` prüfen. IMAP-Verifikation der Mailbox ausschließlich mit `BODY.PEEK[]` (niemals `FETCH RFC822` ohne PEEK) — sonst wird `\Seen` gesetzt und der Test zerstört sich selbst.

- **AC-2:** Given dieselbe Kommando-Mail wurde in #AC-1 an die Staging-Adresse gesendet / When die Prod-Inbox (`gregor_zwanzig@henemm.com`) per IMAP mit `BODY.PEEK[]` auf neue UNSEEN-Mails im relevanten Zeitfenster geprüft wird / Then die Prod-Inbox enthält KEINE neue Mail aus diesem Testlauf (Isolation bewiesen).
  - Test: Echter IMAP-Connect gegen die Prod-Mailbox mit `BODY.PEEK[]`, Zählung neuer UNSEEN-Nachrichten im Testzeitfenster vor/nach Versand vergleichen — kein Mock, echte Zustellung.

### #1079 — Telegram-Webhook 401 (Nginx Basic-Auth)

- **AC-3:** Given der aktuelle Zustand von `getWebhookInfo` für den Staging-Bot zeigt ein `last_error_message` mit 401 (Basic-Auth-Block) / When der konkrete Diff-Vorschlag (Nginx-`location`-Ausnahme analog `/api/health`, mit exaktem Pfad/Secret-Handling) formuliert ist / Then eine Claude-MQ-Nachricht an die `infra`-Instanz ist versendet, die den vollständigen Diff, die Ziel-Datei (`/home/hem/henemm-infra/nginx/staging.gregor20.henemm.com.conf`) und die Begründung enthält.
  - Test: `/home/hem/claude-mq/send.sh gregor infra normal "..." "..."` wird ausgeführt; Nachweis über `check-messages.sh`/MQ-DB, dass die Nachricht zugestellt wurde. Kein Dateiinhalt-Check als Ersatz für den echten Send.

- **AC-4:** Given die `infra`-Instanz hat die Nginx-Änderung committet und deployt / When `bash scripts/telegram_set_webhook.sh info` gegen den Staging-Bot ausgeführt wird / Then die Antwort zeigt `pending_update_count` sinkend gegen 0 und kein neues `last_error_message` seit dem Fix-Zeitpunkt.
  - Test: Echter `curl`-Call gegen die Telegram Bot API (`getWebhookInfo`) für den Staging-Bot-Token, JSON-Response inspizieren. Diese AC gilt erst nach Bestätigung durch die `infra`-Instanz als erfüllt — siehe Known Limitations.

### #937 — Rolling Staging-Test-Trip

- **AC-5:** Given `scripts/setup_staging_validator_trip.py` wurde gegen Staging ausgeführt (idempotent) / When das Script danach ein zweites Mal ausgeführt wird / Then es läuft ohne Fehler durch und verändert `user.json`/Trip nur dort, wo sich Werte tatsächlich unterscheiden (Read-Modify-Write, keine Duplikate, kein Datenverlust bestehender Felder wie `password_hash`).
  - Test: Script zweimal hintereinander gegen Staging ausführen, `user.json` und Trip-Datei vor/nach beiden Läufen per echtem HTTP-GET (`/api/trips`) vergleichen — Feldbestand identisch, keine zweite Trip-Instanz.

- **AC-6:** Given der Rolling-Trip existiert mit Etappen auf `heute+1`/`heute+2` (Innsbruck) und `mail_to=gregor-test@henemm.com` in `validator-issue110`'s `user.json` / When `curl -s -X POST "http://localhost:8001/api/scheduler/trips/<test-trip-id>/send?user_id=validator-issue110&report_type=evening"` auf Staging aufgerufen wird / Then die Antwort ist `{"sent": true, ...}`.
  - Test: Echter HTTP-POST-Call gegen den internen Staging-Scheduler-Port, JSON-Response auf `sent: true` prüfen — kein Mock.

- **AC-7:** Given die Mail aus AC-6 wurde tatsächlich versendet und ist im Stalwart-Postfach `gregor-test@henemm.com` zugestellt / When `uv run python3 .claude/hooks/briefing_mail_validator.py --mail-type trip-briefing` ausgeführt wird / Then der Validator terminiert mit Exit 0 (Stundentabelle mit >=2 distinct `HH:00`-Treffern erkannt).
  - Test: Validator läuft gegen die real per IMAP abgerufene Mail (kein Gmail, kein Mock) — Exit-Code direkt prüfen, keine `assert 'x' in mail_body`-Ersatzprüfung.

- **AC-8:** Given der wöchentliche Crontab-Eintrag für `setup_staging_validator_trip.py` ist auf dem Host eingerichtet / When `crontab -l` auf dem Server ausgeführt wird / Then der Eintrag ist sichtbar und ruft das Script mit einem BetterStack-Heartbeat-Ping nach erfolgreichem Lauf auf (kein bedingungsloser Ping — siehe globale Heartbeat-Pflicht-Regel).
  - Test: `crontab -l` real ausführen und den Eintrag zeigen; danach das Script manuell einmal laufen lassen und den Heartbeat-Ping (Exit 0 des Scripts) über den BetterStack-API-Status des Heartbeats nachweisen (`last_ping`/Status "up").

## Known Limitations

- **#1079 hängt an fremder Repo/Instanz-Abhängigkeit:** Der eigentliche Nginx-Fix liegt in `henemm-infra`, nicht in `gregor_zwanzig`. Dieser Workflow kann AC-3 (Diff spezifiziert + gemeldet) vollständig erfüllen, AC-4 (verifizierter Fix) hängt von der Umsetzung durch die `infra`-Instanz ab und kann in diesem Workflow-Durchlauf offen bleiben, ohne dass das den gesamten Workflow blockiert — der PO hat das explizit so entschieden (2026-07-08).
- **Crontab ist kein Repo-Artefakt:** Der neue wöchentliche Cron-Eintrag für #937 ist reiner Host-Zustand (kein Commit, keine Tracking-Datei) — nur `crontab -l` zeigt ihn. Bei Server-Neuaufsetzung geht er verloren, sofern nicht anderweitig dokumentiert.
- **Stalwart-Postfach-Anlage ist manuell/extern:** #1049 erfordert eine einmalige Aktion im Stalwart-Admin-UI außerhalb jedes Code-Workflows, bevor die `.env`-Änderung wirksam werden kann.
- **BetterStack-Quota:** Das Konto erlaubt maximal 10 aktive Heartbeats (Stand 2026-06-24 alle belegt). Ein neuer dedizierter Heartbeat für #937 kann an dieser Quota scheitern — ggf. Integration in einen bestehenden Heartbeat statt Neuanlage.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Alle drei Fixe sind reine Bugfixes auf Config-/Infra-Ebene (getrenntes Mail-Postfach, Nginx-Auth-Ausnahme nach etabliertem Muster, ein zusätzliches idempotentes Setup-Script) — kein neues Architektur-Pattern, keine neue Systemgrenze, kein Wechsel bestehender Verantwortlichkeiten. Das Muster "Test-/Prod-Trennung pro Kanal" existiert bereits (#1077 für Telegram) und wird hier für Mail (#1049) analog angewendet, nicht neu erfunden.

## Changelog

- 2026-07-08: Initial spec created

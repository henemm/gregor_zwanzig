---
entity_id: webhook_secrets_config_2715
type: module
created: 2026-10-31
updated: 2026-10-31
status: draft
version: "1.0"
tags: [security, config, go, epic-2138, issue-2163, issue-2715, scheibe-1b, webhooks]
workflow: feat-2715-webhook-secrets-config
---

# Webhook-Secrets über Config (#2715, Scheibe 1b von #2163)

## Approval

- [ ] Approved

## Purpose

Die sechs Webhook-Werte für Telegram, seven.io (SMS und Premium-SMS) und Stalwart (E-Mail) kommen zentral über `config.Config` statt per `os.Getenv` in den einzelnen Handlern. Das Verhalten nach außen bleibt gleich: falsches Secret ⇒ 403, richtiges ⇒ Erfolg, leerer Wert ⇒ 503 (fail-closed). Es ist reine Konfigurations-Umstellung ohne neues Verhalten; sie wurde per Abtrennregel aus `docs/specs/modules/auth_haertung_go_2163.md` (Zeile 82) als Folgescheibe abgetrennt.

## Source

- **File:** `internal/config/config.go`, `internal/handler/telegram_webhook.go`, `internal/handler/telegram_connect.go`, `internal/handler/inbound_webhooks.go`, `internal/router/router.go`
- **Identifier:** `config.Config` (6 neue Felder), Webhook-Handler-Konstruktoren für Telegram, seven.io, Stalwart sowie `GetTelegramLinkHandler`

> **Schicht-Hinweis:** ausschließlich Go-API (`internal/`). Kein Frontend, kein Python-Core. Die Env-Namen bleiben unverändert, daher bleiben `scripts/telegram_set_webhook.sh`, `scripts/seven_hooks.sh` und `.env.example` unberührt.
>
> **Querschnitts-Prüfpunkte:**
> - **Trip/Ortsvergleich-Teilung:** nicht betroffen, kein Trip- oder Compare-Pendant.
> - **Mandantentrennung (ADR-0003):** Die Webhooks tragen keinen Nutzerbezug; das Secret ist systemweit. Kein neuer nutzerbezogener Endpoint, daher kein Zwei-Nutzer-Test nötig.
> - **Kanäle:** Briefing- und Alarm-Inhalte sind nicht berührt. Betroffen sind die Eingänge aller drei Kanalwege: Telegram, seven.io (SMS und Premium-SMS) und Stalwart (E-Mail). Alle sind gleichrangig und werden einzeln geprüft (Route-Test und Staging-Nachweis), nicht nur einer.

## Estimated Scope

- **Files:** ca. 5 Produktionsdateien, 2 neue Testdateien, 5 umgestellte Testdateien
- **LoC:** Produktion ca. +25/−15 (Branch-Diff geprüft: 41 Zeilen, deutlich unter 250); Tests ca. +500
- **Effort:** low bis medium
- **Risk:** MEDIUM. Kleiner Diff, aber ein falscher Tag oder eine fehlende Durchreichung im Router lässt alle drei Eingänge auf Prod mit 503 antworten (kein Telegram-, SMS- oder Mail-Befehl käme mehr an).
- **Test-Budget:** Das Test-LoC-Budget von 450 aus der Mutterspec gilt für diese Scheibe nicht mehr (der Testumbau ist der Grund der Abtrennung).

**Vorarbeit:** Fertige Umsetzung im Branch `feat-2163-s1b-webhook-config` (Stand a3f4760e7). Übernommen werden nur die Punkt-7-Dateien per `git diff main feat-2163-s1b-webhook-config -- <Dateien>`; kein Neuentwurf.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `config.Load` (envconfig v1.4.0) | Modul | liest `GZ_<NAME>`, dann unpräfixiert `<NAME>`; Muster existiert bei `SMTP_HOST` (`config.go:45`) |
| Router-`Deps.Config` | Struktur | transportiert die Werte zu den Handler-Konstruktoren |
| Env-Dateien Prod/Staging | Betrieb | setzen die sechs Variablen bereits unpräfixiert; kompatibel durch die Fallback-Regel |

## Implementation Details

- `internal/config/config.go`: sechs neue Felder `TelegramWebhookSecret`, `TelegramBotUsername`, `SevenWebhookPathSecret`, `SevenWebhookSigningKey`, `StalwartWebhookPathSecret`, `StalwartWebhookSecret`. Je `default:""` und der unpräfixierte Name als `envconfig`-Tag (Namen: `TELEGRAM_WEBHOOK_SECRET`, `TELEGRAM_BOT_USERNAME`, `SEVEN_WEBHOOK_PATH_SECRET`, `SEVEN_WEBHOOK_SIGNING_KEY`, `STALWART_WEBHOOK_PATH_SECRET`, `STALWART_WEBHOOK_SECRET`).
- `telegram_webhook.go`: `os.Getenv("TELEGRAM_WEBHOOK_SECRET")` wird Parameter `secret`.
- `telegram_connect.go`: `os.Getenv("TELEGRAM_BOT_USERNAME")` wird Parameter `botUsername`. Leerer Bot-Name liefert weiterhin 500 (unverändert).
- `inbound_webhooks.go`: die vier `os.Getenv` (SEVEN_*, STALWART_*) werden Parameter.
- `router.go`: reicht die Config-Werte an die vier Konstruktoren durch.
- Fail-closed bleibt: leerer Wert ⇒ 503 `webhook not configured`.
- SEVEN_*/STALWART_* sind eine begründete Scope-Erweiterung gegenüber dem reinen Telegram-Fall (gleiches Muster in `inbound_webhooks.go`).

## Expected Behavior

- **Input:** Env-Variablen (unpräfixiert, optional mit `GZ_`-Präfix) beim Serverstart; eingehende Webhook-Aufrufe.
- **Output:** Antworten der Webhooks wie bisher (403 / Erfolg / 503).
- **Side effects:** keine. Die Handler lesen zur Laufzeit kein `os.Getenv` mehr.

## Test Plan

Kern-Schicht (Go, deterministisch, ohne Netz, kein Mock-Theater; echter Router und `httptest` erlaubt).

### Automated Tests (TDD RED)

- [ ] Config-Test über `config.Load` (AC-15, AC-16): `internal/config/webhook_secrets_config_test.go`.
- [ ] Route-Test über den echten Router (AC-17, AC-18): `internal/router/webhook_secrets_config_route_test.go`; ohne `os.Setenv`, nur mit Config-Werten.
- [ ] Umstellung der bestehenden Tests von Env-Setzen auf die neuen Signaturen: `telegram_webhook_test.go`, `telegram_webhook_secret_test.go`, `telegram_webhook_secret_forwarding_test.go`, `inbound_webhooks_test.go`, `account_deletion_leftovers_test.go` (alle unter `internal/handler/`).

### Mutationsprobe (Adversary)

Je Mutation muss mindestens ein Test rot werden: Tag falsch geschrieben, `pathSecret` und `signingKey` vertauscht, Durchreichung im Router weggelassen.

### Staging-Nachweis (AC-19)

Nach dem Push gegen `https://staging.gregor20.henemm.com` mit Staging-`.env`: Telegram-, seven.io- UND Stalwart-Webhook mit falschem Secret liefern 403 (nicht 503); zusätzlich funktioniert die Telegram-Verknüpfung (`telegram-link`) weiter.

## Acceptance Criteria

- **AC-15:** Given die Env-Variablen `TELEGRAM_WEBHOOK_SECRET`, `TELEGRAM_BOT_USERNAME`, `SEVEN_WEBHOOK_PATH_SECRET`, `SEVEN_WEBHOOK_SIGNING_KEY`, `STALWART_WEBHOOK_PATH_SECRET`, `STALWART_WEBHOOK_SECRET` sind unpräfixiert gesetzt (wie in den Env-Dateien von Prod und Staging) / When `config.Load` läuft / Then stehen die Werte in den sechs neuen Config-Feldern, und ein `GZ_`-präfixierter Wert hat Vorrang.
  - Test: Config-Test mit gesetzten unpräfixierten und präfixierten Namen; Felder tragen den erwarteten Wert.
- **AC-16:** Given keine der sechs Variablen ist gesetzt (Telegram bewusst nicht konfiguriert) / When der Server startet / Then startet er ohne Fehler, die Felder sind leer.
  - Test: `config.Load` ohne diese Variablen liefert keinen Fehler und leere Felder.
- **AC-17:** Given der echte Router ist mit einem Telegram-Secret aus der Config gebaut / When ein Telegram-Webhook eintrifft / Then antwortet er bei falschem Secret mit 403, bei richtigem Secret mit Erfolg und bei leerem Config-Wert mit 503 (fail-closed bleibt).
  - Test: Route-Test über den echten Router ohne `os.Setenv`, nur mit dem Config-Wert; drei Fälle.
- **AC-18:** Given der echte Router ist mit seven.io- und Stalwart-Werten aus der Config gebaut / When ein seven- oder Stalwart-Webhook eintrifft / Then antwortet er bei falschem Secret mit 403, bei richtigem Secret mit Erfolg und bei leerem Config-Wert mit 503.
  - Test: Route-Tests über den echten Router für seven.io (Pfad-Secret und Signatur) und Stalwart (Pfad-Secret und Secret); je drei Fälle.
- **AC-19:** Given die Änderung ist auf Staging ausgerollt / When der Telegram-, der seven.io- und der Stalwart-Webhook mit falschem Secret aufgerufen werden und die Telegram-Verknüpfung (`telegram-link`) benutzt wird / Then liefern die drei Webhooks je 403 (nicht 503), und die Verknüpfung funktioniert weiter.
  - Test: E2E-Verifikation gegen `https://staging.gregor20.henemm.com` mit Staging-`.env`; Status und Body werden protokolliert.

## Known Limitations

- Ein Tippfehler im `envconfig`-Tag würde auf Prod alle drei Eingänge auf 503 setzen; deshalb sind Route-Test über den echten Router, Config-Test und der Staging-Nachweis für alle drei Eingänge Pflicht.
- `GetTelegramLinkHandler` liefert bei leerem Bot-Namen weiterhin 500 (bewusst unverändert, kein 503).
- Die Login-/Passwort-vergessen-Teile von AC-19 der Mutterspec gehören zu Scheibe 1 (bereits in `main`, PR #2717) und sind hier nicht Teil.
- #2163 bleibt nach dieser Scheibe offen (Scheibe 2: Python-Pfadbauten ohne `VALID_USER_ID_RE`, `.env.tpl`). PR-Text daher „Refs #2715" und „Refs #2163", nie „Closes".

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue; bestätigt ADR-0003 (Mandantentrennung).
- **Rationale:** Reine Verlagerung der Konfigurationsquelle innerhalb bestehender Entscheidungen; Verhalten nach außen unverändert.

## Changelog

- 2026-10-31: Initiale Spec; ACs 15 bis 18 wörtlich aus `auth_haertung_go_2163.md`, AC-19 auf die Webhook-Teile zugeschnitten.

# Context: feat-2715-webhook-secrets-config

## Request Summary
Folgescheibe 1b von #2163 (Epic #2138): Die sechs Webhook-Werte (Telegram, seven.io, Stalwart) kommen über `config.Config` statt per `os.Getenv` in den Handlern. Leerer Wert ⇒ Route antwortet fail-closed 503. ACs: AC-15 bis AC-18 aus `docs/specs/modules/auth_haertung_go_2163.md`, AC-19 (Staging-Nachweis) für die Webhook-Teile.

## Related Files
| File | Relevance |
|------|-----------|
| `internal/config/config.go` | 6 neue Felder (`TelegramWebhookSecret`, `TelegramBotUsername`, `SevenWebhookPathSecret`, `SevenWebhookSigningKey`, `StalwartWebhookPathSecret`, `StalwartWebhookSecret`), `default:""`, unpräfixierter Tag |
| `internal/handler/telegram_webhook.go:44` | `os.Getenv("TELEGRAM_WEBHOOK_SECRET")` → Parameter `secret` |
| `internal/handler/telegram_connect.go:199` | `os.Getenv("TELEGRAM_BOT_USERNAME")` → Parameter `botUsername` |
| `internal/handler/inbound_webhooks.go:101,102,148,149` | vier `os.Getenv` (SEVEN_*, STALWART_*) → Parameter |
| `internal/router/router.go:152,178-186` | reicht die Config-Werte an die Handler durch |
| `internal/handler/{telegram_webhook,telegram_webhook_secret,telegram_webhook_secret_forwarding,inbound_webhooks,account_deletion_leftovers}_test.go` | nutzen `os.Setenv`/`t.Setenv` und die alten Konstruktor-Signaturen, müssen umgestellt werden |
| `scripts/telegram_set_webhook.sh`, `scripts/seven_hooks.sh`, `.env.example` | lesen/dokumentieren dieselben Env-Namen, bleiben unverändert (Env-Namen ändern sich nicht) |

## Existing Patterns
- Vorarbeit fertig im Branch `feat-2163-s1b-webhook-config` (Stand a3f4760e7). Er enthält auch Scheibe 1 (bereits in `main` gemergt, PR #2717). Nur die Punkt-7-Dateien übernehmen, per `git diff main feat-2163-s1b-webhook-config -- <Dateien>`.
- Produktions-Diff im Branch ist klein: config +9, telegram_connect ±4, telegram_webhook ±7, inbound_webhooks ±11, router ±10. Die Abtrennregel (250 Zeilen Produktionscode) wird nicht berührt.
- Test-Zusatz im Branch: `internal/config/webhook_secrets_config_test.go` (122 Zeilen), `internal/router/webhook_secrets_config_route_test.go` (372 Zeilen), dazu Umstellungen in den bestehenden Tests. Das Test-LoC-Budget von 450 aus der Muttersspec gilt für diese Scheibe nicht mehr.
- Muster Fallback: `envconfig` liest `GZ_<NAME>`, dann `<NAME>`; Beispiel `SMTP_HOST` (`config.go:45`).
- Fail-closed bleibt: leerer Wert ⇒ 503 `webhook not configured`. Ausnahme `GetTelegramLinkHandler`: leerer Bot-Name ⇒ 500, unverändert.

## Dependencies
- Upstream: `config.Load` (envconfig v1.4.0), Router-`Deps.Config`.
- Downstream: nur `internal/router/router.go` ruft die vier Konstruktoren produktiv auf; alle anderen Aufrufer sind Tests.
- Betrieb: Prod und Staging setzen die Variablen unpräfixiert in ihren Env-Dateien; die Fallback-Regel hält das kompatibel. Ein Tippfehler im Tag würde auf Prod alle drei Eingänge auf 503 setzen (kein Telegram-/SMS-/Mail-Befehl käme mehr an).

## Existing Specs
- `docs/specs/modules/auth_haertung_go_2163.md`: ACs 15 bis 18, Abtrennregel (Zeile 82), Known Limitations (Zeile 202). Für #2715 braucht es eine eigene Spec `docs/specs/modules/webhook_secrets_config_2715.md`, ACs wörtlich übernommen.
- ADR-0003 (Mandantentrennung): die Webhooks tragen keinen Nutzerbezug, das Secret ist systemweit; kein neuer Nutzer-Endpoint.
- Kontext der Mutter-Scheibe: `docs/context/feat-2163-s1-auth-haertung-go.md`.

## Risks & Considerations
- **Hohes Betriebsrisiko bei falschem Tag oder fehlender Durchreichung:** Webhook liefert 503 statt 403/200. Deshalb Pflicht: Route-Test über den echten Router und Staging-Nachweis (403 bei falschem Secret, nicht 503) für Telegram, seven.io und Stalwart.
- Vierte Funktion `GetTelegramLinkHandler` erhält ebenfalls einen Parameter (Bot-Name); Telegram-Verknüpfung im Frontend darf nicht kaputtgehen (Prüfung `telegram-link` auf Staging).
- Alle vier Kanäle sind gleichrangig (CLAUDE.md): Telegram-, SMS- und Mail-Eingang müssen jeweils geprüft werden, nicht nur einer.
- Tests nicht mit Mock-Theater: Route-Tests laufen über den echten Router, Config-Test über `config.Load`.
- Adversary-Mutationsprobe: Tag falsch schreiben, Parameter vertauschen (pathSecret/signingKey), Durchreichung im Router weglassen. Je Mutation muss ein Test rot werden.
- Python-Core ist nicht betroffen.

## Analysis

### Type
Feature (Folgescheibe 1b von #2163, reine Konfigurations-Umstellung ohne neues Verhalten)

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| internal/config/config.go | MODIFY | 6 neue Felder, `default:""`, unpräfixierter envconfig-Tag (+9) |
| internal/handler/telegram_webhook.go | MODIFY | `os.Getenv` -> Parameter `secret` (±7) |
| internal/handler/telegram_connect.go | MODIFY | `os.Getenv` -> Parameter `botUsername` (±4) |
| internal/handler/inbound_webhooks.go | MODIFY | 4x `os.Getenv` -> Parameter (±11) |
| internal/router/router.go | MODIFY | Config-Werte an die vier Konstruktoren durchreichen (±10) |
| internal/config/webhook_secrets_config_test.go | CREATE | Config-Test über `config.Load` (122 Zeilen, aus Branch) |
| internal/router/webhook_secrets_config_route_test.go | CREATE | Route-Test über echten Router (372 Zeilen, aus Branch) |
| internal/handler/{telegram_webhook,telegram_webhook_secret,telegram_webhook_secret_forwarding,inbound_webhooks,account_deletion_leftovers}_test.go | MODIFY | Env-Setzen -> neue Signaturen |
| docs/specs/modules/webhook_secrets_config_2715.md | CREATE | eigene Spec, ACs 15-18 wörtlich aus Muttersspec, AC-19 für Webhook-Teile |

### Scope Assessment
- Files: ca. 5 Produktion + 2 neue Tests + 5 umgestellte Tests + 1 Spec
- Estimated LoC: Produktion ca. +25/-15 (Branch-Diff geprüft: 41 Zeilen, unter 250), Tests ca. +500
- Risk Level: MEDIUM (kleiner Diff, aber Fehler = alle drei Eingänge liefern 503)

### Technical Approach
Vorarbeit aus Branch `feat-2163-s1b-webhook-config` (a3f4760e7) übernehmen, nur Punkt-7-Dateien per `git diff main <branch> -- <Dateien>`. Kein Neuentwurf. Fail-closed 503 bleibt, `GetTelegramLinkHandler` bleibt bei 500 für leeren Bot-Namen. Env-Namen und Skripte (`scripts/*.sh`, `.env.example`) unverändert.
Pflicht-Nachweise: Route-Test über echten Router (403/Erfolg/503), Config-Test über `config.Load`, Staging-Nachweis für Telegram, seven.io UND Stalwart (403, nicht 503) sowie `telegram-link`. Adversary-Mutationen: Tag falsch, pathSecret/signingKey vertauscht, Durchreichung weglassen.

### Dependencies
Upstream `config.Load` (envconfig v1.4.0), Router-`Deps.Config`. Downstream nur `router.go` produktiv. Python-Core nicht betroffen.

### Open Questions
- [ ] Keine fachlichen. Spec ist eigene Datei; Test-LoC-Budget 450 der Muttersspec gilt hier nicht mehr (in der neuen Spec festhalten).

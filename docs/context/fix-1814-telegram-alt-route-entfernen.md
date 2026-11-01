# Context: fix-1814-telegram-alt-route-entfernen

## Request Summary
Folge-Scheibe von #1814 (Scheibe 1 ist live, PR #2638): die Alt-Route `POST /api/webhooks/telegram/{secret}` entfernen und danach das Telegram-Webhook-Secret auf beiden Umgebungen rotieren, weil das alte Secret im URL-Pfad lag. Der bisherige Kontext steht in `docs/context/fix-1814-telegram-webhook-header.md`.

## Ausgangslage (belegt)
- Go-Handler liest den URL-Pfad **nie**; einziger Auth-Träger ist der Header `X-Telegram-Bot-Api-Secret-Token` (`internal/handler/telegram_webhook.go`). Die Alt-Route ist funktional nur ein zweiter Eingang auf denselben Handler.
- `internal/router/router.go:179-180` registriert beide Routen mit demselben Handler (`/inbound` statisch, `{secret}` als Übergang).
- Beide Bots sind laut Issue-Kommentar umregistriert (URL endet auf `/inbound`, `last_error_message` leer, AC-7). **Nicht bewiesen** (AC-8): Zustellung durch Telegram selbst an die neue URL. Ein Handy-Nachtest steht aus. In den Journalen der letzten 3 Tage (gregor-api, gregor-api-staging) fand sich keine Telegram-Zeile; ein Zugriffslog-Beleg fehlt damit.

## Related Files
| File | Relevanz |
|------|----------|
| `internal/router/router.go:176-180` | Alt-Route entfernen, Kommentar anpassen |
| `internal/handler/telegram_webhook.go` | Kopfkommentar „Übergang" bereinigen |
| `internal/router/telegram_webhook_inbound_route_test.go` | Tests `..BeideRoutenGleich`, `..GleicherStatusWieAltRoute`, `TestTelegramInbound_AltRoute_BleibtErreichbar` müssen umgedreht werden (Alt-Route → 404/405, `/inbound` bleibt) |
| `internal/router/webhook_secrets_config_route_test.go` | nutzt `/inbound`, voraussichtlich unberührt |
| `internal/middleware/auth.go:62` | Public-Allowlist per **Präfix** `/api/webhooks/telegram/`; Präfix muss bleiben (`/inbound`). Beobachtung: nach Entfernung bleibt ein unbekannter Pfad unter dem Präfix öffentlich, liefert aber 404 |
| `internal/handler/staging_verify_token.go:17` | erwähnt das Präfix, nur Kommentar |
| `internal/scheduler/scheduler.go:348` | Kommentar nennt `{secret}`-Route |
| `.claude/tools/staging_messlauf.py:79` | `WEBHOOK_PFAD = /api/webhooks/telegram/messlauf` ruft die Alt-Route auf. **Bricht nach Entfernung** (404) und muss auf `/inbound` |
| `tests/tdd/test_staging_messlauf.py:722,1067,1312` | Fake-Welt und Endpunkt-Allowlist erwarten `/api/webhooks/telegram/[^/]+`; passt auch auf `/inbound`, Messlauf-Pfad trotzdem anpassen |
| `scripts/telegram_set_webhook.sh`, `tests/tdd/test_telegram_set_webhook_url.py` | registrieren bereits `/inbound`; `ALT_URL` in den Tests prüft nur die Erkennung einer Alt-Registrierung |
| `docs/reference/api_contract.md:287-288`, `telegram_format.md:52-54`, `sms_format.md:74`, `docs/features/architecture.md:84,280` | Doku „Alt-Route nur Übergang" bereinigen |
| `docs/specs/modules/fix_1814_telegram_webhook_secret_nicht_im_pfad.md` | bestehende Spec mit Scheibe 1; Folge-Scheibe als eigene Spec oder Ergänzung |
| `/home/hem/henemm-infra/nginx/gregor20.henemm.com.conf:19`, `staging.gregor20.henemm.com.conf:26` | `location /api/webhooks/telegram/` (Präfix, IP-Allowlist + Rate-Limit); bleibt gültig. `conf.d/gregor-staging-webhook-logging.conf` redigiert den Pfad (`[redacted]`) |
| Secret: `TELEGRAM_WEBHOOK_SECRET` | Go-Config (`TelegramWebhookSecret`, #2715) und Python (`api/routers/webhook.py:73`, zweite Prüfung) lesen **denselben** Wert, beide Prozesse je Umgebung neu starten |

## Existing Patterns
- Webhook-Secrets laufen seit #2715 über `config.Config`, fail-closed bei leerem Secret (503).
- Registrierung/Prüfung per `scripts/telegram_set_webhook.sh` (`set` und `info`), gibt weder Secret noch rohe `getWebhookInfo`-Antwort aus.
- Mutationsprobe per String-Ersetzung nach `implementation-validator.md`.

## Dependencies / Dependents
- Upstream: Telegram-Server (feste IP-Ranges), nginx (IP-Allowlist), Go-Config, Python-Core `/api/internal/telegram-webhook`.
- Downstream: Telegram-Befehle aller Nutzer (Kanal-Parität), Staging-Messlauf-Werkzeug, Prod-Selftest.

## Risiken
1. **Vorbedingung offen:** Entfernen und Rotieren dürfen erst folgen, wenn belegt ist, dass Telegram wirklich an `/inbound` zustellt (sonst fällt der Telegram-Eingang still aus; Kanal-Parität). Belegmöglichkeiten für die Spec: `getWebhookInfo` (`pending_update_count`, `last_error_*`, `last_synchronization_error_date`) und ein echter Befehl über den Bot. Ein Handy-Test ist nötig, wenn der Zugriffslog nichts hergibt.
2. **Rotation ist ein Zwei-Schritt:** Secret in ENV beider Prozesse (Go + Python) und per `setWebhook secret_token` bei Telegram gleichzeitig tauschen. Dazwischen liegt ein Fenster mit 403. Reihenfolge und Fenster müssen in der Spec stehen.
3. **Prod vs. Staging:** Das Issue nennt Prod als bereits header-basiert; ob das Prod-Secret jemals im Pfad lag, ist zu klären (Skript-Historie, `ALT_URL`). Das entscheidet, ob Prod-Rotation nötig ist oder nur Staging.
4. Staging-Messlauf-Werkzeug und seine Tests hängen an der Alt-Route.
5. `Co-Existenz`: Präfix-Allowlist in `auth.go` lässt unbekannte Unterpfade unauthentifiziert durch; harmlos (404), aber zu notieren.

## Analysis

### Type
Feature/Sicherheits-Nacharbeit (Folge-Scheibe 2 von #1814, kein Bug im Nutzerverhalten)

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| internal/router/router.go | MODIFY | Zeile `/api/webhooks/telegram/{secret}` entfernen, Kommentar anpassen |
| internal/handler/telegram_webhook.go | MODIFY | Kopfkommentar „Übergang" bereinigen |
| internal/scheduler/scheduler.go, internal/handler/staging_verify_token.go | MODIFY | nur Kommentar (`{secret}`-Erwähnung) |
| internal/router/telegram_webhook_inbound_route_test.go | MODIFY | Alt-Route-Tests umdrehen (Alt-Pfad → 404/405, `/inbound` unverändert) |
| .claude/tools/staging_messlauf.py, tests/tdd/test_staging_messlauf.py | MODIFY | `WEBHOOK_PFAD` von `/telegram/messlauf` auf `/telegram/inbound` |
| docs/reference/api_contract.md, telegram_format.md, sms_format.md, docs/features/architecture.md | MODIFY | „Alt-Route nur Übergang" streichen |
| docs/specs/modules/fix_1814_...md | MODIFY | Scheibe 2 mit ACs ergänzen |
| Secret `TELEGRAM_WEBHOOK_SECRET` (Prod + Staging, Go + Python) | OPS | Rotation, kein Code |

### Belegte Befunde (Phase 2)
- Prod-Journal der letzten 7 Tage: **keine einzige** Telegram-Zustellung an `/inbound` (nur Selftest-403 vom 29.10. von 127.0.0.1). Die Zustellung durch Telegram selbst ist also weiterhin unbewiesen; `last_error_*` leer heißt nur „kein Fehler", nicht „zugestellt".
- Auth liest den Pfad nie → Entfernen der Alt-Route ändert für Telegram nichts, **sofern** die Registrierung wirklich auf `/inbound` steht.

### Scope Assessment
- Files: ~10 Code/Test/Doku (+ Ops-Rotation)
- Estimated LoC: +40/-60
- Risk Level: MEDIUM (Code trivial; Risiko liegt im stillen Ausfall des Telegram-Eingangs, wenn Reihenfolge falsch)

### Technical Approach
Reihenfolge mit harten Vorbedingungen (jeweils Gate in der Spec):
1. **Vorbedingung Zustellbeweis:** je Umgebung ein echter Befehl über den Bot (Handy) → Beleg im Go-Journal (`POST …/telegram/inbound … 200` von Telegram-IP) bzw. `pending_update_count=0`. Ohne Beleg kein Schritt 2.
2. Code: Alt-Route entfernen, Tests zuerst rot (Alt-Pfad liefert heute 200/403 statt 404), Messlauf-Werkzeug auf `/inbound`.
3. Deploy Staging → `/e2e-verify` → Prod.
4. **Rotation je Umgebung** (Staging zuerst): neues Secret erzeugen → ENV von Go UND Python tauschen → beide Dienste neu starten → direkt `telegram_set_webhook.sh set` (Fenster mit 403 nur Sekunden) → `info` (ja/nein) → Test-Befehl. Secret nie in Logs/Chat.
5. Prod-Rotation nur, falls das Prod-Secret je im Pfad lag (Skript-Historie/`ALT_URL` in Spec klären); sonst begründet überspringen.

### Dependencies
Telegram-Server (feste IP-Ranges) → nginx (Präfix `/api/webhooks/telegram/`, bleibt) → Go (`config.TelegramWebhookSecret`) → Python `api/routers/webhook.py:73` (zweite Prüfung, selber Wert). `auth.go:62` Präfix-Allowlist bleibt; unbekannte Unterpfade bleiben öffentlich, liefern aber 404 (harmlos, in Spec notieren).

### Open Questions
- [ ] Handy-Nachtest je Bot (Prod + Staging) nötig, solange das Journal keine Telegram-Zustellung zeigt — PO-Handlung, Claude gibt exakten Satz vor.
- [ ] Lag das Prod-Secret jemals im Pfad? (Git-Historie von `telegram_set_webhook.sh` prüfen, in Phase 3 klären)

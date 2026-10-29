# Context: fix-1814-telegram-webhook-header

## Request Summary
#1814 (Red-Team-Finding henemm-security#221): Staging-Telegram-Webhook trägt das Secret im URL-Pfad. Vorschlag im Ticket: „Staging analog Prod auf Header-Secret umstellen".

## Kernbefund (Ticket-Prämisse ist teils falsch)
- **Die Authentifizierung läuft schon auf BEIDEN Umgebungen über den Header** `X-Telegram-Bot-Api-Secret-Token` (`internal/handler/telegram_webhook.go:48`, Konstantzeit-Vergleich; Python prüft zusätzlich, #2142).
- **Das Secret steht trotzdem auf BEIDEN Umgebungen im Pfad:** `scripts/telegram_set_webhook.sh:45` registriert `…/api/webhooks/telegram/${TELEGRAM_WEBHOOK_SECRET}` bei Telegram. Prod ist also nicht „bereits umgestellt" — es hat nur die IP-Allowlist/Redaktion.
- Das Pfadsegment `{secret}` wird vom Handler **nie gelesen** (`router.go:171`). Es ist rein dekorativ, trägt aber den echten Secret-Wert in Telegram-Konfiguration, ggf. Proxy-/Telegram-Logs.

## Related Files
| File | Relevanz |
|------|----------|
| `scripts/telegram_set_webhook.sh:45-46` | baut die Registrier-URL mit Secret im Pfad — Hauptursache |
| `internal/router/router.go:171` | Route `/api/webhooks/telegram/{secret}`; Param ungenutzt |
| `internal/handler/telegram_webhook.go` | Header-Prüfung, Doku-Kommentar nennt Pfad „Defense-in-Depth" |
| `internal/middleware/auth.go:62` | sitzungsfreie Präfix-Ausnahme `/api/webhooks/telegram/` (Slash am Ende!) |
| `internal/handler/telegram_webhook_test.go`, `telegram_webhook_secret_test.go`, `telegram_webhook_secret_forwarding_test.go` | Tests rufen `/…/whatever` bzw. `/…/x` auf |
| `.claude/tools/staging_messlauf.py:79`, `tests/tdd/test_staging_messlauf.py:722,1067,1312` | Messlauf kennt Pfad `/api/webhooks/telegram/<seg>`; Regex `[^/]+` |
| `docs/runbooks/telegram-webhook.md`, `docs/reference/api_contract.md:270`, `telegram_format.md:50`, `architecture.md:84,279`, `sms_format.md:72`, Spec `telegram_webhook_inbound.md` | beschreiben `{secret}`-Pfad |
| `/home/hem/henemm-infra/nginx/{gregor20,staging.gregor20}.henemm.com.conf` | `location /api/webhooks/telegram/` (Präfix) — matcht auch einen secretfreien Pfad unter diesem Präfix; Staging-Kommentar „Secret steckt im Pfad" veraltet |
| `/home/hem/henemm-infra/nginx/conf.d/gregor-staging-webhook-logging.conf` | Log-Redaktion des Pfad-Secrets; bleibt als Altlast-Schutz sinnvoll |

## Existing Patterns
- `POST /api/webhooks/sms/{secret}` und `…/mail/{secret}` (#2439) nutzen ebenfalls Secret-im-Pfad — **eigene Prüfung nötig**, ob dort der Pfad der echte Auth-Träger ist (Stalwart/seven.io können keine Header setzen). Außerhalb dieses Tickets; nicht anfassen.
- chi: statische Route schlägt Param-Route. Eine neue statische Route `/api/webhooks/telegram/inbound` würde die alte `{secret}`-Route nicht verdrängen; `…/inbound` matcht heute sogar schon über `{secret}`.

## Dependencies
- Upstream: Telegram `setWebhook` (Bot-Token Prod/Staging getrennt), `TELEGRAM_WEBHOOK_SECRET` (Go-ENV).
- Downstream: nginx-Location (Präfix `/api/webhooks/telegram/` mit Slash — ein Pfad ohne Slash am Ende würde NICHT matchen), AuthMiddleware-Präfix, Staging-Messlauf.

## Lösungsrichtung (für /20-analyse)
1. Registrier-URL ohne Secret: festes Segment (z. B. `/api/webhooks/telegram/inbound`), Präfix bleibt ⇒ nginx und AuthMiddleware brauchen keine Änderung.
2. Router: statische Route ergänzen; alte `{secret}`-Route als Übergang erhalten, bis beide Umgebungen neu registriert sind, dann entfernen (kein 404 für Telegram, kein Update-Verlust).
3. Skript, Runbook, api_contract, Spec anpassen; Test, dass Skript kein Secret in die URL schreibt.
4. Betrieb: `set` auf Staging UND Prod ausführen, `info` prüfen (Ausgabe enthält die URL — nicht ins Ticket kopieren). Danach Secret rotieren, weil das alte im Pfad lag und ggf. geloggt wurde.

## Risks & Considerations
- **Prod-Webhook kappen:** vorzeitiges Entfernen der alten Route ⇒ Telegram-Befehle fallen still aus. Reihenfolge zwingend: neue Route live → neu registrieren → verifizieren → alte Route raus.
- **Nutzer-Befehle über echten Eingang** testen (Staging-Bot), nicht nur Handler-Unittest.
- Zwei-Nutzer-Test hier nicht einschlägig (kein nutzerbezogener Datenpfad); der Webhook trägt keine user_id im Pfad.
- Ticket-Titel/Prämisse korrigieren (Prod betroffen, nicht nur Staging); Ticket als Kommentar nachführen.
- Live-Stand der Registrierung (`getWebhookInfo`) nicht geprüft; Ausgabe enthält das Secret → nur ausgewertet, nie ausgegeben.

## Analysis

### Type
Bug (Sicherheits-Härtung, strukturell). Ticket-Prämisse korrigiert: Header-Auth läuft auf Staging UND Prod; das Secret steht auf BEIDEN im Pfad der bei Telegram registrierten URL.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| scripts/telegram_set_webhook.sh | MODIFY | Registrier-URL ohne Secret: `/api/webhooks/telegram/inbound` |
| internal/router/router.go | MODIFY | statische Route `/api/webhooks/telegram/inbound` ergänzen; `{secret}`-Route als Übergang behalten |
| internal/handler/telegram_webhook.go | MODIFY | Doku-Kommentar (Pfad ist nicht Auth-Träger) |
| tests/tdd/test_telegram_set_webhook_url.py | CREATE | Skript schreibt kein Secret in die URL |
| internal/handler/telegram_webhook_*_test.go | MODIFY | Fall für `/inbound` ergänzen |
| docs/runbooks/telegram-webhook.md, docs/reference/api_contract.md, telegram_format.md, architecture.md, Spec telegram_webhook_inbound.md | MODIFY | `{secret}` → `inbound` |
| henemm-infra nginx Staging-Kommentar | MODIFY (infra-Instanz) | veralteter Kommentar „Secret steckt im Pfad" |

### Scope Assessment
- Files: ca. 6 Code/Test + Docs
- Estimated LoC: +60/-15 (ohne Docs)
- Risk Level: MEDIUM — Fehlreihenfolge kappt Telegram-Befehle auf Prod still

### Technical Approach
1. Neue statische Route `/inbound` (gleicher Handler); Präfix bleibt ⇒ nginx und AuthMiddleware unverändert.
2. Skript registriert die secretfreie URL; Test beweist das.
3. Betrieb in zwingender Reihenfolge: Route live (Staging, dann Prod) → `set` → `info` auswerten (nie ausgeben) → Befehl über echten Staging-Bot → alte `{secret}`-Route entfernen (Folge-Scheibe, nach beiden Umgebungen) → Secret rotieren (lag im Pfad, ggf. geloggt).
4. Ticket per Kommentar korrigieren. SMS/Mail-Webhooks (#2439) bleiben unberührt.

### Dependencies
Telegram setWebhook (Bot-Token je Umgebung), `TELEGRAM_WEBHOOK_SECRET`, nginx-Präfix mit Slash, AuthMiddleware-Präfix, Staging-Messlauf (`.claude/tools/staging_messlauf.py:79`, Regex `[^/]+` passt auf `inbound`).

### Open Questions
- [ ] Rotation + Entfernen der Alt-Route im selben Ticket (empfohlen, themenweise abschließen) — Betrieb auf Prod braucht Abstimmung mit laufender Tour-Phase.

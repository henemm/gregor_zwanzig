---
entity_id: fix_1814_telegram_webhook_secret_nicht_im_pfad
type: module
created: 2026-10-29
updated: 2026-10-29
status: draft
version: "1.0"
tags: [telegram, webhook, security, hardening, secret]
---

# Telegram-Webhook: Secret nicht mehr im URL-Pfad (Issue #1814)

## Approval

- [ ] Approved

## Purpose

Das Webhook-Secret steht heute im Pfad der bei Telegram registrierten URL
(`/api/webhooks/telegram/<SECRET>`) und damit in der Telegram-Konfiguration
sowie potenziell in Proxy- und Telegram-Logs. Die Authentifizierung läuft
bereits über den Header `X-Telegram-Bot-Api-Secret-Token`; der Pfadanteil
wird vom Handler nie gelesen. Diese Spec entfernt das Secret aus der
registrierten URL, ohne den laufenden Telegram-Eingang zu unterbrechen.

Korrektur der Ticket-Prämisse: Nicht nur Staging ist betroffen. Header-Auth
gilt auf Staging und Prod, das Secret steht aber auf beiden im Pfad, weil
`scripts/telegram_set_webhook.sh` es so registriert.

## Source

- **Go-Router:** `internal/router/router.go` (Route `/api/webhooks/telegram/{secret}`, Zeile ~171) — Identifier: Webhook-Route-Registrierung
- **Go-Handler:** `internal/handler/telegram_webhook.go` — nur Doku-Kommentar (Pfad ist nicht Auth-Träger)
- **Setup-Skript:** `scripts/telegram_set_webhook.sh` (Zeile ~45) — Identifier: Aufbau der Registrier-URL
- **Unverändert (Präfix-Treffer):** `internal/middleware/auth.go` (Ausnahme `/api/webhooks/telegram/`), nginx-Location `/api/webhooks/telegram/` in `henemm-infra`
- **Schicht:** Go-API und Betriebsskript. Python-Core unverändert (prüft den Header weiter, #2142).

## Estimated Scope

- **LoC:** ca. +60/-15 (ohne Docs und Tests der Doku-Dateien)
- **Files:** ca. 6 Code-/Test-Dateien plus Docs (Runbook, api_contract, telegram_format, architecture, Spec `telegram_webhook_inbound.md`)
- **Effort:** low bis medium (Risiko MEDIUM wegen Betriebsreihenfolge)

## Scope / Nicht-Scope

**Im Scope (diese Scheibe):**
- Neue statische Route `POST /api/webhooks/telegram/inbound` mit demselben Handler.
- `telegram_set_webhook.sh` registriert die secretfreie URL und gibt das Secret nirgends aus.
- Alte Route `/api/webhooks/telegram/{secret}` bleibt vorerst als Übergang bestehen.
- Doku-Anpassungen (`{secret}` wird zu `inbound`), Doku-Kommentar im Handler.

**Folge-Scheibe im selben Ticket (nach Neuregistrierung beider Umgebungen):**
- Alte `{secret}`-Route entfernen, danach Secret rotieren (altes lag im Pfad und ist ggf. geloggt). Das Ticket wird erst geschlossen, wenn beides erledigt ist.

**Ausdrücklich außerhalb des Scopes:**
- SMS- und Mail-Webhooks (`/api/webhooks/sms/{secret}`, `/api/webhooks/mail/{secret}`, #2439): Dort kann der Absender (seven.io, Stalwart) keine Header setzen, der Pfad ist womöglich der echte Auth-Träger. Eigene Prüfung nötig, nicht anfassen.
- Staging-nginx-Kommentar „Secret steckt im Pfad" (veraltet): gehört der `infra`-Instanz, hier nur Hinweis per Nachricht an `infra`. Die nginx-Location (Präfix mit Slash) matcht `/inbound` bereits; keine nginx-Änderung nötig. Die Log-Redaktion bleibt als Altlast-Schutz bestehen.

## Mandantentrennung / Kanäle / Pendant

- **Zwei-Nutzer-Test nicht einschlägig:** Der Webhook trägt keine `user_id` im Pfad und bewegt keine Nutzerdaten in diesem Baustein; die Zuordnung Chat zu Nutzer geschieht unverändert im Handler/Python-Core hinter der Secret-Prüfung. Es ändert sich nur die Adresse, nicht der Datenpfad.
- **Kanäle:** Betroffen ist nur der Telegram-Eingang; Briefing- und Alarm-Inhalte bleiben unverändert.
- **Trip/Ortsvergleich-Teilung:** nicht einschlägig (kein UI-Baustein).

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| Telegram `setWebhook` / `getWebhookInfo` | extern | Registrierung je Umgebung (Bot-Token Prod/Staging getrennt) |
| `TELEGRAM_WEBHOOK_SECRET` | ENV (Go) | Header-Vergleich, Konstantzeit |
| nginx `location /api/webhooks/telegram/` | Infra | Präfix matcht `/inbound` ohne Änderung |
| `AuthMiddleware`-Präfixausnahme | Go | sitzungsfreier Zugang für `/api/webhooks/telegram/` |
| `.claude/tools/staging_messlauf.py` | Tooling | Pfad-Regex `[^/]+` passt auf `inbound` |

## Implementation Details

```
router.go:
  r.Post("/api/webhooks/telegram/inbound", telegramWebhookHandler)   // neu, statisch
  r.Post("/api/webhooks/telegram/{secret}", telegramWebhookHandler)  // Übergang, bleibt
  (chi: statische Route hat Vorrang vor Param-Route)

telegram_set_webhook.sh:
  WEBHOOK_URL="${PUBLIC_BASE}/api/webhooks/telegram/inbound"
  setWebhook(url=WEBHOOK_URL, secret_token=$TELEGRAM_WEBHOOK_SECRET)
  Ausgabe: weder Secret noch eine URL mit Secret; getWebhookInfo wird
  nicht roh ausgegeben.

Betriebsreihenfolge (zwingend):
  1. Merge + Deploy: Route /inbound live (Staging, dann Prod)
  2. set auf Staging; set auf Prod
  3. info je Umgebung auswerten (nur ausgewertet, Ausgabe enthält die URL
     und wird nicht ins Ticket kopiert): URL endet auf /inbound, kein Secret
  4. Befehl über den echten Staging-Bot senden, Antwort kommt an
  5. Folge-Scheibe: Alt-Route entfernen
  6. Secret rotieren (ENV + set neu auf beiden Umgebungen)
```

Wichtig: Die Alt-Route darf nie vor Schritt 3 für beide Umgebungen entfernt werden, sonst fallen Telegram-Befehle still aus (kein 404-Hinweis an den Nutzer).

## Expected Behavior

- **Input:** `POST /api/webhooks/telegram/inbound` mit Header `X-Telegram-Bot-Api-Secret-Token` und Telegram-Update-Body.
- **Output:** wie bisher: 200 bei korrektem Header, Ablehnung (401/403, wie heute implementiert) bei fehlendem oder falschem Header.
- **Side effects:** Telegram-Registrierung enthält künftig kein Secret mehr im Pfad.

## Acceptance Criteria

- **AC-1:** Given das Skript `telegram_set_webhook.sh` mit gesetztem `TELEGRAM_WEBHOOK_SECRET` und einer Testumgebung / When es die Webhook-URL für `setWebhook` aufbaut / Then endet die URL auf `/api/webhooks/telegram/inbound` und enthält den Secret-Wert an keiner Stelle (weder Pfad noch Query).
  - Test: `tests/tdd/test_telegram_set_webhook_url.py` führt das Skript mit Stub-`curl` (aufgezeichnete Argumente) aus und prüft die tatsächlich übergebene URL und das `secret_token`-Feld.

- **AC-2:** Given das Skript wird mit einem eindeutigen Test-Secret ausgeführt / When die Konsolenausgabe (stdout und stderr) betrachtet wird / Then kommt das Secret darin nicht vor und es wird keine URL mit Secret ausgegeben.
  - Test: `tests/tdd/test_telegram_set_webhook_url.py` sucht den Test-Secret-Wert in der gesamten Ausgabe; Treffer ist ein Fehler.

- **AC-3:** Given die Go-API läuft mit gesetztem `TELEGRAM_WEBHOOK_SECRET` / When Telegram per `POST /api/webhooks/telegram/inbound` mit korrektem Header `X-Telegram-Bot-Api-Secret-Token` ein Update sendet, ohne Sitzungs-Cookie / Then antwortet die API mit 200 und das Update wird wie bisher an den Python-Core weitergereicht.
  - Test: Go-Testfall im Handler-/Router-Test über den echten Router inklusive `AuthMiddleware` (nicht nur Handler direkt); der Weiterreichungs-Mock sieht genau ein Update.

- **AC-4:** Given dieselbe Konfiguration / When ein `POST` an `/api/webhooks/telegram/inbound` ohne Header oder mit falschem Header eingeht / Then wird er mit demselben Status abgelehnt wie bisher auf der Alt-Route und es wird nichts an den Python-Core weitergereicht.
  - Test: Go-Testfälle für fehlenden und falschen Header auf `/inbound`; Statuscode identisch zur Alt-Route (gleiche Erwartung in beiden Fällen).

- **AC-5:** Given die Übergangszeit, in der Telegram noch die alte URL kennt / When ein `POST /api/webhooks/telegram/<beliebiges-Segment>` mit korrektem Header eingeht / Then antwortet die API weiterhin mit 200, es entsteht kein 404 und kein Update-Verlust.
  - Test: bestehende Go-Testfälle (`/…/whatever`, `/…/x`) bleiben unverändert grün; die statische Route `/inbound` verdrängt die Param-Route nicht für andere Segmente.

- **AC-6:** Given zwei verschiedene Nutzer haben je einen verknüpften Telegram-Chat / When beide nacheinander einen Befehl über `/inbound` senden / Then wird jeder Befehl dem richtigen Nutzer zugeordnet wie über die Alt-Route (keine Verschiebung der Zuordnung durch die neue Adresse).
  - Test: Go-Testfall, der die Zuordnung an den Core-Aufruf weiterreicht und für beide Routen dieselbe `chat`-Zuordnung prüft. Dient als Regressionsnachweis; die Zuordnung selbst ist unverändert (siehe Abschnitt Mandantentrennung).

- **AC-7:** Given beide Umgebungen wurden nach dem Deploy neu registriert / When `getWebhookInfo` je Umgebung ausgewertet wird (ohne die URL auszugeben) / Then endet die registrierte URL auf `/inbound`, enthält kein Secret, und `last_error_message` ist leer.
  - Test: Betriebsnachweis im Deploy-Schritt (Auswertung per Skript, Ausgabe nur ja/nein), nicht im Kern-Testlauf.

- **AC-8:** Given der echte Staging-Bot ist auf `/inbound` registriert / When ein Nutzer einen Telegram-Befehl an diesen Bot sendet / Then kommt die Antwort des Systems im Chat an.
  - Test: Live-E2E über den echten Eingang (Staging-Bot) im `/e2e-verify`, nicht nur Handler-Unittest.

- **AC-9:** Given die Doku (Runbook, api_contract, telegram_format, architecture, Spec `telegram_webhook_inbound.md`) / When der Telegram-Webhook beschrieben wird / Then nennt sie als registrierte URL `/api/webhooks/telegram/inbound`, benennt den Header als einzigen Auth-Träger und markiert den `{secret}`-Pfad als Übergang.
  - Test: `# doc-compliance-test`, nur Doku-Konsistenz, kein Verhaltensnachweis.

## Geplante Tests

- **CREATE** `tests/tdd/test_telegram_set_webhook_url.py` (AC-1, AC-2): Skript mit Stub-`curl`, prüft übergebene URL und Ausgabe. Mutation zur Gegenprobe: Secret wieder in die URL einsetzen muss den Test rot machen.
- **MODIFY** `internal/handler/telegram_webhook_test.go`, `telegram_webhook_secret_test.go`, `telegram_webhook_secret_forwarding_test.go` (AC-3 bis AC-6): Fälle für `/inbound` ergänzen, mindestens einer über den echten Router mit `AuthMiddleware` (Wirkungsort der Zusicherung: sitzungsfreier Zugang).
- Live-E2E (AC-7, AC-8) in `/e2e-verify` gegen Staging; Prod-Auswertung im Deploy.

## Known Limitations

- In der Übergangszeit akzeptiert die Alt-Route weiterhin jedes Segment; das ist unkritisch, weil die Header-Prüfung greift.
- Bis zur Rotation (Folge-Scheibe) bleibt das alte Secret gültig, obwohl es in früheren Logs stehen kann.
- Das Secret in `getWebhookInfo` der vor der Neuregistrierung gesetzten URL bleibt bis zum `set` sichtbar; Ausgaben nie ins Ticket kopieren.
- Betrieb auf Prod: Während laufender Trips wird normal ausgeliefert; die Reihenfolge oben verhindert einen Ausfall des Eingangs.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Härtung einer Adresse bei unveränderter Auth-Entscheidung (Header-Secret, bereits dokumentiert). Keine Grundsatzänderung an Kanälen, Provider, Datenmodell oder Auth.

## Changelog

- 2026-10-29: Initial spec created (Issue #1814, Phase 3)

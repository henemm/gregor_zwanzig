---
entity_id: fix_1814_s2_telegram_alt_route_entfernen
type: module
created: 2026-11-01
updated: 2026-11-01
status: draft
version: "1.0"
tags: [telegram, webhook, security, hardening, secret, rotation]
---

# Telegram-Webhook Scheibe 2: Alt-Route entfernen und Secret rotieren (Issue #1814)

## Approval

- [ ] Approved

## Purpose

Scheibe 1 (`fix_1814_telegram_webhook_secret_nicht_im_pfad`) hat die secretfreie Route `POST /api/webhooks/telegram/inbound` eingeführt und die Alt-Route `/api/webhooks/telegram/{secret}` als Übergang belassen. Diese Scheibe entfernt die Alt-Route und rotiert danach das Secret auf Staging und Prod, weil das alte Secret im URL-Pfad lag und ggf. in Logs steht. Das Ticket #1814 ist erst damit erledigt.

Belegt (nicht erneut offen): Das Prod-Secret lag ebenfalls im Pfad, denn `scripts/telegram_set_webhook.sh` registrierte seit #637 (Commit `2a1be1e95`) beide Umgebungen so; erst Scheibe 1 (Commit `566a046fe`) hat das geändert. Die Prod-Rotation ist deshalb nötig.

## Source

- **Go-Router:** `internal/router/router.go:178-180` (Alt-Route Zeile 180 entfernen; Kommentar bei Zeile ~176 anpassen)
- **Kommentare bereinigen:** `internal/handler/telegram_webhook.go` (Kopf „Übergang"), `internal/scheduler/scheduler.go:~348` (nennt `{secret}`), `internal/handler/staging_verify_token.go:~17`
- **Tests:** `internal/router/telegram_webhook_inbound_route_test.go` (Zeilen 71, 97, 115)
- **Werkzeug:** `.claude/tools/staging_messlauf.py:79` (`WEBHOOK_PFAD`), `tests/tdd/test_staging_messlauf.py` (~722, 1067, 1312; Kopfdoc Z.30 nennt `{secret}`)
- **Unverändert:** `internal/middleware/auth.go:62` (Präfix `/api/webhooks/telegram/`), nginx-Location, `scripts/telegram_set_webhook.sh` (registriert bereits `/inbound`)
- **Schicht:** Go-API, Betriebsrotation (ENV Go + Python), Tooling, Doku. Python-Core-Code unverändert (`api/routers/webhook.py:~73` prüft denselben Secret-Wert ein zweites Mal).

## Estimated Scope

- **LoC:** ca. +40/-60
- **Files:** ca. 10 (Code/Test/Tooling/Doku) plus Ops-Rotation
- **Effort:** low (Code), medium (Betriebsreihenfolge)

## Scope / Nicht-Scope

**Im Scope:** Alt-Route entfernen, Tests umdrehen, Messlauf-Werkzeug auf `/inbound`, Doku bereinigen, Zustellbeweis und Rotation je Umgebung als Betriebsschritte.

**Nicht im Scope:**
- SMS-/Mail-Webhooks (`/api/webhooks/sms/{secret}`, `/mail/{secret}`): dort ist das Secret im Pfad womöglich der echte Auth-Träger (Ticket #2439).
- nginx-Kommentare und -Konfiguration: gehören der Instanz `infra`.
- Auth-Präfix `/api/webhooks/telegram/` in `auth.go` und nginx bleiben (`/inbound` braucht ihn). Beobachtung: unbekannte Unterpfade bleiben dadurch unauthentifiziert erreichbar, liefern aber nach der Entfernung 404/405 und erreichen keinen Handler.

## Mandantentrennung / Kanäle / Pendant

- **Mandantentrennung:** Zwei-Nutzer-Test für die Adresse nicht einschlägig (kein `user_id` im Pfad). Die Zuordnung Chat zu Nutzer bleibt aber Regressionsfall: ein Test mit zwei Nutzern über `/inbound` (AC-5).
- **Kanäle:** Nur der Telegram-Eingang ist betroffen; Briefing- und Alarminhalte unverändert. **Hauptrisiko ist stiller Ausfall**: Fehlt die Zustellung an `/inbound`, bekommt der Nutzer keinen 404-Hinweis, seine Befehle laufen ins Leere. Deshalb die harten Gates unten (Kanalparität, alle vier Kanäle gleichrangig).
- **Trip/Ortsvergleich-Teilung:** nicht einschlägig (kein UI-Baustein).

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| Telegram `setWebhook` / `getWebhookInfo` | extern | Registrierung und Zustellbeleg je Umgebung |
| `TELEGRAM_WEBHOOK_SECRET` | ENV (Go + Python) | derselbe Wert in beiden Prozessen je Umgebung |
| `scripts/telegram_set_webhook.sh` | Ops-Skript | `set`/`info`, gibt weder Secret noch rohe Antwort aus |
| Go-Journal (gregor-api, gregor-api-staging) | Betrieb | Zustellbeleg `POST …/telegram/inbound … 200` |
| `AuthMiddleware` Präfixausnahme | Go | bleibt unverändert |

## Implementation Details

```
router.go:   r.Post("/api/webhooks/telegram/{secret}", telegramWebhook)  -> entfernen
             r.Post("/api/webhooks/telegram/inbound", telegramWebhook)    -> bleibt
Alt-Pfad:    chi liefert 404 oder 405 (im RED-Test festlegen, was chi real liefert);
             Zusicherung der Spec: nicht 200 und kein Weiterreichen an den Core.
staging_messlauf.py: WEBHOOK_PFAD = "/api/webhooks/telegram/inbound"

Reihenfolge (hart, jede Umgebung für sich, Staging zuerst):
 G1 Zustellbeweis (VOR allem anderen): PO sendet einen Befehl vom Handy an den
    echten Bot; Claude gibt den Satz vor und wertet aus (Journal-Zeile
    POST .../telegram/inbound ... 200 ODER getWebhookInfo pending_update_count=0;
    keine Secret-/IP-Details ins Ticket). Ohne Beleg KEIN Entfernen, KEIN Rotieren.
 G2 Code erst nach G1 deployen: Staging -> /e2e-verify -> Prod.
 R  Rotation je Umgebung, Staging zuerst:
    1. neues Secret kryptografisch zufällig erzeugen (nie in Log/Chat/Ticket)
    2. TELEGRAM_WEBHOOK_SECRET in der ENV von Go UND Python tauschen
    3. beide Dienste der Umgebung neu starten
    4. sofort scripts/telegram_set_webhook.sh set (Fenster mit 403: nur Sekunden)
    5. info (nur ja/nein auswerten)
    6. Test-Befehl über den echten Bot
    Prod-Rotation nur außerhalb einer akuten Alarmphase, Fenster kurz halten.
```

## Expected Behavior

- **Input:** `POST /api/webhooks/telegram/<beliebiges-Segment außer inbound>` mit korrektem Header.
- **Output:** weder 200 noch Weiterreichung an den Core (404/405). `POST …/inbound` verhält sich unverändert (200 bei korrektem Header, Ablehnung sonst).
- **Side effects:** altes Secret wird ungültig; Telegram sendet mit dem neuen `secret_token`.

## Acceptance Criteria

**A. Kern-Tests (deterministisch, ohne Netz, Go/pytest)**

- **AC-1:** Given die Go-API mit gesetztem Secret und dem echten Router samt `AuthMiddleware` / When ein `POST /api/webhooks/telegram/irgendein-segment` mit korrektem Header eingeht / Then antwortet sie nicht mit 200 (404 oder 405) und der Python-Core-Mock sieht kein Update.
  - Test: `internal/router/telegram_webhook_inbound_route_test.go`: `…AltRoute_BleibtErreichbar` wird zu „Alt-Pfad nicht zugestellt"; der RED-Test legt den von chi real gelieferten Status fest.

- **AC-2:** Given dieselbe Konfiguration / When Telegram per `POST /api/webhooks/telegram/inbound` mit korrektem Header ein Update sendet, ohne Sitzungs-Cookie / Then antwortet die API 200 und genau ein Update wird an den Core weitergereicht.
  - Test: `…BeideRoutenGleich` wird zu „nur `/inbound` stellt zu" (über den echten Router mit `AuthMiddleware`).

- **AC-3:** Given dieselbe Konfiguration / When ein `POST` an `/inbound` ohne oder mit falschem Header eingeht / Then wird er wie bisher abgelehnt und nichts an den Core weitergereicht.
  - Test: `…GleicherStatusWieAltRoute` wird zu „fehlender/falscher Header auf `/inbound`, Status unverändert; Alt-Pfad nie 200".

- **AC-4:** Given die Tests aus AC-1 / When die Alt-Route im Router testweise wieder eingefügt wird (Mutationsgegenprobe, String-Ersetzung mit externer Sicherungskopie, kein git checkout/stash/reset) / Then wird mindestens AC-1 rot.
  - Test: Mutationsprobe im Adversary-Schritt (`implementation-validator`); Ergebnis im Workflow-Artefakt dokumentiert.

- **AC-5:** Given zwei verschiedene Nutzer mit je einem verknüpften Telegram-Chat / When beide nacheinander einen Befehl über `/inbound` senden / Then wird jeder Befehl dem richtigen Nutzer zugeordnet.
  - Test: Go-Testfall, der die `chat`-Zuordnung am Core-Aufruf für beide Nutzer prüft (Regressionsnachweis, Zuordnung selbst unverändert).

- **AC-6:** Given das Staging-Messlauf-Werkzeug / When es seinen Telegram-Webhook-Schritt ausführt / Then ruft es `/api/webhooks/telegram/inbound` auf und nicht mehr den Alt-Pfad.
  - Test: `tests/tdd/test_staging_messlauf.py` (Fake-Welt, Endpunkt-Allowlist) prüft den tatsächlich aufgerufenen Pfad `WEBHOOK_PFAD`.

- **AC-7:** Given die Doku (`api_contract.md`, `telegram_format.md`, `sms_format.md`, `docs/features/architecture.md`, Scheibe-1-Spec „Übergang"-Hinweise, Kommentare in `router.go`, `telegram_webhook.go`, `scheduler.go`, `staging_verify_token.go`) / When der Telegram-Webhook beschrieben wird / Then nennt sie nur `/api/webhooks/telegram/inbound` und benennt den Header als einzigen Auth-Träger; der `{secret}`-Pfad kommt nicht mehr als gültige Route vor.
  - Test: `# doc-compliance-test`, nur Doku-Konsistenz, kein Verhaltensnachweis.

**B. Live-/Betriebsnachweise (nicht im Kern-Testlauf, vom PO-Handy bzw. Betrieb)**

- **AC-8:** Given Staging und Prod sind auf `/inbound` registriert / When der PO je Umgebung einen Befehl vom Handy an den echten Bot sendet (Satz gibt Claude vor), VOR dem Deploy des Codes / Then liegt je Umgebung ein Beleg vor (Go-Journal `POST …/telegram/inbound … 200` oder `pending_update_count=0`) und die Antwort kommt im Chat an.
  - Test: Betriebs-Gate G1, Auswertung durch Claude; ohne Beleg wird weder entfernt noch rotiert.

- **AC-9:** Given der Code ist auf Staging deployt / When `/e2e-verify` läuft / Then ist ein Befehl über den echten Staging-Bot angekommen und der Verifikationsnachweis `.claude/e2e_verified/<sha>.json` ist frisch, bevor Prod deployt wird.
  - Test: Live-E2E gegen Staging (Hard Gate), danach Prod-Deploy und Selftest Exit 0.

- **AC-10:** Given die Rotation wurde je Umgebung (Staging zuerst, dann Prod) in der oben festgelegten Reihenfolge durchgeführt / When `info` ausgewertet wird und der PO einen Test-Befehl über den echten Bot sendet / Then endet die registrierte URL auf `/inbound`, `last_error_message` ist leer, die Antwort kommt an, und das alte Secret wird von Go und Python mit 403 abgelehnt.
  - Test: Betriebsnachweis je Umgebung (Ausgabe nur ja/nein; Secret erscheint in keinem Log, Chat oder Ticket).

- **AC-11:** Given Code deployt, beide Umgebungen rotiert und je ein Nach-Rotation-Befehl angekommen / When #1814 geschlossen werden soll / Then ist genau dann alles erledigt; vorher bleibt das Ticket offen, der PR-Text lautet „Refs #1814", nie „Closes".
  - Test: Abschluss-Gate im Deploy-Schritt (Checkliste im Issue-Kommentar, ohne Secret/IP-Details).

## Geplante Tests

- **MODIFY** `internal/router/telegram_webhook_inbound_route_test.go` (AC-1 bis AC-3, AC-5): mindestens ein Test über den echten Router mit `AuthMiddleware`. Mutation: Alt-Route wieder einfügen muss rot machen (AC-4).
- **MODIFY** `tests/tdd/test_staging_messlauf.py` (AC-6).
- Live (AC-8 bis AC-11): Handy-Befehl des PO, `/e2e-verify`, Rotation, Selftest.

## Known Limitations

- Zwischen `Neustart` und `set` liegt je Umgebung ein Fenster von Sekunden, in dem Telegram-Zustellungen 403 erhalten; Telegram wiederholt Updates, ein Verlust ist nicht zu erwarten, aber nicht garantiert.
- Prod-Rotation nur außerhalb einer akuten Alarmphase; Ausfall des Eingangs ist für den Nutzer unsichtbar.
- Unbekannte Unterpfade unter `/api/webhooks/telegram/` bleiben unauthentifiziert erreichbar (liefern 404/405).
- Bereits in Logs/Telegram-Konfiguration stehende alte Secrets werden durch die Rotation entwertet, nicht gelöscht.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Abschluss der Härtung aus Scheibe 1 bei unveränderter Auth-Entscheidung (Header-Secret); keine Grundsatzänderung.

## Changelog

- 2026-11-01: Initial spec created (Issue #1814, Scheibe 2, Phase 3)

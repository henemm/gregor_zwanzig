---
entity_id: feat_2439_befehle_push_eingang
type: module
created: 2026-10-13
updated: 2026-10-13
status: draft
version: "1.0"
tags: [inbound, premium-sms, email, webhook, scheduler, push, 2439]
---

# Push-Eingang für Befehle (Premium-SMS + E-Mail) — „Webhook = Weckruf“

## Approval

- [ ] Approved

## Purpose

Befehle, die der Nutzer per Premium-SMS (seven.io) oder E-Mail (Stalwart) schickt, werden heute erst beim nächsten 5-Minuten-Poll verarbeitet (PO-Befund 28.09.: `CODES` nach 4:28 min beantwortet, Rechnen < 1 s). Ein Webhook des jeweiligen Anbieters weckt den bestehenden Poll-Job sofort; der Poll bleibt als Fallback und als alleinige Wahrheit der Verarbeitung bestehen. Scheibe (a) von Issue #2439.

## Source

- **File:** `internal/handler/inbound_webhooks.go` (neu), `internal/scheduler/scheduler.go`
- **Identifier:** `InboundSMSWebhook`, `InboundMailWebhook`, `Scheduler.Kick`
- **Issue:** #2439 (Scheibe a). Scheibe (b) Rechenzeit ist **Out of Scope** (Berührung mit #2554, andere Sitzung).
- **Go-API (neu/ändern):** `internal/handler/inbound_webhooks.go` (neu), `internal/scheduler/scheduler.go`, `internal/router/router.go`, `internal/middleware/auth.go`, `internal/config/config.go`
- **Python-Core (ändern):** `api/routers/scheduler.py` (flock + busy), `src/services/inbound_sms_reader.py` (`processed` im Ergebnis)
- **Infra (Lieferbestandteil, selbst erledigt):** `henemm-infra` Nginx prod + staging; Hook-Registrierung bei seven.io und Stalwart
- **Doku:** neues ADR (Push weckt, Poll bleibt Wahrheit), Runbook zur Hook-Registrierung

## Entscheidung (Variante A: Weckruf)

Der Webhook verarbeitet die Nachricht **nicht** selbst und parst den Body nicht (nur für die Signatur gehasht). Nach bestandener Prüfung stößt er den **bestehenden** Poll-Job des Kanals (`premium_sms_poll` bzw. `inbound_command_poll`) sofort an. Journal-Abruf, Learn-Call, `last_seen_id`, IMAP-`UNSEEN`-Logik und die Nutzerzuordnung bleiben unverändert. Verworfen: Variante B (Einzelnachricht-Pfad wie Telegram) — zwei Verarbeiter ⇒ Doppelverarbeitung kostenpflichtiger SMS, Abhängigkeit vom undokumentierten `sms_mo`-Payload, ~450+ LoC.

Für **alle vier Kanäle** gilt unverändert: Antworten gehen über den Kanal, auf dem der Befehl eingegangen ist; dieses Feature berührt nur das *Wann* der Verarbeitung von SMS- und E-Mail-Befehlen. Telegram hat bereits einen Push-Eingang (Vorlage) und bleibt unberührt.

### Entschiedene offene Fragen der Analyse

| Frage | Entscheidung |
|---|---|
| Admin-Proxy `/api/scheduler/inbound-commands` | **flock behalten** (Defense in Depth): der Proxy umgeht den Go-`jobLock`, läuft aber in denselben Python-flock wie der Push-Pfad. Kein Ersatz durch `Kick`. |
| seven.io-Signatur (Encoding, ob Pfad-Secret Teil der signierten URL) | **Implementierungs-Vorbedingung:** Vor GREEN wird ein echter `sms_mo`-Request mitgeschnitten (Request-Catcher/Staging-Hook) und als versionierte Fixture abgelegt (Header, Body, Signatur). Die Signaturprüfung wird gegen diese Fixture gebaut, nicht gegen Annahmen. Signatur-URL wird aus `PublicHost` + Pfad rekonstruiert, nie aus `r.URL`. |
| Stalwart-Eventname | **Implementierungs-Vorbedingung:** Eventname (`message-ingest.ham` laut Doku vs. `store.ingest`) wird an Stalwart v0.16.26 per Admin-API verifiziert und im Runbook festgehalten. Ein falscher Name wäre stille Nicht-Zustellung — daher zusätzlich AC-8 (Sichtbarkeit über `push.last_received`). |
| Netzpfad Stalwart-Container → Go (Go lauscht nur `127.0.0.1:8090`) | **Öffentlicher Nginx-Pfad** (Hairpin über `https://…/api/webhooks/mail/<secret>`); keine Änderung der Go-Bind-Adresse. |
| Staging-Beleg SMS | Zweite seven.io-Nummer mit eigenem Hook (`event_filter` → Staging-URL); Beleg = `push.last_received` + sofortiger `last_run` ohne 5-Min-Tick. Mail: Staging-Stalwart-Hook + Postfach `gregor-test@`. |
| seven.io ohne IP-Ranges | Kein IP-Filter möglich ⇒ Pfad-Secret (erste Schranke) + Signatur (zweite Schranke) + Nginx `limit_req`. |
| Aufteilung | Beide Kanäle in **einer** Spec/einem Workflow; LoC-Überschreitung ⇒ `loc_limit_override 500`. |

## Estimated Scope

- **LoC:** ~+265 produktiv (Go ~230, Python ~30), plus Tests, ADR, Runbook, Infra-Konfig
- **Files:** ~9 Code + Tests + ADR/Runbook + Nginx (prod+staging)
- **Effort:** medium (Risiko MEDIUM: zentraler Scheduler + neuer öffentlicher Eingang; Verarbeitungslogik selbst unverändert)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `internal/handler/telegram_webhook.go` | Vorlage | 503 fail-closed ohne Secret, konstantzeitiger Vergleich, Zähler, immer 200 |
| `Scheduler.recordRun` / `jobLock` | bestehend | Overlap-Schutz je Job; Cron-Tick bleibt TryLock |
| `internal/coreauth/transport.go` | bestehend | `X-GZ-Core-Auth` Go → Python |
| `internal/config/config.go` `PublicHost` | bestehend | Signatur-URL-Rekonstruktion |
| `src/services/inbound_sms_reader.py` | bestehend | Journal-Abruf, `_verarbeite_befehl`, `last_seen_id` |
| `src/services/inbound_email_reader.py` | bestehend | IMAP `UNSEEN`, Autorisierung, `lookup_user_by_email` |
| `internal/handler/premium_sms_connect.go` | bestehend | Absender→Nutzer-Zuordnung (Go einziger Schreiber, ADR-0015) |
| `/api/scheduler/status` | bestehend | Observability, Token-geschützt (`X-GZ-Status-Token`) |
| seven.io `POST /api/hooks` (`sms_mo`) | extern | Inbound-Webhook, HMAC-SHA256-Signatur (`X-Signature`/`X-Timestamp`/`X-Nonce`) |
| Stalwart v0.16.26 Webhooks | extern | Ereignis bei Mail-Eingang, HMAC/Bearer |

## Implementation Details

```
1. Scheduler.Kick(jobID):
   - Flags pending/running je Job; höchstens EINE Kick-Goroutine je Job.
   - Kick setzt pending=true; läuft die Goroutine schon, kehrt Kick sofort zurück
     (kicks_coalesced++). Sonst startet sie.
   - Goroutine: solange pending: pending=false; recordRunWait(job) (blockierender
     jobLock, gleicher wie Cron); Python-busy ⇒ pending=true (später erneut).
   - Cron-Tick bleibt TryLock (überspringt bei Belegung, Fallback-Poll).
   - Mindestabstand zwischen zwei tatsächlichen Läufen ~2 s.
2. Nachversuch gegen Journal-Verzögerung:
   - SMS: Läufe bei 0 s / 3 s / 8 s; Abbruch, sobald ein Lauf processed>0 meldet.
   - Mail: ein Nachversuch nach ~2 s.
   - Nachversuche rufen nur Journal/IMAP ab, lösen keine zusätzlichen SMS aus.
3. Handler POST /api/webhooks/sms/{secret} und /api/webhooks/mail/{secret}:
   - Env fehlt (Pfad-Secret bzw. SEVEN_WEBHOOK_SIGNING_KEY bzw. STALWART_WEBHOOK_SECRET)
     ⇒ 503 fail-closed, keine Verarbeitung.
   - Pfad-Secret konstantzeitig prüfen; SMS: HMAC-Signatur (Timestamp-Fenster 30 s,
     Nonce-Cache); Mail: Stalwart-HMAC/Bearer. Fehlschlag ⇒ 403, rejected_total++,
     KEIN Kick, KEIN last_received.
   - Bestanden ⇒ last_received setzen, received_total++, Kick asynchron, sofort 200.
4. Router: 2 Routen; middleware/auth.go: sitzungsfreie Präfix-Ausnahme analog Telegram.
5. Python: api/routers/scheduler.py /inbound-sms und /inbound-commands mit
   nicht-blockierendem flock; belegt ⇒ {"status":"busy"} ohne Verarbeitung.
   Ergebnis liefert "processed" (SMS: im Reader ergänzen, falls fehlt).
6. Status: /api/scheduler/status je Kanal
   push: {last_received, received_total, rejected_total, kicks_coalesced}.
7. Fallback-Poll bleibt */5 (Absenkung = spätere Folgeentscheidung nach Prod-Beleg).
8. Infra: Nginx-Locations /api/webhooks/sms/ und /api/webhooks/mail/ (prod+staging),
   Staging-Basic-Auth-Ausnahme analog Telegram, limit_req; Hooks bei seven.io und
   Stalwart (Prod + Staging) registrieren; Runbook dokumentiert Eventname,
   Registrierung, Rotation der Secrets.
9. ADR: „Push weckt, Poll bleibt Wahrheit; Prüfung/Lock in Go“ + Index-Eintrag.
```

## Expected Behavior

- **Input:** Eingehender seven.io-`sms_mo`-Webhook bzw. Stalwart-Mail-Eingangs-Webhook auf öffentlichem Pfad.
- **Output:** HTTP 200 sofort (bestanden), 403 (Prüfung fehlgeschlagen), 503 (Secret fehlt). Befehl wird im selben Poll-Job wie bisher verarbeitet, nur ohne Warten auf den 5-Min-Tick.
- **Side effects:** Antwort auf den Befehl über den Eingangskanal (bei SMS kostenpflichtige Premium-SMS — genau eine je Befehl); Push-Zähler im Status-Endpoint.

## Out of Scope

- Scheibe (b) Rechenzeit / Wetterabruf-Dauer (#2554, #2439b).
- `BODY.PEEK` statt `RFC822` beim IMAP-Fetch (Status quo `\Seen`).
- Absenkung des Fallback-Poll-Intervalls.
- Änderungen am Telegram-Eingang.

## Acceptance Criteria

- **AC-1:** Given ein Nutzer mit verknüpfter Absendernummer und produktivem seven.io-Hook, When er per Premium-SMS einen Befehl ohne Wetterabruf (z. B. `CODES`) sendet, Then trifft der gültig signierte Webhook ein, der Poll-Job `premium_sms_poll` läuft sofort ohne auf den 5-Minuten-Tick zu warten, und die Antwort-SMS wird innerhalb von 30 Sekunden ab Eingang des Webhooks versendet.
  - Test: Go-Handlertest mit echter, aufgezeichneter seven.io-Fixture (Header+Body) startet den Job; Staging-Beleg: `last_run` des Jobs liegt Sekunden nach `push.last_received`, nicht Minuten.
- **AC-2:** Given ein Nutzer mit autorisierter Absenderadresse und registriertem Stalwart-Hook, When er eine E-Mail mit einem Befehl ohne Wetterabruf sendet, Then löst der gültige Mail-Webhook `inbound_command_poll` sofort aus und die Antwortmail kommt innerhalb von 30 Sekunden ab Eingang des Webhooks im Postfach an.
  - Test: Staging-Lauf mit `gregor-test@`-Postfach; IMAP-Beleg der Antwort und `last_run`-Zeitstempel unabhängig vom 5-Min-Raster.
- **AC-3:** Given ein Webhook-Aufruf mit falschem Pfad-Secret oder ungültiger/abgelaufener Signatur (SMS) bzw. falschem Secret/Bearer (Mail), When die Anfrage eintrifft, Then wird kein Poll-Job angestoßen, keine Nachricht verarbeitet, `rejected_total` erhöht sich um 1, und die Antwort ist 403.
  - Test: Go-Handlertest je Variante (falsches Pfad-Secret, manipulierter Body, veralteter Timestamp, wiederverwendete Nonce); Zähler und fehlender Job-Lauf werden geprüft.
- **AC-4:** Given das Pfad-Secret, der Signatur-Schlüssel bzw. das Stalwart-Secret ist in der Umgebung nicht gesetzt, When ein Webhook-Aufruf eintrifft, Then antwortet der Endpunkt mit 503 (fail-closed), verarbeitet nichts und stößt keinen Job an.
  - Test: Go-Handlertest ohne Env-Wert je Endpunkt (SMS und Mail getrennt).
- **AC-5:** Given viele Webhooks treffen gleichzeitig oder während eines laufenden Poll-Laufs ein, When `Kick` mehrfach aufgerufen wird, Then geht kein Weckruf verloren (nach dem laufenden Lauf folgt höchstens ein weiterer Lauf), es läuft nie mehr als ein Lauf je Job gleichzeitig, und jeder Befehl löst genau eine Antwort aus (keine doppelte kostenpflichtige SMS).
  - Test: Go-Scheduler-Test mit gesteuertem Job (N parallele Kicks ⇒ ≤ 2 Läufe, `kicks_coalesced` stimmt, kein Verlust bei Kick während Lauf) und Race-Detektor.
- **AC-6:** Given ein Poll-Lauf (Cron, Webhook oder Admin-Proxy `/api/scheduler/inbound-commands`) hält den Python-flock, When ein zweiter Aufruf von `/inbound-sms` bzw. `/inbound-commands` eintrifft, Then antwortet der Core sofort mit `{"status":"busy"}` ohne zu verarbeiten, Go setzt den Weckruf erneut auf pending, und `last_seen_id` bzw. `UNSEEN` werden nicht doppelt abgearbeitet.
  - Test: Python-Test mit echtem flock (zwei konkurrierende Aufrufe auf echter Zeigerdatei im tmp-Verzeichnis); der Admin-Proxy-Pfad wird ebenfalls gegen den gehaltenen Lock geprüft.
- **AC-7:** Given der SMS-Lauf findet beim ersten Abruf die Nachricht wegen Journal-Verzögerung noch nicht (`processed=0`), When der Webhook eingegangen ist, Then wiederholt Go den Lauf nach 3 s und 8 s und bricht ab, sobald ein Lauf `processed>0` meldet; findet der erste Lauf die Nachricht, gibt es keine weiteren Läufe.
  - Test: Go-Scheduler-Test mit Job-Stub, der gestaffelt `processed` liefert (0,0,1 ⇒ 3 Läufe; 1 ⇒ 1 Lauf; 0,0,0 ⇒ 3 Läufe und Ende); Zeitsteuerung über injizierbare Uhr.
- **AC-8:** Given der Webhook-Eingang fällt aus oder ist falsch konfiguriert (z. B. falscher Stalwart-Eventname), When ein Befehl gesendet wird, Then wird er spätestens vom Fallback-Poll `*/5` unverändert verarbeitet, und der Status-Endpoint zeigt durch ein ausbleibendes `push.last_received` den Ausfall.
  - Test: Scheduler-Test bestätigt, dass Cron-Registrierung `*/5` für beide Jobs unverändert besteht und ohne Kick läuft; Staging-Prüfung, dass `push.last_received` ohne Webhook unverändert bleibt.
- **AC-9:** Given `/api/scheduler/status` wird mit gültigem `X-GZ-Status-Token` abgefragt, When Webhooks eingegangen sind (gültige und abgewiesene), Then zeigt jeder der Kanäle SMS und E-Mail `push.last_received`, `received_total`, `rejected_total` und `kicks_coalesced`, wobei `last_received` und `received_total` nur nach bestandener Prüfung steigen und abgewiesene Aufrufe ausschließlich `rejected_total` erhöhen.
  - Test: Go-Test ruft Handler mit gültigen und ungültigen Requests und liest danach den Status-Endpoint; ohne Token weiterhin abgewiesen.
- **AC-10:** Given zwei verschiedene Nutzer mit je eigener Absendernummer bzw. E-Mail-Adresse und je eigenem Trip, When beide kurz nacheinander Befehle über Webhook-Auslösung senden, Then wirkt jeder Befehl nur auf den Trip seines Absenders, jede Antwort geht nur an den eigenen Absender, und ein unbekannter Absender wird nie dem Nutzer „default“ zugeordnet.
  - Test: Zwei-Nutzer-Test über den echten Eingang (Webhook-Fixture → Kick → Poll → Zuordnung) mit zwei Absendern und getrennten Trips; Gegenprobe mit unbekanntem Absender ohne Wirkung.
- **AC-11:** Given Nginx und Hooks sind (Staging zuerst, dann Prod) eingerichtet, When von außen die Pfade `/api/webhooks/sms/…` und `/api/webhooks/mail/…` aufgerufen werden, Then erreichen sie die Go-API (auf Staging ohne Basic-Auth-Hürde für diese Pfade, übrige Staging-Pfade weiter geschützt), übermäßige Aufrufraten werden per `limit_req` gebremst, und die Hooks bei seven.io und Stalwart sind für beide Umgebungen registriert und im Runbook dokumentiert.
  - Test: HTTP-Smoke gegen Staging und Prod (ungültiges Secret ⇒ 403, nicht 401/404/Basic-Auth-Challenge; übriger Staging-Pfad ⇒ 401); Beleg der Hook-Registrierung per API-Abfrage.
- **AC-12:** Given die Implementierungs-Vorbedingungen (echter seven.io-Header-Mitschnitt, verifizierter Stalwart-Eventname an v0.16.26, Container→Go-Netzpfad über öffentlichen Nginx-Pfad) sind erfüllt, When die Tests laufen, Then nutzt die Signaturprüfung die aufgezeichnete Fixture statt erfundener Werte, und ADR samt Index-Eintrag („Push weckt, Poll bleibt Wahrheit“) sind angelegt.
  - Test: Signaturtest lädt die versionierte Fixture; `tests/test_adr_index_drift.py` bleibt grün.
- **AC-13:** Given der Sofort-Weg eines Kanals fällt aus (falsche Signaturannahme, falscher Stalwart-Eventname, Hook gelöscht, Nginx-Pfad kaputt), When der Fallback-Poll `*/5` einen Befehl verarbeitet, zu dem in den letzten 5 Minuten kein gültiger Webhook eingegangen war, Then zählt der Status-Endpoint das je Kanal als `push.missed_total` mit `push.last_missed`, und das externe Monitoring (`henemm-infra/scripts/check-gregor20.sh`) meldet einen steigenden `missed_total` als Fehler ⇒ kein BetterStack-Heartbeat-Ping ⇒ E-Mail-Alarm an den PO. Der Ausfall bleibt also nicht unbemerkt.
  - Test: Go-Scheduler-Test: Cron-Lauf mit `processed>0` ohne vorausgehenden Kick erhöht `missed_total`, Lauf nach Kick nicht; Infra: `check-gregor20.sh` gegen eine Kopie mit gestelltem Status-JSON (steigender Zähler ⇒ ERRORS>0, kein Ping; gleicher Zähler ⇒ Ping). Mutationen nur in einer Kopie (Arbeitsbaum von henemm-infra ist sofort live).

## Geplante Tests (nach Verhalten benannt, kein Mock-Theater)

- `internal/handler/inbound_webhooks_test.go` — Pfad-Secret, Signatur (aufgezeichnete Fixture), Nonce/Timestamp, 503 fail-closed, 403-Zähler, Mail-Secret
- `internal/scheduler/scheduler_kick_test.go` — Coalescing, kein verschluckter Weckruf, Nachversuch 0/3/8 s mit Abbruch bei `processed>0`, Cron-Fallback unverändert, Race-Detektor
- `tests/test_inbound_poll_lock.py` — flock/busy mit echten konkurrierenden Aufrufen inkl. Admin-Proxy-Pfad
- Zwei-Nutzer-Test über den echten Eingang (Go + Python-Core)
- Live-Schicht (nur `/e2e-verify`): Staging-Hook SMS (zweite seven.io-Nummer) und Mail (`gregor-test@`), IMAP-Beleg der Antwort

## Known Limitations

- seven.io liefert keine IP-Ranges ⇒ Schutz nur über Pfad-Secret + Signatur + Rate-Limit.
- Kick-Goroutine kann bis zu einem Lauf lang auf den laufenden Job warten (max. eine je Job).
- Mail-Fetch setzt weiterhin implizit `\Seen` (Status quo, nicht Teil dieser Scheibe).
- Fallback-Poll bleibt `*/5`, bis die Push-Zuverlässigkeit in Prod belegt ist.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0087 (neu, „Push weckt, Poll bleibt Wahrheit“)
- **Rationale:** Erstmals ein Push-Eingang für SMS/E-Mail neben dem Poll. Festzuhalten: der Webhook verarbeitet nichts selbst, sondern stößt nur den bestehenden Poll-Job an (ein einziger Verarbeiter ⇒ keine doppelte kostenpflichtige SMS). Prüfung und Coalescing liegen in Go, der Python-flock schützt zusätzlich. Der Poll bleibt Fallback und alleinige Wahrheit.

## Changelog

- 2026-10-13: Initial spec created (v1.0)
- 2026-10-13: AC-13 ergänzt — Ausfall des Sofort-Wegs wird über `push.missed_total` erkannt und alarmiert (Befund PO-Briefing)

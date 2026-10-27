# Context: feat-2439-befehle-push-eingang

## Request Summary
Issue #2439, Scheibe (a): Befehle per Premium-SMS (seven.io) und E-Mail sollen sofort per Push
verarbeitet werden statt erst beim nächsten 5-Minuten-Poll (PO-Befund 28.09.: `CODES` 4:28 gewartet,
< 1 s Rechnen). Der Poll bleibt als (seltenerer) Fallback. Scheibe (b) Rechenzeit ist NICHT Teil dieses
Workflows (Berührung mit #2554 DWD-Gewitterbudget, läuft in anderer Sitzung).

## Related Files
| File | Relevance |
|------|-----------|
| `internal/router/router.go:166,170-171,304` | Telegram-Webhook-Route, `/api/internal/premium-sms-learn`, Status-Route |
| `internal/middleware/auth.go:62` | Sitzungsfreie Präfix-Ausnahme `/api/webhooks/telegram/` — neuer Webhook-Pfad muss hier rein |
| `internal/handler/telegram_webhook.go:39-91` | Vorlage: fail-closed 503 ohne Secret, konstantzeitiger Secret-Vergleich, 403-Zähler, synchrone Weiterleitung (5 s) an Python, immer 200 |
| `internal/coreauth/transport.go:27,46-55` | `X-GZ-Core-Auth` per RoundTripper auf DefaultTransport |
| `api/main.py:125-184` | Python-Middleware erzwingt Core-Auth |
| `api/routers/webhook.py:35-94` | Python-Endpoint Telegram, Dedup per In-Memory-Set `update_id` |
| `internal/scheduler/scheduler.go:310,324,861-920,946-986,1330` | Cron `*/5` für `inbound_command_poll`/`premium_sms_poll`, `recordRun` TryLock je Job, Status |
| `api/routers/scheduler.py:170-220` | `/inbound-commands`, `/inbound-sms` |
| `src/services/inbound_sms_reader.py` | seven.io-Journal-Abruf (`/api/journal/inbound?limit=100`), Prod-only-Gate (:166-181), `to == SERVICE_NUMBER` (:83,:236), Zeigerdatei `last_seen_id` (:86,:433-462), `_verarbeite_befehl` (:313-411) |
| `internal/handler/premium_sms_connect.go:10-150` | Nutzerzuordnung Absender→Nutzer (gelernte Rückadresse / Verknüpfungscode, 409/429) |
| `src/services/inbound_email_reader.py:137-386` | IMAP `UNSEEN`-Suche, `\Seen`, Autorisierung (Absender=`mail_to`, verifiziert, SPF/DKIM via Stalwart-`Authentication-Results`), `lookup_user_by_email` |
| `src/output/channels/seven_io_base.py`, `premium_sms.py` | seven.io-Versand |
| `internal/egress/inventory.go:40`, `src/app/egress_guard.py:51` | `gateway.seven.io` im Egress-Inventar |

## Existing Patterns
- **Webhook-Muster Telegram:** öffentliche Go-Route mit Secret → Weiterleitung an internen Python-Endpoint
  mit Core-Auth → Python prüft Secret erneut → Dedup → bestehender Verarbeiter. Nutzerzuordnung über
  Kanal-Kennung, ohne Treffer `None`, nie „default“ (#2151).
- **Poll-Muster:** Go-Cron triggert globalen Python-Endpoint, `recordRun` liefert `last_run` + Overlap-Zähler.
- **Nutzerzuordnung SMS** liegt in Go (`premium-sms-learn`), Go ist einziger Schreiber von `user.json` (ADR-0015).

## Dependencies
- Upstream: seven.io (Journal-API; ob/wie ein Inbound-Webhook existiert und signiert wird: **offen, im Repo nichts**),
  Stalwart-IMAP (IDLE oder Ereignis-Hook: **im Repo nichts**), Nginx in `henemm-infra` (öffentlicher Pfad,
  IP-Allowlist/`limit_req`, Staging-Basic-Auth-Ausnahme analog Telegram).
- Downstream: `_verarbeite_befehl` (SMS), Befehlsverarbeitung E-Mail, Premium-SMS-Versand (kostenpflichtig),
  Status-Endpoint/BetterStack-Monitoring.

## Existing Specs
- `docs/specs/modules/inbound_command_channels.md` (v1.6), `telegram_webhook_inbound.md`,
  `feat_1676_s1_premium_sms_rueckkanal.md`, `feat_2184_s4_premium_sms_kommandoverarbeiter.md`,
  `fix_2154_premium_sms_verknuepfungscode.md`, `fix_2323_premium_sms_gate_generisch.md`,
  `fix_2328_premium_sms_rueckkanal_kollision.md`, `fix_1369_inbound_telegram_poll_entfernen.md`,
  `feat_2417_befehle_e2e_echter_eingang.md`, `bug_inbound_email_loop.md`
- ADRs: `0049-premium-sms-vierter-kanal.md`, `0015-dual-stack-zielarchitektur.md`
- Runbooks: `docs/runbooks/telegram-webhook.md`, `premium_sms_generalprobe.md`
- `docs/context/feat-2184-premium-sms-kommando.md:30` hält „kein Webhook“ fest — bewusste frühere Entscheidung, prüfen ob ADR-relevant.

## Risks & Considerations
- **Doppelverarbeitung Poll vs. Push (hoch):** SMS-Zeigerdatei ohne Lock (Lesen→Verarbeiten→Schreiben),
  E-Mail Rennfenster zwischen `search UNSEEN` und `fetch`. Push umgeht den `recordRun`-TryLock. Folge:
  doppelte, kostenpflichtige Premium-SMS-Antwort. Braucht echte Nachrichten-Idempotenz (z. B. gemeinsamer
  Lock je Kanal oder Dedup-Register der Nachrichten-IDs).
- **seven.io-Webhook-Sicherheit:** unbekannt, ob seven.io signiert; Secret im Pfad/Header, IP-Allowlist,
  Rate-Limit. Absender-Fälschung darf keine fremden Trips steuern (Mandantentrennung über bestehende Go-Zuordnung).
- **Stalwart-Push:** IMAP IDLE braucht langlebige Verbindung (eigener Prozess/Thread, Reconnect, Event-Loop
  darf nicht blockieren — `test_event_loop_bleibt_frei.py`); Alternative Stalwart-Webhook/Sieve. Unerforscht.
- **Prod-only-Gate SMS:** Journal-Abruf läuft nur in Prod; Staging-Prüfweg für Push muss geklärt werden
  (Sandbox-Key liest dasselbe Prod-Journal).
- **Infra-Anteil:** Nginx-Location + Basic-Auth-Ausnahme in `henemm-infra`, seven.io-Webhook-Registrierung im
  seven.io-Konto — selbst erledigen (Infra-Repo), nicht dem PO zuschieben.
- **Observability:** Webhooks haben kein `last_run`; neuer Eingang braucht Tracking im Status-Endpoint.
- **Mehrnutzer:** Test mit zwei Nutzern Pflicht.
- **LoC-Limit 250** voraussichtlich zu knapp für SMS+E-Mail zusammen → ggf. Scheibe (a) weiter teilen
  (a1 SMS-Webhook, a2 E-Mail-Push).

## Analysis

### Type
Feature (Issue #2439, Scheibe a — Push-Eingang SMS + E-Mail; Scheibe b Rechenzeit NICHT enthalten). Beide Kanäle in EINER Spec — kein Abspalten a1/a2 (LoC ⇒ `loc_limit_override`).

### Kernentscheidung: „Webhook = Weckruf“ (Variante A)
Der Webhook verarbeitet die Nachricht NICHT selbst. Nach Authentizitätsprüfung stößt er den BESTEHENDEN Poll-Job
des Kanals sofort an (`premium_sms_poll` bzw. `inbound_command_poll`). Journal-Abruf, Learn-Call, `last_seen_id`,
IMAP-`UNSEEN`-Logik bleiben alleinige Wahrheit. Body wird nicht geparst (nur für Signatur gehasht).

| Kriterium | A: Weckruf | B: Einzelnachricht-Pfad (wie Telegram) |
|---|---|---|
| Doppelverarbeitung (kostenpflichtige SMS) | gering — ein Verarbeiter | hoch — zwei Verarbeiter, Idempotenz-Register nötig |
| Abhängigkeit vom Payload | keine | hoch: seven.io `sms_mo`-Felder sind NICHT dokumentiert |
| LoC produktiv | ~265 | ~450+ |
| Latenz | Sekunden (SMS + 0–11 s Nachversuch) | < 1 s besser — irrelevant ggü. 4:28 min |
| Testbarkeit | Kick/Coalescing rein in Go testbar | Payload-Fixtures müssten erfunden werden |

### Belegte Fakten (Code, geprüft 13.10.)
- SMS `src/services/inbound_sms_reader.py`: `poll_and_process` :153 (Prod-Gate :165-181), `_poll_journal` :191, Schleife :232-310 (Learn :252, `_verarbeite_befehl` :281/:313), High-Watermark `last_seen_id` :433-461 in `data_root/diagnostics/premium_sms_inbound.json`. Kein Lock, synchron.
- Mail `src/services/inbound_email_reader.py`: `poll_and_process` :137 (`UNSEEN` :159/161), `_process_single` :181, `fetch(RFC822)` ohne BODY.PEEK :189, `\Seen` im finally :259. Kein Lock.
- Go-Scheduler `internal/scheduler/scheduler.go`: Cron `*/5` :310 (`inbound_command_poll`), :324 (`premium_sms_poll`); `recordRun` :968 mit `jobLock` :946 **TryLock → überspringt** bei belegt. Python-Endpoints `api/routers/scheduler.py` :170 `/inbound-commands`, :187 `/inbound-sms` (sync, ohne Lock).
- Admin-Proxy `/api/scheduler/inbound-commands` (`internal/router/router.go:330`) umgeht den Go-`jobLock`.
- Telegram-Vorlage `internal/handler/telegram_webhook.go` (Secret-Env, konstantzeitig, 503 fail-closed, 403-Zähler, immer 200), Route `router.go:171`, Auth-Ausnahme `internal/middleware/auth.go:62`.
- `Config.PublicHost` (`PUBLIC_HOST`) existiert: `internal/config/config.go:60` → für Signatur-URL-Rekonstruktion nutzen.
- Stalwart v0.16.26 läuft als Docker-Container (Netz `stalwart_default`) auf demselben Host; Go-API lauscht nur `127.0.0.1:8090` ⇒ Container erreicht Go nur über öffentlichen Nginx-Pfad (Hairpin) oder Host-Gateway. Stalwart-Config liegt in der DB (Admin-UI/API), nicht als Datei in `henemm-infra/stalwart/`.
- Kein ADR entscheidet Poll vs. Push; „kein Webhook“ in `docs/context/feat-2184-premium-sms-kommando.md:30` ist Ist-Beschreibung, keine Begründung.

### Externe Fakten (Web-Recherche)
- seven.io: `POST https://gateway.seven.io/api/hooks` (`target_url`, `event_type=sms_mo`, `event_filter`=Inbound-Nummer ohne „+“, `request_method` POST/GET/JSON). Signatur: Header `X-Signature`/`X-Timestamp`/`X-Nonce`, HMAC-SHA256 mit **Account-Signing-Key** über Timestamp+Nonce+Methode+**volle Ziel-URL**+MD5(Body); 30-s-Fenster, Nonce-Cache. Retries existieren (Verhalten undokumentiert). Keine IP-Ranges ⇒ kein IP-Filter möglich. Quellen: docs.seven.io/en/rest-api/endpoints/webhooks, /signing.
- Stalwart Webhooks (Telemetry): Events einzeln, `message-ingest.ham` laut Doku (Beispielseite nennt `store.ingest` ⇒ an v0.16.26 verifizieren), throttle 1 s, `lossy=false` hält Events bis 5 min, HMAC Base64 in `X-Signature` oder `httpAuth` Bearer. IMAP IDLE: Forum-Bug 0.16.x (kein EXISTS) ⇒ verworfen.

### Technical Approach (Empfehlung)
1. **Go `Scheduler.Kick(jobID)` mit Coalescing:** Flags `pending`/`running` je Job; höchstens eine Kick-Goroutine je Job; sie läuft über blockierendes `recordRunWait` (gleicher `jobLock`) und läuft erneut, solange `pending` gesetzt ist. Cron-Tick bleibt TryLock. ⇒ Kein verschluckter Weckruf, mehrere Webhooks verschmelzen.
2. **Nachversuch gegen Journal-Verzögerung (SMS):** bis 3 Läufe (0 s / 3 s / 8 s), Abbruch sobald ein Lauf `processed>0` meldet (Python-Ergebnis muss `processed` liefern). Mail: ein Nachversuch nach ~2 s.
3. **Handler `internal/handler/inbound_webhooks.go`:** `POST /api/webhooks/sms/{secret}`, `POST /api/webhooks/mail/{secret}`; Pfad-Secret (erste Schranke) + Signatur (zweite Schranke) in Go; sofort 200, Kick asynchron; Mindestabstand Kicks (~2 s). SMS-Signatur-URL aus `PublicHost`+Pfad rekonstruieren, nicht `r.URL`. Neue Env: SMS-Pfad-Secret, `SEVEN_WEBHOOK_SIGNING_KEY`, `STALWART_WEBHOOK_SECRET`. Fail-closed 503 ohne Secret.
4. **Python `flock` (non-blocking)** auf `/inbound-sms` und `/inbound-commands` → `{"status":"busy"}`; Go wertet busy als „pending neu setzen“. Schließt Admin-Proxy-Lücke, schützt `last_seen_id`.
5. **Observability:** `/api/scheduler/status` je Kanal `push: {last_received, received_total, rejected_total, kicks_coalesced}`; `last_received` erst nach bestandener Prüfung.
6. **Fallback-Poll bleibt `*/5`** bis Push-Zuverlässigkeit in Prod belegt (Senkung = Folgeentscheidung).
7. **ADR** neu: „Push weckt, Poll bleibt Wahrheit; Prüfung/Lock in Go“.
8. **Mandantentrennung unverändert:** Nutzerzuordnung bleibt in bestehendem Poll (Learn-Endpoint / `lookup_user_by_email`); Webhook berührt keine Nutzerdaten. Zwei-Nutzer-Test trotzdem Pflicht (zwei Absender, je eigener Trip).

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `internal/scheduler/scheduler.go` | MODIFY | `Kick`, `recordRunWait`, Nachversuch, Push-Status (~90 LoC) |
| `internal/handler/inbound_webhooks.go` | CREATE | SMS + Mail-Webhook, Signatur, Nonce-Cache (~130) |
| `internal/handler/inbound_webhooks_test.go` | CREATE | Tests |
| `internal/scheduler/*_test.go` | CREATE/MODIFY | Coalescing-/Nachversuch-Tests |
| `internal/router/router.go` | MODIFY | 2 Routen (~6) |
| `internal/middleware/auth.go` | MODIFY | Public-Präfix-Ausnahme (~3) |
| `internal/config/config.go` | MODIFY | 3 Env-Felder (~6) |
| `api/routers/scheduler.py` | MODIFY | flock + busy (~25) |
| `src/services/inbound_sms_reader.py` | MODIFY | `processed` im Ergebnis, falls fehlt (~5) |
| `docs/adr/00xx-push-eingang-weckruf.md` + Index | CREATE | ADR |
| `docs/runbooks/` | CREATE/MODIFY | Hook-Registrierung seven.io + Stalwart |
| henemm-infra Nginx (prod + staging) | MODIFY (selbst, Infra-Repo) | Locations `/api/webhooks/sms/`, `/api/webhooks/mail/`, Staging-Basic-Auth-Ausnahme, `limit_req` |

### Scope Assessment
- Files: ~9 Code + Tests + ADR/Runbook + Infra
- Estimated LoC: ~+265 produktiv ⇒ `loc_limit_override 500` in /30 setzen
- Risk Level: MEDIUM (zentraler Scheduler + neuer öffentlicher Eingang; Verarbeitungslogik selbst unverändert)

### Dependencies / Reihenfolge
Code+Tests (Go-Kick, Handler, Python-flock) → Staging-Deploy mit Env → henemm-infra Nginx (Staging zuerst, Basic-Auth-Ausnahme) → Staging-Hooks registrieren → Prod-Deploy → Prod-Nginx + Prod-Hooks → Beobachtung → Folgeentscheidung Poll-Intervall.

### Risiken
- seven.io Signaturdetails (ist Pfad-Secret Teil der signierten URL? Hex/Base64?) — erst mit echtem Request belegbar ⇒ Implementierung muss echten Header-Mitschnitt als Fixture nutzen.
- Stalwart-Eventname in v0.16.26 ungeprüft; falscher Name ⇒ stille Nicht-Zustellung, nur über `last_received` sichtbar.
- Kick-Goroutine wartet bis zu Minuten auf laufenden Job (max. eine je Job).
- Mail `fetch(RFC822)` setzt `\Seen` implizit — Status quo, durch Push nicht schlechter; BODY.PEEK NICHT in Scope.
- Kosten: Nachversuche lösen keine zusätzlichen SMS aus (nur Journal-Abrufe).

### Open Questions (für /30 klären, keine PO-Fragen)
- [ ] seven.io: Echten `sms_mo`-Request mitschneiden (Header, signierte URL inkl. Pfad-Secret?, Signatur-Encoding) — Testhook auf Request-Catcher/Staging.
- [ ] Stalwart v0.16.26: genauer Eventname (`message-ingest.ham`?) und Webhook-Konfig via Admin-API verifizieren; Netzpfad Container→Go (Hairpin über öffentliche Domain vs. Host-Gateway).
- [ ] Staging-Beleg SMS: zweite seven.io-Nummer (empfängt, siehe Memory) mit eigenem Hook + `event_filter` → Staging-URL; Beleg = `push.last_received` + sofortiger Dry-Run-`last_run` ohne 5-Min-Tick. Mail: Staging-Stalwart-Webhook + Test-Postfach `gregor-test@`.
- [ ] Admin-Proxy `/api/scheduler/inbound-commands`: durch `Kick` ersetzen (spart Python-Lock) oder flock behalten — in Spec entscheiden (Empfehlung: flock behalten, Defense in Depth).
- [ ] Zielgröße als AC: Antwort auf Befehl ohne Wetterabruf < 30 s ab Eingang (Issue-Vorschlag).

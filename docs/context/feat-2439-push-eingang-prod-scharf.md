# Context: feat-2439-push-eingang-prod-scharf

## Request Summary
Restarbeit an #2439: Der Push-Eingang für Befehle (seven.io-Webhook für Premium-SMS, Stalwart-Webhook für E-Mail; Poll bleibt Fallback) ist im Code seit 19.10. live (`e7832bd14`, PR #2579), auf Prod aber nicht aktiv — es sind keine Prod-Hooks registriert, seit 15.10. kein POST auf `/api/webhooks/sms|mail/`. Ziel: Sofort-Weg in Prod einschalten, die offenen Live-ACs belegen, die drei fehlerhaften Live-Tests korrigieren.

## Offene Punkte (aus Issue-Kommentaren 15.10./19.10.)
| # | Punkt | Spec / AC |
|---|---|---|
| 1 | SMS-Nachversuch 0/3/8 s mit echter SMS auf Staging neu messen (`test_ac1` grün, kein EOF) | Antwortzeit AC-14 (Z.142) |
| 2 | Prod-Hooks registrieren: seven.io `sms_mo`, Stalwart `message-ingest.ham` | Push AC-1/AC-11; Antwortzeit AC-15 (Z.145) |
| 3 | `received_total` je Kanal vor/nach echtem Prod-Befehl | Antwortzeit AC-15 (Z.146) |
| 4 | Premium-SMS-Eingang auf Prod messen | Antwortzeit AC-3 (Z.109), AC-4 (Z.112), AC-12 (Z.136) |
| 5 | Telegram HEUTE/MORGEN messen | Antwortzeit AC-4 |
| 6 | Live-Tests korrigieren: `test_ac12`, `test_ac5`, `test_ac4` (+ `test_ac3`) | — |
| — | Erledigt (verifiziert): Runbook-Eventname `message-ingest.ham` (`docs/runbooks/inbound-webhooks.md:56-57,102-103`); henemm-infra Nginx versioniert (`a1c596d`), missed-Check scharf (PR #268, `f89f442`, `scripts/check-gregor20.sh:962-1028`) | Push AC-13, Antwortzeit AC-16/17 |

## Related Files
| File | Relevance |
|------|-----------|
| `docs/specs/modules/feat_2439_befehle_push_eingang.md` | AC-1..13 (Z.121-145), u. a. AC-11 Hooks beider Umgebungen, AC-12 Signatur gegen echten Mitschnitt |
| `docs/specs/modules/feat_2439_befehle_antwortzeit.md` | AC-1..17 (Z.103-152), Testplan Z.158-160 |
| `tests/e2e/test_push_eingang_befehle_staging.py` | Live-Tests; Marker `live`+`staging`, skipif `GZ_STAGING_E2E!=1` (Z.36-43); nur Env, keine Fixtures (Z.141-146) |
| `docs/runbooks/inbound-webhooks.md` | seven.io-Hook (Z.26-34), Signatur (Z.37-43), IP-Allowlist (Z.48-51), Stalwart (Z.53-59), Inbetriebnahme-Reihenfolge (Z.93-103), Staging-Beleg (Z.105-112) |
| `internal/handler/inbound_webhooks.go` | Handler: Env fehlt → 503 (Z.101-104/148-151), Abweisung 403 + `RecordPushRejected` (Z.82-86), gültig → `RecordPushReceived` + `Kick` (Z.91-92) |
| `internal/scheduler/push_kick.go` | `kickRetryDelays` 0/3/5 s (kumuliert 0/3/8), Zähler `pushField` (Z.203-213), `cronPoll` missed-Zählung (Z.173-189) |
| `internal/router/router.go` | Webhook-Routen Z.174-175; Status-Endpoint Z.310-311 (Header `X-GZ-Status-Token`) |
| `.claude/tools/seven_journal.py` | Nur-Lese-Werkzeug seven.io-Journal (inbound/outbound) |
| `.claude/tools/staging_befehl_pruefen.py` | Staging-Befehlsprobe, deckt NUR E-Mail ab |
| `src/app/loader.py:1446-1498` | `lookup_user_by_telegram_chat_id` — echter Treffer schlägt Testtreffer |
| `src/app/config.py:56` | `is_test_user_id` |
| `/home/hem/henemm-infra/scripts/check-gregor20.sh:962-1028` | missed_total-Check (scharf seit 19.10.) |

## Befunde zu den Live-Tests
- **test_ac1 (Z.97-124):** Grenze `GRENZE_SEKUNDEN=60` (Z.34) misst Webhook→Poll-Lauf, nicht die Antwort; ein späterer `*/5`-Tick überschreibt `last_run` → falsches Rot, wenn nicht direkt nach der SMS gefahren.
- **test_ac4 (Z.244-270), test_ac3 (Z.228), test_ac12 (Z.293):** verlangen die Kanalgruppe `premium_sms` auf Staging — strukturell unmöglich (Herkunftssperre). Prod-Selftest führt sie schon als `NOT_MEASURABLE_ON_STAGING` (`docs/artifacts/feat-2439-befehle-antwortzeit/prod-selftest.md:17-26`, nur im Haupt-Checkout).
- **test_ac5 (Z.273-290):** ruft `_kalt` nicht auf, filtert auf eine Trip-ID. `_kalt` prüft DWD-Downloadzeilen (Z.157, 211-214); `fr_direct` (Korsika) erzeugt keine solche Zeile — es fehlt ein Kalt-Signal für Korsika.
- **test_ac12 (Z.298-307):** paart jedes HEUTE mit dem nächsten HELP im gesamten Messfenster ohne Zeitgrenze → 813 s. Nötig: Paar nur bei HELP innerhalb des Fensters nach HEUTE-Start ohne dazwischenliegenden Befehl; HEUTE ohne Partner überspringen.
- Die Tests lösen nichts aus; der Treiber, der die Befehle sendet, ist nicht im Repo.

## Existing Patterns
- Telegram-Webhook mit Secret im Pfad (`/api/webhooks/telegram/{secret}`), Registrierskript `scripts/telegram_set_webhook.sh` — für seven.io/Stalwart gibt es kein solches Skript.
- Messbarkeit auf Staging: `NOT_MEASURABLE_ON_STAGING` mit ausdrücklichem Ersatzweg (Memory `reference_staging_hat_keinen_dateizugriff_fuer_hem`).
- Status-Abfrage: `GET /api/scheduler/status` + `X-GZ-Status-Token` (Env `GZ_STATUS_TOKEN`), auf Staging zusätzlich Basic-Auth.

## Dependencies
- Upstream: seven.io Hooks-API (`POST gateway.seven.io/api/hooks`, `event_type=sms_mo`, `event_filter`=Service-Nummer), Stalwart-Webhook (Event `message-ingest.ham`), Nginx-Locations (henemm-infra, live und versioniert).
- Downstream: `check-gregor20.sh` missed-Check (BetterStack-Heartbeat), Befehlsantworten aller Kanäle.

## Existing Specs
- `docs/specs/modules/feat_2439_befehle_push_eingang.md`
- `docs/specs/modules/feat_2439_befehle_antwortzeit.md`

## Risks & Considerations
1. **DRINGEND — Fehlalarm steht bevor:** Der missed-Check ist seit 19.10. scharf, die Prod-Hooks fehlen aber (Widerspruch zu Runbook Z.99-101). `cronPoll` (`push_kick.go:173-189`) zählt jeden per Cron verarbeiteten Befehl ohne Kick als `missed`. Der nächste echte Prod-Befehl per SMS/Mail ⇒ FAIL ⇒ kein Heartbeat ⇒ Alarm-Mail an den PO (einmal je Zuwachs, Basis wird auch bei FAIL fortgeschrieben, Z.1013-1015). Reihenfolge: Hooks registrieren VOR dem nächsten Befehl, oder Check bis dahin entschärfen.
2. **Echte SMS von der zweiten seven.io-Nummer:** per API mit `from=…902` kommt nur als `InfoSMS` an; …902 hängt nicht am Zugang hinter `GZ_SEVEN_API_KEY` (nur …595). Der Eingangstest am 27.09. lief über das Handy des PO. Für AC-14 und Prod-AC-3/4/12 ist eine echte eingehende SMS nötig — Weg klären, ohne den PO nach Schlüsseln oder Verifizierungsanrufen zu fragen (Memory `feedback_premium_sms_empfang_ueber_zweite_seven_nummer_selbst_pruefen`).
3. **Signatur gegen Prod unbelegt:** Runbook Z.38 verweist auf `docs/artifacts/feat-2439-befehle-push-eingang/seven-signatur-nachweis.md` — Datei existiert nicht; Fixture ist laut Z.45-46 kein Mitschnitt. Echte Staging-Zustellung am 15.10. wurde akzeptiert (`rejected_total 0`). Nach Prod-Registrierung `rejected_total` beobachten.
4. **Ein Hook auf dieselbe Service-Nummer weckt beide Umgebungen** (Staging-Hook 4750 existiert). Gewollt; die Sperre gegen Doppelantwort hängt allein an der Herkunftssperre auf Staging.
5. **Telegram auf Staging:** verwaistes Konto `e2ek71785826879` teilt die `telegram_chat_id` mit `tg-live-e2e` und gewinnt (`loader.py:1446-1498`). Lösung: `telegram_chat_id` im verwaisten Profil leeren; Daten unter `/var/lib/gregor-staging` gehören `claude-gregor`, für `hem` nicht lesbar. Alternative: Messung über Prod-Testchat.
6. **Kein Kalt-Signal für Korsika** (`fr_direct`) — AC-5 ist ohne neue Log-Zeile nicht ehrlich auf „kalt" prüfbar.
7. **Hook-IDs** (Staging seven.io 4750, Stalwart `jjsl7jjqacaa`) sind nirgends dokumentiert; Runbook nennt keine Prod-Hook-IDs.
8. **Zähler nur im Speicher:** zwischen Vorher-/Nachher-Messung (AC-15) kein Neustart/Deploy.
9. Die feat-2439-Artefaktordner (`prod-selftest.md`) liegen nur im Haupt-Checkout, nicht auf `origin/main`.

## Analysis

### Type
Feature (Restarbeit #2439: Inbetriebnahme Prod + Korrektur Live-Tests). Kein Produktfehler im Push-Code.

### Messungen 2026-10-20 (lesend)
- **Prod-Env vollständig:** `/home/hem/gregor_zwanzig/.env` setzt `SEVEN_WEBHOOK_PATH_SECRET`, `SEVEN_WEBHOOK_SIGNING_KEY`, `STALWART_WEBHOOK_PATH_SECRET`, `STALWART_WEBHOOK_SECRET`, `GZ_STATUS_TOKEN` (Staging ebenso). Nginx-Locations Prod/Staging existieren (henemm-infra `nginx/gregor20.henemm.com.conf:39,55`, `staging…conf:41,58`). **Es fehlt allein die Registrierung bei seven.io und Stalwart für Prod.**
- **Prod-Push-Status 09:15:** `premium_sms_poll` und `inbound_command_poll` je `received_total 0`, `rejected_total 0`, `missed_total 0`, `last_run ok`. Noch kein Fehlalarm ausgelöst.
- **seven.io-Konto (`GZ_SEVEN_API_KEY`, lesend `GET /api/hooks`):** genau ein Hook — ID 4750, `sms_mo`, Filter `4916092172595`, Ziel Staging, angelegt 2026-10-14 19:12. ⇒ Der Schlüssel sieht die Servicenummer; die Prod-Registrierung ist mit vorhandenem Zugang per API möglich.
- **Mail-Handler filtert nicht nach Empfänger** (`internal/handler/inbound_webhooks.go:146-164`): jede von Stalwart als `message-ingest.ham` gemeldete Mail zählt als `received` und weckt den Poll — auch Mails an andere Postfächer, sofern der Stalwart-Hook nicht selbst filtert. Folgen: (a) „`received_total` steigt" ist allein kein Beleg für einen Befehl → Beleg muss Eingang dem konkreten Befehl zeitlich zuordnen (`last_received` ≈ Sendezeit, Antwort zugestellt); (b) fremde Mails im 5-Min-Fenster (`pushMissedWindow`, `push_kick.go:29`) können ein echtes `missed` verdecken. In der Spec prüfen, ob der Stalwart-Hook einen Empfängerfilter erlaubt.
- **`missed` bedingungslos ist schon bewacht:** `internal/scheduler/scheduler_kick_test.go:633` `TestPushMissed_CronLaufMitBefehlenOhneKickZaehltAlsVerpasst`. Kein neues AC nötig, nur Verweis.
- `prod_selftest.py` prüft keine Push-Zähler. `.env.example` nennt die vier Webhook-Variablen nicht.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `scripts/seven_hooks.sh` | CREATE | `list\|set\|delete` für seven.io-Hooks, idempotent (gleiche Ziel-URL+Event ⇒ überspringen), Secret in Ausgabe maskiert; Stil wie `scripts/telegram_set_webhook.sh` |
| `docs/runbooks/inbound-webhooks.md` | MODIFY | Hook-IDs Staging (4750, Stalwart `jjsl7jjqacaa`) + Prod, Skript-Aufruf, Signatur-Aussage Z.38 auf tatsächlichen Beleg korrigieren (Nachweis-Datei existiert nicht) |
| `tests/e2e/test_push_eingang_befehle_staging.py` | MODIFY | `test_ac1` Gültigkeitsprüfung (überholte Messung ⇒ skip mit Hinweis statt Rot); `test_ac3/ac4/ac12` ohne `premium_sms` auf Staging (Herkunftssperre), expliziter Verweis auf Prod-Messweg; `test_ac12` Paarung mit Zeitgrenze und ohne Zwischenbefehl; `test_ac5` nur kalte Korsika-Läufe |
| `.claude/tools/` (neues Lese-Werkzeug, Name in Spec) | CREATE | Premium-SMS-Antwortzeiten aus Prod-Journal auswerten (Ersatzweg für Staging-unmögliche ACs) |
| Provider `fr_direct` (Datei in Spec festlegen) | MODIFY | Log-Zeile mit `downloads=N` als Kalt-Signal, analog DWD-Zeile |
| `.env.example` | MODIFY | vier Webhook-Variablen dokumentieren |
| `.claude/hooks/prod_selftest.py` | optional MODIFY | `received_total`/`rejected_total` ausgeben — nur wenn er einen offenen Punkt bedient (Regel-Budget) |

### Abdeckung der offenen Punkte
| # | Punkt | Wie abgedeckt |
|---|---|---|
| 1 | SMS-Nachversuch AC-14 (echte SMS auf Staging) | Echte eingehende SMS nötig; per API von …902 nur `InfoSMS`. Belegter Weg bisher nur Handy des PO. Ersatz: seven.io-Hook weckt Staging UND Prod — ein echter Prod-Befehl (z. B. nächster PO-Befehl unterwegs) erzeugt zugleich die Staging-Messung. Offener Punkt für die Spec. |
| 2 | Prod-Hooks registrieren | seven.io per `seven_hooks.sh set` (Zugang belegt), Stalwart im Admin; IDs ins Runbook |
| 3 | `received_total` vor/nach Prod-Befehl | Mail: selbst über Testkonto an Prod-Befehlsadresse senden, zeitlich zugeordnet. SMS: s. Punkt 1 |
| 4 | Premium-SMS-Eingang Prod (Antwortzeit AC-3/4/12) | neues Lese-Werkzeug auf Prod-Journal |
| 5 | Telegram HEUTE/MORGEN (AC-4) | Staging: `telegram_chat_id` des verwaisten Kontos `e2ek71785826879` leeren (Daten gehören `claude-gregor`, Weg in Spec klären) — oder Messung über Prod-Testchat |
| 6 | Live-Tests `ac1/ac3/ac4/ac5/ac12` | siehe Affected Files |

### Scope Assessment
- Files: ~6–7
- Estimated LoC: +250/-40 (Skript ~90, Testkorrekturen ~60, Prod-Messwerkzeug ~60, `fr_direct` ~15, Test ac5 ~20). Werkzeuge unter `.claude/` und Doku zählen voraussichtlich nicht ins LoC-Limit — vor `/40` mit `workflow.py status` klären; ggf. `loc_limit_override 500`.
- Risk Level: MEDIUM — Code-Risiko gering (fast nur Tests/Werkzeuge, eine Log-Zeile), aber Betriebsänderung an Prod (Hook weckt Prod-Poll; Fehlbetrieb wäre stiller 403 oder Doppelantwort).

### Technical Approach (Empfehlung)
1. **Hooks zuerst** (Runbook-Reihenfolge Z.99-101): seven.io per neuem idempotentem Skript, Stalwart manuell im Admin; Hook-IDs dokumentieren.
2. **`missed`-Zählung NICHT aufweichen** (nicht an „mind. ein received seit Start" koppeln): ein kompletter Push-Ausfall — genau der heutige Prod-Zustand — bliebe sonst ewig stumm, und jeder Neustart setzt `received` auf 0. Bewacht durch `scheduler_kick_test.go:633`.
3. Nach Registrierung je Kanal einen echten Befehl, Zähler vor/nach ohne Deploy dazwischen (Zähler nur im Speicher), `rejected_total` muss 0 bleiben (Signatur gegen Prod).
4. Live-Tests korrigieren; Staging-unmögliche Premium-SMS-Teile über Prod-Lese-Werkzeug mit `NOT_MEASURABLE_ON_STAGING`-Muster.
5. Kalt-Signal `fr_direct` als einzige Produktcode-Änderung.

### Dependencies
- seven.io Hooks-API (Zugang `GZ_SEVEN_API_KEY` belegt), Stalwart-Admin (`message-ingest.ham`), Nginx henemm-infra (live), `check-gregor20.sh` missed-Check (scharf).
- Herkunftssperre auf Staging verhindert Doppelantwort, weil ein Hook auf dieselbe Servicenummer beide Umgebungen weckt — vor Prod-Registrierung aktiv bestätigen.

### Risks (Ergänzung)
- **Korrektur zu Kontext-Risiko 1:** Nicht „genau eine Alarm-Mail" — solange Prod-Hooks fehlen, zählt **jeder** per Cron verarbeitete Prod-Befehl (SMS oder Mail) als `missed` ⇒ je Befehl ein Anstieg ⇒ je Befehl eine Alarm-Mail. Stand 09:15: noch 0.
- IP-Allowlist seven.io nur in Nginx; ändert seven.io die IPs ⇒ stiller 403, sichtbar erst über `missed`.
- Vorschlag fürs henemm-infra-Backlog (nicht dieser Workflow): `check-gregor20.sh` könnte `received_total` mitlesen.
- `PUBLIC_HOST` steht in keiner der beiden `.env`; Runbook verlangt ihn für Staging, trotzdem hat Staging am 15.10. akzeptiert → Variablenname in der Spec prüfen (Prod-Default = Prod-Host, unkritisch).

### Open Questions
- [x] Prod-Hooks: PO-Entscheid 2026-10-20 „regulär im Ablauf" — Registrierung nach Spec-Freigabe und Test, per Skript mit Beleg; Fehlalarme bis dahin hingenommen
- [ ] Echte SMS für AC-14/Prod-SMS-Messung: einziger belegter Weg ist das Handy des PO bzw. dessen nächster echter Befehl — Ersatzweg in Spec festlegen, ohne den PO zum Tester zu machen
- [ ] Erlaubt der Stalwart-Hook einen Empfängerfilter (nur Befehlsadresse)?
- [ ] Telegram-Messung: verwaistes Staging-Konto bereinigen oder Prod-Testchat?

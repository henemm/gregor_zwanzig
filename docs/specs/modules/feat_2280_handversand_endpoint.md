---
entity_id: feat_2280_handversand_endpoint
type: module
created: 2026-10-20
updated: 2026-10-20
status: draft
version: "1.0"
tags: [epic-2345, versand, trip, ortsvergleich, shared, fehlervokabular]
issue: 2280
workflow: feat-2280-handversand-endpoint
---

# Handversand-Endpoint für Trip und Ortsvergleich

## Approval

- [ ] Approved

## Purpose

Ein einziger, kind-neutraler Endpoint `POST /api/briefings/{id}/send?kind=route|vergleich` löst den Handversand eines Briefings aus, für Trip und Ortsvergleich mit **einem** Fehlervokabular, **einer** Antwortform und **einem** Sende-Lock. Heute meldet ein Ortsvergleich „ok", obwohl nichts zugestellt wurde (kein Kanal, alle Kanäle gescheitert) oder antwortet mit einem unlesbaren Serverfehler (keine Wetterdaten). Das widerspricht dem Grundsatz „Erfolg heißt Zustellung" (Epic #2505). Ticket #2280, Epic #2345 Etappe P4. Alle Scheiben S1 bis S3 liegen in dieser einen Spec; nichts wird abgespalten.

### Was sich für den Nutzer ändert

- Ein Ortsvergleich, der nichts zustellen konnte, meldet das jetzt ehrlich und nennt den Grund: kein Kanal eingestellt, Kanäle nicht erreichbar oder keine Wetterdaten.
- Ein Ortsvergleich, der nur Telegram oder SMS nutzt, lässt sich ohne E-Mail-Adresse versenden (vorher: Fehler).
- Doppelklick auf „Senden" beim Ortsvergleich führt zu genau einer Zustellung.

### Bewusste Abweichungen vom Ticket-Zielbild (begründet)

1. **Lock-Schlüssel bleibt unverändert.** Trip: `(user_id, trip_id, report_type)`. Ortsvergleich: `("compare", user_id, preset_id)`. Der Slot-Begriff des Tickets ist beim Trip durch `report_type` abgedeckt; beim Ortsvergleich gibt es im Handversand keinen Slot. Der Trip-Schlüssel wird mit dem Inbound-Pfad (`trip_command_processor.py`) geteilt; eine Änderung würde dessen Kollisionen verschieben. Das ist Zielbild-Text, keine Anforderung.
2. **`report_type`-Default `morning` im neuen Endpoint.** Frontend und Vorschau nehmen `morning`. Der Alt-Delegate `/api/scheduler/trips/{id}/send` behält `evening`, weil Bestandsaufrufer darauf bauen.
3. **`winner` und `empfaenger_count` entfallen** aus der Antwort. Kein Leser im Frontend, kein Test mit Nutzerwirkung.
4. **`detail` bleibt ein deutscher Text** (Fehlerform A) statt eines Objekts. Das Frontend zeigt `detail` bei 4xx unverändert an; ein Objekt würde `sendOutcome.ts` und viele Tests brechen. Der maschinenlesbare Code steht zusätzlich auf oberster Ebene als `code`.
5. **`kind` im Query, nicht im Pfad** — wie beim Vorschau-Dispatcher (#2283, ADR-0023). Das Frontend-Wort `trip` wird beim Aufruf auf `route` abgebildet (bestehende Zuordnung, keine zweite).

## Source

- **Python-Core:** `src/services/send_outcomes.py` (neu), `api/routers/briefings_send.py` (neu, Router ohne Prefix, neben `preview.py`), `api/routers/scheduler.py`, `api/main.py`, `src/services/trip_report_scheduler.py`, `src/services/notification_service.py`, `src/services/scheduler_dispatch_service.py`, `tests/test_success_status_guard.py`
- **Go-API:** `internal/handler/send_proxy.go` (neu, `forwardSend`), `internal/handler/briefing_send.go` (neu), `internal/handler/proxy.go`, `internal/handler/compare_preset.go`, `internal/router/router.go`
- **Frontend:** `frontend/src/lib/utils/sendOutcome.ts`, `frontend/src/lib/components/shared/subscriptionExec.ts`, `frontend/src/routes/compare/[id]/+page.svelte`
- **Doku:** `docs/reference/api_contract.md`, `openapi.yaml`, ADR-0023 (Nachtrag)
- **Identifier:** `POST /api/briefings/{entity_id}/send`, `forwardSend`, `send_outcomes` (Vokabular + Ableitung), `sendSubscription`

## Estimated Scope

- **LoC:** produktiv ca. +400 bis 450 / −120 (Python ca. 200, Go ca. 100–130, Frontend ca. 50). `loc_limit_override 500` ist gesetzt. Test-LoC zählen nicht zum Limit.
- **Files:** ca. 14 produktiv plus Tests
- **Effort:** medium bis high. Risiko MEDIUM: zentraler Versandpfad beider Flächen; der Cron-Pfad des Ortsvergleichs ist über die geteilte Ableitung mitbetroffen.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `/api/briefings` Dispatcher (`briefing_subscription.go`, `briefing_preview.go`) | Go-Handler | Vorbild: `kind`-Pflicht, `writeBriefingKindRequired`, `briefingPreviewTarget`, `ValidEntityID` |
| `forwardPreview` (`preview_proxy.go`) | Go | Vorbild für Delegate-Muster; **nicht** Basis, da ohne `context.WithoutCancel` |
| `appendUserID`, `middleware.UserIDFromContext` | Go | `user_id` aus Auth, Client-Wert verwerfen (ADR-0003) |
| `sendProxyTimeout` (300 s, `proxy.go`) | Go | gemeinsames Zeitlimit beider Pfade |
| `try_acquire_send_lock` (`send_lock.py`) | Python | bestehender Lock, generisch, unverändert |
| `send_test_report_outcome`, `send_on_demand_report` (`trip_report_scheduler.py`) | Python | Trip-Versand; teilt den Lock-Schlüssel mit Inbound |
| `send_compare_preset`, `send_one_compare_preset` (`scheduler_dispatch_service.py`) | Python | Ortsvergleich-Versand (Handversand und Cron) |
| `NotificationService.send_compare_report` → `NotificationResult` | Python | liefert `sent`, `failed_channels`, `blocked_channels` |
| `sendSubscription` (`subscriptionExec.ts`, #2278) | Frontend | einziger Versand-Auslöser |
| ADR-0023, ADR-0003, ADR-0062, ADR-0088 | Entscheidungen | Dispatcher, Mandantentrennung, Core-Auth, fcntl-Lock |

## Implementation Details

**Scheiben (Reihenfolge verbindlich, S1 → S2 → S3)**

| Scheibe | Inhalt |
|---|---|
| S1 Python | Vokabular + geteilte Ableitung, Ortsvergleich-Fehlerfälle, neuer Endpoint, Alt-Routen als Delegates, Wächter-Bestand entfernen |
| S2 Go | `forwardSend`, Dispatcher-Route mit `kind`/ID-Prüfung, Alt-Handler als Delegates |
| S3 Frontend | Send-URL an einer Stelle, `compare/[id]` über `sendSubscription`, Anzeigetexte, Testumstellung, Doku |

**Ein Vokabular, eine Ableitung (Trip/Ortsvergleich-Teilung).** `src/services/send_outcomes.py` hält in einer Datei die Zuordnung Code → (HTTP-Status, deutscher Text) für `no_stage`, `no_weather`, `no_channels`, `channels_unreachable`, `already_in_progress`, `not_found`, `invalid_report_type`, `smtp_not_configured`. Die Texte wandern aus `scheduler.py` (bisher Zeilen 316/326/336–338/351–353/362) hierher. Dazu kommt **eine** Funktion, die aus einem `NotificationResult` den Ausgang ableitet (`no_channels` / `channels_unreachable` / zugestellt). Sie ersetzt die bisher nur im Trip vorhandene Ableitung (`trip_report_scheduler.py` um Zeile 2025–2038) und wird von Trip **und** Ortsvergleich benutzt. Es gibt kein eigenes `no_recipient`; `no_channels` gilt nur, wenn wirklich kein Kanal wirksam ist.

**Ein Helfer, zwei Delegates (Python).** Der neue Router `briefings_send.py` hat keinen Prefix (`/api/briefings/{entity_id}/send`), mit `kind: Query(...)`, `user_id: Query(...)` und `report_type` (nur bei `route`). Er ruft einen gemeinsamen Helfer, der je `kind` den Trip- oder Ortsvergleich-Versand aufruft und Fehler **ausschließlich** über das Vokabular abbildet. Die beiden Alt-Routen in `scheduler.py` rufen denselben Helfer; die Fehler-Mappings gibt es danach nur noch einmal.

**Fehlerform:** `{"detail": "<deutscher Text>", "code": "<code>"}` mit passendem HTTP-Status. **Erfolgsform:** `{status:"ok", kind, id, sent:true}` plus `report_type` (nur `route`) bzw. `fehlende_orte` (nur `vergleich`). Ein Fehlschlag ist immer 4xx, nie 200 mit `sent:false`.

**Ortsvergleich-Änderungen (Kern der Fehlerbehebung):**
- `send_compare_report` setzt `no_channel_configured`, wenn keine Kanäle wirksam sind (Parität zum Trip).
- `send_compare_preset` wertet `send_result` aus. `channels_unreachable` führt zu 422 ohne Anker-Reset und ohne gespeicherten Erfolgs-Status (spiegelt `VERMERK_AUSGAENGE` beim Trip).
- Scheitern alle Orte an den Wetterdaten, wird die Exception als `no_weather` (422) abgebildet statt als 500.
- `mail_to` ist nur Pflicht, wenn E-Mail unter den wirksamen Kanälen ist. Das wirkt bewusst **auch im Cron-Pfad** (Kanal-Parität). Der Cron-Wrapper fängt Exceptions weiter ab; ein Cron-Lauf ohne Kanal wird nicht mehr als „versendet" verbucht.
- „E-Mail wirksam" heißt beim Ortsvergleich: E-Mail ist immer gewählt (`compare_alert_channels.py`, `channels = {"email"}`; `ComparePreset` hat kein `send_email`, KL-6 in `versand_tab_vergleich.md`) **und** `mail_to` ist vorhanden — analog zur Sendefähigkeit bei Telegram/SMS. Ohne `mail_to` fällt E-Mail aus der wirksamen Menge; den Fall „E-Mail wirksam, `mail_to` fehlt" gibt es damit per Definition nicht. Die AC-7-Gegenprobe ist deshalb „ohne `mail_to` und ohne Telegram/SMS bleibt Fehler" (`test_ac7_gegenprobe_ohne_mail_to_und_ohne_telegram_sms_bleibt_fehler`, 422 `no_channels`).

**Go.** `forwardSend` ist eine einzige Proxy-Funktion (`context.WithoutCancel`, `sendProxyTimeout`, `appendUserID`, Body und Status durchreichen). `BriefingSendHandler` prüft `kind` (`isValidBriefingKind`) und `store.ValidEntityID` selbst und antwortet bei Fehlern in Fehlerform A (`writeSendError`, `{"detail","code"}`): 400 `kind_required` bzw. 400 `validation_error`. Bewusst **nicht** über `briefingPreviewTarget`/`writeBriefingKindRequired`/`bailIf` — deren Form `{"error":"<code>"}` ist der dokumentierte Vertrag von Vorschau und Briefing-CRUD (`api_contract.md`) und bleibt unverändert. `forwardSend` meldet eigene Fehler ebenfalls in Form A: 502 `upstream_unreachable` (Python-Core nicht erreichbar oder `sendProxyTimeout` überschritten), 500 `proxy_error` (Anfrage nicht baubar). Die Alt-Handler (`proxy.go`, `compare_preset.go`) werden Delegates auf `forwardSend`; das Duplikat entfällt. Die Alt-Routen bleiben ohne ID-Validierung (Bestandsverhalten), die Gleichheit der Antwort wird geprüft.

**Frontend.** `sendOutcome.ts` baut die Send-URL an genau einer Stelle (`/api/briefings/{id}/send?kind=…[&report_type=]`). `sendSubscription` bildet `trip → route` ab. `compare/[id]/+page.svelte` (Zeile 233) ruft nicht mehr `sendComparePreset` direkt auf, sondern `sendSubscription('vergleich', …)`. Die neuen Codes `no_channels`, `channels_unreachable`, `no_weather` zeigen den deutschen `detail`-Text unverändert an (bestehender 4xx-Pfad).

**Doku.** `docs/reference/api_contract.md` und `openapi.yaml` (kennt bisher weder `/send` noch `/api/briefings`) beschreiben den neuen Endpoint, Alt-Routen sind als „Delegate" markiert. ADR-0023 bekommt einen Nachtrag (der Dispatcher über `kind` ist das dort beschlossene Modell, `/send` fügt sich ein). Kein neues ADR.

## Expected Behavior

- **Input:** `POST /api/briefings/{id}/send?kind=route|vergleich` (Go setzt `user_id` aus der Anmeldung; bei `route` optional `report_type`).
- **Output:** Erfolg `{status:"ok", kind, id, sent:true, …}`; Fehler `{detail, code}` mit 400/404/409/422.
- **Side effects:** Zustellung über die konfigurierten Kanäle des Nutzers; Anker-Reset und Erfolgs-Status nur bei echter Zustellung.

## Acceptance Criteria

- **AC-1:** Given ein angemeldeter Nutzer mit einem Trip und einem Ortsvergleich, die je einen wirksamen Kanal haben / When er `POST /api/briefings/{id}/send` mit `kind=route` bzw. `kind=vergleich` aufruft / Then wird das jeweilige Briefing zugestellt und die Antwort ist 200 mit `status:"ok"`, `kind`, `id` und `sent:true`. *(Neuer Endpoint für beide Arten)*
  - Test: Python-Kern `tests/tdd/test_briefings_send_endpoint.py` für beide kinds; Go-Dispatcher-Test.

- **AC-2:** Given ein Aufruf des Endpoints / When `kind` fehlt oder ist ungültig (zum Beispiel `trip`) / Then antwortet der Server mit 400 und `code:"kind_required"` und es wird nichts versendet. *(kind Pflicht)*
  - Test: Go `briefing_send_test.go` (Vorbild `briefing_preview_test.go:243`) und Python-Endpoint-Test.

- **AC-3:** Given Nutzer A besitzt ein Briefing und Nutzer B ist angemeldet / When B die ID von A aufruft, oder eine unbekannte ID, oder eine ungültig geformte ID / Then antwortet der Server mit 404 (fremd/unbekannt) bzw. 400 (ungültig geformte ID), und bei A wird nichts ausgelöst. *(ID und Eigentümerschaft, Zwei-Nutzer-Test)*
  - Test: Python- und Go-Test mit zwei verschiedenen Nutzern; Client-gesendeter `user_id`-Wert wird verworfen (`appendUserID`).

- **AC-4:** Given ein Ortsvergleich ohne wirksamen Kanal / When der Versand ausgelöst wird / Then antwortet der Server mit 422 und `code:"no_channels"` mit genau demselben Text wie beim Trip, statt wie bisher mit 200 „ok". *(Ortsvergleich ohne Kanal)*
  - Test: Python-Kern; Textgleichheit gegen den Trip-Fall (`tests/unit/test_trip_send_endpoint_no_channels.py` bleibt grün).

- **AC-5:** Given ein Ortsvergleich, dessen Kanäle alle beim Senden scheitern / When der Versand ausgelöst wird / Then antwortet der Server mit 422 und `code:"channels_unreachable"`, der Anker wird nicht zurückgesetzt und es wird kein Erfolgs-Status gespeichert. *(Ortsvergleich, alle Kanäle gescheitert)*
  - Test: Python-Kern mit ausgefallenem Transport; Prüfung von Anker-Stand und gespeichertem Preset-Status vor und nach dem Aufruf.

- **AC-6:** Given ein Ortsvergleich, für dessen Orte keine Wetterdaten zu bekommen sind / When der Versand ausgelöst wird / Then antwortet der Server mit 422 und `code:"no_weather"` und einem verständlichen deutschen Text, statt mit einem Serverfehler 500. *(Ortsvergleich ohne Wetterdaten)*
  - Test: Python-Kern mit Provider, der für alle Orte scheitert (`comparison_parallel`).

- **AC-7:** Given ein Ortsvergleich, dessen wirksame Kanäle nur Telegram und/oder SMS sind und der keine `mail_to` hat / When er per Hand oder per Cron versendet wird / Then wird er zugestellt; eine `mail_to` ist nur Pflicht, wenn der E-Mail-Kanal wirksam ist. *(Nur Telegram/SMS, keine E-Mail-Adresse)*
  - Test: Python-Kern für Handversand und `send_one_compare_preset` (Cron-Pfad); Gegenprobe: E-Mail-Kanal wirksam und `mail_to` fehlt bleibt Fehler.

- **AC-8:** Given ein Cron-Lauf für einen Ortsvergleich ohne wirksamen Kanal oder mit nur gescheiterten Kanälen / When der Lauf endet / Then wird er nicht als „versendet" verbucht (kein Erfolgs-Status, kein Anker-Reset) und der Cron-Wrapper bricht dabei nicht ab. *(Cron-Pfad bucht ehrlich)*
  - Test: Python-Kern `tests/tdd/test_compare_preset_send.py` erweitert.

- **AC-9:** Given ein beliebiger Fehlschlag des Endpoints für Trip oder Ortsvergleich / When die Antwort gelesen wird / Then enthält sie `detail` (deutscher Text, unverändert anzeigbar) und auf oberster Ebene `code`, und alle Codes samt Texten stehen in **einer** Datei (`send_outcomes.py`). *(Einheitliche Fehlerform, ein Vokabular)*
  - Test: Python-Test über alle Codes (Status, Text, `code`); Wächter-Test, dass `scheduler.py` keine eigenen Fehlertexte für diese Fälle mehr enthält (Verhaltenstest über die Endpoints, kein Dateiinhalt-Check).

- **AC-10:** Given eine erfolgreiche Zustellung / When die Antwort gelesen wird / Then lautet sie `{status:"ok", kind, id, sent:true}` plus `report_type` nur bei Trip und `fehlende_orte` nur bei Ortsvergleich; ein Versand ohne Zustellung liefert nie `status:"ok"`. *(Einheitliche Erfolgsform, Erfolg heißt Zustellung)*
  - Test: Python-Kern; `tests/test_success_status_guard.py` darf den Ortsvergleich-Versand nicht mehr als Ausnahme führen.

- **AC-11:** Given der Wächter `tests/test_success_status_guard.py` / When er läuft / Then enthält er keinen Bestandseintrag `send_compare_preset` mehr und bleibt grün, weil der Status aus dem echten Ausgang abgeleitet wird. *(Wächter-Bestandseintrag entfernt)*
  - Test: Lauf des Wächters; Gegenprobe: ein fest verdrahtetes „ok" in `send_compare_preset` macht ihn rot.

- **AC-12:** Given ein Ortsvergleich, dessen Versand gerade läuft / When der Versand ein zweites Mal ausgelöst wird / Then antwortet der Server mit 409 und `code:"already_in_progress"`, und der Empfänger erhält genau eine Zustellung. *(Doppelauslösung Ortsvergleich)*
  - Test: Kern `tests/tdd/test_compare_send_lock.py` (besteht bereits, bleibt grün); Live-Schicht: zwei gleichzeitige Aufrufe auf Staging mit Wegwerf-Nutzer `gregor-test+…`, Zählung der zugestellten Mails per IMAP = 1.

- **AC-13:** Given die bisherigen Routen `/api/scheduler/trips/{id}/send` und `/api/scheduler/compare-presets/{id}/send` (Python) bzw. deren Go-Pendants / When sie aufgerufen werden / Then liefern sie dieselbe Antwort- und Fehlerform wie der neue Endpoint (gleicher Status, `detail`, `code`), und die Alt-Trip-Route behält den Default `report_type=evening`. *(Alt-Routen als Delegates)*
  - Test: Python- und Go-Test mit Delegate-Gleichheit (gleiche Eingabe, gleiche Antwort); Bestandstests der Alt-URLs bleiben grün.

- **AC-14:** Given der neue Dispatcher und die beiden Alt-Handler in Go / When ein Versand weitergereicht wird / Then laufen alle über `forwardSend`, die Anfrage überlebt einen Verbindungsabbruch des Browsers (`context.WithoutCancel`), nutzt `sendProxyTimeout` und setzt `user_id` über `appendUserID`; der Client-Wert wird verworfen. *(Go: eine Proxy-Funktion)*
  - Test: Go `send_proxy_context_test.go` und `proxy_timeout_chain_test.go` bleiben grün und werden auf den Dispatcher ausgeweitet; Spoofing-Test mit fremdem `user_id` im Query.

- **AC-15:** Given die Oberfläche von Trip-Liste, Trip-Hub, Ortsvergleich-Liste und Ortsvergleich-Hub / When ein Versand ausgelöst wird / Then entsteht die Send-URL an genau einer Stelle (`sendOutcome.ts`), alle Auslöser laufen über `sendSubscription`, und `compare/[id]/+page.svelte` ruft `sendComparePreset` nicht mehr direkt auf. *(Frontend: eine Stelle, ein Auslöser)*
  - Test: Frontend-Unit `subscriptionExec.test.ts`, `sendOutcome.test.ts` (URL für `route` und `vergleich`, `trip → route`); Verhaltenstest, dass der Hub-Klick den neuen Endpoint trifft.

- **AC-16:** Given ein Ortsvergleich, der nicht zugestellt werden kann / When der Nutzer auf „Senden" klickt / Then sieht er den konkreten Grund (kein Kanal eingestellt, Kanäle nicht erreichbar oder keine Wetterdaten) statt der generischen Fehlermeldung, und `fehlende_orte` wird bei Erfolg weiterhin angezeigt. *(Nutzer sieht den konkreten Grund)*
  - Test: Frontend-Unit mit den drei 422-Antworten; Playwright gegen Staging `compare-hub-versand-inline`.

## Bereits erfüllte Ticket-ACs (nicht neu bauen)

| Ticket-AC | Stand auf `ed2547b3e` | Nachweis |
|---|---|---|
| Ticket-AC 3 `user_id` Pflicht, kein Rückfall auf `"default"` | Erfüllt (#2151): beide Python-Send-Endpoints haben `user_id: Query(...)`. Der neue Endpoint übernimmt das. | `tests/test_scheduler_router_requires_user_id.py`, `tests/test_user_id_default_guard.py` (AST-Wächter, deckt den neuen Router mit ab) |
| Ticket-AC 4 einheitliches Zeitlimit | Erfüllt: `sendProxyTimeout = 300 s` gilt für beide Pfade. | `internal/handler/proxy_timeout_chain_test.go`, `trip_send_timeout_test.go` |
| Ticket-AC 2 Send-Lock beim Ortsvergleich | Lock und 409 existieren bereits (#2124). **Nur der Staging-Nachweis „genau eine Zustellung" ist neu** → siehe AC-12. | `tests/tdd/test_compare_send_lock.py`, `test_send_idempotenz_lock.py` |

## Test Plan

**Kern-Schicht (deterministisch, ohne Netz):**
- Python: neue Datei `tests/tdd/test_briefings_send_endpoint.py` (AC-1 bis AC-3, AC-9, AC-10, AC-13; AC-9-Wächter als Herkunftsprobe: Vokabular-Eintrag zur Laufzeit durch Marker ersetzt, Alt-Route muss den Marker liefern; `fehlende_orte` über AC-10; unerwartete Ausnahme → 500 `send_failed` für beide Arten auf neuem Endpoint und Alt-Routen; `kind_required`-Wortlaut gegen die geteilte Paritäts-Fixture); `tests/tdd/test_compare_preset_send.py` erweitert (AC-4 bis AC-8); `test_compare_missing_locations.py` bleibt unverändert (Regression); `tests/test_success_status_guard.py` (AC-11).
- Go: `internal/handler/briefing_send_test.go` nach Vorbild `briefing_preview_test.go` (kind, ID, `user_id`, 404, Delegate-Gleichheit, AC-2, AC-3, AC-13, AC-14; Go-Fehler strikt als JSON `{"detail","code"}` geprüft inkl. 502 `upstream_unreachable` und 500 `proxy_error` für Dispatcher und beide Alt-Routen; Alt-Trip-Route reicht `report_type` durch; `kind_required`-Wortlaut gegen die geteilte Paritäts-Fixture); `proxy_timeout_chain_test.go` um den Dispatcher erweitert (AC-14).
- Frontend: `sendOutcome.test.ts`, `subscriptionExec.test.ts` (AC-15, AC-16).
- Mutations-Gegenproben (Adversary): Ableitung auf „immer zugestellt" umdrehen, Anker-Reset bei `channels_unreachable` zurückholen, `mail_to`-Pflicht für alle Kanäle wiederherstellen, `kind`-Prüfung entfernen. Jede muss genau den zuständigen Test rot machen.

**Live-Schicht (nur `/e2e-verify`):** Doppelauslösung eines Ortsvergleichs auf Staging mit Wegwerf-Nutzer `gregor-test+…`, Zählung der Zustellung per IMAP (AC-12); je ein Versand Trip und Ortsvergleich durch den echten Eingang (Oberfläche) mit Mail-Validator-Lauf.

**Testbruch durch die URL-Umstellung (anzupassen):**
- Unit: `sendOutcomeTrigger.test.ts`, `sendOutcome.test.ts`, `subscriptionExec.test.ts`, `trip_liste_aktionen_verhalten.test.ts`, `trip_hub_aktionen_verhalten.test.ts`, `compare_hub_aktionen_verhalten.test.ts`, `compare_hub_test_send_meldung.test.ts`.
- E2E: `trips-list-send`, `aktionsmodell-durchklick`, `issue-767-768-test-briefing`, `send-in-flight-guard`, `compare-hub-versand-inline`, `compare-mobile-vervollstaendigung`, `compare-send-dialog-target.staging`.
- Unverändert bleiben (Regression): `send_proxy_context_test.go`, `proxy_timeout_chain_test.go`, `test_send_idempotenz_lock.py`, `test_compare_send_lock.py`, `test_issue_1148_prod_send_gate.py`, `test_bug_716_test_briefing_silent_fail.py`.

## Known Limitations

- Der Send-Lock gilt nur im eigenen Prozess und hat keine Ablaufzeit; der Cron-Pfad ist davon nicht gedeckt. Das ist Thema von #1777, nicht dieses Tickets.
- Die Alt-Routen bleiben für Altbestand erhalten; ihre Entfernung ist nicht Teil dieses Tickets.
- Ein Ortsvergleich-Zeitplan-Briefing, bei dem alle Kanäle scheitern, wird ehrlich als nicht zugestellt verbucht und im Monitoring (`record_briefing_dispatch_failure`, kind `vergleich`) sichtbar. Ein Nachhol-Versand wie beim Trip (`pending_briefings.json`) fehlt jedoch → #2587.
- `confidence_pct` und andere Inhalte der Briefings sind nicht berührt; geändert wird ausschließlich der Versandweg.
- **Unerwartete Ausnahmen im Versand** fängt `send_briefing` (`api/routers/briefings_send.py`) für neuen Endpoint und beide Alt-Routen ab: Traceback ins Log, Antwort 500 `send_failed` mit deutschem Text aus `send_outcomes.py`. Der Cron-Pfad ist davon unberührt (eigene Fehlerisolierung, AC-8). Das Frontend zeigt bei 500 die generische Serverfehler-Meldung aus `sendOutcome.ts`, nicht den `detail`-Text.
- **Go-seitige Fehlertexte liegen in Go, nicht in `send_outcomes.py`.** Die Fälle `kind_required` (Wortlaut wie im Python-Vokabular; Gleichlauf per geteilter Fixture `tests/fixtures/send_detail_parity/faelle.json` von beiden Seiten per Verhalten geprüft), `validation_error`, `upstream_unreachable` und `proxy_error` entstehen, bevor bzw. ohne dass der Python-Core antwortet; ihre deutschen Texte stehen als Konstanten in `internal/handler/briefing_send.go`. Alle fachlichen Versand-Ausgänge (Python) stehen weiterhin ausschließlich in `send_outcomes.py`. Das Frontend zeigt bei 4xx den `detail`-Text; 502 wird bewusst als „Ergebnis unklar — nicht erneut senden" angezeigt (`sendOutcome.ts`, #2124).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0023 (Nachtrag), kein neues ADR
- **Rationale:** Der Dispatcher über `kind` ist dort bereits beschlossen; `/send` fügt sich als weiterer Eintrag ein. Das Fehlervokabular ist eine Umsetzungsentscheidung dieser Spec, keine neue Grundsatzentscheidung.

## Changelog

- 2026-10-20: Initial spec created (Ticket #2280, Epic #2345 Etappe P4)
- 2026-10-20: AC-Zeilen als Listeneinträge (`- **AC-N:**`) gemäß `_template.md` formatiert, damit der AC-Parser sie erkennt; Wortlaut unverändert
- 2026-10-20: Fix nach /60-validate (bewegliche Teile): Go-Versandweg mit eigener Fehlerform A statt geteilter Vorschau-Helfer; Go-Fehlertexte in Known Limitations dokumentiert; Test Plan an Ist-Stand angepasst
- 2026-10-20: Fix nach Adversary-Dialog (bewegliche Teile): Auffangklausel 500 `send_failed` (F001), Tests für Alt-Trip-Query (F002), `proxy_error` (F003) und `kind_required`-Paritäts-Fixture Go↔Python (F004)

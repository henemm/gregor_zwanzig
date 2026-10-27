# Context: feat-2280-handversand-endpoint

## Request Summary
Issue #2280 (Epic #2345, Etappe P4): ein kind-neutraler Handversand-Endpoint `POST /api/briefings/{id}/send` mit einem Fehlervokabular, einem Send-Lock und einer Antwortform für Trip und Ortsvergleich. Die Alt-Pfade werden zu Delegates.

**Ist-Stand auf HEAD ed2547b3e (2026-10-20). Mehrere Befunde im Ticket sind überholt:**
- `user_id` ist in **beiden** Python-Send-Endpoints bereits Pflicht (`Query(...)`, `api/routers/scheduler.py:282/374`, #2151). Den Rückfall auf `"default"` bewacht `tests/test_user_id_default_guard.py`. → **AC-3 des Tickets ist schon erfüllt.**
- Der Vergleich hat **bereits** einen Send-Lock und antwortet mit 409 (#2124, `scheduler.py:381-386`, `scheduler_dispatch_service.py:775-785`). → **AC-2 ist dem Grunde nach erfüllt.** Der Staging-Nachweis „genau eine Zustellung“ ist noch offen.
- Das Go-Timeout ist **bereits** vereinheitlicht: `sendProxyTimeout = 300 s` (`internal/handler/proxy.go:22`) gilt für beide Pfade, `proxy_timeout_chain_test.go` prüft das. → **AC-4 ist erfüllt.**
- Der Lock-Schlüssel enthält **keinen** Slot: Trip `(user_id, trip_id, report_type)`, Vergleich `("compare", user_id, preset_id)`.

**Echt offen:**
- Es gibt keinen kind-neutralen Send-Endpoint.
- Die Fehlervokabulare sind verschieden.
- Die Antwortformen sind verschieden.
- Beim Vergleich fehlen Fehlerfälle: kein Kanal und alle Kanäle gescheitert ergeben 200 „ok“, keine Wetterdaten ergibt 500.

## Related Files
| Datei:Zeile | Relevanz |
|---|---|
| api/routers/scheduler.py:281-370 | Trip-Send: 404, 422 keine Etappen / SMTP / ungültiger report_type, 422 no_stage/no_weather/no_channels/channels_unreachable (313-355), 409 already_in_progress (359); Antwort `{status, trip_id, report_type, sent}` |
| api/routers/scheduler.py:373-391 | Vergleich-Send: 409, KeyError→404, ValueError→422, sonst wird das Service-Dict durchgereicht |
| api/routers/scheduler.py:30-54 | `_poll_lock` (fcntl, ADR-0088) |
| src/services/send_lock.py:1-30 | In-Memory-Lock pro Prozess, keine TTL, Schlüssel aus `*key_parts` |
| src/services/trip_report_scheduler.py:524-531, 1304-1393 | Trip-Lock-Wrapper, `send_test_report_outcome`, `send_on_demand_report` (Inbound teilt denselben Schlüsselraum) |
| src/services/trip_report_scheduler.py:1555/1709/2025/2037 | Erzeugung der Outcomes no_stage/no_weather/no_channels/channels_unreachable |
| src/services/scheduler_dispatch_service.py:746-791 | `send_compare_preset`: strikt laden, Lock, Antwort `{status:"ok", winner, empfaenger_count, fehlende_orte?}`; **wertet `send_result.sent` nicht aus** |
| src/services/scheduler_dispatch_service.py:455-743 | `send_one_compare_preset`: ValueError bei fehlendem mail_to (517) bzw. wenn kein Ort auflösbar ist (529); Kanal-Fehler nur geloggt (706-711) |
| src/services/comparison_parallel.py:146-152 | scheitern alle Orte → Exception → 500 im Router |
| src/services/notification_service.py:~1366-1460 | `send_compare_report` → `NotificationResult(sent, failed_channels, blocked_channels, blocked_reason_codes)` |
| internal/router/router.go:267, 289, 290-299 | Trip-/Vergleich-Send-Routen; `/api/briefings`-Dispatcher **ohne** `/send` |
| internal/handler/proxy.go:18-25, 163-175, 270-310 | Timeout-Konstanten; `appendUserID` (Anti-Spoofing); Trip-Send-Proxy mit `WithoutCancel` |
| internal/handler/compare_preset.go:608-645 | Vergleich-Send-Proxy, Duplikat des Trip-Proxys |
| internal/handler/briefing_subscription.go:21-110 | kind-Konstanten, `writeBriefingKindRequired`, `GetBriefingHandler` |
| internal/handler/briefing_preview.go:20-64, preview_proxy.go:13-63 | **Vorbild** (#2283): `briefingPreviewTarget`, `forwardPreview` als Delegate |
| api/routers/preview.py:155-195, api/routers/validator.py:378 | Python-Dispatcher `/api/briefings/{id}/preview` und `alert-preview` |
| api/main.py:125-175 | Middleware `X-GZ-Core-Auth`; `user_id` kommt nur als Query vom Go-Proxy |
| frontend/src/lib/utils/sendOutcome.ts:8-146 | Geteilte Auswertung (409, 5xx, 4xx-`detail`); Client-Lock `trip:<id>`/`compare:<id>`; `sendTripBriefing`, `sendComparePreset` (liest `fehlende_orte`) |
| frontend/src/lib/components/shared/subscriptionExec.ts:94-103 | `sendSubscription(kind,id,…)` (#2278) |
| frontend/src/routes/compare/[id]/+page.svelte:41,233 | ruft `sendComparePreset` direkt auf, **an `sendSubscription` vorbei** |

## Existing Patterns
- Dispatcher (ADR-0023): `kind` ist Pflicht (`route|vergleich`), sonst 400 `kind_required`; ID-Prüfung über `store.ValidEntityID`; die Eigentümerschaft prüft der user-scoped Python-Loader (404).
- Alt-Routen als Delegates über eine gemeinsame Proxy-Funktion (#2283, `forwardPreview`).
- Das Frontend zeigt bei 4xx das Python-`detail` wörtlich an; maschinenlesbare Codes gibt es heute nur bei 409.
- `try_acquire_send_lock(*parts)` ist generisch und wiederverwendbar.

## Dependencies
- Upstream-Kette: `sendOutcome.ts`/`subscriptionExec.ts` → Go `router.go:267/289` → Python `/api/scheduler/...` → `send_test_report_outcome` / `send_compare_preset` → NotificationService.
- Mitbetroffen: `trip_command_processor.py:885/922/2665` (Inbound teilt den Trip-Lock-Schlüssel).
- Tests Python: tests/tdd/test_issue_695_test_briefing_send.py, test_send_idempotenz_lock.py, test_compare_send_lock.py, test_compare_preset_send.py, test_compare_missing_locations.py, test_bug_716_test_briefing_silent_fail.py, test_issue_1148_prod_send_gate.py; tests/unit/test_trip_send_endpoint_no_channels.py; tests/test_scheduler_router_requires_user_id.py, tests/test_user_id_default_guard.py, tests/test_success_status_guard.py.
- Tests Go: internal/handler/trip_send_timeout_test.go, compare_preset_send_test.go, proxy_timeout_chain_test.go, send_proxy_context_test.go.
- Tests Frontend: sendOutcome.test.ts, sendOutcomeTrigger.test.ts, subscriptionExec.test.ts, aktionsmodell_seiten_bindung.test.ts, testBriefingLockResponse.test.ts, send_confirm_dialog_sperre.test.ts; E2E: send-in-flight-guard, trips-list-send, compare-hub-versand-inline, issue-767-768-test-briefing, aktionsmodell-durchklick, compare-send-dialog-target.staging.

## Existing Specs
- docs/specs/modules/fix_1756_send_idempotenz_lock.md, fix_2124_versand_nginx_timeout.md, fix_2151_default_fallbacks_scheibe_*.md, shared_preview_tab.md (#2283), feat_2278_aktionsmodell.md, fix_2275_compare_premium_sms_versand.md, fix_1629_briefing_anker_versandfehler.md, fix_1897_verwaister_briefing_slot.md
- issue_695_test_briefing_send.md: Ablage prüfen, vermutlich archiviert
- ADRs: 0023 (Briefing-Subscription), 0003 (Mandantentrennung), 0062 (Core-Auth), 0088 (fcntl-Lock)

## Risks & Considerations
1. **Hauptlücke:** Ein Vergleich ohne Kanal oder mit nur gescheiterten Kanälen meldet 200 „ok“. Das ist ein stiller Fehlschlag und widerspricht Epic #2505 („Erfolg heißt Zustellung“).
2. Ein Vergleich ohne Wetterdaten ergibt 500, im Frontend erscheint dann nur ein generischer Text.
3. Der Lock gilt nur im eigenen Prozess und hat keine TTL. Den Cron-Pfad deckt er nicht ab (Thema von #1777, nicht hier). Ein Slot-Begriff fehlt beim Vergleich. Der Trip-Schlüssel wird mit dem Inbound-Pfad geteilt, eine Schlüsseländerung verschiebt also die Kollisionen.
4. Die Antwortform muss `fehlende_orte` erhalten. Neue Fehlercodes brauchen Anzeigetexte im Frontend.
5. Der Go-Delegate muss `context.WithoutCancel` behalten (`forwardPreview` hat das nicht).
6. Der Python-Endpoint braucht `kind` und `user_id` als Pflichtparameter, sonst schlägt der AST-Wächter an.
7. `compare/[id]/+page.svelte:233` mitziehen.
8. openapi.yaml kennt weder `/send` noch `/api/briefings`.

## Analysis

### Type
Feature (Konsolidierung) mit Bug-Anteil: Ein Ortsvergleich meldet heute fälschlich Erfolg (200 „ok“), obwohl nichts zugestellt wurde.

### Ist-Befunde der Analyse (2026-10-20, auf HEAD verifiziert)
- **Vergleich, kein Kanal:** `send_compare_report` (`notification_service.py:1359`) setzt **kein** `no_channel_configured`. Das gibt es nur im Trip (`:693`). Ist `effective_channels` leer, gilt `sent=False` (`:2101`) und der Router antwortet trotzdem 200 „ok“.
- **Vergleich, alle Kanäle gescheitert:** `send_result.sent` wird nur für `mark_first_briefing` ausgewertet (`scheduler_dispatch_service.py:716-733`). Danach laufen Anker-Reset (735) und `save_compare_preset_status` (737) trotzdem. Die Antwort ist 200 „ok“.
- **Vergleich, kein Wetter:** `run_comparison_parallel` (`comparison_parallel.py:151`) wirft eine Exception. Der Aufruf (`dispatch:575`) steht vor dem `try` (666), also entsteht 500. Im Frontend erscheint nur die generische Meldung.
- **Vergleich, `mail_to` fehlt:** `ValueError` (`dispatch:517-521`) **auch dann, wenn nur Telegram oder SMS aktiv ist**. Das verstößt gegen die Kanal-Parität.
- **Festes „ok“:** `send_compare_preset` liefert fest `"status": "ok"` und bleibt nur deshalb grün, weil `tests/test_success_status_guard.py` es als Bestand führt (INTENTIONAL_CONSTANT_SUCCESS 1593-1595, SPEC_LISTED 1726).
- **Aufrufer:** `send_one_compare_preset` wird vom Cron-Wrapper (`dispatch:169`, fängt alles ab) und von `send_compare_preset` (781) aufgerufen. `send_compare_preset` hat nur den Router (`scheduler.py:380`) als Aufrufer. Der Inbound-Befehl REPORT am Vergleich ist eine Übergangsantwort ohne Versand (`trip_command_processor.py:1416-1430`), also kein weiterer Aufrufer.
- **Prefix:** `scheduler.router` hat den Prefix `/api/scheduler` (`scheduler.py:27`), `preview.router` hat keinen (`preview.py:23`). Go-`briefingPreviewTarget` baut `<python>/api/briefings/{id}/<suffix>`. Ein neuer Python-Endpoint gehört deshalb in einen Router **ohne** Prefix.
- **kind-Wörter:** Das Frontend hat `SubscriptionKind = 'trip'|'vergleich'` (`subscriptionTabs.ts:7`). Der Dispatcher erwartet `route|vergleich` und weist `trip` mit 400 ab (`briefing_preview_test.go:243`). Die Vorschau-Clients in `frontend/src/lib/api.ts:295-315` senden schon `kind=route|vergleich`. Diese Zuordnung (`trip → route`) wird übernommen, keine zweite.
- **Fehlerform heute:** `detail` ist immer ein deutscher String. Das Frontend zeigt ihn bei 4xx roh an (`sendOutcome.ts:27-30`). Bei 409 ignoriert es `detail` und bei 500 zeigt es eine feste Meldung. Erfolgsfelder liest es nur aus `fehlende_orte`. `winner`, `empfaenger_count` und `sent` liest das Frontend nirgends.
- **Go:** Die beiden Send-Proxies (`proxy.go:273-313`, `compare_preset.go:609-645`) sind fast wörtliche Duplikate. Beide haben `WithoutCancel` und `sendProxyTimeout`, aber **keine** ID-Validierung. `forwardPreview` hat **kein** `WithoutCancel` und scheidet als Basis aus.
- **report_type-Default:** Python-Trip-Send nimmt `evening` (`scheduler.py:282`), Frontend und Vorschau nehmen `morning`.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| src/services/send_outcomes.py | CREATE | Gemeinsames Vokabular: Code → (HTTP-Status, deutscher Text) für `no_stage`, `no_weather`, `no_channels`, `channels_unreachable`, `already_in_progress`, `not_found`, `invalid_report_type`, `smtp_not_configured`. Texte wandern aus `scheduler.py:316/326/336-338/351-353/362` hierher. Dazu eine **geteilte** Ableitungsfunktion `NotificationResult → outcome` (heute Trip-only, `trip_report_scheduler.py:2025-2038`). |
| src/services/trip_report_scheduler.py | MODIFY | Die Ableitung `no_channels`/`channels_unreachable`/`sent` nutzt die geteilte Funktion. Lock-Schlüssel und Outcome-Literale bleiben unverändert. |
| src/services/notification_service.py | MODIFY | `send_compare_report` setzt `no_channel_configured`, wenn `effective_channels` leer ist (Parität zum Trip). |
| src/services/scheduler_dispatch_service.py | MODIFY | `send_compare_preset` leitet den Outcome ab statt fest „ok“ zu liefern. Kein Wetter → `no_weather`. Bei `channels_unreachable` kein Anker-Reset und kein Erfolgs-Status. `mail_to`-Pflicht greift nur, wenn E-Mail unter den wirksamen Kanälen ist. |
| api/routers/briefings_send.py (oder neben `preview.py`, Router ohne Prefix) | CREATE | `POST /api/briefings/{entity_id}/send` mit `kind: Query(...)`, `user_id: Query(...)` und `report_type` (nur bei `route`). Ruft den gemeinsamen Helfer auf. |
| api/routers/scheduler.py | MODIFY | Die beiden Alt-Send-Routen werden Delegates auf denselben Helfer. Die Fehler-Mappings gibt es dann nur noch einmal. |
| api/main.py | MODIFY | Neuen Router einhängen (falls eigene Datei). |
| tests/test_success_status_guard.py | MODIFY | Bestandseintrag `send_compare_preset` (1593-1595, 1726) entfernen. |
| internal/handler/send_proxy.go (oder proxy.go) | CREATE/MODIFY | Gemeinsame `forwardSend` mit `context.WithoutCancel`, `sendProxyTimeout`, `appendUserID`, Body und Status durchreichen. |
| internal/handler/briefing_preview.go / briefing_send.go | MODIFY/CREATE | `BriefingSendHandler`: nutzt `briefingPreviewTarget(…, "send")` für die kind-Pflicht und `ValidEntityID`. |
| internal/handler/proxy.go, compare_preset.go | MODIFY | Die Alt-Handler werden Delegates auf `forwardSend`. Das Duplikat entfällt. |
| internal/router/router.go | MODIFY | `POST /api/briefings/{id}/send` im Dispatcher-Block (292-299). |
| frontend/src/lib/utils/sendOutcome.ts | MODIFY | **Eine** Stelle baut die Send-URL `/api/briefings/{id}/send?kind=route\|vergleich[&report_type=]`. |
| frontend/src/lib/components/shared/subscriptionExec.ts | MODIFY | `sendSubscription` bildet `trip → route` ab. |
| frontend/src/routes/compare/[id]/+page.svelte | MODIFY | Zeile 233 auf `sendSubscription('vergleich', …)` umstellen. |
| docs/reference/api_contract.md, openapi.yaml | MODIFY | Neuen Endpoint dokumentieren, Alt-Routen als „Delegate“ markieren. |
| Tests (Python/Go/Frontend) | CREATE/MODIFY | siehe unten |

**Testbruch durch die URL-Umstellung** (Test-LoC zählen nicht zum Limit). Folgende Tests matchen exakte Alt-URLs:
- **Unit:** `sendOutcomeTrigger.test.ts`, `sendOutcome.test.ts`, `subscriptionExec.test.ts`, `trip_liste_aktionen_verhalten.test.ts`, `trip_hub_aktionen_verhalten.test.ts`, `compare_hub_aktionen_verhalten.test.ts`, `compare_hub_test_send_meldung.test.ts`.
- **E2E:** `trips-list-send`, `aktionsmodell-durchklick`, `issue-767-768-test-briefing`, `send-in-flight-guard`, `compare-hub-versand-inline`, `compare-mobile-vervollstaendigung`, `compare-send-dialog-target.staging`.
- **Go:** `briefing_preview_test.go` ist das Vorbild für die neuen Dispatcher-Tests (kind, ID, user_id, 404, Delegate-Gleichheit). `send_proxy_context_test.go` und `proxy_timeout_chain_test.go` bleiben als Regressionstests bestehen.

### Scope Assessment
- Dateien: ca. 14 produktiv plus Tests
- Geschätzte LoC: +400 bis 450 / -120 produktiv (Python ca. 200, Go ca. 100-130, Frontend ca. 50) → **`loc_limit_override 500` nötig**
- Risk Level: **MEDIUM**. Zentraler Versandpfad beider Flächen. Der Cron-Pfad des Vergleichs ist über die geteilte Ableitung mitbetroffen.

### Technical Approach (Tech-Lead-Entscheidungen)
1. **Fehlerform A:** `detail` bleibt ein deutscher String, damit die Frontend-Anzeige unverändert greift. Zusätzlich kommt ein Top-Level-Feld `code`. Verworfen ist `detail` als Objekt, weil das `sendOutcome.ts` und viele Tests bricht.
2. **Ein Vokabular heißt eine Ableitung:** Vergleich und Trip liefern **denselben** Code und **denselben** Text (Ticket-AC-1). Es gibt kein eigenes `no_recipient`. `no_channels` gilt nur, wenn wirklich kein Kanal wirksam ist.
3. **Antwortform:** `{status, kind, id, sent, report_type?, fehlende_orte?}`. `status` ist „ok“ nur bei echter Zustellung. Ein Fehlschlag ergibt 4xx, nie 200 mit `sent:false`. `winner` und `empfaenger_count` entfallen (kein Leser). Die Alt-Delegates liefern dieselbe Form.
4. **Gescheiterter Vergleichsversand** gilt nicht als zugestellt: kein Anker-Reset, kein Erfolgs-Status. Das spiegelt `VERMERK_AUSGAENGE` beim Trip, wo `channels_unreachable` bewusst fehlt.
5. **Cron-Pfad:** Die geteilte Ableitung ändert dort nur Status und Logging. Der Cron-Wrapper fängt Exceptions weiter ab, ein Funktionsbruch entsteht nicht. Prüfpunkt im Adversary: Ein Cron-Lauf ohne Kanal darf nicht mehr als „versendet“ verbucht werden.
6. **Go:** `forwardSend` ist eine einzige Funktion für Dispatcher und Alt-Routen. Der neue Pfad bekommt die ID-Validierung. Die Alt-Routen bleiben ohne Validierung, aber die Delegate-Gleichheit wird geprüft.
7. **Frontend:** Die Send-URL wird an **einer** Stelle auf den neuen Endpoint umgestellt. Alle Versand-Auslöser laufen über `sendSubscription`. Die Alt-URLs bleiben serverseitig als Delegates für Altbestand bestehen.
8. **Lock-Schlüssel bleibt unverändert:** Trip `(user_id, trip_id, report_type)`, Vergleich `("compare", user_id, preset_id)`. Der Slot-Begriff des Tickets ist beim Trip durch `report_type` abgedeckt. Beim Vergleich gibt es im Handversand keinen Slot. Eine Schlüsseländerung würde die Kollisionen mit dem Inbound-Pfad verschieben. Das ist Zielbild-Text, keine AC.
9. **report_type-Default:** Die Pflicht kommt vom Aufrufer. Der neue Endpoint nimmt `morning` als Default, wie Frontend und Vorschau. Der Alt-Delegate behält `evening`, weil Bestandsaufrufer existieren.
10. **ADR-0023:** Der Dispatcher über `kind` ist das dort beschlossene Modell, `/send` fügt sich ein. In `/30` nur ein Nachtrag im Index- oder ADR-Text, kein neues ADR.

### Scheiben (alle in diesem Ticket, Reihenfolge)
- **S1 Python:** Vokabular, geteilte Ableitung, Vergleichs-Fehlerfälle, neuer Endpoint, Delegates, Wächter-Bestand entfernen
- **S2 Go:** `forwardSend`, Dispatcher-Route, Delegates
- **S3 Frontend:** URL-Umstellung an einer Stelle, `compare/[id]`, Tests, Doku

### Dependencies
S1 → S2 → S3. Upstream-Kette und betroffene Tests: siehe oben, Abschnitte „Dependencies“ und „Testbruch“.

### Offene Punkte für /30 (technisch, Entscheidung beim Tech Lead, kein PO-Punkt)
- [ ] Staging-Nachweis Ticket-AC-2 per IMAP: Doppelauslösung ergibt genau eine Zustellung (Wegwerf-Nutzer `gregor-test+…`)
- [ ] Zwei-Nutzer-Test für den neuen Endpoint (Pflicht laut CLAUDE.md)
- [ ] Ticket-AC-3 (`user_id`) und AC-4 (Timeout) als „bereits erfüllt“ mit Testverweis in die Spec, nicht neu bauen
- [ ] `mail_to`-Lockerung (nur Pflicht bei aktivem E-Mail-Kanal) wirkt auch im Cron-Pfad. Das ist gewollt (Kanal-Parität), muss aber als AC sichtbar sein.

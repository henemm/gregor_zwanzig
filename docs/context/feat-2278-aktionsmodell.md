# Context: feat-2278-aktionsmodell

Issue #2278 · Epic #2345 Etappe P3 · löst #1064 mit (#2214 bereits CLOSED)
Gemessen auf `origin/main` @ `6fafebf3e` (2026-10-17). Ticket-Befund stammt vom 2026-09-09.

## Request Summary
Ein gemeinsames Aktionsmodell (`subscriptionActions(kind, status)`) für Liste, Detail/Hub und Mobil bei Trip und Ortsvergleich: dieselben Handlungen am selben Ort, mit derselben Beschriftung und demselben Ergebnis; ein Test-Versand-Dialog mit echtem Ziel; ein Status-Helfer; eine mobile Listenkarte mit Aktionsblatt.

## Ist-Stand je Befundzeile (neu gemessen)

| # | Fläche | Trip | Ortsvergleich | gegenüber Ticket |
|---|---|---|---|---|
| 1/2 | Desktop-Liste | `TRIP_ACTIONS` `routes/trips/+page.svelte:92-99` (Senden · E-Mail-Vorschau · Alert-Konfiguration · Wetter-Metriken · Bearbeiten · Löschen), Dispatch `onTripAction` :136-144, Primär „Briefing senden" `tripRowPrimary` :129-134 — **kein Pausieren** | `compareActions()` `lib/components/compare/subscriptionHelpers.ts:285-304` (Pausieren/Aktivieren · Senden · Vorschau · Bearbeiten · Löschen; Entwurf: Setup fortsetzen · Löschen), Archivieren bewusst nicht in Liste (:293-296); Aufruf `routes/compare/+page.svelte:110-131`; Pause via `togglePause` :134-152 (PUT ganzes Preset, RMW) | unverändert |
| 3/4 | Detail/Hub | Breadcrumb-Leiste `routes/trips/[id]/+page.svelte:314-373`: Pausieren/Fortsetzen :321, Archivieren/Reaktivieren :324 (+ConfirmDialog :387-402), Test-Briefing Morgen/Abend :327-363 (ohne Bestätigung, ohne Ziel); auch mobil sichtbar (#2284 S2). **Löschen tot**: `handleDeleteClick` :229 ohne Aufrufer, Dialog :404-417 unerreichbar (#1064) | Kebab `CompareKebab` `routes/compare/[id]/+page.svelte:376` mit `compareDetailActions` = Alias `compareLifecycleActions()` (subscriptionHelpers.ts:311-318, :330-332): Pausieren/Aktivieren · Archivieren · Löschen (Entwurf: Entwurf löschen); Desktop-Primär „Test senden"/„Setup abschließen" :367-375; mobil Knopf :378-385 → `MCompareActionSheet` :416-422 (`lib/components/mobile/MCompareActionSheet.svelte:31`); Dispatch `handleAction` :254-274; Pause `toggleActiveFromParent()` :239-248; Archiv PATCH /state :289-301 | unverändert |
| 5 | Mobile Liste | Filter-Pillen Alle/Aktiv/Geplant/Pausiert/Fertig :382-401 (Pausiert neu, #1271), Kartenstapel :403-435, Bottom-Sheet inline :500-556 — Sheet hat Pausieren (:536-539), getrennte Morgen/Abend-Test-Knöpfe (:541-548), **„Briefing senden" :520-523 öffnet nur Vorschau, sendet nicht**, kein Archivieren | `<a href>` um `CompareTile dense` `routes/compare/+page.svelte:300-305`: keine Aktionen, keine Filter, nur Stat-Zahlen :287-291 — **bewusst** laut Kommentar :197-199 (#1256 S8 AC-21) | Trip: neuer Defekt „Senden" sendet nicht |
| 7 | Test-Versand | Liste: `TestReportDialog` :490-497 ohne Ziel; `trips/+page.server.ts` lädt kein Profil; Versand `tripListSend.ts` → `sendTripBriefing` (POST /api/trips/{id}/send), Desktop immer Morgen (Stunde 7) | Liste: ConfirmDialog :324-333 mit `sendTargetLabel(data.profile, sendTarget)` :45, `disabled={sendZiel.gesperrt}`; Profil aus `compare/+page.server.ts`. **Hub sendet ohne Rückfrage, ohne Ziel, ohne Sperre** (`handleTestSend` :215-225) | Compare-Hub präzisiert |
| 8 | Lösch-Bestätigung | Liste: ConfirmDialog :458-467 → `api.del('/api/trips/{id}')`; Hub: Dialog vorhanden, unerreichbar | Liste: ConfirmDialog :313-322; Hub: ConfirmDialog :425-438 (#2214, testid `compare-detail-delete-confirm-*`) → DELETE + Redirect /compare | Compare-Hub erledigt |
| 9 | Status-Ableitung | `lib/utils/tripStatus.ts:14` `deriveTripStatus` (6 Zustände, archived_at > paused_at > Datum); Listen-Wrapper `tripStatus()` :75 mappt archived → `fertig` (:51) | `subscriptionHelpers.ts:83-88` `deriveStatusFromPreset` (active/paused/draft; paused über `paused_at` oder `schedule==='manual'`) + `deriveStatusWithScheduleOverride` :109; kein Archiviert-Status | unverändert |
| 10 | Mobile Listenkarte | inline `routes/trips/+page.svelte:405-433` | `lib/components/compare/CompareTile.svelte` (auch in `routes/_home/CompareKachel.svelte`) | unverändert |

**Toter Code Trip-Liste:** `primaryLabel` :154-159, `handlePrimaryAction` :161-190, `handleArchive` :192-210 ohne Aufrufer; Archivier-ConfirmDialog :469-477 unerreichbar.

**Archiv-Asymmetrie:** Compare-Liste filtert Archiviertes serverseitig (`compare/+page.server.ts`); Trip-Liste filtert nicht — archivierte Trips erscheinen dort als „fertig".

## API (Go, `internal/router/router.go`)
| Handlung | Trip | Ortsvergleich |
|---|---|---|
| Pausieren | PATCH `/api/trips/{id}/state` :246 `{paused?, archived?}` (`handler/trip.go:506-509`), `model/trip.go:134` `PausedAt` | PUT `/api/compare/presets/{id}` :286 mit `{schedule, previous_schedule}`; Server leitet `paused_at` ab (`compareHubPersistenz.ts:35-48, :81`) |
| Archivieren | PATCH /state | PATCH `/api/compare/presets/{id}/state` :287 nur `{archived}` (`compare_preset.go:493-498`) |
| Löschen | DELETE `/api/trips/{id}` :248 | DELETE :288 |
| Senden | POST `/api/trips/{id}/send` :267 | POST `…/send` :289 |
| kind-neutral | `/api/briefings` GET/GET{id}/POST/PUT/DELETE `?kind=` :292-296 (`handler/briefing_subscription.go`) — **kein** PATCH /state, **kein** send; Frontend nutzt es nicht (nur Test `lib/__tests__/etagRegistryQueue.test.ts:71`) | |

Folge: Pausieren läuft auf zwei verschiedenen Wegen (Trip PATCH /state, Compare PUT schedule). Ein geteiltes Aktionsmodell im Frontend braucht einen kind-abhängigen Ausführungs-Adapter oder eine Backend-Angleichung (Scope-Entscheidung in /20-analyse; Backend-Angleichung gehört eher zu P4/P7).

## Geteilte Bausteine heute
- `organisms/ListTable`, `ListTableRow`, `ListActionsMenu`, `ListNameCell` — beide Desktop-Listen (#1277)
- `molecules/ConfirmDialog`, `molecules/TestReportDialog`
- `mobile/Sheet.svelte` generisch (TripNewEditor, CompareNewEditor, KontoSheet) — nicht für Listenaktionen
- `shared/subscription-header/SubscriptionHeader.svelte` (#2284) — ohne Aktionen
- `lib/utils/sendOutcome.ts` — gemeinsamer Laufzustand (`sendTripBriefing` :113, `sendComparePreset` :124, Schlüssel `trip:`/`compare:` :77-78)
- `shared/versand-tab/sendTargetLabel` — nur von Compare-Liste genutzt
- **Kein** Trip-Pendant zu `CompareKebab` / `MCompareActionSheet`; Trip-Sheet inline im Route-File

## Existing Patterns
- Aktionslisten als Daten (`{id,label,…}[]`) + Dispatch-Funktion je Route (`onTripAction`, `handleAction`)
- Compare-Lebenszyklus-Aktionen aus Helfer-Funktion statt inline (Vorbild für `subscriptionActions`)
- Read-Modify-Write beim Pausieren (Compare `togglePause`, `list_toggle_read_modify_write`-Test)
- Sende-Ziel-Anzeige + Sperre über `sendTargetLabel` (Spec `fix_1471_sende_dialog_ziel`)

## Dependencies
- Upstream: Go-Endpunkte oben, `sendOutcome.ts`, `tripStatus.ts`, `subscriptionHelpers.ts`, Profil-Laden in `+page.server.ts`
- Downstream: `routes/trips/+page.svelte`, `routes/trips/[id]/+page.svelte`, `routes/compare/+page.svelte`, `routes/compare/[id]/+page.svelte`, `CompareKebab`, `MCompareActionSheet`, `CompareTile` (auch Home `CompareKachel`), `routes/archiv/archiveHelpers`, Home/Cockpit-Status-Pillen (über `tripStatus`)

## Bestehende Tests (Auswahl, müssen grün bleiben oder bewusst angepasst werden)
- Unit Compare: `lib/components/compare/__tests__/` compare_list_kebab_actions, compare_hub_lifecycle_actions, compareDetailEditActions, bug_626_compare_menu_actions, bug_591_pausieren_button, compare_status_paused_at, hub_status_pill_override, list_toggle_read_modify_write, issue_627_send_action, issue_493_compare_mobile, compare_mobile_shared_hub, issue_488_compare_tile_atoms, issue_491_compare_detail
- Unit Compare-Routen: `routes/compare/__tests__/` compare_hub_loeschen_bestaetigung, compare_send_dialog_target, compare_hub_test_send_meldung, compare_list_mobile_chrome
- Unit Trip: `routes/trips/` trips-list-send, issue_477_486, issue_402, `__tests__/tripPausiertFilter`
- Status: `lib/utils/tripStatus.test.ts`, `lib/utils/__tests__/tripStatusConsolidation.test.ts`, `routes/archiv/archiveHelpers.test.ts`
- Sonstige: `organisms/__tests__/list_table_unify`, `molecules/confirm_dialog`, `shared/versand-tab/__tests__/sendTargetLabel*`
- Playwright Trip: issue-486-trips-overflow, issue-268-trips-mobile-card-stack, bug-282-295-trips-list-redesign, trips-list-send, issue-592-593-trips-navigation, issue-616-trip-one-surface, issue-714-trip-ui-polish, trip-edit, trip-hub-kopf-region-aktivitaet
- Playwright Compare: bug-626-compare-menu-actions, compare-mobile-vervollstaendigung, compare-hub-fidelity-s8c, compare-detail-edit-entry, compare-flow-navigation, compare-hub-kopf-einmal
- Übergreifend: send-in-flight-guard, hub-reiter-alt-kennungen-umleitung
- Frontend-Unit läuft über `node --test` (kein Vitest)

## Existing Specs
- Aktiv `docs/specs/modules/`: trips_atomic_kebab, subscriptions_crud, bug_2214_compare_hub_delete_confirm, fix_1471_sende_dialog_ziel, feat_2284_s1_subscription_header, feat_2284_s2_trip_kopf, feat_1481b_pendant_gate
- Archiv `docs/specs/_archive/modules/`: issue_1250_briefing_subscription, issue_1256_compare_ui_rewire (enthält die bewusste Entscheidung „Compare-Mobil-Liste nur Link", AC-21), issue_268_trips_mobile_card_stack, issue_302_trip_detail_page, issue_611_archiv_entruempeln, issue_627_631_compare_send_rhythm, bug_486_trips_overflow_regression, bug_270_compare_mobile, issue_1059_trip_resume_error_feedback

## Pendant-Sperre
`.claude/hooks/pendant_gate.py` (Bash-PreToolUse): sperrt Neuanlagen in `lib/components/compare/`, `compare-new/`, `trip-detail/`, `trip-new/` ohne `gz-eigenstaendig:`-Kopfzeile. Nicht überwacht: `routes/`, `lib/utils/`, `shared/`, `organisms/`, `molecules/`, `mobile/`. Prüfdatum 2026-11-03. → Neue geteilte Bausteine gehören nach `shared/` bzw. `organisms/`/`molecules/`/`mobile/` (kein Gate-Konflikt).

## Risks & Considerations
- **Frühere PO-Entscheidung kollidiert mit AC-2:** Compare-Mobil-Liste „nur Link" ist in #1256 S8 AC-21 bewusst festgelegt. Ticket-AC-2 kehrt das um. Die Paritäts-Vorgabe des Epics (#2345, DoD-3) ist die jüngere PO-Vorgabe — in der Spec ausdrücklich als Ablösung benennen, nicht still ändern.
- **Zwei Pausier-Wege im Backend** (PATCH /state vs. PUT schedule): Frontend-Adapter ja, Backend-Angleichung nicht vorgreifen (P4/P7). Datenerhalt: Compare-Pause muss RMW bleiben.
- **Archiv-Asymmetrie** der Listen: Entscheidung nötig, ob die Trip-Liste Archiviertes ausblendet wie Compare (Status-Helfer berührt Archiv-Seite und Cockpit).
- **Defekte nebenbei:** mobiles Trip-„Briefing senden" sendet nicht; Compare-Hub-Test-Versand ohne Ziel/Sperre; toter Code in Trip-Liste und Trip-Hub (#1064). Alle fallen in den Umfang des Aktionsmodells (Invariante „kein Element ohne Wirkung").
- **LoC-Limit 250**: Umbau berührt vier Route-Dateien + Helfer + neue Bausteine — Override auf 500 wahrscheinlich nötig; ggf. Scheiben (Status-Helfer → Aktionsquelle → Mobil/Test-Dialog), aber das Epic gilt themenweise (keine Reste abspalten).
- **Viele bestehende Tests** prüfen heutige Beschriftungen/testids (`compare_list_kebab_actions`, `bug-626…`, `trips-list-send`) — Umbenennungen bewusst pro Test entscheiden, nicht pauschal anpassen.
- `tripStatus` speist auch Home/Cockpit — Änderungen an der Ableitung wirken über die Liste hinaus.

## Analysis

### Type
Feature (Rework, Epic #2345 Etappe P3) — schließt #1064 mit; #2214 ist bereits CLOSED (AC-4 betrifft nur noch den Trip-Hub).

### Rahmen
- Epic #2345 trägt noch `status:deferred` (PO-Parkung 2026-10-05). Entparkungs-Regel des PO: „sobald ein Fokus-Epic geschlossen ist" — #2047 ist seit 2026-10-07 CLOSED, Bedingung erfüllt; PO hat `/20-analyse #2278` selbst gestartet. Label-Entfernung am Epic nachziehen.
- Epic-DoD-3: jede Handlung (Pausieren, Archivieren, Löschen, Test-Versand, Vorschau …) in beiden Bereichen am selben Ort, gleiche Beschriftung, gleiches Ergebnis. DoD-2: Kebab/Action-Sheet je **ein** Baustein mit `kind`.
- Backend-Angleichung (Pausier-Endpunkt, ein Datenmodell, kind-neutraler Handversand) = P4/P7 — **nicht** in #2278.
- `git log origin/main --grep "#2278"` @ 6fafebf3e: leer (keine Parallelarbeit).

### Geprüfte Fakten (aus Analyse-Agenten)
- **Versandziel Trip machbar ohne Backend:** `internal/store/trip.go:56-100` `deriveFlatFields` setzt `send_telegram/send_sms/send_premium_sms` aus `report_config`, aufgerufen über `normalizeTrip` in `LoadTrips` (:171) und `LoadTrip` (:225); Felder sind Pointer mit `omitempty` (`model/trip.go:181-185`) → fehlend = false; `sendTargetLabel` (`shared/versand-tab/sendTargetLabel.ts:60`, rein, liefert `{text, deliverable, gesperrt}`) behandelt optionale Flags bereits so. Trip hat keine eigene Empfängerliste — E-Mail kommt wie bei Compare aus dem Profil (`mail_to`).
- **Profil fehlt in drei Loadern:** `routes/trips/+page.server.ts`, `routes/trips/[id]/+page.server.ts`, `routes/compare/[id]/+page.server.ts`. Muster: `compare/+page.server.ts:14-29` (fail-soft `profile=null`, Session-Cookie durchreichen, nie Default-Nutzer). Empfehlung: geteilter Loader-Helfer in `lib/server/`.
- **Senden:** Trip `POST /api/trips/{id}/send?report_type=morning|evening` ohne Body (`handler/proxy.go:273-313`; Mapping 7→morning/18→evening `routes/trips/tripListSend.ts:11-13`). Compare `POST /api/compare/presets/{id}/send` ohne Parameter (`handler/compare_preset.go:609-640`), Antwort ggf. `fehlende_orte`. Kanäle kommen serverseitig aus dem gespeicherten Objekt.
- **`TestReportDialog`** (`molecules/TestReportDialog.svelte`, Props open/hour/running/result/error/onClose) nur in Trip-Liste :490; Tests `routes/trips/issue_477_486.test.ts`, `issue_402.test.ts`.
- **Status-Verbraucher (bleiben unangetastet):** `deriveTripStatus` (englisch: archived/paused/draft/finished/active/planned) in tripHero.ts:55, fullProfile.ts:152, TripStatusBadge, TripHeader, archiveHelpers.ts:28, Trip-Liste, Trip-Hub; `tripStatus()` (deutsch, archived→'fertig' :51) in Cockpit `routes/+page.svelte:122`, `_home/TripKachel`, `_home/cockpitHelpers.ts:298`, `lib/utils/cockpitHelpers568.ts:145,176`. Compare: `deriveStatusFromPreset` (active/paused/draft, **kein archived**) in CompareTile:61, Compare-Liste, Cockpit :48; `deriveStatusWithScheduleOverride` in CompareTabs:193, compare/[id]:166.
- **Baustein-Verbraucher:** `CompareKebab` in CompareTile:168 + compare/[id]:376; `MCompareActionSheet` nur compare/[id]:416; `CompareTile` in Compare-Liste :303 + `_home/CompareKachel.svelte:15`; `TRIP_ACTIONS` ohne Tests.
- **Trip-only-Listenaktionen:** „Wetter-Metriken" ist schon Link `?tab=wetter-metriken` (trips/+page.svelte:141); „Alert-Konfiguration" öffnet Sonderdialog `openReportConfig` (:140). `subscriptionTabs(kind)` (`shared/subscriptionTabs.ts:27-37`) liefert `wetter-metriken` + `alarme` für beide kinds; CompareTabs kennt Deep-Link `?tab=alarme` (:446).

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/lib/components/shared/subscriptionActions.ts` | CREATE | `subscriptionActions(kind, status, surface)` + `subscriptionLifecycle(kind, obj)` → draft/active/paused/archived (dünner Wrapper auf bestehenden Ableitungen) |
| `frontend/src/lib/components/shared/subscriptionExec.ts` | CREATE | Ausführungs-Adapter je kind (pause/resume, archive, delete, send) — umhüllt `sendOutcome.ts`, `compareHubPersistenz.ts`, PATCH /state |
| `frontend/src/lib/server/` (Profil-Loader) | CREATE | geteilter fail-soft Profil-Fetch |
| `lib/components/compare/CompareKebab.svelte` → `molecules/SubscriptionKebab.svelte` | MOVE/MODIFY | kind-neutral: `actions` + `onAction` |
| `lib/components/mobile/MCompareActionSheet.svelte` → `mobile/SubscriptionActionSheet.svelte` | MOVE/MODIFY | kind-neutral |
| `lib/components/compare/CompareTile.svelte` → `organisms/SubscriptionCard.svelte` | MOVE/MODIFY | mobile Listenkarte für beide kinds mit Aktionsblatt; Home-`CompareKachel` mitziehen |
| `lib/components/molecules/SendConfirmDialog.svelte` | CREATE (ersetzt `TestReportDialog`) | auf `ConfirmDialog`, echtes Ziel via `sendTargetLabel`, Sperre; Morgen/Abend nur bei kind=trip (Default Morgen) |
| `lib/components/compare/subscriptionHelpers.ts` | MODIFY | `compareActions`/`compareLifecycleActions`/`compareDetailActions` → dünne Wrapper oder entfallen |
| `routes/trips/+page.svelte` | MODIFY | `TRIP_ACTIONS` → Aktionsquelle (Pausieren neu), Inline-Karte/-Sheet → geteilte Bausteine, mobiles „Senden" sendet wirklich, Archiviertes ausblenden, toter Code (`primaryLabel`, `handlePrimaryAction`, `handleArchive`, Archiv-Dialog) raus, Alert-Konfiguration → `?tab=alarme` |
| `routes/trips/+page.server.ts` | MODIFY | Profil laden |
| `routes/trips/[id]/+page.svelte` | MODIFY | Lifecycle-Kebab statt Breadcrumb-Aktionsleiste, Löschen erreichbar (#1064), Test-Versand über Sende-Dialog, Breadcrumb „Trips" verlinken (~:259) |
| `routes/trips/[id]/+page.server.ts` | MODIFY | Profil laden |
| `lib/components/trip-new/TripNewEditor.svelte` | MODIFY | toter Breadcrumb „Trips" (:363) verlinken (#1064) |
| `routes/compare/+page.svelte` | MODIFY | Aktionsquelle; mobile Liste: Filter-Pillen + Karte mit Aktionsblatt (löst #1256 S8 AC-21 ab) |
| `routes/compare/[id]/+page.svelte` + `+page.server.ts` | MODIFY | Kebab/Sheet aus Aktionsquelle; Test-Versand mit Bestätigung, Ziel, Sperre; Profil laden |
| ggf. `molecules/StatusFilterPills.svelte` | CREATE | geteilte Filter-Pillen (Trip heute inline :382-401) |
| Tests (siehe unten) | CREATE/MODIFY | Tabellentest beider kinds; bestehende Label-/testid-Tests bewusst neu fassen |

(Pfade ohne Präfix relativ zu `frontend/src/`.)

### Scope Assessment
- Files: ~16–20 produktiv + Tests
- Estimated LoC: ca. +900/−700 (Plan-Schätzung) → über 250; `loc_limit_override` je Scheibe messen.
- Risk Level: **MEDIUM** — reine Frontend-Arbeit, Backend unberührt; Risiko liegt in vielen Beschriftungs-/testid-Tests, der Home-Kachel (CompareTile-Umzug) und der Archiv-Ausblendung der Trip-Liste. Cockpit bleibt stabil, solange `tripStatus()`/`deriveTripStatus` unverändert bleiben.

### Technical Approach (Empfehlung)
1. **Eine Aktionsquelle** `subscriptionActions(kind, status, surface: 'list'|'hub'|'mobile')` als reine Funktion mit IDs `pause|resume|send|preview|alarms|weather|edit|archive|unarchive|delete|continue-setup`; Labels kind-unabhängig. Reihenfolge Liste/Mobil: Pausieren/Fortsetzen · Senden · Vorschau · Alarme · Wetter-Metriken · Bearbeiten · Löschen; Entwurf: Setup fortsetzen · Löschen. Hub-Kebab: Pausieren/Aktivieren · Archivieren · Löschen (Senden als Primärknopf). Archivieren bleibt aus der Liste (Liste blendet Archiviertes aus). Ein Tabellentest prüft beide kinds gegen dieselbe Tabelle. AC-5 umformulieren: „eine Aktionsquelle + eine Lebenszyklus-Schicht mit kind", nicht „alle Statusableitungen ersetzt".
2. **Lebenszyklus-Schicht** als dünner Wrapper: Trip planned/active/finished → active; Compare zusätzlich `archived_at` berücksichtigen (Hub). Die ~15 Status-Verbraucher bleiben unangetastet.
3. **Ausführungs-Adapter** je kind; Compare-Pause bleibt PUT mit Read-Modify-Write (Test `list_toggle_read_modify_write`), Trip PATCH /state. Kein Backend-Eingriff.
4. **Bestehende Compare-Bausteine verallgemeinern** (Kebab, Action-Sheet, Kachel) statt Trip-Pendants neu zu bauen; Ablage `molecules/`/`mobile/`/`organisms/` (außerhalb der Pendant-Sperre).
5. **Ein Sende-Dialog** mit echtem Ziel + Sperre für Liste, Hub und Mobil beider kinds; Morgen/Abend-Wahl nur beim Trip (echter fachlicher Unterschied), Default Morgen. Behebt: mobiles Trip-„Senden" sendet nicht; Compare-Hub sendet ohne Rückfrage/Ziel/Sperre.
6. **Trip-only-Aktionen** „Alarme"/„Wetter-Metriken" werden für beide kinds Direktlinks auf die geteilten Tabs (`?tab=alarme`, `?tab=wetter-metriken`); Trip-Sonderdialog Alert-Konfiguration entfällt, falls ohne weiteren Aufrufer (in /30 prüfen).
7. **Archiv-Parität:** Trip-Liste blendet Archiviertes aus wie Compare; Filter „Fertig" = nur Datum vorbei; `tripStatus()` (archived→fertig) bleibt für Cockpit unverändert; Archiv-Seite (`archiveHelpers`) wird einzige Fundstelle.
8. **#1064 komplett:** Trip-Hub-Löschen über Kebab + gemeinsamen Lösch-Dialog; tote „Trips"-Breadcrumbs (trips/[id] ~:259, TripNewEditor :363) verlinken; toter Code entfernen.
9. **Scheiben innerhalb #2278** (alle ACs bleiben im Ticket): S1 Aktionsquelle + Lebenszyklus + Adapter + Profil-Loader (rein, Tabellentest) → S2 Bausteine kind-neutral + Compare-Seiten (Liste, Hub, Mobil mit Filtern/Sheet) → S3 Trip-Liste + Trip-Hub (Pausieren, Kebab, Dialoge, Archiv-Filter, #1064, toter Code) → S4 Test-/Playwright-Bereinigung.

### Bewusst zu ändernde Tests (vor Umsetzung per grep auf alte Labels/testids nachziehen)
- `lib/components/compare/__tests__/`: compare_list_kebab_actions, compare_hub_lifecycle_actions, compareDetailEditActions, bug_626_compare_menu_actions, bug_591_pausieren_button, issue_627_send_action, issue_493_compare_mobile, compare_mobile_shared_hub, issue_488_compare_tile_atoms
- `routes/compare/__tests__/`: compare_send_dialog_target, compare_hub_test_send_meldung, compare_hub_loeschen_bestaetigung (testid `compare-detail-delete-confirm-*` beibehalten), compare_list_mobile_chrome (Link-only wird abgelöst)
- `routes/trips/`: trips-list-send, issue_477_486, issue_402, `__tests__/tripPausiertFilter`
- Playwright: bug-626-compare-menu-actions, compare-mobile-vervollstaendigung, trips-list-send, issue-268-trips-mobile-card-stack, bug-282-295-trips-list-redesign, issue-616-trip-one-surface, send-in-flight-guard

### Dependencies
- Upstream (unverändert): Go-Endpunkte (`router.go` :246/:248/:267 Trip, :286-289 Compare), `sendOutcome.ts`, `compareHubPersistenz.ts`, `tripStatus.ts`, `subscriptionTabs.ts`, `sendTargetLabel.ts`, `ConfirmDialog`
- Downstream: Trip-/Compare-Liste und -Hub, Home `CompareKachel`, Cockpit (nur indirekt, bleibt stabil)

### In der Spec ausdrücklich zu benennen
- Ablösung #1256 S8 AC-21 (Compare-Mobil-Liste „nur Link") durch Epic-Paritätsvorgabe DoD-3.
- #2214 CLOSED → AC-4 nur Trip-Hub; Compare-testids bleiben.
- Compare-Menü wird um „Alarme"/„Wetter-Metriken" länger (Folge der einen Tabelle).
- Trip-Liste bekommt Pausieren (Hub hat es bereits, :321 — Lücke, keine Absicht).
- Zwei Backend-Pausierwege bleiben bis P4/P7, nur durch Adapter verdeckt.

### Open Questions
- [ ] Keine PO-Fragen offen — Produktpunkte (Archiv-Ausblendung, längeres Compare-Menü, Trip-Pausieren in der Liste, Morgen/Abend-Default) werden als ACs formuliert und mit der Spec-Freigabe entschieden.
- [ ] Technisch in /30 klären: hat der Trip-Dialog `openReportConfig` weitere Aufrufer? Zählt das Cockpit archivierte Trips (unverändert lassen)?

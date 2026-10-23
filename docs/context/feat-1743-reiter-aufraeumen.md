# Context: feat-1743-reiter-aufraeumen

## Request Summary
Issue #1743: In den Detail-Hubs von Trip **und** Ortsvergleich (gemeinsame Reiterleiste) entfällt der
Reiter „Vorschau"; der Reiter „Versand" entfällt ebenfalls, seine Inhalte hängen unten am Reiter
„Wetter-Metriken". PO-Entscheid 2026-10-22 (Intake): Versand-Reiter fällt weg (keine Dopplung), beide
Hubs gleich (Code-Teilungs-Vorgabe).

Neue Reiterleiste: Übersicht · Etappen & Wegpunkte / Orte · Wetter-Metriken · Wertebereiche · Alarme.

Pfade unten relativ zu `frontend/src/`.

## Related Files
| File | Relevance |
|------|-----------|
| `lib/components/shared/subscriptionTabs.ts:28-38,44-53` | EINE Reiter-Tabelle beider Hubs (#2287) + LEGACY-Map (`briefings→versand`, `preview→vorschau`) |
| `lib/components/trip-detail/TripTabs.svelte:84,185,200-221,23-31,61-69,108-114,165-171` | Trip-Hub: Leiste, Panels wetter-metriken/versand (`BriefingScheduleTab`)/vorschau (`PreviewTab`), Badges, Flush vor Reiterwechsel |
| `lib/components/compare/CompareTabs.svelte:149-175,418-437,490-562,601,676-683,819-877,954-1083` | Compare-Hub: Panels, Versand-Hydration, Aktivierungs-Karte (Pausieren/Aktivieren) im Versand-Panel, Sprunglinks, Vorschau-Panel |
| `lib/components/shared/corridor-editor/wertebereicheVergleichSpeicherung.ts:252-257` | Liste der selbst speichernden Reiter für den Flush-Guard (enthält `versand`) |
| `lib/components/trip-detail/BriefingScheduleTab.svelte:45-54,92-122` | Trip-Versand-Wrapper um `shared/VersandTab` (route), Autosave per saveController |
| `lib/components/shared/VersandTab.svelte:347-367`, `shared/versandVergleichSpeicherung.ts:275` | Versand-Inhalt + Vergleichs-Speicherweg |
| `lib/components/shared/WeatherMetricsTab.svelte:42-43,1013,1038,1512,1650-1665` | Ziel-Reiter; Autosave; Kommentar „Mail-Vorschau bleibt im Hub-Reiter Vorschau" |
| `lib/components/shared/weather-metrics-tab/weatherMetricsCompareSave.ts:490-533` | Wetter-Metriken-Speicherweg Vergleich |
| `lib/components/shared/pickEigenfelder.ts:47-88` | Feld-Eigentum `VERSAND_REPORT_KEYS` vs. `WETTER_*_KEYS` (überschneidungsfrei) |
| `lib/stores/saveStatusStore.svelte.ts:386-392` | saveController: `schedule()` hat EINEN Pending-Slot, 700 ms Debounce |
| `lib/components/shared/PreviewTab.svelte`, `shared/previewLoader.ts` | Briefing-Vorschau je Kanal — einzige Stelle im Produkt |
| `lib/components/shared/subscriptionActions.ts:17,36,67,71` | Aktion `preview` (Listen/Mobil) → `?tab=vorschau` |
| `routes/trips/+page.svelte:108,170`, `routes/compare/+page.svelte:123` | Listen-Aktion „Vorschau" |
| `lib/components/trip-detail/HubOverview.svelte:116,130-132` | „Zeitplan bearbeiten →" (versand), „Vorschau öffnen" |
| `routes/+page.svelte:127,361-367,629-635` | Cockpit: `TRIP_TAB_MAP`, Schnellaktionen versand/vorschau |
| `routes/compare/[id]/+page.svelte:388` | „Setup abschließen" → `?tab=versand` |
| `lib/components/trip-detail/PreviewCard.svelte`, `BriefingPreviewCard.svelte` | nur exportiert, scheinbar unbenutzt (Sprunglinks auf vorschau/versand) |
| `lib/components/shared/infoboxKeys.ts:11` | Infobox-Typ `versand` |
| `lib/components/shared/layout-tab/LTComparePreview.svelte` | nirgends importiert (Totcode) |

## Existing Patterns
- **Reiter-Abbau mit Umleitung:** #2287 hat Alt-Kennungen über die LEGACY-Map umgeleitet (`layout→wetter-metriken`, `idealwerte→wertebereiche`); der Hub bereinigt die Adresszeile einmal. Dasselbe Muster passt für `versand→wetter-metriken`, `vorschau→?`.
- **Reiter-Auflösung mit Inhaltsübernahme:** `compare_layout_tab_dissolution.md` (Layout-Reiter in Wetter-Metriken aufgelöst) ist das direkte Vorbild.
- **Selbst speichernde Reiter** im Hub: Autosave über gemeinsamen saveController, kein Speichern-Knopf, keine zweite Sticky-Leiste. Beide Reiter (Wetter-Metriken, Versand) sind schon so gebaut.
- Geteilte Bausteine mit `context="route"|"vergleich"` — Änderung in `shared/` wirkt in beiden Hubs.

## Dependencies
- Upstream: saveController (`saveStatusStore`), `pickEigenfelder`, Hydrationen in CompareTabs, `hubPutQueue`.
- Downstream: Listen-/Mobil-Aktion „Vorschau", Cockpit-Schnellaktionen, HubOverview-Karten, Compare-Sprunglinks, Lesezeichen/geteilte Links mit `?tab=versand|vorschau`, Badges in TripTabs, Flush-Guards.

## Existing Specs
- `docs/specs/modules/feat_2287_tab_kennungen.md` — eine Reiterleiste, 7 Kennungen
- `docs/specs/modules/shared_preview_tab.md` — #2283 geteilter Vorschau-Reiter
- `docs/specs/modules/feat_2278_aktionsmodell.md` — Aktion `preview` (AC-2/AC-14)
- `docs/specs/modules/compare_layout_tab_dissolution.md` — Vorbild Reiter-Auflösung
- `docs/specs/modules/versand_tab_route.md`, `versand_tab_vergleich.md`, `rework_2276_s5_versand.md`, `rework_2276_s6e_versand.md`
- `docs/specs/modules/compare_weather_metrics_tab.md`, `mobile_tab_leisten_mtabbar.md`, `feat_1256_s8c_hub_fidelity.md`
- Kein ADR legt Reiterleiste oder Vorschau-Reiter fest.
- Referenz-Doku: `docs/reference/navigation.md:11-31` (gültige `?tab=`-Werte + LEGACY), `docs/features/architecture.md:1209`.

## Risks & Considerations
1. **🔴 Funktionsverlust Briefing-Vorschau:** `PreviewTab` ist die EINZIGE Stelle, an der man das Briefing je Kanal (E-Mail, Telegram, SMS, Premium-SMS-Hinweis) vorab sieht. Reiter weg ohne neuen Platz ⇒ Vorschau komplett weg, Listen-Aktion „Vorschau", Cockpit-Schnellaktion und „Vorschau öffnen" laufen ins Leere. Analyse muss klären: Vorschau an neuen Ort (z.B. ebenfalls unten in Wetter-Metriken, Übersicht, Kopf-Aktion/Dialog) oder bewusst ersatzlos — Letzteres wäre eine Produktentscheidung, die dem PO vorzulegen ist (Ticket sagt nur „Reiter entfernen").
2. **Ein Pending-Slot im saveController:** Wetter-Metriken- und Versand-Edit innerhalb 700 ms auf derselben Seite ⇒ erster Save wird überschrieben (Datenverlust-Risiko). Heute schützt nur der Flush beim Reiterwechsel. Muss gelöst und mit Test bewacht werden.
3. **Doppelte Trip-Snapshots:** `BriefingScheduleTab` und `WeatherMetricsTab` halten je eine eigene `report_config`-Kopie aus dem `trip`-Prop — Read-Modify-Write-Merge (CLAUDE.md) muss bei gleichzeitigem Anzeigen weiter gelten, keiner darf die Felder des anderen mit Altstand überschreiben.
4. **Compare-Aktivierungs-Karte** (Pausieren/Aktivieren) hängt am Versand-Panel — zieht mit um.
5. **Hydration Compare:** Wetter-Metriken mountet erst nach zwei Hydrationen, Versand hat eine eigene — beide müssen auf der vereinten Seite fertig sein.
6. **Alt-Kennungen:** `versand`, `vorschau`, `briefings`, `preview` müssen auflösen (kein Leerlauf von Lesezeichen); Badges/Flush-Listen/`TRIP_TAB_MAP`/Infobox-Key bereinigen.
7. **Test-Ratsche:** viele Unit-/E2E-Tests nageln 7 Reiter fest; `e2e/issue-736-tabs-reorg.spec.ts` widerspricht dem Merge direkt (Kanal-Schalter NICHT in Wetter-Metriken) — veraltetes Verhalten ⇒ anpassen/löschen, nicht liegenlassen.
8. **Anlege-Editoren** (`TripNewEditor`, `CompareNewEditor`) haben eigene Kette mit Versand als letztem Pflichtschritt, keinen Vorschau-Reiter, nutzen `subscriptionTabs.ts` nicht. Ticket meint die Hub-Leiste ⇒ voraussichtlich außer Scope; in Analyse bestätigen (Trip/Compare-Gleichlauf bleibt gewahrt, da beide unverändert).
9. **Seitenlänge Wetter-Metriken** (bereits ~2200 Zeilen Komponente, lange Seite) — Versand unten anhängen verlängert die Seite; Sprungziel/Anker für „Zeitplan bearbeiten →" sinnvoll.
10. Totcode-Gelegenheit: `PreviewCard`, `BriefingPreviewCard`, `LTComparePreview` unbenutzt.

## Analysis

### Type
Feature (Aufräumen der Hub-Reiterleiste, Trip + Ortsvergleich gleich)

### PO-Entscheide 2026-10-22 (Analyse-Rückfrage, beide abweichend von der Empfehlung)
1. **Briefing-Vorschau entfällt ganz** — kein Ersatzort. Mit weg: Hub-Panel `vorschau`, `PreviewTab.svelte`, `previewLoader.ts`, Listen-/Mobil-Aktion „Vorschau" (`subscriptionActions.ts`), Cockpit „Vorschau prüfen →" (`routes/+page.svelte:367,635`), CompareTabs-Sprunglink :876, HubOverview „Vorschau öffnen" (:130-132), zugehörige Tests (`previewTab.test`, `previewVerdrahtungHubs.test`, `compare_preview_channel_switch.test`, Staging-Specs `trip-preview-thunder-origin`, `ausblick-einfach-wirkt`, `kanal-grenzen-ortsvergleich`). Alt-Kennungen `vorschau`/`preview` → `uebersicht`.
   - **Bleibt (andere Funktion):** Mini-Vorschauen im Layout/Wetter-Metriken (`molecules/CompareChatBubble.svelte` → `POST /api/preview/compare/{id}`, `preview/SmsPhoneFrame.svelte` + `previewHelpers.ts` → `GET /api/preview/{trip}/{channel}`), Alarm-Vorschau im Reiter Alarme.
   - **Backend `GET /api/briefings/{id}/preview`** (`internal/handler/briefing_preview.go`, `router.go:299`, Python-Gegenstück in `src/services/preview_service.py`): einziger Frontend-Aufrufer war `previewLoader.ts` ⇒ wird toter Code. Technischer Entscheid (Tech Lead): **mit entfernen**, sofern `/30` keinen weiteren Aufrufer (Inbound-Befehle, Tests mit Fachwert) findet; sonst belassen und begründen. #1839 (Vorschau-502) wird gegenstandslos ⇒ nach Lieferung mit Verweis schließen.
2. **Anlege-Seiten werden ebenfalls zusammengelegt** (Trip `/trips/new` UND Ortsvergleich `/compare/new`, gleich gebaut): Schritt „Versand" entfällt, sein Inhalt hängt unten am Schritt „Wetter-Metriken". Neue Anlege-Kette: Trip `route · etappen · wegpunkte · wetter-metriken · wertebereiche · alarme`, Vergleich `vergleich · orte · wetter-metriken · wertebereiche · alarme`.
   - Betroffen: `trip-new/tripNewLogic.ts:23,30,94,100`, `trip-new/TripNewEditor.svelte`, `compare-new/CompareNewEditor.svelte:74-78,88,143,150,175,184,242`, `shared/anlegeLockEngine.ts:16,25,39,49,54-55` (TailIds ohne `versand`, `canFinish`).
   - **Technischer Default:** „Fertig/Anlegen" freigeschaltet, sobald der letzte Schritt **Alarme** besucht ist (heute: Versand besucht); Fortschrittszähler ohne `versand`. Infobox `versand` (`infoboxKeys.ts:11,19,26`) wandert als Abschnitts-Infobox unter Wetter-Metriken oder entfällt — in `/30` festlegen.
   - Zusätzlich betroffene Tests: `anlege_lock_engine`, `compare_anlege_freischaltung`, `anlege_reiter_kennungen_gleich`, `tripNewLogic.test`, `trip_new_reiterleiste_besuchs_flags`, `trip_new_zeitplan_tab_nutzt_geteilten_versand_baustein`, `trip_new_mail_inhalt_karte_genau_eine_instanz`, `trip_new_versandkanaele_unabhaengig_von_metriken`, `trip_new_wertebereiche_reiter`, `infobox_nur_beim_anlegen`, `infoboxTexte`, `standardwerte_knopf_geteilt`, `standardwerte_gate`, `anlege_weiter_knopf_zielt_auf_existierenden_reiter`, `begriff_erklaerung_infobox_bausteine`, E2E `begriff-erklaerung.spec.ts`.
   - Speicher-Slot-Problem gilt auf den Anlege-Seiten nicht in gleicher Form (dort wird erst beim Anlegen gespeichert) — in `/30` verifizieren.

### Affected Files (with changes) — Pfade relativ zu `frontend/src/`
| File | Change Type | Description |
|------|-------------|-------------|
| `lib/stores/saveStatusStore.svelte.ts:67,386-392,452-463` | MODIFY | `schedule(fn, ms, owner?)`: wartet ein fremder Besitzer, wird er zuerst gesendet; `cancel(owner?)` löscht nur eigenes |
| `lib/components/shared/subscriptionTabs.ts:28-53` | MODIFY | `versand`/`vorschau` raus; LEGACY `versand`,`briefings` → `wetter-metriken`; `vorschau`,`preview` → je PO-Entscheid |
| `lib/components/trip-detail/TripTabs.svelte:184-228` | MODIFY | Panel `wetter-metriken` bekommt `BriefingScheduleTab` darunter (Anker `#versand`); Panels versand/vorschau, Badges, Flush-Liste weg |
| `lib/components/compare/CompareTabs.svelte:420-425,525-530,876,954-1083` | MODIFY | Versand unter Wetter-Metriken, beide Hydrationen an `wetter-metriken` binden, Aktivierungs-Karte zieht mit, Sprunglinks, Vorschau-Panel |
| `lib/components/shared/versandVergleichSpeicherung.ts:317-320`, `weather-metrics-tab/weatherMetricsCompareSave.ts:524-528` | MODIFY | `cancel()` mit Besitzer-Schlüssel |
| `lib/components/shared/WeatherMetricsTab.svelte:1002-1040,1650-1665` | MODIFY | Besitzer-Schlüssel für die zwei eigenen Speicherwege; Vorschau-Kommentar |
| `lib/components/shared/corridor-editor/wertebereicheVergleichSpeicherung.ts:252-257` | MODIFY | `versand` aus Selbstspeicherer-Liste |
| `lib/components/shared/subscriptionActions.ts:17,36,67,71`, `routes/trips/+page.svelte:108`, `routes/compare/+page.svelte:123` | MODIFY | Aktion „Vorschau" je PO-Entscheid (umleiten oder entfernen) |
| `routes/+page.svelte:127,361-367,629-635` | MODIFY | `TRIP_TAB_MAP`, Cockpit-Schnellaktionen Versand/Vorschau |
| `lib/components/trip-detail/HubOverview.svelte:116,130-132` | MODIFY | „Zeitplan bearbeiten →" → `?tab=wetter-metriken#versand`; „Vorschau öffnen" je PO-Entscheid |
| `routes/compare/[id]/+page.svelte:388` | MODIFY | „Setup abschließen" → `wetter-metriken#versand` |
| `lib/components/shared/PreviewTab.svelte`, `shared/previewLoader.ts` | MODIFY/DELETE | je PO-Entscheid (umhängen vs. löschen) |
| `lib/components/trip-detail/PreviewCard.svelte`, `BriefingPreviewCard.svelte`, `shared/layout-tab/LTComparePreview.svelte`, `trip-detail/index.ts:7,9` | DELETE | Totcode |
| `docs/reference/navigation.md:24-28`, Specs `feat_2287_tab_kennungen.md` (AC-4, AC-9), `shared_preview_tab.md` (AC-8, AC-9), `feat_2278_aktionsmodell.md` (AC-2), `mobile_tab_leisten_mtabbar.md` (AC-1-Beispiel) | MODIFY | Doku/Specs nachziehen |
| Tests: ~30 Hub-bezogene `*.test.ts` (u. a. `subscription_tabs_resolve`, `hub_reiter_gemeinsame_aufloesung`, `reiter_sprunglinks_nur_neue_kennungen`, `wetterMetrikenTabRegistration`, `versand_panel_ohne_wrapper_div`, `issue_1273_s3_redirect_links`, `tripMehrreiterPruefstand`, `deadTripOverviewComponentsRemoved`, `aktionsmodell_seiten_bindung`, Flush-Guard-Tests) | MODIFY | Reiter-Fixierungen auf neue Leiste |
| Tests Vorschau (`previewTab.test`, `previewVerdrahtungHubs.test`, `compare_preview_channel_switch.test`) | MODIFY/DELETE | je PO-Entscheid |
| Playwright ~18 Specs (`trip-detail-tabs`, `hub-reiter-alt-kennungen-umleitung`, `issue-616-trip-one-surface`, `issue-736-tabs-reorg` (widerspricht direkt), `versand-tab`, `issue-758-save-indicator`, `versandzeit-stundenwahl`, `compare-hub-briefing-times`, `bug-626-compare-menu-actions`, …), `.github/ci_e2e_specs.txt` | MODIFY/DELETE | Veraltetes Verhalten anpassen/löschen, nie rot liegen lassen |
| `tests/tdd/test_issue_1069_tier_channel_gating.py:641,681,718` | MODIFY ggf. | `?tab=briefings` läuft weiter über LEGACY |
| NEU: Test „zwei Schreiber binnen 700 ms, beide im Backend" (Trip + Vergleich) | CREATE | bewacht Speicher-Slot-Fix |

### Scope Assessment
- Produktdateien: ~20, Tests: ~30 Unit + ~18 E2E
- Estimated LoC Produkt: +150..250 / −300..500 (Löschanteil hoch). **LoC-Override 500 voraussichtlich nötig** (`workflow.py set-field loc_limit_override 500`).
- Risk Level: **MEDIUM-HIGH** — stiller Datenverlust beim Speichern (s. u.) + breite Test-Ratsche + Produktentscheid Vorschau.

### Technical Approach
1. **Speicher-Slot (Pflicht, im selben Ticket):** `saveStatusStore` hat EINEN Pending-Slot (`_pendingFn` L67), `schedule()` überschreibt ihn binnen 700 ms still, UI zeigt trotzdem „Gespeichert"; `cancel()` kennt keinen Besitzer. Heute verhindern nur exklusive Panels den Konflikt. **Lösung:** Besitzer-Schlüssel — `schedule(fn, ms, owner)`: wartet ein fremder Besitzer, wird dessen Funktion zuerst gesendet (flush), dann der neue Slot gesetzt; `cancel(owner)` löscht nur die eigene. Speicher-Anzeige bleibt EIN Zustand pro Seite. Netz-PUTs sind schon je Ressource serialisiert (`enqueueTripWrite`/`hubPutQueue` + If-Match), Feldmengen disjunkt (`pickEigenfelder.ts:47-88`), Backend mergt `report_config` flach (`handler/trip.go:384-387`). Behebt auch den **heute schon bestehenden** Trip-internen Verlust (`WeatherMetricsTab` `scheduleAutoSave` :1002-1020 vs `scheduleReportConfigOnlySave` :1030-1040).
2. **Einhängen:** Versand als zweiter Baustein im Hub-Panel UNTER `WeatherMetricsTab` (nicht in die 2235-Zeilen-Komponente). Trip: `BriefingScheduleTab` in `TripTabs`; Vergleich: Versand-Panel-Inhalt inkl. Aktivierungs-Karte (`hubActivationCard` :1045-1063 → `VersandTab.svelte:445`) in `CompareTabs`. Anker `#versand` als Sprungziel.
3. **Hydration Vergleich:** Versand-`$effect` (:420-425) und Wetter-`$effect` (:525-530) beide an `activeTab==='wetter-metriken'`; Versand-Baustein mountet erst nach seiner Hydration.
4. **Alt-Kennungen:** `versand`,`briefings` → `wetter-metriken` (Anker bleibt via `bereinigteTabAdresse`); `vorschau`,`preview` → je PO-Entscheid.
5. **Umsetzungsreihenfolge (Scheiben nur als Reihenfolge, EIN Workflow, alle ACs):** (1) Store + Test, (2) Hub-Umbau beide Hubs + Alt-Kennungen + Sprunglinks, (3) Vorschau je PO-Entscheid + Totcode + Test-/Doku-Bereinigung.

### Dependencies
- Upstream: `saveStatusStore` (saveController), `pickEigenfelder`, `hubPutQueue`/`enqueueTripWrite`, Compare-Hydrationen.
- Downstream: Listen-/Mobil-Aktion „Vorschau", Cockpit-Schnellaktionen, HubOverview-Karten, Compare-Sprunglinks, Lesezeichen `?tab=versand|vorschau|briefings|preview`, Flush-Guards.
- Verwandte Tickets: #1839 (Trip-Vorschau 502 nach 30 s), #2243 (tote Playwright-Specs), #2347 (Paritäts-E2E), #2345 (Epic Ortsvergleich).

### Ungeprüfte Annahmen (in Spec/RED absichern)
- Plan-Bewertung hat CompareTabs/VersandTab-Speicherwege nicht selbst gelesen — Explore-Befund ist die Grundlage.
- `flush` vor Fremd-Slot muss mit `defer`/`retryConflict`/`cancel` zusammenpassen.
- **Re-Hydrations-Fall:** `onTripUpdate` nach Versand-PUT darf noch nicht gespeicherte Wetter-Metriken-Eingaben (und umgekehrt) nicht mit dem neuen Prop überschreiben — eigene AC + Test „Metrik ändern, dann Versandzeit ändern ⇒ beide Werte im Backend und in der UI".

### PO-Einwand 2026-10-22: „Das soll doch der gleiche Code sein!"
Die Rückfrage „Anlege-Seite unverändert?" war falsch gestellt — Anlegen und Bearbeiten sind nach Code-Teilungs-Vorgabe derselbe Code, der Gleichlauf ist gesetzt, keine Wahl.
**Befund:** Die Reiter-INHALTE sind bereits geteilt (`shared/WeatherMetricsTab`, `shared/VersandTab`, `shared/AlarmeTab`, `shared/corridor-editor/CorridorEditor` in Hub UND Anlege-Editoren). Die Reiter-LISTE ist aber dreifach verdrahtet: `shared/subscriptionTabs.ts:28-38` (beide Hubs), `trip-new/TripNewEditor.svelte:81-87` + `tripNewLogic.ts:23,30`, `compare-new/CompareNewEditor.svelte:74-78,138-143`. Diese Dreifach-Liste ist die Ursache, warum der Abbau überhaupt an Anlege-Seiten „vorbei" gehen könnte — Verstoß gegen die Code-Teilungs-Invariante.
**Technischer Entscheid (Tech Lead):** In diesem Ticket wird die Reiterfolge EINE Quelle — die Anlege-Editoren leiten ihre Schrittfolge aus derselben Definition ab (Kennungen + Labels + Reihenfolge), ergänzen nur anlege-eigene Felder (`lockHint`, `optional`, Startreiter `route`/`vergleich` statt `uebersicht`). Prüfbare AC: Entfernen/Umbenennen eines Reiters in der einen Quelle wirkt auf alle vier Seiten (Trip-Hub, Vergleichs-Hub, `/trips/new`, `/compare/new`), ohne dass eine zweite Liste geändert werden muss.

### Open Questions
- [x] Vorschau → entfällt ganz (PO 2026-10-22)
- [x] Anlege-Seiten → ebenfalls zusammenlegen; Gleichlauf ist gesetzt, keine Wahl (PO-Einwand 2026-10-22) ⇒ Reiterfolge wird EINE Quelle für Hub + Anlegen
- [ ] (technisch, `/30`) Weitere Aufrufer von `GET /api/briefings/{id}/preview`? Infobox `versand` beim Anlegen: verschieben oder streichen?

### Scope-Hinweis nach PO-Entscheid
Umfang wächst durch die Anlege-Seiten deutlich (≈ +4 Produktdateien, +16 Tests). LoC-Override 500 sicher nötig; ggf. Umsetzung in drei Reihenfolge-Scheiben (Store → Hubs → Anlege-Seiten + Vorschau-Rückbau), weiterhin EIN Workflow.

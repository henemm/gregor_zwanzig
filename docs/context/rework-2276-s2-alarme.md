# Context: rework-2276-s2-alarme (Issue #2276, Scheibe S2)

Epic-Kontext, Entscheidungen E1–E4 und Scheibenplan: `docs/context/rework-2276-compare-speicherweg.md`.
S1-Lieferung: `docs/specs/modules/rework_2276_s1_netz_und_fundament.md` (live `58eb84c4`).
Pfade relativ zu `frontend/src/`, Stand `58eb84c4`.

## Request Summary
Der Alarme-Reiter des Ortsvergleich-Hubs speichert selbst über den Speicher-Controller der Seite
(wie beim Trip), statt über `handleAlarmeCommit` + Bridge + `hubPutQueue` in `CompareTabs`. Dazu
wird der Hub-Controller mit Kennung `{typ:'vergleich', id}` erzeugt, damit ein 412 zum Zustand
`conflict` mit „Nochmal speichern" führt (heute: generischer Fehler).

## Related Files
| Datei | Relevanz |
|---|---|
| `lib/components/shared/AlarmeTab.svelte` (509 Z.) | Ziel-Organismus. Trip-Speicherweg `buildAlarmeSaveFn()` :302-317, `$effect` :331-346 (`saveController.schedule`). `wiz` als Prop :78/:106 |
| `lib/components/compare/CompareTabs.svelte` | Mount :1445-1451 (Wrapper-`div` ruft `handleAlarmeCommit` bei change/focusout/click), `currentPreset` :200, `createPutQueue` :208, `currentAlarmSnapshot` :566-591, Hydration :604-622, `handleAlarmeCommit` :648-678, `handleValueChange` :152-159 (kein `flush`), Preset-Reset :1067-1073 |
| `lib/components/compare/compareHubWizardBridge.ts` | `hydrateAlarmFieldsFromPreset` :519-555 (setzt auch `corridors`, `activeMetricKeys`), `AlarmSnapshot` :562, `flushPendingAlarmSave` :613-641, `rollbackAlarmSnapshot` :662-690, `buildHubPutPayload` :138-228, Queue :451-463 |
| `lib/components/compare/compareEditorSave.ts` | `buildComparePresetSavePayload` :115-270, Voll-Spread `{...original}` :206, RMW auf `display_config` :126-131 |
| `routes/compare/[id]/+page.svelte` | `createSaveStatus()` OHNE Kennung :59, `sichereAusstehendeSpeicherung` :65-67, eigenes `currentPreset` :50-53, Kopf-PUTs Name/Region/Profil :162/:189/:206, Weitergabe :489-497 |
| `lib/stores/saveStatusStore.svelte.ts` | `createSaveStatus(kennung?)` :262, `doSave` :120-143 (412→conflict nur mit Kennung), `retryConflict` :152-164, `hasPending` :170, `schedule` :184, `flush` :196 |
| `routes/trips/[id]/+page.svelte`, `lib/components/trip-detail/TripTabs.svelte` | Vorbild: `createSaveStatus({typ:'trip',id})` :43, `handleTripUpdate` :226-228, `flush()` beim Reiterwechsel :145-182 |
| `lib/components/compare-new/CompareNewEditor.svelte` :412/:499 | Anlege-Seite mountet AlarmeTab ohne Preset/Controller, speichert per POST `wiz.saveNewPreset()` — muss unverändert bleiben |
| `tripSpeicherung.ts`, `alarmeDeliveryPayload.ts` | Trip-Nutzlast (`alert_channels`-Objekt) — für den Vergleich NICHT verwendbar (#2293) |

## Existing Patterns
- **Trip-Speicherweg:** Organismus baut SaveFn, `saveController.schedule(fn)` (700 ms, Letzter gewinnt), Antwort über `onTripUpdate` → lokales State-Replace, `flush()` beim Reiterwechsel, `enqueueTripWrite` serialisiert Netzwerk-Schreibvorgänge, If-Match generisch in `api.ts`.
- **Compare heute:** Commit-Handler je Reiter, alle rechnen mit derselben `currentPreset`-Basis, serialisiert über `hubPutQueue`; Controller wird nur optisch über `setSaving/setSaved/setError` bedient.
- **Epic-Entscheidung E2:** Vergleich bekommt `onCompareUpdate` in der Rolle von `currentPreset`; Queue fällt erst, wenn alle Reiter umgestellt sind (S6).

## Preset-Felder des Alarme-Reiters
`official_warnings{enabled}`, `radar_alert_enabled`, `display_config.metric_alert_levels`,
`display_config.telegram_style`, `alert_cooldown_minutes`, `alert_quiet_from`, `alert_quiet_to`,
`send_telegram`, `send_sms`, `send_premium_sms`, `alert_channel_thresholds`.
`official_alerts_enabled` bedient AlarmeTab seit D2 nicht mehr, der Hub-Stand sendet es trotzdem.

## Dependencies
- Upstream: `api.ts` (If-Match, `enqueueTripWrite`, `refreshResourceEtag`), `saveStatusStore`, Go-Handler `PUT /api/compare/presets/{id}` (Minimal-PUT verlustfrei, S1-Test).
- Downstream: übrige Hub-Reiter (Versand, Wertebereiche, Wetter) lesen `currentPreset` als Basis ihrer Voll-Spread-PUTs; `SaveIndicator`; Anlege-Seite.

## Existing Tests
- Unit `compare/__tests__/`: `hub_put_queue.test.ts` (F002 :106, F003 :149), `compare_hub_alarme_bridge.test.ts`, `compare_alarme_channel_threshold_save.test.ts`, `compare_hub_wizard_bridge.test.ts`.
- Unit `shared/__tests__/`: `alarme_save_single_writer.test.ts`, `alarme_delivery_consolidated_save.test.ts`, `alarme_tab_catalog_prop_structure.test.ts`, `alarme_tab_unalertable_hint_structure.test.ts` (zählen Mounts), `telegram_kurzstil_shared_toggle.test.ts` (referenziert `flushPendingAlarmSave`), `trip_speicherung_reicht_keepalive_durch.test.ts`.
- `lib/__tests__/fakeTripServer.ts` ersetzt den Stand komplett (:150), prüft also keine Teil-PUT-Verlustfreiheit.
- E2E in CI-Ratsche: `compare-radar-toggle`, `speicherung-ueberlebt-neuladen` (Vergleichsteil nur Idealwerte). NICHT in CI: `compare-alarm-config`, `feat-1745-a-alarm-premium-sms`, `feat-1461-s3b2b-compare-kanal-schwelle`, `compare-hub-versand-inline` (F004).

## Bezug #2293
#2293 führt `alert_channels` am Ortsvergleich ein (inkl. E-Mail-Schalter, heute fest `true`). Bis
dahin muss der Vergleichszweig bei den flachen `send_*`-Feldern bleiben, die Nutzlast-Bildung aber
so geschnitten sein, dass #2293 nur sie austauscht.

## Risks & Considerations
1. **Veraltete Basis:** Speichert AlarmeTab am `hubPutQueue` vorbei, bleibt `currentPreset` alt; der nächste Voll-Spread-PUT eines anderen Reiters schreibt alte Alarmfelder zurück ⇒ `onCompareUpdate` aktualisiert `currentPreset` + Alarm-Basis; Mutations-Gegenprobe Pflicht.
2. **Kein `flush()` beim Reiterwechsel** in `CompareTabs.handleValueChange` ⇒ Lost-Update bei 700 ms Debounce; TripTabs-Muster übernehmen.
3. **Reihenfolge Queue vs. Controller:** Alarm-PUT (über `enqueueTripWrite`) und Queue-PUTs anderer Reiter können sich überholen; Basis-Aktualisierung muss beide Richtungen abdecken.
4. **Doppeltes Speichern:** Wrapper `hub-alarme-wrap` + `handleAlarmeCommit` entfernen.
5. **Kennung:** `createSaveStatus({typ:'vergleich', id})` — Kennung bei Alt-Slugs ohne `cp-`-Präfix übergeben, nie ableiten (S1).
6. **Gemischter Controller-Betrieb:** übrige Handler setzen Status direkt und können ein ausstehendes `schedule()` optisch als „Gespeichert" überdecken.
7. **Nutzlast:** keine `alert_channels`; `display_config` nur Ebene-1-Merge ⇒ `metric_alert_levels` vollständig senden, `telegram_style` erhalten; `official_alerts_enabled` nicht mehr senden.
8. **Überschneidende Felder:** `metricAlertLevels` auch im Korridor-Stand, Cooldown/Stille Stunden/`send_*` auch im Versand-Stand ⇒ `wizardState` konsistent halten.
9. **Anlege-Seite:** Weg nur über `wiz` ohne Preset/Controller unverändert; Strukturtests zählen Mounts.
10. **Hydration** setzt `activeMetricKeys`/`corridors` für andere Reiter mit — nicht in AlarmeTab verlegen (Deep-Link #1320).
11. **Kopfzeile** (Name/Region/Profil) schreibt per Voll-Spread aus dem eigenen alten `currentPreset` der Seite — vorbestehend, nicht S2-verursacht, wird aber sichtbarer.
12. **Keepalive:** SaveFn des Vergleichs muss `init` durchreichen (Entladen).
13. **Netz schwach:** Alarme-E2E überwiegend nicht in CI, `fakeTripServer` merged nicht.

## Analysis

### Type
Rework (verhaltensneutrale Umstellung) mit einem nutzersichtbaren Defekt-Fix: 412 im Ortsvergleich
führt heute zu generischem Fehler statt `conflict` + „Nochmal speichern".

### Affected Files (with changes)
| Datei | Change | Beschreibung |
|---|---|---|
| `routes/compare/[id]/+page.svelte` :59 | MODIFY | `createSaveStatus({typ:'vergleich', id})` |
| `lib/components/shared/AlarmeTab.svelte` | MODIFY | Vergleich-Zweig speichert selbst: Props `preset`, `onCompareUpdate`, `enqueueHubWrite`; Baseline `lastPersistedAlarmSnapshot`; `$effect` mit Diff-Gate vor `schedule()` |
| `lib/components/shared/alarmeVergleichSpeicherung.ts` (Name vorläufig) | CREATE | Snapshot/Diff/Rollback-Helfer (heute `flushPendingAlarmSave`/`rollbackAlarmSnapshot`/`AlarmSnapshot` in der Bridge) — wandern nach `shared/`, weil `shared/` heute nur **Typ**-Importe aus `compare/` hat (`CompareWizardState`, 6 Stellen) und keine Laufzeit-Abhängigkeit auf die Klebeschicht entstehen darf |
| `lib/components/compare/compareHubWizardBridge.ts` :562-690 | MODIFY | Alarm-Helfer entfernen bzw. auf das neue Modul verweisen |
| `lib/components/compare/CompareTabs.svelte` | MODIFY | `hub-alarme-wrap` + `handleAlarmeCommit` + `currentAlarmSnapshot` weg (:564-678, :1445-1451); Mount mit neuen Props; `handleValueChange` (:152) → `flush()` beim Verlassen von `alarme`; `handleToggleActive` (:1014) → `flush()` vorab |
| `compare/__tests__/compare_hub_alarme_bridge.test.ts`, `compare_alarme_channel_threshold_save.test.ts` | MODIFY | Import auf neues Modul umhängen, Zusicherungen (Radar im Body, Kanal-Schwellen, No-Op) bleiben |
| `shared/__tests__/telegram_kurzstil_shared_toggle.test.ts`, `e2e/feat-1745-a-alarm-premium-sms.spec.ts` | MODIFY | Kommentar-Referenzen |
| neue Unit-Tests (Orchestrierung) | CREATE | s. Tests unten |

### Scope Assessment
- Dateien: ~8 Quell-/Testdateien
- LoC grob: Quellcode +~150/−~120, Tests +~200 ⇒ `loc_limit_override 500` einplanen
- Risk Level: HIGH (Persistenz, Lost-Update-Fläche)

### Technical Approach (Empfehlung Plan-Agent, Advisor-korrigiert)
1. **Serialisierung über die bestehende Hub-Queue (Option A):** Die Alarm-SaveFn läuft über
   `hubPutQueue.enqueue` (Prop `enqueueHubWrite`, kein zweites `createPutQueue`) und setzt nach
   Erfolg `currentPreset` per `onCompareUpdate` — in derselben Kette. Damit bleibt die
   F002/F003-Zusicherung (Basis wird erst bei **Ausführung** gelesen) gültig; die Queue fällt erst in
   S6 (E2). Präzedenz: `CorridorEditor.svelte:229` (`saveController?.schedule(async (init) => …)`).
   Ein Alarm-PUT am Queue vorbei (Option B) würde sich mit Voll-Spread-PUTs anderer Reiter überholen.
2. **Nutzlast bleibt Voll-Spread** (`buildHubPutPayload` → `buildComparePresetSavePayload`), wie alle
   übrigen 6 Hub-Handler. fix_2285 erlaubt inzwischen Teil-PUTs, aber zwei Nutzlast-Konventionen im
   selben Hub erhöhen das Risiko ohne Gewinn. `metric_alert_levels` und `telegram_style` werden
   vollständig gesendet (E3 erfüllt).
3. **No-Op-Entscheid VOR `schedule()`:** `doSave()` ruft nach der SaveFn unbedingt `setSaved()` —
   ein `markPristine()` in der SaveFn wäre wirkungslos. Der `$effect` prüft den Diff gegen
   `lastPersistedAlarmSnapshot` (nicht gegen einen reinen Effekt-Zuletzt-Wert — die beiden
   divergieren nach Fehlschlag oder Nachbar-Edit an geteilten Feldern); ohne Diff `markPristine()`.
4. **Rollback nur bei Nicht-412:** Bei 412 bleibt `wiz` unverändert, sonst sendet
   `retryConflict()` eine leere Differenz und meldet fälschlich „Gespeichert".
5. **Flush beim Reiterwechsel** (TripTabs-Muster) und vor `handleToggleActive`.
6. **Anlege-Seite** bleibt unverändert: ohne `saveController` und `preset` ist der neue Zweig inaktiv.

### Bewusste Abweichungen (in Spec zu benennen)
- `official_alerts_enabled` wird weiter mitgesendet (heute geteiltes Feld mit dem Wetter-Stand) —
  Verhaltensneutralität geht vor; Rückbau in S4/S6.
- Die übrigen 5 Hub-Handler steuern den Controller weiter direkt (gemischter Betrieb bis S3–S6).
- Kopfzeile (Name/Region/Profil) mit eigenem `currentPreset` der Seite: vorbestehend, nicht Teil von S2.

### Tests mit Mutations-Gegenprobe (Pflicht)
1. **Kein Zurückschreiben alter Alarmwerte:** Alarm-Änderung speichern → danach Versand- oder
   Idealwerte-Commit auslösen → der **abgefangene Body des zweiten PUT** trägt die neuen Alarmfelder.
   Assertion auf den Request-Body, nicht auf Server-Stand (`fakeTripServer.ts:150` ersetzt statt zu
   mergen). Mutation: `onCompareUpdate` weglassen ⇒ rot.
2. **Lesen erst bei Ausführung:** zwei Schreibvorgänge einreihen, `currentPreset` dazwischen ändern
   ⇒ die zweite Closure sieht den neuen Wert (belegt die Annahme „Svelte-5-Prop-Getter" statt sie
   vorauszusetzen). Mutation: Basis beim Einreihen kopieren ⇒ rot.
3. **412 → conflict, Wiederholen sendet die Änderung:** Mutation: Rollback auch bei 412 ⇒ rot.
4. **No-Op stempelt kein „Gespeichert":** Mutation: `schedule()` ohne Diff-Gate ⇒ rot.
5. **Reiterwechsel flusht:** Änderung + sofortiger Wechsel zu Versand ⇒ PUT mit Änderung vor dem
   Wechsel. Mutation: `flush()` entfernen ⇒ rot.

### Dependencies
S1 gelandet (`58eb84c4`): `createSaveStatus({typ,id})`, `refreshResourceEtag`. `api.ts` serialisiert
Compare-PUTs bereits über `enqueueTripWrite` mit If-Match (:184, `etagRegistry.ts:56`).
Relevante Specs: `feat_1273_s1_compare_hub_save_chip.md` (No-Op → `markPristine`),
`fix_2285_compare_put_merge_kernel.md`, `_archive/modules/issue_1258_alarme_tab_official_warnings.md`
(S5 Hub-Integration, wird durch S2 abgelöst), ADR-0032, ADR-0036.

### Open Questions
- keine an den PO; technische Entscheidungen oben getroffen.

## Befunde aus TDD RED (2026-09-19)
- **AC-9-Präzisierung:** Die Spec-Annahme „`shared/` importiert nur Typen aus `compare/`" stimmt
  nicht — `shared/weather-metrics-tab/weatherMetricsCompareSave.ts:10` lädt `buildHubPutPayload` aus
  der Bridge zur Laufzeit (Präzedenz). Der AC-9-Test verbietet daher gezielt den Ladepfad
  `AlarmeTab` → `compare/compareHubWizardBridge.ts` (die Klebeschicht, die in S6 fällt); der
  Nutzlast-Baustein `compare/compareEditorSave.ts` bleibt erlaubt (lädt die Bridge nachweislich
  nicht). Folge: `alarmeVergleichSpeicherung.ts` baut die Voll-Spread-Nutzlast über
  `buildComparePresetSavePayload`, nicht über `buildHubPutPayload`.
- **Aufrufstellen nicht in der Kernschicht messbar:** Der Prüfstand hat kein DOM, SSR führt kein
  `$effect` aus. AC-1/5/6 prüfen die Helfer (`erstelleAlarmeVergleichSpeicherung`,
  `sichereAlarmeVorReiterwechsel`), nicht die Verdrahtung in `AlarmeTab.svelte`/`CompareTabs.svelte`;
  AC-4-Kennung in `+page.svelte` ebenso ⇒ Staging-Klickpfad ist für diese Verdrahtung Pflicht.
- **AC-10:** Keepalive-PUT läuft über die Hub-Queue (ein Microtask-Hop), wie bereits
  `CorridorEditor.svelte:229`.

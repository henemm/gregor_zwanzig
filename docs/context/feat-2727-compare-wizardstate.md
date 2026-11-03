# Context: feat-2727-compare-wizardstate

Issue #2727 (Epic #2345, DoD-1). Gemessen auf `origin/main` `60b932c94` am 2026-11-01.

## Request Summary
`frontend/src/lib/components/compare/compareWizardState.svelte.ts` (Klasse `CompareWizardState`, 199 Z.) verliert seine 5 produktiven Importeure und wird gelöscht. Hub und Anlegen des Ortsvergleichs halten ihren Zustand wie der Trip (`TripTabs` / `TripNewEditor`). Ein Wächter-Test verhindert die Rückkehr. Zusätzlich: `context ===` in `shared/` gegen die Soll-Liste aus #2276 abgleichen.

## Inhalt von CompareWizardState
- Nur `$state`-Felder (:14–118): Stammdaten (`name`, `region`, `activityProfile`, `pickedIds`, `isEditMode`), Wertebereiche (`idealRanges`, `corridors`), Metriken (`activeMetricKeys`, `channelActiveMetricKeys`, `hourly*/outlook*`), Versand (`send*`, `channels`, `schedule`, `morning*/evening*`, `endDate`, `dayWindow*`), Alarme (`official*`, `radarAlertEnabled`, `metricAlertLevels`, `channelThresholds`, `alertCooldownMinutes`, `alertQuiet*`), `telegramStyle`.
- Keine `$derived`-Werte. Prüfwerte `nameOk/orteOk/canContinue/orteContinueReady` liegen in `CompareNewEditor.svelte:161–200`.
- Eine Methode: `saveNewPreset()` (:132) → `buildNewComparePresetPayload` (`compareEditorSave.ts:425`) → POST `/api/compare/presets` → `goto`. Plus `extractErrorMessage` (:191).
- Vermutlich tot: `saveStatus`, `saveError` (kein Leser), `weekday` (nur geschrieben in `compareNewVorlage.ts:49`), `metricsManuallyEdited`; Context `compare-wizard-profile` (`routes/compare/new/+page.svelte:26`) wird nie gelesen.

## Related Files
| Datei | Relevanz |
|---|---|
| `frontend/src/lib/components/compare/compareWizardState.svelte.ts` | wird gelöscht |
| `frontend/src/lib/components/compare/CompareTabs.svelte` | `new CompareWizardState()` (:355) lokal; Hydration schreibt Felder (:368–536); liest über 4 `*PropsAus` (:777–823) + `telegramStyle` (:779). Orte schon eigenes `$state currentLocationIds` (:235). `saveNewPreset` ungenutzt |
| `frontend/src/routes/compare/new/+page.svelte` | `new` (:20), `vorlageInZustand` (:23), `setContext('compare-wizard-state')` (:25) |
| `frontend/src/lib/components/compare-new/CompareNewEditor.svelte` | `getContext` (:98); nutzt `name/region/activityProfile/pickedIds`, `saveNewPreset()` (:260, :292), schreibt `corridors/idealRanges/activeMetricKeys/metricAlertLevels` (:281–284), mountet Step2Orte (:466, :569) |
| `frontend/src/lib/components/compare-new/compareNewVorlage.ts` | `vorlageInZustand(state, …)` – `Object.assign` der Hydrierer + `name/region/pickedIds/schedule/weekday/officialAlertTriggersEnabled` (:33–50) |
| `frontend/src/lib/components/compare/steps/Step2Orte.svelte` | `getContext('compare-wizard-state')` (:30), liest/schreibt nur `ws.pickedIds` |
| `compare/corridorPropsAus.ts`, `alarmePropsAus.ts`, `versandPropsAus.ts`, `wetterMetrikenPropsAus.ts` | Adapter Zustand → Organismus-Props; verlangen nur Ausschnitts-Typen (`*ZustandsQuelle`), nicht die Klasse |
| `compare/compareHubHydration.ts` (:51, :86), `shared/versandVergleichSpeicherung.ts:83`, `shared/weather-metrics-tab/weatherMetricsCompareSave.ts` (:52/78/92/212) | Hydrierer Preset → Felder |
| `compare/compareEditorSave.ts` (:121 `buildComparePresetSavePayload`, :297 Partial, :425 `buildNewComparePresetPayload`) | Payload-Bau |
| `compare/compareHubPersistenz.ts`, `shared/*VergleichSpeicherung.ts`, `weatherMetricsCompareSave.ts` | einzige Schreiber (Leitplanke #102), bleiben |

## Existing Patterns
- **TripTabs:** kein Zustandsobjekt; bekommt `trip`, `onTripUpdate`, `saveController` als Props (TripTabs.svelte:31–49). Seite hält `let trip = $state<Trip>` (`routes/trips/[id]/+page.svelte:39`) und einen `createSaveStatus({typ:'trip'})` (:62). Autosave je Reiter über `saveController.schedule`.
- **TripNewEditor:** lose `$state`-Variablen (:91–140), `$derived stubTrip` (:163) mit `createMode` + Rückrufen (:927–958), ein POST in `buildAndSave` (:451–473); kein Context.
- Shared-Reiter bauen ihre `*ZustandsBruecke` schon selbst aus Props (AlarmeTab:429, VersandTab:331, WeatherMetricsTab:1310, CorridorEditor:99, CorridorEditorMobile:107). `wiz` lebt nur noch in `compare/` und `compare-new/`.
- Wächter-Muster „kein Importeur“: `compare/__tests__/compare_hub_bridge_restlos_entfernt.test.ts` (existsSync + grep über `src`, Begriff zweiteilig, Positivkontrolle), `shared/__tests__/anlege_lock_engine_waechter.test.ts`, `shared/__tests__/legacy_wizard_removed.test.ts`.

## Dependencies
- Upstream: Hydrierer, `*PropsAus`-Adapter, `compareEditorSave`, `compareHubPersistenz`, `*VergleichSpeicherung`, `anlegeLockEngine`.
- Downstream (Tests):
  - Brechen hart: `compare/__tests__/totcode_rueckbau_speicherweg.test.ts:53`, `wizard_state_no_legacy_save.test.ts:22`, `compare_wizard_save_new_preset_channels.test.ts:69`, `compare-new/__tests__/compareNewVorlage.test.ts:38`, `shared/__tests__/infoboxSsr.ts:26` (`neuerWiz`) und alle Abhängigen (infobox_*, standardwerte_*, begriff_erklaerung_*, anlegen_ohne_versand_beruehrung_postet_standardversand, standardwerte_payload_paritaet_compare, molecules/begriff_erklaerung_*).
  - Stub am Context-Schlüssel `compare-wizard-state`: anlege_reiter_kennungen_gleich, anlege_reiterleiste_trip_vergleich_paritaet, compare_new_lock_engine_wirkstelle, compare_anlege_freischaltung, corridor_editor_laedt_keine_compare_klebeschicht, infobox_nur_beim_anlegen, begriff_erklaerung_an_den_vier_begriffen.
  - Schon vorhandene Wächter „Typ verschwunden“: compare_wetter_metriken_wertprops:363, compare_versand_wertprops:256, compare_corridor_wertprops:266, compare_alarme_wertprops:241.
  - Gegenläufig, umzudrehen: `issue_683_wizard_remove.test.ts` (verlangt Datei :163 und `saveNewPreset` :215).
  - E2E: `e2e/issue-452-smart-import-step2.spec.ts`, `compare-neu-kanal-anlegen.staging.spec.ts`, `hub-anlegen-ablauf.spec.ts` + `hub-*.spec.ts` (Paritäts-E2E #2347 S4). Python-Gates: `tests/tdd/test_pendant_gate.py`.

## Existing Specs / ADRs
- `docs/adr/0097-trip-ortsvergleich-code-teilung.md` (Pendant-Sperre; neue Dateien in `compare/` brauchen Kopf `gz-eigenstaendig:`)
- `docs/adr/0032-wizard-abschaffung-progressive-editoren.md`
- `docs/specs/modules/rework_2276_s6h_ac2_endbilanz.md` (Soll-Liste `context ===`, :103–163)
- `feat_2347_s1…s4_paritaets_e2e.md`, `feat_1301_f2a_compare_new_trip_pattern.md`, `feat_2277_s2c_compare_from_vorlage.md`, `feat_2277_s4_anlege_lockengine.md`, `issue_440_compare_wizard_shell_step1_step2.md`

## Zweiter Teil DoD-1: `context ===` – Befund
- Soll-Liste eingefroren in `shared/__tests__/context_herkunft_zweige_eingefroren.test.ts:187–282`, `EINGEFROREN_SOLL_ANZAHL = 47`.
- Ist-Stand = 47, Diff gegen Liste identisch → **kein Treffer außerhalb der Soll-Liste**. Die im Issue gezählte Liste entspricht genau diesen 47.
- Inkonsistenz in der Spec: Summenzeile (:165) sagt 46, Tabellen haben 27/5/15 = 47. Doku-Korrektur fällig.
- 15 HERKUNFT-Zweige (nicht fachlich, geduldet). Davon direkt zustandsbezogen: die drei Gates `p.context === 'vergleich' && !!p.zustand` in `versandVergleichSpeicherung.ts:244`, `wertebereicheVergleichSpeicherung.ts:209`, `weatherMetricsCompareSave.ts:561`. Zu prüfen, ob sie nach dem Umbau entfallen können.

## Risks & Considerations
- Ratsche ist nach `datei:zeile` geschlüsselt: jede Zeilenverschiebung in den Shared-Dateien macht sie rot → Änderungen in `shared/` minimal halten oder die Liste bewusst nachziehen.
- Verhalten darf sich nicht ändern: Anlegen inkl. `?from=`, Autosave, Speicher-Chip, Cross-User-Sperre, Lock-Engine.
- Pendant-Sperre: kein neues Compare-Zustandsmodul mit Trip-Pendant. Ein „Nachfolger mit gleicher Rolle“ (z. B. umbenannte Klasse) würde DoD verfehlen; der Wächter muss Rolle prüfen, nicht nur Namen.
- Context-Schlüssel `compare-wizard-state` ist in ~7 Tests als Stub verdrahtet; Step2Orte holt `pickedIds` per Context → auf Props umstellen (Muster Trip).
- Viele Tests hängen an `infoboxSsr.neuerWiz` → zentraler Helper, einmal umbauen.
- Datenerhalt #102: Speicherwege bleiben unverändert die einzigen Schreiber.

## Analysis

### Type
Feature (Rückbau/Refactoring, Epic #2345 DoD-1) — kein Nutzerverhalten ändert sich.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/lib/components/compare/compareWizardState.svelte.ts` | DELETE | Klasse samt `saveNewPreset`/`extractErrorMessage` |
| `frontend/src/routes/compare/new/+page.svelte` | MODIFY | keine Instanz, kein `setContext` (beide Schlüssel); reicht `data.vorlage`/`locations` als Props durch |
| `frontend/src/lib/components/compare-new/CompareNewEditor.svelte` | MODIFY | Zustand als lokales `$state` (Muster `TripNewEditor:91–140`), Startwerte aus `stateOverride` (existiert, :81–96) bzw. Vorlage; lokale `async function` statt `wiz.saveNewPreset()` (`buildNewComparePresetPayload` + `api.post` + `goto`) |
| `frontend/src/lib/components/compare-new/compareNewVorlage.ts` | MODIFY | reine Funktion `preset, locations → Feldsatz` statt Mutation; `weekday` entfällt |
| `frontend/src/lib/components/compare/steps/Step2Orte.svelte` | MODIFY | `pickedIds` als `$bindable`-Prop statt `getContext` |
| `frontend/src/lib/components/compare/CompareTabs.svelte` | MODIFY | `new CompareWizardState()` → ein komponentenlokales `$state`-Feldobjekt; 39 Vorkommen mechanisch umbenannt; Hydrationsstellen und `*PropsAus` unverändert |
| `compare/*PropsAus.ts` | MODIFY (nur Kommentare) | Verweise auf die Klasse/„Wizard-Zustand“ |
| `shared/__tests__/infoboxSsr.ts` | MODIFY | `neuerWiz` + Context-Map entfallen, alles über `stateOverride` (zentraler Hebel) |
| ~20–25 Testdateien (Liste unter Dependencies) | MODIFY | Context-Stubs `compare-wizard-state` raus, harte Brüche umbauen |
| `compare/__tests__/issue_683_wizard_remove.test.ts` | MODIFY | umdrehen: Datei darf NICHT existieren, Anlegen postet aus dem Editor |
| `compare-new/__tests__/compareNewVorlage.test.ts` | MODIFY | prüft zurückgegebenen Feldsatz statt Mutation |
| `compare/__tests__/compare_wizard_state_entfernt.test.ts` (Name vorläufig) | CREATE | Wächter (s. u.) |
| `docs/specs/modules/rework_2276_s6h_ac2_endbilanz.md` | MODIFY | Summenzeile korrigieren: 14→15 HERKUNFT, 46→47 |
| `shared/` (Produktivcode) | — | unberührt |

### Scope Assessment
- Files: ~8 produktiv + ~20–25 Tests + 1 Spec-Doku
- Estimated LoC (produktiv): ca. +250 / −400 (Schätzung); Testumbau größer
- Risk Level: MEDIUM — reiner Umbau ohne Verhaltensänderung, aber der Hub (985 Z.) ist zentral (Autosave, 412-Konflikt, Rollback, verzögerte Hydration), und die Anlege-Seite hat viele Prüfstände.

### Technical Approach
**Hub — Variante A (gewählt): ein komponentenlokales `$state`-Feldobjekt in CompareTabs.**
Variantenvergleich:

| | A (ein `$state`-Objekt im Hub) | A' (je Reiter ein Satz) | B (Props `$derived` aus `currentPreset`) |
|---|---|---|---|
| Hub-Änderung | 39 Vorkommen mechanisch | A + Aufteilung | Hydration, Schreibweg, Rollback neu |
| geteilte Felder Cooldown/Quiet (Versand ↔ Alarme) | konsistent | **auseinanderlaufend** | konsistent |
| sichtbarer Wert vor Server-Antwort | erhalten | erhalten | **verloren** |
| Rollback (`rollbackVersandSnapshot`/`rollbackAlarmSnapshot`) | erhalten | erhalten | **ohne Ziel** |
| `shared/` + Ratsche | unberührt | unberührt | müssen geändert werden |

Begründung gegen B: Im Trip halten die geteilten Reiter ihren Bearbeitungsstand selbst und melden `onTripUpdate` erst mit der Server-Antwort (`AlarmeTab.svelte:389`, `CorridorEditor.svelte:299`). Im Vergleich schreiben dieselben Reiter über die `on*Change`-Rückrufe der Adapter zurück (`versandPropsAus.ts:84–110`, `alarmePropsAus.ts:161–167`, `corridorPropsAus.ts`) und haben keine eigene Kopie. B ginge nur, wenn sich die Reiter in `shared/` ändern (eigener Bearbeitungsstand im Vergleich). Das wäre ein eigenes Vorhaben mit Ratschen-Eingriff und widerspricht der Leitplanke „kein Verhalten ändern“.

**Ehrliche Restabweichung (gehört so in die Spec):** Der Hub hält weiterhin einen komponentenlokalen Feldsatz als Zwischenstand. Es entfällt das geteilte Zustandsmodul (Klasse, Context-Schlüssel, Import über Komponentengrenzen), nicht aber jeder Zwischenstand. Die volle Trip-Gleichheit („Reiter halten ihren Bearbeitungsstand selbst, Hub nur `currentPreset`“) ist mit diesem Ticket nicht erreicht und wäre ein Folgevorhaben.

**Anlegen:** lokaler `$state` in `CompareNewEditor` wie im `TripNewEditor`, kein Context. Die Vorlage `?from=` wird einmal im Init ausgeführt, ohne `$effect` (AC-10 aus #2277 S2c). Speichern geschieht als lokale Funktion mit einem POST. Step2Orte bekommt `pickedIds` als bindbare Prop (Orte-Organismus ist Compare-eigen, kein Pendant-Verstoß).

**Wächter (prüft Rolle, nicht nur Namen),** nach dem Vorbild `compare_hub_bridge_restlos_entfernt.test.ts` mit zweiteiligen Begriffen und Positivkontrolle:
- (a) Datei existiert nicht.
- (b) Schlüssel `compare-wizard-state` / `compare-wizard-profile` kommen in `src` nicht vor.
- (c) Unter `compare/` und `compare-new/` exportiert keine `.ts`/`.svelte.ts` eine Klasse oder Factory mit `$state`. Reine Daten-Factories bleiben erlaubt.
- (d) Kein `setContext`/`getContext` unter `compare/` und `compare-new/`.

**Reihenfolge innerhalb DIESES Tickets und EINER Spec** (keine neuen Issues): S1 Anlegen (Editor, Seite, Vorlage, Step2Orte, `infoboxSsr`, Stub-Tests), S2 Hub (CompareTabs, Klasse löschen, Wächter, `issue_683` umdrehen, Doku-Summenzeile).

**Zweiter Teil DoD-1 (`context ===` in `shared/`):** Ist 47 = Soll 47, kein Zweig außerhalb der Liste. Alle 15 HERKUNFT-Begründungen (`rework_2276_s6h_ac2_endbilanz.md:146–162`) verweisen auf andere Persistenz-Endpoints, Katalog-Ladepfade oder `maybeSchedule`, keine auf den Wizard-Zustand. Mit dem Löschen der Klasse entfällt daher kein Zweig. Die drei `p.context === 'vergleich' && !!p.zustand`-Gates prüfen die aus Props gebaute `*ZustandsBruecke` der Reiter, nicht die Klasse, und bleiben. Ergebnis: Abgleich bestanden, jede Abweichung ist begründet. Nur die Summenzeile der Spec ist falsch (14/46 statt 15/47) und wird korrigiert.

### Verifizierte Fakten
- `compare-wizard-profile`: nur `setContext` (`routes/compare/new/+page.svelte:26`), kein Leser → entfällt.
- `saveStatus`, `saveError`, `metricsManuallyEdited`: kein Leser außerhalb der Klasse → entfallen.
- `weekday`: nur von der Vorlage gesetzt, nicht im POST-Payload (`compareEditorSave.ts` reicht `weekday` nur im Update-Pfad aus `original` durch) → entfällt.
- `stateOverride` existiert bereits in `CompareNewEditor` (:81–96) und wird von `infoboxSsr.ts:66–72` genutzt.

### Nebenbefund (Verhalten bleibt unverändert)
Schlägt der POST beim Anlegen fehl, landet die Meldung in `saveError`. Das liest niemand, der Knopf „Briefing aktivieren“ tut für den Nutzer also still nichts. Der Umbau behält das Verhalten bei (Leitplanke). Eintrag ins Sammel-Issue #1199.

### Dependencies
Siehe Abschnitt „Dependencies“ oben (Upstream unverändert: Hydrierer, `*PropsAus`, `compareEditorSave`, `compareHubPersistenz`, `*VergleichSpeicherung`). E2E-Absicherung: Paritäts-E2E #2347 S4 (`hub-*.spec.ts`, `hub-anlegen-ablauf.spec.ts`), `issue-452-smart-import-step2.spec.ts`, `compare-neu-kanal-anlegen.staging.spec.ts`.

### Open Questions
- keine (technische Entscheidungen getroffen; die Restabweichung im Hub wird in der Spec offen benannt und mit ihr freigegeben)

## RED-Übergabe an /50-implement (2026-11-02)

RED-Beleg: `docs/artifacts/feat-2727-compare-wizardstate/test-red-output.txt` (29 Dateien, 414 Tests, 205 grün / 209 rot; Zusammenfassung je Datei am Ende). Ein Wegwerf-Prototyp des Vertrags (außerhalb des Worktrees) machte alle 29 Dateien und 137 Nachbar-Testdateien grün.

### Schnittstellen-Vertrag (durch die Tests festgelegt)
1. `compare/compareEditorSave.ts` exportiert `compareFeldsatzStandard(): CompareFeldsatz` (+ Typ): reine Daten-Factory ohne `$state`, frisches Objekt je Aufruf, genau die Felder der alten Klasse ohne `saveStatus`, `saveError`, `metricsManuallyEdited`, `weekday` (die vier mit `undefined` startenden Felder dürfen fehlen oder `undefined` sein).
2. `compare-new/compareNewVorlage.ts`: `feldsatzAusVorlage(preset, locations): Partial<CompareFeldsatz>` ersetzt `vorlageInZustand`; ohne `weekday`/`isEditMode`.
3. `CompareNewEditor.svelte`: kein `getContext`; Variable heißt weiter **`wiz`** (`compareNewResponsiveSwitch.test.ts` prüft `bind:value={wiz.name}`), `wiz = $state({...compareFeldsatzStandard(), ...})`; Prop `vorlage?: ComparePreset | null`, angewendet im Deklarations-Initialisierer (kein `$effect`, keine nackte Anweisung), Import unter dem Namen `feldsatzAusVorlage`; `stateOverride` nimmt `name`, `region`, `activityProfile`, `pickedIds`. Namen bleiben: `handleActivate`, `nameOk`, `orteOk`, `canActivateNow`, `canContinue`, `standardwerteKatalog`. Speichern lokal: `buildNewComparePresetPayload` (mit `channels` → `alertChannels`, `channelActiveMetricKeys` kopiert) + POST `/api/compare/presets` genau einmal (auch bei Doppelklick) + statischer `import { goto } from '$app/navigation'`, Navigation nach `/compare/<id>`. `<Step2Orte bind:pickedIds={wiz.pickedIds} …/>`.
4. `compare/steps/Step2Orte.svelte`: kein `getContext`; `pickedIds = $bindable<string[]>([])`; `togglePick` bleibt.
5. `routes/compare/new/+page.svelte`: kein `setContext`; `<CompareNewEditor locations={data.locations} vorlage={data.vorlage} />`.
6. `compare/CompareTabs.svelte`: wörtlich `$state(compareFeldsatzStandard())` (Regex in `totcode_rueckbau_speicherweg.test.ts`). **Abweichung von der Spec-Notiz „39 Vorkommen umbenennen":** die Variable heißt weiter **`wizardState`**, weil `compare_hub_uebernimmt_serverantwort_als_basis.test.ts` (AC-12, „unverändert grün") den Hub-Zustand über diesen Namen sät; eine Umbenennung macht dort 6 Tests rot. Kein AC verlangt den neuen Namen.
7. `compareWizardState.svelte.ts` löschen; Kommentare in `shared/`-Produktivcode NICHT anfassen (AC-18, Wächter zählt nur Import-Specifier bzw. Nicht-Kommentarzeilen).
8. Doku `docs/specs/modules/rework_2276_s6h_ac2_endbilanz.md` Summenzeile → 15 HERKUNFT / 47 gesamt (`endbilanz_summenzeile_stimmt.test.ts`).

### Testdateien (alle benannt laufen lassen)
Neu: `compare/__tests__/{compare_wizard_state_entfernt,compare_feldsatz_standard_startwerte,compare_feldsatz_roundtrip_datenerhalt,step2_orte_pickedids_prop}.test.ts`, `shared/__tests__/{compare_new_editor_postet_einmal,hub_geteilte_felder_cooldown_quiet_konsistent,endbilanz_summenzeile_stimmt}.test.ts`, Hilfsmodule `shared/__tests__/compareFeldsatzPruefstand.ts`, `compareNeuEditorPruefstand.ts`.
Geändert: siehe `git show --stat` des RED-Commits. Unverändert und weiter grün zu halten: `compare_*_wertprops` (4), `compare_hub_uebernimmt_serverantwort_als_basis`, `compareNewResponsiveSwitch`, die 412-Tests aus AC-12, `context_herkunft_zweige_eingefroren`, `tests/tdd/test_pendant_gate.py`.

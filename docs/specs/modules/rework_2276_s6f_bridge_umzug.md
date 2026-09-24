---
entity_id: rework_2276_s6f_bridge_umzug
type: module
created: 2026-09-22
updated: 2026-09-22
status: draft
version: "1.0"
tags: [compare, hub, bridge, refactor, ratsche]
---

# Bridge-Umzug: Auflösung von `compareHubWizardBridge.ts` (Issue #2276, Scheibe S6f, Epic #2345)

## Approval

- [ ] Approved

## Purpose

Scheibe **S6f** von #2276 (Epic #2345) löst die letzte Compare-Klebeschicht
`compare/compareHubWizardBridge.ts` (455 Zeilen) auf. Die Datei verliert dabei **keinen**
Export — sie hat heute genau drei produktive Importeure (`CompareTabs.svelte`,
`routes/compare/+page.svelte`, `shared/alarmeVergleichSpeicherung.ts` als Typ-Import) und
34 Testdateien, die einzelne Funktionen davon importieren. AC-4 aus #2276 heißt deshalb
**umziehen, nicht löschen**: alle acht Laufzeit-Exporte + der eine Typ-Export wandern
byte-identisch (nur Modul und, bei zwei Namen, entwizardisierter Bezeichner) in zwei neue
Zielmodule, danach existiert `compareHubWizardBridge.ts` nicht mehr. Zusätzlich fällt der
tote `setContext('compare-wizard-state', …)`-Aufruf in `CompareTabs.svelte` (kein Leser mehr
im Hub-Baum — selbst `CorridorEditor(Mobile).svelte` liest seit S6d nicht mehr aus dem
Context, sondern aus `corridorPropsAus(wizardState)`), und der Schlangen-Entscheid F1
(`hubPutQueue` bleibt aktiv, Payload-Bau bleibt im `enqueue()`-Closure) wird dokumentiert.

**Diese Scheibe verändert kein Verhalten.** Kein Payload-Bau, keine Hydration, kein
Rollback und keine Schreibschlangen-Logik wird inhaltlich angefasst — reiner Umzug plus
mechanische Importpfad-Korrektur.

## Source

- **File (Frontend):**
  `frontend/src/lib/components/compare/compareHubWizardBridge.ts` (DELETE),
  `frontend/src/lib/components/compare/compareHubPersistenz.ts` (neu),
  `frontend/src/lib/components/compare/compareHubHydration.ts` (neu),
  `frontend/src/lib/components/shared/alarmeVergleichSpeicherung.ts`,
  `frontend/src/lib/components/compare/CompareTabs.svelte`,
  `frontend/src/routes/compare/+page.svelte`,
  42 Testdateien (s. Test-Plan).
- **Identifier:** `compareHubPersistenz.ts` exportiert `buildHubPutPayload`, `HubEdit`,
  `snapshotForRollback`, `buildToggleActivePutPayload`, `buildFreshTogglePutPayload`,
  `hubActivationBanner`, `createPutQueue`, `PutQueue`. `compareHubHydration.ts` exportiert
  `hydrateHubFieldsFromPreset` (vormals `hydrateWizardStateFromPreset`), `HubFields`
  (vormals `HubWizardFields`), `hydrateAlarmFieldsFromPreset`. `AlarmHydrationTarget`
  (vormals in der Bridge) wird als lokaler Typ in `shared/alarmeVergleichSpeicherung.ts`
  definiert, Muster `VersandHydrationTarget` dort.

Betroffene Schicht: ausschließlich **Frontend** (`frontend/src/lib/components/`). Kein
Go-API- und kein Python-Core-Code in dieser Scheibe.

## Nicht in dieser Scheibe

- **`WeatherMetricsTab.svelte` behält `wiz: CompareWizardState` als Prop.** Der Umbau auf
  Wertprops (`wetterMetrikenPropsAus`) ist eine eigene, deutlich größere Scheibe (S6g) —
  Grund: WMT schreibt zehn Felder direkt und braucht dafür eine eigene
  Ratschen-Vertragsausnahme (s. „Randbedingungen für S6g" unten). Die S6e-Spec-Aussage
  (`rework_2276_s6e_versand.md:33`), S6e sei „die letzte Scheibe, die eine `wiz`-Referenz
  aus einem `shared/`-Organismus abbaut", ist damit **überholt** — sie stimmte nur für
  `VersandTab.svelte`, nicht für `WeatherMetricsTab.svelte`. Diese Spec korrigiert das.
- **Die Hub-Klasseninstanz `new CompareWizardState()` (`CompareTabs.svelte:329`) bleibt
  bestehen.** Sie wird nach wie vor für `WeatherMetricsTab` (Prop `wiz`) und als Ziel der
  Hydrationsfunktionen gebraucht. Nur der `setContext`-Aufruf auf Zeile 330 entfällt — die
  Instanz selbst, ihre Hydration und ihre Verwendung als `wiz`-Prop für WMT sind unverändert.
- **`/compare/new` (Issue #2277) wird nicht berührt.** `CompareNewEditor.svelte` und
  `Step2Orte.svelte` importieren die Bridge **nicht** — ihr `getContext('compare-wizard-state')`
  liest aus einem eigenen, unabhängigen `setContext` in `routes/compare/new/+page.svelte:20`,
  nicht aus `CompareTabs.svelte`. Der Wegfall des Hub-`setContext` hat dort keine Wirkung.
- **AC-2-Endbilanz der 14 verbleibenden HERKUNFT-Einträge** (Speicherweg-Prädikate,
  Corridor-Katalog-Guards, `maybeSchedule` u. a., s. Kontextdokument Risiko 5) wird NICHT in
  dieser Scheibe gezogen — sie hängt am WMT-Umbau und gehört zu S6g.
- **Kein Ratschen-Rückbau.** `context_herkunft_zweige_eingefroren.test.ts` wird in dieser
  Scheibe NICHT angefasst — weder Zahl noch Fundorte ändern sich (s. AC-6).
- **`flushPendingLayoutSave` (`weatherMetricsCompareSave.ts:231`, ohne Produktiv-Aufrufer)
  wird nicht bereinigt** — Nebenbefund, gehört zu S6g/#1199.
- **Kein neuer E2E-Test.** Das bestehende Compare-Hub-Regressionsnetz deckt alle betroffenen
  Pfade bereits ab (s. AC-7) — reiner Umzug rechtfertigt keine neue Spec.

## Affected Files

| File | Change Type | Description |
|------|-------------|--------------|
| `frontend/src/lib/components/compare/compareHubWizardBridge.ts` | **DELETE** | Nach dem Umzug 0 Zeilen Restbestand; kein Re-Export-Shim |
| `frontend/src/lib/components/compare/compareHubPersistenz.ts` | **CREATE** | `buildHubPutPayload`, `HubEdit`, `snapshotForRollback`, `buildToggleActivePutPayload`, `buildFreshTogglePutPayload`, `hubActivationBanner`, `createPutQueue`, `PutQueue` — Funktionskörper/JSDoc byte-identisch aus der Bridge übernommen, nur Modul-Header neu; Import von `buildComparePresetSavePayload` (`compareEditorSave.ts`), `CompareChannelActiveMetrics` (`weather-metrics-tab/compareChannelMetricLayouts.ts`), `normalizeStoredActiveMetrics`/`normalizeStoredOutlookMetrics` (`weather-metrics-tab/compareMetricSelection.ts`), `CompareStatus`/`computePauseToggle` (`subscriptionHelpers.ts`), `ActivityProfile`/`ComparePreset`/`Corridor` (`../../types.ts`), `IdealRange` (`shared/corridor-editor/corridorEditorState.ts`) |
| `frontend/src/lib/components/compare/compareHubHydration.ts` | **CREATE** | `hydrateHubFieldsFromPreset` (vormals `hydrateWizardStateFromPreset`), `HubFields` (vormals `HubWizardFields`), `hydrateAlarmFieldsFromPreset` — byte-identisch übernommen bis auf die zwei Umbenennungen; Import von `rehydrateActiveMetrics` (`compareEditorLoad.ts`), `registeredCompareMetricCatalog`/`CompareSelectionEntry` (`compareMetricSelection.ts`), `hydrateWeatherMetricsFromPreset` (`weather-metrics-tab/weatherMetricsCompareSave.ts`), `ActivityProfile`/`ComparePreset`/`Corridor` (`../../types.ts`), `IdealRange` (`corridorEditorState.ts`); **neu:** `import type { AlarmHydrationTarget } from '../shared/alarmeVergleichSpeicherung.ts'` (Richtung dreht sich um, s. Design-Entscheidung 2) |
| `frontend/src/lib/components/shared/alarmeVergleichSpeicherung.ts` | MODIFY | Zeile 17 (`import type { AlarmHydrationTarget } from '../compare/compareHubWizardBridge.ts';`) entfällt; `AlarmHydrationTarget`-Interface (32 Zeilen, aus Bridge `:360-391`, byte-identisch samt JSDoc) wird lokal definiert, Einfügeort zwischen `AlarmSnapshot`-Interface und `alarmSnapshotAus()` — Muster `VersandHydrationTarget` in `versandVergleichSpeicherung.ts:48-63`; Kommentar `:9` („aus ihr kommen nur Typen") wird an Ort und Stelle umformuliert (gleiche Zeilenanzahl, keine Zeile entfernt/hinzugefügt) |
| `frontend/src/lib/components/compare/CompareTabs.svelte` | MODIFY | Importblock `:80-88` (`hydrateWizardStateFromPreset, buildHubPutPayload, snapshotForRollback, buildToggleActivePutPayload, hydrateAlarmFieldsFromPreset, hubActivationBanner, createPutQueue` aus `./compareHubWizardBridge.ts`) wird auf zwei Importe gegen `./compareHubHydration.ts` (`hydrateHubFieldsFromPreset`, `hydrateAlarmFieldsFromPreset`) und `./compareHubPersistenz.ts` (`buildHubPutPayload`, `snapshotForRollback`, `buildToggleActivePutPayload`, `hubActivationBanner`, `createPutQueue`) aufgeteilt; Aufrufstelle `:342` (`hydrateWizardStateFromPreset` → `hydrateHubFieldsFromPreset`); Kommentar `:207` (`compareHubWizardBridge.ts: createPutQueue`) an Ort und Stelle umformuliert; `setContext`-Aufruf `:330` entfällt; `setContext`-Import aus `import { setContext, onMount } from 'svelte'` (`:41`) entfällt (`onMount` bleibt, wird bei `:140` noch gebraucht); `CompareWizardState`-Instanziierung `:329` bleibt unverändert |
| `frontend/src/routes/compare/+page.svelte` | MODIFY | Importpfad `:26` (`buildFreshTogglePutPayload` aus `$lib/components/compare/compareHubWizardBridge.js`) → `$lib/components/compare/compareHubPersistenz.js` |
| `frontend/src/lib/components/compare/__tests__/compare_hub_wizard_bridge.test.ts` | **SPLIT + RENAME** | Zerfällt entlang der Produktiv-Modulgrenze: `describe('AC-16: …')` (Zeilen 111–164, nutzt ausschließlich `hydrateWizardStateFromPreset`) → neue Datei `compare_hub_idealwerte_hydration.test.ts`; alle übrigen `describe`-Blöcke (Zeilen 166–498, nutzen ausschließlich `buildHubPutPayload`/`snapshotForRollback`/`buildToggleActivePutPayload`) → neue Datei `compare_hub_orte_idealwerte_persistenz.test.ts`. Beide erhalten ihre eigene Kopie von Header-Kommentar (aktualisiert auf S6f), Imports und `makePreset()`-Fixture. Alte Datei entfällt |
| 34 weitere Testdateien mit echtem Laufzeit-Import aus der Bridge (Liste s. Test-Plan) | MODIFY | Nur Importpfad (ggf. + Funktionsname `hydrateWizardStateFromPreset`→`hydrateHubFieldsFromPreset`), keine Assertion ändert sich |
| `frontend/src/lib/components/compare/__tests__/totcode_rueckbau_speicherweg.test.ts` | MODIFY | `signaturTypen`-Eintrag `[['compare', 'compareHubWizardBridge.ts'], ['HubWizardFields', 'HubEdit', 'PutQueue']]` (Zeile 180) wird zu zwei Einträgen: `[['compare', 'compareHubPersistenz.ts'], ['HubEdit', 'PutQueue']]` und `[['compare', 'compareHubHydration.ts'], ['HubFields']]` |
| `frontend/src/lib/components/compare/__tests__/compare_hub_layout_save.test.ts`, `compare_hub_layout_rollback.test.ts` | MODIFY | Reine Kommentar-Erwähnungen (`:8/:16` bzw. `:14`) von `compareHubWizardBridge.ts`, kein echter Import — Text an Ort und Stelle ersetzt (AC-4-Messung erfasst auch Kommentare) |
| `frontend/src/lib/components/shared/__tests__/versand_tab_laedt_keine_compare_klebeschicht.test.ts`, `alarme_tab_laedt_keine_compare_klebeschicht.test.ts`, `frontend/src/lib/components/shared/corridor-editor/__tests__/corridor_editor_laedt_keine_compare_klebeschicht.test.ts`, `frontend/src/lib/components/shared/weather-metrics-tab/__tests__/wetter_metriken_laedt_keine_compare_klebeschicht.test.ts` | MODIFY | `BRIDGE`-Konstante (bisher genau ein Pfad `/src/lib/components/compare/compareHubWizardBridge.ts`) wird auf zwei Pfade erweitert (`compareHubPersistenz.ts`, `compareHubHydration.ts`); Abwesenheits-Assertion prüft beide |
| Kommentar-Erwähnungen `VersandTab.svelte:27`, `versandVergleichSpeicherung.ts:10`, `corridor-editor/wertebereicheVergleichSpeicherung.ts:10`, `weather-metrics-tab/weatherMetricsCompareSave.ts:5/12/129/184` | MODIFY | Text an Ort und Stelle ersetzt (`compareHubWizardBridge.ts` → passender neuer Modulname), **Zeilenzahl der jeweiligen Datei bleibt exakt gleich** — diese vier Dateien liegen unter `shared/` und tragen ratschengeschützte Zeilen (`versandVergleichSpeicherung.ts:221`, `wertebereicheVergleichSpeicherung.ts:200`, `weatherMetricsCompareSave.ts:534`) unterhalb der bearbeiteten Kommentare |
| `frontend/src/lib/components/compare/__tests__/compare_hub_bridge_restlos_entfernt.test.ts` | **CREATE** | Neuer, kleiner Kern-Test für die AC-4-Messung: (a) `compareHubWizardBridge.ts` existiert nicht mehr, (b) `grep -rn compareHubWizardBridge frontend/src` (mit `SHARED`-artiger, relativ zur Testdatei aufgelöster Wurzel wie in der HERKUNFT-Ratsche) liefert 0 Treffer |

**5 produktive Dateien** (1 DELETE, 2 CREATE, 2 MODIFY) + **43 Testdateien** (1 SPLIT+RENAME
→ 2 neue, 34 mechanisch, 2 Kommentar-only, 1 Signatur-Update, 4 Guard-Fortschreibungen, 1 neue
Kern-Prüfung).

## Estimated Scope

- **LoC (produktiv):** ca. **455 Zeilen aus der Bridge raus, ~460 Zeilen in die zwei neuen
  Module rein** (455 + minimale Header-/Rename-Differenz) + 32 Zeilen `AlarmHydrationTarget`
  neu in `alarmeVergleichSpeicherung.ts` (Import-Zeile −1) + kleine Importblock-Änderungen in
  `CompareTabs.svelte`/`+page.svelte`. Netto praktisch **0** an Logik, aber brutto hoch, weil
  ein voller Datei-Umzug als Löschung + Neuanlage zählt, nicht als Verschiebung.
- **LoC (Tests):** 34 Dateien mit 1–2 geänderten Zeilen (Importpfad, ggf. Funktionsname) +
  2 Dateien mit 1 geänderter Kommentarzeile + 1 Datei mit einer aufgeteilten Array-Zeile
  (`totcode_rueckbau_speicherweg.test.ts`) + 4 Guard-Dateien mit je ~3 geänderten Zeilen +
  1 gesplittete Datei (498 Zeilen brutto neu verteilt, netto ~0) + 1 neue kleine Kern-Testdatei
  (~50–70 Zeilen).
- **Files:** 5 produktiv (1 DELETE, 2 CREATE, 2 MODIFY) + 43 Test-Dateien.
- **Effort:** medium — inhaltlich trivial (mechanischer Umzug), aber **breit** (43 Dateien)
  und **fehleranfällig an genau einer Stelle**: die vier `shared/`-Dateien mit
  ratschengeschützten Zeilen darunter (Kommentar-Ersetzung MUSS zeilenneutral sein, sonst wird
  `context_herkunft_zweige_eingefroren.test.ts` grundlos rot).
- **Risk Level: NIEDRIG.** Reiner Umzug ohne Verhaltensänderung, aber die Ratschen-Zeilenneutralität
  in vier Dateien ist eine harte, leicht zu übersehende Nebenbedingung (s. AC-6,
  Mutations-Gegenprobe).
- **LoC-Limit 250/Workflow wird überschritten** — allein der Bridge-Umzug (455 raus + ~460
  rein) sprengt das Limit brutto, obwohl netto ~0 Logik geändert wird. `workflow.py set-field
  loc_limit_override 500` vor `/40` einplanen; nach `/50` per `workflow.py status` den
  tatsächlichen Delta-Wert prüfen (Umzug zählt als Löschung+Neuanlage, nicht als Rename) — bei
  weiterer Überschreitung Override entsprechend nachziehen, Begründung „Umzug, keine neue
  Logik" im Commit vermerken.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/src/lib/components/shared/versandVergleichSpeicherung.ts` (`VersandHydrationTarget`, S5/S6e) | module | Formvorbild für Platzierung und Struktur von `AlarmHydrationTarget` in `alarmeVergleichSpeicherung.ts` |
| `frontend/src/lib/components/compare/__tests__/hub_put_queue.test.ts` | test | Bestehender, unveränderter (nur Importpfad) Verhaltensnachweis für F1 — Cross-Tab-Sequenz gegen `fakeTripServer`, beweist Payload-Bau innerhalb `enqueue()` |
| `frontend/src/lib/components/shared/__tests__/context_herkunft_zweige_eingefroren.test.ts` | test | HERKUNFT-Ratsche, 47 Fundstellen unter `shared/` — wird NICHT editiert, muss aber unverändert grün bleiben (s. AC-6) |
| `docs/specs/modules/rework_2276_s6a_totcode_und_ratsche.md`, `…s6b…`, `…s6c_alarme.md`, `…s6d_wertebereiche.md`, `…s6e_versand.md` | spec | Vorgänger-Scheiben; S6e-Spec-Aussage „letzte wiz-Abbau-Scheibe" wird hier korrigiert (s. Nicht in dieser Scheibe) |
| `docs/context/refactor-2276-s6f-bridge-rueckbau.md` | context | Analyse dieser Scheibe inkl. Schnitt-Entscheid; diese Spec präzisiert die Test-Dateizahl (42 statt geschätzt ~32, s. u.) |

## Implementation Details

### Design-Entscheidungen

1. **Zwei Zielmodule nach Funktionsklasse, nicht nach Feature.** Die acht
   Laufzeit-Exporte der Bridge zerfallen sauber in zwei unabhängige Gruppen ohne
   Querimporte zwischen ihnen (geprüft durch Lesen aller Bridge-internen Importe):
   - **`compareHubPersistenz.ts`** — alles, was einen Hub-PUT baut oder serialisiert:
     `buildHubPutPayload`, `HubEdit`, `snapshotForRollback`, `buildToggleActivePutPayload`,
     `buildFreshTogglePutPayload`, `hubActivationBanner`, `createPutQueue`, `PutQueue`.
   - **`compareHubHydration.ts`** — alles, was einen Hub-Zustand aus einem `ComparePreset`
     befüllt: `hydrateHubFieldsFromPreset` (vormals `hydrateWizardStateFromPreset`),
     `HubFields` (vormals `HubWizardFields`), `hydrateAlarmFieldsFromPreset`.

   Keine der beiden Gruppen importiert etwas aus der jeweils anderen — jede zieht ihre
   Fremdimporte unabhängig aus `compareEditorSave.ts`, `compareEditorLoad.ts`,
   `weatherMetricsCompareSave.ts`, `compareMetricSelection.ts`,
   `compareChannelMetricLayouts.ts`, `subscriptionHelpers.ts`, `types.ts`,
   `corridorEditorState.ts`. Einzige neue Kopplung: `compareHubHydration.ts` importiert
   `AlarmHydrationTarget` per `import type` aus `shared/alarmeVergleichSpeicherung.ts` (s.
   Design-Entscheidung 2) — ein reiner Typ-Import, verschwindet beim Übersetzen, taucht in
   keinem Ladegraphen auf.

2. **`AlarmHydrationTarget` wandert nach `shared/alarmeVergleichSpeicherung.ts`, die
   Importrichtung dreht sich um.** Heute importiert `shared/alarmeVergleichSpeicherung.ts`
   (Zeile 17) den Typ AUS `compare/compareHubWizardBridge.ts` — die einzige
   `shared/`→`compare/`-Kopplung in der gesamten Speicherweg-Landschaft (alle anderen
   `*VergleichSpeicherung.ts`-Module definieren ihr `*HydrationTarget` lokal, Muster
   `VersandHydrationTarget`). Nach dem Umzug definiert `alarmeVergleichSpeicherung.ts` den
   Typ lokal (Einfügeort: zwischen `AlarmSnapshot`-Interface und `alarmSnapshotAus()`,
   analog `VersandSnapshot` → `VersandHydrationTarget` → `versandSnapshotAus()` in
   `versandVergleichSpeicherung.ts:35-98`). `compareHubHydration.ts` (für
   `hydrateAlarmFieldsFromPreset`s Parametertyp) importiert ihn jetzt PER TYP aus
   `shared/`. Die Kopplungsrichtung dreht sich also von `shared→compare` auf `compare→shared`
   (Typ-only) — konsistent mit dem Muster aller anderen Speicherweg-Module und mit der
   AST-Wächter-Regel „kein `shared/`-Organismus lädt Compare-Hub-Orchestrierung zur
   Laufzeit" (Typ-Imports laden zur Laufzeit nichts, s. AC-3).

3. **Kein Re-Export-Shim.** Eine Datei `compareHubWizardBridge.ts`, die nur noch
   `export * from './compareHubPersistenz.ts'; export * from './compareHubHydration.ts';`
   enthielte, würde AC-4 aushebeln (der Name bliebe im Ladegraphen sichtbar) und wäre genau
   die Art Übergangs-Klebeschicht, die diese Scheibe beseitigen soll. Alle 36 Importeure
   (2 produktiv + 34 Test) werden im selben Commit auf die neuen Pfade umgestellt.

4. **F1 — die Schreibschlange bleibt unverändert aktiv (dokumentierter Entscheid, kein neuer
   Code).** `hubPutQueue = createPutQueue()` (`CompareTabs.svelte:208`, unverändert) bleibt
   die einzige Serialisierung aller vier Hub-PUT-Pfade (Orte/Idealwerte/Versand/Toggle-Active).
   Payload-Bau bleibt im `enqueue()`-Closure (`persistPickedIds`, `:265-267`, unverändert) —
   NICHT davor. Begründung (unverändert seit #1256 Scheibe 7 Fix-Loop 1, F002/F003): ETag/
   If-Match serialisiert nur das Netz, nicht den Zustand — ohne die Queue könnte eine zweite,
   schneller startende PUT-Anfrage mit veralteter `currentPreset`-Baseline eine erste,
   noch laufende überschreiben (Orte↔Reiter, Toggle↔Reiter, Orte↔Toggle, Orte↔Orte). Der
   Umzug von `createPutQueue`/`buildToggleActivePutPayload` nach `compareHubPersistenz.ts`
   ändert an dieser Garantie nichts — `hub_put_queue.test.ts` bewacht sie unverändert (nur
   Importpfad geändert, s. AC-5).

5. **F4 — Voll-Spread-Payload bleibt.** `buildHubPutPayload` reicht weiterhin das komplette
   `ComparePreset` an `buildComparePresetSavePayload` (kein Minimal-Body, kein Patch-DTO in
   dieser Scheibe) — unverändert seit der ursprünglichen Bridge-Implementierung.

6. **Toter `setContext`-Aufruf entfällt, Instanz bleibt.** `CompareTabs.svelte:329` legt
   weiterhin `const wizardState = new CompareWizardState();` an (gebraucht für
   `WeatherMetricsTab`s Prop `wiz={wizardState}` sowie als Hydrationsziel). Nur
   `setContext('compare-wizard-state', wizardState)` (`:330`) entfällt — verifiziert durch
   Grep über den gesamten Hub-Baum: kein `getContext('compare-wizard-state')` existiert dort
   mehr (`CorridorEditor(Mobile).svelte` liest seit S6d aus `corridorPropsAus(wizardState)`,
   nicht mehr aus Context). Die beiden einzigen `getContext`-Leser
   (`compare/steps/Step2Orte.svelte:30`, `compare-new/CompareNewEditor.svelte:67`) hängen an
   einem eigenen, unabhängigen `setContext` in `routes/compare/new/+page.svelte:20` — sie sind
   nie mit dem Hub-Context verbunden gewesen.

7. **Kommentar-Bereinigung ist Ersetzung an Ort und Stelle, niemals Zeilen-Löschung — Pflicht
   für vier `shared/`-Dateien.** `VersandTab.svelte:27`, `versandVergleichSpeicherung.ts:10`,
   `corridor-editor/wertebereicheVergleichSpeicherung.ts:10`,
   `weather-metrics-tab/weatherMetricsCompareSave.ts:5/12/129/184` erwähnen
   `compareHubWizardBridge.ts` nur in Kommentaren. Unterhalb jeder dieser Stellen liegen
   ratschengeschützte Zeilen (`versandVergleichSpeicherung.ts:221`,
   `wertebereicheVergleichSpeicherung.ts:200`, `weatherMetricsCompareSave.ts:534`) — würde
   eine Zeile gelöscht statt ersetzt, verschöbe sich die geschützte Zeile nach oben und
   `context_herkunft_zweige_eingefroren.test.ts` würde grundlos rot (Präzedenz-Vertrag aus
   S6a/S6b, unverändert gültig). `alarmeVergleichSpeicherung.ts:9` fällt NICHT unter diese
   Einschränkung im engen Sinn (die Datei trägt keine ratschengeschützte Zeile), wird aber aus
   Konsistenzgründen ebenfalls zeilenneutral editiert.

### Wirkort je Zusicherung

| Zusicherung | Wirkort | Warum |
|---|---|---|
| AC-1 (Bridge-Datei weg, Exporte vollständig umgezogen) | Kern — Existenzprüfung + `totcode_rueckbau_speicherweg.test.ts` (Signaturtypen) + umgezogene Verhaltenstests | Statischer Fakt + Verhaltensnachweis der reinen Funktionen |
| AC-2 (AC-4 aus #2276: 0 wörtliche Treffer) | Kern — neue Datei `compare_hub_bridge_restlos_entfernt.test.ts` | Grep-Messung ist der im Ticket vorgeschriebene Nachweis, strenger als ein Kommentarfilter |
| AC-3 (kein `shared/`-Organismus lädt die neuen Hub-Module) | Kern — vier fortgeschriebene Ladegraph-Wächter | Laufzeit-Ladegraph, kein Dateiinhalt-Grep — bereits etabliertes Muster (S2–S5) |
| AC-4 (toter Context-Aufruf weg, `/compare/new` unberührt) | Kern (statisch) + bestehende E2E (Regressionsnetz) | Statischer Fakt + Verhaltensgleichheit an zwei getrennten Flächen |
| AC-5 (F1: Schlange unverändert wirksam) | Kern — `hub_put_queue.test.ts`, unverändert bis auf Importpfad | Bereits vorhandener, scharfer Verhaltensnachweis (Cross-Tab-Sequenz) |
| AC-6 (HERKUNFT-Ratsche unverändert, 47, Datei nicht angefasst) | Kern — `node --test` auf `context_herkunft_zweige_eingefroren.test.ts` | Struktur-, kein Verhaltensnachweis |
| AC-7 (Verhaltensgleichheit Hub + Liste) | bestehende E2E, unverändert grün | Reiner Umzug — kein neuer Test nötig, bestehendes Netz deckt alle betroffenen Pfade |

### Reihenfolge (Implementation Note)

1. `compareHubPersistenz.ts` und `compareHubHydration.ts` anlegen (Funktionskörper
   byte-identisch kopiert, Rename nur bei `HubWizardFields`→`HubFields` und
   `hydrateWizardStateFromPreset`→`hydrateHubFieldsFromPreset`).
2. `AlarmHydrationTarget` nach `shared/alarmeVergleichSpeicherung.ts` verschieben, Import in
   `compareHubHydration.ts` auf `import type … from '../shared/alarmeVergleichSpeicherung.ts'`
   umstellen.
3. `CompareTabs.svelte` und `routes/compare/+page.svelte` auf die neuen Importpfade umstellen;
   `setContext`-Aufruf + Import entfernen.
4. `compareHubWizardBridge.ts` löschen.
5. Alle 34 mechanischen Testdateien + 2 Kommentar-only-Testdateien + `totcode_rueckbau_speicherweg.test.ts`
   auf die neuen Pfade/Namen umstellen.
6. `compare_hub_wizard_bridge.test.ts` in die zwei neuen Dateien aufteilen, alte Datei löschen.
7. Vier `*_laedt_keine_compare_klebeschicht.test.ts`-Wächter fortschreiben.
8. Neue Kern-Testdatei `compare_hub_bridge_restlos_entfernt.test.ts` anlegen (AC-2-Nachweis).
9. Vier Kommentar-Stellen in `shared/` zeilenneutral bereinigen — als letzter Schritt, damit
   sich beim Test-Lauf zwischendurch keine Ratschen-Fehlmeldung durch einen noch
   unvollständigen Zwischenstand einschleicht.
10. `context_herkunft_zweige_eingefroren.test.ts` läuft **unverändert** grün — falls nicht:
    Zeilenzahl der zuletzt bearbeiteten `shared/`-Datei wiederherstellen, NICHT die
    eingefrorene Liste nachziehen (Standard-Vertrag aus S6a).

## Test-Plan

**Umbenannt/gesplittet (Verhalten statt Issue-Nummer):**

| Alt | Neu | Grund |
|---|---|---|
| `compare/__tests__/compare_hub_wizard_bridge.test.ts` (498 Z.) | `compare/__tests__/compare_hub_idealwerte_hydration.test.ts` (describe AC-16, ~55 Z. + Fixture) | Testet ausschließlich `hydrateHubFieldsFromPreset` |
| — (Teil derselben Ursprungsdatei) | `compare/__tests__/compare_hub_orte_idealwerte_persistenz.test.ts` (übrige describes, ~390 Z. + Fixture) | Testet ausschließlich `buildHubPutPayload`/`snapshotForRollback`/`buildToggleActivePutPayload` |

**Neu angelegt:**

- `compare/__tests__/compare_hub_bridge_restlos_entfernt.test.ts` — AC-2-Nachweis (Datei weg +
  0 Grep-Treffer).

**Mechanisch fortgeschrieben (nur Importpfad, ggf. + `hydrateWizardStateFromPreset` →
`hydrateHubFieldsFromPreset`), 34 Dateien:**

`compare/__tests__/`: `hub_versand_inline.test.ts`, `hub_put_queue.test.ts`,
`hub_idealwerte_fehlschlag_erreicht_speichertakt.test.ts`, `kebab_toggle_delegation.test.ts`,
`list_toggle_read_modify_write.test.ts`, `compareActiveMetricsStorageFormat.test.ts` (Import
splittet sich auf beide neuen Module).

`shared/corridor-editor/__tests__/`: `wertebereiche_vergleich_speichert_einmal.test.ts`,
`wertebereiche_vergleich_flush_vor_pausieren.test.ts`,
`wertebereiche_nutzlast_verliert_keine_daten.test.ts`,
`wertebereiche_und_alarme_teilen_den_speicherplatz.test.ts`,
`wertebereiche_vergleich_konflikt_nochmal_speichern.test.ts`.

`shared/__tests__/`: `versand_vergleich_flush_vor_pausieren.test.ts`,
`versand_vergleich_konflikt_nochmal_speichern.test.ts`,
`alarme_vergleich_konflikt_nochmal_speichern.test.ts`,
`versand_enddatum_ohne_ereignis_bleibt_wirksam.test.ts`,
`alarme_vergleich_ruecknahme_waehrend_put.test.ts`, `compare_hub_alarme_bridge.test.ts`,
`alarme_vergleich_kein_zurueckschreiben.test.ts`, `alarme_vergleich_speichert_selbst.test.ts`,
`versand_vergleich_reiterwechsel_verliert_nichts.test.ts`,
`versand_vergleich_speichert_selbst.test.ts`, `alarme_vergleich_flush_beim_reiterwechsel.test.ts`,
`compare_alarme_channel_threshold_save.test.ts`, `versand_nutzlast_reicht_keepalive_durch.test.ts`.

`shared/weather-metrics-tab/__tests__/`: `wetter_metriken_drei_stille_gesten_bleiben_wirksam.test.ts`,
`wetter_metriken_vergleich_flush_vor_pausieren.test.ts`,
`wetter_metriken_vergleich_konflikt_nochmal_speichern.test.ts`,
`wetter_metriken_hydration_vollstaendig_vor_baseline.test.ts`,
`wetter_metriken_nutzlast_verliert_keine_daten.test.ts`,
`wetter_metriken_und_wertebereiche_teilen_active_metric_keys.test.ts`,
`wetter_metriken_vergleich_speichert_einmal.test.ts`, `wetter_metriken_intra_gesture_kollision.test.ts`,
`wetter_metriken_nutzlast_reicht_keepalive_durch.test.ts`,
`wetter_metriken_reiterwechsel_verliert_nichts.test.ts`.

**Kommentar-only (kein echter Import), Text an Ort und Stelle ersetzt:**
`compare/__tests__/compare_hub_layout_save.test.ts`, `compare_hub_layout_rollback.test.ts`.

**Signatur-Anker aktualisiert:** `compare/__tests__/totcode_rueckbau_speicherweg.test.ts`
(`signaturTypen`-Array, ein Eintrag wird zu zwei).

**Guard-Wächter fortgeschrieben (BRIDGE-Konstante auf zwei Pfade erweitert):**
`shared/__tests__/versand_tab_laedt_keine_compare_klebeschicht.test.ts`,
`shared/__tests__/alarme_tab_laedt_keine_compare_klebeschicht.test.ts`,
`shared/corridor-editor/__tests__/corridor_editor_laedt_keine_compare_klebeschicht.test.ts`,
`shared/weather-metrics-tab/__tests__/wetter_metriken_laedt_keine_compare_klebeschicht.test.ts`.

**Unverändert (nur zur Kenntnis — bleiben grün ohne jede Änderung):**
`context_herkunft_zweige_eingefroren.test.ts` sowie alle E2E-Specs aus AC-7.

**LoC-Messverfahren:** Diese Scheibe ist ein reiner Datei-Umzug — `git diff --stat` zählt eine
Löschung (455 Z.) und zwei Neuanlagen (~460 Z. zusammen) als Brutto-Delta, obwohl die Logik
netto unverändert bleibt. Vor `/40`: `workflow.py set-field loc_limit_override 500` setzen
(analog S6c/S6d/S6e). Nach `/50`: `workflow.py status` gegenlesen — überschreitet das
tatsächliche Delta weiterhin 500 (z. B. durch die Testdatei-Aufteilung), Override auf einen
gemessenen, im Commit begründeten Wert erhöhen („Umzug, keine neue Logik, Brutto-Diff durch
Datei-Split").

## Expected Behavior

- **Input:** Alle bisherigen Nutzeraktionen im Ortsvergleich-Hub (`/compare/[id]`) und in der
  Liste (`/compare`) — Orte hinzufügen/entfernen/umsortieren, Idealwerte/Alarme/Versand/
  Wetter-Metriken bearbeiten, Aktivieren/Pausieren im Hub und im Listen-Kebab.
- **Output:** Identisch zu heute — derselbe Speicherweg (ein PUT je Änderung über
  `hubPutQueue`, Diff-Gate wo zutreffend, Rollback bei Fehler), dieselbe
  Aktivierungs-Banner-Anzeige, dieselbe Hydration beim Laden. Intern liegen Payload-Bau und
  Hydration jetzt in zwei benannten Modulen statt einer Klebeschicht — sichtbar für
  Nutzer:innen ist das nicht.
- **Side effects:** Keine. Kein API-Vertrag, kein Go-Handler, kein Datenmodell wird
  angefasst.

## Acceptance Criteria

- **AC-1 (Bridge-Datei vollständig aufgelöst, Exporte byte-identisch in zwei Zielmodulen):**
  Given `compareHubWizardBridge.ts` trägt heute acht Laufzeit-Exporte + einen Typ-Export,
  alle mit produktiven Importeuren / When die Datei aufgelöst wird in
  `compare/compareHubPersistenz.ts` (`buildHubPutPayload`, `HubEdit`, `snapshotForRollback`,
  `buildToggleActivePutPayload`, `buildFreshTogglePutPayload`, `hubActivationBanner`,
  `createPutQueue`, `PutQueue`) und `compare/compareHubHydration.ts`
  (`hydrateHubFieldsFromPreset`, `HubFields`, `hydrateAlarmFieldsFromPreset`), ohne
  Re-Export-Shim / Then existiert `compareHubWizardBridge.ts` nicht mehr, beide neuen Module
  exportieren exakt die genannten Namen, und alle umgezogenen Verhaltenstests
  (`compare_hub_idealwerte_hydration.test.ts`, `compare_hub_orte_idealwerte_persistenz.test.ts`
  sowie die 34 mechanisch fortgeschriebenen Dateien) bleiben inhaltlich unverändert grün.
  - Test: Kern — Datei-Existenzprüfung, `totcode_rueckbau_speicherweg.test.ts` (Signaturtypen
    auf die zwei neuen Module aufgeteilt), plus die umgezogenen Verhaltenstests selbst.

- **AC-2 (AC-4 aus #2276 — wörtliche Suche liefert 0 Treffer):** Given der Name
  `compareHubWizardBridge` steht heute in 3 produktiven Dateien und 40 Testdateien (davon 38
  echte Importe/Signatur-Anker, 2 reine Kommentar-Erwähnungen) / When Datei gelöscht, alle
  Importpfade umgestellt und alle Kommentar-Erwähnungen an Ort und Stelle ersetzt werden /
  Then liefert `grep -rn compareHubWizardBridge frontend/src` **0 Treffer**.
  - Test: Kern — `compare_hub_bridge_restlos_entfernt.test.ts` (neu), Shell-Grep relativ zur
    eigenen Testdatei aufgelöst (Pfadregel #1409, Muster `context_herkunft_zweige_eingefroren.test.ts`).

- **AC-3 (kein `shared/`-Organismus lädt die neuen Hub-Module zur Laufzeit):** Given die vier
  bestehenden Ladegraph-Wächter (`versand_tab_…`, `alarme_tab_…`, `corridor_editor_…`,
  `wetter_metriken_…laedt_keine_compare_klebeschicht.test.ts`) prüfen heute die Abwesenheit
  von `compare/compareHubWizardBridge.ts` im Ladegraphen der jeweiligen Organismen / When ihre
  `BRIDGE`-Konstante auf die Abwesenheit BEIDER neuer Module
  (`compare/compareHubPersistenz.ts`, `compare/compareHubHydration.ts`) erweitert wird / Then
  bleiben alle vier Wächter grün.
  - Mutations-Gegenprobe: probeweise einen echten Laufzeit-Import von `createPutQueue` aus
    `compareHubPersistenz.ts` in `VersandTab.svelte` einfügen ⇒
    `versand_tab_laedt_keine_compare_klebeschicht.test.ts` wird rot — kein anderer Test im
    Bestand sieht diese Regression, weil ein reiner Werte-Vergleich die Reaktivität/den
    Ladegraphen nicht prüft.

- **AC-4 (toter Context-Aufruf entfernt, `/compare/new` unberührt):** Given
  `CompareTabs.svelte:330` ruft `setContext('compare-wizard-state', wizardState)` auf, obwohl
  im gesamten Hub-Baum kein `getContext('compare-wizard-state')` mehr existiert (verifiziert:
  `CorridorEditor(Mobile).svelte` liest seit S6d aus `corridorPropsAus(wizardState)`; die
  einzigen zwei `getContext`-Leser, `Step2Orte.svelte:30` und `CompareNewEditor.svelte:67`,
  hängen an einem eigenen `setContext` in `routes/compare/new/+page.svelte:20`) / When der
  `setContext`-Aufruf und der ungenutzte `setContext`-Import entfernt werden, die
  `CompareWizardState`-Instanz selbst aber bestehen bleibt / Then rendert der Hub unverändert,
  UND `/compare/new` bleibt vollständig unverändert (kein gemeinsamer Context, nie gewesen).
  - Test: Kern — statische Prüfung „`CompareTabs.svelte` enthält keinen `setContext`-Aufruf
    mehr" (Ergänzung in `totcode_rueckbau_speicherweg.test.ts` oder äquivalenter Kern-Check) +
    bestehendes E2E-Regressionsnetz für Hub (AC-7) UND `/compare/new`
    (`compare-editor-slice1.spec.ts`, `compare-editor-slice3.spec.ts`,
    `issue-682-compare-editor-mobile.spec.ts` — alle in `.github/ci_e2e_specs.txt`),
    unverändert grün.

- **AC-5 (F1 — Schreibschlange bleibt unverändert wirksam):** Given `hubPutQueue` serialisiert
  heute alle vier Hub-PUT-Pfade, Payload-Bau liegt im `enqueue()`-Closure
  (`CompareTabs.svelte:265-267`), `hub_put_queue.test.ts` bewacht das bereits real (Cross-Tab-
  Sequenz gegen `fakeTripServer`) / When `createPutQueue`/`buildToggleActivePutPayload` nach
  `compare/compareHubPersistenz.ts` umziehen, ohne dass sich am `enqueue()`-Aufrufmuster in
  `CompareTabs.svelte` oder an der Funktionslogik etwas ändert / Then bleibt
  `hub_put_queue.test.ts` (nur Importpfad geändert) unverändert grün.
  - Mutations-Gegenprobe: den Payload-Bau in `persistPickedIds` (`CompareTabs.svelte`) aus dem
    `enqueue()`-Closure VOR den `hubPutQueue.enqueue(...)`-Aufruf ziehen ⇒ die Cross-Tab-
    Sequenz in `hub_put_queue.test.ts` wird rot, weil die zweite PUT eine bereits veraltete
    Baseline sendet — kein anderer Test im Bestand sieht diese Regression, weil sie nur bei
    zwei schnell aufeinanderfolgenden Schreibvorgängen sichtbar wird.

- **AC-6 (HERKUNFT-Ratsche unverändert grün, Datei nicht angefasst):** Given
  `context_herkunft_zweige_eingefroren.test.ts` zählt heute 47 Fundstellen ausschließlich
  unter `shared/`, vier davon liegen unterhalb von Kommentarzeilen, die in dieser Scheibe
  editiert werden (`versandVergleichSpeicherung.ts:221` unter `:10`,
  `wertebereicheVergleichSpeicherung.ts:200` unter `:10`,
  `weatherMetricsCompareSave.ts:534` unter `:5/12/129/184`) / When alle vier
  Kommentar-Stellen **an Ort und Stelle** (gleiche Zeile, keine Zeile addiert/entfernt) ersetzt
  werden UND `AlarmHydrationTarget` in `alarmeVergleichSpeicherung.ts` eingefügt wird (Datei
  ohne eigene HERKUNFT-Fundstelle, daher ratschenneutral) / Then bleibt
  `context_herkunft_zweige_eingefroren.test.ts` unverändert grün bei
  `EINGEFROREN_SOLL_ANZAHL = 47`, ohne dass diese Scheibe die Ratschen-Datei selbst editiert.
  - Test: Kern — bestehender Ratschen-Test, `node --test`, unverändert.
  - Mutations-Gegenprobe: eine der vier Kommentarstellen durch Zeilen-Löschen statt
    Ersetzen-an-Ort-und-Stelle bereinigen (z. B. `versandVergleichSpeicherung.ts:10` komplett
    entfernen statt umzuformulieren) ⇒ `versandVergleichSpeicherung.ts:221` verschiebt sich
    auf `:220` ⇒ `context_herkunft_zweige_eingefroren.test.ts` wird rot („Ist-Eintrag
    zusätzlich" bzw. „Soll-Eintrag fehlt").

- **AC-7 (Verhaltensgleichheit — bestehendes E2E-Regressionsnetz unverändert grün):** Given
  Orte-Speichern, Aktiv-Schalter im Hub und in der Liste `/compare`, Aktivierungs-Banner,
  Rollback bei Fehler und Hydration werden heute durch das bestehende Compare-Hub-E2E-Netz
  abgedeckt (`compare-hub-inline-edit.spec.ts`, `compare-detail-edit-entry.spec.ts`,
  `compare-cross-user-write-block.spec.ts`, `compare-legacy-fields-survive-save.spec.ts`,
  `compare-alarme-speichert-selbst.spec.ts`, `compare-versand-speichert-selbst.spec.ts`,
  `compare-wertebereiche-speichert-selbst.spec.ts`,
  `compare-wetter-metriken-speichert-selbst.spec.ts` — alle in `.github/ci_e2e_specs.txt`) /
  When Payload-Bau, Schlange, Hydration und Rollback wortidentisch in die neuen Module
  umziehen / Then bleiben alle genannten Specs ohne inhaltliche Änderung grün.
  - Test: Live-E2E — bestehende Specs, keine neue Datei.

## Known Limitations

- **Der Listen-Toggle (`/compare`-Kebab „Pausieren/Aktivieren", `buildFreshTogglePutPayload`)
  hat keine CI-E2E-Abdeckung.** Einziger produktiver Konsument ist
  `routes/compare/+page.svelte`, einziger Verhaltensnachweis ist der Kern-Test
  `list_toggle_read_modify_write.test.ts` (nur Importpfad geändert) sowie der
  Staging-only-Manuallauf `bug-626-compare-menu-actions.spec.ts` (nicht in der CI-Ampel) —
  vorbestehende Lücke, von S6f weder verursacht noch geschlossen.
- **`WeatherMetricsTab.svelte` behält `wiz: CompareWizardState` als Prop.** Das ist bewusst
  außerhalb dieses Schnitts (s. „Nicht in dieser Scheibe") — S6g trägt den Wertprops-Umbau und
  die damit verbundene AC-2-Endbilanz nach.
- **Die Testdatei-Aufteilung (`compare_hub_wizard_bridge.test.ts` → zwei Dateien) ist eine
  Interpretation der Tech-Lead-Entscheidung, keine im Kontextdokument vorweggenommene
  Festlegung** — das Kontextdokument nannte nur „MODIFY/RENAME, nach Verhalten benennen",
  ohne die Aufteilungsgrenze zu bestimmen. Diese Spec legt die Grenze anhand der tatsächlich
  verwendeten Importe fest (AC-16-Block nutzt ausschließlich `hydrateWizardStateFromPreset`,
  alle übrigen Blöcke ausschließlich die drei Persistenz-Funktionen) — eine sauberere,
  spätere Aufteilung wäre nur mit unnötigem Zusatzaufwand möglich gewesen.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue.
- **Rationale:** Die Modul-Aufteilung nach Funktionsklasse (Persistenz vs. Hydration) und die
  Vermeidung von Re-Export-Shims sind lokale Umsetzungsentscheidungen innerhalb eines bereits
  etablierten Musters (jeder Compare-Speicherweg-Baustein — `versandVergleichSpeicherung.ts`,
  `alarmeVergleichSpeicherung.ts`, `wertebereicheVergleichSpeicherung.ts`,
  `weatherMetricsCompareSave.ts` — trägt seine eigene Hydration + Persistenz lokal, ohne
  Laufzeit-Abhängigkeit von einer zentralen Klebeschicht). S6f wendet dasselbe Prinzip auf die
  letzten drei Hub-eigenen PUT-Pfade (Orte, Idealwerte-Teil-Edit, Toggle-Active) an. Kein
  Architekturwechsel, kein neuer API-Vertrag, kein neues Datenmodell.

## Changelog

- 2026-09-22: Initial spec created (Scheibe S6f von #2276, Epic #2345)

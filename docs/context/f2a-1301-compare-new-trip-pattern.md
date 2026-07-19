# Context: f2a-1301-compare-new-trip-pattern

**Issue:** #1301 Scheibe F2a = Vorstufe zu #1273 S5 · **Datum:** 2026-07-19 · **Track:** Full Process
**Verbindliche Richtung (PO 2026-07-19, CLAUDE.md-Invariante „Anlegen"):** `/compare/new` wird Progressive-Tab-Anlege-Seite nach Trip-Muster #622; `CompareEditor` + Wizard fallen danach (F2b).

## Request Summary

Die Anlege-Strecke des Ortsvergleichs (`/compare/new`, heute `CompareEditor mode="create"`, 1.686 Z.) wird durch eine Anlege-Seite nach dem Trip-Vorbild `TripNewEditor` (#622) ersetzt: Progressive Tabs mit Freischalt-Logik, lokaler State, genau EIN `POST` bei „Briefing aktivieren", zusammengesetzt aus den bereits geteilten Organismen. F2b (separater Workflow) löscht danach den Alt-Editor.

## Analyse-Ergebnisse (3 parallele Explore-Agenten)

### A. Trip-Vorbild (#622/#661) — das nachzubauende Muster
- `frontend/src/routes/trips/new/+page.svelte:9` → `<TripNewEditor />`; Server-Load lädt profile fail-soft.
- `TripNewEditor.svelte:38-45` `TAB_DEFS` (6 Tabs mit `lockHint`); reine Logik in `tripNewLogic.ts`: `unlockedTabs`/`doneTabs` (`:14-44`), `progressCount` (`:61`), `canSave` (`:68`), `buildCreateTripPayload` (`:117-156`).
- **Persistenz-Modell:** lokaler State bis zum Schluss, EIN `POST /api/trips` in `buildAndSave()` (`:300-329`), Redirect `goto('/trips/${id}')`; `beforeNavigate`-Auto-Save-Guard (`:332-339`).
- Organismen per `bind:`/lokalem State, KEINE Save-Callbacks: `WeatherMetricsTab` mit `createMode={true}` + `stubTrip` (id `'__new__'`, `:86-92`, `:780`), `EditReportConfigSection mode="create"`, `AlertRulesEditor bind:rules`, `EditStagesPanelNew showSave={false}`.
- Mobile: CSS-only-Switch ≤899px (`.tn-desktop`/`.tn-mobile`, `:1046-1058`), paralleles Markup, `matchMedia`-Flag nur für Einzel-DOM-Fälle (#932). Toast statt Flash bei gesperrtem Tab.
- Specs: `issue_622_trip_new_progressive_editor.md` (Kern: Erstellen-Modus desselben Tab-Editors, EIN POST, geteilte Komponenten ADDITIV create-tauglich), `issue_661_trip_new_mobile.md`. Tests: `tripNewLogic.test.ts`, `issue_658_waypoint_persistence.test.ts`, `issue-661-trip-new-mobile.spec.ts`.

### B. Heutiger Compare-Anlege-Fluss — was zu ersetzen ist
- `routes/compare/new/+page.svelte:16-21`: `new CompareWizardState()` + `setContext('compare-wizard-state')` → `<CompareEditor mode="create" locations>`; Server-Load: locations + profile.
- Tabs `compareEditorLogic.ts:11`: vergleich→orte→idealwerte→layout→alarme→versand; Freischalt-Kette `:27-38` (Name → ≥2 Orte → visited-Kaskade). Continue-CTAs `compare-editor-continue-*` (`CompareEditor.svelte:1251-1310`).
- **Bereits Trip-artig:** KEIN Draft-POST unterwegs; Preset entsteht erst bei „Briefing aktivieren" → `wiz.saveNewPreset()` = `POST /api/compare/presets` (`compareWizardState.svelte.ts:90-153`), Redirect `goto('/compare/'+id)` auf den Hub. `handleSave()` (PUT) ist im Create no-op.
- „Draft" ist rein frontend-abgeleitet (`subscriptionHelpers.ts:83-88`: kein Name oder 0 Orte); kein Backend-Statusfeld. „Setup fortsetzen" geht bereits auf den Hub.
- `steps/Step2Orte.svelte` (424 Z., Prop `dense`, Context `compare-wizard-state`): Compare-eigen = 2-Orte-Minimum-Counter, nummerierte Picked-Liste, Mobile-Library-Verzweigung; geteilt genutzt = `groupLocations` (#301), Smart-Import (#1080: resolve→create→merge).

### C. Organismen-Readiness + Abhängige + E2E-Verträge
- **Alle 4 geteilten Organismen sind anlage-tauglich:** Im `vergleich`-Zweig mutieren `WeatherMetricsTab` (`:601-617`), `CorridorEditor` (`syncToWizard :105-116`, explizite Anlage-Unterstützung `isFreshCompareCreate :62` mit Profil-Prefill), `AlarmeTab` (`:96-162`, Save-$effect route-only `:203`), `VersandTab` (`:154-159`, `activation`-Snippet `:282`) NUR lokalen `wiz`-State — kein Self-Save. PUT-Kopplung liegt ausschließlich außen (`compareHubWizardBridge.ts`, PUT-only, braucht `preset.id` → für Anlage NICHT nutzbar; `saveNewPreset()`-POST bleibt der Weg).
- **Lücke:** Der heutige Create-Modus mountet `WeatherMetricsTab` GAR NICHT (Metrik-Grundauswahl fehlt im Anlegen; nur Hub hat sie seit C1). Die neue Seite schließt das (Tab „Wetter-Metriken" wie Hub/Trip).
- **C2-Stundenverlauf** ist KEIN Organism — Inline-Markup nur im Hub (`CompareTabs.svelte:1349-1373`), bewusst dupliziert aus `CompareInhaltSection` (Begründung `:704-706`: die Section fällt mit F2). Für die Anlege-Seite: kleine geteilte Komponente extrahieren (Hub + Anlege-Seite nutzen sie), sonst Dreifach-Kopie.
- **F2b-Löschliste (verifiziert):** `CompareEditor.svelte` (einziger Mount: `/compare/new`), mitlöschbar `compareEditorLogic.ts` + `steps/Step2Orte.svelte` (falls nicht wiederverwendet); **NICHT löschbar:** `compareWizardState.svelte.ts` (Hub instanziiert sie, `CompareTabs.svelte:319`) und `compareEditorSave.ts` (`compareHubWizardBridge.ts:18`).
- **E2E-Verträge auf /compare/new** (~15 Dateien): tragende Testid-Familien `compare-editor{,-name,-progress,-activate,-continue-*,-tab-*,-profile-*}`, `compare-step2-*`, `corridor-editor-vergleich`, `compare-step4-*`/`channel-tab-*` (Layout-Organism), `compare-step5-*`, `cm-mobile-*`/`top-app-bar-*`. Details im Agent-C-Befund; Datei-Liste: slice1/3/4, layout-tab-vergleich, sortable-list-shared, issue-951 AC-3, issue-1080, flow-navigation Create-ACs, fidelity-s8d, issue-682, issue-718 AC-2, versand-tab AC-6, mobile-vervollstaendigung, issue-609, issue-1093.

## Design-Entscheidungen für die Spec (mit Begründung)

1. **`CompareNewEditor` als struktureller Spiegel von `TripNewEditor`** (`frontend/src/lib/components/compare-new/` mit `compareNewLogic.ts` pur). Begründung zur Teilungs-Invariante: geteilt sind die Organismen + das Logik-Muster; die Anlege-Shell ist je Domäne eigen — exakt wie `TripNewEditor` selbst (Trip-Pendant vorhanden = dokumentierte Ausnahme). Eine generische Shell-Extraktion ist als späterer Refactor möglich (Radar), nicht Teil von F2a.
2. **Tab-Satz an Hub angleichen:** Vergleich (Name/Region/Profil) → Orte → **Wetter-Metriken (NEU im Anlegen, schließt die C1-Lücke)** → Wertebereiche → Layout (NUR C2-Stundenverlauf) → Alarme → Versand mit Aktivierungs-Banner. Freischalt-Kette wie heute (Name → ≥2 Orte → visited-Kaskade).
3. **Kein Attrappen-Transfer:** Der alte Wizard-Layout-Organism (channel-tabs, Top-N, SMS-Budget/DnD = `channel_layouts`, das der Compare-Renderpfad nie liest — #1301-Grundbefund) wird NICHT übernommen. Layout-Tab der Anlege-Seite = C2-Stundenverlauf, als kleine geteilte Komponente aus dem Hub extrahiert.
4. **Persistenz unverändert:** lokaler `CompareWizardState` + `saveNewPreset()`-POST + Redirect auf Hub. Kein Backend-Change.
5. **`Step2Orte` wird WIEDERVERWENDET** (nicht neu gebaut): Import in die neue Seite, ggf. Umzug aus `steps/` nach `compare/` in F2b. Erhält #1080/#301/#951-Verhalten und die `compare-step2-*`-E2E-Verträge unverändert.
6. **Testids:** `compare-editor-name/-activate/-continue-*/-profile-*`, `compare-step2-*`, `cm-mobile-*`/`top-app-bar-*` bleiben erhalten (E2E-Verträge); `compare-editor-tab-*` bleibt als Tab-Testid der Anlege-Seite. Wizard-Layout-Testids (`compare-step4-*`, `channel-tab-*` im Compare-Kontext, `layout-editor`) entfallen MIT den zugehörigen Attrappen-Tests (Umbau der betroffenen E2E-Blöcke gehört zu F2a, sonst rote Suite).

## Risks & Considerations
- **E2E-Umbau ist Teil von F2a** (nicht F2b): slice4/layout-tab-vergleich/sortable-list-shared (Compare-Teil) testen die entfallende Attrappe → Blöcke löschen bzw. auf C2-Stundenverlauf umschreiben; sortable-DnD-Abdeckung bleibt über den Trip-Kontext bestehen (SortableList ist geteilt). slice1/3, 1080, 951, 682, s8d, 718 AC-2, flow-navigation laufen gegen die neue Seite weiter (Testids erhalten).
- **LoC deutlich >250:** neue Shell (~600-900 Z.) + Logik + Tests + E2E-Umbau. Override mit Spec-Freigabe erfragen.
- Mobile-Parität ist Pflicht (Trip-Vorbild #661, CSS-only) — fidelity-s8d/682-Verträge zeigen die erwarteten `cm-mobile-*`/`top-app-bar-*`-Anker.
- `WeatherMetricsTab` im Anlege-Modus: Vorbild `createMode={true}`-Pfad des Trips; im vergleich-Zweig arbeitet der Tab ohnehin nur auf `wiz` — erwartbar geringes Risiko, aber Adversary-Punkt.
- Nach F2a MUSS `/compare/new` funktional identisch-oder-besser sein; Alt-Editor bleibt bis F2b unangetastet im Repo (Rollback-Punkt wie S3).

## Existing Specs
- `docs/specs/modules/issue_622_trip_new_progressive_editor.md` + `issue_661_trip_new_mobile.md` (Vorbild)
- `docs/specs/modules/epic_1273_s4c_e2e_migration.md` (E2E-Verträge), `docs/features/epic-1273-compare-one-surface.md` (S5-Plan, PO-Entscheid verankert)

---
entity_id: rework_1215_dead_code_scheibe2
type: module
created: 2026-07-11
updated: 2026-07-11
status: implemented
version: "1.1"
tags: [cleanup, dead-code, frontend, e2e]
---

<!-- Issue #1215 — Scheibe 2 von 3: Toten Code entfernen (Frontend: alter Trip-Wizard + NewLocationWizard); Issue #1201 (stale Wizard-E2E-Specs) im selben Zug -->

# Toten Code entfernen — Scheibe 2 (Frontend: alter Trip-Wizard + NewLocationWizard)

## Approval

- [ ] Approved

## Purpose

Toten Frontend-Code entfernen: der alte Trip-Wizard (`trip-wizard/`, abgelöst
durch den Tab-Editor #622) und `NewLocationWizard.svelte` (abgelöst durch
`LocationNewModal` #588) haben außer zwei kleinen, noch aktiv genutzten
Bausteinen keine Aufrufer mehr. Diese zwei Bausteine (`ChannelToggle.svelte`,
`wizardHelpers.ts`) ziehen vor der Löschung nach `$lib/components/shared/` um,
damit ihre aktiven Importer — 6 Dateien: `Step5Versand.svelte`, `AlertsTab.svelte`,
`CompareAlarmSection.svelte`) weiterhin funktionieren. Zugleich werden die 10
stale E2E-Specs des toten Wizards gelöscht (Issue #1201-Teilarbeit). Reine
Aufräumarbeit — kein Produktionsverhalten ändert sich. Scheibe 2 von 3
(Scheibe 1 = Python/Root, abgeschlossen; Scheibe 3 = Go `internal/compare/` +
`PresetHeader.svelte` + `compare-main-stage.spec.ts`, eigener späterer
Workflow).

## Source

- **File:** `frontend/src/lib/components/trip-wizard/` — kompletter Ordner
  (5.294 LoC: Shell, Stepper, wizardState, stepperState, stepperCompact, 12
  steps/-Komponenten, `templates/TemplatePicker.svelte`, 16
  `__tests__/`-Dateien) — **Frontend**, wird gelöscht bis auf die 2
  Umzugsdateien
- **File:** `frontend/src/lib/components/compare/NewLocationWizard.svelte`
  (292 LoC) — **Frontend**, wird gelöscht
- **File:** `frontend/src/lib/components/organisms/index.ts` — Zeile 16
  (`TripWizardShell`-Re-Export) + Kommentar-Erwähnung Zeile 4 — **Frontend**,
  wird entfernt
- **File:** `frontend/e2e/*.spec.ts` — 10 stale Wizard-Specs — **Frontend
  (E2E)**, werden gelöscht

## Estimated Scope

- **LoC:** ca. -5.470 netto (Löschung ~5.294 LoC `trip-wizard/` + 292 LoC
  `NewLocationWizard.svelte` + 2 Zeilen `organisms/index.ts`, abzüglich 173 LoC
  Umzug nach `shared/` die als Verschiebung nicht netto zählen, plus
  Test-Kürzungen)
- **Files:** 2 Verschiebungen (+ 1 Testdatei-Verschiebung) nach `shared/`, 3
  Import-Pfad-Updates, 1 komplette Ordner-Löschung (`trip-wizard/`), 1
  Datei-Löschung (`NewLocationWizard.svelte`), 1 Datei-Edit
  (`organisms/index.ts`), 3 Test-Anpassungen (1 Löschung, 2 Kürzungen), 10
  E2E-Spec-Löschungen
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/src/lib/components/compare/steps/Step5Versand.svelte` (Zeilen 8/9) | Svelte-Komponente | Importiert `ChannelToggle` + `maskPhone` — Import-Pfad muss auf `$lib/components/shared/` aktualisiert werden |
| `frontend/src/lib/components/alerts-tab/AlertsTab.svelte` (Zeile 9) | Svelte-Komponente | Importiert `ChannelToggle` — Import-Pfad muss aktualisiert werden |
| `frontend/src/lib/components/compare/CompareAlarmSection.svelte` (Zeile 13) | Svelte-Komponente | Importiert `ChannelToggle` (seit #1041 Slice 2 live, Radar-Alarm-Toggle) — Import-Pfad muss aktualisiert werden, Radar-Toggle-UI darf nicht brechen |
| `frontend/src/lib/components/organisms/index.ts` | Barrel-Datei | Bleibt bestehen bis auf die eine `TripWizardShell`-Re-Export-Zeile (aktiv genutzt von `TripNewEditor`, `TripEditView`, `compare/Step4Layout` für die anderen Exporte) |
| `frontend/src/routes/trips/new/+page.svelte` | Route | Bleibt unverändert — nutzt bereits `TripNewEditor`, ist live, wird NICHT gelöscht |
| `frontend/src/lib/issue_518_suggested_cleanup.test.ts` | Test | Testet ausschließlich tote Wizard-Inhalte per `readFileSync` → wird komplett gelöscht |
| `frontend/src/lib/components/trip-detail/bug_499_skala_label.test.ts` | Test | `STEP3_WEATHER`-Konstante (Zeile 20) zeigt auf `trip-wizard/steps/Step3Weather.svelte` — nur diese Konstante + die 2 Tests, die sie lesen, werden entfernt; restliche Tests (`ActiveMetricRow`, `WeatherConfigDialog`, `SavePresetDialog`, `TablePreview`) bleiben unverändert |
| `frontend/src/lib/components/compare/issue_462.test.ts` | Test | `MIGRATED_FILES`-Liste (Zeile 34) enthält den `NewLocationWizard.svelte`-Eintrag → wird entfernt; der `PresetHeader.svelte`-Eintrag (Zeile 35) bleibt — stirbt erst in Scheibe 3 |
| `frontend/e2e/helpers.ts` | E2E-Helper | Bleibt unverändert — `fillStep*`/`seedTrip` werden noch von Specs lebender Features genutzt (`trip-edit.spec.ts`, `issue-264-stage-sort.spec.ts`, `alert-bundle-958ff.spec.ts`, `issue-993-alloff-subdued.spec.ts`); deren Modernisierung ist #1201-Restarbeit, nicht Teil dieser Scheibe |
| `frontend/src/lib/components/compare/PresetHeader.svelte`, `frontend/e2e/compare-main-stage.spec.ts` | Svelte-Komponente / E2E-Spec | Explizit **NICHT** Teil dieser Scheibe — Scheibe 3 (Go `internal/compare/`) |

## Implementation Details

### 1. Umzug (vor der Löschung) — `git mv` + Import-Pfad-Updates

Drei Dateien ziehen von `trip-wizard/` nach `$lib/components/shared/` (Ordner
existiert bereits, enthält `OutputLayoutEditor.svelte` + `__tests__/`):

```
trip-wizard/steps/ChannelToggle.svelte      → shared/ChannelToggle.svelte
trip-wizard/wizardHelpers.ts                → shared/wizardHelpers.ts
trip-wizard/__tests__/wizardHelpers.test.ts → shared/__tests__/wizardHelpers.test.ts
```

Import-Pfad-Updates (3 Stellen, je 2 Importzeilen für Step5Versand, je 1 für
die anderen beiden):

```
# Step5Versand.svelte (Zeile 8/9)
- import ChannelToggle from '$lib/components/trip-wizard/steps/ChannelToggle.svelte';
- import { maskPhone } from '$lib/components/trip-wizard/wizardHelpers';
+ import ChannelToggle from '$lib/components/shared/ChannelToggle.svelte';
+ import { maskPhone } from '$lib/components/shared/wizardHelpers';

# AlertsTab.svelte (Zeile 9)
- import ChannelToggle from '$lib/components/trip-wizard/steps/ChannelToggle.svelte';
+ import ChannelToggle from '$lib/components/shared/ChannelToggle.svelte';

# CompareAlarmSection.svelte (Zeile 13)
- import ChannelToggle from '$lib/components/trip-wizard/steps/ChannelToggle.svelte';
+ import ChannelToggle from '$lib/components/shared/ChannelToggle.svelte';
```

Interner relativer Import in `wizardHelpers.test.ts` (Bezug auf
`../wizardHelpers`) bleibt nach dem Umzug relativ korrekt, da beide Dateien
gemeinsam nach `shared/` bzw. `shared/__tests__/` ziehen.

### 2. Löschen per Commit

- `frontend/src/lib/components/trip-wizard/` komplett (nach Schritt 1 enthält
  der Ordner nur noch die nicht-umgezogenen Reste: Shell, Stepper,
  wizardState, stepperState, stepperCompact, restliche 11 steps/-Komponenten,
  `templates/TemplatePicker.svelte`, restliche 15 `__tests__/`-Dateien)
- `frontend/src/lib/components/compare/NewLocationWizard.svelte`
- `frontend/src/lib/components/organisms/index.ts`: Zeile 16
  (`export { default as TripWizardShell } from '../trip-wizard/TripWizardShell.svelte';`)
  + Kommentar-Erwähnung `TripWizardShell` in Zeile 4 entfernen; alle übrigen
  Zeilen bleiben unverändert
- 10 E2E-Specs in `frontend/e2e/`: `trip-wizard-shell.spec.ts`,
  `trip-wizard-step1.spec.ts`, `trip-wizard-step2.spec.ts`,
  `trip-wizard-step3.spec.ts`, `trip-wizard-step3-wetter.spec.ts`,
  `trip-wizard-step4.spec.ts`, `trip-wizard-step5-reports.spec.ts`,
  `trip-wizard-templates.spec.ts`, `trip-wizard-multi-gpx.spec.ts`,
  `bug-271-wizard-mobile-stepper.spec.ts`

### 3. Test-Anpassungen

- `frontend/src/lib/issue_518_suggested_cleanup.test.ts` komplett löschen
  (Test-Politik: veraltetes Verhalten → löschen statt liegenlassen; Test
  prüft ausschließlich tote Wizard-Dateiinhalte)
- `frontend/src/lib/components/trip-detail/bug_499_skala_label.test.ts`: nur
  die `STEP3_WEATHER`-Konstante (Zeile 20) und die 2 Tests, die sie lesen
  (`'AC-2 (#629): Step3Weather bietet kein scale/symbol-Label mehr'`,
  `'AC-2 (#629): Step3Weather bietet Roh/Einfach-Toggle'`), entfernen. Alle
  übrigen Tests (`ActiveMetricRow`, `WeatherConfigDialog`, `SavePresetDialog`,
  `TablePreview`) bleiben unverändert bestehen und grün.
- `frontend/src/lib/components/compare/issue_462.test.ts`: den
  `NewLocationWizard.svelte`-Eintrag aus `MIGRATED_FILES` (Zeile 34)
  entfernen. Der `PresetHeader.svelte`-Eintrag (Zeile 35) bleibt unverändert
  — er stirbt erst in Scheibe 3.

### 4. Invarianten (nichts tun, nur nachweisen)

- `frontend/src/routes/trips/new/+page.svelte` bleibt unverändert — nutzt
  bereits `TripNewEditor`, ist live geschaltet
- `frontend/e2e/helpers.ts` bleibt unverändert
- `frontend/src/lib/components/organisms/index.ts` bleibt bis auf die eine
  entfernte Zeile vollständig erhalten (alle anderen Re-Exports aktiv genutzt)
- `frontend/src/lib/components/compare/PresetHeader.svelte` und
  `frontend/e2e/compare-main-stage.spec.ts` werden **nicht** angefasst
  (Scheibe 3)
- Kein Produktionsverhalten ändert sich — reine Löschung/Verschiebung toten
  bzw. umgezogenen Codes

## Expected Behavior

- **Input:** Bestehender Frontend-Quellbaum mit totem Wizard-Code in
  `trip-wizard/` und `NewLocationWizard.svelte`, sowie 3 aktive Importer, die
  auf die 2 Umzugsdateien zeigen
- **Output:** `trip-wizard/` existiert nicht mehr, `NewLocationWizard.svelte`
  existiert nicht mehr, `ChannelToggle.svelte` + `wizardHelpers.ts` (+ Test)
  liegen unter `$lib/components/shared/`, alle 6 Importer zeigen auf den
  neuen Pfad und funktionieren unverändert, `organisms/index.ts` ohne
  `TripWizardShell`-Re-Export, 10 stale E2E-Specs gelöscht
- **Side effects:** Kein Import von `$lib/components/trip-wizard/*` oder
  `$lib/components/compare/NewLocationWizard.svelte` ist mehr möglich
  (führt zu Build-Fehler/`ImportError`, was erwünscht ist, da keine echten
  Aufrufer mehr existieren). Frontend-Build (`npm run build`) und
  vitest-Suite (`npm run test`) bleiben grün. UI-Verhalten von Compare-Wizard
  Step 5 (Kanal-Auswahl), AlertsTab (Kanal-Auswahl) und CompareAlarmSection
  (Radar-Alarm-Toggle, #1041) ändert sich nicht sichtbar.

## Acceptance Criteria

- **AC-1:** Given `ChannelToggle.svelte` und `wizardHelpers.ts` (inkl. Test)
  liegen nach `git mv` unter `$lib/components/shared/` / When `Step5Versand.svelte`,
  `AlertsTab.svelte` und `CompareAlarmSection.svelte` mit den aktualisierten
  Import-Pfaden gebaut werden / Then läuft `npm run build` im
  `frontend/`-Verzeichnis ohne Fehler durch, und `npm run test` findet die
  verschobene Testdatei unter `shared/__tests__/wizardHelpers.test.ts` grün
  - Test: `npm run build` Exit 0; `npm run test -- wizardHelpers` Exit 0

- **AC-2:** Given `frontend/src/lib/components/trip-wizard/` ist komplett
  gelöscht (nach dem Umzug der 3 Dateien aus Schritt 1) / When im
  Dateisystem nach dem Ordner gesucht wird / Then existiert
  `frontend/src/lib/components/trip-wizard/` nicht mehr, und kein Import
  irgendeiner Datei im Repo referenziert mehr `$lib/components/trip-wizard/*`
  oder einen relativen Pfad auf den Ordner
  - Test: `test -d frontend/src/lib/components/trip-wizard` schlägt fehl;
    `grep -r "trip-wizard" frontend/src --include=*.svelte --include=*.ts` liefert
    keinen Treffer außerhalb bereits gelöschter/verschobener Dateien

- **AC-3:** Given `frontend/src/lib/components/compare/NewLocationWizard.svelte`
  ist gelöscht / When der Frontend-Build läuft / Then existiert die Datei
  nicht mehr im Dateisystem, `npm run build` bleibt grün, und kein Code
  (außer Kommentaren/Tests, die bereits in dieser Scheibe angepasst wurden)
  referenziert die Komponente mehr
  - Test: `test -f frontend/src/lib/components/compare/NewLocationWizard.svelte`
    schlägt fehl; `npm run build` Exit 0

- **AC-4:** Given `organisms/index.ts` Zeile 16 (`TripWizardShell`-Re-Export)
  und die Kommentar-Erwähnung in Zeile 4 sind entfernt / When die übrigen
  Re-Exports (`TripHeader`, `AlertRulesEditor`, `OutputLayoutEditor`,
  `WeatherMetricsTab`, `ChannelPreviewBlock`, `ChannelPreviewCard`,
  `MetricGroup`, `MetricCheckbox`, `HomeHeroTrip`, `HomeHeroCompare`,
  `OutboxCard`, `AlertsCard`, `PresetRail`, `MetricOffShelf`,
  `MetricsEditorContextBar`) importiert werden / Then bleiben alle
  Importer (`TripNewEditor`, `TripEditView`, `compare/Step4Layout`) unverändert
  funktionsfähig, und `npm run build` bleibt grün
  - Test: `grep -n "TripWizardShell" frontend/src/lib/components/organisms/index.ts`
    liefert keinen Treffer; `npm run build` Exit 0

- **AC-5:** Given die 10 stale Wizard-E2E-Specs (`trip-wizard-shell.spec.ts`,
  `trip-wizard-step1.spec.ts` bis `-step5-reports.spec.ts`, `-templates.spec.ts`,
  `trip-wizard-multi-gpx.spec.ts`, `bug-271-wizard-mobile-stepper.spec.ts`) sind
  gelöscht / When `frontend/e2e/helpers.ts` unverändert bleibt und die übrigen
  E2E-Specs (`trip-edit.spec.ts`, `issue-264-stage-sort.spec.ts`,
  `alert-bundle-958ff.spec.ts`, `issue-993-alloff-subdued.spec.ts`) betrachtet
  werden / Then existieren die 10 gelöschten Dateien nicht mehr im
  Dateisystem, und `helpers.ts` ist byteidentisch mit dem Stand vor dieser
  Scheibe
  - Test: `ls frontend/e2e/trip-wizard-*.spec.ts frontend/e2e/bug-271-wizard-mobile-stepper.spec.ts`
    liefert für alle 10 Dateien "No such file"; `git diff` zeigt keine
    Änderung an `frontend/e2e/helpers.ts`

- **AC-6:** Given `frontend/src/lib/issue_518_suggested_cleanup.test.ts` ist
  gelöscht / When die vitest-Suite ausgeführt wird / Then existiert die Datei
  nicht mehr, und die Gesamtzahl ausgeführter Tests sinkt entsprechend, ohne
  dass ein anderer Test rot wird
  - Test: `test -f frontend/src/lib/issue_518_suggested_cleanup.test.ts` schlägt
    fehl; `npm run test` Exit 0

- **AC-7:** Given in `bug_499_skala_label.test.ts` sind nur die
  `STEP3_WEATHER`-Konstante und die 2 zugehörigen Step3Weather-Tests entfernt
  / When die Datei mit vitest/node --test ausgeführt wird / Then laufen alle
  verbleibenden Tests (`ActiveMetricRow`, `WeatherConfigDialog`,
  `SavePresetDialog`, `TablePreview`) unverändert grün, und kein Verweis auf
  `STEP3_WEATHER` oder `trip-wizard` bleibt in der Datei
  - Test: `grep -n "STEP3_WEATHER\|trip-wizard" frontend/src/lib/components/trip-detail/bug_499_skala_label.test.ts`
    liefert keinen Treffer; verbleibende Tests in der Datei laufen grün

- **AC-8:** Given in `compare/issue_462.test.ts` ist der
  `NewLocationWizard.svelte`-Eintrag aus `MIGRATED_FILES` entfernt, der
  `PresetHeader.svelte`-Eintrag bleibt / When der Test ausgeführt wird / Then
  läuft er grün, ohne dass `NewLocationWizard.svelte` als Datei existieren
  muss, und die `PresetHeader.svelte`-Prüfung bleibt unverändert aktiv
  - Test: `grep -n "NewLocationWizard" frontend/src/lib/components/compare/issue_462.test.ts`
    liefert keinen Treffer; `grep -n "PresetHeader" frontend/src/lib/components/compare/issue_462.test.ts`
    liefert weiterhin einen Treffer; Test läuft grün

- **AC-9:** Given diese Scheibe ist auf Staging deployt / When ein Nutzer im
  Compare-Wizard bis Step 5 (Versand) navigiert und dort den Kanal-Toggle
  bedient, sowie im Alarme-Tab eines Compare-Trips (#1041 Radar-Alarm-Toggle,
  seit gestern live) den Radar-Alarm-Schalter bedient / Then ist der
  Kanal-Toggle in Step 5 sichtbar und bedienbar (E-Mail/Telegram/SMS
  auswählbar wie vor dieser Scheibe), und der Radar-Alarm-Toggle in
  `CompareAlarmSection` funktioniert unverändert (kein Rendering-Fehler, kein
  gebrochener Import in der Browser-Konsole)
  - Test: Staging-Klick-Test (Playwright oder manuell) durch Compare-Wizard
    Step 5 + Compare-Alarme-Tab; Browser-Konsole ohne Import-/Modul-Fehler

- **AC-10:** Given `frontend/src/routes/trips/new/+page.svelte` nutzt bereits
  `TripNewEditor` und wird von dieser Scheibe nicht angefasst / When die Route
  `/trips/new` nach dem Deploy aufgerufen wird / Then funktioniert die
  Trip-Erstellung unverändert wie vor dieser Scheibe (kein Regressionsrisiko
  durch die Wizard-Löschung, da die Route bereits vollständig auf den
  Tab-Editor migriert war)
  - Test: `git diff` zeigt keine Änderung an `frontend/src/routes/trips/new/+page.svelte`;
    manueller/Playwright-Klicktest `/trips/new` erfolgreich

## Known Limitations

- Scheibe 3 (Go `internal/compare/` + `PresetHeader.svelte` +
  `compare-main-stage.spec.ts`) ist explizit außerhalb dieser Scheibe und
  benötigt einen eigenen späteren Workflow.
- Die Modernisierung von `trip-edit.spec.ts`, `waypoints-editor.spec.ts` und
  `issue-494-trip-edit-design.spec.ts` auf neue Testids (weitere
  #1201-Restarbeit) ist nicht Teil dieser Scheibe — `helpers.ts` bleibt daher
  unverändert bestehen, obwohl es historisch aus dem Wizard-Kontext stammt.
- Der Umzug nach `$lib/components/shared/` ist eine reine Pfad-Verschiebung;
  keine funktionale Änderung an `ChannelToggle.svelte` oder `wizardHelpers.ts`
  selbst ist Teil dieser Scheibe.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine Löschung/Verschiebung von totem bzw. bereits
  vollständig abgelöstem Frontend-Code ohne Änderung an Architektur,
  Datenmodell oder Produktionsverhalten — kein ADR-würdiger
  Entscheidungsraum.

## Changelog

- 2026-07-11: Initial spec erstellt — Issue #1215, Scheibe 2 (+ Issue #1201
  E2E-Anteil)
- 2026-07-11: v1.1 — Umsetzungs-Befund: `wizardHelpers` hatte 3 weitere
  lebende Importer (`trip-detail/waypoints/StageCard.svelte`,
  `trip-detail/waypoints/EtappenStrip.svelte`, `trip-detail/WaypointsPanel.svelte`
  — `isPauseStage`/`formatStageNumber`), die dem Umzug nach `shared/` folgen
  mussten, sonst wäre der Build gebrochen. Insgesamt 6 Importer-Dateien
  aktualisiert statt 3. Keine funktionale Änderung, reine Pfad-Folge.

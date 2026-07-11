# Context: rework-1215-scheibe2-frontend

## Request Summary

Issue #1215, Scheibe 2 (von 3): Toten Frontend-Code entfernen — alter Trip-Wizard
(`trip-wizard/`, abgelöst durch Tab-Editor #622) und `NewLocationWizard.svelte`
(abgelöst durch LocationNewModal #588). Vorher zwei noch aktiv genutzte Kleinteile
nach `shared/` umziehen. Verwandt: #1201 (stale Wizard-E2E-Specs) im selben Zug.

## Verifizierte Befunde (eigene Nachprüfung 2026-07-11, Worktree auf origin/main 44bff135)

### Umfang trip-wizard/ — GRÖSSER als Issue-Angabe

`frontend/src/lib/components/trip-wizard/` = **5.294 LoC** (Issue sagte ~1.900):
Shell, Stepper, wizardState, stepperState, stepperCompact, 12 steps/-Komponenten,
templates/TemplatePicker.svelte, 16 `__tests__/`-Dateien.

### Aktiv genutzte Teile (MÜSSEN vor Löschung umziehen → `$lib/components/shared/`)

| Datei | LoC | Aktive Importer |
|---|---|---|
| `trip-wizard/steps/ChannelToggle.svelte` | 51 | `compare/steps/Step5Versand.svelte:8`, `alerts-tab/AlertsTab.svelte:9`, `compare/CompareAlarmSection.svelte:13` (NEU seit Audit, aus #1041 Slice 2!) |
| `trip-wizard/wizardHelpers.ts` (`maskPhone`) | 122 | `compare/steps/Step5Versand.svelte:9` |
| `trip-wizard/__tests__/wizardHelpers.test.ts` | — | Test zum Umzugsgut — mit umziehen |

### Löschbar (verifiziert Aufrufer-frei)

- `trip-wizard/` komplett (nach Umzug der 3 o.g. Dateien) — einziger Code-Importer
  von außen ist der Re-Export `organisms/index.ts:16` (`TripWizardShell`), der
  selbst **null Nutzer** hat (alle organisms-Importer holen nur `AlertRulesEditor`/
  `OutputLayoutEditor`). Re-Export-Zeile 16 + Kommentar-Erwähnung Zeile 4 entfernen;
  organisms/index.ts bleibt sonst (aktiv genutzt von TripNewEditor, TripEditView,
  compare/Step4Layout).
- `compare/NewLocationWizard.svelte` (292 LoC) — 0 Importer (nur Kommentare/Tests)
- `routes/trips/new/+page.svelte` ist bereits sauber (nutzt TripNewEditor, nur
  Deprecation-Kommentar) — NICHT löschen, Route ist live.

### Datei-Inhalt-Tests außerhalb, die auf Löschgut zeigen (brechen sonst)

- `frontend/src/lib/issue_518_suggested_cleanup.test.ts` — liest trip-wizard-Dateien
  per readFileSync, testet ausschließlich tote Wizard-Inhalte → **löschen**
  (Test-Politik: veraltetes Verhalten → löschen)
- `frontend/src/lib/components/trip-detail/bug_499_skala_label.test.ts:19` — Konstante
  `STEP3_WEATHER` zeigt auf trip-wizard/steps/Step3Weather.svelte; nur die Tests,
  die STEP3_WEATHER lesen, entfernen — Rest (ActiveMetricRow etc.) bleibt
- `frontend/src/lib/components/compare/issue_462.test.ts:34` — MIGRATED_FILES-Liste
  enthält `NewLocationWizard.svelte` → Eintrag entfernen (PresetHeader.svelte:35
  bleibt drin — stirbt erst in Scheibe 3!)
- `routes/locations/__tests__/issue_408_location_wizard.test.ts` — nur Kommentare, OK

### E2E-Specs (#1201, stale seit #622)

Löschen (10 Specs des toten Wizards): `trip-wizard-shell.spec.ts`,
`trip-wizard-step1.spec.ts`, `-step2`, `-step3`, `-step3-wetter`, `-step4`,
`-step5-reports`, `-templates`, `trip-wizard-multi-gpx.spec.ts`,
`bug-271-wizard-mobile-stepper.spec.ts`.
`e2e/helpers.ts`: **bleibt** — fillStep*/seedTrip werden noch von Specs lebender
Features genutzt (`trip-edit.spec.ts`, `issue-264-stage-sort.spec.ts`,
`alert-bundle-958ff.spec.ts`, `issue-993-alloff-subdued.spec.ts`); deren
Modernisierung auf neue Testids ist #1201-Restarbeit, NICHT diese Scheibe.
**NICHT in dieser Scheibe:** `trip-edit.spec.ts`-Neuschrieb,
`waypoints-editor.spec.ts` (separater #1201-Fund), `issue-494-trip-edit-design.spec.ts`.
`$lib/components/shared/` existiert bereits (OutputLayoutEditor + __tests__).

## Existing Patterns

- `$lib/components/shared/` — prüfen ob existiert, sonst anlegen (alternativ
  molecules/? — shared/ laut Issue-Vorgabe)
- Frontend-Tests: vitest (`npm run test` in frontend/), Build `npm run build`

## Dependencies

- Upstream: keine — Löschgut hat außer den 2 Umzugsdateien null Aufrufer
- Downstream: 3 Importer-Dateien bekommen neue Import-Pfade (`$lib/components/shared/`)

## Risks & Considerations

1. **CompareAlarmSection.svelte** (Radar-Alarm-Toggle, seit gestern live #1041) importiert
   ChannelToggle — Import-Pfad-Update darf Radar-Toggle-UI nicht brechen (Staging-Klick-Test!)
2. Frontend-Build (Vite/Svelte) muss grün sein — toter Import bricht Build hart
3. E2E-Löschungen: nur Specs des toten Wizards; helpers.ts-Nutzung vorher kartieren
4. LoC-Delta: Umzug 173 LoC + Testanpassungen; Löschung ~5.600 LoC (zählt negativ)
5. Scheibe 3 (Go internal/compare/ + PresetHeader.svelte + compare-main-stage.spec.ts)
   bleibt außen vor

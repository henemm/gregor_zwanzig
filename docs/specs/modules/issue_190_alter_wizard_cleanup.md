---
entity_id: issue_190_alter_wizard_cleanup
type: module
created: 2026-05-15
updated: 2026-05-15
status: draft
version: "1.0"
title: Cleanup alter Wizard-Code nach Epic #136
issue: 190
related: [224, 136, 217, 102]
tags: [cleanup, frontend, refactor, edit, issue-190]
---

<!-- Issue #190 — Cleanup alter Wizard-Code nach Epic #136 -->

# Issue 190 — Cleanup alter Wizard-Code nach Epic #136

## Approval

- [ ] Approved

## Purpose

Nach Abschluss von Epic #136 (neuer Trip-Wizard unter `lib/components/trip-wizard/`)
existiert unter `frontend/src/lib/components/wizard/` veralteter Code: zwei tote
Komponenten ohne Importer und vier aktive Edit-Komponenten mit historisch irrefuehrendem
Wizard-Prefix. Dieser Workflow raumt das Verzeichnis auf — 2 tote Files loeschen,
4 aktive Files in `lib/components/edit/` verschieben und umbenennen,
1 bereits-gedisablten E2E-Test loeschen, 1 leeres Verzeichnis entfernen — ohne
dabei Logik, Datenmodell oder Schnittstellen zu aendern.

## Source

- **MODIFY:** `frontend/src/lib/components/edit/TripEditView.svelte` — Import-Zeilen 6–9
  von `$lib/components/wizard/WizardStep{1,2,3,4}*.svelte` auf
  `./Edit{Route,Stages,Weather,ReportConfig}Section.svelte` umschreiben;
  JSX-Komponentennamen entsprechend anpassen.
- **DELETE:** `frontend/src/lib/components/wizard/TripWizard.svelte`
- **DELETE:** `frontend/src/lib/components/wizard/WizardStepper.svelte`
- **DELETE:** `frontend/e2e/trip-wizard.spec.ts`
- **MOVE+RENAME:**
  - `frontend/src/lib/components/wizard/WizardStep1Route.svelte`
    → `frontend/src/lib/components/edit/EditRouteSection.svelte`
  - `frontend/src/lib/components/wizard/WizardStep2Stages.svelte`
    → `frontend/src/lib/components/edit/EditStagesSection.svelte`
  - `frontend/src/lib/components/wizard/WizardStep3Weather.svelte`
    → `frontend/src/lib/components/edit/EditWeatherSection.svelte`
  - `frontend/src/lib/components/wizard/WizardStep4ReportConfig.svelte`
    → `frontend/src/lib/components/edit/EditReportConfigSection.svelte`
- **DELETE (Verzeichnis):** `frontend/src/lib/components/wizard/`

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `TripEditView.svelte` | Svelte-Komponente | Einziger Konsument der 4 aktiven alten Step-Komponenten; nach Umbau importiert er die neuen Pfade |
| `EditRouteSection.svelte` (neu) | Svelte-Komponente | Inhalt von `WizardStep1Route.svelte`; rendert Route-Eingabe im Edit-Pfad |
| `EditStagesSection.svelte` (neu) | Svelte-Komponente | Inhalt von `WizardStep2Stages.svelte`; Etappen-Reorder (AC fuer Issue #128) |
| `EditWeatherSection.svelte` (neu) | Svelte-Komponente | Inhalt von `WizardStep3Weather.svelte`; Wettereinstellungen im Edit-Pfad |
| `EditReportConfigSection.svelte` (neu) | Svelte-Komponente | Inhalt von `WizardStep4ReportConfig.svelte`; Report-Konfiguration im Edit-Pfad |
| `$lib/types.js` (`Stage`, `Trip`, `AlertRule`) | TS-Type | Verwendet in den verschobenen Komponenten; unveraendert |
| `frontend/src/routes/trips/[id]/edit/+page.svelte` | SvelteKit-Route | Laedt `TripEditView`; nicht direkt veraendert, aber vom Edit-Pfad-Test erfasst |
| `svelte-check` | Build-Tool | Validiert TypeScript-/Svelte-Fehler nach Umbau |

## Implementation Details

### 1. Tote Dateien loeschen

```
rm frontend/src/lib/components/wizard/TripWizard.svelte
rm frontend/src/lib/components/wizard/WizardStepper.svelte
rm frontend/e2e/trip-wizard.spec.ts
```

`TripWizard.svelte` hat keinen Importer im Repo (Phase-2-Grep: 0 Treffer).
`WizardStepper.svelte` wird ausschliesslich von `TripWizard.svelte` importiert —
faellt mit ihm weg.
`trip-wizard.spec.ts` ist bereits vollstaendig mit `.skip` markiert; ein Kommentar
darin verweist explizit auf diesen Cleanup.

### 2. Vier Komponenten verschieben + umbenennen

```
mv frontend/src/lib/components/wizard/WizardStep1Route.svelte \
   frontend/src/lib/components/edit/EditRouteSection.svelte

mv frontend/src/lib/components/wizard/WizardStep2Stages.svelte \
   frontend/src/lib/components/edit/EditStagesSection.svelte

mv frontend/src/lib/components/wizard/WizardStep3Weather.svelte \
   frontend/src/lib/components/edit/EditWeatherSection.svelte

mv frontend/src/lib/components/wizard/WizardStep4ReportConfig.svelte \
   frontend/src/lib/components/edit/EditReportConfigSection.svelte
```

Kein Logik-Eingriff — die Dateien werden 1:1 verschoben. Interner Inhalt (Props,
`$bindable()`-Deklarationen, Event-Handler) bleibt unveraendert.

### 3. Import-Pfade in `TripEditView.svelte` anpassen

```svelte
// VORHER (Zeilen 6-9):
import WizardStep1Route from '$lib/components/wizard/WizardStep1Route.svelte';
import WizardStep2Stages from '$lib/components/wizard/WizardStep2Stages.svelte';
import WizardStep3Weather from '$lib/components/wizard/WizardStep3Weather.svelte';
import WizardStep4ReportConfig from '$lib/components/wizard/WizardStep4ReportConfig.svelte';

// NACHHER:
import EditRouteSection from './EditRouteSection.svelte';
import EditStagesSection from './EditStagesSection.svelte';
import EditWeatherSection from './EditWeatherSection.svelte';
import EditReportConfigSection from './EditReportConfigSection.svelte';
```

Alle JSX-Stellen in `TripEditView.svelte`, die `<WizardStep1Route .../>`,
`<WizardStep2Stages .../>`, `<WizardStep3Weather .../>` oder
`<WizardStep4ReportConfig .../>` verwenden, werden auf die neuen Komponentennamen
(`<EditRouteSection .../>` usw.) umgeschrieben. Props und Bindings bleiben
unveraendert.

### 4. Leeres Verzeichnis entfernen

```
rmdir frontend/src/lib/components/wizard/
```

Nach Schritt 1 und 2 ist das Verzeichnis leer. `rmdir` schlaegt fehl falls noch
Dateien vorhanden sind — das ist beabsichtigt als Sicherheitsnetz.

### 5. Verifikation

```bash
# Kein verbleibender Import auf alten Pfad
grep -r "components/wizard" frontend/src/

# svelte-check ohne neue Fehler
cd frontend && npx svelte-check --tsconfig ./tsconfig.json 2>&1 | grep -i error

# Frontend-Build
cd frontend && npm run build
```

## Expected Behavior

- **Input:** Codebase mit `frontend/src/lib/components/wizard/` (6 Dateien) und
  `frontend/e2e/trip-wizard.spec.ts`.
- **Output:** Verzeichnis `wizard/` existiert nicht mehr; 4 neue Dateien unter
  `frontend/src/lib/components/edit/Edit*Section.svelte` mit identischem Inhalt;
  `TripEditView.svelte` importiert die neuen Pfade.
- **Side effects:** Keine Verhaltensaenderung im Browser sichtbar. Der
  Trip-Edit-Pfad (`/trips/[id]/edit`) laeuft funktional identisch weiter.
  `svelte-check` und `npm run build` laufen fehlerfrei. Die E2E-Tests
  `trip-edit.spec.ts` und `trip-wizard-multi-gpx.spec.ts` bleiben im Zustand
  vor diesem Cleanup (vorbestehend kaputt gemaess Issue #217 — out of scope).

## Acceptance Criteria

- **AC-1:** Given der Cleanup-Workflow ist abgeschlossen
  When `ls frontend/src/lib/components/wizard/` ausgefuehrt wird
  Then existiert das Verzeichnis nicht mehr (Exit-Code != 0 oder "No such file").

- **AC-2:** Given der Cleanup-Workflow ist abgeschlossen
  When die vier Pfade `frontend/src/lib/components/edit/EditRouteSection.svelte`,
  `frontend/src/lib/components/edit/EditStagesSection.svelte`,
  `frontend/src/lib/components/edit/EditWeatherSection.svelte` und
  `frontend/src/lib/components/edit/EditReportConfigSection.svelte` geprueft werden
  Then existieren alle vier Dateien und ihr Inhalt (Props, Logik, Bindings) ist
  identisch mit den jeweiligen alten `WizardStep*.svelte`-Quellen.

- **AC-3:** Given der Cleanup-Workflow ist abgeschlossen
  When `grep -r "components/wizard" frontend/src/` ausgefuehrt wird
  Then liefert der Befehl keinen Treffer — kein Import auf `$lib/components/wizard/...`
  existiert mehr im Quellcode.

- **AC-4:** Given der Cleanup-Workflow ist abgeschlossen
  When `ls frontend/e2e/trip-wizard.spec.ts` ausgefuehrt wird
  Then existiert die Datei nicht mehr (Exit-Code != 0).

- **AC-5:** Given der Cleanup-Workflow ist abgeschlossen
  When `cd frontend && npx svelte-check --tsconfig ./tsconfig.json` ausgefuehrt wird
  Then enthaelt die Ausgabe keine neuen Errors, die durch den Umbau verursacht
  wurden (vorbestehende Warnings aus anderen Dateien bleiben unberuehrt).

- **AC-6:** Given ein bestehender Trip ist in der Datenbank gespeichert
  When der User die URL `/trips/[id]/edit` im Browser aufruft
  Then laden alle vier Accordion-Sektionen (Route, Etappen, Wetter, Report-Konfiguration)
  sichtbar und interagierbar, und die Daten des Trips (Name, Etappen, Wetterkonfiguration,
  Report-Config) werden vollstaendig ohne Verlust angezeigt.

- **AC-7:** Given der Cleanup-Workflow ist abgeschlossen
  When `cd frontend && npm run build` ausgefuehrt wird
  Then laeuft der Build fehlerfrei durch (Exit-Code 0).

- **AC-8:** Given der Cleanup-Workflow ist abgeschlossen
  When `grep -r "WizardStep" frontend/src/` ausgefuehrt wird
  Then liefert der Befehl keinen Treffer — kein Verweis auf die alten Komponentennamen
  in `TripEditView.svelte` oder anderen Quelldateien.

## Out of Scope

- **Mode-Prop-Bereinigung:** Die vier verschobenen Komponenten deklarieren alle
  `mode?: 'create'|'edit'`, aber pruefen den Wert nirgends per `if (mode === ...)`.
  Das Entfernen dieses toten Props ist ein separates Refactoring-Ticket und wird
  hier nicht angefasst.
- **Edit-Pfad zu neuem Wizard-Modell konsolidieren:** Den Edit-Pfad vollstaendig
  auf `trip-wizard/` mit `mode: 'edit'` umzustellen ist ein eigenes Epic — riskant
  wegen Datenverlust-Sensitivitaet (BUG-DATALOSS-GR221, Issue #102).
- **`trip-edit.spec.ts` und `trip-wizard-multi-gpx.spec.ts` reparieren:** Diese
  E2E-Tests sind laut Issue #217 vorbestehend kaputt (alte TestIDs `wizard-next`,
  `trip-name-input`, `bulk-stage-*`). Reparatur gehoert in Issue #217.
- **Backend-Aenderungen:** Kein Schema, keine Go-/Python-Datei wird beruehrt.

## Risiken

- **svelte-check als Sicherheitsnetz:** Falsch gesetzte Import-Pfade werden von
  `svelte-check` sofort als Fehler gemeldet — kein stiller Bruch moeglich.
- **BUG-DATALOSS-GR221 (Issue #102) nicht betroffen:** Es werden ausschliesslich
  UI-Komponenten verschoben, keine Schema-Dateien (`models.py`, `trip.py`,
  `loader.py`, `store.go`). Der `data_schema_backup.py`-Hook reagiert nicht.
- **Mode-Prop ist toter Code:** Kein Risiko fuer den Cleanup — der Prop wird
  weiterhin deklariert und uebergeben, nur nicht ausgewertet. Kein Verhalten
  aendert sich.
- **Vorbestehend kaputte E2E-Tests:** `trip-edit.spec.ts` und
  `trip-wizard-multi-gpx.spec.ts` schlagen vor und nach diesem Cleanup fehl
  (Issue #217). Keine Regression durch diesen Workflow.

## Known Limitations

- Nach dem Verschieben koennen IDE-Breakpoints und -Sprungziele auf die alten
  Pfade zeigen — einmaliges IDE-Reload behebt das.
- `git log --follow` muss mit dem neuen Pfad ausgefuehrt werden, um die History
  der verschobenen Dateien zu sehen.

## Changelog

- 2026-05-15: Initial spec fuer Issue #190 (Cleanup alter Wizard-Code nach Epic #136).
  Strategie aus Phase-2-Kontextdokument uebernommen: kleine Schneise — 2 tote Files
  loeschen, 4 aktive Files nach `components/edit/` verschieben+umbenennen, 1
  `.skip`-E2E loeschen, leeres Verzeichnis entfernen. 8 Acceptance Criteria (AC-N-Format),
  Out-of-Scope explizit (Mode-Prop, Edit→Wizard-Konsolidierung, Issue-#217-Tests),
  Risiken dokumentiert (BUG-DATALOSS-GR221 nicht betroffen).

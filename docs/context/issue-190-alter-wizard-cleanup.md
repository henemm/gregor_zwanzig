# Context: Issue #190 — Cleanup alter Wizard-Code nach Epic #136

## Request Summary

Den alten `frontend/src/lib/components/wizard/`-Ordner aufräumen. Voraussetzung
(„alle Sub-Issues von Epic #136 abgeschlossen") ist erfüllt — der neue Trip-Wizard
unter `frontend/src/lib/components/trip-wizard/` ist seit Epic #136 produktiv,
zuletzt durch Issue #224 erweitert.

## Aktueller Stand der alten Wizard-Familie

`frontend/src/lib/components/wizard/`:

| Datei | Heutige Verwendung |
|---|---|
| `TripWizard.svelte` | **tot** — kein Importer im Repo |
| `WizardStepper.svelte` | **tot** — nur von `TripWizard.svelte` importiert |
| `WizardStep1Route.svelte` | Aktiv im `TripEditView.svelte:6` |
| `WizardStep2Stages.svelte` | Aktiv im `TripEditView.svelte:7` (Etappen-Reorder, AC für #128) |
| `WizardStep3Weather.svelte` | Aktiv im `TripEditView.svelte:8` |
| `WizardStep4ReportConfig.svelte` | Aktiv im `TripEditView.svelte:9` |

**Wichtig:** Die 4 „aktiven" Komponenten sind faktisch _Edit-Komponenten_ — sie
nutzen einfache `bind:`-Props (`stages`, `displayConfig`, `reportConfig`, plus
optional `mode: 'edit'|'create'`), keinen `WizardState`-Context. Sie heißen nur
historisch „Wizard*", weil sie ursprünglich für den alten Wizard gebaut wurden.
Der echte Wizard sitzt heute komplett in `lib/components/trip-wizard/` mit
eigenen Steps (`Step1Profile`, `Step2Stages`, `Step3Waypoints`, `Step4Briefings`).

## Related Files

| File | Relevanz |
|---|---|
| `frontend/src/lib/components/wizard/*.svelte` | Cleanup-Ziel |
| `frontend/src/lib/components/edit/TripEditView.svelte` | Einziger Konsument der 4 aktiven alten Step-Komponenten |
| `frontend/src/routes/trips/[id]/edit/+page.svelte` | Lädt `TripEditView` |
| `frontend/e2e/trip-wizard.spec.ts` | Bereits `.skip` (Kommentar verweist auf diesen Cleanup) — löschbar |
| `frontend/e2e/trip-edit.spec.ts` | Nutzt alte TestIDs (`wizard-next`, `trip-name-input`); per Issue #217 vorbestehend kaputt |
| `frontend/e2e/trip-wizard-multi-gpx.spec.ts` | Nutzt alte TestIDs (`trip-name-input`, `bulk-stage-*`) — Issue #127-Tests, vorbestehend kaputt |
| `frontend/e2e/trip-wizard-step{1,2,3,4}.spec.ts` | Sind NEUE Wizard-Tests (TestIDs `trip-wizard-step1-*` etc.), trotz Pfadnamen mit alten Strings im grep — bleiben unangetastet |
| `docs/specs/modules/epic_136_trip_wizard.md` | Master-Spec, „Not In Scope"-Sektion verweist auf diesen Cleanup |

## Existing Patterns

- Issue #224 hat gezeigt, dass **Komponenten-Konsolidierung** der saubere Weg ist: eine Komponente (`AlertRulesEditor`) für Wizard und Edit. Dieses Pattern auf die 4 aktiven Step-Komponenten zu übertragen ist die Ausbau-Vision des Issues („Option (a): Edit über denselben neuen Wizard mit `mode: 'edit'`").
- **Renaming + Verschieben** ist Risiko-arm — `mv` + Import-Pfade aktualisieren, kein Refactoring der Logik.

## Dependencies

- **Upstream:** SvelteKit, Svelte 5 `$bindable`-Pattern, `$lib/types.js` (`Stage`, `Trip`, `AlertRule`).
- **Downstream:**
  - `routes/trips/[id]/edit/+page.svelte` → `TripEditView` → 4 alte Step-Komponenten.
  - 3–4 E2E-Tests mit alten TestIDs (Issue #217 dokumentiert, dass sie ohnehin schon failt).

## Risks & Considerations

- **Datenverlust-Risiko bei Edit-Pfad-Umbau** (CLAUDE.md §Daten-Schema-Reworks, BUG-DATALOSS-GR221 / Issue #102): Wenn der Edit-Pfad refactored wird, müssen `display_config`, `aggregation`, `weather_config` etc. lückenlos durch das Read-Modify-Write-Pattern fließen. **Bei reinem File-Rename gibt es kein Datenverlust-Risiko** — Pfade ändern sich, Logik nicht.
- **Phase-2-Entscheidung:** Großer Umbau (Edit → neuer Wizard im `mode: 'edit'`) vs. kleine Schneise (2 tote Files löschen, 4 aktive Files umbenennen/verschieben). Memory-Lesson „Sorgsam bei Änderungen — vieles ist schon gut" spricht klar für die kleine Schneise.
- **E2E-Tests trip-edit/trip-wizard-multi-gpx**: Sind laut Issue #217 vorbestehend kaputt; auch ohne unser Cleanup defekt. Wir sollten sie nicht im Scope haben.

## Existing Specs

- `docs/specs/modules/epic_136_trip_wizard.md` — Master-Spec, „Not In Scope" listet diesen Cleanup explizit.
- `docs/specs/modules/issue_224_wizard_alert_rules_editor.md` — Vorgänger-Konsolidierung.

## Phase-2-Erkenntnisse

**Mode-Prop ist toter Code.** Alle vier Komponenten deklarieren `mode?: 'create'|'edit'`, aber keine prüft den Wert per `if (mode === 'edit')` o.ä. (0 Treffer für `mode ===` in allen vier Files). Im Edit-Pfad wird immer `mode="edit"` übergeben, im neuen Wizard wird keine dieser Komponenten mehr genutzt. → Out of Scope für diesen Cleanup (Refactoring), aber gut zu wissen.

**Kein WizardState-Context-Import.** Die vier Komponenten nutzen einfache `$bindable()`-Props (`tripName`, `stages`, `displayConfig`, `reportConfig`). Verschieben + Umbenennen ist daher rein mechanisch — keine Logik-Anpassung nötig.

**E2E-Tests:** `trip-wizard.spec.ts` ist bereits `.skip` mit Kommentar „Loeschung erfolgt im Cleanup-Folge-Issue" — direkt löschen. `trip-edit.spec.ts` und `trip-wizard-multi-gpx.spec.ts` sind laut Issue #217 vorbestehend kaputt und bleiben außerhalb des Scopes.

## Strategie (Empfehlung)

**Kleine Schneise — Verschieben/Umbenennen ohne Logik-Änderung.**

### Datei-Operationen

1. **Löschen (tot):**
   - `frontend/src/lib/components/wizard/TripWizard.svelte`
   - `frontend/src/lib/components/wizard/WizardStepper.svelte`
   - `frontend/e2e/trip-wizard.spec.ts` (`.skip`, Kommentar verweist hierher)

2. **Verschieben + Umbenennen** in `frontend/src/lib/components/edit/`:
   | Alt | Neu |
   |---|---|
   | `WizardStep1Route.svelte` | `EditRouteSection.svelte` |
   | `WizardStep2Stages.svelte` | `EditStagesSection.svelte` |
   | `WizardStep3Weather.svelte` | `EditWeatherSection.svelte` |
   | `WizardStep4ReportConfig.svelte` | `EditReportConfigSection.svelte` |

3. **Imports anpassen** in `frontend/src/lib/components/edit/TripEditView.svelte:6-9` — von `$lib/components/wizard/Wizard*.svelte` auf `./Edit*Section.svelte`.

4. **Verzeichnis `frontend/src/lib/components/wizard/`** löschen (sollte leer sein nach Schritt 1 & 2).

### Scope

| Kategorie | Anzahl |
|---|---|
| Files geändert | 1 (`TripEditView.svelte`, nur Imports) |
| Files gelöscht | 3 (2 tote .svelte + 1 .skip E2E) |
| Files verschoben+umbenannt | 4 |
| LoC-Delta | ~0 (Renames + Import-Pfad-Wechsel) |

Deutlich unter dem 250-LoC-Limit.

### Out of Scope

- **Mode-Prop entfernen** — separates Refactoring-Ticket
- **Edit-Pfad zu neuem Wizard-Modell konsolidieren** (Issue-Vorschlag „(a)") — eigenes Epic, riskant wegen Datenverlust-Sensitivität
- **`trip-edit.spec.ts` und `trip-wizard-multi-gpx.spec.ts` reparieren** — Issue #217

### Risiken

- **svelte-check** fängt Pfad-Fehler ab (alle Imports prüfbar).
- **Memory: BUG-DATALOSS-GR221:** Greift NICHT, weil keine Schema-Datei geändert wird (nur UI-Komponenten verschoben). Hook `data_schema_backup.py` reagiert nicht auf diese Dateien.
- **Build-Sanity:** Frontend-Build muss durchlaufen — kann lokal via `npm run build` getestet werden.

## Nächster Schritt

Phase 3: Spec schreiben (`docs/specs/modules/issue_190_alter_wizard_cleanup.md`). Diese Strategie 1:1 als Spec festhalten.

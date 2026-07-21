---
entity_id: issue_683_compare_wizard_remove
type: rework
created: 2026-06-11
updated: 2026-06-11
status: draft
version: "1.0"
tags: [compare, cleanup, dead-code, frontend, wizard]
---

<!-- Issue #683 — Compare-Editor Slice 6: Wizard entfernen -->

# Issue #683 — Compare-Wizard entfernen (toter Code, ~1700 Zeilen)

## Approval

- [ ] Approved

## Purpose

Der `CompareWizard` (Stepper-Shell) und seine Abhängigkeit `Step1Vergleich.svelte`
sind toter Code: beide Routes (`/compare/new`, `/compare/[id]/edit`) rendern seit
Slice 1 (Issue #678) ausschließlich `CompareEditor`. Ziel ist das Entfernen dieser
~1700 Zeilen ungenutztem Code inklusive der 7 darauf ausgerichteten Wizard-only-Tests
sowie das Bereinigen der Stepper-Felder in `compareWizardState.svelte.ts`, um den
Daten-State für zukünftige Arbeiten schlank und konsistent zu halten.

## Source

- **Löschen:** `frontend/src/lib/components/compare/CompareWizard.svelte` (339 Zeilen)
- **Löschen:** `frontend/src/lib/components/compare/steps/Step1Vergleich.svelte` (100 Zeilen)
- **Bereinigen:** `frontend/src/lib/components/compare/compareWizardState.svelte.ts` — Stepper-Felder entfernen, Datenfelder und save-Methoden behalten
- **Anpassen:** `frontend/src/lib/components/compare/issue_462.test.ts`
- **Anpassen:** `frontend/src/routes/compare/__tests__/issue_582_compare_design_fidelity.test.ts`
- **Anpassen:** `frontend/src/lib/bug_601_api_catch_logging.test.ts` (Zeilennummer nach Cleanup neu ermitteln)
- **Löschen (7 Wizard-only-Tests):**
  - `__tests__/issue_440_compare_wizard_shell.test.ts`
  - `__tests__/issue_440_compare_wizard_state.test.ts`
  - `__tests__/issue_441_step3_idealwerte.test.ts`
  - `__tests__/issue_442_compare_wizard_step4.test.ts`
  - `__tests__/issue_443_step5.test.ts`
  - `__tests__/issue_492_home_umbau_wizard_feinschliff.test.ts`
  - `__tests__/issue_547_auto_profile_preselect.test.ts`

## Estimated Scope

- **LoC:** ~−1700 netto (Löschungen dominieren); bereinigter State und angepasste Tests ergeben netto weniger als 250 LoC Delta
- **Files:** ~12 (7 gelöscht, 2 gelöscht Svelte, 3 angepasst)
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `CompareEditor` | Frontend-Komponente | Einziger aktiver Consumer der Steps 2–5; bleibt unberührt |
| `Step2Orte.svelte` | Frontend-Komponente | Aktiv in CompareEditor (Z.20–23), darf NICHT gelöscht werden |
| `Step3Idealwerte.svelte` | Frontend-Komponente | Aktiv in CompareEditor (Z.492–502), darf NICHT gelöscht werden |
| `Step4Layout.svelte` | Frontend-Komponente | Aktiv in CompareEditor (Z.634–652), darf NICHT gelöscht werden |
| `Step5Versand.svelte` | Frontend-Komponente | Aktiv in CompareEditor, darf NICHT gelöscht werden |
| `compareWizardState.svelte.ts` | Frontend-Store | Datenfelder (`name`, `pickedIds`, `idealRanges`, `schedule` etc.) und save-Methoden (`save`, `saveNewPreset`, `saveComparePreset`, `toggleEnabled`) bleiben vollständig erhalten; nur Stepper-Felder werden entfernt |
| `issue_462.test.ts` | Test | CompareWizard-Eintrag aus `MIGRATED_FILES` und den zugehörigen AC-1-Block entfernen |
| `issue_582_compare_design_fidelity.test.ts` | Test | AC-8 und AC-9 (Wizard-spezifisch) entfernen |
| `bug_601_api_catch_logging.test.ts` | Test | `catchLine: 131` auf neue Zeilennummer in `compareWizardState.svelte.ts` nach Stepper-Removal anpassen |

## Implementation Details

### Reihenfolge der Änderungen

```
1. 7 Wizard-only-Tests löschen (keine Abhängigkeiten untereinander):
     __tests__/issue_440_compare_wizard_shell.test.ts
     __tests__/issue_440_compare_wizard_state.test.ts
     __tests__/issue_441_step3_idealwerte.test.ts
     __tests__/issue_442_compare_wizard_step4.test.ts
     __tests__/issue_443_step5.test.ts
     __tests__/issue_492_home_umbau_wizard_feinschliff.test.ts
     __tests__/issue_547_auto_profile_preselect.test.ts

2. issue_462.test.ts anpassen:
   - CompareWizard aus der MIGRATED_FILES-Konstanten entfernen
   - Den AC-1-Block (oder entsprechenden Test-Block), der CompareWizard
     auf MIGRATED_FILES prüft, entfernen

3. issue_582_compare_design_fidelity.test.ts anpassen:
   - AC-8 und AC-9 (Wizard-Stepper-Tests) entfernen

4. compareWizardState.svelte.ts bereinigen:
   Folgende Stepper-Felder und deren Ableitungen entfernen:
     - currentStep
     - nextStep()
     - prevStep()
     - goToStep()
     - canAdvanceCurrent
     - canAdvanceStep1
     - canAdvanceStep2
     - canAdvanceStep3
     - canAdvanceStep5
   Behalten (unverändert):
     - alle Datenfelder: name, pickedIds, idealRanges, schedule, ...
     - save(), saveNewPreset(), saveComparePreset(), toggleEnabled()
     - alle anderen nicht-Stepper-Exporte

5. bug_601_api_catch_logging.test.ts anpassen:
   - Nach Bereinigung von compareWizardState.svelte.ts die tatsächliche
     neue Zeilennummer des relevanten catch-Blocks via grep ermitteln
   - catchLine: 131 auf neue Zeilennummer setzen

6. CompareWizard.svelte löschen:
   frontend/src/lib/components/compare/CompareWizard.svelte

7. Step1Vergleich.svelte löschen:
   frontend/src/lib/components/compare/steps/Step1Vergleich.svelte

8. Verifikation: rg CompareWizard frontend/src → kein Treffer
9. Test-Suite ausführen: node --experimental-strip-types --test src/**/*.test.ts
   → fail = 0
```

### Kritische Scope-Abgrenzung

`Step2Orte.svelte`, `Step3Idealwerte.svelte`, `Step4Layout.svelte` und
`Step5Versand.svelte` werden von `CompareEditor` aktiv importiert und gerendert
(nachprüfbar in CompareEditor Z.20–23, Z.492–502, Z.634–652). Diese vier Dateien
sind kein toter Code und dürfen unter keinen Umständen gelöscht werden.
Nur `CompareWizard.svelte` (die Stepper-Shell) und `Step1Vergleich.svelte`
(ausschließlich von CompareWizard importiert) sind sicher zu löschen.

### Neue Zeilennummer für bug_601

Nachdem `compareWizardState.svelte.ts` von den Stepper-Feldern befreit wurde,
muss die tatsächliche neue Zeilennummer des catch-Blocks per Grep ermittelt
werden, bevor `bug_601_api_catch_logging.test.ts` angepasst wird:

```bash
grep -n "catch" frontend/src/lib/components/compare/compareWizardState.svelte.ts
```

Der Test referenziert die Zeilennummer hardkodiert über `catchLine`. Der Wert
ist nach dem Cleanup neu zu setzen — kein Schätzen, sondern per Grep beweisen.

## Expected Behavior

- **Input:** Codebase mit ~1700 Zeilen totem Wizard-Code und 7 Wizard-only-Tests
- **Output:** `CompareWizard.svelte` und `Step1Vergleich.svelte` existieren nicht mehr; `compareWizardState.svelte.ts` enthält keine Stepper-Felder mehr; alle 7 Wizard-only-Testdateien sind gelöscht; `issue_462`, `issue_582` und `bug_601`-Tests sind angepasst; die Frontend-Test-Suite ist grün
- **Side effects:** Keine Verhaltensänderung für den Nutzer — `CompareEditor` und alle seine aktiven Steps (2–5) bleiben vollständig funktional

## Acceptance Criteria

**AC-1:** Given das Repo-Verzeichnis `frontend/src`, When `rg CompareWizard frontend/src` ausgeführt wird, Then kein Treffer — weder Import noch Datei noch Referenz in einem Test.

**AC-2:** Given das Verzeichnis `frontend/src/lib/components/compare/steps/`, When der Inhalt aufgelistet wird, Then existiert `Step1Vergleich.svelte` nicht mehr, aber `Step2Orte.svelte`, `Step3Idealwerte.svelte`, `Step4Layout.svelte` und `Step5Versand.svelte` sind alle vorhanden.

**AC-3:** Given `frontend/src/lib/components/compare/compareWizardState.svelte.ts`, When die Datei gelesen wird, Then sind `currentStep`, `nextStep`, `prevStep`, `goToStep`, `canAdvanceCurrent`, `canAdvanceStep1`, `canAdvanceStep2`, `canAdvanceStep3` und `canAdvanceStep5` nicht mehr vorhanden; alle Datenfelder (`name`, `pickedIds`, `idealRanges`, `schedule` etc.) und save-Methoden (`save`, `saveNewPreset`, `saveComparePreset`, `toggleEnabled`) sind weiterhin vorhanden.

**AC-4:** Given die Frontend-Test-Suite, When alle Tests ausgeführt werden (`node --experimental-strip-types --test src/**/*.test.ts`), Then ist die Suite grün — pass-Anzahl gleich oder höher als vor dem Cleanup (7 gelöschte Wizard-Tests zählen nicht mehr), fail = 0.

**AC-5:** Given `frontend/src/routes/compare/new/+page.svelte` und `frontend/src/routes/compare/[id]/edit/+page.svelte`, When beide Dateien gelesen werden, Then importieren beide `CompareEditor` und enthalten keinen `CompareWizard`-Import.

## Known Limitations

- `bug_601_api_catch_logging.test.ts` hält die Zeilennummer hardkodiert; nach dem
  Stepper-Removal ist die Anpassung manuell via Grep zu verifizieren, nicht automatisiert
- Zukünftige Refactors an `compareWizardState.svelte.ts` müssen `bug_601` ebenfalls
  nachziehen, wenn weitere Zeilen oberhalb des catch-Blocks entfernt werden

## Changelog

- 2026-06-11: Initial spec erstellt — Issue #683, Compare-Editor Slice 6

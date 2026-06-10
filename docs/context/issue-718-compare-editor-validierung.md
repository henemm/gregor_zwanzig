# Context: Issue #718 — Compare-Editor Slice 4 Validierungsmeldungen

## Request Summary
Im Compare-Editor Tab „Idealwerte" (Step 3) fehlen Inline-Validierungsmeldungen. Min > Max-Zustände (aus Edit-Mode API-Load) und unplausible Werte sollen direkt an der Metrik angezeigt werden; der Tab gilt erst als „done" wenn die Konfiguration valide ist.

## Wichtige Erkenntnis: RangeSlider erzwingt strukturell Min < Max
Der `RangeSlider.svelte` clamp'd den Min-Handle auf `(min, valueMax - step)` und den Max-Handle auf `(valueMin + step, max)` — Min > Max ist per UI-Interaktion unmöglich. Der einzig realistische Eintrittspunkt für invalide Ranges ist der **Edit-Modus via API-Load** (historical data oder direkter API-Zugriff). „Unplausible Werte" außerhalb MetricDef-Grenzen sind ebenfalls per Slider unerreichbar. Konsequenz: **keine gelbe Warnstufe notwendig** — nur roter Fehler bei Min > Max.

## Related Files
| File | Relevanz |
|------|----------|
| `frontend/src/lib/components/compare/steps/Step3Idealwerte.svelte` | UI — kein Validierungskonzept vorhanden |
| `frontend/src/lib/components/compare/compareEditorLogic.ts` | `doneTabs()` / `unlockedTabs()` — muss `idealsValid` kennen |
| `frontend/src/lib/components/compare/CompareEditor.svelte` | Ruft `doneTabs()` auf, hat lokale `idealsVisited`-State |
| `frontend/src/lib/components/compare/compareWizardState.svelte.ts` | Braucht `canAdvanceStep3`-Getter (Wizard-Footer-Button) |
| `frontend/src/lib/components/compare/compareMetricDefs.ts` | Neue `validateIdealRanges()` pure function hier platzieren |
| `frontend/src/lib/components/compare/RangeSlider.svelte` | Strukturell Min<Max — keine Änderung nötig |
| `frontend/src/lib/components/compare/compareEditorLogic.test.ts` | Tests für `doneTabs()` müssen `idealsValid` berücksichtigen |

## Existierende Patterns
- **Validierung in WizardState:** `canAdvanceStep1/2/5` als Getter-Pattern — `canAdvanceStep3` analog
- **Inline-Fehler:** `LocationForm.svelte` → `let error = $state('')` + `{#if error}<p class="text-sm text-destructive">` 
- **CSS-Tokens:** `--g-danger: #a83232`, `--g-warn: #c08a1a` vorhanden
- **Testids:** `compare-step3-metric-{key}` pro Metrik-Zeile bereits vorhanden

## Architektur-Entscheidung
`validateIdealRanges(ranges, activeKeys): { valid: boolean; invalidKeys: string[] }` als pure Funktion in `compareMetricDefs.ts`. Wird konsumiert von:
1. `CompareWizardState.canAdvanceStep3` → blockiert Wizard-Footer-Weiter-Button
2. `CompareEditor.svelte` → `$derived idealsValid` → an `doneTabs()` übergeben als `idealsValid: wiz.canAdvanceStep3`

## Änderungen im Überblick
1. **`compareMetricDefs.ts`** — `validateIdealRanges()` hinzufügen
2. **`compareEditorLogic.ts`** — `idealsValid?: boolean` in Interface; `doneTabs()`: `idealsVisited && (idealsValid !== false)`  
3. **`compareWizardState.svelte.ts`** — `canAdvanceStep3` Getter + `case 3` in `canAdvanceCurrent`
4. **`CompareEditor.svelte`** — `idealsValid` als `$derived` + an `doneTabs()` übergeben
5. **`Step3Idealwerte.svelte`** — Inline-Fehler pro Metrik-Zeile (unter Slider, `--g-danger`)

## Dependencies
- Upstream: `compareMetricDefs.ts` (MetricDef-Typen, IdealRange)
- Downstream: `CompareEditor.svelte`, `CompareWizardState`, `compareEditorLogic.test.ts`

## Risks & Considerations
- Rückwärtskompatibilität: `idealsValid?: boolean` als optional → bestehende Tests übergeben es nicht → `undefined !== false` → grün ohne Änderung (nur neuen positiven Test hinzufügen)
- Nur `CompareEditor.svelte` ruft `doneTabs()` auf (bestätigt per Grep) → ein Aufrufer
- `unlockedTabs()` bleibt unverändert — Tab-Freischaltung soll auch bei invaliden Idealwerten im Edit-Modus frei bleiben

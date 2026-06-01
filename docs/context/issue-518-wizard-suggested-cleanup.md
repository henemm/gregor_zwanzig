# Context: Issue #518 — KI/Bestätigen-Verwerfen im Trip-Wizard entfernen

## Request Summary

PO-Entscheid (#503): Kein Auto/Manuell-Unterschied mehr — ein Wegpunkt ist ein Wegpunkt. Die alte
"suggested"-Logik (orange gestrichelt, Bestätigen/Verwerfen) wurde im Edit-Flow (#503) bereits
entfernt. Im **Trip-Erstellungs-Wizard** (Step 2 + Step 3) existiert sie noch vollständig.

## Betroffene Dateien

| Datei | Was ändert sich |
|-------|-----------------|
| `frontend/src/lib/components/trip-wizard/TripWizardShell.svelte:51` | `stepHints[2]` → `null` (kein Text über "orange gestrichelt/bestätigen/verwerfen") |
| `frontend/src/lib/components/trip-wizard/steps/WaypointRow.svelte` | `suggested`-Pin-Stil entfernen, `onConfirm`-Prop entfernen, Bestätigen-Button entfernen; alle Wegpunkte uniform; `onReject` bleibt als "Löschen" |
| `frontend/src/lib/components/trip-wizard/wizardState.svelte.ts` | `addStage`: kein automatisches `suggested:true` mehr; `confirmWaypoint()` entfernen; `stripSuggested()` entfernen; `toTripPayload()` ohne suggested-Strip |
| `frontend/src/lib/components/trip-wizard/steps/Step2Stages.svelte` | `suggestedCount()`-Funktion entfernen; "Vorschläge-Pill" entfernen (Zeilen 55–57 + 131 + 143–152) |
| `frontend/src/lib/components/trip-wizard/steps/Step3Waypoints.svelte` | `makeConfirmHandler()` entfernen; `confirmWaypoint()`-Aufruf entfernen; `onConfirm`-Prop aus `WaypointRow` entfernen |
| `frontend/src/lib/components/trip-wizard/steps/ProfileChart.svelte:85` | `{#if p.wp.suggested === true}` → uniform; alle Pins gleich darstellen |

## Explizit NICHT geändert

| Datei | Begründung |
|-------|-----------|
| `frontend/src/lib/components/compare/CompareWizard.svelte` | Dort bedeutet `onConfirm`/`onReject` das Bestätigen/Verwerfen von Orts-Vergleichs-Änderungen — anderer Kontext |
| `frontend/src/lib/components/trip-detail/waypoints/WaypointCard.svelte` | `onConfirm`/`onReject` bleiben als optionale No-Op-Props (Backward-Compat-Stubs) |
| `frontend/src/lib/components/trip-detail/waypoints/WaypointPin.svelte` | `suggested`-Prop bleibt im Interface (WaypointCard nutzt `suggested={false}`) |
| `frontend/src/lib/types.ts` | `Waypoint.suggested?: boolean` bleibt (Backend kann das Feld noch schicken) |
| `frontend/src/lib/utils/waypointEditor.ts` | `stripSuggested()` bleibt (wird in TripEditView + WaypointsPanel genutzt) |

## Bestehende Test-Dateien (müssen angepasst werden)

| Datei | Was |
|-------|-----|
| `__tests__/wizardState.test.ts` | AC#16 (addStage-suggested-Tests) entfernen; AC#14 (confirmWaypoint) entfernen; AC#15 (rejectWaypoint) bleibt |
| `__tests__/tripTemplates.test.ts:97` | "Kein Waypoint einer Vorlage hat suggested=true" entfernen (Konzept existiert nicht mehr im Wizard) |

## Existierende Playwright-TestIDs (bleiben erhalten!)

Laut Issue-AC müssen bestehende `data-testid`s in WaypointRow erhalten bleiben:
- `trip-wizard-step3-waypoint-row-{index}` ✓ bleibt
- `trip-wizard-step3-reject-{index}` ✓ bleibt (Löschen-Button)
- `trip-wizard-step3-confirm-{index}` → **wird entfernt** (Bestätigen-Button weg)

## Existing Patterns

- `stripDateOverridden()` in wizardState ist das Vorbild: transientes Flag wird in `toTripPayload()` gestrippt → analog `stripSuggested()` wird ganz entfernt (kein Flag mehr gesetzt)
- `WaypointCard.onConfirm/onReject` als optionale Props = das Muster für Backward-Compat-Stubs
- Pin-Stil in WaypointRow nach Änderung: immer `stroke=ink-strong, fill=ink-strong` (kein Dash)

## Abhängigkeiten

- **Upstream:** `WizardState.addStage()` → nach Änderung keine suggested-Markierung mehr
- **Downstream:** `Step3Waypoints.svelte` konsumiert `confirmWaypoint`/`rejectWaypoint` → nach Änderung nur noch `rejectWaypoint` (= Löschen)
- `Step2Stages.svelte` konsumiert `suggestedCount()` → nach Änderung weg
- `ProfileChart.svelte` liest `wp.suggested` → nach Änderung uniform

## Risks & Considerations

- **`canAdvanceStep3`-Kommentar** (wizardState:117): Bezieht sich auf `stripSuggested` → muss bereinigt werden
- **`addStage`-Kommentar** (wizardState:185-188): Bezieht sich auf Sub-Spec #163 §3.1 → entfernen/vereinfachen
- **Tests**: Mehrere wizardState-Tests prüfen suggested-Verhalten → müssen entfernt werden, damit sie nicht "rot" werden ohne Grund
- `rejectWaypoint()` bleibt: Es ist die einzige Aktion mit fachlicher Konsequenz (Wegpunkt löschen)

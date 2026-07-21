---
entity_id: issue_518_wizard_suggested_cleanup
type: module
created: 2026-06-01
updated: 2026-06-01
status: implemented
version: "1.0"
tags: [frontend, trip-wizard, svelte, cleanup, suggested-waypoints]
---

# Spec: Issue #518 — KI/Bestätigen-Verwerfen im Trip-Wizard entfernen

## Approval

- [ ] Approved

## Purpose

Entfernt die veraltete "suggested"-Wegpunkt-Logik vollständig aus dem Trip-Erstellungs-Wizard (Step 2 + Step 3). Seit dem PO-Entscheid in #503 gibt es keinen Auto/Manuell-Unterschied mehr — ein Wegpunkt ist ein Wegpunkt; der Edit-Flow wurde bereits bereinigt, der Wizard-Erstellungsflow noch nicht. Dieser Cleanup beseitigt toten Code (orange gestrichelte Pins, Bestätigen-Button, `stripSuggested()`-Logik, Vorschläge-Pill) und macht den Wizard konsistent mit dem Rest der Anwendung.

## Source

- **Files:**
  - `frontend/src/lib/components/trip-wizard/TripWizardShell.svelte`
  - `frontend/src/lib/components/trip-wizard/steps/WaypointRow.svelte`
  - `frontend/src/lib/components/trip-wizard/wizardState.svelte.ts`
  - `frontend/src/lib/components/trip-wizard/steps/Step2Stages.svelte`
  - `frontend/src/lib/components/trip-wizard/steps/Step3Waypoints.svelte`
  - `frontend/src/lib/components/trip-wizard/steps/ProfileChart.svelte`
  - `frontend/src/lib/components/trip-wizard/__tests__/wizardState.test.ts`
  - `frontend/src/lib/components/trip-wizard/__tests__/tripTemplates.test.ts`
- **Identifier:** `WizardState`, `WaypointRow`, `Step2Stages`, `Step3Waypoints`, `ProfileChart`

## Estimated Scope

- **LoC:** ~−154 (fast ausschließlich Löschungen)
- **Files:** 8
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/src/lib/types.ts` | Typdefinition | `Waypoint.suggested?: boolean` bleibt erhalten (Backend-Kompatibilität); kein Import-Change nötig |
| `frontend/src/lib/utils/waypointEditor.ts` | Utility | `stripSuggested()` bleibt (wird in TripEditView + WaypointsPanel genutzt) — nicht berühren |
| `frontend/src/lib/components/compare/CompareWizard.svelte` | Komponente | `onConfirm`/`onReject` in anderem Kontext (Orts-Vergleich) — nicht berühren |
| `frontend/src/lib/components/trip-detail/waypoints/WaypointCard.svelte` | Komponente | Backward-Compat-Stubs `onConfirm`/`onReject` bleiben als optionale No-Op-Props |
| `frontend/src/lib/components/trip-detail/waypoints/WaypointPin.svelte` | Komponente | `suggested`-Prop bleibt im Interface (WaypointCard nutzt `suggested={false}`) |

## Implementation Details

### 1. `TripWizardShell.svelte` — Step-Hint entfernen

`stepHints[2]` (Index für Step 3 "Wegpunkte") auf `null` setzen. Der Hint enthält aktuell Text über "orange gestrichelt", "Vorschläge bestätigen/verwerfen" — dieser Text soll nicht mehr angezeigt werden.

### 2. `WaypointRow.svelte` — Uniform-Pin + Confirm-Button entfernen

- `isSuggested`-Prop entfernen (oder ignorieren, falls Prop-Removal breaking wäre)
- `onConfirm`-Prop entfernen
- Bestätigen-Button (`data-testid="trip-wizard-step3-confirm-{index}"`) entfernen
- SVG-Pin: immer `stroke=ink-strong, fill=ink-strong` (kein gestrichelter Pfad mehr für suggested=true)
- `onReject`-Prop bleibt als Löschen-Aktion; `data-testid="trip-wizard-step3-reject-{index}"` bleibt
- `data-testid="trip-wizard-step3-waypoint-row-{index}"` bleibt

### 3. `wizardState.svelte.ts` — Suggested-Logik entfernen

- `addStage()`: automatisches `suggested: true` beim Hinzufügen von Wegpunkten aus der Stage-Analyse entfernen; alle neuen Wegpunkte werden ohne Flag gesetzt
- `confirmWaypoint()`-Funktion vollständig entfernen
- `stripSuggested()`-Funktion vollständig entfernen (lokale Kopie im wizardState; die Kopie in `waypointEditor.ts` bleibt)
- `toTripPayload()`: den `stripSuggested()`-Aufruf entfernen
- `canAdvanceStep3`-Kommentar, der sich auf `stripSuggested` bezieht, bereinigen
- `addStage`-Kommentar (Zeilen 185–188, Bezug auf Sub-Spec #163 §3.1) entfernen/vereinfachen

### 4. `Step2Stages.svelte` — Vorschläge-Pill entfernen

- `suggestedCount()`-Funktion entfernen
- Vorschläge-Pill (Zeilen 55–57, 131, 143–152) entfernen — das sind die orange Badge/Pill-Elemente, die die Anzahl nicht bestätigter Vorschläge anzeigen

### 5. `Step3Waypoints.svelte` — Confirm-Handler entfernen

- `makeConfirmHandler()`-Funktion entfernen
- `confirmWaypoint()`-Aufruf entfernen
- `onConfirm`-Prop beim `<WaypointRow>`-Aufruf entfernen

### 6. `ProfileChart.svelte` — Uniform-Pins

- `{#if p.wp.suggested === true}`-Branch entfernen; alle Wegpunkt-Pins werden einheitlich dargestellt (kein Sonderfall mehr)

### 7. Tests anpassen

**`wizardState.test.ts`:**
- AC#16-Tests (addStage erzeugt `suggested: true`) entfernen
- AC#14-Tests (`confirmWaypoint` setzt Flag auf `false`) entfernen
- AC#15 (`rejectWaypoint` löscht Wegpunkt) bleibt unverändert

**`tripTemplates.test.ts`:**
- Test "Kein Waypoint einer Vorlage hat suggested=true" (Zeile 97) entfernen — das Konzept existiert nicht mehr im Wizard-Erstellungsfluss

## Expected Behavior

- **Input:** Ein User erstellt einen neuen Trip im Wizard und landet auf Step 2 (Etappen) oder Step 3 (Wegpunkte)
- **Output:** Alle Wegpunkte werden uniform mit gleichem Pin-Stil dargestellt; es gibt keinen Bestätigen-Button; der Löschen-Button funktioniert wie bisher; Step-2-Subtitle enthält keinen Text mehr über Vorschläge; `toTripPayload()` gibt Wegpunkte ohne Filterung nach `suggested` aus
- **Side effects:** Keine Datenverlust-Risiken (nur toten Code löschen); `Waypoint.suggested?: boolean` bleibt im Typ — das Backend kann das Feld weiterhin liefern, der Wizard ignoriert es einfach

## Acceptance Criteria

- **AC-1:** Given der User öffnet den Trip-Wizard und navigiert zu Step 2 (Etappen), When er den Subtitle-Bereich liest, Then enthält er keinen Text über "orange gestrichelt", "Bestätigen" oder "Verwerfen" von Vorschlägen.
  - Test: (populated after /tdd-red)

- **AC-2:** Given der User ist auf Step 3 (Wegpunkte) im Trip-Wizard, When er eine WaypointRow betrachtet — unabhängig davon ob der Wegpunkt ursprünglich per KI vorgeschlagen wurde oder manuell hinzugefügt wurde, Then werden alle Wegpunkte mit identischem Pin-Stil (solid, `stroke=ink-strong, fill=ink-strong`) und ohne Bestätigen-Button dargestellt.
  - Test: (populated after /tdd-red)

- **AC-3:** Given der User ist auf Step 3 und eine WaypointRow ist sichtbar, When er die Aktionsbuttons der Row betrachtet, Then gibt es keinen Bestätigen-Button mehr (`data-testid="trip-wizard-step3-confirm-{index}"` existiert nicht im DOM); der Löschen-Button (`data-testid="trip-wizard-step3-reject-{index}"`) ist weiterhin vorhanden und löscht den Wegpunkt.
  - Test: (populated after /tdd-red)

- **AC-4:** Given `wizardState` verwaltet eine Stage mit Wegpunkten, When `addStage()` aufgerufen wird und anschließend `toTripPayload()` aufgerufen wird, Then enthält keiner der ausgegebenen Wegpunkte ein `suggested: true`-Flag und es gibt keine `stripSuggested()`-Funktion mehr im wizardState-Modul; `rejectWaypoint()` ist weiterhin vorhanden.
  - Test: (populated after /tdd-red)

- **AC-5:** Given `wizardState` führt die Compiler-Prüfung durch, When der TypeScript-Compiler prüft, Then gibt es keinen Aufruf von `confirmWaypoint()` oder `stripSuggested()` mehr (Funktionen sind gelöscht); `rejectWaypoint()` kompiliert fehlerfrei; bestehende `data-testid`s `trip-wizard-step3-waypoint-row-{index}` und `trip-wizard-step3-reject-{index}` bleiben im DOM der WaypointRow vorhanden.
  - Test: (populated after /tdd-red)

## Known Limitations

- `Waypoint.suggested?: boolean` bleibt in `frontend/src/lib/types.ts` — wenn das Backend dieses Feld sendet, wird es stillschweigend ignoriert. Eine vollständige Entfernung aus dem Typ würde Backend-Änderungen erfordern und ist out of scope.
- `stripSuggested()` in `waypointEditor.ts` bleibt; sollte in einem späteren Cleanup-Issue zusammen mit dem Edit-Flow geprüft werden, ob es dort noch gebraucht wird.

## Changelog

- 2026-06-01: Initial spec created
- 2026-06-01: Implementation completed — all suggested-logic removed from Trip-Wizard (Steps 2 & 3)

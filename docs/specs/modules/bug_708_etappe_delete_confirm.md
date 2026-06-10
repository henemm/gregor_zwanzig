---
entity_id: bug_708_etappe_delete_confirm
type: module
created: 2026-06-10
updated: 2026-06-10
status: draft
version: "1.0"
tags: [frontend, trip-edit, trip-new, stages, ux, confirm]
---

# Bug #708 — Etappen dürfen nicht ohne Rückfrage gelöscht werden

## Approval

- [ ] Approved

## Purpose

Ein Klick auf das „×" einer Etappen-Karte löscht die Etappe sofort und unwiederbringlich
— ohne jede Sicherheitsabfrage. Ein Fehlklick zerstört damit Tourenarbeit (Etappe inkl.
Wegpunkte) ohne Möglichkeit zur Korrektur.

**Fix:** Vor dem tatsächlichen Löschen erscheint ein Bestätigungs-Dialog (App-Standard:
bits-ui `Dialog` mit „Abbrechen" / „Löschen", wie bei Locations & Account). Erst der Klick
auf „Löschen" entfernt die Etappe; „Abbrechen" oder Schließen lässt sie unverändert bestehen.
Gilt für **beide** Lösch-Stellen: Trip-Editor (Etappen-Tab) und `/trips/new`.

## Source

- **File:** `frontend/src/lib/components/edit/EditStagesPanelNew.svelte`
- **Identifier:** `handleRemoveStage`, neuer `pendingRemoveStageId`-State, neuer Confirm-Dialog
- **File:** `frontend/src/lib/components/trip-new/TripNewEditor.svelte`
- **Identifier:** `makeRemoveStageHandler`, neuer `pendingRemoveStageId`-State, neuer Confirm-Dialog

> Reine Frontend-Änderung (SvelteKit). Kein Go-/Python-Code betroffen — die Lösch-Mutation
> findet ausschließlich im UI-State statt; Persistenz erfolgt unverändert beim regulären Speichern.

## Estimated Scope

- **LoC:** ~80
- **Files:** 2 (`EditStagesPanelNew.svelte`, `TripNewEditor.svelte`)
- **Effort:** small

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `$lib/components/ui/dialog` | UI | bits-ui Dialog (Root/Content/Header/Title/Description/Footer) — App-Standard |
| `$lib/components/atoms.Btn` | UI | Buttons `variant="outline"` (Abbrechen) + `variant="destructive"` (Löschen) |
| `StageCard.onRemove` | Event | bestehender `×`-Klick-Auslöser (unverändert) |
| `EtappenStrip.onRemoveStage` | Event | reicht `stageId` durch (unverändert) |

## Acceptance Criteria

**AC-1:** Given der Nutzer ist im Trip-Editor auf dem Etappen-Tab (EtappenStrip/StageCard)
und eine Etappe ist sichtbar,
When er auf das „×" der Etappen-Karte klickt,
Then wird die Etappe NICHT sofort gelöscht, sondern es erscheint ein Bestätigungs-Dialog
mit dem Etappennamen und den Optionen „Abbrechen" und „Löschen".

**AC-2:** Given der Bestätigungs-Dialog aus AC-1 ist offen,
When der Nutzer auf „Abbrechen" klickt (oder den Dialog schließt),
Then bleibt die Etappe unverändert in der Liste bestehen und der Dialog schließt sich.

**AC-3:** Given der Bestätigungs-Dialog aus AC-1 ist offen,
When der Nutzer auf „Löschen" klickt,
Then wird die Etappe aus der Liste entfernt und der Dialog schließt sich.

**AC-4:** Given der Nutzer ist auf `/trips/new` im Etappen-Tab,
When er auf das „×" einer Etappe klickt,
Then erscheint ebenfalls der Bestätigungs-Dialog; „Abbrechen" erhält die Etappe,
„Löschen" entfernt sie.

**AC-5:** Given im Trip-Editor wird die aktuell aktive Etappe per Dialog gelöscht (AC-3),
When der Löschvorgang abgeschlossen ist,
Then wird eine andere noch vorhandene Etappe aktiviert (kein leerer/kaputter Zustand) —
das bisherige `activeStageId`-Reset-Verhalten bleibt erhalten.

## Implementation Details

### `EditStagesPanelNew.svelte`

1. Imports ergänzen (falls noch nicht vorhanden): `import * as Dialog from '$lib/components/ui/dialog/index.js';`
   und `import { Btn } from '$lib/components/atoms';`.
2. Neuer State: `let pendingRemoveStageId = $state<string | null>(null)`.
3. `onRemoveStage`-Verdrahtung ändern: statt `handleRemoveStage` direkt → `onRemoveStage={(id) => (pendingRemoveStageId = id)}`.
4. `handleRemoveStage` zu `confirmRemoveStage()` umbauen: nimmt `pendingRemoveStageId`,
   `stages = stages.filter(...)`, `activeStageId`-Reset wie bisher, dann `pendingRemoveStageId = null`.
5. Dialog-Markup (Muster `locations/+page.svelte`):
   `open={pendingRemoveStageId !== null}`, `onOpenChange` → bei `!open` `pendingRemoveStageId = null`.
   Titel „Etappe löschen", Beschreibung mit Etappennamen, Footer: `Btn variant="outline"` (Abbrechen) +
   `Btn variant="destructive"` (Löschen → `confirmRemoveStage`).
   Stabile Testids: `confirm-delete-stage` (Löschen-Button), `cancel-delete-stage` (Abbrechen-Button).

### `TripNewEditor.svelte`

6. Gleiche Imports ergänzen (Dialog; `Btn` falls vorhanden, sonst Inline-Buttons im bestehenden Stil).
7. Neuer State: `let pendingRemoveStageId = $state<number | null>(null)`.
8. `makeRemoveStageHandler(stageId)` ändern: setzt `pendingRemoveStageId = stageId` (kein direkter Filter mehr).
9. `confirmRemoveStage()`: `stages = stages.filter(s => s.id !== pendingRemoveStageId)`, dann `pendingRemoveStageId = null`.
10. Dialog-Markup wie oben mit gleichen Testids.

## Known Limitations

- Kein „Rückgängig"/Undo nach bestätigtem Löschen — die Bestätigung ist die Schutzschicht.
- Tastatur-Schnelllöschung (z.B. Entf-Taste) ist nicht betroffen; nur der `×`-Klick-Pfad.

## Changelog

- 2026-06-10: Spec erstellt (Bug #708, frontend-only, ~80 LoC, 2 Komponenten).

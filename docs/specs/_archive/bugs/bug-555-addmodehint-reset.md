---
entity_id: bug-555-addmodehint-reset
type: bugfix
created: 2026-06-02
updated: 2026-06-02
status: draft
version: "1.0"
tags: [waypoint-editor, ui-state]
---

# Bug #555: addModeHint wird bei Etappen-Wechsel nicht zurückgesetzt

## Approval

- [ ] Approved

## Purpose

Beim Wechsel zwischen Etappen im Wegpunkt-Editor wird der „+ auf Route"-Hinweis-Strip nicht ausgeblendet, weil `handleStageActivate` zwar `activeWaypointId` zurücksetzt, aber `addModeHint` vergisst.

## Source

- **File:** `frontend/src/lib/components/edit/EditStagesPanelNew.svelte`
- **Identifier:** `handleStageActivate` (Zeile 132)

## Estimated Scope

- **LoC:** ~1
- **Files:** 1
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `EditStagesPanelNew.svelte` | Modified | Enthält `addModeHint`-State und `handleStageActivate` |

## Implementation Details

```typescript
// VORHER (Zeile 132–135):
function handleStageActivate(stageId: string): void {
    activeStageId = stageId;
    activeWaypointId = null;
}

// NACHHER:
function handleStageActivate(stageId: string): void {
    activeStageId = stageId;
    activeWaypointId = null;
    addModeHint = false;
}
```

## Acceptance Criteria

**AC-1:** Given der „+ auf Route"-Hinweis-Strip ist in Etappe A sichtbar / When der Nutzer eine andere Etappe B im Etappen-Strip auswählt / Then verschwindet der Hinweis-Strip sofort — er ist in Etappe B nicht sichtbar.
- Test: (populated after /tdd-red)

**AC-2:** Given der „+ auf Route"-Hinweis-Strip ist sichtbar / When der Nutzer die gleiche Etappe erneut anklickt (kein Wechsel) / Then bleibt der Strip sichtbar (kein ungewollter Reset bei Selbst-Selektion).
- Test: (populated after /tdd-red)

**AC-3:** Given kein Hinweis-Strip ist sichtbar / When der Nutzer zwischen Etappen wechselt / Then passiert nichts Unerwartetes (kein Flackern, kein Fehler).
- Test: (populated after /tdd-red)

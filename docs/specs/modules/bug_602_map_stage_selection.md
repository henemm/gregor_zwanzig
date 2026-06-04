# Spec: Bug #602 — Karte zeigt immer Etappe 1

## Summary

Im Wegpunkt-Editor zeigt die Leaflet-Karte immer Etappe 1, unabhängig von der ausgewählten Etappe. Ursache: Svelte 5 `$effect` in `MapCanvas.svelte` liest `stage` nur asynchron → keine reactive Dependency → kein Re-Run bei Stage-Wechsel.

## Root Cause

`MapCanvas.svelte` Zeile 30: `stage.waypoints` wird innerhalb eines `async`-IIFE nach mehreren `await`-Calls gelesen. Svelte 5 trackt nur synchrone Reads als reactive Dependencies. Der `$effect` hat daher keine Dependency auf `stage` und re-rendert die Karte nicht wenn die Stage-Prop sich ändert.

## Fix

In `EditStagesPanelNew.svelte` `{#key activeStageId}`-Blöcke um beide MapCanvas-Instanzen (mobile + desktop) legen. Der `{#key}`-Block zerstört und re-erstellt die Komponente bei jedem Wechsel von `activeStageId`, was den `$effect` neu auslöst.

Hinweis: `WaypointsPanel.svelte` ist Dead Code (wird von keiner Route importiert). Der aktive Component-Pfad ist `TripTabs → EditStagesSection → EditStagesPanelNew`.

## Acceptance Criteria

**AC-1:** Given ein Trip mit ≥2 nicht-Pause-Etappen / When der User auf Etappe 2 im EtappenStrip klickt / Then wird map-canvas remounted (neues DOM-Element, Karte zeigt Etappe-2-Wegpunkte).

**AC-2:** Given der User wechselt zwischen Etappe 1 und Etappe 3 / When er auf Etappe 1 zurückklickt / Then wird map-canvas erneut remounted (korrekte Rückkehr, kein DOM-Fingerprint aus Etappe 2).

**AC-3:** Given eine Etappe ohne Wegpunkte (Pausenetappe) / When der User diese Etappe wählt / Then zeigt das Panel die PauseStageView (kein MapCanvas, kein Absturz, Panel bleibt bedienbar).

## Affected Files

- `frontend/src/lib/components/edit/EditStagesPanelNew.svelte` — Fix-Stelle (beide MapCanvas-Instanzen)

## Out of Scope

- `WaypointsPanel.svelte` ist Dead Code — keine Änderung nötig oder sinnvoll
- `ProfileEditor.svelte` ist nicht betroffen (nutzt `$derived`, ist reaktiv)
- `MapCanvas.svelte` selbst wird nicht geändert

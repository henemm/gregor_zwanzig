# Spec: Bug #602 — Karte zeigt immer Etappe 1

## Summary

Im Wegpunkt-Editor zeigt die Leaflet-Karte immer Etappe 1, unabhängig von der ausgewählten Etappe. Ursache: Svelte 5 `$effect` in `MapCanvas.svelte` liest `stage` nur asynchron → keine reactive Dependency → kein Re-Run bei Stage-Wechsel.

## Root Cause

`MapCanvas.svelte` Zeile 30: `stage.waypoints` wird innerhalb eines `async`-IIFE nach mehreren `await`-Calls gelesen. Svelte 5 trackt nur synchrone Reads als reactive Dependencies. Der `$effect` hat daher keine Dependency auf `stage` und re-rendert die Karte nicht wenn die Stage-Prop sich ändert.

## Fix

In `WaypointsPanel.svelte` einen `{#key activeStageId}`-Block um `MapCanvas` (und zur Konsistenz auch um `ProfileEditor`) legen. Der `{#key}`-Block zerstört und re-erstellt die Komponente bei jedem Wechsel von `activeStageId`, was den `$effect` neu auslöst.

## Acceptance Criteria

**AC-1:** Given ein Trip mit ≥2 nicht-Pause-Etappen / When der User auf Etappe 2 im EtappenStrip klickt / Then zeigt die Karte die Wegpunkte von Etappe 2 (nicht von Etappe 1).

**AC-2:** Given der User wechselt zwischen Etappe 1 und Etappe 3 / When er auf Etappe 1 zurückklickt / Then zeigt die Karte wieder Etappe 1 (korrekte Rückkehr).

**AC-3:** Given eine Etappe ohne Wegpunkte / When der User diese Etappe wählt / Then zeigt die Karte die Default-Ansicht (keine Wegpunkte, Zentrierung auf Europa) — kein Absturz.

## Affected Files

- `frontend/src/lib/components/trip-detail/WaypointsPanel.svelte` — Fix-Stelle

## Out of Scope

- `ProfileEditor.svelte` ist nicht betroffen (nutzt `$derived`, ist reaktiv)
- `MapCanvas.svelte` selbst wird nicht geändert

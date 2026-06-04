# Context: Bug #602 — Karte zeigt immer Etappe 1

## Bug Summary

- **Location:** `frontend/src/lib/components/trip-detail/waypoints/MapCanvas.svelte`
- **Problem:** Die Leaflet-Karte zeigt immer die Wegpunkte von Etappe 1, unabhängig davon welche Etappe in der EtappenStrip ausgewählt ist.
- **Expected:** Beim Klick auf eine andere Etappe zeigt die Karte die Wegpunkte dieser Etappe.
- **Root Cause:** Svelte 5 `$effect` in `MapCanvas.svelte` liest `stage.waypoints` ausschließlich asynchron (innerhalb eines `async`-IIFE nach mehreren `await`-Aufrufen). Svelte 5 trackt reactive Dependencies nur für synchrone Lesezugriffe — asynchrone Reads werden ignoriert. Damit ist `stage` kein reaktiver Dependency des Effects. Der Effect läuft einmalig beim Mount, niemals wieder wenn die Stage-Prop wechselt.
- **Test:** Waypoints-Tab öffnen → andere Etappe im Strip wählen → Karte muss wechseln
- **Effort:** Small

## Root Cause Detail

```typescript
// MapCanvas.svelte:30 — $effect
$effect(() => {
    if (!browser || !mapEl) return;
    let aborted = false;
    (async () => {
        const L = (await import('leaflet')).default;  // <-- await hier
        // ...
        const waypoints = stage.waypoints;  // <-- stage wird NACH await gelesen → nicht getrackt!
    })();
    // ...
});
```

`stage` wird nie synchron gelesen → Effect hat keine Dependency auf `stage` → Re-Run bei Stage-Wechsel findet nicht statt.

## Fix Options

**Option A (empfohlen): `{#key}` in WaypointsPanel**

```svelte
{#key activeStageId}
  <MapCanvas stage={activeStage} ... />
{/key}
```

Erzwingt komplettes Remount von MapCanvas wenn Stage wechselt. Semantisch klar, keine MapCanvas-Änderung nötig.

**Option B: Synchroner Capture in MapCanvas**

```typescript
$effect(() => {
    const currentStage = stage; // Synchron lesen → trackt als Dependency
    if (!browser || !mapEl) return;
    // ... benutze currentStage statt stage
});
```

## Related Files

| File | Relevance |
|------|-----------|
| `frontend/src/lib/components/trip-detail/waypoints/MapCanvas.svelte:30` | Root Cause: $effect trackt stage nicht |
| `frontend/src/lib/components/trip-detail/WaypointsPanel.svelte:146` | Fix-Stelle Option A: `{#key activeStageId}` |

## Existing Patterns

- `{#key}` wird bereits in anderen Svelte-Komponenten für Component-Remount genutzt
- `WaypointsPanel` verwaltet korrekt `activeStageId` und `activeStage`

## Risks & Considerations

- Fix ist minimal: 2 Zeilen in WaypointsPanel
- Kein Datenverlust-Risiko (read-only Karte)
- ProfileEditor (`line 151`) hat dasselbe potenzielle Problem — prüfen ob gleicher Fix nötig

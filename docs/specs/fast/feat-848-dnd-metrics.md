# Mini-Spec: feat-848-dnd-metrics

## Was ändert sich

**`WeatherV2Reihenfolge.svelte`**
- Props: `onReorder: (id: string, dir: -1|1)` → `onDndReorder: (fromId: string, toId: string)`
- Jede `.row` bekommt `draggable="true"` + `cursor: grab`
- Die `.drag-dots`-SVG wird zum visuellen Handle (`cursor: grab`)
- State `dragSourceId: string | null` für die laufende Drag-Session
- Events: `ondragstart`, `ondragover` (preventDefault), `ondrop`
- Drag-over-Zeile bekommt eine visuelle Hervorhebung (Trennlinie oben)
- Arrow-Buttons (▲▼) entfernt — D&D ersetzt sie vollständig

**`WeatherMetricsTab.svelte`**
- `onReorder`-Handler → `onDndReorder(fromId, toId)`: berechnet fromIdx/toIdx, baut neue Liste mit splice, ruft `applyDiff` + `scheduleAutoSave` auf

## Was darf sich nicht ändern

- `onRemove`, `onMode` und alle anderen Callbacks bleiben unverändert
- Die orange Schnittlinie (`cut-line`) bei Telegram-Limit bleibt
- Das Highlight-System (`hl`-Class) bleibt
- `metricsEditor.ts` wird nicht angefasst

## Acceptance Criteria

**AC-1:** Given mindestens 2 Metriken aktiv / When Nutzer Metrik an den Dots anfasst und auf eine andere zieht / Then Reihenfolge ändert sich sofort, Mail-Vorschau aktualisiert sich, AutoSave greift.

**AC-2:** Given Drag-Session aktiv / When Nutzer über eine andere Zeile fährt / Then visuelle Drop-Markierung (Trennlinie oben an der Zielzeile) erscheint.

**AC-3:** Given Telegram als aktiver Kanal / When Metriken per D&D verschoben / Then Schnittlinie bleibt an der korrekten Budget-Position.

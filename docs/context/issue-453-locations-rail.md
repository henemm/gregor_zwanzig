# Context: Issue #453 — Locations-Rail (Compare-Hauptbühne)

## Request Summary

Die Locations-Rail der Compare-Hauptbühne (Epic #246): 240px-breite linke Sidebar
mit Suche, Chip-Filter, gruppierten Checkboxen, Min/Max-Constraint und NEU-Button.

## Abhängigkeit

- **#451 Location-Datenmodell** → CLOSED ✅ (CRUD-API + `GET /api/locations/{id}` fertig)
- **#452 Smart-Import Modal** → OPEN (NEU-Button-Ziel; für #453 reicht `onNewLocation`-Callback)
- **#455 Compare-Hauptbühne Frontend** → OPEN, hängt von #453 ab

## Was bereits existiert

### `LocationsRail.svelte` (aus #249, `frontend/src/lib/components/compare/`)

Vollständige Komponente, aber **nirgendwo auf einer Produktionsseite eingebunden** (nur in Tests referenziert).

Bereits vorhanden:
- ✅ Suche (Echtzeit, filtert Name + Gruppenname)
- ✅ Chip-Filter Gruppen (group_id, Toggle)
- ✅ Chip-Filter Aktivitätsprofil
- ✅ Multi-Select Checkboxen (inkl. "Alle"-Checkbox)
- ✅ Gruppen faltbar/aufklappbar (via `GroupSection.svelte`)
- ✅ `+ Ort` und `+ Gruppe` Button (Callbacks: `onNewLocation`, `onGroupCreated`)
- ✅ Leer-Filter-State (zeigt nur Orte, die zum Filter passen)

Fehlend für #453:
- ❌ Breite: aktuell hardcoded `320px` → muss auf `240px` angepasst werden
- ❌ Min 2 / Max 8 Constraint-Feedback (visuell: Zähler + Warnung)
- ❌ Leerer Zustand (keine Locations) mit Onboarding-Hinweis
- ❌ Drag-Reihenfolge (beeinflusst Spalten-Reihenfolge in Matrix)

### Hilfsfunktionen

- `locationHelpers.ts`: `filterLocations()`, `groupLocations()`, `toKebabCase()`, `isCoordsValid()`
- `GroupSection.svelte`: Gruppen-Header + kollabierbare Locationsliste
- `CreateGroupDialog.svelte`: Dialog zum Erstellen neuer Gruppen

### API

- `GET /api/locations` → alle Locations des Users (Array)
- `GET /api/locations/{id}` → einzelne Location (neu aus #451)
- `POST /api/locations` → neue Location anlegen
- `PUT /api/locations/{id}` → bearbeiten
- `DELETE /api/locations/{id}` → löschen

## Related Files

| Datei | Relevanz |
|-------|----------|
| `frontend/src/lib/components/compare/LocationsRail.svelte` | Zu adaptierende Basiskomponente |
| `frontend/src/lib/components/compare/GroupSection.svelte` | Gruppen-Rendering, unveränderlich |
| `frontend/src/lib/components/compare/CreateGroupDialog.svelte` | Gruppen-Erstellen-Dialog |
| `frontend/src/lib/components/compare/locationHelpers.ts` | filterLocations(), groupLocations() |
| `frontend/src/lib/types.ts` | Location + Group Interface |
| `frontend/src/lib/components/ui/checkbox/` | Checkbox-Komponente |
| `frontend/src/lib/components/ui/pill/` | Chip-Pill-Komponente |
| `frontend/src/lib/components/ui/empty-state/` | Leer-Zustand-Komponente |

## Scope der Änderungen

**Nur Frontend, 1–2 Dateien:**

1. **`LocationsRail.svelte` anpassen:**
   - Breite: `240px` (von `320px`)
   - Neues Prop `maxSelect?: number = 8` und `minSelect?: number = 2`
   - Constraint-Zähler: `{selectedIds.length} von max. {maxSelect} Orten`
   - Warnung wenn < minSelect: roter Hinweis-Text
   - Leerer-Zustand: wenn `locations.length === 0` → EmptyState mit "Ersten Ort anlegen"
   - Drag-and-Drop via HTML5 Drag-Events auf Location-Items (kein externes Package)

2. **Tests:** `__tests__/issue_453_locations_rail.test.ts` (unit, node:test)

## Existing Patterns

- Svelte 5 Runes (`$state`, `$derived`, `$props`)
- Props-only-Komponente (kein eigener API-Call, State liegt auf der Page)
- TestIDs-Konvention: `compare-rail-*`
- Constraint-Feedback-Muster: analog `counterText` in `Step2Orte.svelte`

## Risiken

- Drag-and-Drop: HTML5 API ist mobil-inkompatibel → akzeptabel (Desktop-Planungstool)
- Breiten-Änderung 320→240px bricht keine bestehende Page (Rail wird nirgends genutzt)
- #452 noch offen → NEU-Button-Callback bleibt `onNewLocation`, wird in #455 verdrahtet

## Implementierungsstrategie (Phase 2)

### Dateien & Umfang

| Datei | Typ | LoC |
|-------|-----|-----|
| `LocationsRail.svelte` | Geändert | +35 |
| `GroupSection.svelte` | Geändert | +15 |
| `__tests__/issue_453_locations_rail.test.ts` | Neu | +70 |
| **Total** | **3 Dateien** | **~120 LoC** |

### Architekturentscheidungen

1. **Breite**: `320px` → `240px` direkt (kein Prop — keine bestehenden Consumer)
2. **Drag-State** zentral in `LocationsRail`, Events an `GroupSection` delegiert via `onDragStart`/`onDrop`-Callbacks (Rail bleibt single-scope über beide Listen)
3. **Constraint-Zähler** unter Suchfeld, über Chip-Filter (sofort sichtbar ohne Scrollen)
4. **Max-8 = nur visuelle Warnung** (kein Hard-Block auf Checkboxen, konsistent mit Step2Orte)
5. **onReorder optional** (`?`) — kein Consumer existiert noch → kein TypeScript-Fehler
6. **Tests**: Source-Inspection (node:test), 7 Tests gegen Quelltext der .svelte-Dateien

### Neue Props

```typescript
onReorder?: (sourceId: string, targetId: string) => void;
// GroupSection bekommt zusätzlich:
onDragStart?: (id: string) => void;
onDrop?: (targetId: string) => void;
```

### Implementierungsreihenfolge

1. Test-Datei (RED)
2. GroupSection.svelte (`draggable`-Attribute + Props)
3. LocationsRail.svelte (Breite, EmptyState, Zähler, Drag-State, GroupSection-Aufruf)

## Workflow-Phase

Phase 2 abgeschlossen → weiter mit `/write-spec`

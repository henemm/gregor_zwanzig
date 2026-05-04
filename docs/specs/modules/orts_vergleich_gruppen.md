---
entity_id: orts_vergleich_gruppen
type: module
created: 2026-04-18
updated: 2026-04-18
status: draft
version: "1.0"
tags: [sveltekit, go, frontend, backend, ux, f76, compare, locations]
---

# F76 Phase C4 — Location-Gruppen in Sidebar

## Approval

- [ ] Approved

## Purpose

Locations in der Orts-Vergleich Sidebar koennen einer Gruppe zugeordnet werden (z.B. "Skigebiete Tirol", "Surfspots Portugal"). Die Sidebar zeigt Locations gruppiert mit aufklappbaren Headern. Locations ohne Gruppe erscheinen unter "Ungroupiert".

Teil des UX-Redesigns (#76), Eltern-Spec: `docs/specs/ux_redesign_navigation.md` Abschnitt 3.

## Ist-Zustand

Sidebar zeigt eine flache Liste aller Locations mit Checkboxen:

```
Meine Orte
☑ Alle (5)
☑ Stubaier Gletscher
☑ Hintertux
☑ Axamer Lizum
☑ Nazare
☑ Peniche
[Neuer Ort]
```

## Soll-Zustand

```
Meine Orte
☑ Alle (5)

▼ Skigebiete Tirol
  ☑ Stubaier Gletscher
  ☑ Hintertux
  ☑ Axamer Lizum

▼ Surfspots Portugal
  ☑ Nazare
  ☑ Peniche

[Neuer Ort]
```

- Gruppen sind aufklappbar (Toggle)
- Klick auf Gruppen-Header selektiert/deselektiert alle Orte der Gruppe
- Locations ohne Gruppe erscheinen direkt unter "Alle" (ohne Gruppen-Header)
- Das Group-Feld wird beim Erstellen/Bearbeiten einer Location gesetzt

## Source

- **File:** `internal/model/location.go` **(EDIT, +1 LoC)**
- **File:** `frontend/src/lib/types.ts` **(EDIT, +1 LoC)**
- **File:** `frontend/src/lib/components/LocationForm.svelte` **(EDIT, +15 LoC)**
- **File:** `frontend/src/routes/compare/+page.svelte` **(EDIT, +50 LoC)**

## Aenderungen im Detail

### 1. Backend: Location Model (internal/model/location.go)

```go
Group *string `json:"group,omitempty"`
```

Kein Store-Aenderung noetig — JSON wird 1:1 serialisiert/deserialisiert.

### 2. Frontend: TypeScript Type (frontend/src/lib/types.ts)

```typescript
group?: string;
```

### 3. Frontend: LocationForm (frontend/src/lib/components/LocationForm.svelte)

Neues Input-Feld "Gruppe" (optional, Text) zwischen Name und Koordinaten:

```svelte
<label for="loc-group">Gruppe (optional)</label>
<Input id="loc-group" placeholder="z.B. Skigebiete Tirol" bind:value={group} />
```

### 4. Frontend: Sidebar Gruppierung (frontend/src/routes/compare/+page.svelte)

Derived State fuer gruppierte Locations:

```typescript
let groupedLocations = $derived(() => {
  const groups = new Map<string, Location[]>();
  const ungrouped: Location[] = [];
  for (const loc of locations) {
    if (loc.group) {
      const list = groups.get(loc.group) ?? [];
      list.push(loc);
      groups.set(loc.group, list);
    } else {
      ungrouped.push(loc);
    }
  }
  return { groups, ungrouped };
});
```

Sidebar-Rendering: Gruppen mit Toggle (aufklappbar via `openGroups` Set), Checkboxen pro Location, Ungroupierte Locations darunter.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `ux_redesign_navigation` | spec | Eltern-Spec |
| `orts_vergleich_master_detail` | spec | C1: Sidebar bereits implementiert |
| `internal/model/location.go` | file | Go Location struct |
| `frontend/src/lib/types.ts` | types | Location interface |
| `LocationForm.svelte` | component | Group-Input hinzufuegen |
| `compare/+page.svelte` | file | Sidebar gruppiert rendern |

## Was sich NICHT aendert

- Compare-Logik (selectedIds, runComparison)
- Auto-Reports Section (C3)
- API-Endpunkte (Group wird als normales JSON-Feld mitgeschickt)
- Store-Code (JSON-Serialisierung handled neue Felder automatisch)
- /locations Seite
- /subscriptions Seite

## Expected Behavior

- **Location mit Gruppe:** Erscheint unter dem Gruppen-Header in der Sidebar
- **Location ohne Gruppe:** Erscheint direkt unter "Alle" ohne Header
- **Gruppen-Toggle:** Klick auf Pfeil klappt Gruppe auf/zu
- **Gruppen-Checkbox:** Selektiert/deselektiert alle Locations der Gruppe
- **Neuer Ort:** LocationForm hat optionales Gruppe-Feld
- **Bestehende Locations:** Behalten group=null, erscheinen als ungroupiert

## Known Limitations

- Gruppen-Reihenfolge ist alphabetisch (kein Drag & Drop)
- Gruppen koennen nicht umbenannt werden (nur ueber Location bearbeiten)
- Kein separater "Gruppe erstellen" Dialog — Gruppe entsteht durch Eingabe im LocationForm

## Changelog

- 2026-04-18: Initial spec fuer Phase C4

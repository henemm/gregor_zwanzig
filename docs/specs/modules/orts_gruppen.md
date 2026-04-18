---
entity_id: orts_gruppen
type: module
created: 2026-04-18
updated: 2026-04-18
status: draft
version: "1.0"
tags: [sveltekit, frontend, go, locations, sidebar, ux, f76]
---

# F76 Phase C2 — Orts-Gruppen (Location Groups)

## Approval

- [ ] Approved

## Purpose

Erweitert das Location-Datenmodell um ein optionales Gruppenfeld und zeigt Orte im Compare-Sidebar als aufklappbare Gruppen-Sektionen an. User koennen Orte thematisch buendeln (z.B. "Ski Alpin", "Surfen") und die Vergleichs-Sidebar uebersichtlich auf- und zuklappen, statt durch eine lange, ungrupierte Ortsliste zu scrollen.

Teil des UX-Redesigns (#76), Eltern-Spec: `docs/specs/ux_redesign_navigation.md` (approved, Section 3). Baut auf Phase C1 (Master-Detail Layout, bereits committed) auf.

## Ist-Zustand

- `internal/model/location.go`: `Location`-Struct ohne Gruppenfeld
- `frontend/src/lib/types.ts`: `Location`-Interface ohne `group`
- `LocationForm.svelte`: Kein Gruppen-Eingabefeld
- `compare/+page.svelte`: Flache Ortsliste in der Sidebar (Phase C1)

## Soll-Zustand

```
Sidebar (Compare-Seite)

☑ Alle

▼ ☑ Ski Alpin          ← Gruppe (aufgeklappt, alle selektiert)
    ☑ Stubaier Gletscher
    ☑ Zillertal

▶ ◐ Surfen              ← Gruppe (zugeklappt, teilweise selektiert)

  ☑ Sölden              ← Ohne Gruppe (kein Header, am Ende)
  ☐ Obertauern
```

Alle Orte ohne `group`-Feld erscheinen ohne Gruppen-Header nach allen gruppierten Sektionen. Falls ALLE Orte ungrupiert sind, zeigt die Sidebar eine flache Liste wie in Phase C1 (kein Gruppen-Header).

## Source

- **File:** `internal/model/location.go` **(EDIT, +1 LoC)**
- **File:** `frontend/src/lib/types.ts` **(EDIT, +1 LoC)**
- **File:** `frontend/src/lib/components/LocationForm.svelte` **(EDIT, +15-20 LoC)**
- **File:** `frontend/src/routes/compare/+page.svelte` **(EDIT, +40-60 LoC)**
- **File:** `frontend/src/routes/locations/+page.svelte` **(EDIT, +1 LoC)**

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `ux_redesign_navigation` | spec | Eltern-Spec (approved), Section 3 definiert grupierte Sidebar |
| `nav_redesign_phase_c1` | spec | Vorgaenger-Phase (Master-Detail), bereits committed |
| `internal/model/location.go` | file | Go-Struct fuer Location, erhaelt neues `Group`-Feld |
| `frontend/src/lib/types.ts` | file | TypeScript-Interface fuer Location, erhaelt `group?: string` |
| `LocationForm.svelte` | component | Formular fuer Ort anlegen/bearbeiten, erhaelt Gruppen-Eingabe |
| `compare/+page.svelte` | file | Compare-Seite, Sidebar wird auf Gruppen-Rendering umgebaut |
| `locations/+page.svelte` | file | Locations-Seite, uebergibt `locations`-Prop an LocationForm |
| shadcn-svelte | library | Bestehende Card/Checkbox-Komponenten |
| Lucide Icons | library | `ChevronDown`, `ChevronRight` fuer Auf-/Zuklapp-Indikatoren |

## Implementation Details

### 1. Go-Modell (location.go)

Neues optionales Feld nach `ActivityProfile`, vor `DisplayConfig`:

```go
Group *string `json:"group,omitempty"`
```

Kein Aenderungsbedarf in Handlern, Store oder Validierung — das Feld ist optional und JSON-Serialisierung behandelt `nil` als fehlend (`omitempty`). Bestehende JSON-Dateien ohne `group` deserialisieren zu `nil`.

### 2. TypeScript-Typ (types.ts)

Neues optionales Feld nach `activity_profile`:

```typescript
group?: string;
```

### 3. LocationForm.svelte — Gruppen-Eingabe

Neue optionale Prop:

```svelte
let { location, locations = [] }: { location?: Location; locations?: Location[] } = $props();
```

Neuer State:

```svelte
let group = $state(location?.group ?? '');
```

Einzigartiger Gruppen-Werte fuer Datalist (Autocomplete aus bestehenden Gruppen):

```typescript
const existingGroups = [...new Set(locations.flatMap(l => l.group ? [l.group] : []))].sort();
```

Neues Formularfeld (nach dem bestehenden `name`-Feld, vor dem Submit-Button):

```svelte
<div class="flex flex-col gap-1">
  <label for="group">Gruppe (optional)</label>
  <input
    id="group"
    list="group-options"
    bind:value={group}
    placeholder="z.B. Ski Alpin"
    class="..."
  />
  <datalist id="group-options">
    {#each existingGroups as g}
      <option value={g} />
    {/each}
  </datalist>
</div>
```

In der `save()`-Funktion:

```typescript
group: group.trim() || undefined
```

Leerer String wird zu `undefined` normalisiert, sodass kein `group: ""`-Eintrag in JSON landet.

### 4. Compare-Sidebar (+page.svelte) — Gruppen-Rendering

#### State

```typescript
let collapsedGroups = $state<Set<string>>(new Set());
```

#### Derived: Gruppen-Map

Orte in geordnete Gruppen aufteilen. Ungrupierte Orte kommen zuletzt:

```typescript
const groupedLocations = $derived(() => {
  const map = new Map<string, Location[]>();
  const ungrouped: Location[] = [];
  for (const loc of locations) {
    if (loc.group) {
      const list = map.get(loc.group) ?? [];
      list.push(loc);
      map.set(loc.group, list);
    } else {
      ungrouped.push(loc);
    }
  }
  // Gruppen alphabetisch sortieren
  const sorted = new Map([...map.entries()].sort((a, b) => a[0].localeCompare(b[0])));
  return { groups: sorted, ungrouped };
});
```

#### Hilfsfunktionen

```typescript
function toggleGroup(groupName: string) {
  const next = new Set(collapsedGroups);
  if (next.has(groupName)) next.delete(groupName);
  else next.add(groupName);
  collapsedGroups = next;
}

function groupCheckedState(locs: Location[]): 'all' | 'none' | 'partial' {
  const selected = locs.filter(l => selectedLocations.has(l.id));
  if (selected.length === locs.length) return 'all';
  if (selected.length === 0) return 'none';
  return 'partial';
}

function toggleGroupSelection(locs: Location[], state: 'all' | 'none' | 'partial') {
  const next = new Set(selectedLocations);
  if (state === 'all') locs.forEach(l => next.delete(l.id));
  else locs.forEach(l => next.add(l.id));
  selectedLocations = next;
}
```

#### Template (Desktop-Sidebar und Mobile-Sektion)

Beide Bereiche bekommen identisches Gruppen-Rendering. Gruppen-Header:

```svelte
{#each [...groupedLocations.groups.entries()] as [groupName, locs]}
  {@const state = groupCheckedState(locs)}
  {@const collapsed = collapsedGroups.has(groupName)}

  <!-- Gruppen-Header -->
  <div class="flex items-center gap-2 cursor-pointer select-none"
       onclick={() => toggleGroup(groupName)}>
    {#if collapsed}
      <ChevronRightIcon class="size-4 shrink-0" />
    {:else}
      <ChevronDownIcon class="size-4 shrink-0" />
    {/if}
    <input
      type="checkbox"
      checked={state === 'all'}
      indeterminate={state === 'partial'}
      onclick={(e) => { e.stopPropagation(); toggleGroupSelection(locs, state); }}
    />
    <span class="font-medium text-sm">{groupName}</span>
  </div>

  <!-- Orts-Liste (nur wenn nicht zugeklappt) -->
  {#if !collapsed}
    {#each locs as loc}
      <label class="flex items-center gap-2 pl-6 cursor-pointer">
        <input type="checkbox"
          checked={selectedLocations.has(loc.id)}
          onchange={() => toggleLocation(loc.id)} />
        <span class="text-sm">{loc.name}</span>
      </label>
    {/each}
  {/if}
{/each}

<!-- Ungrupierte Orte (kein Header) -->
{#each groupedLocations.ungrouped as loc}
  <label class="flex items-center gap-2 cursor-pointer">
    <input type="checkbox"
      checked={selectedLocations.has(loc.id)}
      onchange={() => toggleLocation(loc.id)} />
    <span class="text-sm">{loc.name}</span>
  </label>
{/each}
```

"Alle"-Master-Checkbox bleibt unveraendert an der Spitze der Liste.

### 5. locations/+page.svelte — Prop weitergeben

In den Create- und Edit-Dialog-Aufrufen von `LocationForm` wird das `locations`-Prop uebergeben:

```svelte
<LocationForm {location} locations={locations} />
```

## Expected Behavior

- **Input:** User navigiert auf `/compare` (Sidebar) oder `/locations` (Formular)
- **Output (Sidebar):** Orte erscheinen unter ihrem Gruppen-Header; Gruppen sind standardmaessig aufgeklappt; Klick auf Header klappt die Gruppe ein/aus; Gruppen-Checkbox selektiert/deselektiert alle Orte der Gruppe; Indeterminate-Zustand bei Teilauswahl; "Alle"-Checkbox funktioniert weiterhin
- **Output (Formular):** Gruppen-Eingabefeld mit Autocomplete erscheint; bestehende Gruppen-Namen werden als Vorschlaege angeboten; leeres Feld speichert keinen Gruppen-Wert
- **Side effects:** `collapsedGroups`-State ist nur client-seitig (kein Persist); Gruppen-Zustand wird nicht in der URL oder im Server gespeichert

### Randfaelle

| Situation | Verhalten |
|-----------|-----------|
| Alle Orte ungrupiert | Sidebar zeigt flache Liste ohne Gruppen-Header (identisch zu Phase C1) |
| Eine Gruppe + einige ungrupiert | Gruppen-Header fuer die eine Gruppe; ungrupierte Orte darunter ohne Header |
| Gruppe wird vollstaendig geleert | Gruppe verschwindet natuerlich (keine leeren Header) |
| Bestehende JSON-Dateien ohne `group` | Deserialisieren zu `nil`/`undefined` → als ungrupiert behandelt |
| Gruppe zugeklappt, Alle-Checkbox geklickt | "Alle" selektiert/deselektiert auch Orte in zugeklappten Gruppen |
| Gruppen-Name mit Leerzeichen/Sonderzeichen | Wird als reiner String behandelt; kein Encoding noetig |

## Was sich NICHT aendert

- Keine neuen API-Endpunkte — das `group`-Feld reist im bestehenden Location-JSON mit
- Alle anderen Routen (`/trips`, `/subscriptions`, `/settings`) bleiben unveraendert
- Bestehende Location-JSON-Dateien auf dem Server sind rueckwaertskompatibel (optionales Feld)
- Die Sortierung innerhalb einer Gruppe folgt der bestehenden Reihenfolge (keine neue Sortierlogik)
- `compare`-Seite Subscription-Logik, Chart-Rendering und API-Calls bleiben unveraendert

## Known Limitations

- Gruppen-Collapse-Zustand wird nicht persistiert — nach Seitenreload sind alle Gruppen wieder aufgeklappt
- Kein Drag-and-Drop zum Umordnen von Gruppen oder Orte zwischen Gruppen — nur ueber das Edit-Formular
- Gruppen koennen nicht umbenannt werden ohne alle Orte einzeln zu editieren — kein Bulk-Rename

## Risiken

- **Minimal** — 5 Dateien, kein neuer API-Endpunkt, rueckwaertskompatibles Schema-Aenderung
- `indeterminate`-Checkbox-Binding in Svelte 5 (`bind:indeterminate`) muss auf Kompatibilitaet geprueft werden — Fallback: Attribut direkt per DOM setzen falls `bind:` nicht unterstuetzt wird

## Changelog

- 2026-04-18: Initial spec fuer Phase C2 (Orts-Gruppen)

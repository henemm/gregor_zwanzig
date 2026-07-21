---
entity_id: issue_301_sidebar_groups
type: module
created: 2026-05-23
updated: 2026-05-23
status: draft
version: "1.0"
issue: 301
tags: [frontend, svelte, compare, groups, sidebar, group-entity, issue-301, lieferung-a]
---

# Issue #301 Lieferung A — Compare Gruppen-Sidebar: Group-Entity ins Frontend verdrahten

## Approval

- [x] Approved (2026-05-23, PO)

## Purpose

Das Compare-Frontend gruppiert Orte bisher nach dem Legacy-Freitext `Location.group`.
Das Backend hat mit Issue #341 (Commit `be9cca7`, deployed) die `Group`-Entity vollständig
geliefert. Diese Lieferung A verdrahtet das Frontend auf die echte Group-Entity: Typen,
API-Aufruf, Filter-Logik, Sidebar-Elemente und Edit-Dialoge wechseln konsequent von
`loc.group` (Freitext) auf `group_id` + `GET /api/groups`. Sichtbare Ergebnisse:
Sidebar 320 px mit Profil-Dot pro Gruppe, klickbarer Ortsname öffnet Edit-Dialog,
neuer „+ Gruppe"-Button und `CreateGroupDialog`. Lieferung B (AutoReportsOverview-Content)
folgt separat.

## Source

**Schicht: Frontend ausschließlich.** Kein Go-/Python-Backend wird geändert.

- **MODIFY:** `frontend/src/lib/types.ts`
- **MODIFY:** `frontend/src/lib/api.ts`
- **MODIFY:** `frontend/src/routes/compare/+page.server.ts`
- **MODIFY:** `frontend/src/routes/compare/+page.svelte`
- **MODIFY:** `frontend/src/lib/components/compare/LocationsRail.svelte`
- **MODIFY:** `frontend/src/lib/components/compare/locationHelpers.ts`
- **MODIFY:** `frontend/src/lib/components/compare/__tests__/locationHelpers.test.ts`
- **MODIFY:** `frontend/src/lib/components/compare/NewLocationWizard.svelte`
- **MODIFY:** `frontend/src/lib/components/LocationForm.svelte`
- **NEU:** `frontend/src/lib/components/compare/GroupSection.svelte`
- **NEU:** `frontend/src/lib/components/compare/CreateGroupDialog.svelte`

## Dependencies

| Entity | Art | Zweck |
|--------|-----|-------|
| `internal/model/group.go` | Go-Backend (read-only) | Datenmodell-Referenz für TS-Interface `Group` |
| `internal/model/location.go` | Go-Backend (read-only) | `Location.GroupID *string` — Quellfeld für `group_id` |
| `GET /api/groups` | Backend-Endpoint (read-only) | Liefert `Group[]` sortiert nach `order` |
| `POST /api/groups` | Backend-Endpoint | `CreateGroupDialog` legt neue Gruppen an |
| `PATCH /api/locations/{id}` | Backend-Endpoint | Ort zu Gruppe zuweisen (nur `group_id`) |
| `PUT /api/locations/{id}` | Backend-Endpoint | Vollständige Location-Aktualisierung via Edit-Dialog |
| `frontend/src/lib/components/ui/` | Design-System | `Btn`, `Checkbox`, `Pill`, `data-slot`-Muster, `Dot` |
| `profileSignature()` | `frontend/src/lib/utils/profileSignature.ts` | Profil-Dot-Farbe aus `default_profile` — gibt `.accent` = `var(--g-profile-*)` zurück, Fallback `allgemein` |
| `ACTIVITY_PROFILE_OPTIONS` / `ActivityProfile` | `frontend/src/lib/types.ts` | Kanonische Profil-Werte (Unterstrich: `wintersport`/`wandern`/`summer_trekking`/`allgemein`) für Select + default_profile |
| `frontend/src/lib/components/LocationForm.svelte` | Svelte-Komponente | Edit-Dialog-Formular für Ort; bekommt `groups`-Prop |
| `frontend/src/lib/components/compare/NewLocationWizard.svelte` | Svelte-Komponente | Step 2 Gruppen-Auswahl auf `group_id` umstellen |
| E2E `orts-vergleich-c1.spec.ts` / `c4.spec.ts` | Playwright-Tests | Suchen `page.locator('aside')` — Rail muss `<aside>` sein |

## Implementation Details

### 1. `types.ts` — Group-Interface + Location.group_id ergänzen

```typescript
// NEU:
export interface Group {
  id: string;
  name: string;
  default_profile?: ActivityProfile; // kanonisch (Unterstrich): 'wintersport' | 'wandern' | 'summer_trekking' | 'allgemein'
  order: number;
}

// BESTEHEND erweitern (group?: string bleibt, wird nicht entfernt):
export interface Location {
  // ... bestehende Felder ...
  group?: string;      // Legacy — bleibt erhalten, wird nicht mehr gelesen
  group_id?: string;   // NEU — Source of Truth
}
```

### 2. `api.ts` — `patch()`-Methode ergänzen

```typescript
export async function patch<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`/api/${path}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}
```

Der SvelteKit-Proxy (`/api/[...path]/+server.ts`) exportiert PATCH bereits — kein Proxy-Änderung nötig.

### 3. `+page.server.ts` — `/api/groups` parallel laden

```typescript
export const load: PageServerLoad = async ({ fetch }) => {
  const [locations, subscriptions, groups] = await Promise.all([
    fetch('/api/locations').then(r => r.json()),
    fetch('/api/subscriptions').then(r => r.json()),
    fetch('/api/groups').then(r => r.json()),
  ]);
  return { locations, subscriptions, groups };
};
```

### 4. `locationHelpers.ts` — `filterLocations()` auf `group_id` umstellen

```typescript
export function filterLocations(
  locations: Location[],
  search: string,
  activeGroup: string | null,   // group.id statt Gruppenname
  activeProfile: string | null,
  groupNameMap: Map<string, string> // group_id → group.name für Suche im Gruppennamen
): Location[] {
  return locations.filter(loc => {
    if (activeGroup && loc.group_id !== activeGroup) return false;
    if (activeProfile && loc.activity_profile !== activeProfile) return false;
    if (search) {
      const q = search.toLowerCase();
      const groupName = groupNameMap.get(loc.group_id ?? '') ?? '';
      if (!loc.name.toLowerCase().includes(q) && !groupName.toLowerCase().includes(q)) return false;
    }
    return true;
  });
}
```

Bestehende `locationHelpers.test.ts`-Fixtures werden auf `group_id` angepasst.
Keine Mocks — reine Unit-Logik-Tests via Vitest ohne externe Abhängigkeiten.

### 5. `GroupSection.svelte` (NEU)

Rendert eine einzelne klappbare Gruppe in der Sidebar.

**Props:**
```typescript
let {
  group,                          // Group
  locations,                      // Location[] — Mitglieder dieser Gruppe
  open = true,                    // boolean — aufgeklappt/eingeklappt
  onToggle,                       // () => void
  onToggleAll,                    // () => void — Gruppe komplett an/ab
  selectedIds,                    // Set<string>
  onToggleLocation,               // (id: string) => void
  onEditLocation,                 // (loc: Location) => void
}: { ... } = $props();
```

**Layout (Schlüssel-Teile):**

```svelte
<div class="group-section" data-testid="group-section-{group.id}">
  <!-- Header -->
  <button class="group-header" onclick={onToggle} aria-expanded={open}>
    <span class="chevron" class:open>{/* SVG */}</span>
    <Checkbox
      checked={allSelected}
      indeterminate={someSelected && !allSelected}
      onchange={onToggleAll}
    />
    <!-- Profil-Dot: Farbe via profileSignature() (KEIN manueller Token-Bau) -->
    <span data-slot="dot" style="background: {profileSignature(group.default_profile).accent}"></span>
    <span class="group-name">{group.name}</span>
    <span class="group-count" data-testid="group-count-{group.id}">{locations.length}</span>
  </button>

  <!-- Ortsliste (sichtbar wenn open) -->
  {#if open}
    <ul class="location-list">
      {#each locations as loc (loc.id)}
        <li class="location-row">
          <Checkbox
            checked={selectedIds.has(loc.id)}
            onchange={() => onToggleLocation(loc.id)}
          />
          <!-- Klickbarer Ortsname → Edit-Dialog -->
          <button
            class="loc-name-btn"
            onclick={() => onEditLocation(loc)}
            data-testid="loc-name-{loc.id}"
          >{loc.name}</button>
          <!-- Wetter-Icon (bestehend) -->
        </li>
      {/each}
    </ul>
  {/if}
</div>
```

Die Dot-Farbe kommt aus `profileSignature(group.default_profile).accent` (Import aus
`$lib/utils/profileSignature`); diese liefert bereits `var(--g-profile-*)` und fällt bei
unbekanntem/leerem Profil auf `allgemein` zurück. **Kein manueller Token-Bau, kein
`.replace()`** — die Profil-Werte sind die kanonischen `ActivityProfile` (Unterstrich
`summer_trekking`), sonst greift der Fallback fälschlich. Keine Hex-Literale (AP-007),
nur `--g-s-*` Spacing-Tokens (AP-008), keine Emojis (AP-009).

### 6. `CreateGroupDialog.svelte` (NEU)

Dialog für neues Gruppen-Anlegen. Pattern: `Dialog.Root` wie `SavePresetDialog.svelte`.

**Props:**
```typescript
let { open = $bindable(false), onCreate }: {
  open: boolean;
  onCreate: (group: Group) => void;
} = $props();
```

**Formular-Felder:**
- Name-Input (required, max 80 Zeichen), `data-testid="create-group-name"`
- optional: Profil-Auswahl über die **`Select`-Komponente** (`$lib/components/ui/select`) — **KEIN natives `<select>`** (Projekt-Regel Issue #278, durch `test_issue_278_form_controls.py` erzwungen). Optionen aus `ACTIVITY_PROFILE_OPTIONS` (`$lib/types`), kanonische Unterstrich-Werte; `data-testid="create-group-profile"`
- Fehler-State: `<p class="error-msg" data-testid="create-group-error">` — sichtbar wenn Backend-Fehler (z.B. doppelter Name → gleiche kebab-ID → 409-Response)

**Submit:**
```typescript
async function submit() {
  error = '';
  try {
    const group = await api.post<Group>('groups', { name, default_profile: profile || undefined });
    onCreate(group);
    open = false;
  } catch (e) {
    error = (e as Error).message;
  }
}
```

### 7. `LocationsRail.svelte` — Umbau

- `<div class="w-60 ...">` → `<aside style="width: 320px; ...">` (E2E-Pflicht)
- Gruppen-Render: `{#each groups as group}` → `<GroupSection {group} locations={groupedMap.get(group.id) ?? []} .../>`
- Ungruppiert-Bucket (nur gerendert wenn `ungroupedLocations.length > 0`, immer zuletzt):
  ```svelte
  {#if ungroupedLocations.length > 0}
    <div class="ungroup-section" data-testid="ungroup-section">
      <!-- Orte ohne group_id, inline analog GroupSection ohne Profil-Dot -->
    </div>
  {/if}
  ```
- Footer: `+ NEU`-Btn (bestehend) + `+ Gruppe`-Btn (NEU) → öffnet `CreateGroupDialog`

```svelte
<!-- Footer -->
<div class="rail-footer">
  <Btn variant="ghost" onclick={onNewLocation}>+ Ort</Btn>
  <Btn variant="ghost" onclick={() => createGroupOpen = true}>+ Gruppe</Btn>
</div>
<CreateGroupDialog bind:open={createGroupOpen} onCreate={handleGroupCreated} />
```

### 8. `+page.svelte` — Verdrahtung

- `groupedLocations` ($derived): `Map<string, Location[]>` via `group_id` aus `groups`-Array (nach `order` sortiert)
- `openGroups` Init: `new Set(groups.map(g => g.id))` statt Gruppen-String-Namen
- Edit-Dialog für Orte:
  ```svelte
  <!-- Dialog.Root für Location-Bearbeitung -->
  {#if editingLocation}
    <Dialog.Root bind:open={locationEditOpen}>
      <LocationForm
        location={editingLocation}
        groups={data.groups}
        onSave={handleLocationSave}
        onCancel={() => locationEditOpen = false}
      />
    </Dialog.Root>
  {/if}
  ```
- `handleLocationSave`: `PUT /api/locations/{id}` mit vollem Location-Body inkl. `group_id`, danach `invalidateAll()`

### 9. `NewLocationWizard.svelte` — Step 2 auf group_id

```svelte
<!-- ALT: <datalist> Freitext -->
<!-- NEU: Select-Komponente (KEIN natives <select>, Issue #278) -->
<Select bind:value={selectedGroupId} data-testid="wizard-group-select">
  <!-- "Keine Gruppe" + {#each groups as g} Optionen -->
</Select>
```

Submit (Step 2 → POST): sendet `group_id: selectedGroupId || undefined` statt `group: groupText`.

`groups`-Prop kommt aus `+page.svelte` (bereits aus `load()` verfügbar).

### 10. `LocationForm.svelte` — Group-Select statt Freitext

```svelte
<!-- Groups-Select (NEU): Select-Komponente, KEIN natives <select> (Issue #278) -->
<Select bind:value={form.group_id} data-testid="location-form-group">
  <!-- "Keine Gruppe" + {#each groups as g} Optionen -->
</Select>
```

`groups: Group[]` als neue Prop, optional (Default `[]`); Legacy-`group`-Feld wird beim Speichern nicht mitgesendet (Backend-Merge setzt nur was im Body steht, `group_id` reicht).

## Expected Behavior

- **Input:** Geladene `locations: Location[]`, `groups: Group[]` (sortiert nach `order`), `subscriptions: CompareSubscription[]`
- **Output:**
  - Sidebar `<aside>` 320 px; Gruppen aus `/api/groups` sortiert nach `order`; pro Gruppe: Profil-Dot + Name + Count + klappbare Ortsliste
  - Orte ohne `group_id` erscheinen in „Ungruppiert"-Sektion (nur wenn vorhanden, immer zuletzt)
  - Klick auf Ortsname öffnet Edit-Dialog mit `LocationForm` (Group-Select auf Group-Entities); Speichern via `PUT`
  - „+ Gruppe"-Button öffnet `CreateGroupDialog`; neu angelegte Gruppe erscheint sofort in der Sidebar
  - `NewLocationWizard` sendet `group_id` statt Freitext `group`
  - Suche filtert nach Ortsname UND Gruppenname (via `groupNameMap`)
  - Bestehende Orts-/Gruppen-Daten bleiben erhalten (keine verschwundenen Orte, keine Datenverluste)
- **Side effects:**
  - `POST /api/groups` → neue Gruppe im Backend; `invalidateAll()` holt aktualisierten Stand
  - `PUT /api/locations/{id}` → `group_id` persistiert; bestehende Felder bleiben via Read-Modify-Write erhalten
  - `PATCH /api/locations/{id}` bleibt für Drag-Move reserviert (kein neuer Trigger in Lieferung A)

## Acceptance Criteria

**AC-1:** Given die Compare-Seite lädt und `/api/groups` liefert Gruppen /
When die Sidebar gerendert wird /
Then ist der Wrapper ein `<aside>`-Element mit einer Breite von 320 px und die Gruppen erscheinen sortiert nach ihrem `order`-Wert mit Chevron + Checkbox + Profil-Dot + Name + Count.

**AC-2:** Given eine Gruppe hat `default_profile='summer_trekking'` (kanonisch, Unterstrich) /
When die GroupSection gerendert wird /
Then trägt der Profil-Dot die Farbe aus `profileSignature('summer_trekking').accent` (= `var(--g-profile-summer-trekking)`); kein Hex-Literal, kein Emoji, kein Magic-Pixel-Wert.

**AC-3:** Given ein Ort hat keine `group_id` /
When die Sidebar gerendert wird /
Then erscheint der Ort in einem „Ungruppiert"-Bucket (`data-testid="ungroup-section"`) am Ende der Liste; sind alle Orte einer Gruppe zugewiesen, ist der Bucket nicht sichtbar.

**AC-4:** Given die Suche ist aktiv und ein Suchbegriff trifft den Gruppenname, nicht den Ortsnamen /
When `filterLocations()` aufgerufen wird /
Then werden alle Orte dieser Gruppe in der Sidebar zurückgegeben.

**AC-5:** Given ein Ortsname in der Sidebar wird angeklickt (nicht die Checkbox, nicht der Wetter-Button) /
When der Klick erfolgt /
Then öffnet sich ein Dialog mit `LocationForm`; der Form-Select für die Gruppe zeigt die vorhandenen Group-Entities; nach dem Speichern ist die neue `group_id` via `PUT /api/locations/{id}` persistiert.

**AC-6:** Given der User klickt „+ Gruppe" im Sidebar-Footer /
When der `CreateGroupDialog` geöffnet wird und ein Name eingegeben und bestätigt wird /
Then sendet der Dialog `POST /api/groups` und die neue Gruppe erscheint danach in der Sidebar; bei doppeltem Namen (gleiche kebab-ID) zeigt der Dialog eine Fehlermeldung in `data-testid="create-group-error"`.

**AC-7:** Given der User legt einen neuen Ort via `NewLocationWizard` an und wählt in Step 2 eine Gruppe /
When der Wizard abschickt /
Then enthält der `POST /api/locations`-Body `group_id` (nicht `group`), und der Ort erscheint in der richtigen Gruppe.

**AC-8:** Given das Frontend wechselt von `loc.group` auf `loc.group_id` /
When die Lazy-Migration im Backend (`migrateGroups()`) alle Bestandsorte bei `/api/groups`-Abruf backfüllt /
Then sind alle Orte nach dem Reload ihrer bisherigen Gruppe zugeordnet; kein Ort ist unbeabsichtigt in „Ungruppiert" gelandet.

**AC-9:** Given `openGroups` wird initialisiert /
When die Seite erstmalig lädt /
Then sind alle Gruppen aufgeklappt (`openGroups = new Set(groups.map(g => g.id))`); manuelles Einklappen und Ausklappen per Klick auf den Gruppen-Header funktioniert.

**AC-10:** Given `api.patch()` wird mit Pfad und Body aufgerufen /
When der Proxy `/api/[...path]/+server.ts` die PATCH-Methode empfängt /
Then wird der Request korrekt weitergeleitet und das aktualisierte Objekt zurückgegeben; kein 405-Fehler.

## Affected Files

| Datei | Änderung | LoC (netto) |
|-------|---------|-------------|
| `frontend/src/lib/types.ts` | `Group`-Interface (NEU) + `Location.group_id?: string` | ~10 |
| `frontend/src/lib/api.ts` | `patch()`-Methode ergänzen | ~8 |
| `frontend/src/routes/compare/+page.server.ts` | `/api/groups` parallel laden | ~5 |
| `frontend/src/routes/compare/+page.svelte` | `groupedLocations`-Derived auf `group_id`, `openGroups`-Init, Edit-Dialog-Verdrahtung | ~35 |
| `frontend/src/lib/components/compare/LocationsRail.svelte` | `<aside>` 320px, GroupSection/Ungruppiert-Render, „+ Gruppe"-Footer | ~40 |
| `frontend/src/lib/components/compare/GroupSection.svelte` | NEU — klappbarer Gruppen-Header + Ortsliste mit Edit-Trigger | ~50 |
| `frontend/src/lib/components/compare/CreateGroupDialog.svelte` | NEU — Dialog mit Name-Input, Profil-Select, Error-State | ~40 |
| `frontend/src/lib/components/compare/locationHelpers.ts` | `filterLocations()` auf `group_id` + `groupNameMap` | ~20 |
| `frontend/src/lib/components/compare/__tests__/locationHelpers.test.ts` | Fixtures auf `group_id` anpassen + 2 neue Tests (Suche via Gruppenname) | ~20 |
| `frontend/src/lib/components/compare/NewLocationWizard.svelte` | Step 2: `<select>` auf Group-Entities statt Freitext, sendet `group_id` | ~10 |
| `frontend/src/lib/components/LocationForm.svelte` | `groups`-Prop + Group-`<select>` statt Freitext | ~10 |

**Gesamt: ~248 LoC netto, 9 Dateien geändert / 2 neu**

## Known Limitations

- **Drag-&-Drop zwischen Gruppen:** Ort zu anderer Gruppe verschieben via Drag ist Out of Scope. Zuweisung ausschließlich via Edit-Dialog oder NewLocationWizard. `PATCH /api/locations/{id}` bleibt für zukünftige Drag-Move-Implementierung reserviert.
- **Profil-Variable-Slot:** `--g-profile-{slug}` muss im Design-System (`app.css`) für alle 4 Profile definiert sein. Ist ein Profil-Token undefiniert, fällt der Dot auf die CSS-Fallback-Farbe (transparent/inherit). Diese Spec setzt voraus, dass die Tokens bereits existieren — kein neues Token wird angelegt.
- **Group-Edit/Umbenennen:** `PATCH /api/groups/{id}` und `DELETE /api/groups/{id}` werden in Lieferung A nicht per UI exponiert. Gruppen können angelegt, aber nicht umbenannt oder gelöscht werden. Das ist ein bewusster Scope-Cut.
- **AutoReportsOverview:** Lieferung B — Content-Bereich bleibt `CompareSubscriptionsPanel` unverändert.
- **Lazy-Migration-Timing:** Bestehende Orte erhalten ihre `group_id` erst beim ersten `/api/groups`-Call. Wenn `+page.server.ts` `/api/groups` und `/api/locations` parallel fetcht, kann die Migration beim ersten Seiten-Load noch laufen. Bei erneutem Laden ist sie abgeschlossen. Kein Workaround nötig — der Store garantiert Idempotenz der Migration.

## Changelog

- 2026-05-23: Initial spec erstellt — Lieferung A, Group-Entity-Verdrahtung im Compare-Frontend (Issue #301, nach Backend #341).
- 2026-05-23: Korrektur nach Adversary-QA — alle Selects nutzen die `Select`-Komponente (`$lib/components/ui/select`), KEIN natives `<select>` (Issue #278, `test_issue_278_form_controls.py`). Betrifft CreateGroupDialog/NewLocationWizard/LocationForm.

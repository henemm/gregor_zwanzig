---
entity_id: issue_249_locations_rail
type: module
created: 2026-05-19
updated: 2026-05-19
status: draft
version: "1.0"
tags: [compare, locations, frontend, wizard, rail]
---

# Issue #249 — Compare-Screen: LocationsRail + NewLocationWizard

## Approval

- [ ] Approved

## Purpose

Extrahiert die Location-Sidebar des Compare-Screens in eine eigenständige Komponente
`LocationsRail.svelte` und ersetzt den bestehenden `LocationForm`-Dialog durch einen
3-stufigen `NewLocationWizard.svelte`. Die Extraktion trennt Darstellungs-Logik
(Rail-Rendering, Suche, Chip-Filter) von der Page-State-Verwaltung sauber voneinander
und schafft die Basis für künftige Erweiterungen (URL-Import via Issue #248, Bulk-Select).

Gleichzeitig wird das `Location`-Interface in `types.ts` um drei optionale Felder
(`timezone`, `data_source`, `created_at`) ergänzt, die das Go-Backend seit Issue #247
liefert und die der Frontend-Typ bisher nicht abbildet.

## Source

- **Files:**
  - `frontend/src/lib/components/compare/LocationsRail.svelte` (NEU)
  - `frontend/src/lib/components/compare/NewLocationWizard.svelte` (NEU)
  - `frontend/src/lib/types.ts` (geändert, +3 Felder)
  - `frontend/src/routes/compare/+page.svelte` (geändert, Sidebar + Dialog ersetzt)

## Dependencies

| Abhängigkeit | Art | Zweck |
|---|---|---|
| `frontend/src/lib/components/trip-wizard/Stepper.svelte` | Svelte-Komponente (vorhanden) | Schritt-Indikator (Schritte 1–3) im NewLocationWizard |
| `frontend/src/lib/components/ui/dialog/` | UI-Bibliothek (vorhanden) | Dialog-Root, DialogContent, DialogHeader, DialogFooter |
| `frontend/src/lib/components/ui/pill/Pill.svelte` | UI-Komponente (vorhanden) | Chip-Filter-Buttons in der Rail |
| `frontend/src/lib/types.ts` | TypeScript-Interface | Location-Interface — wird erweitert; enthält auch `ACTIVITY_PROFILE_OPTIONS` |
| `frontend/src/lib/api.ts` | Utility (vorhanden) | `api.post('/api/locations', loc)` zum Persistieren neuer Locations |
| `POST /api/locations` | Go-Backend-Endpoint | Speichert neue Location; existiert bereits |
| `POST /api/locations/resolve` | Go-Backend-Endpoint (Issue #248) | Optionale Dep — noch nicht implementiert; Fallback: manuelle Koordinateneingabe |

## Scope

**Nur Frontend.** 4 Dateien:

- **Neu:** `frontend/src/lib/components/compare/LocationsRail.svelte`
- **Neu:** `frontend/src/lib/components/compare/NewLocationWizard.svelte`
- **Geändert:** `frontend/src/lib/types.ts` (+3 optionale Felder in `Location`)
- **Geändert:** `frontend/src/routes/compare/+page.svelte` (Sidebar + Dialog ersetzt durch neue Komponenten)

Keine Änderungen an:
- `Stepper.svelte`, `Pill.svelte`, Dialog-Komponenten — werden unverändert wiederverwendet
- Go-Backend — `POST /api/locations` existiert bereits
- `api.ts` — keine neuen Methoden erforderlich

## Implementation Details

### types.ts — Erweiterung Location-Interface

Drei optionale Felder werden am Ende des `Location`-Interface ergänzt:

```typescript
export interface Location {
  // ... bestehende Felder unverändert ...
  timezone?: string;       // z.B. "Europe/Vienna"
  data_source?: string;    // z.B. "geosphere", "manual"
  created_at?: string;     // ISO-8601-String, server-seitig gesetzt
}
```

Keine Breaking Changes — alle neuen Felder sind optional mit `?`.

### LocationsRail.svelte

Props-Interface:

```typescript
interface Props {
    locations: Location[];
    selectedIds: string[];
    groupedLocations: { groups: Map<string, Location[]>; ungrouped: Location[] };
    openGroups: Set<string>;
    allSelected: boolean;
    onToggleAll: () => void;
    onToggleLocation: (id: string) => void;
    onToggleGroup: (name: string) => void;
    onToggleGroupSelection: (name: string) => void;
    onShowWeather: (id: string) => void;
    onNewLocation: () => void;
}
```

Lokaler State (nur in der Rail, nicht nach außen gehoben):

```typescript
let search = $state('');
let activeGroup = $state<string | null>(null);
```

Gefilterte Location-Liste via `$derived`:

```typescript
let filteredLocations = $derived(
    locations.filter(l =>
        (search === '' || l.name.toLowerCase().includes(search.toLowerCase()) ||
         (l.group ?? '').toLowerCase().includes(search.toLowerCase())) &&
        (activeGroup === null || l.group === activeGroup)
    )
);
```

Struktur der Komponente von oben nach unten:

1. **Suchfeld** — `<input type="search">` bindet `search`; filtert client-seitig via `filteredLocations`
2. **Chip-Gruppen-Filter** — `{#each [...groupedLocations.groups.keys()] as g}` → `<Pill tone={activeGroup === g ? 'accent' : 'default'} onclick={...}>`. Klick auf aktiven Chip setzt `activeGroup = null` (Filterung aufheben).
3. **"Alle auswählen"-Checkbox** mit Zähler `({selectedIds.length}/{locations.length})`
4. **Gruppen-Blöcke** — für jede Gruppe in `groupedLocations.groups`:
   - Gruppen-Header: Expand/Collapse-Button (`openGroups.has(name)`) + Gruppen-Checkbox (ruft `onToggleGroupSelection(name)`) + Gruppen-Name + Zähler `({n})`
   - Indentierte Location-Zeilen (nur wenn Gruppe offen): Checkbox (ruft `onToggleLocation(id)`) + Name + Wetter-Icon-Button (ruft `onShowWeather(id)`)
5. **Ungrouped Locations** — aus `groupedLocations.ungrouped`, gleiche Zeilen-Struktur ohne Einrückung
6. **"+ NEU"-Button** — `<button>` mit `onclick={onNewLocation}`, positioniert am unteren Rand der Rail

### NewLocationWizard.svelte

Props-Interface:

```typescript
interface Props {
    locations: Location[];   // für existierende Gruppen-Suggestions via <datalist>
    onsave: (loc: Location) => void;
    oncancel: () => void;
}
```

Lokaler State:

```typescript
let step = $state<1 | 2 | 3>(1);
let lat = $state(47.0);
let lon = $state(11.0);
let elevationM = $state<number | undefined>(undefined);
let name = $state('');
let group = $state('');
let activityProfile = $state<ActivityProfile>('allgemein');
let saving = $state(false);
let error = $state<string | null>(null);
```

**Schritt 1 — Verortung:**

- Lat/Lon-Eingabefelder (nummerisch, Pflicht)
- Höhe über NN optional (`elevationM`)
- Hinweistext: "URL-Import folgt in einem Update" — kein interaktives Element, da Issue #248 noch nicht implementiert ist
- Validierung vor "Weiter": `lat !== 0 || lon !== 0` (nicht beide Null)

**Schritt 2 — Benennung:**

- Name-Feld (`<Input>`, Pflicht, mindestens 1 Zeichen)
- Gruppe-Feld: `<input list="group-opts">` mit `<datalist id="group-opts">` aus bestehenden Gruppen (`[...new Set(locations.map(l => l.group).filter(Boolean))]`)
- Freie Texteingabe erzeugt automatisch eine neue Gruppe, wenn kein Match in `datalist` — kein separates UI nötig
- Validierung vor "Weiter": `name.trim().length > 0`

**Schritt 3 — Aktivitätsprofil:**

- `{#each ACTIVITY_PROFILE_OPTIONS as opt}` → Card-Element mit `data-selected={activityProfile === opt.value}`
- Grid-Layout 2×2
- Klick setzt `activityProfile = opt.value`
- Kein Icon in v1 — nur Label (+ optionale kurze Beschreibung aus `ACTIVITY_PROFILE_OPTIONS`)

**Footer-Logik (alle Schritte):**

- Links: "Abbrechen" wenn `step === 1`, sonst "Zurück" (dekrementiert `step`)
- Rechts: "Weiter" wenn `step < 3` (inkrementiert `step` nach Validierung), "Speichern" wenn `step === 3`

**Speichern-Funktion (Schritt 3):**

```typescript
async function save() {
    saving = true;
    error = null;
    try {
        const loc: Location = {
            id: toKebabCase(name),
            name: name.trim(),
            lat: Number(lat),
            lon: Number(lon),
            elevation_m: elevationM,
            group: group.trim() || undefined,
            activity_profile: activityProfile,
        };
        await api.post('/api/locations', loc);
        onsave(loc);
    } catch (e: unknown) {
        error = e instanceof Error ? e.message : 'Fehler beim Speichern';
    } finally {
        saving = false;
    }
}
```

`toKebabCase(name)` ist eine lokale Hilfsfunktion: Leerzeichen → `-`, Kleinbuchstaben, Sonderzeichen entfernen.

**Stepper-Integration:**

```svelte
<Stepper current={step as 1|2|3|4} labels={['Verortung', 'Benennung', 'Aktivitätsprofil']} />
```

### compare/+page.svelte — Änderungen

**Sidebar ersetzen** (bisheriger `<aside>`-Block, ~Zeilen 284–345):

```svelte
<LocationsRail
    {locations}
    {selectedIds}
    {groupedLocations}
    {openGroups}
    {allSelected}
    onToggleAll={toggleAll}
    onToggleLocation={toggleLocation}
    onToggleGroup={toggleGroup}
    onToggleGroupSelection={toggleGroupSelection}
    onShowWeather={showWeather}
    onNewLocation={() => (showNewLocDialog = true)}
/>
```

**Dialog-Inhalt ersetzen** (bisheriger `<LocationForm .../>` im Dialog):

```svelte
<NewLocationWizard
    {locations}
    onsave={handleNewLocSave}
    oncancel={() => (showNewLocDialog = false)}
/>
```

`handleNewLocSave(loc)` fügt die neue Location zur lokalen `locations`-Liste hinzu und schließt den Dialog: `locations = [...locations, loc]; showNewLocDialog = false;`

Gruppen-State (`groupedLocations`, `openGroups` und alle Toggle-Funktionen) verbleibt in der Page — er steuert die Rail via Props.

**Neue Imports in der Page:**

```typescript
import LocationsRail from '$lib/components/compare/LocationsRail.svelte';
import NewLocationWizard from '$lib/components/compare/NewLocationWizard.svelte';
```

## Expected Behavior

- **Input (LocationsRail):** `locations[]` + `selectedIds[]` + Gruppen-State + Callback-Props
- **Input (NewLocationWizard):** `locations[]` (für Gruppen-Suggestions) + `onsave` + `oncancel`
- **Output (LocationsRail):** Gefilterte, gruppierte Locations-Liste als Sidebar; kein eigener API-Aufruf
- **Output (NewLocationWizard):** Nach "Speichern" ruft `onsave(loc)` mit dem neuen Location-Objekt auf; die Page ergänzt die Liste und schließt den Dialog
- **Side effects:** `NewLocationWizard` ruft `api.post('/api/locations', loc)` auf — persistiert die neue Location im Backend. `LocationsRail` hat keine eigenen Side Effects.

## Acceptance Criteria

**AC-1:** Given mindestens eine gespeicherte Location mit der Gruppe "Zillertal" / When die LocationsRail gerendert wird / Then erscheint ein Gruppen-Header mit dem Text "Zillertal (N)" (N = Anzahl der Locations in dieser Gruppe), einer Gruppen-Checkbox und einem Expand/Collapse-Button; bei geöffneter Gruppe sind darunter alle Locations der Gruppe mit eigener Checkbox aufgelistet.

**AC-2:** Given ein Suchbegriff wird in das Rail-Suchfeld eingegeben / When der User Text tippt / Then werden nur die Locations angezeigt, deren Name oder Gruppenname den eingegebenen Begriff enthält — Groß- und Kleinschreibung wird dabei ignoriert.

**AC-3:** Given der Gruppen-Chip-Filter zeigt mehrere Gruppen an / When ein Chip ausgewählt wird / Then werden nur Locations der gewählten Gruppe angezeigt; ein erneuter Klick auf denselben Chip hebt die Filterung auf und zeigt wieder alle Locations.

**AC-4:** Given der User klickt den "+ NEU"-Button in der Rail / When der Dialog öffnet / Then ist ein Stepper mit drei Schritten "Verortung", "Benennung", "Aktivitätsprofil" sichtbar und Schritt 1 ist aktiv markiert.

**AC-5:** Given Schritt 1 des NewLocationWizard ist ausgefüllt mit gültigen Koordinaten (lat und lon nicht beide 0) / When der User auf "Weiter" klickt / Then wechselt der Stepper-Indikator zu Schritt 2 (Benennung) und das Benennung-Formular wird angezeigt.

**AC-6:** Given Schritt 3 des NewLocationWizard ist erreicht und ein Aktivitätsprofil ist ausgewählt / When der User auf "Speichern" klickt / Then wird die neue Location via `POST /api/locations` im Backend gespeichert und erscheint unmittelbar danach in der LocationsRail der Compare-Page.

## Affected Files

| Datei | Änderung |
|-------|---------|
| `frontend/src/lib/types.ts` | +3 optionale Felder in `Location`: `timezone?`, `data_source?`, `created_at?` |
| `frontend/src/lib/components/compare/LocationsRail.svelte` | NEU — Sidebar mit Suchfeld, Chip-Filter, Gruppen, Multi-Select |
| `frontend/src/lib/components/compare/NewLocationWizard.svelte` | NEU — 3-Schritt-Dialog-Wizard für neue Locations |
| `frontend/src/routes/compare/+page.svelte` | `<aside>` → `<LocationsRail>`, `<LocationForm>` → `<NewLocationWizard>` |

## LoC Estimate

~180 LoC gesamt (LocationsRail ~90, NewLocationWizard ~80, types.ts +3, +page.svelte Netto ~+5 durch Extraktion).

## Known Limitations

- **URL-Import (Issue #248):** Schritt 1 enthält einen Hinweistext, aber kein funktionales Eingabefeld für URLs. Der `POST /api/locations/resolve`-Endpoint ist noch nicht implementiert. Wird in einem Folge-Issue nachgerüstet.
- **id-Generierung:** `toKebabCase(name)` ist clientseitig — bei identischem Namen kann es zu Kollisionen kommen. Das Backend muss ggf. eine ID-Kollision mit einem 409-Fehler zurückmelden; der Wizard zeigt diesen als `error`-State an.
- **Stepper-Props:** `Stepper.svelte` erwartet `current: 1|2|3|4` — Schritt 4 wird in diesem Wizard nie gesetzt; der Subtyp `1|2|3` ist kompatibel.

## Changelog

- 2026-05-19: Initial spec erstellt (Issue #249 — LocationsRail + NewLocationWizard).

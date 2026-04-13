---
entity_id: sveltekit_locations
type: module
created: 2026-04-13
updated: 2026-04-13
status: draft
version: "1.0"
tags: [migration, sveltekit, frontend, locations]
---

# M3b: Locations Page (SvelteKit)

## Approval

- [ ] Approved

## Purpose

Locations CRUD als SvelteKit-Page implementieren. Ersetzt NiceGUI `locations.py` (259 LOC). Folgt dem M3a-Pattern (Trips) mit vereinfachtem Form (flaches Modell, keine verschachtelten Objekte).

## Scope

### In Scope

- Locations-Tabelle (Name, Koordinaten, Hoehe, Activity Profile Badge)
- Create Dialog mit LocationForm (Name, Lat, Lon, Elevation, Region, Bergfex Slug, Activity Profile)
- Edit Dialog (vorausgefuellt, ID readonly)
- Delete mit Bestaetigungsdialog
- Activity Profile Dropdown (wintersport/wandern/allgemein)
- ID auto-generiert aus Name (kebab-case) bei Create
- Server-side Load mit Cookie-Forwarding

### Out of Scope

- Weather-Metriken Dialog (eigenes Feature)
- DMS-Koordinaten-Parser (spaeter)
- Karten-Integration (spaeter)
- display_config Bearbeitung (wird preserved aber nicht exponiert)

## Architecture

```
/locations
  +page.server.ts: fetch locations[] von Go API
  +page.svelte: Table + Dialog-Orchestrierung
    |
    +-- LocationForm.svelte (shared Create/Edit)
          Name, Lat, Lon, Elevation, Region, Bergfex Slug
          Activity Profile <select>
          Save -> onsave callback
    |
    +-- Delete Confirmation Dialog
```

### Datenfluss

Identisch zu M3a:
- SSR: `+page.server.ts` -> `fetch('http://localhost:8090/api/locations')` mit Cookie
- Client Mutations: `api.post/put/del('/api/locations/...')` via SvelteKit Proxy Route

## Source

### Neue Dateien

| Datei | Zweck | ~LOC |
|-------|-------|------|
| `frontend/src/routes/locations/+page.server.ts` | Load Locations Array | ~16 |
| `frontend/src/routes/locations/+page.svelte` | Tabelle + Dialog-Steuerung | ~145 |
| `frontend/src/lib/components/LocationForm.svelte` | Flat Form (7 Felder + Select) | ~120 |

### Geaenderte Dateien

Keine. TypeScript `Location` Interface, Layout-Navigation und API-Proxy existieren bereits.

### Gesamt: 3 Dateien, ~280 LOC

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| SvelteKit Setup (M2) | Foundation | Auth, Layout, API Client, Types |
| Go Location CRUD (M1f) | API | GET/POST/PUT/DELETE /api/locations |
| M3a Dashboard+Trips | Pattern | Dialog, Table, Form Pattern zum Kopieren |
| shadcn-svelte | Library | Button, Dialog, Input, Label, Badge, Table (bereits installiert) |

## Implementation Details

### LocationForm.svelte

Props:
```typescript
interface Props {
  location?: Location;   // undefined = Create, defined = Edit
  onsave: (loc: Location) => void;
  oncancel: () => void;
}
```

State (Svelte 5 Runes):
```typescript
let name = $state(location?.name ?? '');
let lat = $state(location?.lat ?? 47.0);
let lon = $state(location?.lon ?? 11.0);
let elevationM = $state(location?.elevation_m ?? 2000);
let region = $state(location?.region ?? '');
let bergfexSlug = $state(location?.bergfex_slug ?? '');
let activityProfile = $state(location?.activity_profile ?? '');
```

ID-Generierung (nur Create):
```typescript
function toKebab(s: string): string {
  return s.trim().toLowerCase().replace(/[^a-z0-9äöüß]+/g, '-').replace(/^-|-$/g, '');
}
```

Number Coercion (WICHTIG):
```typescript
function save() {
  const result: Location = {
    id: location?.id ?? toKebab(name),
    name: name.trim(),
    lat: Number(lat),
    lon: Number(lon),
    elevation_m: Number(elevationM) || undefined,
    region: region.trim() || undefined,
    bergfex_slug: bergfexSlug.trim() || undefined,
    activity_profile: activityProfile || undefined,
    ...(location?.display_config && { display_config: location.display_config }),
  };
  onsave(result);
}
```

Activity Profile als plain `<select>`:
```svelte
<select bind:value={activityProfile} class="...tailwind...">
  <option value="">— Kein Profil —</option>
  <option value="wintersport">Wintersport</option>
  <option value="wandern">Wandern</option>
  <option value="allgemein">Allgemein</option>
</select>
```

### Locations Table Spalten

| Spalte | Inhalt |
|--------|--------|
| Name | `location.name` |
| Koordinaten | `{lat.toFixed(4)}, {lon.toFixed(4)}` |
| Hoehe | `{elevation_m ?? '—'} m` |
| Profil | Badge (nur wenn gesetzt) |
| Aktionen | Bearbeiten, Loeschen Buttons |

## Expected Behavior

### Locations (/locations)

- **Liste:** Tabelle aller Locations, sortiert nach Name (Go API liefert sortiert)
- **Leerer State:** "Keine Locations vorhanden" + "Erste Location erstellen" Button
- **Create:** Button oeffnet Dialog mit leerem LocationForm
- **Edit:** Button pro Zeile oeffnet Dialog mit vorausgefuelltem LocationForm, ID nicht editierbar
- **Delete:** Button pro Zeile oeffnet Bestaetigungsdialog, bei Ja -> API DELETE
- **Validierung:** Client-side (Name required, lat/lon nicht beide 0), Go API validiert komplett
- **Fehler:** API-Fehler als Alert unter dem Formular

### LocationForm

- **Create Mode:** Leere Felder (mit sinnvollen Defaults: lat 47.0, lon 11.0, elev 2000)
- **Edit Mode:** Vorausgefuellt, ID nicht editierbar
- **Activity Profile:** Optional, Dropdown mit 3 Optionen + leer
- **display_config:** Wird bei Edit preserved, bei Create nicht gesetzt

## Known Limitations

- Keine Karten-Anzeige fuer Koordinaten
- Kein DMS-Koordinaten-Parser
- Keine Weather-Metriken-Konfiguration (Out of Scope)
- Keine Suche/Filter (bei 15 Locations nicht noetig)
- Activity Profile Validierung nur ueber Go API (kein Client-side Enum-Check)

## Testbarkeit

### Playwright E2E Tests

1. **Locations-Liste:** Tabelle mit Locations sichtbar
2. **Create Location:** Dialog oeffnen, Felder ausfuellen, Save -> in Liste
3. **Edit Location:** Edit klicken, Name aendern, Save -> aktualisiert
4. **Delete Location:** Delete klicken, bestaetigen -> nicht mehr in Liste
5. **Leerer State:** "Keine Locations" Meldung (wenn testbar)
6. **Activity Profile:** Badge sichtbar nach Profil-Auswahl

## Changelog

- 2026-04-13: Initial spec created

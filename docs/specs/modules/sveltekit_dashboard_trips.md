---
entity_id: sveltekit_dashboard_trips
type: module
created: 2026-04-13
updated: 2026-04-13
status: draft
version: "1.0"
tags: [migration, sveltekit, frontend, trips, dashboard]
---

# M3a: Dashboard + Trips Pages (SvelteKit)

## Approval

- [ ] Approved

## Purpose

Dashboard und Trips-CRUD als erste produktive SvelteKit-Pages implementieren. Ersetzt die NiceGUI-Pages `dashboard.py` (75 LOC) und `trips.py` (747 LOC, Kern-CRUD). Nutzt das bestehende SvelteKit-Scaffold (M2) und die Go API Trip-Endpoints (M1e).

## Scope

### In Scope (M3a)

- Dashboard mit Stats (Trip-Count, Location-Count) und Quick-Action-Links
- Trips-Liste als Tabelle (Name, Etappen-Anzahl, Datumsbereich)
- Trip erstellen: Dialog mit verschachteltem Stage/Waypoint-Editor
- Trip bearbeiten: gleicher Dialog, vorausgefuellt
- Trip loeschen: Bestaetigungsdialog
- shadcn-svelte Komponenten installieren (button, card, dialog, input, label, table, badge)
- Server-side Load fuer initiale Daten

### Out of Scope

- GPX-Upload/Import (eigenes Feature, Go-Endpoint fehlt)
- Weather Config / Report Config Dialoge (separate Features)
- Test Morning/Evening Report Buttons (separate Features)
- DMS-Koordinaten-Parser (Nice-to-have, spaeter)
- Avalanche Regions Editing (spaeter, wenn Risk Engine UI kommt)

## Architecture

```
Browser
  |
  +-- / (Dashboard)
  |     +page.server.ts: load tripCount + locationCount
  |     +page.svelte: Stats Cards + Quick Actions
  |
  +-- /trips (Trip Management)
  |     +page.server.ts: load trips[]
  |     +page.svelte: Table + Dialog-Orchestrierung
  |           |
  |           +-- TripForm.svelte (shared Create/Edit)
  |                 Trip Name
  |                 Stages[] -> Waypoints[]
  |                 Save -> onsave callback
  |
  +-- api.ts -> fetch('/api/...') -> Vite Proxy -> Go API :8090
```

### Datenfluss

```
Server-side Load (SSR):
  +page.server.ts
    -> fetch('http://localhost:8090/api/trips', { headers: { Cookie: gz_session } })
    -> return { trips }

Client-side Mutations:
  TripForm onsave
    -> api.post('/api/trips', trip)  [oder api.put]
    -> bei Erfolg: trips-Liste neu laden via api.get
    -> bei Fehler: ApiError.detail anzeigen

Delete:
  Confirm Dialog
    -> api.del('/api/trips/{id}')
    -> trips-Liste lokal filtern
```

### SSR Cookie-Forwarding (WICHTIG)

Server-side `load()` laeuft im Node-Prozess, nicht im Browser. Der Vite-Proxy greift dort nicht. Daher:

```typescript
// +page.server.ts
const GZ_API = env.GZ_API_BASE ?? 'http://localhost:8090';

export const load: PageServerLoad = async ({ cookies }) => {
  const session = cookies.get('gz_session');
  const headers: Record<string, string> = {};
  if (session) headers['Cookie'] = `gz_session=${session}`;

  const res = await fetch(`${GZ_API}/api/trips`, { headers });
  // ...
};
```

## Source

### Neue Dateien

| Datei | Zweck | ~LOC |
|-------|-------|------|
| `frontend/src/routes/+page.server.ts` | Dashboard: Load Trip/Location Counts | ~30 |
| `frontend/src/routes/trips/+page.svelte` | Trips-Liste + Dialog-Steuerung | ~120 |
| `frontend/src/routes/trips/+page.server.ts` | Load Trips Array | ~20 |
| `frontend/src/lib/components/TripForm.svelte` | Verschachtelte Stage/Waypoint-Bearbeitung | ~200 |

### Geaenderte Dateien

| Datei | Aenderung |
|-------|-----------|
| `frontend/src/routes/+page.svelte` | Ersetze Health-Check durch Stats Cards + Quick Actions (~60 LOC) |

### Gesamt: 5 Dateien, ~430 LOC

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| SvelteKit Setup (M2) | Foundation | Auth, Layout, API Client, Types |
| Go Trip CRUD (M1e) | API | GET/POST/PUT/DELETE /api/trips |
| Go Location CRUD (M1f) | API | GET /api/locations (nur fuer Dashboard Count) |
| Go Health (M1) | API | GET /api/health (Dashboard Status) |
| shadcn-svelte | Library | UI Components (button, card, dialog, input, label, table, badge) |

## Implementation Details

### Phase 1: shadcn-svelte Komponenten installieren

```bash
cd frontend
npx shadcn-svelte@next add button card dialog input label badge
npx shadcn-svelte@next add table
```

### Phase 2: Dashboard Page

`+page.server.ts` — Parallel fetch:
```typescript
import { env } from '$env/dynamic/private';
import type { PageServerLoad } from './$types';

const API = env.GZ_API_BASE ?? 'http://localhost:8090';

export const load: PageServerLoad = async ({ cookies }) => {
  const session = cookies.get('gz_session');
  const headers: Record<string, string> = {};
  if (session) headers['Cookie'] = `gz_session=${session}`;

  const [tripsRes, locsRes, healthRes] = await Promise.all([
    fetch(`${API}/api/trips`, { headers }),
    fetch(`${API}/api/locations`, { headers }),
    fetch(`${API}/api/health`),
  ]);

  const trips = tripsRes.ok ? await tripsRes.json() : [];
  const locations = locsRes.ok ? await locsRes.json() : [];
  const health = healthRes.ok ? await healthRes.json() : { status: 'degraded' };

  return {
    tripCount: trips.length,
    locationCount: locations.length,
    health,
  };
};
```

`+page.svelte` — Stats + Quick Actions:
```svelte
<script lang="ts">
  import * as Card from '$lib/components/ui/card';
  import { Button } from '$lib/components/ui/button';

  let { data } = $props();
</script>

<h1>Dashboard</h1>

<div class="grid grid-cols-3 gap-4 mt-4">
  <Card.Root>
    <Card.Header><Card.Title>Trips</Card.Title></Card.Header>
    <Card.Content><span class="text-3xl font-bold">{data.tripCount}</span></Card.Content>
    <Card.Footer><a href="/trips">Verwalten</a></Card.Footer>
  </Card.Root>

  <!-- Location Card, Health Card analog -->
</div>
```

### Phase 3: Trips List Page

`trips/+page.server.ts`:
```typescript
export const load: PageServerLoad = async ({ cookies }) => {
  // Same pattern: fetch from Go API with cookie forwarding
  return { trips };
};
```

`trips/+page.svelte` — State Management:
```svelte
<script lang="ts">
  import type { Trip } from '$lib/types';
  import TripForm from '$lib/components/TripForm.svelte';
  import { api } from '$lib/api';

  let { data } = $props();
  let trips: Trip[] = $state(data.trips);
  let dialogMode: 'create' | 'edit' | null = $state(null);
  let editTarget: Trip | null = $state(null);
  let deleteTarget: Trip | null = $state(null);

  async function handleSave(trip: Trip) {
    if (dialogMode === 'create') {
      await api.post('/api/trips', trip);
    } else {
      await api.put(`/api/trips/${trip.id}`, trip);
    }
    trips = await api.get<Trip[]>('/api/trips');
    dialogMode = null;
  }

  async function handleDelete() {
    if (!deleteTarget) return;
    await api.del(`/api/trips/${deleteTarget.id}`);
    trips = trips.filter(t => t.id !== deleteTarget!.id);
    deleteTarget = null;
  }
</script>
```

Tabelle zeigt pro Trip:
- **Name** (Link oder Text)
- **Etappen** (Badge mit Anzahl)
- **Datumsbereich** (erste Stage.date — letzte Stage.date)
- **Actions** (Edit, Delete Buttons)

### Phase 4: TripForm Component

Props:
```typescript
interface Props {
  trip?: Trip;         // undefined = Create, defined = Edit
  onsave: (t: Trip) => void;
  oncancel: () => void;
}
```

Interner State (Svelte 5 Runes):
```svelte
<script lang="ts">
  import type { Trip, Stage, Waypoint } from '$lib/types';

  let { trip, onsave, oncancel }: Props = $props();

  // Lokaler editierbarer State
  let tripName = $state(trip?.name ?? '');
  let tripId = $state(trip?.id ?? '');
  let stages: Stage[] = $state(
    trip ? JSON.parse(JSON.stringify(trip.stages)) : []
  );
</script>
```

Stage-Bearbeitung:
- Jede Stage als Card mit Name, Date (YYYY-MM-DD), Start Time (HH:MM) Inputs
- Waypoint-Liste innerhalb jeder Stage: kompakte Zeilen mit Name, Lat, Lon, Elevation
- "Etappe hinzufuegen" Button: erzeugt Stage mit auto-generierter ID und heutigem Datum
- "Wegpunkt hinzufuegen" Button pro Stage: erzeugt Waypoint mit Defaults (lat 47.0, lon 11.0, elev 2000)
- "Entfernen" Button fuer Stages und Waypoints

ID-Generierung:
```typescript
const newId = () => crypto.randomUUID().slice(0, 8);
```

Save-Logik:
```typescript
function save() {
  const result: Trip = {
    id: tripId || newId(),
    name: tripName,
    stages,
    // Preserve opaque configs from original trip
    ...(trip && {
      avalanche_regions: trip.avalanche_regions,
      aggregation: trip.aggregation,
      weather_config: trip.weather_config,
      display_config: trip.display_config,
      report_config: trip.report_config,
    }),
  };
  onsave(result);
}
```

## Expected Behavior

### Dashboard (/)

- **Anzeige:** 3 Stats-Cards (Trips, Locations, Health)
- **Links:** "Verwalten" Links zu /trips und /locations
- **Fehlerfall:** Wenn Go API nicht erreichbar -> Count 0, Health "degraded"
- **SSR:** Daten werden server-side geladen, kein Loading-Spinner

### Trips (/trips)

- **Liste:** Tabelle aller Trips, sortiert nach Name (Go API liefert sortiert)
- **Leerer State:** "Keine Trips vorhanden" + "Ersten Trip erstellen" Button
- **Create:** Button oeffnet Dialog mit leerem TripForm
- **Edit:** Button pro Zeile oeffnet Dialog mit vorausgefuelltem TripForm
- **Delete:** Button pro Zeile oeffnet Bestaetigungsdialog, bei Ja -> API DELETE
- **Validierung:** Client-side minimal (Name required), Go API validiert komplett
- **Fehler:** API-Fehler werden als Alert/Toast unter dem Formular angezeigt

### TripForm

- **Create Mode:** Leere Felder, ID wird auto-generiert bei Save
- **Edit Mode:** Vorausgefuellt aus bestehendem Trip, ID nicht editierbar
- **Stages:** Dynamische Liste, mindestens eine Stage zum Speichern erforderlich
- **Waypoints:** Dynamische Liste pro Stage, mindestens ein Waypoint pro Stage
- **In-place Mutation:** Svelte 5 $state Proxy trackt verschachtelte Aenderungen

## Known Limitations

- Kein GPX-Import (Out of Scope M3a)
- Keine Karten-Anzeige fuer Waypoints (spaeter)
- Kein DMS-Koordinaten-Parser (spaeter)
- Keine Weather/Report Config Buttons (separate Features)
- Avalanche Regions werden preserve aber nicht editierbar
- Keine Pagination (bei wenigen Trips nicht noetig)
- Keine Offline-Faehigkeit

## Testbarkeit

### Playwright E2E Tests

1. **Dashboard laedt:** Stats werden angezeigt, Counts > 0 nach Trip-Erstellung
2. **Trips-Liste:** Alle Trips in Tabelle sichtbar
3. **Trip erstellen:** Dialog oeffnen, Name + Stage + Waypoint eingeben, Save -> Trip in Liste
4. **Trip editieren:** Edit klicken, Name aendern, Save -> aktualisierter Name in Liste
5. **Trip loeschen:** Delete klicken, bestaetigen -> Trip nicht mehr in Liste
6. **Leerer State:** Ohne Trips -> "Keine Trips" Meldung sichtbar

### Manuelle Pruefung

- Safari Hard Reload (Cmd+Shift+R) nach jeder UI-Aenderung
- Sidebar-Navigation: Trips-Link aktiv auf /trips
- Responsive: Layout-Shell bleibt konsistent

## Changelog

- 2026-04-13: Initial spec created

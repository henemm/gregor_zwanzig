---
entity_id: trip_wizard_w1
type: module
created: 2026-04-18
updated: 2026-04-18
status: draft
version: "1.0"
tags: [sveltekit, frontend, trips, wizard, gpx, stepper]
---

# Trip Wizard W1: Route + Etappen (SvelteKit)

## Approval

- [ ] Approved

## Purpose

Mehrstufiger Wizard zum Erstellen und Bearbeiten von Trips, der GPX-Upload (Drag & Drop, Mehrfachdateien) und manuelle Etappen-Verwaltung als dedizierte Route-basierte Pages (`/trips/new`, `/trips/[id]/edit`) bereitstellt. Ersetzt den kompakten TripForm-Dialog durch einen 4-Schritte-Workflow, der komplexere Konfigurationen ohne Platzprobleme ermoeglichen kann (W2: Wetter, W3: Reports).

## Scope

### In Scope (W1)

- WizardStepper: visuelle Schritt-Anzeige (4 Schritte, aktueller Schritt hervorgehoben)
- TripWizard: Container mit Navigation (Zurueck/Weiter/Speichern), State, Validation
- Step 1 (Route): GPX-Upload (Drag & Drop, mehrere Dateien) + manuelle Anlage + Trip-Name
- Step 2 (Etappen): Stage/Waypoint-CRUD, vorabgefuellt aus GPX-Parse oder leer
- Steps 3+4: Platzhalter ("Kommt in W2/W3"), keine Funktionalitaet
- Neue Routen `/trips/new` und `/trips/[id]/edit` mit SSR-Load fuer Edit-Mode
- `uploadGpx()` Funktion in `api.ts` fuer FormData-Uploads
- `/trips`-Page: "Neuer Trip"- und Edit-Button wechseln zu goto-Navigation

### Out of Scope (W1)

- Step 3: Wetter-Konfiguration (W2)
- Step 4: Report-Konfiguration (W3)
- Kartendarstellung von Wegpunkten
- DMS-Koordinaten-Parser
- Avalanche Regions Editing

## Architecture

```
Browser

  /trips/new
    +page.svelte → TripWizard (mode=create, existingTrip=undefined)

  /trips/[id]/edit
    +page.server.ts → fetch Trip via Go API (SSR mit Cookie)
    +page.svelte    → TripWizard (mode=edit, existingTrip=Trip)

  TripWizard.svelte
    ├── WizardStepper (step 1–4, aktueller Schritt)
    ├── WizardStep1Route   (step === 1)
    ├── WizardStep2Stages  (step === 2)
    ├── WizardStep3Placeholder (step === 3)
    ├── WizardStep4Placeholder (step === 4)
    └── Navigation-Bar (Zurueck / Weiter / Speichern)

  WizardStep1Route
    → dragover/drop Zone oder <input type="file" multiple accept=".gpx">
    → uploadGpx() pro Datei → POST /api/gpx/parse → Stage[]
    → Trip-Name Input (auto aus erstem GPX-Dateinamen)
    → "Manuell anlegen" Button → leere Stage an Step2 uebergeben

  WizardStep2Stages
    → Stage Cards: Name, Datum (YYYY-MM-DD), Startzeit (HH:MM)
    → Waypoints pro Stage: Name, Lat, Lon, Elevation
    → CRUD: Stage hinzufuegen/loeschen, Waypoint hinzufuegen/loeschen

  api.ts: uploadGpx(file, stageDate, startHour)
    → POST /api/gpx/parse via fetch (FormData, kein JSON)
    → Gibt Stage (mit Waypoints) zurueck
```

## Source

### Neue Dateien

| Datei | Zweck | ~LOC |
|-------|-------|------|
| `frontend/src/routes/trips/new/+page.svelte` | Create-Route: ladet TripWizard ohne existingTrip | ~20 |
| `frontend/src/routes/trips/new/+page.server.ts` | Minimal (keine SSR-Daten benoetigt) | ~5 |
| `frontend/src/routes/trips/[id]/edit/+page.svelte` | Edit-Route: gibt existingTrip an TripWizard | ~20 |
| `frontend/src/routes/trips/[id]/edit/+page.server.ts` | Load Trip via Go API mit Cookie-Forwarding | ~30 |
| `frontend/src/lib/components/wizard/TripWizard.svelte` | Container: State, Navigation, Save | ~150 |
| `frontend/src/lib/components/wizard/WizardStepper.svelte` | Step-Indikator (4 Kreise + Beschriftungen) | ~60 |
| `frontend/src/lib/components/wizard/WizardStep1Route.svelte` | GPX-Upload + manueller Fallback + Trip-Name | ~150 |
| `frontend/src/lib/components/wizard/WizardStep2Stages.svelte` | Stage/Waypoint-CRUD | ~180 |
| `frontend/src/lib/components/wizard/WizardStep3Placeholder.svelte` | "Kommt in W2" Hinweis | ~15 |
| `frontend/src/lib/components/wizard/WizardStep4Placeholder.svelte` | "Kommt in W3" Hinweis | ~15 |

### Geaenderte Dateien

| Datei | Aenderung |
|-------|-----------|
| `frontend/src/lib/api.ts` | `uploadGpx()` fuer FormData-Upload ergaenzen |
| `frontend/src/routes/trips/+page.svelte` | "Neuer Trip" → `goto('/trips/new')`, Edit-Button → `goto('/trips/{id}/edit')` |

### Gesamt: ~10 neue + 2 geaenderte Dateien, ~650 LOC

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| Go API `POST /api/trips` | API (existiert) | Trip erstellen im Create-Mode |
| Go API `PUT /api/trips/{id}` | API (existiert) | Trip aktualisieren im Edit-Mode |
| Go API `GET /api/trips/{id}` | API (existiert) | Trip laden fuer Edit-Mode (SSR) |
| FastAPI `POST /api/gpx/parse` | API (existiert) | GPX-Datei parsen → Stage mit Waypoints |
| `lib/types.ts` `Trip`, `Stage`, `Waypoint` | Types (existieren) | Datentypen fuer State |
| `lib/api.ts` | Modul (existiert) | JSON-API-Client, wird um `uploadGpx()` erweitert |
| `lib/components/TripForm.svelte` | Komponente (existiert) | Stage/Waypoint-Patterns als Referenz fuer Step 2 |
| `shadcn-svelte` Button, Card, Input, Label, Badge | Library (existiert) | UI-Grundbausteine |
| SvelteKit `goto` | Framework | Client-seitige Navigation nach Save |
| Svelte 5 `$state`, `$props` | Framework | Reaktiver State im Wizard-Container |

## Implementation Details

### Phase 1: uploadGpx() in api.ts

```typescript
export async function uploadGpx(
  file: File,
  stageDate: string,   // YYYY-MM-DD
  startHour: number    // 0-23
): Promise<Stage> {
  const form = new FormData();
  form.append('file', file);
  form.append('stage_date', stageDate);
  form.append('start_hour', String(startHour));

  const res = await fetch('/api/gpx/parse', { method: 'POST', body: form });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`GPX parse failed: ${detail}`);
  }
  return res.json() as Promise<Stage>;
}
```

Wichtig: Kein `Content-Type` Header setzen — Browser setzt ihn automatisch mit Boundary fuer FormData.

### Phase 2: Edit-Route SSR Load

```typescript
// frontend/src/routes/trips/[id]/edit/+page.server.ts
import { env } from '$env/dynamic/private';
import { error } from '@sveltejs/kit';
import type { PageServerLoad } from './$types';

const API = env.GZ_API_BASE ?? 'http://localhost:8090';

export const load: PageServerLoad = async ({ params, cookies }) => {
  const session = cookies.get('gz_session');
  const headers: Record<string, string> = {};
  if (session) headers['Cookie'] = `gz_session=${session}`;

  const res = await fetch(`${API}/api/trips/${params.id}`, { headers });
  if (!res.ok) throw error(404, 'Trip nicht gefunden');

  const trip = await res.json();
  return { trip };
};
```

### Phase 3: TripWizard Container State

```svelte
<!-- lib/components/wizard/TripWizard.svelte -->
<script lang="ts">
  import type { Trip, Stage } from '$lib/types';
  import { api, uploadGpx } from '$lib/api';
  import { goto } from '$app/navigation';

  interface Props {
    mode: 'create' | 'edit';
    existingTrip?: Trip;
  }
  let { mode, existingTrip }: Props = $props();

  let currentStep = $state(1);
  let tripName = $state(existingTrip?.name ?? '');
  let tripId = $state(existingTrip?.id ?? '');
  let stages: Stage[] = $state(
    existingTrip ? JSON.parse(JSON.stringify(existingTrip.stages)) : []
  );
  let saveError: string | null = $state(null);

  function canProceed(): boolean {
    if (currentStep === 1) return tripName.trim().length > 0;
    if (currentStep === 2) return stages.length > 0 &&
      stages.every(s => s.waypoints.length > 0);
    return true;
  }

  async function save() {
    const trip: Trip = {
      id: tripId || crypto.randomUUID().slice(0, 8),
      name: tripName,
      stages,
      ...(existingTrip && {
        avalanche_regions: existingTrip.avalanche_regions,
        aggregation: existingTrip.aggregation,
        weather_config: existingTrip.weather_config,
        display_config: existingTrip.display_config,
        report_config: existingTrip.report_config,
      }),
    };
    try {
      if (mode === 'create') {
        await api.post('/api/trips', trip);
      } else {
        await api.put(`/api/trips/${trip.id}`, trip);
      }
      goto('/trips');
    } catch (e) {
      saveError = e instanceof Error ? e.message : 'Unbekannter Fehler';
    }
  }
</script>
```

### Phase 4: WizardStepper

Zeigt 4 Kreise (numeriert 1–4) mit Verbindungslinie. Aktiver Schritt: ausgefuellt, abgeschlossene Schritte: Haken oder ausgefuellt mit anderer Farbe, zukuenftige Schritte: Umriss.

```
● Route  ━━━  ○ Etappen  ━━━  ○ Wetter  ━━━  ○ Reports
```

Labels unter den Kreisen. Keine Klick-Navigation (nur Zurueck/Weiter-Buttons).

### Phase 5: WizardStep1Route

GPX-Upload-Zone:
1. `<div>` mit `dragover`, `dragleave`, `drop` Event-Listenern (Tailwind-Klassen fuer Hover-State)
2. Verstecktes `<input type="file" multiple accept=".gpx">` wird per `<label>` ausgeloest
3. Bei File(s): Sequenziell `uploadGpx(file, todayDate, 8)` aufrufen, Ergebnisse als `Stage[]` akkumulieren
4. Trip-Name: `<Input>` vorabgefuellt mit erstem GPX-Dateinamen ohne Extension
5. "Manuell anlegen": Button fuegt eine leere Stage (kein GPX) zu `stages[]` hinzu und navigiert zu Step 2

Ladeindikator: Einfacher Text "Lade X von Y Dateien..." waehrend Uploads laufen.

Fehlerbehandlung: Fehlgeschlagene GPX-Dateien zeigen Inline-Fehlermeldung (Dateiname + Grund), uebrige Dateien werden weiterverarbeitet.

### Phase 6: WizardStep2Stages

Uebernahme der Stage/Waypoint-CRUD-Patterns aus `TripForm.svelte`:

```
[Stage: "Etappe 1"]   ×
  Datum: [____-__-__]  Startzeit: [__:__]
  Wegpunkte:
    [Name] [Lat] [Lon] [elevation_m] ×
    [Name] [Lat] [Lon] [elevation_m] ×
  [+ Wegpunkt]
[+ Etappe hinzufuegen]
```

- Stage-Name editierbar, Datum (YYYY-MM-DD) editierbar, Startzeit (HH:MM) optional
- Waypoint-Felder: Name (Text), Lat (Number, step=0.0001), Lon (Number, step=0.0001), Elevation (Number, step=1)
- Alle Aenderungen werden direkt in `stages` $state geschrieben (kein separater Submit-Button in Step 2)
- "Etappe loeschen" nur wenn mehr als eine Stage vorhanden
- Validierungshinweis am unteren Rand falls Bedingung nicht erfuellt

### Phase 7: /trips Anpassungen

```typescript
// Statt Dialog oeffnen:
function openCreate() { goto('/trips/new'); }
function openEdit(trip: Trip) { goto(`/trips/${trip.id}/edit`); }
```

Dialog-Code und TripForm-Import koennen aus `/trips/+page.svelte` entfernt werden.

## Expected Behavior

### Create-Flow (`/trips/new`)

- **GPX Upload:** Drag oder Datei-Auswahl → eine Stage pro Datei → Trip-Name auto-befuellt
- **Manuell:** "Manuell anlegen" → leere Stage → Step 2
- **Step 2:** Stages editierbar, Validierung (min. 1 Stage mit 1 Waypoint)
- **Steps 3+4:** Platzhalter, Weiter/Zurueck funktioniert
- **Speichern:** POST /api/trips → bei Erfolg: goto('/trips')
- **Fehler:** Go-API-Fehler als roter Alert-Block unter den Buttons

### Edit-Flow (`/trips/[id]/edit`)

- **SSR:** Trip wird server-side geladen, existingTrip an TripWizard uebergeben
- **Vorausgefuellt:** Alle Felder aus existingTrip (Name, Stages, Waypoints)
- **Opaque Fields:** weather_config, display_config, report_config, aggregation, avalanche_regions werden beim Speichern unveraendert weitergegeben
- **Speichern:** PUT /api/trips/{id} → bei Erfolg: goto('/trips')
- **Trip-ID:** Im Edit-Mode nicht editierbar (read-only)

### Validierung per Schritt

- **Step 1:** Trip-Name nicht leer (Weiter-Button deaktiviert solange leer)
- **Step 2:** Mindestens 1 Stage mit mindestens 1 Waypoint (Weiter-Button deaktiviert)
- **Steps 3+4:** Immer gueltig (keine Eingaben)
- **Save:** Nur auf Step 4 sichtbar (statt Weiter-Button)

### Navigation

- **Zurueck:** Schritt um 1 verringern (Step 1: Zurueck-Button nicht sichtbar)
- **Weiter:** Schritt um 1 erhoehen, nur aktiv wenn `canProceed()` true
- **Speichern:** Sichtbar ab Step 4 (oder Step 2 in W1 als temporaere Geste)
- **Abbrechen:** Link/Button → goto('/trips') ohne zu speichern

## Known Limitations

- GPX-Upload sequenziell (kein paralleles Parsen) → bei vielen Dateien etwas langsamer
- Kein Drag-and-Drop auf Mobile Safari (bekannte Browser-Einschraenkung)
- Steps 3+4 sind reine Platzhalter ohne Funktionalitaet (werden in W2/W3 implementiert)
- Keine Karten-Preview fuer Waypoints
- Kein Rueckgaengig-Machen einzelner GPX-Upload-Schritte (nur gesamt-Reset)
- Trip-ID wird bei Create aus Name-Slug oder UUID abgeleitet, aber keine Slug-Logik definiert — einfache UUID-Variante wird verwendet

## Changelog

- 2026-04-18: Initial spec created

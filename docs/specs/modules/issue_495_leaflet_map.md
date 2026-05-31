---
entity_id: issue_495_leaflet_map
type: module
created: 2026-05-31
updated: 2026-05-31
status: draft
version: "1.0"
tags: [frontend, map, leaflet, waypoints, svelte5]
---

# Issue #495 — Leaflet-Karte im Wegpunkt-Editor

## Approval

- [ ] Approved

## Purpose

`MapCanvas.svelte` ersetzt das dekorative SVG-Topographie-Muster durch eine echte Leaflet-Karte mit OpenTopoMap-Tiles, sodass Wegpunkte geografisch verortbar auf einer Höhenschichtlinien-Karte dargestellt werden. Das ist notwendig, weil die Präzision der Wegpunkt-Koordinaten direkt die Qualität der gelieferten Wetterberichte bestimmt — ein falsch platzierter Wegpunkt liefert falsche Briefings, und ohne geografischen Kontext kann der Nutzer Fehler nicht erkennen.

## Source

- **File:** `frontend/src/lib/components/trip-detail/waypoints/MapCanvas.svelte`
- **Identifier:** `MapCanvas` (Svelte 5 Component)
- **Eingebaut in:** `WaypointEditorPage.svelte` unter `/trips/[id]/edit`

## Estimated Scope

- **LoC:** ~150
- **Files:** 3 (`package.json`, `MapCanvas.svelte`, `waypointEditor.ts`)
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `leaflet` | npm-Paket (^1.9) | Karten-Rendering, Tile-Layer, Marker, Polyline, fitBounds |
| `@types/leaflet` | npm devDependency | TypeScript-Typen für Leaflet |
| `Stage` | Type (`$lib/types`) | Props-Typ für Etappe mit Waypoints-Array (id, lat, lon) |
| `WaypointPin` | Component (`./WaypointPin.svelte`) | Bleibt erhalten als Tooltip-Inhalt in Leaflet-Popups (optional) |
| `buildMapPositions` | Funktion (`waypointEditor.ts`) | Wird entfernt — Leaflet übernimmt die Projektion |

## Implementation Details

### 1. Paket-Installation

In `frontend/package.json` die beiden Pakete hinzufügen:
```json
"leaflet": "^1.9.4",
"@types/leaflet": "^1.9.14"
```

### 2. `MapCanvas.svelte` — Vollrewrite mit Svelte 5 Runes

```svelte
<script lang="ts">
  import type { Stage } from '$lib/types';
  import L from 'leaflet';
  import 'leaflet/dist/leaflet.css';

  interface Props {
    stage: Stage;
    activeWaypointId: string | null;
    onWaypointActivate: (waypointId: string) => void;
  }
  let { stage, activeWaypointId, onWaypointActivate }: Props = $props();

  let mapEl: HTMLDivElement;
  let map: L.Map | null = null;

  $effect(() => {
    if (!mapEl) return;

    map = L.map(mapEl, { zoomControl: true });

    L.tileLayer('https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png', {
      attribution:
        'Kartendaten: © <a href="https://openstreetmap.org/copyright">OpenStreetMap</a>-Mitwirkende, ' +
        'SRTM | Kartendarstellung: © <a href="http://opentopomap.org">OpenTopoMap</a> ' +
        '(<a href="https://creativecommons.org/licenses/by-sa/3.0/">CC-BY-SA</a>)',
      maxZoom: 17
    }).addTo(map);

    const waypoints = stage.waypoints;
    if (waypoints.length > 0) {
      const latlngs = waypoints.map((w) => [w.lat, w.lon] as L.LatLngTuple);

      // Verbindungslinie
      L.polyline(latlngs, { color: 'var(--g-accent)', weight: 2 }).addTo(map);

      // Marker pro Wegpunkt
      waypoints.forEach((w, i) => {
        const marker = L.marker([w.lat, w.lon])
          .addTo(map!)
          .bindPopup(`${i + 1}. ${w.name ?? ''}`);
        marker.on('click', () => onWaypointActivate(w.id));
      });

      // Karte auf alle Wegpunkte einpassen
      map.fitBounds(L.latLngBounds(latlngs), { padding: [24, 24] });
    } else {
      // Fallback: Europa-Zentrum
      map.setView([47.0, 10.0], 5);
    }

    return () => {
      map?.remove();
      map = null;
    };
  });
</script>

<div
  data-testid="map-canvas"
  bind:this={mapEl}
  class="rounded border border-[var(--g-ink-faint)]/20"
  style="width:400px;height:300px;"
></div>
```

**Wichtig — Svelte 5 Runes:**
- `$props()` statt `export let`
- `$effect` statt `onMount` / `onDestroy`
- Der Cleanup-Return aus `$effect` (`return () => { map?.remove() }`) ersetzt `onDestroy`
- `bind:this={mapEl}` liefert den DOM-Container an Leaflet

### 3. `waypointEditor.ts` — `buildMapPositions` entfernen

Die Funktion `buildMapPositions` (Zeilen ~111–150) und den dazugehörigen
`MapPosition`-Typ sowie die `boundingBox`-Hilfsfunktion (falls ausschließlich
von `buildMapPositions` genutzt) werden entfernt. Leaflet übernimmt die
Projektion vollständig. Vor dem Löschen mit `grep -n "buildMapPositions\|MapPosition\|boundingBox"` prüfen,
dass keine weiteren Stellen im Frontend auf diese Exporte referenzieren.

### 4. Leaflet CSS — SSR-Sicherheit

`import 'leaflet/dist/leaflet.css'` im `<script>`-Block des Components.
SvelteKit lädt CSS automatisch. Leaflet darf nicht im SSR-Kontext
instantiiert werden — da der `$effect`-Block nur im Browser läuft,
ist kein expliziter `browser`-Guard nötig. Zur Sicherheit kann
`import L from 'leaflet'` mit `if (typeof window !== 'undefined')` geprüft werden,
falls der Build-Prozess warnt.

### 5. Marker-Icon Fix (bekanntes Leaflet/Vite-Problem)

Leaflet-Standard-Marker-Icons laden via `_getIconUrl` aus dem npm-Bundle,
was mit Vite/SvelteKit zu 404-Fehlern führt. Fix nach dem Init-Call:
```typescript
import iconUrl from 'leaflet/dist/images/marker-icon.png';
import iconRetinaUrl from 'leaflet/dist/images/marker-icon-2x.png';
import shadowUrl from 'leaflet/dist/images/marker-shadow.png';

delete (L.Icon.Default.prototype as unknown as Record<string, unknown>)._getIconUrl;
L.Icon.Default.mergeOptions({ iconUrl, iconRetinaUrl, shadowUrl });
```

## Expected Behavior

- **Input:** `stage: Stage` mit `waypoints[]` (jeder Waypoint hat `id`, `lat`, `lon`, optional `name`)
- **Output:** DOM-Element mit gerendeter Leaflet-Karte (OpenTopoMap-Tiles), Wegpunkt-Markern, Verbindungslinie; Karte ist auf alle Wegpunkte eingefittet
- **Side effects:** Klick auf Marker ruft `onWaypointActivate(waypointId)` auf; Leaflet-Map-Instanz wird bei Component-Destroy via `map.remove()` bereinigt (kein Memory Leak)

## Acceptance Criteria

- **AC-1:** Given eine Etappe mit mindestens zwei Wegpunkten / When der Wegpunkt-Editor geladen wird / Then zeigt `[data-testid="map-canvas"]` eine Leaflet-Karte mit OpenTopoMap-Tiles (kein leeres SVG, kein dekoratives Muster) und alle Marker sind sichtbar innerhalb der Karte

- **AC-2:** Given eine Etappe mit N Wegpunkten (N >= 2) / When die Karte initialisiert wird / Then sind die Marker durch eine Verbindungslinie in Etappen-Reihenfolge verbunden, und die Karte ist via `fitBounds` so gezoomt dass alle Marker ohne manuelles Scrollen sichtbar sind

- **AC-3:** Given ein Wegpunkt-Marker auf der Karte / When der Nutzer auf den Marker klickt / Then wird `onWaypointActivate` mit der korrekten Waypoint-ID aufgerufen und der Wegpunkt in der Tabellen-Liste rechts daneben aktiviert

- **AC-4:** Given die Karte mit OpenTopoMap-Tiles / When sie gerendert ist / Then ist die Leaflet-Attribution sichtbar (Text enthält "OpenStreetMap" und "OpenTopoMap"), entsprechend der CC-BY-SA-Lizenzpflicht

- **AC-5:** Given eine Etappe ohne Wegpunkte / When der Wegpunkt-Editor geladen wird / Then zeigt die Karte eine valide Leaflet-Karte zentriert auf Europa (kein Leer-Fehler, keine JS-Exception in der Console)

- **AC-6:** Given die Wegpunkt-Editor-Seite / When der Nutzer die Seite verlässt (Component wird zerstört) / Then wird `map.remove()` aufgerufen und es gibt keine Leaflet-Fehlermeldung in der Console (kein „Map container is already initialized"-Fehler beim erneuten Öffnen)

- **AC-7:** Given `buildMapPositions` in `waypointEditor.ts` / When das Feature implementiert ist / Then ist die Funktion und der zugehörige `MapPosition`-Typ aus der Datei entfernt, und `grep -r "buildMapPositions" frontend/src` liefert null Treffer

## Known Limitations

- Wegpunkt per Kartenklick setzen (P2) ist nicht in diesem Feature enthalten
- GPX-Track-Overlay ist nicht in diesem Feature enthalten (eigenes Issue)
- OpenTopoMap-Tiles haben kein SLA; bei Nichtverfügbarkeit zeigt Leaflet graue Kacheln (kein Fallback-Provider implementiert)
- Leaflet funktioniert nicht im SSR-Kontext — der Component muss immer client-seitig gerendert werden (wird durch `$effect`-Scoping sichergestellt)

## Changelog

- 2026-05-31: Implementation completed — leaflet-Karte deployed, buildMapPositions und MapPosition entfernt. Dokumentation aktualisiert in:
  - `docs/features/architecture.md` — Section Frontend Dependencies + MapCanvas-Beschreibung
  - `docs/reference/frontend_components.md` — MapCanvas-Eintrag
  - `docs/reference/api_contract.md` — Changelog-Eintrag
  - `docs/specs/modules/epic_137_wegpunkt_editor.md` — Status-Notiz hinzugefügt
- 2026-05-31: Initial spec erstellt — Issue #495

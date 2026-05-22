## Problem — fundamentale Neuausrichtung

Der aktuelle Trip-Editor (`/trips/[id]/edit`) zeigt Wegpunkte als Stack von Eingabezeilen mit **Lat/Lon/Höhen-Number-Inputs**. Das **widerspricht der Spec**:

`docs/specs/user_stories_foundation.md` (US-1, Implizite Anforderungen):
> - Wegpunktvorschläge (Wetterscheiden) werden **algorithmisch berechnet** — aus GPX-Profil
> - Vorschläge sind orange gestrichelt dargestellt — User bestätigt oder verwirft, manuelle Punkte sind voll
> - **Kein Lat/Lon-Interface — alles visuell**
> - Pausentag = leere Etappe
> - **Ankunftszeiten werden vom System aus dem GPX errechnet** (Naismith's Rule) — nicht manuell eingetragen

Lat/Lon-Felder sind ein No-Go aus Usability-Sicht: keiner gibt am Schreibtisch Koordinaten mit 6 Nachkommastellen ein. Das produziert nur Fehler.

## Lösung — drei Bestandteile

1. **Karte** als Haupt-Editor — User klickt Wegpunkte auf der Karte, zieht sie zum Verschieben, löscht per Klick.
2. **Höhenprofil** unten als sekundäre Sicht — sichtbar wo Vorschläge liegen, klickbar.
3. **Wegpunkt-Sidebar** rechts — listet Punkte, zeigt berechnete Höhe + Naismith-Ankunftszeit, erlaubt Override-Felder.

## Files

- `src/lib/components/edit/EditStagesSection.svelte` — komplette Umstellung
- `src/lib/components/edit/StageMapEditor.svelte` — **neu**, Hauptkomponente
- `src/lib/components/edit/ElevationProfile.svelte` — **neu**
- `src/lib/components/edit/WaypointSidebar.svelte` — **neu**
- `src/lib/components/edit/WaypointDetailDialog.svelte` — **neu** (für algorithmische Vorschläge bestätigen)

## Map library — Empfehlung

**MapLibre GL JS** (Open-Source, kein API-Key, OpenStreetMap-Tiles möglich). Wenn ihr schon Mapbox o.ä. nutzt → nehmen. Wenn nicht: MapLibre.

```bash
npm install maplibre-gl
```

## Required changes

### 1. Datenmodell-Erweiterung

`src/lib/types.ts` — Waypoint erweitern:

```ts
export interface Waypoint {
  id: string;
  name: string;
  lat: number;       // weiterhin in DB — User sieht es aber nie
  lon: number;
  elevation_m: number;
  origin: 'manual' | 'algorithm';     // NEW
  confirmed: boolean;                  // NEW — Vorschlag bestätigt?
  arrival_calculated?: string;         // NEW — HH:MM, aus Naismith
  arrival_override?: string | null;    // NEW — manuell überschrieben
}
```

Backend-API muss `origin`, `confirmed`, `arrival_calculated`, `arrival_override` mitliefern. Wenn Backend noch nicht so weit ist: Issue dort öffnen (`backend: compute Naismith arrival times on save`) und im Frontend mit sensible defaults (`origin: 'manual', confirmed: true`) arbeiten.

### 2. Map-Editor Layout

```svelte
<!-- src/lib/components/edit/StageMapEditor.svelte -->
<script lang="ts">
  import maplibregl from 'maplibre-gl';
  import 'maplibre-gl/dist/maplibre-gl.css';
  // ...
  let { stage = $bindable() }: Props = $props();
</script>

<div class="map-editor">
  <header class="map-editor__head">
    <button class="back">← Etappen-Übersicht</button>
    <span class="meta">{stage.id} · {stage.date} · {stage.name}</span>
    <span class="naismith">{stage.km} km · ↑{stage.elev_gain} m · {stage.naismith_total}</span>
  </header>

  <div class="map-editor__body">
    <div class="map" bind:this={mapEl}></div>
    <WaypointSidebar bind:waypoints={stage.waypoints} onSelect={selectWp} />
  </div>

  <ElevationProfile waypoints={stage.waypoints} gpxTrack={stage.track} />
</div>
```

### 3. Wegpunkt-Marker-Stile

```js
// In the map's source layer config:
// 1. GPX-Track als Line — Brand info color
map.addLayer({
  id: 'gpx-track',
  type: 'line',
  source: 'track',
  paint: {
    'line-color': 'var(--g-info)',  // CSS not supported in MapLibre paint — use hex
    'line-width': 2.5,
    'line-opacity': 0.85,
  }
});

// 2. Manuelle Wegpunkte — Solid ink dots
// 3. Algorithmische Vorschläge — Outlined accent dots with dashed stroke
```

In CSS (via Symbol-Layer-Icons oder HTML-Marker):

```css
.wp-marker {
  width: 16px; height: 16px; border-radius: 50%;
  cursor: pointer;
  transition: transform 120ms;
}
.wp-marker:hover { transform: scale(1.2); }
.wp-marker--manual    { background: var(--g-ink); border: 2px solid var(--g-paper); }
.wp-marker--suggested {
  background: var(--g-paper);
  border: 2px dashed var(--g-accent);
}
.wp-marker--suggested.confirmed { background: var(--g-accent); border: 2px solid var(--g-paper); }
```

### 4. Waypoint Sidebar (rechte Spalte, 320 px)

```svelte
<!-- WaypointSidebar.svelte -->
<aside class="wp-sidebar">
  <header>
    <span class="wp-count">Wegpunkte · {waypoints.length}</span>
    <span class="wp-hint">+ Klick auf Karte</span>
  </header>
  {#each waypoints as wp (wp.id)}
    <button class="wp-row" class:active={wp.id === selectedId} onclick={() => onSelect(wp)}>
      <span class="wp-row__icon" class:manual={wp.origin === 'manual'}
            class:suggested={wp.origin === 'algorithm' && !wp.confirmed}
            class:confirmed={wp.origin === 'algorithm' && wp.confirmed}></span>
      <span class="wp-row__main">
        <span class="wp-row__name">{wp.name}</span>
        {#if wp.origin === 'algorithm' && !wp.confirmed}
          <span class="wp-row__pill">vorschlag</span>
        {/if}
        <span class="wp-row__meta">↑{wp.elevation_m} m · {wp.arrival_override ?? wp.arrival_calculated}</span>
      </span>
    </button>
  {/each}
  <footer class="wp-sidebar__actions">
    <button onclick={confirmAllSuggestions}>Alle Vorschläge bestätigen</button>
    <button onclick={discardAllSuggestions}>Verwerfen</button>
  </footer>
</aside>
```

### 5. Wegpunkt-Detail-Dialog (für algorithmische Vorschläge)

Wenn der User auf einen orange-gestrichelten Vorschlag klickt:

```svelte
<Dialog>
  <DialogContent class="max-w-md">
    <Eyebrow>Algorithmischer Vorschlag · Wegpunkt</Eyebrow>
    <h3>{wp.name}</h3>
    <p>Das System hat diesen Punkt vorgeschlagen, weil hier ein Gipfel auf der GPX-Spur
       liegt (signifikanter Höhenwechsel · expositionswichtig).</p>

    <div class="computed-fields">
      <ComputedField label="Höhe" value="{wp.elevation_m} m" />
      <ComputedField label="Ankunft" value={wp.arrival_calculated} hint="Naismith" />
      <ComputedField label="Exposition" value={wp.exposition_label} />
    </div>

    <Checkbox bind:checked={overrideArrival}>Ankunftszeit manuell anpassen</Checkbox>
    {#if overrideArrival}
      <input type="time" bind:value={wp.arrival_override} />
    {/if}

    <DialogFooter>
      <Btn variant="primary" onclick={confirm}>Übernehmen als Wegpunkt</Btn>
      <Btn variant="ghost" onclick={discard}>Verwerfen</Btn>
    </DialogFooter>
  </DialogContent>
</Dialog>
```

### 6. Höhenprofil

```svelte
<!-- ElevationProfile.svelte -->
<svg viewBox="0 0 800 100" class="elev-profile">
  <!-- shaded area under elevation curve -->
  <polygon points={areaPoints} fill="rgba(196,90,42,0.10)" />
  <polyline points={linePoints} stroke="var(--g-accent)" stroke-width="1.8" fill="none" />
  <!-- waypoint markers on the curve -->
  {#each waypoints as wp}
    <circle cx={x(wp)} cy={y(wp)} r="3"
            fill={wp.origin === 'manual' ? 'var(--g-ink)' : 'var(--g-accent)'} />
  {/each}
</svg>
```

Höhe 130 px, sticky am unteren Rand des Map-Editors.

### 7. Lat/Lon-Inputs vollständig entfernen

Das alte `EditStagesSection.svelte`-Layout mit `<Input data-testid="wp-lat">` etc. wird komplett ersetzt. **Playwright-Tests müssen angepasst werden:**

- `wp-lat`, `wp-lon`, `wp-ele` Testids → **entfallen** (es gibt keine Inputs mehr)
- Stattdessen: `data-testid="wp-marker-{id}"` auf der Karte und `data-testid="wp-row-{id}"` in der Sidebar
- Hinzufügen: `data-testid="confirm-suggestion-{id}"`, `data-testid="discard-suggestion-{id}"`

**Migration Note für Tests:** Existing Playwright tests that assert lat/lon values need to be rewritten to assert on the underlying state (read from API response) rather than DOM inputs. New tests should drive the map via simulated clicks.

### 8. Ankunftszeit-Berechnung — Backend coordination

Die Spec sagt explizit:

> Das aktuelle Backend-Datenmodell (`Stage.start_time`, `Waypoint.time_window`) speichert Zeiten als manuelle Felder. Die automatische Berechnung aus GPX (Pace-Schätzung, Höhenmeter-Zuschlag nach Naismith's Rule o.ä.) fehlt noch im Backend.

→ **Vor Implementierung dieses Issues** muss ein separates Backend-Issue erstellt werden: „Compute Naismith arrival times on GPX upload / stage save". Frontend kann mit Placeholder-Werten arbeiten bis Backend liefert.

## Acceptance criteria

- [ ] Keine Lat/Lon-Eingabefelder im UI mehr.
- [ ] Wegpunkte werden auf einer Karte gerendert (MapLibre / Mapbox), mit Topo-Tiles wenn möglich.
- [ ] Klick auf leere Karte = manuellen Wegpunkt hinzufügen.
- [ ] Klick auf Vorschlag-Marker (orange-gestrichelt) öffnet Detail-Dialog mit Bestätigen / Verwerfen.
- [ ] Sidebar zeigt alle Wegpunkte mit berechneter Höhe + Ankunftszeit (Naismith).
- [ ] Höhenprofil unten zeigt Etappenverlauf + Wegpunktmarker.
- [ ] User kann eine berechnete Ankunftszeit per Checkbox-Override manuell anpassen.
- [ ] „Alle Vorschläge bestätigen" / „Verwerfen" Buttons am Sidebar-Footer.
- [ ] Pausentag = Etappe mit `waypoints.length === 0` und nur `date` + `name`.
- [ ] Mobile: Karte vollbreit, Sidebar wird zur Bottom-Sheet.

## 📎 Screenshots

**Soll: visueller Karten-Editor mit Höhenprofil**

![soll-map-editor](https://raw.githubusercontent.com/henemm/gregor_zwanzig/main/.github/issue-assets/soll-flow2B-map-editor.png)

**Soll: Wegpunkt-Detail-Dialog (algorithmischer Vorschlag)**

![soll-wp-detail](https://raw.githubusercontent.com/henemm/gregor_zwanzig/main/.github/issue-assets/soll-flow2C-waypoint-detail.png)

**Ist: Lat/Lon-Number-Inputs (falsch)**

![ist-trip-editor](https://raw.githubusercontent.com/henemm/gregor_zwanzig/main/.github/issue-assets/06-trip-editor-full.png)
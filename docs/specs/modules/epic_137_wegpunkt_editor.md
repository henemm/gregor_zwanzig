---
entity_id: epic_137_wegpunkt_editor
type: module
created: 2026-05-17
updated: 2026-05-17
status: active
version: "1.0"
parent_spec: epic_136_trip_wizard
related: epic_136_trip_wizard
issues: [166, 167, 168, 169, 170, 171, 172]
tags: [sveltekit, frontend, trip-detail, waypoints, map, profile, dnd, epic-137]
---

# Epic 137 — Wegpunkt-Editor: Tab „Etappen & Wegpunkte" in Trip-Detail

## Approval

- [ ] Approved

## Purpose

Befuellt den bisher leeren Platzhalter-Tab `stages` in `/trips/[id]` (TripTabs.svelte)
mit einem vollstaendigen Wegpunkt-Editor. Dieser erlaubt es dem User, Etappen per
Drag-and-Drop neu zu ordnen, Wegpunkte auf einer interaktiven SVG-Karte und einem
SVG-Hoehenprofil zu begutachten, vorgeschlagene Wegpunkte zu bestaetigen oder zu
verwerfen, manuelle Wegpunkte umzubenennen oder zu loeschen und die Aenderungen
explizit zu speichern. Das Epic schreibt ausschliesslich in der Frontend-Schicht
(`frontend/src/`); kein Backend-Touch.

## Source

**Schicht: Frontend / SvelteKit** — alle Dateien unter `frontend/src/`

**NEU — Komponenten:**
- `frontend/src/lib/components/trip-detail/WaypointsPanel.svelte`
- `frontend/src/lib/components/trip-detail/waypoints/WaypointPin.svelte`
- `frontend/src/lib/components/trip-detail/waypoints/StageCard.svelte`
- `frontend/src/lib/components/trip-detail/waypoints/EtappenStrip.svelte`
- `frontend/src/lib/components/trip-detail/waypoints/MapCanvas.svelte`
- `frontend/src/lib/components/trip-detail/waypoints/ProfileEditor.svelte`
- `frontend/src/lib/components/trip-detail/waypoints/WaypointCard.svelte`
- `frontend/src/lib/components/trip-detail/waypoints/PauseStageView.svelte`

**NEU — Utilities:**
- `frontend/src/lib/utils/waypointEditor.ts`
- `frontend/src/lib/utils/waypointEditor.test.ts`

**EDIT:**
- `frontend/src/lib/components/trip-detail/TripTabs.svelte`
- `frontend/src/lib/components/trip-detail/index.ts`
- `frontend/src/app.css`

**Identifier (Exports):**
`WaypointsPanel` (default), `WaypointPin`, `StageCard`, `EtappenStrip`,
`MapCanvas`, `ProfileEditor`, `WaypointCard`, `PauseStageView`,
`stripSuggested`, `buildMapPositions`, `boundingBox`

## Verweis auf Master-Spec

Diese Spec ist ein eigenstaendiges Epic im Kontext des Trip-Wizards (Epic #136).
Sie konsumiert folgende Definitionen der Master-Spec:

- **Waypoint.suggested** — transientes Frontend-Flag (`boolean | undefined`),
  wird vor PUT gestrippt (analog `toTripPayload` / `stripSuggested` im Wizard).
  Der Wegpunkt-Editor implementiert eine eigene `stripSuggested`-Pure-Function
  in `waypointEditor.ts`, da hier kein `WizardState` existiert.
- **isPauseStage()** — aus `wizardHelpers.ts`; eine Stage ohne Waypoints gilt
  als Pausentag (`waypoints.length === 0`). Kein neues Feld noetig.
- **formatStageNumber()** — aus `wizardHelpers.ts`; erzeugt T01/T02-Pill-Text.
- **ActivityProfile** — Enum fuer Aktivitaetsprofile; wird an `WaypointsPanel`
  als Prop durchgereicht (lesend, keine Mutation).

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/src/lib/types.ts` | file (lesen) | `Trip`, `Stage`, `Waypoint`, `Waypoint.suggested?` — unveraendert |
| `wizardHelpers.ts` | file (lesen) | `isPauseStage()`, `formatStageNumber()`, `newId()` |
| `ElevSparkline.svelte` | component (ui) | Hoehenprofil-Miniatur in StageCard |
| `TopoBg.svelte` | component (ui) | Topo-Hintergrundtextur in MapCanvas |
| `Btn.svelte` | component (ui atom) | Bestaetigen/Verwerfen/Umbenennen/Loeschen/Speichern-Buttons |
| `Pill.svelte` | component (ui atom) | T01/T02-Etappen-Pills in StageCard |
| `Eyebrow.svelte` | component (ui atom) | Abschnitts-Eyebrows in WaypointsPanel |
| `svelte-dnd-action` | NPM | Drag-and-Drop horizontal in EtappenStrip |
| `@lucide/svelte` | NPM | Icons: `map-pin`, `check`, `x`, `zoom-in`, `zoom-out`, `layers` |
| `--g-accent` CSS-Token | CSS | Burnt Orange — Routenlinie in MapCanvas |
| `--g-warning` CSS-Token | CSS | `#c8882a` — gestrichelte Pins fuer `suggested` Waypoints |
| `--g-ink-strong` CSS-Token | CSS | Farbe fuer bestaetigte Pins (solid); wird als `--g-ink-strong: var(--g-ink)` Alias in `app.css` ergaenzt |
| `--g-ink-faint` CSS-Token | CSS | Sekundaertext, Borders |
| `--g-surface-raised` CSS-Token | CSS | Hervorhebung aktiver Stage in EtappenStrip |
| `ProfileChart.svelte` | component (Wizard) | Vorbild fuer ProfileEditor (gleiches SVG-Schema, andere Props) |
| `PUT /api/trips/:id` | Go-API | Persistenz — WaypointsPanel schickt Trip mit gemuteten Stages |
| `TripTabs.svelte` | file (edit) | Platzhalter fuer Tab `stages` wird durch WaypointsPanel ersetzt |

## Implementation Details

### §1 Architektur — WaypointsPanel als State-Owner

`WaypointsPanel.svelte` haelt allen relevanten State mit Svelte-5-Runes:

```typescript
let activeStageId = $state<string>(trip.stages.find(s => !isPauseStage(s))?.id ?? '');
let activeWaypointId = $state<string | null>(null);
let localStages = $state<Stage[]>(structuredClone(trip.stages)); // tiefe Kopie
let saving = $state(false);
let saveError = $state<string | null>(null);
```

Kein Auto-Save. Der User sieht einen expliziten Speichern-Button. Beim Klick:

```typescript
async function handleSave(): Promise<void> {
  saving = true;
  saveError = null;
  try {
    await api.put(`/api/trips/${trip.id}`, { ...trip, stages: stripSuggested(localStages) });
  } catch (e) {
    saveError = e instanceof Error ? e.message : 'Speichern fehlgeschlagen';
  } finally {
    saving = false;
  }
}
```

Props:

```typescript
interface Props {
  trip: Trip;
  onSaved?: () => void;
}
let { trip, onSaved }: Props = $props();
```

Layout (2 Zeilen):
- Zeile 1: `EtappenStrip` (volle Breite, scrollbar bei vielen Etappen)
- Zeile 2: `flex gap-4` — links `MapCanvas` + `ProfileEditor` gestapelt (~60% Breite),
  rechts `WaypointCard`-Liste (~40% Breite). Bei aktiver PauseStage: rechte Seite
  zeigt `PauseStageView`, linke Seite ist leer.

### §2 WaypointPin.svelte (#169)

SVG-Pin-Komponente, inline SVG 20×28px. Zeigt eine Nummer (1-basiert) im Kreis
mit spitzem Fuss (klassische Map-Pin-Form).

```typescript
interface Props {
  index: number;         // 1-basierte Pin-Nummer
  active?: boolean;      // visuell hervorgehoben (border, glow)
  suggested?: boolean;   // gestrichelt orange (Vorschlag)
  onclick?: () => void;
}
```

Stil-Regeln:
- `suggested === true`: `stroke="var(--g-warning)" stroke-dasharray="4,3" fill="white"`
- `active === true`: `filter: drop-shadow(0 0 3px var(--g-accent))`
- Standard (bestaetigt, inaktiv): `fill="var(--g-ink-strong)" stroke="none"`

ARIA: `aria-label={suggested ? \`Vorgeschlagener Wegpunkt ${index}\` : \`Wegpunkt ${index}\`}`.

### §3 StageCard.svelte (#167)

Kachel fuer eine Etappe im EtappenStrip. Breite fix ~160px, Hoehe ~100px.

```typescript
interface Props {
  stage: Stage;
  index: number;      // 0-basiert fuer T-Pill via formatStageNumber
  active?: boolean;
  onclick?: () => void;
}
```

Inhalt (vertikal):
1. `Pill` mit `formatStageNumber(index)` (T01, T02 …)
2. `ElevSparkline` mit `stage.waypoints` (wenn vorhanden, sonst Platzhalter)
3. Distanz `stage.distance_km ? \`${stage.distance_km} km\` : ''`
4. Aufstieg/Abstieg `stage.elevation_gain_m` / `stage.elevation_loss_m` (falls vorhanden)

Pausentag: gestrichelte Border (`border-dashed border-[var(--g-ink-faint)]`),
kein Sparkline, Text „Pausentag" zentriert. `active`-Style: `ring-2 ring-[var(--g-accent)]`.

### §4 EtappenStrip.svelte (#166)

Horizontaler Strip mit Drag-and-Drop via `svelte-dnd-action`.

```typescript
import { dndzone } from 'svelte-dnd-action';

interface Props {
  stages: Stage[];
  activeStageId: string;
  onStagesReorder: (stages: Stage[]) => void;
  onStageActivate: (stageId: string) => void;
}
```

DnD-Konfiguration: `type: 'horizontal'`, `flipDurationMs: 150`.

Handler (Factory-Pattern, benannte Funktionen):
```typescript
function handleDndConsider(e: CustomEvent): void {
  stages = e.detail.items;
}
function handleDndFinalize(e: CustomEvent): void {
  stages = e.detail.items;
  onStagesReorder(stages);
}
```

Zwischen je zwei Etappen ein unsichtbarer Pause-Inserter-Button
(`aria-label="Pausentag nach Etappe ${i+1} einfuegen"`). Auswahl einer Stage
ruft `onStageActivate(stage.id)` auf. Aktive Stage: `ring-2 ring-[var(--g-accent)]`.

### §5 MapCanvas.svelte (#168)

SVG-Pseudo-Topokarte in ViewBox `0 0 400 300`.

```typescript
interface Props {
  stage: Stage;
  activeWaypointId: string | null;
  onWaypointActivate: (waypointId: string) => void;
  zoomLevel?: number; // default 1.0, Bereich 0.5–3.0
}
```

Koordinaten-Normierung via `buildMapPositions(stage, 400, 300)` aus `waypointEditor.ts`
(Bounding-Box + Cos-Korrektur fuer Laengengrad-Skalierung).

Rendering:
- `TopoBg.svelte` als Hintergrund-Layer
- Routenlinie: `<polyline>` in `stroke="var(--g-accent)" stroke-width="2" fill="none"`
- Pro Waypoint: `<WaypointPin>` auf normierten Koordinaten
- Zoom via CSS `transform: scale(${zoomLevel})` auf dem inneren SVG-Group

Layer-Toggle (Topo/Sat): Button mit Lucide `layers`-Icon, toggled `TopoBg`
Ein/Aus (Sat-Fallback: einfarbiger `--g-surface`-Hintergrund).

Zoom-Buttons (`+` / `-`): `zoomLevel = Math.min/max(0.5, 3.0, zoomLevel ± 0.25)`.

ARIA: `<svg role="img" aria-label={\`Karte fuer Etappe ${stageLabel} mit ${N} Wegpunkten\`}>`.

### §6 ProfileEditor.svelte (#170)

SVG-Hoehenprofil 360×140px, Padding 8px allseits (Zeichenflaeche 344×124px).

```typescript
interface Props {
  stage: Stage;
  activeWaypointId: string | null;
  onWaypointActivate: (waypointId: string) => void;
}
```

Analog zu `ProfileChart.svelte` (Wizard Step 3):
- x-Position: proportional zum Wegpunkt-Index
- y-Position: elevation-skaliert, invertiert (hoch = oben)
- Gridlines bei 25%, 50%, 75% der Zeichenflaeche-Hoehe
  (`stroke="var(--g-ink-faint)" stroke-dasharray="2,4"`)

Pins sind klickbar: `onclick` auf `<circle>` ruft `onWaypointActivate(waypoint.id)` auf.
Aktiver Pin: `r="7"` statt `r="5"`.

Stil-Regeln identisch wie WaypointPin:
- `suggested`: `stroke="var(--g-warning)" stroke-dasharray="3,3" fill="white"`
- bestaetigt: `fill="var(--g-ink-strong)"`

ARIA: `<svg aria-label={\`Hoehenprofil mit ${N} Wegpunkten\`} role="img">`.

### §7 WaypointCard.svelte (#171)

Listeneintrag fuer einen Wegpunkt in der rechten Spalte.

```typescript
interface Props {
  waypoint: Waypoint;
  index: number;
  active?: boolean;
  onActivate: () => void;
  onConfirm: () => void;   // nur bei suggested
  onReject: () => void;    // nur bei suggested
  onRename: () => void;    // nur bei manuell (nicht suggested)
  onDelete: () => void;    // nur bei manuell (nicht suggested)
}
```

Layout (horizontal, `flex items-center gap-3`):
1. `WaypointPin` klein (inline, 14×18px) — zeigt aktiv/suggested-State
2. Wegpunkt-Name `flex-1 truncate`
3. Hoehe `waypoint.elevation_m ? \`${waypoint.elevation_m} m\` : ''`
4. **Wenn `suggested === true`:** Bestaetigen-Button (`Btn` primary, `Check`-Icon) + Verwerfen-Button (`Btn` ghost, `X`-Icon)
5. **Wenn `suggested` nicht gesetzt:** Umbenennen-Button (`Btn` ghost, Lucide `pencil`-Icon) + Loeschen-Button (`Btn` ghost, `X`-Icon)

Aktiv-Hervorhebung: `bg-[var(--g-surface-raised)]` wenn `active === true`.

TestIDs:
- `waypoint-card-{index}` auf Root-Element
- `waypoint-confirm-{index}`, `waypoint-reject-{index}`
- `waypoint-rename-{index}`, `waypoint-delete-{index}`

### §8 PauseStageView.svelte (#172)

Ansicht fuer einen Pausentag (rechte Spalte, wenn aktive Stage ein Pausentag ist).

```typescript
interface Props {
  stage: Stage;
  prevStage: Stage | null;
  nextStage: Stage | null;
}
```

Inhalt:
- Eyebrow „Pausentag"
- Standort-Info: Zielort der Vorgaenger-Etappe (`prevStage.waypoints.at(-1)?.name`)
  und Startort der Folge-Etappe (`nextStage.waypoints[0]?.name`), falls vorhanden.
- Datum der Stage (`stage.date ?? ''`)
- Name der Stage (`stage.name ?? ''`)
- Kein MapCanvas, kein ProfileEditor.

### §9 Pure Functions — waypointEditor.ts

```typescript
// Entfernt das suggested-Flag aus allen Waypoints aller Stages
export function stripSuggested(stages: Stage[]): Stage[];

// Normiert Waypoint-Koordinaten (lat/lon) auf SVG-Koordinaten (x/y)
// mit Bounding-Box-Berechnung und Cos-Korrektur fuer Breitengrad-Skalierung
export function buildMapPositions(
  stage: Stage,
  svgWidth: number,
  svgHeight: number
): Array<{ waypointId: string; x: number; y: number }>;

// Berechnet Bounding-Box (minLat, maxLat, minLon, maxLon) + Aspect-Ratio-Faktor
export function boundingBox(
  waypoints: Waypoint[]
): { minLat: number; maxLat: number; minLon: number; maxLon: number; cosLat: number };
```

`boundingBox` berechnet `cosLat = Math.cos(centerLat * Math.PI / 180)` und gibt
ihn zurueck, damit `buildMapPositions` die x-Skalierung entsprechend anpassen
kann (Lon-Delta * cosLat gibt naehrunungsweise gleiche Bogenlaeinge wie Lat-Delta).

Edge-Cases:
- Leere `waypoints`-Array: `boundingBox` gibt Nullwerte, `buildMapPositions` gibt
  leeres Array zurueck.
- Alle Waypoints am selben Punkt: alle x/y auf Mittelpunkt der SVG.

### §10 CSS-Fix: --g-ink-strong

`frontend/src/app.css` erhaelt folgenden Alias, damit bestehende Komponenten
(ProfileChart, WaypointPin) den Token nutzen koennen:

```css
:root {
  /* … bestehende Tokens … */
  --g-ink-strong: var(--g-ink);
}
```

Dieser Eintrag wird in der bestehenden `:root`-Sektion ergaenzt (kein neuer Block).

### §11 TripTabs.svelte — Platzhalter ersetzen

Der `stages`-Tab-Branch in `TripTabs.svelte` enthaelt heute einen Platzhalter.
Er wird ersetzt durch:

```svelte
{#if activeTab === 'stages'}
  <WaypointsPanel {trip} onSaved={() => dispatch('trip-updated')} />
{/if}
```

`WaypointsPanel` wird aus `$lib/components/trip-detail` importiert (nach Export
in `index.ts`).

### §12 TestID-Inventar

| TestID | Komponente | Zweck |
|--------|------------|-------|
| `waypoints-panel` | `WaypointsPanel.svelte` | Root-Container |
| `etappen-strip` | `EtappenStrip.svelte` | Strip-Container |
| `stage-card-{i}` | `StageCard.svelte` | Einzelne Etappen-Kachel (0-basiert) |
| `stage-card-pause-{i}` | `StageCard.svelte` | Pausentag-Kachel |
| `map-canvas` | `MapCanvas.svelte` | SVG-Karten-Container |
| `map-zoom-in` | `MapCanvas.svelte` | Zoom-in-Button |
| `map-zoom-out` | `MapCanvas.svelte` | Zoom-out-Button |
| `map-layer-toggle` | `MapCanvas.svelte` | Topo/Sat-Toggle |
| `profile-editor` | `ProfileEditor.svelte` | SVG-Hoehenprofil-Container |
| `waypoint-card-{i}` | `WaypointCard.svelte` | Einzelner Wegpunkt (0-basiert) |
| `waypoint-confirm-{i}` | `WaypointCard.svelte` | Bestaetigen-Button |
| `waypoint-reject-{i}` | `WaypointCard.svelte` | Verwerfen-Button |
| `waypoint-rename-{i}` | `WaypointCard.svelte` | Umbenennen-Button |
| `waypoint-delete-{i}` | `WaypointCard.svelte` | Loeschen-Button |
| `pause-stage-view` | `PauseStageView.svelte` | Pausentag-Ansicht |
| `waypoints-save-btn` | `WaypointsPanel.svelte` | Expliziter Speichern-Button |
| `waypoints-save-error` | `WaypointsPanel.svelte` | Fehler-Meldung nach fehlgeschlagenem Save |

## Expected Behavior

- **Input:** User oeffnet Tab „Etappen & Wegpunkte" auf einer Trip-Detail-Seite.
  `trip.stages` enthaelt 1–n Stages mit `waypoints[]`. Waypoints koennen
  `suggested: true` tragen (noch nicht bestaetigte Vorschlaege aus Step 3
  des Wizards) oder kein Flag (manuelle / bestaetigte Wegpunkte).
- **Output:**
  - EtappenStrip zeigt alle Stages horizontal als klickbare StageCards.
  - Aktive (Nicht-Pause-)Stage: MapCanvas zeigt Routenlinie + WaypointPins,
    ProfileEditor zeigt Hoehenprofil, WaypointCard-Liste zeigt alle Wegpunkte.
  - Aktive PauseStage: PauseStageView zeigt Standort-Info, kein MapCanvas.
  - Karte und Profil sind synchronisiert ueber `activeWaypointId`.
  - Klick Bestaetigen (suggested): `suggested`-Flag entfernt, Pin wird solid.
  - Klick Verwerfen (suggested): Waypoint aus Stage entfernt, WaypointCard verschwindet.
  - DnD in EtappenStrip: `localStages` neu geordnet, Speichern-Button aktiv.
  - Klick Speichern: PUT `/api/trips/:id` mit `stripSuggested(localStages)`.
- **Side effects:**
  - `localStages` (tiefer Klon von `trip.stages`) wird mutiert.
  - Kein direkter Prop-Write auf `trip.stages` — explizites Save-Pattern.
  - Bei erfolgreichem Save: `onSaved()` callback, optionaler Parent-Reload.
  - Bei Fehler: `saveError` State sichtbar im UI (TestID `waypoints-save-error`).

## Acceptance Criteria

- **AC-1:** Given Trip mit 3 Etappen / When User Tab „Etappen & Wegpunkte" oeffnet / Then EtappenStrip zeigt 3 StageCards horizontal sichtbar (TestID `stage-card-0`, `stage-card-1`, `stage-card-2`)
  - Test: (populated after /tdd-red)

- **AC-2:** Given Trip mit 2 Etappen + 1 Pausentag / When User EtappenStrip sieht / Then Pausentag-Kachel ist gestrichelt dargestellt (border-dashed, TestID `stage-card-pause-{i}`)
  - Test: (populated after /tdd-red)

- **AC-3:** Given DnD abgeschlossen / When User Etappe per Drag auf neue Position zieht und loslässt / Then `localStages` ist neu geordnet und Speichern-Button ist aktiv (TestID `waypoints-save-btn` enabled)
  - Test: (populated after /tdd-red)

- **AC-4:** Given Etappe mit GPX-Daten / When StageCard gerendert / Then `ElevSparkline`, km-Angabe und Aufstieg/Abstieg sichtbar im TestID `stage-card-{i}`
  - Test: (populated after /tdd-red)

- **AC-5:** Given aktive Etappe mit Waypoints / When MapCanvas gerendert / Then Routenlinie (`<polyline>`) mit `stroke="var(--g-accent)"` in SVG TestID `map-canvas` sichtbar
  - Test: (populated after /tdd-red)

- **AC-6:** Given Waypoint mit `suggested: true` / When WaypointPin gerendert / Then Pin hat `stroke-dasharray` gesetzt und `stroke="var(--g-warning)"`
  - Test: (populated after /tdd-red)

- **AC-7:** Given User klickt WaypointPin auf Karte / When `onWaypointActivate` feuert / Then `activeWaypointId` gesetzt und derselbe Pin in MapCanvas visuell aktiv (groesserer Radius oder Glow)
  - Test: (populated after /tdd-red)

- **AC-8:** Given aktive Etappe mit Waypoints / When ProfileEditor gerendert / Then Hoehenprofil mit Gridlines bei 25/50/75% sichtbar in TestID `profile-editor`
  - Test: (populated after /tdd-red)

- **AC-9:** Given User klickt Waypoint-Pin im ProfileEditor / When `onWaypointActivate` feuert / Then derselbe Pin ist in MapCanvas aktiv (`activeWaypointId` synchronisiert)
  - Test: (populated after /tdd-red)

- **AC-10:** Given Waypoint mit `suggested: true` / When WaypointCard gerendert / Then Bestaetigen-Button (TestID `waypoint-confirm-{i}`) und Verwerfen-Button (TestID `waypoint-reject-{i}`) sichtbar
  - Test: (populated after /tdd-red)

- **AC-11:** Given Waypoint ohne `suggested`-Flag / When WaypointCard gerendert / Then Umbenennen-Button (TestID `waypoint-rename-{i}`) und Loeschen-Button (TestID `waypoint-delete-{i}`) sichtbar; Bestaetigen-Button nicht vorhanden
  - Test: (populated after /tdd-red)

- **AC-12:** Given User klickt Speichern / When kein Netzwerkfehler / Then PUT `/api/trips/:id` aufgerufen mit `stripSuggested(localStages)` (kein `suggested`-Flag in Payload)
  - Test: (populated after /tdd-red)

- **AC-13:** Given aktive Stage ist Pausentag (`waypoints.length === 0`) / When User Tab `stages` oeffnet / Then `PauseStageView` (TestID `pause-stage-view`) statt MapCanvas + ProfileEditor gerendert
  - Test: (populated after /tdd-red)

- **AC-14:** Given Stage mit `suggested: true` Waypoints / When `stripSuggested(stages)` aufgerufen / Then returned Stages enthalten keinen Waypoint mehr mit `suggested: true`
  - Test: (populated after /tdd-red)

- **AC-15:** Given Waypoints mit lat/lon / When `buildMapPositions(stage, 400, 300)` aufgerufen / Then x/y-Koordinaten liegen alle im Bereich [0, 400] bzw. [0, 300] und Seitenverhaeltnis ist korrekt skaliert (Cos-Korrektur angewandt)
  - Test: (populated after /tdd-red)

## Datei-Liste

### NEU

| Datei | Zweck | LoC (Schaetzung) |
|-------|-------|------------------|
| `frontend/src/lib/components/trip-detail/WaypointsPanel.svelte` | Parent/State-Owner, Layout (Strip + 2-Spalten) | ~100 |
| `frontend/src/lib/components/trip-detail/waypoints/WaypointPin.svelte` | SVG-Pin mit Nummer, aktiv/suggested-Stile | ~50 |
| `frontend/src/lib/components/trip-detail/waypoints/StageCard.svelte` | Etappen-Kachel mit Sparkline, km, Hoehendaten | ~70 |
| `frontend/src/lib/components/trip-detail/waypoints/EtappenStrip.svelte` | Horizontaler Strip mit DnD, Pause-Inserter | ~90 |
| `frontend/src/lib/components/trip-detail/waypoints/MapCanvas.svelte` | SVG-Karte, Koordinaten-Normierung, Zoom, Layer | ~120 |
| `frontend/src/lib/components/trip-detail/waypoints/ProfileEditor.svelte` | SVG-Hoehenprofil, Gridlines, klickbare Pins | ~100 |
| `frontend/src/lib/components/trip-detail/waypoints/WaypointCard.svelte` | Wegpunkt-Listeneintrag, Aktionen je Typ | ~80 |
| `frontend/src/lib/components/trip-detail/waypoints/PauseStageView.svelte` | Pausentag-Ansicht mit Standort-Info | ~50 |
| `frontend/src/lib/utils/waypointEditor.ts` | Pure Functions: `stripSuggested`, `buildMapPositions`, `boundingBox` | ~60 |
| `frontend/src/lib/utils/waypointEditor.test.ts` | Unit-Tests fuer Pure Functions (AC-14, AC-15) | ~80 |

### EDIT

| Datei | Aenderung | LoC |
|-------|-----------|-----|
| `frontend/src/lib/components/trip-detail/TripTabs.svelte` | Platzhalter `stages`-Tab-Branch durch `<WaypointsPanel>` ersetzen | +5 / -3 |
| `frontend/src/lib/components/trip-detail/index.ts` | `WaypointsPanel` exportieren | +1 |
| `frontend/src/app.css` | `--g-ink-strong: var(--g-ink)` als Alias in `:root` ergaenzen | +1 |

### NICHT BERUEHRT

- `frontend/src/lib/types.ts` (kein neues Feld — `Waypoint.suggested?` bereits vorhanden)
- `frontend/src/lib/components/trip-wizard/` (kein Wizard-Touch)
- `internal/`, `src/`, `cmd/`, `api/` (kein Backend-Touch)
- `frontend/src/lib/components/ui/` (alle Atom-Komponenten werden nur konsumiert)

## Known Limitations

- **Kein Undo fuer Verwerfen.** Wer einen Wegpunkt versehentlich verwirft oder
  loescht, muss die Seite neu laden (bringt den letzten gespeicherten Stand zurueck).
  Folge-Issue falls Bedarf besteht.
- **MapCanvas ist SVG, kein echter Kartendienst.** Koordinaten werden auf eine
  Pseudo-Topokarte normiert; keine Tiles, kein Routing. Der Sat-Layer-Toggle
  schaltet lediglich `TopoBg` aus (einfarbiger Fallback-Hintergrund). Echter
  Tile-basierter Kartendienst ist nicht in Scope dieses Epics.
- **Kein Inline-Rename-Dialog spezifiziert.** Der Umbenennen-Button (`onRename`)
  ist implementierungsseitig offen — entweder inline `<input>` oder Modal.
  Die Spec gibt nur die Schnittstelle vor; genaue UX wird in Phase 6 entschieden.
- **DnD und Pausentage:** EtappenStrip erlaubt es, eine regulaere Etappe an die
  Position eines Pausentags zu ziehen. Datums-Konsistenz wird nicht automatisch
  neu berechnet — der User traegt dafuer Verantwortung. Datum-Rebalancing ist
  Folge-Issue.
- **Mobile-Responsive nicht spezifiziert.** Das 2-Spalten-Layout (Karte+Profil
  links, Waypoint-Liste rechts) bricht auf schmalem Viewport um. Nicht aktiv
  getestet in diesem Epic — das Frontend ist ein Desktop-Planungstool (CLAUDE.md).
- **Sehr viele Waypoints (>50):** Pin-Overlapping in MapCanvas und ProfileEditor
  tolerierbar fuer typische GR20-Etappen mit 5–20 Wegpunkten. Keine Virtualisierung
  in diesem Epic.

## Not In Scope

- **Waypoint hinzufuegen per Klick auf Karte** — Folge-Issue.
- **Koordinaten-Eingabefelder** fuer Waypoints — explizit ausgeschlossen.
- **Echter Tile-Kartendienst** (Leaflet, Mapbox) — Folge-Epic.
- **Datum-Rebalancing nach DnD** — Folge-Issue.
- **Undo/Redo** — Folge-Issue.
- **Backend-Aenderungen** — `PUT /api/trips/:id` ist bestehender Endpunkt.
- **Neue `isPauseStage`-Felder** — Definition bleibt `waypoints.length === 0`.
- **Bulk-Aktionen** (alle bestaetigen, alle verwerfen) — Folge-Issue.
- **A11y-Erweiterungen ueber ARIA-Labels hinaus** (Keyboard-Navigation im SVG).

## Verweise

- **Master-Spec:** [`epic_136_trip_wizard.md`](./epic_136_trip_wizard.md)
- **Vorgaenger-Sub-Spec Step 3:** [`epic_136_step3_waypoints.md`](./epic_136_step3_waypoints.md)
  (#163 — WaypointPin-Stil, ProfileChart-Schema, `stripSuggested`-Referenz)
- **Issues:** [#166 EtappenStrip](https://github.com/henemm/gregor_zwanzig/issues/166),
  [#167 StageCard](https://github.com/henemm/gregor_zwanzig/issues/167),
  [#168 MapCanvas](https://github.com/henemm/gregor_zwanzig/issues/168),
  [#169 WaypointPin](https://github.com/henemm/gregor_zwanzig/issues/169),
  [#170 ProfileEditor](https://github.com/henemm/gregor_zwanzig/issues/170),
  [#171 WaypointCard](https://github.com/henemm/gregor_zwanzig/issues/171),
  [#172 PauseStageView](https://github.com/henemm/gregor_zwanzig/issues/172)
- **Epic:** [#137 — EPIC 5 Wegpunkt-Editor](https://github.com/henemm/gregor_zwanzig/issues/137)
- **Design-System:** `docs/reference/design_system.md` + `frontend/src/app.css`

## Changelog

- 2026-05-17: Initiale Spec erstellt. 8 neue Komponenten + 1 Parent (WaypointsPanel),
  2 neue Utility-Dateien (waypointEditor.ts + .test.ts), 3 EDIT-Dateien.
  Architektur: WaypointsPanel als State-Owner (Svelte-5-Runes, tiefer Klon,
  expliziter Save-Button), Karte-Profil-Sync via `activeWaypointId` Prop,
  DnD via svelte-dnd-action horizontal, Koordinaten-Normierung mit Cos-Korrektur,
  CSS-Alias `--g-ink-strong` in app.css. 15 Acceptance Criteria (AC-1 bis AC-15),
  vollstaendiges TestID-Inventar, Datei-Liste mit LoC-Schaetzungen.

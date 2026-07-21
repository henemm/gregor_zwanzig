---
entity_id: epic_135_step4_left_column
type: module
created: 2026-05-12
updated: 2026-05-12
status: draft
version: "1.0"
parent_spec: epic_135_trip_detail
related: epic_135_step3_trip_hero, epic_136_step3_waypoints
issues: [156, 157]
followup_issue: 203
tags: [frontend, sveltekit, svelte5, trip-detail, epic-135, issue-156, issue-157]
---

# Epic 135 — Sub-Spec #156 + #157: Trip-Detail Overview, linke Spalte (Full-Profil + Stage-Liste)

## Approval

- [ ] Approved

## Purpose

Erweitert das Overview-Tab der Trip-Detail-Seite unterhalb des `TripHero` (Step 3) um die linke Spalte: ein kombiniertes Full-Profil-SVG aller Etappen (#156) und darunter eine vertikale Stage-Row-Liste mit KPIs pro Etappe (#157). Beide Komponenten teilen einen `selectedStageId`-State — Klick im Profil markiert die zugehörige Card; Klick auf eine Card markiert das Segment im Profil. Eine neue `TripOverview.svelte` kapselt den Hero und das 2-Spalten-Grid `[2fr_1fr]`; die rechte Spalte bleibt vorerst leer und wird in den Folge-Issues #158 (Tagespanel) und #159 (Briefing-Konfigurator) gefüllt, ohne dass `TripOverview` erneut editiert werden muss.

## Source

- **NEU:** `frontend/src/lib/components/trip-detail/TripOverview.svelte` — Wrapper: Hero + 2-Spalten-Grid, `selectedStageId` als `$state`
- **NEU:** `frontend/src/lib/components/trip-detail/FullProfile.svelte` — Multi-Stage-SVG-Profil mit Active/Selected-Highlights und Klick-Hit-Areas
- **NEU:** `frontend/src/lib/components/trip-detail/StageList.svelte` — Container für Stage-Cards + Empty-State
- **NEU:** `frontend/src/lib/components/trip-detail/StageDetailRow.svelte` — Stage-Card mit Code, Datum, km, Hm, Waypoint-Count, Klick-Handler
- **NEU:** `frontend/src/lib/utils/fullProfile.ts` — Pure-Functions: `buildProfilePoints`, `computeStageBoundaries`, `formatStageCode`, `getActiveStageId`
- **NEU:** `frontend/src/lib/utils/fullProfile.test.ts` — Vitest-Unit-Tests (mind. 20)
- **NEU:** `frontend/e2e/trip-detail-overview-left.spec.ts` — Playwright E2E (mind. 10)
- **EDIT:** `frontend/src/lib/components/trip-detail/TripTabs.svelte` — Overview-Panel rendert `<TripOverview {trip} />` statt direktem Hero
- **EDIT:** `frontend/src/lib/components/trip-detail/index.ts` — Barrel-Export von `TripOverview`, `FullProfile`, `StageList`, `StageDetailRow`
- **EDIT (evtl.):** `frontend/e2e/global.setup.ts` — Test-Trip-Stages mit komplexerem Waypoint-Set, falls bestehendes Setup für E2E-Stabilität zu dünn
- **Identifier:** `buildProfilePoints`, `computeStageBoundaries`, `formatStageCode`, `getActiveStageId`, `TripOverview`, `FullProfile`, `StageList`, `StageDetailRow`

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/src/lib/types.ts` (`Trip`, `Stage`, `Waypoint`) | bestehend | Datenmodell: `Trip.stages`, `Stage.id`, `Stage.name`, `Stage.date`, `Stage.waypoints`, `Waypoint.lat`, `Waypoint.lon`, `Waypoint.elevation_m` |
| `frontend/src/lib/components/email-preview/headerStats.ts` (`computeHeaderStats`) | bestehend | Liefert `distanceKm`, `ascentM`, `descentM`, `maxElevationM` pro Stage (Haversine über Waypoints) — direkt in `StageDetailRow` genutzt |
| `frontend/src/lib/utils/tripStatus.ts` (`deriveTripStatus`) | bestehend (Step 2) | Liefert Trip-Status; `getActiveStageId` ruft das auf, um zwischen `active`/sonst zu unterscheiden |
| `frontend/src/lib/components/trip-detail/TripHero.svelte` | bestehend (Step 3) | Wird von `TripOverview` über `<TripHero {trip} />` eingebunden; bleibt unverändert |
| `frontend/src/lib/components/trip-detail/TripTabs.svelte` | bestehend (EDIT) | Overview-Panel-Inhalt von `<TripHero {trip} />` auf `<TripOverview {trip} />` umstellen; Import-Statement austauschen |
| `frontend/src/lib/components/trip-detail/index.ts` | bestehend (EDIT) | Barrel: 4 neue Komponenten exportieren |
| `frontend/src/lib/components/ui/g-card/` | bestehend | Card-Container-Pattern für `StageDetailRow` (visuelle Konsistenz mit Cockpit) |
| `frontend/src/lib/components/ui/pill/Pill.svelte` | bestehend | Stage-Code-Pill (`T01`, `T02`, `P`) in `StageDetailRow` |
| `frontend/src/lib/components/ui/eyebrow/` | bestehend | Eyebrow-Beschriftungen in `StageDetailRow` (Datum/Distanz/Hm) |
| `frontend/src/app.css` (Tokens) | bestehend | `--g-accent` für aktive Stage (Fill, Opacity 0.15) und Selected-Outline; allgemeine Card-/Pill-Tokens |
| `frontend/src/lib/components/trip-wizard/steps/ProfileChart.svelte` | bestehend (Referenz) | Single-Stage-Vorbild für SVG-Polyline; `FullProfile` ist die Multi-Stage-Generalisierung |
| `frontend/src/routes/_cockpit/ActiveTripCard.svelte` | bestehend (Referenz) | Stil-Vorbild für `StageDetailRow`-Layout (Eyebrow + H2 + Stat-Strip) |
| `frontend/e2e/global.setup.ts` (`e2e-cockpit-test`) | bestehend | Test-Trip mit 3 Stages und 1–2 Waypoints (elevation_m 800/1200/600/400 m) — Grundlage für alle E2E-Assertions |
| `frontend/e2e/trip-detail-hero.spec.ts` | bestehend (Regressions-Guard) | Step-3-Test darf nach TripTabs-Edit nicht brechen |

## Implementation Details

### §1 Pure-Functions `frontend/src/lib/utils/fullProfile.ts`

Alle vier Funktionen sind pure (kein Side-Effect, kein I/O), vollständig unit-testbar.

```typescript
import type { Trip, Stage } from '$lib/types';
import { deriveTripStatus } from './tripStatus';

export interface ProfilePoint {
  x: number;        // kumulative Distanz in km
  y: number;        // elevation_m
  stageId: string;  // Stage-Zugehörigkeit, für Lookup
}

export interface StageBoundary {
  stageId: string;
  xStart: number;   // kumulative km am ersten Waypoint der Stage
  xEnd: number;     // kumulative km am letzten Waypoint der Stage
  code: string;     // T01, T02, P (für Pause)
}

export function buildProfilePoints(trip: Trip): ProfilePoint[] {
  // Iteriert über trip.stages in Reihenfolge und über stage.waypoints in Reihenfolge.
  // Hält einen Cursor (cumKm) über Stages hinweg.
  // Pro Waypoint:
  //   - distance(prev, current) via Haversine (analog headerStats.ts) -> addiere zu cumKm
  //   - falls waypoint.elevation_m null/undefined -> Punkt überspringen, cumKm aber updaten
  //                                                  (Distanz-Achse bleibt konsistent)
  //   - sonst: push { x: cumKm, y: elevation_m, stageId: stage.id }
  // Stage ohne Waypoints -> komplett übersprungen (keine Polyline-Punkte),
  //   computeStageBoundaries kümmert sich um Label-Position via Code.
  // Erster Waypoint überhaupt: cumKm = 0.
}

export function computeStageBoundaries(trip: Trip): StageBoundary[] {
  // Iteriert parallel zu buildProfilePoints und merkt sich pro Stage
  //   xStart (cumKm vor erstem Waypoint der Stage)
  //   xEnd   (cumKm nach letztem Waypoint der Stage)
  // Stage ohne Waypoints: xStart === xEnd (Null-Breite); Code-Label wird trotzdem erzeugt.
  // Pause-Stages werden separat über formatStageCode gehandhabt (Code = 'P').
  // nonPauseIndex wird mitgezählt, um T01/T02 vergeben zu können.
}

export function formatStageCode(nonPauseIndex: number, isPause: boolean): string {
  // isPause === true -> 'P'
  // sonst: 'T' + (nonPauseIndex + 1).toString().padStart(2, '0')
  //   nonPauseIndex 0 -> 'T01'
  //   nonPauseIndex 9 -> 'T10'
  //   nonPauseIndex 99 -> 'T100' (dreistellig, kein Padding-Verbot)
}

export function getActiveStageId(trip: Trip, now: Date): string | null {
  // deriveTripStatus(trip, now) !== 'active' -> return null
  // sonst: today = YYYY-MM-DD aus now (lokale Zeit, Tages-Granularität)
  //        return stages.find(s => s.date === today)?.id ?? null
}
```

**Pause-Heuristik:** Stage gilt als Pause, wenn `stage.date` identisch zum vorherigen Stage-Datum ist (Wizard-Konvention aus Epic #136) oder ein explizites Pause-Flag im Stage-Modell folgt. In Phase 6 wird die genaue Heuristik anhand des aktuellen Wizard-Helpers (`wizardHelpers.ts`) übernommen — keine eigene Erfindung.

### §2 `frontend/src/lib/components/trip-detail/TripOverview.svelte`

**Prop-Signatur:**

```typescript
import type { Trip } from '$lib/types';
import TripHero from './TripHero.svelte';
import FullProfile from './FullProfile.svelte';
import StageList from './StageList.svelte';

interface Props {
  trip: Trip;
  now?: Date; // default new Date() — testbar injizierbar
}
let { trip, now = new Date() }: Props = $props();

let selectedStageId = $state<string | null>(null);

function handleSelectStage(id: string) {
  selectedStageId = id;
}
```

**Template-Struktur:**

```svelte
<section data-testid="trip-overview">
  <TripHero {trip} {now} />

  <div class="grid grid-cols-1 lg:grid-cols-[2fr_1fr] gap-6 mt-6">
    <div data-testid="trip-overview-left-column" class="space-y-6">
      <FullProfile {trip} {selectedStageId} onSelectStage={handleSelectStage} {now} />
      <StageList {trip} {selectedStageId} onSelectStage={handleSelectStage} {now} />
    </div>

    <aside data-testid="trip-overview-right-column">
      <!-- Platzhalter für #158 (Tagespanel) und #159 (Briefing-Konfigurator) -->
    </aside>
  </div>
</section>
```

Unter Tailwind `lg:`-Breakpoint (Desktop) Grid 2:1, darunter (Mobile/Tablet) gestapelt — Frontend bleibt Desktop-Planung, Mobile ist nice-to-have. Die rechte Spalte ist bewusst leer; die folgenden Sub-Issues füllen sie nur durch Einsetzen weiterer Komponenten in das `<aside>`.

### §3 `frontend/src/lib/components/trip-detail/FullProfile.svelte`

**Prop-Signatur:**

```typescript
import type { Trip } from '$lib/types';
import {
  buildProfilePoints,
  computeStageBoundaries,
  getActiveStageId,
  type ProfilePoint,
  type StageBoundary,
} from '$lib/utils/fullProfile';

interface Props {
  trip: Trip;
  selectedStageId: string | null;
  onSelectStage: (id: string) => void;
  now?: Date;
}
let { trip, selectedStageId, onSelectStage, now = new Date() }: Props = $props();

const points = $derived(buildProfilePoints(trip));
const boundaries = $derived(computeStageBoundaries(trip));
const activeStageId = $derived(getActiveStageId(trip, now));
```

**SVG-Aufbau (ViewBox-basiert, responsive):**

- ViewBox z.B. `0 0 1000 220` (Breite 1000, Höhe 220 inkl. Label-Streifen unten).
- Y-Skalierung: `[min(elevation) - pad, max(elevation) + pad]`, `pad = 5 %` der Range. Fallback `pad = 50` bei flachem Profil.
- X-Skalierung: `[0, max(x)]` aus `points`. Fallback bei 0 km Gesamt: leerer Empty-State.
- Reihenfolge der SVG-Children (Z-Order von unten nach oben):
  1. Aktive-Stage-Fill: `<rect>` über `xStart..xEnd` der aktiven Stage, Höhe = volle Profil-Höhe, `fill: var(--g-accent)`, `opacity: 0.15`.
  2. Selected-Stage-Outline: `<rect>` über `xStart..xEnd` der selected Stage, `fill: none`, `stroke: var(--g-accent)`, `stroke-width: 2`.
  3. Polyline der Profil-Punkte: `<polyline>` mit `fill: none`, `stroke: currentColor`, `stroke-width: 1.5`.
  4. Hit-Areas: pro Stage ein transparentes `<rect data-testid="trip-full-profile-stage-{stageId}">` über `xStart..xEnd × volle Höhe` mit `pointer-events: all` und `on:click={() => onSelectStage(stageId)}`.
  5. Stage-Labels: `<text data-testid="trip-full-profile-label-{stageId}">{code}</text>` zentriert unter dem Segment, unterhalb der Profil-Fläche.

**Selected-Fallback:** Wenn `selectedStageId === null` und `activeStageId !== null`, wird der Selected-Outline nicht angezeigt (Fill aus 1. reicht). Erst nach explizitem User-Klick erscheint die Outline. Active-Highlight und Selected-Outline können gleichzeitig sichtbar sein, wenn der User die aktive Stage anklickt (Fill + Outline beide an).

**Empty-State:** Wenn `points.length === 0` UND `boundaries.length === 0` (Trip ohne Stages) → `<p data-testid="trip-full-profile-empty">Keine Etappen geplant</p>` statt SVG.

**Safari-Kompatibilität:** Click-Handler werden über benannte Closures gebunden (`function makeStageClickHandler(id) { return function onStageClick() { onSelectStage(id); }; }`), nicht über Inline-Arrows mit Loop-Variable.

### §4 `frontend/src/lib/components/trip-detail/StageList.svelte`

**Prop-Signatur:**

```typescript
import type { Trip } from '$lib/types';
import StageDetailRow from './StageDetailRow.svelte';
import { computeStageBoundaries, getActiveStageId } from '$lib/utils/fullProfile';

interface Props {
  trip: Trip;
  selectedStageId: string | null;
  onSelectStage: (id: string) => void;
  now?: Date;
}
let { trip, selectedStageId, onSelectStage, now = new Date() }: Props = $props();

const boundaries = $derived(computeStageBoundaries(trip));
```

**Template-Struktur:**

```svelte
<div data-testid="trip-stage-list" class="space-y-3">
  {#if trip.stages.length === 0}
    <p data-testid="trip-stage-empty">Keine Etappen geplant</p>
  {:else}
    {#each trip.stages as stage, index (stage.id)}
      {@const boundary = boundaries.find(b => b.stageId === stage.id)}
      <StageDetailRow
        {stage}
        {index}
        code={boundary?.code ?? ''}
        selected={selectedStageId === stage.id}
        active={getActiveStageId(trip, now) === stage.id}
        onSelect={() => onSelectStage(stage.id)}
        {now}
      />
    {/each}
  {/if}
</div>
```

`getActiveStageId` wird direkt importiert (gleiche Source-of-Truth wie FullProfile, damit Active-State sicher übereinstimmt).

### §5 `frontend/src/lib/components/trip-detail/StageDetailRow.svelte`

**Prop-Signatur:**

```typescript
import type { Stage } from '$lib/types';
import { computeHeaderStats } from '$lib/components/email-preview/headerStats';
import Pill from '$lib/components/ui/pill/Pill.svelte';

interface Props {
  stage: Stage;
  index: number;
  code: string;            // 'T01', 'T02', 'P'
  selected: boolean;
  active: boolean;
  onSelect: () => void;
  now?: Date;
}
let { stage, index, code, selected, active, onSelect, now = new Date() }: Props = $props();

const stats = $derived(computeHeaderStats(stage));
const wptCount = $derived(stage.waypoints?.length ?? 0);
```

**Template-Struktur (GCard-Pattern):**

```svelte
<button
  type="button"
  data-testid="trip-stage-row-{stage.id}"
  data-selected={selected ? 'true' : 'false'}
  data-active={active ? 'true' : 'false'}
  class="g-card text-left w-full"
  onclick={onSelect}
>
  <header class="flex items-center gap-2">
    <Pill tone={active ? 'accent' : 'default'} data-testid="trip-stage-row-code-{stage.id}">
      {code}
    </Pill>
    <span class="eyebrow">{formatDate(stage.date)}</span>
  </header>

  <h3>{stage.name}</h3>

  <dl class="stat-strip">
    <div><dt class="eyebrow">Distanz</dt><dd>{stats.distanceKm.toFixed(1)} km</dd></div>
    <div><dt class="eyebrow">Aufstieg</dt><dd>{stats.ascentM} Hm</dd></div>
    <div><dt class="eyebrow">Abstieg</dt><dd>{stats.descentM} Hm</dd></div>
    <div><dt class="eyebrow">Wegpunkte</dt><dd>{wptCount}</dd></div>
  </dl>
</button>
```

**Klick-Handler:** Native `<button>`-Element, `onclick={onSelect}` — keine Closure mit Loop-Index nötig, weil `onSelect` bereits in `StageList` pro Stage gebunden wird. Safari-tauglich.

**`formatDate`:** Lokaler Helper (in derselben Datei), formatiert `stage.date` (ISO `YYYY-MM-DD`) zu deutschem Kurzformat „DD.MM." — keine externen Locale-Abhängigkeiten.

### §6 TripTabs-Edit `frontend/src/lib/components/trip-detail/TripTabs.svelte`

**Vorher (Step 3):**

```svelte
import { TripHero } from '$lib/components/trip-detail';
...
{#if trip}
  <TripHero {trip} />
{:else}
  <p class="text-muted-foreground">Lade Trip-Daten…</p>
{/if}
```

**Nachher (Step 4):**

```svelte
import { TripOverview } from '$lib/components/trip-detail';
...
{#if trip}
  <TripOverview {trip} />
{:else}
  <p class="text-muted-foreground">Lade Trip-Daten…</p>
{/if}
```

`TripOverview` rendert intern `<TripHero {trip} />` als erstes Child — alle TestIDs aus Step 3 (`trip-hero`, `trip-hero-title`, `trip-hero-stat-*`) bleiben unverändert sichtbar. Damit ist `trip-detail-hero.spec.ts` (Step 3 E2E) regressions-frei.

### §7 Barrel-Edit `frontend/src/lib/components/trip-detail/index.ts`

Vier neue Zeilen ergänzen:

```typescript
export { default as TripOverview } from './TripOverview.svelte';
export { default as FullProfile } from './FullProfile.svelte';
export { default as StageList } from './StageList.svelte';
export { default as StageDetailRow } from './StageDetailRow.svelte';
```

Bestehende Exports (`TripHero` aus Step 3, Header/Tabs aus Step 1/2) bleiben unverändert.

### §8 TestID-Inventar

| TestID | Element | Zweck |
|--------|---------|-------|
| `trip-overview` | `<section>` Wrapper | Container von Hero + 2-Spalten-Grid; Existenz-Check |
| `trip-overview-left-column` | `<div>` linke Spalten-Wrapper | Marker für FullProfile + StageList Region |
| `trip-overview-right-column` | `<aside>` rechte Spalten-Wrapper | Platzhalter-Region für #158 + #159, in Step 4 leer |
| `trip-full-profile` | `<div>` SVG-Wrapper | Profil-Existenz-Check |
| `trip-full-profile-stage-{stageId}` | `<rect>` Hit-Area | Klick-Ziel pro Stage |
| `trip-full-profile-label-{stageId}` | `<text>` Stage-Code unter SVG | Sichtbarkeits-/Reihenfolge-Check |
| `trip-full-profile-empty` | `<p>` | Empty-State bei `stages.length === 0` |
| `trip-stage-list` | `<div>` Listen-Wrapper | Container-Check; enthält N Cards |
| `trip-stage-row-{stageId}` | `<button>` Card | Klick-Ziel + State-Indikator (`data-selected`, `data-active`) |
| `trip-stage-row-code-{stageId}` | `Pill` in Card | Code-Pill (`T01`, `T02`, `P`) Sichtbarkeit |
| `trip-stage-empty` | `<p>` | Empty-State der Liste |

### §9 Datei-Liste

| Art | Datei | Zweck | LoC |
|-----|-------|-------|-----|
| NEU | `frontend/src/lib/components/trip-detail/TripOverview.svelte` | Wrapper: Hero + 2-Spalten-Grid `[2fr_1fr]`, `selectedStageId` als `$state` | ~60 |
| NEU | `frontend/src/lib/components/trip-detail/FullProfile.svelte` | SVG-Profil, Multi-Stage-Polyline, Active+Selected Highlights, Klick-Hit-Areas | ~160 |
| NEU | `frontend/src/lib/components/trip-detail/StageList.svelte` | Container für StageDetailRow + Empty-State | ~50 |
| NEU | `frontend/src/lib/components/trip-detail/StageDetailRow.svelte` | Stage-Card mit Code/Titel/Datum/km/Hm/Wpt-Count, Klick-Handler, `data-selected`/`data-active` | ~90 |
| NEU | `frontend/src/lib/utils/fullProfile.ts` | Pure-Functions: `buildProfilePoints`, `computeStageBoundaries`, `formatStageCode`, `getActiveStageId` | ~130 |
| NEU | `frontend/src/lib/utils/fullProfile.test.ts` | Vitest-Unit-Tests, mind. 20 | ~180 |
| NEU | `frontend/e2e/trip-detail-overview-left.spec.ts` | Playwright E2E, mind. 10 Tests | ~120 |
| EDIT | `frontend/src/lib/components/trip-detail/TripTabs.svelte` | Overview-Panel: `<TripOverview {trip} />` statt `<TripHero {trip} />`, Import austauschen | +2/-3 |
| EDIT | `frontend/src/lib/components/trip-detail/index.ts` | Barrel-Export 4 neuer Komponenten | +4 |
| EDIT (evtl.) | `frontend/e2e/global.setup.ts` | Test-Trip-Stages mit komplexerem Waypoint-Set, nur falls bestehendes Setup zu dünn | ~+30 |
| **Summe** | | | **~825 LoC** |

**LoC-Override erforderlich vor Phase 6:** `workflow.py set-field loc_limit_override 850 --name epic_135_step4_left_column`

## Expected Behavior

- **Input:** `Trip`-Objekt mit `name`, `stages[]` (mit `id`, `name`, `date`, `waypoints[]`), `waypoints` mit `lat`/`lon`/`elevation_m?`; optional `now: Date` (default `new Date()`).
- **Output:**
  - `buildProfilePoints(trip)` liefert eine deterministische Liste `{x, y, stageId}` für alle Waypoints mit gültigem `elevation_m`; Distanz-Cursor wächst stage-übergreifend monoton.
  - `computeStageBoundaries(trip)` liefert pro Stage `{stageId, xStart, xEnd, code}`; Pause-Stages bekommen `code === 'P'`, sonst `T01..T0N`.
  - `formatStageCode(0, false) === 'T01'`; `formatStageCode(2, true) === 'P'`.
  - `getActiveStageId(trip, now)` liefert die heutige Stage-ID, falls Trip-Status `'active'` ist; sonst `null`.
  - `TripOverview` rendert `<TripHero>` + 2-Spalten-Grid; linke Spalte enthält `FullProfile` und `StageList` in dieser Reihenfolge; rechte Spalte ist sichtbar aber leer.
  - `FullProfile` rendert SVG mit Polyline, Active-Fill (falls aktive Stage), Selected-Outline (falls `selectedStageId !== null`), Stage-Hit-Areas und Stage-Labels.
  - `StageList` rendert N `StageDetailRow` für N Stages bzw. `trip-stage-empty` bei leerer Liste.
  - `StageDetailRow` zeigt Code-Pill, Datum, Distanz (km), Aufstieg (Hm), Abstieg (Hm), Waypoint-Count, Stage-Name; `data-selected="true"` wenn ausgewählt, `data-active="true"` wenn heute.
- **Side effects:**
  - Keine externen — alle Berechnungen sind pure. UI-State (`selectedStageId`) lebt ausschließlich in `TripOverview` als `$state`; Klicks in beiden Kindern rufen `handleSelectStage` auf und triggern reaktive Re-Renders via `$derived`.
  - Keine API-Calls in Step 4 — alle Daten kommen aus dem `trip`-Prop, das `+page.server.ts` (Step 2) bereits geladen hat.

## Acceptance Criteria

- **AC-1:** Given eine gerenderte Trip-Detail-Seite mit gültigem Trip / When das Overview-Tab aktiv ist / Then sind `data-testid="trip-overview"`, darin `data-testid="trip-hero"`, `data-testid="trip-overview-left-column"` und `data-testid="trip-overview-right-column"` sichtbar.
  - Test: (populated after /tdd-red)

- **AC-2:** Given eine gerenderte `TripOverview` mit Trip / When der DOM der linken Spalte inspiziert wird / Then sind `data-testid="trip-full-profile"` und `data-testid="trip-stage-list"` in genau dieser DOM-Reihenfolge unterhalb des Hero sichtbar.
  - Test: (populated after /tdd-red)

- **AC-3:** Given ein Trip mit 3 Stages und mindestens je einem Waypoint mit `elevation_m` / When `FullProfile` gerendert wird / Then enthält der DOM ein `<svg>`-Element, ein `<polyline>` mit mindestens 3 Punkten sowie genau 3 Elemente mit `data-testid="trip-full-profile-stage-{stageId}"` (Hit-Areas).
  - Test: (populated after /tdd-red)

- **AC-4:** Given ein Trip mit 3 Stages in Reihenfolge S1, S2, S3 / When `FullProfile` gerendert wird / Then sind die Stage-Code-Labels (`data-testid="trip-full-profile-label-{stageId}"`) in der DOM-Reihenfolge S1, S2, S3 angeordnet (entspricht visuell links-nach-rechts).
  - Test: (populated after /tdd-red)

- **AC-5:** Given ein Trip mit Status `active` und einer Stage, deren `date === today` / When `FullProfile` gerendert wird, ohne dass der User klickt / Then hat das Hit-Area-Rechteck der aktiven Stage einen sichtbaren Active-Fill (`fill: var(--g-accent)`, `opacity: 0.15`) — geprüft über das gerenderte SVG-Attribut oder eine erkennbare CSS-Klasse.
  - Test: (populated after /tdd-red)

- **AC-6:** Given eine gerenderte `TripOverview` mit 3 Stages / When der User auf `data-testid="trip-full-profile-stage-{stages[1].id}"` klickt / Then ist `selectedStageId === stages[1].id` und im SVG erscheint eine Outline-`<rect>` mit `stroke: var(--g-accent)` über dem Segment der zweiten Stage.
  - Test: (populated after /tdd-red)

- **AC-7:** Given ein Trip mit 3 Stages / When `StageList` gerendert wird / Then sind genau 3 Elemente mit `data-testid="trip-stage-row-{stageId}"` sichtbar, in derselben Reihenfolge wie `trip.stages`.
  - Test: (populated after /tdd-red)

- **AC-8:** Given ein Trip mit Stage `{id: "s1", name: "Vizzavona", date: "2026-05-12", waypoints: [<2 waypoints mit elevation>]}` / When `StageDetailRow` für diese Stage gerendert wird / Then enthält das DOM den Code-Pill (`data-testid="trip-stage-row-code-s1"`) mit Text `"T01"`, das Datum `"12.05."`, einen km-Wert > 0, Aufstieg-Hm, Abstieg-Hm, Waypoint-Count `2` und den Text `"Vizzavona"`.
  - Test: (populated after /tdd-red)

- **AC-9:** Given eine gerenderte `TripOverview` mit 3 Stages / When der User auf `data-testid="trip-stage-row-{stages[0].id}"` klickt / Then hat dieses Element `data-selected="true"`, alle anderen Cards `data-selected="false"`, und im SVG ist die Outline-`<rect>` über Segment 1 sichtbar.
  - Test: (populated after /tdd-red)

- **AC-10:** Given eine gerenderte `TripOverview` mit 3 Stages, der User klickt zuerst im Profil auf Stage 2 und dann auf die Card von Stage 1 / When beide Klicks verarbeitet wurden / Then ist Card 1 `data-selected="true"`, Card 2 `data-selected="false"`, und das SVG zeigt die Outline über Segment 1 (Selected-State ist über beide Komponenten in Sync).
  - Test: (populated after /tdd-red)

- **AC-11:** Given ein Trip mit drei Stages, davon eine Stage ohne Waypoints / When `buildProfilePoints(trip)` aufgerufen wird / Then enthält das Ergebnis keine Punkte mit `stageId` dieser Stage; `computeStageBoundaries(trip)` liefert für sie trotzdem einen Eintrag mit gültigem `code` (und `xStart === xEnd`).
  - Test: (populated after /tdd-red)

- **AC-12:** Given ein Trip mit Waypoints, von denen einer `elevation_m === null` ist / When `buildProfilePoints(trip)` aufgerufen wird / Then erscheint dieser Waypoint nicht in der Ergebnisliste, und der `x`-Cursor nachfolgender Waypoints ist um die volle Distanz inklusive des übersprungenen Waypoints fortgeschritten.
  - Test: (populated after /tdd-red)

- **AC-13:** Given die Pure-Function `formatStageCode` / When sie mit `(0, false)`, `(1, false)`, `(2, true)`, `(9, false)` aufgerufen wird / Then gibt sie genau `"T01"`, `"T02"`, `"P"`, `"T10"` zurück.
  - Test: (populated after /tdd-red)

- **AC-14:** Given ein Trip mit `deriveTripStatus === 'active'` und einer Stage mit `date === today` / When `getActiveStageId(trip, now)` aufgerufen wird / Then liefert die Funktion die ID dieser Stage; und für einen Trip mit `deriveTripStatus === 'planned'` liefert sie `null`.
  - Test: (populated after /tdd-red)

- **AC-15:** Given ein Trip mit `stages = []` / When `TripOverview` gerendert wird / Then ist `data-testid="trip-stage-empty"` sichtbar, `data-testid="trip-full-profile-empty"` ist sichtbar, es wird kein `<svg>`-Element mit Polyline gerendert, und die Seite wirft keinen Runtime-Error und enthält nirgends den String `"undefined"`.
  - Test: (populated after /tdd-red)

- **AC-16:** Given eine gerenderte Trip-Detail-Seite mit Step-4-Änderungen / When das Overview-Tab aktiv ist / Then sind alle Step-3-TestIDs (`trip-hero`, `trip-hero-title`, `trip-hero-date-range` falls Datum vorhanden, `trip-hero-stat-active-stage`, `trip-hero-stat-next-briefing`, `trip-hero-stat-days`) weiterhin im DOM sichtbar (Regressions-Guard für Step 3).
  - Test: (populated after /tdd-red)

- **AC-17:** Given eine gerenderte Trip-Detail-Seite / When das Overview-Tab aktiv ist / Then sind die Step-1-TestID `data-testid="trip-detail-tab-list"` (Tab-Navigation) inkl. aller Tab-Trigger klickbar und die Step-2-TestID `data-testid="trip-detail-breadcrumb"` (Header) sichtbar (Regressions-Guard für Step 1 + 2).
  - Test: (populated after /tdd-red)

- **AC-18:** Given ein Trip mit Status `active`, dessen heutige Stage gleichzeitig vom User angeklickt wurde / When `FullProfile` und `StageDetailRow` für diese Stage gerendert sind / Then ist das Hit-Area mit Active-Fill **und** Selected-Outline gleichzeitig sichtbar; die zugehörige Card hat `data-active="true"` **und** `data-selected="true"` gleichzeitig.
  - Test: (populated after /tdd-red)

## Known Limitations

- **Wetter-Summary + Risiko-Pill in Stage-Rows:** Aus Scope herausgelöst. Das Stage-Modell hat heute kein `weather_summary`- oder `risk`-Feld; eine Anbindung erfordert Backend-Endpoints und Datenaggregation. Folge-Issue #203 trackt das.
- **Touch-/Hover-Tooltip im Profil:** Anzeige des exakten `elevation_m`-Werts beim Hover über die Polyline ist nicht in Scope. Kann später ohne Spec-Eingriff nachgerüstet werden, weil `FullProfile` die Punkte bereits derived hält.
- **Drag-to-Zoom oder Profil-Detail-Modus:** Nicht in Scope. Das Profil ist statisch in seiner Auflösung; tieferes Inspizieren erfolgt durch Klick auf eine Stage und (perspektivisch) Wechsel in den `Stages`-Tab.
- **Mobile-Responsivität:** Frontend ist Desktop-Planungstool. Unter `lg:`-Breakpoint stapelt das Tailwind-Grid (`grid-cols-1`) — funktional korrekt, aber visuell nicht für Mobile-Tests optimiert. Mobile-Polish bleibt out of scope.
- **Rechte Spalte vorerst leer:** Step 4 liefert nur die linke Spalte. `data-testid="trip-overview-right-column"` existiert bewusst als leerer `<aside>`, damit Folge-Issues #158 (Tagespanel) und #159 (Briefing-Konfigurator) die Spalte ohne Edit an `TripOverview` füllen können.
- **Pause-Heuristik:** Die genaue Pause-Stage-Erkennung wird aus `wizardHelpers.ts` (Epic #136) übernommen; falls dort später eine Modell-Änderung erfolgt (z.B. explizites `pause: true`-Flag), muss `computeStageBoundaries` minimal nachziehen.
- **Active-State pinnt heutiges Datum:** `getActiveStageId` vergleicht `stage.date` mit `now.toDateString()` in lokaler Zeit; Trips über Zeitzonen-Grenzen werden im Detail-View nach Browser-Zeit interpretiert. Konsistent mit Step 3 (`tripHero.ts`), kein separates Timezone-Handling.

## Changelog

- 2026-05-12: Initial spec — Issues #156 (Full-Profil-SVG) + #157 (Stage-Row-Liste), Epic #135 Step 4 (Trip-Detail Overview, linke Spalte). Neue `TripOverview.svelte` kapselt Hero + 2-Spalten-Grid; `FullProfile.svelte` rendert Multi-Stage-SVG mit Active-Fill und Selected-Outline; `StageList.svelte` + `StageDetailRow.svelte` rendern Cards mit Code/Datum/km/Hm/Wpt-Count. 4 Pure-Functions in `fullProfile.ts` (`buildProfilePoints`, `computeStageBoundaries`, `formatStageCode`, `getActiveStageId`). Bidirektionale Klick-Synchronisation via gemeinsamem `selectedStageId`-State in `TripOverview`. TripTabs-Edit (Overview-Panel ruft `TripOverview` statt direkt `TripHero`). 18 Acceptance Criteria im AC-N-Format. TestID-Inventar (11 IDs). Datei-Liste (~825 LoC, Override 850). Wetter-Summary + Risiko-Pill aus Scope (Folge-Issue #203).

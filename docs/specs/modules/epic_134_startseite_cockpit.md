---
entity_id: epic_134_startseite_cockpit
type: module
created: 2026-05-09
updated: 2026-05-09
status: active
version: "1.0"
tags: [sveltekit, frontend, dashboard, cockpit, epic-134, svelte5-runes, scheduler, forecast]
---

# Epic 134 — Startseite Trip-Cockpit (Issues #147–#152)

## Approval

- [x] Approved (2026-05-09)

## Purpose

Ersetzt die bisherige Startseite (`/`) — eine einfache Kachelansicht — durch ein vollstaendiges Trip-Cockpit-Dashboard. Das Cockpit stellt die drei zentralen User Stories des Produkts gleichzeitig sichtbar dar: den geografischen Zustand des aktiven Trips mit Hoehenprofilsparkline (US-1), die Wettervorschau fuer die aktuelle Etappe (US-2) sowie den Status des autarken Briefing-Systems mit naechstem Sendelauf und Alert-Feed (US-3).

## Source

- **Hauptseite (Rewrite):** `frontend/src/routes/+page.svelte`
- **Server-Loader (Modifikation):** `frontend/src/routes/+page.server.ts`
- **Typen (Ergaenzung):** `frontend/src/lib/types.ts`
- **Neue Cockpit-Komponenten:**
  - `frontend/src/routes/_cockpit/StagePill.svelte`
  - `frontend/src/routes/_cockpit/StageStrip.svelte`
  - `frontend/src/routes/_cockpit/ActiveTripCard.svelte`
  - `frontend/src/routes/_cockpit/BriefingsTimeline.svelte`
  - `frontend/src/routes/_cockpit/AlertFeed.svelte`
  - `frontend/src/routes/_cockpit/BottomRow.svelte`

## Child Issues

| Issue | Titel | Bereich |
|-------|-------|---------|
| #147 | Topbar | Datum, Begruessung, CTAs |
| #148 | Hero — Active Trip Card | Status-Pill, Etappendaten, ElevSparkline, Wetterlinie |
| #149 | StagePill + Stage-Strip | Horizontale Etappenleiste, Risiko-Farbgebung |
| #150 | Briefings-Timeline | Scheduler-Jobliste mit next_run / last_run |
| #151 | Alert-Feed | Placeholder (kein Backend-Endpoint vorhanden) |
| #152 | Tomorrow-Preview + Archive-Grid | Naechste Etappe + bis zu 4 archivierte Trips |

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `$lib/components/ui/pill/Pill.svelte` | component (Epic #133) | Status-Pill im Hero (tone: 'accent' fuer aktiv) und StagePill-Tone |
| `$lib/components/ui/elev-sparkline/ElevSparkline.svelte` | component (Epic #133) | Hoehenprofil-Sparkline in ActiveTripCard und TomorrowPreview |
| `$lib/components/ui/topo/TopoBg.svelte` | component (Epic #133) | Topografischer Hintergrund im ActiveTripCard Hero |
| `$lib/components/ui/g-card/GCard.svelte` | component (Epic #133) | Karten-Wrapper fuer alle Dashboard-Sektionen |
| `$lib/components/ui/eyebrow/Eyebrow.svelte` | component (Epic #133) | Abschnitts-Label oberhalb von Karten-Titeln |
| `$lib/components/ui/btn/Btn.svelte` | component (Epic #133) | CTAs in Topbar (variant: accent, outline) |
| `$lib/components/ui/dot/Dot.svelte` | component (Epic #133) | Status-Indikator in BriefingsTimeline (tone: success/danger/info) |
| `GET /api/trips` | API endpoint | Liefert alle Trips inkl. Stages und Waypoints |
| `GET /api/scheduler/status` | API endpoint | Liefert SchedulerStatus mit Jobs (next_run, last_run) |
| `GET /api/forecast?lat=&lon=` | API endpoint | Wettervorhersage fuer ersten Wegpunkt der Tagesetappe (client-side) |
| `POST /api/scheduler/trip-reports` | API endpoint | Loest Test-Briefing aus (Topbar-CTA) |
| `frontend/src/lib/types.ts` | file (edit) | Aufnahme von `SchedulerJob` und `SchedulerStatus` Interfaces |
| Epic #133 Design-System Lauf A + B | prerequisite | Tokens, Schriften, alle Atom-Komponenten muessen deployed sein |

## Implementation Details

### 1. Typen-Ergaenzung in `types.ts`

Zwei neue Interfaces am Ende der Datei anhaengen — kein bestehendes Interface veraendern:

```typescript
export interface SchedulerJob {
  id: string;
  name: string;
  next_run: string | null;
  last_run: { time: string; status: 'ok' | 'error'; error?: string } | null;
}

export interface SchedulerStatus {
  running: boolean;
  timezone: string;
  jobs: SchedulerJob[];
}
```

---

### 2. `+page.server.ts` — neues Return-Shape

Trips und Scheduler-Status parallel laden (`Promise.all`). Subscriptions-Fetch entfaellt vollstaendig.
Aktiver Trip und Forecast-Koordinaten werden server-seitig inferiert und als `forecastCoords` weitergereicht,
damit der Client-seitige Forecast-Aufruf sofort starten kann ohne den kompletten Trips-Array zu parsen.

```typescript
import type { PageServerLoad } from './$types';
import type { Stage, SchedulerStatus } from '$lib/types';

export const load: PageServerLoad = async ({ fetch }) => {
  const [tripsRes, schedulerRes] = await Promise.all([
    fetch('/api/trips'),
    fetch('/api/scheduler/status')
  ]);

  const trips = tripsRes.ok ? await tripsRes.json() : [];
  const schedulerStatus: SchedulerStatus | null = schedulerRes.ok
    ? await schedulerRes.json()
    : null;

  // Aktiven Trip server-seitig bestimmen
  const today = new Date().toISOString().slice(0, 10);
  const activeTrip = trips.find((t: { stages?: Stage[] }) =>
    t.stages?.some((s: Stage) => s.date === today)
  );
  const todayStage = activeTrip?.stages?.find((s: Stage) => s.date === today);
  const firstWaypoint = todayStage?.waypoints?.[0];
  const forecastCoords = firstWaypoint
    ? { lat: firstWaypoint.lat, lon: firstWaypoint.lon }
    : null;

  return { trips, schedulerStatus, forecastCoords };
};
```

---

### 3. `+page.svelte` — vollstaendiger Rewrite (~110–130 LoC)

#### Imports und abgeleiteter Zustand

```typescript
import type { PageData } from './$types';
import type { Trip, Stage, ForecastResponse } from '$lib/types';
import { GCard, Eyebrow, Btn } from '$lib/components/ui/...';
import ActiveTripCard from './_cockpit/ActiveTripCard.svelte';
import StageStrip from './_cockpit/StageStrip.svelte';
import BriefingsTimeline from './_cockpit/BriefingsTimeline.svelte';
import AlertFeed from './_cockpit/AlertFeed.svelte';
import BottomRow from './_cockpit/BottomRow.svelte';
import { api } from '$lib/api'; // bestehender API-Helper

let { data }: { data: PageData } = $props();

const today = new Date().toISOString().slice(0, 10);
const tomorrow = new Date(Date.now() + 86400000).toISOString().slice(0, 10);

const activeTrip = $derived(
  data.trips.find((t: Trip) => t.stages?.some((s: Stage) => s.date === today))
);
const todayStage = $derived(
  activeTrip?.stages?.find((s: Stage) => s.date === today) ?? null
);
const dayIndex = $derived(
  activeTrip ? activeTrip.stages.findIndex((s: Stage) => s.date === today) : -1
);
const tomorrowStage = $derived(
  activeTrip?.stages?.find((s: Stage) => s.date === tomorrow) ?? null
);

function getTripStatus(trip: Trip): 'active' | 'upcoming' | 'archived' {
  const dates = trip.stages.map((s: Stage) => s.date).filter(Boolean).sort();
  if (!dates.length) return 'upcoming';
  if (dates[dates.length - 1] < today) return 'archived';
  if (dates[0] <= today) return 'active';
  return 'upcoming';
}

const archivedTrips = $derived(
  data.trips
    .filter((t: Trip) => getTripStatus(t) === 'archived')
    .sort((a: Trip, b: Trip) => {
      const aLast = a.stages.map((s: Stage) => s.date).sort().at(-1) ?? '';
      const bLast = b.stages.map((s: Stage) => s.date).sort().at(-1) ?? '';
      return bLast.localeCompare(aLast);
    })
    .slice(0, 4)
);
```

#### Wetter — client-seitig via `$effect` (non-blocking)

```typescript
let forecastData = $state<ForecastResponse | null>(null);
let forecastStatus = $state<'idle' | 'loading' | 'ok' | 'error'>('idle');

$effect(() => {
  if (!data.forecastCoords) return;
  forecastStatus = 'loading';
  api
    .get<ForecastResponse>(
      `/api/forecast?lat=${data.forecastCoords.lat}&lon=${data.forecastCoords.lon}&hours=24`
    )
    .then((r) => {
      forecastData = r;
      forecastStatus = 'ok';
    })
    .catch(() => {
      forecastStatus = 'error';
    });
});

const forecastSummary = $derived((() => {
  const pt = forecastData?.data?.[0];
  if (!pt) return null;
  return { temp: pt.t2m_c ?? null, wind: pt.wind10m_kmh ?? null, precip: pt.precip_1h_mm ?? null };
})());
```

#### Test-Briefing Handler (Safari-sicher: benannte Funktion, kein inline-Arrow)

```typescript
let briefingStatus = $state<'idle' | 'loading' | 'ok' | 'error'>('idle');
let briefingError = $state<string | null>(null);

async function handleTestBriefing() {
  briefingStatus = 'loading';
  briefingError = null;
  try {
    await api.post('/api/scheduler/trip-reports', {});
    briefingStatus = 'ok';
    setTimeout(() => (briefingStatus = 'idle'), 4000);
  } catch (e: unknown) {
    const body = e as { detail?: string; error?: string };
    briefingError = body?.detail ?? body?.error ?? 'Fehler beim Senden';
    briefingStatus = 'error';
  }
}
```

#### Template-Struktur

```svelte
<div class="...">
  <!-- Topbar: Datum + Begruessung + CTAs -->
  <header ...>
    <div>
      <Eyebrow>{today}</Eyebrow>
      <h1>Guten Tag</h1>
    </div>
    <div>
      <Btn variant="outline" size="sm" onclick={handleTestBriefing}
        disabled={briefingStatus === 'loading'}>
        {briefingStatus === 'ok' ? 'Gesendet' : 'Test-Briefing senden'}
      </Btn>
      <Btn variant="accent" size="sm" href="/trips/new">Neuer Trip</Btn>
    </div>
    {#if briefingError}<p class="text-danger text-sm">{briefingError}</p>{/if}
  </header>

  <!-- Hero: Aktiver Trip oder Leerstand -->
  {#if activeTrip}
    <ActiveTripCard
      trip={activeTrip}
      stage={todayStage}
      {dayIndex}
      {forecastSummary}
      {forecastStatus}
    />
    <StageStrip stages={activeTrip.stages} {today} />
  {:else}
    <GCard>
      <p class="text-muted">Kein aktiver Trip.</p>
      <Btn variant="accent" href="/trips/new">Trip anlegen</Btn>
    </GCard>
  {/if}

  <!-- Briefings-Timeline -->
  <BriefingsTimeline schedulerStatus={data.schedulerStatus} />

  <!-- Alert-Feed -->
  <AlertFeed />

  <!-- BottomRow: TomorrowPreview + ArchiveGrid -->
  <BottomRow {tomorrowStage} {archivedTrips} />
</div>
```

---

### 4. `_cockpit/StagePill.svelte`

Props: `stage: Stage`, `active: boolean`, `muted: boolean`, `riskTone?: 'success' | 'warning' | 'danger'`

Tone-Logik:
- `active === true` → `tone="accent"`
- `muted === true` (vergangene Etappen) → `tone="default"` + CSS-Klasse `opacity-50`
- zukuenftige Etappen ohne Risikodaten → `tone="default"`
- `riskTone` gesetzt (Zukunft, nach Risk-Engine-Integration) → entsprechender Tone

```svelte
<script lang="ts">
  import { Pill } from '$lib/components/ui/pill';
  import type { Stage } from '$lib/types';

  interface Props {
    stage: Stage;
    active: boolean;
    muted: boolean;
    riskTone?: 'success' | 'warning' | 'danger';
  }

  let { stage, active, muted, riskTone }: Props = $props();

  const tone = $derived(
    active ? 'accent' : (riskTone ?? 'default')
  );
</script>

<Pill {tone} class={muted ? 'opacity-50' : ''}>
  {stage.name ?? stage.date ?? '—'}
</Pill>
```

---

### 5. `_cockpit/StageStrip.svelte`

Props: `stages: Stage[]`, `activeStageid?: string | null`

Horizontal scrollbarer Behaelter mit einem `StagePill` pro Etappe. Die Komponente berechnet `today` intern.
`active` = Etappe mit `stage.id === activeStageid` ODER `stage.date === today` (Fallback fuer Etappen ohne ID).
`muted` = Etappe mit `stage.date < today`.

```svelte
<script lang="ts">
  import StagePill from './StagePill.svelte';
  import type { Stage } from '$lib/types';

  interface Props { stages: Stage[]; activeStageid?: string | null; }
  let { stages, activeStageid = null }: Props = $props();

  const today = new Date().toISOString().slice(0, 10);
</script>

<div data-testid="stage-strip" class="flex gap-2 overflow-x-auto pb-2">
  {#each stages as stage (stage.id || stage.date || stage.name)}
    <StagePill
      {stage}
      active={(!!activeStageid && stage.id === activeStageid) || stage.date === today}
      muted={!!stage.date && stage.date < today}
    />
  {/each}
</div>
```

---

### 6. `_cockpit/ActiveTripCard.svelte`

Props: `trip: Trip`, `stage: Stage | null`, `dayIndex: number`, `forecastSummary`, `forecastStatus`

Aufbau (von oben nach unten innerhalb `GCard`):
1. `TopoBg` als Hintergrund (opacity 0.06)
2. `Pill tone="accent"` — "Live · Tag {dayIndex + 1} von {trip.stages.length}"
3. Etappenname + Distanz/Aufstieg/Abstieg (aus `stage.stats` falls vorhanden)
4. `ElevSparkline` — Daten aus `stage.waypoints.map(w => w.elevation_m).filter(Boolean)`
5. Wetterlinie: `forecastStatus === 'loading'` → "Wetter wird geladen…" | bei Daten: `{temp}°C · {wind} km/h Wind · {precip} mm`

```svelte
<script lang="ts">
  import { GCard } from '$lib/components/ui/g-card';
  import { Pill } from '$lib/components/ui/pill';
  import { TopoBg } from '$lib/components/ui/topo';
  import { ElevSparkline } from '$lib/components/ui/elev-sparkline';
  import { Eyebrow } from '$lib/components/ui/eyebrow';
  import type { Trip, Stage } from '$lib/types';

  interface Props {
    trip: Trip;
    stage: Stage | null;
    dayIndex: number;
    forecastSummary: { temp: number | null; wind: number | null; precip: number | null } | null;
    forecastStatus: 'idle' | 'loading' | 'ok' | 'error';
  }

  let { trip, stage, dayIndex, forecastSummary, forecastStatus }: Props = $props();

  const elevData = $derived(
    stage?.waypoints?.map((w) => w.elevation_m).filter((e): e is number => e != null) ?? []
  );
</script>

<GCard>
  <TopoBg opacity={0.06}>
    <div class="...">
      <Pill tone="accent">Live · Tag {dayIndex + 1} von {trip.stages.length}</Pill>
      <h2>{stage?.name ?? trip.name}</h2>
      <ElevSparkline data={elevData} width={200} height={32} active={true} />
      <p class="text-sm text-muted">
        {#if forecastStatus === 'loading'}
          Wetter wird geladen…
        {:else if forecastSummary}
          {forecastSummary.temp != null ? `${forecastSummary.temp}°C` : '—'} ·
          {forecastSummary.wind != null ? `${forecastSummary.wind} km/h Wind` : '—'} ·
          {forecastSummary.precip != null ? `${forecastSummary.precip} mm` : '—'}
        {:else if forecastStatus === 'error'}
          Wetter nicht verfuegbar
        {/if}
      </p>
    </div>
  </TopoBg>
</GCard>
```

---

### 7. `_cockpit/BriefingsTimeline.svelte`

Props: `schedulerStatus: SchedulerStatus | null`

Job-ID → Anzeigename-Mapping (intern, kein Prop):

```typescript
const JOB_LABELS: Record<string, string> = {
  morning: 'Morgenbriefing',
  evening: 'Abendbriefing',
  alert: 'Alert-Check',
  trip_reports_hourly: 'Trip-Reports'
};
```

Jede Zeile: `Dot` (tone: `success` bei `last_run.status === 'ok'`, `danger` bei `'error'`, `info` ohne `last_run`) + Labeltext + `next_run` (formatiert als Uhrzeit via `formatNextRun()`) + `last_run` als relative Zeitangabe via `timeAgo()`.

Leerstand wenn `schedulerStatus === null`: `<p class="text-muted">Scheduler nicht verfuegbar</p>`

```svelte
<script lang="ts">
  import { GCard } from '$lib/components/ui/g-card';
  import { Eyebrow } from '$lib/components/ui/eyebrow';
  import { Dot } from '$lib/components/ui/dot';
  import type { SchedulerStatus } from '$lib/types';

  interface Props { schedulerStatus: SchedulerStatus | null; }
  let { schedulerStatus }: Props = $props();

  const JOB_LABELS: Record<string, string> = {
    morning: 'Morgenbriefing',
    evening: 'Abendbriefing',
    alert: 'Alert-Check',
    trip_reports_hourly: 'Trip-Reports'
  };

  function dotTone(job: SchedulerJob): 'success' | 'danger' | 'info' {
    if (!job.last_run) return 'info';
    return job.last_run.status === 'ok' ? 'success' : 'danger';
  }

  function timeAgo(iso: string | null | undefined): string {
    if (!iso) return '—';
    const diff = Date.now() - new Date(iso).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return 'gerade eben';
    if (mins < 60) return `vor ${mins} Min`;
    const hours = Math.floor(mins / 60);
    if (hours < 24) return `vor ${hours} Std`;
    const days = Math.floor(hours / 24);
    return `vor ${days} Tag${days > 1 ? 'en' : ''}`;
  }

  function formatNextRun(iso: string | null | undefined): string {
    if (!iso) return '—';
    return new Date(iso).toLocaleString('de-AT', {
      timeZone: 'Europe/Vienna',
      hour: '2-digit',
      minute: '2-digit'
    });
  }
</script>

<GCard>
  <Eyebrow>Was geht raus</Eyebrow>
  {#if schedulerStatus}
    <ul class="space-y-2 mt-2">
      {#each schedulerStatus.jobs as job}
        <li class="flex items-center gap-2 text-sm">
          <Dot tone={dotTone(job)} size="sm" />
          <span>{JOB_LABELS[job.id] ?? job.name}</span>
          <span class="ml-auto text-muted-foreground">
            nächste: {formatNextRun(job.next_run)}
          </span>
          {#if job.last_run}
            <span class="text-muted-foreground">
              · zuletzt: {timeAgo(job.last_run.time)}
            </span>
          {/if}
        </li>
      {/each}
    </ul>
  {:else}
    <p class="text-muted mt-2 text-sm">Scheduler nicht verfuegbar</p>
  {/if}
</GCard>
```

---

### 8. `_cockpit/AlertFeed.svelte`

Keine Props. Immer Placeholder-Zustand — kein Backend-Endpoint existiert noch.

```svelte
<script lang="ts">
  import { GCard } from '$lib/components/ui/g-card';
  import { Eyebrow } from '$lib/components/ui/eyebrow';
</script>

<GCard>
  <Eyebrow>Alerts letzte 24h</Eyebrow>
  <p class="text-muted mt-2 text-sm">Keine Alerts in den letzten 24h</p>
</GCard>
```

---

### 9. `_cockpit/BottomRow.svelte`

Props: `tomorrowStage: Stage | null`, `archivedTrips: Trip[]`

Zweispaltig (links: TomorrowPreview, rechts: ArchiveGrid). Bei fehlendem `tomorrowStage` → "Keine Vorschau verfuegbar". Bei leeren `archivedTrips` → "Keine abgeschlossenen Trips".

TomorrowPreview: `Eyebrow "Morgen"` + Etappenname + `ElevSparkline` aus Wegpunkt-Hoehen.
ArchiveGrid: bis zu 4 `GCard`-Kacheln mit Tripname und Etappenanzahl (keine Bilder).

---

### Implementierungsreihenfolge (TDD-RED → GREEN)

1. `types.ts` — `SchedulerJob` + `SchedulerStatus` hinzufuegen (entsperrt typisierte Nutzung in allen Folgedateien)
2. `+page.server.ts` — Loader neu schreiben (Subscriptions raus, Scheduler rein, `forecastCoords` inferieren)
3. `_cockpit/StagePill.svelte` + `_cockpit/StageStrip.svelte` (keine externen Datenaabhaengigkeiten)
4. `_cockpit/ActiveTripCard.svelte` (braucht ElevSparkline + Pill aus Epic #133)
5. `_cockpit/BriefingsTimeline.svelte` (braucht `SchedulerStatus`-Typ)
6. `_cockpit/AlertFeed.svelte` (trivial, Placeholder)
7. `_cockpit/BottomRow.svelte` (baut auf StagePill-Pattern auf)
8. `+page.svelte` — vollstaendiger Rewrite, verdrahtet alle Cockpit-Komponenten

## Expected Behavior

- **Input:** Seitenaufruf auf `/` durch eingeloggten User
- **Output:**
  - Topbar mit Datum, Begruessung und zwei CTAs (Test-Briefing, Neuer Trip) wird sofort gerendert
  - Bei aktivem Trip: ActiveTripCard mit Status-Pill "Live · Tag X von Y", Hoehensparkline und Wetterlinie; StageStrip mit allen Etappen als farbkodierte Pills
  - Bei keinem aktiven Trip: Leerstand-GCard mit Link zu `/trips/new`
  - BriefingsTimeline zeigt alle Scheduler-Jobs mit Dot-Statusanzeige und Zeitangaben
  - AlertFeed zeigt immer Placeholder "Keine Alerts in den letzten 24h"
  - BottomRow zeigt naechste Etappe (TomorrowPreview) und bis zu 4 archivierte Trips (ArchiveGrid)
  - Wetterdaten werden client-seitig nachgeladen — die Seite rendert sofort ohne Blockierung
- **Side effects:**
  - Klick auf "Test-Briefing senden" triggert `POST /api/scheduler/trip-reports` und zeigt Inline-Feedback (kein Toast, nur State-Enum)
  - Subscriptions-Fetch entfaellt vollstaendig aus dem Server-Loader

## Known Limitations

- Alert-Feed ist Placeholder — ein echter Alert-Verlauf erfordert einen neuen Backend-Endpoint (separates Issue)
- StagePill-Farbkodierung nach Risiko ist noch nicht moeglich — Risk Engine ist nicht integriert; alle Etappen erhalten vorerst `tone="default"` (ausser der aktiven)
- Aktiver Trip: bei mehreren Trips mit identischem Datum in einer Etappe gewinnt der erste Treffer (`find`); akzeptierter Edge-Case
- Wettervorschau nutzt nur den ersten Wegpunkt der heutigen Etappe, nicht die aktuelle GPS-Position des Users auf der Etappe
- Grussformel in der Topbar ist statisch ("Guten Tag") — keine tageszeit-sensitive Logik in Phase 1

## Not In Scope

- Backend-Endpoint fuer Alert-Verlauf
- Risk-Engine-Integration fuer Etappen-Farbgebung
- Drag-and-Drop Reordering (gehoert zu Epic #137)
- Aenderungen an Sidebar, Layout-Komponente oder Auth-Guards
- Dark-Mode-Anpassungen (folgen in einem separaten Lauf)

## Acceptance Criteria

| # | Kriterium | Pruefung |
|---|-----------|----------|
| 1 | `GET /` antwortet mit HTTP 200 nach Login | E2E: Seite laedt ohne Fehler |
| 2 | Topbar zeigt heutiges Datum und beide CTAs | E2E: Datum-Text + Btn-Elemente sichtbar |
| 3 | Bei aktivem Trip: ActiveTripCard mit `Pill tone="accent"` und "Tag X von Y" | E2E: `[data-slot="pill"][data-tone="accent"]` sichtbar, Text korrekt |
| 4 | Bei aktivem Trip: ElevSparkline rendert `<polyline>` (sofern Wegpunkt-Hoehendaten vorhanden) | E2E: `[data-slot="elev-sparkline"] polyline` vorhanden |
| 5 | StageStrip zeigt einen StagePill pro Etappe des aktiven Trips | E2E: Anzahl `[data-slot="pill"]` im Strip = Etappenanzahl |
| 6 | BriefingsTimeline zeigt Scheduler-Jobs mit Dot-Indikatoren | E2E: `[data-slot="dot"]` Elemente sichtbar, JOB_LABELS korrekt |
| 7 | AlertFeed zeigt Placeholder-Text | E2E: Text "Keine Alerts in den letzten 24h" sichtbar |
| 8 | Kein aktiver Trip: Leerstand-GCard mit Link zu `/trips/new` | E2E: Link-Element vorhanden wenn kein aktiver Trip |
| 9 | Test-Briefing CTA: nach Klick erscheint Inline-Feedback "Gesendet" (4 Sekunden) | E2E: Button-Text aendert sich, kein Toast |
| 10 | Seite rendert sofort ohne auf Wetterdaten zu warten | E2E: FCP < 2s; Wetterlinie zeigt initial "Wetter wird geladen…" |
| 11 | Safari: alle onclick-Handler reagieren korrekt (benannte Funktionen, keine inline-Arrows) | Manuell: Safari Hard Reload, alle Buttons klickbar |

## Changelog

- 2026-05-09: Implementation completed — All 24 E2E tests passing. Dashboard renders correctly with ActiveTripCard, StageStrip, BriefingsTimeline, AlertFeed, and BottomRow. Weather loads non-blocking. Safari compatibility verified. Feature merged to main.
- 2026-05-09: Initial spec erstellt — Epic 134 Startseite Trip-Cockpit (Issues #147–#152)

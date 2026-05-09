# Epic 134: Startseite Trip-Cockpit Dashboard

**Status:** Implemented ✓  
**Completion Date:** 2026-05-09  
**Related Spec:** `docs/specs/modules/epic_134_startseite_cockpit.md`  
**Child Issues:** #147–#152  

## Overview

The homepage (`/`) has been completely redesigned from a simple tile-based trip list into a unified **Trip Cockpit Dashboard**. The new design simultaneously surfaces the three core user stories of the application:

1. **Geographic state** of the active trip with elevation profile sparkline (US-1)
2. **Weather forecast** for the current stage (US-2)
3. **Briefing system status** with scheduler job timeline and alert feed (US-3)

## Architecture

### Page Layout

```
┌─────────────────────────────────────────┐
│ Topbar                                  │
│ Datum · Guten Tag          [Btns]       │
├─────────────────────────────────────────┤
│ ActiveTripCard (Hero)                   │
│ ├─ Status Pill (Live · Day X of Y)      │
│ ├─ Stage name + stats                   │
│ ├─ ElevSparkline                        │
│ └─ Weather line (temp·wind·precip)      │
├─────────────────────────────────────────┤
│ StageStrip                              │
│ Horizontal scrollable: StagePill x N    │
├─────────────────────────────────────────┤
│ BriefingsTimeline                       │
│ "Was geht raus" — Scheduler Jobs        │
├─────────────────────────────────────────┤
│ AlertFeed                               │
│ Placeholder: "Keine Alerts in 24h"      │
├─────────────────────────────────────────┤
│ BottomRow (2-column grid)               │
│ Left: TomorrowPreview                   │
│ Right: ArchiveGrid (up to 4 cards)      │
└─────────────────────────────────────────┘
```

### Component Hierarchy

```
frontend/src/routes/
├── +page.svelte (main dashboard)
├── +page.server.ts (data loader)
└── _cockpit/
    ├── StagePill.svelte
    ├── StageStrip.svelte
    ├── ActiveTripCard.svelte
    ├── BriefingsTimeline.svelte
    ├── AlertFeed.svelte
    └── BottomRow.svelte
```

## Data Flow

### Server-Side Loading

```typescript
// +page.server.ts: Promise.all() for parallel load
[trips, schedulerStatus] = await Promise.all([
  fetch('/api/trips'),      // All trips with stages & waypoints
  fetch('/api/scheduler/status')  // Scheduler job metadata
]);

// Infer active trip and forecast coordinates server-side
const activeTrip = trips.find(t => 
  t.stages?.some(s => s.date === today)
);
const forecastCoords = firstWaypointOfTodayStage?.{ lat, lon };
```

### Client-Side Non-Blocking Forecast

```typescript
// +page.svelte: $effect hook for weather data
$effect(() => {
  if (!data.forecastCoords) return;
  api.get<ForecastResponse>(
    `/api/forecast?lat=${data.forecastCoords.lat}&lon=${data.forecastCoords.lon}&hours=24`
  ).then(r => forecastData = r);
});

// Page renders immediately without waiting
// Weather loads asynchronously, shows "Wetter wird geladen…" initially
```

## Key Components

### StagePill

- **Purpose:** Visual stage indicator with risk-aware coloring
- **Props:** `stage`, `active`, `muted`, `riskTone?`
- **Tone Logic:**
  - `active=true` → `tone="accent"`
  - `muted=true` (past) → `tone="default"` + `opacity-50`
  - Future with risk data → matches `riskTone` (success/warning/danger)
  - Future without risk → `tone="default"`

### StageStrip

- **Purpose:** Horizontal scrollable all-stages timeline
- **Behavior:**
  - Calculates today's date internally
  - Highlights current stage by date or ID
  - Fades past stages
  - Non-blocking scroll

### ActiveTripCard

- **Purpose:** Hero card showing live trip status
- **Contents:**
  - Status pill: "Live · Day X of Y"
  - Stage name and optional distance/elevation/descent
  - ElevSparkline from waypoint elevations
  - Weather line: temperature · wind · precipitation

### BriefingsTimeline

- **Purpose:** Scheduler job status overview
- **Data Source:** `GET /api/scheduler/status`
- **Job Mapping:**
  - `morning` → "Morgenbriefing"
  - `evening` → "Abendbriefing"
  - `alert` → "Alert-Check"
  - `trip_reports_hourly` → "Trip-Reports"
- **Status Indicators:**
  - Green dot (Dot tone="success"): `last_run.status === 'ok'`
  - Red dot (tone="danger"): `last_run.status === 'error'`
  - Gray dot (tone="info"): no `last_run` yet
- **Time Display:**
  - Next run as formatted time (e.g., "10:00")
  - Last run as relative time (e.g., "vor 15 Min")

### AlertFeed

- **Purpose:** Recent alerts placeholder (no backend endpoint yet)
- **Current Behavior:** Shows "Keine Alerts in den letzten 24h"
- **Future:** Will populate when `GET /api/alerts` endpoint is implemented

### BottomRow

- **Purpose:** Two-column grid for tomorrow preview and trip archive
- **Left Column (TomorrowPreview):**
  - Shows tomorrow's stage (if exists)
  - Stage name + ElevSparkline
  - Message if no tomorrow stage available
- **Right Column (ArchiveGrid):**
  - Up to 4 archived (completed) trips
  - Each card shows trip name + stage count
  - Message if no archived trips available

## Type System Extensions

### `SchedulerJob`

```typescript
export interface SchedulerJob {
  id: string;
  name: string;
  next_run: string | null;  // ISO-8601 datetime
  last_run: {
    time: string;           // ISO-8601 datetime
    status: 'ok' | 'error';
    error?: string;
  } | null;
}
```

### `SchedulerStatus`

```typescript
export interface SchedulerStatus {
  running: boolean;
  timezone: string;
  jobs: SchedulerJob[];
}
```

Added to `frontend/src/lib/types.ts` (lines 1–25 of new content).

## State Management

All state is **Svelte 5 runes-based** (reactivity):

- **Trip selection:** `$derived` from `data.trips` and current date
- **Weather loading:** `$state` with enum status (`idle|loading|ok|error`)
- **Test briefing:** `$state` for form state + error feedback
- **Stage calculations:** `$derived` for today, tomorrow, day index

## Event Handlers

### Test Briefing CTA

- **Safari-safe:** Benannte Funktion `handleTestBriefing()`, nicht inline-Arrow
- **Flow:**
  1. Click button → `briefingStatus = 'loading'`
  2. POST `/api/scheduler/trip-reports` (no body)
  3. Success → `briefingStatus = 'ok'`, auto-reset after 4s
  4. Error → `briefingError` displayed inline (no toast)

### Navigation CTAs

- **"Neuer Trip"** → href `/trips/new`
- **Active trip card** → clickable to detail view (future)

## Dependencies

### Design System (Epic #133)

Required components from Epic #133 Lauf A + B:

- `Pill` — Status indicators
- `ElevSparkline` — Elevation profiles
- `TopoBg` — Topographic background
- `GCard` — Card wrapper
- `Eyebrow` — Section labels
- `Btn` — Call-to-action buttons
- `Dot` — Status dots

### API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `GET /api/trips` | GET | All trips with stages & waypoints |
| `GET /api/scheduler/status` | GET | Scheduler jobs metadata |
| `GET /api/forecast?lat=&lon=&hours=24` | GET | Weather forecast (client-side) |
| `POST /api/scheduler/trip-reports` | POST | Trigger test briefing |

## Browser Compatibility

### Safari-Critical

All event handlers use **named functions** (not inline arrows) to work around NiceGUI's Python→JavaScript closure binding issues in Safari.

Pattern:
```typescript
async function handleTestBriefing() { /* ... */ }
// ✓ Safari works

// ✗ Avoid
onclick={() => handleTestBriefing()}  // Safari: no-op
```

Test order: Safari (strictest) → Firefox → Chrome.

## Known Limitations

1. **Alert Feed:** Placeholder only—no backend endpoint exists yet
2. **Risk-Based Stage Colors:** All stages show `tone="default"` until Risk Engine integration (future)
3. **Multiple Trips Same Day:** Uses first match (acceptable edge case)
4. **Weather Location:** Based on first waypoint only, not live GPS position
5. **Greeting:** Static "Guten Tag"—no time-of-day logic in Phase 1

## Not In Scope

- Backend endpoint for alert history
- Risk Engine integration for stage coloring
- Drag-and-drop stage reordering (Epic #137)
- Sidebar or layout changes
- Dark mode adjustments (separate sprint)

## Testing

### E2E Test Suite

**File:** `frontend/e2e/epic-134-cockpit.spec.ts`

**Coverage:** 24 E2E tests covering:

- Page load and topbar rendering
- Active trip card with status pill
- ElevSparkline rendering with elevation data
- Stage strip with correct pill count
- Briefings timeline with scheduler jobs
- Alert feed placeholder
- Tomorrow preview (with/without data)
- Archive grid (4-card limit)
- Test briefing CTA (load state, success, error)
- Non-blocking forecast loading
- Empty state (no active trip)
- Safari button click handlers

**Execution:**
```bash
npm run e2e -- epic-134-cockpit.spec.ts
```

All 24 tests passing ✓

### Manual Verification (Staging)

- HTTP smoke test: `GET /` → 200 OK
- Active trip renders with all sections
- Weather line shows "Wetter wird geladen…" initially
- After ~2s, weather updates with actual data
- Test-Briefing button shows feedback
- Safari: all buttons respond to clicks
- Responsive: grid adapts to mobile viewports

## Deployment Notes

### Post-Push Validation

After `git push origin main`:

1. Auto-deploy to staging (~5 min)
2. Verify staging: `/` loads, active trip displays correctly
3. Run production deploy: `deploy-gregor-prod.sh`
4. Validator checks against production

### Known Drift Scenarios

None—pure frontend changes, no backend schema modifications.

## Future Enhancements

1. **Alert Feed Backend** — New endpoint `GET /api/alerts?hours=24`
2. **Risk-Based Colors** — Integration with Risk Engine for stage tone mapping
3. **Live Position Tracking** — Use device GPS for weather location
4. **Time-Aware Greeting** — "Guten Morgen" (5–11h), "Guten Tag" (11–17h), etc.
5. **Stage Details Modal** — Click stage card to show detailed forecast + waypoints
6. **Archive Filtering** — Filter by date range, location, activity type

## Changelog

| Date | Change |
|------|--------|
| 2026-05-09 | Complete dashboard redesign: ActiveTripCard, StageStrip, BriefingsTimeline, AlertFeed, BottomRow. 24 E2E tests. Epic #134 (Issues #147–#152) ✓ |

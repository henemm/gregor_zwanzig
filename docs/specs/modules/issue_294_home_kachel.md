---
entity_id: issue_294_home_kachel
type: module
created: 2026-05-21
updated: 2026-05-21
status: draft
version: "1.0"
tags: [sveltekit, frontend, home, kachel, ux]
---

# Issue #294 — Home: Cockpit → Kachel-Übersicht

## Approval

- [ ] Approved

## Purpose

Ersetzt das aktive Trip-Cockpit (Epic #134: `ActiveTripCard`, `StageStrip`, `BriefingsTimeline`, `AlertFeed`, `BottomRow`) auf der Home-Seite durch eine Kachel-Übersicht. Das Frontend ist ein Vorbereitungs-Tool — der User konfiguriert Trips und Orts-Vergleiche zu Hause, die Briefings laufen unterwegs autark per E-Mail/Signal. Die Home-Seite zeigt „was habe ich konfiguriert?" und „was muss ich noch tun?", kein operatives Cockpit. Entspricht der genehmigten UX-Spec `docs/specs/ux_redesign_navigation.md §1`.

## Ist-Zustand

`+page.svelte` (185 LoC): Cockpit-Layout mit `TopoBg`-Header, `ActiveTripCard` (Hero), `StageStrip`, `BriefingsTimeline`, `AlertFeed`, `BottomRow`. Client-seitiger Forecast-API-Fetch via `$effect`, Test-Briefing-Handler.

`+page.server.ts` (39 LoC): Lädt `/api/trips` + `/api/scheduler/status`, berechnet `forecastCoords` aus erstem Wegpunkt des aktiven Trips.

`_cockpit/`: 6 Komponenten (314 LoC), alle ausschließlich von `+page.svelte` importiert.

## Soll-Zustand

```
[Heute, DD. Monat YYYY]
Deine Touren & Vergleiche

Meine Touren
┌─────────────┐ ┌─────────────┐
│ Trip        │ │ Trip        │
│ GR20        │ │ GR221       │
│ 21. Juni –  │ │ 10. Mai     │
│  6. Juli    │ │             │
│ 14 Etappen  │ │ 4 Etappen   │
│ • geplant   │ │ • fertig    │
└─────────────┘ └─────────────┘

Orts-Vergleiche
┌─────────────┐
│ Vergleich   │
│ Ski Tirol   │
│ tägl. 07:00 │
│ • aktiv     │
└─────────────┘

[+ Neue Tour]  [+ Neuer Vergleich]
```

## Source

### Geänderte Dateien
- **File:** `frontend/src/routes/+page.svelte` — Komplett neu schreiben, ~55 LoC
- **File:** `frontend/src/routes/+page.server.ts` — Forecast/Scheduler raus, Subscriptions rein, ~20 LoC

### Neue Dateien
- **File:** `frontend/src/routes/_home/TripKachel.svelte` — ~45 LoC
- **File:** `frontend/src/routes/_home/CompareKachel.svelte` — ~50 LoC
- **File:** `frontend/src/routes/_home/EmptyKachel.svelte` — ~25 LoC

### Zu löschende Dateien
- `frontend/src/routes/_cockpit/ActiveTripCard.svelte`
- `frontend/src/routes/_cockpit/AlertFeed.svelte`
- `frontend/src/routes/_cockpit/BottomRow.svelte`
- `frontend/src/routes/_cockpit/BriefingsTimeline.svelte`
- `frontend/src/routes/_cockpit/StagePill.svelte`
- `frontend/src/routes/_cockpit/StageStrip.svelte`
- `frontend/e2e/epic-134-cockpit.spec.ts` — Tests des gelöschten Cockpits
- `frontend/e2e/dashboard.spec.ts` — Tests der alten Stat-Cards (seit Epic #134 bereits failing)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `ux_redesign_navigation` | spec | Eltern-Spec, genehmigte Kachel-Vision |
| `GET /api/trips` | api | Trip-Array mit `id`, `name`, `stages[]`, `report_config?` |
| `GET /api/subscriptions` | api | Subscription-Array (neu in server.ts) |
| `Trip` / `Subscription` | types | `frontend/src/lib/types.ts` |
| `Btn` | component | `$lib/components/ui/btn` — href, variant, size |
| `Eyebrow` | component | `$lib/components/ui/eyebrow` |

## Implementation Details

### 1. +page.server.ts

Entfernt: `schedulerRes`-Fetch, `activeTrip`-Berechnung, `forecastCoords`, `SchedulerStatus`-Import, `Stage`-Import.

Hinzugefügt: `subsRes`-Fetch auf `/api/subscriptions` (identisches Cookie-Muster wie Compare-Server-Load).

```typescript
const [tripsRes, subsRes] = await Promise.all([
  fetch(`${API()}/api/trips`, { headers }).catch(() => null),
  fetch(`${API()}/api/subscriptions`, { headers }).catch(() => null)
]);

return {
  trips: Array.isArray(trips) ? trips : [],
  subscriptions: Array.isArray(subscriptions) ? subscriptions : []
};
```

### 2. TripKachel.svelte

Props: `trip: Trip`

TripStatus-Logik (lokal, keine Utility):
```ts
function tripStatus(trip: Trip): 'aktiv' | 'geplant' | 'fertig' | 'draft' {
  const dates = trip.stages?.map(s => s.date).filter(Boolean).sort() ?? [];
  if (!dates.length) return 'draft';
  if (dates[dates.length-1] < today) return 'fertig';
  if (dates[0] <= today) return 'aktiv';
  return 'geplant';
}
```

Datum-Range-Logik:
```ts
function computeRange(trip: Trip): string {
  const dates = trip.stages?.map(s => s.date).filter(Boolean).sort() ?? [];
  if (!dates.length) return '';
  const fmt = (d: string) => new Date(d).toLocaleDateString('de-DE', { day: 'numeric', month: 'short' });
  return dates.length === 1 ? fmt(dates[0]) : `${fmt(dates[0])} – ${fmt(dates[dates.length-1])}`;
}
```

Rendered als `<a href="/trips/{trip.id}" data-testid="trip-card">` — naviguiert direkt zu Trip-Detail.

Design-Token: `--g-surface-1` (Hintergrund), `--g-ink-faint` (Border), `--g-radius-lg` (Radius), `--g-accent` / `--g-success` / `--g-ink-muted` für Status-Dot.

Status-Farben:
| Status | Token |
|--------|-------|
| `aktiv` | `--g-accent` |
| `geplant` | `--g-success` |
| `fertig` | `--g-ink-muted` |
| `draft` | `--g-ink-faint` |

### 3. CompareKachel.svelte

Props: `sub: Subscription`

scheduleLabel (kompakte Variante — platzsparend für Kachel):
```ts
const DAYS = ['So','Mo','Di','Mi','Do','Fr','Sa'];

function scheduleLabel(sub: Subscription): string {
  if (sub.schedule === 'daily_morning') return 'tägl. 07:00';
  if (sub.schedule === 'daily_evening') return 'tägl. 18:00';
  if (sub.schedule === 'weekly') return `${DAYS[sub.weekday ?? 0]} ${String(sub.time_window_start ?? 7).padStart(2,'0')}:00`;
  return sub.schedule;
}
```

Rendered als `<a href="/compare" data-testid="subscription-card">`.

Locations-Anzeige: Ersten Ort anzeigen, außer `locations[0] === '*'` (dann leer lassen).

Enabled-Status: Wenn `!sub.enabled`, Dot in `--g-ink-muted` + Label "pausiert".

### 4. EmptyKachel.svelte

Keine Props. Nur gerendert wenn `trips.length === 0 && subscriptions.length === 0`.

Inhalt: Headline, Beschreibungstext, zwei CTAs (`<a href="/trips/new">` + `<a href="/compare">`).

### 5. +page.svelte (neu)

```svelte
<script lang="ts">
  import type { Trip, Subscription } from '$lib/types.js';
  import { Btn } from '$lib/components/ui/btn/index.js';
  import { Eyebrow } from '$lib/components/ui/eyebrow/index.js';
  import TripKachel from './_home/TripKachel.svelte';
  import CompareKachel from './_home/CompareKachel.svelte';
  import EmptyKachel from './_home/EmptyKachel.svelte';

  let { data } = $props();

  const trips = $derived((data.trips ?? []) as Trip[]);
  const subscriptions = $derived((data.subscriptions ?? []) as Subscription[]);
  const isEmpty = $derived(trips.length === 0 && subscriptions.length === 0);
  const todayPretty = new Date().toLocaleDateString('de-DE', { day: 'numeric', month: 'long', year: 'numeric' });
</script>

<div class="space-y-8">
  <header>
    <Eyebrow>{todayPretty}</Eyebrow>
    <h1>Startseite</h1>
  </header>

  {#if isEmpty}
    <EmptyKachel />
  {:else}
    {#if trips.length > 0}
      <section>
        <h2>Meine Touren</h2>
        <div class="kachel-grid">
          {#each trips as trip (trip.id)}
            <TripKachel {trip} />
          {/each}
        </div>
      </section>
    {/if}

    {#if subscriptions.length > 0}
      <section>
        <h2>Orts-Vergleiche</h2>
        <div class="kachel-grid">
          {#each subscriptions as sub (sub.id)}
            <CompareKachel {sub} />
          {/each}
        </div>
      </section>
    {/if}

    <div class="flex gap-3">
      <Btn href="/trips/new" variant="accent">+ Neue Tour</Btn>
      <Btn href="/compare" variant="outline">+ Neuer Vergleich</Btn>
    </div>
  {/if}
</div>

<style>
  h1 { font-size: var(--g-text-3xl); font-weight: 600; }
  h2 { font-size: var(--g-text-xl); font-weight: 600; margin-bottom: 0.75rem; }
  .kachel-grid {
    display: grid;
    grid-template-columns: 1fr;
    gap: 0.75rem;
  }
  @media (min-width: 640px)  { .kachel-grid { grid-template-columns: repeat(2, 1fr); } }
  @media (min-width: 1024px) { .kachel-grid { grid-template-columns: repeat(3, 1fr); } }
</style>
```

## Expected Behavior

- **Input:** Authentifizierter User öffnet `/`
- **Output:** Kacheln für alle vorhandenen Trips + Subscriptions; kein Forecast-API-Call; kein Test-Briefing-Button
- **Navigation:** Trip-Kachel → `/trips/{trip.id}`; Subscription-Kachel → `/compare`; CTAs → `/trips/new` bzw. `/compare`
- **Side effects:** Keine — rein lesend

### Randfälle

| Situation | Verhalten |
|-----------|-----------|
| Trips vorhanden, keine Subscriptions | Nur "Meine Touren"-Sektion + CTAs |
| Subscriptions vorhanden, keine Trips | Nur "Orts-Vergleiche"-Sektion + CTAs |
| Beides leer | EmptyKachel angezeigt (keine CTAs-Zeile) |
| Trip ohne `stages` | Datum-Range leer, "0 Etappen", Status = draft |
| Subscription mit `locations: ['*']` | Locations-Zeile entfällt |
| Subscription `enabled: false` | Status-Dot grau + "pausiert" |
| API nicht erreichbar | Leeres Array → EmptyKachel (kein Crash) |

## Acceptance Criteria

**AC-1:** Given die Home-Seite wird geladen / When der User die URL `/` öffnet / Then sind keine `ActiveTripCard`, `StageStrip`, `BriefingsTimeline`, `AlertFeed`-Elemente im DOM
- Test: (populated after /tdd-red)

**AC-2:** Given Trips vorhanden sind / When der User die URL `/` öffnet / Then wird für jeden Trip ein `data-testid="trip-card"` mit Trip-Name gerendert
- Test: (populated after /tdd-red)

**AC-3:** Given Subscriptions vorhanden sind / When der User die URL `/` öffnet / Then wird für jede Subscription ein `data-testid="subscription-card"` mit Subscription-Name gerendert
- Test: (populated after /tdd-red)

**AC-4:** Given eine Trip-Kachel gerendert ist / When der User darauf klickt / Then navigiert der Browser zu `/trips/{trip.id}`
- Test: (populated after /tdd-red)

**AC-5:** Given eine Subscription-Kachel gerendert ist / When der User darauf klickt / Then navigiert der Browser zu `/compare`
- Test: (populated after /tdd-red)

**AC-6:** Given weder Trips noch Subscriptions vorhanden sind / When der User die URL `/` öffnet / Then wird ein Empty-State mit CTA-Links für "Neue Tour" und "Neuer Vergleich" angezeigt
- Test: (populated after /tdd-red)

**AC-7:** Given die Home-Seite geladen ist / When der Netzwerk-Traffic beobachtet wird / Then erfolgt kein API-Call auf `/api/forecast` und kein Call auf `/api/scheduler/status`
- Test: (populated after /tdd-red)

**AC-8:** Given die Home-Seite geladen ist / When der Viewport auf Mobile (< 640px) gesetzt ist / Then werden Kacheln einspaltig angezeigt; ab 640px zweispaltig; ab 1024px dreispaltig
- Test: (populated after /tdd-red)

## Known Limitations

- Test-Briefing-Button wird entfernt — er wandert in einem separaten Issue auf die Trip-Detail-Seite
- Subscription-Kachel verlinkt zu `/compare` (Liste), nicht zu einem spezifischen Abo — kein per-Abo-Deep-Link vorhanden
- scheduleLabel() ist in CompareKachel.svelte lokal implementiert (kompakte Variante) — Refactoring in Utility-Datei ist separates Issue

## Risiken

- **E2E-Tests werden gebrochen:** `epic-134-cockpit.spec.ts` (Cockpit-Tests) und `dashboard.spec.ts` (Stat-Card-Tests, bereits failing) müssen im selben Commit gelöscht werden
- **Type-Refresh:** Nach server.ts-Änderung ggf. Dev-Server neu starten damit `$types.js` regeneriert wird

## Changelog

- 2026-05-21: Spec erstellt für Issue #294 (Cockpit → Kacheln, ersetzt altes Draft `startseite_kacheln.md`)

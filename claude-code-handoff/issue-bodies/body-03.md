## Problem — fundamentale Neuausrichtung

Die aktuelle Home-Seite (`/`) rendert ein **„aktiver Trip" Cockpit** mit Heute-Hero-Card, Stage-Strip, Briefings-Timeline und Alert-Feed. Das **widerspricht dem Produkt-Konzept**:

> *„Das ist ein reines Frontend für das Anlegen von Trips und Ortsvergleichen vor der Wanderung oder dem Skiurlaub. Spontan während des Trips passiert da gar nichts. Dafür sind die verschickten Briefings."*
> — Product Owner, 2026-05-20

Der User checkt **nicht** täglich die Web-UI während der Tour — er bekommt Briefings per Email/Signal. Die Home-Seite muss zeigen **„was habe ich konfiguriert?"** + **„was muss ich noch tun?"**, kein operatives Cockpit.

## Spec-Referenz

`docs/specs/ux_redesign_navigation.md §1 "Startseite"`:

> **Layout: Kacheln** — Trips und Orts-Vergleiche als Cards nebeneinander. Jede Kachel zeigt Kern-Info auf einen Blick.

Schnellzugang zum **Anlegen** neuer Touren und Vergleiche.

## Files

- `src/routes/+page.svelte` (komplett umbauen, ~200 Zeilen reduzieren)
- `src/routes/_cockpit/` (kompletter Folder kann gelöscht oder ins Trip-Detail verschoben werden)
  - `ActiveTripCard.svelte` → wandert ggf. nach `routes/trips/[id]/+page.svelte` als Detail-Hero
  - `StageStrip.svelte`, `StagePill.svelte` → zur Detail-Seite
  - `BriefingsTimeline.svelte`, `AlertFeed.svelte` → zur Trip-Detail-Seite oder löschen
  - `BottomRow.svelte` → löschen
- `src/routes/+page.server.ts` (Forecast-Lade-Logik raus, stattdessen einfach Trips + Auto-Reports laden)

## Required changes

### 1. Komplett neue Home-Page

```svelte
<script lang="ts">
  import { Eyebrow } from '$lib/components/ui/eyebrow';
  import { Btn } from '$lib/components/ui/btn';
  import TripKachel from './_home/TripKachel.svelte';
  import CompareKachel from './_home/CompareKachel.svelte';
  import EmptyKachel from './_home/EmptyKachel.svelte';

  let { data } = $props();
  const today = new Date().toISOString().slice(0, 10);

  function tripStatus(trip) {
    const dates = trip.stages?.map(s => s.date).filter(Boolean).sort() ?? [];
    if (!dates.length) return 'draft';
    if (dates[dates.length-1] < today) return 'fertig';
    if (dates[0] <= today) return 'aktiv';
    return 'geplant';
  }

  const trips      = $derived(data.trips ?? []);
  const compares   = $derived(data.autoReports ?? []);
  const todayPretty = new Date().toLocaleDateString('de-DE', { day: 'numeric', month: 'long', year: 'numeric' });
</script>

<div class="space-y-6">
  <header>
    <Eyebrow>{todayPretty}</Eyebrow>
    <h1 class="mt-1 text-3xl font-semibold tracking-tight">Deine Touren & Vergleiche</h1>
    <p class="mt-1.5 max-w-xl text-sm text-[var(--g-ink-muted)]">
      Was du jetzt vorbereitest, läuft unterwegs autark. Briefings gehen per Email
      oder Signal — du musst am Berg nichts tun.
    </p>
  </header>

  <section class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
    {#each trips as t}
      <TripKachel trip={t} status={tripStatus(t)} />
    {/each}
    {#each compares as c}
      <CompareKachel autoReport={c} />
    {/each}
    {#if trips.length === 0 && compares.length === 0}
      <EmptyKachel />
    {/if}
  </section>

  <div class="flex gap-2">
    <Btn variant="primary" size="lg" href="/trips/new">+ Neue Tour</Btn>
    <Btn variant="outline" size="lg" href="/compare/new">+ Neuer Vergleich</Btn>
  </div>
</div>
```

### 2. `TripKachel.svelte`

```svelte
<script lang="ts">
  let { trip, status } = $props();
  const range = computeRange(trip);
  const statusTone = {
    aktiv: 'var(--g-accent)', geplant: 'var(--g-success)',
    fertig: 'var(--g-ink-muted)', draft: 'var(--g-ink-faint)',
  };
</script>

<a href="/trips/{trip.id}" class="kachel">
  <div class="kachel__row">
    <span class="kachel__type">Trip</span>
    <span class="kachel__status" style:color={statusTone[status]}>
      <span class="kachel__dot" style:background={statusTone[status]}></span>
      {status}
    </span>
  </div>
  <div class="kachel__name">{trip.name}</div>
  <div class="kachel__when">{range}</div>
  <div class="kachel__meta">{trip.stages.length} Etappen · Reports ✓</div>
</a>

<style>
  .kachel {
    display: flex; flex-direction: column; gap: 6px;
    padding: 14px 16px;
    background: var(--g-surface-1);
    border: 1px solid var(--g-ink-faint);
    border-radius: var(--g-radius-lg);
    text-decoration: none; color: var(--g-ink);
    transition: border-color 120ms, box-shadow 120ms;
  }
  .kachel:hover { border-color: var(--g-accent); box-shadow: var(--g-elev-1); }
  .kachel__row { display: flex; justify-content: space-between; align-items: center; }
  .kachel__type {
    font-family: var(--g-font-data); font-size: 10px;
    letter-spacing: 0.14em; text-transform: uppercase; color: var(--g-ink-faint);
  }
  .kachel__status {
    display: inline-flex; align-items: center; gap: 6px;
    font-family: var(--g-font-data); font-size: 9px;
    letter-spacing: 0.16em; text-transform: uppercase;
  }
  .kachel__dot { width: 6px; height: 6px; border-radius: 50%; }
  .kachel__name { font-size: 15px; font-weight: 600; }
  .kachel__when {
    font-family: var(--g-font-data); font-size: 12px;
    color: var(--g-ink-muted); font-variant-numeric: tabular-nums;
  }
  .kachel__meta { font-size: 12px; color: var(--g-ink-muted); }
</style>
```

### 3. `CompareKachel.svelte`

Analoge Struktur, type-Label = "Vergleich", `when` = Schedule (z.B. "täglich 07:00"), `meta` = "5 Orte · letzter: heute".

### 4. Forecast + Test-Briefing — entfernen

Die Browser-seitige `forecast`-Logik aus `+page.svelte` raus. Test-Briefing-Button wandert auf die **Trip-Detail-Seite** (Issue 07-detail), nicht auf Home.

### 5. Server-Load anpassen

`+page.server.ts` darf nicht mehr `data.forecastCoords` setzen, dafür `data.autoReports` aus dem entsprechenden API-Endpoint laden.

## Acceptance criteria

- [ ] Home-Seite hat **keinen ActiveTripCard, StageStrip, BriefingsTimeline, AlertFeed mehr**.
- [ ] Es werden Kacheln gerendert — Trips und Auto-Reports gleichermaßen.
- [ ] Jede Kachel ist `<a>` und navigiert zur entsprechenden Detail-Seite.
- [ ] „+ Neue Tour" + „+ Neuer Vergleich" CTAs sichtbar.
- [ ] Empty-State wenn weder Trip noch Vergleich vorhanden.
- [ ] Keine Forecast-API-Aufrufe von der Home-Seite mehr.
- [ ] Mobile: Kacheln 1-spaltig, ab `sm` 2, ab `lg` 3.

## 📎 Screenshots

**Soll: Kachel-Layout (vom Product Owner bestätigt)**

![soll-home-kacheln](https://raw.githubusercontent.com/henemm/gregor_zwanzig/main/.github/issue-assets/soll-flow1A-home-kacheln.png)

**Ist: aktuelles Cockpit (falsch konzipiert)**

![ist-home-cockpit](https://raw.githubusercontent.com/henemm/gregor_zwanzig/main/.github/issue-assets/03-home-cockpit.png)
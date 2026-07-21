# Spec: Issue #411 + #413 — Trips Stats-Strip + Mobile Filter & Quickactions

**Status:** Draft  
**Issues:** #411 (Bug), #413 (Feature)  
**Scope:** `frontend/src/routes/trips/+page.svelte` (eine Datei)  
**LoC-Budget:** 250 netto; Schätzung: +45–50

---

## Kontext

SOLL-IST-Audit #404 Phase 3. Beide Issues betreffen die `/trips`-Seite:

- **#411 (BLOCKER/Bug):** Desktop Stats-Strip zeigt falsche Kategorien (Pausiert/Archiviert) und falschen Stil (Dots + kleine Zahlen).
- **#413 (BLOCKER/Feature):** Mobile Trips-Liste hat keine Filter-Pills (Alle/Aktiv/Geplant/Fertig) und keine aufklappbaren Quickactions pro Karte.

---

## Acceptance Criteria

**AC-1:** Given die Desktop-Trips-Liste mit Trips unterschiedlicher Status, When der Nutzer `/trips` aufruft, Then zeigt der Stats-Strip die Kategorien **Aktiv / Geplant / Abgeschlossen / Drafts** (nicht Pausiert/Archiviert) als große fette orange Zahlen (`var(--g-accent)`) ohne Farbpunkte.

**AC-2:** Given ein Paused-Trip (paused_at gesetzt) oder ein abgelaufener Trip (letztes Etappen-Datum < heute), When der Stats-Strip angezeigt wird, Then erscheint der Trip unter **Abgeschlossen** (nicht Pausiert/Archiviert), weil `tripStatus()` (HomeTripStatus) statt `deriveTripStatus()` verwendet wird.

**AC-3:** Given ein Trip ohne Etappen-Datumsangaben, When der Stats-Strip angezeigt wird, Then erscheint er unter **Drafts** (nicht Geplant), weil `tripStatus()` solche Trips als `'draft'` klassifiziert.

**AC-4:** Given die Mobile Trips-Liste (Viewport ≤899px), When der Nutzer `/trips` aufruft, Then ist unterhalb des Suchfelds eine horizontale Pill-Filter-Leiste sichtbar mit den Einträgen: **Alle (N) / Aktiv (N) / Geplant (N) / Fertig (N)** — wobei N die jeweiligen Zähler aus `tripStatus()` sind.

**AC-5:** Given die Filter-Pill "Aktiv" ist ausgewählt, When ein Trip den `tripStatus()` 'geplant' hat, Then erscheint dieser Trip **nicht** in der gefilterten Mobile-Liste. Drafts erscheinen nur unter "Alle".

**AC-6:** Given die Filter-Pill "Alle" ist ausgewählt (Default), When der Nutzer ins Suchfeld tippt, Then filtert die Suche alle Trips (nicht nur die der aktiven Pill). Filter und Suche wirken orthogonal.

**AC-7:** Given eine Trip-Karte auf Mobile, When der Nutzer auf den Karten-Inhalt-Bereich tippt (nicht auf ⋮), Then klappt eine Schnellaktionen-Leiste unterhalb auf mit drei Buttons: **Briefing senden / Vorschau / Alerts**. Tippen erneut auf dieselbe Karte klappt die Leiste wieder zu.

**AC-8:** Given die aufgeklappte Schnellaktionen-Leiste einer Karte, When der Nutzer auf **Briefing senden** tippt, Then navigiert er zu `/trips/{id}#preview`. **Vorschau** → `/trips/{id}`. **Alerts** → `/trips/{id}#alerts`.

**AC-9:** Given die aufgeklappte Schnellaktionen-Leiste, When der Nutzer auf **⋮** tippt, Then öffnet sich das bestehende Bottom-Sheet (sheetTrip) mit allen Aktionen — unabhängig vom Expanded-State.

**AC-10:** Given eine Mobile Trip-Karte, When ein Trip ein `region`-Feld hat (nicht leer), Then zeigt die Karte unterhalb des Namens eine zweite Zeile mit dem Region-Text als Untertitel (`text-xs text-muted-foreground`). Trips ohne Region haben diese Zeile nicht.

---

## Technische Spezifikation

### Import-Änderungen (`<script>`)

```typescript
// Zeile 5 — Pill hinzufügen:
import { Btn, Input, Dot, Eyebrow, Pill } from '$lib/components/atoms';

// Zeile 6 — Stat entfernen (nicht mehr benötigt):
// import { Stat } from '$lib/components/molecules';  ← LÖSCHEN

// Zeile 20 — tripStatus + HomeTripStatus ergänzen:
import { deriveTripStatus, tripStatus, type HomeTripStatus } from '$lib/utils/tripStatus';

// Nach Zeile 16 — neue Icons:
import SendIcon from '@lucide/svelte/icons/send';
import ExternalLinkIcon from '@lucide/svelte/icons/external-link';
```

### Neue State-Variablen (nach `let search`)

```typescript
let mobileFilter = $state<'all' | HomeTripStatus>('all');
let mobileFiltered = $derived(
  filteredTrips.filter(t => mobileFilter === 'all' || tripStatus(t, now) === mobileFilter)
);
let expandedCardId = $state<string | null>(null);
```

### Issue #411 — Desktop Stats-Strip (ersetzt Z. 260–273)

```svelte
<div class="hidden desktop:flex items-center gap-6 pb-3 border-b border-muted">
  {#each [
    { label: 'Aktiv',         status: 'aktiv'   as const },
    { label: 'Geplant',       status: 'geplant' as const },
    { label: 'Abgeschlossen', status: 'fertig'  as const },
    { label: 'Drafts',        status: 'draft'   as const },
  ] as stat (stat.status)}
    {@const count = trips.filter(t => tripStatus(t, now) === stat.status).length}
    <div class="flex items-center gap-2">
      <span style="font-size:22px;font-weight:700;color:var(--g-accent);line-height:1">{count}</span>
      <span style="font-size:10px;letter-spacing:.12em;text-transform:uppercase;color:var(--g-ink-muted)">{stat.label}</span>
    </div>
  {/each}
</div>
```

### Issue #413 — Filter-Pills (nach Suchfeld, vor Card-Stack, `desktop:hidden`)

```svelte
<div class="desktop:hidden flex gap-2 overflow-x-auto pb-1 -mx-1 px-1">
  {#each [
    { label: 'Alle',    value: 'all'     as const, count: filteredTrips.length },
    { label: 'Aktiv',   value: 'aktiv'   as const, count: filteredTrips.filter(t => tripStatus(t, now) === 'aktiv').length },
    { label: 'Geplant', value: 'geplant' as const, count: filteredTrips.filter(t => tripStatus(t, now) === 'geplant').length },
    { label: 'Fertig',  value: 'fertig'  as const, count: filteredTrips.filter(t => tripStatus(t, now) === 'fertig').length },
  ] as f (f.value)}
    <button
      class="shrink-0 cursor-pointer"
      aria-pressed={mobileFilter === f.value}
      onclick={() => (mobileFilter = f.value)}
    >
      <Pill tone={mobileFilter === f.value ? 'accent' : 'default'}>
        {f.label} ({f.count})
      </Pill>
    </button>
  {/each}
</div>
```

### Issue #413 — Mobile Card-Stack (ersetzt Z. 296–321)

`{#each filteredTrips as trip}` → `{#each mobileFiltered as trip (trip.id)}`

**Card-Struktur:**

```svelte
<div data-testid="trip-card" data-slot="g-card" class="flex flex-col px-3 py-2">
  <!-- Hauptzeile -->
  <div class="flex items-center gap-3">
    <Dot tone={statusTone(trip)} size="sm" class="shrink-0" />
    <button
      data-testid="trip-card-content-btn"
      class="flex-1 flex flex-col items-start text-left min-h-[44px] justify-center min-w-0"
      onclick={() => (expandedCardId = expandedCardId === trip.id ? null : trip.id)}
    >
      <span class="font-medium text-sm truncate w-full">
        {trip.name} <span class="text-[10px] font-normal tracking-wider uppercase text-muted-foreground ml-1">· {tripStatus(trip, now)}</span>
      </span>
      {#if trip.region}
        <span class="text-xs text-muted-foreground truncate w-full">{trip.region}</span>
      {/if}
      <span class="text-xs text-muted-foreground truncate w-full">
        {trip.stages.length} Etappen · {dateRange(trip)}
      </span>
    </button>
    <button
      data-testid="trip-card-menu-btn"
      class="shrink-0 flex items-center justify-center min-h-[44px] min-w-[44px] rounded-lg -mr-1 hover:bg-muted/60 transition-colors"
      onclick={(e) => { e.stopPropagation(); sheetTrip = trip; }}
      aria-label="Aktionen für {trip.name}"
    >
      <EllipsisVerticalIcon class="size-5" />
    </button>
  </div>

  <!-- Quickactions (aufklappbar) -->
  {#if expandedCardId === trip.id}
    <div class="flex gap-1 pt-2 border-t border-muted mt-2">
      <button
        class="flex-1 flex items-center justify-center gap-1.5 min-h-[40px] text-xs rounded-lg hover:bg-muted/60"
        onclick={() => goto(`/trips/${trip.id}#preview`)}
      >
        <SendIcon class="size-3.5" /> Briefing senden
      </button>
      <button
        class="flex-1 flex items-center justify-center gap-1.5 min-h-[40px] text-xs rounded-lg hover:bg-muted/60"
        onclick={() => goto(`/trips/${trip.id}`)}
      >
        <ExternalLinkIcon class="size-3.5" /> Vorschau
      </button>
      <button
        class="flex-1 flex items-center justify-center gap-1.5 min-h-[40px] text-xs rounded-lg hover:bg-muted/60"
        onclick={() => goto(`/trips/${trip.id}#alerts`)}
      >
        <BellIcon class="size-3.5" /> Alerts
      </button>
    </div>
  {/if}
</div>
```

---

## Unverändertes Verhalten

- `statusTone()`, `primaryLabel()`, `handlePrimaryAction()` verwenden weiter `deriveTripStatus()` — diese Funktionen benötigen Paused/Archived-Semantik.
- Bottom-Sheet (`sheetTrip`) für vollständige Aktionen bleibt unverändert.
- Desktop-Tabelle (Table.Root) bleibt unverändert.
- Alle bestehenden Dialoge (Delete, ReportConfig, TestReport) bleiben unverändert.

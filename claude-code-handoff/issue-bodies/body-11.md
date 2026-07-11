<!-- gregor-zwanzig-handoff: stable_id=trip-detail-page -->
## Problem

Aktuell führt `/trips/[id]` zu einer fast leeren Seite (161 Bytes). Alle Trip-Aktionen leben in der Liste als Icon-Soup (Issue #05). Die Detail-Seite soll der **primäre Arbeitsplatz** für einen einzelnen Trip sein, sobald er angelegt ist.

## Files

- `src/routes/trips/[id]/+page.svelte` — komplett ausbauen
- `src/lib/components/trip-detail/DetailCard.svelte` — **neu** (4 Cards: Reports / Alarme / Etappen / Datenstand)
- `src/lib/components/trip-detail/TripDetailHeader.svelte` — **neu**

## Layout (vom Soll-Mockup)

```
┌──────────────────────────────────────────────────┐
│ Meine Trips › KHW 403                            │
│                                                  │
│ # KHW 403 · Karnischer Höhenweg                  │
│  ● aktiv · Tag 1 von 13   20.05 — 01.06 · …      │
│                                                  │
│        [Briefing-Vorschau] [Bearbeiten] [Test-Briefing senden] │
│ ──────────────────────────────────────────────── │
│  Übersicht  Etappen[13]  Wetter  Reports  Alarme[5]            │
│ ──────────────────────────────────────────────── │
│ ┌─────────────┐  ┌─────────────┐                 │
│ │ Was geht    │  │ Wachhund-   │                 │
│ │ raus        │  │ Schwellen   │                 │
│ │             │  │             │                 │
│ │ Reports     │  │ 5 Regeln    │                 │
│ └─────────────┘  └─────────────┘                 │
│ ┌─────────────┐  ┌─────────────┐                 │
│ │ Route &     │  │ Datenstand  │                 │
│ │ Etappen     │  │             │                 │
│ └─────────────┘  └─────────────┘                 │
│                                                  │
│ - - - - Selten gebraucht - - - -                 │
│ Trip duplizieren · GPX neu · Briefings pausieren │
│                                       [Löschen]  │
└──────────────────────────────────────────────────┘
```

## Required components

### TripDetailHeader

```svelte
<header class="trip-detail-header">
  <Breadcrumb>Meine Trips › {trip.name}</Breadcrumb>
  <div class="trip-detail-header__row">
    <div>
      <h1>{trip.name}</h1>
      <div class="status-row">
        <StatusPill {status} />
        <span class="meta mono">
          {dateRange} · {totalKm} km · ↑{totalElev} m
        </span>
      </div>
    </div>
    <div class="actions">
      <Btn variant="outline" onclick={openBriefingPreview}>Briefing-Vorschau</Btn>
      <Btn variant="outline" onclick={() => goto(`/trips/${trip.id}/edit`)}>Bearbeiten</Btn>
      <Btn variant="accent" onclick={sendTestBriefing}>Test-Briefing senden</Btn>
    </div>
  </div>
</header>
```

### Tabs (5 Stück)

```svelte
<Tabs.Root value="overview">
  <Tabs.List>
    <Tabs.Trigger value="overview">Übersicht</Tabs.Trigger>
    <Tabs.Trigger value="stages">Etappen <Badge>{trip.stages.length}</Badge></Tabs.Trigger>
    <Tabs.Trigger value="weather">Wetter-Briefing</Tabs.Trigger>
    <Tabs.Trigger value="reports">Reports & Kanäle</Tabs.Trigger>
    <Tabs.Trigger value="alarms">Alarmregeln <Badge>{alarmCount}</Badge></Tabs.Trigger>
  </Tabs.List>
  <Tabs.Content value="overview"><OverviewCards {trip} /></Tabs.Content>
  …
</Tabs.Root>
```

### OverviewCards (4 Cards, 2×2 Grid)

Each card has:
- Eyebrow (small caps mono)
- Title (15px semibold)
- 3-4 rows of label + meta + optional state-dot
- "Action →" link in top-right

```svelte
<DetailCard
  eyebrow="Reports"
  title="Was geht raus"
  rows={[
    { label: 'Abend-Briefing', meta: 'täglich 18:00 · Email + Signal', state: 'good' },
    { label: 'Morgen-Update',  meta: 'täglich 07:00 · Email',           state: 'good' },
    { label: 'Warnungen',      meta: '5 aktive Schwellen · Signal',     state: 'good' },
    { label: 'Trend-Vorschau', meta: 'deaktiviert',                     state: 'off' },
  ]}
  action="Reports anpassen"
  href="?tab=reports"
/>

<DetailCard eyebrow="Alarmregeln · 5" title="Wachhund-Schwellen" rows={[…]} action="Regeln verwalten" />
<DetailCard eyebrow="13 Etappen" title="Route & Etappen" rows={[…]} action="Etappen-Editor öffnen" />
<DetailCard eyebrow="Letzter Briefing-Lauf" title="Datenstand" rows={[…]} action="Briefing-Log öffnen" />
```

### Danger zone (am Seitenfuß)

```svelte
<div class="danger-zone">
  <span class="dz-eyebrow">Selten gebraucht</span>
  <button class="dz-link" onclick={duplicateTrip}>Trip duplizieren</button>
  <button class="dz-link" onclick={reimportGpx}>GPX neu importieren</button>
  <button class="dz-link" onclick={pauseTrip}>Briefings pausieren</button>
  <span class="spacer"></span>
  <button class="dz-link dz-link--danger" onclick={deleteTrip}>Trip löschen</button>
</div>
```

## Acceptance criteria

- [ ] `/trips/[id]` rendert Detail-Header mit Breadcrumb, Titel, Status, Meta, 3 Action-Buttons.
- [ ] Tab-Bar mit 5 Tabs (Übersicht aktiv default).
- [ ] Übersicht zeigt 4 DetailCards in 2×2-Grid.
- [ ] Jede Card hat einen Action-Link zum entsprechenden Tab oder Editor.
- [ ] Danger-Zone am Fuß mit 3 selten gebrauchten Aktionen + Löschen.
- [ ] „Test-Briefing senden" wandert von Home (Issue #03) hierher.

## 📎 Screenshots

**Soll: Detail-Seite mit Übersichts-Cards**

![soll-7B](https://raw.githubusercontent.com/henemm/gregor_zwanzig/main/.github/issue-assets/soll-flow7B-trip-detail.png)
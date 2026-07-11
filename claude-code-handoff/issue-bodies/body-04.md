<!-- gregor-zwanzig-handoff: stable_id=screen-trips-list -->
## Problem

Die `/trips` Liste rendert **6 Icon-Buttons pro Zeile** (Bell, Cloud-Sun, Pencil, Play, Play, Trash), separiert in „Edit-Gruppe" und „Send-Gruppe" via `gap-3`. Jeder Icon braucht einen Tooltip um seine Bedeutung zu offenbaren — das ist Datenbank-Admin-Tool-Optik, nicht produktiv:

> *„Selbst mit Tooltip — wer will das so bedienen? Versuche das einmal inhaltlich zu hinterfragen!"*
> — Product Owner, 2026-05-20

> *„Das ist doch ein längst verworfenes Layout! Wem sollen die vielen kleinen Buttons helfen?"*
> — Product Owner (Henning), 2026-06-05 — **das Icon-Geschwader war zwischenzeitlich wieder aufgetaucht (Regression). Dieses Issue ist die verbindliche Fassung.**

Inhaltliche Beobachtung: Die Trip-Liste ist ein **Werkzeugregal**, der User schaut hin um zu **sehen** was vorbereitet ist — die meiste Zeit nicht um zu **administrieren**. Die meiste Edit-Arbeit passiert vor dem Trip einmal (Wizard). Danach im Alltag: gelegentlich Briefing-Vorschau, sehr selten Schwellen-Tunen.

## Lösung (verbindlich = kanonisches Mockup)

**Cockpit-Muster, identisch zur Mobile-Karte (`TripCardM`):**

1. **Die ganze Zeile ist klickbar** → führt zur Trip-Detail-/Setup-Seite (`/trips/{id}`). Hover-Highlight + Chevron (`›`) am rechten Rand als Affordanz.
2. **Alle Aktionen kollabieren in EIN Overflow-Menü (`⋯`)** pro Zeile — kein Icon-Geschwader.
3. **Nur der aktive Trip** zeigt zusätzlich **eine** inline Quick-Action **„Briefing senden"** (links vom `⋯`). Geplante / fertige / Draft-Zeilen haben nur das `⋯`-Menü.

Maßgeblich ist das kanonische JSX-Mockup `claude-code-handoff/current/jsx/screen-trips.jsx` (1:1-Quelle für Epic #575) und das SOLL-Bild `current/soll/E-trips-list-variant.png`.

### Im Overflow-Menü (`⋯`) — exakt diese 6 Einträge (deckungsgleich mit dem Mobile-Sheet `TripActionsSheet`)

1. Briefing jetzt senden
2. Email-Vorschau
3. Alert-Konfiguration
4. Wetter-Metriken
5. Bearbeiten
6. Löschen *(danger, mit Confirm)*

Weitergehende Aktionen (Duplizieren, Pausieren/Reaktivieren) leben **auf der Detail-Seite**, nicht in der Listen-Zeile — siehe Issue #11 „Trip-Detail-Seite".

## Files

- `src/routes/trips/+page.svelte` (Hauptdatei, ~280 Zeilen)

## Required changes

### 1. Header + Eyebrow + Subtitle

```svelte
<header class="flex items-start justify-between gap-6 mb-7">
  <div>
    <Eyebrow>Workspace · Trips</Eyebrow>
    <h1 class="mt-1 text-3xl font-semibold tracking-tight">Trips</h1>
    <p class="mt-1.5 max-w-xl text-sm text-[var(--g-ink-muted)]">
      Alle aktiven, geplanten und abgeschlossenen Mehrtages-Trips. Pro Trip
      kannst du Alerts justieren, ein Briefing direkt schicken oder die
      Email-Vorschau öffnen. Klick auf eine Zeile öffnet die Detail-Ansicht.
    </p>
  </div>
  <Btn variant="primary" size="md" onclick={() => goto('/trips/new')}>+ Neuer Trip</Btn>
</header>
```

### 2. Tabellen-Zeile — neue Struktur

Die **ganze Zeile** ist die Navigations-Fläche (`role="button"`, Klick → Detail).
Die Aktions-Zelle stoppt die Event-Propagation, damit Buttons nicht die
Zeilen-Navigation auslösen.

```svelte
<Table.Row
  class="trip-row"
  role="button"
  tabindex="0"
  onclick={() => goto(`/trips/${trip.id}`)}
  onkeydown={(e) => (e.key === 'Enter' || e.key === ' ') && goto(`/trips/${trip.id}`)}
>
  <Table.Cell>
    <span class="flex items-center gap-2.5 min-w-0">
      <span data-slot="dot" data-size="xs" data-tone={statusTone(status)}></span>
      <span class="trip-name">{trip.name}</span>
      <span class="status-caption">· {statusLabel(status)}</span>
    </span>
  </Table.Cell>
  <Table.Cell class="hidden sm:table-cell">
    <span class="tabular-nums text-sm text-[var(--g-ink-muted)]">
      {trip.stages.length} {trip.stages.length === 1 ? 'Etappe' : 'Etappen'}
    </span>
  </Table.Cell>
  <Table.Cell class="hidden sm:table-cell font-mono tabular-nums text-sm text-[var(--g-ink-muted)]">
    {dateRange(trip)}
  </Table.Cell>
  <Table.Cell class="text-right">
    <div class="flex items-center justify-end gap-2" onclick={(e) => e.stopPropagation()}>
      {#if status === 'aktiv'}
        <Btn variant="ghost" size="sm" onclick={() => sendBriefing(trip)}>
          <PlayIcon class="size-3.5" /> Briefing senden
        </Btn>
      {/if}
      <KebabMenu trip={trip} />
      <ChevronRight class="size-4 text-[var(--g-ink-faint)]" aria-hidden="true" />
    </div>
  </Table.Cell>
</Table.Row>
```

Helpers:

```ts
function statusTone(s: string) { return ({aktiv:'warning', geplant:'success', fertig:'default', draft:'default'}[s] ?? 'default'); }
function statusLabel(s: string) { return ({aktiv:'aktiv', geplant:'geplant', fertig:'fertig', draft:'draft'}[s] ?? 'draft'); }
```

### 3. KebabMenu component

Use the existing shadcn `<DropdownMenu>` primitives (already in the project, search `lib/components/ui/dropdown-menu/`). **Exakt die 6 kanonischen Einträge:**

```svelte
<DropdownMenu.Root>
  <DropdownMenu.Trigger>
    <Btn variant="ghost" size="icon-sm" title="Aktionen">⋯</Btn>
  </DropdownMenu.Trigger>
  <DropdownMenu.Content align="end" class="w-56">
    <DropdownMenu.Item onclick={() => sendBriefing(trip)}>Briefing jetzt senden</DropdownMenu.Item>
    <DropdownMenu.Item onclick={() => openBriefingPreview(trip)}>Email-Vorschau</DropdownMenu.Item>
    <DropdownMenu.Item onclick={() => openAlertConfig(trip)}>Alert-Konfiguration</DropdownMenu.Item>
    <DropdownMenu.Item onclick={() => openMetricsEditor(trip)}>Wetter-Metriken</DropdownMenu.Item>
    <DropdownMenu.Item onclick={() => openEdit(trip)}>Bearbeiten</DropdownMenu.Item>
    <DropdownMenu.Separator />
    <DropdownMenu.Item class="text-[var(--g-danger)]" onclick={() => deleteTarget = trip}>
      Löschen
    </DropdownMenu.Item>
  </DropdownMenu.Content>
</DropdownMenu.Root>
```

### 4. Klickbare Zeile → Detail-Seite

Die Zeile (nicht nur der Name) navigiert. Name optisch als Anker erkennbar:

```css
.trip-row { cursor: pointer; transition: background 120ms; }
.trip-row:hover { background: var(--g-card-alt); }
.trip-name { font-size: 14px; font-weight: 600; color: var(--g-ink); letter-spacing: -0.01em; }
```

### 5. Status-Caption + Status-Dot

Reuse existing `[data-slot="dot"]` tones. Caption:

```css
.status-caption {
  font-family: var(--g-font-data);
  font-size: 9px; letter-spacing: 0.18em; text-transform: uppercase;
  color: var(--g-ink-faint);
}
```

### 6. Footer counter

```svelte
<p class="mt-4 font-mono text-[10px] tracking-wide uppercase text-[var(--g-ink-faint)]">
  {filteredTrips.length} von {trips.length} Trips
</p>
```

### 7. Search

Bestehender Search-Input erhalten — nur Styling-Diffs:
- `max-w-[380px]`
- `rounded-full`
- Search-Icon `--g-ink-faint`

### 8. Remove the old action-icon grid

Lösche die kompletten `<div class="inline-flex flex-wrap justify-end gap-3">…</div>` Blöcke mit den 6 Icon-Buttons.

## Acceptance criteria

- [ ] **Kein** Icon-Geschwader mehr — pro Zeile höchstens: (aktiv) ein „Briefing senden"-Button + `⋯` + Chevron; (sonst) nur `⋯` + Chevron.
- [ ] Klick auf eine **Zeile** navigiert zu `/trips/{id}` (Detail-Seite); Buttons in der Aktions-Zelle lösen die Zeilen-Navigation **nicht** aus (`stopPropagation`).
- [ ] Inline „Briefing senden" erscheint **nur** beim aktiven Trip.
- [ ] Das `⋯`-Menü enthält genau die 6 kanonischen Einträge (Briefing jetzt senden · Email-Vorschau · Alert-Konfiguration · Wetter-Metriken · Bearbeiten · Löschen), Löschen als danger mit Confirm.
- [ ] Status-Dot + lowercase mono caption pro Zeile.
- [ ] Mono-Daten mit tabular-nums.
- [ ] Footer „N von M Trips" in mono caps.
- [ ] Tastatur: Zeile ist mit Enter/Space aktivierbar; `⋯`-Menü per Tastatur bedienbar.
- [ ] Alle Playwright `data-testid`s erhalten — Tests dürfen nicht brechen.

## 📎 Screenshots

**Soll: reduzierte Liste — Overflow-Menü + (aktiv) inline „Briefing senden", ganze Zeile klickbar**

![soll-trips-reduced](https://raw.githubusercontent.com/henemm/gregor_zwanzig/main/.github/issue-assets/soll-trips-list-reduced.png)

**Ist (Regression): 6 Icons pro Zeile mit Tooltips**

![ist-trips](https://raw.githubusercontent.com/henemm/gregor_zwanzig/main/.github/issue-assets/01-trips-list.png)

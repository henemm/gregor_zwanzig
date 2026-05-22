<!-- gregor-zwanzig-handoff: stable_id=screen-trips-list -->
## Problem

Die `/trips` Liste rendert **6 Icon-Buttons pro Zeile** (Bell, Cloud-Sun, Pencil, Play, Play, Trash), separiert in „Edit-Gruppe" und „Send-Gruppe" via `gap-3`. Jeder Icon braucht einen Tooltip um seine Bedeutung zu offenbaren — das ist Datenbank-Admin-Tool-Optik, nicht produktiv:

> *„Selbst mit Tooltip — wer will das so bedienen? Versuche das einmal inhaltlich zu hinterfragen!"*
> — Product Owner, 2026-05-20

Inhaltliche Beobachtung: Die Trip-Liste ist ein **Werkzeugregal**, der User schaut hin um zu **sehen** was vorbereitet ist — die meiste Zeit nicht um zu **administrieren**. Die meiste Edit-Arbeit passiert vor der Tour einmal (Wizard). Danach im Alltag: gelegentlich Briefing-Vorschau, sehr selten Schwellen-Tunen.

## Lösung

**Eine kontextuelle Primäraktion + ein Kebab-Menü.** Klick auf den Trip-Namen führt zur Detail-Seite, wo alle Aktionen prominent erreichbar sind.

### Status-driven primary actions

| Status | Primäraktion |
|---|---|
| `aktiv`   | „Briefing-Vorschau" |
| `geplant` | „Briefing-Vorschau" |
| `fertig`  | „Archivieren" |
| `draft`   | „Fertigstellen" (springt in Wizard) |

### Im Kebab-Menü (`⋯`)

- Bearbeiten
- Test-Briefing senden (Morgen / Abend)
- Wetter-Konfiguration
- Alerts justieren
- Duplizieren
- Pausieren / Reaktivieren
- Löschen (mit Confirm)

Alle anderen Aktionen sind **auf der Detail-Seite** prominent — siehe Issue #07b "Trip-Detail-Seite".

## Files

- `src/routes/trips/+page.svelte` (Hauptdatei, ~280 Zeilen)

## Required changes

### 1. Header + Eyebrow + Subtitle

```svelte
<header class="flex items-start justify-between gap-6 mb-7">
  <div>
    <Eyebrow>Meine Touren</Eyebrow>
    <h1 class="mt-1 text-3xl font-semibold tracking-tight">Deine Trips</h1>
    <p class="mt-1.5 max-w-xl text-sm text-[var(--g-ink-muted)]">
      Trips vor der Abreise vorbereiten — unterwegs läuft alles autark.
      Klick auf einen Trip-Namen für die Detail-Ansicht.
    </p>
  </div>
  <Btn variant="primary" size="md" onclick={() => goto('/trips/new')}>+ Neuer Trip</Btn>
</header>
```

### 2. Tabellen-Zeile — neue Struktur

```svelte
<Table.Row>
  <Table.Cell>
    <span class="flex items-center gap-2.5 min-w-0">
      <span data-slot="dot" data-size="xs" data-tone={statusTone(status)}></span>
      <a href="/trips/{trip.id}" class="trip-link">{trip.name}</a>
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
    <Btn variant="outline" size="sm" onclick={() => primaryAction(trip, status)}>
      {primaryLabel(status)}
    </Btn>
  </Table.Cell>
  <Table.Cell class="w-8">
    <KebabMenu trip={trip} />
  </Table.Cell>
</Table.Row>
```

Helpers:

```ts
function statusTone(s: string) { return ({aktiv:'warning', geplant:'success', fertig:'default', draft:'default'}[s] ?? 'default'); }
function statusLabel(s: string) { return ({aktiv:'aktiv', geplant:'geplant', fertig:'fertig', draft:'draft'}[s] ?? 'draft'); }
function primaryLabel(s: string) {
  return { aktiv: 'Briefing-Vorschau', geplant: 'Briefing-Vorschau',
           fertig: 'Archivieren', draft: 'Fertigstellen' }[s] ?? 'Öffnen';
}
function primaryAction(trip: Trip, s: string) {
  if (s === 'draft') goto(`/trips/${trip.id}/wizard`);
  else if (s === 'fertig') archiveTrip(trip);
  else openBriefingPreview(trip);
}
```

### 3. KebabMenu component

Use the existing shadcn `<DropdownMenu>` primitives (already in the project, search `lib/components/ui/dropdown-menu/`):

```svelte
<DropdownMenu.Root>
  <DropdownMenu.Trigger>
    <Btn variant="ghost" size="icon-sm" title="Mehr Aktionen">⋯</Btn>
  </DropdownMenu.Trigger>
  <DropdownMenu.Content align="end" class="w-56">
    <DropdownMenu.Item onclick={() => openEdit(trip)}>Bearbeiten</DropdownMenu.Item>
    <DropdownMenu.Sub>
      <DropdownMenu.SubTrigger>Test-Briefing senden</DropdownMenu.SubTrigger>
      <DropdownMenu.SubContent>
        <DropdownMenu.Item onclick={() => runTestReport(trip, 7)}>Morgen-Report (07:00)</DropdownMenu.Item>
        <DropdownMenu.Item onclick={() => runTestReport(trip, 18)}>Abend-Report (18:00)</DropdownMenu.Item>
      </DropdownMenu.SubContent>
    </DropdownMenu.Sub>
    <DropdownMenu.Item onclick={() => weatherConfigTarget = trip}>Wetter-Konfiguration…</DropdownMenu.Item>
    <DropdownMenu.Item onclick={() => openReportConfig(trip)}>Alerts justieren…</DropdownMenu.Item>
    <DropdownMenu.Separator />
    <DropdownMenu.Item onclick={() => duplicateTrip(trip)}>Duplizieren</DropdownMenu.Item>
    <DropdownMenu.Item onclick={() => togglePause(trip)}>{trip.paused ? 'Reaktivieren' : 'Pausieren'}</DropdownMenu.Item>
    <DropdownMenu.Separator />
    <DropdownMenu.Item class="text-[var(--g-danger)]" onclick={() => deleteTarget = trip}>
      Löschen
    </DropdownMenu.Item>
  </DropdownMenu.Content>
</DropdownMenu.Root>
```

### 4. Klickbarer Trip-Name → Detail-Seite

```css
.trip-link {
  font-size: 14px; font-weight: 600;
  color: var(--g-ink);
  text-decoration-color: transparent;
  text-decoration-line: underline;
  text-underline-offset: 4px;
  transition: text-decoration-color 120ms;
}
.trip-link:hover { text-decoration-color: var(--g-accent); }
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
  {filteredTrips.length} Trips · {trips.length - filteredTrips.length} versteckt
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

- [ ] Pro Zeile sind **maximal 2 sichtbare interaktive Elemente**: Primärbutton + Kebab.
- [ ] Klick auf Trip-Name navigiert zu `/trips/{id}` (Detail-Seite).
- [ ] Primärbutton-Label ändert sich kontextabhängig (`aktiv`/`geplant` = Briefing-Vorschau; `fertig` = Archivieren; `draft` = Fertigstellen).
- [ ] Kebab-Menü enthält alle ursprünglichen Aktionen (Bearbeiten, Test-Briefings, Wetter-Config, Alert-Config, Duplizieren, Pausieren, Löschen).
- [ ] Status-Dot + lowercase mono caption pro Zeile.
- [ ] Mono-Daten mit tabular-nums.
- [ ] Footer „N Trips · M versteckt" in mono caps.
- [ ] Alle Playwright `data-testid`s erhalten — Tests dürfen nicht brechen.

## 📎 Screenshots

**Soll: reduzierte Liste mit einer Primäraktion + Kebab**

![soll-trips-reduced](https://raw.githubusercontent.com/henemm/gregor_zwanzig/main/.github/issue-assets/soll-flow7A-trip-list-reduced.png)

**Ist: 6 Icons pro Zeile mit Tooltips**

![ist-trips](https://raw.githubusercontent.com/henemm/gregor_zwanzig/main/.github/issue-assets/01-trips-list.png)
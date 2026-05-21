---
entity_id: bug_282_295_trips_list_redesign
type: module
created: 2026-05-21
updated: 2026-05-21
status: draft
version: "1.0"
tags: [frontend, trips, desktop, table, kebab, visual-structure, redesign, issue-282, issue-295]
---

# Bug #282 + #295 — Trips-Liste: Visual Structure Restore + Kebab-Menü

## Approval

- [ ] Approved

## Purpose

Die Desktop-Tabelle auf `/trips` hat nach früheren Refactors optische Struktur verloren (fehlende Eyebrow, falsche H1-Typografie, kein Subtitle, kein Summary-Stats-Strip) und eine unübersichtliche Aktionsspalte mit sechs gleichrangigen Icon-Buttons angehäuft. Issue #282 stellt die visuelle Hierarchie der Seiten-Kopfzeile wieder her und ergänzt eine kompakte Status-Statistik-Zeile. Issue #295 ersetzt die sechs Icon-Buttons durch einen primären kontextabhängigen Aktions-Button und ein Kebab-Menü (`⋯`) mit Inline-Dropdown — dadurch wird die Aktionsspalte übersichtlich und die wichtigste Aktion ist mit einem Klick erreichbar. Beide Issues teilen dieselbe Zieldatei und werden als ein einziger Workflow umgesetzt. Die Mobile-Ansicht (Card-Stack + Bottom-Sheet aus Issue #268) bleibt vollständig unverändert.

> **Schicht-Hinweis:** Alle Änderungen liegen ausschließlich im Frontend-Layer (`frontend/src/`). Kein Go-API-Code, kein Python-Backend-Code ist betroffen.

## Source

- **File:** `frontend/src/routes/trips/+page.svelte`
- **Identifier:** `+page.svelte` (SvelteKit Route Component)

## Dependencies

| Entity | Type | Zweck |
|--------|------|-------|
| `frontend/src/lib/utils/tripStatus.ts` | TypeScript-Utility (vorhanden, read-only) | `deriveTripStatus(trip, now)` liefert `'active' \| 'planned' \| 'paused' \| 'archived'` — steuert Primary-Button-Label, Dot-Tone und Summary-Stats |
| `frontend/src/lib/components/ui/dot/Dot.svelte` | Svelte-Komponente (vorhanden, read-only) | Farbiger Status-Dot mit `tone`-Prop und `size="sm"` — wird in Tabellenzeilen genutzt |
| `frontend/src/lib/components/ui/eyebrow/Eyebrow.svelte` | Svelte-Komponente (vorhanden, read-only) | Eyebrow-Text über dem H1 |
| `frontend/src/lib/components/ui/btn/index.js` | Svelte-Komponente (vorhanden, read-only) | `<Btn variant="outline" size="sm">` für Primary-Button; bestehende Btn-Importe bleiben |
| `frontend/src/lib/components/ui/input/index.js` | Svelte-Komponente (vorhanden, read-only) | Search-Input erhält zusätzliche Klassen `max-w-[380px] rounded-full` |
| `frontend/src/lib/types.ts` | TypeScript-Typdefinition (vorhanden, read-only) | `Trip`-Interface |
| `$app/navigation` (SvelteKit) | Framework-Utility | `goto()` für Navigation zu `/trips/{id}#preview` |
| `frontend/src/app.css` | CSS-Datei (vorhanden, unverändert) | `desktop:` Breakpoint (`@media (min-width: 900px)`), Design-Tokens, `hidden desktop:flex` |

## Scope

**Direkt geänderte Dateien:**

| Datei | Änderung |
|-------|---------|
| `frontend/src/routes/trips/+page.svelte` | Header-Umbau (Eyebrow, H1, Subtitle, Summary-Stats), Search-Klassen, Tabellen-Aktionsspalte (Primary-Button + Kebab-State + Inline-Dropdown), Trip-Name als `<a>`-Link, Footer-Zeile, neue Imports/State |
| `frontend/e2e/trips.spec.ts` | Delete-Test: Kebab öffnen vor dem Klick auf "Löschen" |
| `frontend/e2e/issue-90-trip-icon-grouping.spec.ts` | Vollständige Neufassung — alte 6-Button-Struktur existiert nicht mehr |
| `frontend/e2e/trip-edit.spec.ts` | `trip-edit-btn` liegt jetzt im Kebab-Menü — Kebab muss vor dem Klick geöffnet werden |

**Nicht geändert:**

- Mobile Card-Stack (`desktop:hidden`) und Bottom-Sheet aus Issue #268 — vollständig unberührt
- Mobile Test-IDs: `trip-card-stack`, `trip-card`, `trip-card-content-btn`, `trip-card-menu-btn`, `trip-action-sheet`
- Alle bestehenden Dialog-Komponenten (`ReportConfigDialog`, `WeatherConfigDialog`, `EditTripDialog`, Test-Report-Dialog, Delete-Dialog)
- `frontend/src/app.css`
- Go-Backend, Python-Backend

## Implementation Details

### 1. Neue Imports und State

Im `<script>`-Block ergänzen:

```typescript
import { Eyebrow } from '$lib/components/ui/eyebrow/index.js';
// Dot, deriveTripStatus, filteredTrips, now, statusTone bereits vorhanden (Issue #268)

let kebabOpenId: string | null = $state(null);
```

`kebabOpenId` speichert die `trip.id` des Trips, für dessen Zeile das Kebab-Dropdown offen ist. `null` = alle Dropdowns geschlossen.

### 2. Header-Umbau (Issue #282)

Bestehenden Header-Block ersetzen:

```svelte
<div class="flex items-start justify-between gap-4">
  <div>
    <Eyebrow>WORKSPACE · TOUREN</Eyebrow>
    <h1 class="text-3xl font-semibold tracking-tight">Trips</h1>
    <p class="text-muted-foreground mt-1">
      Alle Touren auf einen Blick — Status, Zeitraum und Aktionen.
    </p>
  </div>
  <Btn variant="accent" onclick={() => goto('/trips/new')}>Neuer Trip</Btn>
</div>
```

### 3. Summary-Stats (Issue #282, desktop only)

Direkt nach dem Header-Block, vor dem Search-Input:

```svelte
{#if trips.length > 0}
  <div class="hidden desktop:flex gap-6 mt-4">
    {#each [
      { label: 'Aktiv',      status: 'active',   tone: 'success' },
      { label: 'Geplant',    status: 'planned',  tone: 'info'    },
      { label: 'Pausiert',   status: 'paused',   tone: 'warning' },
      { label: 'Archiviert', status: 'archived', tone: 'danger'  },
    ] as stat}
      {@const count = trips.filter(t => deriveTripStatus(t, now) === stat.status).length}
      <div class="flex items-center gap-1.5 text-sm">
        <Dot tone={stat.tone} size="sm" />
        <span class="font-mono tabular-nums">{count}</span>
        <span class="text-muted-foreground">{stat.label}</span>
      </div>
    {/each}
  </div>
{/if}
```

### 4. Search-Input Anpassung (Issue #282)

Am bestehenden `<Input>`-Tag die Klassen `max-w-[380px]` und `rounded-full` ergänzen:

```svelte
<Input placeholder="Suchen..." class="pl-8 max-w-[380px] rounded-full" bind:value={search} />
```

### 5. Trip-Name als Link (Issue #295)

In der Desktop-Tabelle den Trip-Namen-Span durch einen Link ersetzen:

```svelte
<a href="/trips/{trip.id}" class="font-medium hover:underline">
  {trip.name}
</a>
<div class="font-mono text-xs text-muted-foreground tabular-nums">
  {trip.stages?.length ?? 0} Etappen
</div>
```

### 6. Datum-Spalte (Issue #282)

Datum-Zelle erhält `font-mono tabular-nums text-sm text-muted-foreground`.

### 7. Aktionsspalte: Primary-Button + Kebab (Issue #295)

Die sechs Icon-Buttons werden ersetzt. Hilfsfunktion im `<script>`-Block:

```typescript
function primaryAction(trip: Trip): { label: string; action: () => void } {
  const status = deriveTripStatus(trip, now);
  if (status === 'active' || status === 'planned') {
    return { label: 'Briefing-Vorschau', action: () => goto(`/trips/${trip.id}#preview`) };
  }
  if (status === 'paused') {
    return {
      label: 'Reaktivieren',
      action: () => fetch(`/api/trips/${trip.id}/state`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ paused: false })
      }).then(() => location.reload())
    };
  }
  // archived
  return {
    label: 'Dearchivieren',
    action: () => fetch(`/api/trips/${trip.id}/state`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ archived: false })
    }).then(() => location.reload())
  };
}
```

Aktionsspalte im Template:

```svelte
<td class="relative">
  <div class="flex items-center gap-2">
    <!-- Primary Button -->
    {@const pa = primaryAction(trip)}
    <Btn variant="outline" size="sm" onclick={pa.action}>{pa.label}</Btn>

    <!-- Kebab -->
    <div class="relative">
      <Btn
        variant="ghost"
        size="icon-sm"
        title="Weitere Aktionen"
        onclick={(e) => {
          e.stopPropagation();
          kebabOpenId = kebabOpenId === trip.id ? null : trip.id;
        }}
      >⋯</Btn>

      {#if kebabOpenId === trip.id}
        <div
          class="absolute right-0 top-full mt-1 z-50 min-w-[200px] rounded-md border
                 bg-popover shadow-md py-1"
          onfocusout={(e) => {
            if (!e.currentTarget.contains(e.relatedTarget)) kebabOpenId = null;
          }}
          tabindex="-1"
        >
          <button
            data-testid="trip-edit-btn"
            class="w-full text-left px-3 py-1.5 text-sm hover:bg-accent"
            onclick={() => { kebabOpenId = null; openEdit(trip); }}
          >Bearbeiten</button>

          <button
            class="w-full text-left px-3 py-1.5 text-sm hover:bg-accent"
            onclick={() => { kebabOpenId = null; runTestReport(trip, 7); }}
          >Test-Briefing Morgen</button>

          <button
            class="w-full text-left px-3 py-1.5 text-sm hover:bg-accent"
            onclick={() => { kebabOpenId = null; runTestReport(trip, 18); }}
          >Test-Briefing Abend</button>

          <button
            class="w-full text-left px-3 py-1.5 text-sm hover:bg-accent"
            onclick={() => { kebabOpenId = null; weatherConfigTarget = trip; }}
          >Wetter-Konfiguration</button>

          <button
            class="w-full text-left px-3 py-1.5 text-sm hover:bg-accent"
            onclick={() => { kebabOpenId = null; openReportConfig(trip); }}
          >Report-Konfiguration</button>

          <hr class="my-1 border-border" />

          <button
            class="w-full text-left px-3 py-1.5 text-sm text-destructive hover:bg-accent"
            onclick={() => { kebabOpenId = null; deleteTarget = trip; }}
          >Löschen</button>
        </div>
      {/if}
    </div>
  </div>
</td>
```

**Schließen-Mechanismus:** `onfocusout` auf dem Dropdown-Container: wenn der Fokus das Element verlässt und das neue `relatedTarget` nicht innerhalb des Containers liegt, wird `kebabOpenId = null` gesetzt. Das Dropdown bleibt offen während der Nutzer zwischen den Items tabbt. Kein globaler `document.click`-Listener nötig.

### 8. Footer-Zeile (Issue #282)

Direkt nach dem schließenden `</table>`-Tag der Desktop-Tabelle:

```svelte
<p class="hidden desktop:block text-xs font-mono uppercase tracking-wide text-muted-foreground mt-2">
  {filteredTrips.length} von {trips.length} Trips
</p>
```

### 9. E2E-Test-Anpassungen

**`frontend/e2e/trips.spec.ts` — Delete-Test:**

```typescript
// Alt: const deleteBtn = firstRow.getByRole('button', { name: 'Löschen' });
// Neu: Kebab öffnen, dann Löschen klicken
const kebabBtn = firstRow.getByTitle('Weitere Aktionen');
await kebabBtn.click();
const deleteBtn = firstRow.getByRole('button', { name: 'Löschen' });
await deleteBtn.click();
```

**`frontend/e2e/trip-edit.spec.ts` — Edit-Test:**

```typescript
// Alt: await row.locator('[data-testid="trip-edit-btn"]').click();
// Neu:
await row.getByTitle('Weitere Aktionen').click();
await row.locator('[data-testid="trip-edit-btn"]').click();
```

**`frontend/e2e/issue-90-trip-icon-grouping.spec.ts` — Vollneufassung:**

Alle Tests, die die alte 6-Icon-Struktur prüfen, werden durch Tests ersetzt, die:
1. Primary-Button mit status-korrektem Label prüfen (`Briefing-Vorschau` / `Reaktivieren` / `Dearchivieren`)
2. Kebab öffnet Dropdown mit genau 6 Items (Bearbeiten, Test-Briefing Morgen, Test-Briefing Abend, Wetter-Konfiguration, Report-Konfiguration, Löschen) in der angegebenen Reihenfolge
3. Kebab schließt sich bei Fokus-Verlust

## Expected Behavior

- **Input:** Liste der Trips via SvelteKit `$page.data.trips` (unverändert)
- **Output (visuell, Desktop ≥ 900px):**
  - Eyebrow "WORKSPACE · TOUREN" über H1 "Trips" mit `text-3xl font-semibold tracking-tight`
  - Subtitle unterhalb der H1
  - 4-Spalten Summary-Stats-Strip (nur wenn mindestens 1 Trip vorhanden)
  - Search-Input mit `max-w-[380px]` und `rounded-full`
  - Trip-Name als anklickbarer Link zum Trip-Detail
  - Datum-Zelle in `font-mono tabular-nums`
  - Aktionsspalte: 1 Primary-Button + 1 Kebab-Button pro Zeile
  - Footer: `{filteredTrips.length} von {trips.length} Trips` in Mono-Caps
- **Output (Mobile ≤ 899px):** Identisch zu vorherigem Stand (Issue #268) — keinerlei Änderung
- **Side effects:**
  - `kebabOpenId = trip.id` öffnet Inline-Dropdown für genau diese Zeile; alle anderen Dropdowns sind geschlossen
  - `kebabOpenId = null` schließt das Dropdown (via onfocusout oder Item-Klick)
  - PATCH-Calls (`Reaktivieren`, `Dearchivieren`) führen nach Erfolg `location.reload()` aus
  - Navigation zu `#preview` öffnet den Preview-Tab in der Trip-Detail-Seite

## Acceptance Criteria

**AC-1:** Given die Route `/trips` auf einem Viewport ≥ 900px mit mindestens einem Trip / When die Seite geladen wird / Then ist über der H1 "Trips" ein Eyebrow-Text "WORKSPACE · TOUREN" sichtbar, die H1 hat `text-3xl font-semibold tracking-tight`, und darunter steht der Subtitle-Text.

**AC-2:** Given die Route `/trips` auf einem Viewport ≥ 900px mit Trips verschiedener Status / When die Seite geladen wird / Then ist ein Summary-Stats-Strip mit 4 Einträgen sichtbar (Aktiv, Geplant, Pausiert, Archiviert), jeder mit einem farbigen Status-Dot und der korrekten Anzahl aus `deriveTripStatus()`.

**AC-3:** Given die Desktop-Tabelle auf einem Viewport ≥ 900px / When der Nutzer in der Aktionsspalte auf den `⋯`-Button einer Tabellenzeile klickt / Then öffnet sich ein Inline-Dropdown mit genau 6 Items in der Reihenfolge: Bearbeiten, Test-Briefing Morgen, Test-Briefing Abend, Wetter-Konfiguration, Report-Konfiguration, [Trennlinie], Löschen — und das Item "Bearbeiten" trägt `data-testid="trip-edit-btn"`.

**AC-4:** Given das Kebab-Dropdown ist geöffnet / When der Nutzer den Fokus aus dem Dropdown heraus bewegt (Tab oder Klick außerhalb) / Then schließt sich das Dropdown (`kebabOpenId` wird `null`) ohne dass ein Dialog geöffnet wurde.

**AC-5:** Given ein Trip mit Status `active` oder `planned` in der Desktop-Tabelle / When die Aktionsspalte gerendert wird / Then zeigt der Primary-Button das Label "Briefing-Vorschau"; bei `paused` lautet das Label "Reaktivieren"; bei `archived` lautet das Label "Dearchivieren".

**AC-6:** Given die Desktop-Tabelle auf einem Viewport ≥ 900px / When der Nutzer auf den Trip-Namen klickt / Then navigiert der Browser zur Route `/trips/{id}` für diesen Trip, ohne dass das Kebab-Dropdown geöffnet wird.

**AC-7:** Given die Route `/trips` auf einem Viewport ≤ 899px / When die Seite geladen wird / Then sind Card-Stack (`trip-card-stack`), alle `trip-card`-Elemente, `trip-card-content-btn`, `trip-card-menu-btn` und `trip-action-sheet` vollständig erhalten und funktionsfähig — keine Mobile-Elemente wurden verändert.

**AC-8:** Given die Desktop-Tabelle mit aktiver Suchfilterung (z.B. `filteredTrips.length < trips.length`) / When die Seite gerendert wird / Then zeigt der Footer "X von Y Trips" mit den korrekten Zahlen in Mono-Caps unterhalb der Tabelle.

## Known Limitations

- **`location.reload()` nach PATCH:** `Reaktivieren` und `Dearchivieren` lösen einen vollen Page-Reload aus, um den aktualisierten Status-Dot und Primary-Button-Label korrekt darzustellen. Ein reaktives Store-Update wäre eleganter, ist aber kein Bestandteil dieses Issues.
- **`onfocusout` auf dem Dropdown:** Funktioniert zuverlässig bei Tab-Navigation und Mausklick außerhalb. Bei Touch ohne Fokus-Unterstützung (bestimmte mobile Browser) kann das Dropdown offen bleiben — auf Mobile ist die Desktop-Tabelle jedoch ohnehin nicht sichtbar (`hidden desktop:block`).
- **Kebab öffnet nur ein Dropdown gleichzeitig:** `kebabOpenId` ist ein einzelner String-State. Beim Klick auf einen zweiten Kebab schließt sich das erste automatisch, weil `kebabOpenId` überschrieben wird.
- **`deriveTripStatus` mit fester `now`-Zeit:** Identisch zu Issue #268 — `now` wird einmalig beim Komponenten-Mount gesetzt. Akzeptables Verhalten.

## Changelog

- 2026-05-21: Initial spec erstellt (Issues #282 + #295 — Desktop Trips-Liste: Visual Structure Restore + Primary-Button + Kebab-Menü).

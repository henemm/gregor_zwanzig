---
entity_id: issue_268_trips_mobile_card_stack
type: module
created: 2026-05-20
updated: 2026-05-20
status: active
version: "1.0"
tags: [frontend, mobile, trips, card-stack, bottom-sheet, touch-target, svelte, responsive, issue-268]
---

# Issue #268 — Trips-Liste: Card-Stack + Bottom-Sheet auf Mobile

## Approval

- [ ] Approved

## Purpose

Die Trips-Übersicht auf `/trips` rendert auf Viewports ≤ 899px eine HTML-Tabelle mit Aktions-Icons von ca. 30px — deutlich unter dem 44px-Touch-Target-Minimum für mobile Geräte. Dieses Modul ersetzt die Tabelle auf Mobile durch einen vertikal gestapelten Card-Stack, bei dem jede Card einen Status-Dot, den Trip-Namen, die Etappen-Anzahl und den Reisezeitraum anzeigt, und alle Aktionen in ein Bottom-Sheet-Menü hinter einem `···`-Button kollabiert, der das 44×44px-Touch-Target-Minimum erfüllt — während die Desktop-Tabelle ab ≥ 900px vollständig unverändert bleibt.

> **Schicht-Hinweis:** Alle Änderungen liegen ausschließlich im Frontend-Layer (`frontend/src/`). Kein Go-API-Code, kein Python-Backend-Code ist betroffen.

## Source

- **File:** `frontend/src/routes/trips/+page.svelte`
- **Identifier:** `+page.svelte` (SvelteKit Route Component)

## Dependencies

| Entity | Type | Zweck |
|--------|------|-------|
| `frontend/src/lib/utils/tripStatus.ts` | TypeScript-Utility (vorhanden, read-only) | `deriveTripStatus(trip, now)` liefert `'active' \| 'planned' \| 'paused' \| 'archived'` — bestimmt Farb-Tone des Status-Dots |
| `frontend/src/lib/components/ui/dot/Dot.svelte` | Svelte-Komponente (vorhanden, read-only) | Farbiger Status-Dot mit `tone`-Prop: `success`, `info`, `warning`, `danger` |
| `frontend/src/lib/types.ts` | TypeScript-Typdefinition (vorhanden, read-only) | `Trip`-Interface mit allen Trip-Feldern |
| `@lucide/svelte/icons/ellipsis-vertical` | Icon-Bibliothek (vorhanden) | `EllipsisVerticalIcon` für den `···`-Button im Card-Stack |
| `frontend/src/app.css` | CSS-Datei (vorhanden, unverändert) | Stellt `desktop:hidden`, `hidden desktop:block`, `data-slot="g-card"`-Hooks, `--g-paper-deep`, `--g-rule-soft`, `--g-ink`, `--g-accent` bereit |
| `$app/navigation` (SvelteKit) | Framework-Utility | `goto()` für Navigation zum Trip-Detail beim Tippen auf die Card |

## Scope

**Nur 1 Datei ändert sich:**

- **Geändert:** `frontend/src/routes/trips/+page.svelte` — Neue Imports, neuer State, Card-Stack-Block, Desktop-Wrapper-Klasse, Bottom-Sheet

Keine Änderungen an:
- `frontend/src/app.css` (alle benötigten Tokens und Variants sind vorhanden)
- `frontend/src/lib/utils/tripStatus.ts`
- `frontend/src/lib/components/ui/dot/Dot.svelte`
- `frontend/src/lib/types.ts`
- Alle Dialog-Komponenten (`ReportConfigDialog`, `WeatherConfigDialog`, `EditTripDialog`, etc.)
- Go-Backend, Python-Backend

## Implementation Details

### 1. Neue Imports

Folgende Imports am Anfang des `<script>`-Blocks ergänzen:

```typescript
import EllipsisVerticalIcon from '@lucide/svelte/icons/ellipsis-vertical';
import { Dot } from '$lib/components/ui/dot/index.js';
import { deriveTripStatus } from '$lib/utils/tripStatus.js';
// goto ist bereits importiert — kein neuer Import nötig

const now = new Date(); // einmalig, kein reaktiver State
```

### 2. Neuer State

Im `<script>`-Block unmittelbar nach den bestehenden State-Deklarationen einfügen:

```typescript
let sheetTrip: Trip | null = $state(null);
```

`sheetTrip` hält die Referenz auf den Trip, für den das Bottom-Sheet gerade geöffnet ist. `null` bedeutet: Sheet geschlossen.

### 3. Status-Dot-Tone-Mapping

Hilfsfunktion im `<script>`-Block:

```typescript
function statusTone(trip: Trip): 'success' | 'info' | 'warning' | 'danger' {
  const status = deriveTripStatus(trip, now);
  if (status === 'active')   return 'success';
  if (status === 'planned')  return 'info';
  if (status === 'paused')   return 'warning';
  return 'danger'; // 'archived'
}
```

### 4. Desktop-Tabelle: Wrapper-Klasse ergänzen

Den bestehenden äußersten `<div>`- oder `<table>`-Wrapper der Tabelle erhält zusätzlich:

```svelte
<div class="hidden desktop:block">
  <!-- bestehende Tabelle unverändert -->
</div>
```

**Keine weiteren Änderungen** an der Tabelle oder den Aktions-Icons.

### 5. Card-Stack (Mobile, `desktop:hidden`)

Direkt vor dem Desktop-Tabellen-Wrapper einfügen:

```svelte
<div class="desktop:hidden flex flex-col gap-3 p-4">
  {#each trips as trip (trip.id)}
    <div data-slot="g-card" class="flex items-center gap-3 px-3 py-2">
      <!-- Status-Dot links -->
      <Dot tone={statusTone(trip)} />

      <!-- Inhalt-Block: navigiert zur Trip-Detail-Seite -->
      <button
        class="flex-1 flex flex-col items-start text-left min-h-[44px] justify-center"
        onclick={() => goto(`/trips/${trip.id}`)}
      >
        <span class="font-semibold text-[var(--g-ink)]">{trip.name}</span>
        <span class="text-sm text-[var(--g-ink-muted)]">
          {trip.stages?.length ?? 0} Etappen · {dateRange(trip)}
        </span>
      </button>

      <!-- ··· Menü-Button rechts -->
      <button
        class="min-h-[44px] min-w-[44px] flex items-center justify-center"
        onclick={() => (sheetTrip = trip)}
        aria-label="Aktionen für {trip.name}"
      >
        <EllipsisVerticalIcon size={20} />
      </button>
    </div>
  {/each}
</div>
```

`dateRange(trip)` ist die bereits im File vorhandene Hilfsfunktion für den Zeitraum-String.

### 6. Bottom-Sheet

Nach allen bestehenden Dialog-Blöcken, unmittelbar vor dem schließenden Root-Tag, einfügen:

```svelte
<!-- Bottom-Sheet Backdrop -->
{#if sheetTrip !== null}
  <div
    class="fixed inset-0 z-[70] bg-black/50 desktop:hidden"
    onclick={() => (sheetTrip = null)}
    role="presentation"
  ></div>
{/if}

<!-- Bottom-Sheet Panel (immer im DOM, per translate-y animiert) -->
<div
  class="fixed bottom-0 left-0 right-0 z-[75] desktop:hidden rounded-t-2xl
         transition-transform duration-300 ease-out"
  style="
    background: var(--g-paper-deep);
    border-top: 1px solid var(--g-rule-soft);
    padding-bottom: env(safe-area-inset-bottom);
    transform: {sheetTrip !== null ? 'translateY(0)' : 'translateY(100%)'};
  "
  role="dialog"
  aria-modal="true"
  aria-label="Aktionen"
>
  <!-- Handle-Bar -->
  <div class="flex justify-center pt-3 pb-1">
    <div class="w-10 h-1 rounded-full bg-[var(--g-rule-soft)]"></div>
  </div>

  <!-- Sheet-Titel -->
  <div class="px-4 py-2 font-semibold text-[var(--g-ink)]">
    {sheetTrip?.name ?? ''}
  </div>

  <!-- Aktionen -->
  {#each [
    { label: 'Report-Konfiguration', icon: BellIcon,    action: (t) => { openReportConfig(t); sheetTrip = null; } },
    { label: 'Wetter-Konfiguration', icon: CloudSunIcon, action: (t) => { weatherConfigTarget = t; sheetTrip = null; } },
    { label: 'Bearbeiten',           icon: PencilIcon,   action: (t) => { openEdit(t); sheetTrip = null; } },
    { label: 'Test Morgen-Report',   icon: PlayIcon,     action: (t) => { runTestReport(t, 7); sheetTrip = null; } },
    { label: 'Test Abend-Report',    icon: PlayIcon,     action: (t) => { runTestReport(t, 18); sheetTrip = null; } },
    { label: 'Löschen',             icon: Trash2Icon,   action: (t) => { deleteTarget = t; sheetTrip = null; }, destructive: true },
  ] as item}
    <button
      class="w-full flex items-center gap-3 px-4 min-h-[44px]
             {item.destructive ? 'text-[var(--g-wx-thunder)]' : 'text-[var(--g-ink)]'}"
      onclick={() => sheetTrip && item.action(sheetTrip)}
    >
      <svelte:component this={item.icon} size={20} />
      <span>{item.label}</span>
    </button>
  {/each}

  <div class="h-4"></div>
</div>
```

### 7. Z-Index-Hierarchie

| Element | z-index |
|---------|---------|
| BottomNav (Issue #267) | z-50 |
| TopAppBar (Issue #267) | z-[60] |
| Bottom-Sheet Backdrop | z-[70] |
| Bottom-Sheet Panel | z-[75] |

Das Sheet liegt oberhalb der App-Shell-Elemente aus Issue #267, sodass es diese vollständig überdeckt.

## Expected Behavior

- **Input:** Liste der Trips via SvelteKit `$page.data.trips` (unverändert, wie Desktop)
- **Output (visuell):**
  - Viewport ≤ 899px: Vertikal gestapelte Cards (eine pro Trip), Desktop-Tabelle nicht sichtbar
  - Viewport ≥ 900px: Desktop-Tabelle wie bisher, Card-Stack nicht sichtbar, Bottom-Sheet nicht sichtbar
- **Side effects:**
  - `sheetTrip = trip` öffnet das Bottom-Sheet für den gewählten Trip
  - `sheetTrip = null` schließt das Bottom-Sheet (via Backdrop-Klick, Aktions-Ausführung oder programmatisch)
  - Aktionen im Sheet rufen dieselben Handler auf wie die Desktop-Tabellen-Icons — kein Verhalten-Unterschied

## Acceptance Criteria

**AC-1:** Given ein Viewport kleiner oder gleich 899px / When die Route `/trips` mit mindestens einem Trip geöffnet wird / Then ist ein Card-Stack mit einer Card pro Trip sichtbar, jede Card zeigt einen farbigen Status-Dot links, den Trip-Namen, Etappen-Anzahl und Zeitraum — und die HTML-Tabelle ist nicht sichtbar.

**AC-2:** Given die Trips-Liste auf Mobile (≤ 899px) / When der Nutzer auf den `···`-Button einer Trip-Card tippt / Then öffnet sich ein Bottom-Sheet mit einem halbtransparenten Backdrop, das den Sheet-Titel (Trip-Name) und genau 6 Aktionen zeigt: Report-Konfiguration, Wetter-Konfiguration, Bearbeiten, Test Morgen-Report, Test Abend-Report, Löschen.

**AC-3:** Given das Bottom-Sheet ist geöffnet / When der Nutzer außerhalb des Sheets auf den Backdrop tippt / Then schließt sich das Bottom-Sheet, `sheetTrip` wird auf `null` gesetzt, und alle Dialoge bleiben geschlossen.

**AC-4:** Given die Trips-Liste auf Mobile (≤ 899px) / When der Nutzer auf den mittleren Inhalts-Block einer Trip-Card (Name + Metadaten) tippt / Then navigiert die App zur Trip-Detail-Route `/trips/{id}` für genau diesen Trip.

**AC-5:** Given das Bottom-Sheet ist sichtbar / When der Nutzer auf "Löschen" tippt / Then wird `deleteTarget` auf den jeweiligen Trip gesetzt, das Bottom-Sheet schließt sich (`sheetTrip = null`), und der bestehende Lösch-Bestätigungs-Dialog öffnet sich — identisches Verhalten wie der Löschen-Icon in der Desktop-Tabelle.

**AC-6:** Given ein Viewport größer oder gleich 900px / When die Route `/trips` geöffnet wird / Then ist die bestehende Desktop-Tabelle mit allen Aktions-Icons vollständig sichtbar und unverändert; Card-Stack und Bottom-Sheet sind nicht sichtbar.

**AC-7:** Given die Trips-Liste auf Mobile (≤ 899px) / When der `···`-Button gemessen wird / Then hat der Button eine Mindestgröße von 44×44px (Touch-Target-Minimum gemäß WCAG 2.5.5).

## Known Limitations

- **`dateRange(trip)` muss vorhanden sein:** Die Funktion wird im Card-Stack wiederverwendet und muss bereits im File deklariert sein — sie wird nicht neu eingeführt. Falls der Name im File abweicht, muss der Aufruf angepasst werden.
- **`deriveTripStatus` mit fester `now`-Zeit:** `now` wird einmalig beim Komponenten-Mount gesetzt. Bei sehr langen Sessions ohne Page-Reload kann der Status-Dot veralten — akzeptables Verhalten für diesen Use-Case.
- **Bottom-Sheet immer im DOM:** Das Panel ist immer gerendert (nur per `translateY` ausgeblendet), damit die CSS-Transition funktioniert. Screenreader erhalten `aria-modal="true"` nur wenn `sheetTrip !== null`, andernfalls ist das Panel per `transform` außerhalb des sichtbaren Bereichs.
- **`svelte:component` für Icon-Iteration:** Die Aktions-Liste im Sheet nutzt `{#each}` mit `svelte:component` — falls das Projekt auf Svelte 5 vollständig migriert ist, muss stattdessen das native Snippet-Pattern oder dynamisches Binding verwendet werden.

## Affected Files

| Datei | Änderung |
|-------|---------|
| `frontend/src/routes/trips/+page.svelte` | Neue Imports (`EllipsisVerticalIcon`, `Dot`, `deriveTripStatus`, `goto`), neuer State (`sheetTrip`), `statusTone()`-Funktion, Desktop-Wrapper `hidden desktop:block`, Card-Stack-Block `desktop:hidden`, Bottom-Sheet mit Backdrop |

## Changelog

- 2026-05-20: Initial spec erstellt (Issue #268 — Mobile Card-Stack für Trips-Liste + Bottom-Sheet für Aktionen).

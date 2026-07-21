---
entity_id: issue_488_compare_tile_atoms
type: module
created: 2026-05-31
updated: 2026-05-31
status: draft
version: "1.0"
issue: 488
tags: [sveltekit, frontend, compare, molecules, atoms, epic-485, bits-ui, svelte5]
---

# Issue #488 — Orts-Vergleich Kachel-Atome (Block A)

## Approval

- [ ] Approved

## Purpose

Definiert die drei Molecule-Komponenten `CompareTile`, `CompareStatusPill` und `CompareKebab`
sowie die zugehörige `compareActions`-Hilfsfunktion und Index-Re-Exporte, die zusammen Block A
des Epic #485 (Orts-Vergleich Kachel-Grid) bilden. Diese Komponenten sind die atomaren Bausteine
des Vergleichs-Dashboards: `CompareTile` stellt eine vollständige Kachel für einen
`ComparePreset` dar (Name, Status, Aktionsmenü, Layout-Varianten), `CompareStatusPill` zeigt
den Vergleichs-Status als visuelles Badge, und `CompareKebab` liefert ein bits-ui-basiertes
Kontextmenü mit statusabhängigen Aktionen. Alle drei Downstream-Issues (#485-B CompareGrid,
#485-C CompareDetail, #485-D Home-Umbau) sind ohne diesen Block blockiert.

## Source

- **Neue Dateien:**
  - `frontend/src/lib/components/compare/CompareTile.svelte` — Molecule, Kachel-Hauptkomponente
  - `frontend/src/lib/components/compare/CompareStatusPill.svelte` — Molecule, Status-Badge
  - `frontend/src/lib/components/compare/CompareKebab.svelte` — Molecule, Kebab-Kontextmenü
- **Geänderte Dateien:**
  - `frontend/src/lib/components/compare/subscriptionHelpers.ts` — `compareActions(status)` + `CompareAction`-Typ
  - `frontend/src/lib/components/molecules/index.ts` — 3 neue Re-Exporte
- **Test-Datei (NEU):**
  - `frontend/src/lib/components/compare/__tests__/issue_488_compare_tile_atoms.test.ts`
- **Identifier:** `CompareTile`, `CompareStatusPill`, `CompareKebab` (default exports); `compareActions`, `CompareAction` (named exports)

## Not In Scope

- `CompareGrid`-Layout und Grid-Seite `/compare` (Block B, Folge-Issue)
- `CompareDetail`-Panel (Block C, Folge-Issue)
- Home-Umbau (Block D, Folge-Issue)
- Backend-Endpunkte für Vergleichs-Aktionen (senden, pausieren, löschen) — Kebab emittiert
  nur `onSelect(id)`, die Elternkomponente ist für API-Calls zuständig
- Animation und Transition-Effekte auf der Kachel

## Estimated Scope

- **LoC:** ~160 Produktionscode + ~110 Tests = ~270 gesamt
- **Files:** 5 Produktions-Dateien (3 neu, 2 erweitert) + 1 Test-Datei
- **Effort:** medium
- **LoC-Override:** 350

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `ComparePreset` (`frontend/src/lib/types.ts`) | TypeScript-Typ | Props-Typ für `CompareTile`; enthält Name, ID, Status und Kanal-Konfiguration |
| `CompareStatus` (`frontend/src/lib/types.ts`) | TypeScript-Union | Status-Typ für `CompareStatusPill` und `CompareKebab` (`'active' \| 'paused' \| 'draft'`) |
| `STATUS_MAP` (`subscriptionHelpers.ts`) | Map/Objekt | Liefert deutschsprachige Status-Labels für `CompareStatusPill` |
| `deriveStatusFromPreset` (`subscriptionHelpers.ts`) | Funktion | Leitet `CompareStatus` aus `ComparePreset` ab; wird in `CompareTile` via `$derived` genutzt |
| `Pill` (`$lib/components/atoms/Pill.svelte` o.ä.) | Atom-Komponente | Basis-Rendering für `CompareStatusPill`-Varianten (tone="success" vs. Outline) |
| `bits-ui` v2.17.3 (`DropdownMenu`) | externe Bibliothek | Barrierefreies, Portal-basiertes Dropdown für `CompareKebab` |
| `@lucide/svelte` (`EllipsisVerticalIcon`) | Icon-Bibliothek | Kebab-Trigger-Icon in `CompareKebab` |
| `frontend/src/app.css` | Design-Tokens | `--g-accent`, `--g-ink-3`, `--g-shadow-2` für Hover- und Accent-Styles auf `CompareTile` |

## Implementation Details

### 1. `compareActions` + `CompareAction` (subscriptionHelpers.ts)

Neuer Typ und neue Funktion werden am Ende der Datei hinzugefügt — kein bestehendes Symbol verändern:

```typescript
export type CompareAction = { id: string; label: string; danger?: boolean };

export function compareActions(status: CompareStatus): CompareAction[] {
  if (status === 'draft') {
    return [
      { id: 'setup',  label: 'Setup fortsetzen' },
      { id: 'delete', label: 'Löschen', danger: true }
    ];
  }
  // 'active' und 'paused' liefern dieselbe 5-Element-Liste
  return [
    { id: 'pause',   label: 'Pausieren' },
    { id: 'send',    label: 'Briefing jetzt senden' },
    { id: 'preview', label: 'Vorschau öffnen' },
    { id: 'edit',    label: 'Bearbeiten' },
    { id: 'delete',  label: 'Löschen', danger: true }
  ];
}
```

### 2. `CompareStatusPill.svelte`

Props:
```typescript
interface Props { status: CompareStatus; class?: string; }
```

Render-Logik:
- `status === 'active'` → Filled-Variante: grüngefülltes Badge, `tone="success"` via `Pill`-Atom
  oder direktes CSS `background: var(--g-success); color: #fff`
- `status === 'paused'` oder `'draft'` → Outline-Variante: `border: 1px solid currentColor`,
  transparenter Hintergrund, Farbe aus `--g-ink-3`
- Label-Text aus `STATUS_MAP[status]` (vorhanden in `subscriptionHelpers.ts`)

### 3. `CompareTile.svelte`

Props:
```typescript
interface Props {
  sub: ComparePreset;
  dense?: boolean;    // Mobile-Spacing: reduziertes Padding/Gap
  compact?: boolean;  // Home-Kachel: ohne Kanal-Pills
  accent?: boolean;   // Aktive Kachel: border-left-Hervorhebung
  onclick?: () => void;
  class?: string;
}
```

Aufbau des Wurzelelements:
```svelte
<div
  class="compare-tile {compact ? 'compact' : ''} {dense ? 'dense' : ''} {$$props.class ?? ''}"
  style:border-left={accent ? '3px solid var(--g-accent)' : undefined}
  role="button"
  tabindex={onclick ? 0 : undefined}
  {onclick}
>
  ...
</div>
```

Hover-Styles (CSS auf `.compare-tile:hover`):
```css
.compare-tile:hover {
  border-color: var(--g-ink-3);
  box-shadow: var(--g-shadow-2);
}
```

Interne Struktur:
1. Header-Zeile: Name (`<h3>`) + `CompareKebab` (rechts ausgerichtet, `onclick` auf Kebab muss
   `e.stopPropagation()` aufrufen damit Kachel-Klick nicht ausgelöst wird)
2. `CompareStatusPill` mit abgeleitetem Status
3. Kanal-Pills (nur wenn `!compact`): z.B. E-Mail, SMS — aus `sub`-Daten ablesen
4. Svelte-5-Reaktivität: `const status = $derived(deriveStatusFromPreset(sub))`

### 4. `CompareKebab.svelte`

Props:
```typescript
interface Props {
  status: CompareStatus;
  onSelect?: (id: string) => void;
}
```

Vollständiges bits-ui-v2-Trigger-Pattern (PFLICHT — abweichendes Pattern bricht Portal):
```svelte
<script lang="ts">
  import { DropdownMenu } from 'bits-ui';
  import EllipsisVerticalIcon from '@lucide/svelte/icons/ellipsis-vertical';
  import { compareActions } from './subscriptionHelpers.js';
  import type { CompareStatus } from '$lib/types.js';

  let { status, onSelect }: Props = $props();
  const actions = $derived(compareActions(status));
</script>

<DropdownMenu.Root>
  <DropdownMenu.Trigger>
    {#snippet child({ props })}
      <button {...props} onclick={(e) => { e.stopPropagation(); }}>
        <EllipsisVerticalIcon size={16} />
      </button>
    {/snippet}
  </DropdownMenu.Trigger>

  <DropdownMenu.Content
    align="end"
    sideOffset={4}
    class="z-50 min-w-[180px] rounded-md border bg-popover shadow-md py-1"
  >
    {#each actions as action}
      <DropdownMenu.Item
        class={action.danger ? 'text-destructive' : ''}
        onclick={() => onSelect?.(action.id)}
      >
        {action.label}
      </DropdownMenu.Item>
    {/each}
  </DropdownMenu.Content>
</DropdownMenu.Root>
```

### 5. `molecules/index.ts` — Re-Exporte

Am Ende der Datei drei Zeilen hinzufügen (Cross-Verzeichnis-Re-Exporte, bestehende Zeilen unberührt):
```typescript
export { default as CompareTile }       from '../compare/CompareTile.svelte';
export { default as CompareStatusPill } from '../compare/CompareStatusPill.svelte';
export { default as CompareKebab }      from '../compare/CompareKebab.svelte';
```

### 6. Tests (`issue_488_compare_tile_atoms.test.ts`)

Tests mit `node:test` + `node:assert/strict` + `readFileSync` (Source-Inspection). Kein DOM-Rendering, keine Mocks. Für `compareActions` direkter Funktionsaufruf-Test (Import aus `subscriptionHelpers.ts`).

Zu testende Szenarien:
- `compareActions('active')` → 5 Einträge, letzter ist `danger: true`
- `compareActions('paused')` → identisch 5 Einträge wie `active`
- `compareActions('draft')` → 2 Einträge (`setup`, `delete`), `delete.danger === true`
- `CompareStatusPill` mit `status='active'` → rendered Element enthält Filled-Klasse/Style
- `CompareStatusPill` mit `status='paused'` → rendered Element enthält Outline-Klasse/Style
- `CompareTile` mit `accent=true` → Wurzelelement hat `border-left`-Style mit `--g-accent`
- `CompareTile` mit `compact=true` → Kanal-Pills fehlen im DOM
- `CompareTile` mit `dense=true` → Klasse `dense` auf Wurzelelement
- `CompareKebab` Source-Check → enthält `stopPropagation` im Trigger-Bereich
- Build-Check: `cd frontend && npm run build` ohne Fehler (wird in AC-5 als Build-Check geführt,
  nicht als Unit-Test)

## Expected Behavior

- **Input:** Ein `ComparePreset`-Objekt (mit `id`, `name`, Status-Feldern) wird an `CompareTile`
  übergeben.
- **Output:**
  - `CompareTile` rendert eine Card-ähnliche Kachel mit Name, Status-Badge, optionalen Kanal-Pills
    und einem Kebab-Menü rechts oben.
  - `accent=true` setzt `border-left: 3px solid var(--g-accent)` direkt auf das Wurzelelement.
  - `dense=true` reduziert Padding/Gap (Mobile-Layout-Variante).
  - `compact=true` unterdrückt die Kanal-Pills (Home-Kachel-Variante).
  - `CompareStatusPill` zeigt grüngefülltes Badge für `active`, Outline-Badge für `paused`/`draft`.
  - `CompareKebab` öffnet ein bits-ui-Portal-Dropdown mit statusabhängigen Aktionen; `onSelect`
    wird mit der Aktions-ID aufgerufen; Klick auf den Trigger stoppt Propagation zur Kachel.
- **Side effects:**
  - Kein API-Call aus den Komponenten selbst — alle Aktionen werden via `onSelect`/`onclick`
    nach oben delegiert.
  - Die drei Komponenten sind via `molecules/index.ts` öffentlich re-exportiert und für alle
    Downstream-Blöcke (#485-B/C/D) importierbar.

## Acceptance Criteria

**AC-1:** Given eine `CompareTile`-Instanz mit `accent=true` / When der Svelte-Source geprüft wird / Then enthält das Wurzelelement `border-left: 3px solid var(--g-accent)` und die Props `dense` und `compact` sind vorhanden und steuern Layout-Varianten.

**AC-2:** Given `CompareStatusPill` / When der Svelte-Source geprüft wird / Then ist `status: CompareStatus` als Prop typisiert, und der Source enthält sowohl eine Filled-Variante (aktiv/grün) als auch eine Outline-Variante (pausiert/draft).

**AC-3:** Given `CompareKebab` / When der Svelte-Source geprüft wird / Then enthält der Source `stopPropagation` im Trigger-Bereich und importiert `DropdownMenu` aus bits-ui sowie ein Ellipsis-Icon.

**AC-4:** Given `compareActions("active")` aufgerufen / When das Ergebnis geprüft wird / Then enthält die Liste genau 5 Einträge (pause, send, preview, edit, delete). Given `compareActions("draft")` / Then enthält die Liste genau 2 Einträge (setup, delete).

**AC-5:** Given alle 3 Komponenten + Helper + Index-Ergänzung implementiert / When `cd frontend && npm run build` ausgeführt wird / Then läuft der Build ohne TypeScript- oder Svelte-Fehler durch.

## Known Limitations

- `CompareKebab` emittiert nur `onSelect(id)` — die Elternkomponente (Block B/C) ist vollständig
  für API-Calls und Fehlerbehandlung zuständig. Kein Ladezustand im Kebab.
- `CompareTile` nutzt kein benutzerdefiniertes Dialog-Muster für destruktive Aktionen (Löschen);
  die Elternkomponente entscheidet über Confirm-Dialog.
- Hover-Styles sind rein CSS-basiert; bei SSR/Hydration-Mismatch kann ein kurzes Flackern
  auftreten (akzeptiert, kein Blocker).
- Cross-Verzeichnis-Re-Exporte in `molecules/index.ts` sind eine Ausnahme vom Muster; sie sind
  bewusst gewählt um die öffentliche API der Molecule-Schicht konsistent zu halten.

## Verweise

- **Epic:** #485 — Orts-Vergleich Kachel-Grid
- **Issue:** [#488 — Compare Tile Atoms (Block A)](https://github.com/henemm/gregor_zwanzig/issues/488)
- **Abhängige Issues (blockiert):** #485-B (CompareGrid), #485-C (CompareDetail), #485-D (Home-Umbau)
- **Referenz bits-ui v2 Trigger-Pattern:** `frontend/src/lib/components/trips/TripKebab.svelte`
- **Referenz ComparePreset/CompareStatus:** `frontend/src/lib/types.ts`
- **Referenz subscriptionHelpers:** `frontend/src/lib/components/compare/subscriptionHelpers.ts`
- **Design-System:** `docs/design-system/` (Tokens, Atoms, Screens)

## Changelog

- 2026-05-31: Initiale Spec erstellt — CompareTile (accent/dense/compact-Varianten), CompareStatusPill
  (filled/outline), CompareKebab (bits-ui v2 Portal-Pattern + stopPropagation), compareActions-Helper
  (draft=2, active/paused=5), molecules/index.ts-Re-Exporte, 5 Acceptance Criteria im AC-N
  Given/When/Then-Format, LoC-Override 350.

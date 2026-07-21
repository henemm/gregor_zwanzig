---
entity_id: issue_453_locations_rail_hauptbuehne
type: module
created: 2026-05-29
updated: 2026-05-29
status: draft
version: "1.0"
issue: 453
tags: [sveltekit, frontend, compare, locations, rail, drag-and-drop, epic-438]
---

# Issue #453 — Locations-Rail Erweiterungen fuer die Compare-Hauptbuehne

## Approval

- [ ] Approved

## Status

**Draft** — bereit zur Freigabe durch User.

## Purpose

Erweitert `LocationsRail.svelte` (aus Issue #249 implementiert, bisher auf keiner Produktionsseite
eingebunden) um vier Faehigkeiten, die fuer den Einsatz auf der Compare-Hauptbuehne benoetigt
werden: Breitenreduktion auf 240px, einen Constraint-Zaehler der dem User Feedback zu Min/Max-
Orte-Grenzen gibt, einen Leerzustand wenn noch keine Locations vorhanden sind, und HTML5-Drag-
Reihenfolge-Aenderung zwischen Location-Items. Die Komponente bleibt Props-driven — sie haelt
keinen eigenen API-State und interagiert mit der Hauptbuehne ausschliesslich ueber Callbacks.

## Source

- **Dateien (EDIT):**
  - `frontend/src/lib/components/compare/LocationsRail.svelte` — Breite, Zaehler, EmptyState, DnD-State + Callback
  - `frontend/src/lib/components/compare/GroupSection.svelte` — neue DnD-Props auf `<li>`-Elementen
- **Datei (NEU):**
  - `frontend/src/lib/components/compare/__tests__/issue_453_locations_rail.test.ts` — Source-Inspection-Tests (node:test)
- **Identifier:** `LocationsRail` (default export), `GroupSection` (default export)

## Not In Scope

- Einbindung der Rail in die Compare-Hauptbuehne (eigene Route/Page, Folge-Issue in Epic #438)
- Persistierung der neu geordneten Reihenfolge im Backend (kein API-Aufruf in dieser Rail; Consumer-Verantwortung via `onReorder`-Callback)
- Animations- oder Drag-Overlay (kein Ghost-Element, kein CSS-Transition bei Reorder)
- Mobile-Anpassungen ueber Standard-Wrapper hinaus

## Scope

- **LoC-Schaetzung:** ~120 LoC, 3 Dateien
  - `LocationsRail.svelte`: +35 LoC
  - `GroupSection.svelte`: +15 LoC
  - `issue_453_locations_rail.test.ts`: +70 LoC (neu)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/src/lib/components/compare/LocationsRail.svelte` | component (edit, aus #249) | Basis-Komponente — Suche, Chip-Filter, Multi-Select, Gruppen-Toggle; wird erweitert |
| `frontend/src/lib/components/compare/GroupSection.svelte` | component (edit) | Rendert Gruppen-Bloecke mit `<li>`-Items; erhaelt neue DnD-Props |
| `$lib/components/ui/empty-state/index.js` (`EmptyState`) | component | Onboarding-Hinweis wenn `locations.length === 0`; CTA ruft `onNewLocation` auf |
| `frontend/src/app.css` | file | Design-Tokens `--g-danger`, `--g-success`, `--g-ink-muted` fuer Zaehler-Faerbung |
| Issue #249 | spec (approved) | Definiert bestehende Props, State und Render-Logik von `LocationsRail.svelte` |
| Issue #451 | issue | Voraussetzung: Compare-Hauptbuehnen-Route muss `onReorder`-Callback konsumieren koennen |

## Implementation Details

### 1. Breite 240px (LocationsRail.svelte)

Der bestehende Inline-Style bzw. CSS-Wert `width: 320px` wird direkt auf `240px` geaendert.
Kein neuer Prop — die Breite ist laut Architekturentscheidung fix fuer diesen Einsatzort.

```svelte
<!-- vorher -->
<aside style="width: 320px; ...">

<!-- nachher -->
<aside style="width: 240px; ...">
```

Sicherstellung per Test: `assert.doesNotMatch(src, /width:\s*320px/)`.

### 2. Neuer `onReorder`-Prop (LocationsRail.svelte)

```typescript
interface Props {
    // ... bestehende Props aus #249 unveraendert ...
    onReorder?: (sourceId: string, targetId: string) => void;  // NEU — optional
}
```

Interner Drag-State (lokaler `$state` in LocationsRail):

```typescript
let dragSourceId = $state<string | null>(null);
```

### 3. Neue DnD-Props in GroupSection.svelte

```typescript
interface GroupSectionProps {
    // ... bestehende Props unveraendert ...
    onDragStart?: (id: string) => void;   // NEU
    onDrop?: (targetId: string) => void;  // NEU
}
```

Auf jedem `<li>`-Element innerhalb von GroupSection:

```svelte
<li
    draggable="true"
    ondragstart={() => onDragStart?.(location.id)}
    ondragover={(e) => e.preventDefault()}
    ondrop={() => onDrop?.(location.id)}
>
```

### 4. DnD-Verkabelung in LocationsRail.svelte

LocationsRail uebergibt die Callbacks an GroupSection und behandelt ungrouped Items direkt:

```svelte
<GroupSection
    ...
    onDragStart={(id) => (dragSourceId = id)}
    onDrop={(targetId) => {
        if (dragSourceId && dragSourceId !== targetId) {
            onReorder?.(dragSourceId, targetId);
        }
        dragSourceId = null;
    }}
/>
```

Ungrouped Items in LocationsRail erhalten dieselben `ondragstart`/`ondragover`/`ondrop`-Attribute
direkt auf dem `<li>`.

### 5. Constraint-Zaehler (LocationsRail.svelte)

Position: direkt unter dem Suchfeld, ueber der Chip-Zeile.
TestID: `data-testid="compare-rail-counter"`.

```svelte
<p data-testid="compare-rail-counter" class={counterClass}>
    {locations.length} Orte · min. 2 / max. 8
</p>
```

Faerbungslogik via `$derived`:

```typescript
let counterClass = $derived(
    locations.length < 2
        ? 'text-[var(--g-danger)]'
        : locations.length <= 8
            ? 'text-[var(--g-success)]'
            : 'text-[var(--g-ink-muted)]'
);
```

Farbregeln im Detail:

| Anzahl Locations | CSS-Token | Semantik |
|-----------------|-----------|----------|
| < 2 | `--g-danger` | Mindestanzahl nicht erfuellt |
| 2–8 | `--g-success` | Gueltiger Bereich |
| > 8 | `--g-ink-muted` | Obergrenze ueberschritten (kein Hard-Block) |

### 6. Leerzustand EmptyState (LocationsRail.svelte)

Wenn `locations.length === 0` wird statt der Liste die `EmptyState`-Komponente gerendert.
TestID des Wrappers: `data-testid="compare-rail-empty"`.

```svelte
{#if locations.length === 0}
    <div data-testid="compare-rail-empty">
        <EmptyState
            title="Noch keine Orte"
            description="Lege deinen ersten Ort an, um einen Vergleich zu starten."
            ctaLabel="Ersten Ort anlegen"
            onCta={onNewLocation}
        />
    </div>
{:else}
    <!-- bestehende Listen-Render-Logik aus #249 -->
{/if}
```

Import oben in der Komponente:

```typescript
import { EmptyState } from '$lib/components/ui/empty-state/index.js';
```

### 7. Test-Datei (issue_453_locations_rail.test.ts)

Alle Tests arbeiten als Source-Inspection (kein DOM-Rendering, kein JSDOM). Laufzeit: `node:test`.

```typescript
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

const RAIL  = resolve('src/lib/components/compare/LocationsRail.svelte');
const GROUP = resolve('src/lib/components/compare/GroupSection.svelte');

// AC-1 (indirekt — Gruppen-Render aus #249 bleibt unveraendert; Smoke-Check)
test('LocationsRail importiert GroupSection', () => {
    const src = readFileSync(RAIL, 'utf-8');
    assert.match(src, /GroupSection/);
});

// Breite
test('Breite ist 240px und nicht mehr 320px', () => {
    const src = readFileSync(RAIL, 'utf-8');
    assert.match(src, /240px/);
    assert.doesNotMatch(src, /width:\s*320px/);
});

// Constraint-Zaehler TestID
test('Constraint-Zaehler hat testid compare-rail-counter', () => {
    const src = readFileSync(RAIL, 'utf-8');
    assert.match(src, /compare-rail-counter/);
});

// Zaehler-Faerbung: alle drei Tokens vorhanden
test('Zaehler-Faerbung referenziert alle drei Design-Tokens', () => {
    const src = readFileSync(RAIL, 'utf-8');
    assert.match(src, /--g-danger/);
    assert.match(src, /--g-success/);
    assert.match(src, /--g-ink-muted/);
});

// EmptyState
test('EmptyState-Import vorhanden', () => {
    const src = readFileSync(RAIL, 'utf-8');
    assert.match(src, /empty-state/);
});

test('EmptyState-Wrapper hat testid compare-rail-empty', () => {
    const src = readFileSync(RAIL, 'utf-8');
    assert.match(src, /compare-rail-empty/);
});

// Drag — onReorder Prop
test('LocationsRail deklariert onReorder-Prop', () => {
    const src = readFileSync(RAIL, 'utf-8');
    assert.match(src, /onReorder/);
});

test('LocationsRail haelt dragSourceId-State', () => {
    const src = readFileSync(RAIL, 'utf-8');
    assert.match(src, /dragSourceId/);
});

// Drag — GroupSection Props
test('GroupSection deklariert onDragStart-Prop', () => {
    const src = readFileSync(GROUP, 'utf-8');
    assert.match(src, /onDragStart/);
});

test('GroupSection deklariert onDrop-Prop', () => {
    const src = readFileSync(GROUP, 'utf-8');
    assert.match(src, /onDrop/);
});

test('GroupSection setzt draggable="true" auf li-Elementen', () => {
    const src = readFileSync(GROUP, 'utf-8');
    assert.match(src, /draggable/);
});
```

## Expected Behavior

- **Input:** `locations: Location[]` (alle Locations des Users); bestehende Props aus #249 unveraendert; neu: `onReorder?: (sourceId, targetId) => void`
- **Output:**
  - Rail ist 240px breit
  - Zaehler unter Suchfeld zeigt `{N} Orte · min. 2 / max. 8` in der kontextabhaengigen Farbe
  - Bei 0 Locations: `EmptyState` mit CTA "Ersten Ort anlegen" (ruft `onNewLocation` auf)
  - Drag-Interaktion auf jedem Location-Item: `dragstart` → `dragover` → `drop` ruft `onReorder(sourceId, targetId)` auf; keine visuelle Reorder-Animation in der Komponente selbst
- **Side effects:** Keine eigenen API-Aufrufe; `onReorder`-Callback liegt in der Verantwortung des Consumers (Compare-Hauptbuehne)

## Acceptance Criteria

- **AC-1:** Given gespeicherte Locations mit Gruppenzuordnung / When die Rail gerendert wird / Then erscheinen alle Locations gruppiert mit Gruppen-Headern, Expand/Collapse und Einzel-Checkboxen (unveraendert aus #249).
  - Test: (populated after /tdd-red)

- **AC-2:** Given mehrere Locations vorhanden / When einzelne Locations per Checkbox angeklickt werden / Then aendert sich `selectedIds` entsprechend (Multi-Select unveraendert aus #249).
  - Test: (populated after /tdd-red)

- **AC-3:** Given Text im Suchfeld eingegeben / When User tippt / Then werden nur Locations angezeigt deren Name oder Gruppenname den Text enthaelt (Gross/Kleinschreibung ignoriert, unveraendert aus #249).
  - Test: (populated after /tdd-red)

- **AC-4:** Given User klickt den NEU-Button / When Button angeklickt / Then wird `onNewLocation`-Callback aufgerufen (unveraendert aus #249).
  - Test: (populated after /tdd-red)

- **AC-5:** Given `locations.length === 0` / When Rail gerendert wird / Then ist `data-testid="compare-rail-empty"` im DOM sichtbar und enthaelt einen CTA mit dem Text "Ersten Ort anlegen"; die normale Locations-Liste und der Zaehler sind nicht sichtbar.
  - Test: (populated after /tdd-red)

- **AC-Breite:** Given Rail gerendert / When CSS geprueft / Then ist `width: 240px` gesetzt und `width: 320px` nicht vorhanden.
  - Test: Source-Inspection (`assert.match(src, /240px/)` + `assert.doesNotMatch`)

- **AC-Zaehler-Farben:** Given 3 Locations (Bereich 2–8) / When Zaehler-Element geprueft / Then hat Zaehler-Text die Farbe `--g-success`.
  - Test: (populated after /tdd-red)

- **AC-Zaehler-Farben-Danger:** Given 1 Location (unter Minimum) / When Zaehler-Element geprueft / Then hat Zaehler-Text die Farbe `--g-danger`.
  - Test: (populated after /tdd-red)

- **AC-Zaehler-Farben-Muted:** Given 9 Locations (ueber Maximum) / When Zaehler-Element geprueft / Then hat Zaehler-Text die Farbe `--g-ink-muted`.
  - Test: (populated after /tdd-red)

- **AC-DnD:** Given User zieht Location-Item A auf Location-Item B / When Drop-Event ausgeloest / Then wird `onReorder('id-a', 'id-b')` aufgerufen; bei Drop auf dasselbe Item kein Callback.
  - Test: (populated after /tdd-red)

## Known Limitations

- `onReorder` ist optional und hat keinen Consumer in diesem Issue — die Reihenfolge-Aenderung wird erst mit der Compare-Hauptbuehnen-Einbindung (Folge-Issue #451 oder Folgewerk) persistiert.
- Kein visuelles Drag-Feedback (kein Ghost-Element, keine Highlight-Farbe auf Drop-Ziel). Ausbau bei Bedarf in separatem Issue.
- Der Zaehler ist informativ — er blockiert keine Interaktion bei >8 Locations (kein Hard-Block per Architekturentscheidung).
- `EmptyState`-Komponente wird mit unveraenderten Props aus `$lib/components/ui/empty-state/index.js` eingebunden — falls die Komponente andere Prop-Namen erwartet, muss vor Implementierung ein `grep`-Check gegen die Quelldatei erfolgen.

## Verweise

- **Epic:** #438 — Orts-Vergleich
- **Issue:** [#453 — Locations-Rail Hauptbuehne](https://github.com/henemm/gregor_zwanzig/issues/453)
- **Vorgaenger-Spec:** `docs/specs/modules/issue_249_locations_rail.md` (bestehende Rail-Implementierung)
- **Stil-Referenz Spec:** `docs/specs/modules/issue_440_compare_wizard_shell_step1_step2.md`
- **Design-System:** `docs/design-system/` (Tokens, Atoms, Screens)

## Changelog

- 2026-05-29: Initiale Spec erstellt — Breite 240px, Constraint-Zaehler mit 3-Farb-Logik,
  EmptyState-Leerzustand mit Onboarding-CTA, HTML5-DnD via `onReorder`-Callback,
  Props-Erweiterung LocationsRail + GroupSection, 11 Acceptance Criteria im Given/When/Then-Format,
  Source-Inspection-Testdatei mit 11 Tests, LoC-Schaetzung 120 / 3 Dateien.

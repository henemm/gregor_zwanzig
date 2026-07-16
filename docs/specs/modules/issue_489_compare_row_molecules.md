---
entity_id: issue_489_compare_row_molecules
type: module
created: 2026-05-31
updated: 2026-05-31
status: active
version: "1.0"
tags: [frontend, atomic-design, molecules, compare, issue-489, svelte5]
---

<!-- Issue #489 — Block A2 (Epic #485): 3 neue Molecule-Komponenten für Compare-Detail-Seite -->

# Issue #489 — CompareLocationRow, CompareIdealRow, CompareLayoutRow

## Approval

- [ ] Approved

## Purpose

Drei neue Svelte 5 Molecule-Komponenten liefern die Zeilen-Bausteine für die Compare-Detail-Seite (Block A2, Epic #485): `CompareLocationRow` stellt einen Standort mit Rang-Badge und Höhenangabe dar, `CompareIdealRow` zeigt eine Idealwert-Konfigurationszeile mit gewichtetem Pill, und `CompareLayoutRow` visualisiert die Ausgabe-Kanaleinstellung mit Spalten-Chips. Ohne diese Komponenten kann Issue #491 (CompareDetail-Seite) nicht implementiert werden.

## Source

- **File:** `frontend/src/lib/components/molecules/CompareLocationRow.svelte` (NEU)
- **File:** `frontend/src/lib/components/molecules/CompareIdealRow.svelte` (NEU)
- **File:** `frontend/src/lib/components/molecules/CompareLayoutRow.svelte` (NEU)
- **File:** `frontend/src/lib/components/molecules/index.ts` (ÄNDERUNG — 3 Re-Exporte am Ende)

> **Schicht-Hinweis:** Reine Frontend-Änderung (SvelteKit `frontend/src/lib/components/molecules/`). Keine Go/Python-Schicht betroffen.

## Estimated Scope

- **LoC:** ~90
- **Files:** 4
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `Pill` aus `$lib/components/atoms` | Atom (upstream) | Gewicht-Pill in `CompareIdealRow` (tone: accent/default/ghost) und Spalten-Chips in `CompareLayoutRow` |
| `Location` aus `$lib/types.js` | TypeScript-Typ | Typisierung des `loc`-Props in `CompareLocationRow` |
| `ChannelRow.svelte` | Molecules-Referenz | Muster für `dense`/`last`-Props und Divider-Logik |
| `DetailRow.svelte` | Molecules-Referenz | Muster für `1px solid var(--g-rule-soft)` Divider |
| `ThresholdRow.svelte` | Molecules-Referenz | Muster für mono-Label links, Wert rechts |
| `molecules/index.ts` | Barrel (ändern) | Erhält 3 neue Re-Export-Einträge am Ende der Datei |

## Implementation Details

### CompareLocationRow.svelte

Props (Svelte 5 `$props()`):

```typescript
let { loc, index, dense = false, alt = false }: {
  loc: Location;
  index: number;
  dense?: boolean;
  alt?: boolean;
} = $props();
```

Aufbau:
- Container `<div>` mit `background: alt ? 'var(--g-card-alt)' : 'transparent'`; Padding: Standard `12px 16px`, `dense=true` → `8px 16px`; `border-bottom: 1px solid var(--g-rule-soft)` immer
- Rang-Badge: nullpadded zweistellig (`String(index).padStart(2, '0')`), `font-family: var(--g-font-mono)`, `color: var(--g-accent)`
- Name: `color: var(--g-ink)`, normale Schrift
- Gruppe (`loc.group`): nur rendern wenn truthy, `color: var(--g-ink-3)`, kleiner
- Höhe: `${loc.elevation_m} m`, `color: var(--g-ink-3)`, mono

Layout: Flex-Row, Rang-Badge links (feste Breite ca. 2.5rem), Name + Gruppe mittig (flex: 1), Höhe rechts.

### CompareIdealRow.svelte

Props:

```typescript
let { item, dense = false, last = false }: {
  item: { metric: string; range: string; weight: 'hoch' | 'mittel' | 'niedrig' };
  dense?: boolean;
  last?: boolean;
} = $props();
```

Gewicht-Tone-Mapping via `$derived()`:

```typescript
const tone = $derived(
  item.weight === 'hoch' ? 'accent' : item.weight === 'mittel' ? 'default' : 'ghost'
);
```

Aufbau:
- Container `<div>`: Padding Standard `12px 16px`, `dense=true` → `8px 16px`; `border-bottom: 1px solid var(--g-rule-soft)` nur wenn `!last`
- Metrik-Label links: `font-family: var(--g-font-mono)`, `color: var(--g-ink-3)`
- Idealwert-Bereich mittig: `font-family: var(--g-font-mono)`, `color: var(--g-ink)`, flex: 1
- `<Pill {tone}>{item.weight}</Pill>` rechts

### CompareLayoutRow.svelte

Props:

```typescript
let { channel, cols, dense = false }: {
  channel: string;
  cols: string[];
  dense?: boolean;
} = $props();
```

SMS-Sonderfall via `$derived()`:

```typescript
const isSmsFlat = $derived(channel.toLowerCase() === 'sms' && cols.length === 0);
```

Aufbau:
- Container `<div>`: Padding Standard `12px 16px`, `dense=true` → stapelt Label und Chips vertikal (flex-direction: column), sonst flex-row
- Kopfzeile: fetter Kanal-Name (z.B. „Email", „Telegram", „SMS") über mono Constraint-Unterzeile (z.B. „alle Spalten", „max 8", „flach")
- Spalten-Chips rechts: für jeden Namen in `cols` ein `<Pill tone={idx === 0 ? 'accent' : 'default'}>{name}</Pill>`; bei `isSmsFlat` (Array leer) keine Chips rendern
- **Änderung (Issue #1267, 2026-07-16):** Prop-Typ `cols: number` → `cols: string[]` (echte Ortsnamen statt Zahlen); Kopfzeile umgestellt auf fetten Channel-Label + Constraint-Text; SMS-Bedingung auf Array-Länge prüfen (`cols.length === 0`)

### molecules/index.ts — Änderung

Am Ende der bestehenden Datei drei Zeilen anhängen:

```typescript
export { default as CompareLocationRow } from './CompareLocationRow.svelte';
export { default as CompareIdealRow } from './CompareIdealRow.svelte';
export { default as CompareLayoutRow } from './CompareLayoutRow.svelte';
```

### Nicht ändern

- Keine bestehenden Molecule-Komponenten berühren
- Keine Atom-Schicht ändern
- `Pill`-Props müssen dem vorhandenen API-Vertrag von `atoms/Pill.svelte` entsprechen — vor Implementierung `grep -n 'tone\|props' frontend/src/lib/components/atoms/Pill.svelte` prüfen

## Expected Behavior

- **Input:** Props gemäß den oben definierten TypeScript-Interfaces; kein externes State, keine API-Calls
- **Output:** Gerenderte HTML-Zeile mit korrekten CSS-Variablen, Divider, Rang-Badge, Pill oder Chips
- **Side effects:** Keine — alle drei Komponenten sind rein präsentational

## Acceptance Criteria

**AC-1:** Given `CompareLocationRow` mit `index=1`, `loc={name: "Chamonix", elevation_m: 1035}` / When gerendert / Then zeigt Rang-Badge „01" in mono+accent-Farbe, Name „Chamonix" und Höhe „1035 m"; kein Gruppen-Element im DOM (da `loc.group` nicht gesetzt).

**AC-2:** Given `CompareIdealRow` mit `item={metric: "Niederschlag", range: "0–3 mm", weight: "hoch"}` / When gerendert / Then zeigt das Gewicht-Pill mit `tone="accent"` und Text „hoch"; Metrik-Label in mono+muted, Idealwert in mono+ink.

**AC-3:** Given `CompareLayoutRow` mit `channel="sms", cols=0` / When gerendert / Then erscheint der Hint-Text „flach · ohne Spalten" neben dem Label, und es werden keine Spalten-Chips gerendert.

**AC-4:** Given alle 3 Komponenten in `molecules/index.ts` exportiert / When `cd frontend && npm run build` ausgeführt wird / Then schlägt kein Build-Schritt fehl und es gibt keine TypeScript-Fehler.

## Known Limitations

- `CompareLayoutRow` bildet aktuell nur den SMS-Sonderfall für `cols=0` ab; andere kanalspezifische Constraints (z.B. E-Mail-Maximalspalten) sind in dieser Iteration nicht implementiert
- Die Komponenten enthalten keine eigene Keyboard-Navigation oder ARIA-Rollen — das ist Aufgabe des umschließenden Containers in Issue #491

## Changelog

- 2026-05-31: Implemented & Adversary VERIFIED (CompareLocationRow, CompareIdealRow, CompareLayoutRow exported via molecules/index.ts)
- 2026-05-31: Initial spec created (Issue #489, Block A2 Epic #485 — Compare-Row-Molecules)

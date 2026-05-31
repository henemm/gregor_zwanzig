# Context: compare-row-atoms-485-a2

## Request Summary
Issue #489 (Block A2 von Epic #485): 3 neue Svelte-Molecules für die CompareDetail-Seite — `CompareLocationRow`, `CompareIdealRow`, `CompareLayoutRow` — plus Re-Export in `molecules/index.ts`.

## Related Files
| Datei | Relevanz |
|-------|----------|
| `frontend/src/lib/components/molecules/index.ts` | Wird erweitert (3 neue Re-Exporte) |
| `frontend/src/lib/components/molecules/DetailRow.svelte` | Muster: Flex-Zeile mit Label/Value, `dense`, `last`, Divider-Pattern |
| `frontend/src/lib/components/molecules/ChannelRow.svelte` | Muster: `dense`-Prop, `last`-Prop (kein unterer Border), dense vs. Card-Layout |
| `frontend/src/lib/components/atoms/Pill.svelte` | Import: Tone `accent` / `default` / `ghost` |
| `frontend/src/lib/components/atoms/KV.svelte` | Referenz: label/value-Muster mit mono-Font |
| `frontend/src/lib/components/compare/CompareRow.svelte` | Orientierung: vergleichbare Ziel-Komponenten-Familie |
| `frontend/src/lib/types.ts` | Location-Typ (id, name, elevation_m, group_id) |
| `frontend/src/app.css` | Design-Tokens (--g-accent, --g-ink-3, --g-rule-soft, etc.) |
| `frontend/src/lib/components/molecules/molecules.test.ts` | Test-Muster (node:test, Source-Inspection) |

## Existing Patterns

### Zeilen-Komponenten (Molecules)
- **Props-Muster:** `dense` für Mobile-Spacing, `last` für Divider-Unterdrückung, `class` für className-Erweiterung
- **Style-Muster:** Inline-Styles mit CSS-Variablen (kein Tailwind), Svelte 5 `$props()`
- **Divider:** `border-bottom: 1px solid var(--g-rule-soft)`, bei `last=true` → `'none'`
- **Mono-Font:** `font-family: var(--g-font-mono)` für Messwerte/Nummern
- **Labels:** `color: var(--g-ink-3)`, `font-size: 12px`, `letter-spacing: 0.02em`

### Pill-Tone-Mapping
| Tone | Effekt |
|------|--------|
| `accent` | `background: var(--g-accent)`, warm orange |
| `default` | `background: var(--g-surface-2)`, neutral |
| `ghost` | transparent, `border: 1px solid var(--g-rule)`, `color: var(--g-ink-3)` |

### Location-Typ (types.ts)
```typescript
interface Location {
  id: string;
  name: string;
  elevation_m?: number;    // für Höhe m
  group_id?: string;       // FK auf Group
  // group?: string;       // Legacy, nicht mehr lesen
}
```

### molecules/index.ts Muster
```typescript
export { default as NewComponent } from './NewComponent.svelte';
```

## Target: 3 neue Komponenten

### CompareLocationRow
- Zeigt: Rang-Badge (01, 02, ...) · Name · Gruppe · Höhe m
- Props: `loc` (Location-Objekt), `index` (number), `dense` (bool), `alt` (bool, alternating bg)
- Badge: nullpadded Index (01, 02, ...) in mono, `--g-accent`-getönt
- `alt` → leichter Hintergrund `--g-card-alt`

### CompareIdealRow
- Zeigt: Metrik-Label · Idealwert (mono) · Gewicht-Pill
- Props: `item` ({metric, range, weight: 'hoch'|'mittel'|'niedrig'}), `dense`, `last`
- Gewicht-Pill: hoch=`accent`, mittel=`default`, niedrig=`ghost`

### CompareLayoutRow
- Zeigt: Kanal-Label + Constraint-Hint links · Spalten-Chips rechts
- Props: `channel` (string), `cols` (number), `dense`
- SMS-Sonderfall: `cols === 0` → Hint „flach · ohne Spalten", keine Chips
- Erstes Chip: `accent`-getönt, weitere `default`

## Dependencies
- **Upstream:** `Pill` aus `$lib/components/atoms` — bereits vorhanden
- **Abhängig von Block A (#488):** Block A (CompareTile etc.) ist NOCH NICHT implementiert — Block A2 ist aber parallel umsetzbar (keine Abhängigkeit von Block A)
- **Blockiert:** #491 (Block C: CompareDetail) braucht alle 3 Komponenten

## Existing Specs
- `docs/specs/modules/issue_372_molecules.md` — Molecules-Schicht (Muster-Spec)
- `docs/specs/modules/issue_371_atoms.md` — Atoms-Schicht (Pill, KV)

## Risks & Considerations
- Block A (#488) ist noch nicht implementiert — kein Import-Konflikt, da A2-Komponenten keine A-Komponenten brauchen
- `location.group` ist Legacy (nicht lesen); für Gruppen-Label muss der Aufrufer den Namen auflösen (oder `group_id` weitergeben) — CompareLocationRow bekommt einfach `loc` und zeigt `loc.group ?? ''`
- Kein Tailwind — nur Inline-Styles mit CSS-Variablen (Projektkonvention)
- Svelte 5 Syntax (`$props()`, `$derived()`) — wie alle anderen Molecules
- LoC-Schätzung: ~90 LoC (3×~25 + index.ts ~15) — innerhalb 250er-Limit

---
entity_id: issue_372_molecules
type: module
created: 2026-05-26
updated: 2026-05-26
status: draft
version: "1.0"
tags: [frontend, atomic-design, molecules, epic-368, issue-372]
---

<!-- Issue #372 — Molecules lib/components/molecules/ (10 Bausteine) -->

# Issue #372 — Molecules-Schicht `lib/components/molecules/`

## Approval

- [ ] Approved

## Zweck

`frontend/src/lib/components/molecules/` mit den 10 Molecules aus `molecules.jsx` (Epic #368). Sie kombinieren #371-Atome zu zusammengesetzten Listen-/Form-Bausteinen und bedienen Desktop UND Mobile über `dense`/`last`/`compact`/`size`-Props (C3 — keine separaten Mobile-Varianten). Alle 10 sind Neubau (Greenfield). Token-basiert, SSR-fest, backward-compatible (kein bestehender Code betroffen).

## Quelle / Source

**Kanonische Vorlage:** `docs/design-requests/issue_15_atomic_design/spec/molecules.jsx` (React/JSX → Svelte 5) + `body-15-atomic-design-library.md` §Molecules.

**Neue Dateien (10 Molecules + Barrel + Issue #489 Add-ons):**
- `frontend/src/lib/components/molecules/Field.svelte`, `DetailRow.svelte`, `StagePill.svelte`, `ChannelRow.svelte`, `ChannelChip.svelte`, `BriefingTimelineRow.svelte`, `BriefingScheduleRow.svelte`, `ThresholdRow.svelte`, `Stat.svelte`, `AlertRow.svelte`
- `frontend/src/lib/components/molecules/index.ts` (re-exportiert alle 10 + Issue #489: CompareLocationRow, CompareIdealRow, CompareLayoutRow)

**Atom-Abhängigkeiten (Import aus `$lib/components/atoms`, #371 auf main):**
- ChannelRow → Switch · BriefingScheduleRow → Switch · BriefingTimelineRow → Dot + ChannelChip · AlertRow → WIcon · DetailRow → optional WIcon.

**Neue Test-Datei:** `frontend/src/lib/components/molecules/molecules.test.ts` (Source-Inspection, node:test, keine Mocks).

**NICHT in #372 (andere/größere Bausteine in molecules.jsx):** HorizonChips (existiert als `ui/horizon-chip`), ScoreToggle, MetricEditorRow/MetricArrow, ChannelLimitChip, ChannelPreviewCard — gehören nicht zu den 10 #372-Molecules.

> **Schicht-Hinweis:** Reine Frontend-Änderung (SvelteKit `frontend/src/lib/components/`). Keine Go/Python-Schicht.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `molecules.jsx` | Spec-Vorlage | Kanonische Definitionen der 10 Molecules |
| `frontend/src/lib/components/atoms/` (#371) | Atom-Schicht | Switch/Dot/WIcon/ChannelChip-Bausteine |
| `frontend/src/app.css` (#369 Bridge) | CSS-Tokens | `--g-*`; kein verbotener Inline-Hex (C1) |
| `frontend/src/lib/contrast-audit.test.ts` (#377) | Kontrast-Schutznetz | WCAG-AA-Text-Kontrast — greift beim Rebase |
| body-15 §Molecules | Übergeordnete Spec | dense/last/compact/size, Callback→Event, Element→Snippet |

## Implementation Details

### 10 Molecules (1:1 aus molecules.jsx, Svelte 5 `$props()`, Token-basiert)
- **Field**: label, hint, error, side, dense + Snippet. Label-Position via side.
- **DetailRow**: label, value, sub, icon (Snippet/WIcon), right (Snippet), mono, divider dashed|solid|none.
- **StagePill**: stage {code, risk}, state active|done|future|muted. `data-state={state}`. Risk-Farbe token-basiert.
- **ChannelRow**: kind, target, active, sub, onToggle, dense, last. Ohne dense = Card-Layout (`--g-card-alt`, rounded); mit dense = Reihe (kein bg, bottom-border `--g-rule-soft`). Nutzt Switch; onToggle=undefined → read-only.
- **ChannelChip**: kind, active, compact. compact = 24×24-Tile.
- **BriefingTimelineRow**: report {when,kind,etappe,channels,status}, dense. Ohne dense = Channel-Pills + Status-Suffix; mit dense = 24×24 ChannelChip compact, kein Suffix. Nutzt Dot + ChannelChip.
- **BriefingScheduleRow**: label, sub, time, enabled, onToggle, last. Nutzt Switch.
- **ThresholdRow**: label, value, divider, last, editable, onEdit.
- **Stat**: label, value, sub, unit, tone default|accent, layout stack|inline, size sm|md|lg, mono. layout=stack: Label oben/Value unten; inline: Value links groß/Label rechts klein. Leerer value → Em-Dash `—`.
- **AlertRow**: alert {kind,when,msg,channel?}, variant icon|dot|plain, divider, last. icon = WIcon links; dot = Accent-Dot; plain = kein Marker.

### Konvertierungs-Regeln
- Callback-Props (onToggle/onEdit) → Svelte-Callback-Props/`bind:`. Element-Props (icon/right) → Snippets.
- Unbekannte state/variant/tone/divider/size → Default-Fallback, kein Crash. SSR-fest.

## Expected Behavior

- **Input:** keiner zur Laufzeit (Komponenten).
- **Output:** `import { Stat, ChannelRow, AlertRow, … } from '$lib/components/molecules'` liefert alle 10; SSR-fest, Token-basiert, WCAG-AA-Kontrast.
- **Side effects:** keine; kein bestehender Code betroffen (Greenfield).

## Acceptance Criteria

- **AC-1:** Given die Molecules-Schicht / When man `frontend/src/lib/components/molecules/` auflistet / Then existieren Dateien + `index.ts`-Re-Exporte für alle 10 Molecules (Field, DetailRow, StagePill, ChannelRow, ChannelChip, BriefingTimelineRow, BriefingScheduleRow, ThresholdRow, Stat, AlertRow).
  - Test: (populated after /tdd-red)

- **AC-2:** Given ChannelRow / When ohne `dense` bzw. mit `dense` gerendert / Then ohne dense = Card-Layout (`--g-card-alt`), mit dense = Reihen-Layout mit bottom-border `--g-rule-soft`; bei `onToggle=undefined` rendert der Switch read-only (kein Crash).
  - Test: (populated after /tdd-red)

- **AC-3:** Given Stat / When `value` leer/null ist / Then rendert ein Em-Dash `—`; `layout=stack|inline` und `size=sm|md|lg` ergeben distinct Layouts.
  - Test: (populated after /tdd-red)

- **AC-4:** Given AlertRow / When mit `variant=icon|dot|plain` gerendert / Then icon = WIcon-Marker links, dot = Dot-Marker, plain = kein Marker; StagePill trägt `data-state`.
  - Test: (populated after /tdd-red)

- **AC-5:** Given die Atom-Abhängigkeiten / When Molecules importieren / Then nutzen ChannelRow/BriefingScheduleRow `Switch`, BriefingTimelineRow `Dot`+`ChannelChip`, AlertRow `WIcon` aus `$lib/components/atoms` (keine Inline-Duplikate); alle Molecules sind SSR-fest (kein `window.*` ohne Guard).
  - Test: (populated after /tdd-red)

- **AC-6:** Given Token-/Kontrast-Disziplin / When man die 10 Molecules prüft / Then nutzen sie `var(--g-*)` (kein verbotener Inline-Hex außer Vorlage), echter Text wahrt WCAG-AA (kein `--g-ink-4` für Daten/Labels), und `contrast-audit.test.ts` (#377) bleibt grün.
  - Test: (populated after /tdd-red)

## Known Limitations

- Visuelle Abnahme mit Showcase #374 (Bibliothek inert bis Nutzung).
- Tiefere Vereinheitlichung (Screens auf `molecules/` umstellen) → opportunistisch bei Screen-Migration (#368 Phase 2).
- Wrapper-Typ-Transparenz analog #371-F003 (Molecules sind hier keine Wrapper, eigenständig typisiert).

## Changelog

- 2026-05-31: Issue #489 add-ons (CompareLocationRow, CompareIdealRow, CompareLayoutRow) integrated into molecules barrel; Block A2 Epic #485 Compare-Detail prep
- 2026-05-26: Initial spec created (Issue #372, Molecules-Schicht)

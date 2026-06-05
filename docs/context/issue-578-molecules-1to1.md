# Context: Issue #578 — Molecules + Organisms + Sidebar 1:1

## Request Summary

Issue #578 wurde wiedergeöffnet (Pilot #582 zeigte 51,5 % Pixel-Diff
gegen SOLL). Alle Molecules, Organisms und die Sidebar müssen 1:1 aus
den JSX-Vorlagen neu implementiert werden — Inline-Styles zeichenweise
übernehmen, sichtbarer Text wortgleich, keine Tailwind-Übersetzung,
keine erfundenen Sub-Komponenten oder States.

## JSX-Inventory (verbindlich)

| Quelle | Komponenten | Inline-Styles | Mock-Felder |
|--------|-------------|---------------|-------------|
| `claude-code-handoff/current/jsx/molecules.jsx` (1574 Z) | 32 Funktionen (Field, DetailRow, StagePill, ChannelRow, ChannelChip, BriefingTimelineRow, BriefingScheduleRow, ThresholdRow, Stat, AlertRow, HorizonChips, ScoreToggle, MetricEditorRow, MetricArrow, ChannelLimitChip, ChannelPreviewCard, QuickAction(+Glyph), SetupResumeCard, CompareStatusPill, CompareTile, CompareKebab, CompareLocationRow, CompareIdealRow, CompareLayoutRow, StageDateField, StageCascadeNotice, ComparePreviewMissing, CompareBriefingPreview, CompareChatBubble, CompareSmsPreview, CompareChannelSwitch …) | **119** | viele |
| `claude-code-handoff/current/jsx/organisms.jsx` (1341 Z) | PresetRail, MetricBucket, MetricOffShelf, ChannelPreviewStrip, MetricsEditorContextBar, MetricsEditor, MetricEditorRow (dup), ChannelLimitChip (dup), ChannelPreviewCard (dup), MetricCheckbox | **39** | 79 |
| `claude-code-handoff/current/jsx/sidebar.jsx` (27 Z) | nur Mapping-Wrapper auf `brand-kit::BrandSidebar` (Items: home/trips/compare/archive) | — | — |
| `claude-code-handoff/current/jsx/brand-kit.jsx` (Sidebar-Block 229–351) | BrandSidebarHeader, BrandSidebar, BrandSidebarItem, BrandSidebarIcon (home/trip/compare/archive) | — | — |

## Aktueller Bestand im Frontend

`frontend/src/lib/components/molecules/*.svelte` (Auszug):
- Field, DetailRow, StagePill, ChannelRow, ChannelChip,
  BriefingTimelineRow, BriefingScheduleRow, ThresholdRow, Stat,
  AlertRow, HorizonChips, ScoreToggle, QuickAction, SetupResumeCard,
  StageCascadeNotice, sämtliche Compare-Row-Atoms — alle vorhanden.

`frontend/src/lib/components/organisms/*.svelte`:
- AlertsCard, HomeHeroCompare, HomeHeroTrip, MetricOffShelf,
  MetricsEditorContextBar, OutboxCard, PresetRail vorhanden.
- MetricsEditor / MetricBucket / MetricCheckbox / ChannelPreviewStrip /
  ChannelLimitChip liegen unter `components/edit/` bzw. `components/preview/`.

`frontend/src/lib/components/ui/sidebar/Sidebar.svelte`:
- **Massive Drift**: Tailwind-Klassen statt Inline-Styles, Lucide-Icons
  statt SVG-Originale aus brand-kit, Hover-Tokens `bg-sidebar-accent`
  statt `rgba(196,90,42,0.10)`, `--g-paper-deep`, `--g-rule`.
- Vermutlicher Haupttreiber der 51,5 %-Drift im Pilot #582 (Sidebar
  liegt in jedem Compare-/Home-/Trip-Screen mit drin).

## Drift-Beispiele (Stichprobe)

**Field.svelte** Hint-Color:
- JSX: `error ? "var(--g-bad)" : "var(--g-ink-4)"`
- Svelte: `error ? 'var(--g-danger)' : 'var(--g-ink-3)'`
- bewusst gehärtet für WCAG-AA (#377). **Konflikt zu „JSX ist die
  Wahrheit"** ([[feedback_jsx_always_truth]]). Plan: JSX-Werte
  übernehmen, Token-Kontrast-Folge im Design-Charter klären (nicht
  hier blockieren).

**Sidebar.svelte**:
- JSX: `width:220, background:var(--g-paper-deep), border-right:1px solid var(--g-rule), padding:24px 0 0` + Inline-SVG-Icons + Token `rgba(196,90,42,0.10)` für Active-State + BrandWordmark.
- Svelte: `w-60 bg-sidebar text-sidebar-foreground p-4 …` + Lucide-Icons.

## Mock-Felder vs. Backend

Liste enthält ~79 Felder aus `mock-data.jsx` (z. B. `alert.kind`,
`report.channels`, `sub.profileLabel`, `loc.elev`, …). Da #578 ein
Foundation-Issue ist und keine Daten-Endpoints liefert, wird der
Backend-Pre-Check pro Screen-Issue (#579 ff.) gemacht — hier reicht es,
die Komponenten so zu bauen, dass sie alle JSX-Props/Slots
unterstützen.

## Diff-Gate (verbindlich, Issue-Body)

> „Dieses Issue ist Fundament (keine direkte Screen-Bindung). Erfolg
> wird über die abhängigen Screen-Issues nachgewiesen."

Praktisch heißt das: Issue-Close erst, wenn ein Tracer-Screen
(z. B. `D-home-trip` als #579) `passed: true` (diff_pct < 10 %) liefert.

## Referenzen

- Pilot mit 51,5 % Drift: Issue #582 (Compare-Liste), Memory
  `project_issue_582_done.md`.
- Atoms-Welle 0: Issue #577, Memory `project_issue_577_done.md`
  (10 Drift-Punkte, alle gefixt, 30 LoC CSS).
- Tokens-Welle 0: Issue #576 (`--g-info` korrigiert).
- Foundation-First-Lehre: `project_issue_577_done.md` —
  Tokens 3 + Atoms 10 = 13 Werte-Fixes haben Screen-Diff massiv
  reduziert.
- Gate-Tool: `.claude/hooks/pre_issue_close_design_gate.py`
  (blockt Close ohne `passed:true`-Artefakt).
- 1:1-Regel: [[feedback_design_fidelity_1to1]].
- Token-Konflikt-Regel: [[feedback_jsx_always_truth]] —
  JSX gewinnt automatisch, SOLL-Aktualisierung als Design-Request.

## Risiken

- **Sidebar-Umbau betrifft jeden Screen** — wenn die Sidebar 1:1 wird,
  verschieben sich Layout-Bounding-Boxes minimal in jedem Screen-Diff.
  Tracer-Screen also nach Sidebar-Migration neu rendern.
- **Doppel-Komponenten in organisms.jsx** (MetricEditorRow,
  ChannelLimitChip, ChannelPreviewCard erscheinen sowohl in
  molecules.jsx als auch in organisms.jsx). JSX behält in organisms
  die spezifischeren Varianten — Stand prüfen, kein doppelt
  exportieren.
- **Tailwind-Sidebar-Test** — viele E2E-Tests greifen vermutlich auf
  Tailwind-Klassen (`data-testid="desktop-sidebar"`, `class*="bg-sidebar"`).
  Tests vor Migration kartieren.
- **LoC-Limit 250** wird mit Sicherheit überschritten (Sidebar allein
  ~150 LoC, Molecules-/Organisms-Korrekturen je 5–15 LoC × 30+).
  Override schon in Phase 3 setzen.

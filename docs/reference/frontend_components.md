# Frontend Components Reference

**Updated:** 2026-06-08 (Issue #647 — Home-Screen Fidelity: homeCompareTimeline Helper); 2026-05-31  
**Version:** 1.8

## Overview

Gregor Frontend uses a component-based architecture with SvelteKit (Svelte 5 Runes) and Tailwind CSS. This document describes the available component library: both shadcn-svelte imports and custom Gregor atoms.

## Component Organization

```
frontend/src/lib/components/
├── ui/                    # UI component library
│   ├── button/           # shadcn: standard form button
│   ├── card/             # shadcn: content container
│   ├── dialog/           # shadcn: modal
│   ├── badge/            # shadcn: label/tag
│   │
│   ├── btn/              # GREGOR atom (Issue #144)
│   ├── g-card/           # GREGOR atom (Issue #144)
│   ├── pill/             # GREGOR atom (Issue #144)
│   ├── eyebrow/          # GREGOR atom (Issue #144)
│   ├── dot/              # GREGOR atom (Issue #144)
│   ├── topo/             # GREGOR atom (Issue #143)
│   ├── elev-sparkline/   # GREGOR atom (Issue #146)
│   │
│   └── sidebar/
│       ├── TopAppBar.svelte    # Fixed top bar (mobile-only, Issue #267)
│       ├── BottomNav.svelte    # Fixed bottom nav (mobile-only, Issue #267)
│       └── Sidebar.svelte      # Main navigation (Issue #145)
│
├── trip-wizard/          # Trip-Wizard components (Epic #136)
│   ├── TripWizardShell.svelte   # Shell + 4-step stepper
│   ├── Stepper.svelte           # Generic step indicator
│   ├── wizardState.svelte.ts    # Central Runes state class
│   ├── wizardHelpers.ts         # Shared helpers (newId, today, isPauseStage, etc.)
│   ├── steps/
│   │   ├── Step1Profile.svelte      # Activity profile + name/dates
│   │   ├── Step2Stages.svelte       # Multi-GPX upload, drag-sort, pause
│   │   ├── Step3Waypoints.svelte    # AI waypoint confirmation
│   │   └── Step4Briefings.svelte    # Briefing channels & thresholds
│   ├── templates/
│   │   └── TemplatePicker.svelte    # GR20, KHW, Stubai pre-configs
│   └── __tests__/
│       ├── wizardHelpers.test.ts
│       └── wizardState.test.ts
│
└── layout/
    └── (organized in sidebar/ above)
```

## Gregor Atoms (Epic #133)

All Gregor atoms follow a consistent pattern:
- Svelte 5 Runes (`$props()`, `$bindable()`, `$derived()`)
- `data-slot`, `data-variant`, `data-tone` attributes for CSS-based styling
- Token-based colors from `--g-*` CSS custom properties
- `WithElementRef` type from `bits-ui` for `bind:this={ref}`
- Pure function rendering without side effects

### Import Pattern

```typescript
import { Btn } from '$lib/components/ui/btn';
import { GCard } from '$lib/components/ui/g-card';
import { Pill } from '$lib/components/ui/pill';
import { Eyebrow } from '$lib/components/ui/eyebrow';
import { Dot } from '$lib/components/ui/dot';
import { TopoBg } from '$lib/components/ui/topo';
import { ElevSparkline } from '$lib/components/ui/elev-sparkline';
```

### Btn Component

**File:** `frontend/src/lib/components/ui/btn/Btn.svelte`

Interactive button with three variants.

**Props:**
```typescript
interface BtnProps extends WithElementRef<HTMLButtonAttributes> {
  variant?: 'accent' | 'ghost' | 'outline';  // default: 'accent'
  size?: 'sm' | 'md' | 'lg';                 // default: 'md'
  class?: string;
  children?: Snippet;
}
```

**Example:**
```svelte
<Btn variant="accent" size="md" on:click={handleSave}>
  Speichern
</Btn>
```

**Styling:** Global `[data-slot="btn"]` selectors in `app.css` (`@layer components`)

**Variants:**
- `accent`: burnt orange background (`--g-accent`), white text
- `ghost`: transparent, ink-colored text
- `outline`: transparent, ink-colored border + text

**Sizes:**
- `sm`: 0.25rem padding, 0.75rem horizontal, 0.75rem font-size
- `md`: 0.5rem padding, 1rem horizontal, 0.875rem font-size
- `lg`: 0.75rem padding, 1.5rem horizontal, 1rem font-size

---

### GCard Component

**File:** `frontend/src/lib/components/ui/g-card/GCard.svelte`

Surface container with elevation and hover effects.

**Props:**
```typescript
interface GCardProps {
  class?: string;
  children?: Snippet;
}
```

**Example:**
```svelte
<GCard>
  <h3>Trip Overview</h3>
  <p>Content here</p>
</GCard>
```

**Styling:**
- Background: `--g-surface-1`
- Border-radius: `--g-radius-lg`
- Elevation: `--g-elev-1` (resting), `--g-elev-2` (hover)

---

### Pill Component

**File:** `frontend/src/lib/components/ui/pill/Pill.svelte`

Compact inline label with semantic color tones.

**Props:**
```typescript
interface PillProps {
  tone?: 'default' | 'success' | 'warning' | 'danger' | 'info' | 'accent';
  class?: string;
  children?: Snippet;
}
```

**Example:**
```svelte
<Pill tone="success">OK</Pill>
<Pill tone="danger">Error</Pill>
<Pill tone="warning">Caution</Pill>
```

**Tones & Colors:**
- `default`: surface-2 background, ink text
- `success`: `--g-success` background, white text
- `warning`: `--g-warning` background, white text
- `danger`: `--g-danger` background, white text
- `info`: `--g-info` background, white text
- `accent`: `--g-accent` background, paper text

---

### Eyebrow Component

**File:** `frontend/src/lib/components/ui/eyebrow/Eyebrow.svelte`

All-caps label text for metadata or section headers.

**Props:**
```typescript
interface EyebrowProps {
  class?: string;
  children?: Snippet;
}
```

**Example:**
```svelte
<Eyebrow>Wetter</Eyebrow>
<Eyebrow>Alarme</Eyebrow>
```

**Styling:**
- Font: `--g-font-data` (JetBrains Mono)
- Size: 0.625rem
- Weight: 400
- Letter-spacing: 0.1em (uppercase)
- Color: `--g-ink-faint`

---

### Dot Component

**File:** `frontend/src/lib/components/ui/dot/Dot.svelte`

Circular indicator for weather conditions or semantic status.

**Props:**
```typescript
interface DotProps {
  size?: 'xs' | 'sm' | 'md';     // default: 'md'
  tone?: string;  // Weather (rain, sun, wind, snow, thunder, fog) or Semantic (success, warning, danger, info)
  class?: string;
}
```

**Example:**
```svelte
<Dot tone="rain" size="md" />
<Dot tone="sun" size="sm" />
<Dot tone="thunder" size="xs" />
<Dot tone="success" size="md" />
```

**Weather Tones & Colors:**
- `rain`: `--g-wx-rain` (#4a7fb5)
- `sun`: `--g-wx-sun` (#e8a820)
- `wind`: `--g-wx-wind` (#6b8a8a)
- `snow`: `--g-wx-snow` (#a8c8e8)
- `thunder`: `--g-wx-thunder`
- `fog`: `--g-wx-fog`

**Semantic Tones:** `success`, `warning`, `danger`, `info` (same as Pill tones)

**Sizes:**
- `xs`: 6px × 6px
- `sm`: 8px × 8px
- `md`: 10px × 10px

---

### TopoBg Component

**File:** `frontend/src/lib/components/ui/topo/TopoBg.svelte`

Background pattern (topographic map grid). Renders a concentric-striped radial gradient via the `.g-topo` utility.

**Props:**
```typescript
interface TopoBgProps {
  opacity?: number;  // default: 0.04
  children?: Snippet;
}
```

**Example:**
```svelte
<TopoBg opacity={0.06}>
  <section>
    <p>Content over topo pattern</p>
  </section>
</TopoBg>
```

**Implementation:**
- Wrapper div with `position: relative`
- Inner div with `.g-topo` class (utility from `app.css`)
- `--g-topo-opacity` CSS custom property set via `style` attribute
- Absolute positioning + `pointer-events: none` prevents pattern from blocking interactions
- Children rendered in a separate positioned-relative div above the pattern

**Styling:** `.g-topo` is defined in `app.css` `@layer components`:
```css
.g-topo {
  background-image:
    radial-gradient(...),
    radial-gradient(...);
  background-size: 60px 60px;
  opacity: var(--g-topo-opacity, 0.04);
  pointer-events: none;
}
```

---

### ElevSparkline Component

**File:** `frontend/src/lib/components/ui/elev-sparkline/ElevSparkline.svelte`

Inline SVG sparkline for elevation profiles or metric trends.

**Props:**
```typescript
interface ElevSparklineProps {
  data: number[];
  width?: number;      // default: 120
  height?: number;     // default: 24
  active?: boolean;    // default: false
}
```

**Example:**
```svelte
<ElevSparkline data={[800, 1200, 950, 1500, 1100]} width={200} height={40} />
<ElevSparkline data={[]} width={120} height={24} />
<ElevSparkline data={[1500]} width={120} height={24} />
```

**Behavior:**
- **Non-empty array:** Renders `<polyline>` with one point per data value
- **Empty array:** Renders SVG container without `<polyline>` (no crash)
- **Single value:** Renders horizontal line at midpoint (no division by zero)
- **Identical values:** Renders horizontal line (range = 1 fallback)

**Y-Scaling:**
- Maps min/max data values to pixel coordinates
- Preserves relative height differences
- Padding: 2px top + bottom

**Styling:**
- Stroke color: `currentColor` — set via parent CSS `color` property
- Stroke-width: 1.5px
- Line-join: round, line-cap: round

**SVG Attributes:**
- `data-slot="elev-sparkline"` (for testing)
- `data-active={active}` (for conditional styling if needed)
- `viewBox="0 0 {width} {height}"` — responsive scaling
- `aria-hidden="true"` — decorative, not announced

---

## Gregor Molecules (Epic #368/372)

Molecules are composite components built from atoms and `ui/` primitives. They encapsulate common UI patterns and free consumers from direct `ui/` imports.

All molecules export from the barrel `$lib/components/molecules/index.ts`.

### Import Pattern

```typescript
import { ConfirmDialog, DetailRow, StagePill, ChannelRow, AlertRow, Stat } from '$lib/components/molecules';
```

### ConfirmDialog Component

**File:** `frontend/src/lib/components/molecules/ConfirmDialog.svelte`

Modal dialog for destructive confirmations (archive, delete). Wraps `ui/dialog` primitives + `Btn` atoms.

**Props:**
```typescript
interface ConfirmDialogProps {
  open: boolean;
  title: string;
  description: string;
  confirmLabel: string;
  confirmVariant?: 'primary' | 'destructive';  // default: 'primary'
  cancelLabel?: string;                        // default: 'Abbrechen'
  disabled?: boolean;
  'data-testid'?: string;
  cancelTestid?: string;
  confirmTestid?: string;
  onConfirm: () => void;
  onCancel: () => void;
  onOpenChange: (open: boolean) => void;
}
```

**Example:**
```svelte
<ConfirmDialog
  open={archiveDialogOpen}
  title="Trip archivieren?"
  description="Diese Tour kann später aus dem Archiv wiederhergestellt werden."
  confirmLabel="Ja, archivieren"
  confirmVariant="destructive"
  onConfirm={handleArchiveConfirm}
  onCancel={handleArchiveCancel}
  onOpenChange={handleArchiveDialogOpenChange}
  data-testid="trip-detail-archive-confirm-dialog"
  confirmTestid="trip-detail-archive-confirm-yes"
  cancelTestid="trip-detail-archive-confirm-cancel"
/>
```

**Usage:** Issue #478 migrated Trip-Detail page away from direct `ui/dialog` imports; ConfirmDialog now encapsulates the pattern.

---

### Other Molecules

Additional molecules available:
- `<DetailRow>` — Key-value pair with label, value, optional icon
- `<StagePill>` — Stage badge with risk color + state icon
- `<ChannelRow>` — Notification channel row with toggle switch
- `<ChannelChip>` — Small channel indicator (compact mode for timelines)
- `<BriefingTimelineRow>` — Briefing history row with timestamp + channels
- `<BriefingScheduleRow>` — Scheduler row with time + toggle
- `<ThresholdRow>` — Alert limit configuration row
- `<Stat>` — Statistics display (counts, distances, etc.)
- `<AlertRow>` — Alert configuration row
- `<Field>` — Form field with label, hint, error

See `docs/design-system/COMPONENTS.md` §4.5 for full spec.

---

## Design Tokens

All Gregor atoms reference design tokens defined in `app.css` `@layer base`. See `docs/specs/modules/epic_133_design_system_lauf_a.md` for the full token list.

### Token Namespace: `--g-*`

**Primary Colors:**
- `--g-accent`: Burnt orange (#c45a2a) — CTAs, highlights
- `--g-paper`: Warm off-white (#f6f4ee) — page background
- `--g-ink`: Almost black (#1a1a18) — primary text

**Surfaces:**
- `--g-surface-0`: paper (alias)
- `--g-surface-1`: Card backgrounds
- `--g-surface-2`: Hover/active states

**Text Levels:**
- `--g-ink-muted`: Secondary text
- `--g-ink-faint`: Placeholders, metadata

**Semantic:**
- `--g-success`, `--g-warning`, `--g-danger`, `--g-info`

**Weather:**
- `--g-wx-rain`, `--g-wx-sun`, `--g-wx-wind`, `--g-wx-snow`, `--g-wx-thunder`, `--g-wx-fog`

**Typography:**
- `--g-font-ui`: Inter Tight (buttons, labels)
- `--g-font-data`: JetBrains Mono (monospace, eyebrow)

**Layout:**
- `--g-radius-md`, `--g-radius-lg`, `--g-radius-pill`
- `--g-elev-1`, `--g-elev-2` (box-shadow)

---

## Testing

### Showcase Route

All atoms are rendered together at `/_design` for E2E testing and visual inspection. This route requires authentication and is not exposed in the navigation sidebar.

**File:** `frontend/src/routes/_design/+page.svelte`

**E2E Tests:** `frontend/e2e/design-system-lauf-b.spec.ts` (10 tests)

---

## Future Considerations

- **Dark Mode:** Token variants not yet defined (planned for future lauf)
- **Accessibility:** All atoms use semantic HTML (`<button>`, `<span>`); SVG components use `aria-hidden="true"`
- **CSS Custom Property Override:** Atoms accept `class` prop for additional Tailwind utilities
- **Element Binding:** Use `bind:this={ref}` with `WithElementRef` for direct DOM access (e.g., focus management)

---

## Migration from shadcn

Gregor atoms (`Btn`, `Pill`, etc.) are **custom lightweight alternatives** to shadcn imports. They trade shadcn's composability (compound component patterns, flexible variant systems) for **predictable token-based styling** and **reduced bundle size**.

Use Gregor atoms for:
- Consistent branding via `--g-*` tokens
- Quick, deterministic styling without `cv()` variance chains
- Simpler HTML output (no nested helper components)

Use shadcn for:
- Complex modal dialogs, popovers, select dropdowns
- Highly customizable form inputs
- Existing patterns that shadcn already provides well (card layouts, tabs, etc.)

Both can coexist in the same codebase without conflicts — namespaces (Gregor `data-slot` vs. shadcn class-based) are disjoint.

---

## App-Shell Navigation (Issue #267)

Mobile-responsive navigation system with responsive layout switching at the 900px breakpoint.

### TopAppBar Component

**File:** `frontend/src/lib/components/ui/sidebar/TopAppBar.svelte`

Fixed header bar for mobile viewports (< 900px). Contains hamburger menu trigger, app title, and dark mode toggle.

**Props:**
```typescript
interface Props {
  mobileMenuOpen: boolean;
}
let { mobileMenuOpen = $bindable() }: Props = $props();
```

**Layout:**
- **Height:** 56px, `position: fixed; top: 0; left: 0; right: 0; z-index: 60`
- **Background:** `var(--g-paper)`
- **Border:** `1px solid var(--g-rule-soft)` (bottom)
- **Visibility:** Mobile only (`class="desktop:hidden"`)

**Sections:**
1. **Left:** Hamburger button (Menu/X icon) — toggles `mobileMenuOpen` state
2. **Center:** Title "Gregor 20" (bold)
3. **Right:** Dark mode toggle (Moon/Sun icon)

**Usage:**
```svelte
import TopAppBar from '$lib/components/ui/sidebar/TopAppBar.svelte';

let mobileMenuOpen = $state(false);
// ... in template:
<TopAppBar bind:mobileMenuOpen />
```

### BottomNav Component

**File:** `frontend/src/lib/components/ui/sidebar/BottomNav.svelte`

Fixed footer bar for mobile viewports (< 900px). Contains 4 workspace navigation items with active state indication.

**Props:** None — route detection via SvelteKit `page` store

**Layout:**
- **Height:** 64px + `env(safe-area-inset-bottom)` (iPhone notch/home-indicator support)
- `position: fixed; bottom: 0; left: 0; right: 0; z-index: 50`
- **Background:** `var(--g-paper-deep)`
- **Border:** `1px solid var(--g-rule-soft)` (top)
- **Grid:** 4 equal columns `grid-template-columns: repeat(4, 1fr)`
- **Visibility:** Mobile only (`class="desktop:hidden"`)

**Navigation Items (auto-generated from NAV_ITEMS):**

| Icon | Label | Route |
|------|-------|-------|
| LayoutDashboard | Übersicht | `/` |
| Route | Trips | `/trips` |
| GitCompare | Vergleich | `/compare` |
| MapPin | Locations | `/locations` |

**Per-Item Styling:**
- **Active State:** 
  - Accent line top: `box-shadow: inset 0 2px 0 var(--g-accent)`
  - Font-weight: 600
  - Color: `var(--g-ink)`
- **Inactive State:**
  - No line
  - Font-weight: 500
  - Color: `var(--g-ink-muted)`
- **Icon Size:** 22px
- **Label Size:** 10px

**Usage:**
```svelte
import BottomNav from '$lib/components/ui/sidebar/BottomNav.svelte';

// ... in template:
<BottomNav />
```

### Layout Integration

Both components are orchestrated in `frontend/src/routes/+layout.svelte`:

```svelte
<script>
  import TopAppBar from '$lib/components/ui/sidebar/TopAppBar.svelte';
  import BottomNav from '$lib/components/ui/sidebar/BottomNav.svelte';
  
  let mobileMenuOpen = $state(false);
</script>

<TopAppBar bind:mobileMenuOpen />

<div class="desktop:flex h-screen">
  <Sidebar bind:mobileMenuOpen />
  
  <main class="flex-1 overflow-y-auto mobile:pt-14 mobile-scroll-pad">
    {@render children()}
  </main>
</div>

<BottomNav />
```

**Responsive Breakpoint:** 900px (custom `@custom-variant` in `app.css`)
- **< 900px:** TopAppBar visible, BottomNav visible, Sidebar drawer-only
- **>= 900px:** TopAppBar hidden, BottomNav hidden, Sidebar full sidebar (unchanged)

**CSS Utilities Added:**
- `--g-paper-deep` — BottomNav background (slightly darker than surface)
- `--g-rule-soft` — Border/divider color (soft ink at 8% opacity)
- `.mobile-scroll-pad` — Padding-bottom to prevent BottomNav overlap: `calc(64px + env(safe-area-inset-bottom))`
- `@custom-variant mobile` — Matches viewport < 900px
- `@custom-variant desktop` — Matches viewport >= 900px

### Sidebar Component Updates

**File:** `frontend/src/lib/components/ui/sidebar/Sidebar.svelte`

Updated to support both desktop full-sidebar and mobile drawer modes.

**Changes from Issue #267:**
- Removed mobile-specific (hamburger, overlay) UI logic
- Added 4th NavItem for Locations (`/locations`)
- Accepts `mobileMenuOpen` as `$bindable()` prop to control drawer state
- All `md:` Tailwind breakpoint classes → `desktop:` (900px instead of 768px)
- On mobile, drawer shows only secondary items (Konto, Status, Dark Mode, Logout)
- Workspace routes (Übersicht, Trips, Vergleich, Locations) removed from drawer, available only in BottomNav

---

## Trip-Wizard Components (Epic #136)

Multi-step wizard for creating new trips with activity profiles, GPX import, AI waypoint confirmation, and briefing config.

**Route:** `/trips/new` → mounted by `frontend/src/routes/trips/new/+page.svelte`

**Varianten:** Der Trip-Wizard hat zwei mögliche Step-4-Konfigurationen (per Trip konfigurierbar):
1. **Step4Briefings** (traditionell): Kanal-Toggles + Alarm-Schwellenwerte
2. **Step4Layout** (Issue #431): Pro-Kanal-Metriken-Konfiguration (Reihenfolge, Bucket-Zuordnung) — wird in `compareWizardState` als Vorlage für Orts-Vergleiche verwendet

### Component Architecture

```
TripWizardShell (container, stepper + steps)
├── Stepper (visual step indicator)
├── Step1Profile (activity + name + dates)
├── Step2Stages (GPX multi-upload, drag-sort, pause)
├── Step3Waypoints (confirm AI-suggested waypoints)
├── Step4Briefings OR Step4Layout (channel config variants)
└── TemplatePicker (GR20, KHW, Stubai shortcuts)
```

**State Management:** `WizardState` (Svelte 5 Runes class in `wizardState.svelte.ts`)

**Shared Helpers:** `wizardHelpers.ts`
- `newId()` — Generate unique component IDs
- `today()` — Current date (test-injectable)
- `addDays(date, n)` — Date arithmetic
- `mapActivityToProfile(activityType)` — Maps 5 UI profiles → 4 canonical aggregation profiles (Wintersport, Wandern, Summer-Trekking, Allgemein)
- `formatStageNumber(index)` — Formats as "T01", "T02", etc.
- `isPauseStage(stage)` — True if `waypoints: []` (pause day)

### Datenmodell Extensions (Epic #136)

**Trip model additions** (`internal/model/trip.go` + `frontend/src/lib/types.ts`):
- `Trip.shortcode?: string` — Short identifier for trip (e.g., "GR20", "KHW")
- `Trip.activity?: ActivityType` — Selected profile ("wandern", "wintersport", "summer_trekking", "allgemein", "klettern")

**Waypoint model** — New transient field:
- `Waypoint.suggested?: boolean` — True if AI-generated (UI hint: show "Confirm" button, not "Edit")

**Pause Stage Support:**
- Stages with `waypoints: []` are valid (represent pause days)
- Backend `validateTrip()` accepts this pattern
- Frontend renders as gray/muted pill

### Key Features

1. **Profile Selection (Step 1):** 5 activity chips → UI state saved as `trip.activity`
2. **Multi-GPX Upload (Step 2):** Drag-drop multiple GPX files, auto-sorted, natural sort order (T01, T02, ..., T10, T11, not T10, T11, T2)
3. **Pause Days:** Insert empty-waypoint stages to skip days (e.g., rest day, weather day)
4. **AI Waypoint Confirmation (Step 3):** Show suggested waypoints per stage, user confirms/edits
5. **Briefing Config (Step 4a, traditional):** Email/SMS toggles, thresholds (temp, wind, precip, etc.)
6. **Layout Config (Step 4b, Issue #431):** Pro-Kanal-Metrik-Reihenfolge, Bucket-Zuordnung (primär/sekundär/aus), Channel-Constraint-Anzeige
7. **Templates (Step 2 right sidebar):** GR20, KHW, Stubai → quick-populate name, dates, stages from template

### Example Usage

```svelte
<TripWizardShell {wizardState} />

<!-- From within Step1Profile: -->
<Btn on:click={() => wizardState.goToStep(2)}>Nächster Schritt</Btn>

<!-- Check pause status: -->
{#if isPauseStage(stage)}
  <Pill tone="info">Pausentag</Pill>
{/if}
```

### Links

- **Master Spec:** `docs/specs/modules/epic_136_trip_wizard.md`
- **Sub-Specs:** `docs/specs/modules/epic_136_step{0..5}_*.md`
- **Child Issues:** #160–#165

---

## Component Inventory (Ist-Stand Phase 1 + Issue #440)

Vollstaendiges Inventar aller Komponenten unter `frontend/src/lib/components/` (plus
route-lokale Kacheln unter `frontend/src/routes/_home/`). Pfade sind relativ zu
`frontend/src/lib/components/`. Volle Props-Tiefe nur fuer Kern-Atome (siehe oben:
Btn, GCard, Pill, Eyebrow, Dot, TopoBg, ElevSparkline) sowie Wordmark (unten);
Detail-Props weiterer Komponenten stehen im jeweiligen Quellcode/Spec.

**2026-05-29:** Orts-Vergleich-Wizard hinzugefuegt (Issue #440) — separater 5-Schritt-Wizard fuer Create/Edit-Modus mit Stepper-Reuse + Test-Suites.

### ui/ — Atome & shadcn-Bausteine

| Komponente | Pfad rel. zu components/ | Kurzbeschreibung |
|---|---|---|
| Btn | `ui/btn/Btn.svelte` | Gregor-Button-Atom, 3 Varianten (siehe Detail oben), Issue #144 |
| GCard | `ui/g-card/GCard.svelte` | Surface-Container mit Elevation/Hover, Issue #144 |
| Pill | `ui/pill/Pill.svelte` | Kompaktes Inline-Label mit semantischen Tones, Issue #144 |
| Eyebrow | `ui/eyebrow/Eyebrow.svelte` | All-Caps-Metadaten-/Sektions-Label, Issue #144 |
| Dot | `ui/dot/Dot.svelte` | Runder Status-/Wetter-Indikator, Issue #144 |
| TopoBg | `ui/topo/TopoBg.svelte` | Topographisches Hintergrundmuster, Issue #143 |
| ElevSparkline | `ui/elev-sparkline/ElevSparkline.svelte` | Inline-SVG-Sparkline fuer Hoehenprofile, Issue #146 |
| badge | `ui/badge/badge.svelte` | shadcn-Label/Tag |
| Checkbox | `ui/checkbox/Checkbox.svelte` | Auswahl-Checkbox |
| HorizonChip | `ui/horizon-chip/HorizonChip.svelte` | Chip fuer Zeit-Horizont-Auswahl |
| input | `ui/input/input.svelte` | shadcn-Texteingabefeld |
| label | `ui/label/label.svelte` | shadcn-Formular-Label |
| Segmented | `ui/segmented/Segmented.svelte` | Segmented-Control ([data-slot]-Muster), Issue #285 |
| Select | `ui/select/Select.svelte` | Dropdown-Auswahl |
| table | `ui/table/table.svelte` (+ table-* Teile) | shadcn-Tabellen-Bausteine |
| card | `ui/card/card.svelte` (+ card-* Teile) | shadcn-Card-Bausteine |
| dialog | `ui/dialog/dialog.svelte` (+ dialog-* Teile) | shadcn-Modal-Bausteine |
| WIcon | `ui/wicon/WIcon.svelte` | Lucide-Wrapper, 8 Wetter-Icon-Kinds, Issue #322 |
| Wordmark | `ui/wordmark/Wordmark.svelte` | Wortmarke „gregor.zwanzig" (siehe Props unten), Issue #293 |

#### Icons (Lucide)

**WICHTIG:** Das Icon-System ist in `docs/reference/sveltekit_best_practices.md` → „Icons (Lucide)" dokumentiert. Dort stehen die verbindlichen Regeln für:
- **Import-Pfade:** Immer `@lucide/svelte/icons/<name>` (kein Barrel-Import)
- **Alias-Namenskonvention:** Kurze/mehrdeutige Namen mit `-Icon`-Suffix (`PencilIcon`, `CheckIcon`, `XIcon`, `Trash2Icon`, `PlusIcon`, `UploadIcon`, `ArchiveIcon`); mehrsilbige selbsterklärende Namen ohne Suffix (`GripVertical`, `ChevronDown`, `EllipsisVertical`, `Loader2`)
- **Genehmigte Aktions-Icons:** Vollständige Liste für Bearbeiten/Löschen/Schließen/Hinzufügen/Bestätigen/usw.
- **Wetter-Icons:** Nur `<WIcon kind="..." />` verwenden, nicht direkt `Cloud`/`Sun`/`CloudRain` etc. (Issue #322)

**Beziehung zu WIcon:** `WIcon` ist ein spezialisierter Wrapper für Wetter-Inhalte (8 kinds: rain, sun, wind, snow, thunder, fog + 2 Fallbacks). Alle anderen UI-Icons (Buttons, Menüs, Listen) nutzen Lucide-Icons gemäß der Konvention oben.
| TopAppBar | `ui/sidebar/TopAppBar.svelte` | Fixierte Top-Bar (mobile), Issue #267 (Detail oben) |
| BottomNav | `ui/sidebar/BottomNav.svelte` | Fixierte Bottom-Navigation (mobile), Issue #267 (Detail oben) |
| Sidebar | `ui/sidebar/Sidebar.svelte` | Haupt-Navigation (Desktop + Drawer), Issue #145 (Detail oben) |

#### Wordmark Component

**File:** `frontend/src/lib/components/ui/wordmark/Wordmark.svelte`

Wortmarke „gregor.zwanzig" in JetBrains Mono. Rendert als anklickbarer
`<a href>`-Link (Home-Link), Ziel ueber `href` (Default `/`).

**Props:**
```typescript
interface WordmarkProps {
  size?: 'sm' | 'md' | 'lg';   // 14–24px; Untertitel ab 'md'; default 'md'
  href?: string;               // Link-Ziel, default '/'
}
```

**Darstellung:**
- „gregor**.**zwanzig" in JetBrains Mono (`--g-font-data`)
- Punkt in `--g-ink-faint`, „zwanzig" in `--g-accent`
- Untertitel „v0.20 · wetter-briefing" ab `md`
- Drei Groessen: `sm`/`md`/`lg` (14–24px)

**Einsatz:** Sidebar (`md`), TopAppBar (`sm`), Login-Seite (`lg`). Spec: `docs/specs/modules/issue_293_wordmark.md`.

### alert-rules-editor/ — Alert-Regel-Editor (#284/#297/#317)

| Komponente | Pfad rel. zu components/ | Kurzbeschreibung |
|---|---|---|
| AlertRulesEditor | `alert-rules-editor/AlertRulesEditor.svelte` | Container fuer Alert-Regeln, Brand-Token-Styling |
| AlertRuleRow | `alert-rules-editor/AlertRuleRow.svelte` | Einzelne Alert-Regel-Zeile (Metrik + Schwellwert + Schweregrad) |
| ModeCard | `alert-rules-editor/ModeCard.svelte` | Modus-Auswahl (Absolut/Δ/Beides), Issue #297 |
| alertRuleDefaults.ts | `alert-rules-editor/alertRuleDefaults.ts` | Default-Werte + Metrik-Normalisierung (Helper) |

### alerts-tab/ — Alarm-Tab (#180)

| Komponente | Pfad rel. zu components/ | Kurzbeschreibung |
|---|---|---|
| AlertsTab | `alerts-tab/AlertsTab.svelte` | Tab-Container fuer Alarm-Konfiguration |
| AlertMetricTable | `alerts-tab/AlertMetricTable.svelte` | Schwellwert-Tabelle mit Metrik-Zeilen |
| AlertMetricRow | `alerts-tab/AlertMetricRow.svelte` | Einzelne Metrik-Zeile (Toggle + Schwellwert + Schweregrad) |
| AlertCooldownCard | `alerts-tab/AlertCooldownCard.svelte` | Cooldown-Einstellung |
| AlertQuietHoursCard | `alerts-tab/AlertQuietHoursCard.svelte` | Ruhezeiten-Einstellung |
| AlertPreviewCard | `alerts-tab/AlertPreviewCard.svelte` | Vorschau ausgeloester Alarme |
| alertMetricTable.ts | `alerts-tab/alertMetricTable.ts` | Tabellen-Logik (Helper) |
| alertPreviewHelpers.ts | `alerts-tab/alertPreviewHelpers.ts` | Vorschau-Logik (Helper) |

### briefings-tab/ — Briefing-Zeitplan-Tab (#259)

| Komponente | Pfad rel. zu components/ | Kurzbeschreibung |
|---|---|---|
| BriefingsTab | `briefings-tab/BriefingsTab.svelte` | Briefing-Zeitplan-Tab (morgen/abend, Kanaele, Optionen) |

### compare/ — Vergleichs-Screen (EPIC #246/#250) & Orts-Vergleich-Wizard (Issue #440)

#### Screen & Report Components (existing)

| Komponente | Pfad rel. zu components/ | Kurzbeschreibung |
|---|---|---|
| AddReportCard | `compare/AddReportCard.svelte` | Karte zum Hinzufuegen eines Vergleichs-Reports |
| AutoReportCard | `compare/AutoReportCard.svelte` | Auto-Report-Karte (umgebaut auf ComparePreset, Issue #459) |
| AutoReportsOverview | `compare/AutoReportsOverview.svelte` | Uebersicht automatischer Reports (ComparePreset-System, Issue #459) |
| SavePresetDialog | `compare/SavePresetDialog.svelte` | Dialog zum Speichern neuer Presets (Issue #459) |
| CompareMatrix | `compare/CompareMatrix.svelte` | Vergleichs-Matrix (Locations × Metriken) |
| CreateGroupDialog | `compare/CreateGroupDialog.svelte` | Dialog zum Anlegen einer Location-Gruppe |
| HourlyMatrix | `compare/HourlyMatrix.svelte` | Stuendliche Wetter-Matrix |
| LocationPreviewMap | `compare/LocationPreviewMap.svelte` | Mini-Map-Vorschau im Wizard, Issue #266 |
| LocationsRail | `compare/LocationsRail.svelte` | Sidebar (Suche + Chip-Filter + Gruppen + Drag-Reorder), Issue #249/#453 |
| GroupSection | `compare/GroupSection.svelte` | Gruppen-Abschnitt in der Sidebar mit Drag-Reihenfolge, Issue #301/#453 |
| NewLocationWizard | `compare/NewLocationWizard.svelte` | 3-Schritt-Wizard (Verortung→Benennung→Profil), Issue #249 |
| PresetHeader | `compare/PresetHeader.svelte` | Kopfzeile fuer Compare-Preset |
| RecommendationBanner | `compare/RecommendationBanner.svelte` | Empfehlungs-Banner (Winner-Tags) |
| locationHelpers.ts | `compare/locationHelpers.ts` | Location-Logik inkl. isCoordsValid() (Helper) |
| subscriptionHelpers.ts | `compare/subscriptionHelpers.ts` | Subscription- und Preset-Logik: presetScheduleLabel, formatLastSent, formatNextSend (Issue #459, #647) |

#### Orts-Vergleich-Wizard (Issue #440 — Create/Edit Mode)

New 5-step wizard for creating and editing compare subscriptions (Orts-Vergleiche). Separate from TripWizard, reuses `Stepper` via `testidPrefix` prop.

| Komponente | Pfad rel. zu components/ | Kurzbeschreibung |
|---|---|---|
| CompareWizard | `compare/CompareWizard.svelte` | Shell + 5-Schritt-Stepper, State-Management |
| compareWizardState.svelte.ts | `compare/compareWizardState.svelte.ts` | Zentrale State-Klasse (Runes), analog `wizardState.svelte.ts` |
| Step1Vergleich | `compare/steps/Step1Vergleich.svelte` | Schritt 1: Name + Region + Aktivitaetsprofil |
| Step2Orte | `compare/steps/Step2Orte.svelte` | Schritt 2: Orte waehlen via Smart-Import + Library |
| Step3Metriken | `compare/steps/Step3Metriken.svelte` | Schritt 3: Wetter-Metriken waehlen |
| Step4Layout | `compare/steps/Step4Layout.svelte` | Schritt 4: Pro-Kanal-Layout (E-Mail/Telegram/Signal/SMS), Issue #442 |
| Step5Versand | `compare/steps/Step5Versand.svelte` | Schritt 5: Versand + Aktivierung |
| compareWizardHelpers.ts | `compare/compareWizardHelpers.ts` | Shared helpers (newId, validRegions, mapActivityProfile) |

**Step4Layout (Issue #442):** Directe Adaption von Trip-Wizard Step4Layout. Der Nutzer konfiguriert pro Kanal (Email/Telegram/Signal/SMS) die Wetter-Metriken und deren Reihenfolge im Briefing. Verwendet `OutputLayoutEditor` (gemeinsame Komponente, Issue #431) mit Channel-Tabs + Bucket-Konfiguration (primär/sekundär/aus). Fallback bei neuer Subscription: `autoAssign([], catalog)` statt `weatherMetrics`.

**Routes:**
- `frontend/src/routes/compare/new/+page.svelte` — Create mode (Wizard-Entry)
- `frontend/src/routes/compare/new/+page.server.ts` — Server actions (POST /api/subscriptions)
- `frontend/src/routes/compare/[id]/edit/+page.svelte` — Edit mode (Load existing subscription)
- `frontend/src/routes/compare/[id]/edit/+page.server.ts` — Server actions (PUT /api/subscriptions/{id})

#### LocationsRail Component (Issue #453)

**File:** `frontend/src/lib/components/compare/LocationsRail.svelte`

Sidebar-Rail für die Compare-Hauptbühne. Zeigt Locations als gruppierte/ungrupierte Liste mit Suche, Chip-Filter nach Gruppen/Aktivitätsprofilen, Constraint-Zähler (min 2 / max 8) mit farblicher Warnung, Leerzustand, und HTML5-Drag-Reihenfolge-Unterstützung.

**Props:**
```typescript
interface Props {
  locations: Location[];
  groups: Group[];
  selectedIds: string[];
  groupedLocations: { sections: { group: Group; locations: Location[] }[]; ungrouped: Location[] };
  openGroups: Set<string>;
  allSelected: boolean;
  onToggleAll: () => void;
  onToggleLocation: (id: string) => void;
  onToggleGroup: (id: string) => void;
  onToggleGroupSelection: (id: string) => void;
  onShowWeather: (id: string) => void;
  onEditLocation: (loc: Location) => void;
  onNewLocation: () => void;
  onGroupCreated: (group: Group) => void;
  onReorder?: (sourceId: string, targetId: string) => void;  // NEW Issue #453
}
```

**Layout & Sizing (Issue #453):**
- **Width:** `240px` (fixed, no responsive variants)
- **Border:** Right border 1px, `--g-ink-faint` at 40% opacity
- **Sections (top to bottom):**
  1. Search input
  2. Constraint-Zähler (nur wenn `locations.length > 0`), TestID: `compare-rail-counter`
  3. Chip-Filter für Gruppen + Activity-Profile (optional)
  4. "Alle auswählen" Checkbox
  5. Gruppierte/Ungrupierte Locations mit Drag-Support
  6. Footer mit "+ Ort" + "+ Gruppe" Buttons

**Constraint-Zähler Farben (Issue #453):**
```
< 2:   --g-danger   (Mindestanzahl unterschritten)
2–8:   --g-success  (Gültige Bereich)
> 8:   --g-ink-muted (Obergrenze überschritten, kein Hard-Block)
```

**EmptyState (Issue #453):**
Wenn `locations.length === 0`:
- Zeigt `EmptyState` mit Title "Noch keine Orte" + Description + CTA "Ersten Ort anlegen"
- TestID des Wrapper-Divs: `compare-rail-empty`
- Normal-Render (Zähler, Filter, Liste) ist nicht sichtbar

**Drag-and-Drop (Issue #453):**
- Alle Location-Items (`<li>`) sind `draggable="true"`
- `ondragstart` setzt intern `dragSourceId`
- `ondrop` ruft optional `onReorder(sourceId, targetId)` auf
- Drop auf dasselbe Item wird ignoriert (kein Callback)
- Keine visuelle Reorder-Animation im Component selbst — Consumer (Compare-Hauptbühne) verantwortlich

**TestIDs:**
- `compare-rail` — Hauptcontainer
- `compare-rail-search` — Suchfeld
- `compare-rail-counter` — Constraint-Zähler
- `compare-rail-empty` — EmptyState-Wrapper
- `compare-rail-chip` — Gruppen-Filter-Chip
- `compare-rail-profile-chip` — Profil-Filter-Chip
- `compare-rail-new-btn` — "+ Ort"-Button
- `compare-rail-new-group-btn` — "+ Gruppe"-Button
- `ungroup-section` — Ungrupierte-Sektion-Wrapper
- `loc-name-{loc.id}` — Location-Namen-Button
- `group-section-{group.id}` — Gruppen-Sektion (aus GroupSection)

**Related (Issue #453):**
- `GroupSection.svelte` — Rendert Gruppen-Blöcke mit neuen DnD-Props `onDragStart` / `onDrop`
- `EmptyState` — UI-Komponente für Leerzustand (aus `$lib/components/ui/empty-state/`)

#### GroupSection Component (Issue #301/#453)

**File:** `frontend/src/lib/components/compare/GroupSection.svelte`

Render-Komponente für eine einzelne Gruppen-Sektion in LocationsRail. Zeigt klapbare Gruppen-Header (Chevron + Checkbox mit indeterminate-State + Profil-Dot + Name + Count) und darunter Liste mit Locations + Drag-Support.

**Props (Issue #453):**
```typescript
interface Props {
  group: Group;
  locations: Location[];
  open?: boolean;
  selectedIds: string[];
  onToggle: () => void;
  onToggleAll: () => void;
  onToggleLocation: (id: string) => void;
  onEditLocation: (loc: Location) => void;
  onShowWeather: (id: string) => void;
  onDragStart?: (id: string) => void;    // NEW Issue #453
  onDrop?: (targetId: string) => void;   // NEW Issue #453
}
```

**Drag-Support (Issue #453):**
- Alle Location-Items in der ausgeklappten Liste sind `draggable="true"`
- `ondragstart={() => onDragStart?.(loc.id)}` — Parent (LocationsRail) setzt `dragSourceId`
- `ondragover={(e) => e.preventDefault()}` — Standard DnD-Handling
- `ondrop={() => onDrop?.(loc.id)}` — Parent ruft `onReorder` auf; Logik: `if (dragSourceId !== targetId)`

**TestIDs:**
- `group-section-{group.id}` — Sektion-Wrapper
- `compare-rail-group-header` — Gruppen-Header-Zeile
- `group-count-{group.id}` — Locations-Zähler im Header

---

### edit/ — Trip-Bearbeitung

| Komponente | Pfad rel. zu components/ | Kurzbeschreibung |
|---|---|---|
| TripEditView | `edit/TripEditView.svelte` | Container der Trip-Bearbeitung |
| EditReportConfigSection | `edit/EditReportConfigSection.svelte` | Report-Konfiguration (Zeiten, Kanaele, Optionen) |
| EditRouteSection | `edit/EditRouteSection.svelte` | Routen-/Region-Bearbeitung |
| EditStagesPanelNew | `edit/EditStagesPanelNew.svelte` | Etappen-Panel |
| EditWeatherSection | `edit/EditWeatherSection.svelte` | Wetter-Metriken-Bearbeitung |
| AccordionSection | `edit/AccordionSection.svelte` | Aufklappbarer Abschnitts-Wrapper |

### email-preview/ — Email-Vorschau-Kopf

| Komponente | Pfad rel. zu components/ | Kurzbeschreibung |
|---|---|---|
| EmailPreviewHeader | `email-preview/EmailPreviewHeader.svelte` | Kopfzeile der Email-Vorschau |
| headerStats.ts | `email-preview/headerStats.ts` | Statistik-Logik fuer den Kopf (Helper) |

### preview/ — Output-Vorschau (Epic #140)

| Komponente | Pfad rel. zu components/ | Kurzbeschreibung |
|---|---|---|
| EmailIframe | `preview/EmailIframe.svelte` | Gerenderte HTML-Mail im iframe |
| SmsPhoneFrame | `preview/SmsPhoneFrame.svelte` | SMS-Vorschau im iOS-Phone-Frame |
| previewHelpers.ts | `preview/previewHelpers.ts` | Vorschau-Logik (Helper) |

### trip-detail/ — Trip-Detail-Ansicht (#302/#138/#259)

| Komponente | Pfad rel. zu components/ | Kurzbeschreibung |
|---|---|---|
| TripHeader | `trip-detail/TripHeader.svelte` | H1-Header mit Breadcrumb + Status; Titel-Bearbeitung via Stift-Icon (Issue #713) |
| TripOverview | `trip-detail/TripOverview.svelte` | 2×2 DetailCard-Grid (Uebersicht-Tab) |
| TripTabs | `trip-detail/TripTabs.svelte` | Tab-Leiste mit Badge-Zaehlern |
| TripStatusBadge | `trip-detail/TripStatusBadge.svelte` | Status-Badge des Trips |
| DetailCard | `trip-detail/DetailCard.svelte` | Karte im Uebersicht-Grid |
| StageList | `trip-detail/StageList.svelte` | Etappen-Liste |
| StageDetailRow | `trip-detail/StageDetailRow.svelte` | Etappen-Detailzeile (SVG-Icons, #322) |
| WaypointsPanel | `trip-detail/WaypointsPanel.svelte` | Panel-Wrapper fuer Wegpunkt-Editor |
| WeatherMetricsTab | `trip-detail/WeatherMetricsTab.svelte` | Wetter-Metriken-Tab |
| WeatherMetricsPreviewCard | `trip-detail/WeatherMetricsPreviewCard.svelte` | Live-Vorschau der Metriken-Tabelle |
| MetricGroup | `trip-detail/MetricGroup.svelte` | Metrik-Gruppe im Editor |
| MetricCheckbox | `trip-detail/MetricCheckbox.svelte` | Metrik-Auswahl-Checkbox |
| TablePreview | `trip-detail/TablePreview.svelte` | Tabellen-Vorschau der Metriken |
| SavePresetDialog | `trip-detail/SavePresetDialog.svelte` | Dialog zum Speichern eines Presets |
| PresetRow | `trip-detail/PresetRow.svelte` | Preset-Listenzeile |
| ActiveMetricRow | `trip-detail/ActiveMetricRow.svelte` | Aktive-Metrik-Zeile |
| BucketSection | `trip-detail/BucketSection.svelte` | Metrik-Bucket-Abschnitt |
| BucketSectionOff | `trip-detail/BucketSectionOff.svelte` | Deaktivierter Bucket-Abschnitt |
| FullProfile | `trip-detail/FullProfile.svelte` | Vollstaendige Profil-Ansicht |
| AboutOutputLayout | `trip-detail/AboutOutputLayout.svelte` | Erklaer-Layout zur Ausgabe |
| BriefingPreviewCard | `trip-detail/BriefingPreviewCard.svelte` | Briefing-Vorschau-Karte |
| ChannelPreviewCard | `trip-detail/ChannelPreviewCard.svelte` | Kanal-Vorschau-Karte |
| ChannelPreviewBlock | `trip-detail/ChannelPreviewBlock.svelte` | Kanal-Vorschau-Block |
| ChannelLimitMarkers | `trip-detail/ChannelLimitMarkers.svelte` | Zeichen-Limit-Marker (SMS) |
| PreviewCard | `trip-detail/PreviewCard.svelte` | Generische Vorschau-Karte |
| OutputLayoutEditor | `shared/OutputLayoutEditor.svelte` (re-exported via `organisms/index.ts`, Issue #475) | Universal Layout-Editor mit Channel-Tabs + Bucket-Reorder (Issue #431, reused in Compare Issue #442) |
| metricsEditor.ts | `trip-detail/metricsEditor.ts` | Metriken-Editor-Logik (Helper) — `autoAssign`, `buildWeatherConfigMetrics`, `move`, `reorder`, `CHANNEL_COL_BUDGET` |

### trip-detail/waypoints/ — Wegpunkt-Editor (Epic #137)

| Komponente | Pfad rel. zu components/ | Kurzbeschreibung |
|---|---|---|
| EtappenStrip | `trip-detail/waypoints/EtappenStrip.svelte` | Etappen-Strip mit Drag-Drop |
| MapCanvas | `trip-detail/waypoints/MapCanvas.svelte` | Leaflet-Karte mit OpenTopoMap-Tiles (Issue #495) |
| WaypointPin | `trip-detail/waypoints/WaypointPin.svelte` | Wegpunkt-Marker auf der Karte |
| PauseStageView | `trip-detail/waypoints/PauseStageView.svelte` | Ansicht fuer Pausen-Etappen |
| ProfileEditor | `trip-detail/waypoints/ProfileEditor.svelte` | Hoehenprofil-Editor |
| StageCard | `trip-detail/waypoints/StageCard.svelte` | Etappen-Karte |
| WaypointCard | `trip-detail/waypoints/WaypointCard.svelte` | Wegpunkt-Editor-Karte |

### trip-wizard/ — Trip-Wizard (Epic #136) & Reusable Stepper

Architektur + Detail siehe Abschnitt „Trip-Wizard Components" oben. Inventar-Ergaenzung:

| Komponente | Pfad rel. zu components/ | Kurzbeschreibung |
|---|---|---|
| TripWizardShell | `trip-wizard/TripWizardShell.svelte` | Shell + 5-Schritt-Stepper |
| Stepper | `trip-wizard/Stepper.svelte` | Generischer Schritt-Indikator, reusbar via `testidPrefix` + `onStepClick` Props (Issue #440) |
| Step1Profile | `trip-wizard/steps/Step1Profile.svelte` | Schritt 1: Profil + Name + Datum |
| Step2Stages | `trip-wizard/steps/Step2Stages.svelte` | Schritt 2: GPX-Upload, Drag-Sort, Pause |
| Step3Waypoints | `trip-wizard/steps/Step3Waypoints.svelte` | Schritt 3: Wegpunkt-Bestaetigung |
| Step4Briefings | `trip-wizard/steps/Step4Briefings.svelte` | Schritt 4: Briefings & Kanaele |
| Step4Layout | `trip-wizard/steps/Step4Layout.svelte` | Schritt 4 (alt.): Pro-Kanal-Layout (E-Mail/Telegram/Signal/SMS), Issue #431 |
| ChannelToggle | `trip-wizard/steps/ChannelToggle.svelte` | Kanal-Umschalter |
| ProfileChart | `trip-wizard/steps/ProfileChart.svelte` | Profil-Chart-Vorschau |
| ReportRow | `trip-wizard/steps/ReportRow.svelte` | Report-Zeile |
| StageRow | `trip-wizard/steps/StageRow.svelte` | Etappen-Zeile |
| WaypointRow | `trip-wizard/steps/WaypointRow.svelte` | Wegpunkt-Zeile |
| TemplatePicker | `trip-wizard/templates/TemplatePicker.svelte` | Vorlagen (GR20, KHW, Stubai) |
| stepperCompact.ts | `trip-wizard/stepperCompact.ts` | Kompakter Stepper-Zustand (Helper) |
| stepperState.ts | `trip-wizard/stepperState.ts` | Stepper-Zustand (Helper) |
| tripTemplates.ts | `trip-wizard/templates/tripTemplates.ts` | Vorlagen-Definitionen (Helper) |

### Top-Level (direkt in components/)

| Komponente | Pfad rel. zu components/ | Kurzbeschreibung |
|---|---|---|
| LocationForm | `LocationForm.svelte` | Formular zum Anlegen/Bearbeiten einer Location |
| SubscriptionForm | `SubscriptionForm.svelte` | Formular fuer Abonnement-/Empfaenger-Daten |
| WeatherConfigDialog | `WeatherConfigDialog.svelte` | Dialog fuer Wetter-Konfiguration, Issue #285 |

### routes/_home/ — Route-lokale Kacheln & Helpers

Pfade relativ zu `frontend/src/routes/_home/`.

| Komponente | Pfad rel. zu routes/_home/ | Kurzbeschreibung |
|---|---|---|
| TripKachel | `TripKachel.svelte` | Trip-Kachel auf der Startseite |
| CompareKachel | `CompareKachel.svelte` | Vergleichs-Kachel auf der Startseite |
| EmptyKachel | `EmptyKachel.svelte` | Platzhalter-Kachel (kein Inhalt) |
| cockpitHelpers.ts | `cockpitHelpers.ts` | Pure Helpers: `liveTrip`, `deriveNextSend` (Issue #571), `homeCompareTimeline` (Issue #647) |

## Atomic-Design-Bibliothek (Epic #368)

Kanonische Komponenten-Hierarchie, 1:1 an die Claude-Design-Sandbox angeglichen. Eine Quelle für künftige UI-Arbeit. **Vor jeder UI-Änderung die Showcase-Route `/_design-system` ansehen** (Regressions-Referenz).

| Kategorie | Pfad | Inhalt |
|---|---|---|
| **brand** | `lib/brand/` | Marken-Bausteine: BrandIcon, BrandIconSquare, BrandWordmark, BrandUserBadge, BrandSidebar, BrandShell (Issue #370) |
| **atoms** | `lib/components/atoms/` | 13 Atome: Eyebrow, Pill, Card, Btn, Input, Switch, Dot, WIcon, ElevSparkline, SectionH, AvatarStack, TopoBg, KV (Issue #371) |
| **molecules** | `lib/components/molecules/` | 10 Molecules: Field, DetailRow, StagePill, ChannelRow, ChannelChip, BriefingTimelineRow, BriefingScheduleRow, ThresholdRow, Stat, AlertRow (Issue #372) |
| **mobile** | `lib/components/mobile/` | 12 Touch-Primitive (M*): MBtn, MInput, MField, MSwitch, MTab, MIcon, TopAppBar, BottomNav, Drawer, Sheet, Toast, MobileShell (Issue #373) |

**Naming-Konvention:** Brand-only → `Brand*`. Mobile-only → `M*`. Atoms/Molecules → sprechender Name ohne Prefix. **Konflikt-Regel:** Bei Widerspruch gewinnt `brand-kit`, dann `atoms`.

**Showcase:** `routes/_design-system/+page.svelte` rendert alle Bausteine in allen Varianten (Issue #374).

# Frontend Components Reference

**Updated:** 2026-07-21 (Doku-Audit #1341 — Wizard-Sektionen und Datei-Inventar entfernt, Anlege-Editoren dokumentiert); 2026-05-25 (Issue #316 — briefing-history/ + trip-new/ Kategorien ergänzt, verwaiste Cockpit-Molekül-Referenz entfernt); 2026-07-15 (Issue #1256 Scheibe S8d — TopAppBar per-page fill pattern via `topAppBar.svelte.ts`, additive `title`/`backHref` props); 2026-06-08 (Issue #647 — Home-Screen Fidelity: homeCompareTimeline Helper); 2026-05-31; 2026-07-19 (Epic #1301 Scheibe F2b — `CompareEditor.svelte` gelöscht, TopAppBar-Referenzimplementierung entsprechend aktualisiert)  
**Version:** 1.10

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
├── trip-new/             # Progressiver Anlege-Editor /trips/new (TripNewEditor, #622)
├── compare-new/          # Progressiver Anlege-Editor /compare/new (CompareNewEditor, #1301 F2)
├── shared/               # Geteilte Tab-Organismen (context="route"|"vergleich"):
│                         #   WeatherMetricsTab, layout-tab/, versand-tab/, alarme-tab/,
│                         #   OutputLayoutEditor, corridor-editor/, dnd/
├── trip-detail/          # Trip-Detail-Ansicht + Wegpunkt-Editor
├── compare/              # Vergleichs-Screen (CompareTabs, CompareDetail, CompareMatrix, …)
├── edit/                 # Trip-Bearbeitungs-Sektionen
├── organisms/            # Barrel: lib/components/organisms/index.ts (Exporte = Wahrheit)
├── atoms/ · molecules/ · mobile/  # Atomic-Design-Bibliothek (Epic #368, s.u.)
└── alert-rules-editor/ · alerts-tab/ · briefings-tab/ · briefing-history/ · preview/ · email-preview/
```

**Wizards existieren nicht mehr.** `trip-wizard/` und `CompareWizard.svelte` wurden
ersatzlos entfernt (#622, Epic #1273/#1301); Anlegen läuft über die progressiven
Tab-Editoren `TripNewEditor`/`CompareNewEditor` mit Auto-Save. Absicherung:
`shared/__tests__/legacy_wizard_removed.test.ts`.

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
import { ConfirmDialog, DetailRow, ChannelRow, AlertRow, Stat } from '$lib/components/molecules';
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

All Gregor atoms reference design tokens defined in `app.css` `@layer base`. See `docs/specs/_archive/modules/epic_133_design_system_lauf_a.md` for the full token list.

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

Fixed header bar for mobile viewports (< 900px). This is the ONE globally
mounted instance (in `+layout.svelte`); on unfilled pages it shows the
default hamburger + Wordmark + Bell/Plus. Since Issue #1256 Scheibe S8d it
can be **filled per-page** (title/eyebrow/back/right action) — see
"Per-Page Fill Pattern" below.

**Props (Updated 2026-07-15, Issue #1256 S8d — additive over #267/#373):**
```typescript
interface Props {
  mobileMenuOpen?: boolean;   // #267: hamburger drawer toggle
  darkMode?: boolean;         // #267 (optional, default false)
  ontoggleDark?: () => void;  // #267 (optional)
  eyebrow?: string;           // #373: small all-caps line above title
  leftIcon?: string;          // #373/#1256-S8d: 'back' renders a back-arrow
                               // link (→ backHref) instead of the hamburger
  right?: Snippet;            // #373: replaces the default Bell/Plus group
  dense?: boolean;            // #373: compact title size
  scrolled?: boolean;         // #373: scroll-state styling hook
  title?: string;             // #1256-S8d: replaces the Wordmark default
                               // when set
  backHref?: string;          // #1256-S8d: target for leftIcon="back"
                               // (default '/')
}
```

**Layout:**
- **Height:** 56px, `position: fixed; top: 0; left: 0; right: 0; z-index: 60`
- **Background:** `var(--g-paper)`
- **Border:** `1px solid var(--g-rule-soft)` (bottom)
- **Visibility:** Mobile only (`class="desktop:hidden"`)

**Sections:**
1. **Left:** Hamburger button (Menu/X icon), or a back-arrow link when
   `leftIcon="back"` (navigates to `backHref`)
2. **Center:** `title` (+ optional `eyebrow` above it) if filled, otherwise
   the Wordmark default
3. **Right:** page-supplied `right` snippet if given, otherwise the default
   Bell (disabled) + Plus→`/trips/new` group

**Usage (unfilled, #267 default):**
```svelte
import TopAppBar from '$lib/components/ui/sidebar/TopAppBar.svelte';

let mobileMenuOpen = $state(false);
// ... in template:
<TopAppBar bind:mobileMenuOpen />
```

### Per-Page Fill Pattern (Issue #1256 Scheibe S8d)

Pages can populate the single global `TopAppBar` instance instead of
mounting their own header. This replaced an earlier anti-pattern (a
hand-rebuilt `cm-mobile-appbar` inside `CompareEditor.svelte`) per the
PO rule "use/extend the Design component, never rebuild it in-page"
(2026-07-15).

**Store:** `frontend/src/lib/stores/topAppBar.svelte.ts` — a small Runes
singleton (`topAppBarStore`, `fill: $state<TopAppBarFill>({})`) since there
is exactly one mounted `TopAppBar`.

**Contract:**
- A page/component calls `topAppBarStore.set({ title, eyebrow, leftIcon,
  backHref, right })` in an `$effect` on mount and `topAppBarStore.reset()`
  on cleanup (SvelteKit navigation away from the page).
- `+layout.svelte` reads `topAppBarStore.fill` and spreads it onto the one
  `<TopAppBar>` mount — no other page is affected.
- Default (`fill = {}`) reproduces the exact pre-#1256-S8d appearance
  (Wordmark + Bell + Plus→`/trips/new`), so pages that never call `set()`
  are unchanged.

**Reference implementations:** `frontend/src/routes/compare/+page.svelte`
(mobile list header: title "Orts-Vergleiche", eyebrow "Workspace · N",
right = Plus→`/compare/new`). *(Der frühere zweite Referenzfall,
`frontend/src/lib/components/compare/CompareEditor.svelte` — mobile editor
header mit aktivem Tab-Namen/Compare-Name/Zurück-Icon — ist mit Epic #1301
Scheibe F2b am 2026-07-19 gelöscht; die Datei existiert nicht mehr.)*

**Reuse note:** this is a generic pattern, not Compare-specific — intended
to be reused by Trip pages during the Trip/Compare convergence work
(Epic #1230) rather than re-invented per surface.

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

## Anlege-Editoren (statt Wizards)

`/trips/new` und `/compare/new` sind progressive Tab-Anlege-Seiten aus geteilten
Bausteinen — **kein** Multi-Step-Wizard mit Stepper (abgeschafft, PO-bekräftigt
2026-07-19):

| Route | Editor | Logik |
|---|---|---|
| `/trips/new` | `trip-new/TripNewEditor.svelte` (#622) | `trip-new/tripNewLogic.ts` (Freischalt-/Fortschritts-Logik, reine Funktionen) |
| `/compare/new` | `compare-new/CompareNewEditor.svelte` (#1301 F2) | `compare-new/compareNewLogic.ts` |

Beide nutzen die geteilten Tab-Organismen aus `shared/` (`context="route"|"vergleich"`).
Persistenz: Auto-Save gegen `/api/trips` bzw. `/api/compare/presets` — nicht
`/api/subscriptions` (entfernt, liefert 404).

---

## Komponenten-Inventar: Dateisystem ist die Wahrheit

Frühere Fassungen dieses Dokuments pflegten Datei-für-Datei-Tabellen aller
Komponenten. Die veralteten zwangsläufig (gelöschte Wizards, umbenannte
Komponenten) und wurden 2026-07-21 entfernt. Regel:

- **Inventar:** `ls frontend/src/lib/components/<ordner>/` — nie hier abschreiben.
- **Organisms-Exporte:** `lib/components/organisms/index.ts` lesen, nicht raten.
- **Props/Verhalten:** jeweilige `.svelte`-Datei + co-located Tests.
- **Route-lokale Bausteine:** unter `frontend/src/routes/` (z. B. `_home/` Kacheln,
  `_design-system/` Showcase).

Konzeptionelles (Atome mit Beispielen, Design Tokens, App-Shell-Navigation,
Naming-Regeln) steht weiterhin in diesem Dokument — siehe Sektionen oben/unten.

---

## Atomic-Design-Bibliothek (Epic #368)

Kanonische Komponenten-Hierarchie, 1:1 an die Claude-Design-Sandbox angeglichen. Eine Quelle für künftige UI-Arbeit. **Vor jeder UI-Änderung die Showcase-Route `/_design-system` ansehen** (Regressions-Referenz).

| Kategorie | Pfad | Inhalt |
|---|---|---|
| **brand** | `lib/brand/` | Marken-Bausteine: BrandIcon, BrandIconSquare, BrandWordmark, BrandUserBadge, BrandSidebar, BrandShell (Issue #370) |
| **atoms** | `lib/components/atoms/` | 13 Atome: Eyebrow, Pill, Card, Btn, Input, Switch, Dot, WIcon, ElevSparkline, SectionH, AvatarStack, TopoBg, KV (Issue #371) |
| **molecules** | `lib/components/molecules/` | 9 Molecules: Field, DetailRow, ChannelRow, ChannelChip, BriefingTimelineRow, BriefingScheduleRow, ThresholdRow, Stat, AlertRow (Issue #372) |
| **mobile** | `lib/components/mobile/` | 12 Touch-Primitive (M*): MBtn, MInput, MField, MSwitch, MTab, MIcon, TopAppBar, BottomNav, Drawer, Sheet, Toast, MobileShell (Issue #373) |

**Naming-Konvention:** Brand-only → `Brand*`. Mobile-only → `M*`. Atoms/Molecules → sprechender Name ohne Prefix. **Konflikt-Regel:** Bei Widerspruch gewinnt `brand-kit`, dann `atoms`.

**Showcase:** `routes/_design-system/+page.svelte` rendert alle Bausteine in allen Varianten (Issue #374).

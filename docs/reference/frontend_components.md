# Frontend Components Reference

**Updated:** 2026-05-09  
**Version:** 1.0

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
│   └── elev-sparkline/   # GREGOR atom (Issue #146)
│
└── layout/
    └── Sidebar.svelte    # Main navigation (Issue #145)
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

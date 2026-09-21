# Frontend Components Reference

**Updated:** 2026-09-21 (Issue #1895 — Alert-Rules-Editor kennt nur noch den Änderungs-Modus; `ModeCard` gelöscht, Modus-Toggle und Absolut-Feld aus `AlertRuleRow` entfernt); 2026-09-19 (Mobile-Shell S2 — `TopAppBar`, `topAppBarStore` und Hamburger-Drawer entfernt; Konto-Kreis + `KontoSheet`, `PageHeader back`, `EditorStickyFooter`, Safe-Area oben); 2026-08-03 (Issue #1196 S1 — Wordmark-Props + 10 real existierende Komponenten ergänzt: MapCanvas, WaypointPin, ProfileEditor, StageCard, WaypointCard, PauseStageView, AlertRulesEditor, AlertRuleRow, ModeCard, LocationPreviewMap); 2026-07-21 (Doku-Audit #1341 — Wizard-Sektionen und Datei-Inventar entfernt, Anlege-Editoren dokumentiert); 2026-05-25 (Issue #316 — briefing-history/ + trip-new/ Kategorien ergänzt, verwaiste Cockpit-Molekül-Referenz entfernt); 2026-07-15 (Issue #1256 Scheibe S8d — TopAppBar per-page fill pattern via `topAppBar.svelte.ts`, additive `title`/`backHref` props); 2026-06-08 (Issue #647 — Home-Screen Fidelity: homeCompareTimeline Helper); 2026-05-31; 2026-07-19 (Epic #1301 Scheibe F2b — `CompareEditor.svelte` gelöscht, TopAppBar-Referenzimplementierung entsprechend aktualisiert)  
**Version:** 1.12

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
│       ├── BottomNav.svelte    # Schwebende Glas-Bottom-Nav + Konto-Kreis (mobile-only)
│       ├── KontoSheet.svelte   # Konto-Sheet (Mobile-Shell S2, ersetzt den Drawer)
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

### Wordmark Component

**File:** `frontend/src/lib/components/ui/wordmark/Wordmark.svelte` (thin
wrapper, delegiert an `lib/brand/BrandWordmark.svelte` — die kanonische
Brand-Bibliothek, Issue #370). Rendert das Gregor-Zwanzig-Logo: Desktop in
der Sidebar, mobil als erste Zeile der Übersicht (`size="sm"`, nur auf `/`,
Mobile-Shell S2 — kein fixer Balken mehr).

**Props:**
```typescript
interface WordmarkProps {
  size?: 'sm' | 'md' | 'lg';  // default: 'md' — 'sm' zeigt keinen Untertitel
  href?: string;              // default: '/'
}
```

**Example:**
```svelte
<Wordmark size="sm" href="/" />
```

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

### Kein Top-Balken mehr (Mobile-Shell S2)

Seit 2026-09-19 gibt es auf Mobile **keinen fixen Balken oben** und keinen
Hamburger-Drawer (`docs/design-requests/mobile_shell_ohne_topbar.md`, PO-
Entscheide §8). Ersatz:

| Früher im Balken | Jetzt |
|---|---|
| Wordmark | Erste Zeile der Übersicht (`routes/+page.svelte`, `data-testid="home-wordmark-row"`, mit Datum als Mono-Caption) |
| Seitentitel/Eyebrow via `topAppBarStore` | `<PageHeader eyebrow title>` der Seite (AP-011); Store gelöscht |
| `leftIcon: back` + `backHref` | `<PageHeader back={{ href, label }}>` — rendert `<BackLink>` (Atom) über dem Eyebrow; auch allein nutzbar (Compare-Hub) |
| Rechts-Slot („Neuer Vergleich", „Aktivieren") | Rechts-Slot des `<PageHeader>` bzw. `<EditorStickyFooter context="vergleich">` (geteilter Sticky-Footer, `shared/`) |
| Hamburger → Drawer | **Konto-Kreis** in `BottomNav` → `<KontoSheet>` |
| Glocke / Plus | entfallen (AP-004/AP-012) |

**Safe-Area oben:** `.mobile-scroll-pad { padding-top: calc(env(safe-area-inset-top) + var(--g-s-3)) }`.
Die Offline-Bänder (`#gz-stand`, `[data-gz-offline-band]`) sind die erste Zeile
des Dokuments und tragen die Safe-Area selbst (`app.css`), `<main>` gibt seinen
Anteil dann ab. `apple-mobile-web-app-status-bar-style` bleibt `default`.

### KontoSheet Component

**File:** `frontend/src/lib/components/ui/sidebar/KontoSheet.svelte`

Konto-Sheet aus `mobile/Sheet.svelte` (`snap="auto"`, inhaltshoch). Vom
`+layout.svelte` gemountet, geöffnet über den Konto-Kreis der `BottomNav`,
schließt bei jeder Navigation (`afterNavigate`).

**Props:** `open`, `onClose`, `initials` (aus `$lib/utils/initialen`), `displayName`, `userId`, `darkMode`, `ontoggleDark`.

**Inhalt (PO 2026-09-19, keine Benachrichtigungen-Zeile):** Kopf (Avatar 44 px
Akzent, Name, Schließen) · Kanäle & Empfänger (`/account#kanaele`) ·
Einstellungen (`/account`) · System-Status (`/account#system-status`) ·
Dunkles Design (`<Switch>`) · Datenexport (`/account#datenexport`) · Fuß mit
Version + Abmelden (`POST /logout`). TestIDs: `konto-sheet`, `konto-sheet-*`.

### BottomNav Component

**File:** `frontend/src/lib/components/ui/sidebar/BottomNav.svelte`

Schwebende Glas-Leiste (iOS-27-Stil) für Mobile-Viewports (< 900px). 4 Workspace-Ziele mit Aktiv-Kapsel. Konzept: `docs/design-requests/mobile_shell_ohne_topbar.md`.

**Props:** `active?: string` (überschreibt die Routen-Erkennung), `onChange?: (id) => void` — ohne Props Routen-Erkennung via `$app/state`. **Konto-Kreis (S2):** `initials`, `onKonto`, `kontoOpen` — nur mit `onKonto` gerendert (`data-testid="konto-kreis"`, 64 × 64 Glas, Avatar 36 px Akzent, `aria-haspopup="dialog"`). Rahmen `bottom-shell` (flex, `--g-nav-konto-gap`) trägt die Position; Leiste und Kreis teilen das Glas (`.nav-glass`).

**Layout (alle Werte aus den `--g-nav-*` Tokens in `app.css`):**
- `position: fixed; z-index: 50`, `left/right: var(--g-nav-inset)` (16px), `bottom: calc(var(--g-nav-gap) + env(safe-area-inset-bottom))` (6px über der Home-Indicator-Zone)
- **Height:** `var(--g-nav-h)` (64px), innen `padding: var(--g-s-1)`, Radius `--g-r-pill`
- **Glas:** `background: var(--g-nav-glass)` (paper, 86 %) + `backdrop-filter: blur(var(--g-nav-blur)) saturate(180%)`, `1px solid var(--g-nav-hairline)`, `--g-shadow-3` + innere Highlight-Linie
- **Fallback:** ohne `backdrop-filter`-Support oder bei `prefers-reduced-transparency: reduce` opak `--g-paper-deep`
- **Grid:** 4 gleiche Spalten, `gap: var(--g-s-1)`
- **Visibility:** Mobile only (`class="desktop:hidden"`)
- **Oberkante für Dritte:** `--g-nav-clearance` = `--g-nav-h + --g-nav-gap + safe-area`; `.mobile-scroll-pad`, Toast-Anker in `+layout.svelte` und `SaveIndicator` rechnen damit — nie mit 64px hart.

**Navigation Items:**

| Icon | Label | Route |
|------|-------|-------|
| LayoutDashboard | Übersicht | `/` |
| Route | Trips | `/trips` |
| GitCompare | Vergleich | `/compare` |
| Archive | Archiv | `/archiv` |

**Per-Item Styling:**
- **Touch-Ziel:** `min-height: 44px`, Radius `--g-r-pill`
- **Active State:** Kapsel `background: var(--g-nav-active)` (Akzent 12 %), Icon `--g-accent`, Label `--g-ink` / 600, `aria-current="page"`
- **Inactive State:** kein Hintergrund, Icon + Label `--g-ink-2` / 500
- **Icon Size:** 24px (`size-6`)
- **Label Size:** `--g-text-xs` (11px)
- **E2E:** `frontend/e2e/mobile-bottom-nav-floating.spec.ts` (Geometrie + Computed Style)

**Usage:**
```svelte
import BottomNav from '$lib/components/ui/sidebar/BottomNav.svelte';

// ... in template:
<BottomNav />
```

### Layout Integration

The shell is orchestrated in `frontend/src/routes/+layout.svelte`:

```svelte
<script>
  import BottomNav from '$lib/components/ui/sidebar/BottomNav.svelte';
  import KontoSheet from '$lib/components/ui/sidebar/KontoSheet.svelte';
  import { initialen } from '$lib/utils/initialen';

  let kontoOpen = $state(false);
  const kontoInitialen = $derived(initialen(data.displayName, data.userId));
</script>

<div class="flex h-screen">
  <Sidebar ... />
  <main class="mobile-scroll-pad flex-1 overflow-auto px-4 desktop:p-6">
    {@render children()}
  </main>
</div>

<BottomNav initials={kontoInitialen} {kontoOpen} onKonto={() => (kontoOpen = true)} />
<KontoSheet open={kontoOpen} onClose={() => (kontoOpen = false)} ... />
```

**Responsive Breakpoint:** 900px (custom `@custom-variant` in `app.css`)
- **< 900px:** BottomNav + Konto-Kreis visible, kein Balken oben, Sidebar hidden
- **>= 900px:** BottomNav hidden, Sidebar full sidebar (unchanged)

**CSS Utilities:**
- `--g-nav-*` — Geometrie und Glas der schwebenden Leiste (`docs/design-system/TOKENS.md`)
- `--g-rule-soft` — Border/divider color (soft ink at 8% opacity)
- `.mobile-scroll-pad` — Padding-top `calc(env(safe-area-inset-top) + var(--g-s-3))`, Padding-bottom `calc(var(--g-nav-clearance) + var(--g-s-4))`
- `@custom-variant mobile` — Matches viewport < 900px
- `@custom-variant desktop` — Matches viewport >= 900px

### Sidebar Component Updates
- Desktop-only (`hidden desktop:flex`); der mobile Drawer wurde mit Mobile-Shell S2 entfernt
- All `md:` Tailwind breakpoint classes → `desktop:` (900px instead of 768px)
- Konto, Status, Dark Mode, Logout: Desktop im User-Badge-Dropdown, mobil im `KontoSheet`

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

## Trip-Detail Wegpunkt-Editor (`trip-detail/waypoints/`)

Rechte-Spalte-Bausteine des Wegpunkt-Editors (Epic #137), gemeinsam genutzt
von Trip-Editor und Trip-Detail-Ansicht:

- **`MapCanvas.svelte`** — Leaflet-Kartenfläche einer Etappe; Pin-Klick ruft
  `onWaypointActivate(waypointId)`, optionaler `onMapClick(lat, lon)` zum
  Einfügen neuer Wegpunkte, `fillHeight` für den mobilen Vollbild-Container
  (Issue #963).
- **`WaypointPin.svelte`** — SVG-Pin-Marker (Kreis + Nummer + Spitze) für
  Karte und Höhenprofil; Props `index`, `active`, `onclick`, `size`.
- **`ProfileEditor.svelte`** — SVG-Höhenprofil (360×140) mit klickbaren Pins;
  analog `ProfileChart.svelte`, erweitert um Gridlines + `onWaypointActivate`.
- **`StageCard.svelte`** — kompakte Etappen-Karte (Mini-Höhenprofil, Distanz)
  für die Etappenliste; Design-Fidelity 1:1 (Issue #585).
- **`WaypointCard.svelte`** — Listeneintrag für einen Wegpunkt (Name, Typ,
  Höhe, Ankunftszeit); aktiver Zustand zeigt Umbenennen/Verschieben/Löschen.
- **`PauseStageView.svelte`** — Ansicht für einen Pausentag (editierbares
  Datum via `StageDateField`, Standort aus Vorgänger-/Folge-Etappe).

## Alert-Rules-Editor (`alert-rules-editor/`)

Liste-basierter Editor für `Trip.alert_rules` (Issue #223/#179):

Seit Issue #1895 (2026-09-21) kennt der Editor nur noch den Änderungs-Modus
(Δ, `kind: 'delta'`); die Modus-Auswahl (Absolut/Änderung/Beides), die Komponente
`ModeCard` und das Absolut-Feld `alert-rule-threshold-abs` sind entfernt.

- **`AlertRulesEditor.svelte`** — Container: Empty-State, Liste, Add-Button;
  `updateRules(index, updated[])` ersetzt eine Regel durch die von der Zeile
  gelieferte Regelliste (seit #1895 genau eine Regel).
- **`AlertRuleRow.svelte`** — eine Zeile pro `AlertRule` mit View- und
  Edit-Modus (Metric-Select, Δ-Schwelle `alert-rule-threshold`, Zeitfenster
  `alert-rule-delta-window`, Kanal-Chips, Aktiv-Checkbox).
- **`alertRuleDefaults.ts`** — `newDefaultRule()` liefert `kind: 'delta'`,
  `threshold: 20`, `delta_window: '6h'`; `expandRules()` liefert je Eingaberegel
  genau eine Regel mit `kind: 'delta'` und ohne `pair_id` (kein Regelpaar mehr).

## Compare Components (`compare/`)

- **`LocationPreviewMap.svelte`** — Mini-Karten-Vorschau (Topo-Hintergrund +
  zentrierter Pin) für einen Ort im Ortsvergleich-Anlege-Fluss; Props `lat`,
  `lon`.

## Account Components (`account/`)

- **`PremiumSmsLinkCard.svelte`** — Karte im Konto-Bereich (`/account`) für
  Premium-Nutzer: erzeugt/erneuert den Premium-SMS-Verknüpfungscode (Issue
  #2154 Scheibe B). Der Klartext-Code wird nur einmalig nach erfolgreichem
  `POST` angezeigt, nie erneut ausgeliefert (fail-closed über
  `premiumSmsLinkCodeExists`).

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
| **mobile** | `lib/components/mobile/` | 11 Touch-Primitive (M*): MBtn, MInput, MField, MSwitch, MTab, MIcon, BottomNav, Drawer, Sheet, Toast, MobileShell (Issue #373; TopAppBar seit Mobile-Shell S2 entfernt) |

**Naming-Konvention:** Brand-only → `Brand*`. Mobile-only → `M*`. Atoms/Molecules → sprechender Name ohne Prefix. **Konflikt-Regel:** Bei Widerspruch gewinnt `brand-kit`, dann `atoms`.

**Showcase:** `routes/_design-system/+page.svelte` rendert alle Bausteine in allen Varianten (Issue #374).

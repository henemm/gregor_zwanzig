---
entity_id: issue_214_btn_feature_parity
type: module
created: 2026-05-13
updated: 2026-05-13
status: draft
version: "1.0"
parent_spec: epic_133_design_system
issues: [214]
parent_epic: 133
parent_umbrella: 212
followup_issues: [215, 216]
tags: [frontend, sveltekit, design-system, epic-133, issue-214, button-consolidation]
---

# Issue #214 — Btn-Feature-Parität (Phase A der Button-Konsolidierung)

## Approval

- [ ] Approved

## Purpose

Die Design-System-Komponente `Btn` (Token-basiert, `data-slot`-Pattern, CSS in `app.css`) wird um genau die Features erweitert, die heute die parallele `Button`-Komponente (shadcn/Tailwind-Variante) bereitstellt: 7 Variants (`primary`, `accent`, `outline`, `ghost`, `secondary`, `destructive`, `link`), 8 Sizes (`xs`, `sm`, `md`, `lg`, `icon`, `icon-xs`, `icon-sm`, `icon-lg`), `href`-Switch mit korrektem `<a>`/`<button>`-Rendering, `disabled`-State (inkl. WAI-ARIA-Pattern für disabled Links), Icon-Sizing pro Size und vollständige Showcase-Coverage im `/_design`-Verzeichnis. Damit wird `Btn` zum Drop-in-Replacement, das Phase B (#215 — Migration der 94 Button-Aufrufstellen) und Phase C (#216 — Entfernen der alten Button-Komponente) ermöglicht; die Arbeit ist reine Frontend-Arbeit ohne Backend-Berührung.

## Source

- **EDIT:** `frontend/src/lib/components/ui/btn/Btn.svelte` — Props-Interface erweitern, href-Switch einbauen, disabled-Rendering
- **EDIT:** `frontend/src/lib/components/ui/btn/index.ts` — neue Type-Exports `BtnVariant`, `BtnSize`, `BtnProps`
- **EDIT:** `frontend/src/app.css` — Btn-CSS-Block (Z. 127–149) komplett ersetzen + erweitern
- **EDIT:** `frontend/src/routes/_design/+page.svelte` — Showcase um 3 Sektionen (Variants, Sizes, States) erweitern
- **NEU:** `frontend/src/lib/components/ui/btn/Btn.test.ts` — Vitest-Unit-Tests
- **NEU:** `frontend/e2e/btn-feature-parity.spec.ts` — Playwright-Smoke-Tests im `/_design`
- **Identifier:** Svelte-Komponente `Btn`, Props-Types `BtnVariant`, `BtnSize`, `BtnProps`
- **Referenz (NICHT editieren):** `frontend/src/lib/components/ui/button/button.svelte` — Variants/Sizes/href-Pattern als Vorlage

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/src/lib/components/ui/btn/Btn.svelte` | bestehend (EDIT) | Erweiterung des Props-Interface, Render-Logik mit href-Switch |
| `frontend/src/lib/components/ui/btn/index.ts` | bestehend (EDIT) | Re-Export der neuen Typen `BtnVariant`, `BtnSize`, `BtnProps` |
| `frontend/src/app.css` Z. 127–149 | bestehend (EDIT) | CSS-Block für Btn wird vollständig ersetzt durch Variants/Sizes/Disabled/Icon-Sizing-Selektoren |
| `frontend/src/lib/components/ui/button/button.svelte` | bestehend (REFERENZ) | Variants/Sizes/href-disabled-Pattern werden inhaltlich übernommen, Komponente selbst bleibt unverändert |
| `frontend/src/routes/_design/+page.svelte` | bestehend (EDIT) | Showcase wird um 3 strukturierte Sektionen erweitert |
| `frontend/src/lib/utils.js` (`cn`, `WithElementRef`) | bestehend | Helper für className-Merge und Element-Ref-Typing |
| `svelte/elements` (`HTMLButtonAttributes`, `HTMLAnchorAttributes`) | bestehend | Type-Basis für Restprops |
| `--g-*`-Design-Tokens (`--g-ink`, `--g-paper`, `--g-accent`, `--g-surface-2`, `--g-danger`, `--g-radius-md`, `--g-text-sm` u.a.) | bestehend | Quelle für alle Farb-, Spacing- und Radius-Werte |
| 8 bestehende Aufrufstellen (TripWizardShell + `/_design`) | bestehend | Regressions-Guard — müssen unverändert funktionieren, Variants werden explizit angegeben |

## Implementation Details

### §1 `Btn.svelte` — neues Props-Interface

Vollständiges `<script lang="ts" module>`-Block am Datei-Anfang:

```typescript
import { cn, type WithElementRef } from "$lib/utils.js";
import type { HTMLAnchorAttributes, HTMLButtonAttributes } from "svelte/elements";
import type { Snippet } from "svelte";

export type BtnVariant =
  | "primary"
  | "accent"
  | "outline"
  | "ghost"
  | "secondary"
  | "destructive"
  | "link";

export type BtnSize =
  | "xs"
  | "sm"
  | "md"
  | "lg"
  | "icon"
  | "icon-xs"
  | "icon-sm"
  | "icon-lg";

export type BtnProps = WithElementRef<HTMLButtonAttributes> &
  Partial<HTMLAnchorAttributes> & {
    variant?: BtnVariant;
    size?: BtnSize;
    href?: string;
    disabled?: boolean;
    children?: Snippet;
  };
```

`<script lang="ts">`:

```typescript
let {
  class: className,
  variant = "primary",
  size = "md",
  ref = $bindable(null),
  href = undefined,
  type = "button",
  disabled = false,
  children,
  ...restProps
}: BtnProps = $props();
```

**Default-Wechsel:** `variant` Default von `accent` (Ist) → `primary` (Soll, D5). Die 8 bestehenden Aufrufstellen geben den Variant explizit an und brechen damit nicht.

### §2 `Btn.svelte` — Render-Logik (href-Switch + disabled)

```svelte
{#if href}
  <a
    bind:this={ref}
    data-slot="btn"
    data-variant={variant}
    data-size={size}
    class={cn(className)}
    href={disabled ? undefined : href}
    aria-disabled={disabled ? "true" : undefined}
    role={disabled ? "link" : undefined}
    tabindex={disabled ? -1 : undefined}
    {...restProps}
  >
    {@render children?.()}
  </a>
{:else}
  <button
    bind:this={ref}
    data-slot="btn"
    data-variant={variant}
    data-size={size}
    class={cn(className)}
    {type}
    {disabled}
    {...restProps}
  >
    {@render children?.()}
  </button>
{/if}
```

**Schlüssel-Regeln (D7):**

- Beide Pfade setzen IMMER `data-slot="btn"`, `data-variant`, `data-size` (Selektor-Anker für CSS).
- `href` + `disabled` → `href` wird auf `undefined` gesetzt (Attribut entfällt im DOM), `aria-disabled="true"`, `tabindex="-1"`, `role="link"` — WAI-ARIA-Pattern für nicht-navigierbare Links.
- `button` + `disabled` → natives HTML `disabled`-Attribut.

### §3 `app.css` — Btn-Block ersetzen (Z. 127–149)

Kompletter Ersatz des bestehenden Blocks. Struktur in dieser Reihenfolge:

```css
  /* === Issue #214: Btn — Feature-Parität (7 Variants × 8 Sizes + States) === */

  /* Base */
  [data-slot="btn"] {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: var(--g-s-2, 8px);
    font-family: inherit;
    font-weight: 500;
    line-height: 1.2;
    border-radius: var(--g-radius-md);
    border: 1px solid transparent;
    cursor: pointer;
    user-select: none;
    white-space: nowrap;
    text-decoration: none;
    transition: background-color 120ms ease, border-color 120ms ease, color 120ms ease;
  }
  [data-slot="btn"]:focus-visible {
    outline: 2px solid var(--g-accent);
    outline-offset: 2px;
  }

  /* Sizes */
  [data-slot="btn"][data-size="xs"]      { padding: 4px 8px;   font-size: var(--g-text-xs, 11px); min-height: 24px; }
  [data-slot="btn"][data-size="sm"]      { padding: 6px 10px;  font-size: var(--g-text-sm, 13px); min-height: 28px; }
  [data-slot="btn"][data-size="md"]      { padding: 8px 14px;  font-size: var(--g-text-sm, 13px); min-height: 32px; }
  [data-slot="btn"][data-size="lg"]      { padding: 10px 18px; font-size: var(--g-text-md, 15px); min-height: 36px; }
  [data-slot="btn"][data-size="icon"]    { padding: 0; width: 32px; height: 32px; min-height: 32px; }
  [data-slot="btn"][data-size="icon-xs"] { padding: 0; width: 24px; height: 24px; min-height: 24px; }
  [data-slot="btn"][data-size="icon-sm"] { padding: 0; width: 28px; height: 28px; min-height: 28px; }
  [data-slot="btn"][data-size="icon-lg"] { padding: 0; width: 36px; height: 36px; min-height: 36px; }

  /* Variants — D1, D2 */
  [data-slot="btn"][data-variant="primary"] {
    background-color: var(--g-ink);
    color: var(--g-paper);
    border-color: var(--g-ink);
  }
  [data-slot="btn"][data-variant="primary"]:hover {
    background-color: color-mix(in oklab, var(--g-ink) 88%, var(--g-paper));
  }

  [data-slot="btn"][data-variant="accent"] {
    background-color: var(--g-accent);
    color: var(--g-paper);
    border-color: var(--g-accent);
  }
  [data-slot="btn"][data-variant="accent"]:hover {
    background-color: color-mix(in oklab, var(--g-accent) 90%, black);
  }

  [data-slot="btn"][data-variant="outline"] {
    background-color: transparent;
    color: var(--g-ink);
    border-color: var(--g-ink);
  }
  [data-slot="btn"][data-variant="outline"]:hover {
    background-color: var(--g-surface-2);
  }

  [data-slot="btn"][data-variant="ghost"] {
    background-color: transparent;
    color: var(--g-ink);
    border-color: transparent;
  }
  [data-slot="btn"][data-variant="ghost"]:hover {
    background-color: var(--g-surface-2);
  }

  [data-slot="btn"][data-variant="secondary"] {
    background-color: var(--g-surface-2);
    color: var(--g-ink);
    border-color: var(--g-surface-2);
  }
  [data-slot="btn"][data-variant="secondary"]:hover {
    background-color: color-mix(in oklab, var(--g-surface-2) 85%, var(--g-ink));
  }

  [data-slot="btn"][data-variant="destructive"] {
    background-color: rgba(179, 58, 42, 0.10);
    color: var(--g-danger);
    border: 1px solid var(--g-danger);
  }
  [data-slot="btn"][data-variant="destructive"]:hover {
    background-color: rgba(179, 58, 42, 0.18);
  }

  [data-slot="btn"][data-variant="link"] {
    background-color: transparent;
    color: var(--g-accent);
    border-color: transparent;
    padding-left: 0;
    padding-right: 0;
    text-underline-offset: 4px;
  }
  [data-slot="btn"][data-variant="link"]:hover {
    text-decoration: underline;
  }

  /* Icon-Sizing (D6) — Descendant-Selektor */
  [data-slot="btn"] > svg                        { width: 1rem;     height: 1rem;     flex-shrink: 0; }
  [data-slot="btn"][data-size="xs"] > svg        { width: 0.875rem; height: 0.875rem; }
  [data-slot="btn"][data-size="sm"] > svg        { width: 0.875rem; height: 0.875rem; }
  [data-slot="btn"][data-size="md"] > svg        { width: 1rem;     height: 1rem;     }
  [data-slot="btn"][data-size="lg"] > svg        { width: 1.125rem; height: 1.125rem; }
  [data-slot="btn"][data-size="icon-xs"] > svg   { width: 0.875rem; height: 0.875rem; }
  [data-slot="btn"][data-size="icon-sm"] > svg   { width: 1rem;     height: 1rem;     }
  [data-slot="btn"][data-size="icon"] > svg      { width: 1rem;     height: 1rem;     }
  [data-slot="btn"][data-size="icon-lg"] > svg   { width: 1.125rem; height: 1.125rem; }

  /* Disabled-State */
  [data-slot="btn"][disabled],
  [data-slot="btn"][aria-disabled="true"] {
    opacity: 0.5;
    pointer-events: none;
    cursor: not-allowed;
  }
```

**Spezifizitäts-Hinweis:** Alle Selektoren haben dieselbe Spezifizität (Attribute-Selektor mit `data-slot`); damit greift ein vom Aufrufer per `class`-Prop mitgegebener Tailwind-Override weiter (kommt nach Variant-CSS in der Stylesheet-Reihenfolge).

### §4 `index.ts` — Type-Re-Exports

```typescript
export { default as Btn } from "./Btn.svelte";
export type { BtnVariant, BtnSize, BtnProps } from "./Btn.svelte";
```

### §5 `_design/+page.svelte` — Showcase erweitern (D3)

Drei strukturierte Sektionen mit eindeutigen `data-testid`-Attributen:

```svelte
<section>
  <h2>Btn — Variants</h2>
  <div class="flex gap-2 flex-wrap">
    <Btn variant="primary"     data-testid="btn-showcase-variant-primary">Primary</Btn>
    <Btn variant="accent"      data-testid="btn-showcase-variant-accent">Accent</Btn>
    <Btn variant="outline"     data-testid="btn-showcase-variant-outline">Outline</Btn>
    <Btn variant="ghost"       data-testid="btn-showcase-variant-ghost">Ghost</Btn>
    <Btn variant="secondary"   data-testid="btn-showcase-variant-secondary">Secondary</Btn>
    <Btn variant="destructive" data-testid="btn-showcase-variant-destructive">Delete</Btn>
    <Btn variant="link"        data-testid="btn-showcase-variant-link">Link</Btn>
  </div>
</section>

<section>
  <h2>Btn — Sizes</h2>
  <div class="flex gap-2 items-center flex-wrap">
    <Btn size="xs"      data-testid="btn-showcase-size-xs"><Pencil />XS</Btn>
    <Btn size="sm"      data-testid="btn-showcase-size-sm"><Pencil />SM</Btn>
    <Btn size="md"      data-testid="btn-showcase-size-md"><Pencil />MD</Btn>
    <Btn size="lg"      data-testid="btn-showcase-size-lg"><Pencil />LG</Btn>
    <Btn size="icon-xs" data-testid="btn-showcase-size-icon-xs"><Pencil /></Btn>
    <Btn size="icon-sm" data-testid="btn-showcase-size-icon-sm"><Pencil /></Btn>
    <Btn size="icon"    data-testid="btn-showcase-size-icon"><Pencil /></Btn>
    <Btn size="icon-lg" data-testid="btn-showcase-size-icon-lg"><Pencil /></Btn>
  </div>
</section>

<section>
  <h2>Btn — States</h2>
  <div class="flex gap-2 flex-wrap">
    <Btn disabled data-testid="btn-showcase-state-disabled">Disabled</Btn>
    <Btn data-testid="btn-showcase-state-icon"><Pencil />With Icon</Btn>
    <Btn href="/_design" data-testid="btn-showcase-state-link">As Link</Btn>
    <Btn href="/_design" disabled data-testid="btn-showcase-state-link-disabled">Link Disabled</Btn>
  </div>
</section>
```

(Konkretes Icon kann ein bereits importiertes Lucide-SVG sein, z. B. `Pencil` aus `lucide-svelte`.)

### §6 `Btn.test.ts` — Vitest-Unit-Tests (mind. 15)

Test-Liste (jeder Test ein eigener `it()`-Block):

1. Rendert als `<button>`, wenn kein `href` gesetzt ist.
2. Rendert als `<a>`, wenn `href` gesetzt ist.
3. `href` + `disabled` → kein `href`-Attribut im DOM.
4. `href` + `disabled` → `aria-disabled="true"` gesetzt.
5. `href` + `disabled` → `tabindex="-1"` gesetzt.
6. `href` + `disabled` → `role="link"` gesetzt.
7. `<button>` + `disabled` → natives `disabled`-Attribut vorhanden.
8. Default-Variant ist `primary` (`data-variant="primary"`).
9. Default-Size ist `md` (`data-size="md"`).
10. `data-slot="btn"` ist auf beiden Render-Pfaden gesetzt.
11. Eigene `className` wird via `cn()` an die `class`-Attribut-Liste angehängt.
12. `children`-Snippet wird gerendert (Text-Content stimmt).
13. Alle 7 Variants akzeptiert ohne TS-/Runtime-Fehler (Loop-Test).
14. Alle 8 Sizes akzeptiert ohne TS-/Runtime-Fehler (Loop-Test).
15. Click-Handler auf `<button>` feuert, wenn nicht `disabled`.
16. Click-Handler auf `<button>` feuert NICHT, wenn `disabled` (HTML-Native-Verhalten, plus Spec-Verifikation).

### §7 `btn-feature-parity.spec.ts` — Playwright-E2E (mind. 8)

Spec gegen Route `/_design`. Tests entsprechen AC-1…AC-8 (s. Acceptance Criteria).

```typescript
import { test, expect } from '@playwright/test';

test.describe('Issue #214 — Btn Feature-Parität', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/_design');
  });

  // AC-1 … AC-8 implementieren — siehe Acceptance Criteria
});
```

### §8 TestID-Inventar

| TestID | Bedeutung |
|---|---|
| `btn-showcase-variant-primary` | Variants-Sektion |
| `btn-showcase-variant-accent` | Variants-Sektion |
| `btn-showcase-variant-outline` | Variants-Sektion |
| `btn-showcase-variant-ghost` | Variants-Sektion |
| `btn-showcase-variant-secondary` | Variants-Sektion |
| `btn-showcase-variant-destructive` | Variants-Sektion |
| `btn-showcase-variant-link` | Variants-Sektion |
| `btn-showcase-size-xs` | Sizes-Sektion |
| `btn-showcase-size-sm` | Sizes-Sektion |
| `btn-showcase-size-md` | Sizes-Sektion |
| `btn-showcase-size-lg` | Sizes-Sektion |
| `btn-showcase-size-icon-xs` | Sizes-Sektion |
| `btn-showcase-size-icon-sm` | Sizes-Sektion |
| `btn-showcase-size-icon` | Sizes-Sektion |
| `btn-showcase-size-icon-lg` | Sizes-Sektion |
| `btn-showcase-state-disabled` | States-Sektion |
| `btn-showcase-state-icon` | States-Sektion |
| `btn-showcase-state-link` | States-Sektion |
| `btn-showcase-state-link-disabled` | States-Sektion |

Insgesamt 19 TestIDs.

### §9 Datei-Liste (LoC)

| Art | Datei | Zweck | LoC |
|-----|-------|-------|-----|
| EDIT | `frontend/src/lib/components/ui/btn/Btn.svelte` | Props-Interface + href-Switch + Disabled-Render | +20 |
| EDIT | `frontend/src/lib/components/ui/btn/index.ts` | Re-Export `BtnVariant`, `BtnSize`, `BtnProps` | +3 |
| EDIT | `frontend/src/app.css` | Btn-CSS-Block (Z. 127–149) ersetzen + erweitern | +50 / -23 |
| NEU | `frontend/src/lib/components/ui/btn/Btn.test.ts` | Vitest-Unit-Tests (16) | +140 |
| EDIT | `frontend/src/routes/_design/+page.svelte` | Showcase um 3 Sektionen erweitern | +40 |
| NEU | `frontend/e2e/btn-feature-parity.spec.ts` | Playwright-Smoke-Tests (8) | +90 |
| **Summe** | | | **~340 LoC** |

**LoC-Override 350 erforderlich** (`workflow.py set-field loc_limit_override 350`).

## Expected Behavior

- **Input:**
  - Props an `<Btn>`: `variant` (BtnVariant), `size` (BtnSize), `href` (string?), `disabled` (boolean?), `class` (string?), `children` (Snippet), plus beliebige weitergeleitete HTML-Button-/Anchor-Attribute (`type`, `onclick`, `aria-*`, `data-*` etc.).
  - Defaults: `variant="primary"`, `size="md"`, `disabled=false`, `type="button"`.
- **Output:**
  - DOM-Element: `<button>` ohne `href`, `<a>` mit `href`. Beide tragen `data-slot="btn"`, `data-variant`, `data-size`. CSS aus `app.css` greift über diese Attribute.
  - Bei `disabled` + `href`: kein `href`-Attribut im DOM, `aria-disabled="true"`, `tabindex="-1"`, `role="link"`. Bei `disabled` + `<button>`: HTML-native `disabled`-Attribut.
  - `<svg>`-Kinder werden pro Size auf eine definierte Größe skaliert (D6).
- **Side effects:**
  - Visuelle Veränderung in `/_design` (Showcase erweitert). Cockpit, Trip-Wizard etc. bleiben unverändert, da die 8 bestehenden Aufrufer ihren Variant explizit angeben.
  - Kein Backend-Effekt, kein Persistenz-Effekt, keine API-Änderung.

## Acceptance Criteria

- **AC-1:** Given die `/_design`-Seite ist geladen / When 7 `data-testid="btn-showcase-variant-*"`-Elemente abgefragt werden / Then sind alle 7 (primary, accent, outline, ghost, secondary, destructive, link) sichtbar und aktiviert.
  - Test: (populated after /tdd-red)

- **AC-2:** Given die `/_design`-Seite ist geladen / When 8 `data-testid="btn-showcase-size-*"`-Elemente abgefragt werden / Then sind alle 8 (xs, sm, md, lg, icon-xs, icon-sm, icon, icon-lg) sichtbar und tragen das passende `data-size`-Attribut.
  - Test: (populated after /tdd-red)

- **AC-3:** Given ein `<Btn>` wird ohne `variant`-Prop verwendet / When das gerenderte Element inspiziert wird / Then trägt es `data-variant="primary"` (Default-Wechsel von `accent` → `primary`, D5).
  - Test: (populated after /tdd-red)

- **AC-4:** Given ein `<Btn>` wird ohne `size`-Prop verwendet / When das gerenderte Element inspiziert wird / Then trägt es `data-size="md"` (Default).
  - Test: (populated after /tdd-red)

- **AC-5:** Given ein `<Btn href="/x">` ist gerendert / When `tagName` des DOM-Elements geprüft wird / Then ist es `"A"`; ohne `href` ist es `"BUTTON"`.
  - Test: (populated after /tdd-red)

- **AC-6:** Given ein `<Btn href="/x" disabled>` ist gerendert / When das `<a>`-Element inspiziert wird / Then ist KEIN `href`-Attribut vorhanden, `aria-disabled="true"`, `tabindex="-1"` und `role="link"` sind gesetzt (D7).
  - Test: (populated after /tdd-red)

- **AC-7:** Given ein `<Btn disabled>` ohne `href` ist gerendert / When das `<button>`-Element inspiziert wird / Then ist das native HTML-`disabled`-Attribut vorhanden und Click-Events feuern nicht.
  - Test: (populated after /tdd-red)

- **AC-8:** Given die `/_design`-Seite ist geladen / When das `data-testid="btn-showcase-state-disabled"`-Element gemessen wird / Then ist die Computed-Style-Opacity `< 1` (Disabled-State sichtbar).
  - Test: (populated after /tdd-red)

- **AC-9:** Given ein `<Btn size="md">` mit `<svg>`-Kind ist gerendert / When `getBoundingClientRect()` des SVG gelesen wird / Then ist `width === 16` und `height === 16` (1 rem, D6).
  - Test: (populated after /tdd-red)

- **AC-10:** Given ein `<Btn size="lg">` mit `<svg>`-Kind ist gerendert / When `getBoundingClientRect()` des SVG gelesen wird / Then ist `width === 18` und `height === 18` (1.125 rem, D6).
  - Test: (populated after /tdd-red)

- **AC-11:** Given ein `<Btn size="icon-sm">` ist gerendert / When das DOM-Element gemessen wird / Then ist es exakt `28×28 px` (quadratisch, D6).
  - Test: (populated after /tdd-red)

- **AC-12:** Given ein `<Btn class="custom-class">` ist gerendert / When das `class`-Attribut gelesen wird / Then enthält es `"custom-class"` (cn-Merge funktioniert weiter, Tailwind-Overrides bleiben möglich).
  - Test: (populated after /tdd-red)

- **AC-13:** Given die App ist gebaut / When alle 8 bestehenden Btn-Aufrufstellen (TripWizardShell + `/_design`) gerendert werden / Then werfen sie keine Runtime-Errors und behalten ihren Variant (`accent`, `ghost`, `outline`) und Size (`sm`, `md`, `lg`) — Regressions-Guard.
  - Test: (populated after /tdd-red)

- **AC-14:** Given ein `<Btn variant="primary">` ist gerendert / When `getComputedStyle()` gelesen wird / Then ist `background-color` der OKlab-Wert von `--g-ink` und `color` der von `--g-paper` (D1).
  - Test: (populated after /tdd-red)

- **AC-15:** Given ein `<Btn variant="destructive">` ist gerendert / When `getComputedStyle()` gelesen wird / Then ist `border` ein `1px solid` mit der Farbe von `--g-danger` und `color` ebenfalls `--g-danger` (D2).
  - Test: (populated after /tdd-red)

- **AC-16:** Given ein `<Btn variant="accent">` ist gerendert / When `getComputedStyle()` gelesen wird / Then ist `background-color` der OKlab-Wert von `--g-accent` (Regressions-Guard: Burnt-Orange-Branding bleibt erhalten).
  - Test: (populated after /tdd-red)

- **AC-17:** Given ein `<Btn variant="link">` ist gerendert und mit der Maus überfahren / When der `:hover`-State aktiv ist / Then enthält `text-decoration-line` den Wert `"underline"`.
  - Test: (populated after /tdd-red)

- **AC-18:** Given ein `<Btn>` erhält Tastatur-Fokus / When `:focus-visible` aktiv ist / Then ist ein sichtbarer Outline (`2px solid var(--g-accent)`, Offset `2px`) gerendert.
  - Test: (populated after /tdd-red)

- **AC-19:** Given die `/_design`-Seite ist geladen / When per Tab-Taste durch die States-Sektion navigiert wird / Then springt der Fokus NICHT auf `data-testid="btn-showcase-state-disabled"` (HTML-disabled) und NICHT auf `btn-showcase-state-link-disabled` (`tabindex="-1"`).
  - Test: (populated after /tdd-red)

## Known Limitations

- **Phase B (#215) folgt:** Die 94 Button-Aufrufstellen werden in 4 Sprints auf Btn migriert. Das exakte Variant-Mapping (`default` → `primary`, `outline` → `outline`, `secondary` → `secondary`, `ghost` → `ghost`, `destructive` → `destructive`, `link` → `link`; `default`-Size → `md`) wird in der Phase-B-Spec dokumentiert. Diese Spec liefert nur die Voraussetzung — kein Alias-Backward-Compat in Btn (D8).
- **Phase C (#216) folgt:** Erst nach abgeschlossener Migration wird die alte Button-Komponente und der gesamte `frontend/src/lib/components/ui/button/`-Ordner entfernt. Solange koexistieren beide Komponenten parallel.
- **Tailwind-Klassen via `class`-Prop bleiben möglich:** Aufrufer können weiter Utility-Klassen (`text-sm`, `w-full`, `mt-2` etc.) durchreichen — `cn(className)` merged korrekt. Keine Hard-Removal von Tailwind in Phase A.
- **`aria-invalid` / `aria-expanded`-States werden NICHT übernommen:** Die alte Button-Komponente hat dafür eigene Variant-Stylings; falls relevant, kommt das als Folge-Issue. In Phase A sind die States nicht Treiber.
- **Icon-Sizing über Descendant-Selektor (`> svg`):** Custom-Icon-Komponenten, die ihre eigene Größe via `class`-Override setzen (z. B. `<svg class="size-5">`), werden durch das CSS überschrieben — Reihenfolge in `app.css` greift. Wer das nicht will, gibt explizit eine `style="width:20px;height:20px"` mit. Default-Verhalten ist gewollt eng definiert.
- **Test-Setup gegen `/_design`:** Die Playwright-Tests laufen ausschließlich gegen die synthetische `/_design`-Route — kein Trip-/User-Setup nötig. Damit ist die Test-Laufzeit niedrig und stabil gegen Daten-Drift.
- **Frontend = Desktop-Planungstool:** Touch-Target-Empfehlung von 44×44 px ist NICHT Treiber. Default-Size `md` bleibt bei 32 px Höhe (kompakt, dichte Side-by-Side-Layouts). `icon-lg` (36 px) ist das größte Standard-Element; größer ggf. via Custom-Klasse.
- **`color-mix(in oklab, …)`-Hover-States:** Setzt einen modernen Browser voraus (alle Evergreen seit 2023). Safari ≥16.4, Firefox ≥113, Chrome ≥111 — alle Zielbrowser dieses Projekts erfüllen das.

## Changelog

- 2026-05-13: Initial spec — Phase A der Button-Konsolidierung (Issue #214). Erweitert `Btn` von 3 Variants × 3 Sizes auf 7 Variants × 8 Sizes, fügt href-Switch, disabled-State (inkl. WAI-ARIA-Pattern für disabled Links), Icon-Sizing pro Size und vollständige Showcase-Coverage hinzu. 19 Acceptance Criteria zu Variants, Sizes, Render-Verhalten, Computed-Styles und Regressions-Schutz für 8 bestehende Aufrufer. ~340 LoC, Override 350. Folge-Phasen: #215 (Migration 94 Aufrufstellen), #216 (Button entfernen).

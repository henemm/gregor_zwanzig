# SvelteKit Best Practices – Gregor Frontend

**Updated:** 2026-05-26  
**Version:** 1.1

## Overview

This document codifies patterns and conventions established during Epic #133 (Design System Lauf A & B) for consistent, maintainable SvelteKit development in the Gregor Frontend.

---

## Component Architecture

### Svelte 5 Runes (Mandatory)

All new components must use Svelte 5 Runes syntax. No legacy reactive declarations.

**Rune Functions:**
- `$state()` — Component state (props with `$bindable()`)
- `$props()` — Destructure props inline at declaration
- `$derived()` — Computed properties from state
- `$effect()` — Side effects (component lifecycle)

**Pattern:**

```svelte
<script lang="ts">
  import type { Snippet } from 'svelte';
  import type { HTMLDivAttributes } from 'svelte/elements';

  interface MyComponentProps extends HTMLDivAttributes {
    label?: string;
    variant?: 'default' | 'accent';
    children?: Snippet;
  }

  let {
    label = 'Default',
    variant = 'default',
    class: className,
    children,
    ...rest
  }: MyComponentProps = $props();

  let derived = $derived(label.toUpperCase());

  let count = $state(0);

  function increment() {
    count++;
  }
</script>

<div class={cn(className)}>
  <h3>{derived}</h3>
  {@render children?.()}
</div>
```

---

## Component Props & Typing

### WithElementRef Pattern (Mandatory for Interactive Components)

Interactive components (`<Btn>`, form inputs, etc.) must support `bind:this={ref}` for DOM manipulation.

**Import:**
```typescript
import type { WithElementRef } from 'bits-ui';
```

**Pattern:**
```typescript
interface BtnProps extends WithElementRef<HTMLButtonAttributes> {
  variant?: 'accent' | 'ghost';
  children?: Snippet;
}

let { variant = 'accent', ref = $bindable(null), children, ...rest }: BtnProps = $props();
```

**Binding in Parent:**
```svelte
<script lang="ts">
  let myButton;
</script>

<Btn bind:ref={myButton} on:click={() => myButton?.focus()} />
```

### Class Extension (Always Allow)

All components must accept an optional `class` prop and merge it with internal styles.

**Pattern:**
```typescript
interface MyComponentProps extends HTMLDivAttributes {
  children?: Snippet;
}

let { class: className, children, ...rest }: MyComponentProps = $props();
```

**Render:**
```svelte
<div class={cn(className)} {...rest}>
  {@render children?.()}
</div>
```

### Use `cn()` for Class Merging

All class composition must use the `cn()` utility (clsx + tailwind-merge).

**Import:**
```typescript
import { cn } from '$lib/utils';
// or
import { cn } from '$lib/utils/cn';
```

**Pattern:**
```svelte
<button class={cn('base-class', variant && `variant-${variant}`, className)}>
  Click me
</button>
```

---

## Styling Patterns

### Token-Based Atoms (Lauf B Pattern)

Gregor atoms (`Btn`, `Pill`, `Eyebrow`, etc.) use **`data-slot` attributes** with global CSS selectors, not Tailwind classes or inline styles.

**Why?**
- Scan-safe (Tailwind 4 can't guarantee arbitrary-value classes at build time)
- Predictable token mapping (no `cv()` variance chains)
- Easy to visually audit in DevTools

**Pattern:**

1. **Component renders with `data-slot` attribute:**
   ```svelte
   <button data-slot="btn" data-variant={variant} data-size={size}>
     {@render children?.()}
   </button>
   ```

2. **Global CSS in `app.css` `@layer components`:**
   ```css
   [data-slot="btn"] {
     display: inline-flex;
     align-items: center;
     font-family: var(--g-font-ui);
     border-radius: var(--g-radius-md);
   }
   [data-slot="btn"][data-variant="accent"] {
     background: var(--g-accent);
     color: var(--g-paper);
   }
   [data-slot="btn"]:hover {
     opacity: 0.85;
   }
   ```

### Token Namespace: `--g-*`

All design tokens use the `--g-` prefix (Gregor namespace). See `docs/reference/frontend_components.md` for the full token list.

**Never use:**
- Hardcoded hex colors in component templates
- Arbitrary Tailwind values like `text-[#c45a2a]`

**Always use:**
- CSS custom properties: `color: var(--g-ink);`
- Component `data-` attributes with global selectors

### Hover/Focus States

Use CSS `:hover`, `:focus-visible`, `:active` selectors in global CSS. No inline style bindings.

**Pattern:**
```css
[data-slot="btn"]:hover {
  opacity: 0.85;
}
[data-slot="btn"]:focus-visible {
  outline: 2px solid var(--g-accent);
  outline-offset: 2px;
}
```

---

## Svelte Component Structure

### Module-Level Scripts (For Type Imports)

Use `<script context="module">` only for type exports or re-exported types.

**Anti-pattern (don't do this in atoms):**
```svelte
<script context="module">
  // ❌ Module state — causes issues with tree-shaking
  let globalState = 0;
</script>
```

**Good pattern:**
```svelte
<script lang="ts" module>
  // ✅ Type imports only
  import type { ComponentType } from 'svelte';
  
  // ✅ Re-export utilities
  import { tv } from 'tailwind-variants';
</script>
```

### Snippet Children (Instead of Slots)

Use Svelte 5 `Snippet` type for child content. This is more type-safe than slot forwarding.

**Pattern:**
```typescript
interface MyLayoutProps {
  header?: Snippet;
  children?: Snippet;
  footer?: Snippet;
}

let { header, children, footer }: MyLayoutProps = $props();
```

**Render:**
```svelte
<div class="layout">
  {#if header}
    <header>{@render header()}</header>
  {/if}
  <main>{@render children?.()}</main>
  {#if footer}
    <footer>{@render footer()}</footer>
  {/if}
</div>
```

### Form Element Bindings

For form inputs, use `bind:value`, `bind:checked`, etc. (still works with Runes).

**Pattern:**
```svelte
<script lang="ts">
  let email = $state('');
  let agreed = $state(false);
</script>

<input type="email" bind:value={email} />
<input type="checkbox" bind:checked={agreed} />
```

---

## Accessibility

### Semantic HTML First

Always use semantic elements (`<button>`, `<nav>`, `<header>`, `<article>`).

**Anti-patterns:**
```svelte
<!-- ❌ Don't use divs for buttons -->
<div role="button" on:click={...}>Click</div>

<!-- ❌ Don't wrap links in buttons -->
<button><a href="/">Home</a></button>
```

**Good:**
```svelte
<!-- ✅ Use native button -->
<button on:click={...}>Click</button>

<!-- ✅ Use native link -->
<a href="/">Home</a>
```

### ARIA Attributes (When Necessary)

Use `aria-*` only for non-semantic enhancements.

**SVG Decorations:**
```svelte
<!-- Decorative SVG should be hidden from screen readers -->
<svg data-slot="elev-sparkline" aria-hidden="true">
  ...
</svg>
```

**Form Validation:**
```svelte
<label for="email">Email</label>
<input
  id="email"
  type="email"
  aria-describedby={error ? 'error-msg' : undefined}
/>
{#if error}
  <span id="error-msg" role="alert">{error}</span>
{/if}
```

### Keyboard Navigation

All interactive components must be keyboard-accessible.

**Pattern:**
```svelte
<button
  type="button"
  on:click={handleClick}
  on:keydown={(e) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      handleClick();
    }
  }}
>
  Click or press Space/Enter
</button>
```

---

## UI State Patterns (Error · Loading · Empty · API-Error)

Four UI situations recur on almost every page. Historically each page solved them
differently (some forms showed no feedback, loading was sometimes a spinner and
sometimes a blank table, API errors were sometimes `alert()` and sometimes silent).
To keep UX consistent and stop re-inventing the wheel, **every page must follow the
rules below.** (Issue #314)

> **Scope note.** This section is the *contract*. The reusable `EmptyState.svelte`
> primitive, the global input-error CSS rule, and the `Toast` primitive are
> implemented as part of the Atomic-Design component epic (`EmptyState` → #372,
> input atom → #371, `Toast` → #312) — **not** here. Until those land, use the
> inline fallbacks documented below. This doc decides the *behaviour*; the epic
> ships the *components*.

### Decision Matrix

| Situation | Rule |
|-----------|------|
| **Form-field error** | Red field border + error text directly below the field. No toast. Stays visible until corrected. |
| **Loading — page** | Skeleton blocks sized like the final content. No full-page spinner/overlay, no blank screen. |
| **Loading — button action** | Disable the button + inline spinner icon. Rest of the page stays interactive. |
| **Empty state** | Centered icon + headline + description + optional CTA, via the shared `EmptyState`. |
| **API error** | Always visible to the user — `Toast tone="error"` (preferred) or inline error block. Never silent. |

### 1. Form-Field Errors

- Mark the invalid field with `aria-invalid` (accessible **and** styleable).
- Show the message directly below the field in `--g-danger`, small text.
- **No toast** for validation errors — they must stay visible until the user fixes them.

**✅ Correct:**
```svelte
<input
  data-slot="input"
  type="email"
  bind:value={email}
  aria-invalid={!!emailError}
  aria-describedby={emailError ? 'email-error' : undefined}
/>
{#if emailError}
  <p id="email-error" class="mt-1 text-xs" style="color: var(--g-danger)">
    {emailError}
  </p>
{/if}
```

The red border is driven by a global rule on the input atom (added with the atom in #371):
```css
[data-slot="input"][aria-invalid="true"] {
  border-color: var(--g-danger);
}
```

> Drive the colour through the `--g-danger` **token** (inline `style` or `data-slot`),
> never an arbitrary Tailwind value like `text-[color:var(--g-danger)]`
> (see *Common Pitfalls #4*). `text-xs` etc. are fine — those are standard utilities.

### 2. Loading States

**Page load → skeletons, not spinners.** Render neutral placeholder blocks shaped
like the content that will appear (same card sizes, same list rows). This avoids
layout shift and feels faster than a centered spinner.

- Use a neutral surface token (`--g-surface-2`) with a subtle pulse.
- **No full-page overlay** and no blank screen while loading.

**Button action → disable + inline spinner.** While an action runs (save, send,
test channel), disable the button and show a spinning `Loader2` icon inside it.
Keep the rest of the page interactive — never block the whole screen for one action.

**✅ Correct:**
```svelte
<Btn variant="accent" disabled={saving} aria-busy={saving}>
  {#if saving}<Loader2 class="animate-spin" size={16} />{/if}
  Speichern
</Btn>
```

### 3. Empty States

When a list/collection is empty, show one centered block — **icon + headline +
description + optional CTA** — and the same layout everywhere via the shared
`EmptyState` primitive.

```svelte
<EmptyState
  icon={MapPin}
  title="Noch keine Orte"
  description="Füge deinen ersten Ort hinzu, um Wettervergleiche zu starten."
>
  <Btn variant="accent" href="/locations/new">Ort hinzufügen</Btn>
</EmptyState>
```

`EmptyState` lives in `frontend/src/lib/components/ui/` (shipped with #372).
`routes/_home/EmptyKachel.svelte` is the existing prototype and should be migrated
onto the shared primitive when #372 lands.

### 4. API Errors

An API/network failure must **always be visible to the user** (AC-3) — never an
`alert()`, never a silent failure, never console-only.

- **Preferred:** `Toast` with `tone="error"` (once the `Toast` primitive from #312 exists).
- **Until then:** an inline error block at the top of the affected section, in `--g-danger`.

**✅ Correct (inline fallback):**
```svelte
{#if loadError}
  <p role="alert" class="text-sm" style="color: var(--g-danger)">
    {loadError}
  </p>
{/if}
```

**❌ Wrong:** `alert(err.message)` · `console.error(err)` as the only handling ·
swallowing the error so the user sees nothing.

---

## Event Handling

### Native Event Forwarding

SvelteKit components automatically forward events. No need to re-declare.

**Pattern (works automatically):**
```svelte
<script lang="ts">
  interface BtnProps extends HTMLButtonAttributes {
    children?: Snippet;
  }
  let { children, ...rest }: BtnProps = $props();
</script>

<button {...rest}>
  {@render children?.()}
</button>
```

**Parent can use:**
```svelte
<Btn on:click={handleClick} on:focus={handleFocus} />
```

---

## File Organization

### New Component Checklist

When creating a new component:

1. **Create directory:** `frontend/src/lib/components/ui/[component-name]/`
2. **Main file:** `[ComponentName].svelte` (PascalCase, matches component name)
3. **Index re-export:** `index.ts` with `export { default as ComponentName }`
4. **Test file** (optional): `[ComponentName].spec.ts` in `frontend/e2e/`

**Example structure:**
```
frontend/src/lib/components/ui/btn/
├── Btn.svelte
├── index.ts
└── README.md (optional, for internal notes)
```

**index.ts pattern:**
```typescript
export { default as Btn } from './Btn.svelte';
```

### Import Paths

Always use path aliases for imports:

```typescript
// ✅ Good
import { Btn } from '$lib/components/ui/btn';
import { cn } from '$lib/utils';
import type { User } from '$lib/types';

// ❌ Avoid
import { Btn } from '../../../components/ui/btn';
import { cn } from '../utils/cn';
```

---

## Routes & Pages

### Page Routes

Routes follow SvelteKit conventions. See `frontend/src/routes/` for examples.

**Layout inheritance:** Routes automatically inherit parent `+layout.svelte` components (e.g., Sidebar, Auth).

**Authentication:** All routes are protected via `hooks.server.ts` (Session verification). No additional code needed in routes.

### Showcase Routes (Development)

Internal routes prefixed with `_` (underscore) are hidden from production navigation but still compiled.

**Example:** `frontend/src/routes/_design/+page.svelte` (Epic #133 Lauf B)

- Not linked in Sidebar
- Accessible via direct URL for logged-in users
- Used for component testing and E2E validation
- Included in production build (no harm, just not user-facing)

---

## Testing

### E2E Testing with Playwright

All UI features should have E2E tests using Playwright.

**Pattern:**
```typescript
import { test, expect } from '@playwright/test';
import { login } from './helpers';

test.use({ storageState: 'playwright/.auth/admin.json' });

test.describe('My Feature', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/my-page');
  });

  test('button is visible', async ({ page }) => {
    const btn = page.locator('[data-slot="btn"]');
    await expect(btn).toBeVisible();
  });

  test('button triggers action', async ({ page }) => {
    await page.locator('button:has-text("Click")').click();
    await expect(page.locator('[data-testid="result"]')).toContainText('Success');
  });
});
```

**Selectors:**
- Prefer `[data-testid="..."]` for stable, semantic anchors
- Use `[data-slot="..."]` for component structure validation
- Avoid brittle selectors like `:nth-child(3)` or `button:first`

### Testing Against Tokens

When testing styled components, validate CSS custom property usage, not hardcoded colors.

**Pattern:**
```typescript
test('button uses accent token', async ({ page }) => {
  const btn = page.locator('[data-slot="btn"][data-variant="accent"]');
  // Check computed style (browser will resolve the CSS variable)
  const bgColor = await btn.evaluate((el) =>
    window.getComputedStyle(el).backgroundColor
  );
  // Expect the computed color (not the variable name)
  expect(bgColor).toBe('rgb(196, 90, 42)'); // #c45a2a in RGB
});
```

---

## Performance

### Client-Side State

Keep component state minimal. Use Svelte Stores only for truly shared state (auth, theme, etc.).

**Anti-pattern:**
```svelte
<script lang="ts">
  // ❌ Store every form field
  import { writable } from 'svelte/store';
  let email = writable('');
</script>
```

**Good:**
```svelte
<script lang="ts">
  // ✅ Component-local state for forms
  let email = $state('');
</script>
```

### Derived State

Use `$derived()` for computed values instead of watchers.

**Pattern:**
```svelte
<script lang="ts">
  let firstName = $state('Alice');
  let lastName = $state('Smith');
  
  // ✅ Automatic re-computation, no watcher
  let fullName = $derived(`${firstName} ${lastName}`);
  
  // Usage:
  // fullName is always up-to-date when firstName or lastName changes
</script>

<p>{fullName}</p>
```

---

## Common Pitfalls & How to Avoid Them

### 1. Forgetting `$props()` Destructuring

**❌ Wrong:**
```svelte
<script lang="ts">
  export let variant = 'default';
  export let size = 'md';
</script>
```

**✅ Correct:**
```svelte
<script lang="ts">
  let { variant = 'default', size = 'md' } = $props();
</script>
```

### 2. Not Spreading Rest Props

**❌ Wrong:**
```svelte
<script lang="ts">
  interface BtnProps {
    variant?: string;
  }
  let { variant }: BtnProps = $props();
</script>

<button data-variant={variant}>Click</button>
```

(Missing `on:click`, `on:focus`, `disabled`, `aria-*`, etc.)

**✅ Correct:**
```svelte
<script lang="ts">
  interface BtnProps extends HTMLButtonAttributes {
    variant?: string;
  }
  let { variant, ...rest }: BtnProps = $props();
</script>

<button data-variant={variant} {...rest}>Click</button>
```

### 3. Inline Styles Over Token CSS

**❌ Wrong:**
```svelte
<div style="color: #c45a2a; background: #f6f4ee;">
  Content
</div>
```

**✅ Correct:**
```svelte
<div style="color: var(--g-accent); background: var(--g-paper);">
  Content
</div>
```

Or better yet, use `data-slot` and global CSS.

### 4. Arbitrary Tailwind Values in Components

**❌ Wrong:**
```svelte
<button class="bg-[#c45a2a] text-[#f6f4ee]">
  Click
</button>
```

**✅ Correct:**
```svelte
<button
  data-slot="btn"
  data-variant="accent"
  class={cn(className)}
>
  Click
</button>
```

---

## Dark Mode (Future)

Currently, Gregor uses a light-mode-only design. When dark mode is added:

1. Token variants will be defined via `@media (prefers-color-scheme: dark)` or CSS scope `:root.dark`
2. Components do **not** need to change — they just reference `--g-*` variables
3. A theme switcher will toggle the color scheme globally

No component refactoring needed when dark mode arrives.

---

## Icons (Lucide)

Gregor nutzt [Lucide](https://lucide.dev/) (`@lucide/svelte`) als einzige Icon-Bibliothek
für UI-Aktions-Icons. Diese Sektion ist die **verbindliche und einzige schreibende Autorität**
für Icon-Auswahl und Import-Alias-Namensgebung.

### 1. Import-Pfad-Regel

Immer den **tiefen Import-Pfad** (`@lucide/svelte/icons/<name>`) verwenden, niemals den
Barrel-Import — der Barrel lädt die gesamte Bibliothek ins Bundle.

```svelte
<!-- Korrekt: tiefer Pfad, ein Icon -->
import PencilIcon from '@lucide/svelte/icons/pencil';
import Trash2Icon from '@lucide/svelte/icons/trash-2';

<!-- Verboten: Barrel-Import lädt die gesamte Bibliothek -->
import { Pencil, Trash2 } from '@lucide/svelte';
```

### 2. Alias-Namens-Konvention

Kurze oder mehrdeutige Icon-Namen erhalten das Suffix `Icon`. Mehrsilbige,
selbsterklärende Namen bleiben ohne Suffix.

| Kategorie | Beispiele mit `Icon`-Suffix | Beispiele ohne Suffix |
|-----------|-----------------------------|-----------------------|
| Kurz / mehrdeutig | `PencilIcon`, `Trash2Icon`, `XIcon`, `CheckIcon`, `PlusIcon`, `UploadIcon`, `ArchiveIcon`, `BellIcon`, `SearchIcon` | — |
| Mehrsilbig / selbsterklärend | — | `GripVertical`, `ChevronDown`, `ChevronUp`, `LayoutDashboard`, `GitCompare`, `LogOut`, `EllipsisVertical`, `Loader2` |

**Faustformel:** Ein Name, der als JavaScript-Bezeichner allein stehend wie eine gewöhnliche
Variable aussieht (`X`, `Check`, `Plus`), bekommt `Icon` als Suffix. Namen, die eindeutig ein
visuelles Konzept beschreiben (`ChevronDown`, `GripVertical`), bleiben unverändert.

### 3. Genehmigte Aktions-Icons

| Aktion | Lucide-Icon | Import-Alias |
|--------|-------------|--------------|
| Bearbeiten | `pencil` | `PencilIcon` |
| Löschen | `trash-2` | `Trash2Icon` |
| Schließen / Dialog-X | `x` | `XIcon` |
| Entfernen aus Liste | `x` | `XIcon` |
| Hinzufügen / Neu | `plus` | `PlusIcon` |
| Bestätigen / Speichern | `check` | `CheckIcon` |
| Suche | `search` | `SearchIcon` |
| Drag-Handle | `grip-vertical` | `GripVertical` |
| Kebab-Menü | `ellipsis-vertical` | `EllipsisVertical` |
| Laden / Spinner | `loader-2` | `Loader2` |
| Hochladen / Import | `upload` | `UploadIcon` |
| Archivieren | `archive` | `ArchiveIcon` |
| Alarm / Benachrichtigung | `bell` | `BellIcon` |

### 4. Wetter-Icons — Abgrenzung

**Wichtig:** Für Wetter-Icons (Sonne, Regen, Schnee, Gewitter usw.) ausschließlich
`<WIcon kind="..." />` aus `$lib/components/ui/wicon` verwenden. Lucide-Wetter-Icons
(`Cloud`, `Sun`, `CloudRain`, …) dürfen in der App-UI **nicht** direkt importiert werden.
`WIcon` ist in `docs/specs/_archive/modules/issue_322_wicon_komponente.md` spezifiziert.

**Kreuzreferenz:** AP-009 (Emojis als Icons verboten — stattdessen Lucide bzw. WIcon),
AP-005 (kein Icon-Überfluss — nicht jede Zeile braucht ein Icon).

---

## Resources

- **Component Library:** `docs/reference/frontend_components.md`
- **Design Tokens:** `docs/specs/_archive/modules/epic_133_design_system_lauf_a.md`
- **Svelte 5 Docs:** https://svelte.dev/docs
- **SvelteKit Docs:** https://kit.svelte.dev/docs
- **Tailwind CSS:** https://tailwindcss.com/docs

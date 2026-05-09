---
entity_id: epic_133_design_system_lauf_b
type: module
created: 2026-05-08
updated: 2026-05-09
status: completed
version: "1.0"
tags: [sveltekit, frontend, css, design-system, epic-133, atoms, svg, e2e]
---

# Epic 133 — Design-System Lauf B (Issues #143, #144, #146)

## Approval

- [x] Implemented (2026-05-09)

## Purpose

Ergaenzt das in Lauf A etablierte Token- und Schrift-Fundament um wiederverwendbare UI-Bausteine: ein Topo-Hintergrundmuster (`.g-topo` + `<TopoBg>`), fuenf Atom-Komponenten (`<Btn>`, `<GCard>`, `<Pill>`, `<Eyebrow>`, `<Dot>`) und eine SVG-Sparkline fuer Hoehenprofile (`<ElevSparkline>`). Lauf B ist vollstaendig additiv — es werden ausschliesslich neue Dateien angelegt sowie ein einziger Edit an `app.css` vorgenommen; bestehende Routen, Pages und shadcn-Komponenten bleiben unveraendert.

## Source

- **Issue #143 — Topo-Hintergrundmuster:**
  - `frontend/src/app.css` **(EDIT)**: `.g-topo`-Utility-Klasse hinzufuegen
  - `frontend/src/lib/components/ui/topo/TopoBg.svelte` **(NEU)**
  - `frontend/src/lib/components/ui/topo/index.ts` **(NEU)**
- **Issue #144 — Atom-Komponenten:**
  - `frontend/src/lib/components/ui/btn/Btn.svelte` **(NEU)**
  - `frontend/src/lib/components/ui/btn/index.ts` **(NEU)**
  - `frontend/src/lib/components/ui/g-card/GCard.svelte` **(NEU)**
  - `frontend/src/lib/components/ui/g-card/index.ts` **(NEU)**
  - `frontend/src/lib/components/ui/pill/Pill.svelte` **(NEU)**
  - `frontend/src/lib/components/ui/pill/index.ts` **(NEU)**
  - `frontend/src/lib/components/ui/eyebrow/Eyebrow.svelte` **(NEU)**
  - `frontend/src/lib/components/ui/eyebrow/index.ts` **(NEU)**
  - `frontend/src/lib/components/ui/dot/Dot.svelte` **(NEU)**
  - `frontend/src/lib/components/ui/dot/index.ts` **(NEU)**
- **Issue #146 — ElevSparkline:**
  - `frontend/src/lib/components/ui/elev-sparkline/ElevSparkline.svelte` **(NEU)**
  - `frontend/src/lib/components/ui/elev-sparkline/index.ts` **(NEU)**
- **Zusaetzlich:**
  - `frontend/src/routes/_design/+page.svelte` **(NEU)** — Showcase-Route
  - `frontend/e2e/design-system-lauf-b.spec.ts` **(NEU)** — E2E-Tests

## Abhaengigkeiten

| Entity | Typ | Zweck |
|--------|-----|-------|
| `frontend/src/app.css` | file (edit) | Aufnahme von `.g-topo` + globaler `[data-slot][data-variant]`/`[data-tone]`-Selektoren im `@layer components`-Block |
| `frontend/src/lib/components/ui/button/button.svelte` | file (referenz) | Referenz-Pattern fuer `<Btn>`: `tv()`, `cn()`, `data-slot`, `WithElementRef` |
| `frontend/src/lib/components/ui/card/card.svelte` | file (referenz) | Referenz-Pattern fuer `<GCard>`: Slot-Pattern, Hover-Effekt |
| `frontend/src/lib/components/ui/badge/badge.svelte` | file (referenz) | Referenz-Pattern fuer `<Pill>`: kompakte Label-Komponente |
| `frontend/src/lib/utils/cn.ts` | file | `cn()`-Implementierung (clsx + tailwind-merge) fuer class-Merging in Atoms |
| `bits-ui` | package | `WithElementRef`-Type fuer alle neuen Atoms (direkter Import, nicht ueber `$lib/utils`) |
| `tailwind-variants` | package | `tv()`-Funktion fuer Varianten-Definitionen in Atoms |
| `frontend/e2e/helpers.ts` | file | `login()`-Helper fuer E2E-Auth-Setup |
| `frontend/e2e/design-system-lauf-a.spec.ts` | file (referenz) | Test-Pattern (Playwright-Struktur) als Vorbild fuer Lauf-B-Tests |
| `--g-*`-Tokens (Lauf A) | css | Alle Atom-Styles referenzieren Token aus `@layer base` — Lauf A ist Voraussetzung |
| `frontend/src/lib/types.ts` | file (referenz) | `Waypoint.elevation_m: number` — kuenftiger ElevSparkline-Datenpfad (kein direkter Import in Lauf B) |
| `hooks.server.ts` | file | Auth-Guard: `/_design`-Route ist automatisch durch Session-Verifizierung geschuetzt (kein zusaetzlicher Code noetig) |

## Implementierungsdetails

### Reihenfolge (kritisch fuer TDD-RED und Implementation-Phase)

1. **`app.css` erweitern** — CSS-Schicht zuerst, damit Komponenten beim ersten Render sofort korrekt aussehen
2. **Showcase-Route `/_design` anlegen** — anfangs leer, wächst mit jedem fertigen Atom; bildet den E2E-Anker
3. **Atoms parallel**: `<Btn>`, `<GCard>`, `<Pill>`, `<Eyebrow>`, `<Dot>` — gleiche Struktur, trivial parallelisierbar
4. **`<TopoBg>`** — Wrapper um `.g-topo` mit `opacity`-Prop als CSS Custom Property
5. **`<ElevSparkline>`** — eigenstaendiges SVG ohne Token-Abhaengigkeit (nur `currentColor`)
6. **E2E-Tests** (`design-system-lauf-b.spec.ts`) — pro Komponente 1-2 Assertions gegen `/_design`

---

### Strategische Entscheidung: `data-`-Attribute statt Tailwind-Arbitrary-Values

Atoms tragen `data-slot="<name>"`, `data-variant="..."` und `data-tone="..."`-Attribute. Globale CSS-Selektoren in `app.css` (`[data-slot="btn"][data-variant="accent"] { background: var(--g-accent); }`) setzen Background, Border und Color. Dieses Pattern ist identisch zum `data-slot`-Pattern von shadcn-svelte und scan-sicher gegenueber Tailwind 4.

**Verworfene Alternativen:**
- `bg-[var(--g-accent)]` in `tv()`-Variants: Tailwind-Arbitrary-Values mit Custom-Properties in `tv()`-Branches schwer als statische Strings zu garantieren → Klassen drohen im Build zu fehlen
- Inline `style="..."`-Attribute: unleserlich, nicht hover/focus-faehig

---

### `app.css`-Erweiterungen

In `frontend/src/app.css` wird nach dem bestehenden `@layer base`-Block (Lauf A) ein neuer `@layer components`-Block eingefuegt:

```css
@layer components {
  /* === Issue #143: Topo-Hintergrundmuster === */
  .g-topo {
    background-image:
      radial-gradient(circle at 50% 50%, transparent 0, transparent 14px, var(--g-ink) 14px, var(--g-ink) 15px, transparent 15px),
      radial-gradient(circle at 50% 50%, transparent 0, transparent 28px, var(--g-ink) 28px, var(--g-ink) 29px, transparent 29px);
    background-size: 60px 60px;
    opacity: var(--g-topo-opacity, 0.04);
    pointer-events: none;
  }

  /* === Issue #144: Btn === */
  [data-slot="btn"] {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 0.5rem;
    font-family: var(--g-font-ui);
    font-weight: 500;
    border-radius: var(--g-radius-md);
    cursor: pointer;
    transition: opacity 0.15s ease, box-shadow 0.15s ease;
  }
  [data-slot="btn"][data-size="sm"] { padding: 0.25rem 0.75rem; font-size: 0.75rem; }
  [data-slot="btn"][data-size="md"] { padding: 0.5rem 1rem;     font-size: 0.875rem; }
  [data-slot="btn"][data-size="lg"] { padding: 0.75rem 1.5rem;  font-size: 1rem; }
  [data-slot="btn"][data-variant="accent"]  { background: var(--g-accent);    color: var(--g-paper); border: none; }
  [data-slot="btn"][data-variant="ghost"]   { background: transparent;        color: var(--g-ink);   border: none; }
  [data-slot="btn"][data-variant="outline"] { background: transparent;        color: var(--g-ink);   border: 1px solid var(--g-ink); }
  [data-slot="btn"]:hover                   { opacity: 0.85; }
  [data-slot="btn"]:focus-visible           { outline: 2px solid var(--g-accent); outline-offset: 2px; }

  /* === Issue #144: GCard === */
  [data-slot="g-card"] {
    background: var(--g-surface-1);
    border-radius: var(--g-radius-lg);
    box-shadow: var(--g-elev-1);
    padding: 1rem;
    transition: box-shadow 0.15s ease;
  }
  [data-slot="g-card"]:hover { box-shadow: var(--g-elev-2); }

  /* === Issue #144: Pill === */
  [data-slot="pill"] {
    display: inline-flex;
    align-items: center;
    padding: 0.125rem 0.5rem;
    border-radius: var(--g-radius-pill);
    font-family: var(--g-font-ui);
    font-size: 0.75rem;
    font-weight: 500;
  }
  [data-slot="pill"][data-tone="default"]  { background: var(--g-surface-2);   color: var(--g-ink); }
  [data-slot="pill"][data-tone="success"]  { background: var(--g-success);     color: #fff; }
  [data-slot="pill"][data-tone="warning"]  { background: var(--g-warning);     color: #fff; }
  [data-slot="pill"][data-tone="danger"]   { background: var(--g-danger);      color: #fff; }
  [data-slot="pill"][data-tone="info"]     { background: var(--g-info);        color: #fff; }
  [data-slot="pill"][data-tone="accent"]   { background: var(--g-accent);      color: var(--g-paper); }

  /* === Issue #144: Eyebrow === */
  [data-slot="eyebrow"] {
    display: block;
    font-family: var(--g-font-data);
    font-size: 0.625rem;
    font-weight: 400;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: var(--g-ink-faint);
  }

  /* === Issue #144: Dot === */
  [data-slot="dot"] {
    display: inline-block;
    border-radius: 50%;
    flex-shrink: 0;
  }
  [data-slot="dot"][data-size="xs"] { width: 6px;  height: 6px; }
  [data-slot="dot"][data-size="sm"] { width: 8px;  height: 8px; }
  [data-slot="dot"][data-size="md"] { width: 10px; height: 10px; }
  [data-slot="dot"][data-tone="rain"]    { background: var(--g-wx-rain); }
  [data-slot="dot"][data-tone="sun"]     { background: var(--g-wx-sun); }
  [data-slot="dot"][data-tone="wind"]    { background: var(--g-wx-wind); }
  [data-slot="dot"][data-tone="snow"]    { background: var(--g-wx-snow); }
  [data-slot="dot"][data-tone="thunder"] { background: var(--g-wx-thunder); }
  [data-slot="dot"][data-tone="fog"]     { background: var(--g-wx-fog); }
  [data-slot="dot"][data-tone="success"] { background: var(--g-success); }
  [data-slot="dot"][data-tone="warning"] { background: var(--g-warning); }
  [data-slot="dot"][data-tone="danger"]  { background: var(--g-danger); }
  [data-slot="dot"][data-tone="info"]    { background: var(--g-info); }
}
```

---

### Komponenten-Pattern (gilt fuer alle 5 Atoms)

Svelte 5 Runes, `data-slot` + `data-variant`/`data-tone`, Props-Typ via Interface, `WithElementRef` direkt aus `bits-ui`:

```svelte
<!-- Btn.svelte -->
<script lang="ts" module>
  import { tv } from 'tailwind-variants';
  // tv() wird nur fuer class-Komposition genutzt (keine Arbitrary-Values)
</script>

<script lang="ts">
  import type { Snippet } from 'svelte';
  import type { HTMLButtonAttributes } from 'svelte/elements';
  import type { WithElementRef } from 'bits-ui';
  import { cn } from '$lib/utils/cn';

  interface Props extends WithElementRef<HTMLButtonAttributes> {
    variant?: 'accent' | 'ghost' | 'outline';
    size?: 'sm' | 'md' | 'lg';
    children?: Snippet;
  }

  let {
    variant = 'accent',
    size = 'md',
    class: className,
    ref = $bindable(null),
    children,
    ...rest
  }: Props = $props();
</script>

<button
  data-slot="btn"
  data-variant={variant}
  data-size={size}
  class={cn(className)}
  bind:this={ref}
  {...rest}
>
  {@render children?.()}
</button>
```

Analoges Pattern fuer `<GCard>`, `<Pill>`, `<Eyebrow>`, `<Dot>`:
- `<GCard>`: `data-slot="g-card"`, Props: `class?`, `children?`
- `<Pill>`: `data-slot="pill"`, `data-tone`, Tone-Werte: `default | success | warning | danger | info | accent`
- `<Eyebrow>`: `data-slot="eyebrow"`, Props: `class?`, `children?` — rendert `<span>`
- `<Dot>`: `data-slot="dot"`, `data-tone` (Wetter-Tones + Semantic-Tones), `data-size` (`xs | sm | md`)

---

### `<TopoBg>`-Implementierung

```svelte
<!-- TopoBg.svelte -->
<script lang="ts">
  import type { Snippet } from 'svelte';

  interface Props {
    opacity?: number;
    children?: Snippet;
  }

  let { opacity = 0.04, children }: Props = $props();
</script>

<div class="relative">
  <div
    data-slot="topo-bg"
    class="g-topo absolute inset-0"
    style:--g-topo-opacity={opacity}
  ></div>
  <div class="relative">
    {@render children?.()}
  </div>
</div>
```

Hinweis: Der Eltern-Container traegt `position: relative` (durch den Wrapper-`<div class="relative">`); das `position: absolute; inset: 0`-Element mit `pointer-events: none` verhindert, dass das Muster Hover/Click-Events der darunterliegenden Inhalte abfaengt.

---

### `<ElevSparkline>`-Implementierung

```svelte
<!-- ElevSparkline.svelte -->
<script lang="ts">
  interface Props {
    data: number[];
    width?: number;
    height?: number;
    active?: boolean;
  }

  let { data, width = 120, height = 24, active = false }: Props = $props();

  const padding = 2;

  let polyline = $derived((() => {
    if (data.length === 0) return '';
    const min = Math.min(...data);
    const max = Math.max(...data);
    const range = max - min || 1; // verhindert Division durch 0 bei min===max
    return data.map((v, i) => {
      const x = (i / Math.max(data.length - 1, 1)) * width;
      const y = max === min
        ? height / 2
        : padding + ((max - v) / range) * (height - 2 * padding);
      return `${x},${y}`;
    }).join(' ');
  })());
</script>

<svg
  data-slot="elev-sparkline"
  data-active={active}
  {width}
  {height}
  viewBox="0 0 {width} {height}"
  aria-hidden="true"
>
  {#if polyline}
    <polyline
      points={polyline}
      fill="none"
      stroke="currentColor"
      stroke-width="1.5"
      stroke-linejoin="round"
      stroke-linecap="round"
    />
  {/if}
</svg>
```

**Y-Skalierungs-Logik:**
- `data.length === 0` → `polyline = ''` → kein `<polyline>`-Element, kein Crash
- `data.length === 1` → `i / Math.max(0, 1)` → `x = 0`; min === max → `y = height / 2` → einzelner Punkt mittig
- `min === max` (alle Werte identisch) → `range = 1` (Fallback), `y = height / 2` → horizontale Linie

---

### Showcase-Route `/_design`

```svelte
<!-- frontend/src/routes/_design/+page.svelte -->
<script lang="ts">
  import { Btn } from '$lib/components/ui/btn';
  import { GCard } from '$lib/components/ui/g-card';
  import { Pill } from '$lib/components/ui/pill';
  import { Eyebrow } from '$lib/components/ui/eyebrow';
  import { Dot } from '$lib/components/ui/dot';
  import { TopoBg } from '$lib/components/ui/topo';
  import { ElevSparkline } from '$lib/components/ui/elev-sparkline';
</script>

<div class="p-8 space-y-8">
  <h1 data-testid="design-showcase-title">Design-System Showcase</h1>

  <section data-testid="atoms-section">
    <Btn variant="accent">Speichern</Btn>
    <Btn variant="ghost">Abbrechen</Btn>
    <Btn variant="outline" size="sm">Mehr</Btn>

    <Pill tone="success">OK</Pill>
    <Pill tone="warning">Achtung</Pill>
    <Pill tone="danger">Fehler</Pill>

    <Eyebrow>Wetter</Eyebrow>

    <Dot tone="rain" size="md" />
    <Dot tone="sun" size="md" />
    <Dot tone="thunder" size="sm" />

    <GCard>
      <p>Karten-Inhalt</p>
    </GCard>
  </section>

  <section data-testid="topo-section">
    <TopoBg opacity={0.06}>
      <p>Inhalt auf Topo-Hintergrund</p>
    </TopoBg>
  </section>

  <section data-testid="sparkline-section">
    <ElevSparkline data={[800, 1200, 950, 1500, 1100]} width={200} height={40} />
    <ElevSparkline data={[]} width={120} height={24} />
    <ElevSparkline data={[1500]} width={120} height={24} />
  </section>
</div>
```

Kein `prerender`-Export noetig (`adapter-node` schaltet statische Generierung nicht ein). Kein Eintrag in `navItems` von `Sidebar.svelte`.

---

### Index-Dateien (alle identisches Pattern)

```typescript
// Beispiel: frontend/src/lib/components/ui/btn/index.ts
export { default as Btn } from './Btn.svelte';
// analog: TopoBg, GCard, Pill, Eyebrow, Dot, ElevSparkline
```

---

### E2E-Tests `design-system-lauf-b.spec.ts`

```typescript
import { test, expect } from '@playwright/test';
import { login } from './helpers';

test.use({ storageState: 'playwright/.auth/admin.json' });

test.describe('Design-System Lauf B — Showcase', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/_design');
    await expect(page.getByTestId('design-showcase-title')).toBeVisible();
  });

  // TopoBg
  test('TopoBg rendert data-slot="topo-bg"', async ({ page }) => {
    const topo = page.locator('[data-slot="topo-bg"]');
    await expect(topo).toBeVisible();
  });

  // Btn
  test('Btn accent hat data-slot und data-variant', async ({ page }) => {
    const btn = page.locator('[data-slot="btn"][data-variant="accent"]').first();
    await expect(btn).toBeVisible();
    await expect(btn).toContainText('Speichern');
  });

  // Pill
  test('Pill success hat data-slot und data-tone', async ({ page }) => {
    const pill = page.locator('[data-slot="pill"][data-tone="success"]');
    await expect(pill).toBeVisible();
    await expect(pill).toContainText('OK');
  });

  // Eyebrow
  test('Eyebrow hat data-slot="eyebrow"', async ({ page }) => {
    const eyebrow = page.locator('[data-slot="eyebrow"]');
    await expect(eyebrow).toBeVisible();
    await expect(eyebrow).toContainText('Wetter');
  });

  // Dot
  test('Dot rain hat data-slot und data-tone', async ({ page }) => {
    const dot = page.locator('[data-slot="dot"][data-tone="rain"]');
    await expect(dot).toBeVisible();
  });

  // GCard
  test('GCard hat data-slot="g-card"', async ({ page }) => {
    const card = page.locator('[data-slot="g-card"]');
    await expect(card).toBeVisible();
  });

  // ElevSparkline — Normalfall
  test('ElevSparkline rendert SVG mit Polyline fuer 5 Datenpunkte', async ({ page }) => {
    const svgs = page.locator('[data-slot="elev-sparkline"]');
    const first = svgs.nth(0);
    await expect(first).toBeVisible();
    const polyline = first.locator('polyline');
    await expect(polyline).toBeVisible();
    const points = await polyline.getAttribute('points');
    expect(points?.split(' ').length).toBe(5);
  });

  // ElevSparkline — leeres Array
  test('ElevSparkline rendert SVG ohne Polyline fuer leeres Array', async ({ page }) => {
    const svgs = page.locator('[data-slot="elev-sparkline"]');
    const empty = svgs.nth(1);
    await expect(empty).toBeVisible();
    const polyline = empty.locator('polyline');
    await expect(polyline).toHaveCount(0);
  });

  // ElevSparkline — Single-Point
  test('ElevSparkline rendert SVG fuer Single-Point ohne Crash', async ({ page }) => {
    const svgs = page.locator('[data-slot="elev-sparkline"]');
    const single = svgs.nth(2);
    await expect(single).toBeVisible();
  });
});
```

## Expected Behavior

- **Input:** Konsument importiert eine der neuen Komponenten und rendert sie mit Props
- **Output:**
  - Atoms tragen `data-slot`, `data-variant`/`data-tone` und erhalten dadurch automatisch Token-basierte Styles aus `app.css`
  - `<TopoBg>` legt ein konzentrisch-gestreiftes Muster hinter seine Kinder (radial-gradient, `opacity` ueber CSS Custom Property steuerbar)
  - `<ElevSparkline>` gibt ein `<svg>`-Element mit `<polyline>` zurueck; bei leerem Array kein Element-Fehler
  - `/_design`-Route zeigt alle Komponenten visuell an und dient als deterministischer E2E-Anker
- **Side effects:**
  - `.g-topo`-Klasse und `[data-slot]`-Selektoren sind global verfuegbar — kein Konflikt mit bestehenden shadcn-Klassen, da Namespace disjunkt
  - 10 E2E-Tests in `design-system-lauf-b.spec.ts` muessen gruen sein

## Was sich NICHT aendert

- Bestehende shadcn-Komponenten (`button`, `card`, `badge`, `dialog`, ...) bleiben unveraendert
- `app.html`, `+layout.svelte`, `hooks.server.ts` — keine Aenderungen
- Bestehender `@theme`-Block und `@layer base`-Block in `app.css` (Lauf A) — kein Eingriff
- Keine neuen npm-Pakete

## Akzeptanzkriterien

| # | Kriterium | Pruefung | Status |
|---|-----------|----------|--------|
| 1 | `.g-topo`-Klasse existiert in `app.css` und definiert `background-image` (radial-gradient) und `background-size` | Grep in `app.css` | [ ] |
| 2 | `<TopoBg opacity={0.04}>` rendert Element mit `data-slot="topo-bg"` und `--g-topo-opacity: 0.04` | E2E: `[data-slot="topo-bg"]` sichtbar | [ ] |
| 3 | `<Btn variant="accent">Speichern</Btn>` rendert mit `data-slot="btn"`, `data-variant="accent"`, sichtbarem Text | E2E: Element sichtbar + Text vorhanden | [ ] |
| 4 | `<Pill tone="success">OK</Pill>` rendert mit `data-slot="pill"`, `data-tone="success"` | E2E: `[data-slot="pill"][data-tone="success"]` sichtbar | [ ] |
| 5 | `<Eyebrow>Wetter</Eyebrow>` rendert mit `data-slot="eyebrow"` und JetBrains-Mono-Font (`font-family: var(--g-font-data)`) | E2E: Element sichtbar; DevTools: `font-family` computed | [ ] |
| 6 | `<Dot tone="rain" />` rendert mit `data-slot="dot"`, `data-tone="rain"` | E2E: `[data-slot="dot"][data-tone="rain"]` sichtbar | [ ] |
| 7 | `<GCard>` rendert mit `data-slot="g-card"` | E2E: `[data-slot="g-card"]` sichtbar | [ ] |
| 8 | `<ElevSparkline data={[800,1200,950,1500,1100]}>` rendert `<svg>` mit `<polyline points>` (5 Punkte) | E2E: Polyline vorhanden, 5 Koordinaten-Paare | [ ] |
| 9 | `<ElevSparkline data={[]}>` rendert `<svg>` ohne `<polyline>` — kein Crash | E2E: SVG vorhanden, polyline-Count = 0 | [ ] |
| 10 | `<ElevSparkline data={[1500]}>` und `data={[1500,1500]}` rendern SVG ohne Crash (horizontale Linie) | E2E: SVG vorhanden, kein NaN in points-Attribut | [ ] |
| 11 | `/_design` antwortet mit HTTP 200 nach Login | E2E: Seite laedt, `data-testid="design-showcase-title"` sichtbar | [ ] |
| 12 | `/_design` ist nicht in der Sidebar verlinkt | Grep in `Sidebar.svelte` auf `/_design` — kein Treffer | [ ] |

## Known Limitations

- `<ElevSparkline>` nutzt `currentColor` fuer Stroke — Konsumenten muessen `color` via CSS setzen oder ueberschreiben; kein Token-Default in der Komponente, weil Verwendungskontexte variieren
- `<TopoBg>` setzt voraus, dass der Wrapper-Container `position: relative` hat — der Komponenten-Wrapper erledigt das selbst, setzt aber kein explizites `overflow: hidden`, d.h. das Muster ragt bei groessen Radii-Werten am Rand sichtbar heraus
- `/_design`-Route ist per direkter URL fuer eingeloggte User sichtbar — bewusste Dev-Convenience, kein Bug; sie landet im Production-Build, ist aber nicht navigierbar ohne direkten Link
- Btn/Pill/Dot-Tones deckeln bei Dark-Mode nicht automatisch um — Dark-Mode-Tokens sind in Lauf A nicht definiert (folgt in einem spaeteren Lauf)

## Changelog

- 2026-05-09: Implementation completed — Atoms (Btn, GCard, Pill, Eyebrow, Dot), TopoBg, ElevSparkline, /_design showcase, E2E tests green
- 2026-05-08: Initial spec erstellt — Epic 133 Lauf B (Issues #143, #144, #146)

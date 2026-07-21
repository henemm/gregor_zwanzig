---
entity_id: epic_133_tokens_and_topo
type: module
created: 2026-05-13
updated: 2026-05-13
status: draft
version: "1.0"
parent_spec: epic_133_design_system
issues: [208, 209]
parent_epic: 133
tags: [frontend, sveltekit, design-system, epic-133, issue-208, issue-209]
---

# Epic #133 — Issues #208 + #209: Tokens nachziehen + Topo-Muster sichtbar machen

## Approval

- [ ] Approved

## Purpose

Bündelt zwei verwandte Design-System-Lücken in einem Workflow: (1) Typography-, Spacing- und Tracking-Tokens, die im Spec `design_system_tokens.css` definiert sind, aber in `app.css` komplett fehlen, werden nachgezogen; (2) das Topo-Hintergrundmuster wird von zwei harten Punkt-Ringen auf die spezifizierten 5 weichen Ellipsen umgestellt und durch höhere RGBA-Alpha + angehobenen Default-Opacity-Wert tatsächlich sichtbar gemacht. Beide Änderungen sind frontend-only und betreffen nur `app.css` plus eine Default-Prop in `TopoBg.svelte`.

## Source

- **EDIT:** `frontend/src/app.css` — 24 neue Tokens (#208) + neue Topo-Geometrie (#209)
- **EDIT:** `frontend/src/lib/components/ui/topo/TopoBg.svelte` — Default-Prop `opacity` von `0.04` auf `0.5`
- **EDIT:** `frontend/src/routes/_cockpit/ActiveTripCard.svelte` — hartkodiertes `opacity={0.06}` aus `<TopoBg>` entfernen
- **EDIT:** `frontend/src/routes/_design/+page.svelte` — hartkodiertes `opacity={0.06}` aus `<TopoBg>` entfernen
- **NEU:** `frontend/e2e/tokens-and-topo.spec.ts` — Playwright-Tests
- **Identifier:** keine Code-Identifier, nur CSS-Variablen und ein Svelte-Prop-Default

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `docs/reference/design_system_tokens.css` | bestehend (Soll-Quelle) | Liefert die exakten Werte für Type Scale, Tracking, Spacing und Topo-Geometrie |
| `frontend/src/app.css` Z. 28–80 (`:root`-Block) | bestehend (EDIT) | Bestehende `--g-*`-Tokens bleiben unverändert; nur additive Erweiterung |
| `frontend/src/app.css` Z. 85–92 (`.g-topo`) | bestehend (EDIT) | Geometrie + Opacity-Default ersetzt |
| `frontend/src/lib/components/ui/topo/TopoBg.svelte` Z. 9 | bestehend (EDIT) | Default-Prop ändern |
| `frontend/src/routes/_cockpit/ActiveTripCard.svelte` Z. 42 | bestehend (EDIT) | `opacity={0.06}` entfernen, Default greift |
| `frontend/src/routes/_design/+page.svelte` Z. 68 | bestehend (EDIT) | dito |

## Implementation Details

### §1 Typography-, Tracking-, Spacing-Tokens (Issue #208)

In `frontend/src/app.css` im Block `@layer base { :root { ... } }` nach den bestehenden Tokens ergänzen (direkt vor dem schließenden `}` von `:root`):

```css
    /* Type Scale (Spec design_system_tokens.css Z. 47–55) */
    --g-text-xs:  11px;
    --g-text-sm:  13px;
    --g-text-md:  15px;
    --g-text-lg:  17px;
    --g-text-xl:  20px;
    --g-text-2xl: 24px;
    --g-text-3xl: 32px;
    --g-text-4xl: 44px;
    --g-text-5xl: 60px;

    /* Tracking (Spec design_system_tokens.css Z. 58–61) */
    --g-track-tight:  -0.02em;
    --g-track-normal: 0;
    --g-track-wide:   0.06em;
    --g-track-caps:   0.12em;

    /* Spacing Grid 4px (Spec design_system_tokens.css Z. 64–74) */
    --g-s-1:  4px;
    --g-s-2:  8px;
    --g-s-3:  12px;
    --g-s-4:  16px;
    --g-s-5:  20px;
    --g-s-6:  24px;
    --g-s-8:  32px;
    --g-s-10: 40px;
    --g-s-12: 48px;
    --g-s-16: 64px;
    --g-s-20: 80px;
```

**Hinweis Naming:** Spec nutzt `--g-text-md` (nicht `-base`), `--g-track-wide: 0.06em` (nicht `0.04em` wie im Issue #208-Body). Spec ist maßgeblich.

### §2 Topo-Geometrie ersetzen (Issue #209)

In `frontend/src/app.css` den `.g-topo`-Block (Z. 85–92) komplett ersetzen:

```css
  /* === Issue #143 + #209: Topo-Hintergrundmuster === */
  .g-topo {
    background-image:
      radial-gradient(ellipse 800px 400px at 20% 30%, transparent 30%, rgba(26, 26, 24, 0.10) 30.5%, transparent 31%),
      radial-gradient(ellipse 700px 350px at 22% 32%, transparent 35%, rgba(26, 26, 24, 0.12) 35.5%, transparent 36%),
      radial-gradient(ellipse 600px 300px at 24% 34%, transparent 40%, rgba(26, 26, 24, 0.14) 40.5%, transparent 41%),
      radial-gradient(ellipse 900px 450px at 80% 70%, transparent 30%, rgba(26, 26, 24, 0.10) 30.5%, transparent 31%),
      radial-gradient(ellipse 800px 400px at 78% 68%, transparent 35%, rgba(26, 26, 24, 0.12) 35.5%, transparent 36%);
    opacity: var(--g-topo-opacity, 0.5);
    pointer-events: none;
  }
```

**Änderungen ggü. Ist:**
- 5 Ellipsen statt 2 Circles (Spec-Geometrie, aber mit höheren RGBA-Alphas von `0.10–0.14` statt Spec-`0.025–0.035`, damit das Muster sichtbar wird)
- `background-size: 60px 60px` entfällt (Ellipsen sind absolut positioniert in Prozent)
- Default-Opacity der CSS-Variable von `0.04` auf `0.5` angehoben
- `pointer-events: none` bleibt
- Kein `background-color` — die Komponente bleibt Overlay-fähig

### §3 TopoBg-Default-Opacity anheben

In `frontend/src/lib/components/ui/topo/TopoBg.svelte` Zeile 9:

```typescript
let { opacity = 0.5, children }: Props = $props();
```

(Vorher: `opacity = 0.04`.)

### §4 Aufrufer-Edits

In `frontend/src/routes/_cockpit/ActiveTripCard.svelte` Z. 42 und `frontend/src/routes/_design/+page.svelte` Z. 68:

```svelte
<!-- ALT: -->
<TopoBg opacity={0.06}>

<!-- NEU: -->
<TopoBg>
```

(Default `0.5` greift; bei Bedarf kann jeder Aufrufer wieder einen eigenen Wert setzen.)

### §5 Neuer Test `frontend/e2e/tokens-and-topo.spec.ts`

Playwright-E2E-Spec mit den 6 Tests entsprechend AC-1…AC-6 unten.

```typescript
import { test, expect } from '@playwright/test';

test.describe('Epic #133 — Tokens + Topo', () => {
  test('AC-1: --g-text-md = "15px"', async ({ page }) => {
    await page.goto('/');
    const v = await page.evaluate(() =>
      getComputedStyle(document.documentElement).getPropertyValue('--g-text-md').trim()
    );
    expect(v).toBe('15px');
  });

  test('AC-2: --g-s-4 = "16px"', async ({ page }) => {
    await page.goto('/');
    const v = await page.evaluate(() =>
      getComputedStyle(document.documentElement).getPropertyValue('--g-s-4').trim()
    );
    expect(v).toBe('16px');
  });

  test('AC-3: --g-track-wide = "0.06em"', async ({ page }) => {
    await page.goto('/');
    const v = await page.evaluate(() =>
      getComputedStyle(document.documentElement).getPropertyValue('--g-track-wide').trim()
    );
    expect(v).toBe('0.06em');
  });

  test('AC-4: .g-topo background-image enthält "ellipse"', async ({ page }) => {
    await page.goto('/');
    // .g-topo nur sichtbar wenn TopoBg auf einer Route gemountet ist. Direkt im DOM injizieren:
    const bg = await page.evaluate(() => {
      const el = document.createElement('div');
      el.className = 'g-topo';
      document.body.appendChild(el);
      const result = getComputedStyle(el).backgroundImage;
      el.remove();
      return result;
    });
    expect(bg).toContain('ellipse');
  });

  test('AC-5: .g-topo backgroundImage enthält 5x radial-gradient', async ({ page }) => {
    await page.goto('/');
    const bg = await page.evaluate(() => {
      const el = document.createElement('div');
      el.className = 'g-topo';
      document.body.appendChild(el);
      const result = getComputedStyle(el).backgroundImage;
      el.remove();
      return result;
    });
    const count = (bg.match(/radial-gradient/g) ?? []).length;
    expect(count).toBe(5);
  });

  test('AC-6: .g-topo opacity-default >= 0.4', async ({ page }) => {
    await page.goto('/');
    const opacity = await page.evaluate(() => {
      const el = document.createElement('div');
      el.className = 'g-topo';
      document.body.appendChild(el);
      const result = parseFloat(getComputedStyle(el).opacity);
      el.remove();
      return result;
    });
    expect(opacity).toBeGreaterThanOrEqual(0.4);
  });
});
```

### §6 Datei-Liste

| Art | Datei | Zweck | LoC |
|-----|-------|-------|-----|
| EDIT | `frontend/src/app.css` | 24 neue Tokens + Topo-Geometrie | +30 / -3 |
| EDIT | `frontend/src/lib/components/ui/topo/TopoBg.svelte` | Default-Prop `opacity` 0.04→0.5 | ±0 (1 Wert) |
| EDIT | `frontend/src/routes/_cockpit/ActiveTripCard.svelte` | `opacity={0.06}` entfernen | ±0 |
| EDIT | `frontend/src/routes/_design/+page.svelte` | dito | ±0 |
| NEU | `frontend/e2e/tokens-and-topo.spec.ts` | 6 Playwright-Tests | ~55 |
| **Summe** | | | **~85 LoC** |

Default-LoC-Limit 250, kein Override nötig.

## Expected Behavior

- **Input:** keine Laufzeit-Inputs. Beim Seitenaufruf liefert das gerenderte Stylesheet die zusätzlichen Tokens und das neue Topo-Pattern.
- **Output:**
  - 24 neue CSS-Variablen im `:root` verfügbar (`--g-text-*`, `--g-track-*`, `--g-s-*`).
  - `.g-topo` rendert 5 organische Ellipsen statt 2 Punkt-Ringe; Default-Opacity sichtbar.
  - TopoBg-Komponente erscheint visuell als dezente Höhenlinien-Textur.
- **Side effects:**
  - Visuelle Veränderung in `ActiveTripCard` (Cockpit) und `/_design`-Showcase: Topo-Muster deutlich sichtbar.
  - Keine Code-Pfad-Änderung in Komponenten — nur ein Svelte-Prop-Default und 2 entfernte Aufruf-Attribute.

## Acceptance Criteria

- **AC-1:** Given das Frontend ist geladen / When `getComputedStyle(document.documentElement).getPropertyValue('--g-text-md')` ausgeführt wird / Then liefert es exakt `"15px"` (Spec-konform).
  - Test: (populated after /tdd-red)

- **AC-2:** Given das Frontend ist geladen / When `--g-s-4` aus dem `:root`-Block gelesen wird / Then liefert es exakt `"16px"` als Spacing-Grid-Element 4.
  - Test: (populated after /tdd-red)

- **AC-3:** Given das Frontend ist geladen / When `--g-track-wide` aus dem `:root` gelesen wird / Then liefert es exakt `"0.06em"` (Spec-Quelle, nicht der Issue-Body-Wert `0.04em`).
  - Test: (populated after /tdd-red)

- **AC-4:** Given ein DOM-Element mit der Klasse `.g-topo` existiert / When `getComputedStyle().backgroundImage` ausgelesen wird / Then enthält der String den Substring `"ellipse"` (Spec-Geometrie statt Circle).
  - Test: (populated after /tdd-red)

- **AC-5:** Given ein DOM-Element mit der Klasse `.g-topo` existiert / When `getComputedStyle().backgroundImage` ausgelesen wird / Then enthält der String genau **5** Vorkommen von `"radial-gradient"`.
  - Test: (populated after /tdd-red)

- **AC-6:** Given ein DOM-Element mit der Klasse `.g-topo` ohne explizit gesetzten Inline-Style existiert / When `parseFloat(getComputedStyle().opacity)` gelesen wird / Then ist der Wert mindestens `0.4` (Default sichtbar).
  - Test: (populated after /tdd-red)

## Known Limitations

- **Migration auf Token-Nutzung (Tailwind → Tokens) ist nicht in Scope:** Bestehende Komponenten nutzen weiter Tailwind-Utilities; die neuen `--g-text-*`/`--g-s-*`-Tokens sind ab jetzt verfügbar, ein bewusster Migrations-Sprint folgt später.
- **Token-Naming-Drift zwischen Spec (`--g-paper`, `--g-good`, `--g-weather-*`) und Ist (`--g-surface-0`, `--g-success`, `--g-wx-*`) bleibt bestehen** — wird in #213 final geklärt; Spec wird voraussichtlich auf das gewachsene Naming aktualisiert.
- **RGBA-Alphas im Topo-Muster sind pragmatisch erhöht** gegenüber der Spec (0.10–0.14 statt 0.025–0.035), weil die Spec-Werte mit dem zusätzlichen `opacity`-Multiplier praktisch unsichtbar wären. Die Spec wird in #213 entsprechend angepasst.
- **Visuelle Verifikation post-deploy:** Die E2E-Tests sichern die CSS-Struktur, nicht die optische Wirkung. Sichtprüfung auf `/_design` und Cockpit-Karten nach Live-Schaltung.
- **Kein Snapshot-Test:** Pixel-Vergleich wäre fragil bei jeder Schriftänderung.

## Changelog

- 2026-05-13: Initial spec — Bündelt Issues #208 (Typography/Spacing/Tracking-Tokens) und #209 (Topo-Muster sichtbar machen). 24 neue CSS-Variablen in `app.css`, Topo-Geometrie auf 5 Ellipsen umgestellt, `TopoBg`-Default-Opacity von `0.04` auf `0.5` angehoben, 2 Aufrufstellen vereinfacht. 6 ACs zur CSS-Struktur-Verifikation via Playwright. ~85 LoC.

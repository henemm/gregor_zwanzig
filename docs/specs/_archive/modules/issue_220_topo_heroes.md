---
entity_id: issue_220_topo_heroes
type: module
created: 2026-05-13
updated: 2026-05-13
status: draft
version: "1.0"
parent_spec: epic_133_design_system
issues: [220]
parent_epic: 133
tags: [frontend, sveltekit, design-system, epic-133, issue-220, topo, branding]
---

# Issue #220 — Topo-Hintergrundmuster auf Hero-Bereichen sichtbar machen

## Approval

- [ ] Approved

## Purpose

Das in Issue #209 eingeführte Topo-Hintergrundmuster (5 organische Ellipsen, Default-Opacity 0.5) wird derzeit nur in `ActiveTripCard` und im Design-Showcase angezeigt. Damit es als Marken-Element erkennbar wird, soll es an drei weiteren Hero-Bereichen sichtbar werden: Cockpit-Topbar (Startseite), Trip-Detail-Hero (Overview-Tab) und Wizard-Header (Schritt-Indikator). Die Änderung ist frontend-only, ergänzt das bestehende `<TopoBg>`-Atom an drei Stellen ohne Atom-Modifikation.

## Source

- **EDIT:** `frontend/src/routes/+page.svelte` — Cockpit-Topbar mit `<TopoBg opacity={0.3}>` wrappen, Padding ergänzen
- **EDIT:** `frontend/src/lib/components/trip-detail/TripHero.svelte` — Outer-Div mit `<TopoBg opacity={0.4}>` wrappen
- **EDIT:** `frontend/src/lib/components/trip-wizard/TripWizardShell.svelte` — Header + Stepper (NICHT Step-Slots) mit `<TopoBg opacity={0.4}>` wrappen
- **NEU:** `frontend/e2e/topo-heroes.spec.ts` — Playwright-Tests für sichtbares Topo + Scope-Guard
- **Identifier:** keine neuen Code-Identifier; nur Svelte-Markup-Wraps + Imports

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/src/lib/components/ui/topo/TopoBg.svelte` | bestehend (unverändert) | Wrapper-Atom mit `opacity`-Prop und Snippet-Child |
| `frontend/src/lib/components/ui/topo/index.ts` | bestehend (unverändert) | Barrel-Export `TopoBg` |
| `frontend/src/app.css` (`.g-topo` Z. 134–145) | bestehend (unverändert) | 5 radiale Gradients + `--g-topo-opacity` Variable |
| `frontend/src/routes/+page.svelte` Z. 109–150 | bestehend (EDIT) | `<header data-testid="cockpit-topbar">` wird gewrappt |
| `frontend/src/lib/components/trip-detail/TripHero.svelte` Z. 33–43 | bestehend (EDIT) | `<div data-testid="trip-hero">` wird gewrappt |
| `frontend/src/lib/components/trip-wizard/TripWizardShell.svelte` Z. 65–70 | bestehend (EDIT) | `<header>` + `<Stepper>` werden gewrappt |
| `frontend/e2e/topo-heroes.spec.ts` | neu | E2E-Verifikation |

## Implementation Details

### §1 Cockpit-Topbar (`frontend/src/routes/+page.svelte`)

Import ergänzen:
```ts
import { TopoBg } from '$lib/components/ui/topo';
```

Den bestehenden `<header data-testid="cockpit-topbar">`-Block (Z. 109–150) **um einen TopoBg-Wrapper ergänzen**. TopoBg umschließt den Header, der Header selbst behält `data-testid` und alle inneren Strukturen. Padding (`p-6`) und Rundung (`rounded-lg`) wandern an den TopoBg-Wrapper:

```svelte
<TopoBg opacity={0.3}>
  <header
    data-testid="cockpit-topbar"
    class="flex items-center justify-between gap-4 flex-wrap p-6 rounded-lg"
  >
    <!-- bestehender Inhalt unverändert: Datum + H1, CTA-Bereich -->
  </header>
</TopoBg>
```

Die Klassen `flex items-center justify-between gap-4 flex-wrap` bleiben am `<header>`; ergänzt werden nur `p-6 rounded-lg`. TopoBg setzt selbst `relative overflow-hidden` am äußeren Container.

### §2 Trip-Detail-Hero (`frontend/src/lib/components/trip-detail/TripHero.svelte`)

Import ergänzen (oben im `<script lang="ts">`):
```ts
import { TopoBg } from '$lib/components/ui/topo';
```

Den outer `<div data-testid="trip-hero" class="trip-hero">` (Z. 33–43) **mit TopoBg wrappen**. Das outer `<div>` bleibt erhalten (TestID darf nicht umziehen), TopoBg umschließt es:

```svelte
<TopoBg opacity={0.4}>
  <div data-testid="trip-hero" class="trip-hero">
    <h1 data-testid="trip-hero-title" class="trip-hero-title">{trip.name}</h1>
    <!-- restlicher Inhalt unverändert -->
  </div>
</TopoBg>
```

Die existierende `.trip-hero { padding: 1rem }` Klasse bleibt unverändert — Innen-Padding ist ausreichend. Keine zusätzlichen Tailwind-Klassen am TopoBg.

### §3 Wizard-Header (`frontend/src/lib/components/trip-wizard/TripWizardShell.svelte`)

Import ergänzen:
```ts
import { TopoBg } from '$lib/components/ui/topo';
```

**Wrap-Scope (kritisch):** Nur `<header>` (Eyebrow + H1) + `<Stepper>` werden gewrappt. NICHT der Step-Slot (`Step1Profile` etc.), NICHT die Save-Status-Region, NICHT der Footer mit Btns.

Z. 65–70 Originalstruktur:
```svelte
<header class="mb-6 space-y-1">
  <Eyebrow>Schritt {state.currentStep} von 4</Eyebrow>
  <h1 class="text-2xl font-bold">Neuer Trip</h1>
</header>

<Stepper current={state.currentStep} labels={stepLabels} subLabels={stepSubLabels} />
```

Wird zu:
```svelte
<TopoBg opacity={0.4}>
  <div class="p-6 rounded-lg mb-6">
    <header class="space-y-1 mb-4">
      <Eyebrow>Schritt {state.currentStep} von 4</Eyebrow>
      <h1 class="text-2xl font-bold">Neuer Trip</h1>
    </header>

    <Stepper current={state.currentStep} labels={stepLabels} subLabels={stepSubLabels} />
  </div>
</TopoBg>
```

- `mb-6` wandert vom `<header>` (entfernt) an den inneren Padding-Container (am `<div>`), damit Abstand zum Step-Slot erhalten bleibt.
- `<header>` erhält neues `mb-4` für Abstand zum Stepper.
- Padding+Rundung sitzen am inneren `<div>`, nicht am `<header>` — TopoBg's `overflow-hidden` schneidet sonst die Rundung ab.

### §4 E2E-Spec (`frontend/e2e/topo-heroes.spec.ts`)

Neue Playwright-Datei mit vier Akzeptanzkriterien. Nutzt bestehende `playwright/.auth/admin.json`-Auth aus `global.setup.ts`. Verwendet den Seed-Trip `e2e-cockpit-test` (vorhanden, mit Stages 11.–13. Mai 2026).

```ts
import { test, expect } from '@playwright/test';
import { login } from './helpers.js';

test.describe('Issue #220 — Topo-Muster auf Hero-Bereichen', () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
  });

  test('AC-1: Cockpit-Topbar enthält .g-topo', async ({ page }) => {
    await page.goto('/');
    const topbar = page.getByTestId('cockpit-topbar');
    await expect(topbar).toBeVisible();
    // .g-topo ist Sibling im TopoBg-Wrapper, nicht Descendant des Headers selbst.
    // Wrapper ist Parent des Headers → .g-topo liegt im selben Wrapper.
    const hasTopo = await topbar.locator('xpath=ancestor::div[1]').locator('.g-topo').count();
    expect(hasTopo).toBeGreaterThan(0);
  });

  test('AC-2: Trip-Hero enthält .g-topo', async ({ page }) => {
    await page.goto('/trips/e2e-cockpit-test');
    const hero = page.getByTestId('trip-hero');
    await expect(hero).toBeVisible();
    const hasTopo = await hero.locator('xpath=ancestor::div[1]').locator('.g-topo').count();
    expect(hasTopo).toBeGreaterThan(0);
  });

  test('AC-3: Wizard-Header enthält .g-topo um Stepper', async ({ page }) => {
    await page.goto('/trips/new');
    const stepper = page.getByTestId('trip-wizard-stepper');
    await expect(stepper).toBeVisible();
    const hasTopo = await stepper.locator('xpath=ancestor::div[contains(@class,"relative")]//*[contains(@class,"g-topo")]').count();
    expect(hasTopo).toBeGreaterThan(0);
  });

  test('AC-4: Wizard-Topo umschließt NICHT den Step-Slot (Scope-Guard)', async ({ page }) => {
    await page.goto('/trips/new');
    const step1 = page.getByTestId('trip-wizard-step1-profile');
    await expect(step1).toBeVisible();
    // Step1Profile darf keinen .g-topo-Ancestor haben
    const topoAncestors = await step1.locator('xpath=ancestor::*[contains(@class,"g-topo")]').count();
    expect(topoAncestors).toBe(0);
  });
});
```

## Expected Behavior

- **Input:** User navigiert zu `/`, `/trips/<id>` oder `/trips/new`.
- **Output:** Sichtbares Topo-Muster im jeweiligen Hero-Bereich (Cockpit-Topbar, Trip-Hero, Wizard-Header). Pattern ist subtil (Opacity 0.3 bzw. 0.4), beeinträchtigt Lesbarkeit nicht.
- **Side effects:** Keine. DOM-Tiefe steigt pro Stelle um 2 `<div>`s (TopoBg-Outer + TopoBg-Inner). Bestehende Test-IDs bleiben am Original-Element.

## Acceptance Criteria

- **AC-1:** Given User auf `/` (Startseite, eingeloggt) / When DOM gerendert / Then `[data-testid="cockpit-topbar"]` ist sichtbar und im selben TopoBg-Wrapper befindet sich ein Element mit Klasse `.g-topo`.
  - Test: (populated after /tdd-red)

- **AC-2:** Given User auf `/trips/e2e-cockpit-test` (Overview-Tab) / When Hero gerendert / Then `[data-testid="trip-hero"]` ist sichtbar und im selben TopoBg-Wrapper befindet sich ein Element mit Klasse `.g-topo`.
  - Test: (populated after /tdd-red)

- **AC-3:** Given User auf `/trips/new` (Wizard) / When Stepper gerendert / Then `[data-testid="trip-wizard-stepper"]` hat einen TopoBg-Ancestor mit `.g-topo`-Descendant.
  - Test: (populated after /tdd-red)

- **AC-4:** Given User auf `/trips/new` / When Step 1 sichtbar / Then `[data-testid="trip-wizard-step1-profile"]` hat KEINEN Ancestor mit Klasse `.g-topo` (Scope-Guard: Topo nur um Header+Stepper, nicht um Step-Inhalte).
  - Test: (populated after /tdd-red)

- **AC-5:** Given die drei Hero-Bereiche zeigen Topo / When ein User die Inhalte liest / Then alle Texte (H1, Eyebrow, Stat-Values, Stepper-Labels) bleiben lesbar (manuelle Sichtprüfung via Screenshot, kein automatischer Test).
  - Test: visual review (Pre/Post-Screenshots in PR)

- **AC-6:** Given bestehende E2E-Specs (`epic-134-cockpit.spec.ts`, `trip-detail-hero.spec.ts`, `trip-wizard-shell.spec.ts`, `tokens-and-topo.spec.ts`) / When sie laufen nach Änderung / Then sie bleiben unverändert grün (kein Regressions-Bruch durch zusätzliche DOM-Wrapper).
  - Test: existing test suites

## Known Limitations

- **Mobile-Topbar flach:** Auf engen Viewports kann die Cockpit-Topbar durch `flex-wrap` zweizeilig werden, aber das Topo-Muster ist trotzdem nur in flachem Streifen sichtbar. Akzeptiert — Hauptfall ist Desktop.
- **Doppel-Topo im Cockpit:** Direkt unter der Topbar steht der `ActiveTripCard` mit eigenem TopoBg (Default-Opacity 0.5). Mit Topbar-Opacity 0.3 entkoppelt das visuell. Final-Kalibrierung erfolgt nach Screenshot-Review; ggf. wird Opacity nachgezogen (≤0.5, ≥0.3).
- **Stat-Tiles-Transparenz:** Die `.stat-tile`-Boxen im TripHero nutzen `background: var(--g-surface-2, rgba(0,0,0,0.03))` — das Topo-Muster scheint leicht durch. Branding-konform, akzeptiert.
- **Keine globale Opacity-Token:** Die Werte 0.3/0.4 sind hartkodiert. Eine spätere Konsolidierung in CSS-Tokens (`--g-topo-opacity-subtle`, `--g-topo-opacity-hero`) ist denkbar, aber nicht Scope dieses Issues.

## Changelog

- 2026-05-13: Initial spec created

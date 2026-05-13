---
entity_id: epic_133_step7_accent_ctas
type: module
created: 2026-05-13
updated: 2026-05-13
status: draft
version: "1.0"
parent_spec: epic_133_design_system
issues: [219]
parent_epic: 133
tags: [frontend, sveltekit, design-system, epic-133, issue-219, btn, accent]
---

# Epic #133 — Issue #219: Marken-CTAs auf Btn `variant="accent"` (Burnt-Orange)

## Approval

- [x] Approved (2026-05-13)

## Purpose

Nach der Theme-Bridge (Step 6) ist `--g-accent` (Burnt-Orange) als Marken-Farbe sichtbar verfügbar. Damit die Markenidentität auch genutzt wird, werden an 3 gezielten Stellen die Haupt-CTAs von `variant="primary"` (Ink-Schwarz) auf `variant="accent"` (Burnt-Orange) umgestellt — bewusst sparsam, damit der Akzent als Marken-Signal wirkt und nicht verwässert. Restliche Buttons (Formular-Speichern, Confirm-Dialoge, Stage-/Waypoint-CTAs, Pause/Archive) bleiben unverändert.

## Source

- **EDIT:** `frontend/src/routes/+page.svelte` Z. 142 — Cockpit/Startseite "Neuer Trip"-CTA
- **EDIT:** `frontend/src/routes/trips/+page.svelte` Z. 213 — Trips-Liste "Neuer Trip"-CTA
- **EDIT:** `frontend/src/routes/compare/+page.svelte` Z. 423 — Compare "Vergleichen"-Button
- **Identifier:** `cta-new-trip` (Cockpit), Btn-Komponente mit `variant`-Prop

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/src/lib/components/ui/btn/Btn.svelte` | bestehend (Lieferant) | Btn-Atom mit 7 Varianten inkl. `accent` (Issue #214) |
| `frontend/src/app.css` Z. 170-177 | bestehend (Style) | `[data-slot="btn"][data-variant="accent"]` mit `background-color: var(--g-accent)`, `color: var(--g-paper)`, Hover-Variante |
| `--g-accent` Token (`#c45a2a`) | bestehend (Token) | Burnt-Orange-Markenfarbe in `app.css` `:root` |
| `frontend/src/lib/components/trip-wizard/TripWizardShell.svelte` Z. 123/133 | bestehend (Referenz) | "Weiter" + "Speichern" bereits auf `variant="accent"` — Vorbild |

## Implementation Details

### §1 Cockpit/Startseite-CTA

In `frontend/src/routes/+page.svelte` Z. 142 das `variant`-Attribut anpassen:

```svelte
<!-- ALT (Z. 141-148): -->
<Btn
  variant="primary"
  data-testid="cta-new-trip"
  href="/trips/new"
  size="sm"
>
  Neuer Trip
</Btn>

<!-- NEU: -->
<Btn
  variant="accent"
  data-testid="cta-new-trip"
  href="/trips/new"
  size="sm"
>
  Neuer Trip
</Btn>
```

### §2 Trips-Liste-CTA

In `frontend/src/routes/trips/+page.svelte` Z. 213:

```svelte
<!-- ALT: -->
<Btn variant="primary" onclick={() => goto('/trips/new')}>Neuer Trip</Btn>

<!-- NEU: -->
<Btn variant="accent" onclick={() => goto('/trips/new')}>Neuer Trip</Btn>
```

### §3 Compare "Vergleichen"-Button

In `frontend/src/routes/compare/+page.svelte` Z. 423:

```svelte
<!-- ALT: -->
<Btn variant="primary" onclick={runComparison} disabled={loading}>
  {loading ? 'Lädt...' : 'Vergleichen'}
</Btn>

<!-- NEU: -->
<Btn variant="accent" onclick={runComparison} disabled={loading}>
  {loading ? 'Lädt...' : 'Vergleichen'}
</Btn>
```

### §4 Tests `frontend/e2e/accent-ctas.spec.ts`

3 Playwright-Tests entsprechend AC-1…AC-3. Prüfen das `data-variant`-Attribut, das die Btn-Komponente aus dem `variant`-Prop rendert.

```typescript
import { test, expect } from '@playwright/test';
import { login } from './helpers.js';

test.describe('Epic #133 Step 7 — Marken-CTAs auf accent (Issue #219)', () => {
	test.beforeEach(async ({ page }) => {
		await login(page);
	});

	test('AC-1: Cockpit "Neuer Trip"-CTA hat variant="accent"', async ({ page }) => {
		await page.goto('/');
		const cta = page.getByTestId('cta-new-trip');
		await expect(cta).toBeVisible();
		await expect(cta).toHaveAttribute('data-variant', 'accent');
	});

	test('AC-2: Trips-Liste "Neuer Trip"-Button hat variant="accent"', async ({ page }) => {
		await page.goto('/trips');
		const cta = page.getByRole('button', { name: 'Neuer Trip' });
		await expect(cta).toBeVisible();
		await expect(cta).toHaveAttribute('data-variant', 'accent');
	});

	test('AC-3: Compare "Vergleichen"-Button hat variant="accent"', async ({ page }) => {
		await page.goto('/compare');
		const cta = page.getByRole('button', { name: /Vergleichen/i });
		await expect(cta).toBeVisible();
		await expect(cta).toHaveAttribute('data-variant', 'accent');
	});
});
```

### §5 Datei-Liste

| Art | Datei | Zweck | LoC |
|-----|-------|-------|-----|
| EDIT | `frontend/src/routes/+page.svelte` | Z. 142: `variant="primary"` → `variant="accent"` | 1 Zeile |
| EDIT | `frontend/src/routes/trips/+page.svelte` | Z. 213: dito | 1 Zeile |
| EDIT | `frontend/src/routes/compare/+page.svelte` | Z. 423: dito | 1 Zeile |
| NEU | `frontend/e2e/accent-ctas.spec.ts` | 3 Playwright-Tests | ~35 LoC |
| **Summe** | | | **~38 LoC** |

Default-LoC-Limit 250, kein Override nötig.

## Expected Behavior

- **Input:** kein Laufzeit-Input. Edit greift beim CSS-Build, sichtbar beim Seitenaufruf.
- **Output (visuell):**
  - Cockpit/Startseite: Top-rechts "Neuer Trip"-Button in Burnt-Orange statt Ink-Schwarz.
  - Trips-Liste: Top-rechts "Neuer Trip"-Button in Burnt-Orange.
  - Compare: "Vergleichen"-Button in Burnt-Orange.
- **Output (DOM):** Die 3 Buttons haben `data-variant="accent"` statt `data-variant="primary"`.
- **Side effects:**
  - Keine Verhaltensänderung (selber Click-Handler, selbes Routing, selbe Disabled-Logik).
  - Bestehende E2E-Tests (`trips.spec.ts`, `trip-wizard.spec.ts`, `epic-134-cockpit.spec.ts`, `orts-vergleich-c1/c3.spec.ts`, `adhoc-to-abo.spec.ts`) bleiben grün — sie selektieren via `getByRole('button', { name: ... })` oder `getByTestId('cta-new-trip')`, beides unverändert.
- **Failure mode:** Falls die Btn-Komponente das `variant`-Prop nicht als `data-variant`-Attribut rendert, schlagen die ACs fehl. Bekanntes Verhalten seit Issue #214 — `data-slot="btn"` mit `data-variant` ist Vertrag der Btn-Komponente.

## Acceptance Criteria

- **AC-1:** Given das Frontend ist im Light-Mode geladen und der User ist auf `/` (Cockpit) / When `getByTestId('cta-new-trip')` lokalisiert wird / Then hat das Element das Attribut `data-variant="accent"` — der Marken-Akzent ist auf dem zentralen Cockpit-CTA aktiv.
  - Test: `frontend/e2e/accent-ctas.spec.ts` (§4)

- **AC-2:** Given das Frontend ist geladen und der User ist auf `/trips` (Trips-Liste) / When der Button mit Text "Neuer Trip" lokalisiert wird / Then hat das Element das Attribut `data-variant="accent"` — der Marken-Akzent ist auf dem Trips-Liste-CTA aktiv.
  - Test: `frontend/e2e/accent-ctas.spec.ts` (§4)

- **AC-3:** Given das Frontend ist geladen und der User ist auf `/compare` / When der Button mit Text "Vergleichen" (case-insensitive) lokalisiert wird / Then hat das Element das Attribut `data-variant="accent"` — der Marken-Akzent ist auf dem Compare-CTA aktiv.
  - Test: `frontend/e2e/accent-ctas.spec.ts` (§4)

## Known Limitations

- **Wizard Step 4 "Speichern" wurde nicht editiert:** Der Button in `frontend/src/lib/components/trip-wizard/TripWizardShell.svelte` Z. 133 ist bereits seit längerem auf `variant="accent"` — Punkt 3 aus dem Issue-Body ist deshalb implizit erfüllt, ohne Codeänderung.
- **Cockpit Top-CTA (Punkt 5 optional im Issue) = Startseite "Neuer Trip" (Punkt 1):** Beide Pfade führen auf denselben Button — eine einzige Edit-Stelle reicht.
- **Andere "Neuer Trip"-Buttons unberührt:** In `trips/+page.svelte` Z. 225 existiert ein Empty-State-Button `<Btn variant="outline">Ersten Trip erstellen</Btn>` — gemäß Issue bleibt der `outline` (sekundäre Aktion im leeren Zustand).
- **Pre/Post-Screenshots manuell:** Sichtprüfung auf `/`, `/trips`, `/compare` parallel zur Implementierung. Kein Visual-Regression-Tooling für 3 Wort-Edits.
- **Konsistenz bei späteren CTAs:** Wenn neue Haupt-CTAs hinzukommen (z.B. "Neue Subscription"), muss die Marken-Akzent-Linie bewusst entschieden werden. Spec dokumentiert die kuratorischen Regeln explizit (Forms/Confirm-Dialoge bleiben `primary`).

## Changelog

- 2026-05-13: Initial spec — Issue #219, 3 gezielte Btn-Variant-Umstellungen (`primary` → `accent`) an Cockpit-CTA, Trips-Liste-CTA und Compare-Button. ~38 LoC inkl. 3 Playwright-AC-Tests. AC-N-Pflicht erfüllt (3 ACs im Given/When/Then-Format, alle >=30 Zeichen). Wizard-Save-Button ist bereits accent (Issue-Punkt implizit erfüllt).

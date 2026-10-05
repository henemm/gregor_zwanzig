// Playwright E2E — Mobile Etappen-Tab: Listen-only ohne Karte/Profil
//
// Spec: docs/specs/modules/mobile_stages_tab_listen_only.md (Iteration 1)
// Soll: docs/design-requests/mobile_usability_stages_soll.md (PO-Entscheid F5,
// Variante B — Karte + Höhenprofil entfallen auf Mobile ersatzlos).
//
// Verhalten: Auf Mobile (<900px) zeigt der stages-Tab eine vertikale
// StageCardM-Liste + neutralen Desktop-Hinweis; Karte, Profil-Sheet,
// EtappenStrip und StageSelectSheet sind IM DOM ENTFALLEN (nicht nur
// versteckt). Auf Desktop (>=900px) ist der Editor 1:1 unverändert.
//
// Ausführung:
//   cd frontend && npx playwright test mobile-stages-listen-only.spec.ts

import { test, expect } from '@playwright/test';

// Seed-Trip aus global.setup.ts (3 Etappen, 2 mit Wegpunkten)
const TRIP_ID = 'e2e-cockpit-test';
const STAGES_URL = `/trips/${TRIP_ID}?tab=stages`;

const DESKTOP_HINT_TEXT = /Karte & Höhenprofil sind am Desktop verfügbar/;

async function openStagesTab(page: import('@playwright/test').Page, width: number, height: number) {
	await page.setViewportSize({ width, height });
	await page.goto(STAGES_URL);
	await expect(page.getByTestId('edit-stages-panel')).toBeVisible({ timeout: 10_000 });
}

// =============================================================================
// Mobile (<900px): Listen-only — Karte/Profil/Strip entfallen im DOM
// =============================================================================

test('Mobile: stages-Tab ist listen-only — Karte/Profil/Strip nicht im DOM', async ({ page }) => {
	await openStagesTab(page, 390, 844);

	// DOM-Entfall (AC-1): keine Karte, kein Profil-Sheet, kein Strip, kein Switcher
	await expect(page.getByTestId('map-canvas')).toHaveCount(0);
	await expect(page.getByTestId('profile-sheet-host')).toHaveCount(0);
	await expect(page.getByTestId('etappen-strip-wrapper')).toHaveCount(0);
	await expect(page.getByTestId('stage-switcher-pill')).toHaveCount(0);

	// Stattdessen: vertikale Liste + Desktop-Hinweis (AC-2)
	const hint = page.getByTestId('desktop-hint');
	await expect(hint).toBeVisible();
	await expect(hint).toContainText(DESKTOP_HINT_TEXT);
	await expect(page.getByTestId('stage-cardm')).toHaveCount(3);
});

test('Mobile: kein horizontaler Overflow im stages-Tab', async ({ page }) => {
	await openStagesTab(page, 390, 844);
	await expect(page.getByTestId('stage-cardm').first()).toBeVisible();

	const overflow = await page.evaluate(() => {
		const se = document.scrollingElement ?? document.documentElement;
		return se.scrollWidth - window.innerWidth;
	});
	expect(overflow).toBeLessThanOrEqual(0);
});

test('Mobile: langer Trip-Titel steht einzeilig in 20px mit Ellipsis', async ({ page }) => {
	await openStagesTab(page, 390, 844);

	const h1 = page.locator('[data-testid="trip-detail-h1"]');
	await expect(h1).toBeVisible();
	const metrics = await h1.evaluate((el) => {
		const cs = getComputedStyle(el);
		return { fontSize: cs.fontSize, scrollWidth: el.scrollWidth, clientWidth: el.clientWidth };
	});
	expect(metrics.fontSize).toBe('20px');
	expect(metrics.scrollWidth).toBeLessThanOrEqual(metrics.clientWidth + 1);
});

// =============================================================================
// Iteration 2 — F7: aufklappbare Wegpunkt-Zeilen, F3: Pause-Wahl, F2: Cascade inline
// =============================================================================

test('Mobile: Tap auf Etappen-Karte klappt Wegpunkt-Zeilen auf und zu', async ({ page }) => {
	await openStagesTab(page, 390, 844);

	const firstCard = page.getByTestId('stage-cardm').first();
	// Standard: zu — keine Wegpunkt-Zeilen im DOM-Bereich sichtbar
	await expect(page.getByTestId('stage-cardm-wp-row')).toHaveCount(0);
	await expect(firstCard.getByTestId('stage-cardm-chevron')).toBeVisible();

	// Tap → aufgeklappt: Zeilen der ersten Etappe (Seed: 2 Wegpunkte 'Start'/'Zwischenstopp')
	await firstCard.click();
	await expect(firstCard.getByTestId('stage-cardm-wp-row')).toHaveCount(2);
	await expect(firstCard.getByTestId('stage-cardm-wp-row').first()).toContainText('Start');
	await expect(firstCard.getByTestId('stage-cardm-wp-row').first()).toContainText('800');
	const expanded = await firstCard.getAttribute('data-open');
	expect(expanded).toBe('true');

	// Zweiter Tap → wieder zu
	await firstCard.click();
	await expect(page.getByTestId('stage-cardm-wp-row')).toHaveCount(0);
});

test('Mobile: + Etappe bietet Wahl Etappe/Pausentag; Pausentag landet in der Liste', async ({ page }) => {
	await openStagesTab(page, 390, 844);
	const countBefore = await page.getByTestId('stage-cardm').count();

	await page.getByTestId('mobile-add-stage').click();
	const choice = page.getByTestId('mobile-add-choice');
	await expect(choice).toBeVisible();
	await expect(choice.getByRole('menuitem', { name: 'Etappe' })).toBeVisible();
	await expect(choice.getByRole('menuitem', { name: 'Pausentag' })).toBeVisible();

	await choice.getByRole('menuitem', { name: 'Pausentag' }).click();
	await expect(page.getByTestId('stage-cardm')).toHaveCount(countBefore + 1);
	await expect(page.locator('[data-testid="stage-cardm"][data-pause="true"]')).toHaveCount(1);
});

test('Mobile: Cascade-Banner steht inline vor der Liste, nicht fixiert', async ({ page }) => {
	// Kaskade nur über das Datumsfeld auslösbar (Desktop-Zweig) — Zustand
	// überlebt den Wechsel in den Mobile-Zweig und muss dort INLINE stehen.
	await openStagesTab(page, 1280, 900);
	const dateInput = page.getByTestId('stage-date-field').first().locator('input[type="date"]');
	await expect(dateInput).toBeVisible({ timeout: 10_000 });
	const nextWeek = new Date(Date.now() + 7 * 86400000).toISOString().slice(0, 10);
	await dateInput.fill(nextWeek);
	await expect(page.getByTestId('cascade-strip')).toBeVisible({ timeout: 10_000 });

	await page.setViewportSize({ width: 390, height: 844 });
	const strip = page.getByTestId('cascade-strip');
	await expect(strip).toBeVisible();
	const position = await strip.evaluate((el) => getComputedStyle(el).position);
	expect(position).not.toBe('fixed');
	// Inline = im Panel-Dokumentenfluss: Oberkante unterhalb der Listen-Kopfzeile
	const hintBox = await page.getByTestId('mobile-stages-list').boundingBox();
	const stripBox = await strip.boundingBox();
	expect(stripBox).not.toBeNull();
	expect(hintBox).not.toBeNull();
	expect(stripBox!.y).toBeGreaterThan(hintBox!.y);
});

// =============================================================================
// Desktop (>=900px): Editor unverändert (Karte + Profil + Strip vorhanden)
// =============================================================================

test('Desktop: Editor bleibt 1:1 — Karte, Profil, Strip vorhanden', async ({ page }) => {
	await openStagesTab(page, 1280, 900);

	// Desktop-Karte ist die im editor-grid (map-card).
	const DESKTOP_MAP_CANVAS = '[data-testid="map-card"] [data-testid="map-canvas"]';
	await expect(page.locator(DESKTOP_MAP_CANVAS)).toBeVisible({ timeout: 10_000 });
	await expect(page.getByTestId('profile-editor')).toBeVisible();
	await expect(page.getByTestId('etappen-strip-wrapper')).toBeVisible();

	// Listen-only-Mobile-Elemente dürfen auf Desktop nicht existieren
	await expect(page.getByTestId('desktop-hint')).toHaveCount(0);
	await expect(page.getByTestId('stage-cardm')).toHaveCount(0);
});

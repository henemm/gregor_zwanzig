// E2E-Tests fuer Epic #136 Sub-Spec #163 (Step 3: Wegpunkt-Vorschlaege bestaetigen).
//
// Spec-Referenz: docs/specs/modules/epic_136_step3_waypoints.md
// Issue: #163
//
// TestID-Inventar (Sub-Spec §9):
//   trip-wizard-step3-container
//   trip-wizard-step3-stages-list
//   trip-wizard-step3-stage-row-{i}
//   trip-wizard-step3-stage-pill-{i}
//   trip-wizard-step3-pause-marker-{i}
//   trip-wizard-step3-profile-chart
//   trip-wizard-step3-waypoints-list
//   trip-wizard-step3-waypoint-row-{i}
//   trip-wizard-step3-confirm-{i}
//   trip-wizard-step3-reject-{i}
//   trip-wizard-step3-empty-no-stages
//   trip-wizard-step3-empty-only-pauses
//   trip-wizard-step3-empty-no-waypoints
//
// Dieses Skelett deckt die per E2E pruefbaren ACs ab (Subset von 25):
//   AC#1, AC#2, AC#3, AC#4, AC#5, AC#6, AC#7, AC#9, AC#11, AC#12, AC#13,
//   AC#19, AC#20, AC#22, AC#23
// Unit-only: AC#14–18, AC#21 (siehe wizardState.test.ts).
// Build-only: AC#25.
//
// RED-Phase: Step3Waypoints.svelte ist heute ein 8-Zeilen-Stub ohne TestIDs —
// alle Tests scheitern in dieser Phase wie erwartet.

import { test, expect, type Page } from '@playwright/test';
import { login, fillStep1, fillStep2, type Step1Input } from './helpers.js';
import * as path from 'node:path';

const DEFAULT_STEP1: Step1Input = {
	activity: 'trekking',
	name: 'Step3-Test',
	startDate: '2026-06-01'
};

const FIXTURE_DIR = path.resolve('./e2e/fixtures');
const TEST_GPX = path.resolve(FIXTURE_DIR, 'test-trip.gpx');

/**
 * Navigiert zu Step 3 mit einer einzelnen GPX-Etappe (default-Fixture).
 * Nutzt fillStep1 + fillStep2 (Default = test-trip.gpx).
 */
async function gotoStep3(page: Page) {
	await page.goto('/trips/new');
	await fillStep1(page, DEFAULT_STEP1);
	await page.getByTestId('trip-wizard-next').click();
	await fillStep2(page);
	await page.getByTestId('trip-wizard-next').click();
	await expect(page.getByTestId('trip-wizard-step3-container')).toBeVisible();
}

test.describe('Trip-Wizard Step 3 — Wegpunkt-Vorschlaege bestaetigen (#163)', () => {
	test.beforeEach(async ({ page }) => {
		await login(page);
	});

	test('AC#1: Step3-Container mit TestID trip-wizard-step3-container ist sichtbar', async ({
		page
	}) => {
		await gotoStep3(page);
		await expect(page.getByTestId('trip-wizard-step3-container')).toBeVisible();
	});

	test('AC#2: Linke Liste zeigt alle Stages inkl. Pausentage', async ({ page }) => {
		await gotoStep3(page);
		// 1 Etappe + (in Step 2 inserted Pause) — hier nur 1 Etappe ohne Pause.
		await expect(page.getByTestId('trip-wizard-step3-stages-list')).toBeVisible();
		await expect(page.getByTestId('trip-wizard-step3-stage-row-0')).toBeVisible();
	});

	test('AC#3: Pausentage in linker Liste sind nicht klickbar (TestID pause-marker)', async ({
		page
	}) => {
		// Setup: 1 Etappe + 1 Pause via Step 2
		await page.goto('/trips/new');
		await fillStep1(page, DEFAULT_STEP1);
		await page.getByTestId('trip-wizard-next').click();
		const fileInput = page.locator('input[type="file"][accept=".gpx"]');
		await fileInput.setInputFiles([TEST_GPX]);
		await page.getByTestId('trip-wizard-step2-bulk-commit').click();
		await page.getByTestId('trip-wizard-step2-stage-row-0').waitFor({ state: 'visible' });
		await page.getByTestId('trip-wizard-step2-pause-after-0').click({ force: true });
		await page.getByTestId('trip-wizard-step2-pause-marker-1').waitFor({ state: 'visible' });
		await page.getByTestId('trip-wizard-next').click();
		await expect(page.getByTestId('trip-wizard-step3-container')).toBeVisible();
		// Pause-Marker existiert
		await expect(page.getByTestId('trip-wizard-step3-pause-marker-1')).toBeVisible();
		// Nicht klickbar: pointer-events: none ODER kein onclick-Handler
		const pauseEl = page.getByTestId('trip-wizard-step3-pause-marker-1');
		const pe = await pauseEl.evaluate((el) => getComputedStyle(el).pointerEvents);
		expect(pe).toBe('none');
	});

	test('AC#4: Klick auf Nicht-Pause-Stage setzt diese aktiv (visuelles Highlight)', async ({
		page
	}) => {
		await gotoStep3(page);
		const row0 = page.getByTestId('trip-wizard-step3-stage-row-0');
		await row0.click();
		// Aktive Stage hat data-active="true" oder aria-current="true" (Implementation entscheidet).
		// Wir pruefen min. eine der beiden Markierungen.
		const isActive = await row0.evaluate((el) => {
			return (
				el.getAttribute('data-active') === 'true' ||
				el.getAttribute('aria-current') === 'true' ||
				el.getAttribute('aria-selected') === 'true'
			);
		});
		expect(isActive).toBe(true);
	});

	test('AC#5: Init: erste Nicht-Pause-Stage ist aktiv ohne Klick', async ({ page }) => {
		await gotoStep3(page);
		const row0 = page.getByTestId('trip-wizard-step3-stage-row-0');
		const isActive = await row0.evaluate((el) => {
			return (
				el.getAttribute('data-active') === 'true' ||
				el.getAttribute('aria-current') === 'true' ||
				el.getAttribute('aria-selected') === 'true'
			);
		});
		expect(isActive).toBe(true);
	});

	test('AC#6: ProfileChart hat aria-label „Hoehenprofil mit N Wegpunkten"', async ({ page }) => {
		await gotoStep3(page);
		const chart = page.getByTestId('trip-wizard-step3-profile-chart');
		await expect(chart).toBeVisible();
		const label = await chart.getAttribute('aria-label');
		expect(label).toMatch(/Hoehenprofil mit \d+ Wegpunkten/);
	});

	test('AC#7: ProfileChart zeigt gestrichelte Pins fuer suggested:true-Waypoints', async ({
		page
	}) => {
		await gotoStep3(page);
		const chart = page.getByTestId('trip-wizard-step3-profile-chart');
		await expect(chart).toBeVisible();
		// Mindestens ein <circle> hat stroke-dasharray (gestrichelt).
		const dashedCount = await chart.evaluate((el) => {
			const circles = el.querySelectorAll('circle');
			let count = 0;
			circles.forEach((c) => {
				const da = c.getAttribute('stroke-dasharray');
				if (da && da.length > 0 && da !== 'none') count++;
			});
			return count;
		});
		expect(dashedCount).toBeGreaterThan(0);
	});

	test('AC#9: Waypoint-Liste rendert Rows mit TestID trip-wizard-step3-waypoint-row-{i}', async ({
		page
	}) => {
		await gotoStep3(page);
		await expect(page.getByTestId('trip-wizard-step3-waypoints-list')).toBeVisible();
		await expect(page.getByTestId('trip-wizard-step3-waypoint-row-0')).toBeVisible();
	});

	test('AC#11: Bestaetigen-Button nur sichtbar wenn waypoint.suggested === true', async ({
		page
	}) => {
		await gotoStep3(page);
		// Initial: alle Waypoints suggested (vom addStage-Patch) → Button sichtbar.
		await expect(page.getByTestId('trip-wizard-step3-confirm-0')).toBeVisible();
		// Klick bestaetigt → Button verschwindet.
		await page.getByTestId('trip-wizard-step3-confirm-0').click();
		await expect(page.getByTestId('trip-wizard-step3-confirm-0')).not.toBeVisible();
	});

	test('AC#12: Klick Bestaetigen: Pin wird solid, Bestaetigen-Button verschwindet', async ({
		page
	}) => {
		await gotoStep3(page);
		const chart = page.getByTestId('trip-wizard-step3-profile-chart');
		const dashedBefore = await chart.evaluate((el) => {
			let count = 0;
			el.querySelectorAll('circle').forEach((c) => {
				const da = c.getAttribute('stroke-dasharray');
				if (da && da.length > 0 && da !== 'none') count++;
			});
			return count;
		});
		expect(dashedBefore).toBeGreaterThan(0);

		await page.getByTestId('trip-wizard-step3-confirm-0').click();
		await expect(page.getByTestId('trip-wizard-step3-confirm-0')).not.toBeVisible();

		const dashedAfter = await chart.evaluate((el) => {
			let count = 0;
			el.querySelectorAll('circle').forEach((c) => {
				const da = c.getAttribute('stroke-dasharray');
				if (da && da.length > 0 && da !== 'none') count++;
			});
			return count;
		});
		expect(dashedAfter).toBe(dashedBefore - 1);
	});

	test('AC#13: Klick Verwerfen: Waypoint-Row + Pin verschwinden', async ({ page }) => {
		await gotoStep3(page);
		const chart = page.getByTestId('trip-wizard-step3-profile-chart');
		const pinsBefore = await chart.evaluate((el) => el.querySelectorAll('circle').length);
		expect(pinsBefore).toBeGreaterThan(0);

		await page.getByTestId('trip-wizard-step3-reject-0').click();

		const pinsAfter = await chart.evaluate((el) => el.querySelectorAll('circle').length);
		expect(pinsAfter).toBe(pinsBefore - 1);
	});

	test('AC#19: Weiter-Button ist in Step 3 immer enabled (auch ohne Aktion)', async ({ page }) => {
		await gotoStep3(page);
		await expect(page.getByTestId('trip-wizard-next')).toBeEnabled();
	});

	// AC#20 (Empty-State §8a: keine Stages) ist per E2E nicht erreichbar — der
	// Stepper ist nicht klickbar (nur Weiter/Zurueck-Navigation), und Step 2
	// blockt Weiter mit canAdvanceStep2 = false bei 0 Etappen. Der Empty-State
	// ist defensive Programmierung fuer kuenftige Pfade (z.B. Deep-Link
	// /trips/new?step=3). E2E-Coverage entfaellt; der Empty-State-Render-Branch
	// ist statisch im Step3Waypoints-Markup verifiziert.
	test.skip('AC#20: Empty-State §8a (keine Stages) — nicht via UserFlow erreichbar', async () => {
		// intentionally skipped — see comment above
	});

	test('AC#22: Empty-State §8c (alle Waypoints verworfen) → trip-wizard-step3-empty-no-waypoints', async ({
		page
	}) => {
		await gotoStep3(page);
		const rows = page.getByTestId(/^trip-wizard-step3-waypoint-row-/);
		// Sicherheits-Cap; in der Praxis hat eine GPX-Etappe selten >20 Waypoints.
		for (let i = 0; i < 100; i++) {
			const remaining = await rows.count();
			if (remaining === 0) break;
			await page.getByTestId('trip-wizard-step3-reject-0').click();
			// Auf DOM-Aktualisierung nach Klick warten.
			await expect(rows).toHaveCount(remaining - 1);
		}
		await expect(page.getByTestId('trip-wizard-step3-empty-no-waypoints')).toBeVisible();
	});

	test('AC#23: fillStep3() ohne Param klickt Weiter und landet in Step 4', async ({ page }) => {
		await gotoStep3(page);
		// Weiter-Button klicken — sollte ohne weitere Aktionen funktionieren
		// (canAdvanceStep3 = true). Sub-Spec #164 §11 hat den TestID von
		// `trip-wizard-step4-briefings` auf `trip-wizard-step4-container`
		// migriert.
		await page.getByTestId('trip-wizard-next').click();
		await expect(page.getByTestId('trip-wizard-step4-container')).toBeVisible();
	});
});

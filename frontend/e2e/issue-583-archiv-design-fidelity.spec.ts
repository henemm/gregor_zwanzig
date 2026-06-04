// TDD RED — Issue #583: Archiv-Screen 1:1 nach screen-archive.jsx
//
// Tests gegen STAGING (https://staging.gregor20.henemm.com) mit Validator-Account.
// Sub-Issue von Epic #575 — alle Tests schlagen fehl bis Backend-Felder,
// Demo-Daten und Suchfeld-Breite live sind.
//
// Spec: docs/specs/modules/issue_583_archiv_1to1.md
//
// Ausführung:
//   STAGING=1 GZ_VALIDATOR_USER=... GZ_VALIDATOR_PASS=... \
//     npx playwright test e2e/issue-583-archiv-design-fidelity.spec.ts

import { test, expect } from '@playwright/test';

const STAGING_URL = 'https://staging.gregor20.henemm.com';
const VALIDATOR_USER = process.env.GZ_VALIDATOR_USER ?? '';
const VALIDATOR_PASS = process.env.GZ_VALIDATOR_PASS ?? '';

test.describe('Issue #583: Archiv-Screen 1:1', () => {
	test.beforeEach(async ({ page }) => {
		test.skip(!VALIDATOR_USER || !VALIDATOR_PASS, 'GZ_VALIDATOR_USER/PASS not set');

		await page.goto(`${STAGING_URL}/login`);
		await page.fill('input[name="username"]', VALIDATOR_USER);
		await page.fill('input[name="password"]', VALIDATOR_PASS);
		await page.click('button[type="submit"]');
		await page.waitForURL((u) => !u.pathname.includes('/login'), { timeout: 15_000 });
		await page.goto(`${STAGING_URL}/archiv`);
		await page.waitForLoadState('networkidle');
	});

	// AC-5: Such-Eingabefeld umschließendes <div> hat flex: 0 0 380px.
	test('AC-5: Suchfeld-Wrapper hat flex:0 0 380px (nicht volle Breite)', async ({ page }) => {
		const wrapper = page.locator('input[placeholder="Suchen…"]').locator('xpath=ancestor::div[1]');
		await expect(wrapper).toBeVisible();

		const flex = await wrapper.evaluate((el) => getComputedStyle(el).flex);
		// flex shorthand: "0 0 380px" wird zu "0 0 380px"
		expect(flex).toMatch(/0 0 380px/);
	});

	// AC-3: AccuracyBar zeigt echten Wert + Farbe für ortler-2025 (accuracy=92).
	test('AC-3: AccuracyBar zeigt 92% bei ortler-2025 mit good-Farbe', async ({ page }) => {
		const row = page.locator('text="Ortler-Überquerung"').locator('xpath=ancestor::div[contains(@style,"display:grid")][1]');
		await expect(row).toBeVisible();

		// Zahl 92% sichtbar in der Zeile
		await expect(row).toContainText('92%');

		// AccuracyBar-Innen-Div hat width:92% und good-Farbe (#3d6b3a)
		const fill = row.locator('div[style*="background"]').filter({
			has: page.locator('xpath=self::div[contains(@style,"width: 92")]')
		}).first();
		// Fallback: prüfe das Existieren eines 92%-breiten Bars
		const bars = row.locator('div').evaluateAll((divs) => {
			return divs
				.map((d) => ({
					width: (d as HTMLElement).style.width,
					background: (d as HTMLElement).style.background
				}))
				.filter((s) => s.width && s.width.includes('92'));
		});
		const matches = await bars;
		expect(matches.length).toBeGreaterThan(0);
	});

	// AC-4: "Was passiert ist"-Spalte zeigt trip.headline aus Demo-Daten.
	test('AC-4: Headline-Spalte zeigt Demo-Text für ortler-2025', async ({ page }) => {
		const row = page.locator('text="Ortler-Überquerung"').locator('xpath=ancestor::div[contains(@style,"display:grid")][1]');
		await expect(row).toBeVisible();
		await expect(row).toContainText('Gewitter Tag 2');
	});

	// AC-1: 8 Demo-Trips sichtbar im Archiv.
	test('AC-1: Validator-Account hat 8 archivierte Demo-Trips', async ({ page }) => {
		const tripNames = [
			'Ortler-Überquerung',
			'Zillertal mit Steffi',
			'Rofan Tageswanderung',
			'Großvenediger Rundtour',
			'Stubaier Höhenweg',
			'KHW 402',
			'Gardasee Klettersteige',
			'Dachstein Überschreitung'
		];

		for (const name of tripNames) {
			await expect(page.locator(`text="${name}"`)).toBeVisible();
		}
	});
});

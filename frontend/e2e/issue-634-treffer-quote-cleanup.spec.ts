// TDD RED — Issue #634: Reste der erfundenen Forecast-Treffer-Quote entfernen
//
// Behavior-Test gegen STAGING (https://staging.gregor20.henemm.com) als eingeloggter
// Validator. /_design-system ist NICHT öffentlich → Login nötig.
//
// RED vor Fix: Staging zeigt im Stat-Showcase noch "Treffer Ø" / "87%" → AC-1 schlägt fehl.
// GREEN nach Deploy: die erfundene Metrik ist entfernt, der Stat-Showcase bleibt sichtbar.
//
// Spec: docs/specs/modules/issue_634_treffer_quote_cleanup.md
//
// Ausführung:
//   GZ_VALIDATOR_USER=... GZ_VALIDATOR_PASS=... \
//     npx playwright test e2e/issue-634-treffer-quote-cleanup.spec.ts

import { test, expect } from '@playwright/test';

const STAGING_URL = process.env.GZ_SVELTE_BASE ?? 'https://staging.gregor20.henemm.com';
const VALIDATOR_USER = process.env.GZ_VALIDATOR_USER ?? '';
const VALIDATOR_PASS = process.env.GZ_VALIDATOR_PASS ?? '';

async function login(page) {
	await page.goto(`${STAGING_URL}/login`);
	await page.fill('input[name="username"]', VALIDATOR_USER);
	await page.fill('input[name="password"]', VALIDATOR_PASS);
	await page.click('button[type="submit"]');
	await page.waitForURL((u) => !u.pathname.includes('/login'), { timeout: 15_000 });
}

test.describe('Issue #634: Forecast-Treffer-Quote entfernt', () => {
	test.beforeEach(async ({ page }) => {
		test.skip(!VALIDATOR_USER || !VALIDATOR_PASS, 'GZ_VALIDATOR_USER/PASS not set');
		await login(page);
	});

	// AC-1: Design-System-Showcase zeigt keine erfundene "Treffer Ø"-Metrik mehr,
	//        der Stat-Showcase rendert aber weiterhin (inkl. accent-Variante).
	test('AC-1: /_design-system zeigt kein "Treffer Ø" mehr, Stat-Showcase bleibt', async ({ page }) => {
		await page.goto(`${STAGING_URL}/_design-system`);
		await page.waitForLoadState('networkidle');

		// Die erfundene Metrik darf nicht mehr auftauchen
		await expect(page.getByText('Treffer Ø', { exact: false })).toHaveCount(0);
		await expect(page.getByText('87%', { exact: false })).toHaveCount(0);

		// Der Stat-Showcase-Block existiert weiterhin (Panel-Titel "Stat · zwei Layouts")
		await expect(page.getByText(/Stat\s*·\s*zwei Layouts/)).toBeVisible();
		// und zeigt weiterhin reale inline-Stats (z.B. "Trips" / "Briefings")
		await expect(page.getByText('Briefings', { exact: false }).first()).toBeVisible();
	});

	// AC-2: Die generische Stat-Komponente ist intakt — Trips-Liste lädt mit Kennzahlen.
	test('AC-2: /trips lädt weiterhin (Stat-Komponente nicht beschädigt)', async ({ page }) => {
		await page.goto(`${STAGING_URL}/trips`);
		await page.waitForLoadState('networkidle');
		// Seite gerendert, kein Crash
		await expect(page.locator('body')).toBeVisible();
		await expect(page).toHaveURL(/\/trips/);
	});
});

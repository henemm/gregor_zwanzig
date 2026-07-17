// E2E (Staging) — Issue #1261 (a): Compare-Detailseite (Desktop) — Mobile-
// Regressionswächter + Draft-Ausnahme.
//
// Ursprünglich Spec: docs/specs/modules/issue_1261_compare_edit_autosave.md
//   § Acceptance Criteria AC-1..AC-4. AC-1 (Desktop-Header-"Bearbeiten") und
// AC-2 (Kebab-"Bearbeiten") wurden mit Epic #1273 S4a entfernt — die
// getesteten Einstiegspunkte existieren seit S3 nicht mehr (siehe
// docs/specs/modules/epic_1273_s4a_test_migration.md § AC-4).
//
// Echter Klick-Pfad (Kebab-Klick statt goto), Auth ueber die im
// playwright.config.ts hinterlegte storageState (kein Login pro Test —
// vermeidet das Staging-Auth-Rate-Limit, #703).
//
// Ausführen (gegen Staging, aus frontend/):
//   npx playwright test e2e/compare-detail-edit-entry.spec.ts --config playwright.config.ts

import { test, expect, type Page } from '@playwright/test';

let createdIds: string[] = [];
let createdLocationIds: string[] = [];

test.afterEach(async ({ page }) => {
	for (const id of createdIds) {
		try {
			await page.request.delete(`/api/compare/presets/${id}`);
		} catch {
			/* Staging-Hygiene: Cleanup-Fehler ist nicht test-kritisch */
		}
	}
	createdIds = [];
	for (const id of createdLocationIds) {
		try {
			await page.request.delete(`/api/locations/${id}`);
		} catch {
			/* Staging-Hygiene: Cleanup-Fehler ist nicht test-kritisch */
		}
	}
	createdLocationIds = [];
});

async function createLocation(page: Page, name: string, lat: number, lon: number): Promise<string> {
	const res = await page.request.post('/api/locations', { data: { name, lat, lon } });
	expect(res.ok(), 'Location-Anlage fehlgeschlagen: ' + res.status()).toBeTruthy();
	const body = await res.json();
	createdLocationIds.push(body.id);
	return body.id as string;
}

// deriveStatusFromPreset() (subscriptionHelpers.ts) braucht Name + mind. 1 Ort
// fuer active/paused — leere location_ids faellt sonst auf "draft" zurueck.
async function createPresetWithLocation(
	page: Page,
	name: string,
	schedule: 'daily' | 'manual',
	locationId: string
): Promise<string> {
	const res = await page.request.post('/api/compare/presets', {
		data: {
			name,
			location_ids: [locationId],
			schedule,
			profil: 'wandern',
			hour_from: 7,
			hour_to: 16,
			empfaenger: ['urlauber@example.com']
		}
	});
	expect(res.ok(), 'Preset-Anlage fehlgeschlagen: ' + res.status()).toBeTruthy();
	const body = await res.json();
	createdIds.push(body.id);
	return body.id as string;
}

async function createDraftPreset(page: Page, name: string): Promise<string> {
	const res = await page.request.post('/api/compare/presets', {
		data: {
			name,
			location_ids: [],
			schedule: 'daily',
			profil: 'wandern',
			hour_from: 7,
			hour_to: 16,
			empfaenger: []
		}
	});
	expect(res.ok(), 'Draft-Preset-Anlage fehlgeschlagen: ' + res.status()).toBeTruthy();
	const body = await res.json();
	createdIds.push(body.id);
	return body.id as string;
}

test.describe('Issue #1261 (a): Compare-Detail "Bearbeiten" auffindbar (Desktop)', () => {
	test.beforeEach(async ({ page }) => {
		await page.setViewportSize({ width: 1280, height: 900 });
	});

	// AC-1 (Desktop-Header-"Bearbeiten"-Button) und AC-2 (Kebab-Menüpunkt
	// "Bearbeiten") entfernt — Epic #1273 S3 hat beide Einstiegspunkte bewusst
	// aus dem Hub entfernt ("der Hub IST die Bearbeiten-Fläche"), bestätigt
	// durch frontend/src/lib/components/compare/__tests__/
	// issue_1273_s3_redirect_links.test.ts AC-4. Keine URL-Korrektur möglich,
	// da die getesteten UI-Elemente selbst nicht mehr existieren.
	// Spec: docs/specs/modules/epic_1273_s4a_test_migration.md § AC-4

	// ── AC-3: Mobile-Sheet bleibt ohne "Bearbeiten" (Regression #1256 S8 AC-23) ──
	test('AC-3: Mobile Bottom-Sheet enthält weiterhin KEIN "Bearbeiten" (aktiv)', async ({ page }) => {
		await page.setViewportSize({ width: 375, height: 667 });
		const suffix = Date.now();
		const locId = await createLocation(page, `E2E 1261 AC3 Ort ${suffix}`, 47.07, 11.33);
		const id = await createPresetWithLocation(page, `E2E 1261 AC3 ${suffix}`, 'daily', locId);

		await page.goto(`/compare/${id}`);
		await page.waitForLoadState('networkidle');

		const moreBtn = page.locator('button[aria-label="Weitere Aktionen"]:visible').first();
		await expect(moreBtn).toBeVisible({ timeout: 10_000 });
		await moreBtn.click();

		await expect(page.getByRole('button', { name: 'Pausieren' })).toBeVisible({ timeout: 5_000 });
		// Exaktes Match: Substring-Match traf sonst faelschlich die S2-Inline-Stifte
		// "Name bearbeiten"/"Region bearbeiten" im Hub-Header (2 statt 0 Treffer).
		await expect(page.getByRole('button', { name: 'Bearbeiten', exact: true })).toHaveCount(0);
	});

	// ── AC-4: Draft — kein zusätzlicher Bearbeiten-Einstieg ──────────────────
	test('AC-4: Draft zeigt "Setup abschließen", KEIN zusätzlichen Bearbeiten-Einstieg', async ({ page }) => {
		const suffix = Date.now();
		const id = await createDraftPreset(page, `E2E 1261 AC4 Draft ${suffix}`);

		await page.goto(`/compare/${id}`);
		await page.waitForLoadState('networkidle');

		await expect(page.getByRole('button', { name: 'Setup abschließen' })).toBeVisible({ timeout: 10_000 });
		await expect(page.locator('[data-testid="compare-detail-edit-button"]')).toHaveCount(0);

		const kebabTrigger = page.locator('button[aria-label="Weitere Aktionen"]:visible').first();
		await expect(kebabTrigger).toBeVisible({ timeout: 10_000 });
		await kebabTrigger.click();
		await expect(page.getByRole('menuitem', { name: 'Bearbeiten' })).toHaveCount(0);
	});
});

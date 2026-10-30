// gz-eigenstaendig: nur der Orte-Tab (Drag, Hinzufuegen-Panel, Entfernen) ist uebrig -- erlaubte Compare-Eigenheit; der Wertebereich-Teil lebt kind-parametrisiert in hub-wertebereiche-wertprops WW-3a/b/c, Etappen-Pendant: hub-save-chip SC-2 und etappen-strip-sortieren.spec.ts
// E2E (Staging) — Issue #1256 Scheibe 6: Hub-Orte-Tab Drag/Entfernen/
// Add-Panel + eingebetteter CorridorEditor im Hub-Idealwerte-Tab
// (AC-14, AC-15, AC-31, AC-32, AC-33, AC-34).
//
// Spec: docs/specs/modules/issue_1256_compare_ui_rewire.md § Scheibe 6
// Context: docs/context/feat-1256-s6-hub-idealwerte-inline.md
//
// Ausführen (gegen Staging, aus frontend/):
//   set -a; source /home/hem/gregor_zwanzig/.claude/validator.env; set +a
//   npx playwright test --config=playwright.1256-s6.staging.config.ts

import { test, expect, type Page } from '@playwright/test';
// `dragDndZoneItem` ist seit #1771 S1 geteilt (war hier lokal kopiert) und
// wartet auf das echte `finalize`-Ereignis statt auf eine feste Frist.
import { createTestLocation, dragDndZoneItem } from './helpers';

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
	// #1329 Maßnahme B: zentralisiert über den geteilten Helfer (helpers.ts).
	const loc = await createTestLocation(page.request, { name, lat, lon });
	createdLocationIds.push(loc.id);
	return loc.id;
}

async function createPresetWithLocations(
	page: Page,
	name: string,
	locationIds: string[],
	extra: Record<string, unknown> = {}
): Promise<string> {
	const res = await page.request.post('/api/compare/presets', {
		data: {
			name,
			location_ids: locationIds,
			schedule: 'daily',
			profil: 'wintersport',
			hour_from: 7,
			hour_to: 16,
			empfaenger: ['urlauber@example.com'],
			...extra
		}
	});
	expect(res.ok(), 'Preset-Anlage fehlgeschlagen: ' + res.status()).toBeTruthy();
	const body = await res.json();
	const id = body.id as string;
	createdIds.push(id);
	return id;
}

test.describe('Issue #1256 Scheibe 6: Hub-Orte-Tab (AC-14/15/31/32)', () => {
	test.beforeEach(async ({ page }) => {
		await page.setViewportSize({ width: 1280, height: 900 });
	});

	// ── AC-14/AC-15: Drag ändert Reihenfolge sofort + PUT + Reload-Persistenz ──
	test('AC-14/AC-15: Ort per Drag umsortieren löst PUT mit neuer location_ids-Reihenfolge aus, überlebt Reload', async ({
		page
	}) => {
		const suffix = Date.now();
		const locA = await createLocation(page, `E2E S6 Ort-A ${suffix}`, 47.26, 11.4);
		const locB = await createLocation(page, `E2E S6 Ort-B ${suffix}`, 47.1, 11.29);
		const locC = await createLocation(page, `E2E S6 Ort-C ${suffix}`, 47.05, 11.32);
		const name = `E2E S6 Reorder ${suffix}`;
		const id = await createPresetWithLocations(page, name, [locA, locB, locC]);

		await page.goto(`/compare/${id}?tab=orte`);
		await page.waitForLoadState('networkidle');
		await page.locator('[data-testid="compare-detail-tab-orte"]:visible').click();

		const rows = page.locator('[data-testid="hub-orte-row"]');
		await expect(rows).toHaveCount(3, { timeout: 10_000 });
		await expect(rows.nth(0)).toHaveAttribute('data-loc-id', locA);

		const source = page.locator(`[data-testid="hub-orte-row"][data-loc-id="${locC}"]`);
		const target = page.locator(`[data-testid="hub-orte-row"][data-loc-id="${locA}"]`);

		const putPromise = page.waitForResponse(
			(res) => res.url().includes(`/api/compare/presets/${id}`) && res.request().method() === 'PUT'
		);
		await dragDndZoneItem(page, source, target);
		const putRes = await putPromise;
		expect(putRes.ok(), 'PUT nach Drag fehlgeschlagen: ' + putRes.status()).toBeTruthy();
		const putBody = putRes.request().postDataJSON() as { location_ids: string[] };
		expect(putBody.location_ids[0]).toBe(locC);

		await expect(rows.nth(0)).toHaveAttribute('data-loc-id', locC, { timeout: 5_000 });

		// AC-15: Reload zeigt die zuletzt gespeicherte Reihenfolge.
		await page.reload();
		await page.waitForLoadState('networkidle');
		const reloadedRows = page.locator('[data-testid="hub-orte-row"]');
		await expect(reloadedRows.nth(0)).toHaveAttribute('data-loc-id', locC, { timeout: 5_000 });
	});

	// ── AC-31: "Ort hinzufügen" öffnet inline im Hub, kein Redirect ──────────
	test('AC-31: "Ort hinzufügen" öffnet ein Inline-Panel im Hub, URL bleibt /compare/{id}?tab=orte', async ({
		page
	}) => {
		const suffix = Date.now();
		const locA = await createLocation(page, `E2E S6 Add-Ort-A ${suffix}`, 47.4, 10.9);
		const locB = await createLocation(page, `E2E S6 Add-Ort-B ${suffix}`, 47.35, 10.85);
		const name = `E2E S6 AddPanel ${suffix}`;
		const id = await createPresetWithLocations(page, name, [locA]);

		await page.goto(`/compare/${id}?tab=orte`);
		await page.waitForLoadState('networkidle');
		await page.locator('[data-testid="compare-detail-tab-orte"]:visible').click();

		const addBtn = page.locator('[data-testid="hub-orte-add"]:visible');
		await expect(addBtn).toBeVisible({ timeout: 10_000 });
		await addBtn.click();

		const panel = page.locator('[data-testid="hub-orte-panel"]:visible');
		await expect(panel).toBeVisible({ timeout: 10_000 });
		await expect(page).toHaveURL(new RegExp(`/compare/${id}\\?tab=orte$`));

		await expect(panel).toContainText(`E2E S6 Add-Ort-B ${suffix}`, { timeout: 10_000 });
	});

	// ── AC-32: Entfernen persistiert per PUT, Zeile verschwindet, Tab bleibt ──
	test('AC-32: Entfernen-Klick löscht die Zeile und persistiert per PUT ohne Tab-Verlassen', async ({ page }) => {
		const suffix = Date.now();
		const locA = await createLocation(page, `E2E S6 Remove-Ort-A ${suffix}`, 47.2, 11.1);
		const locB = await createLocation(page, `E2E S6 Remove-Ort-B ${suffix}`, 47.15, 11.05);
		const name = `E2E S6 Remove ${suffix}`;
		const id = await createPresetWithLocations(page, name, [locA, locB]);

		await page.goto(`/compare/${id}?tab=orte`);
		await page.waitForLoadState('networkidle');
		await page.locator('[data-testid="compare-detail-tab-orte"]:visible').click();

		const rows = page.locator('[data-testid="hub-orte-row"]');
		await expect(rows).toHaveCount(2, { timeout: 10_000 });

		const removeBtn = page.locator(
			`[data-testid="hub-orte-row"][data-loc-id="${locB}"] [data-testid="hub-orte-remove"]`
		);
		const putPromise = page.waitForResponse(
			(res) => res.url().includes(`/api/compare/presets/${id}`) && res.request().method() === 'PUT'
		);
		await removeBtn.click();
		const putRes = await putPromise;
		expect(putRes.ok(), 'PUT nach Entfernen fehlgeschlagen: ' + putRes.status()).toBeTruthy();
		const putBody = putRes.request().postDataJSON() as { location_ids: string[] };
		expect(putBody.location_ids).toEqual([locA]);

		await expect(rows).toHaveCount(1, { timeout: 5_000 });
		await expect(page.locator('[data-testid="compare-detail-panel-orte"]:visible')).toBeVisible();
	});
});

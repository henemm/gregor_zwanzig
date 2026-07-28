// E2E (Staging) — D3 von Epic #1301 (Alarm-Tab Struktur/Beschriftung),
// Commit e203a2d5.
//
// Spec: docs/specs/modules/epic_1301_d3_alarm_tab_struktur.md
//
// Ausfuehren (gegen Staging, aus frontend/):
//   set -a; source /home/hem/gregor_zwanzig/.claude/validator.env; set +a
//   export GZ_AUTH_USER=... GZ_AUTH_PASS=...
//   npx playwright test --config=playwright.1301-d3.staging.config.ts

import { test, expect, type Page } from '@playwright/test';

let createdTripIds: string[] = [];
let createdPresetIds: string[] = [];
let createdLocationIds: string[] = [];

test.afterEach(async ({ page }) => {
	for (const id of createdTripIds) {
		try {
			await page.request.delete(`/api/trips/${id}`);
		} catch {
			/* Staging-Hygiene: Cleanup-Fehler ist nicht test-kritisch */
		}
	}
	createdTripIds = [];
	for (const id of createdPresetIds) {
		try {
			await page.request.delete(`/api/compare/presets/${id}`);
		} catch {
			/* Staging-Hygiene: Cleanup-Fehler ist nicht test-kritisch */
		}
	}
	createdPresetIds = [];
	for (const id of createdLocationIds) {
		try {
			await page.request.delete(`/api/locations/${id}`);
		} catch {
			/* Staging-Hygiene: Cleanup-Fehler ist nicht test-kritisch */
		}
	}
	createdLocationIds = [];
});

async function createTrip(page: Page, id: string): Promise<void> {
	await page.request.delete(`/api/trips/${id}`).catch(() => {});
	const res = await page.request.post('/api/trips', {
		data: {
			id,
			name: `D3 Val ${id}`,
			region: 'Test',
			stages: [
				{
					id: `${id}-stage-1`,
					name: 'Etappe 1',
					date: new Date(Date.now() + 86400000).toISOString().slice(0, 10),
					waypoints: [{ id: `${id}-wp-1`, name: 'Start', lat: 47.2692, lon: 11.4041, elevation_m: 574 }]
				}
			],
			official_alerts_enabled: true
		}
	});
	expect(res.ok(), 'Trip-Anlage fehlgeschlagen: ' + res.status()).toBeTruthy();
	createdTripIds.push(id);
}

async function createLocation(page: Page, name: string, lat: number, lon: number): Promise<string> {
	const res = await page.request.post('/api/locations', { data: { name, lat, lon } });
	expect(res.ok(), 'Location-Anlage fehlgeschlagen: ' + res.status()).toBeTruthy();
	const body = await res.json();
	const id = body.id as string;
	createdLocationIds.push(id);
	return id;
}

async function createCompare(page: Page, name: string, locationIds: string[]): Promise<string> {
	const res = await page.request.post('/api/compare/presets', {
		data: {
			name,
			location_ids: locationIds,
			schedule: 'daily',
			profil: 'wandern',
			hour_from: 8,
			hour_to: 17,
			forecast_hours: 48,
			empfaenger: ['urlauber@example.com'],
			official_alerts_enabled: true,
			official_warnings: { enabled: true }
		}
	});
	expect(res.ok(), 'Vergleich-Anlage fehlgeschlagen: ' + res.status()).toBeTruthy();
	const body = await res.json();
	const id = body.id as string;
	createdPresetIds.push(id);
	return id;
}

async function getPreset(page: Page, id: string): Promise<Record<string, unknown>> {
	const res = await page.request.get(`/api/compare/presets/${id}`);
	expect(res.ok(), 'Preset-Lesen fehlgeschlagen: ' + res.status()).toBeTruthy();
	return res.json();
}

test.describe('D3 von #1301: Alarm-Tab Struktur/Beschriftung', () => {
	test.beforeEach(async ({ page }) => {
		await page.setViewportSize({ width: 1280, height: 900 });
	});

	// ── AC-1 + AC-2 (Vergleich): Ueberschrift + Reihenfolge official-warnings -> radar -> metric-levels ──
	test('AC-1/AC-2 (Vergleich): Ueberschrift "Amtliche & Radar-Warnungen", Radar direkt nach Amtliche-Schalter', async ({
		page
	}) => {
		const locA = await createLocation(page, 'D3 Ort A', 47.42, 10.98);
		const locB = await createLocation(page, 'D3 Ort B', 47.5, 11.1);
		const locC = await createLocation(page, 'D3 Ort C', 47.6, 11.2);
		const id = await createCompare(page, `D3 AC1-2 ${Date.now()}`, [locA, locB, locC]);

		await page.goto(`/compare/${id}?tab=alarme`);
		await page.waitForURL(/\/compare\/[^/]+/);

		const tab = page.locator('[data-testid="alarme-tab"]:visible');
		await expect(tab).toBeVisible({ timeout: 15000 });

		// AC-2: Ueberschrift + Abwesenheit alter Text.
		await expect(tab.locator('text="Amtliche & Radar-Warnungen"')).toBeVisible();
		await expect(page.locator('text="Wann Warnungen rausgehen"')).toHaveCount(0);

		// AC-1: DOM-Reihenfolge der alarme-section-* Container.
		const sectionIds = await tab
			.locator('[data-testid^="alarme-section-"]:visible')
			.evaluateAll((els) => els.map((el) => el.getAttribute('data-testid')));
		const officialIdx = sectionIds.indexOf('alarme-section-official-warnings');
		const radarIdx = sectionIds.indexOf('alarme-section-radar');
		const metricIdx = sectionIds.indexOf('alarme-section-metric-levels');
		expect(officialIdx, 'official-warnings section fehlt: ' + JSON.stringify(sectionIds)).toBeGreaterThanOrEqual(0);
		expect(radarIdx, 'radar section fehlt: ' + JSON.stringify(sectionIds)).toBeGreaterThanOrEqual(0);
		expect(metricIdx, 'metric-levels section fehlt: ' + JSON.stringify(sectionIds)).toBeGreaterThanOrEqual(0);
		expect(radarIdx, 'radar nicht direkt nach official-warnings: ' + JSON.stringify(sectionIds)).toBe(
			officialIdx + 1
		);
		expect(metricIdx, 'metric-levels nicht nach radar: ' + JSON.stringify(sectionIds)).toBeGreaterThan(radarIdx);

		// Widget-Reihenfolge im DOM zusaetzlich visuell/positional pruefen.
		const officialToggle = page.locator('[data-testid="alerts-tab-official-alert-triggers-toggle"]:visible');
		const radarToggle = page.locator('[data-testid="alarme-radar-toggle"]:visible');
		await expect(officialToggle).toBeVisible();
		await expect(radarToggle).toBeVisible();
		const officialBox = await officialToggle.boundingBox();
		const radarBox = await radarToggle.boundingBox();
		expect(officialBox && radarBox && radarBox.y > officialBox.y, 'Radar-Schalter steht nicht unterhalb des Amtliche-Schalters').toBeTruthy();

		await page.screenshot({
			path: '/home/hem/gregor_zwanzig/docs/artifacts/d3-alarm-tab-struktur/ac-1-ac-2-vergleich-PASS.png',
			fullPage: true
		});
	});

	// ── AC-2/AC-5 (Trip): Ueberschrift "Amtliche Warnungen", kein Radar-Schalter ──
	test('AC-2/AC-5 (Trip): Ueberschrift "Amtliche Warnungen", kein Radar-Schalter, Reihenfolge unveraendert', async ({
		page
	}) => {
		const id = `d3-ac2-trip-${Date.now()}`;
		await createTrip(page, id);

		await page.goto(`/trips/${id}?tab=alarme`);
		await page.waitForURL(/\/trips\/[^/]+/);

		const tab = page.locator('[data-testid="alarme-tab"]:visible');
		await expect(tab).toBeVisible({ timeout: 15000 });

		await expect(tab.locator('text="Amtliche Warnungen"')).toBeVisible();
		await expect(tab.locator('text="Amtliche & Radar-Warnungen"')).toHaveCount(0);
		await expect(page.locator('text="Wann Warnungen rausgehen"')).toHaveCount(0);

		await expect(page.locator('[data-testid="alarme-radar-toggle"]:visible')).toHaveCount(0);
		await expect(page.locator('[data-testid="alarme-section-radar"]:visible')).toHaveCount(0);

		// AC-5: uebrige Block-Reihenfolge unveraendert.
		const sectionIds = await tab
			.locator('[data-testid^="alarme-section-"]:visible')
			.evaluateAll((els) => els.map((el) => el.getAttribute('data-testid')));
		expect(sectionIds).toEqual([
			'alarme-section-korridor-summary',
			'alarme-section-official-warnings',
			'alarme-section-metric-levels',
			'alarme-section-channels',
			'alarme-section-cooldown',
			'alarme-section-quiet-hours',
			'alarme-section-sample'
		]);

		await page.screenshot({
			path: '/home/hem/gregor_zwanzig/docs/artifacts/d3-alarm-tab-struktur/ac-2-ac-5-trip-PASS.png',
			fullPage: true
		});
	});

	// ── AC-3: Funktion unveraendert — Amtliche-Warnungen-Schalter im Vergleich toggeln + persistieren ──
	test('AC-3: Amtliche-Warnungen-Schalter im Vergleich toggelt weiterhin official_warnings.enabled + persistiert', async ({
		page
	}) => {
		const locA = await createLocation(page, 'D3 AC3 Ort A', 46.9, 9.9);
		const locB = await createLocation(page, 'D3 AC3 Ort B', 47.0, 10.0);
		const locC = await createLocation(page, 'D3 AC3 Ort C', 47.1, 10.1);
		const id = await createCompare(page, `D3 AC3 ${Date.now()}`, [locA, locB, locC]);

		const before = await getPreset(page, id);
		const beforeEnabled = (before.official_warnings as { enabled?: boolean } | undefined)?.enabled;
		expect(beforeEnabled, 'Ausgangszustand vor Toggle').toBe(true);

		await page.goto(`/compare/${id}?tab=alarme`);
		await page.waitForURL(/\/compare\/[^/]+/);
		const toggle = page.locator('[data-testid="alerts-tab-official-alert-triggers-toggle"]:visible');
		await expect(toggle).toBeVisible({ timeout: 15000 });
		const checkbox = toggle.locator('input[type="checkbox"]');
		await expect(checkbox).toBeChecked();

		const putPromise = page.waitForResponse(
			(r) => r.url().includes(`/api/compare/presets/${id}`) && r.request().method() === 'PUT'
		);
		await checkbox.click();
		const putRes = await putPromise;
		expect(putRes.ok(), 'PUT nach Toggle fehlgeschlagen: ' + putRes.status()).toBeTruthy();

		const afterOff = await getPreset(page, id);
		expect(
			(afterOff.official_warnings as { enabled?: boolean } | undefined)?.enabled,
			'GET nach PUT (aus)'
		).toBe(false);

		await page.reload();
		await page.waitForURL(/\/compare\/[^/]+/);
		await page.goto(`/compare/${id}?tab=alarme`);
		const toggle2 = page.locator('[data-testid="alerts-tab-official-alert-triggers-toggle"]:visible');
		await expect(toggle2).toBeVisible({ timeout: 15000 });
		await expect(toggle2.locator('input[type="checkbox"]')).not.toBeChecked();
		await page.screenshot({
			path: '/home/hem/gregor_zwanzig/docs/artifacts/d3-alarm-tab-struktur/ac-3-persisted-off-PASS.png'
		});

		// Ausgangszustand wiederherstellen (an).
		const putBackPromise = page.waitForResponse(
			(r) => r.url().includes(`/api/compare/presets/${id}`) && r.request().method() === 'PUT'
		);
		await toggle2.locator('input[type="checkbox"]').click();
		const putBackRes = await putBackPromise;
		expect(putBackRes.ok(), 'Rueck-PUT fehlgeschlagen: ' + putBackRes.status()).toBeTruthy();
		const afterOn = await getPreset(page, id);
		expect(
			(afterOn.official_warnings as { enabled?: boolean } | undefined)?.enabled,
			'GET nach Rueck-PUT (an)'
		).toBe(true);
	});
});

// E2E (Staging) — Epic #1301 Scheibe C2 (Stundenverlauf-Steuerung im
// Hub-Layout-Tab), Re-Verifikation nach AC-5-Fix (Issue #1299, Commit
// 8fdb514b, Staging-Fund F005).
//
// Spec: docs/specs/modules/compare_hub_hourly_metrics.md
//
// Ausfuehren (gegen Staging, aus frontend/):
//   set -a; source /home/hem/gregor_zwanzig/.claude/validator.env; set +a
//   export GZ_AUTH_USER=... GZ_AUTH_PASS=...
//   npx playwright test --config=playwright.1301-c2.staging.config.ts

import { test, expect, type Page } from '@playwright/test';
import { ALL_HOURLY_METRICS } from '../src/lib/components/compare/compareHourlyMetricDefs.ts';

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
	const id = body.id as string;
	createdLocationIds.push(id);
	return id;
}

// AC-3-Kontrollwerte — bewusst NICHT die Defaults, damit ein stiller
// Verlust/eine stille Rundung sichtbar würde.
const AC3_GUARD_FIELDS = {
	top_n: 2,
	channel_layouts: { email: ['a', 'b'], telegram: ['a'] },
	forecast_hours: 72,
	hour_from: 8,
	hour_to: 17
};

async function createPresetWithLocations(page: Page, name: string, locationIds: string[]): Promise<string> {
	const res = await page.request.post('/api/compare/presets', {
		data: {
			name,
			location_ids: locationIds,
			schedule: 'daily',
			profil: 'wandern',
			hour_from: AC3_GUARD_FIELDS.hour_from,
			hour_to: AC3_GUARD_FIELDS.hour_to,
			forecast_hours: AC3_GUARD_FIELDS.forecast_hours,
			empfaenger: ['urlauber@example.com'],
			display_config: {
				top_n: AC3_GUARD_FIELDS.top_n,
				channel_layouts: AC3_GUARD_FIELDS.channel_layouts
			}
		}
	});
	expect(res.ok(), 'Preset-Anlage fehlgeschlagen: ' + res.status()).toBeTruthy();
	const body = await res.json();
	const id = body.id as string;
	createdIds.push(id);
	return id;
}

async function getPreset(page: Page, id: string): Promise<Record<string, unknown>> {
	const res = await page.request.get(`/api/compare/presets/${id}`);
	expect(res.ok(), 'Preset-Lesen fehlgeschlagen: ' + res.status()).toBeTruthy();
	return res.json();
}

function assertAc3Guard(preset: Record<string, unknown>, label: string): void {
	expect(preset.hour_from, `${label}: hour_from`).toBe(AC3_GUARD_FIELDS.hour_from);
	expect(preset.hour_to, `${label}: hour_to`).toBe(AC3_GUARD_FIELDS.hour_to);
	expect(preset.forecast_hours, `${label}: forecast_hours`).toBe(AC3_GUARD_FIELDS.forecast_hours);
	const dc = preset.display_config as Record<string, unknown>;
	expect(dc.top_n, `${label}: top_n`).toBe(AC3_GUARD_FIELDS.top_n);
	expect(dc.channel_layouts, `${label}: channel_layouts`).toEqual(AC3_GUARD_FIELDS.channel_layouts);
}

test.describe('Epic #1301 Scheibe C2: Hub-Layout-Tab Stundenverlauf (AC-1..AC-5)', () => {
	test.beforeEach(async ({ page }) => {
		await page.setViewportSize({ width: 1280, height: 900 });
	});

	// ── AC-1/AC-4 Kurz-Regression ───────────────────────────────────────────
	test('AC-1/AC-4: Layout-Tab zeigt 9 Stundenverlauf-Checkboxen + Schalter, keine Top-N-/Bucket-Attrappe', async ({
		page
	}) => {
		const suffix = Date.now();
		const locA = await createLocation(page, `E2E-C2 Regr-A ${suffix}`, 47.1, 11.2);
		const locB = await createLocation(page, `E2E-C2 Regr-B ${suffix}`, 47.2, 11.3);
		const locC = await createLocation(page, `E2E-C2 Regr-C ${suffix}`, 47.3, 11.4);
		const id = await createPresetWithLocations(page, `E2E-C2 Regr ${suffix}`, [locA, locB, locC]);

		await page.goto(`/compare/${id}?tab=layout`);
		await page.waitForLoadState('networkidle');
		await page.locator('[data-testid="compare-detail-tab-layout"]:visible').click();

		const panel = page.locator('[data-testid="compare-detail-panel-layout"]:visible');
		await expect(panel).toBeVisible({ timeout: 10_000 });

		await expect(page.locator('[data-testid="compare-layout-hourly-enabled-toggle"]:visible')).toBeVisible({
			timeout: 10_000
		});
		for (const metric of ALL_HOURLY_METRICS) {
			await expect(
				page.locator(`[data-testid="compare-layout-hourly-metric-${metric.key}"]:visible`)
			).toBeVisible();
		}
		expect(ALL_HOURLY_METRICS.length).toBe(9);

		// AC-4: keine Top-N-/Bucket-Attrappe im erreichbaren Hub.
		await expect(page.locator('[data-testid*="topn"]:visible')).toHaveCount(0);
		await expect(page.locator('[data-testid*="bucket"]:visible')).toHaveCount(0);
		await expect(page.locator('[data-testid*="channel-layout-edit"]:visible')).toHaveCount(0);
	});

	// ── AC-2: genau ein PUT pro Interaktion + No-Op-Guard ───────────────────
	test('AC-2: ein Toggle-Klick = genau ein PUT; Klick ohne Zustandsaenderung = kein PUT', async ({ page }) => {
		const suffix = Date.now();
		const locA = await createLocation(page, `E2E-C2 AC2-A ${suffix}`, 46.9, 10.7);
		const locB = await createLocation(page, `E2E-C2 AC2-B ${suffix}`, 47.0, 10.8);
		const locC = await createLocation(page, `E2E-C2 AC2-C ${suffix}`, 47.05, 10.85);
		const id = await createPresetWithLocations(page, `E2E-C2 AC2 ${suffix}`, [locA, locB, locC]);

		await page.goto(`/compare/${id}?tab=layout`);
		await page.waitForLoadState('networkidle');
		await page.locator('[data-testid="compare-detail-tab-layout"]:visible').click();
		await expect(page.locator('[data-testid="compare-layout-hourly-enabled-toggle"]:visible')).toBeVisible({
			timeout: 10_000
		});

		let putCount = 0;
		page.on('response', (res) => {
			if (res.url().includes(`/api/compare/presets/${id}`) && res.request().method() === 'PUT') putCount++;
		});

		const firstMetricKey = ALL_HOURLY_METRICS[0].key;
		const firstCheckbox = page
			.locator(`[data-testid="compare-layout-hourly-metric-${firstMetricKey}"]:visible`)
			.locator('input[type="checkbox"]');

		const putPromise = page.waitForResponse(
			(res) => res.url().includes(`/api/compare/presets/${id}`) && res.request().method() === 'PUT'
		);
		await firstCheckbox.click();
		const putRes = await putPromise;
		expect(putRes.ok(), 'PUT nach Metrik-Abwahl fehlgeschlagen: ' + putRes.status()).toBeTruthy();

		await page.waitForTimeout(500); // Nachlauf: sicherstellen, dass kein zweiter PUT nachtrudelt
		expect(putCount, 'genau ein PUT pro abgeschlossener Interaktion').toBe(1);

		// No-Op: Klick auf ein nicht-interaktives Element INNERHALB des Wraps
		// (SectionH-Titel "Stundenverlauf") — bubble-Click loest
		// handleLayoutCommit aus, aber kein Checkbox-Zustand aendert sich ->
		// flushPendingLayoutSave muss null liefern -> kein PUT.
		putCount = 0;
		await page.locator('[data-slot="section-h"]:has-text("Stundenverlauf"):visible').first().click();
		await page.waitForTimeout(1500);
		expect(putCount, 'No-Op-Klick darf keinen PUT ausloesen').toBe(0);
	});

	// ── AC-5 (KRITISCH, der Fix): Leerauswahl -> [] statt Key-Loeschung ─────
	test('AC-5: alle 9 Metriken abwaehlen persistiert display_config.hourly_metrics als [] (nicht geloescht), Reload zeigt wieder alle an', async ({
		page
	}) => {
		const suffix = Date.now();
		const locA = await createLocation(page, `E2E-C2 AC5-A ${suffix}`, 47.3, 11.0);
		const locB = await createLocation(page, `E2E-C2 AC5-B ${suffix}`, 47.4, 11.1);
		const locC = await createLocation(page, `E2E-C2 AC5-C ${suffix}`, 47.45, 11.15);
		const id = await createPresetWithLocations(page, `E2E-C2 AC5 ${suffix}`, [locA, locB, locC]);

		const presetBeforeSequence = await getPreset(page, id);
		assertAc3Guard(presetBeforeSequence, 'vor der AC-5-Sequenz');

		await page.goto(`/compare/${id}?tab=layout`);
		await page.waitForLoadState('networkidle');
		await page.locator('[data-testid="compare-detail-tab-layout"]:visible').click();
		await expect(page.locator('[data-testid="compare-layout-hourly-enabled-toggle"]:visible')).toBeVisible({
			timeout: 10_000
		});

		// Vor der Sequenz: alle 9 Checkboxen angehakt (Default "alle sichtbar",
		// da display_config.hourly_metrics beim Anlegen nicht gesetzt wurde).
		for (const metric of ALL_HOURLY_METRICS) {
			const cb = page
				.locator(`[data-testid="compare-layout-hourly-metric-${metric.key}"]:visible`)
				.locator('input[type="checkbox"]');
			await expect(cb).toBeChecked();
		}

		let lastPutBody: { display_config?: { hourly_metrics?: unknown } } | null = null;
		for (const metric of ALL_HOURLY_METRICS) {
			const checkbox = page
				.locator(`[data-testid="compare-layout-hourly-metric-${metric.key}"]:visible`)
				.locator('input[type="checkbox"]');
			const putPromise = page.waitForResponse(
				(res) => res.url().includes(`/api/compare/presets/${id}`) && res.request().method() === 'PUT'
			);
			await checkbox.click();
			const putRes = await putPromise;
			expect(putRes.ok(), `PUT nach Abwahl von ${metric.key} fehlgeschlagen: ` + putRes.status()).toBeTruthy();
			lastPutBody = putRes.request().postDataJSON();
		}

		// KRITISCH (AC-5-Fix): der LETZTE PUT-Body traegt den Schluessel
		// hourly_metrics EXPLIZIT als [] — nicht weggelassen (das war der
		// Staging-Fund F005: der Merge-only-Server ignoriert einen fehlenden
		// Key, der alte Wert blieb wirkungslos bestehen).
		expect(lastPutBody, 'letzter PUT-Body vorhanden').not.toBeNull();
		const finalDisplayConfig = lastPutBody!.display_config;
		expect(finalDisplayConfig, 'display_config im letzten PUT-Body vorhanden').toBeDefined();
		expect(
			Object.prototype.hasOwnProperty.call(finalDisplayConfig, 'hourly_metrics'),
			'hourly_metrics-Key MUSS im letzten PUT-Body vorhanden sein (nicht geloescht)'
		).toBe(true);
		expect(finalDisplayConfig!.hourly_metrics).toEqual([]);

		// GET danach: Server persistiert [] (nicht den alten Wert).
		const presetAfterUncheck = await getPreset(page, id);
		const dcAfter = presetAfterUncheck.display_config as Record<string, unknown>;
		expect(dcAfter.hourly_metrics, 'GET nach Leerauswahl: hourly_metrics ist []').toEqual([]);
		assertAc3Guard(presetAfterUncheck, 'nach der AC-5-Sequenz (vor Reload)');

		// Reload: Default-Semantik "alle sichtbar" — alle 9 Checkboxen wieder
		// angehakt (hydrateLayoutFieldsFromPreset behandelt [] wie hourly
		// enabled=alle, isHourlyMetricActive: length===0 -> true).
		await page.reload();
		await page.waitForLoadState('networkidle');
		await page.locator('[data-testid="compare-detail-tab-layout"]:visible').click();
		await expect(page.locator('[data-testid="compare-layout-hourly-enabled-toggle"]:visible')).toBeVisible({
			timeout: 10_000
		});
		for (const metric of ALL_HOURLY_METRICS) {
			const cb = page
				.locator(`[data-testid="compare-layout-hourly-metric-${metric.key}"]:visible`)
				.locator('input[type="checkbox"]');
			await expect(cb, `nach Reload: ${metric.key} wieder angehakt`).toBeChecked({ timeout: 10_000 });
		}
		await page.screenshot({
			path: '../docs/artifacts/feat-1301-c2-hub-zugang/ac-5-reload-all-checked-PASS.png',
			fullPage: true
		});

		// AC-3 erneut nach dem vollen Reload — derselbe Payload-Builder wurde
		// vom Fix angefasst.
		const presetAfterReload = await getPreset(page, id);
		assertAc3Guard(presetAfterReload, 'nach Reload (Abschluss)');
	});
});

test.describe('Epic #1301 Scheibe C2: Runde 2 — Adversary-Kantenfaelle', () => {
	test.beforeEach(async ({ page }) => {
		await page.setViewportSize({ width: 1280, height: 900 });
	});

	// ── Kantenfall A: Teil-Auswahl (nicht alle 9) uebersteht Reload byteidentisch ──
	test('R2-A: Teilweise Abwahl (3 von 9) persistiert exakte Teilliste, Reload zeigt exakt dieselben 6 an', async ({
		page
	}) => {
		const suffix = Date.now();
		const locA = await createLocation(page, `E2E-C2 R2A-A ${suffix}`, 47.5, 10.3);
		const locB = await createLocation(page, `E2E-C2 R2A-B ${suffix}`, 47.55, 10.35);
		const locC = await createLocation(page, `E2E-C2 R2A-C ${suffix}`, 47.6, 10.4);
		const id = await createPresetWithLocations(page, `E2E-C2 R2A ${suffix}`, [locA, locB, locC]);

		await page.goto(`/compare/${id}?tab=layout`);
		await page.waitForLoadState('networkidle');
		await page.locator('[data-testid="compare-detail-tab-layout"]:visible').click();
		await expect(page.locator('[data-testid="compare-layout-hourly-enabled-toggle"]:visible')).toBeVisible({
			timeout: 10_000
		});

		const toUncheck = ALL_HOURLY_METRICS.slice(0, 3).map((m) => m.key);
		for (const key of toUncheck) {
			const cb = page.locator(`[data-testid="compare-layout-hourly-metric-${key}"]:visible`).locator('input');
			const putPromise = page.waitForResponse(
				(res) => res.url().includes(`/api/compare/presets/${id}`) && res.request().method() === 'PUT'
			);
			await cb.click();
			const res = await putPromise;
			expect(res.ok(), `PUT nach Abwahl von ${key} fehlgeschlagen`).toBeTruthy();
		}

		const expectedRemaining = ALL_HOURLY_METRICS.map((m) => m.key)
			.filter((k) => !toUncheck.includes(k))
			.sort();

		const presetAfter = await getPreset(page, id);
		const dcAfter = presetAfter.display_config as Record<string, unknown>;
		const remainingSorted = (dcAfter.hourly_metrics as string[]).slice().sort();
		expect(remainingSorted, 'GET: genau die 6 verbleibenden Keys, kein Verlust/Zuwachs').toEqual(expectedRemaining);
		assertAc3Guard(presetAfter, 'nach Teilweiser Abwahl (R2-A)');

		await page.reload();
		await page.waitForLoadState('networkidle');
		await page.locator('[data-testid="compare-detail-tab-layout"]:visible').click();
		await expect(page.locator('[data-testid="compare-layout-hourly-enabled-toggle"]:visible')).toBeVisible({
			timeout: 10_000
		});
		for (const metric of ALL_HOURLY_METRICS) {
			const cb = page
				.locator(`[data-testid="compare-layout-hourly-metric-${metric.key}"]:visible`)
				.locator('input[type="checkbox"]');
			if (toUncheck.includes(metric.key)) {
				await expect(cb, `${metric.key} bleibt nach Reload abgewaehlt`).not.toBeChecked({ timeout: 10_000 });
			} else {
				await expect(cb, `${metric.key} bleibt nach Reload angehakt`).toBeChecked({ timeout: 10_000 });
			}
		}
	});

	// ── Kantenfall B: mehrere rapide Klicks OHNE zwischen ihnen zu warten
	// (Stresstest hubPutQueue-Serialisierung) — bewusst NICHT alle 9 auf einmal
	// (das wuerde die dokumentierte "leere Auswahl -> sofort alle wieder
	// angehakt"-Reaktivierung ausloesen, s. isHourlyMetricActive/
	// makeHourlyMetricHandler, KEIN Bug, sondern die AC-5-Default-Semantik
	// bereits VOR dem Klick-Ende). Hier: 4 von 9 rapide ohne Wartezeit
	// abwaehlen, Endzustand muss alle 4 Aktionen verlustfrei enthalten. ────
	test('R2-B: 4 rapide Abwahl-Klicks ohne Zwischenwarten — kein Update geht in der hubPutQueue verloren', async ({
		page
	}) => {
		const suffix = Date.now();
		const locA = await createLocation(page, `E2E-C2 R2B-A ${suffix}`, 46.6, 10.2);
		const locB = await createLocation(page, `E2E-C2 R2B-B ${suffix}`, 46.65, 10.25);
		const locC = await createLocation(page, `E2E-C2 R2B-C ${suffix}`, 46.7, 10.3);
		const id = await createPresetWithLocations(page, `E2E-C2 R2B ${suffix}`, [locA, locB, locC]);

		await page.goto(`/compare/${id}?tab=layout`);
		await page.waitForLoadState('networkidle');
		await page.locator('[data-testid="compare-detail-tab-layout"]:visible').click();
		await expect(page.locator('[data-testid="compare-layout-hourly-enabled-toggle"]:visible')).toBeVisible({
			timeout: 10_000
		});

		const keys = ALL_HOURLY_METRICS.map((m) => m.key);
		const toUncheck = keys.slice(0, 4);
		// Rapide, OHNE auf jede einzelne PUT-Antwort zu warten (Stresstest der
		// Queue-Serialisierung, hubPutQueue muss trotzdem alle 4 verarbeiten).
		for (const key of toUncheck) {
			await page.locator(`[data-testid="compare-layout-hourly-metric-${key}"]:visible`).locator('input').click();
		}

		await page.waitForLoadState('networkidle');
		await page.waitForTimeout(1000);

		const presetAfter = await getPreset(page, id);
		const dcAfter = presetAfter.display_config as Record<string, unknown>;
		const expectedRemaining = keys.filter((k) => !toUncheck.includes(k)).sort();
		expect(
			(dcAfter.hourly_metrics as string[]).slice().sort(),
			'alle 4 rapiden Abwahlen persistiert, kein Lost-Update in der Queue'
		).toEqual(expectedRemaining);
		assertAc3Guard(presetAfter, 'nach Stresstest R2-B');

		await page.reload();
		await page.waitForLoadState('networkidle');
		await page.locator('[data-testid="compare-detail-tab-layout"]:visible').click();
		await expect(page.locator('[data-testid="compare-layout-hourly-enabled-toggle"]:visible')).toBeVisible({
			timeout: 10_000
		});
		for (const key of keys) {
			const cb = page.locator(`[data-testid="compare-layout-hourly-metric-${key}"]:visible`).locator('input[type="checkbox"]');
			if (toUncheck.includes(key)) {
				await expect(cb, `${key} bleibt nach Reload abgewaehlt`).not.toBeChecked({ timeout: 10_000 });
			} else {
				await expect(cb, `${key} bleibt nach Reload angehakt`).toBeChecked({ timeout: 10_000 });
			}
		}
	});
});

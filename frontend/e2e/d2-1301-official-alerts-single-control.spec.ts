// E2E (Staging) — D2 von Epic #1301 (Amtliche-Warnungen: eine Bedienstelle
// je Editor), Re-Verifikation nach Fix-Loop 2 (Commit 63c1fc95).
//
// Spec: docs/specs/modules/d2_1301_official_alerts_single_control.md
// Vorheriger Staging-Lauf war BROKEN (AC-6): CompareInhaltSection ist nur
// im Anlege-Wizard erreichbar; bestehende Vergleiche hatten nach Entfernen
// des Alarm-Tab-Toggles keinen erreichbaren Schalter mehr. Fix-Loop 2:
// Toggle erscheint jetzt im Hub-Tab "Wetter-Metriken" (context='vergleich').
//
// Ausfuehren (gegen Staging, aus frontend/):
//   set -a; source /home/hem/gregor_zwanzig/.claude/validator.env; set +a
//   export GZ_AUTH_USER=... GZ_AUTH_PASS=...
//   npx playwright test --config=playwright.1301-d2.staging.config.ts

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
			name: `D2 Re-Val ${id}`,
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
			official_alerts_enabled: true
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

async function getTrip(page: Page, id: string): Promise<Record<string, unknown>> {
	const res = await page.request.get(`/api/trips/${id}`);
	expect(res.ok(), 'Trip-Lesen fehlgeschlagen: ' + res.status()).toBeTruthy();
	return res.json();
}

test.describe('D2 von #1301: Amtliche-Warnungen eine Bedienstelle je Editor (Re-Val Fix-Loop 2)', () => {
	test.beforeEach(async ({ page }) => {
		await page.setViewportSize({ width: 1280, height: 900 });
	});

	// ── AC-6 (NEU, kritisch): bestehender Vergleich, Hub-Tab Wetter-Metriken ──
	test('AC-6: bestehender Vergleich — Toggle im Hub-Tab Wetter-Metriken sichtbar, Umschalten persistiert', async ({
		page
	}) => {
		const locA = await createLocation(page, 'D2 Ort A', 47.42, 10.98);
		const locB = await createLocation(page, 'D2 Ort B', 47.5, 11.1);
		const locC = await createLocation(page, 'D2 Ort C', 47.6, 11.2);
		const id = await createCompare(page, `D2 AC6 ${Date.now()}`, [locA, locB, locC]);

		// Schritt 2/3: Hub oeffnen (nicht /compare/new), Deep-Link auf den Tab.
		await page.goto(`/compare/${id}?tab=wetter-metriken`);
		await page.waitForURL(/\/compare\/[^/]+/);

		const toggle = page.locator('[data-testid="report-show-official-alerts"]:visible');
		await expect(toggle).toHaveCount(1, { timeout: 15000 });
		await expect(toggle).toBeVisible();
		await expect(toggle.locator('text=Amtliche Warnungen im Bericht')).toBeVisible();
		await page.screenshot({ path: '/home/hem/gregor_zwanzig/docs/artifacts/d2-1301-doppelter-warnschalter/ac-6-toggle-visible-PASS.png' });

		const checkbox = toggle.locator('input[type="checkbox"]');
		await expect(checkbox).toBeChecked();

		// Schritt 5: umschalten (AUS), PUT abwarten.
		const putPromise = page.waitForResponse(
			(r) => r.url().includes(`/api/compare/presets/${id}`) && r.request().method() === 'PUT'
		);
		await checkbox.click();
		const putRes = await putPromise;
		expect(putRes.ok(), 'PUT nach Toggle fehlgeschlagen: ' + putRes.status()).toBeTruthy();

		const afterPut = await getPreset(page, id);
		expect(afterPut.official_alerts_enabled, 'GET nach PUT: official_alerts_enabled').toBe(false);

		// Seite neu laden, Tab erneut oeffnen -> Toggle zeigt gespeicherten Wert.
		await page.reload();
		await page.waitForURL(/\/compare\/[^/]+/);
		await page.goto(`/compare/${id}?tab=wetter-metriken`);
		const toggle2 = page.locator('[data-testid="report-show-official-alerts"]:visible');
		await expect(toggle2).toBeVisible({ timeout: 15000 });
		const checkbox2 = toggle2.locator('input[type="checkbox"]');
		await expect(checkbox2).not.toBeChecked();
		await page.screenshot({ path: '/home/hem/gregor_zwanzig/docs/artifacts/d2-1301-doppelter-warnschalter/ac-6-persisted-after-reload-PASS.png' });
	});

	// ── AC-1 (Regression, Vergleich): Alarme-Tab hat nur noch einen Schalter ──
	test('AC-1 (Vergleich): Alarme-Tab zeigt keinen Amtliche-Warnungen-Content-Toggle mehr', async ({ page }) => {
		const locA = await createLocation(page, 'D2 AC1 Ort A', 47.0, 10.0);
		const locB = await createLocation(page, 'D2 AC1 Ort B', 47.1, 10.1);
		const locC = await createLocation(page, 'D2 AC1 Ort C', 47.2, 10.2);
		const id = await createCompare(page, `D2 AC1 ${Date.now()}`, [locA, locB, locC]);

		await page.goto(`/compare/${id}?tab=alarme`);
		await page.waitForURL(/\/compare\/[^/]+/);

		await expect(page.locator('[data-testid="alerts-tab-official-alerts-toggle"]:visible')).toHaveCount(0);
		await expect(
			page.locator('[data-testid="alerts-tab-official-alert-triggers-toggle"]:visible')
		).toHaveCount(1, { timeout: 15000 });
		await page.screenshot({ path: '/home/hem/gregor_zwanzig/docs/artifacts/d2-1301-doppelter-warnschalter/ac-1-compare-alarme-tab-PASS.png' });
	});

	test('AC-1 (Trip): Alarme-Tab zeigt keinen Amtliche-Warnungen-Content-Toggle mehr', async ({ page }) => {
		const id = `d2-ac1-trip-${Date.now()}`;
		await createTrip(page, id);

		await page.goto(`/trips/${id}?tab=alarme`);
		await page.waitForURL(/\/trips\/[^/]+/);

		await expect(page.locator('[data-testid="alerts-tab-official-alerts-toggle"]:visible')).toHaveCount(0);
		await expect(
			page.locator('[data-testid="alerts-tab-official-alert-triggers-toggle"]:visible')
		).toHaveCount(1, { timeout: 15000 });
		await page.screenshot({ path: '/home/hem/gregor_zwanzig/docs/artifacts/d2-1301-doppelter-warnschalter/ac-1-trip-alarme-tab-PASS.png' });
	});

	// ── AC-3 (Trip): Label im Inhalt-Tab ──
	test('AC-3: Trip Inhalt-Tab Content-Toggle traegt Label "Amtliche Warnungen im Bericht"', async ({ page }) => {
		const id = `d2-ac3-trip-${Date.now()}`;
		await createTrip(page, id);

		await page.goto(`/trips/${id}?tab=weather`);
		await page.waitForURL(/\/trips\/[^/]+/);

		const toggle = page.locator('[data-testid="report-show-official-alerts"]:visible');
		await expect(toggle).toBeVisible({ timeout: 15000 });
		await expect(toggle.locator('text=Amtliche Warnungen im Bericht')).toBeVisible();
		await page.screenshot({ path: '/home/hem/gregor_zwanzig/docs/artifacts/d2-1301-doppelter-warnschalter/ac-3-trip-label-PASS.png' });
	});

	// ── AC-2 (Trip): Single-Writer — Alarme-Tab-Save enthaelt das Feld nicht ──
	test('AC-2: Trip — Alarme-Tab-Save ueberschreibt official_alerts_enabled nicht mehr', async ({ page }) => {
		const id = `d2-ac2-trip-${Date.now()}`;
		await createTrip(page, id);

		// Content-Toggle im Inhalt-Tab auf false setzen, PUT abwarten.
		await page.goto(`/trips/${id}?tab=weather`);
		await page.waitForURL(/\/trips\/[^/]+/);
		const contentToggle = page.locator('[data-testid="report-show-official-alerts"]:visible');
		await expect(contentToggle).toBeVisible({ timeout: 15000 });
		const contentCheckbox = contentToggle.locator('input[type="checkbox"]');
		await expect(contentCheckbox).toBeChecked();

		const contentPutPromise = page.waitForResponse(
			(r) => r.url().includes(`/api/trips/${id}`) && r.request().method() === 'PUT'
		);
		await contentCheckbox.click();
		const contentPut = await contentPutPromise;
		expect(contentPut.ok(), 'Content-Tab-PUT fehlgeschlagen: ' + contentPut.status()).toBeTruthy();

		const afterContentPut = await getTrip(page, id);
		expect(afterContentPut.official_alerts_enabled, 'Nach Content-Tab-PUT').toBe(false);

		// Im Alarme-Tab ein beliebiges Alarm-Feld aendern (Cooldown), Save abwarten.
		const putBodies: Record<string, unknown>[] = [];
		page.on('requestfinished', async (req) => {
			if (req.method() === 'PUT' && req.url().includes(`/api/trips/${id}`)) {
				try {
					const data = req.postDataJSON();
					putBodies.push(data);
				} catch {
					/* kein JSON-Body — ignorieren */
				}
			}
		});

		await page.goto(`/trips/${id}?tab=alarme`);
		await page.waitForURL(/\/trips\/[^/]+/);
		const cooldownInput = page.locator('[data-testid="alert-cooldown-input"]:visible');
		await expect(cooldownInput).toBeVisible({ timeout: 15000 });
		await cooldownInput.fill('45');
		// Debounced Auto-Save (saveController) — auf mindestens einen PUT warten.
		await page.waitForResponse(
			(r) => r.url().includes(`/api/trips/${id}`) && r.request().method() === 'PUT',
			{ timeout: 20000 }
		);
		// Debounce-Nachlauf abwarten, falls mehrere PUTs feuern.
		await page.waitForTimeout(2000);

		expect(putBodies.length, 'Alarme-Tab hat keinen PUT ausgeloest').toBeGreaterThan(0);
		for (const body of putBodies) {
			expect(
				Object.prototype.hasOwnProperty.call(body, 'official_alerts_enabled'),
				'Alarme-Tab-PUT enthaelt official_alerts_enabled: ' + JSON.stringify(body)
			).toBe(false);
		}

		const afterAlarmSave = await getTrip(page, id);
		expect(afterAlarmSave.official_alerts_enabled, 'Nach Alarme-Tab-Save').toBe(false);
		await page.screenshot({ path: '/home/hem/gregor_zwanzig/docs/artifacts/d2-1301-doppelter-warnschalter/ac-2-trip-single-writer-PASS.png' });
	});

	// ── Adversary Round 2: rapides Doppel-Toggle + Round-Trip beide Richtungen ──
	test('AC-6 Adversary: rasches Doppel-Toggle (aus/an) persistiert den finalen Zustand korrekt', async ({ page }) => {
		const locA = await createLocation(page, 'D2 R2 Ort A', 46.9, 9.9);
		const locB = await createLocation(page, 'D2 R2 Ort B', 47.0, 10.0);
		const locC = await createLocation(page, 'D2 R2 Ort C', 47.1, 10.1);
		const id = await createCompare(page, `D2 R2 AC6 ${Date.now()}`, [locA, locB, locC]);

		await page.goto(`/compare/${id}?tab=wetter-metriken`);
		await page.waitForURL(/\/compare\/[^/]+/);
		const toggle = page.locator('[data-testid="report-show-official-alerts"]:visible');
		await expect(toggle).toBeVisible({ timeout: 15000 });
		const checkbox = toggle.locator('input[type="checkbox"]');
		await expect(checkbox).toBeChecked();

		// Schnell aus -> an klicken (Doppel-Submit-Risiko), auf beide PUTs warten.
		const firstPut = page.waitForResponse(
			(r) => r.url().includes(`/api/compare/presets/${id}`) && r.request().method() === 'PUT'
		);
		await checkbox.click();
		await firstPut;
		const secondPut = page.waitForResponse(
			(r) => r.url().includes(`/api/compare/presets/${id}`) && r.request().method() === 'PUT'
		);
		await checkbox.click();
		const secondRes = await secondPut;
		expect(secondRes.ok(), 'zweiter PUT fehlgeschlagen: ' + secondRes.status()).toBeTruthy();

		// Finaler Zustand nach aus->an muss wieder true sein (kein Stale-Write-Verlust).
		const afterToggleBack = await getPreset(page, id);
		expect(afterToggleBack.official_alerts_enabled, 'Round-Trip aus->an').toBe(true);

		await page.reload();
		await page.waitForURL(/\/compare\/[^/]+/);
		await page.goto(`/compare/${id}?tab=wetter-metriken`);
		const toggle2 = page.locator('[data-testid="report-show-official-alerts"]:visible');
		await expect(toggle2).toBeVisible({ timeout: 15000 });
		await expect(toggle2.locator('input[type="checkbox"]')).toBeChecked();
	});

	test('AC-2 Adversary: mehrfache Alarme-Tab-Saves (Doppel-Aenderung) schreiben official_alerts_enabled nie', async ({
		page
	}) => {
		const id = `d2-r2-ac2-trip-${Date.now()}`;
		await createTrip(page, id);

		await page.goto(`/trips/${id}?tab=weather`);
		await page.waitForURL(/\/trips\/[^/]+/);
		const contentToggle = page.locator('[data-testid="report-show-official-alerts"]:visible');
		await expect(contentToggle).toBeVisible({ timeout: 15000 });
		const contentCheckbox = contentToggle.locator('input[type="checkbox"]');
		const contentPutPromise = page.waitForResponse(
			(r) => r.url().includes(`/api/trips/${id}`) && r.request().method() === 'PUT'
		);
		await contentCheckbox.click();
		await contentPutPromise;
		const afterContentPut = await getTrip(page, id);
		expect(afterContentPut.official_alerts_enabled, 'Nach Content-Tab-PUT').toBe(false);

		const putBodies: Record<string, unknown>[] = [];
		page.on('requestfinished', async (req) => {
			if (req.method() === 'PUT' && req.url().includes(`/api/trips/${id}`)) {
				try {
					putBodies.push(req.postDataJSON());
				} catch {
					/* kein JSON-Body */
				}
			}
		});

		await page.goto(`/trips/${id}?tab=alarme`);
		await page.waitForURL(/\/trips\/[^/]+/);
		const cooldownInput = page.locator('[data-testid="alert-cooldown-input"]:visible');
		await expect(cooldownInput).toBeVisible({ timeout: 15000 });
		// Zwei rasche Aenderungen hintereinander (Doppel-Submit-Adversary).
		await cooldownInput.fill('30');
		await page.waitForTimeout(300);
		await cooldownInput.fill('60');
		await page.waitForResponse(
			(r) => r.url().includes(`/api/trips/${id}`) && r.request().method() === 'PUT',
			{ timeout: 20000 }
		);
		await page.waitForTimeout(2500);

		expect(putBodies.length, 'Alarme-Tab hat keinen PUT ausgeloest').toBeGreaterThan(0);
		for (const body of putBodies) {
			expect(
				Object.prototype.hasOwnProperty.call(body, 'official_alerts_enabled'),
				'Alarme-Tab-PUT enthaelt official_alerts_enabled: ' + JSON.stringify(body)
			).toBe(false);
		}

		const afterAlarmSave = await getTrip(page, id);
		expect(afterAlarmSave.official_alerts_enabled, 'Nach mehrfachem Alarme-Tab-Save').toBe(false);
	});
});

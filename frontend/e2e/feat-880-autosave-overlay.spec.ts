// feat_880 — Autospeicher-Indikator: Timestamp + fixes Overlay.
// Spec: docs/specs/modules/feat_880_autosave_overlay.md (Issue #947).
// Charakterisierungstests gegen den LIVE-Code auf Staging (kein Mock; die Route-
// Injektion in AC-4 ist reine Fehler-Injektion, kein Verhaltens-Mock).
// Ausführen: cd frontend && npx playwright test e2e/feat-880-autosave-overlay.spec.ts \
//   --config=playwright.880.staging.config.ts --reporter=list

import { test, expect, type Page } from '@playwright/test';

const TRIP_ID = 'e2e-880-overlay';
const TRIP_NAME = 'E2E #880 Overlay';

const wp = (id: string, lat: number) => ({ id, name: id, lat, lon: 9.0, elevation_m: 800 });

const seedBody = {
	id: TRIP_ID,
	name: TRIP_NAME,
	region: 'Korsika',
	stages: [
		{ id: 's1', name: 'Tag 1', date: '2026-08-01', waypoints: [wp('a', 42.0), wp('b', 42.04)] },
		{ id: 's2', name: 'Tag 2', date: '2026-08-02', waypoints: [wp('c', 42.1), wp('d', 42.14)] }
	],
	report_config: {
		enabled: true,
		morning_enabled: true,
		evening_enabled: true,
		morning_time: '07:00:00',
		evening_time: '18:00:00'
	}
};

function saveIndicator(page: Page) {
	return page.getByTestId('save-indicator');
}

async function openStagesEditor(page: Page) {
	await page.goto(`/trips/${TRIP_ID}?tab=stages`);
	await expect(page.getByTestId('edit-stages-panel')).toBeVisible();
	await expect(page.getByTestId('stage-date-field').first()).toBeVisible();
}

function firstDateInput(page: Page) {
	return page.getByTestId('stage-date-field').first().locator('input[type="date"]');
}

// Computed CSS-Property des Overlays im Browser auslesen (keine Style-Attribut-Analyse).
async function overlayStyle(page: Page, prop: string): Promise<string> {
	return saveIndicator(page).evaluate(
		(el, p) => getComputedStyle(el as HTMLElement).getPropertyValue(p),
		prop
	);
}

async function changeStageDate(page: Page, value: string) {
	const input = firstDateInput(page);
	await input.fill(value);
	await input.blur();
}

test.describe('feat_880 — Trip-Editor Autospeicher-Overlay', () => {
	test.beforeEach(async ({ page }) => {
		await page.request.delete(`/api/trips/${TRIP_ID}`).catch(() => {});
		const res = await page.request.post('/api/trips', { data: seedBody });
		expect(res.ok(), `seed HTTP ${res.status()}`).toBeTruthy();
	});

	test.afterEach(async ({ page }) => {
		await page.request.delete(`/api/trips/${TRIP_ID}`).catch(() => {});
	});

	// AC-1: Overlay ist position:fixed; kein inline-Indikator in der Header-Statuszeile.
	test('AC-1: Overlay ist fixed, kein zweiter inline-Indikator', async ({ page }) => {
		await openStagesEditor(page);
		await expect(saveIndicator(page)).toBeVisible();
		expect(await overlayStyle(page, 'position')).toBe('fixed');
		// Genau ein Indikator im DOM — kein zusätzlicher inline in der Statuszeile.
		await expect(saveIndicator(page)).toHaveCount(1);
	});

	// AC-2 (KERN): Etappen-Datum ändern → Auto-Save → idle → .save-time zeigt HH:MM.
	test('AC-2: nach Auto-Save zeigt Overlay Uhrzeit im Format HH:MM', async ({ page }) => {
		await openStagesEditor(page);
		await changeStageDate(page, '2026-08-20');

		await expect(saveIndicator(page)).toHaveAttribute('data-state', 'idle', { timeout: 10_000 });
		const saveTime = saveIndicator(page).locator('.save-time');
		await expect(saveTime).toBeVisible();
		await expect(saveTime).toHaveText(/^\d{2}:\d{2}$/);
		await expect(saveIndicator(page)).toContainText(/Gespeichert/i);
	});

	// AC-3: idle-Overlay dimmt nach >3s auf opacity ≤ 0.5, bleibt aber sichtbar/erreichbar.
	test('AC-3: idle-Overlay dimmt nach 3s auf opacity ≤ 0.5 (nie display:none)', async ({
		page
	}) => {
		await openStagesEditor(page);
		await changeStageDate(page, '2026-08-21');
		await expect(saveIndicator(page)).toHaveAttribute('data-state', 'idle', { timeout: 10_000 });

		// Fade-Animation startet 3s nach Erreichen von idle → warten, dann messen.
		await page.waitForTimeout(3_300);
		const opacity = parseFloat(await overlayStyle(page, 'opacity'));
		expect(opacity).toBeLessThanOrEqual(0.5);
		expect(opacity).toBeGreaterThan(0);
		expect(await overlayStyle(page, 'display')).not.toBe('none');
	});

	// AC-4: PUT scheitert → data-state="error"; bleibt dauerhaft opacity:1 (kein Dimming).
	test('AC-4: Save-Fehler → error-Zustand bleibt bei opacity 1', async ({ page }) => {
		await openStagesEditor(page);
		await page.route(`**/api/trips/${TRIP_ID}`, (route) => {
			if (route.request().method() === 'PUT') {
				return route.fulfill({ status: 500, body: JSON.stringify({ error: 'Serverfehler' }) });
			}
			return route.continue();
		});

		await changeStageDate(page, '2026-08-22');
		await expect(saveIndicator(page)).toHaveAttribute('data-state', 'error', { timeout: 10_000 });

		// Auch nach Ablauf des Idle-Fade-Fensters kein Dimming.
		await page.waitForTimeout(3_300);
		const opacity = parseFloat(await overlayStyle(page, 'opacity'));
		expect(opacity).toBe(1);
	});

	// AC-5: Mobile-Viewport — Overlay sitzt ≥ 64px über dem Viewport-Unterrand,
	// BottomNav bleibt sichtbar und klickbar (nicht verdeckt).
	test('AC-5: Mobile — Overlay über der BottomNav, Nav klickbar', async ({ page }) => {
		await page.setViewportSize({ width: 390, height: 844 });
		await openStagesEditor(page);
		await expect(saveIndicator(page)).toBeVisible();

		const box = await saveIndicator(page).boundingBox();
		expect(box, 'Overlay hat eine BoundingBox').not.toBeNull();
		const viewport = page.viewportSize()!;
		const bottomGap = viewport.height - (box!.y + box!.height);
		expect(bottomGap).toBeGreaterThanOrEqual(64);

		const nav = page.getByTestId('bottom-nav');
		await expect(nav).toBeVisible();
		const compareItem = page.getByTestId('bottom-nav-item-compare');
		await expect(compareItem).toBeVisible();

		// Das Overlay darf die BottomNav nicht überlagern: Der Overlay-Kasten
		// überschneidet den Nav-Kasten geometrisch nicht (Overlay sitzt darüber).
		const navBox = (await nav.boundingBox())!;
		expect(box!.y + box!.height).toBeLessThanOrEqual(navBox.y + 1);

		// Am Nav-Mittelpunkt liegt NICHT das save-indicator-Overlay ganz oben (Scope
		// dieser Spec ist ausschließlich das Overlay; ein app-weiter Sheet-Host nicht).
		const itemBox = (await compareItem.boundingBox())!;
		const overlaysNav = await page.evaluate(
			({ x, y }) => {
				const el = document.elementFromPoint(x, y) as HTMLElement | null;
				return !!el?.closest('[data-testid="save-indicator"]');
			},
			{ x: itemBox.x + itemBox.width / 2, y: itemBox.y + itemBox.height / 2 }
		);
		expect(overlaysNav, 'save-indicator darf die BottomNav nicht verdecken').toBe(false);
	});
});

test.describe('feat_880 — Compare-Editor & Cross-Tab-Isolation', () => {
	async function createPreset(page: Page): Promise<string> {
		// Eindeutige Ortsnamen je Lauf — feste Namen kollidieren (HTTP 409).
		const suffix = Date.now();
		const resA = await page.request.post('/api/locations', {
			data: { name: `Ort-880-A ${suffix}`, lat: 47.4, lon: 13.0, region: 'Hochkönig' }
		});
		expect(resA.ok(), `locA HTTP ${resA.status()}`).toBeTruthy();
		const locA = await resA.json();
		const resB = await page.request.post('/api/locations', {
			data: { name: `Ort-880-B ${suffix}`, lat: 47.1, lon: 12.8, region: 'Hochkönig' }
		});
		expect(resB.ok(), `locB HTTP ${resB.status()}`).toBeTruthy();
		const locB = await resB.json();
		const resP = await page.request.post('/api/compare/presets', {
			data: {
				name: 'Vergleich #880 ' + suffix,
				location_ids: [locA.id, locB.id],
				schedule: 'daily',
				profil: 'wintersport',
				hour_from: 7,
				hour_to: 16,
				empfaenger: ['e2e-880@example.com'],
				display_config: {}
			}
		});
		expect(resP.ok(), `Preset HTTP ${resP.status()}`).toBeTruthy();
		return (await resP.json()).id;
	}

	// AC-7: Compare-Editor rendert genau EIN Overlay (kein zweiter inline-Indikator).
	test('AC-7: Compare-Editor hat genau ein save-indicator', async ({ page }) => {
		const presetId = await createPreset(page);
		await page.goto(`/compare/${presetId}`);
		await expect(page.getByTestId('compare-detail-tab-list')).toBeVisible();
		await expect(saveIndicator(page)).toHaveCount(1);
		expect(await overlayStyle(page, 'position')).toBe('fixed');
	});

	// AC-6: Trip-Editor und Compare-Editor in getrennten Kontexten. Speichern im
	// Trip-Editor setzt dessen Timestamp; der Compare-Indikator zeigt NICHT denselben
	// Zustand/Timestamp — jede Seite hat eine isolierte SaveStatus-Instanz.
	test('AC-6: Trip- und Compare-Indikator sind unabhängig (kein geteilter Store)', async ({
		browser
	}) => {
		const ctxTrip = await browser.newContext({
			storageState: 'playwright/.auth/staging-880.json'
		});
		const ctxCompare = await browser.newContext({
			storageState: 'playwright/.auth/staging-880.json'
		});
		const pageTrip = await ctxTrip.newPage();
		const pageCompare = await ctxCompare.newPage();
		try {
			// Trip seeden + öffnen.
			await pageTrip.request.delete(`/api/trips/${TRIP_ID}`).catch(() => {});
			const seed = await pageTrip.request.post('/api/trips', { data: seedBody });
			expect(seed.ok(), `seed HTTP ${seed.status()}`).toBeTruthy();

			const presetId = await createPreset(pageCompare);
			await pageCompare.goto(`/compare/${presetId}`);
			await expect(pageCompare.getByTestId('compare-detail-tab-list')).toBeVisible();
			// Compare-Editor frisch → idle, kein savedAt-Timestamp.
			await expect(saveIndicator(pageCompare)).toHaveAttribute('data-state', 'idle');
			await expect(saveIndicator(pageCompare).locator('.save-time')).toHaveCount(0);

			// Im Trip-Editor speichern → dessen Timestamp erscheint.
			await pageTrip.goto(`/trips/${TRIP_ID}?tab=stages`);
			await expect(pageTrip.getByTestId('edit-stages-panel')).toBeVisible();
			const input = pageTrip.getByTestId('stage-date-field').first().locator('input[type="date"]');
			await input.fill('2026-08-23');
			await input.blur();
			await expect(saveIndicator(pageTrip)).toHaveAttribute('data-state', 'idle', {
				timeout: 10_000
			});
			await expect(saveIndicator(pageTrip).locator('.save-time')).toBeVisible();

			// Der Compare-Indikator hat sich NICHT verändert (isolierte Instanz).
			await expect(saveIndicator(pageCompare).locator('.save-time')).toHaveCount(0);
			await expect(saveIndicator(pageCompare)).toHaveAttribute('data-state', 'idle');

			await pageTrip.request.delete(`/api/trips/${TRIP_ID}`).catch(() => {});
		} finally {
			await ctxTrip.close();
			await ctxCompare.close();
		}
	});
});

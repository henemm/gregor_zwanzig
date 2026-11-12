// E2E (Staging) — Issue #2794 S3a, Teil-PR 4b: Listen-Sprünge, Menü-Wortlaut, Übersicht U3/U4, Englisch.
// Spec: docs/specs/modules/feat_2794_s3a_teil4_entfernen.md — AC-32, AC-33, AC-34, AC-48
// Fix-Loop: docs/specs/modules/fix_2794_s3a_teil4b_befunde.md — AC-4, AC-6, AC-7, AC-8 (Ende der Datei)
// Nur gegen Staging (/e2e-verify), nie gegen Produktion. Daten nur Wegwerf (Präfix E2E-GZ-).
//
//   cd frontend && npx playwright test --config playwright.2794-s3a4b.staging.config.ts

import { test, expect, type Page } from '@playwright/test';
import { cleanupTracked, createTestTrip, seedHub } from './helpers';

const HANDY = { width: 390, height: 844 };
const DESKTOP = { width: 1280, height: 900 };

test.afterEach(async ({ page }) => {
	await cleanupTracked(page.request);
});

async function aktiverTrip(page: Page): Promise<string> {
	const heute = new Date().toISOString().slice(0, 10);
	const tripId = `e2e-gz-trip-${Date.now()}-${Math.floor(Math.random() * 1e6)}`;
	const { id } = await createTestTrip(page.request, {
		id: tripId,
		stages: [
			{
				id: `${tripId}-s1`,
				name: 'Etappe 1',
				date: heute,
				waypoints: [{ id: `${tripId}-w1`, name: 'Start', lat: 42.1, lon: 9.0, elevation_m: 500 }]
			}
		]
	});
	return id;
}

type Ziel = { aktion: 'weather' | 'alarms'; label: string; tab: 'wetter' | 'zustellung' };
const ZIELE_DE: Ziel[] = [
	{ aktion: 'weather', label: 'Wetter', tab: 'wetter' },
	{ aktion: 'alarms', label: 'Alarme', tab: 'zustellung' }
];

/** Öffnet das Listen-Menü und liefert den Menüeintrag (Handy: Aktionsblatt, Desktop: Zeilen-Kebab). */
async function eintragImMenue(page: Page, kind: 'trip' | 'compare', id: string, ansicht: 'handy' | 'desktop', z: Ziel) {
	if (ansicht === 'handy') {
		await page.getByTestId(`subscription-card-menu-${id}`).click();
		return page.getByTestId(`subscription-action-${z.aktion}`).locator('visible=true').first();
	}
	const zeile = page.getByTestId(kind === 'trip' ? `trip-row-${id}` : `compare-tile-${id}`).locator('visible=true').first();
	await zeile.getByTestId(kind === 'trip' ? 'trip-row-menu-btn' : 'compare-row-kebab').click();
	const menue = page.getByRole('menu');
	await expect(menue).not.toContainText('Wetter-Metriken');
	return menue.getByRole('menuitem', { name: z.label, exact: true });
}

for (const ansicht of ['handy', 'desktop'] as const) {
	for (const z of ZIELE_DE) {
		test(`AC-33/AC-48 Trip-Liste (${ansicht}): „${z.label}" führt in den Reiter ${z.tab}`, async ({ page }) => {
			const id = await aktiverTrip(page);
			await page.setViewportSize(ansicht === 'handy' ? HANDY : DESKTOP);
			await page.goto('/trips');
			const eintrag = await eintragImMenue(page, 'trip', id, ansicht, z);
			await expect(eintrag).toContainText(z.label);
			await eintrag.click();
			await expect(page).toHaveURL(new RegExp(`/trips/${id}\\?tab=${z.tab}`), { timeout: 15_000 });
			await expect(page.locator(`[data-testid="trip-detail-panel-${z.tab}"]:visible`).first()).toBeVisible({ timeout: 15_000 });
		});

		test(`AC-33/AC-48 Orts-Liste (${ansicht}): „${z.label}" führt in den Reiter ${z.tab}`, async ({ page }) => {
			const hub = await seedHub(page.request, 'vergleich');
			try {
				await page.setViewportSize(ansicht === 'handy' ? HANDY : DESKTOP);
				await page.goto('/compare');
				const eintrag = await eintragImMenue(page, 'compare', hub.id, ansicht, z);
				await expect(eintrag).toContainText(z.label);
				await eintrag.click();
				await expect(page).toHaveURL(new RegExp(`/compare/${hub.id}\\?tab=${z.tab}`), { timeout: 15_000 });
				await expect(page.locator(`[data-testid="compare-detail-panel-${z.tab}"]:visible`).first()).toBeVisible({ timeout: 15_000 });
			} finally {
				await hub.aufraeumen();
			}
		});
	}
}

test('AC-32 U3: Übersicht Orts-Briefing nennt „Wetter" und springt in den Reiter Wetter', async ({ page }) => {
	const hub = await seedHub(page.request, 'vergleich');
	try {
		await page.setViewportSize(DESKTOP);
		await page.goto(`/compare/${hub.id}?tab=uebersicht`);
		const panel = page.locator('[data-testid="compare-detail-panel-uebersicht"]:visible').first();
		await expect(panel).toBeVisible({ timeout: 15_000 });
		await expect(panel).not.toContainText(/Wertebereiche/i);
		const karte = panel.locator('div', { has: page.getByText('Wetter', { exact: true }) }).filter({ has: page.getByRole('button', { name: /Bearbeiten/ }) }).last();
		await karte.getByRole('button', { name: /Bearbeiten/ }).first().click();
		await expect(page).toHaveURL(new RegExp(`/compare/${hub.id}\\?tab=wetter`), { timeout: 15_000 });
		await expect(page.locator('[data-testid="compare-detail-panel-wetter"]:visible').first()).toBeVisible({ timeout: 15_000 });
	} finally {
		await hub.aufraeumen();
	}
});

test('AC-32 U4: Trip-Übersicht zeigt den „Alarm ab"-Zähler wie der Reiter Wetter', async ({ page }) => {
	const id = await aktiverTrip(page);
	await page.setViewportSize(DESKTOP);
	await page.goto(`/trips/${id}?tab=uebersicht`);
	const ov = page.locator('[data-testid="hub-overview"]:visible').first();
	await expect(ov).toBeVisible({ timeout: 15_000 });
	await expect(ov).toContainText(/\d+ von \d+ Metriken lösen einen Alarm aus|—/, { timeout: 15_000 });
	const text = (await ov.innerText()).match(/(\d+) von (\d+) Metriken lösen einen Alarm aus/);
	await page.goto(`/trips/${id}?tab=wetter`);
	const zaehler = page.locator('[data-testid="wetter-alarm-zaehler"]:visible').first();
	await expect(zaehler).toBeVisible({ timeout: 15_000 });
	if (text) await expect(zaehler).toContainText(`${text[1]} von ${text[2]} Metriken lösen einen Alarm aus`);
});

test('AC-34/AC-48 Englisch: Menü heißt „Weather" und „Alerts", Übersicht englisch', async ({ page }) => {
	const id = await aktiverTrip(page);
	const res = await page.request.put('/api/auth/profile', { data: { language: 'en' } });
	expect(res.ok(), `Sprachwechsel: ${res.status()}`).toBeTruthy();
	try {
		await page.setViewportSize(HANDY);
		await page.goto('/trips');
		await page.getByTestId(`subscription-card-menu-${id}`).click();
		await expect(page.getByTestId('subscription-action-weather').locator('visible=true').first()).toContainText('Weather');
		await expect(page.getByTestId('subscription-action-alarms').locator('visible=true').first()).toContainText('Alerts');
		await page.getByTestId('subscription-action-weather').locator('visible=true').first().click();
		await expect(page).toHaveURL(new RegExp(`/trips/${id}\\?tab=wetter`), { timeout: 15_000 });
		await page.setViewportSize(DESKTOP);
		await page.goto(`/trips/${id}?tab=uebersicht`);
		const ov = page.locator('[data-testid="hub-overview"]:visible').first();
		await expect(ov).toContainText(/\d+ of \d+ metrics trigger an alert|—/, { timeout: 15_000 });
	} finally {
		await page.request.put('/api/auth/profile', { data: { language: 'de' } }).catch(() => {});
	}
});

test('AC-33 Startseite: Schnellaktionen führen in Reiter Wetter bzw. Zustellung, keine alten Reiter', async ({ page }) => {
	await aktiverTrip(page);
	await page.setViewportSize(DESKTOP);
	await page.goto('/');
	const wetter = page.locator('a[href*="?tab=wetter"]:visible').first();
	await expect(wetter).toBeVisible({ timeout: 15_000 });
	await expect(page.locator('a[href*="?tab=alerts"], a[href*="?tab=layout"], a[href*="?tab=wertebereiche"], a[href*="?tab=idealwerte"]')).toHaveCount(0);
	await expect(page.locator('a[href*="?tab=zustellung"]:visible').first()).toBeVisible();
	await wetter.click();
	await expect(page).toHaveURL(/\?tab=wetter/, { timeout: 15_000 });
	await expect(page.locator('[data-testid$="-panel-wetter"]:visible').first()).toBeVisible({ timeout: 15_000 });
});

// ── #2794 Fix-Loop teil4b (Spec fix_2794_s3a_teil4b_befunde): AC-4, AC-6, AC-7, AC-8 ──

const PILLS = ['uebersicht', 'etappen', 'wetter', 'zustellung'] as const;

/** Karten-Raster der Übersicht: Elternelement der Karte mit dem Versand-Knopf. */
function kartenRaster(page: Page, versandTestid: string) {
	return page
		.locator(`[data-testid="${versandTestid}"]:visible`)
		.first()
		.locator('xpath=ancestor::div[@data-slot="card"][1]/..');
}

for (const sprache of ['de', 'en'] as const) {
	for (const breite of [360, 375, 390]) {
		test(`AC-4 Pill-Leiste Trip ${breite} px (${sprache}): vier Pills ohne Wischen sichtbar, je ≥ 44 px hoch`, async ({ page }) => {
			const id = await aktiverTrip(page);
			if (sprache === 'en') {
				const res = await page.request.put('/api/auth/profile', { data: { language: 'en' } });
				expect(res.ok(), `Sprachwechsel: ${res.status()}`).toBeTruthy();
			}
			try {
				await page.setViewportSize({ width: breite, height: 800 });
				await page.goto(`/trips/${id}?tab=uebersicht`);
				const leiste = page.locator('[data-testid="trip-detail-tab-list"] .mtabbar').first();
				await expect(leiste).toBeVisible({ timeout: 15_000 });
				await expect(page.getByTestId('trip-detail-tab-etappen')).toContainText(sprache === 'en' ? 'Stages' : 'Etappen');
				const lb = await leiste.boundingBox();
				expect(lb, 'Leiste ohne Box').not.toBeNull();
				const ueberlauf = await leiste.evaluate((el) => el.scrollWidth - el.clientWidth);
				expect(ueberlauf, `Leiste muss gewischt werden (Überlauf ${ueberlauf} px)`).toBeLessThanOrEqual(0);
				for (const p of PILLS) {
					const b = await page.getByTestId(`trip-detail-tab-${p}`).boundingBox();
					expect(b, `Pill ${p} ohne Box`).not.toBeNull();
					expect(b!.x, `Pill ${p} links abgeschnitten`).toBeGreaterThanOrEqual(lb!.x - 0.5);
					expect(b!.x + b!.width, `Pill ${p} rechts abgeschnitten`).toBeLessThanOrEqual(lb!.x + lb!.width + 0.5);
					expect(b!.height, `Pill ${p} ist ${b!.height} px hoch`).toBeGreaterThanOrEqual(44);
				}
			} finally {
				if (sprache === 'en') await page.request.put('/api/auth/profile', { data: { language: 'de' } }).catch(() => {});
			}
		});
	}
}

// #2794 B3: Desktop beginnt bei 900 px Viewport; mit 220 px Seitenleiste ist das Raster bei
// 1024 px nur ~700 px breit — genau dort stand die Versand-Karte allein in halber Breite.
const DESKTOP_BREITEN = [1024, 1280, 1440];

for (const breite of DESKTOP_BREITEN) {
	test(`AC-6 Trip-Übersicht Desktop ${breite} px: Versand-Karte füllt die Zeile (≥ 90 % des Rasters)`, async ({ page }) => {
		const id = await aktiverTrip(page);
		await page.setViewportSize({ width: breite, height: 900 });
		await page.goto(`/trips/${id}?tab=uebersicht`);
		const raster = kartenRaster(page, 'hub-uebersicht-versand-edit');
		await expect(raster).toBeVisible({ timeout: 15_000 });
		const r = await raster.boundingBox();
		const k = await raster.locator(':scope > [data-slot="card"]').first().boundingBox();
		expect(r && k, 'Raster/Karte ohne Box').toBeTruthy();
		expect(k!.width / r!.width, `Versand-Karte ${k!.width} von ${r!.width} px`).toBeGreaterThanOrEqual(0.9);
	});

	test(`AC-7 Vergleich-Übersicht Desktop ${breite} px: keine Karte allein in halber Breite`, async ({ page }) => {
		const hub = await seedHub(page.request, 'vergleich');
		try {
			await page.setViewportSize({ width: breite, height: 900 });
			await page.goto(`/compare/${hub.id}?tab=uebersicht`);
			const raster = kartenRaster(page, 'compare-hub-versand-edit');
			await expect(raster).toBeVisible({ timeout: 15_000 });
			const r = (await raster.boundingBox())!;
			const karten = raster.locator(':scope > [data-slot="card"]');
			await expect(karten).toHaveCount(3);
			const boxen = [];
			for (let i = 0; i < 3; i++) boxen.push((await karten.nth(i).boundingBox())!);
			// Zeilen nach y gruppieren; jede Zeile muss gefüllt sein (eine Karte allein füllt sie).
			const zeilen = new Map<number, typeof boxen>();
			for (const b of boxen) {
				const key = [...zeilen.keys()].find((y) => Math.abs(y - b.y) < 2) ?? b.y;
				zeilen.set(key, [...(zeilen.get(key) ?? []), b]);
			}
			for (const [y, z] of zeilen) {
				const links = Math.min(...z.map((b) => b.x));
				const rechts = Math.max(...z.map((b) => b.x + b.width));
				expect((rechts - links) / r.width, `Zeile y=${y} (${z.length} Karte(n)): ${rechts - links} von ${r.width} px belegt`).toBeGreaterThanOrEqual(0.9);
				if (z.length === 1) expect(z[0].width / r.width, `Karte allein in Zeile y=${y}: ${z[0].width} von ${r.width} px`).toBeGreaterThanOrEqual(0.9);
			}
		} finally {
			await hub.aufraeumen();
		}
	});
}

test('AC-8 Vergleich-Übersicht: Karte „Wetter" nennt die Metriken im Briefing (Zahl > 0)', async ({ page }) => {
	// Seed ohne gespeicherte Metrikliste ⇒ die Vorlage gilt (wie im Reiter Wetter).
	const hub = await seedHub(page.request, 'vergleich');
	try {
		await page.setViewportSize(DESKTOP);
		await page.goto(`/compare/${hub.id}?tab=uebersicht`);
		const panel = page.locator('[data-testid="compare-detail-panel-uebersicht"]:visible').first();
		await expect(panel).toContainText(/\d+ Metriken? im Briefing/, { timeout: 15_000 });
		const n = Number((await panel.innerText()).match(/(\d+) Metriken? im Briefing/)![1]);
		expect(n, 'Karte „Wetter" zählt 0 Metriken').toBeGreaterThan(0);
		await expect(panel).not.toContainText('Idealbereich');
		await expect(panel).not.toContainText('Markierung, kein Score');
	} finally {
		await hub.aufraeumen();
	}
});

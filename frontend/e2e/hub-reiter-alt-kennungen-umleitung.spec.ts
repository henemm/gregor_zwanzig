// E2E — gemeinsame Reiter-Kennungen in Trip- und Ortsvergleich-Hub (Issue #2287,
// Epic #2345 Etappe P2 „eine Reiterleiste").
//
// Spec: docs/specs/modules/feat_2287_tab_kennungen.md
// Abgedeckt hier (Browser-Hälfte, die der SSR-Harness nicht sieht):
//   AC-3/AC-12 — Alt-Kennung öffnet den neuen Reiter UND die Adresszeile wird per
//                replaceState bereinigt (kein zusätzlicher Verlaufseintrag).
//   AC-5       — kind-fremde Punkte-Kennung (Trip `orte`, Vergleich `etappen`).
//   AC-6       — unbekannte Kennung → Übersicht, Parameter `tab` entfernt.
//   AC-10      — Bestandsfehler: Startseiten-Schnellaktion „Vorschau prüfen" eines
//                Ortsvergleichs und der „Wetter"-Eintrag der Trip-Liste.
//   AC-14      — Handy-Reiterleiste (MTabBar) in beiden Hubs: gleiche Kennungen,
//                gleiche Reihenfolge; Antippen öffnet den Reiter.
//
// AC-10, dritter Bestandsfehler (WeatherSummaryCard `#weather`): NICHT im Browser
// prüfbar. `WeatherSummaryCard.svelte` wird nur von `EditWeatherSection.svelte`
// eingebunden, und `EditWeatherSection` ist von keiner Route mehr eingebunden
// (grep am 2026-10-05). Der Link ist für den Nutzer unerreichbar; die Ziel-URL
// bewacht der Unit-Test der Spec (AC-10 „Unit-Test auf die erzeugten Ziel-URLs").
//
// Daten: nur Wegwerf-Trips/-Vergleiche (Präfix E2E-GZ-, cleanupTracked). Der
// Startseiten-Test braucht einen Nutzer OHNE laufenden Trip (sonst zeigt die
// Startseite den Trip-Modus, nicht den Vergleich-Modus) — dafür ein frisch
// registrierter Zweitnutzer über den Staging-Testweg (wie
// konto-loeschdialog-mobil-ueberlauf.spec.ts), der am Ende gelöscht wird.
//
// Ausführen (lokal/CI-Stack bzw. gegen Staging mit Staging-Config):
//   cd frontend && npx playwright test e2e/hub-reiter-alt-kennungen-umleitung.spec.ts

import { test, expect, type Page } from '@playwright/test';
import {
	cleanupTracked,
	createTestComparePreset,
	createTestLocation,
	createTestTrip,
	registriereBestaetigtenZweitnutzer
} from './helpers';

const HANDY = { width: 390, height: 844 };

test.afterEach(async ({ page }) => {
	await cleanupTracked(page.request);
});

async function neuerTrip(page: Page): Promise<{ id: string; name: string }> {
	return createTestTrip(page.request);
}

async function neuerVergleich(page: Page): Promise<string> {
	const ids: string[] = [];
	for (let i = 0; i < 2; i++) {
		const loc = await createTestLocation(page.request, { lat: 47.1 + i * 0.1, lon: 11.2 + i * 0.1 });
		ids.push(loc.id);
	}
	const preset = await createTestComparePreset(page.request, { locationIds: ids });
	return preset.id;
}

/** `tab`-Parameter der aktuellen Adresse (null = nicht vorhanden). */
function tabParam(page: Page): string | null {
	return new URL(page.url()).searchParams.get('tab');
}

/** Kennungen der Handy-Reiterleiste in DOM-Reihenfolge, Präfix abgeschnitten. */
async function mobileReiter(page: Page, prefix: string): Promise<string[]> {
	// getByRole überspringt verborgene Elemente (Muster mobile-tab-bar/compare-tab-bar).
	const tabs = page.getByRole('tablist').getByRole('tab');
	const ids: string[] = [];
	for (let i = 0; i < (await tabs.count()); i++) {
		ids.push(((await tabs.nth(i).getAttribute('data-testid')) ?? '').replace(prefix, ''));
	}
	return ids;
}

test.describe('Trip-Hub: Alt-Kennungen werden umgeleitet und die URL bereinigt', () => {
	test('AC-3/AC-12: ?tab=alerts öffnet Wertebereiche, URL wird ?tab=wertebereiche', async ({ page }) => {
		const { id } = await neuerTrip(page);
		await page.goto(`/trips/${id}?tab=alerts`);

		await expect(page.getByTestId('trip-detail-panel-wertebereiche')).toBeVisible({ timeout: 15_000 });
		await expect(page.getByTestId('trip-detail-tab-wertebereiche')).toHaveAttribute('aria-selected', 'true');
		await expect.poll(() => tabParam(page)).toBe('wertebereiche');
		await expect(page.getByTestId('trip-detail-panel-uebersicht')).toHaveCount(0);
	});

	test('AC-3: Umleitung erzeugt keinen Verlaufseintrag — Zurück führt nicht auf die Alt-URL', async ({
		page,
		context
	}) => {
		const { id } = await neuerTrip(page);

		// Referenz: Direktaufruf mit der NEUEN Kennung in einem frischen Tab.
		const direkt = await context.newPage();
		await direkt.goto(`/trips/${id}?tab=wertebereiche`);
		await expect(direkt.getByTestId('trip-detail-panel-wertebereiche')).toBeVisible({ timeout: 15_000 });
		const laengeDirekt = await direkt.evaluate(() => history.length);
		await direkt.close();

		const alt = await context.newPage();
		await alt.goto(`/trips/${id}?tab=alerts`);
		await expect(alt.getByTestId('trip-detail-panel-wertebereiche')).toBeVisible({ timeout: 15_000 });
		await expect.poll(() => tabParam(alt)).toBe('wertebereiche');
		expect(await alt.evaluate(() => history.length), 'replaceState statt pushState').toBe(laengeDirekt);

		await alt.goBack().catch(() => null);
		expect(alt.url(), 'Zurück darf nicht auf ?tab=alerts landen').not.toContain('tab=alerts');
		await alt.close();
	});

	test('AC-5: ?tab=orte (kind-fremd) öffnet Etappen, URL wird ?tab=etappen', async ({ page }) => {
		const { id } = await neuerTrip(page);
		await page.goto(`/trips/${id}?tab=orte`);

		await expect(page.getByTestId('trip-detail-panel-etappen')).toBeVisible({ timeout: 15_000 });
		await expect.poll(() => tabParam(page)).toBe('etappen');
	});

	test('AC-6: ?tab=foo öffnet die Übersicht und entfernt den Parameter', async ({ page }) => {
		const { id } = await neuerTrip(page);
		await page.goto(`/trips/${id}?tab=foo`);

		await expect(page.getByTestId('trip-detail-panel-uebersicht')).toBeVisible({ timeout: 15_000 });
		await expect.poll(() => new URL(page.url()).searchParams.has('tab')).toBe(false);
	});
});

test.describe('Vergleich-Hub: Alt-Kennungen werden umgeleitet und die URL bereinigt', () => {
	test('AC-3/AC-12: ?tab=idealwerte öffnet Wertebereiche, URL wird ?tab=wertebereiche', async ({ page }) => {
		const id = await neuerVergleich(page);
		await page.goto(`/compare/${id}?tab=idealwerte`);

		await expect(
			page.locator('[data-testid="compare-detail-panel-wertebereiche"]:visible').first()
		).toBeVisible({ timeout: 15_000 });
		await expect.poll(() => tabParam(page)).toBe('wertebereiche');
		await expect(page.locator('[data-testid="compare-detail-panel-uebersicht"]')).toHaveCount(0);
	});

	test('AC-5: ?tab=etappen (kind-fremd) öffnet Orte, URL wird ?tab=orte', async ({ page }) => {
		const id = await neuerVergleich(page);
		await page.goto(`/compare/${id}?tab=etappen`);

		await expect(
			page.locator('[data-testid="compare-detail-panel-orte"]:visible').first()
		).toBeVisible({ timeout: 15_000 });
		await expect.poll(() => tabParam(page)).toBe('orte');
	});

	test('AC-6: ?tab=foo öffnet die Übersicht und entfernt den Parameter', async ({ page }) => {
		const id = await neuerVergleich(page);
		await page.goto(`/compare/${id}?tab=foo`);

		await expect(
			page.locator('[data-testid="compare-detail-panel-uebersicht"]:visible').first()
		).toBeVisible({ timeout: 15_000 });
		await expect.poll(() => new URL(page.url()).searchParams.has('tab')).toBe(false);
	});
});

test.describe('AC-10: Bestandsfehler der Schnellaktionen', () => {
	test('Trip-Liste (Handy): „Wetter-Konfiguration" öffnet den Reiter Wetter-Metriken', async ({ page }) => {
		const { id, name } = await neuerTrip(page);
		await page.setViewportSize(HANDY);
		await page.goto('/trips');

		await page.getByRole('button', { name: `Aktionen für ${name}` }).click();
		const sheet = page.getByTestId('trip-action-sheet');
		await expect(sheet).toBeVisible();
		await sheet.getByRole('button', { name: /Wetter-Konfiguration/ }).click();

		await expect(page).toHaveURL(new RegExp(`/trips/${id}\\?tab=wetter-metriken$`), { timeout: 15_000 });
		await expect(page.getByTestId('trip-detail-panel-wetter-metriken')).toBeVisible({ timeout: 15_000 });
	});

	test('Startseite (Vergleich-Modus): „Vorschau prüfen" öffnet die Vorschau, nicht die Übersicht', async ({
		page,
		browser
	}) => {
		// Zweitnutzer ohne Trips ⇒ Startseite im Vergleich-Modus (routes/+page.svelte:64-66).
		const username = `e2ehubreiter${Date.now()}`;
		const password = 'Test1234!x';
		const ctx = await browser.newContext({
			storageState: undefined,
			viewport: { width: 1280, height: 900 },
			serviceWorkers: 'block'
		});
		const gast = await ctx.newPage();
		let angelegt = false;
		try {
			await registriereBestaetigtenZweitnutzer(page.request, gast.request, username, password);
			angelegt = true;

			const loc = await gast.request.post('/api/locations', {
				data: { name: 'E2E-GZ-Reiter-Ort', lat: 47.2, lon: 11.3 }
			});
			expect(loc.ok(), `Ort-Anlage: ${loc.status()}`).toBeTruthy();
			const locId = ((await loc.json()) as { id: string }).id;
			const preset = await gast.request.post('/api/compare/presets', {
				data: {
					name: 'E2E-GZ-Reiter-Vergleich',
					location_ids: [locId],
					schedule: 'daily',
					profil: 'wandern',
					hour_from: 7,
					hour_to: 18,
					empfaenger: []
				}
			});
			expect(preset.ok(), `Vergleich-Anlage: ${preset.status()}`).toBeTruthy();
			const presetId = ((await preset.json()) as { id: string }).id;

			await gast.goto('/');
			await gast.locator('a:visible', { hasText: 'Vorschau prüfen' }).first().click();

			await expect(gast).toHaveURL(new RegExp(`/compare/${presetId}\\?tab=vorschau$`), {
				timeout: 15_000
			});
			await expect(
				gast.locator('[data-testid="compare-detail-panel-vorschau"]:visible').first()
			).toBeVisible({ timeout: 15_000 });
			await expect(gast.locator('[data-testid="compare-detail-panel-uebersicht"]')).toHaveCount(0);
		} finally {
			if (angelegt) {
				await gast.request.post('/api/auth/account/delete', { data: { password } }).catch(() => {});
			}
			await ctx.close();
		}
	});
});

test.describe('AC-14: Handy-Reiterleiste in beiden Hubs gleich', () => {
	const SCHWANZ = ['wetter-metriken', 'wertebereiche', 'alarme', 'versand', 'vorschau'];

	test('Trip: Reihenfolge uebersicht · etappen · … · vorschau, Antippen öffnet Wertebereiche', async ({
		page
	}) => {
		const { id } = await neuerTrip(page);
		await page.setViewportSize(HANDY);
		await page.goto(`/trips/${id}`);
		await expect(page.getByTestId('trip-detail-tab-list')).toBeVisible({ timeout: 15_000 });

		expect(await mobileReiter(page, 'trip-detail-tab-')).toEqual(['uebersicht', 'etappen', ...SCHWANZ]);

		// dispatchEvent statt click: Scroll-Snap + Fade-Maske des Bands stören
		// Playwrights Actionability-Scroll (Muster mobile-tab-bar.spec.ts).
		await page.getByTestId('trip-detail-tab-wertebereiche').dispatchEvent('click');
		await expect(page.getByTestId('trip-detail-panel-wertebereiche')).toBeVisible();
		await expect.poll(() => tabParam(page)).toBe('wertebereiche');
	});

	test('Vergleich: Reihenfolge uebersicht · orte · … · vorschau, Antippen öffnet Wertebereiche', async ({
		page
	}) => {
		const id = await neuerVergleich(page);
		await page.setViewportSize(HANDY);
		await page.goto(`/compare/${id}`);
		await expect(page.getByTestId('compare-detail-tab-list')).toBeVisible({ timeout: 15_000 });

		expect(await mobileReiter(page, 'compare-detail-tab-')).toEqual(['uebersicht', 'orte', ...SCHWANZ]);

		await page.getByTestId('compare-detail-tab-wertebereiche').dispatchEvent('click');
		await expect(
			page.locator('[data-testid="compare-detail-panel-wertebereiche"]:visible').first()
		).toBeVisible();
		await expect.poll(() => tabParam(page)).toBe('wertebereiche');
	});
});

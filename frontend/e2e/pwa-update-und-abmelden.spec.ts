// TDD RED — Issue #2128 (Scheibe 1 zu Epic #2127).
// Spec: docs/specs/modules/pwa_installierbar_offline_start.md
// Abgedeckt: AC-8, AC-9, AC-10, AC-11, AC-12, AC-15
//
// AC-12 ist die Gegenprobe zu AC-11: ohne sie waere AC-11 auch durch
// bedingungsloses Dauer-Raeumen beim Betreten der Anmeldeseite erfuellbar —
// was die Offline-Faehigkeit genau dann zerstoert, wenn sie gebraucht wird.
//
// Ausfuehrung:
//   cd frontend && npx playwright test e2e/pwa-update-und-abmelden.spec.ts

import { test, expect, type Page } from '@playwright/test';
import * as fs from 'node:fs';
import { assertNotProdBaseURL } from './prodUrlGuard.ts';
import {
	AUTH_STATE,
	activateServiceWorker,
	cacheNames,
	controllingScriptUrl,
	readCacheEntries,
	storageAndRegistrationCount,
	triggerServiceWorkerUpdate
} from './pwaHelpers.ts';

test.use({ serviceWorkers: 'allow' });

// Die Abmelde-Nachweise veraendern den geteilten Anmelde-Zustand. Innerhalb
// einer Datei laeuft Playwright ohnehin der Reihe nach; `serial` waere hier
// schaedlich, weil ein Fehlschlag alle folgenden Nachweise verschlucken wuerde
// statt sie zu zeigen.

test.beforeEach(({ baseURL }) => {
	assertNotProdBaseURL(baseURL ?? '');
});

// ===========================================================================
// AC-8 — die neue Version meldet sich, uebernimmt aber nichts
// ===========================================================================

test('AC-8: neue Version meldet sich, ohne die Kontrolle zu uebernehmen', async ({ page }) => {
	await activateServiceWorker(page);
	const vorher = await controllingScriptUrl(page);
	expect(vorher).toBeTruthy();

	await triggerServiceWorkerUpdate(page);

	await expect(page.getByText('Neue Version verfügbar')).toBeVisible({ timeout: 20_000 });
	expect(
		await controllingScriptUrl(page),
		'die neue Version hat die Kontrolle ungefragt uebernommen'
	).toBe(vorher);
});

// ===========================================================================
// AC-9 — Antippen uebernimmt und laedt GENAU EINMAL neu
// ===========================================================================

test('AC-9: Antippen uebernimmt die neue Version und laedt genau einmal neu', async ({ page }) => {
	// Zaehlt jeden Dokument-Start in diesem Tab (ueberlebt das Neuladen).
	await page.addInitScript(() => {
		const n = Number(sessionStorage.getItem('gz-e2e-loads') ?? '0') + 1;
		sessionStorage.setItem('gz-e2e-loads', String(n));
	});

	await activateServiceWorker(page);
	const alteSkriptUrl = await controllingScriptUrl(page);
	const ladungenVorher = Number(
		await page.evaluate(() => sessionStorage.getItem('gz-e2e-loads'))
	);

	await triggerServiceWorkerUpdate(page);
	await expect(page.getByText('Neue Version verfügbar')).toBeVisible({ timeout: 20_000 });

	await page.getByRole('button', { name: 'Jetzt aktualisieren' }).click();

	await page.waitForFunction(
		(alt) => navigator.serviceWorker.controller?.scriptURL !== alt,
		alteSkriptUrl,
		{ timeout: 30_000 }
	);

	await expect
		.poll(
			async () => Number(await page.evaluate(() => sessionStorage.getItem('gz-e2e-loads'))),
			{ timeout: 20_000 }
		)
		.toBe(ladungenVorher + 1);

	// Nachlauf: eine Neulade-Schleife wuerde sich hier zeigen.
	await page.waitForTimeout(3_000);
	expect(
		Number(await page.evaluate(() => sessionStorage.getItem('gz-e2e-loads'))),
		'die Seite hat mehr als einmal neu geladen'
	).toBe(ladungenVorher + 1);
});

// ===========================================================================
// AC-10 — ohne Antippen bleibt die installierte Version aktiv
// ===========================================================================

test('AC-10: ohne Antippen bleibt die installierte Version aktiv', async ({ page }) => {
	await activateServiceWorker(page);
	const alteSkriptUrl = await controllingScriptUrl(page);

	await triggerServiceWorkerUpdate(page);
	await expect(page.getByText('Neue Version verfügbar')).toBeVisible({ timeout: 20_000 });

	// Weiterarbeiten, ohne den Hinweis anzutippen.
	await page.goto('/trips');
	await page.waitForLoadState('networkidle');
	await page.waitForTimeout(2_000);

	expect(
		await controllingScriptUrl(page),
		'die Kontrolle ist ohne Zutun des Nutzers gewechselt'
	).toBe(alteSkriptUrl);
	expect(
		await page.evaluate(async () => !!(await navigator.serviceWorker.getRegistration())?.waiting),
		'die neue Version wartet nicht mehr — sie wurde ungefragt umgeschaltet'
	).toBe(true);
});

// ===========================================================================
// AC-11 — beide Abmelde-Wege raeumen Speicher und Worker
// ===========================================================================

test('AC-11: Abmelden ueber die Seitenleiste raeumt Speicher und Worker', async ({ page }) => {
	await activateServiceWorker(page);
	expect((await readCacheEntries(page)).length).toBeGreaterThan(0);

	const sidebar = page.getByTestId('desktop-sidebar');
	await sidebar.locator('button').last().click(); // Nutzer-Menue aufklappen
	await sidebar.locator('form[action="/logout"] button[type="submit"]').click();
	await page.waitForURL(/\/login/);

	await expect
		.poll(() => storageAndRegistrationCount(page), { timeout: 20_000 })
		.toEqual({ caches: 0, registrations: 0 });
});

test('AC-11: "Auf allen Geraeten abmelden" raeumt Speicher und Worker', async ({ page }) => {
	await activateServiceWorker(page, '/account');
	expect((await readCacheEntries(page)).length).toBeGreaterThan(0);

	await page.getByRole('button', { name: 'Auf allen Geräten abmelden' }).click();
	await page.getByRole('dialog').getByRole('button', { name: 'Abmelden', exact: true }).click();
	await page.waitForURL(/\/login/);

	await expect
		.poll(() => storageAndRegistrationCount(page), { timeout: 20_000 })
		.toEqual({ caches: 0, registrations: 0 });
});

// "Auf allen Geraeten abmelden" beendet AUCH die Anmeldung, die
// global.setup.ts in playwright/.auth/admin.json abgelegt hat. Ohne
// Reparatur liefen alle spaeter startenden Specs in den Auth-Guard.
// `baseURL` ist test-scoped und in afterAll nicht verfuegbar -- darum hier
// derselbe lokale Vorschau-Port wie in playwright.config.ts.
const LOKALE_BASIS = process.env.PLAYWRIGHT_BASE_URL ?? 'http://localhost:4173';

test.afterAll(async ({ browser }) => {
	if (!fs.existsSync(AUTH_STATE)) return;
	assertNotProdBaseURL(LOKALE_BASIS);
	const context = await browser.newContext({ baseURL: LOKALE_BASIS, serviceWorkers: 'block' });
	try {
		const page = await context.newPage();
		await page.goto('/login');
		await page.fill('input[name="username"]', process.env.E2E_USER ?? 'admin');
		await page.fill('input[name="password"]', process.env.E2E_PASS ?? 'test1234');
		await page.click('button[type="submit"]');
		await page.waitForURL('/');
		await context.storageState({ path: AUTH_STATE });
	} finally {
		await context.close();
	}
});

// ===========================================================================
// AC-12 — Gegenprobe: die Anmeldeseite allein raeumt NICHT
// ===========================================================================

test('AC-12: Anmeldeseite ohne vorheriges Abmelden laesst Speicher und Worker unangetastet', async ({
	page
}) => {
	await activateServiceWorker(page);
	const vorher = (await readCacheEntries(page)).map((e) => e.url).sort();
	expect(vorher.length).toBeGreaterThan(0);

	// Direkter Aufruf der Anmeldeseite — wie bei abgelaufener Sitzung oder
	// schlichtem Aufruf. Kein Abmelde-Vorgang.
	await page.goto('/login');
	await expect(page.locator('input[name="username"]')).toBeVisible();
	await page.waitForTimeout(3_000);

	const nachher = (await readCacheEntries(page)).map((e) => e.url).sort();
	expect(
		nachher,
		'die Anmeldeseite hat bedingungslos geraeumt — das zerstoert die Offline-Faehigkeit'
	).toEqual(vorher);
	expect(
		await page.evaluate(async () => (await navigator.serviceWorker.getRegistrations()).length),
		'die Worker-Registrierung wurde ohne Abmelde-Vorgang entfernt'
	).toBeGreaterThan(0);
});

// ===========================================================================
// AC-15 — iOS-Installationshinweis: einmalig, nie im Startbildschirm-Betrieb
// ===========================================================================

const IOS_SAFARI_UA =
	'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 ' +
	'(KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1';

async function iosKontext(
	browser: import('@playwright/test').Browser,
	baseURL: string | undefined,
	startbildschirm: boolean
): Promise<{ page: Page; close: () => Promise<void> }> {
	const context = await browser.newContext({
		baseURL,
		storageState: AUTH_STATE,
		serviceWorkers: 'allow',
		userAgent: IOS_SAFARI_UA,
		viewport: { width: 390, height: 844 }
	});
	if (startbildschirm) {
		// So meldet sich eine vom Startbildschirm gestartete App unter iOS:
		// `navigator.standalone` ist true, und `(display-mode: standalone)` greift.
		await context.addInitScript(() => {
			Object.defineProperty(navigator, 'standalone', { value: true, configurable: true });
			const echtes = window.matchMedia.bind(window);
			window.matchMedia = (query: string) =>
				query.includes('display-mode: standalone')
					? ({
							matches: true,
							media: query,
							onchange: null,
							addListener: () => {},
							removeListener: () => {},
							addEventListener: () => {},
							removeEventListener: () => {},
							dispatchEvent: () => false
						} as MediaQueryList)
					: echtes(query);
		});
	}
	const page = await context.newPage();
	return { page, close: () => context.close() };
}

test('AC-15: der iOS-Hinweis erscheint und kehrt nach dem Schliessen nicht wieder', async ({
	browser,
	baseURL
}) => {
	const { page, close } = await iosKontext(browser, baseURL, false);
	try {
		await page.goto('/');
		const hinweis = page.getByTestId('ios-install-hint');
		await expect(hinweis).toBeVisible({ timeout: 15_000 });
		await expect(hinweis).toContainText('Auf den Startbildschirm legen');

		await hinweis.getByRole('button', { name: 'Schließen' }).click();
		await expect(hinweis).toBeHidden();

		await page.goto('/trips');
		await page.waitForLoadState('networkidle');
		await expect(
			page.getByTestId('ios-install-hint'),
			'der geschlossene Hinweis ist wiedergekommen'
		).toHaveCount(0);
	} finally {
		await close();
	}
});

test('AC-15: im Startbildschirm-Betrieb erscheint der Hinweis gar nicht', async ({
	browser,
	baseURL
}) => {
	const { page, close } = await iosKontext(browser, baseURL, true);
	try {
		await page.goto('/');
		await page.waitForLoadState('networkidle');
		await page.waitForTimeout(2_000);
		await expect(
			page.getByTestId('ios-install-hint'),
			'die App laeuft bereits vom Startbildschirm — der Installationshinweis ist sinnlos'
		).toHaveCount(0);
	} finally {
		await close();
	}
});

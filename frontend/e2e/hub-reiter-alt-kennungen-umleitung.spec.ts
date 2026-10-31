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
	// getByRole überspringt verborgene Elemente (Muster hub-tab-bar).
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

// Issue #1743 (docs/specs/modules/feat_1743_reiter_aufraeumen.md): die Reiter
// „Versand" und „Vorschau" sind aufgeloest. Alt-Links fuehren an den neuen Ort:
// ?tab=versand|briefings → ?tab=wetter-metriken#versand (Abschnitt im Blick),
// ?tab=vorschau|preview → ?tab=uebersicht.
const HUBS = [
	{
		art: 'Trip',
		pfad: async (page: Page) => `/trips/${(await neuerTrip(page)).id}`,
		prefix: 'trip-detail'
	},
	{
		art: 'Vergleich',
		pfad: async (page: Page) => `/compare/${await neuerVergleich(page)}`,
		prefix: 'compare-detail'
	}
] as const;

// #1743 F002: Der Wetter-Metriken-Inhalt OBERHALB des Versand-Abschnitts lädt nach
// dem ersten Sprung nach und schob den Abschnitt aus dem Blick. Ein einmaliges
// toBeInViewport greift im kurzen Fenster davor (falsches Grün) — darum werden die
// Katalog-Abrufe künstlich verzögert (Rennen erzwungen, unabhängig von der
// Ladegeschwindigkeit) und erst der ENDZUSTAND geprüft.
const KATALOG = /\/api\/(metrics|sms-symbols|templates|metric-presets)$/;
const KATALOG_VERZUG_MS = 1_500;

async function katalogVerzoegern(page: Page): Promise<void> {
	await page.route(
		(url) => KATALOG.test(url.pathname),
		async (route) => {
			await new Promise((r) => setTimeout(r, KATALOG_VERZUG_MS));
			await route.continue();
		}
	);
}

/** Anker: /api/sms-symbols lädt in beiden Kontexten (Trip über load(), Vergleich
 *  über den eigenen Effekt in WeatherMetricsTab.svelte). */
function katalogGeladen(page: Page) {
	return page.waitForResponse((r) => new URL(r.url()).pathname.endsWith('/api/sms-symbols'), {
		timeout: 20_000
	});
}

/** Wartet, bis die top-Position des Elements ~2 s (8 × 250 ms) unverändert ist. */
async function positionStabil(locator: ReturnType<Page['locator']>): Promise<void> {
	let proben: number[] = [];
	await expect
		.poll(
			async () => {
				const top = await locator.evaluate((el) => Math.round(el.getBoundingClientRect().top));
				proben = [...proben, top].slice(-8);
				return proben.length === 8 && Math.max(...proben) - Math.min(...proben) <= 2;
			},
			{ message: 'Versand-Abschnitt kommt nicht zur Ruhe', intervals: [250], timeout: 20_000 }
		)
		.toBe(true);
}

for (const hub of HUBS) {
	test.describe(`#1743 ${hub.art}-Hub: Alt-Links auf Versand/Vorschau`, () => {
		for (const vp of [{ width: 1280, height: 900 }, HANDY])
		for (const alt of ['versand', 'briefings']) {
			test(`?tab=${alt} → ?tab=wetter-metriken#versand, Versand-Abschnitt bleibt im Blick (${vp.width}x${vp.height})`, async ({ page }) => {
				await page.setViewportSize(vp);
				const pfad = await hub.pfad(page);
				await katalogVerzoegern(page);
				const geladen = katalogGeladen(page);
				await page.goto(`${pfad}?tab=${alt}`);

				await expect(
					page.locator(`[data-testid="${hub.prefix}-panel-wetter-metriken"]:visible`).first()
				).toBeVisible({ timeout: 15_000 });
				await expect(
					page.locator(`[data-testid="${hub.prefix}-tab-wetter-metriken"]:visible`).first()
				).toHaveAttribute('aria-selected', 'true');
				await expect
					.poll(() => {
						const u = new URL(page.url());
						return `${u.searchParams.get('tab')}${u.hash}`;
					})
					.toBe('wetter-metriken#versand');
				const abschnitt = page.locator('[data-testid="versand-abschnitt"]:visible').first();
				await expect(abschnitt).toBeVisible({ timeout: 15_000 });
				await geladen;
				await positionStabil(abschnitt);
				await expect(abschnitt).toBeInViewport({ timeout: 1_000 });
				await expect(page.locator(`[data-testid="${hub.prefix}-panel-uebersicht"]`)).toHaveCount(0);
			});
		}

		for (const alt of ['vorschau', 'preview']) {
			test(`?tab=${alt} → ?tab=uebersicht`, async ({ page }) => {
				const pfad = await hub.pfad(page);
				await page.goto(`${pfad}?tab=${alt}`);

				await expect(
					page.locator(`[data-testid="${hub.prefix}-panel-uebersicht"]:visible`).first()
				).toBeVisible({ timeout: 15_000 });
				await expect.poll(() => tabParam(page)).toBe('uebersicht');
			});
		}

		// #2347 S4 (feat_2347_s4_paritaets_e2e.md AC-5): Alt compare-flow-navigation
		// Z. 675-700 und compare-layout-tab-dissolution AC-3 — der aufgelöste Reiter
		// „Layout" (LEGACY.layout in subscriptionTabs.ts) führt in Wetter-Metriken.
		test('?tab=layout → ?tab=wetter-metriken, URL bereinigt, kein Layout-Panel', async ({ page }) => {
			const pfad = await hub.pfad(page);
			// Rumpf-Abgleich compare-layout-tab-dissolution AC-3: Umleitung ohne Fehlermeldung.
			const seitenfehler: string[] = [];
			page.on('pageerror', (err) => seitenfehler.push(String(err)));
			await page.goto(`${pfad}?tab=layout`);

			await expect(
				page.locator(`[data-testid="${hub.prefix}-panel-wetter-metriken"]:visible`).first()
			).toBeVisible({ timeout: 15_000 });
			await expect(
				page.locator(`[data-testid="${hub.prefix}-tab-wetter-metriken"]:visible`).first()
			).toHaveAttribute('aria-selected', 'true');
			await expect.poll(() => tabParam(page)).toBe('wetter-metriken');
			await expect(page.locator(`[data-testid="${hub.prefix}-panel-layout"]`)).toHaveCount(0);
			await expect(page.locator(`[data-testid="${hub.prefix}-panel-uebersicht"]`)).toHaveCount(0);
			expect(seitenfehler, '?tab=layout: Umleitung mit pageerror').toEqual([]);
		});
	});
}

test.describe('AC-10: Bestandsfehler der Schnellaktionen', () => {
	test('Trip-Liste (Handy): „Wetter-Metriken" öffnet den Reiter Wetter-Metriken', async ({ page }) => {
		// Datierte Etappe Pflicht: ein Trip ohne Etappen ist seit #2278 ein Entwurf, dessen
		// Menü nur „Setup fortsetzen"/„Löschen" anbietet (subscriptionActions.ts, draft).
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
		await page.setViewportSize(HANDY);
		await page.goto('/trips');

		// Issue #2278: geteilte SubscriptionCard + SubscriptionActionSheet
		await page.getByTestId(`subscription-card-menu-${id}`).click();
		await page.getByTestId('subscription-action-weather').click();

		await expect(page).toHaveURL(new RegExp(`/trips/${id}\\?tab=wetter-metriken$`), { timeout: 15_000 });
		await expect(page.getByTestId('trip-detail-panel-wetter-metriken')).toBeVisible({ timeout: 15_000 });
	});

	// Issue #1743: die Schnellaktion „Vorschau prüfen" ist entfallen (kein Reiter
	// Vorschau mehr). Die Zusicherung „Schnellaktion öffnet ihr Ziel, nicht die
	// Übersicht" bleibt — am „Briefing-Zeitplan" → Wetter-Metriken, Abschnitt #versand.
	test('Startseite (Vergleich-Modus): „Briefing-Zeitplan" öffnet den Versand-Abschnitt, nicht die Übersicht', async ({
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
			// #1743 F002: Endzustand prüfen, Nachladen oberhalb erzwingen (s. katalogVerzoegern).
			await katalogVerzoegern(gast);
			const geladen = katalogGeladen(gast);
			await gast.locator('a:visible', { hasText: 'Briefing-Zeitplan' }).first().click();

			await expect(gast).toHaveURL(new RegExp(`/compare/${presetId}\\?tab=wetter-metriken#versand$`), {
				timeout: 15_000
			});
			await expect(
				gast.locator('[data-testid="compare-detail-panel-wetter-metriken"]:visible').first()
			).toBeVisible({ timeout: 15_000 });
			const abschnitt = gast.locator('[data-testid="versand-abschnitt"]:visible').first();
			await expect(abschnitt).toBeVisible({ timeout: 15_000 });
			await geladen;
			await positionStabil(abschnitt);
			await expect(abschnitt).toBeInViewport({ timeout: 1_000 });
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
	// Issue #1743: fuenf Reiter — kein `versand`/`vorschau` mehr.
	const SCHWANZ = ['wetter-metriken', 'wertebereiche', 'alarme'];

	test('Trip: Reihenfolge uebersicht · etappen · … · alarme, Antippen öffnet Wertebereiche', async ({
		page
	}) => {
		const { id } = await neuerTrip(page);
		await page.setViewportSize(HANDY);
		await page.goto(`/trips/${id}`);
		await expect(page.getByTestId('trip-detail-tab-list')).toBeVisible({ timeout: 15_000 });

		expect(await mobileReiter(page, 'trip-detail-tab-')).toEqual(['uebersicht', 'etappen', ...SCHWANZ]);

		// dispatchEvent statt click: Scroll-Snap + Fade-Maske des Bands stören
		// Playwrights Actionability-Scroll (Muster der früheren Trip-Reiterleisten-Spec, heute hub-tab-bar.spec.ts).
		await page.getByTestId('trip-detail-tab-wertebereiche').dispatchEvent('click');
		await expect(page.getByTestId('trip-detail-panel-wertebereiche')).toBeVisible();
		await expect.poll(() => tabParam(page)).toBe('wertebereiche');
	});

	test('Vergleich: Reihenfolge uebersicht · orte · … · alarme, Antippen öffnet Wertebereiche', async ({
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

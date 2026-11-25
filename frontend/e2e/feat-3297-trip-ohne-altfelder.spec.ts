// E2E — Issue #3297 (+ #3020, Epic #3122): Trip-Pfad ohne Altfelder.
// Spec docs/specs/modules/feat_3297_trip_pfad_ohne_altfelder.md (AC-1, AC-2, AC-3, AC-5, AC-9).
// Echte Go- und Python-Server (Staging in /e2e-verify), keine gemockten Antworten; geprüft wird der
// Request-Body, den der Browser wirklich sendet, und die Startseite eines frischen Nutzers.
//
//   AW-1 (AC-1/AC-9) Trip anlegen (durch Wetter und Zustellung geklickt): der eine POST /api/trips trägt
//                    keinen der sechs Altschlüssel (auch nicht leer); der Hub des neuen Trips öffnet Wetter und
//                    Zustellung mit denselben Flächen (Karte „Was steht wo“, Zustellungs-Tabelle).
//   AW-2 (AC-2)      Trip „Mit Standardwerten“ anlegen: POST ohne Altschlüssel.
//   AW-3 (AC-3)      Bestandstrip mit Altfeldern: Reiter Wetter („−“ an einer Zeile) und Reiter Zustellung
//                    (Abend-Schalter) speichern; kein PUT trägt einen Altschlüssel; Werte bleiben nach Neuladen.
//   AW-4 (AC-5)      Frischer Nutzer, ein geplanter Trip mit Tabelle (`placements.rows`): Startseite zeigt
//                    „Layout je Kanal“ als erledigt.
//
// RED heute: AW-1/AW-2 (POST trägt multi_day_trend_reports und show_outlook), AW-3 (der Reiter Wetter
// reicht show_outlook/multi_day_trend_reports der Bestands-report_config im PUT durch), AW-4 (Startseite
// wertet placements.rows nicht aus).
//
//   cd frontend && npx playwright test e2e/feat-3297-trip-ohne-altfelder.spec.ts --workers=1 --trace off

import { test, expect, request as pwRequest, type Browser, type Page, type Request } from '@playwright/test';
import { ANLEGE_SEL, anlegenPflicht, cleanupTracked, E2E_TEST_PREFIX, registerForCleanup } from './helpers';
import { wegwerfPasswort } from './stagingZugang';
import { DESKTOP, WT, oeffneWetter } from './s3a2794-teil3.helpers';
import { ZT, oeffneZustellung, schalte } from './s3b2795-zustellung.helpers';
import { seedAbo, stand } from './was-steht-wo.helpers';

type Json = Record<string, any>; // eslint-disable-line @typescript-eslint/no-explicit-any

const ALTSCHLUESSEL = [
	'channel_layouts',
	'channel_layouts_per_report',
	'outlook_metrics',
	'outlook_metric_formats',
	'show_outlook',
	'multi_day_trend_reports'
];

/** Fundstellen der Altschlüssel in beliebiger Tiefe (gefüllt oder leer). */
function altschluesselFunde(wert: unknown, pfad = ''): string[] {
	if (Array.isArray(wert)) return wert.flatMap((v, i) => altschluesselFunde(v, `${pfad}[${i}]`));
	if (!wert || typeof wert !== 'object') return [];
	const funde: string[] = [];
	for (const [k, v] of Object.entries(wert as Json)) {
		const hier = pfad ? `${pfad}.${k}` : k;
		if (ALTSCHLUESSEL.includes(k)) funde.push(hier);
		funde.push(...altschluesselFunde(v, hier));
	}
	return funde;
}

const einName = (tag: string) => `${E2E_TEST_PREFIX}AW-${tag}-${Date.now()}`;

test.afterEach(async ({ page }) => {
	await cleanupTracked(page.request);
});

/** Mitschnitt aller schreibenden API-Aufrufe (Methode, Pfad, gesendeter Rumpf). */
type Aufruf = { methode: string; pfad: string; rumpf: Json | null };
function mitschneiden(page: Page): Aufruf[] {
	const alle: Aufruf[] = [];
	page.on('request', (r: Request) => {
		const url = new URL(r.url());
		if (!url.pathname.startsWith('/api/') || !['POST', 'PUT', 'PATCH'].includes(r.method())) return;
		let rumpf: Json | null = null;
		try {
			rumpf = (r.postDataJSON() ?? null) as Json | null;
		} catch {
			rumpf = null;
		}
		alle.push({ methode: r.method(), pfad: url.pathname, rumpf });
	});
	return alle;
}

async function anlegePost(page: Page, klick: () => Promise<void>): Promise<{ id: string; rumpf: Json }> {
	const antwort = page.waitForResponse((r) => r.request().method() === 'POST' && new URL(r.url()).pathname === '/api/trips', { timeout: 30_000 });
	await klick();
	const r = await antwort;
	expect([200, 201], `Anlege-POST HTTP ${r.status()}`).toContain(r.status());
	const id = ((await r.json()) as { id: string }).id;
	registerForCleanup('trip', id);
	return { id, rumpf: r.request().postDataJSON() as Json };
}

async function schritt(page: Page, id: string): Promise<void> {
	await ANLEGE_SEL.route.reiter(page, id, false).click();
	await expect.poll(async () => (await ANLEGE_SEL.route.zustand(ANLEGE_SEL.route.reiter(page, id, false))).aktiv, { timeout: 10_000 }).toBe(true);
}

test.describe('#3297 Trip-Pfad ohne Altfelder', () => {
	test('AW-1 (AC-1/AC-9): Anlege-POST ohne Altschlüssel; Hub zeigt dieselben Flächen', async ({ page }) => {
		await anlegenPflicht(page, 'route', { name: einName('1'), viewport: DESKTOP });
		await schritt(page, 'wetter');
		await expect(page.locator('.tn-desktop [data-testid="was-steht-wo"]'), 'AC-9: Karte „Was steht wo“ im Anlegen').toBeVisible({ timeout: 20_000 });
		await schritt(page, 'zustellung');
		const { id, rumpf } = await anlegePost(page, () => ANLEGE_SEL.route.abschluss(page, false).click());
		expect(altschluesselFunde(rumpf), 'AC-1: Altschlüssel im Anlege-POST').toEqual([]);

		// AC-9: dieselben Flächen im Hub des neuen Trips.
		const wetter = await oeffneWetter(page, 'route', id);
		await expect(wetter.getByTestId('was-steht-wo'), 'AC-9: Karte „Was steht wo“ im Hub').toBeVisible({ timeout: 20_000 });
		const zustellung = await oeffneZustellung(page, 'route', id);
		await expect(zustellung.getByTestId(ZT.tabelle), 'AC-9: Zustellungs-Tabelle im Hub').toBeVisible();
	});

	test('AW-2 (AC-2): „Mit Standardwerten“ anlegen — POST ohne Altschlüssel', async ({ page }) => {
		await anlegenPflicht(page, 'route', { name: einName('2'), viewport: DESKTOP });
		const knopf = ANLEGE_SEL.route.standardwerte(page);
		await expect(knopf).toBeEnabled({ timeout: 15_000 });
		const { rumpf } = await anlegePost(page, () => knopf.click());
		expect(altschluesselFunde(rumpf), 'AC-2: Altschlüssel im Standardwerte-POST').toEqual([]);
		expect(rumpf.report_config?.morning_time, 'AC-2: Standard-Versandeinstellungen fehlen').toBeTruthy();
	});

	test('AW-3 (AC-3/AC-9): Bestandstrip mit Altfeldern — Reiter-PUTs ohne Altschlüssel, Werte bleiben', async ({ page }) => {
		await page.setViewportSize(DESKTOP);
		const abo = await seedAbo(page.request, 'route', {
			oben: {
				report_config: {
					enabled: true,
					morning_enabled: true,
					evening_enabled: true,
					morning_time: '06:00:00',
					evening_time: '18:00:00',
					show_outlook: true,
					multi_day_trend_reports: ['evening']
				}
			},
			dc: {
				channel_layouts: { email: ['wind'] },
				channel_layouts_per_report: { morning: { email: ['wind'] } },
				outlook_metrics: ['temperature'],
				outlook_metric_formats: { temperature: true }
			}
		});
		try {
			const vorher = await stand(page.request, 'route', abo.id);
			test.info().annotations.push({
				type: 'Messaufbau',
				description: `Altfelder im gespeicherten Bestand: ${JSON.stringify(altschluesselFunde(vorher))}`
			});
			const aufrufe = mitschneiden(page);
			const putsDesTrips = () => aufrufe.filter((a) => a.methode === 'PUT' && a.pfad.startsWith(`/api/trips/${abo.id}`));

			// Reiter Wetter: „−“ an Böen löst den Speichervorgang des Reiters aus (weather-config + Trip-PUT).
			const reiter = await oeffneWetter(page, 'route', abo.id);
			const tripPut = page.waitForResponse((r) => r.request().method() === 'PUT' && new URL(r.url()).pathname === `/api/trips/${abo.id}`, { timeout: 20_000 });
			await reiter.getByTestId(WT.entfernen('gust')).click();
			expect((await tripPut).status(), 'PUT Reiter Wetter').toBe(200);

			// Reiter Zustellung: Abend-Briefing aus.
			const z = await oeffneZustellung(page, 'route', abo.id);
			const zPut = page.waitForResponse((r) => r.request().method() === 'PUT' && new URL(r.url()).pathname === `/api/trips/${abo.id}`, { timeout: 20_000 });
			await schalte(z.getByTestId(ZT.schalter('abend')), false);
			expect((await zPut).status(), 'PUT Reiter Zustellung').toBe(200);

			expect(putsDesTrips().length, 'Messaufbau: Speicher-PUTs mitgeschnitten').toBeGreaterThanOrEqual(2);
			for (const a of putsDesTrips()) {
				expect(altschluesselFunde(a.rumpf), `AC-3: Altschlüssel im PUT ${a.pfad}`).toEqual([]);
			}

			// AC-9: nach Neuladen stehen die Werte (Abend aus, Böen nicht mehr in der Grundauswahl).
			const nachher = await stand(page.request, 'route', abo.id);
			expect(nachher.report_config.evening_enabled, 'AC-9: Abend-Schalter gespeichert').toBe(false);
			expect(nachher.report_config.morning_time, 'AC-3: übriges Bestandsfeld erhalten').toBe('06:00:00');
			const z2 = await oeffneZustellung(page, 'route', abo.id);
			await expect(z2.getByTestId(ZT.schalter('abend')), 'AC-9: Abend nach Neuladen aus').toHaveAttribute('aria-checked', 'false');
		} finally {
			await abo.aufraeumen();
		}
	});

	test('AW-4 (AC-5): Startseite zeigt „Layout je Kanal“ erledigt für einen Trip mit Tabelle', async ({ page, browser }) => {
		const b = await frischerNutzer(browser, page, '10.32.97.14');
		try {
			const morgen = new Date(Date.now() + 2 * 86_400_000).toISOString().slice(0, 10);
			const name = einName('4');
			const res = await b.seite.request.post('/api/trips', {
				data: {
					id: `e2e-gz-aw4-${Date.now()}`,
					name,
					stages: [{ id: 's1', name: 'Tag 1', date: morgen, waypoints: [{ id: 'a', name: 'a', lat: 42.0, lon: 9.0, elevation_m: 800 }, { id: 'b', name: 'b', lat: 42.04, lon: 9.0, elevation_m: 1200 }] }],
					display_config: {
						metrics: [{ metric_id: 'wind', enabled: true }],
						placements: { version: 1, rows: [{ metric_id: 'wind', places: { email: ['tabelle'] } }], outlook_reports: ['evening'] }
					}
				}
			});
			expect(res.ok(), `Messaufbau: Trip anlegen HTTP ${res.status()}`).toBeTruthy();
			const gespeichert = (await (await b.seite.request.get(`/api/trips/${((await res.json()) as { id: string }).id}`)).json()) as Json;
			expect((gespeichert.display_config?.placements?.rows ?? []).length, 'Messaufbau: Trip trägt placements.rows').toBeGreaterThan(0);
			expect(gespeichert.display_config?.channel_layouts, 'Messaufbau: ohne channel_layouts').toBeUndefined();
			expect(gespeichert.display_config?.preset_name, 'Messaufbau: ohne preset_name').toBeUndefined();

			await b.seite.goto('/');
			const karte = b.seite.locator('div, section, article').filter({ has: b.seite.getByRole('heading', { name, exact: true }) }).last();
			await expect(karte, 'Setup-Karte des geplanten Trips fehlt').toBeVisible({ timeout: 15_000 });
			const chip = karte.locator('span').filter({ hasText: /^\s*Layout je Kanal\s*$/ }).first();
			await expect(chip).toBeVisible();
			await expect(chip.locator('svg'), 'AC-5: „Layout je Kanal“ nicht als erledigt markiert').toHaveCount(1);
		} finally {
			await b.aufraeumen();
		}
	});
});

/** Frisch registrierter, angemeldeter Nutzer ohne Trips (Muster trip-anlegen-zustellung-3332 zweitNutzer). */
async function frischerNutzer(browser: Browser, admin: Page, ip: string): Promise<{ seite: Page; aufraeumen: () => Promise<void> }> {
	const basis = new URL((await admin.goto('/'))!.url()).origin;
	const name = `e2eaw3297${Date.now()}`;
	const passwort = wegwerfPasswort();
	const gast = await pwRequest.newContext({ baseURL: basis, storageState: { cookies: [], origins: [] }, extraHTTPHeaders: { 'X-Real-IP': ip } });
	const reg = await gast.post('/api/auth/register', { data: { username: name, password: passwort, email: `${name}@example.com`, language: 'de' } });
	expect([200, 201]).toContain(reg.status());
	const { id: nutzer } = (await reg.json()) as { id: string };
	const tok = (await (await admin.request.post('/api/auth/verify-email/staging-token', { data: { username: nutzer } })).json()) as { token: string };
	expect((await gast.post('/api/auth/verify-email', { data: { user: nutzer, token: tok.token } })).ok()).toBeTruthy();
	await gast.dispose();
	const ctx = await browser.newContext({ storageState: { cookies: [], origins: [] }, serviceWorkers: 'block', locale: 'de-DE', viewport: DESKTOP });
	const seite = await ctx.newPage();
	await seite.goto('/login');
	await seite.fill('input[name="username"]', `${name}@example.com`);
	await seite.fill('input[name="password"]', passwort);
	await seite.click('form[action="?/login"] button[type="submit"]');
	await seite.waitForURL((u) => u.pathname === '/', { timeout: 15_000 });
	return {
		seite,
		aufraeumen: async () => {
			await seite.request.post('/api/auth/account/delete', { data: { password: passwort } }).catch(() => {});
			await ctx.close();
		}
	};
}

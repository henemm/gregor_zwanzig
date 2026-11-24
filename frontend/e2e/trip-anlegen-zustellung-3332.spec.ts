// E2E — Issue #3332 (Teil D1 von #3307, Epic #3122): Reiter „Zustellung“ beim Trip-Anlegen.
// Spec docs/specs/modules/feat_3332_zustellung_anlegen_trip.md, Test Plan Nr. 10 bis 12
// (AC-1, AC-2, AC-3, AC-5, AC-6, AC-7, AC-8, AC-9, AC-12). Echte Go- und Python-Server (Staging in /e2e-verify),
// keine gemockten Antworten. Einzige Ausnahme wie in hub-anlegen-ablauf AN-6: die PROFIL-LESUNG im Browser
// des Prüfkontos wird um eine Test-Chat-ID ergänzt (kein Profil wird verändert), damit Telegram als verbunden
// gilt und die Dringlichkeit bedienbar ist.
//
//   TZ-1 (AC-1/2/3/5/8/9) Zeiten, Kanäle, Dringlichkeit HIGH, Stille, Cooldown im Reiter setzen; genau ein POST
//                         /api/trips mit diesen Werten, kein PUT, kein Schreibaufruf vorher; Alt-Panel und Mail-Inhalt-
//                         Karte nicht da, alte Stufen-Wahl im Reiter Alarme nicht da; Hub-Reiter Zustellung des neuen
//                         Trips zeigt denselben Stand.
//   TZ-2 (AC-7)           rasterfremde Uhrzeit 06:50: Meldung, Anlegen gelingt (kein 400), POST trägt die letzte gültige.
//   TZ-3 (AC-1/AC-6)      Mobil und Desktop: Reiter da, Alt-Panel weg; Stand überlebt Ansichts- und Schrittwechsel und
//                         steht im POST.
//   TZ-4 (AC-12)          Zwei Nutzer: A (Telegram verbunden) sieht die Dringlichkeit, B (ohne Telegram) nicht; jeder
//                         Trip nur beim eigenen Nutzer, B liest den Trip von A nicht.
//
//   cd frontend && npx playwright test e2e/trip-anlegen-zustellung-3332.spec.ts --workers=1 --trace off

import { test, expect, request as pwRequest, type Browser, type Locator, type Page, type Request } from '@playwright/test';
import { ANLEGE_SEL, anlegenPflicht, cleanupTracked, E2E_TEST_PREFIX, hubApiPath, tippeUhrzeit } from './helpers';
import { wegwerfPasswort } from './stagingZugang';
import { DESKTOP, MOBIL, ZT, angezeigteZeit, cooldownFeld, oeffneZustellung, schalte } from './s3b2795-zustellung.helpers';

type Json = Record<string, any>; // eslint-disable-line @typescript-eslint/no-explicit-any
const einName = (tag: string) => `${E2E_TEST_PREFIX}TZ-${tag}-${Date.now()}`;
const VORSCHAU_PFAD = '/api/briefings/placements/vorschau';

test.afterEach(async ({ page }) => {
	await cleanupTracked(page.request);
});

/** Nur die Profil-Lesung im Browser: Telegram gilt als verbunden (nichts am Konto wird verändert). */
async function telegramVerbunden(page: Page): Promise<void> {
	await page.route('**/api/auth/profile', async (route) => {
		if (route.request().method() !== 'GET') return route.continue();
		const echt = await route.fetch();
		const profil = (await echt.json()) as Record<string, unknown>;
		await route.fulfill({ response: echt, json: { ...profil, telegram_chat_id: 'e2e-tz3332-chat' } });
	});
}

// ── Mitschnitt aller API-Aufrufe der Seite (Muster trip-anlegen-was-steht-wo-3305) ──
type Mitschnitt = { alle: { methode: string; pfad: string; rumpf: Json | null }[]; anlegeIds: string[] };
function mitschneiden(page: Page): Mitschnitt {
	const m: Mitschnitt = { alle: [], anlegeIds: [] };
	page.on('request', (r: Request) => {
		const url = new URL(r.url());
		if (!url.pathname.startsWith('/api/')) return;
		let rumpf: Json | null = null;
		try {
			rumpf = (r.postDataJSON() ?? null) as Json | null;
		} catch {
			rumpf = null;
		}
		m.alle.push({ methode: r.method(), pfad: url.pathname, rumpf });
	});
	page.on('response', async (r) => {
		if (r.request().method() !== 'POST' || new URL(r.url()).pathname !== '/api/trips' || !r.ok()) return;
		const id = ((await r.json().catch(() => ({}))) as { id?: string }).id;
		if (id) m.anlegeIds.push(id);
	});
	return m;
}
const anlegePosts = (m: Mitschnitt) => m.alle.filter((x) => x.methode === 'POST' && x.pfad === '/api/trips');
const schreibAufrufe = (m: Mitschnitt) =>
	m.alle.filter(
		(x) =>
			['PUT', 'PATCH', 'DELETE'].includes(x.methode) ||
			(x.methode === 'POST' && x.pfad !== VORSCHAU_PFAD && x.pfad !== '/api/trips' && !x.pfad.startsWith('/api/gpx/') && !x.pfad.startsWith('/api/locations/resolve'))
	);

// ── Anlege-Seite ─────────────────────────────────────────────────────────────
const huelle = (mobil: boolean) => (mobil ? '.tn-mobile' : '.tn-desktop');
async function schritt(page: Page, id: string, mobil = false): Promise<void> {
	await ANLEGE_SEL.route.reiter(page, id, mobil).click({ force: mobil });
	await expect.poll(async () => (await ANLEGE_SEL.route.zustand(ANLEGE_SEL.route.reiter(page, id, mobil))).aktiv, { timeout: 10_000 }).toBe(true);
}
/** Reiter Zustellung im Schritt Zustellung der Anlege-Seite, Kanal-Tabelle geladen. */
async function anlegeReiter(page: Page, mobil = false): Promise<Locator> {
	const reiter = page.locator(`${huelle(mobil)} [data-testid="${ZT.tab}"][data-context="route"]`);
	await expect(reiter, 'AC-1: Reiter Zustellung fehlt im Trip-Anlegen').toBeVisible({ timeout: 15_000 });
	await expect(reiter.getByTestId(ZT.tabelle)).toBeVisible({ timeout: 15_000 });
	return reiter;
}
async function zumSchrittZustellung(page: Page, name: string, mobil = false): Promise<Locator> {
	await anlegenPflicht(page, 'route', { name, mobil, viewport: mobil ? MOBIL : DESKTOP });
	await schritt(page, 'zustellung', mobil);
	return anlegeReiter(page, mobil);
}
async function anlegen(page: Page, m: Mitschnitt, mobil = false): Promise<{ id: string; status: number }> {
	const post = page.waitForResponse((r) => r.request().method() === 'POST' && new URL(r.url()).pathname === '/api/trips', { timeout: 30_000 });
	await ANLEGE_SEL.route.abschluss(page, mobil).click();
	const antwort = await post;
	expect([200, 201], `Anlege-POST HTTP ${antwort.status()}`).toContain(antwort.status());
	await expect.poll(() => m.anlegeIds.length).toBe(1);
	return { id: m.anlegeIds[0], status: antwort.status() };
}

/** Bedient den Reiter: Morgen 06:45, Abend aus, Telegram-Briefing an, SMS-Alarm wenn bedienbar,
 *  Telegram-Dringlichkeit „hoch“, Stille 22:30–06:15, Cooldown 45. */
async function bedienen(page: Page, reiter: Locator): Promise<void> {
	await tippeUhrzeit(page, reiter.getByTestId(ZT.zeit('morgen')), '06:45');
	await page.keyboard.press('Tab');
	expect(await angezeigteZeit(reiter.getByTestId(ZT.zeit('morgen')))).toBe('06:45');
	await schalte(reiter.getByTestId(ZT.schalter('abend')), false);
	await schalte(reiter.getByTestId(ZT.briefing('telegram')), true);
	await schalte(reiter.getByTestId(ZT.alarm('telegram')), true);
	const hoch = reiter.getByTestId(ZT.dringlichkeitOption('telegram', 'HIGH'));
	await hoch.click();
	await expect(hoch).toHaveAttribute('aria-checked', 'true');
	await schalte(reiter.getByTestId(ZT.stilleSchalter), true);
	await tippeUhrzeit(page, reiter.getByTestId(ZT.stilleVon), '22:30');
	await page.keyboard.press('Tab');
	await tippeUhrzeit(page, reiter.getByTestId(ZT.stilleBis), '06:15');
	await page.keyboard.press('Tab');
	const cd = await cooldownFeld(reiter);
	await cd.fill('45');
	await cd.blur();
}

test.describe('#3332 Reiter Zustellung beim Trip-Anlegen', () => {
	test('TZ-1 (AC-1/2/3/5/8/9): ein POST mit Zeiten, Kanälen, Dringlichkeit, Stille, Cooldown; Hub zeigt denselben Stand', async ({ page }) => {
		await telegramVerbunden(page);
		const m = mitschneiden(page);
		const reiter = await zumSchrittZustellung(page, einName('1'));
		const tn = page.locator('.tn-desktop');
		await expect(tn.getByTestId('versand-abschnitt'), 'AC-1: Alt-Panel noch im Trip-Anlegen').toHaveCount(0);
		await expect(tn.getByTestId('report-mail-content'), 'AC-1: Mail-Inhalt-Karte noch im Trip-Anlegen').toHaveCount(0);
		for (const s of ['channels', 'cooldown', 'quiet-hours'])
			await expect(tn.getByTestId(`alarme-section-${s}`), `AC-9: Abschnitt ${s} im Reiter Alarme hat eine zweite Bedienstelle`).toHaveCount(0);
		await expect(tn.getByTestId('alarme-section-official-warnings'), 'AC-9: amtliche Warnungen bleiben im Reiter Alarme').toHaveCount(1);

		await bedienen(page, reiter);
		expect(schreibAufrufe(m), 'AC-5: Schreibaufruf vor dem Anlegen').toEqual([]);

		const { id } = await anlegen(page, m);
		const posts = anlegePosts(m);
		expect(posts, 'AC-5: genau ein Anlege-POST').toHaveLength(1);
		expect(schreibAufrufe(m), 'AC-5: kein PUT/Schreibaufruf').toEqual([]);
		const r = posts[0].rumpf!;
		expect(r.report_config?.morning_time, 'AC-2').toBe('06:45:00');
		expect(r.report_config?.morning_enabled, 'AC-2').toBe(true);
		expect(r.report_config?.evening_enabled, 'AC-2').toBe(false);
		expect(r.report_config?.send_email, 'AC-2').toBe(true);
		expect(r.report_config?.send_telegram, 'AC-2').toBe(true);
		expect(r.report_config?.multi_day_trend_reports, 'Ausblick-Vorbelegung bleibt im POST').toBeDefined();
		expect(r.alert_channels?.telegram, 'AC-3').toBe(true);
		expect(r.alert_channel_thresholds?.telegram, 'AC-3').toBe('HIGH');
		expect(r.alert_quiet_from, 'AC-2').toBe('22:30');
		expect(r.alert_quiet_to, 'AC-2').toBe('06:15');
		expect(r.alert_cooldown_minutes, 'AC-3').toBe(45);

		// AC-8: Rückweg in den Hub-Reiter Zustellung des neuen Trips.
		const hub = await oeffneZustellung(page, 'route', id);
		expect(await angezeigteZeit(hub.getByTestId(ZT.zeit('morgen'))), 'AC-8: Morgen-Zeit').toBe('06:45');
		await expect(hub.getByTestId(ZT.schalter('morgen')), 'AC-8: Morgen an').toHaveAttribute('aria-checked', 'true');
		await expect(hub.getByTestId(ZT.schalter('abend')), 'AC-8: Abend aus').toHaveAttribute('aria-checked', 'false');
		await expect(hub.getByTestId(ZT.briefing('telegram')), 'AC-8: Briefing Telegram').toHaveAttribute('aria-checked', 'true');
		await expect(hub.getByTestId(ZT.alarm('telegram')), 'AC-8: Alarm Telegram').toHaveAttribute('aria-checked', 'true');
		await expect(hub.getByTestId(ZT.dringlichkeitOption('telegram', 'HIGH')), 'AC-8: Dringlichkeit').toHaveAttribute('aria-checked', 'true');
		await expect(hub.getByTestId(ZT.stilleSchalter), 'AC-8: Stille an').toHaveAttribute('aria-checked', 'true');
		expect(await angezeigteZeit(hub.getByTestId(ZT.stilleVon)), 'AC-8: Stille von').toBe('22:30');
		expect(await angezeigteZeit(hub.getByTestId(ZT.stilleBis)), 'AC-8: Stille bis').toBe('06:15');
		await expect(await cooldownFeld(hub), 'AC-8: Cooldown').toHaveValue('45');
	});

	test('TZ-2 (AC-7): 06:50 eingegeben — Meldung, Anlegen ohne 400, POST trägt die letzte gültige Zeit', async ({ page }) => {
		const m = mitschneiden(page);
		const reiter = await zumSchrittZustellung(page, einName('2'));
		const feld = reiter.getByTestId(ZT.zeit('morgen'));
		await tippeUhrzeit(page, feld, '06:45');
		await page.keyboard.press('Tab');
		await tippeUhrzeit(page, feld, '06:50');
		await page.keyboard.press('Tab');
		await expect(reiter.getByTestId(ZT.zeitFehler('morgen')), 'Raster-Meldung fehlt').toBeVisible();
		await anlegen(page, m);
		const r = anlegePosts(m)[0].rumpf!;
		expect(r.report_config?.morning_time, 'AC-7: letzte gültige Zeit').toBe('06:45:00');
		expect(JSON.stringify(r), 'AC-7: rasterfremde Zeit im POST').not.toContain('06:50');
	});

	test('TZ-3 (AC-1/AC-6): Mobil und Desktop — Reiter statt Alt-Panel, Stand überlebt Ansichts- und Schrittwechsel', async ({ page }) => {
		await telegramVerbunden(page);
		const m = mitschneiden(page);
		const reiter = await zumSchrittZustellung(page, einName('3'));
		await tippeUhrzeit(page, reiter.getByTestId(ZT.zeit('morgen')), '06:45');
		await page.keyboard.press('Tab');
		await schalte(reiter.getByTestId(ZT.alarm('telegram')), true);
		await reiter.getByTestId(ZT.dringlichkeitOption('telegram', 'HIGH')).click();

		await page.setViewportSize(MOBIL);
		const mobil = await anlegeReiter(page, true);
		await expect(page.locator('.tn-mobile').getByTestId('versand-abschnitt'), 'AC-1 Mobil: Alt-Panel').toHaveCount(0);
		await expect(page.locator('.tn-mobile').getByTestId('report-mail-content'), 'AC-1 Mobil: Mail-Inhalt-Karte').toHaveCount(0);
		expect(await angezeigteZeit(mobil.getByTestId(ZT.zeit('morgen'))), 'AC-6: Wechsel auf Mobil verliert die Zeit').toBe('06:45');
		await expect(mobil.getByTestId(ZT.dringlichkeitOption('telegram', 'HIGH')), 'AC-6: Wechsel auf Mobil verliert die Dringlichkeit').toHaveAttribute('aria-checked', 'true');
		await schalte(mobil.getByTestId(ZT.stilleSchalter), true);

		await page.setViewportSize(DESKTOP);
		await schritt(page, 'wetter');
		await schritt(page, 'zustellung');
		const zurueck = await anlegeReiter(page);
		expect(await angezeigteZeit(zurueck.getByTestId(ZT.zeit('morgen'))), 'AC-6: Schrittwechsel verliert die Zeit').toBe('06:45');
		await expect(zurueck.getByTestId(ZT.stilleSchalter), 'AC-6: Geste auf Mobil verloren').toHaveAttribute('aria-checked', 'true');

		await anlegen(page, m);
		const r = anlegePosts(m)[0].rumpf!;
		expect(r.report_config?.morning_time).toBe('06:45:00');
		expect(r.alert_channel_thresholds?.telegram).toBe('HIGH');
		expect(r.alert_quiet_from, 'AC-6: Stille aus der Mobil-Ansicht fehlt im POST').not.toBeNull();
	});

	test('TZ-4 (AC-12): A mit Telegram sieht die Dringlichkeit, B ohne nicht; jeder Trip nur beim eigenen Nutzer', async ({ page, browser }) => {
		await telegramVerbunden(page);
		const mA = mitschneiden(page);
		const reiterA = await zumSchrittZustellung(page, einName('4A'));
		await schalte(reiterA.getByTestId(ZT.alarm('telegram')), true);
		await expect(reiterA.getByTestId(ZT.dringlichkeitOption('telegram', 'HIGH')), 'AC-12: A sieht die Dringlichkeit nicht').toBeVisible();
		const { id: idA } = await anlegen(page, mA);

		const b = await zweitNutzer(browser, page, '10.33.32.12');
		try {
			const mB = mitschneiden(b.seite);
			const reiterB = await zumSchrittZustellung(b.seite, einName('4B'));
			await expect(reiterB.getByTestId(ZT.dringlichkeitOption('telegram', 'HIGH')), 'AC-12: B sieht die Dringlichkeit ohne Telegram').toHaveCount(0);
			await expect(reiterB.getByTestId(ZT.alarmGesperrt('telegram')), 'AC-12: B — Telegram-Alarm nicht als gesperrt markiert').toBeVisible();
			const { id: idB } = await anlegen(b.seite, mB);

			const listeB = ((await (await b.seite.request.get('/api/trips')).json()) as Json[]).map((t) => t.id);
			expect(listeB, 'AC-12: Trip von A in der Liste von B').not.toContain(idA);
			expect(listeB).toContain(idB);
			expect((await b.seite.request.get(hubApiPath('route', idA))).ok(), 'AC-12: B liest den Trip von A').toBe(false);
			const listeA = ((await (await page.request.get('/api/trips')).json()) as Json[]).map((t) => t.id);
			expect(listeA, 'AC-12: Trip von B in der Liste von A').not.toContain(idB);
			expect(listeA).toContain(idA);
		} finally {
			await b.aufraeumen();
		}
	});
});

/** Zweiter, frisch registrierter und angemeldeter Nutzer in eigenem Browser-Kontext (Muster trip-anlegen-was-steht-wo-3305). */
async function zweitNutzer(browser: Browser, admin: Page, ip: string): Promise<{ seite: Page; aufraeumen: () => Promise<void> }> {
	const basis = new URL((await admin.goto('/'))!.url()).origin;
	const name = `e2etz3332${Date.now()}`;
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

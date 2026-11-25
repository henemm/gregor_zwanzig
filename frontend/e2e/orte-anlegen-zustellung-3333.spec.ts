// E2E — Issue #3333 (Teil D2 von #3307, Epic #3122): Reiter „Zustellung“ beim Ortsvergleich-Anlegen.
// Spec docs/specs/modules/feat_3333_zustellung_anlegen_orte.md, Test Plan Nr. 10 bis 12
// (AC-1, AC-2, AC-3, AC-4, AC-6, AC-7, AC-8, AC-9, AC-10, AC-11, AC-14). Pendant zu trip-anlegen-zustellung-3332.spec.ts.
// Echte Go- und Python-Server (Staging in /e2e-verify), keine gemockten Antworten. Einzige Ausnahme wie in
// #3332 TZ-1: die PROFIL-LESUNG im Browser des Prüfkontos wird um eine Test-Chat-ID ergänzt (kein Profil wird
// verändert), damit Telegram als verbunden gilt und die Dringlichkeit bedienbar ist.
//
//   OZ-1 (AC-1/2/3/4/6/9/10/11) Morgen 06:45, Abend aus, E-Mail aus, Telegram-Briefing an, Telegram-Alarm mit
//                         Dringlichkeit HIGH, Stille 22:30–06:15, Cooldown 45 im Reiter setzen; genau ein POST
//                         /api/compare/presets mit diesen Werten (send_email:false), kein PUT, kein Schreibaufruf
//                         vorher; Alt-Panel weg, Banner im Reiter; Reiter Alarme ohne Kanäle/Cooldown/Stille;
//                         Hub-Reiter Zustellung des neuen Vergleichs zeigt denselben Stand.
//   OZ-2 (AC-8)           rasterfremde Uhrzeit 06:50: Meldung, Anlegen gelingt (kein 400), POST trägt die letzte gültige.
//   OZ-3 (AC-1/AC-7)      Mobil und Desktop: Reiter da, Alt-Panel weg; Stand überlebt Ansichts- und Schrittwechsel und
//                         steht im POST.
//   OZ-4 (AC-14)          Zwei Nutzer: A (Telegram verbunden) sieht die Dringlichkeit, B (ohne Telegram) nicht; jeder
//                         Vergleich nur beim eigenen Nutzer, B liest den Vergleich von A nicht.
//
//   cd frontend && npx playwright test e2e/orte-anlegen-zustellung-3333.spec.ts --workers=1 --trace off

import { test, expect, request as pwRequest, type Browser, type Locator, type Page, type Request } from '@playwright/test';
import { ANLEGE_SEL, anlegenPflicht, cleanupTracked, E2E_TEST_PREFIX, hubApiPath, registerForCleanup, tippeUhrzeit } from './helpers';
import { wegwerfPasswort } from './stagingZugang';
import { DESKTOP, MOBIL, ZT, angezeigteZeit, cooldownFeld, oeffneZustellung, schalte } from './s3b2795-zustellung.helpers';

type Json = Record<string, any>; // eslint-disable-line @typescript-eslint/no-explicit-any
const einName = (tag: string) => `${E2E_TEST_PREFIX}OZ-${tag}-${Date.now()}`;
const POST_PFAD = '/api/compare/presets';
const VORSCHAU_PFAD = '/api/briefings/placements/vorschau';
/** Auflösung der Ampel: nur Lesen, aber POST (#2988). */
const AUFLOESUNG_PFAD = '/api/ampel/aufloesung';
const ALT_PANEL = ['versand-abschnitt', 'versand-tab', 'compare-step5-channel-email', 'weather-metrics-vergleich-reihenfolge', 'infobox-versand-vergleich', 'infobox-wetter-metriken-vergleich'];

test.afterEach(async ({ page }) => {
	await cleanupTracked(page.request);
});

/** Nur die Profil-Lesung im Browser: Telegram gilt als verbunden (nichts am Konto wird verändert). */
async function telegramVerbunden(page: Page): Promise<void> {
	await page.route('**/api/auth/profile', async (route) => {
		if (route.request().method() !== 'GET') return route.continue();
		const echt = await route.fetch();
		const profil = (await echt.json()) as Record<string, unknown>;
		await route.fulfill({ response: echt, json: { ...profil, telegram_chat_id: 'e2e-oz3333-chat' } });
	});
}

// ── Mitschnitt aller API-Aufrufe der Seite ──────────────────────────────────
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
		if (r.request().method() !== 'POST' || new URL(r.url()).pathname !== POST_PFAD || !r.ok()) return;
		const id = ((await r.json().catch(() => ({}))) as { id?: string }).id;
		if (id) m.anlegeIds.push(id);
	});
	return m;
}
const anlegePosts = (m: Mitschnitt) => m.alle.filter((x) => x.methode === 'POST' && x.pfad === POST_PFAD);
const schreibAufrufe = (m: Mitschnitt) =>
	m.alle.filter((x) => ['PUT', 'PATCH', 'DELETE'].includes(x.methode) || (x.methode === 'POST' && x.pfad !== VORSCHAU_PFAD && x.pfad !== AUFLOESUNG_PFAD && x.pfad !== POST_PFAD));

// ── Anlege-Seite ─────────────────────────────────────────────────────────────
const huelle = (mobil: boolean) => (mobil ? '.cm-mobile' : '.cm-desktop');
async function schritt(page: Page, id: string, mobil = false): Promise<void> {
	await ANLEGE_SEL.vergleich.reiter(page, id, mobil).click({ force: mobil });
	await expect.poll(async () => (await ANLEGE_SEL.vergleich.zustand(ANLEGE_SEL.vergleich.reiter(page, id, mobil))).aktiv, { timeout: 10_000 }).toBe(true);
}
/** Reiter Zustellung im Schritt Zustellung der Anlege-Seite, Kanal-Tabelle geladen. */
async function anlegeReiter(page: Page, mobil = false): Promise<Locator> {
	const reiter = page.locator(`${huelle(mobil)} [data-testid="${ZT.tab}"][data-context="vergleich"]`);
	await expect(reiter, 'AC-1: Reiter Zustellung fehlt im Orte-Anlegen').toBeVisible({ timeout: 15_000 });
	await expect(reiter.getByTestId(ZT.tabelle)).toBeVisible({ timeout: 15_000 });
	return reiter;
}
async function zumSchrittZustellung(page: Page, name: string, mobil = false): Promise<Locator> {
	await anlegenPflicht(page, 'vergleich', { name, mobil, viewport: mobil ? MOBIL : DESKTOP });
	// Der Schritt Zustellung ist bis zum ersten Öffnen von Wetter gesperrt (AN-5).
	await schritt(page, 'wetter', mobil);
	await schritt(page, 'zustellung', mobil);
	return anlegeReiter(page, mobil);
}
async function anlegen(page: Page, m: Mitschnitt, mobil = false, aufraeumen = true): Promise<{ id: string; status: number }> {
	const post = page.waitForResponse((r) => r.request().method() === 'POST' && new URL(r.url()).pathname === POST_PFAD, { timeout: 30_000 });
	await ANLEGE_SEL.vergleich.abschluss(page, mobil).click();
	const antwort = await post;
	expect([200, 201], `Anlege-POST HTTP ${antwort.status()}`).toContain(antwort.status());
	await expect.poll(() => m.anlegeIds.length).toBe(1);
	if (aufraeumen) registerForCleanup('preset', m.anlegeIds[0]);
	return { id: m.anlegeIds[0], status: antwort.status() };
}

/** Bedient den Reiter: Morgen 06:45, Abend aus, E-Mail aus, Telegram-Briefing an, Telegram-Alarm an mit
 *  Dringlichkeit „hoch“, Stille 22:30–06:15, Cooldown 45. */
async function bedienen(page: Page, reiter: Locator): Promise<void> {
	await tippeUhrzeit(page, reiter.getByTestId(ZT.zeit('morgen')), '06:45');
	await page.keyboard.press('Tab');
	expect(await angezeigteZeit(reiter.getByTestId(ZT.zeit('morgen')))).toBe('06:45');
	await schalte(reiter.getByTestId(ZT.schalter('abend')), false);
	await schalte(reiter.getByTestId(ZT.briefing('telegram')), true);
	await schalte(reiter.getByTestId(ZT.briefing('email')), false);
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

test.describe('#3333 Reiter Zustellung beim Ortsvergleich-Anlegen', () => {
	test('OZ-1 (AC-1/2/3/4/6/9/10/11): ein POST mit Zeiten, Kanälen, E-Mail aus, Dringlichkeit, Stille, Cooldown; Hub zeigt denselben Stand', async ({ page }) => {
		await telegramVerbunden(page);
		const m = mitschneiden(page);
		const reiter = await zumSchrittZustellung(page, einName('1'));
		const cm = page.locator('.cm-desktop');
		for (const id of ALT_PANEL) await expect(cm.getByTestId(id), `AC-1/AC-12: Alt-Panel-Baustein ${id} noch im Orte-Anlegen`).toHaveCount(0);
		const banner = reiter.getByTestId('compare-step5-activation-banner');
		await expect(banner, 'AC-11: Aktivierungs-Banner fehlt im Reiter Zustellung').toBeVisible();
		await expect(banner).toHaveAttribute('data-ready', 'true');
		// AC-10: jede Alarm-Einstellung genau eine Bedienstelle.
		await expect(cm.getByTestId('alarme-section-official-warnings'), 'AC-10: amtliche Warnungen bleiben im Reiter Alarme').toHaveCount(1, { timeout: 15_000 });
		for (const s of ['radar', 'metric-levels'])
			await expect(cm.getByTestId(`alarme-section-${s}`), `AC-10: ${s} bleibt im Reiter Alarme`).toHaveCount(1);
		for (const s of ['channels', 'cooldown', 'quiet-hours'])
			await expect(cm.getByTestId(`alarme-section-${s}`), `AC-10: Abschnitt ${s} im Reiter Alarme hat eine zweite Bedienstelle`).toHaveCount(0);

		await bedienen(page, reiter);
		expect(schreibAufrufe(m), 'AC-6: Schreibaufruf vor dem Anlegen').toEqual([]);

		const { id } = await anlegen(page, m);
		const posts = anlegePosts(m);
		expect(posts, 'AC-6: genau ein Anlege-POST').toHaveLength(1);
		expect(schreibAufrufe(m), 'AC-6: kein PUT/Schreibaufruf').toEqual([]);
		const r = posts[0].rumpf!;
		expect(r.morning_time, 'AC-2').toBe('06:45:00');
		expect(r.morning_enabled, 'AC-2').toBe(true);
		expect(r.evening_enabled, 'AC-2').toBe(false);
		expect(r.send_email, 'AC-4: E-Mail abgewählt').toBe(false);
		expect(r.send_telegram, 'AC-2').toBe(true);
		expect(r.alert_channels?.telegram, 'AC-3').toBe(true);
		expect(r.alert_channel_thresholds?.telegram, 'AC-3').toBe('HIGH');
		expect(r.alert_quiet_from, 'AC-2').toBe('22:30');
		expect(r.alert_quiet_to, 'AC-2').toBe('06:15');
		expect(r.alert_cooldown_minutes, 'AC-3').toBe(45);

		// AC-9: Rückweg in den Hub-Reiter Zustellung des neuen Vergleichs.
		const hub = await oeffneZustellung(page, 'vergleich', id);
		expect(await angezeigteZeit(hub.getByTestId(ZT.zeit('morgen'))), 'AC-9: Morgen-Zeit').toBe('06:45');
		await expect(hub.getByTestId(ZT.schalter('morgen')), 'AC-9: Morgen an').toHaveAttribute('aria-checked', 'true');
		await expect(hub.getByTestId(ZT.schalter('abend')), 'AC-9: Abend aus').toHaveAttribute('aria-checked', 'false');
		await expect(hub.getByTestId(ZT.briefing('email')), 'AC-9: E-Mail-Briefing aus').toHaveAttribute('aria-checked', 'false');
		await expect(hub.getByTestId(ZT.briefing('telegram')), 'AC-9: Briefing Telegram').toHaveAttribute('aria-checked', 'true');
		await expect(hub.getByTestId(ZT.alarm('telegram')), 'AC-9: Alarm Telegram').toHaveAttribute('aria-checked', 'true');
		await expect(hub.getByTestId(ZT.dringlichkeitOption('telegram', 'HIGH')), 'AC-9: Dringlichkeit').toHaveAttribute('aria-checked', 'true');
		await expect(hub.getByTestId(ZT.stilleSchalter), 'AC-9: Stille an').toHaveAttribute('aria-checked', 'true');
		expect(await angezeigteZeit(hub.getByTestId(ZT.stilleVon)), 'AC-9: Stille von').toBe('22:30');
		expect(await angezeigteZeit(hub.getByTestId(ZT.stilleBis)), 'AC-9: Stille bis').toBe('06:15');
		await expect(await cooldownFeld(hub), 'AC-9: Cooldown').toHaveValue('45');
		// Gespeicherter Stand per API (unabhängig von der Anzeige).
		const gespeichert = (await (await page.request.get(hubApiPath('vergleich', id))).json()) as Json;
		expect(gespeichert.send_email, 'AC-4: send_email:false nicht gespeichert').toBe(false);
	});

	test('OZ-2 (AC-8): 06:50 eingegeben — Meldung, Anlegen ohne 400, POST trägt die letzte gültige Zeit', async ({ page }) => {
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
		expect(r.morning_time, 'AC-8: letzte gültige Zeit').toBe('06:45:00');
		expect(JSON.stringify(r), 'AC-8: rasterfremde Zeit im POST').not.toContain('06:50');
		expect(r.send_email, 'AC-4: unberührte E-Mail reist als send_email:true').toBe(true);
	});

	test('OZ-3 (AC-1/AC-7): Mobil und Desktop — Reiter statt Alt-Panel, Stand überlebt Ansichts- und Schrittwechsel', async ({ page }) => {
		await telegramVerbunden(page);
		const m = mitschneiden(page);
		const reiter = await zumSchrittZustellung(page, einName('3'));
		await tippeUhrzeit(page, reiter.getByTestId(ZT.zeit('morgen')), '06:45');
		await page.keyboard.press('Tab');
		await schalte(reiter.getByTestId(ZT.alarm('telegram')), true);
		await reiter.getByTestId(ZT.dringlichkeitOption('telegram', 'HIGH')).click();

		await page.setViewportSize(MOBIL);
		const mobil = await anlegeReiter(page, true);
		for (const id of ALT_PANEL) await expect(page.locator('.cm-mobile').getByTestId(id), `AC-1 Mobil: Alt-Panel-Baustein ${id}`).toHaveCount(0);
		await expect(mobil.getByTestId('compare-step5-activation-banner'), 'AC-11 Mobil: Banner im Reiter').toBeVisible();
		expect(await angezeigteZeit(mobil.getByTestId(ZT.zeit('morgen'))), 'AC-7: Wechsel auf Mobil verliert die Zeit').toBe('06:45');
		await expect(mobil.getByTestId(ZT.dringlichkeitOption('telegram', 'HIGH')), 'AC-7: Wechsel auf Mobil verliert die Dringlichkeit').toHaveAttribute('aria-checked', 'true');
		await schalte(mobil.getByTestId(ZT.stilleSchalter), true);
		await schalte(mobil.getByTestId(ZT.briefing('email')), false);

		await page.setViewportSize(DESKTOP);
		await schritt(page, 'wetter');
		await schritt(page, 'zustellung');
		const zurueck = await anlegeReiter(page);
		expect(await angezeigteZeit(zurueck.getByTestId(ZT.zeit('morgen'))), 'AC-7: Schrittwechsel verliert die Zeit').toBe('06:45');
		await expect(zurueck.getByTestId(ZT.stilleSchalter), 'AC-7: Geste auf Mobil verloren').toHaveAttribute('aria-checked', 'true');
		await expect(zurueck.getByTestId(ZT.briefing('email')), 'AC-7: E-Mail-Abwahl auf Mobil verloren').toHaveAttribute('aria-checked', 'false');

		await anlegen(page, m);
		expect(anlegePosts(m), 'AC-6: genau ein Anlege-POST').toHaveLength(1);
		const r = anlegePosts(m)[0].rumpf!;
		expect(r.morning_time).toBe('06:45:00');
		expect(r.alert_channel_thresholds?.telegram).toBe('HIGH');
		expect(r.alert_quiet_from, 'AC-7: Stille aus der Mobil-Ansicht fehlt im POST').toBeTruthy();
		expect(r.send_email, 'AC-7: E-Mail-Abwahl aus der Mobil-Ansicht fehlt im POST').toBe(false);
	});

	test('OZ-4 (AC-14): A mit Telegram sieht die Dringlichkeit, B ohne nicht; jeder Vergleich nur beim eigenen Nutzer', async ({ page, browser }) => {
		await telegramVerbunden(page);
		const mA = mitschneiden(page);
		const reiterA = await zumSchrittZustellung(page, einName('4A'));
		await schalte(reiterA.getByTestId(ZT.alarm('telegram')), true);
		await expect(reiterA.getByTestId(ZT.dringlichkeitOption('telegram', 'HIGH')), 'AC-14: A sieht die Dringlichkeit nicht').toBeVisible();
		const { id: idA } = await anlegen(page, mA);

		const b = await zweitNutzer(browser, page, '10.33.33.13');
		try {
			const mB = mitschneiden(b.seite);
			const reiterB = await zumSchrittZustellung(b.seite, einName('4B'));
			await expect(reiterB.getByTestId(ZT.dringlichkeitOption('telegram', 'HIGH')), 'AC-14: B sieht die Dringlichkeit ohne Telegram').toHaveCount(0);
			await expect(reiterB.getByTestId(ZT.alarmGesperrt('telegram')), 'AC-14: B — Telegram-Alarm nicht als gesperrt markiert').toBeVisible();
			// B: Vergleich und Orte verschwinden mit dem Konto (kein Eintrag in die Aufräumliste von A).
			const { id: idB } = await anlegen(b.seite, mB, false, false);

			const listeB = ((await (await b.seite.request.get(POST_PFAD)).json()) as Json[]).map((p) => p.id);
			expect(listeB, 'AC-14: Vergleich von A in der Liste von B').not.toContain(idA);
			expect(listeB).toContain(idB);
			expect((await b.seite.request.get(hubApiPath('vergleich', idA))).ok(), 'AC-14: B liest den Vergleich von A').toBe(false);
			const listeA = ((await (await page.request.get(POST_PFAD)).json()) as Json[]).map((p) => p.id);
			expect(listeA, 'AC-14: Vergleich von B in der Liste von A').not.toContain(idB);
			expect(listeA).toContain(idA);
		} finally {
			await b.aufraeumen();
		}
	});
});

/** Zweiter, frisch registrierter und angemeldeter Nutzer in eigenem Browser-Kontext (Muster #3332 TZ-4). */
async function zweitNutzer(browser: Browser, admin: Page, ip: string): Promise<{ seite: Page; aufraeumen: () => Promise<void> }> {
	const basis = new URL((await admin.goto('/'))!.url()).origin;
	const name = `e2eoz3333${Date.now()}`;
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

// E2E — Issue #3305 (Teil B von #3041, Epic #3122): Tabelle „Was steht wo“ beim Trip-Anlegen.
// Spec docs/specs/modules/feat_3305_tabelle_trip_anlegen.md, Test Plan Nr. 7 bis 10 (AC-1 bis AC-5, AC-7 bis AC-10).
// Echte Go- und Python-Server (Staging in /e2e-verify), keine gemockten Antworten.
//
//   TA-1  (AC-1)        Karte im Schritt Wetter, Desktop und Mobil; Haken bleibt beim Wechsel Desktop/Mobil und
//                       beim Weiter-/Zurückgehen der Schritte gesetzt.
//   TA-2  (AC-2/3/4/10) Haken, Format, Reihenfolge und Schalter ändern, Trip anlegen: genau ein POST /api/trips mit
//                       display_config.placements und den Schalterfeldern; kein PUT, kein Schreibaufruf vorher;
//                       reine Kartenbedienung lädt keine Vorschau nach.
//   TA-3  (AC-5/AC-10)  Metrik entfernen/hinzufügen: Zeile entfällt/kommt hinzu, Haken bleibt; genau ein entprelltes
//                       Nachladen der Vorschau je Metrikwechsel.
//   TA-4  (AC-7)        Karte nicht bedient: POST ohne placements.rows und ohne Schalterfelder.
//   TA-5  (AC-8)        Rückweg: Reiter Wetter des neuen Trips zeigt dieselben Haken, Formate, Reihenfolge, Schalter.
//   TA-6  (AC-9)        Zwei Nutzer: B sieht den Trip von A nicht, kann seine Tabelle nicht lesen; Vorschau als B
//                       mit der Kennung von A liefert nichts von A.
//
//   cd frontend && npx playwright test e2e/trip-anlegen-was-steht-wo-3305.spec.ts --workers=1 --trace off

import { test, expect, request as pwRequest, type Browser, type Locator, type Page, type Request } from '@playwright/test';
import { ANLEGE_SEL, anlegenPflicht, cleanupTracked, E2E_TEST_PREFIX, hubApiPath } from './helpers';
import { wegwerfPasswort } from './stagingZugang';
import { DESKTOP, MOBIL, WT, oeffneWetter } from './s3a2794-teil3.helpers';

type Json = Record<string, any>; // eslint-disable-line @typescript-eslint/no-explicit-any
const VORSCHAU_PFAD = '/api/briefings/placements/vorschau';
const einName = (tag: string) => `${E2E_TEST_PREFIX}TA-${tag}-${Date.now()}`;

test.afterEach(async ({ page }) => {
	await cleanupTracked(page.request);
});

// ── Mitschnitt aller API-Aufrufe der Seite ───────────────────────────────────
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
const vorschauen = (m: Mitschnitt) => m.alle.filter((x) => x.methode === 'POST' && x.pfad === VORSCHAU_PFAD).length;
const anlegePosts = (m: Mitschnitt) => m.alle.filter((x) => x.methode === 'POST' && x.pfad === '/api/trips');
/** Schreibaufrufe außer Vorschau und Hilfsaufrufen (GPX, Ortsauflösung) — beim Anlegen darf es keine geben. */
const schreibAufrufe = (m: Mitschnitt) =>
	m.alle.filter(
		(x) =>
			['PUT', 'PATCH', 'DELETE'].includes(x.methode) ||
			(x.methode === 'POST' && x.pfad !== VORSCHAU_PFAD && x.pfad !== '/api/trips' && !x.pfad.startsWith('/api/gpx/') && !x.pfad.startsWith('/api/locations/resolve'))
	);

/** Stabilitätsfenster statt festem Schlaf. */
async function bleibtBei(lies: () => number, soll: number, ms: number, message: string): Promise<void> {
	let seit = 0;
	await expect
		.poll(
			() => {
				if (lies() !== soll) seit = 0;
				else if (!seit) seit = Date.now();
				return seit > 0 && Date.now() - seit >= ms;
			},
			{ message, timeout: ms + 10_000, intervals: [100] }
		)
		.toBe(true);
	expect(lies(), message).toBe(soll);
}

// ── Anlege-Seite ─────────────────────────────────────────────────────────────
const huelle = (mobil: boolean) => (mobil ? '.tn-mobile' : '.tn-desktop');
async function schritt(page: Page, id: string, mobil = false): Promise<void> {
	await ANLEGE_SEL.route.reiter(page, id, mobil).click({ force: mobil });
	await expect.poll(async () => (await ANLEGE_SEL.route.zustand(ANLEGE_SEL.route.reiter(page, id, mobil))).aktiv, { timeout: 10_000 }).toBe(true);
}
/** Karte im Schritt Wetter der Anlege-Seite, geladen. */
async function anlegeKarte(page: Page, mobil = false): Promise<Locator> {
	const tab = page.locator(`${huelle(mobil)} [data-testid="${WT.tab}"][data-context="route"]`);
	await expect(tab.getByTestId(WT.laden)).toHaveCount(0, { timeout: 20_000 });
	const karte = tab.getByTestId('was-steht-wo');
	await expect(karte.getByTestId('was-steht-wo-tabelle')).toBeVisible({ timeout: 20_000 });
	return karte;
}
async function zumSchrittWetter(page: Page, name: string, mobil = false): Promise<Locator> {
	await anlegenPflicht(page, 'route', { name, mobil, viewport: mobil ? MOBIL : DESKTOP });
	await schritt(page, 'wetter', mobil);
	return anlegeKarte(page, mobil);
}
async function anlegen(page: Page, m: Mitschnitt, mobil = false): Promise<string> {
	await schritt(page, 'zustellung', mobil);
	const post = page.waitForResponse((r) => r.request().method() === 'POST' && new URL(r.url()).pathname === '/api/trips', { timeout: 30_000 });
	await ANLEGE_SEL.route.abschluss(page, mobil).click();
	expect((await post).ok(), 'Anlege-POST').toBeTruthy();
	await expect.poll(() => m.anlegeIds.length).toBe(1);
	return m.anlegeIds[0];
}

// ── Karte ────────────────────────────────────────────────────────────────────
const zeile = (karte: Locator, metrik: string) => karte.locator(`[data-slot="et-zeile"][data-metrik="${metrik}"]`);
const zelle = (karte: Locator, metrik: string, stelle: string) => zeile(karte, metrik).locator(`[data-slot="et-zelle"][data-stelle="${stelle}"]`);
const haken = (karte: Locator, metrik: string, stelle: string) => zelle(karte, metrik, stelle).locator('input[type="checkbox"]');
const knopf = (karte: Locator, metrik: string, stelle: string) => zelle(karte, metrik, stelle).locator('[data-slot="roh-einfach"]');
const folge = (karte: Locator) => karte.locator('[data-slot="et-zeile"]').evaluateAll((z) => z.map((e) => e.getAttribute('data-metrik')!));
async function ersteAngehakte(karte: Locator, stelle: string, ohne: string[] = []): Promise<string> {
	for (const m of await folge(karte)) {
		if (ohne.includes(m)) continue;
		const h = haken(karte, m, stelle);
		if ((await h.count()) && (await h.isChecked()) && (await h.isEnabled())) return m;
	}
	throw new Error(`keine angehakte Zelle in ${stelle}`);
}
const rowVon = (p: Json | undefined, m: string) => ((p?.rows ?? []) as Json[]).find((r) => r.metric_id === m);

/** Bedient die Karte: Telegram-Haken weg, Roh/Einfach in der E-Mail, eine Zeile nach oben, drei Schalter aus,
 *  E-Mail-Format „Kompakt“. Liefert, was eingestellt wurde. */
async function karteBedienen(page: Page, karte: Locator): Promise<{ hakenMetrik: string; formatMetrik: string; formatVorher: string | null; folgeNach: string[] }> {
	const hakenMetrik = await ersteAngehakte(karte, 'telegram');
	await haken(karte, hakenMetrik, 'telegram').click();
	await expect(haken(karte, hakenMetrik, 'telegram')).not.toBeChecked();
	let formatMetrik = '';
	let formatVorher: string | null = null;
	for (const m of await folge(karte)) {
		if ((await knopf(karte, m, 'email').count()) === 0) continue;
		formatMetrik = m;
		formatVorher = await knopf(karte, m, 'email').getAttribute('data-wert');
		await knopf(karte, m, 'email').click();
		break;
	}
	expect(formatMetrik, 'Messaufbau: keine Zelle mit Roh/Einfach').not.toBe('');
	const vorher = await folge(karte);
	await zeile(karte, vorher[1]).getByTestId('drag-handle').focus();
	await page.keyboard.press('Space');
	await page.keyboard.press('ArrowUp');
	await page.keyboard.press('Space');
	await expect.poll(() => folge(karte)).not.toEqual(vorher);
	for (const feld of ['show_stage_stats', 'show_yesterday_comparison', 'show_night_block']) {
		const s = karte.getByTestId(`was-steht-wo-${feld}`);
		await expect(s).toHaveAttribute('aria-checked', 'true');
		await s.click();
		await expect(s).toHaveAttribute('aria-checked', 'false');
	}
	await karte.getByTestId('was-steht-wo-email-format-compact').click();
	return { hakenMetrik, formatMetrik, formatVorher, folgeNach: await folge(karte) };
}

test.describe('#3305 Tabelle „Was steht wo“ beim Trip-Anlegen', () => {
	test('TA-1 (AC-1): Karte in Desktop und Mobil, Haken überlebt Ansichtswechsel und Schrittwechsel', async ({ page }) => {
		const karte = await zumSchrittWetter(page, einName('1'));
		const m = await ersteAngehakte(karte, 'telegram');
		await haken(karte, m, 'telegram').click();
		await expect(haken(karte, m, 'telegram')).not.toBeChecked();

		await page.setViewportSize(MOBIL);
		const mobil = await anlegeKarte(page, true);
		await expect(haken(mobil, m, 'telegram'), 'Wechsel auf Mobil: Haken verloren').not.toBeChecked();
		await expect(mobil.getByTestId('was-steht-wo-show_night_block')).toBeVisible();

		await page.setViewportSize(DESKTOP);
		await schritt(page, 'zustellung');
		await schritt(page, 'wetter');
		const zurueck = await anlegeKarte(page);
		await expect(haken(zurueck, m, 'telegram'), 'Schrittwechsel: Haken verloren').not.toBeChecked();
	});

	test('TA-2 (AC-2/3/4/10): genau ein POST mit Tabelle und Schaltern, kein PUT, keine Vorschau bei reiner Bedienung', async ({ page }) => {
		const m = mitschneiden(page);
		const karte = await zumSchrittWetter(page, einName('2'));
		await expect.poll(() => vorschauen(m), { message: 'Karte lädt über die Vorschau' }).toBeGreaterThanOrEqual(1);
		const vorschauVorher = vorschauen(m);
		const e = await karteBedienen(page, karte);
		await bleibtBei(() => vorschauen(m), vorschauVorher, 2_000, 'AC-10: reine Kartenbedienung lädt die Vorschau nach');
		expect(schreibAufrufe(m), 'AC-4: Schreibaufruf vor dem Anlegen').toEqual([]);

		await anlegen(page, m);
		const posts = anlegePosts(m);
		expect(posts, 'AC-4: genau ein Anlege-POST').toHaveLength(1);
		expect(schreibAufrufe(m), 'AC-4: kein PUT/Schreibaufruf').toEqual([]);
		const rumpf = posts[0].rumpf!;
		const pl = rumpf.display_config?.placements;
		expect((pl?.rows as Json[] | undefined)?.map((r) => r.metric_id).slice(0, e.folgeNach.length), 'AC-2: Reihenfolge').toEqual(e.folgeNach);
		expect(rowVon(pl, e.hakenMetrik)?.places?.telegram, 'AC-2: Haken').toBe(false);
		expect(rowVon(pl, e.formatMetrik)?.formats?.email, 'AC-2: Format').not.toBe(e.formatVorher ?? undefined);
		expect(rumpf.display_config?.show_night_block, 'AC-3').toBe(false);
		expect(rumpf.report_config?.show_stage_stats, 'AC-3').toBe(false);
		expect(rumpf.report_config?.show_yesterday_comparison, 'AC-3').toBe(false);
		expect(rumpf.report_config?.email_format, 'AC-3').toBe('compact');
	});

	test('TA-3 (AC-5/AC-10): Metrik weg und hinzu — Zeilen folgen, Haken bleibt, je Wechsel genau eine Vorschau', async ({ page }) => {
		const m = mitschneiden(page);
		const karte = await zumSchrittWetter(page, einName('3'));
		const tab = page.locator(`.tn-desktop [data-testid="${WT.tab}"][data-context="route"]`);
		await expect.poll(() => vorschauen(m)).toBeGreaterThanOrEqual(1);
		const reihe = await folge(karte);
		const bleibt = await ersteAngehakte(karte, 'telegram');
		await haken(karte, bleibt, 'telegram').click();
		const weg = reihe.find((x) => x !== bleibt)!;

		let vorher = vorschauen(m);
		await tab.getByTestId(WT.entfernen(weg)).click();
		await expect(zeile(karte, weg)).toHaveCount(0, { timeout: 15_000 });
		await bleibtBei(() => vorschauen(m), vorher + 1, 2_000, 'AC-10: Metrik entfernt — genau ein Nachladen');
		await expect(haken(karte, bleibt, 'telegram'), 'AC-5: Haken nach Entfernen verloren').not.toBeChecked();

		vorher = vorschauen(m);
		await tab.getByTestId(WT.plus(weg)).click();
		await expect(zeile(karte, weg)).toHaveCount(1, { timeout: 15_000 });
		await bleibtBei(() => vorschauen(m), vorher + 1, 2_000, 'AC-10: Metrik hinzugefügt — genau ein Nachladen');
		await expect(haken(karte, bleibt, 'telegram'), 'AC-5: Haken nach Hinzufügen verloren').not.toBeChecked();
		expect((await folge(karte)).at(-1), 'AC-5: neue Zeile steht hinten').toBe(weg);
	});

	test('TA-4 (AC-7): Karte nicht bedient — POST ohne placements.rows und ohne Schalterfelder', async ({ page }) => {
		const m = mitschneiden(page);
		await zumSchrittWetter(page, einName('4'));
		await anlegen(page, m);
		const rumpf = anlegePosts(m)[0].rumpf!;
		expect(rumpf.display_config?.placements?.rows, 'AC-7: rows im POST').toBeUndefined();
		expect(rumpf.display_config?.show_night_block, 'AC-7: Nacht-Block aus der Karte im POST').toBeUndefined();
		// Fix-Loop 4: `report_config` trägt die Blöcke und Formate schon ohne Karte (Mail-Inhalt und Zustellung
		// schreiben sie in den Entwurf). AC-7 heißt: die Karte fügt nichts hinzu und ändert nichts — der POST
		// trägt genau die Werte des Entwurfs, den die Karte selbst als Vorschau gesendet hat (ohne Kartenstand).
		const entwuerfe = m.alle.filter((x) => x.methode === 'POST' && x.pfad === VORSCHAU_PFAD).map((x) => x.rumpf!);
		expect(entwuerfe.length, 'Messaufbau: die Karte hat keine Vorschau geladen').toBeGreaterThanOrEqual(1);
		const ohneKarte = entwuerfe.at(-1)!;
		expect(ohneKarte.display_config?.placements, 'Messaufbau: unbediente Karte sendet einen Tabellenstand').toBeUndefined();
		for (const feld of ['show_stage_stats', 'show_yesterday_comparison', 'email_format', 'telegram_style'])
			expect(rumpf.report_config?.[feld], `AC-7: report_config.${feld} weicht vom Stand ohne Karte ab`).toEqual(ohneKarte.report_config?.[feld]);
	});

	test('TA-5 (AC-8): Reiter Wetter des neuen Trips zeigt das beim Anlegen Eingestellte', async ({ page }) => {
		const m = mitschneiden(page);
		const karte = await zumSchrittWetter(page, einName('5'));
		const e = await karteBedienen(page, karte);
		const formatNach = await knopf(karte, e.formatMetrik, 'email').getAttribute('data-wert');
		const id = await anlegen(page, m);

		const reiter = await oeffneWetter(page, 'route', id);
		const hub = reiter.getByTestId('was-steht-wo');
		await expect(hub.getByTestId('was-steht-wo-tabelle')).toBeVisible({ timeout: 20_000 });
		expect((await folge(hub)).slice(0, e.folgeNach.length), 'AC-8: Reihenfolge').toEqual(e.folgeNach);
		await expect(haken(hub, e.hakenMetrik, 'telegram'), 'AC-8: Haken').not.toBeChecked();
		await expect(knopf(hub, e.formatMetrik, 'email'), 'AC-8: Format').toHaveAttribute('data-wert', formatNach ?? '');
		for (const feld of ['show_stage_stats', 'show_yesterday_comparison', 'show_night_block'])
			await expect(hub.getByTestId(`was-steht-wo-${feld}`), `AC-8: ${feld}`).toHaveAttribute('aria-checked', 'false');
		await expect(hub.getByTestId('was-steht-wo-email-format-compact'), 'AC-8: E-Mail-Format').toHaveAttribute('aria-checked', 'true');
		const t = await (await page.request.get(`/api/briefings/${id}/placements?kind=route`)).json();
		expect(t.stored, 'Tabelle ist gespeichert').toBe(true);
	});

	test('TA-6 (AC-9): zweiter Nutzer sieht Trip und Tabelle von A nicht; Vorschau als B ohne Daten von A', async ({ page, browser }) => {
		const m = mitschneiden(page);
		const karte = await zumSchrittWetter(page, einName('6'));
		const e = await karteBedienen(page, karte);
		const id = await anlegen(page, m);
		const b = await zweitNutzer(browser, page, '10.33.5.7');
		try {
			const liste = (await (await b.seite.request.get('/api/trips')).json()) as Json[];
			expect(liste.map((t) => t.id), 'AC-9: Trip von A in der Liste von B').not.toContain(id);
			expect((await b.seite.request.get(hubApiPath('route', id))).ok(), 'AC-9: B liest den Trip von A').toBe(false);
			expect((await b.seite.request.get(`/api/briefings/${id}/placements?kind=route`)).ok(), 'AC-9: B liest die Tabelle von A').toBe(false);
			const v = await b.seite.request.post(`${VORSCHAU_PFAD}?kind=route`, {
				data: { id, name: 'B-Entwurf', stages: [], display_config: { metrics: [{ metric_id: 'wind', enabled: true }] } }
			});
			expect(v.ok(), `Vorschau als B: ${v.status()}`).toBe(true);
			const antwort = (await v.json()) as Json;
			expect(antwort.stored).toBe(false);
			expect(rowVon(antwort.placements, e.hakenMetrik)?.places?.telegram, 'AC-9: Vorschau als B trägt die Einstellung von A').not.toBe(false);
		} finally {
			await b.aufraeumen();
		}
	});
});

/** Zweiter, frisch registrierter und angemeldeter Nutzer in eigenem Browser-Kontext (Muster was-steht-wo-karte.spec.ts). */
async function zweitNutzer(browser: Browser, admin: Page, ip: string): Promise<{ seite: Page; aufraeumen: () => Promise<void> }> {
	const basis = new URL((await admin.goto('/'))!.url()).origin;
	const name = `e2eta3305${Date.now()}`;
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

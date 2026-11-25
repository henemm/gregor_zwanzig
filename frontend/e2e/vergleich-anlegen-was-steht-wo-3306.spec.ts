// E2E — Issue #3306 (Teil C von #3041, Epic #3122): Tabelle „Was steht wo“ beim Ortsvergleich-Anlegen.
// Spec docs/specs/modules/feat_3306_tabelle_orte_anlegen.md, Test Plan Nr. 7 bis 10 (AC-1 bis AC-7).
// Echte Go- und Python-Server (Staging in /e2e-verify), keine gemockten Antworten. Einzige Ausnahme wie in
// hub-anlegen-ablauf.spec.ts AN-6: die Profil-LESUNG im Browser wird um eine Test-Chat-ID ergänzt, damit der
// Telegram-Kurzstil bedienbar ist (der Env-Admin hat kein Telegram; kein Profil wird verändert).
//
//   VA-1  (AC-1)        Karte im Schritt Wetter, Desktop und Mobil, mit Beispielwerten der gewählten Orte; Haken
//                       und Schalter bleiben beim Wechsel Desktop/Mobil und beim Weiter-/Zurückgehen der Schritte.
//   VA-2  (AC-2/3/4)    Haken, Format, Reihenfolge, Stundenverlauf, Ausblick, Kurzstil ändern, anlegen: genau ein
//                       POST /api/compare/presets mit display_config.placements, hourly_enabled,
//                       display_config.telegram_style; kein PUT, kein Schreibaufruf vorher; keine Altschlüssel;
//                       Versandzeiten und Kanäle wie im Entwurf.
//   VA-3  (AC-5)        Karte nicht bedient: POST ohne placements.rows und ohne Schalterfelder aus der Karte.
//   VA-4  (AC-6)        Rückweg: Reiter Wetter des neuen Ortsvergleichs zeigt dieselben Haken, Formate,
//                       Reihenfolge und Schalter.
//   VA-5  (AC-7)        Zwei Nutzer: B sieht den Ortsvergleich von A nicht, kann ihn und seine Tabelle nicht lesen;
//                       Vorschau als B mit den Orts-Kennungen von A rechnet mit null Orten.
//
//   cd frontend && npx playwright test e2e/vergleich-anlegen-was-steht-wo-3306.spec.ts --workers=1 --trace off

import { test, expect, request as pwRequest, type Browser, type Locator, type Page, type Request } from '@playwright/test';
import { ANLEGE_SEL, anlegenPflicht, cleanupTracked, E2E_TEST_PREFIX, hubApiPath, registerForCleanup } from './helpers';
import { wegwerfPasswort } from './stagingZugang';
import { DESKTOP, MOBIL, WT, oeffneWetter } from './s3a2794-teil3.helpers';

type Json = Record<string, any>; // eslint-disable-line @typescript-eslint/no-explicit-any
const VORSCHAU_PFAD = '/api/briefings/placements/vorschau';
/** Auflösung der Ampel: nur Lesen, aber POST (#2988). */
const AUFLOESUNG_PFAD = '/api/ampel/aufloesung';
const ANLEGE_PFAD = ANLEGE_SEL.vergleich.postPfad; // /api/compare/presets
const ALTSCHLUESSEL = ['channel_layouts', 'outlook_metrics', 'outlook_metric_formats', 'channel_active_metrics', 'hourly_metrics', 'hourly_metric_formats'];
const einName = (tag: string) => `${E2E_TEST_PREFIX}VA-${tag}-${Date.now()}`;

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
		if (r.request().method() !== 'POST' || new URL(r.url()).pathname !== ANLEGE_PFAD || !r.ok()) return;
		const id = ((await r.json().catch(() => ({}))) as { id?: string }).id;
		if (id) {
			m.anlegeIds.push(id);
			registerForCleanup('preset', id);
		}
	});
	return m;
}
const vorschauRuempfe = (m: Mitschnitt) => m.alle.filter((x) => x.methode === 'POST' && x.pfad === VORSCHAU_PFAD).map((x) => x.rumpf ?? {});
const anlegePosts = (m: Mitschnitt) => m.alle.filter((x) => x.methode === 'POST' && x.pfad === ANLEGE_PFAD);
/** Schreibaufrufe außer Vorschau, Anlege-POST und Test-Orten (vor dem Seitenaufruf) — beim Anlegen darf es keine geben. */
const schreibAufrufe = (m: Mitschnitt) =>
	m.alle.filter(
		(x) => ['PUT', 'PATCH', 'DELETE'].includes(x.methode) || (x.methode === 'POST' && x.pfad !== VORSCHAU_PFAD && x.pfad !== AUFLOESUNG_PFAD && x.pfad !== ANLEGE_PFAD && x.pfad !== '/api/locations')
	);

/** Profil-Lesung im Browser mit Test-Chat-ID (Kurzstil bedienbar); das gespeicherte Profil bleibt unverändert. */
async function telegramVerbundenAnzeigen(page: Page): Promise<void> {
	await page.route('**/api/auth/profile', async (route) => {
		if (route.request().method() !== 'GET') return route.continue();
		const echt = await route.fetch();
		const profil = (await echt.json()) as Json;
		await route.fulfill({ response: echt, json: { ...profil, telegram_chat_id: 'e2e-va3306-test-chat' } });
	});
}

// ── Anlege-Seite ─────────────────────────────────────────────────────────────
const huelle = (mobil: boolean) => (mobil ? '.cm-mobile' : '.cm-desktop');
async function schritt(page: Page, id: string, mobil = false): Promise<void> {
	await ANLEGE_SEL.vergleich.reiter(page, id, mobil).click({ force: mobil });
	await expect.poll(async () => (await ANLEGE_SEL.vergleich.zustand(ANLEGE_SEL.vergleich.reiter(page, id, mobil))).aktiv, { timeout: 10_000 }).toBe(true);
}
/** Karte im Schritt Wetter der Anlege-Seite, geladen. */
async function anlegeKarte(page: Page, mobil = false): Promise<Locator> {
	const tab = page.locator(`${huelle(mobil)} [data-testid="${WT.tab}"][data-context="vergleich"]`);
	await expect(tab.getByTestId(WT.laden)).toHaveCount(0, { timeout: 20_000 });
	const karte = tab.getByTestId('was-steht-wo');
	await expect(karte.getByTestId('was-steht-wo-tabelle'), 'AC-1: Karte „Was steht wo“ fehlt im Schritt Wetter').toBeVisible({ timeout: 20_000 });
	return karte;
}
async function zumSchrittWetter(page: Page, name: string, mobil = false): Promise<Locator> {
	await anlegenPflicht(page, 'vergleich', { name, mobil, viewport: mobil ? MOBIL : DESKTOP });
	await schritt(page, 'wetter', mobil);
	return anlegeKarte(page, mobil);
}
async function anlegen(page: Page, m: Mitschnitt, mobil = false): Promise<string> {
	await schritt(page, 'zustellung', mobil);
	const post = page.waitForResponse((r) => r.request().method() === 'POST' && new URL(r.url()).pathname === ANLEGE_PFAD, { timeout: 30_000 });
	await ANLEGE_SEL.vergleich.abschluss(page, mobil).click();
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
const an = async (s: Locator) => (await s.getAttribute('aria-checked')) === 'true';
async function ersteAngehakte(karte: Locator, stelle: string, ohne: string[] = []): Promise<string> {
	for (const m of await folge(karte)) {
		if (ohne.includes(m)) continue;
		const h = haken(karte, m, stelle);
		if ((await h.count()) && (await h.isChecked()) && (await h.isEnabled())) return m;
	}
	throw new Error(`keine angehakte Zelle in ${stelle}`);
}
const rowVon = (p: Json | undefined, m: string) => ((p?.rows ?? []) as Json[]).find((r) => r.metric_id === m);

type Bedient = {
	hakenMetrik: string;
	formatMetrik: string;
	formatVorher: string | null;
	folgeNach: string[];
	stundenverlauf: boolean;
	ausblickMorgen: boolean;
	kurzstil: boolean;
};
/** Bedient die Karte: Telegram-Haken weg, Roh/Einfach in der E-Mail, eine Zeile nach oben, Stundenverlauf,
 *  Ausblick morgens und Telegram-Kurzstil umschalten. Liefert, was eingestellt wurde. */
async function karteBedienen(page: Page, karte: Locator): Promise<Bedient> {
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

	const umschalten = async (testid: string): Promise<boolean> => {
		const s = karte.getByTestId(testid);
		await expect(s, `Schalter ${testid} fehlt in der Karte`).toBeVisible();
		await expect(s).not.toHaveAttribute('aria-disabled', 'true');
		const soll = !(await an(s));
		await s.click();
		await expect(s).toHaveAttribute('aria-checked', String(soll));
		return soll;
	};
	const stundenverlauf = await umschalten('was-steht-wo-stundenverlauf');
	const ausblickMorgen = await umschalten('was-steht-wo-ausblick-morning');
	const kurzstil = await umschalten('was-steht-wo-kurzstil');
	return { hakenMetrik, formatMetrik, formatVorher, folgeNach: await folge(karte), stundenverlauf, ausblickMorgen, kurzstil };
}

test.describe('#3306 Tabelle „Was steht wo“ beim Ortsvergleich-Anlegen', () => {
	test('VA-1 (AC-1): Karte in Desktop und Mobil mit Beispielwerten der Orte, Stand überlebt Ansichts- und Schrittwechsel', async ({ page }) => {
		await telegramVerbundenAnzeigen(page);
		const m = mitschneiden(page);
		const karte = await zumSchrittWetter(page, einName('1'));
		const rumpf = vorschauRuempfe(m).at(-1);
		expect((rumpf?.location_ids as string[] | undefined)?.length, 'AC-1: Vorschau ohne die gewählten Orte').toBe(2);
		await expect(karte.getByTestId('was-steht-wo-sms-text'), 'AC-1: keine Beispielwerte der gewählten Orte').not.toHaveText('', { timeout: 15_000 });

		const mt = await ersteAngehakte(karte, 'telegram');
		await haken(karte, mt, 'telegram').click();
		await expect(haken(karte, mt, 'telegram')).not.toBeChecked();
		const stunden = karte.getByTestId('was-steht-wo-stundenverlauf');
		const stundenSoll = !(await an(stunden));
		await stunden.click();
		await expect(stunden).toHaveAttribute('aria-checked', String(stundenSoll));

		await page.setViewportSize(MOBIL);
		const mobil = await anlegeKarte(page, true);
		await expect(haken(mobil, mt, 'telegram'), 'Wechsel auf Mobil: Haken verloren').not.toBeChecked();
		await expect(mobil.getByTestId('was-steht-wo-stundenverlauf'), 'Wechsel auf Mobil: Schalter verloren').toHaveAttribute('aria-checked', String(stundenSoll));
		await expect(mobil.getByTestId('was-steht-wo-kurzstil')).toBeVisible();
		await expect(mobil.getByTestId('was-steht-wo-ausblick-morning')).toBeVisible();

		await page.setViewportSize(DESKTOP);
		await schritt(page, 'zustellung');
		await schritt(page, 'wetter');
		const zurueck = await anlegeKarte(page);
		await expect(haken(zurueck, mt, 'telegram'), 'Schrittwechsel: Haken verloren').not.toBeChecked();
		await expect(zurueck.getByTestId('was-steht-wo-stundenverlauf'), 'Schrittwechsel: Schalter verloren').toHaveAttribute('aria-checked', String(stundenSoll));
	});

	test('VA-2 (AC-2/3/4): genau ein POST mit Tabelle und Schaltern, kein PUT, keine Altschlüssel', async ({ page }) => {
		await telegramVerbundenAnzeigen(page);
		const m = mitschneiden(page);
		const karte = await zumSchrittWetter(page, einName('2'));
		const e = await karteBedienen(page, karte);
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
		expect(((pl?.outlook_reports ?? []) as string[]).includes('morning'), 'AC-3: Ausblick als outlook_reports').toBe(e.ausblickMorgen);
		expect(rumpf.hourly_enabled, 'AC-3: Stundenverlauf').toBe(e.stundenverlauf);
		expect(rumpf.display_config?.telegram_style ?? 'rich', 'AC-3: Telegram-Kurzstil').toBe(e.kurzstil ? 'kurzform' : 'rich');
		for (const a of ALTSCHLUESSEL) {
			expect(rumpf[a], `AC-3: Altschlüssel ${a} im POST`).toBeUndefined();
			expect(rumpf.display_config?.[a], `AC-3: Altschlüssel display_config.${a} im POST`).toBeUndefined();
		}
		// Orte wie im Entwurf der Vorschau (Schritt Orte liegt vor Wetter). Versandzeiten und Kanäle ohne
		// Kartenbedienung prüft der Kern-Test (vergleich_anlegen_karte_payload_3306, Abweichungsliste).
		const entwurf = vorschauRuempfe(m)[0];
		expect(rumpf.location_ids, 'Orte im POST = Orte des Entwurfs').toEqual(entwurf.location_ids);
	});

	test('VA-3 (AC-5): Karte nicht bedient — POST ohne placements.rows und ohne Schalterfelder aus der Karte', async ({ page }) => {
		const m = mitschneiden(page);
		await zumSchrittWetter(page, einName('3'));
		await anlegen(page, m);
		const rumpf = anlegePosts(m)[0].rumpf!;
		expect(rumpf.display_config?.placements?.rows, 'AC-5: rows im POST').toBeUndefined();
		expect(rumpf.hourly_enabled, 'AC-5: hourly_enabled weicht vom Feldsatz ab').toBe(true);
		expect(rumpf.display_config?.telegram_style, 'AC-5: telegram_style aus der Karte im POST').toBeUndefined();
		const t = await (await page.request.get(`/api/briefings/${m.anlegeIds[0]}/placements?kind=vergleich`)).json();
		expect((t.placements?.rows ?? []).length, 'AC-5: Server baut die Tabelle aus der Grundauswahl').toBeGreaterThan(0);
	});

	test('VA-4 (AC-6): Reiter Wetter des neuen Ortsvergleichs zeigt das beim Anlegen Eingestellte', async ({ page }) => {
		await telegramVerbundenAnzeigen(page);
		const m = mitschneiden(page);
		const karte = await zumSchrittWetter(page, einName('4'));
		const e = await karteBedienen(page, karte);
		const formatNach = await knopf(karte, e.formatMetrik, 'email').getAttribute('data-wert');
		const id = await anlegen(page, m);

		const reiter = await oeffneWetter(page, 'vergleich', id);
		const hub = reiter.getByTestId('was-steht-wo');
		await expect(hub.getByTestId('was-steht-wo-tabelle')).toBeVisible({ timeout: 20_000 });
		expect((await folge(hub)).slice(0, e.folgeNach.length), 'AC-6: Reihenfolge').toEqual(e.folgeNach);
		await expect(haken(hub, e.hakenMetrik, 'telegram'), 'AC-6: Haken').not.toBeChecked();
		await expect(knopf(hub, e.formatMetrik, 'email'), 'AC-6: Format').toHaveAttribute('data-wert', formatNach ?? '');
		await expect(hub.getByTestId('was-steht-wo-stundenverlauf'), 'AC-6: Stundenverlauf').toHaveAttribute('aria-checked', String(e.stundenverlauf));
		await expect(hub.getByTestId('was-steht-wo-ausblick-morning'), 'AC-6: Ausblick morgens').toHaveAttribute('aria-checked', String(e.ausblickMorgen));
		await expect(hub.getByTestId('was-steht-wo-kurzstil'), 'AC-6: Telegram-Kurzstil').toHaveAttribute('aria-checked', String(e.kurzstil));
		const t = await (await page.request.get(`/api/briefings/${id}/placements?kind=vergleich`)).json();
		expect(t.stored, 'Tabelle ist gespeichert').toBe(true);
	});

	test('VA-5 (AC-7): zweiter Nutzer sieht Ortsvergleich und Tabelle von A nicht; Vorschau als B ohne Orte von A', async ({ page, browser }) => {
		await telegramVerbundenAnzeigen(page);
		const m = mitschneiden(page);
		const karte = await zumSchrittWetter(page, einName('5'));
		await karteBedienen(page, karte);
		const id = await anlegen(page, m);
		const orteA = (anlegePosts(m)[0].rumpf?.location_ids ?? []) as string[];
		expect(orteA.length, 'Messaufbau: POST ohne Orte').toBe(2);
		const vorschauA = (await (await page.request.post(`${VORSCHAU_PFAD}?kind=vergleich`, { data: { location_ids: orteA } })).json()) as Json;
		expect(vorschauA.location_count, 'Messaufbau: Vorschau als A rechnet mit den eigenen Orten').toBe(2);

		const b = await zweitNutzer(browser, page, '10.33.6.7');
		try {
			const liste = (await (await b.seite.request.get(ANLEGE_PFAD)).json()) as Json[];
			expect(liste.map((p) => p.id), 'AC-7: Ortsvergleich von A in der Liste von B').not.toContain(id);
			expect((await b.seite.request.get(hubApiPath('vergleich', id))).ok(), 'AC-7: B liest den Ortsvergleich von A').toBe(false);
			expect((await b.seite.request.get(`/api/briefings/${id}/placements?kind=vergleich`)).ok(), 'AC-7: B liest die Tabelle von A').toBe(false);
			const v = await b.seite.request.post(`${VORSCHAU_PFAD}?kind=vergleich`, { data: { location_ids: orteA } });
			expect(v.ok(), `Vorschau als B: ${v.status()}`).toBe(true);
			const antwort = (await v.json()) as Json;
			expect(antwort.stored).toBe(false);
			expect(antwort.location_count, 'AC-7: Vorschau als B rechnet mit Orten von A').toBe(0);
			expect(antwort.sms_example?.text ?? null, 'AC-7: Vorschau als B zeigt Beispielwerte aus Orten von A').not.toBe(vorschauA.sms_example?.text);
		} finally {
			await b.aufraeumen();
		}
	});
});

/** Zweiter, frisch registrierter und angemeldeter Nutzer in eigenem Browser-Kontext (Muster trip-anlegen-was-steht-wo-3305.spec.ts). */
async function zweitNutzer(browser: Browser, admin: Page, ip: string): Promise<{ seite: Page; aufraeumen: () => Promise<void> }> {
	const basis = new URL((await admin.goto('/'))!.url()).origin;
	const name = `e2eva3306${Date.now()}`;
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

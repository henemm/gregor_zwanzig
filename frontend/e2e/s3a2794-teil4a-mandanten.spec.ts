// E2E (Staging, nur /e2e-verify) — Issue #2794 S3a, Teil-PR 4a (Entfernen und Umzug).
// Spec: docs/specs/modules/feat_2794_s3a_teil4_entfernen.md — AC-43 bis AC-46.
//
// Der Corridor-Editor lief bisher versteckt in den Anlege-Ketten und lieferte dort die
// Vorbelegung der Wertebereiche (`corridors`). Seit 4a rechnet sie eine reine Funktion
// (shared/wetter-tab/anlegeVorbelegung.ts) in genau einem `$effect` je Anlege-Editor.
// Dieser Spec prueft das aus Nutzersicht, am echten Anlege-POST und am gespeicherten Objekt:
//
//   AC-43  Trip: Durchklicken UND „Mit Standardwerten speichern" tragen die vorbelegten
//          `corridors`; ohne Wetter-Metriken wird der Standardwerte-Knopf trotzdem frei.
//   AC-44  Orts-Briefing: Schritt Wetter verlassen und wieder betreten belegt nicht erneut vor —
//          die einmal belegten Wertebereiche bleiben, wie sie sind.
//   AC-45  Breitenwechsel Desktop ⇄ mobil waehrend des Anlegens: genau EIN Anlege-POST, jede
//          Metrik genau einmal in `corridors`.
//   AC-46  Zwei Nutzer: A legt Trip und Orts-Briefing mit geaenderten Grenzen an, B mit
//          Standardwerten. Jedes Objekt traegt nur die Werte seines Nutzers, B sieht A's
//          Objekte weder per API noch in seiner Liste.
//
// Dieselbe Pruefung fuer Trip (route) und Orts-Briefing (vergleich), wo das Verhalten gleich ist.
//
//   cd frontend && npx playwright test e2e/s3a2794-teil4a-mandanten.spec.ts --config playwright.config.ts

import { test, expect, type APIRequestContext, type Page, type Request } from '@playwright/test';
import {
	ANLEGE_SEL,
	HUB_KINDS,
	anlegenPflicht,
	cleanupTracked,
	login,
	registerForCleanup,
	registriereBestaetigtenZweitnutzer,
	type HubKind
} from './helpers';
import { DESKTOP, MOBIL, WT, type Json } from './s3a2794-teil3.helpers';
import { wegwerfPasswort } from './stagingZugang';

/** Metrik, deren Grenzen Nutzer A aendert (Bestandteil jeder Systemvorlage, vgl. s3a2794-teil3-mandanten). */
const METRIK = 'gust';
const A_WERT = 52;
const LISTE = { route: '/api/trips', vergleich: '/api/compare/presets' } as const;
const CLEANUP = { route: 'trip', vergleich: 'preset' } as const;

test.beforeEach(async ({ page }) => {
	await login(page);
});
test.afterEach(async ({ page }) => {
	await cleanupTracked(page.request);
});

const name = (kind: HubKind, wer: string) => `E2E-GZ-4a-${kind}-${wer} ${Date.now()}`;

/** Zaehlt jeden Anlege-POST der Art (auch fehlgeschlagene). */
function postZaehler(page: Page, kind: HubKind): Request[] {
	const posts: Request[] = [];
	page.on('request', (r) => {
		if (r.method() === 'POST' && new URL(r.url()).pathname === ANLEGE_SEL[kind].postPfad) posts.push(r);
	});
	return posts;
}

/** Den Anlege-POST ausloesen und die Kennung des neuen Objekts liefern (zum Raeumen registriert). */
async function anlegen(page: Page, kind: HubKind, knopf: ReturnType<Page['getByTestId']>, aufraeumen = true): Promise<string> {
	await expect(knopf).toBeEnabled({ timeout: 15_000 });
	const antwort = page.waitForResponse(
		(r) => r.request().method() === 'POST' && new URL(r.url()).pathname === ANLEGE_SEL[kind].postPfad,
		{ timeout: 30_000 }
	);
	await knopf.click();
	const r = await antwort;
	expect(r.ok(), `Anlege-POST ${kind}: HTTP ${r.status()}`).toBeTruthy();
	const id = ((await r.json()) as { id: string }).id;
	if (aufraeumen) registerForCleanup(CLEANUP[kind], id);
	return id;
}

async function lies(request: APIRequestContext, kind: HubKind, id: string): Promise<Json> {
	const r = await request.get(`${LISTE[kind]}/${id}`);
	expect(r.ok(), `GET ${LISTE[kind]}/${id}: HTTP ${r.status()}`).toBeTruthy();
	return r.json();
}

/** Schritt Wetter des Anlege-Editors oeffnen und auf den geladenen Reiter warten. */
async function schrittWetter(page: Page, kind: HubKind, mobil = false) {
	await ANLEGE_SEL[kind].reiter(page, 'wetter', mobil).click({ force: mobil });
	const reiter = page.locator(`[data-testid="${WT.tab}"][data-context="${kind}"]:visible`).first();
	await expect(reiter).toBeVisible({ timeout: 15_000 });
	await expect(reiter.getByTestId(WT.laden)).toHaveCount(0, { timeout: 15_000 });
	return reiter;
}

/** Bis zum Ende durchklicken (Wetter, Zustellung) — der Bestandsweg „Speichern". */
async function durchklicken(page: Page, kind: HubKind, mobil = false): Promise<void> {
	for (const s of ['wetter', 'zustellung']) await ANLEGE_SEL[kind].reiter(page, s, mobil).click({ force: mobil });
}

/** Nutzer A aendert im Schritt Wetter eine Grenze (die sichtbare „Wertebereiche"-Bedienung seit Teil 3). */
async function grenzeAendern(page: Page, kind: HubKind): Promise<void> {
	const reiter = await schrittWetter(page, kind);
	const zeile = reiter.getByTestId(WT.zeile(METRIK));
	await expect(zeile, `Messaufbau: Zeile ${METRIK} fehlt in der Vorlage`).toBeVisible();
	await zeile.getByTestId(WT.grenzenAendern(METRIK)).click();
	await zeile.getByTestId(WT.grenze(METRIK, 'upper', 'orange')).fill(String(A_WERT));
	await zeile.getByTestId(WT.grenzenAendern(METRIK)).click();
}

const metrikenIn = (corridors: Json[]): string[] => corridors.map((c: Json) => String(c.metric));
const orangeVon = (o: Json): unknown => o?.display_config?.ampel?.metrics?.[METRIK]?.upper?.orange;

// ── AC-43 / AC-45: Vorbelegung beim Anlegen, Desktop und mobil, je Art ──────────────────────
for (const kind of HUB_KINDS) {
	test(`AC-43/AC-45 (${kind}): Durchklicken mit Breitenwechsel — genau ein POST, corridors vorbelegt, keine Metrik doppelt`, async ({ page }) => {
		const posts = postZaehler(page, kind);
		await anlegenPflicht(page, kind, { name: name(kind, 'breite'), viewport: DESKTOP });
		await schrittWetter(page, kind);
		// Breitenwechsel mitten im Anlegen (Fenster gedreht): Desktop → mobil → Desktop.
		await page.setViewportSize(MOBIL);
		await expect(ANLEGE_SEL[kind].mobilFooter(page)).toBeVisible({ timeout: 10_000 });
		await page.setViewportSize(DESKTOP);
		await durchklicken(page, kind);
		const id = await anlegen(page, kind, ANLEGE_SEL[kind].abschluss(page));
		expect(posts.length, 'AC-45: Anlege-POST nicht genau einmal').toBe(1);

		const gesendet = posts[0].postDataJSON() as Json;
		const corridors = (gesendet.corridors ?? []) as Json[];
		expect(corridors.length, 'AC-43: Anlege-POST ohne vorbelegte Wertebereiche').toBeGreaterThan(0);
		const metriken = metrikenIn(corridors);
		expect(new Set(metriken).size, `AC-45: Metrik doppelt vorbelegt: ${metriken.join(', ')}`).toBe(metriken.length);
		expect(metrikenIn((await lies(page.request, kind, id)).corridors ?? []).sort(), 'gespeichert = gesendet').toEqual([...metriken].sort());
	});

	test(`AC-43 (${kind}): „Mit Standardwerten speichern" traegt dieselben corridors wie der durchgeklickte Weg`, async ({ page }) => {
		await anlegenPflicht(page, kind, { name: name(kind, 'durch'), viewport: DESKTOP });
		await durchklicken(page, kind);
		const durch = await lies(page.request, kind, await anlegen(page, kind, ANLEGE_SEL[kind].abschluss(page)));

		await anlegenPflicht(page, kind, { name: name(kind, 'std'), viewport: DESKTOP });
		const std = await lies(page.request, kind, await anlegen(page, kind, ANLEGE_SEL[kind].standardwerte(page)));

		expect((std.corridors ?? []).length, 'AC-43: Standardwerte-Objekt ohne Wertebereiche').toBeGreaterThan(0);
		expect(std.corridors, 'AC-43: Standardwerte und Durchklicken belegen verschieden vor').toEqual(durch.corridors);
	});
}

test('AC-43 (route, mobil): Standardwerte-Knopf in der unteren Leiste wird frei und traegt corridors', async ({ page }) => {
	await anlegenPflicht(page, 'route', { name: name('route', 'mobil'), mobil: true, viewport: MOBIL });
	const knopf = page.locator('[data-testid="tn-mobile-footer"] [data-testid="tn-mobile-standardwerte"]');
	const posts = postZaehler(page, 'route');
	const trip = await lies(page.request, 'route', await anlegen(page, 'route', knopf));
	expect(posts.length).toBe(1);
	expect((trip.corridors ?? []).length, 'AC-43: mobiler Standardwerte-Trip ohne Wertebereiche').toBeGreaterThan(0);
});

test('AC-43 (route): ohne Wetter-Metriken wird „Mit Standardwerten speichern" trotzdem frei', async ({ page }) => {
	await anlegenPflicht(page, 'route', { name: name('route', 'leer'), viewport: DESKTOP });
	const reiter = await schrittWetter(page, 'route');
	// Alle Metrik-Zeilen aus dem Briefing nehmen — danach ist nichts mehr vorzubelegen.
	const entfernen = reiter.locator('[data-testid^="wetter-zeile-entfernen-"]:visible');
	for (let i = 0; i < 60 && (await entfernen.count()) > 0; i++) await entfernen.first().click();
	await expect(entfernen, 'Messaufbau: es stehen noch Metriken im Briefing').toHaveCount(0);
	await expect(ANLEGE_SEL.route.standardwerte(page), 'AC-43: Standardwerte bleibt ohne Metriken gesperrt (Deadlock)').toBeEnabled({
		timeout: 15_000
	});
});

// ── AC-44: Orts-Briefing — Schritt verlassen und wieder betreten belegt nicht erneut vor ────
test('AC-44 (vergleich): Schritt Wetter verlassen und wieder betreten — Wertebereiche bleiben, ein POST', async ({ page }) => {
	const posts = postZaehler(page, 'vergleich');
	await anlegenPflicht(page, 'vergleich', { name: name('vergleich', 'zurueck'), viewport: DESKTOP });
	await grenzeAendern(page, 'vergleich');
	await ANLEGE_SEL.vergleich.reiter(page, 'orte').click();
	await schrittWetter(page, 'vergleich');
	await ANLEGE_SEL.vergleich.reiter(page, 'zustellung').click();
	const preset = await lies(page.request, 'vergleich', await anlegen(page, 'vergleich', ANLEGE_SEL.vergleich.abschluss(page)));
	expect(posts.length, 'AC-44: Anlege-POST nicht genau einmal').toBe(1);
	const metriken = metrikenIn(preset.corridors ?? []);
	expect(metriken.length, 'AC-44: Orts-Briefing ohne vorbelegte Wertebereiche').toBeGreaterThan(0);
	expect(new Set(metriken).size, `AC-44: nach dem Zurueckgehen doppelt vorbelegt: ${metriken.join(', ')}`).toBe(metriken.length);
	expect(orangeVon(preset), 'AC-44: die geaenderte Grenze ging beim Reiterwechsel verloren').toBe(A_WERT);
});

// ── AC-46: zwei Nutzer, Trip und Orts-Briefing ─────────────────────────────────────────────
for (const kind of HUB_KINDS) {
	test(`AC-46 (${kind}): A mit geaenderten Grenzen, B mit Standardwerten — jeder nur seine Werte, B sieht A nicht`, async ({ page, browser }) => {
		// Nutzer A (Login aus beforeEach): Grenze aendern, durchklicken, speichern.
		await anlegenPflicht(page, kind, { name: name(kind, 'A'), viewport: DESKTOP });
		await grenzeAendern(page, kind);
		await ANLEGE_SEL[kind].reiter(page, 'zustellung').click();
		const idA = await anlegen(page, kind, ANLEGE_SEL[kind].abschluss(page));
		const vorherA = await lies(page.request, kind, idA);
		expect(orangeVon(vorherA), 'Messaufbau: A hat die Grenze nicht gespeichert').toBe(A_WERT);
		expect((vorherA.corridors ?? []).length, 'AC-43: A ohne vorbelegte Wertebereiche').toBeGreaterThan(0);

		// Nutzer B: eigenes, bestaetigtes Konto in einem eigenen Browser-Kontext.
		const gast = await browser.newContext({
			baseURL: test.info().project.use.baseURL,
			storageState: { cookies: [], origins: [] },
			serviceWorkers: 'block',
			httpCredentials: test.info().project.use.httpCredentials
		});
		const kennwort = wegwerfPasswort();
		try {
			// meldet B im Gast-Kontext an (Sitzung gilt fuer gast.request UND die Seiten des Kontexts).
			await registriereBestaetigtenZweitnutzer(page.request, gast.request, `e2e4amandant${kind}${Date.now()}`, kennwort);
			const seiteB = await gast.newPage();
			await anlegenPflicht(seiteB, kind, { name: name(kind, 'B'), viewport: DESKTOP });
			const idB = await anlegen(seiteB, kind, ANLEGE_SEL[kind].standardwerte(seiteB), false);
			const objB = await lies(gast.request, kind, idB);

			// B: eigene Vorbelegung, keine Werte von A.
			expect((objB.corridors ?? []).length, 'AC-46: B ohne vorbelegte Wertebereiche').toBeGreaterThan(0);
			expect(orangeVon(objB), 'AC-46: Grenze von A steht bei B').not.toBe(A_WERT);
			expect(objB.id).not.toBe(idA);

			// A unveraendert (Antwort des Kontos A).
			expect(await lies(page.request, kind, idA), 'AC-46: Objekt von A veraendert').toEqual(vorherA);

			// B liest A's Objekt nicht, es steht nicht in B's Liste — und umgekehrt.
			const fremd = await gast.request.get(`${LISTE[kind]}/${idA}`);
			expect([403, 404], `B liest A's Objekt: HTTP ${fremd.status()}`).toContain(fremd.status());
			expect(JSON.stringify(await (await gast.request.get(LISTE[kind])).json()), 'AC-46: A in B-Liste').not.toContain(idA);
			expect(JSON.stringify(await (await page.request.get(LISTE[kind])).json()), 'AC-46: B in A-Liste').not.toContain(idB);
		} finally {
			await gast.request.post('/api/auth/account/delete', { data: { password: kennwort } }).catch(() => {});
			await gast.close();
		}
	});
}

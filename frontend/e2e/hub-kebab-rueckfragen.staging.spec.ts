// E2E (Staging) — Issue #3442 (S5c aus #2797, Epic #2791): Rückfragen im Kebab-Menü (Archivieren, Löschen)
// in Trip- und Orts-Vergleich-Hub. Spec: docs/specs/modules/feat_3442_kebab_rueckfragen.md — AC-1 bis AC-13, AC-14 (EN).
// AC-15 (Abschnitte gefunden) belegt der Elementlisten-Abgleich elementliste-abgleich.staging.spec.ts.
//
// Läuft NICHT im PR-CI, sondern in /e2e-verify bzw. /60-validate nach Push und Staging-Deploy:
//   cd frontend && npx playwright test --config playwright.3442-kebab.staging.config.ts
// Umgebung (nie im Klartext ausgeben): GZ_AUTH_USER/GZ_AUTH_PASS = Prüfkonto (GZ_PRUEFKONTO_* aus der Staging-.env),
// optional GZ_VALIDATOR_* (nginx). Das Prüfkonto legt je Fall EIGENE Abos an (E2E-GZ--Präfix) und löscht nur diese.

import { test, expect, type Page, type Request, type Cookie, type Locator } from '@playwright/test';
import { HUB_KINDS, HUB_SEL, createTestLocation, hubApiPath, openHub, seedHub, type HubKind, type SeededHub } from './helpers';

test.describe.configure({ mode: 'serial' });

// Ein Login je Lauf (Login-Bremse der Go-API, siehe hub-send-menue.staging.spec.ts).
let sitzung: Cookie[] = [];
let orte: string[] = [];

test.beforeAll(async ({ browser }) => {
	const user = process.env.GZ_AUTH_USER;
	const pass = process.env.GZ_AUTH_PASS;
	expect(user && pass, 'Vorbedingung: GZ_AUTH_USER/GZ_AUTH_PASS (Prüfkonto) gesetzt').toBeTruthy();
	const ctx = await browser.newContext({ baseURL: test.info().project.use.baseURL, ignoreHTTPSErrors: true });
	const login = await ctx.request.post('/api/auth/login', { data: { username: user, password: pass } });
	expect(login.ok(), `Login HTTP ${login.status()}`).toBeTruthy();
	sitzung = (await ctx.storageState()).cookies as Cookie[];
	// Der Orts-Vergleich braucht zwei eigene Orte des Prüfkontos (sonst Entwurf).
	orte = [(await createTestLocation(ctx.request)).id, (await createTestLocation(ctx.request)).id];
	await ctx.close();
});

test.beforeEach(async ({ page }) => {
	await page.context().addCookies(sitzung);
});

test.afterAll(async ({ browser }) => {
	const ctx = await browser.newContext({ baseURL: test.info().project.use.baseURL, ignoreHTTPSErrors: true });
	await ctx.addCookies(sitzung);
	for (const id of orte) await ctx.request.delete(`/api/locations/${encodeURIComponent(id)}`).catch(() => {});
	await ctx.request.post('/api/auth/logout').catch(() => {});
	await ctx.close();
});

// ── Werkzeuge ────────────────────────────────────────────────────────────────

async function anlegen(page: Page, kind: HubKind, archiviert = false): Promise<SeededHub & { name: string }> {
	const hub = await seedHub(page.request, kind, kind === 'vergleich' ? { extra: { location_ids: orte } } : {});
	if (archiviert) expect((await page.request.patch(`${hubApiPath(kind, hub.id)}/state`, { data: { archived: true } })).ok()).toBeTruthy();
	const stand = await page.request.get(hubApiPath(kind, hub.id));
	return { ...hub, name: String(((await stand.json()) as { name: string }).name) };
}

/** Schreibende Abrufe (alles außer GET) auf genau dieses Abo. */
function schreibAbrufe(page: Page, kind: HubKind, id: string): Request[] {
	const pfad = hubApiPath(kind, id);
	const liste: Request[] = [];
	page.on('request', (r) => {
		if (r.method() !== 'GET' && new URL(r.url()).pathname.startsWith(pfad)) liste.push(r);
	});
	return liste;
}

const kebab = (page: Page) => page.locator('[data-testid="subscription-kebab"]:visible').first();
const menueListe = (page: Page) => page.locator('[data-abschnitt="kebab-menue"]:visible');
const rueckfrage = (page: Page, art: 'loeschen' | 'archivieren') => page.locator(`[data-abschnitt="kebab-bestaetigung-${art}"]:visible`);
const meldung = (page: Page) => page.locator('[data-testid="hub-aktion-meldung"]:visible');
const fehler = (page: Page) => page.locator('[data-testid="trip-detail-action-error"]:visible, [data-testid="compare-hub-aktion-fehler"]:visible');
const status = (page: Page) => page.locator('[data-testid="trip-detail-status-badge"]:visible').first();
const listenPfad = (kind: HubKind) => (kind === 'route' ? '/trips' : '/compare');

async function waehle(page: Page, id: string): Promise<void> {
	await kebab(page).click();
	await expect(menueListe(page)).toBeVisible();
	await menueListe(page).getByTestId(`subscription-action-${id}`).click();
}

/** Seiten-Marke: verschwindet bei einem Neuladen (AC-5/AC-10 „kein Reload“). */
const setzeMarke = (page: Page) => page.evaluate(() => ((window as unknown as { __gz3442: number }).__gz3442 = 1));
const marke = (page: Page) => page.evaluate(() => (window as unknown as { __gz3442?: number }).__gz3442);

/** WCAG-Kontrast Text/Fläche eines Elements (Flächen-Stapel bis zur ersten deckenden Farbe, per Canvas gemischt). */
function kontrast(el: Locator): Promise<number> {
	return el.evaluate((knoten) => {
		const g = document.createElement('canvas').getContext('2d', { willReadFrequently: true })!;
		const pixel = (farben: string[]) => {
			g.clearRect(0, 0, 1, 1);
			g.fillStyle = '#ffffff';
			g.fillRect(0, 0, 1, 1);
			for (const f of farben) {
				g.fillStyle = f;
				g.fillRect(0, 0, 1, 1);
			}
			return [...g.getImageData(0, 0, 1, 1).data];
		};
		const stapel: string[] = [];
		for (let x: Element | null = knoten; x; x = x.parentElement) {
			const b = getComputedStyle(x).backgroundColor;
			stapel.unshift(b);
			g.clearRect(0, 0, 1, 1);
			g.fillStyle = b;
			g.fillRect(0, 0, 1, 1);
			if (g.getImageData(0, 0, 1, 1).data[3] === 255) break;
		}
		const lum = ([r, gr, b]: number[]) => {
			const k = (c: number) => ((c /= 255) <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);
			return 0.2126 * k(r) + 0.7152 * k(gr) + 0.0722 * k(b);
		};
		const a = lum(pixel([...stapel, getComputedStyle(knoten).color]));
		const b = lum(pixel(stapel));
		return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
	});
}

// ── Desktop ──────────────────────────────────────────────────────────────────

for (const kind of HUB_KINDS) {
	test(`AC-1/AC-6/AC-13 (${kind}): „Löschen …“ fragt im Menü nach; „Abbrechen“ führt zur Liste zurück, ohne Wirkung`, async ({ page }) => {
		const hub = await anlegen(page, kind);
		try {
			await openHub(page, kind, hub.id);
			const schreib = schreibAbrufe(page, kind, hub.id);
			await waehle(page, 'delete');
			const r = rueckfrage(page, 'loeschen');
			await expect(r).toBeVisible();
			await expect(r).toContainText('Löschen?');
			await expect(r).toContainText(`„${hub.name}“ wird endgültig gelöscht. Briefings und Alarme hören sofort auf.`);
			await expect(r.getByTestId('kebab-rueckfrage-bestaetigen')).toHaveText('Endgültig löschen');
			await expect(kebab(page)).toHaveAttribute('aria-expanded', 'true');
			await expect(page.getByRole('dialog')).toHaveCount(0);
			expect(schreib, 'vor der Bestätigung geht nichts an den Server').toEqual([]);

			await r.getByTestId('kebab-rueckfrage-abbrechen').click();
			await expect(r).toHaveCount(0);
			await expect(menueListe(page).getByRole('menuitem')).toHaveText(['Pausieren', 'Archivieren …', 'Löschen …']);
			await expect(kebab(page)).toHaveAttribute('aria-expanded', 'true');
			await expect(meldung(page)).toHaveCount(0);
			expect(schreib).toEqual([]);
			expect((await page.request.get(hubApiPath(kind, hub.id))).ok(), 'Abo besteht noch').toBeTruthy();
			await page.keyboard.press('Escape');
		} finally {
			await hub.aufraeumen();
		}
	});

	test(`AC-7 (${kind}): Escape und Außenklick schließen ohne Wirkung; Wiederöffnen zeigt die Liste`, async ({ page }) => {
		const hub = await anlegen(page, kind);
		try {
			await openHub(page, kind, hub.id);
			const schreib = schreibAbrufe(page, kind, hub.id);
			await waehle(page, 'delete');
			await expect(rueckfrage(page, 'loeschen')).toBeVisible();
			await page.keyboard.press('Escape');
			await expect(kebab(page)).toHaveAttribute('aria-expanded', 'false');
			await kebab(page).click();
			await expect(menueListe(page)).toBeVisible();
			await expect(rueckfrage(page, 'loeschen')).toHaveCount(0);

			await menueListe(page).getByTestId('subscription-action-archive').click();
			await expect(rueckfrage(page, 'archivieren')).toBeVisible();
			await page.mouse.click(5, 600);
			await expect(kebab(page)).toHaveAttribute('aria-expanded', 'false');
			await kebab(page).click();
			await expect(menueListe(page)).toBeVisible();
			await expect(rueckfrage(page, 'archivieren')).toHaveCount(0);
			await page.keyboard.press('Escape');
			expect(schreib).toEqual([]);
		} finally {
			await hub.aufraeumen();
		}
	});

	test(`AC-8 (${kind}): nur Tastatur erreicht Rückfrage und Knöpfe; Fokus in der Rückfrage; Gefahrknopf WCAG-AA`, async ({ page }) => {
		const hub = await anlegen(page, kind);
		try {
			await openHub(page, kind, hub.id);
			const schreib = schreibAbrufe(page, kind, hub.id);
			const fokus = () => page.evaluate(() => document.activeElement?.getAttribute('data-testid') ?? '');
			await kebab(page).focus();
			await page.keyboard.press('Enter');
			await expect(menueListe(page)).toBeVisible();
			for (let i = 0; i < 6 && (await fokus()) !== 'subscription-action-delete'; i++) await page.keyboard.press('ArrowDown');
			expect(await fokus(), '„Löschen …“ per Pfeiltaste erreichbar').toBe('subscription-action-delete');
			await page.keyboard.press('Enter');
			await expect(rueckfrage(page, 'loeschen')).toBeVisible();
			await expect.poll(fokus, { message: 'Fokus liegt nach dem Umschalten in der Rückfrage' }).toBe('kebab-rueckfrage-abbrechen');
			await page.keyboard.press('ArrowUp');
			await expect.poll(fokus).toBe('kebab-rueckfrage-bestaetigen');
			expect(await kontrast(rueckfrage(page, 'loeschen').getByTestId('kebab-rueckfrage-bestaetigen')), 'Kontrast „Endgültig löschen“').toBeGreaterThanOrEqual(4.5);
			await page.keyboard.press('Escape');
			expect(schreib).toEqual([]);
		} finally {
			await hub.aufraeumen();
		}
	});

	test(`AC-3/AC-4/AC-5 (${kind}): „Archivieren …“ fragt mit Namen nach; Bestätigen archiviert auf der Seite, ohne Konflikt`, async ({ page }) => {
		const hub = await anlegen(page, kind);
		try {
			await openHub(page, kind, hub.id);
			const pfad = new URL(page.url()).pathname;
			await setzeMarke(page);
			const schreib = schreibAbrufe(page, kind, hub.id);
			await waehle(page, 'archive');
			const r = rueckfrage(page, 'archivieren');
			await expect(r).toContainText('Archivieren?');
			await expect(r).toContainText(`„${hub.name}“ verschwindet aus der Liste.`);
			expect(schreib).toEqual([]);

			const patch = page.waitForResponse((x) => x.request().method() === 'PATCH' && new URL(x.url()).pathname === `${hubApiPath(kind, hub.id)}/state`);
			await r.getByTestId('kebab-rueckfrage-bestaetigen').click();
			const antwort = await patch;
			expect(antwort.ok()).toBeTruthy();
			expect(antwort.request().postDataJSON()).toEqual({ archived: true });
			await expect(meldung(page)).toHaveText('Archiviert. Im Archiv kannst du es reaktivieren.');
			await expect(status(page)).toHaveAttribute('data-status', 'archived');
			expect(new URL(page.url()).pathname, 'bleibt auf der Seite').toBe(pfad);
			expect(await marke(page), 'kein Neuladen').toBe(1);

			// AC-5: der nächste Schreibvorgang trägt den frischen Stempel (kein Konflikt-Banner).
			const kopf = HUB_SEL[kind].kopf;
			const put = page.waitForResponse((x) => x.request().method() === 'PUT' && new URL(x.url()).pathname === hubApiPath(kind, hub.id));
			await page.locator(`[data-testid="${kopf}-name-edit-toggle"]:visible`).click();
			await page.locator(`[data-testid="${kopf}-name-edit"]:visible`).fill(`${hub.name} B`);
			await page.locator(`[data-testid="${kopf}-name-save"]:visible`).click();
			expect((await put).status(), 'Umbenennen nach dem Archivieren ohne 412').toBe(200);
			await expect(page.locator('[data-testid="save-indicator"]')).not.toHaveAttribute('data-state', 'conflict');
		} finally {
			await hub.aufraeumen();
		}
	});

	test(`AC-10 (${kind}): „Reaktivieren“ ohne Rückfrage, Status aktiv ohne Neuladen, Meldung`, async ({ page }) => {
		const hub = await anlegen(page, kind, true);
		try {
			await openHub(page, kind, hub.id);
			await setzeMarke(page);
			const patch = page.waitForResponse((x) => x.request().method() === 'PATCH' && new URL(x.url()).pathname === `${hubApiPath(kind, hub.id)}/state`);
			await waehle(page, 'unarchive');
			expect((await patch).request().postDataJSON()).toEqual({ archived: false });
			await expect(page.locator('[data-abschnitt^="kebab-bestaetigung-"]')).toHaveCount(0);
			await expect(meldung(page)).toHaveText('Reaktiviert.');
			await expect(status(page)).not.toHaveAttribute('data-status', 'archived');
			expect(await marke(page), 'kein Neuladen').toBe(1);
		} finally {
			await hub.aufraeumen();
		}
	});

	test(`AC-11 (${kind}): Pausieren und Fortsetzen ohne Rückfrage, mit Meldung`, async ({ page }) => {
		const hub = await anlegen(page, kind);
		try {
			await openHub(page, kind, hub.id);
			await waehle(page, 'pause');
			await expect(meldung(page)).toHaveText('Pausiert. Bis ‚Fortsetzen‘ kommen keine Briefings und Alarme.', { timeout: 15_000 });
			await expect(status(page)).toHaveAttribute('data-status', 'paused');
			await waehle(page, 'resume');
			await expect(meldung(page)).toHaveText('Fortgesetzt. Das nächste Briefing kommt wie geplant.', { timeout: 15_000 });
		} finally {
			await hub.aufraeumen();
		}
	});

	test(`AC-12 (${kind}): Löschen ohne Verbindung ⇒ Meldung, Seite bleibt, Abo bleibt`, async ({ page }) => {
		const hub = await anlegen(page, kind);
		try {
			await openHub(page, kind, hub.id);
			const pfad = new URL(page.url()).pathname;
			await page.route(`**${hubApiPath(kind, hub.id)}`, (route) => (route.request().method() === 'DELETE' ? route.abort('failed') : route.continue()));
			await waehle(page, 'delete');
			await rueckfrage(page, 'loeschen').getByTestId('kebab-rueckfrage-bestaetigen').click();
			await expect(fehler(page)).toHaveText('Löschen hat nicht geklappt: keine Verbindung zum Server. Versuch es gleich noch einmal.');
			expect(new URL(page.url()).pathname).toBe(pfad);
			expect((await page.request.get(hubApiPath(kind, hub.id))).ok(), 'Abo besteht noch').toBeTruthy();
		} finally {
			await hub.aufraeumen();
		}
	});

	test(`AC-2 (${kind}): „Endgültig löschen“ löscht genau einmal und führt zur Liste`, async ({ page }) => {
		const hub = await anlegen(page, kind);
		try {
			await openHub(page, kind, hub.id);
			const schreib = schreibAbrufe(page, kind, hub.id);
			await waehle(page, 'delete');
			await rueckfrage(page, 'loeschen').getByTestId('kebab-rueckfrage-bestaetigen').click();
			await page.waitForURL((u) => u.pathname.replace(/\/$/, '') === listenPfad(kind), { timeout: 15_000 });
			expect(schreib.filter((r) => r.method() === 'DELETE').length, 'genau ein DELETE').toBe(1);
			expect((await page.request.get(hubApiPath(kind, hub.id))).status()).toBe(404);
			await expect(page.getByText(hub.name, { exact: true })).toHaveCount(0);
		} finally {
			await hub.aufraeumen().catch(() => {});
		}
	});
}

test('AC-14 (route): Rückfrage und Menülabels englisch aus dem Katalog', async ({ page }) => {
	const vorher = ((await (await page.request.get('/api/auth/profile')).json()) as { language?: string }).language ?? 'de';
	const hub = await anlegen(page, 'route');
	try {
		expect((await page.request.put('/api/auth/profile', { data: { language: 'en' } })).ok()).toBeTruthy();
		await openHub(page, 'route', hub.id);
		await kebab(page).click();
		await expect(menueListe(page).getByRole('menuitem')).toHaveText(['Pause', 'Archive …', 'Delete …']);
		await menueListe(page).getByTestId('subscription-action-delete').click();
		const r = rueckfrage(page, 'loeschen');
		await expect(r).toContainText('Delete?');
		await expect(r).toContainText(`“${hub.name}” will be deleted permanently.`);
		await expect(r.getByTestId('kebab-rueckfrage-bestaetigen')).toHaveText('Delete permanently');
		await expect(r.getByTestId('kebab-rueckfrage-abbrechen')).toHaveText('Cancel');
		await page.keyboard.press('Escape');
	} finally {
		await page.request.put('/api/auth/profile', { data: { language: vorher } });
		await hub.aufraeumen();
	}
});

// ── Mobil (≤899 px) ──────────────────────────────────────────────────────────

test.describe('AC-9: Rückfrage im Aktionsblatt (390 px)', () => {
	test.use({ viewport: { width: 390, height: 844 } });
	for (const kind of HUB_KINDS) {
		test(`AC-9 (${kind}): Blatt fragt nach, „Abbrechen“ führt zurück, schließt erst nach Bestätigung; Zeilen ≥ 44 px`, async ({ page }) => {
			const hub = await anlegen(page, kind);
			try {
				await openHub(page, kind, hub.id);
				const schreib = schreibAbrufe(page, kind, hub.id);
				await kebab(page).click();
				const blatt = page.locator('[data-snap="half"]:visible');
				await expect(blatt).toBeVisible();
				for (const z of await blatt.locator('[data-testid^="subscription-action-"]').all())
					expect((await z.boundingBox())!.height, 'Aktionszeile ≥ 44 px').toBeGreaterThanOrEqual(44);

				await blatt.getByTestId('subscription-action-delete').click();
				const r = blatt.locator('[data-abschnitt="kebab-bestaetigung-loeschen"]');
				await expect(r).toContainText(`„${hub.name}“ wird endgültig gelöscht.`);
				for (const k of ['kebab-rueckfrage-bestaetigen', 'kebab-rueckfrage-abbrechen'])
					expect((await r.getByTestId(k).boundingBox())!.height, `${k} ≥ 44 px`).toBeGreaterThanOrEqual(44);
				await r.getByTestId('kebab-rueckfrage-abbrechen').click();
				await expect(blatt.getByTestId('subscription-action-delete')).toBeVisible();
				expect(schreib).toEqual([]);

				await blatt.getByTestId('subscription-action-archive').click();
				await expect(blatt).toBeVisible();
				expect(schreib, 'vor der Bestätigung kein Archivieren').toEqual([]);
				const patch = page.waitForResponse((x) => x.request().method() === 'PATCH' && new URL(x.url()).pathname === `${hubApiPath(kind, hub.id)}/state`);
				await blatt.getByTestId('kebab-rueckfrage-bestaetigen').click();
				expect((await patch).ok()).toBeTruthy();
				await expect(blatt).toHaveCount(0);
				await expect(meldung(page)).toHaveText('Archiviert. Im Archiv kannst du es reaktivieren.');
			} finally {
				await hub.aufraeumen();
			}
		});
	}
});

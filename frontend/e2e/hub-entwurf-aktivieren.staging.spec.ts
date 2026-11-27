// E2E (Staging) — Issue #3443 (S5d aus #2797, Epic #2791): Entwurf aktivieren über Knopf im Kopf und Kebab,
// Trip-Hub und Orts-Vergleich-Hub. Spec: docs/specs/modules/feat_3443_entwurf_aktivieren.md —
// AC-1 bis AC-4, AC-6, AC-7, AC-9, AC-10, AC-11, AC-12 (Browser-Anteil). AC-5 (nur Name fehlt) lässt sich über
// die Oberfläche nicht anlegen und ist im Kern-Test belegt; AC-13 gleicht unten die Einträge der Elementliste
// (docs/context/einstellungen_neu/elementliste.json: kopf und kebab-menue des Entwurfs) mit einem selbst
// angelegten Entwurf gegen die Seite ab.
//
// Läuft NICHT im PR-CI, sondern in /e2e-verify bzw. /60-validate nach Push und Staging-Deploy.
// Config legt der Developer an (Vorlage playwright.3442-kebab.staging.config.ts, testMatch
// /hub-entwurf-aktivieren\.staging\.spec\.ts/):
//   cd frontend && npx playwright test --config playwright.3443-aktivieren.staging.config.ts
// Umgebung (nie im Klartext ausgeben): GZ_AUTH_USER/GZ_AUTH_PASS = Prüfkonto (GZ_PRUEFKONTO_* aus der Staging-.env),
// optional GZ_VALIDATOR_* (nginx). Der Prüfkonto-Seed legt Abos aktiv an — deshalb legt dieser Test seine Entwürfe
// SELBST per API an (Trip mit einer Etappe ohne Datum, Orts-Vergleich ohne Orte, E2E-GZ--Präfix) und löscht nur diese.
// Der Wechsel auf „aktiv“ wird über die Oberfläche herbeigeführt (Datum im Reiter Etappen, Ort im Reiter Orte),
// weil er innerhalb der geöffneten Sitzung passieren muss (Spec Punkt 8).

import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { test, expect, type Page, type Cookie, type Locator } from '@playwright/test';
import {
	HUB_KINDS,
	HUB_KOPF_SEL,
	createTestLocation,
	hubApiPath,
	openHub,
	oeffneEtappenEditor,
	seedHub,
	tippeDatum,
	type HubKind,
	type SeededHub
} from './helpers';

test.describe.configure({ mode: 'serial' });

type Lang = 'de' | 'en';
const SPRACHEN: Lang[] = ['de', 'en'];
const VIEWPORTS = { desktop: { width: 1280, height: 900 }, mobil: { width: 390, height: 844 } } as const;

// Soll-Texte aus dem Katalog (ADR-0104) — der EN-Wortlaut der Hinweise steht nur dort.
const HIER = path.dirname(fileURLToPath(import.meta.url));
const katalog = (lang: Lang, bereich: string): Record<string, string> =>
	JSON.parse(readFileSync(path.join(HIER, '..', 'src', 'lib', 'i18n', 'messages', lang, `${bereich}.json`), 'utf8'));
const TEXT = (lang: Lang) => {
	const a = katalog(lang, 'aktionen');
	const v = katalog(lang, 'vergleich');
	return {
		knopf: a['aktionen.kopf.aktivieren'],
		loeschen: a['aktionen.kebab.menue_delete'],
		hinweis: { route: a['aktionen.aktivieren.hinweis_etappen_datum'], vergleich: a['aktionen.aktivieren.hinweis_orte'] } as Record<HubKind, string>,
		erfolg: a['aktionen.aktivieren.erfolg'],
		erfolgMitZeit: a['aktionen.aktivieren.erfolg_mit_zeit'],
		setup: v['vergleich.hub.setup_abschliessen']
	};
};
const ZIEL_TAB: Record<HubKind, string> = { route: 'etappen', vergleich: 'orte' };

// Ein Login je Lauf (Login-Bremse der Go-API, Muster hub-kebab-rueckfragen.staging.spec.ts).
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
	await ctx.close();
});

test.beforeEach(async ({ page }) => {
	await page.context().addCookies(sitzung);
});

test.afterEach(async ({ page }) => {
	await page.request.put('/api/auth/profile', { data: { language: 'de' } }).catch(() => {});
	for (const id of orte) await page.request.delete(`/api/locations/${encodeURIComponent(id)}`).catch(() => {});
	orte = [];
});

test.afterAll(async ({ browser }) => {
	const ctx = await browser.newContext({ baseURL: test.info().project.use.baseURL, ignoreHTTPSErrors: true });
	await ctx.addCookies(sitzung);
	await ctx.request.post('/api/auth/logout').catch(() => {});
	await ctx.close();
});

// ── Werkzeuge ────────────────────────────────────────────────────────────────

const wp = (id: string, lat: number, elevation_m: number) => ({ id, name: id, lat, lon: 9.0, elevation_m });

async function sprache(page: Page, lang: Lang): Promise<void> {
	const res = await page.request.put('/api/auth/profile', { data: { language: lang } });
	expect(res.ok(), `Sprache ${lang} setzen: HTTP ${res.status()}`).toBeTruthy();
}

/** Eigener Entwurf: Trip mit einer Etappe OHNE Datum; Orts-Vergleich OHNE Orte (Zeitplan daily aus dem Seed). */
async function entwurf(page: Page, kind: HubKind): Promise<SeededHub> {
	const extra =
		kind === 'route'
			? { stages: [{ id: 'e1', name: 'Tag 1', waypoints: [wp('a', 42.0, 800), wp('b', 42.04, 1200)] }] }
			: { location_ids: [] };
	const hub = await seedHub(page.request, kind, { extra });
	const stand = await (await page.request.get(hubApiPath(kind, hub.id))).json();
	if (kind === 'route') expect((stand.stages as Array<{ date?: string }>).every((s) => !s.date), 'Vorbedingung: Etappe ohne Datum').toBeTruthy();
	else expect(stand.location_ids, 'Vorbedingung: Vergleich ohne Orte').toEqual([]);
	return hub;
}

/** Alle schreibenden Abrufe (PUT/PATCH/POST/DELETE) an die API ab jetzt. */
function schreibAbrufe(page: Page): string[] {
	const liste: string[] = [];
	page.on('request', (r) => {
		const u = new URL(r.url());
		if (r.method() !== 'GET' && r.method() !== 'HEAD' && u.pathname.startsWith('/api/')) liste.push(`${r.method()} ${u.pathname}`);
	});
	return liste;
}

/** Abrufe von „nächstes Briefing“ ab jetzt. */
function naechstesAbrufe(page: Page): string[] {
	const liste: string[] = [];
	page.on('request', (r) => {
		const u = new URL(r.url());
		if (r.method() === 'GET' && u.pathname === '/api/next-briefings') liste.push(u.search);
	});
	return liste;
}

const sichtbar = (wo: Page | Locator, id: string): Locator => wo.locator(`[data-testid="${id}"]:visible`).first();
const pille = (page: Page) => sichtbar(page, 'trip-detail-status-badge');
const knopf = (page: Page) => sichtbar(sichtbar(page, HUB_KOPF_SEL.status), 'hub-kopf-aktivieren');
const meldung = (page: Page) => page.locator('[data-testid="hub-aktion-meldung"]:visible');
const kebab = (page: Page) => sichtbar(page, HUB_KOPF_SEL.kebab);

/** Öffnet das Kebab-Menü (Desktop) bzw. das Aktionsblatt (≤ 899 px) und liefert den Behälter der Einträge. */
async function oeffneMenue(page: Page): Promise<Locator> {
	await kebab(page).click();
	const mobil = (page.viewportSize()?.width ?? 1280) < 900;
	const behaelter = mobil ? page.locator('[data-snap="half"]:visible') : page.locator('[data-abschnitt="kebab-menue"]:visible');
	await expect(behaelter).toBeVisible();
	return behaelter;
}

/** Menü schließen: Desktop per Escape; das mobile Blatt hat keine Tastenbedienung, dort über „Schließen“. */
async function schliesseMenue(page: Page): Promise<void> {
	const mobil = (page.viewportSize()?.width ?? 1280) < 900;
	if (mobil) await page.locator('[data-snap="half"]:visible').getByTestId('sheet-close').click();
	else await page.keyboard.press('Escape');
	await expect(page.locator('[data-snap="half"]:visible, [data-abschnitt="kebab-menue"]:visible')).toHaveCount(0);
}

/** Texte der Menü-Einträge in Reihenfolge. */
async function eintraege(behaelter: Locator): Promise<string[]> {
	return (await behaelter.locator('[data-testid^="subscription-action-"]').allInnerTexts()).map((t) => t.trim());
}

// ── AC-1, AC-2, AC-3, AC-4, AC-6, AC-11, AC-12: Knopf, Menü, Klick (beide Hubs, DE/EN, Desktop/390 px) ───────

for (const kind of HUB_KINDS) {
	for (const lang of SPRACHEN) {
		for (const [vp, groesse] of Object.entries(VIEWPORTS) as Array<[keyof typeof VIEWPORTS, { width: number; height: number }]>) {
			test(`${kind} ${lang} ${vp}: Entwurf zeigt „Aktivieren“ neben der Pill und zuerst im Menü; Kopf und Menü nennen, was fehlt, ohne zu schreiben`, async ({ page }) => {
				const T = TEXT(lang);
				await page.setViewportSize(groesse);
				await sprache(page, lang);
				const hub = await entwurf(page, kind);
				try {
					await openHub(page, kind, hub.id);
					// AC-1: Pill Entwurf, daneben ein echter Akzent-Knopf
					await expect(pille(page), 'AC-1: Pill zeigt Entwurf').toHaveAttribute('data-status', 'draft');
					const k = knopf(page);
					await expect(k, 'AC-1: „Aktivieren“ neben der Pill').toBeVisible();
					await expect(k, 'AC-11: Knopftext aus dem Katalog').toHaveText(T.knopf);
					expect(await k.evaluate((el) => el.tagName), 'AC-1: Knopf, kein Link').toBe('BUTTON');
					expect(await k.getAttribute('href'), 'AC-1: kein href').toBeNull();
					await expect(k, 'AC-1: Akzent-Knopf').toHaveAttribute('data-variant', 'accent');
					await expect(k, 'Knopf im Sichtbereich (390 px)').toBeInViewport();

					// AC-2: Menü — „Aktivieren“ an erster Stelle, danach „Löschen …“
					const menue = await oeffneMenue(page);
					expect(await eintraege(menue), 'AC-2: Menü im Entwurf').toEqual([T.knopf, T.loeschen]);
					await schliesseMenue(page);

					// AC-3/AC-4: Klick auf den Kopf-Knopf — Hinweis, Reiter, kein Schreibzugriff, kein Neuladen
					await page.evaluate(() => ((window as unknown as { __gz3443: number }).__gz3443 = 1));
					const schreib = schreibAbrufe(page);
					await knopf(page).click();
					await expect(meldung(page), 'AC-3/AC-4: Hinweis über den Meldungsweg').toHaveText(T.hinweis[kind]);
					await expect(page, `AC-3/AC-4: Reiter ${ZIEL_TAB[kind]} geöffnet`).toHaveURL(new RegExp(`[?&]tab=${ZIEL_TAB[kind]}(&|#|$)`));
					await expect(page.locator('[role="tab"][data-state="active"]:visible').first()).toHaveAttribute('data-value', ZIEL_TAB[kind]);
					expect(await page.evaluate(() => (window as unknown as { __gz3443?: number }).__gz3443), 'Seite wurde neu geladen').toBe(1);
					await page.waitForLoadState('networkidle').catch(() => {});
					expect(schreib, 'AC-3/AC-4: kein Schreibzugriff beim Klick').toEqual([]);
					const kopfUrl = new URL(page.url()).search;

					// AC-6: derselbe Klick aus dem Menü — gleicher Hinweis, gleiche Stelle, kein Schreibzugriff
					await openHub(page, kind, hub.id);
					await expect(meldung(page)).toHaveCount(0);
					const schreib2 = schreibAbrufe(page);
					const m2 = await oeffneMenue(page);
					await m2.getByTestId('subscription-action-activate').click();
					await expect(meldung(page), 'AC-6: Menü nennt denselben Hinweis').toHaveText(T.hinweis[kind]);
					await expect(page).toHaveURL(new RegExp(`[?&]tab=${ZIEL_TAB[kind]}(&|#|$)`));
					expect(new URL(page.url()).search, 'AC-6: dieselbe Stelle wie der Kopf-Knopf').toBe(kopfUrl);
					await page.waitForLoadState('networkidle').catch(() => {});
					expect(schreib2, 'AC-6: kein Schreibzugriff aus dem Menü').toEqual([]);

					// Der Entwurf ist unverändert (nichts geschrieben)
					const stand = await (await page.request.get(hubApiPath(kind, hub.id))).json();
					if (kind === 'route') expect((stand.stages as Array<{ date?: string }>).every((s) => !s.date)).toBeTruthy();
					else expect(stand.location_ids).toEqual([]);
				} finally {
					await hub.aufraeumen();
				}
			});
		}
	}
}

// ── AC-7: Daten in der geöffneten Seite ergänzen ⇒ Pill aktiv, Meldung mit dem Termin der Zustellung ───────────

/** Erwarteter Meldungstext aus GET /api/next-briefings (Format der übrigen Anzeigen, nie erfunden). */
async function sollMeldung(page: Page, kind: HubKind, id: string, lang: Lang): Promise<RegExp> {
	const T = TEXT(lang);
	const param = kind === 'route' ? 'trip_id' : 'preset_id';
	const bereich = kind === 'route' ? 'trips' : 'compare';
	const res = await page.request.get(`/api/next-briefings?${param}=${encodeURIComponent(id)}`);
	expect(res.ok(), `next-briefings HTTP ${res.status()}`).toBeTruthy();
	const nb = ((await res.json()) as Record<string, Record<string, { at: string | null; local_time?: string; tz_abbr?: string }>>)[bereich]?.[id];
	const esc = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
	if (!nb || nb.at == null || !nb.local_time || !nb.tz_abbr) return new RegExp(`^${esc(T.erfolg)}$`);
	const [vor, nach] = T.erfolgMitZeit.split('{wann}');
	return new RegExp(`^${esc(vor)}.+ ${esc(nb.local_time)} \\(${esc(nb.tz_abbr)}\\)${esc(nach)}$`);
}

for (const kind of HUB_KINDS) {
	test(`${kind} DE desktop: AC-7 Entwurf über die Oberfläche vervollständigen ⇒ aktiv, „Aktiviert. Das erste Briefing kommt …“, genau ein Abruf`, async ({ page }) => {
		test.setTimeout(150_000);
		await page.setViewportSize(VIEWPORTS.desktop);
		await sprache(page, 'de');
		let ort: { id: string; name: string } | null = null;
		if (kind === 'vergleich') {
			ort = await createTestLocation(page.request, { lat: 47.26, lon: 11.39 });
			orte.push(ort.id);
		}
		const hub = await entwurf(page, kind);
		try {
			await openHub(page, kind, hub.id);
			await knopf(page).click();
			await expect(page).toHaveURL(new RegExp(`[?&]tab=${ZIEL_TAB[kind]}`));
			const abrufe = naechstesAbrufe(page);
			const pfad = hubApiPath(kind, hub.id);
			const gespeichert = page.waitForResponse((r) => r.request().method() === 'PUT' && new URL(r.url()).pathname === pfad && r.ok(), { timeout: 30_000 });
			if (kind === 'route') {
				// Heute (UTC, Regel deriveTripStatus) ⇒ der Trip läuft, Pill „aktiv“.
				await oeffneEtappenEditor(page);
				await tippeDatum(page, sichtbar(page, 'stage-date-field'), new Date().toISOString().slice(0, 10));
			} else {
				await sichtbar(page, 'hub-orte-add').click();
				await sichtbar(page, 'hub-orte-panel').getByRole('button', { name: new RegExp(ort!.name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')) }).click();
			}
			await gespeichert;
			await expect(pille(page), 'AC-7: Pill wechselt auf aktiv (ohne Neuladen)').toHaveAttribute('data-status', 'active', { timeout: 15_000 });
			await expect(page.locator('[data-testid="hub-kopf-aktivieren"]'), 'AC-1: Knopf verschwindet nach der Aktivierung').toHaveCount(0);
			await expect(meldung(page), 'AC-7: Meldung nach der Aktivierung').toHaveText(await sollMeldung(page, kind, hub.id, 'de'), { timeout: 15_000 });
			await expect(meldung(page)).not.toContainText('Zum Aktivieren');
			await page.waitForLoadState('networkidle').catch(() => {});
			const param = kind === 'route' ? 'trip_id' : 'preset_id';
			expect(abrufe, 'AC-7: genau ein Abruf von „nächstes Briefing“ nach dem Wechsel').toEqual([`?${param}=${hub.id}`]);
		} finally {
			await hub.aufraeumen();
		}
	});
}

// ── AC-9: bereits aktive Seite ⇒ kein Knopf, keine Meldung, kein Abruf vom Kopf ─────────────────────────────────

for (const kind of HUB_KINDS) {
	test(`${kind} DE desktop: AC-9 aktiver Hub — kein „Aktivieren“, keine „Aktiviert“-Meldung, kein Abruf von „nächstes Briefing“ beim Laden`, async ({ page }) => {
		await page.setViewportSize(VIEWPORTS.desktop);
		await sprache(page, 'de');
		const hub = await seedHub(page.request, kind, kind === 'route' ? { extra: { stages: [{ id: 's1', name: 'Tag 1', date: new Date().toISOString().slice(0, 10), waypoints: [wp('a', 42.0, 800), wp('b', 42.04, 1200)] }] } } : {});
		try {
			const abrufe = naechstesAbrufe(page);
			// Reiter Übersicht: deren Karte lädt „nächstes Briefing“ genau einmal (Bestand, #1969). Jeder Reiter
			// zeigt beim ersten Bild kurz die Übersicht (Startwert der Reiter), deshalb gibt es keinen Reiter ohne
			// diesen einen Abruf. Ein zweiter Abruf käme vom Kopf (Aktivierungs-Wechsel) und ist der Fehler.
			await openHub(page, kind, hub.id, { tab: 'uebersicht' });
			await page.waitForLoadState('networkidle').catch(() => {});
			await expect(pille(page)).toHaveAttribute('data-status', 'active');
			await expect(page.locator('[data-testid="hub-kopf-aktivieren"]')).toHaveCount(0);
			await page.waitForTimeout(1500);
			await expect(meldung(page)).toHaveCount(0);
			expect(abrufe, 'AC-9: nur der Abruf der Übersicht-Karte, keiner vom Kopf').toHaveLength(1);
			const menue = await oeffneMenue(page);
			expect(await eintraege(menue), 'AC-2: aktives Menü unverändert').toEqual(['Pausieren', 'Archivieren …', 'Löschen …']);
			await page.keyboard.press('Escape');
		} finally {
			await hub.aufraeumen();
		}
	});
}

// ── AC-10: „Setup abschließen“ im Vergleich-Entwurf bleibt auf dem Platz von „Test schicken“ ───────────────────

for (const lang of SPRACHEN) {
	test(`vergleich ${lang} desktop: AC-10 „Setup abschließen“ bleibt im Entwurf auf dem Platz von „Test schicken“`, async ({ page }) => {
		const T = TEXT(lang);
		await page.setViewportSize(VIEWPORTS.desktop);
		await sprache(page, lang);
		const hub = await entwurf(page, 'vergleich');
		try {
			await openHub(page, 'vergleich', hub.id);
			const leiste = sichtbar(page, HUB_KOPF_SEL.leiste);
			await expect(leiste.locator('[data-testid="subscription-hub-send"]'), 'AC-10: kein „Test schicken“ im Entwurf').toHaveCount(0);
			await expect(leiste.getByRole('button', { name: T.setup, exact: true }), 'AC-10: „Setup abschließen“ in der Leiste').toBeVisible();
			await expect(knopf(page), 'AC-1: „Aktivieren“ zusätzlich neben der Pill').toBeVisible();
		} finally {
			await hub.aufraeumen();
		}
	});
}

// ── AC-13: Elementliste (Soll aus dem Mockup) gegen die Seite mit einem selbst angelegten Entwurf ─────────────────
// Die Elementliste führt den Entwurf nur im Orte-Kontext (Mockup-Zustand „normal“). Trip und Orte teilen HubKopf und
// subscriptionActions (AC-12), deshalb gilt dasselbe Soll für beide Hubs.

type ListenEintrag = { ctx: string; reiter: string; zustand: string; abschnitt: string; ordnung: number; rolle: string; text_de: string; text_en: string | null; i18n_key: string | null };
const ELEMENTLISTE = (
	JSON.parse(readFileSync(path.join(HIER, '..', '..', 'docs', 'context', 'einstellungen_neu', 'elementliste.json'), 'utf8')) as { elemente: ListenEintrag[] }
).elemente;

/** Soll des Entwurfs: Pill und Knopf im Kopf (Knopf direkt nach der Pill), erster Kebab-Eintrag. */
function sollEntwurf(): { pill: ListenEintrag; knopf: ListenEintrag; kebab1: ListenEintrag } {
	const bereich = ELEMENTLISTE.filter((e) => e.ctx === 'orte' && e.zustand === 'normal');
	const reiter = bereich.find((e) => e.abschnitt === 'kopf' && e.i18n_key === 'aktionen.kopf.aktivieren')?.reiter;
	const eintraege = bereich.filter((e) => e.reiter === reiter);
	const kopf = eintraege.filter((e) => e.abschnitt === 'kopf').sort((a, b) => a.ordnung - b.ordnung);
	const knopf = kopf.find((e) => e.i18n_key === 'aktionen.kopf.aktivieren');
	const pill = kopf.find((e) => e.rolle === 'status');
	const kebab1 = eintraege.find((e) => e.abschnitt === 'kebab-menue' && e.ordnung === 1);
	expect(knopf && pill && kebab1, 'Elementliste: kopf (Pill, Knopf „Aktivieren“) und kebab-menue Ordnung 1 vorhanden').toBeTruthy();
	expect(knopf!.rolle, 'Elementliste: „Aktivieren“ ist ein Knopf').toBe('knopf');
	expect(knopf!.ordnung, 'Elementliste: Knopf steht direkt nach der Pill').toBe(pill!.ordnung + 1);
	expect(kebab1!.i18n_key, 'Elementliste: Kebab Ordnung 1 ist „Aktivieren“').toBe('aktionen.kopf.aktivieren');
	return { pill: pill!, knopf: knopf!, kebab1: kebab1! };
}

for (const kind of HUB_KINDS) {
	for (const lang of SPRACHEN) {
		test(`${kind} ${lang} desktop: AC-13 Elementliste — Kopf „Aktivieren“ neben der Pill, Kebab Ordnung 1 „Aktivieren“`, async ({ page }) => {
			const soll = sollEntwurf();
			const text = (e: ListenEintrag) => (lang === 'de' ? e.text_de : e.text_en);
			await page.setViewportSize(VIEWPORTS.desktop);
			await sprache(page, lang);
			const hub = await entwurf(page, kind);
			try {
				await openHub(page, kind, hub.id);
				const status = sichtbar(page, HUB_KOPF_SEL.status);
				await expect(pille(page), 'AC-13: Pill des Entwurfs').toContainText(text(soll.pill) ?? '');
				await expect(knopf(page), 'AC-13: Knopf „Aktivieren“ laut Elementliste').toHaveText(text(soll.knopf) ?? '');
				expect(await knopf(page).evaluate((el) => el.tagName), 'AC-13: Rolle knopf').toBe('BUTTON');
				// Reihenfolge im Kopf: Pill, direkt danach der Knopf (sichtbare Elemente der Status-Zeile).
				const folge = await status.evaluate((el) =>
					[...el.querySelectorAll('[data-testid="trip-detail-status-badge"], [data-testid="hub-kopf-aktivieren"]')]
						.filter((x) => (x as HTMLElement).offsetParent !== null)
						.map((x) => x.getAttribute('data-testid'))
				);
				expect(folge, 'AC-13: Knopf steht direkt nach der Pill').toEqual(['trip-detail-status-badge', 'hub-kopf-aktivieren']);
				const menue = await oeffneMenue(page);
				const liste = await eintraege(menue);
				expect(liste[0], 'AC-13: Kebab-Eintrag Ordnung 1').toBe(text(soll.kebab1));
				await page.keyboard.press('Escape');
			} finally {
				await hub.aufraeumen();
			}
		});
	}
}

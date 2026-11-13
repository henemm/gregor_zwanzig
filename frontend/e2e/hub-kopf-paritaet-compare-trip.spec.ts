// E2E — Issue #2837 Scheibe S1 (Epic #2345, ADR-0110): Hub-Kopf für Trip und Ortsvergleich
// als EIN Baustein (`shared/hub-kopf/HubKopf.svelte`). EINE Zusicherung für BEIDE Arten per
// Schleife über HUB_KINDS, je bei 1440 px (Desktop) und 390 px (Handy).
//
// Spec: docs/specs/modules/rework_2837_s1_hub_kopf.md — AC-1 … AC-10, AC-13 (HP-1 … HP-13).
// Gemessen wird im echten Browser (getComputedStyle, boundingBox), nicht am Quelltext:
//   - Senden: in der Leiste ganz oben, Hintergrund --g-ink, helle Schrift, gleiche Zeile wie
//     Breadcrumb bzw. Zurück-Pfeil, bei beiden Arten an derselben Stelle; mobil ≥ 44 px hoch.
//   - Entwurf: Trip-Senden gesperrt, Vergleich „Setup abschließen" auf dem Senden-Platz.
//   - Breadcrumb: Elternteil Link (Klick → Liste), Kind kein Link, kein „Hub".
//   - Status als Badge in der Titelzeile (aktiv, pausiert, Entwurf), keine Statuszeile.
//   - Kebab mobil vertikal, öffnet bei beiden dasselbe Aktionsblatt.
//   - langer Name 390 px: Leiste einzeilig, Senden sichtbar, kein waagerechtes Scrollen.
//   - Titelblock: Region-Platzhalter „—", h1 38 px bei beiden; Reiter-Zähler neutral,
//     Kontrast ≥ 4,5:1 berechnet.
//   - de/en: Breadcrumb und Aria-Texte über den Katalog (Zweitnutzer mit Sprache en).
//
// Pflicht-Mutationen (Spec Test Plan): (a) Trip-Senden wieder `accent` ⇒ HP-1 rot
// (Hintergrund rgb(196, 90, 42) statt Ink); (b) Zähler wieder Accent ⇒ HP-10 rot;
// (c) Status wieder eigene Zeile ⇒ HP-6 rot.
//
// Kind-Zweige NUR für Seeds (Vergleich-Entwurf = keine Orte, Trip-Entwurf = Etappe ohne
// Datum; Zweitnutzer braucht eigene Orte) und für die Whitelist-Werte (Elternteil-Text).
// Kein fester Schlaf, kein networkidle. Anmeldung über storageState (global.setup.ts),
// HP-13 über den Zweitnutzer aus helpers.testMitZustellbaremZiel. Aufräumen im finally.
//
// Status: in RED geschrieben, NICHT ausgeführt (lokaler Stack fehleranfällig); Lauf in
// /e2e-verify bzw. im CI-`e2e`-Job.

import { test, expect, type APIRequestContext, type Locator, type Page } from '@playwright/test';
import {
	createTestLocation,
	HUB_KINDS,
	HUB_KOPF_SEL,
	HUB_SEL,
	hubApiPath,
	kontrastVerhaeltnis,
	openHub,
	seedHub,
	testMitZustellbaremZiel,
	TOKEN_RGB,
	type HubKind,
	type SeededHub
} from './helpers';

const DESKTOP = { width: 1440, height: 900 };
const MOBIL = { width: 390, height: 844 };
const BREITEN = [DESKTOP, MOBIL] as const;
const PAPIER = 'rgb(246, 244, 238)'; // --g-paper (Schrift auf Btn primary)

/** Katalogtexte des Breadcrumb-Elternteils (listen.json, de/en) — Whitelist-Wert je Art. */
const ELTERN: Record<HubKind, { de: string; en: string; url: string }> = {
	route: { de: 'Trips', en: 'Trips', url: '/trips' },
	// #2913 c2 (Mockup): Elternteil „Orte"/„Locations" (aktionen.kopf.eltern_orte).
	vergleich: { de: 'Orte', en: 'Locations', url: '/compare' }
};

type Zustand = 'aktiv' | 'pausiert' | 'entwurf';

/** Seed je Art und Zustand (Muster hub-list-menu.spec.ts). */
async function seed(request: APIRequestContext, kind: HubKind, zustand: Zustand = 'aktiv', extra: Record<string, unknown> = {}): Promise<SeededHub> {
	if (kind === 'route') {
		const ohneDatum = zustand === 'entwurf' ? { stages: [{ id: 's1', name: 'Tag 1', waypoints: [{ id: 'a', name: 'a', lat: 42, lon: 9, elevation_m: 800 }] }] } : {};
		const hub = await seedHub(request, kind, { extra: { ...ohneDatum, ...extra } });
		if (zustand === 'pausiert') {
			const res = await request.patch(`${hubApiPath(kind, hub.id)}/state`, { data: { paused: true } });
			if (!res.ok()) {
				await hub.aufraeumen();
				throw new Error(`Trip pausieren (Seed) fehlgeschlagen: HTTP ${res.status()}`);
			}
		}
		return hub;
	}
	if (zustand === 'pausiert') return seedHub(request, kind, { extra: { schedule: 'manual', ...extra } });
	if (zustand === 'entwurf') return seedHub(request, kind, { extra: { location_ids: [], ...extra } });
	return seedHub(request, kind, { extra });
}

const leiste = (page: Page) => page.getByTestId(HUB_KOPF_SEL.leiste);
const senden = (page: Page) => leiste(page).locator(`[data-testid="${HUB_KOPF_SEL.senden}"]:visible`);
const titel = (page: Page) => page.getByRole(HUB_KOPF_SEL.titelRolle.role, { level: HUB_KOPF_SEL.titelRolle.level }).filter({ visible: true }).first();

async function box(loc: Locator, was: string) {
	const b = await loc.boundingBox();
	expect(b, `${was} hat keine Box (unsichtbar?)`).not.toBeNull();
	return b!;
}
const mitteY = (b: { y: number; height: number }) => b.y + b.height / 2;

/** Lage von „Senden" relativ zur Leiste: Abstand zur rechten Kante, senkrechte Mitte. */
async function sendenLage(page: Page) {
	const l = await box(leiste(page), 'Leiste');
	const s = await box(senden(page), 'Senden');
	return { rechts: l.x + l.width - (s.x + s.width), mitte: mitteY(s) - l.y, hoehe: s.height };
}

async function stil(loc: Locator) {
	return loc.evaluate((el) => {
		const s = getComputedStyle(el);
		return { grund: s.backgroundColor, schrift: s.color, groesse: s.fontSize };
	});
}

for (const kind of HUB_KINDS) {
	for (const vp of BREITEN) {
		const w = vp.width;

		test(`HP-1/HP-2 (${kind}, ${w} px): „Senden" in der Leiste, schwarz mit heller Schrift, gleiche Zeile wie Pfad/Zurück`, async ({ page }) => {
			await page.setViewportSize(vp);
			const hub = await seed(page.request, kind);
			try {
				await openHub(page, kind, hub.id);
				await expect(senden(page), 'HP-1: „Senden" steht nicht in der Leiste').toHaveCount(1);
				await expect(page.locator(`[data-testid="${HUB_KOPF_SEL.senden}"]:visible`), 'HP-1: ein zweites „Senden" (z. B. neben dem Titel)').toHaveCount(1);
				const f = await stil(senden(page));
				expect(f.grund, 'HP-1: „Senden" ist nicht schwarz (--g-ink) — Mutation (a)').toBe(TOKEN_RGB.ink);
				expect(f.grund).not.toBe(TOKEN_RGB.accent);
				expect(f.schrift, 'HP-1: Schrift auf „Senden" nicht hell (--g-paper)').toBe(PAPIER);
				expect(kontrastVerhaeltnis(f.schrift, f.grund)).toBeGreaterThanOrEqual(4.5);

				const s = await box(senden(page), 'Senden');
				expect(s.x + s.width / 2, 'HP-1: „Senden" steht nicht rechts').toBeGreaterThan(w / 2);
				const pfad = w === DESKTOP.width
					? page.getByTestId(HUB_KOPF_SEL.breadcrumb)
					: leiste(page).locator('[data-testid="back-link"]:visible');
				const p = await box(pfad, w === DESKTOP.width ? 'Breadcrumb' : 'Zurück-Pfeil');
				expect(Math.abs(mitteY(p) - mitteY(s)), 'HP-1: „Senden" steht nicht in derselben Zeile wie Pfad/Zurück').toBeLessThanOrEqual(8);
				const t = await box(titel(page), 'Überschrift');
				expect(s.y + s.height, 'HP-1: „Senden" steht nicht über dem Titel').toBeLessThanOrEqual(t.y + 1);
				if (w === MOBIL.width) expect(s.height, 'HP-2: „Senden" mobil < 44 px hoch').toBeGreaterThanOrEqual(44);
			} finally {
				await hub.aufraeumen();
			}
		});

		test(`HP-6 (${kind}, ${w} px): Status als Badge in der Titelzeile (aktiv, pausiert, Entwurf), keine Statuszeile`, async ({ page }) => {
			await page.setViewportSize(vp);
			for (const zustand of ['aktiv', 'pausiert', 'entwurf'] as const) {
				const hub = await seed(page.request, kind, zustand);
				try {
					await openHub(page, kind, hub.id);
					const status = page.getByTestId(HUB_KOPF_SEL.status).filter({ visible: true });
					await expect(status, `HP-6 (${zustand}): Status nicht genau einmal in der Titelzeile`).toHaveCount(1);
					const t = await box(titel(page), 'Überschrift');
					const b = await box(status, 'Status');
					// Gleiche Zeile wie die Überschrift; einzig erlaubter Umbruch: unmittelbar darunter
					// (AC-8, langer Name mobil) — nie in eine eigene Zeile unter der Region.
					const region = await box(page.getByTestId(`${HUB_SEL[kind].kopf}-region-edit-toggle`).filter({ visible: true }).first(), 'Region-Stift');
					expect(mitteY(b), `HP-6 (${zustand}): Status steht unter der Region (eigene Statuszeile) — Mutation (c)`).toBeLessThan(region.y);
					if (w === DESKTOP.width) {
						expect(mitteY(b), `HP-6 (${zustand}): Status nicht in der Titelzeile`).toBeGreaterThanOrEqual(t.y);
						expect(mitteY(b)).toBeLessThanOrEqual(t.y + t.height);
					}
					expect(b.x, `HP-6 (${zustand}): Badge ragt links aus dem Bild`).toBeGreaterThanOrEqual(0);
					expect(b.x + b.width, `HP-6 (${zustand}): Badge ragt rechts aus dem Bild`).toBeLessThanOrEqual(w + 1);
					await expect(page.locator('.status-line')).toHaveCount(0);
				} finally {
					await hub.aufraeumen();
				}
			}
		});

		test(`HP-9/HP-10 (${kind}, ${w} px): Titelblock gleich aufgebaut — Region „—", h1 38 px (Desktop), Zähler neutral`, async ({ page }) => {
			await page.setViewportSize(vp);
			const ohneRegion = kind === 'route' ? { region: '' } : { display_config: { region: '' } };
			const hub = await seed(page.request, kind, 'aktiv', ohneRegion);
			try {
				await openHub(page, kind, hub.id);
				const region = page.getByTestId(`${HUB_SEL[kind].kopf}-region-edit-toggle`).filter({ visible: true }).first();
				await expect(region.locator('xpath=preceding-sibling::span[1]'), 'HP-9: Region-Platzhalter').toHaveText('—');
				if (w === DESKTOP.width) {
					expect((await stil(titel(page))).groesse, 'HP-9: h1 nicht 38 px').toBe('38px');
				}
				const badge = page.locator(`[data-testid="${HUB_SEL[kind].reiter}-${HUB_SEL[kind].punkteReiter}"]:visible [data-slot="segmented-badge"]`);
				await expect(badge).toBeVisible();
				const z = await stil(badge);
				expect(z.grund, 'HP-10: Zähler nicht neutral — Mutation (b)').toBe(TOKEN_RGB.paperDeep);
				expect(z.schrift).toBe(TOKEN_RGB.ink3);
				expect(z.grund).not.toBe(TOKEN_RGB.accent);
				expect(kontrastVerhaeltnis(z.schrift, z.grund), 'HP-10: Kontrast Zähler').toBeGreaterThanOrEqual(4.5);
			} finally {
				await hub.aufraeumen();
			}
		});
	}

	test(`HP-4 (${kind}, 1440 px): Breadcrumb „${ELTERN[kind].de} / …" — Elternteil Link (Klick → Liste), Kind kein Link, kein „Hub"`, async ({ page }) => {
		await page.setViewportSize(DESKTOP);
		const hub = await seed(page.request, kind);
		try {
			await openHub(page, kind, hub.id);
			const daten = (await (await page.request.get(hubApiPath(kind, hub.id))).json()) as { name: string; shortcode?: string | null };
			const krumen = page.getByTestId(HUB_KOPF_SEL.breadcrumb);
			await expect(krumen).toBeVisible();
			const links = krumen.locator('a');
			await expect(links).toHaveCount(1);
			// textContent (nicht innerText): CSS-Versalien dürfen den Katalogtext nicht ersetzen.
			expect((await links.first().textContent())?.trim()).toBe(ELTERN[kind].de);
			const kind_ = kind === 'route' ? daten.shortcode ?? daten.name : daten.name;
			await expect(krumen).toContainText(kind_);
			await expect(links.first()).not.toContainText(kind_);
			await expect(leiste(page).getByText(/(^|\s)Hub(\s|$)/)).toHaveCount(0);
			await expect(page.getByText(/Orts-Vergleich\s*·\s*Hub/i)).toHaveCount(0);
			await links.first().click();
			await expect.poll(() => new URL(page.url()).pathname).toBe(ELTERN[kind].url);
		} finally {
			await hub.aufraeumen();
		}
	});
}

/** Unterkante des Kopfs (Adversary F001/F006): berechneter Stil der HubKopf-Wurzel und des Titelblocks,
 *  dazu der Abstand Kopf-Unterkante → Reiterleiste. */
async function unterkante(page: Page) {
	const wurzel = leiste(page).locator('xpath=ancestor::*[@data-kind][1]');
	const titelBlock = wurzel.locator('.hub-kopf-titel');
	const w = await wurzel.evaluate((el) => {
		const s = getComputedStyle(el);
		return { breite: s.borderBottomWidth, art: s.borderBottomStyle, farbe: s.borderBottomColor };
	});
	const padding = await titelBlock.evaluate((el) => getComputedStyle(el).paddingBottom);
	const k = await box(wurzel, 'HubKopf-Wurzel');
	const r = await box(page.locator('.mtabbar[role="tablist"]').first(), 'Reiterleiste');
	return { ...w, padding, abstand: r.y - (k.y + k.height) };
}

test.describe('HP Parität — beide Arten nebeneinander gemessen', () => {
	for (const vp of BREITEN) {
		test(`HP-14 (${vp.width} px): Unterkante des Kopfs gleich — Linie, Abstand unter dem Titelblock, Abstand zur Reiterleiste`, async ({ page }) => {
			await page.setViewportSize(vp);
			const mass: Record<string, Awaited<ReturnType<typeof unterkante>>> = {};
			for (const kind of HUB_KINDS) {
				const hub = await seed(page.request, kind);
				try {
					await openHub(page, kind, hub.id);
					mass[kind] = await unterkante(page);
				} finally {
					await hub.aufraeumen();
				}
			}
			const { route, vergleich } = mass;
			expect(vergleich.breite, 'Linienstärke der Unterkante verschieden').toBe(route.breite);
			expect(vergleich.art, 'Linienart der Unterkante verschieden').toBe(route.art);
			expect(vergleich.farbe, 'Linienfarbe der Unterkante verschieden').toBe(route.farbe);
			expect(vergleich.padding, 'Abstand unter dem Titelblock verschieden (F006)').toBe(route.padding);
			expect(Math.abs(vergleich.abstand - route.abstand), 'Abstand Kopf-Unterkante → Reiterleiste verschieden').toBeLessThanOrEqual(4);
			if (vp.width === DESKTOP.width) {
				expect(route.breite, 'Desktop: Unterkante ohne 1-px-Linie').toBe('1px');
				expect(route.art).toBe('solid');
			}
		});


		test(`HP-1/HP-2 (${vp.width} px): „Senden" sitzt bei Trip und Vergleich an derselben Stelle der Leiste`, async ({ page }) => {
			await page.setViewportSize(vp);
			const lagen: Record<string, Awaited<ReturnType<typeof sendenLage>>> = {};
			for (const kind of HUB_KINDS) {
				const hub = await seed(page.request, kind);
				try {
					await openHub(page, kind, hub.id);
					lagen[kind] = await sendenLage(page);
				} finally {
					await hub.aufraeumen();
				}
			}
			expect(Math.abs(lagen.route.rechts - lagen.vergleich.rechts), 'Abstand zur rechten Kante verschieden').toBeLessThanOrEqual(4);
			expect(Math.abs(lagen.route.mitte - lagen.vergleich.mitte), 'Höhe in der Leiste verschieden').toBeLessThanOrEqual(4);
			expect(Math.abs(lagen.route.hoehe - lagen.vergleich.hoehe), 'Knopfhöhe verschieden').toBeLessThanOrEqual(1);
		});

		test(`HP-3 (${vp.width} px): Entwurf — Vergleich „Setup abschließen" auf dem Platz von Senden, Trip-Senden gesperrt`, async ({ page }) => {
			await page.setViewportSize(vp);
			const trip = await seed(page.request, 'route', 'entwurf');
			let tripLage: Awaited<ReturnType<typeof sendenLage>>;
			try {
				await openHub(page, 'route', trip.id);
				await expect(senden(page)).toBeDisabled();
				tripLage = await sendenLage(page);
			} finally {
				await trip.aufraeumen();
			}
			const v = await seed(page.request, 'vergleich', 'entwurf');
			try {
				await openHub(page, 'vergleich', v.id);
				await expect(senden(page), 'Vergleich-Entwurf zeigt „Senden"').toHaveCount(0);
				const setup = leiste(page).getByRole('button', { name: 'Setup abschließen' }).filter({ visible: true });
				await expect(setup).toHaveCount(1);
				await expect(page.getByRole('button', { name: 'Setup abschließen' }).filter({ visible: true }), '„Setup abschließen" zusätzlich neben dem Titel').toHaveCount(1);
				expect((await stil(setup)).grund).toBe(TOKEN_RGB.ink);
				const l = await box(leiste(page), 'Leiste');
				const s = await box(setup, 'Setup abschließen');
				expect(Math.abs(l.x + l.width - (s.x + s.width) - tripLage!.rechts), 'nicht auf dem Senden-Platz (rechts)').toBeLessThanOrEqual(4);
				expect(Math.abs(mitteY(s) - l.y - tripLage!.mitte), 'nicht auf dem Senden-Platz (Höhe)').toBeLessThanOrEqual(4);
				await setup.click();
				// #2794 S3a: „Setup abschließen" springt auf den Versand-Abschnitt im Reiter Zustellung.
				await expect.poll(() => new URL(page.url()).searchParams.get('tab')).toBe('zustellung');
			} finally {
				await v.aufraeumen();
			}
		});
	}

	test('HP-7 (390 px): Kebab bei beiden vertikal, Tippen öffnet dasselbe Aktionsblatt', async ({ page }) => {
		await page.setViewportSize(MOBIL);
		const eintraege: Record<string, string[]> = {};
		for (const kind of HUB_KINDS) {
			const hub = await seed(page.request, kind);
			try {
				await openHub(page, kind, hub.id);
				const kebab = leiste(page).locator(`[data-testid="${HUB_KOPF_SEL.kebab}"]:visible`);
				await expect(kebab, `${kind}: Kebab nicht in der Leiste`).toHaveCount(1);
				const klassen = await kebab.locator('svg').first().getAttribute('class');
				expect(klassen ?? '', `${kind}: Kebab-Symbol nicht vertikal`).toMatch(/\blucide-ellipsis-vertical\b/);
				expect(klassen ?? '', `${kind}: Kebab-Symbol horizontal`).not.toMatch(/lucide-ellipsis(?!-vertical)|lucide-more-horizontal/);
				const k = await box(kebab, 'Kebab');
				expect(k.height, `${kind}: Kebab-Tippfläche < 44 px`).toBeGreaterThanOrEqual(44);
				await kebab.click();
				const blatt = page.locator('div[data-snap]').filter({ has: page.getByTestId('sheet-handle') }).filter({ visible: true });
				await expect(blatt).toBeVisible();
				eintraege[kind] = await blatt.locator('[data-testid^="subscription-action-"]').evaluateAll((els) => els.map((e) => e.getAttribute('data-testid') ?? ''));
				expect(eintraege[kind].length, `${kind}: Aktionsblatt ohne Einträge`).toBeGreaterThan(0);
			} finally {
				await hub.aufraeumen();
			}
		}
		expect(eintraege.vergleich, 'Aktionsblatt-Einträge verschieden').toEqual(eintraege.route);
	});

	test('HP-5 (1440 px): Trip ohne Kürzel — Pfad zeigt den Namen', async ({ page }) => {
		await page.setViewportSize(DESKTOP);
		// Seed ohne Kürzel (helpers.seedHub setzt keins) — Vorbedingung geprüft.
		const hub = await seed(page.request, 'route', 'aktiv');
		try {
			await openHub(page, 'route', hub.id);
			const { name, shortcode } = (await (await page.request.get(hubApiPath('route', hub.id))).json()) as { name: string; shortcode?: string | null };
			expect(shortcode ?? null, 'Vorbedingung: Trip ohne Kürzel').toBeNull();
			const krumen = page.getByTestId(HUB_KOPF_SEL.breadcrumb);
			await expect(krumen).toContainText(name);
			await expect(krumen.locator('a')).not.toContainText(name);
		} finally {
			await hub.aufraeumen();
		}
	});

	for (const kind of HUB_KINDS) {
		test(`HP-5/HP-8 (${kind}, 390 px): sehr langer Name — Leiste einzeilig und oben, „Senden" sichtbar, Badge lesbar, kein waagerechtes Scrollen`, async ({ page }) => {
			await page.setViewportSize(MOBIL);
			const kurz = await seed(page.request, kind);
			let kurzLeiste: { y: number; height: number };
			try {
				await openHub(page, kind, kurz.id);
				kurzLeiste = await box(leiste(page), 'Leiste (kurzer Name)');
			} finally {
				await kurz.aufraeumen();
			}
			const lang = await seed(page.request, kind, 'aktiv', {
				name: 'E2E-GZ-Ein sehr langer Name, der auf dem Handy niemals in eine Zeile passt und umbrechen muss'
			});
			try {
				await openHub(page, kind, lang.id);
				const l = await box(leiste(page), 'Leiste (langer Name)');
				expect(Math.abs(l.height - kurzLeiste!.height), 'HP-5: Leiste bricht um (Höhe verändert)').toBeLessThanOrEqual(1);
				expect(Math.abs(l.y - kurzLeiste!.y), 'HP-8: Leiste verschoben').toBeLessThanOrEqual(1);
				await expect(senden(page)).toBeInViewport();
				const b = await box(page.getByTestId(HUB_KOPF_SEL.status).filter({ visible: true }), 'Status');
				expect(b.x).toBeGreaterThanOrEqual(0);
				expect(b.x + b.width).toBeLessThanOrEqual(MOBIL.width + 1);
				const m = await page.evaluate(() => ({ sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth }));
				expect(m.sw, 'HP-8: die Seite scrollt waagerecht').toBeLessThanOrEqual(m.cw);
			} finally {
				await lang.aufraeumen();
			}
		});
	}
});

// ─── HP-13: Sprache des Nutzers (de/en) ─────────────────────────────────────
// Zweitnutzer (eigenes Konto, Admin bleibt unberührt); Sprache per PUT /api/auth/profile.
// Seed-Besonderheit: die e2e-loc-* aus global.setup.ts gehören dem Admin — der Zweitnutzer
// bekommt für den Vergleich eigene Orte.
for (const kind of HUB_KINDS) {
	testMitZustellbaremZiel(`HP-13 (${kind}): Breadcrumb-Elternteil und Aria-Texte folgen der Nutzersprache (de → en)`, async ({ page }) => {
		const orte =
			kind === 'vergleich'
				? [await createTestLocation(page.request, { name: 'HP13-A' }), await createTestLocation(page.request, { name: 'HP13-B' })]
				: [];
		const hub = await seed(page.request, kind, 'aktiv', orte.length ? { location_ids: orte.map((o) => o.id) } : {});
		try {
			for (const lang of ['de', 'en'] as const) {
				const res = await page.request.put('/api/auth/profile', { data: { language: lang } });
				expect(res.ok(), `Sprache ${lang} setzen: HTTP ${res.status()}`).toBeTruthy();
				await page.setViewportSize(DESKTOP);
				await openHub(page, kind, hub.id);
				const link = page.getByTestId(HUB_KOPF_SEL.breadcrumb).locator('a');
				expect((await link.first().textContent())?.trim(), `${lang}: Elternteil`).toBe(ELTERN[kind][lang]);
				await expect(leiste(page).locator(`[data-testid="${HUB_KOPF_SEL.kebab}"]:visible`)).toHaveAttribute('aria-label', lang === 'de' ? 'Weitere Aktionen' : 'More actions');
				await page.setViewportSize(MOBIL);
				await expect(leiste(page).locator('[data-testid="back-link"]:visible')).toHaveAttribute('aria-label', lang === 'de' ? 'Zurück zur Übersicht' : 'Back to overview');
				// #2913 c2: Beschriftung „Test schicken ▾" / „Send test ▾" (Menü folgt mit #2797).
				await expect(senden(page)).toHaveText(lang === 'de' ? 'Test schicken ▾' : 'Send test ▾');
			}
		} finally {
			await page.request.put('/api/auth/profile', { data: { language: 'de' } }).catch(() => {});
			await hub.aufraeumen();
			for (const o of orte) await page.request.delete(`/api/locations/${o.id}`).catch(() => {});
		}
	});
}

// ─── #2837 Nachbesserung S1b: EIN Status-Schild, Profil in der Unterzeile (HS-1 … HS-6) ────────
// Spec: docs/specs/modules/rework_2837_s1b_status_profil.md — AC-1 … AC-8, AC-11 (Browser-Anteil).
// Gemessen per getComputedStyle; der Schild-Grund ist transparent, deshalb gilt der Kontrast
// gegen den ersten nicht-transparenten Vorfahren (Papier bzw. Karte).
// Pflicht-Mutationen: Vergleich wieder gefüllt/eigenes Schild ⇒ HS-1/HS-4 rot; Pausiert wieder
// --g-warning ⇒ HS-3 rot; profileLabel im Trip weg ⇒ HS-5 rot.
// Status: in RED geschrieben, NICHT ausgeführt (Lauf in /e2e-verify bzw. CI-`e2e`).

const SCHILD = 'trip-detail-status-badge';
const SCHILD_RGB = { pausiert: 'rgb(138, 98, 16)', aktiv: 'rgb(140, 62, 26)' } as const; // --g-warn-deep, --g-accent-deep
const DATA_STATUS: Record<Zustand, string> = { aktiv: 'active', pausiert: 'paused', entwurf: 'draft' };

/** Lokales Datum (YYYY-MM-DD) mit Tagesversatz: der Trip ist nur „aktiv", wenn heute in seine Etappen fällt. */
const tag = (versatz: number) => {
	const d = new Date();
	d.setDate(d.getDate() + versatz);
	return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
};
/** Seed im gewünschten Zustand; Trip-Aktiv bekommt Etappen gestern/heute/morgen, damit ein
 *  Zeitzonen-Versatz zwischen Testprozess und Browser (±1 Tag, vgl. #2847) den Zustand nicht kippt. */
const seedZustand = (request: APIRequestContext, kind: HubKind, zustand: Zustand, extra: Record<string, unknown> = {}) =>
	seed(request, kind, zustand, kind === 'route' && zustand === 'aktiv'
		? { stages: [-1, 0, 1].map((v, i) => ({ id: `s${i + 1}`, name: `Tag ${i + 1}`, date: tag(v), waypoints: [{ id: `a${i}`, name: `a${i}`, lat: 42 + i * 0.02, lon: 9, elevation_m: 800 }] })), ...extra }
		: extra);

async function schildMessen(page: Page) {
	const s = page.locator(`[data-testid="${SCHILD}"]:visible`);
	await expect(s, `[data-testid=${SCHILD}] nicht genau einmal sichtbar (AC-8)`).toHaveCount(1);
	return s.evaluate((el) => {
		const st = getComputedStyle(el);
		let grund = 'rgba(0, 0, 0, 0)';
		for (let n: Element | null = el.parentElement; n; n = n.parentElement) {
			const g = getComputedStyle(n).backgroundColor;
			if (!/rgba\(.*,\s*0\)$/.test(g) && g !== 'transparent') { grund = g; break; }
		}
		return {
			text: (el as HTMLElement).innerText.trim(),
			status: el.getAttribute('data-status'),
			slot: el.getAttribute('data-slot'),
			umrandet: el.hasAttribute('data-outlined'),
			schrift: st.color,
			rand: st.borderTopColor,
			randBreite: st.borderTopWidth,
			eigenerGrund: st.backgroundColor,
			grund,
			umformung: st.textTransform
		};
	});
}

test.describe('HS S1b — Trip und Vergleich zeigen im selben Zustand dasselbe Status-Schild', () => {
	for (const vp of BREITEN) {
		for (const zustand of ['aktiv', 'pausiert', 'entwurf'] as const) {
			test(`HS-1/HS-2/HS-4 (${vp.width} px, ${zustand}): gleicher Text, gleiche Schrift- und Randfarbe, umrandet, Kontrast ≥ 4,5`, async ({ page }) => {
				await page.setViewportSize(vp);
				const m: Partial<Record<HubKind, Awaited<ReturnType<typeof schildMessen>>>> = {};
				for (const kind of HUB_KINDS) {
					const hub = await seedZustand(page.request, kind, zustand);
					try {
						await openHub(page, kind, hub.id);
						m[kind] = await schildMessen(page);
					} finally {
						await hub.aufraeumen();
					}
				}
				const { route, vergleich } = m as Record<HubKind, Awaited<ReturnType<typeof schildMessen>>>;
				for (const [kind, x] of [['route', route], ['vergleich', vergleich]] as const) {
					expect(x.status, `${kind}: data-status (AC-8)`).toBe(DATA_STATUS[zustand]);
					expect(x.slot, `${kind}: Schild ist nicht das Pill-Atom`).toBe('pill');
					expect(x.umrandet, `${kind}: Schild nicht umrandet`).toBe(true);
					expect(x.eigenerGrund, `${kind}: Schild gefüllt (--g-accent) statt umrandet — AC-5`).not.toBe(TOKEN_RGB.accent);
					expect(x.eigenerGrund, `${kind}: Schild hat eigenen Hintergrund`).toMatch(/rgba\(.*,\s*0\)$|transparent/);
					expect(x.randBreite, `${kind}: kein Rand`).not.toBe('0px');
					expect(kontrastVerhaeltnis(x.schrift, x.grund), `${kind}: Kontrast Schild-Schrift zu ${x.grund}`).toBeGreaterThanOrEqual(4.5);
				}
				expect(vergleich.text, 'AC-1: Text (inkl. Großschreibung) verschieden').toBe(route.text);
				expect(vergleich.umformung, 'AC-1: Schreibung (text-transform) verschieden').toBe(route.umformung);
				expect(vergleich.schrift, 'AC-1: Schriftfarbe verschieden').toBe(route.schrift);
				expect(vergleich.rand, 'AC-1: Randfarbe verschieden').toBe(route.rand);
				if (zustand === 'pausiert') expect(route.schrift, 'AC-4: Pausiert nicht --g-warn-deep').toBe(SCHILD_RGB.pausiert);
				if (zustand === 'aktiv') expect(vergleich.schrift, 'AC-5: Aktiv nicht --g-accent-deep').toBe(SCHILD_RGB.aktiv);
				if (zustand === 'entwurf') {
					expect(vergleich.text.toLowerCase(), 'AC-3: Vergleich-Entwurf zeigt „draft"').not.toContain('draft');
					expect(vergleich.text.toLowerCase()).toBe('entwurf');
				}
			});
		}
	}
});

test.describe('HS S1b — Profil in der Zeile unter dem Titel bei beiden Arten', () => {
	const hinterStift = (page: Page, kind: HubKind) =>
		page.getByTestId(`${HUB_SEL[kind].kopf}-region-edit-toggle`).filter({ visible: true }).first().locator('xpath=following-sibling::*[1]');
	const PROFIL: Record<HubKind, { extra: Record<string, unknown>; label: string }> = {
		route: { extra: { activity: 'trekking' }, label: 'Trekking' },
		vergleich: { extra: { profil: 'wandern' }, label: 'Wandern' }
	};
	for (const vp of BREITEN) {
		for (const kind of HUB_KINDS) {
			test(`HS-5 (${kind}, ${vp.width} px): „— ✎ · ${PROFIL[kind].label}" — Profil direkt hinter dem Region-Stift`, async ({ page }) => {
				await page.setViewportSize(vp);
				const ohneRegion = kind === 'route' ? { region: '' } : { display_config: { region: '' } };
				const hub = await seed(page.request, kind, 'aktiv', { ...ohneRegion, ...PROFIL[kind].extra });
				try {
					await openHub(page, kind, hub.id);
					const stift = page.getByTestId(`${HUB_SEL[kind].kopf}-region-edit-toggle`).filter({ visible: true }).first();
					await expect(stift.locator('xpath=preceding-sibling::span[1]'), 'Region-Platzhalter').toHaveText('—');
					await expect(hinterStift(page, kind), `AC-6: Profil fehlt hinter dem Stift (${kind})`).toHaveText(`· ${PROFIL[kind].label}`);
				} finally {
					await hub.aufraeumen();
				}
			});
		}
		test(`HS-6 (route, ${vp.width} px): Trip ohne Aktivität — kein Zusatz hinter „— ✎" (AC-7)`, async ({ page }) => {
			await page.setViewportSize(vp);
			const hub = await seed(page.request, 'route', 'aktiv', { region: '' });
			try {
				await openHub(page, 'route', hub.id);
				const n = hinterStift(page, 'route');
				if (await n.count()) expect((await n.innerText()).trim().startsWith('·'), 'AC-7: Zusatz ohne Aktivität').toBe(false);
			} finally {
				await hub.aufraeumen();
			}
		});
	}
});

// AC-11: Status-Text und Profil folgen der Nutzersprache (Zweitnutzer, Muster HP-13).
for (const kind of HUB_KINDS) {
	testMitZustellbaremZiel(`HS-7 (${kind}): Status-Schild „Pausiert"/„Paused" und Profil folgen der Nutzersprache (de → en)`, async ({ page }) => {
		const orte =
			kind === 'vergleich'
				? [await createTestLocation(page.request, { name: 'HS7-A' }), await createTestLocation(page.request, { name: 'HS7-B' })]
				: [];
		const extra = { ...(orte.length ? { location_ids: orte.map((o) => o.id) } : {}), ...(kind === 'route' ? { activity: 'trekking' } : { profil: 'wandern' }) };
		const hub = await seedZustand(page.request, kind, 'pausiert', extra);
		const ERWARTET = { de: { status: 'pausiert', profil: kind === 'route' ? 'Trekking' : 'Wandern' }, en: { status: 'paused', profil: kind === 'route' ? 'Trekking' : 'Hiking' } } as const;
		try {
			for (const lang of ['de', 'en'] as const) {
				const res = await page.request.put('/api/auth/profile', { data: { language: lang } });
				expect(res.ok(), `Sprache ${lang} setzen: HTTP ${res.status()}`).toBeTruthy();
				await page.setViewportSize(DESKTOP);
				await openHub(page, kind, hub.id);
				const s = await schildMessen(page);
				expect(s.text.toLowerCase(), `${lang}: Status-Text`).toBe(ERWARTET[lang].status);
				const zusatz = page.getByTestId(`${HUB_SEL[kind].kopf}-region-edit-toggle`).filter({ visible: true }).first().locator('xpath=following-sibling::*[1]');
				await expect(zusatz, `${lang}: Profil-Zusatz`).toHaveText(`· ${ERWARTET[lang].profil}`);
			}
		} finally {
			await page.request.put('/api/auth/profile', { data: { language: 'de' } }).catch(() => {});
			await hub.aufraeumen();
			for (const o of orte) await page.request.delete(`/api/locations/${o.id}`).catch(() => {});
		}
	});
}

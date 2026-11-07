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
	vergleich: { de: 'Orts-Vergleiche', en: 'Location comparisons', url: '/compare' }
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
	const r = await box(page.locator('[data-slot="segmented"][role="tablist"]').first(), 'Reiterleiste');
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
				await expect.poll(() => new URL(page.url()).searchParams.get('tab')).toBe('wetter-metriken');
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
				await expect(senden(page)).toHaveText(lang === 'de' ? 'Senden' : 'Send');
			}
		} finally {
			await page.request.put('/api/auth/profile', { data: { language: 'de' } }).catch(() => {});
			await hub.aufraeumen();
			for (const o of orte) await page.request.delete(`/api/locations/${o.id}`).catch(() => {});
		}
	});
}

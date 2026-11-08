// E2E — Issue #2837 Scheibe S2 (Epic #2345, ADR-0110): Anlege-Rahmen für /trips/new und
// /compare/new als EIN Baustein (`shared/anlege-rahmen/AnlegeRahmen.svelte`). EINE Zusicherung
// für BEIDE Arten per Schleife über HUB_KINDS, bei 1440 px (Computer) und 390 px (Handy),
// Texte in de und en.
//
// Spec: docs/specs/modules/rework_2837_s2_anlege_rahmen.md — AC-1 … AC-13, AC-16 … AC-18
// (AR-1 … AR-18, Nummer = AC). Gemessen im echten Browser (getComputedStyle, boundingBox,
// Netzmitschnitt), nicht am Quelltext:
//   - Breadcrumb „Trips / Neuer Trip" bzw. „Orts-Vergleiche / Neuer Vergleich" oben links,
//     Elternteil Link, Kind kein Link; mobil Zurück-Pfeil mit Elternteil.
//   - Eyebrow „Neuer Trip"/„Neuer Vergleich" (en „New trip"/„New comparison"), Computer = Handy.
//   - Fuß: Abbrechen unten links, Standardwerte + Hinweis + Hauptaktion rechts; Hauptaktion
//     Hintergrund --g-ink, gesperrt abgeblendet; Weiter Hintergrund --g-accent, gesperrt NUR über
//     disabled (keine Inline-Deckkraft).
//   - Trip: Abbrechen/Zurück/Pfad-Link ohne Autosave, Menü-Navigation speichert wie bisher.
//   - Vergleich: kein POST /api/compare/presets außer bei „Briefing aktivieren".
//   - Sticky-Fuß sichtbar auch bei 1440×700; mobil über der Navigation, nicht verdeckt.
//   - testids aus AC-16 je genau einmal, `cm-desktop-footer` neu; `?from=`-Vorlage.
//
// Pflicht-Mutationen (Spec Test Plan): Trip-Hauptaktion wieder accent ⇒ AR-8 rot; Abbrechen
// wieder oben ⇒ AR-5 rot; Inline-Deckkraft am Weiter ⇒ AR-11 rot; Eyebrow „Neue Trip" ⇒ AR-4
// rot; Trip-Zurück ruft Autosave ⇒ AR-2/AR-3/AR-6 rot; Fuß im Vergleich entfernt ⇒ AR-5/AR-8/AR-18 rot.
//
// Kind-Zweige NUR für Whitelist-Werte (Elternteil, Kind/Eyebrow, Abschluss-Text, Autosave-
// Semantik AR-6/AR-7) über ART bzw. ANLEGE_SEL. Kein fester Schlaf, kein networkidle.
// Anmeldung über storageState (global.setup.ts); de/en über den Zweitnutzer
// (helpers.testMitZustellbaremZiel, Sprache per PUT /api/auth/profile, Muster HP-13).
//
// Status: in RED geschrieben, lokal NICHT ausgeführt (Vite-Proxy zeigt auf Staging); Lauf in
// /e2e-verify bzw. im CI-`e2e`-Job.

import { test, expect, type Locator, type Page } from '@playwright/test';
import {
	ANLEGE_SEL,
	anlegenPflicht,
	cleanupTracked,
	E2E_TEST_PREFIX,
	HUB_KINDS,
	hubApiPath,
	LISTE_SEL,
	seedHub,
	testMitZustellbaremZiel,
	TOKEN_RGB,
	type HubKind
} from './helpers';

const DESKTOP = { width: 1440, height: 900 };
const NIEDRIG = { width: 1440, height: 700 };
const MOBIL = { width: 390, height: 844 };
const BREITEN = [DESKTOP, MOBIL] as const;
const SPRACHEN = ['de', 'en'] as const;
const PAPIER = 'rgb(246, 244, 238)'; // --g-paper (Schrift auf Btn primary)

/** Whitelist-Werte je Art (Spec „Whitelist" Nr. 2 und 5): Katalogtexte de/en, Listen-URL. */
const ART: Record<HubKind, { eltern: Record<'de' | 'en', string>; neu: Record<'de' | 'en', string>; abschluss: Record<'de' | 'en', string> }> = {
	route: {
		eltern: { de: 'Trips', en: 'Trips' },
		neu: { de: 'Neuer Trip', en: 'New trip' },
		abschluss: { de: 'Trip speichern', en: 'Save trip' }
	},
	vergleich: {
		eltern: { de: 'Orts-Vergleiche', en: 'Location comparisons' },
		neu: { de: 'Neuer Vergleich', en: 'New comparison' },
		abschluss: { de: 'Briefing aktivieren', en: 'Activate briefing' }
	}
};

/** testids aus AC-16 je Art (jede genau einmal im Dokument). */
const TESTIDS: Record<HubKind, string[]> = {
	route: ['trip-new-save-btn', 'tn-desktop-footer', 'trip-new-continue-etappen'],
	vergleich: ['compare-editor-activate', 'compare-editor-standardwerte', 'compare-editor-continue-orte', 'cm-desktop-footer']
};

const einName = (tag: string) => `${E2E_TEST_PREFIX}AR-${tag}-${Date.now()}`;

test.afterEach(async ({ page }) => {
	await cleanupTracked(page.request);
});

async function box(loc: Locator, was: string) {
	const b = await loc.boundingBox();
	expect(b, `${was} hat keine Box (unsichtbar?)`).not.toBeNull();
	return b!;
}
const mitteY = (b: { y: number; height: number }) => b.y + b.height / 2;
const mitteX = (b: { x: number; width: number }) => b.x + b.width / 2;

async function stil(loc: Locator) {
	return loc.evaluate((el) => {
		const s = getComputedStyle(el);
		return { grund: s.backgroundColor, schrift: s.color, deckkraft: Number(s.opacity), inline: (el as HTMLElement).style.opacity };
	});
}

const titel = (page: Page) => page.getByRole('heading', { level: 1 }).filter({ visible: true }).first();
const elternLink = (page: Page, kind: HubKind, lang: 'de' | 'en' = 'de') =>
	page.locator(`a[href="${LISTE_SEL[kind].url}"]:visible`).filter({ hasText: new RegExp(`^\\s*${ART[kind].eltern[lang]}\\s*$`) });
const zurueckMobil = (page: Page) => page.locator('[data-testid="back-link"]:visible');
const eyebrow = (page: Page) => page.locator('[data-slot="eyebrow"]:visible').first();
/** Alle sichtbaren „Abbrechen"-Knöpfe/Links der Seite. */
const alleAbbrechen = (page: Page) => page.locator('a:visible, button:visible').filter({ hasText: /^\s*(Abbrechen|Cancel)\s*$/ });

/** Zählt die Anlege-/Autosave-POSTs der Art. */
function postZaehler(page: Page, kind: HubKind): { n: number } {
	const z = { n: 0 };
	const pfad = ANLEGE_SEL[kind].postPfad;
	page.on('request', (r) => {
		if (['POST', 'PUT'].includes(r.method()) && new URL(r.url()).pathname.startsWith(pfad)) z.n++;
	});
	page.on('response', async (r) => {
		if (r.request().method() !== 'POST' || new URL(r.url()).pathname !== pfad || !r.ok()) return;
		const id = ((await r.json().catch(() => ({}))) as { id?: string }).id;
		if (id) await page.request.delete(hubApiPath(kind, id)).catch(() => {});
	});
	return z;
}

/** Stabilitätsfenster statt festem Schlaf: `lies()` muss `ms` lang `soll` liefern. */
async function bleibtBei(lies: () => number, soll: number, ms: number, message: string): Promise<void> {
	let seit = 0;
	await expect
		.poll(
			() => {
				const n = lies();
				if (n !== soll) {
					seit = 0;
					return n;
				}
				seit ||= Date.now();
				return Date.now() - seit >= ms ? 'stabil' : n;
			},
			{ message, timeout: ms + 8_000, intervals: [200] }
		)
		.toBe('stabil');
}

/** Pflichtangaben + Besuch der drei Schwanz-Schritte ⇒ Abschluss frei (Trip: `ready`, Autosave scharf). */
async function bereit(page: Page, kind: HubKind, name: string, mobil = false): Promise<void> {
	await anlegenPflicht(page, kind, { name, mobil });
	for (const id of ['wetter-metriken', 'wertebereiche', 'alarme']) await ANLEGE_SEL[kind].reiter(page, id, mobil).click({ force: mobil });
	await expect(ANLEGE_SEL[kind].abschluss(page, mobil), 'Vorbedingung: Abschluss frei').toBeEnabled({ timeout: 15_000 });
}

async function sprache(page: Page, lang: 'de' | 'en'): Promise<void> {
	const res = await page.request.put('/api/auth/profile', { data: { language: lang } });
	expect(res.ok(), `Sprache ${lang} setzen: HTTP ${res.status()}`).toBeTruthy();
}

for (const kind of HUB_KINDS) {
	const sel = ANLEGE_SEL[kind];
	const art = ART[kind];
	const liste = LISTE_SEL[kind].url;

	test.describe(`Anlege-Rahmen (${kind})`, () => {
		// ── AR-1: Breadcrumb oben links, kein Abbrechen im Kopf ─────────────────
		test(`AR-1 (${kind}, 1440 px): Pfad „${art.eltern.de} / ${art.neu.de}" oben links, Elternteil Link, Kind kein Link, kein Abbrechen im Kopf`, async ({ page }) => {
			await page.setViewportSize(DESKTOP);
			await page.goto(sel.url);
			const link = elternLink(page, kind);
			await expect(link, 'AR-1: Elternteil-Link fehlt').toHaveCount(1, { timeout: 15_000 });
			const krumen = link.locator('xpath=..');
			await expect(krumen).toContainText(art.neu.de);
			await expect(link, 'AR-1: das Kind ist Teil des Links').not.toContainText(art.neu.de);
			await expect(krumen.locator('a'), 'AR-1: im Pfad darf nur der Elternteil verlinkt sein').toHaveCount(1);
			const l = await box(link, 'Elternteil-Link');
			const t = await box(titel(page), 'Titel');
			expect(l.x, 'AR-1: Pfad steht nicht links').toBeLessThan(DESKTOP.width / 2);
			expect(l.y + l.height, 'AR-1: Pfad steht nicht über dem Titel').toBeLessThanOrEqual(t.y + 1);
			for (const ab of await alleAbbrechen(page).all()) {
				const b = await box(ab, 'Abbrechen');
				expect(b.y, 'AR-1/AR-5: ein Abbrechen steht im Kopf (über dem Titel)').toBeGreaterThan(t.y + t.height);
			}
		});

		// ── AR-2: Pfad-Link ⇒ Liste, nichts angelegt (Trip: auch im bereiten Zustand kein Autosave) ──
		test(`AR-2 (${kind}, 1440 px): Klick auf den Elternteil ⇒ ${liste}, kein Anlege-Request`, async ({ page }) => {
			await page.setViewportSize(DESKTOP);
			const post = postZaehler(page, kind);
			await bereit(page, kind, einName('AR2'));
			await elternLink(page, kind).click();
			await expect.poll(() => new URL(page.url()).pathname, { message: 'AR-2: Pfad-Link führt nicht zur Liste' }).toBe(liste);
			await bleibtBei(() => post.n, 0, 1_500, 'AR-2: Pfad-Link hat gespeichert (Autosave)');
		});

		// ── AR-3: Handy — Zurück-Pfeil mit Elternteil ───────────────────────────
		test(`AR-3 (${kind}, 390 px): Zurück-Pfeil „${art.eltern.de}" oben links ⇒ ${liste}, kein Anlege-Request`, async ({ page }) => {
			await page.setViewportSize(MOBIL);
			const post = postZaehler(page, kind);
			await bereit(page, kind, einName('AR3'), true);
			const z = zurueckMobil(page);
			await expect(z, 'AR-3: genau ein sichtbarer Zurück-Pfeil').toHaveCount(1);
			// textContent statt innerText: CSS-Versalien dürfen den Katalogtext nicht ersetzen.
			expect((await z.textContent())?.trim(), 'AR-3: Beschriftung ist nicht der Elternteil aus dem Katalog').toBe(art.eltern.de);
			const b = await box(z, 'Zurück');
			const t = await box(titel(page), 'Titel');
			expect(b.x, 'AR-3: Zurück steht nicht links').toBeLessThan(MOBIL.width / 2);
			expect(b.y, 'AR-3: Zurück steht nicht über dem Titel').toBeLessThan(t.y);
			await z.click();
			await expect.poll(() => new URL(page.url()).pathname, { message: 'AR-3: Zurück führt nicht zur Liste' }).toBe(liste);
			await bleibtBei(() => post.n, 0, 1_500, 'AR-3: Zurück hat gespeichert');
		});

		// ── AR-5: Abbrechen unten links im Fuß ──────────────────────────────────
		test(`AR-5 (${kind}, 1440 px): „Abbrechen" (Btn ghost) unten links im Fuß, gleiche Zeile wie die Hauptaktion, genau einmal`, async ({ page }) => {
			await page.setViewportSize(DESKTOP);
			await page.goto(sel.url);
			const fuss = sel.desktopFuss(page);
			await expect(fuss, 'AR-5: Desktop-Fuß fehlt').toBeVisible({ timeout: 15_000 });
			await expect(alleAbbrechen(page), 'AR-5: nicht genau ein sichtbares Abbrechen').toHaveCount(1);
			await expect(sel.abbrechen(page)).toHaveAttribute('data-variant', 'ghost');
			const f = await box(fuss, 'Fuß');
			const a = await box(sel.abbrechen(page), 'Abbrechen');
			const h = await box(sel.abschluss(page), 'Hauptaktion');
			expect(mitteX(a), 'AR-5: Abbrechen steht nicht in der linken Hälfte des Fußes').toBeLessThan(f.x + f.width / 2);
			expect(a.x + a.width, 'AR-5: Abbrechen steht nicht links der Hauptaktion').toBeLessThan(h.x);
			expect(Math.abs(mitteY(a) - mitteY(h)), 'AR-5: Abbrechen und Hauptaktion nicht in einer Zeile').toBeLessThanOrEqual(8);
		});

		// ── AR-8/AR-12: Hauptaktion unten rechts, schwarz, Text je Art ──────────
		test(`AR-8 (${kind}, 1440 px): Hauptaktion „${art.abschluss.de}" unten rechts im Fuß, Hintergrund --g-ink, helle Schrift`, async ({ page }) => {
			await page.setViewportSize(DESKTOP);
			await bereit(page, kind, einName('AR8'));
			const fuss = sel.desktopFuss(page);
			const h = sel.abschluss(page);
			await expect(fuss.filter({ has: h }), 'AR-8: Hauptaktion steht nicht im Desktop-Fuß').toHaveCount(1);
			await expect(h).toHaveText(art.abschluss.de);
			const s = await stil(h);
			expect(s.grund, 'AR-8: Hauptaktion ist nicht schwarz (--g-ink)').toBe(TOKEN_RGB.ink);
			expect(s.grund).not.toBe(TOKEN_RGB.accent);
			expect(s.schrift, 'AR-8: Schrift auf der Hauptaktion nicht hell').toBe(PAPIER);
			const f = await box(fuss, 'Fuß');
			const hb = await box(h, 'Hauptaktion');
			expect(mitteX(hb), 'AR-8: Hauptaktion steht nicht rechts im Fuß').toBeGreaterThan(f.x + f.width / 2);
			const t = await box(titel(page), 'Titel');
			expect(hb.y, 'AR-8: Hauptaktion steht oben (Kopfleiste)').toBeGreaterThan(t.y + t.height);
		});

		// Je Breite ein eigener Test: ein zweites goto aus dem bereiten Trip löste sonst das Autosave aus.
		for (const vp of BREITEN) {
			test(`AR-12 (${kind}, ${vp.width} px): Abschluss heißt „${art.abschluss.de}"`, async ({ page }) => {
				const mobil = vp === MOBIL;
				await page.setViewportSize(vp);
				await bereit(page, kind, einName(`AR12-${vp.width}`), mobil);
				await expect(sel.abschluss(page, mobil), `AR-12 (${vp.width} px)`).toHaveText(art.abschluss.de);
			});
		}

		// ── AR-9: gesperrter Abschluss ──────────────────────────────────────────
		test(`AR-9 (${kind}, 1440 px): Hauptaktion anfangs gesperrt und abgeblendet, Klick ohne Request; nach den Pflichtschritten frei`, async ({ page }) => {
			await page.setViewportSize(DESKTOP);
			const post = postZaehler(page, kind);
			await page.goto(sel.url);
			const h = sel.abschluss(page);
			await expect(h).toBeDisabled({ timeout: 15_000 });
			const zu = await stil(h);
			expect(zu.deckkraft, 'AR-9: gesperrte Hauptaktion nicht sichtbar abgeblendet').toBeLessThan(1);
			expect(zu.grund, 'AR-9: gesperrte Hauptaktion wechselt die Farbe statt abzublenden').toBe(TOKEN_RGB.ink);
			await h.click({ force: true }).catch(() => {});
			await bleibtBei(() => post.n, 0, 1_000, 'AR-9: Klick auf die gesperrte Hauptaktion hat einen Request ausgelöst');
			await bereit(page, kind, einName('AR9'));
			await expect(h).toBeEnabled();
			expect((await stil(h)).deckkraft, 'AR-9: freie Hauptaktion bleibt abgeblendet').toBe(1);
		});

		// ── AR-10: Standardwerte + Hinweis im Fuß ───────────────────────────────
		test(`AR-10 (${kind}, 1440 px): „Mit Standardwerten speichern" und Hinweis im Fuß links neben der Hauptaktion, nicht im Kopf`, async ({ page }) => {
			await page.setViewportSize(DESKTOP);
			await anlegenPflicht(page, kind, { name: einName('AR10') });
			const fuss = sel.desktopFuss(page);
			const std = sel.standardwerte(page);
			await expect(fuss.filter({ has: std }), 'AR-10: Standardwerte nicht im Fuß').toHaveCount(1);
			await expect(fuss, 'AR-10: Hinweis zum Abschluss fehlt im Fuß').toContainText(sel.abschlussHinweis);
			const s = await box(std, 'Standardwerte');
			const h = await box(sel.abschluss(page), 'Hauptaktion');
			const t = await box(titel(page), 'Titel');
			expect(s.x + s.width, 'AR-10: Standardwerte steht nicht links neben der Hauptaktion').toBeLessThanOrEqual(h.x);
			expect(Math.abs(mitteY(s) - mitteY(h)), 'AR-10: Standardwerte nicht in der Zeile der Hauptaktion').toBeLessThanOrEqual(8);
			expect(s.y, 'AR-10: Standardwerte steht im Kopf').toBeGreaterThan(t.y + t.height);
		});

		// ── AR-11: Weiter orange, gesperrt nur über disabled ────────────────────
		test(`AR-11 (${kind}, 1440 px): Weiter im ersten Schritt ist Btn accent, gesperrt nur über disabled, Hinweis daneben`, async ({ page }) => {
			await page.setViewportSize(DESKTOP);
			await page.goto(sel.url);
			const w = sel.weiterErsterSchritt(page);
			await expect(w).toBeDisabled({ timeout: 15_000 });
			await expect(w).toHaveAttribute('data-variant', 'accent');
			const zu = await stil(w);
			expect(zu.grund, 'AR-11: gesperrtes Weiter ist nicht orange (--g-accent)').toBe(TOKEN_RGB.accent);
			expect(zu.inline, 'AR-11: Inline-Deckkraft am gesperrten Weiter').toBe('');
			expect(zu.deckkraft, 'AR-11: gesperrtes Weiter nicht abgeblendet').toBeLessThan(1);
			const hinweis = w.locator('xpath=..').locator('.mono').first();
			await expect(hinweis, 'AR-11: Hinweistext neben dem gesperrten Weiter fehlt').toBeVisible();
			await anlegenPflicht(page, kind, { name: einName('AR11'), nurKopf: true });
			await expect(w).toBeEnabled();
			const frei = await stil(w);
			expect(frei.grund, 'AR-11: freies Weiter ist nicht orange').toBe(TOKEN_RGB.accent);
			expect(frei.deckkraft).toBe(1);
		});

		test(`AR-11 (${kind}, 390 px): Weiter im mobilen Fuß ist orange (--g-accent), sobald frei`, async ({ page }) => {
			await page.setViewportSize(MOBIL);
			await anlegenPflicht(page, kind, { name: einName('AR11m'), mobil: true, nurKopf: true });
			const cta = sel.mobilFooter(page).getByRole('button').filter({ visible: true }).last();
			await expect(cta).toBeEnabled({ timeout: 10_000 });
			expect((await stil(cta)).grund, 'AR-11: mobiles Weiter ist nicht orange').toBe(TOKEN_RGB.accent);
		});

		// ── AR-13: mobiler Fuß über der Navigation, nicht verdeckt ──────────────
		test(`AR-13 (${kind}, 390 px): mobiler Fuß vollständig im Fenster und nicht überdeckt`, async ({ page }) => {
			await page.setViewportSize(MOBIL);
			await page.goto(sel.url);
			const fuss = sel.mobilFooter(page);
			await expect(fuss).toBeVisible({ timeout: 15_000 });
			const f = await box(fuss, 'mobiler Fuß');
			expect(f.y + f.height, 'AR-13: mobiler Fuß ragt aus dem Fenster').toBeLessThanOrEqual(MOBIL.height + 1);
			const oben = await page.evaluate(([x, y]) => {
				const el = document.elementFromPoint(x, y);
				return el?.closest('[data-testid="tn-mobile-footer"], [data-testid="cm-mobile-cta"]') !== null;
			}, [f.x + f.width / 2, f.y + f.height / 2]);
			expect(oben, 'AR-13: der mobile Fuß ist an seiner Mitte überdeckt (z. B. von der Navigation)').toBe(true);
		});

		// ── AR-16: testids ───────────────────────────────────────────────────────
		test(`AR-16 (${kind}): testids ${TESTIDS[kind].join(', ')} je genau einmal`, async ({ page }) => {
			await page.setViewportSize(DESKTOP);
			await page.goto(sel.url);
			await expect(sel.desktopFuss(page)).toBeVisible({ timeout: 15_000 });
			for (const id of TESTIDS[kind]) await expect(page.getByTestId(id), `AR-16: ${id}`).toHaveCount(1);
		});

		// ── AR-17: Vorlage ?from= ────────────────────────────────────────────────
		test(`AR-17 (${kind}): ?from=-Vorlage — Felder wie vor dem Umbau, Rahmen wie ohne Vorlage`, async ({ page }) => {
			await page.setViewportSize(DESKTOP);
			const hub = await seedHub(page.request, kind);
			try {
				const daten = (await (await page.request.get(hubApiPath(kind, hub.id))).json()) as { name: string };
				await page.goto(`${sel.url}?from=${hub.id}`);
				// Vergleich: Name „… (Kopie)" (compare-new-vorlage); Trip: /trips/new?from= ist bewusst
				// ohne Vorbelegung (feat_2277_s2c Entscheidung 1) — das bleibt so.
				await expect(sel.name(page)).toHaveValue(kind === 'vergleich' ? `${daten.name} (Kopie)` : '', { timeout: 15_000 });
				await expect(elternLink(page, kind)).toHaveCount(1);
				await expect(sel.desktopFuss(page)).toBeVisible();
				await expect(sel.abbrechen(page)).toHaveCount(1);
				await expect(sel.desktopFuss(page).filter({ has: sel.abschluss(page) })).toHaveCount(1);
			} finally {
				await hub.aufraeumen();
			}
		});

		// ── AR-18: Sticky-Fuß bei niedrigem Fenster und langem Inhalt ───────────
		test(`AR-18 (${kind}, 1440×700): Fuß mit Abbrechen und Hauptaktion bleibt am unteren Rand sichtbar, auch bei langem Inhalt`, async ({ page }, testInfo) => {
			await page.setViewportSize(NIEDRIG);
			await anlegenPflicht(page, kind, { name: einName('AR18') });
			for (const id of ['wetter-metriken', 'wertebereiche', 'alarme']) {
				await ANLEGE_SEL[kind].reiter(page, id).click();
				await page.mouse.wheel(0, 4000);
				const f = await box(sel.desktopFuss(page), `Fuß (${id})`);
				expect(f.y, `AR-18 (${id}): Fuß beginnt außerhalb des Fensters`).toBeGreaterThanOrEqual(0);
				expect(f.y + f.height, `AR-18 (${id}): Fuß ragt unten aus dem Fenster`).toBeLessThanOrEqual(NIEDRIG.height + 1);
				await expect(sel.abbrechen(page)).toBeInViewport();
				await expect(sel.abschluss(page)).toBeInViewport();
			}
			await expect(sel.abschluss(page)).toBeEnabled();
			await sel.abschluss(page).click({ trial: true });
			await page.screenshot({ path: testInfo.outputPath(`ar18-${kind}-1440x700.png`) });
		});
	});
}

// ── AR-6 (Trip) / AR-7 (Vergleich): Autosave-Semantik je Art (Whitelist Nr. 3) ────────
test.describe('Anlege-Rahmen — Abbrechen/Verlassen je Art (Whitelist Nr. 3)', () => {
	test.beforeEach(async ({ page }) => {
		await page.setViewportSize(DESKTOP);
	});

	test('AR-6 (route): Abbrechen im bereiten Zustand ⇒ /trips ohne Autosave', async ({ page }) => {
		const post = postZaehler(page, 'route');
		await bereit(page, 'route', einName('AR6a'));
		await ANLEGE_SEL.route.abbrechen(page).click();
		await expect.poll(() => new URL(page.url()).pathname, { message: 'AR-6: Abbrechen führt nicht zu /trips' }).toBe('/trips');
		await bleibtBei(() => post.n, 0, 1_500, 'AR-6: Abbrechen hat gespeichert');
	});

	test('AR-6 (route): Menü-Navigation im bereiten Zustand speichert wie bisher (Autosave unverändert)', async ({ page }) => {
		const post = postZaehler(page, 'route');
		await bereit(page, 'route', einName('AR6b'));
		await page.getByTestId('nav-home').click();
		await expect.poll(() => post.n, { message: 'AR-6: Menü-Navigation hat NICHT gespeichert (Autosave verloren)', timeout: 15_000 }).toBeGreaterThan(0);
	});

	test('AR-7 (vergleich): Abbrechen und Menü-Navigation legen nichts an; nur „Briefing aktivieren" sendet genau einen POST', async ({ page }) => {
		const post = postZaehler(page, 'vergleich');
		const sel = ANLEGE_SEL.vergleich;
		await bereit(page, 'vergleich', einName('AR7a'));
		await sel.abbrechen(page).click();
		await expect.poll(() => new URL(page.url()).pathname, { message: 'AR-7: Abbrechen führt nicht zu /compare' }).toBe('/compare');
		await bleibtBei(() => post.n, 0, 1_500, 'AR-7: Abbrechen hat einen Vergleich angelegt');

		await bereit(page, 'vergleich', einName('AR7b'));
		await page.getByTestId('nav-home').click();
		await expect.poll(() => new URL(page.url()).pathname, { message: 'AR-7: Menü-Navigation verlässt die Seite nicht' }).toBe('/');
		await bleibtBei(() => post.n, 0, 1_500, 'AR-7: Verlassen hat einen Vergleich angelegt (Entwurf/Autosave)');

		await bereit(page, 'vergleich', einName('AR7c'));
		await sel.desktopFuss(page).getByTestId('compare-editor-activate').click();
		await expect.poll(() => post.n, { message: 'AR-7: „Briefing aktivieren" sendet keinen POST', timeout: 15_000 }).toBe(1);
		await bleibtBei(() => post.n, 1, 1_500, 'AR-7: „Briefing aktivieren" sendet mehr als einen POST');
	});
});

// ── AR-4: Eyebrow je Sprache, Computer = Handy (Zweitnutzer mit Sprache de/en) ────────
for (const kind of HUB_KINDS) {
	testMitZustellbaremZiel(`AR-4 (${kind}): Eyebrow „${ART[kind].neu.de}" / „${ART[kind].neu.en}" auf Computer und Handy gleich, nie „Neue Trip"; Pfad folgt der Sprache`, async ({ page }) => {
		try {
			for (const lang of SPRACHEN) {
				await sprache(page, lang);
				const gelesen: string[] = [];
				for (const vp of BREITEN) {
					await page.setViewportSize(vp);
					await page.goto(ANLEGE_SEL[kind].url);
					await expect(eyebrow(page)).toBeVisible({ timeout: 15_000 });
					const text = (await eyebrow(page).textContent())?.trim() ?? '';
					expect(text, `AR-4 (${lang}, ${vp.width} px): Eyebrow`).toBe(ART[kind].neu[lang]);
					expect(text).not.toMatch(/Neue Trip(?!s)/);
					gelesen.push(text);
					if (vp === DESKTOP) {
						await expect(elternLink(page, kind, lang), `AR-4/AR-15 (${lang}): Elternteil-Text`).toHaveCount(1);
						await expect(elternLink(page, kind, lang).locator('xpath=..')).toContainText(ART[kind].neu[lang]);
					} else {
						expect((await zurueckMobil(page).textContent())?.trim(), `AR-3/AR-15 (${lang}): Zurück-Beschriftung`).toBe(ART[kind].eltern[lang]);
					}
				}
				expect(new Set(gelesen).size, `AR-4 (${lang}): Eyebrow Computer ≠ Handy: ${JSON.stringify(gelesen)}`).toBe(1);
			}
		} finally {
			await page.request.put('/api/auth/profile', { data: { language: 'de' } }).catch(() => {});
		}
	});
}

// E2E — Issue #2347 S4 (Epic #2345, Etappe P6): Seitenrahmen der Listenseite —
// EINE Zusicherung für die Trip-Liste (/trips) UND die Ortsvergleich-Liste
// (/compare) per Schleife über HUB_KINDS.
//
// Spec: docs/specs/modules/feat_2347_s4_paritaets_e2e.md § „Fälle" (HL-1..HL-5), AC-12.
//
// Ersetzt compare-editor-fidelity-s8d AC-1..AC-5 (mobiler Seitenkopf, kurzer
// Intro-Satz, Suchfeld nur Desktop, kompakte Stats, mobiles Padding) — dort nur
// für den Vergleich. Texte je kind stehen in LISTE_SEL (helpers.ts, Kind-Kontraste
// „HL Liste"); die Strukturaussagen sind für beide Arten dieselben.
//
// Kein fester Schlaf, kein networkidle als einziges Warten: `goto` wartet auf
// `load` (SSR-Loader), danach auf sichtbare Zustände. Läuft im isolierten CI-Stack
// (frontend/e2e/ci-stack.sh), Anmeldung über den storageState aus global.setup.ts.
// Jeder Fall legt seinen Eintrag selbst an (seedHub, Präfix E2E-GZ-) und räumt ihn
// im `finally` ab.

import { test, expect, type Page } from '@playwright/test';
import { HUB_KINDS, hubApiPath, LISTE_SEL, seedHub, type HubKind } from './helpers';

const DESKTOP = { width: 1280, height: 900 };
const MOBIL = { width: 390, height: 844 };

/** Mobiler Seitenkopf (geteilter PageHeader im mobilen Zweig der Seite). */
const mobilerKopf = (page: Page) => page.locator('.desktop\\:hidden [data-slot="page-header"]:visible');

/** Erste mobile Karte der Liste (geteilte SubscriptionCard beider Arten). */
const ersteKarte = (page: Page) =>
	page.locator('main [data-testid^="subscription-card-"]:not([data-testid^="subscription-card-menu-"]):visible').first();

const andereArt = (kind: HubKind): HubKind => (kind === 'route' ? 'vergleich' : 'route');

async function nameVon(page: Page, kind: HubKind, id: string): Promise<string> {
	const res = await page.request.get(hubApiPath(kind, id));
	expect(res.ok(), `GET ${hubApiPath(kind, id)} HTTP ${res.status()}`).toBeTruthy();
	return String(((await res.json()) as { name: string }).name);
}

/** Gemessene Geometrie der sichtbaren Stats-Zeile (Stat-Atom, layout="inline"). */
interface StatZeile {
	/** je Stat: Höhe, Label rechts neben der Zahl, Unterkanten-Abstand Zahl/Label, Label-Schrift */
	stats: Array<{ hoehe: number; labelRechts: boolean; unterkantenDiff: number; labelPx: number }>;
	/** Abstände zwischen benachbarten Stats derselben Zeile (gleiche Oberkante) */
	luecken: number[];
}

async function statZeile(page: Page, kind: HubKind): Promise<StatZeile> {
	const label = LISTE_SEL[kind].statLabel;
	const stat = page.getByText(label, { exact: true }).filter({ visible: true }).first();
	await expect(stat, `Stat „${label}" nicht sichtbar`).toBeVisible({ timeout: 15_000 });
	return page.evaluate((label) => {
		const sichtbar = (el: Element) => {
			const b = el.getBoundingClientRect();
			return b.width > 0 && b.height > 0;
		};
		// Anker: das sichtbare Stat-Label (Großschrift, Zahl als Vorgänger) — nicht
		// die gleichnamige Status-Pille der Filterleiste.
		const anker = [...document.querySelectorAll('main span')].find(
			(el) =>
				el.textContent?.trim() === label &&
				sichtbar(el) &&
				getComputedStyle(el).textTransform === 'uppercase' &&
				el.previousElementSibling !== null
		);
		const zeile = anker?.parentElement?.parentElement;
		if (!zeile) return { stats: [], luecken: [] };
		const boxen = [...zeile.children].filter(sichtbar);
		const stats = boxen.map((s) => {
			const [zahl, lab] = [s.children[0], s.children[s.children.length - 1]];
			const z = zahl.getBoundingClientRect();
			const l = lab.getBoundingClientRect();
			return {
				hoehe: s.getBoundingClientRect().height,
				labelRechts: l.left >= z.right - 0.5,
				unterkantenDiff: Math.abs(z.bottom - l.bottom),
				labelPx: parseFloat(getComputedStyle(lab).fontSize)
			};
		});
		const luecken: number[] = [];
		for (let i = 1; i < boxen.length; i++) {
			const a = boxen[i - 1].getBoundingClientRect();
			const b = boxen[i].getBoundingClientRect();
			if (Math.abs(a.top - b.top) <= 1) luecken.push(Math.round(b.left - a.right));
		}
		return { stats, luecken };
	}, label);
}

for (const kind of HUB_KINDS) {
	const liste = LISTE_SEL[kind];

	test(`HL-1 (${kind}): mobiler Seitenkopf mit Titel und Eyebrow, „Neu" führt zur Anlege-Seite; andere Liste trägt ihn nicht; Desktop unverändert`, async ({
		page
	}) => {
		const hub = await seedHub(page.request, kind);
		try {
			await page.setViewportSize(MOBIL);
			await page.goto(liste.url);
			const kopf = mobilerKopf(page);
			await expect(kopf, 'HL-1: mobiler Seitenkopf fehlt').toBeVisible({ timeout: 15_000 });
			await expect(kopf.locator('h1')).toHaveText(liste.titel);
			await expect(kopf, 'HL-1: Eyebrow fehlt').toContainText(/workspace ·/i);

			const neu = page.getByTestId(liste.neuMobil);
			await expect(neu, 'HL-1: „Neu"-Knopf im mobilen Kopf fehlt').toBeVisible();
			await neu.click();
			await expect.poll(() => new URL(page.url()).pathname).toBe(liste.anlegeUrl);

			await page.goto(LISTE_SEL[andereArt(kind)].url);
			await expect(page.getByTestId(liste.neuMobil), 'HL-1: andere Liste trägt den „Neu"-Knopf dieser Art').toHaveCount(0);

			await page.setViewportSize(DESKTOP);
			await page.goto(liste.url);
			await expect(page.getByRole('heading', { level: 1, name: liste.titel, exact: true }).filter({ visible: true })).toHaveCount(1);
			await expect(mobilerKopf(page)).toHaveCount(0);
		} finally {
			await hub.aufraeumen();
		}
	});

	test(`HL-2 (${kind}): kurzer Intro-Satz mobil sichtbar, langer Desktop-Satz mobil nicht sichtbar`, async ({ page }) => {
		const hub = await seedHub(page.request, kind);
		try {
			await page.setViewportSize(MOBIL);
			await page.goto(liste.url);
			await expect(page.getByText(liste.introKurz).filter({ visible: true }).first(), 'HL-2: kurzer Intro-Satz fehlt').toBeVisible({
				timeout: 15_000
			});
			await expect(page.getByText(liste.introLang).filter({ visible: true }), 'HL-2: langer Satz mobil sichtbar').toHaveCount(0);

			await page.setViewportSize(DESKTOP);
			await page.goto(liste.url);
			await expect(page.getByText(liste.introLang).filter({ visible: true }).first()).toBeVisible({ timeout: 15_000 });
		} finally {
			await hub.aufraeumen();
		}
	});

	test(`HL-3 (${kind}): Suchfeld mobil unsichtbar, Desktop sichtbar und filtert`, async ({ page }) => {
		const hub = await seedHub(page.request, kind);
		// Zweiter Eintrag als Filter-Gegenprobe. Seed-Feld je kind: der Vergleich startet
		// pausiert (schedule manual), weil höchstens 2 aktive Vergleiche je Nutzer erlaubt sind.
		const fremd = await seedHub(page.request, kind, { extra: kind === 'vergleich' ? { schedule: 'manual' } : {} });
		try {
			const name = await nameVon(page, kind, hub.id);
			const fremdName = await nameVon(page, kind, fremd.id);

			await page.setViewportSize(MOBIL);
			await page.goto(liste.url);
			await expect(page.locator('main').first()).toBeVisible({ timeout: 15_000 });
			await expect(page.getByPlaceholder(liste.suche).filter({ visible: true }), 'HL-3: Suchfeld mobil sichtbar').toHaveCount(0);

			await page.setViewportSize(DESKTOP);
			await page.goto(liste.url);
			const suche = page.getByPlaceholder(liste.suche).filter({ visible: true });
			await expect(suche, 'HL-3: Suchfeld auf Desktop fehlt').toBeVisible({ timeout: 15_000 });
			await expect(page.getByText(fremdName, { exact: true }).filter({ visible: true }).first()).toBeVisible();
			await suche.fill(name);
			await expect(page.getByText(name, { exact: true }).filter({ visible: true }).first()).toBeVisible();
			await expect(page.getByText(fremdName, { exact: true }).filter({ visible: true }), 'HL-3: Suche filtert nicht').toHaveCount(0);
		} finally {
			await fremd.aufraeumen();
			await hub.aufraeumen();
		}
	});

	// „Kompakte Stats" (s8d AC-4) heißt seit #2601 (Mobile-UX-Audit, Lesbarkeit
	// vor Kompaktheit) NICHT mehr kleinere Schrift: das Stat-Atom hält im
	// Inline-Layout Label 11 px / Zahl ≥ 22 px für jede Größe. Kompakt ist heute
	// die einzeilige Inline-Form (Zahl und Label nebeneinander auf einer Linie,
	// nicht gestapelt) und der engere Abstand der mobilen Zeile (20 px statt 24 px).
	test(`HL-4 (${kind}): Stats mobil kompakt — einzeilig inline, engerer Abstand als Desktop, Label ≥ 11 px`, async ({ page }) => {
		const hub = await seedHub(page.request, kind);
		try {
			await page.setViewportSize(MOBIL);
			await page.goto(liste.url);
			const mobil = await statZeile(page, kind);

			await page.setViewportSize(DESKTOP);
			await page.goto(liste.url);
			const desktop = await statZeile(page, kind);

			expect(mobil.stats.length, 'HL-4: mobile Stats-Zeile nicht gefunden').toBeGreaterThanOrEqual(3);
			for (const s of mobil.stats) {
				expect(s.labelRechts, 'HL-4: Label steht nicht rechts neben der Zahl (gestapelt statt inline)').toBe(true);
				expect(s.unterkantenDiff, 'HL-4: Zahl und Label nicht auf einer Linie').toBeLessThanOrEqual(3);
				expect(s.hoehe, `HL-4: Stat ${s.hoehe}px hoch — mehr als eine Zeile`).toBeLessThanOrEqual(28);
				expect(s.labelPx, 'HL-4: Label unter dem Lesbarkeits-Minimum 11 px (#2601)').toBeGreaterThanOrEqual(11);
			}
			expect(mobil.luecken.length, 'HL-4: keine zwei Stats nebeneinander').toBeGreaterThan(0);
			expect(desktop.luecken.length, 'HL-4: Desktop-Stats-Zeile nicht gefunden').toBeGreaterThan(0);
			for (const l of mobil.luecken) expect(l, `HL-4: mobiler Stat-Abstand ${l}px`).toBe(20);
			for (const l of desktop.luecken) expect(l, `HL-4: Desktop-Stat-Abstand ${l}px`).toBe(24);
		} finally {
			await hub.aufraeumen();
		}
	});

	test(`HL-5 (${kind}): mobil kein horizontaler Überlauf, erste Karte 12–20 px vom Rand`, async ({ page }) => {
		const hub = await seedHub(page.request, kind);
		try {
			await page.setViewportSize(MOBIL);
			await page.goto(liste.url);
			const karte = ersteKarte(page);
			await expect(karte, 'HL-5: keine mobile Karte sichtbar').toBeVisible({ timeout: 15_000 });
			const ueberlauf = await page.evaluate(() => (document.scrollingElement?.scrollWidth ?? 0) - window.innerWidth);
			expect(ueberlauf, 'HL-5: horizontaler Überlauf').toBeLessThanOrEqual(1);
			const box = await karte.boundingBox();
			expect(box, 'HL-5: Karte ohne Box').not.toBeNull();
			expect(box!.x).toBeGreaterThanOrEqual(12);
			expect(box!.x).toBeLessThanOrEqual(20);
		} finally {
			await hub.aufraeumen();
		}
	});
}

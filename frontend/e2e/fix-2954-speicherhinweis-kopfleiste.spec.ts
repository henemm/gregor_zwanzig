// E2E — Issue #2954 (ADR-0120): Speicherhinweis in der Kopfleiste statt festem Overlay unten rechts.
// Spec: docs/specs/modules/fix_2954_speicherhinweis_kopfleiste.md (AC-1 … AC-8; AC-9 Kontrast als
// Kern-Test speicheranzeige_ruhe_kontrast.test.ts, AC-10 ADR-Index als Kern-Test).
//
// Vor #2954 war der Hinweis ein `position: fixed`-Chip unten rechts über dem Inhalt (AC-1),
// nicht in der Kopfleiste (AC-2), dauerhaft „Gespeichert" (AC-3, AC-4, AC-7) und ohne aria-live (AC-8);
// diese Datei war der RED-Nachweis und sichert jetzt den neuen Stand.
//
// Kein fester Schlaf (Filter A der CI-Positivliste): Zeitfenster („nach ~4 s noch da", „über 5 s
// sichtbar") werden per `expect.poll` als Stabilitätsfenster geprüft, „nach ~6 s weg" als Frist.
// Auslöser je kind gleich: Region im Kopf speichern (geteilter SubscriptionHeader, Muster SC-5).
// Konflikt entsteht im Code bei HTTP 412 (Go `ifMatchAllows`), nicht 409 — die Spec-Formulierung
// „409" meint den Konfliktzustand; erzwungen wird er wie in trip-hub-kopf-region-aktivitaet AC-9.
// Nur Wegwerf-Daten des Testnutzers (seedHub), aufgeräumt im finally. Anmeldung über global.setup.

import { test, expect, type Locator, type Page } from '@playwright/test';
import { E2E_TEST_PREFIX, HUB_KINDS, HUB_KOPF_SEL, HUB_SEL, hubApiPath, openHub, seedHub, tippeDatum, type HubKind } from './helpers';

const BREITEN = [
	{ width: 390, height: 844 },
	{ width: 1024, height: 768 },
	{ width: 1280, height: 900 }
];
const DESKTOP = { width: 1280, height: 900 };
const AUSBLENDEN_MS = 5_000;

const hinweis = (page: Page) => page.locator('[data-testid="save-indicator"]');
const leiste = (page: Page) => page.getByTestId(HUB_KOPF_SEL.leiste);
const kebab = (page: Page) => leiste(page).locator(`[data-testid="${HUB_KOPF_SEL.kebab}"]:visible`).first();
const sendenKnopf = (page: Page) => leiste(page).locator(`[data-testid="${HUB_KOPF_SEL.senden}"]:visible`).first();
const setupKnopf = (page: Page) =>
	leiste(page).getByRole('button', { name: 'Setup abschließen' }).filter({ visible: true }).first();
const hinweisText = async (page: Page) => ((await hinweis(page).textContent()) ?? '').replace(/\s+/g, ' ').trim();

const istPut = (pfad: string) => (r: { method(): string; url(): string }) =>
	r.method() === 'PUT' && new URL(r.url()).pathname === pfad;

/** Region im Kopf bearbeiten und speichern (beide kinds, geteilter SubscriptionHeader). */
async function speichereRegion(page: Page, kind: HubKind, wert: string): Promise<void> {
	const k = HUB_SEL[kind].kopf;
	await page.locator(`[data-testid="${k}-region-edit-toggle"]:visible`).first().click();
	await page.locator(`[data-testid="${k}-region-edit"]:visible`).first().fill(wert);
	await page.locator(`[data-testid="${k}-region-save"]:visible`).first().click();
}

/** Speichernde Änderung im Punkte-Reiter (Muster hub-save-chip SC-4): Ort entfernen bzw. Etappen-Datum. */
async function loeseAenderungAus(page: Page, kind: HubKind): Promise<void> {
	if (kind === 'vergleich') {
		await expect(page.getByTestId('hub-orte-row')).toHaveCount(2, { timeout: 10_000 });
		await page.getByTestId('hub-orte-remove').first().click();
	} else {
		const feld = page.getByTestId('stage-date-field').first();
		await expect(feld).toBeVisible({ timeout: 10_000 });
		await tippeDatum(page, feld, '2027-08-22');
	}
}

/** Speichert und wartet auf die PUT-Antwort; liefert den Zeitpunkt der Antwort (ms). */
async function speichereUndWarte(page: Page, kind: HubKind, id: string, wert: string): Promise<number> {
	const antwort = page.waitForResponse((r) => istPut(hubApiPath(kind, id))(r.request()), { timeout: 15_000 });
	await speichereRegion(page, kind, wert);
	await antwort;
	return Date.now();
}

/** Berechnete Farbe eines Tokens im selben Theme-Kontext wie der Hinweis. */
async function tokenFarbe(page: Page, token: string): Promise<string> {
	return hinweis(page).evaluate((el, t) => {
		const probe = document.createElement('span');
		probe.style.color = `var(${t})`;
		(el.parentElement ?? document.body).appendChild(probe);
		const c = getComputedStyle(probe).color;
		probe.remove();
		return c;
	}, token);
}

/**
 * Stabilitätsfenster: `pruef` muss bis `bis` (ms seit Epoche) bei jedem Abtasten wahr sein.
 * Eine einzige Verletzung bleibt stehen und lässt die Zusicherung mit Zeitpunkt scheitern.
 */
async function bleibtBis(bis: number, pruef: () => Promise<boolean>, was: string): Promise<void> {
	const start = Date.now();
	let verletzt: string | null = null;
	await expect
		.poll(
			async () => {
				if (verletzt) return verletzt;
				if (!(await pruef())) {
					verletzt = `${was} — verletzt nach ${Date.now() - start} ms`;
					return verletzt;
				}
				return Date.now() >= bis ? 'stabil' : 'läuft';
			},
			{ message: was, timeout: Math.max(1_000, bis - Date.now()) + 5_000, intervals: [150] }
		)
		.toBe('stabil');
}

/** Frist: bis `bis` muss der Hinweistext leer sein. */
async function leerBis(page: Page, bis: number, was: string): Promise<void> {
	await expect
		.poll(() => hinweisText(page), { message: was, timeout: Math.max(500, bis - Date.now()), intervals: [150] })
		.toBe('');
}

async function verzoegerePuts(page: Page, pfad: string, ms: number): Promise<void> {
	await page.route(`**${pfad}`, async (route) => {
		if (route.request().method() === 'PUT') await new Promise((r) => setTimeout(r, ms));
		await route.continue();
	});
}

async function stubPuts(page: Page, pfad: string, status: number, body: Record<string, unknown>): Promise<void> {
	await page.route(`**${pfad}`, (route) =>
		route.request().method() === 'PUT'
			? route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) })
			: route.continue()
	);
}

type Befund = { geprueft: number; positionen: number; verdeckt: string[] };

/**
 * AC-1 (Messung wie #2913): scrollt den Inhalt in kleinen Schritten durch und prüft an jeder
 * Position jedes sichtbare Bedienelement — `elementFromPoint` in seiner Mitte darf nie im
 * Speicherhinweis landen.
 */
async function verdeckteBedienelemente(page: Page): Promise<Befund> {
	return page.evaluate(async () => {
		const frame = () => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
		const hint = document.querySelector('[data-testid="save-indicator"]');
		const scrollbar = (el: Element | null): el is HTMLElement =>
			!!el && el.scrollHeight > el.clientHeight + 4 && /(auto|scroll)/.test(getComputedStyle(el).overflowY);
		const main = document.querySelector('main');
		const scroller: HTMLElement = scrollbar(main) ? main : (document.scrollingElement as HTMLElement);
		const max = Math.max(0, scroller.scrollHeight - scroller.clientHeight);
		const positionen: number[] = [];
		for (let y = 0; y < max; y += 120) positionen.push(y);
		positionen.push(max);
		const SEL =
			'button, a[href], input:not([type="hidden"]), select, textarea, [role="button"], [role="tab"], ' +
			'[role="switch"], [role="checkbox"], [role="radio"], [role="slider"], [tabindex]:not([tabindex="-1"])';
		let geprueft = 0;
		const verdeckt = new Set<string>();
		for (const y of positionen) {
			scroller.scrollTop = y;
			await frame();
			for (const el of Array.from(document.querySelectorAll<HTMLElement>(SEL))) {
				if (hint && hint.contains(el)) continue;
				const r = el.getBoundingClientRect();
				if (r.width < 1 || r.height < 1) continue;
				const cx = r.left + r.width / 2;
				const cy = r.top + r.height / 2;
				if (cx < 0 || cy < 0 || cx >= window.innerWidth || cy >= window.innerHeight) continue;
				if (getComputedStyle(el).visibility === 'hidden') continue;
				geprueft++;
				const oben = document.elementFromPoint(cx, cy);
				if (oben && hint && hint.contains(oben)) {
					const name = el.getAttribute('data-testid') ?? (el.textContent ?? '').trim().slice(0, 40);
					verdeckt.add(`Scroll ${y}px: <${el.tagName.toLowerCase()}> ${name}`);
				}
			}
		}
		scroller.scrollTop = 0;
		await frame();
		return { geprueft, positionen: positionen.length, verdeckt: [...verdeckt] };
	});
}

async function box(loc: Locator, was: string) {
	const b = await loc.boundingBox();
	expect(b, `${was} hat keine Box (unsichtbar?)`).not.toBeNull();
	return b!;
}

// ─── AC-1: kein Bedienelement im Inhalt wird vom Hinweis verdeckt ─────────────────────────────
for (const kind of HUB_KINDS) {
	for (const vp of BREITEN) {
		test(`AC-1 (${kind}, ${vp.width} px): nach dem Speichern verdeckt der Hinweis an keiner Scroll-Position ein Bedienelement`, async ({
			page
		}) => {
			test.setTimeout(150_000);
			await page.setViewportSize(vp);
			const hub = await seedHub(page.request, kind);
			try {
				const befunde: string[] = [];
				let geprueft = 0;
				for (const tab of ['wetter', 'zustellung']) {
					await openHub(page, kind, hub.id, { tab });
					await speichereUndWarte(page, kind, hub.id, `AC-1 ${tab} ${vp.width}`);
					await expect(hinweis(page)).toHaveAttribute('data-state', 'idle', { timeout: 10_000 });
					await expect(hinweis(page), 'Vorbedingung: gerade gespeichert').toContainText('Gespeichert');
					const b = await verdeckteBedienelemente(page);
					geprueft += b.geprueft;
					expect(b.positionen, `Vorbedingung: Reiter ${tab} scrollt`).toBeGreaterThan(0);
					befunde.push(...b.verdeckt.map((v) => `${tab}: ${v}`));
				}
				expect(geprueft, 'Vorbedingung: Bedienelemente geprüft').toBeGreaterThan(10);
				expect(befunde, `AC-1: vom Speicherhinweis verdeckte Bedienelemente (${vp.width} px)`).toEqual([]);
			} finally {
				await hub.aufraeumen();
			}
		});
	}
}

// ─── AC-2: in der Kopfleiste, links vor Kebab und Hauptknopf (Trip, Orte, Vergleich-Entwurf) ──
const AC2_FAELLE: Array<{ name: string; kind: HubKind; entwurf: boolean }> = [
	{ name: 'Trip', kind: 'route', entwurf: false },
	{ name: 'Orte', kind: 'vergleich', entwurf: false },
	{ name: 'Vergleich-Entwurf', kind: 'vergleich', entwurf: true }
];
for (const f of AC2_FAELLE) {
	test(`AC-2 (${f.name}): nach dem Speichern genau ein Hinweis, in der Kopfleiste links vom Drei-Punkte-Menü`, async ({
		page
	}) => {
		await page.setViewportSize(DESKTOP);
		const hub = await seedHub(page.request, f.kind, f.entwurf ? { extra: { location_ids: [] } } : {});
		try {
			await openHub(page, f.kind, hub.id);
			const knopf = f.entwurf ? setupKnopf(page) : sendenKnopf(page);
			await expect(knopf, 'Vorbedingung: Hauptknopf in der Leiste').toBeVisible({ timeout: 15_000 });
			await speichereUndWarte(page, f.kind, hub.id, `AC-2 ${f.name}`);
			await expect(hinweis(page)).toContainText('Gespeichert');
			await expect(hinweis(page)).toHaveCount(1);
			const h = await box(hinweis(page), 'Speicherhinweis');
			const l = await box(leiste(page), 'Kopfleiste');
			const k = await box(kebab(page), 'Drei-Punkte-Menü');
			const s = await box(knopf, 'Hauptknopf');
			expect(h.y >= l.y - 1 && h.y + h.height <= l.y + l.height + 1, 'AC-2: Hinweis liegt nicht in der Kopfleiste (vertikal)').toBe(true);
			expect(h.x >= l.x - 1 && h.x + h.width <= l.x + l.width + 1, 'AC-2: Hinweis liegt nicht in der Kopfleiste (horizontal)').toBe(true);
			expect(h.x + h.width, 'AC-2: Hinweis steht nicht links vom Drei-Punkte-Menü').toBeLessThanOrEqual(k.x + 1);
			expect(h.x + h.width, 'AC-2: Hinweis steht nicht links vom Hauptknopf').toBeLessThanOrEqual(s.x + 1);
			expect(
				await hinweis(page).evaluate((el) => !!el.closest('[data-testid="hub-kopf-leiste"]')),
				'AC-2: Hinweis ist kein Nachfahre der Kopfleiste'
			).toBe(true);
		} finally {
			await hub.aufraeumen();
		}
	});
}

// ─── AC-3: „Gespeichert" in --g-good, 12,5 px, weg nach 5 s, Neustart je Speichern ─────────────
for (const kind of HUB_KINDS) {
	test(`AC-3 (${kind}): „Gespeichert" in --g-good/12,5 px, nach ~4 s da, nach ~6 s weg, zweites Speichern startet neu`, async ({
		page
	}) => {
		test.setTimeout(90_000);
		await page.setViewportSize(DESKTOP);
		const hub = await seedHub(page.request, kind);
		try {
			await openHub(page, kind, hub.id);
			const t0 = await speichereUndWarte(page, kind, hub.id, 'AC-3 eins');
			await expect(hinweis(page)).toHaveAttribute('data-state', 'idle', { timeout: 5_000 });
			await expect(hinweis(page)).toContainText('Gespeichert');
			// Farbe per Poll: ein CSS-Übergang (transition) darf ausklingen.
			const gut = await tokenFarbe(page, '--g-good');
			await expect
				.poll(() => hinweis(page).evaluate((el) => getComputedStyle(el).color), {
					message: 'AC-3: Erfolgsfarbe ist nicht --g-good',
					timeout: 2_000
				})
				.toBe(gut);
			expect(await hinweis(page).evaluate((el) => getComputedStyle(el).fontSize), 'AC-3: Schriftgröße').toBe('12.5px');

			await bleibtBis(t0 + 4_000, async () => (await hinweisText(page)).includes('Gespeichert'), 'AC-3: „Gespeichert" bis ~4 s nach dem Speichern');
			await leerBis(page, t0 + 6_000, 'AC-3: „Gespeichert" ist ~6 s nach dem Speichern nicht verschwunden');
			await expect(hinweis(page), 'AC-8: Region bleibt im DOM').toBeAttached();

			// Neustart: zweites Speichern ~3 s nach dem ersten — der Text hält bis 5 s nach dem ZWEITEN.
			const a = await speichereUndWarte(page, kind, hub.id, 'AC-3 zwei');
			await expect(hinweis(page)).toContainText('Gespeichert', { timeout: 5_000 });
			await bleibtBis(a + 3_000, async () => (await hinweisText(page)).includes('Gespeichert'), 'AC-3: Text nach dem zweiten Speichern');
			const b = await speichereUndWarte(page, kind, hub.id, 'AC-3 drei');
			await bleibtBis(b + 4_000, async () => (await hinweisText(page)).includes('Gespeichert'), 'AC-3: Neustart — Text bis ~4 s nach dem dritten Speichern (läge sonst nach dem Timer des zweiten)');
			await leerBis(page, b + 6_000, 'AC-3: Text ~6 s nach dem letzten Speichern nicht verschwunden');
		} finally {
			await hub.aufraeumen();
		}
	});
}

// ─── AC-4 + AC-8: beim Öffnen leer, stabile aria-live-Region, data-state folgt ────────────────
for (const kind of HUB_KINDS) {
	test(`AC-4/AC-8 (${kind}): beim Öffnen leer und im DOM, aria-live="polite", data-state folgt saving → idle`, async ({
		page
	}) => {
		test.setTimeout(60_000);
		await page.setViewportSize(DESKTOP);
		const hub = await seedHub(page.request, kind);
		try {
			await openHub(page, kind, hub.id);
			await expect(page.getByTestId(HUB_SEL[kind].reiterListe)).toBeVisible({ timeout: 15_000 });
			await expect(hinweis(page)).toBeAttached({ timeout: 10_000 });
			await expect(hinweis(page)).toHaveCount(1);
			await expect(hinweis(page)).toHaveAttribute('data-state', 'idle');
			await expect(hinweis(page), 'AC-8: aria-live="polite" fehlt').toHaveAttribute('aria-live', 'polite');
			expect(await hinweisText(page), 'AC-4: beim Öffnen ohne Speichern steht ein Hinweistext').toBe('');

			const pfad = hubApiPath(kind, hub.id);
			await verzoegerePuts(page, pfad, 800);
			await speichereRegion(page, kind, 'AC-8 Region');
			await expect(hinweis(page)).toHaveAttribute('data-state', 'saving', { timeout: 5_000 });
			await expect(hinweis(page)).toHaveAttribute('data-state', 'idle', { timeout: 10_000 });
			await expect(hinweis(page)).toContainText('Gespeichert');
			await page.unroute(`**${pfad}`);
			await leerBis(page, Date.now() + 7_000, 'AC-8: Erfolgstext verschwindet nicht');
			await expect(hinweis(page), 'AC-8: Region muss auch leer im DOM bleiben').toBeAttached();
			await expect(hinweis(page)).toHaveAttribute('aria-live', 'polite');
			await expect(hinweis(page)).toHaveAttribute('data-state', 'idle');
		} finally {
			await hub.aufraeumen();
		}
	});
}

// ─── AC-5: Speichern dauert länger als 5 s ⇒ „Speichere …" ohne Zeitablauf ─────────────────────
for (const kind of HUB_KINDS) {
	test(`AC-5 (${kind}): verzögerter PUT (> 5 s) ⇒ „Speichere …" bleibt sichtbar, solange gespeichert wird`, async ({
		page
	}) => {
		test.setTimeout(60_000);
		await page.setViewportSize(DESKTOP);
		const hub = await seedHub(page.request, kind);
		try {
			const pfad = hubApiPath(kind, hub.id);
			await openHub(page, kind, hub.id);
			await verzoegerePuts(page, pfad, 7_500);
			await speichereRegion(page, kind, 'AC-5 Region');
			await expect(hinweis(page)).toHaveAttribute('data-state', 'saving', { timeout: 5_000 });
			const t = Date.now();
			await bleibtBis(
				t + AUSBLENDEN_MS + 1_000,
				async () =>
					(await hinweis(page).getAttribute('data-state')) === 'saving' && (await hinweisText(page)).includes('Speichere'),
				'AC-5: „Speichere …" über mehr als 5 s'
			);
			await expect(hinweis(page)).toHaveAttribute('data-state', 'idle', { timeout: 10_000 });
			await page.unroute(`**${pfad}`);
		} finally {
			await hub.aufraeumen();
		}
	});
}

// ─── AC-6: Fehler (500) und Konflikt (412) bleiben dauerhaft in --g-danger-fg ──────────────────
for (const kind of HUB_KINDS) {
	for (const fall of [
		{ name: 'Fehler 500', status: 500, zustand: 'error', body: { error: 'stubbed failure' } },
		{ name: 'Konflikt 412', status: 412, zustand: 'conflict', body: { error: 'precondition_failed', detail: 'Inzwischen geaendert.' } }
	]) {
		test(`AC-6 (${kind}, ${fall.name}): Hinweis bleibt nach 7 s sichtbar, in --g-danger-fg`, async ({ page }) => {
			test.setTimeout(60_000);
			await page.setViewportSize(DESKTOP);
			const hub = await seedHub(page.request, kind);
			try {
				const pfad = hubApiPath(kind, hub.id);
				if (fall.status === 500) {
					// Ein Kopf-Feld meldet 500 am Feld selbst (nicht im Hinweis) — Auslöser wie
					// hub-save-chip SC-4: Etappen-Datum (Trip) bzw. Ort entfernen (Vergleich).
					await openHub(page, kind, hub.id, { tab: HUB_SEL[kind].punkteReiter });
					await stubPuts(page, pfad, fall.status, fall.body);
					await loeseAenderungAus(page, kind);
				} else {
					await openHub(page, kind, hub.id);
					await stubPuts(page, pfad, fall.status, fall.body);
					await speichereRegion(page, kind, `AC-6 ${fall.status}`);
				}
				await expect(hinweis(page)).toHaveAttribute('data-state', fall.zustand, { timeout: 10_000 });
				const t = Date.now();
				const vorher = await hinweisText(page);
				expect(vorher.length, 'AC-6: Fehler-/Konflikttext fehlt').toBeGreaterThan(0);
				// Farbe per Poll: ein CSS-Übergang (transition) darf ausklingen.
				const gefahr = await tokenFarbe(page, '--g-danger-fg');
				await expect
					.poll(() => hinweis(page).evaluate((el) => getComputedStyle(el).color), {
						message: 'AC-6: Farbe ist nicht --g-danger-fg',
						timeout: 3_000
					})
					.toBe(gefahr);
				const retry = hinweis(page).getByRole('button', { name: 'Nochmal speichern' });
				await bleibtBis(
					t + 7_000,
					async () =>
						(await hinweis(page).getAttribute('data-state')) === fall.zustand &&
						(await hinweisText(page)) === vorher &&
						(fall.zustand !== 'conflict' || (await retry.isVisible())),
					`AC-6: ${fall.name} muss dauerhaft sichtbar bleiben`
				);
				await expect(hinweis(page)).toBeVisible();
				if (fall.zustand === 'conflict') {
					await page.unroute(`**${pfad}`);
					const erneut = page.waitForRequest(istPut(pfad), { timeout: 10_000 });
					await retry.click();
					await erneut;
				}
			} finally {
				await page.unrouteAll({ behavior: 'ignoreErrors' });
				await hub.aufraeumen();
			}
		});
	}
}

// ─── AC-7: Kebab und Hauptknopf bleiben stehen; kein Überlauf; Pfad und Leiste ruhig ────────────
// Fix-Loop 3 (Adversary F001–F006): außer Kebab/Hauptknopf werden Brotkrumen (Breite, y),
// Leistenhöhe und die leere Region gemessen, und der Konflikt (412) bei 390/900/1024 px.
// Breiten 900/1024/1280 haben die 244-px-Seitenleiste — die Kopfleiste ist dort 656/780/1036 px breit.
const AC7_BREITEN = [390, 600, 900, 1024, 1280];
const BROTKRUMEN_MIN = 120;
const LEISTE_MAX = 200;

type Rechteck = { x: number; y: number; width: number; height: number };
type Kopfmass = {
	kebab: Rechteck;
	knopf: Rechteck;
	pfad: Rechteck;
	pfadText: Rechteck;
	leiste: Rechteck;
	hinweis: Rechteck;
	/** Rechte Kanten im Hinweis: je Flex-Zeile das letzte Kind — nicht der Kasten. */
	hinweisKanten: { flexZeilen: number[] };
	ueberlauf: number;
};

async function kopfmass(page: Page): Promise<Kopfmass> {
	const kebabBox = await box(kebab(page), 'Kebab');
	const knopfBox = await box(sendenKnopf(page), 'Hauptknopf');
	const rest = await page.evaluate(() => {
		const r = (sel: string) => {
			const el = document.querySelector(sel);
			if (!el) throw new Error(`${sel} fehlt`);
			const b = el.getBoundingClientRect();
			return { x: b.x, y: b.y, width: b.width, height: b.height };
		};
		return {
			pfad: r('[data-testid="hub-kopf-breadcrumb"]'),
			pfadText: r('[data-testid="hub-kopf-breadcrumb"] .kind'),
			leiste: r('[data-testid="hub-kopf-leiste"]'),
			hinweis: r('[data-testid="save-indicator"]'),
			hinweisKanten: (() => {
				const el = document.querySelector('[data-testid="save-indicator"]');
				if (!el) throw new Error('save-indicator fehlt');
				// Flex-Zeilen: Kinder nach Zeilenanfang (y) gruppieren, je Zeile die größte rechte Kante.
				const zeilen = new Map<number, number>();
				for (const kind of Array.from(el.children)) {
					const b = kind.getBoundingClientRect();
					if (b.width === 0 && b.height === 0) continue;
					const y = Math.round(b.y + b.height / 2);
					const schluessel = Array.from(zeilen.keys()).find((k) => Math.abs(k - y) < b.height / 2);
					const key = schluessel ?? y;
					zeilen.set(key, Math.max(zeilen.get(key) ?? -Infinity, b.right));
				}
				return { flexZeilen: Array.from(zeilen.values()) };
			})(),
			ueberlauf: document.documentElement.scrollWidth - document.documentElement.clientWidth
		};
	});
	return { kebab: kebabBox, knopf: knopfBox, ...rest };
}

/** Einzeiliger Pfad steht mittig zur Aktionszeile (Hauptknopf), ±1 px — wie vor #2954. */
function pruefeMittig(name: string, m: Kopfmass): void {
	const mitte = (b: Rechteck) => b.y + b.height / 2;
	expect(m.pfadText.height, `Vorbedingung (${name}): Pfad einzeilig`).toBeLessThan(m.knopf.height);
	expect(Math.abs(mitte(m.pfadText) - mitte(m.knopf)), `AC-7: Pfad nicht mittig zur Aktionszeile (${name})`).toBeLessThanOrEqual(1);
}

/** Kebab und Hauptknopf 0 px Abweichung, Pfad-y ±1 px, Pfad-Mindestbreite, kein Überlauf, Leiste begrenzt. */
function pruefeRuhe(name: string, vorher: Kopfmass, jetzt: Kopfmass): void {
	expect(jetzt.kebab.x, `AC-7: Kebab verschoben (${name}, x)`).toBe(vorher.kebab.x);
	expect(jetzt.kebab.y, `AC-7: Kebab verschoben (${name}, y)`).toBe(vorher.kebab.y);
	expect(jetzt.knopf.x, `AC-7: Hauptknopf verschoben (${name}, x)`).toBe(vorher.knopf.x);
	expect(jetzt.knopf.y, `AC-7: Hauptknopf verschoben (${name}, y)`).toBe(vorher.knopf.y);
	expect(Math.abs(jetzt.pfad.y - vorher.pfad.y), `AC-7: Brotkrumen springen (${name}, y ${vorher.pfad.y} → ${jetzt.pfad.y})`).toBeLessThanOrEqual(1);
	expect(jetzt.pfad.width, `AC-7: Brotkrumen gequetscht (${name})`).toBeGreaterThanOrEqual(BROTKRUMEN_MIN);
	expect(jetzt.ueberlauf, `AC-7: horizontaler Überlauf (${name})`).toBeLessThanOrEqual(0);
	expect(jetzt.leiste.height, `AC-7: Kopfleiste zu hoch (${name})`).toBeLessThanOrEqual(LEISTE_MAX);
}

for (const kind of HUB_KINDS) {
	for (const breite of AC7_BREITEN) {
		test(`AC-7 (${kind}, ${breite} px): „Gespeichert" — Kebab/Hauptknopf 0 px, Pfad und Leistenhöhe ruhig, leere Region ohne Platz`, async ({
			page
		}) => {
			test.setTimeout(60_000);
			await page.setViewportSize({ width: breite, height: 900 });
			// Üblich kurzer Name (einzeiliger Pfad): ab 600 px darf „Gespeichert" die Leiste nicht erhöhen.
			// Ein sehr langer Name kann durch den inline stehenden Hinweis eine Zeile mehr umbrechen
			// (Known Limitation); den Quetsch-Fall mit langem Namen prüft der Konflikt-Block unten.
			const hub = await seedHub(page.request, kind, { extra: { name: `${E2E_TEST_PREFIX}GR20 Nord` } });
			try {
				await openHub(page, kind, hub.id);
				await expect(sendenKnopf(page)).toBeVisible({ timeout: 15_000 });
				const vorher = await kopfmass(page);
				expect(vorher.hinweis.width, 'AC-4/AC-7: leere Region nimmt Breite ein').toBe(0);
				expect(vorher.hinweis.height, 'AC-4/AC-7: leere Region nimmt Höhe ein').toBe(0);
				expect(vorher.pfad.width, 'Vorbedingung: Brotkrumen im Leerzustand').toBeGreaterThanOrEqual(BROTKRUMEN_MIN);
				if (breite >= 600) pruefeMittig('leer', vorher);

				await speichereUndWarte(page, kind, hub.id, `AC-7 ${breite}`);
				await expect(hinweis(page)).toContainText('Gespeichert');
				const waehrend = await kopfmass(page);
				pruefeRuhe('während', vorher, waehrend);
				if (breite >= 600) {
					// Kurzer Zustand inline vor dem Kebab, in der Aktionszeile — die Leiste wächst nicht.
					expect(waehrend.hinweis.x + waehrend.hinweis.width, 'AC-2: „Gespeichert" nicht links vom Kebab').toBeLessThanOrEqual(waehrend.kebab.x + 1);
					expect(waehrend.hinweis.y, '„Gespeichert" nicht in der Aktionszeile').toBeLessThan(waehrend.kebab.y + waehrend.kebab.height);
					expect(Math.abs(waehrend.leiste.height - vorher.leiste.height), 'AC-7: Leiste wächst durch „Gespeichert"').toBeLessThanOrEqual(0.5);
				} else {
					// Eigene Zeile unter den Aktionen: der Pfad behält seine Breite.
					expect(waehrend.pfad.width, 'AC-7: Brotkrumen schmaler durch „Gespeichert"').toBeGreaterThanOrEqual(vorher.pfad.width - 1);
					// F003: rechtsbündig — rechte Kanten der Flex-Zeilen (der Kasten selbst ist ohnehin so breit wie die Aktionen) = rechte Kante des Hauptknopfs (±1 px).
					// F003: eigene Zeile rechtsbündig — jede Flex-Zeile des Hinweises endet an der rechten
					// Kante des Hauptknopfs (±1 px).
					for (const k of waehrend.hinweisKanten.flexZeilen)
						expect(Math.abs(k - (waehrend.knopf.x + waehrend.knopf.width)), 'ADR-0120: Flex-Zeile des Hinweises nicht rechtsbündig unter dem Hauptknopf').toBeLessThanOrEqual(1);
				}

				await leerBis(page, Date.now() + 7_000, 'AC-7: Hinweis verschwindet nicht');
				const nachher = await kopfmass(page);
				pruefeRuhe('nachher', vorher, nachher);
				expect(Math.abs(nachher.leiste.height - vorher.leiste.height), 'AC-7: Leistenhöhe nach Ablauf ≠ Leerzustand').toBeLessThanOrEqual(0.5);
				expect(nachher.hinweis.width + nachher.hinweis.height, 'AC-7: leere Region nimmt nach Ablauf Platz').toBe(0);
				console.log(
					`[#2954 Mess ${kind} ${breite}] Leiste ${vorher.leiste.height}/${waehrend.leiste.height}/${nachher.leiste.height} px · ` +
						`Brotkrumen ${vorher.pfad.width}/${waehrend.pfad.width}/${nachher.pfad.width} px (leer/Gespeichert/nachher)`
				);
			} finally {
				await hub.aufraeumen();
			}
		});
	}
}

// Konflikt (412, mit Knopf) UND Fehler (500, ohne Knopf) — beide stehen unter 1020 px Inhaltsbreite
// der Kopfleiste in eigener Zeile, darüber inline. Fix-Loop 4 (Adversary F001–F003): Fehlerzustand,
// Schwelle (1280 px stapelt, 1440 px inline) und rechtsbündige Kante werden gemessen.
// Gemessene Lage (Fenster − 244 px Seitenleiste − 24 px Rand = Leiste, minus 80 px Polster = Inhaltsbreite):
// 1280 px ⇒ 932 px, 1360 px ⇒ 1012 px (beide < 1020 ⇒ stapelt), 1376 px ⇒ 1028 px und 1440 px ⇒ 1092 px
// (≥ 1020 und < 1100 ⇒ inline). 1360/1376 liegen je 8 px an der Schwelle; 1440 hält sie unter 1100.
const LANGE_ZUSTAENDE = [
	{ name: 'Konflikt 412', status: 412, zustand: 'conflict', body: { error: 'precondition_failed', detail: 'Inzwischen geaendert.' } },
	{ name: 'Fehler 500', status: 500, zustand: 'error', body: { error: 'stubbed failure' } }
] as const;
const LANGE_BREITEN: { breite: number; stapelt: boolean }[] = [
	{ breite: 390, stapelt: true },
	{ breite: 900, stapelt: true },
	{ breite: 1024, stapelt: true },
	{ breite: 1280, stapelt: true },
	{ breite: 1360, stapelt: true },
	{ breite: 1376, stapelt: false },
	{ breite: 1440, stapelt: false }
];

for (const kind of HUB_KINDS) {
	for (const fall of LANGE_ZUSTAENDE) {
		for (const { breite, stapelt } of LANGE_BREITEN) {
			test(`AC-7 (${kind}, ${breite} px, ${fall.name}): ${stapelt ? 'eigene Zeile, rechtsbündig' : 'inline in der Aktionszeile'} — Kebab/Hauptknopf 0 px, Pfad ungequetscht, Leiste begrenzt`, async ({
				page
			}) => {
				test.setTimeout(60_000);
				await page.setViewportSize({ width: breite, height: 900 });
				const hub = await seedHub(page.request, kind);
				try {
					const pfad = hubApiPath(kind, hub.id);
					if (fall.status === 412) {
						await openHub(page, kind, hub.id);
					} else {
						// Fehler (500) entsteht nicht im Kopf-Feld, sondern im Punkte-Reiter (wie AC-6).
						await openHub(page, kind, hub.id, { tab: HUB_SEL[kind].punkteReiter });
					}
					await expect(sendenKnopf(page)).toBeVisible({ timeout: 15_000 });
					const vorher = await kopfmass(page);
					await stubPuts(page, pfad, fall.status, fall.body);
					if (fall.status === 412) await speichereRegion(page, kind, `AC-7 Konflikt ${breite}`);
					else await loeseAenderungAus(page, kind);
					await expect(hinweis(page)).toHaveAttribute('data-state', fall.zustand, { timeout: 10_000 });
					if (fall.zustand === 'conflict') {
						await expect(hinweis(page).getByRole('button', { name: 'Nochmal speichern' })).toBeVisible();
					}
					expect((await hinweisText(page)).length, `AC-6: ${fall.name}-Text fehlt`).toBeGreaterThan(0);
					const jetzt = await kopfmass(page);
					pruefeRuhe(fall.name, vorher, jetzt);
					if (stapelt) {
						expect(jetzt.pfad.width, `AC-7: ${fall.name} quetscht die Brotkrumen`).toBeGreaterThanOrEqual(vorher.pfad.width - 1);
						expect(jetzt.hinweis.y, `AC-7: ${fall.name} steht nicht unter der Aktionszeile`).toBeGreaterThanOrEqual(
							jetzt.kebab.y + jetzt.kebab.height - 1
						);
						// F003: eigene Zeile rechtsbündig — rechte Kanten der Flex-Zeilen (der Kasten selbst ist ohnehin so breit wie die Aktionen) = rechte Kante des Hauptknopfs.
						// F003: eigene Zeile rechtsbündig — jede Flex-Zeile des Hinweises endet an der rechten
						// Kante des Hauptknopfs (±1 px).
						for (const k of jetzt.hinweisKanten.flexZeilen)
							expect(Math.abs(k - (jetzt.knopf.x + jetzt.knopf.width)), 'ADR-0120: Flex-Zeile des Hinweises nicht rechtsbündig unter dem Hauptknopf').toBeLessThanOrEqual(1);
					} else {
						// Inhaltsbreite ≥ 1020 px: inline links vor dem Kebab, in der Aktionszeile, ohne Leistenwachstum.
						expect(jetzt.hinweis.x + jetzt.hinweis.width, `AC-2: ${fall.name} nicht links vom Kebab`).toBeLessThanOrEqual(jetzt.kebab.x + 1);
						expect(jetzt.hinweis.y, `${fall.name} nicht in der Aktionszeile`).toBeLessThan(jetzt.kebab.y + jetzt.kebab.height);
					}
					console.log(
						`[#2954 Mess ${kind} ${breite} ${fall.name}] Leiste ${vorher.leiste.height}/${jetzt.leiste.height} px (Breite ${jetzt.leiste.width}) · ` +
							`Brotkrumen ${vorher.pfad.width}/${jetzt.pfad.width} px · Hinweis ${jetzt.hinweis.width}x${jetzt.hinweis.height} @${jetzt.hinweis.x},${jetzt.hinweis.y}`
					);
				} finally {
					await page.unrouteAll({ behavior: 'ignoreErrors' });
					await hub.aufraeumen();
				}
			});
		}
	}
}


// Touch-Desktop (pointer: coarse): Btn sm hat dort 36 px Boden — der Pfad bleibt mittig zur Aktionszeile.
test.describe('AC-7 Touch-Desktop', () => {
	test.use({ hasTouch: true });
	for (const kind of HUB_KINDS) {
		test(`AC-7 (${kind}, 1024 px, Touch): einzeiliger Pfad mittig zur 36-px-Aktionszeile, „Gespeichert" ohne Sprung`, async ({ page }) => {
			test.setTimeout(60_000);
			await page.setViewportSize({ width: 1024, height: 900 });
			const hub = await seedHub(page.request, kind, { extra: { name: `${E2E_TEST_PREFIX}GR20 Nord` } });
			try {
				await openHub(page, kind, hub.id);
				await expect(sendenKnopf(page)).toBeVisible({ timeout: 15_000 });
				expect(await page.evaluate(() => matchMedia('(pointer: coarse)').matches), 'Vorbedingung: pointer coarse').toBe(true);
				const vorher = await kopfmass(page);
				pruefeMittig('Touch leer', vorher);
				await speichereUndWarte(page, kind, hub.id, 'AC-7 Touch');
				await expect(hinweis(page)).toContainText('Gespeichert');
				const waehrend = await kopfmass(page);
				pruefeRuhe('Touch während', vorher, waehrend);
				expect(Math.abs(waehrend.leiste.height - vorher.leiste.height), 'AC-7: Leiste wächst durch „Gespeichert" (Touch)').toBeLessThanOrEqual(0.5);
			} finally {
				await hub.aufraeumen();
			}
		});
	}
});

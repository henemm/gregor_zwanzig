// E2E — Issue #2879: jeder sichtbare Text auf den Trip- und Vergleichsseiten hält WCAG-AA
// (4,5:1, großer Text ab 24 px bzw. 18,66 px fett 3:1). Leitprinzip „Hoher Kontrast gewinnt"
// (design_system.md, PO 2026-05-25).
//
// Spec: docs/specs/modules/fix_2879_kontrast_wcag_aa.md — AC-1 … AC-6 (KO-Nummer = AC).
//   KO-1 Listen, Hub-Kopf, Reiterleiste, Reiter Übersicht und Etappen/Orte bei 1280 × 900, de/en.
//   KO-2 dieselben Seiten bei 390 × 844 — aktiver Handy-Reiter mit Zähler (K1/K2), Kürzel (K6).
//   KO-3 Anlegen von Trip und Vergleich, jeder ohne Netz erreichbare Schritt außerhalb der Reiter
//        Wetter/Zustellung (#2794), ohne und mit Namen, beide Größen, de/en.
//   KO-4 Liste: Status „· aktiv" und Zähler „x von y" ≥ 4,5:1; --g-ink-4 nur an Ausnahmen.
//   KO-5 aktiver „Weiter"-Knopf: Fläche --g-accent-deep, im Hover dunkler, beide ≥ 4,5:1;
//        Unterstrich des aktiven Hub-Reiters am Computer bleibt --g-accent. Dazu je Größe: JEDER
//        sichtbare Accent-Knopf (Baustein und Handy-MBtn) jedes Anlege-Zustands im Hover ≥ 4,5:1.
//   KO-6 Selbsttest des Messhelfers über page.setContent mit bekannten Farben.
//
// Gemessen wird im echten Browser über ALLEN sichtbaren Text (helpers.ts `messeKontrast`):
// Textknoten, Eingabewerte, ::before/::after-Inhalte mit Buchstaben/Ziffern; Schriftfarbe gegen den
// effektiven Hintergrund (Schichten der Vorfahrenkette gemischt; Bild/Verlauf darunter = Verstoß
// „nicht berechenbar"). Ausnahmen nach WCAG/Spec: gesperrt (`disabled`, `aria-disabled="true"`),
// `aria-hidden` NUR für Zeichen ohne Buchstabe/Ziffer, der Schriftzug der Wortmarke (WCAG 1.4.3
// „Logotypes") — je Seite höchstens eine Wortmarke, nur ihre Schriftzug-Knoten.
// Jeder Verstoß nennt Seite, Text, Farben, Verhältnis und CSS-Pfad.
//
// Pflicht-Mutationen (Spec Implementation Details 3): app.css Accent-Knopf zurück auf --g-accent,
// ListNameCell-Status zurück auf --g-ink-4, aktiver Handy-Reiter zurück auf --g-accent ⇒ KO-1/KO-2
// bzw. KO-3/KO-4 rot; Mischung transparenter Schichten im Helfer entfernt ⇒ KO-6 rot.
//
// Läuft als Admin des CI-Stacks (keine Registrierung: ein roter Fall startet den Worker neu, die
// Registrierungsbremse 5/h je IP würde sonst greifen). Sprache wird im finally auf de zurückgesetzt.
// Kein fester Schlaf, kein networkidle: gemessen wird, bis zwei Messungen in Folge gleich sind.

import { test, expect, type Locator, type Page } from '@playwright/test';
import {
	ANLEGE_SEL,
	E2E_TEST_PREFIX,
	HUB_SEL,
	TOKEN_RGB,
	cleanupTracked,
	createTestComparePreset,
	createTestLocation,
	kontrastBericht,
	kontrastVerhaeltnis,
	kontrastVerstoesse,
	messeKontrast,
	openHub,
	registerForCleanup,
	type HubKind,
	type KontrastBefund,
	type TestLocation
} from './helpers';
import * as path from 'node:path';

const DESKTOP = { width: 1280, height: 900 };
const MOBIL = { width: 390, height: 844 };
const SPRACHEN = ['de', 'en'] as const;
type Sprache = (typeof SPRACHEN)[number];

const INK4 = 'rgb(154, 149, 138)';
const GPX = path.resolve('./e2e/fixtures/test-trip.gpx');

interface Daten {
	tripId: string;
	tripName: string;
	presetId: string;
	presetName: string;
	orte: TestLocation[];
}

const tag = (d: number): string => new Date(Date.now() + d * 86_400_000).toISOString().slice(0, 10);

/** Trip mit 3 Etappen (heute … übermorgen ⇒ Status aktiv, Kürzel GR20N) und Vergleich mit 3 Orten. */
async function seed(page: Page): Promise<Daten> {
	const suffix = `${Date.now()}-${Math.floor(Math.random() * 1e6)}`;
	const tripId = `e2e-gz-2879-${suffix}`;
	const tripName = `${E2E_TEST_PREFIX}Kontrast-${suffix}`;
	const wp = (id: string, lat: number, elevation_m: number) => ({ id, name: id, lat, lon: 9.0, elevation_m });
	const res = await page.request.post('/api/trips', {
		data: {
			id: tripId,
			name: tripName,
			shortcode: 'GR20N',
			region: 'Korsika',
			stages: [0, 1, 2].map((i) => ({
				id: `s${i + 1}`,
				name: `Etappe ${i + 1}`,
				date: tag(i),
				waypoints: [wp(`a${i}`, 42.0 + i * 0.05, 800), wp(`b${i}`, 42.03 + i * 0.05, 1400)]
			})),
			report_config: { enabled: true, morning_enabled: true, evening_enabled: false, morning_time: '06:00:00', evening_time: '18:00:00' }
		}
	});
	expect(res.ok(), `Seed-Trip: HTTP ${res.status()}`).toBeTruthy();
	registerForCleanup('trip', tripId);
	const orte = [
		await createTestLocation(page.request, { lat: 47.1, lon: 11.2, elevation_m: 900 }),
		await createTestLocation(page.request, { lat: 47.2, lon: 11.3, elevation_m: 1500 }),
		await createTestLocation(page.request, { lat: 47.3, lon: 11.4, elevation_m: 2100 })
	];
	const preset = await createTestComparePreset(page.request, {
		name: `Kontrast-${suffix}`,
		locationIds: orte.map((o) => o.id)
	});
	return { tripId, tripName, presetId: preset.id, presetName: preset.name, orte };
}

async function sprache(page: Page, lang: Sprache): Promise<void> {
	const res = await page.request.put('/api/auth/profile', { data: { language: lang } });
	expect(res.ok(), `Sprache ${lang} setzen: HTTP ${res.status()}`).toBeTruthy();
}

/** Misst, bis zwei Messungen in Folge dieselben Verstöße liefern (Übergänge, Nachladen). */
async function stabileMessung(page: Page): Promise<KontrastBefund[]> {
	let vorher = '';
	let befunde: KontrastBefund[] = [];
	await expect
		.poll(
			async () => {
				befunde = await messeKontrast(page);
				const jetzt = JSON.stringify([befunde.length, kontrastBericht('', kontrastVerstoesse(befunde))]);
				const gleich = jetzt === vorher;
				vorher = jetzt;
				return gleich;
			},
			{ message: 'Kontrastmessung wird nicht stabil', timeout: 20_000, intervals: [400] }
		)
		.toBe(true);
	return befunde;
}

/** Misst die aktuelle Seite und hängt die Verstöße an `sammel` an; liefert alle Befunde. */
async function pruefe(page: Page, seite: string, sammel: string[]): Promise<KontrastBefund[]> {
	await page.mouse.move(0, 0);
	const befunde = await stabileMessung(page);
	expect(befunde.length, `${seite}: keine messbaren Textknoten`).toBeGreaterThan(5);
	sammel.push(...kontrastBericht(seite, kontrastVerstoesse(befunde)));
	// Logo-Ausnahme (WCAG 1.4.3 „Logotypes") nur am Schriftzug EINER Wortmarke: nicht an der
	// Unterzeile, nicht an einem zweiten Element, das die testid trägt.
	const logo = befunde.filter((b) => b.ausnahme === 'logo');
	const instanzen = [...new Set(logo.map((b) => b.logoInstanz))];
	expect(instanzen.length, `${seite}: Logo-Ausnahme an mehreren Wortmarken ${JSON.stringify(instanzen)}`).toBeLessThanOrEqual(1);
	const fremd = logo.filter((b) => !MARKE.has(b.text)).map((b) => `${b.text} @ ${b.pfad}`);
	expect(fremd, `${seite}: Logo-Ausnahme an Text außerhalb des Schriftzugs`).toEqual([]);
	return befunde;
}

/** Textknoten des Schriftzugs „gregor.zwanzig" (bausteine.marke.*, in beiden Sprachen gleich). */
const MARKE = new Set(['gregor', '.', 'zwanzig']);

const sichtbar = (l: Locator): Locator => l.filter({ visible: true }).first();

/** Listen und Hubs (KO-1/KO-2): beide Arten, Reiter Übersicht und Etappen/Orte. */
async function pruefeListenUndHubs(page: Page, d: Daten, wo: string, sammel: string[]): Promise<void> {
	await page.goto('/trips');
	await expect(sichtbar(page.getByText(d.tripName, { exact: true }))).toBeVisible({ timeout: 15_000 });
	await pruefe(page, `${wo} Trip-Liste`, sammel);
	await page.goto('/compare');
	await expect(sichtbar(page.getByText(d.presetName, { exact: true }))).toBeVisible({ timeout: 15_000 });
	await pruefe(page, `${wo} Vergleichsliste`, sammel);
	const hubs: [HubKind, string][] = [
		['route', d.tripId],
		['vergleich', d.presetId]
	];
	for (const [kind, id] of hubs) {
		for (const reiter of ['uebersicht', HUB_SEL[kind].punkteReiter]) {
			await openHub(page, kind, id, { tab: reiter });
			await expect(page.locator(`[data-testid="${HUB_SEL[kind].panel}-${reiter}"]:visible`).first()).toBeVisible({
				timeout: 15_000
			});
			if (reiter === 'etappen') await expect(sichtbar(page.getByText('Etappe 3'))).toBeVisible({ timeout: 15_000 });
			if (reiter === 'orte') await expect(sichtbar(page.getByText(d.orte[2].name))).toBeVisible({ timeout: 15_000 });
			await pruefe(page, `${wo} ${kind === 'route' ? 'Trip' : 'Vergleich'}-Hub ${reiter}`, sammel);
		}
	}
}

for (const [ko, vp] of [
	['KO-1', DESKTOP],
	['KO-2', MOBIL]
] as const) {
	for (const lang of SPRACHEN) {
		test(`${ko} (${vp.width} × ${vp.height}, ${lang}): Listen und Hubs — jeder sichtbare Text hält WCAG-AA`, async ({ page }) => {
			test.setTimeout(150_000);
			await page.setViewportSize(vp);
			const verstoesse: string[] = [];
			try {
				const d = await seed(page);
				await sprache(page, lang);
				await pruefeListenUndHubs(page, d, `${vp.width}px ${lang}`, verstoesse);
				if (vp === MOBIL) {
					// AC-2: K1/K2/K6 ausdrücklich gemessen (nicht nur „irgendwo auf der Seite").
					await openHub(page, 'route', d.tripId, { tab: 'etappen' });
					const aktiv = sichtbar(page.locator(`[data-testid="${HUB_SEL.route.reiter}-etappen"]`));
					const zaehler = aktiv.locator('[data-slot="segmented-badge"]');
					await expect(zaehler).toBeVisible();
					const befunde = await stabileMessung(page);
					for (const [was, text] of [
						['aktiver Reiter (K1)', (
							await aktiv.evaluate((el) =>
								Array.from(el.childNodes)
									.filter((n) => n.nodeType === Node.TEXT_NODE)
									.map((n) => n.textContent)
									.join('')
							)
						).trim()],
						['Zähler im aktiven Reiter (K2)', ((await zaehler.textContent()) ?? '').trim()],
						['Kürzel im Titel (K6)', 'GR20N']
					] as const) {
						const treffer = befunde.filter((b) => b.text === text && b.ausnahme === null);
						expect(treffer.length, `${was} „${text}" nicht gemessen`).toBeGreaterThan(0);
					}
				}
			} finally {
				await page.request.put('/api/auth/profile', { data: { language: 'de' } }).catch(() => {});
				await cleanupTracked(page.request);
			}
			expect(verstoesse, `${ko} WCAG-AA-Verstöße:\n  ${verstoesse.join('\n  ')}`).toEqual([]);
		});
	}
}

/** Anlege-Reiter der Trip-Seite nach Position (sprachneutral). */
const tripReiter = (page: Page, mobil: boolean, nr: number): Locator =>
	page.locator(mobil ? '[data-testid="tn-mobile-tabbar"] [role="tab"]' : '.tn-desktop [role="tab"]').nth(nr);

/** Messung je erreichtem Anlege-Zustand: KO-3 misst allen Text, KO-5 überfährt die Accent-Knöpfe. */
type Messe = (seite: string) => Promise<void>;

async function pruefeTripAnlegen(page: Page, mobil: boolean, wo: string, messe: Messe): Promise<void> {
	await page.goto(ANLEGE_SEL.route.url);
	await expect(ANLEGE_SEL.route.name(page, mobil)).toBeVisible({ timeout: 15_000 });
	await messe(`${wo} Trip anlegen Route ohne Namen`);
	const etappen = tripReiter(page, mobil, 1);
	await expect(async () => {
		await ANLEGE_SEL.route.name(page, mobil).fill(`${E2E_TEST_PREFIX}Kontrast-Anlegen`);
		await (mobil ? page.getByTestId('trip-new-date-input') : page.locator('.tn-desktop input[type="date"]')).fill(tag(7));
		await expect(etappen).not.toHaveAccessibleName(/⊘/, { timeout: 500 });
	}).toPass({ timeout: 10_000 });
	await messe(`${wo} Trip anlegen Route mit Namen`);
	await etappen.click({ force: mobil });
	const eingaben = page.locator(`${mobil ? '.tn-mobile' : '.tn-desktop'} input[type="file"][accept=".gpx"]`);
	await expect(eingaben.first()).toBeAttached();
	await messe(`${wo} Trip anlegen Etappen leer`);
	let rest = await eingaben.count();
	while (rest > 0) {
		const geparst = page.waitForResponse((r) => r.url().includes('/api/gpx/parse'), { timeout: 30_000 });
		await eingaben.first().setInputFiles(GPX);
		await geparst;
		rest -= 1;
		await expect(eingaben).toHaveCount(rest);
	}
	await messe(`${wo} Trip anlegen Etappen mit GPX`);
	const wegpunkte = tripReiter(page, mobil, 2);
	await expect(wegpunkte).not.toHaveAccessibleName(/⊘/);
	await wegpunkte.click({ force: mobil });
	await expect(wegpunkte).toHaveAttribute('aria-selected', 'true');
	await messe(`${wo} Trip anlegen Wegpunkte prüfen`);
}

async function pruefeVergleichAnlegen(page: Page, d: Daten, mobil: boolean, wo: string, messe: Messe): Promise<void> {
	await page.goto(ANLEGE_SEL.vergleich.url);
	await expect(ANLEGE_SEL.vergleich.name(page, mobil)).toBeVisible({ timeout: 15_000 });
	await messe(`${wo} Vergleich anlegen ohne Namen`);
	await ANLEGE_SEL.vergleich.name(page, mobil).fill(`${E2E_TEST_PREFIX}Kontrast-Anlegen`);
	const orte = ANLEGE_SEL.vergleich.reiter(page, 'orte', mobil);
	await expect(orte).not.toHaveAttribute('data-locked', 'true');
	await messe(`${wo} Vergleich anlegen mit Namen`);
	await orte.click();
	await messe(`${wo} Vergleich anlegen Orte leer`);
	if (mobil) {
		await page.getByTestId('compare-step2-mobile-library-btn').click();
		for (const ort of d.orte) await page.getByTestId(`compare-step2-mobile-lib-check-${ort.id}`).click();
		await messe(`${wo} Vergleich anlegen Orte-Bibliothek`);
		await sichtbar(page.locator('button[aria-label="Schliessen"], button[aria-label="Close"]')).click();
		await expect(page.getByTestId(`compare-step2-mobile-lib-check-${d.orte[0].id}`)).toBeHidden();
	} else {
		const bibliothek = sichtbar(page.locator('[data-testid="compare-step2-library"]'));
		await expect(bibliothek).toBeVisible({ timeout: 10_000 });
		for (const ort of d.orte) await bibliothek.getByText(ort.name, { exact: true }).click();
	}
	await messe(`${wo} Vergleich anlegen Orte gewählt`);
}

for (const vp of [DESKTOP, MOBIL]) {
	for (const lang of SPRACHEN) {
		test(`KO-3 (${vp.width} × ${vp.height}, ${lang}): Anlegen von Trip und Vergleich — jeder Schritt ohne und mit Namen hält WCAG-AA`, async ({ page }) => {
			test.setTimeout(180_000);
			await page.setViewportSize(vp);
			const mobil = vp === MOBIL;
			const verstoesse: string[] = [];
			try {
				const d = await seed(page);
				await sprache(page, lang);
				const messe: Messe = async (seite) => void (await pruefe(page, seite, verstoesse));
				await pruefeTripAnlegen(page, mobil, `${vp.width}px ${lang}`, messe);
				await pruefeVergleichAnlegen(page, d, mobil, `${vp.width}px ${lang}`, messe);
			} finally {
				await page.request.put('/api/auth/profile', { data: { language: 'de' } }).catch(() => {});
				await cleanupTracked(page.request);
			}
			expect(verstoesse, `KO-3 WCAG-AA-Verstöße:\n  ${verstoesse.join('\n  ')}`).toEqual([]);
		});
	}
}

test('KO-4: Listen — Status „· aktiv" und Zähler „x von y" ≥ 4,5:1, --g-ink-4 nur an gesperrten Elementen', async ({ page }) => {
	test.setTimeout(120_000);
	const befunde: string[] = [];
	try {
		const d = await seed(page);
		for (const vp of [DESKTOP, MOBIL]) {
			await page.setViewportSize(vp);
			for (const [liste, name] of [
				['/trips', d.tripName],
				['/compare', d.presetName]
			] as const) {
				await page.goto(liste);
				await expect(sichtbar(page.getByText(name, { exact: true }))).toBeVisible({ timeout: 15_000 });
				const alle = await stabileMessung(page);
				const wo = `${vp.width}px ${liste}`;
				const gefunden = { status: 0, zaehler: 0 };
				for (const b of alle) {
					const art = /^·\s*\S/.test(b.text) ? 'status' : /^\d+ von \d+/.test(b.text) ? 'zaehler' : null;
					if (art) {
						gefunden[art] += 1;
						if (b.verhaeltnis < 4.5) befunde.push(`${wo} ${art} ${JSON.stringify(b.text)}: ${b.verhaeltnis}:1 (${b.farbe} auf ${b.hintergrund}) @ ${b.pfad}`);
					}
					if (b.farbeRoh === INK4 && b.ausnahme === null) {
						befunde.push(`${wo} --g-ink-4 als Lesetext ${JSON.stringify(b.text)} @ ${b.pfad}`);
					}
				}
				// Statuszeile „· …" und Zähler stehen nur in der Computer-Ansicht; am Handy trägt die
				// Karte den Status ohne Punkt — dort greift die --g-ink-4-Prüfung oben.
				if (vp === DESKTOP) {
					expect(gefunden.status, `${wo}: Statuszeile „· …" nicht gemessen`).toBeGreaterThan(0);
					expect(gefunden.zaehler, `${wo}: Zähler „x von y" nicht gemessen`).toBeGreaterThan(0);
				}
			}
		}
	} finally {
		await cleanupTracked(page.request);
	}
	expect(befunde, `KO-4:\n  ${[...new Set(befunde)].join('\n  ')}`).toEqual([]);
});

/** Hintergrund und Schrift eines Knopfs (als rgb), gepollt bis die Übergangs-Animation steht. */
async function knopfFarben(knopf: Locator): Promise<{ grund: string; schrift: string }> {
	let vorher = '';
	let wert = { grund: '', schrift: '' };
	await expect
		.poll(async () => {
			wert = await knopf.evaluate((el) => {
				// color-mix() liefert z. B. oklab(…) — über eine 1×1-Leinwand nach rgb() übersetzen.
				const alsRgb = (farbe: string): string => {
					const ctx = document.createElement('canvas').getContext('2d')!;
					ctx.fillStyle = farbe;
					ctx.fillRect(0, 0, 1, 1);
					const [r, g, b] = ctx.getImageData(0, 0, 1, 1).data;
					return `rgb(${r}, ${g}, ${b})`;
				};
				return { grund: alsRgb(getComputedStyle(el).backgroundColor), schrift: alsRgb(getComputedStyle(el).color) };
			});
			const s = JSON.stringify(wert);
			const gleich = s === vorher;
			vorher = s;
			return gleich;
		}, { timeout: 10_000, intervals: [250] })
		.toBe(true);
	return wert;
}

const helligkeit = (c: string): number => kontrastVerhaeltnis(c, 'rgb(0, 0, 0)');

test('KO-5: aktiver „Weiter"-Knopf — Fläche --g-accent-deep, im Hover dunkler, beide ≥ 4,5:1; Hub-Unterstrich bleibt --g-accent', async ({ page }) => {
	test.setTimeout(90_000);
	await page.setViewportSize(DESKTOP);
	try {
		const d = await seed(page);
		for (const kind of ['route', 'vergleich'] as const) {
			await page.goto(ANLEGE_SEL[kind].url);
			await expect(ANLEGE_SEL[kind].name(page)).toBeVisible({ timeout: 15_000 });
			if (kind === 'route') {
				await expect(async () => {
					await ANLEGE_SEL.route.name(page).fill(`${E2E_TEST_PREFIX}Kontrast-Weiter`);
					await page.locator('.tn-desktop input[type="date"]').fill(tag(7));
					await expect(ANLEGE_SEL.route.weiterErsterSchritt(page)).toBeEnabled({ timeout: 500 });
				}).toPass({ timeout: 10_000 });
			} else {
				await ANLEGE_SEL.vergleich.name(page).fill(`${E2E_TEST_PREFIX}Kontrast-Weiter`);
			}
			const weiter = ANLEGE_SEL[kind].weiterErsterSchritt(page);
			await expect(weiter).toBeEnabled();
			await page.mouse.move(0, 0);
			const ruhe = await knopfFarben(weiter);
			expect(ruhe.grund, `${kind}: Weiter-Fläche = --g-accent-deep`).toBe(TOKEN_RGB.accentDeep);
			expect(kontrastVerhaeltnis(ruhe.schrift, ruhe.grund), `${kind}: Weiter ${ruhe.schrift} auf ${ruhe.grund}`).toBeGreaterThanOrEqual(4.5);
			expect(helligkeit(ruhe.schrift), `${kind}: Weiter-Schrift hell`).toBeGreaterThan(15);
			await weiter.hover();
			await expect.poll(async () => (await knopfFarben(weiter)).grund, { timeout: 5_000 }).not.toBe(ruhe.grund);
			const hover = await knopfFarben(weiter);
			expect(helligkeit(hover.grund), `${kind}: Hover-Fläche ${hover.grund} dunkler als ${ruhe.grund}`).toBeLessThan(helligkeit(ruhe.grund));
			expect(kontrastVerhaeltnis(hover.schrift, hover.grund), `${kind}: Hover ${hover.schrift} auf ${hover.grund}`).toBeGreaterThanOrEqual(4.5);
		}
		await openHub(page, 'route', d.tripId, { tab: 'uebersicht' });
		const aktiv = sichtbar(page.locator(`[data-testid="${HUB_SEL.route.reiter}-uebersicht"]`));
		await expect(aktiv).toHaveAttribute('aria-selected', 'true');
		expect(await aktiv.evaluate((el) => getComputedStyle(el).borderBottomColor), 'Unterstrich aktiver Hub-Reiter').toBe(TOKEN_RGB.accent);
	} finally {
		await cleanupTracked(page.request);
	}
});

/** Accent-Knöpfe: Bausteinknopf (`[data-slot="btn"]`) und Handy-Knopf MBtn (`data-size`). */
const ACCENT_KNOPF = '[data-slot="btn"][data-variant="accent"], button[data-variant="accent"][data-size]';

/**
 * Überfährt jeden sichtbaren, nicht gesperrten Accent-Knopf und misst seinen Text im Hover-Zustand
 * (Verstöße nach `sammel`). Verdeckte Knöpfe (z. B. hinter einem offenen Blatt) sind nicht
 * überfahrbar und werden übersprungen. Liefert die Zahl je Knopfart.
 */
async function pruefeAccentHover(page: Page, seite: string, sammel: string[]): Promise<{ btn: number; mbtn: number }> {
	const zahl = { btn: 0, mbtn: 0 };
	for (const knopf of await page.locator(ACCENT_KNOPF).all()) {
		if (!(await knopf.isVisible()) || !(await knopf.isEnabled())) continue;
		await knopf.scrollIntoViewIfNeeded();
		const oben = await knopf.evaluate((el) => {
			const r = el.getBoundingClientRect();
			const treffer = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
			return !!treffer && el.contains(treffer);
		});
		if (!oben) continue;
		await knopf.hover();
		let vorher = '';
		let befunde: KontrastBefund[] = [];
		await expect
			.poll(
				async () => {
					befunde = await messeKontrast(knopf);
					const jetzt = JSON.stringify(befunde.map((b) => [b.text, b.farbe, b.hintergrund]));
					const gleich = jetzt === vorher;
					vorher = jetzt;
					return gleich;
				},
				{ message: `${seite}: Hover-Messung wird nicht stabil`, timeout: 10_000, intervals: [250] }
			)
			.toBe(true);
		const name = ((await knopf.textContent()) ?? '').trim();
		expect(befunde.length, `${seite}: Accent-Knopf „${name}" ohne messbaren Text`).toBeGreaterThan(0);
		sammel.push(...kontrastBericht(`${seite} Hover`, kontrastVerstoesse(befunde)));
		zahl[(await knopf.getAttribute('data-slot')) === 'btn' ? 'btn' : 'mbtn'] += 1;
	}
	await page.mouse.move(0, 0);
	return zahl;
}

for (const vp of [DESKTOP, MOBIL]) {
	test(`KO-5 (${vp.width} × ${vp.height}): jeder sichtbare Accent-Knopf der Anlege-Seiten hält auch im Hover WCAG-AA`, async ({ page }) => {
		test.setTimeout(150_000);
		await page.setViewportSize(vp);
		const mobil = vp === MOBIL;
		const verstoesse: string[] = [];
		const gesamt = { btn: 0, mbtn: 0 };
		try {
			const d = await seed(page);
			const messe: Messe = async (seite) => {
				const zahl = await pruefeAccentHover(page, seite, verstoesse);
				gesamt.btn += zahl.btn;
				gesamt.mbtn += zahl.mbtn;
			};
			await pruefeTripAnlegen(page, mobil, `${vp.width}px`, messe);
			await pruefeVergleichAnlegen(page, d, mobil, `${vp.width}px`, messe);
		} finally {
			await cleanupTracked(page.request);
		}
		// Ohne überfahrene Knöpfe wäre der Test leer grün: am Computer die Bausteinknöpfe
		// (Weiter je Schritt), am Handy mindestens der MBtn unten („Orte hinzufügen").
		if (mobil) expect(gesamt.mbtn, 'Handy: kein Accent-MBtn überfahren').toBeGreaterThan(0);
		else expect(gesamt.btn, 'Computer: zu wenige Accent-Knöpfe überfahren').toBeGreaterThanOrEqual(2);
		expect(verstoesse, `KO-5 Hover-Verstöße:\n  ${verstoesse.join('\n  ')}`).toEqual([]);
	});
}

test('KO-6: Messhelfer — meldet genau die bekannten Verstöße einer Testseite, Ausnahmen nicht', async ({ page }) => {
	await page.setContent(`<!doctype html><html><head><style>
		.nach::after { content: "nachher-schwach"; color: #9a958a; }
		.vor::before { content: "\\203A"; color: #9a958a; }
	</style></head><body style="margin:0;background:#f6f4ee;font:13px sans-serif">
		<p id="ok" style="color:#1a1a18">deckend-gut</p>
		<p style="color:#9a958a">deckend-schwach</p>
		<div style="background:#c45a2a;padding:4px"><span style="background:rgba(255,255,255,0.22);color:#f6f4ee">transluzent-zaehler</span></div>
		<div style="background:#1a1a18;padding:4px"><span style="background:rgba(255,255,255,0.9);color:#1a1a18">transluzent-hell</span></div>
		<div style="background:#ffffff;padding:4px"><span style="background:rgba(0,0,0,0.5);color:#ffffff">transluzent-dunkel</span></div>
		<div style="opacity:.5"><span style="color:#1a1a18">opazitaet-kette</span></div>
		<p style="color:#c45a2a;font-size:24px">gross-ok</p>
		<p style="color:#c45a2a;font-size:23px">fast-gross</p>
		<p style="color:#c45a2a;font-size:18.66px;font-weight:700">fett-gross-ok</p>
		<p style="color:#c45a2a;font-size:18.65px;font-weight:700">fett-fast-gross</p>
		<svg width="240" height="30"><text x="0" y="20" fill="#9a958a" style="color:#1a1a18">svg-fuellung-schwach</text></svg>
		<input value="eingabe-schwach" style="color:#9a958a;background:#f6f4ee">
		<input placeholder="platzhalter-leer" style="color:#9a958a;background:#f6f4ee">
		<input disabled value="eingabe-gesperrt" style="color:#9a958a;background:#f6f4ee">
		<p class="nach" style="color:#1a1a18">vorher-gut</p>
		<p class="vor" style="color:#1a1a18">glyph-davor</p>
		<p style="background:color-mix(in oklab, #1a1a18 60%, #000);color:#1a1a18">mischfarbe-grund</p>
		<div style="background-image:linear-gradient(#1a1a18,#1a1a18)"><span style="color:#1a1a18">bild-grund</span></div>
		<div style="background-image:linear-gradient(#1a1a18,#1a1a18)"><span style="background:#f6f4ee;color:#1a1a18">bild-ueberdeckt</span></div>
		<button disabled style="color:#9a958a;background:#f6f4ee">gesperrt-knopf</button>
		<div aria-disabled="true"><span style="color:#9a958a">gesperrt-aria</span></div>
		<span aria-hidden="true" style="color:#9a958a">versteckt-buchstaben</span>
		<p><span aria-hidden="true" style="color:#9a958a">· › ×</span></p>
		<span data-testid="brand-wordmark"><span class="typo-row" style="color:#9a958a"><span>logo-wortmarke</span></span><span class="caption" style="color:#9a958a">logo-unterzeile</span></span>
		<p data-testid="brand-wordmark" style="color:#9a958a">fremd-testid</p>
		<span style="display:none;color:#9a958a">unsichtbar</span>
	</body></html>`);
	const befunde = await messeKontrast(page);
	const je = Object.fromEntries(befunde.map((b) => [b.text, b]));
	const verstoesse = kontrastVerstoesse(befunde).map((b) => b.text).sort();
	expect(verstoesse, 'genau die bekannten Verstöße').toEqual(
		[
			'bild-grund',
			'deckend-schwach',
			'eingabe-schwach',
			'fast-gross',
			'fett-fast-gross',
			'fremd-testid',
			'logo-unterzeile',
			'mischfarbe-grund',
			'nachher-schwach',
			'opazitaet-kette',
			'svg-fuellung-schwach',
			'transluzent-dunkel',
			'transluzent-zaehler',
			'versteckt-buchstaben'
		].sort()
	);
	// Papier auf rgba(255,255,255,0.22) über Accent = 2,79:1 (Spec K2) — nur mit Mischung.
	expect(je['transluzent-zaehler'].verhaeltnis).toBeCloseTo(2.79, 1);
	expect(je['transluzent-zaehler'].hintergrund).toBe('rgb(209, 126, 89)');
	expect(je['transluzent-hell'].verhaeltnis).toBeGreaterThan(10);
	expect(je['transluzent-dunkel'].verhaeltnis).toBeLessThan(4.5);
	// Opacity der Vorfahren dünnt die Schrift aus: Ink mit 50 % auf Papier < 4,5:1.
	expect(je['opazitaet-kette'].farbe).not.toBe('rgb(26, 26, 24)');
	// Großer Text: Grenzen genau 24 px bzw. 18,66 px bei Gewicht 700.
	expect([je['gross-ok'].schwelle, je['fast-gross'].schwelle]).toEqual([3, 4.5]);
	expect([je['fett-gross-ok'].schwelle, je['fett-fast-gross'].schwelle]).toEqual([3, 4.5]);
	// SVG-Text zählt mit fill, nicht mit color.
	expect(je['svg-fuellung-schwach'].farbeRoh).toBe('rgb(154, 149, 138)');
	expect(je['eingabe-schwach'].quelle).toBe('eingabe');
	expect(je['platzhalter-leer'], 'Platzhalter wird nicht gemessen').toBeUndefined();
	expect(je['eingabe-gesperrt'].ausnahme).toBe('gesperrt');
	expect(je['nachher-schwach'].quelle).toBe('::after');
	expect(je['›'], 'Pseudo-Glyphe ohne Buchstabe/Ziffer wird nicht gemessen').toBeUndefined();
	// color-mix() liefert oklab(…) — der Grund muss trotzdem zählen (sonst Papier statt Ink).
	expect(kontrastVerhaeltnis(je['mischfarbe-grund'].hintergrund, 'rgb(0, 0, 0)')).toBeLessThan(2);
	expect(je['bild-grund'].berechenbar).toBe(false);
	expect(je['bild-ueberdeckt'].berechenbar).toBe(true);
	expect(je['gesperrt-knopf'].ausnahme).toBe('gesperrt');
	expect(je['gesperrt-aria'].ausnahme).toBe('gesperrt');
	expect(je['versteckt-buchstaben'].ausnahme, 'aria-hidden ist keine Ausnahme für Lesetext').toBeNull();
	expect(je['· › ×'].ausnahme).toBe('aria-hidden');
	expect(je['logo-wortmarke'].ausnahme).toBe('logo');
	expect(je['logo-wortmarke'].logoInstanz).toBe(0);
	expect(je['logo-unterzeile'].ausnahme, 'Unterzeile ist kein Logotyp').toBeNull();
	expect(je['fremd-testid'].ausnahme, 'testid allein ist kein Logotyp').toBeNull();
	expect(je.unsichtbar, 'display:none wird nicht gemessen').toBeUndefined();
	expect(je['deckend-gut'].pfad).toContain('p');
});

// E2E — Issue #2879: jeder sichtbare Text auf den Trip- und Vergleichsseiten hält WCAG-AA
// (4,5:1, großer Text ab 24 px bzw. 18,66 px fett 3:1). Leitprinzip „Hoher Kontrast gewinnt"
// (design_system.md, PO 2026-05-25).
//
// Spec: docs/specs/modules/fix_2879_kontrast_wcag_aa.md — AC-1 … AC-6 (KO-Nummer = AC).
//   KO-1 Listen, Hub-Kopf, Reiterleiste, Reiter Übersicht und Etappen/Orte bei 1280 × 900, de/en.
//   KO-2 dieselben Seiten bei 390 × 844 — aktiver Handy-Reiter mit Zähler (K1/K2), Kürzel (K6).
//   KO-3 Anlegen von Trip und Vergleich, jeder ohne Netz erreichbare Schritt außerhalb der Reiter
//        Wetter-Metriken/Wertebereiche/Alarme (#2794), ohne und mit Namen, beide Größen, de/en.
//   KO-4 Liste: Status „· aktiv" und Zähler „x von y" ≥ 4,5:1; --g-ink-4 nur an Ausnahmen.
//   KO-5 aktiver „Weiter"-Knopf: Fläche --g-accent-deep, im Hover dunkler, beide ≥ 4,5:1;
//        Unterstrich des aktiven Hub-Reiters am Computer bleibt --g-accent.
//   KO-6 Selbsttest des Messhelfers über page.setContent mit bekannten Farben.
//
// Gemessen wird im echten Browser über ALLE sichtbaren Textknoten (helpers.ts `messeKontrast`):
// Schriftfarbe gegen den effektiven Hintergrund (Schichten der Vorfahrenkette gemischt).
// Ausnahmen nach WCAG/Spec: gesperrt (`disabled`, `aria-disabled="true"`), `aria-hidden`; dazu das
// Logo (Wortmarke, WCAG 1.4.3 „Logotypes": keine Mindestanforderung).
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
	return befunde;
}

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

async function pruefeTripAnlegen(page: Page, mobil: boolean, wo: string, sammel: string[]): Promise<void> {
	await page.goto(ANLEGE_SEL.route.url);
	await expect(ANLEGE_SEL.route.name(page, mobil)).toBeVisible({ timeout: 15_000 });
	await pruefe(page, `${wo} Trip anlegen Route ohne Namen`, sammel);
	const etappen = tripReiter(page, mobil, 1);
	await expect(async () => {
		await ANLEGE_SEL.route.name(page, mobil).fill(`${E2E_TEST_PREFIX}Kontrast-Anlegen`);
		await (mobil ? page.getByTestId('trip-new-date-input') : page.locator('.tn-desktop input[type="date"]')).fill(tag(7));
		await expect(etappen).not.toHaveAccessibleName(/⊘/, { timeout: 500 });
	}).toPass({ timeout: 10_000 });
	await pruefe(page, `${wo} Trip anlegen Route mit Namen`, sammel);
	await etappen.click({ force: mobil });
	const eingaben = page.locator(`${mobil ? '.tn-mobile' : '.tn-desktop'} input[type="file"][accept=".gpx"]`);
	await expect(eingaben.first()).toBeAttached();
	await pruefe(page, `${wo} Trip anlegen Etappen leer`, sammel);
	let rest = await eingaben.count();
	while (rest > 0) {
		const geparst = page.waitForResponse((r) => r.url().includes('/api/gpx/parse'), { timeout: 30_000 });
		await eingaben.first().setInputFiles(GPX);
		await geparst;
		rest -= 1;
		await expect(eingaben).toHaveCount(rest);
	}
	await pruefe(page, `${wo} Trip anlegen Etappen mit GPX`, sammel);
	const wegpunkte = tripReiter(page, mobil, 2);
	await expect(wegpunkte).not.toHaveAccessibleName(/⊘/);
	await wegpunkte.click({ force: mobil });
	await expect(wegpunkte).toHaveAttribute('aria-selected', 'true');
	await pruefe(page, `${wo} Trip anlegen Wegpunkte prüfen`, sammel);
}

async function pruefeVergleichAnlegen(page: Page, d: Daten, mobil: boolean, wo: string, sammel: string[]): Promise<void> {
	await page.goto(ANLEGE_SEL.vergleich.url);
	await expect(ANLEGE_SEL.vergleich.name(page, mobil)).toBeVisible({ timeout: 15_000 });
	await pruefe(page, `${wo} Vergleich anlegen ohne Namen`, sammel);
	await ANLEGE_SEL.vergleich.name(page, mobil).fill(`${E2E_TEST_PREFIX}Kontrast-Anlegen`);
	const orte = ANLEGE_SEL.vergleich.reiter(page, 'orte', mobil);
	await expect(orte).not.toHaveAttribute('data-locked', 'true');
	await pruefe(page, `${wo} Vergleich anlegen mit Namen`, sammel);
	await orte.click();
	await pruefe(page, `${wo} Vergleich anlegen Orte leer`, sammel);
	if (mobil) {
		await page.getByTestId('compare-step2-mobile-library-btn').click();
		for (const ort of d.orte) await page.getByTestId(`compare-step2-mobile-lib-check-${ort.id}`).click();
		await pruefe(page, `${wo} Vergleich anlegen Orte-Bibliothek`, sammel);
		await sichtbar(page.locator('button[aria-label="Schliessen"], button[aria-label="Close"]')).click();
		await expect(page.getByTestId(`compare-step2-mobile-lib-check-${d.orte[0].id}`)).toBeHidden();
	} else {
		const bibliothek = sichtbar(page.locator('[data-testid="compare-step2-library"]'));
		await expect(bibliothek).toBeVisible({ timeout: 10_000 });
		for (const ort of d.orte) await bibliothek.getByText(ort.name, { exact: true }).click();
	}
	await pruefe(page, `${wo} Vergleich anlegen Orte gewählt`, sammel);
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
				await pruefeTripAnlegen(page, mobil, `${vp.width}px ${lang}`, verstoesse);
				await pruefeVergleichAnlegen(page, d, mobil, `${vp.width}px ${lang}`, verstoesse);
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

test('KO-6: Messhelfer — meldet genau die bekannten Verstöße einer Testseite, Ausnahmen nicht', async ({ page }) => {
	await page.setContent(`<!doctype html><html><body style="margin:0;background:#f6f4ee;font:13px sans-serif">
		<p id="ok" style="color:#1a1a18">deckend-gut</p>
		<p style="color:#9a958a">deckend-schwach</p>
		<div style="background:#c45a2a;padding:4px"><span style="background:rgba(255,255,255,0.22);color:#f6f4ee">transluzent-zaehler</span></div>
		<div style="background:#1a1a18;padding:4px"><span style="background:rgba(255,255,255,0.9);color:#1a1a18">transluzent-hell</span></div>
		<div style="background:#ffffff;padding:4px"><span style="background:rgba(0,0,0,0.5);color:#ffffff">transluzent-dunkel</span></div>
		<p style="color:#c45a2a;font-size:24px">gross-ok</p>
		<button disabled style="color:#9a958a;background:#f6f4ee">gesperrt-knopf</button>
		<div aria-disabled="true"><span style="color:#9a958a">gesperrt-aria</span></div>
		<span aria-hidden="true" style="color:#9a958a">versteckt-aria</span>
		<span data-testid="brand-wordmark"><span style="color:#9a958a">logo-wortmarke</span></span>
		<span style="display:none;color:#9a958a">unsichtbar</span>
	</body></html>`);
	const befunde = await messeKontrast(page);
	const je = Object.fromEntries(befunde.map((b) => [b.text, b]));
	const verstoesse = kontrastVerstoesse(befunde).map((b) => b.text).sort();
	expect(verstoesse, 'genau die bekannten Verstöße').toEqual(['deckend-schwach', 'transluzent-dunkel', 'transluzent-zaehler']);
	// Papier auf rgba(255,255,255,0.22) über Accent = 2,79:1 (Spec K2) — nur mit Mischung.
	expect(je['transluzent-zaehler'].verhaeltnis).toBeCloseTo(2.79, 1);
	expect(je['transluzent-zaehler'].hintergrund).toBe('rgb(209, 126, 89)');
	expect(je['transluzent-hell'].verhaeltnis).toBeGreaterThan(10);
	expect(je['transluzent-dunkel'].verhaeltnis).toBeLessThan(4.5);
	expect(je['gross-ok'].schwelle).toBe(3);
	expect(je['gesperrt-knopf'].ausnahme).toBe('gesperrt');
	expect(je['gesperrt-aria'].ausnahme).toBe('gesperrt');
	expect(je['versteckt-aria'].ausnahme).toBe('aria-hidden');
	expect(je['logo-wortmarke'].ausnahme).toBe('logo');
	expect(je.unsichtbar, 'display:none wird nicht gemessen').toBeUndefined();
	expect(je['deckend-gut'].pfad).toContain('p');
});

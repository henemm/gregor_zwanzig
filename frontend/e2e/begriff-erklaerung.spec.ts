// E2E — Issue #2521 Scheibe S1 (Spec docs/specs/modules/begriff_erklaerung_infobox.md):
// Begriff-Erklaerung (ⓘ-Sprechblase) und Infobox „Kannst du ueberspringen —
// Standard: …“ in den Anlege-Reitern von /trips/new und /compare/new.
//
//   AC-1..AC-5  Infobox je Reiter (Trip + Ortsvergleich), Pflichtreiter ohne
//   AC-7        Infobox bleibt, kein Schliessen-Knopf, nichts gespeichert/gesendet
//   AC-8        ⓘ Wertebereiche — Desktop UND Mobil (CorridorEditor / CorridorEditorMobile)
//   AC-9        ⓘ Dringlichkeits-Schwelle (sichtbares Label), Trip UND Ortsvergleich
//   AC-10       (kein Browserfall, s. u.; Kernfall am Baustein)
//   AC-11       ⓘ Cooldown, Hinweistext bleibt
//   AC-12       Esc und Klick daneben schliessen, Fokus zurueck auf dem ⓘ
//   AC-13       Tastatur (Enter, Leertaste) ohne Mauszeiger; sprechender Name
//   AC-16       keine Konsolenfehler beim Durchlauf aller Reiter und Oeffnen/Schliessen
//
// Warum im Browser: das Popover-Portal, die Fokus-Rueckgabe und `onOpenChange`
// laufen im SSR-Harness nie (Kernsuite = svelte/server). Die Texte selbst sind
// im Katalogtest als Literale gepinnt; hier stehen sie als Literale aus
// src/lib/components/shared/__tests__/infoboxTexte.ts (nicht aus dem Katalog).
//
// Regeln: keine Uhr-Wartezeiten, keine uebersprungenen Faelle, kein Mauszeiger-Schweben. Das ⓘ wird
// ueber `getByRole('button', { name })` (aria-label) gefunden, der Fokus mit
// `toBeFocused` geprueft.
//
// Messaufbau /compare/new: der Durchlauf bis zu den Reitern laeuft im
// Desktop-Viewport (Orte waehlen in der Bibliothek); fuer die Mobil-Faelle wird
// danach der Viewport verkleinert (der Editor haelt seinen Zustand und schaltet
// per matchMedia auf den Mobil-Baum um).
//
// Laeuft im isolierten CI-Stack (Anmeldung ueber den gespeicherten storageState).
// Testdaten tragen das Praefix E2E-GZ- (helpers.ts) und werden in afterEach geraeumt.

import { test, expect, type Locator, type Page } from '@playwright/test';
import * as path from 'node:path';
import { cleanupTracked, createTestLocation } from './helpers';
import {
	ARIA_WORT,
	INFO_TEXTE,
	TIP_TEXTE,
	type Begriff,
	type Kontext
} from '../src/lib/components/shared/__tests__/infoboxTexte.ts';

const DESKTOP = { width: 1280, height: 900 };
const MOBILE = { width: 390, height: 844 };

test.afterEach(async ({ page }) => {
	await cleanupTracked(page.request);
});

// ── Messaufbau ──────────────────────────────────────────────────────────────

function konsolenFehler(page: Page): string[] {
	const fehler: string[] = [];
	page.on('console', (msg) => {
		if (msg.type() === 'error') fehler.push(msg.text());
	});
	page.on('pageerror', (err) => fehler.push(String(err)));
	return fehler;
}

type TripReiter = 'route' | 'etappen' | 'wegpunkte' | 'wetter-metriken' | 'wertebereiche' | 'alarme' | 'versand';
const TRIP_TAB_NAME: Record<TripReiter, RegExp> = {
	route: /Route/,
	etappen: /Etappen/,
	wegpunkte: /Wegpunkte/,
	'wetter-metriken': /Wetter/,
	wertebereiche: /Wertebereiche/,
	alarme: /Alarme/,
	versand: /Versand/
};
const TRIP_KETTE: TripReiter[] = ['wetter-metriken', 'wertebereiche', 'alarme', 'versand'];

function tripTab(page: Page, mobil: boolean, reiter: TripReiter): Locator {
	const leiste = mobil ? page.getByTestId('tn-mobile-tabbar') : page.locator('.tn-desktop');
	return leiste.getByRole('tab', { name: TRIP_TAB_NAME[reiter] });
}

async function wechsleTripReiter(page: Page, mobil: boolean, reiter: TripReiter): Promise<void> {
	await tripTab(page, mobil, reiter).click({ force: mobil });
}

/** /trips/new bis zum Reiter `ziel` durchklicken (Name + Datum, GPX je Etappe, dann die Kette). */
async function tripBis(page: Page, mobil: boolean, ziel: TripReiter): Promise<void> {
	await page.setViewportSize(mobil ? MOBILE : DESKTOP);
	await page.goto('/trips/new');
	await page.getByTestId(`trip-new-name-input-${mobil ? 'mobile' : 'desktop'}`).fill('E2E-GZ-Infobox-Trip');
	await page.getByTestId('trip-new-date-input').fill(new Date().toISOString().slice(0, 10));
	if (ziel === 'route') return;

	await wechsleTripReiter(page, mobil, 'etappen');
	if (ziel === 'etappen') return;

	// Je Etappe eine GPX laden. Der Datei-Input einer Etappe verschwindet nach dem
	// Parsen aus dem DOM — daher immer den ERSTEN verbleibenden aufloesen und auf die
	// Antwort + den kleineren Zaehler warten (statt auf eine Uhr).
	const gpx = path.resolve('./e2e/fixtures/test-trip.gpx');
	const eingaben = page.locator(`${mobil ? '.tn-mobile' : '.tn-desktop'} input[type="file"][accept=".gpx"]`);
	let rest = await eingaben.count();
	expect(rest, 'Messaufbau: keine GPX-Eingabe gefunden').toBeGreaterThan(0);
	while (rest > 0) {
		const geparst = page.waitForResponse((r) => r.url().includes('/api/gpx/parse'), { timeout: 30_000 });
		await eingaben.first().setInputFiles(gpx);
		await geparst;
		rest -= 1;
		await expect(eingaben).toHaveCount(rest);
	}

	if (ziel === 'wegpunkte') {
		await wechsleTripReiter(page, mobil, 'wegpunkte');
		return;
	}
	for (const reiter of TRIP_KETTE) {
		await wechsleTripReiter(page, mobil, reiter);
		if (reiter === ziel) return;
	}
}

type VergleichReiter = 'vergleich' | 'orte' | 'wetter-metriken' | 'wertebereiche' | 'alarme' | 'versand';
const VERGLEICH_KETTE: VergleichReiter[] = ['wetter-metriken', 'wertebereiche', 'alarme', 'versand'];

function vergleichTab(page: Page, mobil: boolean, reiter: VergleichReiter): Locator {
	const id = mobil ? `cm-mobile-tab-${reiter}` : `compare-editor-tab-${reiter}`;
	return page.locator(`[data-testid="${id}"]:visible`);
}

/** /compare/new bis zum Reiter `ziel`; bei `mobil` am Ende auf den Mobil-Baum umgeschaltet. */
async function vergleichBis(page: Page, mobil: boolean, ziel: VergleichReiter): Promise<void> {
	const suffix = Date.now();
	const ortA = await createTestLocation(page.request, { name: `E2E-GZ-Infobox A ${suffix}`, lat: 47.1, lon: 11.2 });
	const ortB = await createTestLocation(page.request, { name: `E2E-GZ-Infobox B ${suffix}`, lat: 47.2, lon: 11.3 });

	await page.setViewportSize(DESKTOP);
	await page.goto('/compare/new');
	await expect(page.getByTestId('compare-editor')).toBeVisible({ timeout: 15_000 });
	await page.getByTestId('compare-editor-name').fill(`E2E-GZ-Infobox-Vergleich ${suffix}`);
	if (ziel !== 'vergleich') {
		await vergleichTab(page, false, 'orte').click();
		const bibliothek = page.locator('[data-testid="compare-step2-library"]:visible').first();
		await expect(bibliothek).toBeVisible({ timeout: 10_000 });
		for (const ort of [ortA, ortB]) await bibliothek.getByText(ort.name, { exact: true }).click();
		if (ziel !== 'orte') {
			for (const reiter of VERGLEICH_KETTE) {
				await vergleichTab(page, false, reiter).click();
				if (reiter === ziel) break;
			}
		}
	}
	if (mobil) {
		await page.setViewportSize(MOBILE);
		await expect(page.locator(`[data-testid="cm-mobile-tab-${ziel}"]:visible`)).toHaveAttribute('data-active', 'true', {
			timeout: 10_000
		});
	}
}

// ── Bausteine der Pruefung ───────────────────────────────────────────────────

function infoboxen(page: Page): Locator {
	return page.locator('[data-testid^="infobox-"]:visible');
}

function infobox(page: Page, reiter: string, kontext: Kontext): Locator {
	return page.locator(`[data-testid="infobox-${reiter}-${kontext}"]:visible`);
}

/** Genau eine sichtbare Infobox mit dem freigegebenen Wortlaut, als <aside> ohne Bedienelement. */
async function pruefeInfobox(page: Page, reiter: string, kontext: Kontext): Promise<void> {
	const box = infobox(page, reiter, kontext);
	await expect(box, `Infobox ${reiter}/${kontext} fehlt oder ist doppelt`).toHaveCount(1);
	await expect(box).toBeVisible();
	await expect(box).toHaveText(INFO_TEXTE[`info.${reiter}.${kontext}`]);
	expect(await box.evaluate((el) => el.tagName)).toBe('ASIDE');
	await expect(box.getByRole('button')).toHaveCount(0);
	await expect(box.locator('input, a, [role="button"]')).toHaveCount(0);
}

function iiKnopf(page: Page, begriff: Begriff): Locator {
	return page.getByRole('button', { name: ARIA_WORT[begriff] });
}

function sprechblase(page: Page, begriff: Begriff): Locator {
	return page.getByText(TIP_TEXTE[`tip.${begriff}`]);
}

/** Oeffnen per Klick, Esc, Enter, Leertaste, Klick daneben — Fokus kehrt jedes Mal zum ⓘ zurueck. */
async function pruefePopover(page: Page, begriff: Begriff, daneben: Locator): Promise<void> {
	const knopf = iiKnopf(page, begriff);
	await expect(knopf, `ⓘ ${begriff}: genau ein sichtbarer Knopf mit sprechendem Namen`).toHaveCount(1);
	const blase = sprechblase(page, begriff);
	await expect(blase).toBeHidden();

	// Klick -> offen -> Esc -> zu, Fokus auf dem ⓘ
	await knopf.click();
	await expect(blase).toBeVisible();
	await page.keyboard.press('Escape');
	await expect(blase).toBeHidden();
	await expect(knopf).toBeFocused();

	// Tastatur: Fokus setzen (ohne Mauszeiger), Enter
	await knopf.focus();
	await expect(knopf).toBeFocused();
	await page.keyboard.press('Enter');
	await expect(blase).toBeVisible();
	await page.keyboard.press('Escape');
	await expect(blase).toBeHidden();
	await expect(knopf).toBeFocused();

	// Leertaste
	await page.keyboard.press('Space');
	await expect(blase).toBeVisible();

	// Klick daneben (auf die neutrale Infobox) schliesst, Fokus zurueck auf dem ⓘ
	await daneben.click();
	await expect(blase).toBeHidden();
	await expect(knopf).toBeFocused();
}

// ─────────────────────────────────────────────────────────────────────────────
// AC-1, AC-3, AC-4, AC-5 — /trips/new, Desktop UND Mobil
// ─────────────────────────────────────────────────────────────────────────────
for (const mobil of [false, true]) {
	const ansicht = mobil ? 'Mobil' : 'Desktop';

	test.describe(`/trips/new (${ansicht}): Infobox je Reiter`, () => {
		test('Pflichtreiter Route/Etappen ohne Infobox; Wegpunkte, Wetter-Metriken, Wertebereiche, Alarme, Versand mit Infobox', async ({ page }) => {
			await tripBis(page, mobil, 'route');
			await expect(infoboxen(page), 'Route-Reiter trägt eine Infobox').toHaveCount(0);

			await tripBis(page, mobil, 'etappen');
			await expect(infoboxen(page), 'Etappen-Reiter trägt eine Infobox').toHaveCount(0);

			await tripBis(page, mobil, 'wegpunkte');
			await pruefeInfobox(page, 'wegpunkte', 'route');

			for (const reiter of TRIP_KETTE) {
				await wechsleTripReiter(page, mobil, reiter);
				await pruefeInfobox(page, reiter, 'route');
			}
			// Versand: beim Trip BEIDE Zeiten.
			await expect(infobox(page, 'versand', 'route')).toContainText('07:00');
			await expect(infobox(page, 'versand', 'route')).toContainText('18:00');
		});
	});
}

// ─────────────────────────────────────────────────────────────────────────────
// AC-2, AC-3, AC-5 — /compare/new
// ─────────────────────────────────────────────────────────────────────────────
test.describe('/compare/new (Desktop): Infobox je Reiter', () => {
	test('Pflichtreiter Vergleich/Orte ohne Infobox; Wetter-Metriken, Wertebereiche, Alarme, Versand mit Vergleichs-Text', async ({ page }) => {
		await vergleichBis(page, false, 'vergleich');
		await expect(infoboxen(page), 'Vergleich-Reiter trägt eine Infobox').toHaveCount(0);
		await vergleichBis(page, false, 'orte');
		await expect(infoboxen(page), 'Orte-Reiter trägt eine Infobox').toHaveCount(0);

		for (const reiter of VERGLEICH_KETTE) {
			await vergleichTab(page, false, reiter).click();
			await pruefeInfobox(page, reiter, 'vergleich');
		}
		// Ortsvergleich-Versand: nur Morgen 07:00, kein Abend-Slot.
		await expect(infobox(page, 'versand', 'vergleich')).toContainText('07:00');
		await expect(infobox(page, 'versand', 'vergleich')).not.toContainText('18:00');
		await vergleichTab(page, false, 'wetter-metriken').click();
		await expect(infobox(page, 'wetter-metriken', 'vergleich')).toContainText('3-Tages-Ausblick');
	});
});

// ─────────────────────────────────────────────────────────────────────────────
// AC-7 — Infobox bleibt, kein Schliessen-Knopf, nichts gespeichert / gesendet
// ─────────────────────────────────────────────────────────────────────────────
test.describe('AC-7: die Infobox ist zustandslos', () => {
	test('bleibt beim Reiterwechsel und nach Neuladen sichtbar; schreibt weder Browser-Speicher noch Server', async ({ page }) => {
		const veraendernde: string[] = [];
		page.on('request', (r) => {
			if (!['GET', 'HEAD', 'OPTIONS'].includes(r.method()) && r.url().includes('/api/')) {
				veraendernde.push(`${r.method()} ${r.url()}`);
			}
		});
		const speicherSchluessel = async () =>
			page.evaluate(() => [...Object.keys(localStorage), ...Object.keys(sessionStorage)]);

		await tripBis(page, false, 'wetter-metriken');
		await pruefeInfobox(page, 'wetter-metriken', 'route');
		const vorher = veraendernde.length;

		await wechsleTripReiter(page, false, 'alarme');
		await pruefeInfobox(page, 'alarme', 'route');
		await wechsleTripReiter(page, false, 'wetter-metriken');
		await pruefeInfobox(page, 'wetter-metriken', 'route');
		expect(veraendernde.slice(vorher), 'Reiterwechsel/Infobox löst eine Schreib-Anfrage aus').toEqual([]);
		expect(
			(await speicherSchluessel()).filter((k) => /infobox|begriff|tip\.|hinweis|dismiss|schliess/i.test(k)),
			'Die Infobox legt etwas im Browser-Speicher ab'
		).toEqual([]);

		await page.reload();
		await tripBis(page, false, 'wetter-metriken');
		await pruefeInfobox(page, 'wetter-metriken', 'route');
	});
});

// ─────────────────────────────────────────────────────────────────────────────
// AC-8, AC-12, AC-13 — Wertebereiche
// ─────────────────────────────────────────────────────────────────────────────
for (const mobil of [false, true]) {
	const ansicht = mobil ? 'Mobil' : 'Desktop';

	test(`AC-8/12/13 Trip (${ansicht}): ⓘ Wertebereiche — Klick, Enter, Leertaste, Esc, Klick daneben, Fokus`, async ({ page }) => {
		await tripBis(page, mobil, 'wertebereiche');
		await pruefePopover(page, 'wertebereiche', infobox(page, 'wertebereiche', 'route'));
	});

	test(`AC-8/12/13 Ortsvergleich (${ansicht}): ⓘ Wertebereiche — ${mobil ? 'CorridorEditorMobile' : 'CorridorEditor'}`, async ({ page }) => {
		await vergleichBis(page, mobil, 'wertebereiche');
		await pruefePopover(page, 'wertebereiche', infobox(page, 'wertebereiche', 'vergleich'));
	});
}

// ─────────────────────────────────────────────────────────────────────────────
// AC-9, AC-10, AC-11, AC-12, AC-13 — Alarme
// ─────────────────────────────────────────────────────────────────────────────
for (const mobil of [false, true]) {
	const ansicht = mobil ? 'Mobil' : 'Desktop';

	test(`AC-9 Trip (${ansicht}): sichtbares Label „Dringlichkeits-Schwelle“ + ⓘ, Erklärung öffnet`, async ({ page }) => {
		await tripBis(page, mobil, 'alarme');
		const kanalBlock = page.getByTestId('alert-channel-picker');
		await expect(kanalBlock.getByText(/^Dringlichkeits-Schwelle$/)).toBeVisible();
		await pruefePopover(page, 'kanal_schwelle', infobox(page, 'alarme', 'route'));
	});

	test(`AC-11 Trip (${ansicht}): ⓘ Cooldown öffnet die Erklärung, Hinweistext bleibt`, async ({ page }) => {
		await tripBis(page, mobil, 'alarme');
		await pruefePopover(page, 'cooldown', infobox(page, 'alarme', 'route'));
		await expect(
			page.getByText('Mindestabstand zwischen zwei Alerts derselben Metrik — verhindert Spam bei zappelnden Werten.')
		).toBeVisible();
	});
}

// AC-10 hat hier bewusst KEINEN Browserfall: `cape` ist seit #1585 `selectable=False`
// (metric_catalog.py), die Alarm-Zeilen im Anlege-Flow werden aus dem waehlbaren Katalog
// abgeleitet (deriveActiveAlertMetricsForTrip) -- die CAPE-Zeile ist in /trips/new und
// /compare/new nicht erreichbar. Ein Fall hier waere dauerhaft rot. AC-10 ist am Baustein
// bewacht: begriff_erklaerung_an_den_vier_begriffen.test.ts (SSR von AlertMetricLevelRow).

test.describe('/compare/new (Desktop): Alarme', () => {
	test('AC-9: ⓘ Dringlichkeits-Schwelle; AC-11: ⓘ Cooldown samt unverändertem Hinweistext', async ({ page }) => {
		await vergleichBis(page, false, 'alarme');
		// CompareNewEditor mountet den Alarme-Reiter in .cm-desktop UND .cm-mobile (nicht per
		// Viewport gegatet) — ohne Scope waeren Kanal-Block und Hinweistext je doppelt (strict mode).
		const desktop = page.locator('.cm-desktop');
		const kanalBlock = desktop.getByTestId('alert-channel-picker');
		await expect(kanalBlock.getByText(/^Dringlichkeits-Schwelle$/)).toBeVisible();
		await pruefePopover(page, 'kanal_schwelle', infobox(page, 'alarme', 'vergleich'));
		await pruefePopover(page, 'cooldown', infobox(page, 'alarme', 'vergleich'));
		await expect(
			desktop.getByText('Mindestabstand zwischen zwei Alerts derselben Metrik — verhindert Spam bei zappelnden Werten.')
		).toBeVisible();
	});
});

// ─────────────────────────────────────────────────────────────────────────────
// AC-16 — keine Konsolenfehler (Frontend-Browser-Gate), Desktop und Mobil
// ─────────────────────────────────────────────────────────────────────────────
for (const mobil of [false, true]) {
	const ansicht = mobil ? 'Mobil' : 'Desktop';

	test(`AC-16 /trips/new (${ansicht}): alle Reiter, Sprechblasen öffnen und schließen — keine Konsolenfehler`, async ({ page }) => {
		const fehler = konsolenFehler(page);
		let geoeffnet = 0;
		await tripBis(page, mobil, 'wegpunkte');
		for (const reiter of TRIP_KETTE) {
			await wechsleTripReiter(page, mobil, reiter);
			for (const begriff of ['wertebereiche', 'kanal_schwelle', 'cooldown'] as Begriff[]) {
				const knopf = iiKnopf(page, begriff);
				if ((await knopf.count()) === 1) {
					await knopf.click();
					await expect(sprechblase(page, begriff)).toBeVisible();
					await page.keyboard.press('Escape');
					await expect(sprechblase(page, begriff)).toBeHidden();
					geoeffnet += 1;
				}
			}
		}
		expect(geoeffnet, 'Messaufbau: es wurden zu wenige Sprechblasen geöffnet (Wertebereiche, Schwelle, Cooldown)').toBeGreaterThanOrEqual(3);
		expect(fehler, `Konsolenfehler: ${fehler.join(' | ')}`).toEqual([]);
	});

	test(`AC-16 /compare/new (${ansicht}): alle Reiter, Sprechblasen öffnen und schließen — keine Konsolenfehler`, async ({ page }) => {
		const fehler = konsolenFehler(page);
		let geoeffnet = 0;
		await vergleichBis(page, false, 'versand');
		if (mobil) await page.setViewportSize(MOBILE);
		for (const reiter of VERGLEICH_KETTE) {
			await vergleichTab(page, mobil, reiter).click();
			for (const begriff of ['wertebereiche', 'kanal_schwelle', 'cooldown'] as Begriff[]) {
				const knopf = iiKnopf(page, begriff);
				if ((await knopf.count()) === 1) {
					await knopf.click();
					await expect(sprechblase(page, begriff)).toBeVisible();
					await page.keyboard.press('Escape');
					await expect(sprechblase(page, begriff)).toBeHidden();
					geoeffnet += 1;
				}
			}
		}
		expect(geoeffnet, 'Messaufbau: es wurden zu wenige Sprechblasen geöffnet (Wertebereiche, Schwelle, Cooldown)').toBeGreaterThanOrEqual(3);
		expect(fehler, `Konsolenfehler: ${fehler.join(' | ')}`).toEqual([]);
	});
}

// ─────────────────────────────────────────────────────────────────────────────
// AC-14 (Browser-Teil) — Tippflaeche des ⓘ gemessen
// ─────────────────────────────────────────────────────────────────────────────
for (const mobil of [false, true]) {
	test(`AC-14 (${mobil ? 'Mobil' : 'Desktop'}): das ⓘ ist mindestens 24 × 24 px groß`, async ({ page }) => {
		await tripBis(page, mobil, 'alarme');
		const box = await iiKnopf(page, 'cooldown').boundingBox();
		expect(box, 'ⓘ Cooldown nicht sichtbar').not.toBeNull();
		expect(box!.width).toBeGreaterThanOrEqual(24);
		expect(box!.height).toBeGreaterThanOrEqual(24);
	});
}

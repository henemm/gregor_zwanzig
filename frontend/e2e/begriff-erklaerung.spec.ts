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
// #3332 (feat_3332_zustellung_anlegen_trip.md): im Trip-Anlegen ist der Schritt Zustellung der Reiter
// Zustellung wie im Hub (ohne Infobox, ohne ⓘ); Dringlichkeit und Cooldown stehen dort.
// #3333 (feat_3333_zustellung_anlegen_orte.md AC-1/AC-10/AC-12): ebenso im Ortsvergleich-Anlegen. Der Reiter
// Alarme zeigt im Anlegen weder Kanal-Block noch Cooldown — die ⓘ Dringlichkeits-Schwelle und ⓘ Cooldown
// (AlertChannelPicker, AlertCooldownCard) sind damit in keiner Anlegeseite mehr gemountet (Known Limitation
// der Spec, Hub-Paritaet). Geprueft wird deshalb in beiden Anlegeseiten: Felder im Reiter Zustellung
// bedienbar, kein verwaistes ⓘ. Die frueheren Sprechblasen-Faelle (Tastatur, Klick daneben, Tippflaeche)
// haben kein Bauteil mehr auf einer Seite und entfallen.
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
import { cleanupTracked, createTestLocation, tippeDatum } from './helpers';
import { ZT, angezeigteZeit, cooldownFeld } from './s3b2795-zustellung.helpers';
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

// Issue #2794 S3a (Spec feat_2794_s3a_teil2_leiste.md): die Anlege-Schritte heißen
// `wetter` (Metrik-Auswahl + Wertebereiche) und `zustellung` (Layout/Kanal, Versand,
// Alarme). Die Infoboxen bleiben je Abschnitt benannt (`infobox-<abschnitt>-<kontext>`).
type TripReiter = 'route' | 'etappen' | 'wegpunkte' | 'wetter' | 'zustellung';
const TRIP_TAB_NAME: Record<TripReiter, RegExp> = {
	route: /Route/,
	etappen: /Etappen/,
	wegpunkte: /Wegpunkte/,
	wetter: /Wetter/,
	zustellung: /Zustellung/
};
const TRIP_KETTE: TripReiter[] = ['wetter', 'zustellung'];

/** Welche Abschnitts-Infoboxen ein Schwanz-Schritt mindestens trägt (#2794 S3a). */
// #2794 Teil 3 (Spec feat_2794_s3a_teil3_wetter.md §4 und §6 (d)): der Schritt Wetter ist der
// WetterTab (Aufbau nach Mockup Fassung 3, ohne Infobox); die Metrik-Oberfläche (Stundenverlauf,
// 3-Tages-Ausblick) samt Infobox „wetter-metriken" steht im Schritt Zustellung. Der CorridorEditor
// mit Infobox „wertebereiche" und ⓘ Wertebereiche ist im Schritt Wetter nur noch unsichtbar
// gemountet (§6 (d): „verschwindet im Schritt wetter aus der Sicht") — die Infobox entfällt.
// #3332 (Spec feat_3332_zustellung_anlegen_trip.md AC-1/AC-11): im Trip-Anlegen ist der Schritt Zustellung
// der Reiter Zustellung wie im Hub (ohne Infobox); das Alt-Panel mit den Infoboxen „wetter-metriken" und
// „versand" gibt es dort nicht mehr. Der Reiter Alarme behaelt seine Infobox. #3333 (AC-12): ebenso im
// Ortsvergleich-Anlegen.
const INFOBOXEN_JE_REITER: Record<Kontext, Record<'wetter' | 'zustellung', string[]>> = {
	route: { wetter: [], zustellung: ['alarme'] },
	vergleich: { wetter: [], zustellung: ['alarme'] }
};

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
	// Eingaben vor der Hydration gehen verloren (Zustand wird zurueckgesetzt, Etappen
	// bleibt gesperrt „⊘“). Deshalb Eingabe wiederholen, bis Etappen freigeschaltet ist.
	await expect(async () => {
		await page.getByTestId(`trip-new-name-input-${mobil ? 'mobile' : 'desktop'}`).fill('E2E-GZ-Infobox-Trip');
		// #2881 Lieferung B: Baustein DatumFeld; gesperrt = aria-disabled (Punkt statt ⊘).
		await tippeDatum(page, page.getByTestId(mobil ? 'trip-new-date-input' : 'trip-new-date-input-desktop'), new Date().toISOString().slice(0, 10));
		await expect(tripTab(page, mobil, 'etappen')).not.toHaveAttribute('aria-disabled', 'true', { timeout: 500 });
	}).toPass({ timeout: 10_000 });
	if (ziel === 'route') return;

	await wechsleTripReiter(page, mobil, 'etappen');
	if (ziel === 'etappen') return;

	// Je Etappe eine GPX laden. Der Datei-Input einer Etappe verschwindet nach dem
	// Parsen aus dem DOM — daher immer den ERSTEN verbleibenden aufloesen und auf die
	// Antwort + den kleineren Zaehler warten (statt auf eine Uhr).
	const gpx = path.resolve('./e2e/fixtures/test-trip.gpx');
	const eingaben = page.locator(`${mobil ? '.tn-mobile' : '.tn-desktop'} input[type="file"][accept=".gpx"]`);
	// count() wartet nicht: erst warten, bis der Etappen-Reiter seine Eingaben gerendert hat.
	await expect(eingaben.first()).toBeAttached();
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

type VergleichReiter = 'vergleich' | 'orte' | 'wetter' | 'zustellung';
const VERGLEICH_KETTE: VergleichReiter[] = ['wetter', 'zustellung'];

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
	return page.getByRole('button', { name: new RegExp('^Erklärung: ' + ARIA_WORT[begriff].source) });
}

function sprechblase(page: Page, begriff: Begriff): Locator {
	return page.getByText(TIP_TEXTE[`tip.${begriff}`]);
}

// ─────────────────────────────────────────────────────────────────────────────
// AC-1, AC-3, AC-4, AC-5 — /trips/new, Desktop UND Mobil
// ─────────────────────────────────────────────────────────────────────────────
for (const mobil of [false, true]) {
	const ansicht = mobil ? 'Mobil' : 'Desktop';

	test.describe(`/trips/new (${ansicht}): Infobox je Reiter`, () => {
		test('Pflichtreiter Route/Etappen ohne Infobox; Wegpunkte, Wetter (Metriken, Wertebereiche), Zustellung (Versand, Alarme) mit Infobox', async ({ page }) => {
			await tripBis(page, mobil, 'route');
			await expect(infoboxen(page), 'Route-Reiter trägt eine Infobox').toHaveCount(0);

			await tripBis(page, mobil, 'etappen');
			await expect(infoboxen(page), 'Etappen-Reiter trägt eine Infobox').toHaveCount(0);

			await tripBis(page, mobil, 'wegpunkte');
			await pruefeInfobox(page, 'wegpunkte', 'route');

			for (const reiter of TRIP_KETTE) {
				await wechsleTripReiter(page, mobil, reiter);
				const erwartet = INFOBOXEN_JE_REITER.route[reiter as 'wetter' | 'zustellung'];
				for (const abschnitt of erwartet) {
					await pruefeInfobox(page, abschnitt, 'route');
				}
				if (erwartet.length === 0) {
					await expect(page.locator('[data-testid="wetter-tab"]:visible'), 'Messaufbau: Schritt Wetter nicht offen').toHaveCount(1);
					await expect(infoboxen(page), `Schritt ${reiter} trägt eine Infobox (#2794 Teil 3 §4)`).toHaveCount(0);
				}
			}
			// #3332 (AC-1/AC-11): Schritt Zustellung = Reiter Zustellung wie im Hub, ohne Infobox; genau die
			// Infobox des Reiters Alarme bleibt. Die Standardzeiten (Trip: BEIDE, 07:00 und 18:00), die bisher
			// die Versand-Infobox nannte, stehen jetzt in den Briefing-Zeiten des Reiters selbst.
			await wechsleTripReiter(page, mobil, 'zustellung');
			const zt = page.locator('[data-testid="zustellung-tab"]:visible');
			await expect(zt, 'Reiter Zustellung fehlt im Trip-Anlegen').toHaveCount(1);
			await expect(zt.locator('[data-testid^="infobox-"]'), 'Reiter Zustellung trägt eine Infobox (#3332 AC-11)').toHaveCount(0);
			await expect(infobox(page, 'versand', 'route'), 'Versand-Infobox des Alt-Panels noch da').toHaveCount(0);
			await expect(infobox(page, 'wetter-metriken', 'route'), 'Metrik-Infobox des Alt-Panels noch da').toHaveCount(0);
			await expect(infoboxen(page), 'Schritt Zustellung: genau die Infobox des Reiters Alarme').toHaveCount(1);
			expect(await angezeigteZeit(zt.getByTestId(ZT.zeit('morgen')))).toBe('07:00');
			expect(await angezeigteZeit(zt.getByTestId(ZT.zeit('abend')))).toBe('18:00');
		});
	});
}

// ─────────────────────────────────────────────────────────────────────────────
// AC-2, AC-3, AC-5 — /compare/new
// ─────────────────────────────────────────────────────────────────────────────
test.describe('/compare/new (Desktop): Infobox je Reiter', () => {
	test('Pflichtreiter Vergleich/Orte ohne Infobox; Wetter ohne, Zustellung nur Alarme-Infobox (Reiter Zustellung ohne, #3333 AC-12)', async ({ page }) => {
		await vergleichBis(page, false, 'vergleich');
		await expect(infoboxen(page), 'Vergleich-Reiter trägt eine Infobox').toHaveCount(0);
		await vergleichBis(page, false, 'orte');
		await expect(infoboxen(page), 'Orte-Reiter trägt eine Infobox').toHaveCount(0);

		for (const reiter of VERGLEICH_KETTE) {
			await vergleichTab(page, false, reiter).click();
			const erwartet = INFOBOXEN_JE_REITER.vergleich[reiter as 'wetter' | 'zustellung'];
			for (const abschnitt of erwartet) {
				await pruefeInfobox(page, abschnitt, 'vergleich');
			}
			if (erwartet.length === 0) {
				await expect(page.locator('[data-testid="wetter-tab"]:visible'), 'Messaufbau: Schritt Wetter nicht offen').toHaveCount(1);
				await expect(infoboxen(page), `Schritt ${reiter} trägt eine Infobox (#2794 Teil 3 §4)`).toHaveCount(0);
			}
		}
		// #3333 (AC-1/AC-12): Schritt Zustellung = Reiter Zustellung wie im Hub, ohne Infobox; die Infoboxen des
		// Alt-Panels („versand", „wetter-metriken") sind weg. Die Standard-Morgenzeit 07:00, die bisher die
		// Versand-Infobox nannte, steht in den Briefing-Zeiten des Reiters selbst.
		await vergleichTab(page, false, 'zustellung').click();
		const zt = page.locator('[data-testid="zustellung-tab"]:visible');
		await expect(zt, 'Reiter Zustellung fehlt im Ortsvergleich-Anlegen').toHaveCount(1);
		await expect(zt.locator('[data-testid^="infobox-"]'), 'Reiter Zustellung trägt eine Infobox (#3333 AC-12)').toHaveCount(0);
		await expect(infobox(page, 'versand', 'vergleich'), 'Versand-Infobox des Alt-Panels noch da').toHaveCount(0);
		await expect(infobox(page, 'wetter-metriken', 'vergleich'), 'Metrik-Infobox des Alt-Panels noch da').toHaveCount(0);
		await expect(infoboxen(page), 'Schritt Zustellung: genau die Infobox des Reiters Alarme').toHaveCount(1);
		expect(await angezeigteZeit(zt.getByTestId(ZT.zeit('morgen')))).toBe('07:00');
	});
});

// ─────────────────────────────────────────────────────────────────────────────
// AC-7 — Infobox bleibt, kein Schliessen-Knopf, nichts gespeichert / gesendet
// ─────────────────────────────────────────────────────────────────────────────
test.describe('AC-7: die Infobox ist zustandslos', () => {
	test('bleibt beim Reiterwechsel und nach Neuladen sichtbar; schreibt weder Browser-Speicher noch Server', async ({ page }) => {
		const veraendernde: string[] = [];
		page.on('request', (r) => {
			// #2988: POST /api/ampel/aufloesung liest nur (Reiter Wetter beim Öffnen).
			if (r.method() === 'POST' && new URL(r.url()).pathname === '/api/ampel/aufloesung') return;
			if (!['GET', 'HEAD', 'OPTIONS'].includes(r.method()) && r.url().includes('/api/')) {
				veraendernde.push(`${r.method()} ${r.url()}`);
			}
		});
		const speicherSchluessel = async () =>
			page.evaluate(() => [...Object.keys(localStorage), ...Object.keys(sessionStorage)]);

		// #3332 (AC-11): im Schritt Zustellung des Trip-Anlegens traegt nur noch der Reiter Alarme eine
		// Infobox (der Reiter Zustellung hat keine, das Alt-Panel mit „wetter-metriken" entfaellt).
		await tripBis(page, false, 'zustellung');
		await pruefeInfobox(page, 'alarme', 'route');
		const vorher = veraendernde.length;

		await wechsleTripReiter(page, false, 'wetter');
		await wechsleTripReiter(page, false, 'zustellung');
		await pruefeInfobox(page, 'alarme', 'route');
		expect(veraendernde.slice(vorher), 'Reiterwechsel/Infobox löst eine Schreib-Anfrage aus').toEqual([]);
		expect(
			(await speicherSchluessel()).filter((k) => /infobox|begriff|tip\.|hinweis|dismiss|schliess/i.test(k)),
			'Die Infobox legt etwas im Browser-Speicher ab'
		).toEqual([]);

		await page.reload();
		await tripBis(page, false, 'zustellung');
		await pruefeInfobox(page, 'alarme', 'route');
	});
});

// ─────────────────────────────────────────────────────────────────────────────
// AC-8, AC-12, AC-13 — Wertebereiche
// ─────────────────────────────────────────────────────────────────────────────
for (const mobil of [false, true]) {
	const ansicht = mobil ? 'Mobil' : 'Desktop';

	// #2794 Teil 3: Spec feat_2794_s3a_teil3_wetter.md §6 (d) — „Der CorridorEditor verschwindet im
	// Schritt wetter aus der Sicht" (bleibt nur unsichtbar als Datenquelle gemountet); damit entfällt
	// das ⓘ Wertebereiche fachlich. Die Wertebereiche bedient der Nutzer dort über „Grenzen ändern"
	// des WetterTab. Geprüft: kein sichtbares ⓘ Wertebereiche (auch kein verwaistes), die Grenzen
	// sind im selben Schritt bedienbar.
	async function pruefeWertebereicheImWetterTab(page: Page): Promise<void> {
		const reiter = page.locator('[data-testid="wetter-tab"]:visible');
		await expect(reiter).toHaveCount(1);
		await expect(reiter.getByTestId('wetter-tab-laden')).toHaveCount(0, { timeout: 15_000 });
		await expect(iiKnopf(page, 'wertebereiche'), 'ⓘ Wertebereiche sichtbar, obwohl der CorridorEditor unsichtbar ist').toHaveCount(0);
		await expect(sprechblase(page, 'wertebereiche')).toBeHidden();
		const knopf = reiter.locator('[data-testid^="wetter-grenzen-aendern-"]').first();
		await expect(knopf).toBeVisible();
		await knopf.click();
		await expect(knopf).toHaveText('Fertig');
		await expect(reiter.locator('[data-testid^="wetter-grenze-"]').first()).toBeEditable();
	}

	test(`AC-8/12/13 Trip (${ansicht}): ⓘ Wertebereiche entfällt (#2794 Teil 3 §6 d) — Grenzen im WetterTab`, async ({ page }) => {
		await tripBis(page, mobil, 'wetter');
		await pruefeWertebereicheImWetterTab(page);
	});

	test(`AC-8/12/13 Ortsvergleich (${ansicht}): ⓘ Wertebereiche entfällt (#2794 Teil 3 §6 d) — Grenzen im WetterTab`, async ({ page }) => {
		await vergleichBis(page, mobil, 'wetter');
		await pruefeWertebereicheImWetterTab(page);
	});
}

// ─────────────────────────────────────────────────────────────────────────────
// AC-9, AC-10, AC-11, AC-12, AC-13 — Alarme
// ─────────────────────────────────────────────────────────────────────────────
for (const mobil of [false, true]) {
	const ansicht = mobil ? 'Mobil' : 'Desktop';

	// #3332 (Spec feat_3332_zustellung_anlegen_trip.md AC-1/AC-9) und #3333 (feat_3333_zustellung_anlegen_orte.md
	// AC-1/AC-10): in beiden Anlegeseiten besitzt der Reiter Zustellung (wie im Hub) Alarm-Kanaele mit
	// Dringlichkeit und den Cooldown; der Reiter Alarme blendet Kanal-Block, Cooldown und Stille Stunden dort
	// aus. Damit gibt es im Anlegen weder die alte Schwellen-Auswahl noch die beiden ⓘ (Hub-Paritaet) — auch
	// kein verwaistes. Geprueft: beide Felder sind im Reiter Zustellung sichtbar und bedienbar.
	async function pruefeZustellungStattAlarmKanaelen(page: Page): Promise<void> {
		const zt = page.locator('[data-testid="zustellung-tab"]:visible');
		await expect(zt).toHaveCount(1);
		await expect(zt.getByTestId(ZT.tabelle)).toBeVisible({ timeout: 15_000 });
		await expect(page.locator('[data-testid="alert-channel-picker"]:visible'), 'alte Schwellen-Auswahl noch im Anlegen').toHaveCount(0);
		await expect(iiKnopf(page, 'kanal_schwelle'), 'verwaistes ⓘ Dringlichkeits-Schwelle').toHaveCount(0);
		await expect(iiKnopf(page, 'cooldown'), 'verwaistes ⓘ Cooldown').toHaveCount(0);
		// Dringlichkeit: Spalte der Kanal-Tabelle (E-Mail-Alarm ist im Anlegen an).
		await expect(zt.getByTestId(ZT.dringlichkeit('email'))).toBeVisible();
		// Cooldown: im Aufklapper „Anpassen“, Startwert 120 Minuten, bedienbar.
		const cd = await cooldownFeld(zt);
		await expect(cd).toHaveValue('120');
		await cd.fill('45');
		await expect(cd).toHaveValue('45');
	}

	test(`AC-9/AC-11 Trip (${ansicht}): Dringlichkeit und Cooldown im Reiter Zustellung (#3332), keine alte Auswahl, kein verwaistes ⓘ`, async ({ page }) => {
		await tripBis(page, mobil, 'zustellung');
		await pruefeZustellungStattAlarmKanaelen(page);
	});

	test(`AC-9/AC-11 Ortsvergleich (${ansicht}): Dringlichkeit und Cooldown im Reiter Zustellung (#3333), keine alte Auswahl, kein verwaistes ⓘ`, async ({ page }) => {
		await vergleichBis(page, mobil, 'zustellung');
		await pruefeZustellungStattAlarmKanaelen(page);
	});
}

// AC-10 hat hier bewusst KEINEN Browserfall: `cape` ist seit #1585 `selectable=False`
// (metric_catalog.py), die Alarm-Zeilen im Anlege-Flow werden aus dem waehlbaren Katalog
// abgeleitet (deriveActiveAlertMetricsForTrip) -- die CAPE-Zeile ist in /trips/new und
// /compare/new nicht erreichbar. Ein Fall hier waere dauerhaft rot. AC-10 ist am Baustein
// bewacht: begriff_erklaerung_an_den_vier_begriffen.test.ts (SSR von AlertMetricLevelRow).

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
		// #2794 Teil 3 (§6 d): ⓘ Wertebereiche entfällt im Schritt Wetter. #3332 (AC-1/AC-9): Schwelle und
		// Cooldown stehen im Reiter Zustellung (Hub-Paritaet, ohne ⓘ) — im Trip-Anlegen gibt es kein ⓘ mehr.
		// Statt der Sprechblasen wird der Reiter Zustellung bedient (Aufklapper „Anpassen“, Cooldown).
		expect(geoeffnet, 'ⓘ im Trip-Anlegen sichtbar, obwohl Schwelle/Cooldown im Reiter Zustellung stehen (#3332)').toBe(0);
		const zt = page.locator('[data-testid="zustellung-tab"]:visible');
		await expect(zt.getByTestId(ZT.tabelle)).toBeVisible({ timeout: 15_000 });
		const cd = await cooldownFeld(zt);
		await cd.fill('60');
		await expect(cd).toHaveValue('60');
		expect(fehler, `Konsolenfehler: ${fehler.join(' | ')}`).toEqual([]);
	});

	test(`AC-16 /compare/new (${ansicht}): alle Reiter, Sprechblasen öffnen und schließen — keine Konsolenfehler`, async ({ page }) => {
		const fehler = konsolenFehler(page);
		let geoeffnet = 0;
		await vergleichBis(page, false, 'zustellung');
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
		// #2794 Teil 3 (§6 d): ⓘ Wertebereiche entfällt im Schritt Wetter. #3333 (AC-1/AC-10): Schwelle und
		// Cooldown stehen im Reiter Zustellung (Hub-Paritaet, ohne ⓘ) — wie im Trip-Anlegen gibt es kein ⓘ mehr.
		// Statt der Sprechblasen wird der Reiter Zustellung bedient (Aufklapper „Anpassen“, Cooldown).
		expect(geoeffnet, 'ⓘ im Ortsvergleich-Anlegen sichtbar, obwohl Schwelle/Cooldown im Reiter Zustellung stehen (#3333)').toBe(0);
		const zt = page.locator('[data-testid="zustellung-tab"]:visible');
		await expect(zt.getByTestId(ZT.tabelle)).toBeVisible({ timeout: 15_000 });
		const cd = await cooldownFeld(zt);
		await cd.fill('60');
		await expect(cd).toHaveValue('60');
		expect(fehler, `Konsolenfehler: ${fehler.join(' | ')}`).toEqual([]);
	});
}

// ─────────────────────────────────────────────────────────────────────────────
// AC-14 (Browser-Teil) — Tippflaeche des ⓘ: entfallen mit #3333. Nach #3332 (Trip) und #3333 (Ortsvergleich)
// mountet keine Seite mehr ein ⓘ Cooldown oder ⓘ Dringlichkeits-Schwelle (der Reiter Alarme blendet beide
// Abschnitte im Anlegen aus, der Hub nutzt den Reiter Zustellung ohne ⓘ).
// ─────────────────────────────────────────────────────────────────────────────

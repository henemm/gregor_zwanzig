// E2E — Issue #3122 Scheibe B3a: Bausteine für die Einstell-Tabelle „Was steht wo“ im echten Browser.
// Spec: docs/specs/modules/feat_3122_was_steht_wo.md — Teil B Nr. 10/11; AC-22, AC-24, AC-25, AC-26,
// AC-28, AC-33, hier nur als Eigenschaften der Bausteine (Haken, RohEinfachKnopf, EinstellTabelle).
//
//   ET-1  Haken an/aus: Klick und Leertaste melden genau ein Ereignis mit dem neuen Wert.
//   ET-2  Haken gesperrt, nicht in der E-Mail, fest, nicht bedienbar: Rolle und Name, kein Ereignis.
//   ET-3  Roh/Einfach-Knopf: Umschalten meldet genau ein Ereignis mit dem neuen Wert, Zustand als Text.
//   ET-4  Tabelle: vier (Trip) und fünf (Orte) Spalten, feste Zeile zuerst ohne Griff und ohne Abwahl,
//         Haken- und Format-Ereignis tragen Metrik und Stelle, Knopf nur bei gesetztem Haken.
//   ET-5  Nicht bedienbare Spalte (Telegram-Kurzstil): Haken gesperrt für Eingaben, kein Knopf, kein Ereignis.
//   ET-6  Umsortieren per Tastatur: Griff, Leertaste, Pfeil, Leertaste ⇒ neue Reihenfolge, ein Ereignis.
//   ET-7  Umsortieren per Maus am Griff.
//   ET-8  390 px, fünf Spalten: Seite scrollt nicht seitlich, jede Spalte erreichbar, Tippfläche ≥ 44 px.
//   ET-9  Kontrast aller Texte der Tabelle nach WCAG AA (Messhelfer aus #2879), 1280 px und 390 px.
//
// Messort ist die Vorschauseite /_design-system/einstelltabelle (nur Bausteine, Beispieldaten nach dem
// Soll-Bild Fassung 4). Sie hält den Zustand selbst und schreibt jedes gemeldete Ereignis als JSON in
// data-testid="demo-ereignisse". Kein Netz, keine Testdaten auf dem Server.
// Keine Uhr-Wartezeiten, keine übersprungenen Fälle. Anmeldung über den storageState (global.setup).
//
//   cd frontend && npx playwright test e2e/einstelltabelle-bausteine.spec.ts --workers=1 --trace off

import { test, expect, type Locator, type Page } from '@playwright/test';
import { kontrastBericht, kontrastVerstoesse, messeKontrast } from './helpers';

const DESKTOP = { width: 1280, height: 900 };
const MOBIL = { width: 390, height: 844 };
const SEITE = '/_design-system/einstelltabelle';
const ORTE_STELLEN = ['email', 'telegram', 'sms', 'hourly', 'outlook'];
const TRIP_STELLEN = ['email', 'telegram', 'sms', 'outlook'];

type Ereignis = Record<string, unknown>;

async function oeffne(page: Page, viewport = DESKTOP): Promise<void> {
	await page.setViewportSize(viewport);
	await page.goto(SEITE);
	await expect(page.getByTestId('demo-orte')).toBeVisible();
	await expect(page.getByTestId('demo-ereignisse')).toHaveAttribute('data-bereit', 'true');
}
async function ereignisse(page: Page): Promise<Ereignis[]> {
	return JSON.parse((await page.getByTestId('demo-ereignisse').textContent()) ?? '[]');
}
const zeile = (tabelle: Locator, metrik: string) => tabelle.locator(`[data-slot="et-zeile"][data-metrik="${metrik}"]`);
const zelle = (tabelle: Locator, metrik: string, stelle: string) => zeile(tabelle, metrik).locator(`[data-slot="et-zelle"][data-stelle="${stelle}"]`);
const reihenfolge = (tabelle: Locator) => tabelle.locator('[data-slot="et-zeile"]').evaluateAll((z) => z.map((e) => e.getAttribute('data-metrik')));

test.describe('Atome', () => {
	test('ET-1: Haken — Klick und Leertaste melden genau ein Ereignis mit dem neuen Wert', async ({ page }) => {
		await oeffne(page);
		const haken = page.getByTestId('demo-haken').getByRole('checkbox', { name: 'Wind in E-Mail' });
		await expect(haken).toBeChecked();
		await haken.click();
		await expect(haken).not.toBeChecked();
		expect(await ereignisse(page)).toEqual([{ quelle: 'haken', an: false }]);
		await haken.focus();
		await expect(haken).toBeFocused();
		await page.keyboard.press('Space');
		await expect(haken).toBeChecked();
		expect(await ereignisse(page)).toEqual([{ quelle: 'haken', an: false }, { quelle: 'haken', an: true }]);
	});

	test('ET-2: Haken gesperrt, nicht in der E-Mail, fest und nicht bedienbar lösen kein Ereignis aus', async ({ page }) => {
		await oeffne(page);
		const bereich = page.getByTestId('demo-haken');
		const gesperrt = bereich.getByRole('img', { name: 'Sonnenstunden im Stundenverlauf: kein Stundenwert' });
		await expect(gesperrt).toBeVisible();
		await expect(gesperrt).toContainText('kein Stundenwert');
		const ohneMail = bereich.getByRole('img', { name: 'Wind im 3-Tages-Ausblick: nicht in der E-Mail' });
		await expect(ohneMail).toBeVisible();
		const fest = bereich.getByRole('img', { name: 'Amtliche Warnungen in SMS: immer dabei' });
		await expect(fest).toBeVisible();
		const ruht = bereich.getByRole('checkbox', { name: 'Böen in Telegram' });
		await expect(ruht).toBeDisabled();
		await expect(ruht).toBeChecked();
		await expect(bereich.getByRole('checkbox')).toHaveCount(2);

		for (const ziel of [gesperrt, ohneMail, fest, ruht]) await ziel.click({ force: true });
		await ruht.dispatchEvent('click');
		await expect(ruht).toBeChecked();
		// Tastatur: die Tab-Folge im Bereich trifft nur den bedienbaren Haken.
		await bereich.getByRole('checkbox', { name: 'Wind in E-Mail' }).focus();
		await page.keyboard.press('Tab');
		await expect(ruht).not.toBeFocused();
		expect(await ereignisse(page)).toEqual([]);
	});

	test('ET-3: Roh/Einfach-Knopf — Umschalten meldet genau ein Ereignis, Zustand steht als Text da', async ({ page }) => {
		await oeffne(page);
		const bereich = page.getByTestId('demo-knopf');
		const roh = bereich.getByRole('button', { name: 'Darstellung Wind in E-Mail: Roh' });
		await expect(roh).toHaveText('Roh', { useInnerText: true });
		await roh.click();
		const einfach = bereich.getByRole('button', { name: 'Darstellung Wind in E-Mail: Einfach' });
		await expect(einfach).toHaveText('Einfach', { useInnerText: true });
		await expect(einfach).toHaveAttribute('data-wert', 'simplified');
		expect(await ereignisse(page)).toEqual([{ quelle: 'knopf', format: 'simplified' }]);
		await einfach.focus();
		await page.keyboard.press('Enter');
		await expect(bereich.getByRole('button', { name: 'Darstellung Wind in E-Mail: Roh' })).toBeVisible();
		expect(await ereignisse(page)).toEqual([{ quelle: 'knopf', format: 'simplified' }, { quelle: 'knopf', format: 'raw' }]);
	});
});

test.describe('Einstell-Tabelle', () => {
	test('ET-4: Spalten, feste Zeile, Haken- und Format-Ereignis mit Metrik und Stelle', async ({ page }) => {
		await oeffne(page);
		const trip = page.getByTestId('demo-trip');
		const orte = page.getByTestId('demo-orte');
		const koepfe = (t: Locator) => t.locator('[data-slot="et-kopf-stelle"]').evaluateAll((k) => k.map((e) => e.getAttribute('data-stelle')));
		expect(await koepfe(trip)).toEqual(TRIP_STELLEN);
		expect(await koepfe(orte)).toEqual(ORTE_STELLEN);
		await expect(trip.locator('[data-slot="et-kopf-stelle"][data-stelle="email"]')).toContainText('Stundentabelle');
		await expect(orte.locator('[data-slot="et-kopf-stelle"][data-stelle="email"]')).toContainText('Übersicht');
		await expect(orte.locator('[data-slot="et-kopf-stelle"][data-stelle="hourly"]')).toContainText('nur E-Mail');

		// Feste Zeile: optisch über der ersten Metrik, ohne Griff, ohne Kontrollkästchen.
		const fest = orte.locator('[data-slot="et-fest"]');
		await expect(fest).toContainText('Amtliche Warnungen');
		const festBox = (await fest.boundingBox())!;
		const ersteBox = (await orte.locator('[data-slot="et-zeile"]').first().boundingBox())!;
		expect(festBox.y + festBox.height).toBeLessThanOrEqual(ersteBox.y + 1);
		await expect(fest.getByTestId('drag-handle')).toHaveCount(0);
		await expect(fest.getByRole('checkbox')).toHaveCount(0);
		await expect(fest.getByRole('img', { name: /immer dabei$/ })).toHaveCount(3);

		// Haken: genau ein Ereignis mit Metrik und Stelle; der Knopf gibt es nur bei gesetztem Haken.
		const windMail = zelle(orte, 'wind', 'email');
		await expect(windMail.getByRole('button', { name: 'Darstellung Wind in E-Mail: Roh' })).toBeVisible();
		await windMail.getByRole('checkbox', { name: 'Wind in E-Mail' }).click();
		await expect(windMail.getByRole('checkbox')).not.toBeChecked();
		await expect(windMail.getByRole('button')).toHaveCount(0);
		await expect(windMail.locator('[data-slot="et-beispiel"]')).toHaveCount(0);
		expect(await ereignisse(page)).toEqual([{ quelle: 'orte', art: 'haken', metrik: 'wind', stelle: 'email', an: false }]);
		await windMail.getByRole('checkbox').click();
		await expect(windMail.getByRole('button', { name: 'Darstellung Wind in E-Mail: Roh' })).toBeVisible();

		// Format: genau ein Ereignis; die Knöpfe der anderen Stellen bleiben, wie sie sind.
		await zelle(orte, 'wind', 'hourly').getByRole('button', { name: 'Darstellung Wind im Stundenverlauf: Roh' }).click();
		await expect(zelle(orte, 'wind', 'hourly').getByRole('button')).toHaveText('Einfach', { useInnerText: true });
		await expect(zelle(orte, 'wind', 'email').getByRole('button')).toHaveText('Roh', { useInnerText: true });
		await expect(zelle(orte, 'wind', 'outlook').getByRole('button')).toHaveText('Roh', { useInnerText: true });
		expect((await ereignisse(page)).slice(2)).toEqual([{ quelle: 'orte', art: 'format', metrik: 'wind', stelle: 'hourly', format: 'simplified' }]);

		// Nie ein Knopf in der SMS-Spalte; Marken stehen in ihrer Zelle.
		await expect(orte.locator('[data-slot="et-zelle"][data-stelle="sms"]').getByRole('button')).toHaveCount(0);
		await expect(zelle(orte, 'sunshine', 'sms').locator('[data-slot="et-marke"]')).toHaveText('passt nicht mehr');
		await expect(zelle(orte, 'sunshine', 'hourly').getByRole('img', { name: 'Sonnenstunden im Stundenverlauf: kein Stundenwert' })).toBeVisible();
		await expect(zelle(trip, 'visibility', 'telegram').locator('[data-slot="et-marke"]')).toHaveText('nur Tageswert');
	});

	test('ET-5: nicht bedienbare Spalte — Haken gesperrt für Eingaben, kein Knopf, kein Ereignis', async ({ page }) => {
		await oeffne(page);
		const orte = page.getByTestId('demo-orte');
		await expect(zelle(orte, 'wind', 'telegram').getByRole('button')).toHaveCount(1);
		await page.getByTestId('demo-kurzstil').click();
		await expect(orte.locator('[data-slot="et-kopf-stelle"][data-stelle="telegram"]')).toContainText('Kurzstil: wie SMS');
		const haken = orte.locator('[data-slot="et-zelle"][data-stelle="telegram"]').getByRole('checkbox');
		const anzahl = await haken.count();
		expect(anzahl).toBeGreaterThanOrEqual(3);
		for (let i = 0; i < anzahl; i++) await expect(haken.nth(i)).toBeDisabled();
		await expect(orte.locator('[data-slot="et-zelle"][data-stelle="telegram"]').getByRole('button')).toHaveCount(0);
		await expect(zelle(orte, 'wind', 'telegram').getByRole('checkbox')).toBeChecked();
		await zelle(orte, 'wind', 'telegram').getByRole('checkbox').click({ force: true });
		await expect(zelle(orte, 'wind', 'email').getByRole('checkbox')).toBeEnabled();
		expect(await ereignisse(page)).toEqual([]);
	});

	test('ET-6: Umsortieren per Tastatur ändert die Reihenfolge und meldet genau ein Ereignis', async ({ page }) => {
		await oeffne(page);
		const orte = page.getByTestId('demo-orte');
		const start = await reihenfolge(orte);
		expect(start.slice(0, 3)).toEqual(['temperature', 'wind', 'gust']);
		const griff = zeile(orte, 'temperature').getByTestId('drag-handle');
		await expect(griff).toHaveAttribute('aria-label', /Temperatur/);
		await griff.focus();
		await expect(griff).toBeFocused();
		await page.keyboard.press('Space');
		await page.keyboard.press('ArrowDown');
		expect(await ereignisse(page), 'vor dem Ablegen wird nichts gemeldet').toEqual([]);
		await page.keyboard.press('Space');
		const neu = ['wind', 'temperature', ...start.slice(2)];
		await expect.poll(() => reihenfolge(orte)).toEqual(neu);
		expect(await ereignisse(page)).toEqual([{ quelle: 'orte', art: 'reihenfolge', metriken: neu }]);
		// Die feste Zeile bleibt oben.
		const fest = (await orte.locator('[data-slot="et-fest"]').boundingBox())!;
		expect(fest.y).toBeLessThan((await zeile(orte, 'wind').boundingBox())!.y);
	});

	test('ET-7: Umsortieren per Ziehen am Griff', async ({ page }) => {
		await oeffne(page);
		const trip = page.getByTestId('demo-trip');
		const start = await reihenfolge(trip);
		const mitte = async (l: Locator) => {
			const b = (await l.boundingBox())!;
			return { x: b.x + b.width / 2, y: b.y + b.height / 2 };
		};
		// Dritte Zeile am Griff über die erste ziehen. Losgelassen wird erst, wenn die Zone den Platz
		// freigemacht hat (Zwischenstand von SortableList) — ohne feste Wartezeit.
		await zeile(trip, start[0]!).scrollIntoViewIfNeeded();
		const von = await mitte(zeile(trip, start[2]!).getByTestId('drag-handle'));
		const nach = await mitte(zeile(trip, start[0]!).getByTestId('drag-handle'));
		await page.mouse.move(von.x, von.y);
		await page.mouse.down();
		await page.mouse.move(von.x, von.y - 12, { steps: 6 });
		await page.mouse.move(nach.x, nach.y, { steps: 15 });
		const neu = [start[2], start[0], start[1], ...start.slice(3)];
		await expect.poll(() => reihenfolge(trip)).toEqual(neu);
		expect(await ereignisse(page), 'während des Ziehens wird nichts gemeldet').toEqual([]);
		await page.mouse.up();
		await expect.poll(() => ereignisse(page)).toEqual([{ quelle: 'trip', art: 'reihenfolge', metriken: neu }]);
		expect(await reihenfolge(trip)).toEqual(neu);
	});
});

test.describe('Handy 390 px', () => {
	test.use({ viewport: MOBIL, hasTouch: true, isMobile: true });

	test('ET-8: fünf Spalten — Seite scrollt nicht seitlich, jede Spalte erreichbar, Tippfläche ≥ 44 px', async ({ page }) => {
		await oeffne(page, MOBIL);
		const orte = page.getByTestId('demo-orte');
		await orte.scrollIntoViewIfNeeded();
		const breiten = await page.evaluate(() => {
			const main = document.querySelector('main')!;
			return { seite: document.documentElement.scrollWidth, fenster: window.innerWidth, main: main.scrollWidth, mainSichtbar: main.clientWidth };
		});
		expect(breiten.seite, 'Seite scrollt seitlich').toBeLessThanOrEqual(breiten.fenster);
		expect(breiten.main, 'Inhaltsbereich scrollt seitlich').toBeLessThanOrEqual(breiten.mainSichtbar);

		// Jede Spalte: Kopf und jedes Bedienelement liegen ganz im Fenster, und der Mittelpunkt trifft das Element selbst.
		for (const stelle of ORTE_STELLEN) {
			const kopf = (await orte.locator(`[data-slot="et-kopf-stelle"][data-stelle="${stelle}"]`).boundingBox())!;
			expect(kopf.x, `Kopf ${stelle} links`).toBeGreaterThanOrEqual(0);
			expect(kopf.x + kopf.width, `Kopf ${stelle} rechts`).toBeLessThanOrEqual(MOBIL.width);
			expect(kopf.width, `Kopf ${stelle} hat Breite`).toBeGreaterThan(0);
		}
		const ziele = orte.locator('[data-slot="et-zeile"] :is(input[type="checkbox"], button)');
		const anzahl = await ziele.count();
		expect(anzahl).toBeGreaterThanOrEqual(40);
		const messung = await ziele.evaluateAll((els) =>
			els.map((el) => {
				// Tippfläche: beim Haken das umschließende label, beim Knopf der button selbst.
				const flaeche = (el.closest('label') ?? el).getBoundingClientRect();
				el.scrollIntoView({ block: 'center' });
				const r = (el.closest('label') ?? el).getBoundingClientRect();
				const treffer = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
				return {
					name: el.getAttribute('aria-label'),
					links: r.left,
					rechts: r.right,
					breite: flaeche.width,
					hoehe: flaeche.height,
					trifft: treffer === el || el.contains(treffer) || (el.closest('label')?.contains(treffer) ?? false)
				};
			})
		);
		for (const m of messung) {
			expect(m.links, `${m.name} links im Fenster`).toBeGreaterThanOrEqual(0);
			expect(m.rechts, `${m.name} rechts im Fenster`).toBeLessThanOrEqual(MOBIL.width);
			expect(m.trifft, `${m.name} ist verdeckt`).toBe(true);
			expect(m.breite, `${m.name} Tippbreite`).toBeGreaterThanOrEqual(44);
			expect(m.hoehe, `${m.name} Tipphöhe`).toBeGreaterThanOrEqual(44);
		}
		// Tippflächen benachbarter Bedienelemente überlappen nicht.
		const rechtecke = await ziele.evaluateAll((els) => els.map((el) => (el.closest('label') ?? el).getBoundingClientRect()).map((r) => ({ l: r.left, r: r.right, o: r.top, u: r.bottom })));
		for (let i = 0; i < rechtecke.length; i++)
			for (let j = i + 1; j < rechtecke.length; j++) {
				const a = rechtecke[i], b = rechtecke[j];
				const ueberlappt = a.l < b.r - 0.5 && b.l < a.r - 0.5 && a.o < b.u - 0.5 && b.o < a.u - 0.5;
				expect(ueberlappt, `Tippflächen ${i} und ${j} überlappen`).toBe(false);
			}

		// Bedienung per Tippen in der letzten Spalte.
		await zelle(orte, 'wind', 'outlook').getByRole('checkbox').tap();
		expect(await ereignisse(page)).toEqual([{ quelle: 'orte', art: 'haken', metrik: 'wind', stelle: 'outlook', an: false }]);
	});
});

test.describe('Kontrast', () => {
	for (const [name, viewport] of [['1280 px', DESKTOP], ['390 px', MOBIL]] as const) {
		test(`ET-9: alle Texte der Tabellen halten WCAG AA (${name})`, async ({ page }) => {
			await oeffne(page, viewport);
			for (const id of ['demo-trip', 'demo-orte', 'demo-haken', 'demo-knopf']) {
				const befunde = await messeKontrast(page.getByTestId(id));
				expect(befunde.length, `${id}: keine Texte gemessen`).toBeGreaterThan(0);
				expect(kontrastBericht(`${id} ${name}`, kontrastVerstoesse(befunde))).toEqual([]);
			}
			// Auch im Zustand „Spalte ruht“ (Kurzstil) bleibt jeder nicht gesperrte Text lesbar.
			await page.getByTestId('demo-kurzstil').click();
			await expect(page.getByTestId('demo-orte').locator('[data-slot="et-kopf-stelle"][data-stelle="telegram"]')).toContainText(/Kurzstil|Telegr/);
			expect(kontrastBericht(`demo-orte Kurzstil ${name}`, kontrastVerstoesse(await messeKontrast(page.getByTestId('demo-orte'))))).toEqual([]);
		});
	}
});

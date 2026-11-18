// E2E — Issue #3007 (Epic #2913): Listen der Reiter Etappen und Orte im echten Browser (Staging).
// Spec: docs/specs/modules/feat_3007_etappen_orte_listen.md — AC-2 (Tastatur), AC-7 (entfernen),
// AC-13 (Aufklappen/Schließen/Wechsel, höchstens ein Editor), AC-22 (Testids bleiben).
// Was SSR nicht kann, wird hier gemessen: Klick und Tastatur auf der Etappenzeile, Entfernen eines Orts.
// Anmeldung über storageState (global.setup.ts); kein fester Schlaf, kein networkidle.

import { test, expect } from '@playwright/test';
import { openHub, seedHub, tippeDatum, feldEingabe } from './helpers';

const DESKTOP = { width: 1280, height: 900 };
const wp = (id: string, name: string, lat: number, lon: number, elevation_m: number) => ({ id, name, lat, lon, elevation_m });
const ETAPPEN = [
	{ id: 'e3007a', name: 'Tag 1', date: '2027-06-01', waypoints: [wp('w1', 'Start A', 39.54, 2.39, 10), wp('w2', 'Ziel B', 39.6, 2.45, 400)] },
	{ id: 'e3007b', name: 'Tag 2', date: '2027-06-02', waypoints: [wp('w3', 'Ziel B', 39.6, 2.45, 400), wp('w4', 'Ziel C', 39.65, 2.5, 150)] }
];

test.describe('#3007 Etappen-Liste: Zeile klappt den Editor auf', () => {
	test.use({ viewport: DESKTOP });
	test('AC-13/AC-2: Klick öffnet, erneuter Klick schließt, Enter und Leertaste öffnen, höchstens ein Editor', async ({ page, request }) => {
		const hub = await seedHub(request, 'route', { extra: { stages: ETAPPEN } });
		try {
			await openHub(page, 'route', hub.id, { tab: 'etappen' });
			const liste = page.locator('[data-abschnitt="liste"]');
			await expect(liste).toHaveCount(1);
			const zeilen = liste.locator('[data-testid="etappen-liste-zeile"]');
			await expect(zeilen).toHaveCount(2);
			await expect(zeilen.nth(0)).toContainText('E1 · Start A → Ziel B');
			await expect(page.getByTestId('etappen-strip-wrapper')).toHaveCount(0);
			const editor = page.getByTestId('etappen-reiterflaeche');
			await expect(editor).toHaveCount(0);

			await zeilen.nth(0).click();
			await expect(zeilen.nth(0)).toHaveAttribute('aria-expanded', 'true');
			await expect(editor).toHaveCount(1);
			await zeilen.nth(0).click();
			await expect(zeilen.nth(0)).toHaveAttribute('aria-expanded', 'false');
			await expect(editor).toHaveCount(0);

			await zeilen.nth(1).focus();
			await page.keyboard.press('Enter');
			await expect(zeilen.nth(1)).toHaveAttribute('aria-expanded', 'true');
			await expect(editor).toHaveCount(1);
			await zeilen.nth(0).focus();
			await page.keyboard.press(' ');
			await expect(zeilen.nth(0)).toHaveAttribute('aria-expanded', 'true');
			await expect(zeilen.nth(1)).toHaveAttribute('aria-expanded', 'false');
			await expect(editor).toHaveCount(1);
			// Leertaste auf der offenen Zeile schließt wieder (Tastatur = Klick).
			await page.keyboard.press(' ');
			await expect(zeilen.nth(0)).toHaveAttribute('aria-expanded', 'false');
			await expect(editor).toHaveCount(0);
		} finally {
			await hub.aufraeumen();
		}
	});

	// Fix-Loop 1 (Adversary F003, M5/M17): der Editor gehört GENAU zur geklickten Etappe — er steht
	// direkt unter ihrer Zeile und zeigt ihren Namen und ihre Wegpunkte; ein Wechsel im Etappen-Band
	// nimmt ihn zur anderen Zeile mit.
	test('AC-13: Editor zeigt die geklickte Etappe unter ihrer Zeile; Wechsel im Band nimmt ihn mit', async ({ page, request }) => {
		const hub = await seedHub(request, 'route', { extra: { stages: ETAPPEN } });
		try {
			await openHub(page, 'route', hub.id, { tab: 'etappen' });
			const zeilen = page.locator('[data-abschnitt="liste"] [data-testid="etappen-liste-zeile"]');
			await expect(zeilen).toHaveCount(2);
			const editor = page.getByTestId('etappen-reiterflaeche');
			const sidebar = editor.getByTestId('waypoint-sidebar');
			const unter = (i: number) => zeilen.nth(i).locator('xpath=following-sibling::*[1]');

			await zeilen.nth(1).click();
			await expect(zeilen.nth(1)).toHaveAttribute('aria-expanded', 'true');
			await expect(zeilen.nth(0)).toHaveAttribute('aria-expanded', 'false');
			await expect(editor).toHaveCount(1);
			await expect(unter(1)).toHaveAttribute('data-testid', 'etappen-aufklapp');
			await expect(unter(1).getByTestId('etappen-reiterflaeche')).toHaveCount(1);
			await expect(editor.locator('p', { hasText: /^Tag 2$/ })).toBeVisible();
			await expect(sidebar).toContainText('Ziel C');
			await expect(sidebar).not.toContainText('Start A');

			// Wechsel über das Etappen-Band im aufgeklappten Bereich: Editor wandert unter Zeile 1.
			await page.getByTestId('etappen-strip').getByTestId('stage-card-0').click();
			await expect(zeilen.nth(0)).toHaveAttribute('aria-expanded', 'true');
			await expect(zeilen.nth(1)).toHaveAttribute('aria-expanded', 'false');
			await expect(editor).toHaveCount(1);
			await expect(unter(0)).toHaveAttribute('data-testid', 'etappen-aufklapp');
			await expect(editor.locator('p', { hasText: /^Tag 1$/ })).toBeVisible();
			await expect(sidebar).toContainText('Start A');
			await expect(sidebar).not.toContainText('Ziel C');

			// Enter auf Zeile 2 wechselt direkt (höchstens ein Editor), Enter erneut schließt.
			await zeilen.nth(1).focus();
			await page.keyboard.press('Enter');
			await expect(zeilen.nth(1)).toHaveAttribute('aria-expanded', 'true');
			await expect(zeilen.nth(0)).toHaveAttribute('aria-expanded', 'false');
			await expect(editor).toHaveCount(1);
			await expect(sidebar).toContainText('Ziel C');
			await zeilen.nth(1).focus();
			await page.keyboard.press('Enter');
			await expect(zeilen.nth(1)).toHaveAttribute('aria-expanded', 'false');
			await expect(editor).toHaveCount(0);
		} finally {
			await hub.aufraeumen();
		}
	});

	// Fix-Runde 3 (Adversary F001, AC-2/AC-13): Wechsel NACH UNTEN per Tastatur. Die Zeile wandert
	// dabei aus dem Block hinter dem Editor in den Block davor; der Tastaturfokus muss auf ihr bleiben.
	test('AC-2/AC-13: Etappe 1 offen, Enter auf Zeile 3 öffnet Etappe 3 und Zeile 3 behält den Fokus', async ({ page, request }) => {
		const drei = [
			...ETAPPEN,
			{ id: 'e3007c', name: 'Tag 3', date: '2027-06-03', waypoints: [wp('w5', 'Ziel C', 39.65, 2.5, 150), wp('w6', 'Ziel D', 39.7, 2.55, 300)] }
		];
		const hub = await seedHub(request, 'route', { extra: { stages: drei } });
		try {
			await openHub(page, 'route', hub.id, { tab: 'etappen' });
			const zeilen = page.locator('[data-abschnitt="liste"] [data-testid="etappen-liste-zeile"]');
			await expect(zeilen).toHaveCount(3);
			const editor = page.getByTestId('etappen-reiterflaeche');
			// Fix-Runde 4 (Adversary F001): Titel ALLER Zeilen vollständig, in Reihenfolge, ohne Dublette —
			// auch die Zeilen hinter dem aufgeklappten Editor tragen ihre eigene Nummer.
			const titel = zeilen.locator('b');
			const alleTitelInReihenfolge = () => expect(titel).toHaveText([/^E1 · Start A/, /^E2 · Ziel B/, /^E3 · Ziel C/]);
			await alleTitelInReihenfolge();

			await zeilen.nth(0).focus();
			await page.keyboard.press('Enter');
			await expect(zeilen.nth(0)).toHaveAttribute('aria-expanded', 'true');
			await expect(editor).toHaveCount(1);
			await expect(zeilen).toHaveCount(3);
			await alleTitelInReihenfolge();

			await zeilen.nth(2).focus();
			await page.keyboard.press('Enter');
			await expect(zeilen.nth(2)).toHaveAttribute('aria-expanded', 'true');
			await expect(zeilen.nth(0)).toHaveAttribute('aria-expanded', 'false');
			await expect(editor).toHaveCount(1);
			await expect(page.locator('[data-stage-id="e3007c"]')).toBeFocused();
			await alleTitelInReihenfolge();
			// Weiter per Tastatur: Enter auf derselben Zeile schließt wieder.
			await page.keyboard.press('Enter');
			await expect(zeilen.nth(2)).toHaveAttribute('aria-expanded', 'false');
			await expect(editor).toHaveCount(0);

			// Mittlere Etappe offen: Zeile 3 steht hinter dem Editor und heißt weiter E3.
			await zeilen.nth(1).click();
			await expect(zeilen.nth(1)).toHaveAttribute('aria-expanded', 'true');
			await expect(editor).toHaveCount(1);
			await expect(zeilen).toHaveCount(3);
			await alleTitelInReihenfolge();

			// Fix-Runde 4 (Adversary F002): kam der Wechsel NICHT von der fokussierten Zeile, wird kein
			// Fokus gezogen. Fokus liegt auf Zeile 1 (bleibt beim Wechsel bestehen), Klick auf Zeile 3 ohne
			// Fokusübergabe (Klick-Ereignis direkt): Zeile 3 wandert nach oben, der Fokus bleibt auf Zeile 1.
			await zeilen.nth(0).focus();
			await expect(page.locator('[data-stage-id="e3007a"]')).toBeFocused();
			await zeilen.nth(2).dispatchEvent('click');
			await expect(zeilen.nth(2)).toHaveAttribute('aria-expanded', 'true');
			await expect(zeilen.nth(1)).toHaveAttribute('aria-expanded', 'false');
			await expect(page.locator('[data-stage-id="e3007a"]')).toBeFocused();
			await expect(page.locator('[data-stage-id="e3007c"]')).not.toBeFocused();
			await alleTitelInReihenfolge();
		} finally {
			await hub.aufraeumen();
		}
	});

	// Fix-Runde 5 (V-2, AC-14, Fehlerklasse #1389/#1390): Datum der Etappe 1 ändern stellt das Speichern
	// zurück und fragt nach den Folge-Etappen. Klappt der Nutzer die Zeile zu oder öffnet eine andere,
	// muss die Rückfrage sichtbar bleiben — genau einmal — sonst bleibt die Änderung unbemerkt ungespeichert.
	test('AC-14: offene Kaskaden-Rückfrage bleibt nach dem Zuklappen sichtbar, genau einmal', async ({ page, request }) => {
		const hub = await seedHub(request, 'route', { extra: { stages: ETAPPEN } });
		try {
			await openHub(page, 'route', hub.id, { tab: 'etappen' });
			const zeilen = page.locator('[data-abschnitt="liste"] [data-testid="etappen-liste-zeile"]');
			await expect(zeilen).toHaveCount(2);
			await zeilen.nth(0).click();
			await expect(zeilen.nth(0)).toHaveAttribute('aria-expanded', 'true');
			const datum = page.locator('[data-testid="etappen-aufklapp"] [data-testid="stage-date-field"]:visible').first();
			await expect(feldEingabe(datum)).toHaveText('01.06.2027');
			await tippeDatum(page, datum, '2027-06-10');
			const rueckfrage = page.getByTestId('cascade-strip');
			await expect(rueckfrage).toHaveCount(1);
			await expect(rueckfrage).toBeVisible();

			await zeilen.nth(0).click();
			await expect(zeilen.nth(0)).toHaveAttribute('aria-expanded', 'false');
			await expect(page.getByTestId('etappen-aufklapp')).toHaveCount(0);
			await expect(rueckfrage, 'zugeklappt: Rückfrage verschwunden').toHaveCount(1);
			await expect(rueckfrage).toBeVisible();

			await zeilen.nth(1).click();
			await expect(zeilen.nth(1)).toHaveAttribute('aria-expanded', 'true');
			await expect(rueckfrage, 'andere Etappe offen: Rückfrage nicht genau einmal').toHaveCount(1);
			await expect(rueckfrage).toBeVisible();
		} finally {
			await hub.aufraeumen();
		}
	});
});

test.describe('#3007 Orte-Liste: entfernen per Textknopf', () => {
	test.use({ viewport: DESKTOP });
	test('AC-7/AC-22: „entfernen“ bei Ort 2 entfernt genau Ort 2, Testids bleiben', async ({ page, request }) => {
		const hub = await seedHub(request, 'vergleich');
		try {
			await openHub(page, 'vergleich', hub.id, { tab: 'orte' });
			const liste = page.locator('[data-abschnitt="liste"]');
			await expect(liste).toHaveCount(1);
			const zeilen = liste.locator('[data-testid="hub-orte-row"]');
			const vorher = await zeilen.count();
			// Prüf-Vergleich braucht mindestens zwei Orte — harte Erwartung statt Skip (Filter A der Positivliste).
			expect(vorher).toBeGreaterThanOrEqual(2);
			// Fix-Loop 1 (Adversary M1): den ZWEITEN Ort entfernen — ein Handler, der immer den ersten
			// (oder einen anderen) entfernt, fällt damit auf. Geprüft über Kennung UND sichtbaren Namen.
			const ids = await zeilen.evaluateAll((els) => els.map((e) => e.getAttribute('data-loc-id')));
			const namen = await zeilen.locator('b').allInnerTexts();
			expect(namen).toHaveLength(vorher);
			const knopf = zeilen.nth(1).getByTestId('hub-orte-remove');
			await expect(knopf).not.toHaveText('✕');
			await knopf.click();
			await expect(zeilen).toHaveCount(vorher - 1);
			const nachher = await zeilen.evaluateAll((els) => els.map((e) => e.getAttribute('data-loc-id')));
			expect(nachher).toEqual([ids[0], ...ids.slice(2)]);
			await expect(zeilen.locator('b')).toHaveText([namen[0], ...namen.slice(2)]);
			await expect(liste).not.toContainText(namen[1]);
			await expect(page.getByTestId('hub-orte-add')).toHaveCount(1);
		} finally {
			await hub.aufraeumen();
		}
	});
});

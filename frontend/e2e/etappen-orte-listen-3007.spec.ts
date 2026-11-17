// E2E — Issue #3007 (Epic #2913): Listen der Reiter Etappen und Orte im echten Browser (Staging).
// Spec: docs/specs/modules/feat_3007_etappen_orte_listen.md — AC-2 (Tastatur), AC-7 (entfernen),
// AC-13 (Aufklappen/Schließen/Wechsel, höchstens ein Editor), AC-22 (Testids bleiben).
// Was SSR nicht kann, wird hier gemessen: Klick und Tastatur auf der Etappenzeile, Entfernen eines Orts.
// Anmeldung über storageState (global.setup.ts); kein fester Schlaf, kein networkidle.

import { test, expect } from '@playwright/test';
import { openHub, seedHub } from './helpers';

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
		} finally {
			await hub.aufraeumen();
		}
	});
});

test.describe('#3007 Orte-Liste: entfernen per Textknopf', () => {
	test.use({ viewport: DESKTOP });
	test('AC-7/AC-22: „entfernen“ entfernt genau diesen Ort, Testids bleiben', async ({ page, request }) => {
		const hub = await seedHub(request, 'vergleich');
		try {
			await openHub(page, 'vergleich', hub.id, { tab: 'orte' });
			const liste = page.locator('[data-abschnitt="liste"]');
			await expect(liste).toHaveCount(1);
			const zeilen = liste.locator('[data-testid="hub-orte-row"]');
			const vorher = await zeilen.count();
			test.skip(vorher < 2, 'Prüf-Vergleich braucht mindestens zwei Orte');
			const ids = await zeilen.evaluateAll((els) => els.map((e) => e.getAttribute('data-loc-id')));
			const knopf = zeilen.nth(0).getByTestId('hub-orte-remove');
			await expect(knopf).not.toHaveText('✕');
			await knopf.click();
			await expect(zeilen).toHaveCount(vorher - 1);
			const nachher = await zeilen.evaluateAll((els) => els.map((e) => e.getAttribute('data-loc-id')));
			expect(nachher).toEqual(ids.slice(1));
			await expect(page.getByTestId('hub-orte-add')).toHaveCount(1);
		} finally {
			await hub.aufraeumen();
		}
	});
});

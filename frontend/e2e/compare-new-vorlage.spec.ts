// E2E (Staging) — Issue #2277 Scheibe S2c: /compare/new?from=<id> belegt die Anlage vor.
// Spec: docs/specs/modules/feat_2277_s2c_compare_from_vorlage.md (AC-2, AC-6, AC-7, AC-8, AC-10, AC-11)
//
// RED-Erwartung (vor Umsetzung): `?from=` wird ignoriert — das Namensfeld bleibt leer,
// "… (Kopie)" erscheint nie.
//
// Zwei echte Sessions (Nutzer A = storageState-Fixture, Nutzer B = frisch registriert).
// Aufraeumen: alle angelegten Vergleiche/Orte am Ende per API loeschen.
//
// Ausfuehren (gegen Staging, aus frontend/): siehe playwright.<n>.staging.config.ts-Muster.

import { test, expect, type Page } from '@playwright/test';
import { createTestLocation, registriereBestaetigtenZweitnutzer } from './helpers';

const HEADER_NAME = '[data-testid="compare-editor-name"]';
const HEADER_NAME_MOBILE = '[data-testid="compare-editor-name-mobile"]';

async function legeVergleichAn(page: Page, name: string, locIds: string[]): Promise<string> {
	const res = await page.request.post('/api/compare/presets', {
		data: {
			name,
			location_ids: locIds,
			schedule: 'weekly',
			weekday: 3,
			profil: 'wandern',
			hour_from: 7,
			hour_to: 16,
			empfaenger: ['urlauber@example.com']
		}
	});
	expect(res.ok(), 'Preset-Anlage fehlgeschlagen: ' + res.status()).toBeTruthy();
	return (await res.json()).id as string;
}

async function listeIds(page: Page): Promise<string[]> {
	const res = await page.request.get('/api/compare/presets');
	expect(res.ok()).toBeTruthy();
	return ((await res.json()) as { id: string }[]).map((p) => p.id);
}

test.describe('S2c — /compare/new?from=<id>', () => {
	test('AC-2/AC-8/AC-10/AC-7: Vorbelegung mit Suffix, ohne from leer, Eingabe bleibt, Original unveraendert', async ({
		page
	}) => {
		const suffix = Date.now();
		const l1 = await createTestLocation(page.request, { name: `E2E 2277 O1 ${suffix}`, lat: 48.5, lon: 12.5 });
		const l2 = await createTestLocation(page.request, { name: `E2E 2277 O2 ${suffix}`, lat: 48.6, lon: 12.6 });
		const name = `E2E 2277 Vorlage ${suffix}`;
		const origId = await legeVergleichAn(page, name, [l1.id, l2.id]);
		const vorher = await (await page.request.get(`/api/compare/presets/${origId}`)).json();
		const anzahlVorher = (await listeIds(page)).length;

		try {
			// AC-8: ohne from leer
			await page.setViewportSize({ width: 1280, height: 900 });
			await page.goto('/compare/new');
			await expect(page.locator(HEADER_NAME)).toBeVisible({ timeout: 15_000 });
			await expect(page.locator(HEADER_NAME)).toHaveValue('');

			// AC-2: mit from => Name + " (Kopie)"
			await page.goto(`/compare/new?from=${origId}`);
			await expect(page.locator(HEADER_NAME)).toHaveValue(`${name} (Kopie)`, { timeout: 15_000 });

			// AC-10: Eingabe aendern, Reiter wechseln, Name bleibt (kein reaktives Zuruecksetzen)
			const neuerName = `${name} angepasst`;
			await page.locator(HEADER_NAME).fill(neuerName);
			await page.getByTestId('compare-editor-tab-orte').click();
			await page.getByTestId('compare-editor-tab-vergleich').click();
			await expect(page.locator(HEADER_NAME)).toHaveValue(neuerName);

			// AC-7: speichern => POST (nie PUT auf Original), neuer Vergleich, Original unveraendert
			const postAbfang = page.waitForRequest(
				(r) => r.url().endsWith('/api/compare/presets') && r.method() === 'POST'
			);
			await page.getByTestId('compare-editor-tab-metriken').click();
			await page.getByTestId('compare-editor-tab-idealwerte').click();
			await page.getByTestId('compare-editor-tab-alarme').click();
			await page.getByTestId('compare-editor-tab-versand').click();
			await page.getByRole('button', { name: 'Briefing aktivieren' }).click();
			const post = await postAbfang;
			const body = post.postDataJSON() as Record<string, unknown>;
			expect(body.id, 'Create-Request darf keine id tragen (AC-3)').toBeUndefined();
			expect(body.letzter_versand).toBeUndefined();
			expect(post.headers()['if-match']).toBeUndefined();

			await expect.poll(async () => (await listeIds(page)).length).toBe(anzahlVorher + 1);
			const nachher = await (await page.request.get(`/api/compare/presets/${origId}`)).json();
			expect(nachher).toEqual(vorher);
		} finally {
			const ids = await listeIds(page);
			for (const id of ids) {
				const p = await (await page.request.get(`/api/compare/presets/${id}`)).json();
				if (typeof p.name === 'string' && p.name.startsWith(`E2E 2277 Vorlage ${suffix}`)) {
					await page.request.delete(`/api/compare/presets/${id}`);
				}
			}
			await page.request.delete(`/api/locations/${l1.id}`);
			await page.request.delete(`/api/locations/${l2.id}`);
		}
	});

	test('AC-6: Nutzer B sieht mit fremder/unbekannter from-ID eine leere Anlage, keine Fehlerseite', async ({
		page: pageA,
		browser
	}) => {
		const suffix = Date.now();
		const lA = await createTestLocation(pageA.request, { name: `E2E 2277 A ${suffix}`, lat: 48.7, lon: 12.7 });
		const nameA = `E2E 2277 GEHEIM-A ${suffix}`;
		const idA = await legeVergleichAn(pageA, nameA, [lA.id]);

		const ctxB = await browser.newContext();
		const pageB = await ctxB.newPage();
		try {
			await registriereBestaetigtenZweitnutzer(pageA.request, pageB.request, 'e2e2277b' + suffix, 'test1234');
			for (const fremd of [idA, 'gibt-es-nicht-' + suffix]) {
				await pageB.goto(`/compare/new?from=${fremd}`);
				await expect(pageB.locator(HEADER_NAME)).toBeVisible({ timeout: 15_000 });
				await expect(pageB.locator(HEADER_NAME)).toHaveValue('');
				await expect(pageB.locator('body')).not.toContainText(nameA);
			}
		} finally {
			await ctxB.close();
			await pageA.request.delete(`/api/compare/presets/${idA}`);
			await pageA.request.delete(`/api/locations/${lA.id}`);
		}
	});

	test('AC-11: 390 px — Vorbelegung sichtbar, kein horizontaler Ueberlauf', async ({ page }) => {
		const suffix = Date.now();
		const l1 = await createTestLocation(page.request, { name: `E2E 2277 M1 ${suffix}`, lat: 48.8, lon: 12.8 });
		const l2 = await createTestLocation(page.request, { name: `E2E 2277 M2 ${suffix}`, lat: 48.9, lon: 12.9 });
		const name = `E2E 2277 Vorlage ${suffix}`;
		const origId = await legeVergleichAn(page, name, [l1.id, l2.id]);
		try {
			await page.setViewportSize({ width: 390, height: 844 });
			await page.goto(`/compare/new?from=${origId}`);
			await expect(page.locator(HEADER_NAME_MOBILE)).toHaveValue(`${name} (Kopie)`, { timeout: 15_000 });
			const ueberlauf = await page.evaluate(
				() => document.documentElement.scrollWidth - document.documentElement.clientWidth
			);
			expect(ueberlauf, 'horizontaler Seitenueberlauf bei 390 px').toBeLessThanOrEqual(0);
		} finally {
			await page.request.delete(`/api/compare/presets/${origId}`);
			await page.request.delete(`/api/locations/${l1.id}`);
			await page.request.delete(`/api/locations/${l2.id}`);
		}
	});
});

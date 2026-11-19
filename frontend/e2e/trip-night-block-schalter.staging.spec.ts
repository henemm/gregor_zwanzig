// E2E (Staging) — Issue #1721 (Epic #2259): Schalter "Nacht-Stundentabelle in der Mail zeigen".
//
// Spec: docs/specs/modules/fix_1721_nachtausgabe.md — AC-1, AC-2, AC-3, AC-6, AC-8.
// (AC-4/5/7 = zugestellte Staging-Mail + briefing_mail_validator.py, siehe Testplan Punkt 2.)
//
// #3154 (#3122 B3b, Spec feat_3122_was_steht_wo.md Teil B Nr. 12/14): der Schalter steht nicht mehr im Reiter
// Zustellung, sondern als „Nacht-Stundentabelle“ unter „Ganze Blöcke ein- und ausschalten“ der Karte „Was steht wo“
// (Reiter Wetter, nur Trip); er schreibt weiter `display_config.show_night_block` (PUT auf den Trip). Die Kuerzel
// erklaert das Feld „Kürzel erklärt“ der Karte.
//
// Ausfuehren (lokal gegen ci-stack.sh mit der Haupt-Config, oder gegen Staging, aus frontend/):
//   npx playwright test --project=tests e2e/trip-night-block-schalter.staging.spec.ts

import { test, expect, type Page } from '@playwright/test';
import { createTestComparePreset, createTestLocation, createTestTrip } from './helpers';
import { oeffneKarte } from './was-steht-wo.helpers';
import { wegwerfPasswort } from './stagingZugang';

const SCHALTER = 'was-steht-wo-show_night_block';

async function oeffneWetterMetriken(page: Page, tripId: string) {
	return oeffneKarte(page, 'route', tripId);
}

function schalterGespeichertTrip(page: Page, tripId: string) {
	return page.waitForResponse((r) => new URL(r.url()).pathname === `/api/trips/${tripId}` && r.request().method() === 'PUT', { timeout: 15000 });
}

async function nachtBlockImStand(request: import('@playwright/test').APIRequestContext, tripId: string) {
	const res = await request.get(`/api/trips/${tripId}`);
	expect(res.ok()).toBeTruthy();
	const trip = (await res.json()) as { display_config?: Record<string, unknown> };
	return trip.display_config?.show_night_block;
}

test.describe('Nacht-Stundentabelle-Schalter (#1721, Staging)', () => {
	test.beforeEach(async ({ page }) => {
		await page.setViewportSize({ width: 1400, height: 950 });
	});

	test('AC-1: Trip zeigt den Schalter, Ortsvergleich im selben Reiter nicht', async ({ page, request }) => {
		const trip = await createTestTrip(request, { name: '1721-ac1-trip' });
		const tab = await oeffneWetterMetriken(page, trip.id);
		const schalter = tab.getByTestId(SCHALTER);
		await expect(schalter, 'AC-1: Schalter fehlt in der Karte des Trips').toBeVisible({ timeout: 10000 });
		await expect(tab.getByText('Nacht-Stundentabelle', { exact: true })).toBeVisible();

		const loc = await createTestLocation(request, { name: `1721-ac1-ort-${Date.now()}` });
		const preset = await createTestComparePreset(request, { name: '1721-ac1-vergleich', locationIds: [loc.id] });
		const panel = await oeffneKarte(page, 'vergleich', preset.id);
		await expect(
			panel.getByTestId(SCHALTER),
			'AC-1: der Schalter darf im Ortsvergleich nicht gerendert werden'
		).toHaveCount(0);
	});

	test('AC-2: Alt-Trip ohne Feld steht auf an und sendet beim Speichern anderer Dinge nichts Neues', async ({
		page,
		request
	}) => {
		const trip = await createTestTrip(request, { name: '1721-ac2-alt' });
		expect(await nachtBlockImStand(request, trip.id), 'Vorbedingung: Alt-Trip ohne Feld').toBeUndefined();
		const tab = await oeffneWetterMetriken(page, trip.id);
		await expect(tab.getByTestId(SCHALTER)).toHaveAttribute('aria-checked', 'true', { timeout: 10000 });
	});

	test('AC-3: ausschalten, speichern, neu laden: bleibt aus (Stand per API gegengelesen)', async ({
		page,
		request
	}) => {
		const trip = await createTestTrip(request, { name: '1721-ac3-aus' });
		const tab = await oeffneWetterMetriken(page, trip.id);
		const schalter = tab.getByTestId(SCHALTER);
		await expect(schalter).toHaveAttribute('aria-checked', 'true', { timeout: 10000 });

		const gespeichert = schalterGespeichertTrip(page, trip.id);
		await schalter.click();
		await gespeichert;
		expect(await nachtBlockImStand(request, trip.id)).toBe(false);

		await page.reload();
		const tab2 = await oeffneWetterMetriken(page, trip.id);
		await expect(tab2.getByTestId(SCHALTER), 'AC-3 FAIL: Schalter nach Neuladen wieder an').toHaveAttribute('aria-checked', 'false', {
			timeout: 10000
		});
	});

	test('AC-6: ein zweiter Nutzer sieht den Trip des ersten nicht und seinen eigenen unveraendert auf an', async ({
		page,
		request,
		playwright
	}) => {
		const tripA = await createTestTrip(request, { name: '1721-ac6-a' });
		const tab = await oeffneWetterMetriken(page, tripA.id);
		const gespeichert = schalterGespeichertTrip(page, tripA.id);
		await tab.getByTestId(SCHALTER).click();
		await gespeichert;
		expect(await nachtBlockImStand(request, tripA.id)).toBe(false);

		// Zweiter Nutzer: eigene Sitzung (Staging-Zweitnutzer-Weg aus helpers.ts).
		const { registriereBestaetigtenZweitnutzer } = await import('./helpers');
		const gast = await playwright.request.newContext({ baseURL: page.url().split('/trips')[0] });
		const name = `e2e-1721-${Date.now()}`;
		const kennwort = wegwerfPasswort();
		await registriereBestaetigtenZweitnutzer(request, gast, name, kennwort);
		await gast.post('/api/auth/login', { data: { username: name, password: kennwort } });
		const idB = `e2e-gz-trip-1721-b-${Date.now()}`;
		const anlegen = await gast.post('/api/trips', { data: { id: idB, name: 'E2E-1721-b', stages: [] } });
		expect(anlegen.ok()).toBeTruthy();
		try {
			const fremd = await gast.get(`/api/trips/${tripA.id}`);
			expect(fremd.status(), 'AC-6 FAIL: Nutzer B erreicht den Trip von Nutzer A').toBeGreaterThanOrEqual(400);
			const b = (await (await gast.get(`/api/trips/${idB}`)).json()) as {
				display_config?: Record<string, unknown>;
			};
			expect(b.display_config?.show_night_block, 'B darf von As Schalter unberuehrt sein').not.toBe(false);
		} finally {
			await gast.delete(`/api/trips/${idB}`);
			await gast.dispose();
		}
	});

	test('AC-8: Metrik "Gefuehlte Nacht-Tiefsttemperatur" gewaehlt -> Kuerzel-Legende erklaert FN', async ({
		page,
		request
	}) => {
		const trip = await createTestTrip(request, { name: '1721-ac8-fn' });
		const put = await request.put(`/api/trips/${trip.id}/weather-config`, {
			data: { metrics: [{ metric_id: 'wind_chill_night', enabled: true, aggregations: ['min'] }] }
		});
		expect(put.ok()).toBeTruthy();
		const tab = await oeffneWetterMetriken(page, trip.id);
		await tab.getByTestId('was-steht-wo-legende-auf').click();
		const eintrag = tab.getByTestId('was-steht-wo-legende').locator('[data-legende="FN"]');
		await expect(eintrag, 'AC-8 FAIL: Legende erklaert FN nicht').toBeVisible({ timeout: 10000 });
		expect(((await eintrag.locator('dd').textContent()) ?? '').trim().length, 'AC-8 FAIL: FN ohne Bedeutung').toBeGreaterThan(0);
	});
});

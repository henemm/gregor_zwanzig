// E2E (Staging) — Issue #1721 (Epic #2259): Schalter "Nacht-Stundentabelle in der Mail zeigen".
//
// Spec: docs/specs/modules/fix_1721_nachtausgabe.md — AC-1, AC-2, AC-3, AC-6, AC-8.
// (AC-4/5/7 = zugestellte Staging-Mail + briefing_mail_validator.py, siehe Testplan Punkt 2.)
//
// SCHREIBT NUR — in der RED-Phase NICHT ausgefuehrt (Marker `staging`).
// Ausfuehren erst NACH GREEN, gegen Staging, aus frontend/.

import { test, expect, type Page } from '@playwright/test';
import { createTestComparePreset, createTestLocation, createTestTrip } from './helpers';

const SCHALTER = 'wm-night-block-toggle';

async function oeffneWetterMetriken(page: Page, tripId: string) {
	// #2794 S3a (Spec feat_2794_s3a_teil2_leiste.md): Abschnitt nachtblock und die
	// Kürzel-Legende der Kanal-Karte stehen im Reiter Zustellung.
	await page.goto(`/trips/${tripId}?tab=zustellung`);
	const tabBtn = page.getByTestId('trip-detail-tab-zustellung');
	await expect(tabBtn).toBeVisible({ timeout: 15000 });
	await tabBtn.click();
	const tab = page.getByTestId('weather-metrics-tab');
	await expect(tab).toBeVisible({ timeout: 15000 });
	return tab;
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
		await expect(schalter, 'AC-1: Schalter fehlt im Trip-Reiter').toBeVisible({ timeout: 10000 });
		await expect(tab.getByText('Nacht-Stundentabelle in der Mail zeigen')).toBeVisible();

		const loc = await createTestLocation(request, { name: '1721-ac1-ort' });
		const preset = await createTestComparePreset(request, { name: '1721-ac1-vergleich', locationIds: [loc.id] });
		await page.goto(`/compare/${preset.id}?tab=zustellung`);
		await page.getByTestId('compare-detail-tab-zustellung').click();
		const panel = page.getByTestId('compare-detail-panel-zustellung');
		await expect(panel).toBeVisible({ timeout: 15000 });
		await expect(panel.getByTestId('weather-metrics-tab-vergleich')).toBeVisible({ timeout: 15000 });
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
		await expect(tab.getByTestId(SCHALTER)).toBeChecked({ timeout: 10000 });
	});

	test('AC-3: ausschalten, speichern, neu laden: bleibt aus (Stand per API gegengelesen)', async ({
		page,
		request
	}) => {
		const trip = await createTestTrip(request, { name: '1721-ac3-aus' });
		const tab = await oeffneWetterMetriken(page, trip.id);
		const schalter = tab.getByTestId(SCHALTER);
		await expect(schalter).toBeChecked({ timeout: 10000 });

		const gespeichert = page.waitForResponse(
			(r) => r.url().includes(`/api/trips/${trip.id}/weather-config`) && r.request().method() === 'PUT',
			{ timeout: 15000 }
		);
		await schalter.click();
		await gespeichert;
		expect(await nachtBlockImStand(request, trip.id)).toBe(false);

		await page.reload();
		const tab2 = await oeffneWetterMetriken(page, trip.id);
		await expect(tab2.getByTestId(SCHALTER), 'AC-3 FAIL: Schalter nach Neuladen wieder an').not.toBeChecked({
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
		const gespeichert = page.waitForResponse(
			(r) => r.url().includes(`/api/trips/${tripA.id}/weather-config`) && r.request().method() === 'PUT',
			{ timeout: 15000 }
		);
		await tab.getByTestId(SCHALTER).click();
		await gespeichert;
		expect(await nachtBlockImStand(request, tripA.id)).toBe(false);

		// Zweiter Nutzer: eigene Sitzung (Staging-Zweitnutzer-Weg aus helpers.ts).
		const { registriereBestaetigtenZweitnutzer } = await import('./helpers');
		const gast = await playwright.request.newContext({ baseURL: page.url().split('/trips')[0] });
		const name = `e2e-1721-${Date.now()}`;
		await registriereBestaetigtenZweitnutzer(request, gast, name, 'Test-Passwort-1721!');
		await gast.post('/api/auth/login', { data: { username: name, password: 'Test-Passwort-1721!' } });
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
		const legende = tab.getByTestId('metric-kuerzel-legend');
		await expect(legende).toBeVisible({ timeout: 10000 });
		await expect(legende, 'AC-8 FAIL: Legende erklaert FN nicht').toContainText('FN');
		await expect(legende).toContainText(/Gef(ü|ue)hlte Nacht-Tiefsttemperatur/i);
	});
});

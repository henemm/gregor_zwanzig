// E2E (Staging) — Issue #1848 Scheibe A3: der 3-Tages-Ausblick verhaelt sich
// wie ein Kanal (Grundauswahl als Ausgangsmenge, "Aus"-Knopf/"Aus"-Gruppe
// statt einer zweiten Kaestchenliste).
//
// Spec: docs/specs/modules/feat_1848_a3_ausblick_erbt_grundauswahl.md
//   AC-5, AC-7, AC-8, AC-9
// Kontext: docs/context/feat-1848-a3-outlook-kanal-modul.md
//   Mutations-Gegenproben M-2 (offColumns fehlt), M-3 (onRestore schreibt in
//   die Grundauswahl), M-6 (Grundauswahl-Prop nur an einem Mountpunkt).
//
// Vorbild (WOERTLICH uebertragen): kanal-abwahl-bleibt-reversibel.staging.spec.ts
// (AC-7/AC-9/AC-11 desselben Reihenfolge-Bausteins, nur im Trip-Kanal-Reiter
// statt im Ausblick) und trip-outlook-metric-selection.staging.spec.ts /
// compare-outlook-metric-selection.staging.spec.ts (Ausblick-spezifische
// Navigation).
//
// 🔴 AC-7 UND diese Datei insgesamt trennen Trip und Ortsvergleich in ZWEI
// eigene Test-Faelle (nicht summarisch) -- ein einseitig verdrahteter
// Mountpunkt (M-6: `grundauswahl`-Prop nur am Trip-Mount) faende sich sonst
// nicht.
//
// SCHREIBT NUR — wird in der RED-Phase NICHT ausgefuehrt (Testauflage,
// Marker `staging`). Ausfuehren erst NACH GREEN, gegen Staging, aus frontend/.

import { test, expect, type APIRequestContext, type Locator, type Page } from '@playwright/test';
import { createTestLocation, createTestTrip } from './helpers';

// ─── Trip ────────────────────────────────────────────────────────────────

async function oeffneTripAusblick(page: Page, tripId: string): Promise<Locator> {
	await page.goto(`/trips/${tripId}?tab=weather`);
	const tabBtn = page.getByTestId('trip-detail-tab-weather');
	await expect(tabBtn).toBeVisible({ timeout: 15000 });
	await tabBtn.click();
	const tab = page.getByTestId('weather-metrics-tab');
	await expect(tab).toBeVisible({ timeout: 15000 });
	await expect(tab.getByTestId('wm2-grundauswahl').locator('.toggle-btn').first()).toBeVisible({
		timeout: 10000
	});
	const ausblick = tab.getByTestId('weather-metrics-ausblick');
	await expect(
		ausblick,
		'AC-1: der Abschnitt "3-Tages-Vorschau" fehlt im Trip-Reiter'
	).toBeVisible({ timeout: 10000 });
	return ausblick;
}

function wartetAufTripAutosave(page: Page, tripId: string) {
	return page.waitForResponse(
		(r) => r.url().includes(`/api/trips/${tripId}/weather-config`) && r.request().method() === 'PUT',
		{ timeout: 15000 }
	);
}

test.describe('Trip: 3-Tages-Vorschau erbt die Grundauswahl (#1848 A3, Staging)', () => {
	test.beforeEach(async ({ page }) => {
		await page.setViewportSize({ width: 1400, height: 950 });
	});

	test('AC-7: eine im Ausblick abgewaehlte Groesse landet in der Aus-Gruppe, uebersteht einen Reload und ist von dort zurueckholbar', async ({
		page,
		request
	}) => {
		const trip = await createTestTrip(request, { name: '1848-A3-trip-ac7' });
		const ausblick = await oeffneTripAusblick(page, trip.id);

		const windRow = ausblick.locator('[data-testid="wm2-reihenfolge-row"][data-metric-id="wind"]');
		await expect(windRow, 'Vorbedingung: "Wind" ist aktiv im Ausblick').toBeVisible();
		const gespeichertePut = wartetAufTripAutosave(page, trip.id);
		await windRow.getByRole('button', { name: 'Aus' }).click();
		await gespeichertePut;

		await expect(
			ausblick.locator('[data-testid="wm2-reihenfolge-row"][data-metric-id="wind"]'),
			'AC-7 FAIL: "Wind" bleibt in der aktiven Ausblick-Liste'
		).toHaveCount(0);
		const ausGruppe = ausblick.getByTestId('wm2-aus-gruppe');
		await expect(ausGruppe, 'AC-7 FAIL: keine "Aus"-Gruppe im Ausblick').toBeVisible();
		const windAusRow = ausGruppe.locator('[data-testid="wm2-aus-row"][data-metric-id="wind"]');
		await expect(windAusRow, 'AC-7 FAIL: "Wind" landet nicht in der Aus-Gruppe').toBeVisible();

		await page.reload();
		const ausblickNachReload = await oeffneTripAusblick(page, trip.id);
		await expect(
			ausblickNachReload
				.getByTestId('wm2-aus-gruppe')
				.locator('[data-testid="wm2-aus-row"][data-metric-id="wind"]'),
			'AC-7 FAIL: "Wind" steht nach dem Reload nicht mehr in der Aus-Gruppe'
		).toBeVisible();

		await ausblickNachReload
			.getByTestId('wm2-aus-gruppe')
			.locator('[data-testid="wm2-aus-row"][data-metric-id="wind"]')
			.getByRole('button', { name: 'Ein' })
			.click();
		await expect(
			ausblickNachReload.locator('[data-testid="wm2-reihenfolge-row"][data-metric-id="wind"]'),
			'AC-7 FAIL: "Wind" steht nach "Ein" nicht wieder in der aktiven Liste'
		).toBeVisible();
	});

	test('AC-5: eine Groesse ausserhalb der Grundauswahl erscheint weder in der aktiven Ausblick-Liste noch in dessen Aus-Gruppe', async ({
		page,
		request
	}) => {
		const trip = await createTestTrip(request, { name: '1848-A3-trip-ac5' });
		const tab = page.getByTestId('weather-metrics-tab');
		const ausblick = await oeffneTripAusblick(page, trip.id);

		await expect(
			ausblick.locator('[data-testid="wm2-reihenfolge-row"][data-metric-id="precipitation"]'),
			'Vorbedingung: "Niederschlag" ist zunaechst aktiv im Ausblick'
		).toBeVisible();

		const precipToggle = tab.locator('[data-testid="wm2-grundauswahl"] .toggle-btn[title="Niederschlag"]');
		await expect(precipToggle).toHaveClass(/\bon\b/);
		const gespeichertePut = wartetAufTripAutosave(page, trip.id);
		await precipToggle.click();
		await gespeichertePut;

		await expect(
			ausblick.locator('[data-testid="wm2-reihenfolge-row"][data-metric-id="precipitation"]'),
			'AC-5 FAIL: eine global abgewaehlte Groesse bleibt in der aktiven Ausblick-Liste'
		).toHaveCount(0);
		await expect(
			ausblick.getByTestId('wm2-aus-gruppe').locator('[data-testid="wm2-aus-row"][data-metric-id="precipitation"]'),
			'AC-5 FAIL: eine global abgewaehlte Groesse taucht in der Ausblick-Aus-Gruppe auf — dort steht nur, was abwaehlbar WAERE'
		).toHaveCount(0);
	});

	test('AC-8: eine im Ausblick abgewaehlte Groesse bleibt abgewaehlt, wenn die Grundauswahl aus- und wieder eingeschaltet wird', async ({
		page,
		request
	}) => {
		const trip = await createTestTrip(request, { name: '1848-A3-trip-ac8' });
		const tab = page.getByTestId('weather-metrics-tab');
		const ausblick = await oeffneTripAusblick(page, trip.id);

		const tempRow = ausblick.locator('[data-testid="wm2-reihenfolge-row"][data-metric-id="temperature"]');
		await expect(tempRow).toBeVisible();
		const putAbwahl = wartetAufTripAutosave(page, trip.id);
		await tempRow.getByRole('button', { name: 'Aus' }).click();
		await putAbwahl;
		await expect(
			ausblick.getByTestId('wm2-aus-gruppe').locator('[data-testid="wm2-aus-row"][data-metric-id="temperature"]')
		).toBeVisible();

		const tempToggle = tab.locator('[data-testid="wm2-grundauswahl"] .toggle-btn[title="Temperatur"]');
		await expect(tempToggle).toHaveClass(/\bon\b/);
		const putAus = wartetAufTripAutosave(page, trip.id);
		await tempToggle.click();
		await putAus;
		const putEin = wartetAufTripAutosave(page, trip.id);
		await tempToggle.click();
		await putEin;

		await expect(
			ausblick.locator('[data-testid="wm2-reihenfolge-row"][data-metric-id="temperature"]'),
			'AC-8 FAIL: die Anwahl in der Grundauswahl schreibt in die Ausblick-Abwahl durch'
		).toHaveCount(0);
		await expect(
			ausblick.getByTestId('wm2-aus-gruppe').locator('[data-testid="wm2-aus-row"][data-metric-id="temperature"]'),
			'AC-8 FAIL: "Temperatur" muss weiterhin in der Ausblick-Aus-Gruppe stehen'
		).toBeVisible();
	});

	test('AC-9: das Zurueckholen einer abgewaehlten Groesse im Ausblick schreibt ausschliesslich in outlook_metrics, nie in die Grundauswahl', async ({
		page,
		request
	}) => {
		const trip = await createTestTrip(request, { name: '1848-A3-trip-ac9' });
		const tab = page.getByTestId('weather-metrics-tab');
		const ausblick = await oeffneTripAusblick(page, trip.id);

		const gustRow = ausblick.locator('[data-testid="wm2-reihenfolge-row"][data-metric-id="gust"]');
		await expect(gustRow).toBeVisible();
		const putAbwahl = wartetAufTripAutosave(page, trip.id);
		await gustRow.getByRole('button', { name: 'Aus' }).click();
		await putAbwahl;

		const gustToggleVorher = tab.locator('[data-testid="wm2-grundauswahl"] .toggle-btn[title="Böen"]');
		await expect(gustToggleVorher, 'Vorbedingung: Grundauswahl "Böen" bleibt aktiv').toHaveClass(/\bon\b/);

		const ausGruppe = ausblick.getByTestId('wm2-aus-gruppe');
		const putZurueckholen = wartetAufTripAutosave(page, trip.id);
		await ausGruppe.locator('[data-testid="wm2-aus-row"][data-metric-id="gust"]').getByRole('button', { name: 'Ein' }).click();
		await putZurueckholen;

		await expect(
			tab.locator('[data-testid="wm2-grundauswahl"] .toggle-btn[title="Böen"]'),
			'AC-9 FAIL: das Zurueckholen im Ausblick hat die Grundauswahl veraendert'
		).toHaveClass(/\bon\b/);

		const gespeichert = await page.request.get(`/api/trips/${trip.id}`);
		const body = await gespeichert.json();
		const gustGrundauswahl = (body.display_config?.metrics ?? []).find(
			(m: { metric_id: string }) => m.metric_id === 'gust'
		);
		expect(
			gustGrundauswahl?.enabled,
			'AC-9 FAIL: display_config.metrics (Grundauswahl) wurde durch das Zurueckholen im Ausblick veraendert'
		).toBe(true);
	});
});

// ─── Ortsvergleich ───────────────────────────────────────────────────────

async function createComparePreset(request: APIRequestContext, locationId: string): Promise<string> {
	const res = await request.post('/api/compare/presets', {
		data: {
			name: 'E2E #1848 A3 Ausblick',
			location_ids: [locationId],
			schedule: 'manual',
			profil: 'wandern',
			hour_from: 7,
			hour_to: 18,
			empfaenger: ['urlauber@example.com'],
			display_config: {}
		}
	});
	expect(res.ok(), `Preset-Anlage fehlgeschlagen: ${res.status()}`).toBeTruthy();
	const body = await res.json();
	return body.id as string;
}

async function oeffneCompareAusblick(page: Page, presetId: string): Promise<Locator> {
	await page.goto(`/compare/${presetId}`);
	await expect(page.getByTestId('compare-detail-tab-list')).toBeVisible({ timeout: 15000 });
	await page.getByTestId('compare-detail-tab-wetter-metriken').click();
	const panel = page.getByTestId('compare-detail-panel-wetter-metriken');
	await expect(panel).toBeVisible({ timeout: 10000 });
	const ausblick = panel.getByTestId('weather-metrics-ausblick');
	await expect(
		ausblick,
		'AC-2: der Abschnitt "3-Tages-Ausblick" fehlt im Ortsvergleich-Reiter'
	).toBeVisible({ timeout: 10000 });
	return ausblick;
}

test.describe('Ortsvergleich: 3-Tages-Ausblick erbt die Grundauswahl (#1848 A3, Staging)', () => {
	test.beforeEach(async ({ page }) => {
		await page.setViewportSize({ width: 1400, height: 950 });
	});

	test('AC-7 (eigener Lauf im Ortsvergleich, s. M-6): eine abgewaehlte Groesse landet in der Aus-Gruppe, uebersteht einen Reload und ist zurueckholbar', async ({
		page,
		request
	}) => {
		const loc = await createTestLocation(request, { name: '1848-A3-compare-loc' });
		const presetId = await createComparePreset(request, loc.id);
		const ausblick = await oeffneCompareAusblick(page, presetId);

		const windRow = ausblick.locator('[data-testid="wm2-reihenfolge-row"][data-metric-id="wind"]');
		await expect(windRow, 'Vorbedingung: "Wind" ist aktiv im Ortsvergleich-Ausblick').toBeVisible();
		await windRow.getByRole('button', { name: 'Aus' }).click();

		await expect(
			ausblick.locator('[data-testid="wm2-reihenfolge-row"][data-metric-id="wind"]'),
			'AC-7 FAIL (Ortsvergleich): "Wind" bleibt in der aktiven Liste'
		).toHaveCount(0);
		const ausGruppe = ausblick.getByTestId('wm2-aus-gruppe');
		await expect(ausGruppe, 'AC-7 FAIL (Ortsvergleich): keine "Aus"-Gruppe im Ausblick').toBeVisible();
		await expect(
			ausGruppe.locator('[data-testid="wm2-aus-row"][data-metric-id="wind"]'),
			'AC-7 FAIL (Ortsvergleich): "Wind" landet nicht in der Aus-Gruppe'
		).toBeVisible();

		await page.reload();
		const panelNachReload = page.getByTestId('compare-detail-panel-wetter-metriken');
		await expect(panelNachReload).toBeVisible({ timeout: 15000 });
		const ausblickNachReload = panelNachReload.getByTestId('weather-metrics-ausblick');
		const ausRowNachReload = ausblickNachReload
			.getByTestId('wm2-aus-gruppe')
			.locator('[data-testid="wm2-aus-row"][data-metric-id="wind"]');
		await expect(
			ausRowNachReload,
			'AC-7 FAIL (Ortsvergleich): "Wind" steht nach dem Reload nicht mehr in der Aus-Gruppe'
		).toBeVisible();

		await ausRowNachReload.getByRole('button', { name: 'Ein' }).click();
		await expect(
			ausblickNachReload.locator('[data-testid="wm2-reihenfolge-row"][data-metric-id="wind"]'),
			'AC-7 FAIL (Ortsvergleich): "Wind" steht nach "Ein" nicht wieder in der aktiven Liste'
		).toBeVisible();

		await request.delete(`/api/compare/presets/${presetId}`).catch(() => {});
		await request.delete(`/api/locations/${loc.id}`).catch(() => {});
	});
});

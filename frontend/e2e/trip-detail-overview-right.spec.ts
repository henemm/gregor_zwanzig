// TDD RED: Epic #135 Step 5 — Trip-Detail Overview, rechte Spalte E2E (#158 + #159).
//
// Spec: docs/specs/modules/epic_135_step5_right_column.md
//
// Voraussetzung (nach Step-6 GREEN-Implementierung):
//   - Test-Trip `e2e-cockpit-test` aus global.setup.ts mit:
//       report_config = { enabled: true, morning_time: '06:00:00',
//                         evening_time: '18:00:00', alert_on_changes: true }
//       weather_config = { metrics: ['temp_min','temp_max','wind_max','precip_sum'] }
//       aggregation    = { activity_profile: 'wandern' }
//
// Erwartet: Alle Tests scheitern in RED-Phase, weil
//   - BriefingPreviewCard / WeatherMetricsPreviewCard / AlertsPreviewCard / PreviewCard
//     noch nicht existieren
//   - TestIDs right-card-* noch nicht im DOM sind
//   - Test-Trip-Seed in global.setup.ts noch nicht erweitert wurde

import { test, expect } from '@playwright/test';

const TRIP_ID = 'e2e-cockpit-test';

async function resetTripState(request: import('@playwright/test').APIRequestContext) {
	await request.patch(`/api/trips/${TRIP_ID}/state`, {
		data: { paused: false, archived: false }
	});
}

test.describe('Epic #135 Step 5 — Trip-Detail Overview, rechte Spalte (#158 + #159)', () => {
	test.beforeEach(async ({ request }) => {
		await resetTripState(request);
	});

	test.afterAll(async ({ request }) => {
		await resetTripState(request);
	});

	test('AC-1: rechte Spalte enthaelt genau 4 Karten in fester DOM-Reihenfolge', async ({
		page
	}) => {
		await page.goto(`/trips/${TRIP_ID}`);
		const aside = page.getByTestId('trip-overview-right-column');
		await expect(aside).toBeVisible();

		await expect(page.getByTestId('right-card-briefings')).toBeVisible();
		await expect(page.getByTestId('right-card-weather')).toBeVisible();
		await expect(page.getByTestId('right-card-alerts')).toBeVisible();
		await expect(page.getByTestId('right-card-preview')).toBeVisible();

		// DOM-Reihenfolge: briefings → weather → alerts → preview
		const order = await page.evaluate(() => {
			const ids = [
				'right-card-briefings',
				'right-card-weather',
				'right-card-alerts',
				'right-card-preview'
			];
			const nodes = ids.map((id) => document.querySelector(`[data-testid="${id}"]`));
			if (nodes.some((n) => !n)) return false;
			for (let i = 0; i < nodes.length - 1; i++) {
				// DOCUMENT_POSITION_FOLLOWING = 4
				if ((nodes[i]!.compareDocumentPosition(nodes[i + 1]!) & 4) === 0) return false;
			}
			return true;
		});
		expect(order).toBe(true);
	});

	test('AC-2: Briefing-Karte zeigt morning_time, evening_time und alert_on_changes "an"', async ({
		page
	}) => {
		await page.goto(`/trips/${TRIP_ID}`);
		const briefingCard = page.getByTestId('right-card-briefings');
		await expect(briefingCard).toBeVisible();

		await expect(page.getByTestId('right-card-briefings-morning')).toContainText('06:00:00');
		await expect(page.getByTestId('right-card-briefings-evening')).toContainText('18:00:00');
		await expect(page.getByTestId('right-card-briefings-alerts')).toContainText('an');
	});

	test('AC-3: Empty-State bei Trip ohne report_config — Bearbeiten-Link bleibt sichtbar', async ({
		page,
		request
	}) => {
		// Eigenen Trip ohne report_config anlegen (analog AC-15 in trip-detail-overview-left.spec.ts).
		const NO_BRIEFING_TRIP_ID = 'e2e-no-briefing-trip';
		await request.post('/api/trips', {
			data: {
				id: NO_BRIEFING_TRIP_ID,
				name: 'E2E No-Briefing Trip',
				stages: [
					{
						id: 'nb-stage-1',
						name: 'Etappe',
						date: new Date().toISOString().slice(0, 10),
						waypoints: [
							{ id: 'nb-wp-1', name: 'Start', lat: 42.1, lon: 9.0, elevation_m: 500 },
							{ id: 'nb-wp-2', name: 'Ziel', lat: 42.2, lon: 9.1, elevation_m: 700 }
						]
					}
				]
			}
		});

		await page.goto(`/trips/${NO_BRIEFING_TRIP_ID}`);
		const briefingCard = page.getByTestId('right-card-briefings');
		await expect(briefingCard).toBeVisible();
		await expect(briefingCard).toContainText('Briefings deaktiviert');

		// Empty-State: die drei Zeilen sollen NICHT im DOM sein.
		await expect(page.getByTestId('right-card-briefings-morning')).toHaveCount(0);
		await expect(page.getByTestId('right-card-briefings-evening')).toHaveCount(0);
		await expect(page.getByTestId('right-card-briefings-alerts')).toHaveCount(0);

		// Bearbeiten-Link bleibt sichtbar und klickbar.
		await expect(page.getByTestId('right-card-briefings-edit-link')).toBeVisible();
	});

	test('AC-4: Klick auf Briefing-Bearbeiten-Link → URL-Hash #briefings + Tab aktiv', async ({
		page
	}) => {
		await page.goto(`/trips/${TRIP_ID}`);
		await page.getByTestId('right-card-briefings-edit-link').click();

		await expect(page).toHaveURL(/#briefings$/);

		// Tab-Trigger ist aktiv (bits-ui setzt data-state="active" auf den aktiven Tab).
		const briefingsTab = page.getByTestId('trip-detail-tab-briefings');
		await expect(briefingsTab).toHaveAttribute('data-state', 'active');
	});

	test('AC-5: Wetter-Karte zeigt Preset-Label als H3 ("Wandern-Standard" bei activity_profile=wandern)', async ({
		page
	}) => {
		await page.goto(`/trips/${TRIP_ID}`);
		const preset = page.getByTestId('right-card-weather-preset');
		await expect(preset).toBeVisible();
		await expect(preset).toContainText('Wandern-Standard');

		// Element ist ein <h3>.
		const tagName = await preset.evaluate((el) => el.tagName.toLowerCase());
		expect(tagName).toBe('h3');
	});

	test('AC-6: Wetter-Karte zeigt 4 Tag-Chips fuer 4 konfigurierte Metriken', async ({ page }) => {
		await page.goto(`/trips/${TRIP_ID}`);

		await expect(page.getByTestId('right-card-weather-chip-temp_min')).toBeVisible();
		await expect(page.getByTestId('right-card-weather-chip-temp_max')).toBeVisible();
		await expect(page.getByTestId('right-card-weather-chip-wind_max')).toBeVisible();
		await expect(page.getByTestId('right-card-weather-chip-precip_sum')).toBeVisible();
	});

	test('AC-7: Klick auf Wetter-Bearbeiten-Link → ?tab=weather + Tab aktiv', async ({
		page
	}) => {
		await page.goto(`/trips/${TRIP_ID}`);
		await page.getByTestId('right-card-weather-edit-link').click();

		await expect(page).toHaveURL(/\?tab=weather$/);
		await expect(page.getByTestId('trip-detail-tab-weather')).toHaveAttribute(
			'data-state',
			'active'
		);
	});

	test('AC-8: Alert-Karte zeigt Empty-State "Noch keine Alerts konfiguriert"', async ({
		page
	}) => {
		await page.goto(`/trips/${TRIP_ID}`);
		const alertEmpty = page.getByTestId('right-card-alerts-empty');
		await expect(alertEmpty).toBeVisible();
		await expect(alertEmpty).toContainText('Noch keine Alerts konfiguriert');
	});

	// Issue #222 W2: Card-Rendering bei vorhandenen alert_rules (AC-4 + AC-6).
	// Legt einen separaten Trip mit alert_rules an, prueft Row-Count + Gewitter-Spezialfall.
	test('AC #222 W2 AC-4/AC-6: Alert-Karte rendert eine Row pro enabled Rule, Gewitter zeigt "MITTEL"', async ({
		page,
		request
	}) => {
		const ALERT_TRIP_ID = 'e2e-alert-rules-trip';
		await request.post('/api/trips', {
			data: {
				id: ALERT_TRIP_ID,
				name: 'E2E Alert Rules Trip',
				stages: [
					{
						id: 'ar-stage-1',
						name: 'Etappe',
						date: new Date().toISOString().slice(0, 10),
						waypoints: [
							{ id: 'ar-wp-1', name: 'Start', lat: 42.1, lon: 9.0, elevation_m: 500 }
						]
					}
				],
				alert_rules: [
					{
						id: 'rule-wind',
						kind: 'absolute',
						metric: 'wind_gust',
						threshold: 50,
						unit: 'km/h',
						severity: 'warning',
						enabled: true
					},
					{
						id: 'rule-thunder',
						kind: 'absolute',
						metric: 'thunder_level',
						threshold: 1.0,
						unit: '',
						severity: 'warning',
						enabled: true
					},
					{
						id: 'rule-thunder-critical',
						kind: 'absolute',
						metric: 'thunder_level',
						threshold: 2.0,
						unit: '',
						severity: 'critical',
						enabled: true
					},
					{
						id: 'rule-disabled',
						kind: 'absolute',
						metric: 'precipitation_sum',
						threshold: 20,
						unit: 'mm',
						severity: 'warning',
						enabled: false
					}
				]
			}
		});

		await page.goto(`/trips/${ALERT_TRIP_ID}`);
		const rows = page.getByTestId('alert-row');
		// AC-4: 3 enabled Rules → 3 Rows. Disabled wird gefiltert.
		await expect(rows).toHaveCount(3);
		// AC-6 (Gewitter-Spezial): threshold=1.0 → "MITTEL", nicht "1.0".
		await expect(rows.nth(1)).toContainText('MITTEL');
		// AC-6: severity=critical → Pill mit tone="danger", threshold=2.0 → "HOCH".
		await expect(rows.nth(2)).toContainText('HOCH');
		const dangerPill = rows.nth(2).locator('[data-slot="pill"][data-tone="danger"]');
		await expect(dangerPill).toBeVisible();

		// Cleanup: Test-Trip loeschen (F006 Fix-Loop 2).
		const deleteRes = await request.delete(`/api/trips/${ALERT_TRIP_ID}`);
		expect([200, 204, 404]).toContain(deleteRes.status());
	});

	test('AC-10: Vorschau-Karte hat genau 2 CTAs (Email + SMS) mit href=#preview', async ({
		page
	}) => {
		await page.goto(`/trips/${TRIP_ID}`);
		const previewCard = page.getByTestId('right-card-preview');
		await expect(previewCard).toBeVisible();

		const emailCta = page.getByTestId('right-card-preview-email');
		const smsCta = page.getByTestId('right-card-preview-sms');

		await expect(emailCta).toBeVisible();
		await expect(smsCta).toBeVisible();

		await expect(emailCta).toHaveAttribute('href', '#preview');
		await expect(smsCta).toHaveAttribute('href', '#preview');
	});

	test('AC-11: Klick auf Email-CTA → URL-Hash #preview + Tab aktiv', async ({ page }) => {
		await page.goto(`/trips/${TRIP_ID}`);
		await page.getByTestId('right-card-preview-email').click();

		await expect(page).toHaveURL(/#preview$/);
		await expect(page.getByTestId('trip-detail-tab-preview')).toHaveAttribute(
			'data-state',
			'active'
		);
	});

	test('AC-12: Klick auf SMS-CTA → URL-Hash #preview + Tab aktiv (data-channel="sms")', async ({
		page
	}) => {
		await page.goto(`/trips/${TRIP_ID}`);
		const smsCta = page.getByTestId('right-card-preview-sms');
		await expect(smsCta).toHaveAttribute('data-channel', 'sms');

		await smsCta.click();
		await expect(page).toHaveURL(/#preview$/);
		await expect(page.getByTestId('trip-detail-tab-preview')).toHaveAttribute(
			'data-state',
			'active'
		);
	});

	test('AC-16: Hero (Step 3) + linke Spalte (Step 4) bleiben sichtbar (Regressions-Guard)', async ({
		page
	}) => {
		await page.goto(`/trips/${TRIP_ID}`);

		// Step 3
		await expect(page.getByTestId('trip-hero')).toBeVisible();
		await expect(page.getByTestId('trip-hero-title')).toBeVisible();

		// Step 4
		await expect(page.getByTestId('trip-overview')).toBeVisible();
		await expect(page.getByTestId('trip-overview-left-column')).toBeVisible();
		await expect(page.getByTestId('trip-full-profile')).toBeVisible();
		await expect(page.getByTestId('trip-stage-list')).toBeVisible();
	});

	test('AC-17: Tab-Navigation + Header bleiben sichtbar (Regressions-Guard)', async ({ page }) => {
		await page.goto(`/trips/${TRIP_ID}`);

		// Step 1
		await expect(page.getByTestId('trip-detail-tab-list')).toBeVisible();
		for (const tab of ['overview', 'stages', 'weather', 'briefings', 'alerts', 'preview']) {
			await expect(page.getByTestId(`trip-detail-tab-${tab}`)).toBeVisible();
		}

		// Step 2
		// Issue #699: innere Duplikat-Breadcrumb entfernt → äußere Bar prüfen.
		await expect(page.getByTestId('trip-detail-breadcrumb-bar')).toBeVisible();
	});
});

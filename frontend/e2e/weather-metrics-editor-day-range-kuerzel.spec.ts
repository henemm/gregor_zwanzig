// E2E — Issue #1728 Scheibe 2: Editor-Nachzug "05 — Auswertungen" entfällt,
// fünf neue Kürzel-Zeilen in "04 — Schwellwerte".
//
// Spec: docs/specs/modules/feat_1728_s2_editor.md § DEC-11, AC-1..AC-12
// Kontext: docs/context/feat-1728-s2-editor.md
//
// Format-Vorbild (DEC-11): issue-494-trip-edit-design.spec.ts:208-216
// ("… existieren NICHT mehr im DOM", toHaveCount(0) je entferntem Testid)
// und versand-tab.spec.ts:142-163 (Element nach Umzug verschwunden).
//
// Drei Nachweispunkte in dieser Datei:
//   1. Trip-Editor: Abschnitt "05 — Auswertungen" existiert NICHT mehr (Negativ).
//   2. Trip-Editor: die fünf neuen Kürzel-Zeilen in "04 — Schwellwerte" sind
//      sichtbar (Positiv, stabile Testids aus MultiSymbolMetricRow.svelte:17,21).
//   3. Vergleich-Editor bleibt unverändert (Regressionsschutz) —
//      AggregationMetricRow mode='multiple' funktioniert weiterhin in der
//      Compare-Grundauswahl "02" (DEC-2, AC-9).
//
// Läuft lokal/manuell gegen den Preview-Server (playwright.config.ts,
// baseURL http://localhost:4173) — NICHT Teil der CI-Positivliste
// (.github/ci_e2e_specs.txt), Filter B (3x grün im Zielverbund) kann diese
// Scheibe nicht selbst herstellen (Spec § Known Limitations, AC-12).
//
// RED bis WeatherMetricsTab.svelte um die fünf {#if}-Blöcke ergänzt und der
// 05-Block entfernt ist (DEC-6, DEC-7).

import { test, expect, type APIRequestContext, type Page } from '@playwright/test';
import { login, createTestLocation, createTestComparePreset } from './helpers.js';

const TRIP_PREFIX = 'e2e-gz-1728-s2';
const tripId = (suffix: string) => `${TRIP_PREFIX}-${suffix}`;

// Muster weather-metrics-tab-autosave.spec.ts: `display_config.metrics` mit
// `bucket: 'primary'` platziert eine metricId in `buckets.primary`, NICHT in
// `buckets.off` — nur so rendern die neuen {#if !buckets.off.includes(...)}-
// Gate-Blöcke ihre Zeile (die vier neuen Größen sind laut Katalog
// "waehlbar, aber bei neuen Trips nicht vorbelegt", s. metric_catalog.py).
const HORIZONS_ALL = { today: true, tomorrow: true, day_after: true };
const NEW_ROW_METRIC_IDS = [
	'temperature_day_low',
	'temperature_day_high',
	'wind_chill_day_low',
	'wind_chill_day_high',
	'wind_chill_night'
];

function seedMetrics(ids: string[]) {
	return ids.map((id, i) => ({
		metric_id: id,
		enabled: true,
		use_friendly_format: true,
		horizons: HORIZONS_ALL,
		bucket: 'primary',
		order: i
	}));
}

async function createTrip(request: APIRequestContext, id: string): Promise<void> {
	const res = await request.post('/api/trips', {
		data: {
			id,
			name: `Issue 1728 S2 ${id}`,
			stages: [
				{
					id: `${id}-stage-1`,
					name: 'Etappe',
					date: new Date().toISOString().slice(0, 10),
					waypoints: [{ id: `${id}-wp-1`, name: 'Start', lat: 42.1, lon: 9.0, elevation_m: 500 }]
				}
			],
			display_config: { metrics: seedMetrics(NEW_ROW_METRIC_IDS) }
		}
	});
	expect([200, 201], `Seed HTTP ${res.status()}`).toContain(res.status());
}

async function deleteTrip(request: APIRequestContext, id: string): Promise<void> {
	const res = await request.delete(`/api/trips/${id}`);
	expect([200, 204, 404]).toContain(res.status());
}

test.describe('Issue #1728 Scheibe 2: "05 — Auswertungen" entfällt, fünf neue Kürzel-Zeilen', () => {
	test.beforeEach(async ({ page }) => {
		await login(page);
	});

	// ── Punkt 1 (AC-7): "05 — Auswertungen" existiert nicht mehr ─────────────
	test('AC-7: Abschnitt "05 — Auswertungen" existiert NICHT mehr im Trip-Editor', async ({
		page,
		request
	}) => {
		const id = tripId('ac7');
		await createTrip(request, id);
		try {
			await page.goto(`/trips/${id}?tab=weather`);
			await page.locator('[data-testid="weather-metrics-tab"]').waitFor({ state: 'visible' });

			// Eyebrow-Überschrift "05 — Auswertungen" darf nicht mehr vorkommen.
			await expect(page.getByText('05 — Auswertungen', { exact: false })).toHaveCount(0);

			// Der vormalige Container-Testid des Bedienabschnitts darf nicht
			// mehr im DOM sein (Muster issue-494-trip-edit-design.spec.ts:208-216).
			await expect(page.locator('[data-testid="metric-aggregations"]')).toHaveCount(0);
		} finally {
			await deleteTrip(request, id);
		}
	});

	// ── Punkt 2 (AC-1..AC-5): fünf neue Kürzel-Zeilen sichtbar ────────────────
	test('AC-1..AC-5: die fünf neuen Kürzel-Zeilen sind in "04 — Schwellwerte" sichtbar', async ({
		page,
		request
	}) => {
		const id = tripId('ac1to5');
		await createTrip(request, id);
		try {
			await page.goto(`/trips/${id}?tab=weather`);
			await page.locator('[data-testid="weather-metrics-tab"]').waitFor({ state: 'visible' });
			await expect(page.getByText('04 — Schwellwerte', { exact: false })).toBeVisible();

			const expectations: Array<[string, string]> = [
				['temperature_day_low', 'K'],
				['temperature_day_high', 'D'],
				['wind_chill_day_low', 'FK'],
				['wind_chill_day_high', 'FD'],
				['wind_chill_night', 'FN']
			];
			for (const [metricId, symbol] of expectations) {
				await expect(
					page.locator(`[data-testid="sms-multi-symbol-row-${metricId}"]`),
					`Zeile für ${metricId} fehlt (AC-1..AC-5)`
				).toBeVisible();
				await expect(
					page.locator(`[data-testid="sms-symbol-badge-${metricId}-${symbol}"]`),
					`Kürzel-Badge ${symbol} für ${metricId} fehlt`
				).toBeVisible();
			}
		} finally {
			await deleteTrip(request, id);
		}
	});

	// ── Punkt 2 (AC-6): Abwahl in "02 — Grundauswahl" blendet die Zeile aus ──
	test('AC-6: eine abgewählte neue Größe zeigt KEINE Zeile in "04 — Schwellwerte"', async ({
		page,
		request
	}) => {
		const id = tripId('ac6');
		// wind_chill_night NICHT in display_config.metrics -> landet in buckets.off.
		await createTrip(request, id);
		const putRes = await request.get(`/api/trips/${id}`);
		expect(putRes.ok()).toBeTruthy();
		const trip = await putRes.json();
		const withoutFN = {
			...trip,
			display_config: {
				...trip.display_config,
				metrics: seedMetrics(NEW_ROW_METRIC_IDS.filter((m) => m !== 'wind_chill_night'))
			}
		};
		const putAbwahl = await request.put(`/api/trips/${id}`, { data: withoutFN });
		expect(putAbwahl.ok()).toBeTruthy();
		try {
			await page.goto(`/trips/${id}?tab=weather`);
			await page.locator('[data-testid="weather-metrics-tab"]').waitFor({ state: 'visible' });

			await expect(
				page.locator('[data-testid="sms-multi-symbol-row-wind_chill_night"]'),
				'AC-6 FAIL: abgewählte Größe zeigt trotzdem eine Zeile'
			).toHaveCount(0);
			// Gegenprobe: eine NICHT abgewählte Zeile bleibt sichtbar.
			await expect(page.locator('[data-testid="sms-multi-symbol-row-temperature_day_low"]')).toBeVisible();
		} finally {
			await deleteTrip(request, id);
		}
	});

	// ── Punkt 3 (AC-9): Vergleich-Editor bleibt unverändert ──────────────────
	test('AC-9: Vergleich-Editor — AggregationMetricRow mode="multiple" funktioniert weiterhin in der Grundauswahl', async ({
		page,
		request
	}) => {
		const locA = await createTestLocation(request, { lat: 47.1, lon: 11.1 });
		const locB = await createTestLocation(request, { lat: 47.2, lon: 11.2 });
		const preset = await createTestComparePreset(request, {
			locationIds: [locA.id, locB.id]
		});

		await page.goto(`/compare/${preset.id}`);
		await expect(page.getByTestId('compare-detail-tab-list')).toBeVisible({ timeout: 10_000 });
		await page.getByTestId('compare-detail-tab-wetter-metriken').click();
		// Vergleich-Kontext traegt ein EIGENES Container-Testid
		// (WeatherMetricsTab.svelte:1252) -- "weather-metrics-tab" ohne Suffix
		// (:1438) existiert nur im 'route'-Zweig (Trip-Editor).
		await page.locator('[data-testid="weather-metrics-tab-vergleich"]').waitFor({ state: 'visible' });

		// "temperature" hat im Katalog 3 Auswertungen (min/max/avg) -> Gruppe mit
		// >1 Option nutzt AggregationMetricRow mode='multiple' (WeatherMetricsTab.
		// svelte:1308-1315). Regressionsnachweis: Zeile UND mindestens eine
		// unabhängige Checkbox-Option sind sichtbar und bedienbar.
		const row = page.getByTestId('weather-metrics-vergleich-row-temperature');
		await expect(row).toBeVisible({ timeout: 8_000 });
		await expect(page.locator('[data-testid="weather-metrics-vergleich-option-temperature-max"]')).toBeVisible();
		await expect(page.locator('[data-testid="weather-metrics-vergleich-option-temperature-min"]')).toBeVisible();
	});
});

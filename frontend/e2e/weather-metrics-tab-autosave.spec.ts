// E2E (Staging) — Issue #1234: Auto-Save im Inhalt-Tab darf Metriken nicht
// stillschweigend leeren.
//
// Spec: docs/specs/modules/issue_1234_autosave_hydration_gate.md
//   § Test Plan, § Acceptance Criteria
// Kausalkette: docs/context/fix-1234-mount-autosave-metrics.md
//
// Nachweis über abgefangene Netzwerk-Requests (page.on('request') / page.route),
// nicht über Optik. Setup/Login-Muster analog compare-hub-fidelity-s8c.spec.ts +
// playwright.1256-s2.staging.config.ts (storageState statt Login pro Test —
// vermeidet das Staging-Auth-Rate-Limit, #703).
//
// Ausführen (gegen Staging, aus frontend/):
//   set -a; source /home/hem/gregor_zwanzig/.claude/validator.env; set +a
//   npx playwright test --config=playwright.1234.staging.config.ts

import { test, expect, type Page, type Request, type APIRequestContext } from '@playwright/test';
import { oeffneKarte } from './was-steht-wo.helpers';

const TRIP_PREFIX = 'e2e-1234';
const HORIZONS_ALL = { today: true, tomorrow: true, day_after: true };
// Fix-Loop 3: 'wind_gust' existierte nicht im Metrik-Katalog (echte ID: 'gust',
// src/app/metric_catalog.py:155) — die Toggle-Abwahl-Schleife in AC-4 konnte
// diese unbekannte ID nie abwählen, wodurch der Test nie sein eigenes
// Soll-Ziel (0 aktive Metriken) erreichte. Betrifft NUR display_config.metrics
// (Weather-Tab-Katalog); die Alarm-Regel-Metrik 'wind_gust' weiter unten ist
// ein separates Enum (AlertMetric, src/app/models.py:785) und bleibt korrekt.
const METRIC_IDS = ['temperature', 'wind', 'precipitation', 'gust', 'uv_index'];

function tripId(suffix: string): string {
	return `${TRIP_PREFIX}-${suffix}`;
}

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

async function createTrip(
	request: APIRequestContext,
	id: string,
	opts: { metrics?: unknown[]; alert_rules?: unknown[] } = {}
) {
	const res = await request.post('/api/trips', {
		data: {
			id,
			name: `Issue 1234 ${id}`,
			stages: [
				{
					id: `${id}-stage-1`,
					name: 'Etappe',
					date: new Date().toISOString().slice(0, 10),
					waypoints: [{ id: `${id}-wp-1`, name: 'Start', lat: 42.1, lon: 9.0, elevation_m: 500 }]
				}
			],
			display_config: { metrics: opts.metrics ?? [] },
			alert_rules: opts.alert_rules ?? []
		}
	});
	expect([200, 201], `Seed HTTP ${res.status()}`).toContain(res.status());
}

async function deleteTrip(request: APIRequestContext, id: string) {
	const res = await request.delete(`/api/trips/${id}`);
	expect([200, 204, 404]).toContain(res.status());
}

async function fetchTrip(request: APIRequestContext, id: string) {
	const res = await request.get(`/api/trips/${id}`);
	expect(res.ok(), `GET HTTP ${res.status()}`).toBeTruthy();
	return res.json();
}

function activeMetricIds(metrics: Array<{ metric_id: string; enabled: boolean }> = []): string[] {
	return metrics.filter((m) => m.enabled).map((m) => m.metric_id);
}

/** Zeichnet jeden PUT-Request auf den Trip (Detail + weather-config) auf. */
function collectTripPuts(page: Page, id: string): Request[] {
	const puts: Request[] = [];
	page.on('request', (req) => {
		if (req.method() === 'PUT' && req.url().includes(`/api/trips/${id}`)) {
			puts.push(req);
		}
	});
	return puts;
}

test.describe('Issue #1234: Auto-Save-Hydration-Gate im Inhalt-Tab', () => {
	// AC-1/AC-2/AC-6: Tab öffnen, nichts anklicken, über die Debounce-Zeit hinaus
	// warten, Tab wechseln → kein Speichervorgang, Metriken UND Alarm-Regeln
	// bleiben unverändert.
	test('AC-1/AC-2/AC-6: Tab öffnen ohne Klick → kein PUT, Metriken + Alarm-Regeln unverändert', async ({
		page,
		request
	}) => {
		const id = tripId('ac1');
		const seedAlertRules = [
			{
				id: 'r1',
				kind: 'absolute',
				metric: 'wind_gust',
				threshold: 50,
				unit: 'km/h',
				severity: 'warning',
				enabled: true
			}
		];
		await createTrip(request, id, { metrics: seedMetrics(METRIC_IDS), alert_rules: seedAlertRules });
		// AC-2 prüft Unverändertheit ("bleiben erhalten"), nicht eine Anzahl.
		// Die starke Fassung (Trip HAT Regeln → Regeln überleben) ist heute nicht
		// herstellbar: #1257 löscht alert_rules bei jedem Speichern/Laden
		// (Namensraum-Mismatch gust/wind_gust). Sobald #1257 gefixt ist, wird dieser
		// Test automatisch zur starken Fassung — ohne Änderung.
		const before = await fetchTrip(request, id);
		const puts = collectTripPuts(page, id);
		try {
			await page.goto(`/trips/${id}`);
			await page.getByTestId('trip-detail-tab-wetter').click();
			await expect(page.getByTestId('weather-metrics-tab')).toBeVisible();

			// > 700ms Debounce (saveStatusStore.svelte.ts schedule()).
			await page.waitForTimeout(3_000);
			await page.getByTestId('trip-detail-tab-etappen').click();
			await page.waitForTimeout(500);

			expect(
				puts.map((p) => p.url()),
				'kein PUT auf /api/trips/{id} oder /api/trips/{id}/weather-config erwartet'
			).toHaveLength(0);

			const trip = await fetchTrip(request, id);
			expect(activeMetricIds(trip.display_config?.metrics).sort()).toEqual([...METRIC_IDS].sort());
			expect(trip.alert_rules).toEqual(before.alert_rules);
		} finally {
			await deleteTrip(request, id);
		}
	});

	// AC-3: Katalog-Fetch schlägt fehl → Fehlermeldung + Wiederholen, kein
	// Editor, kein Schreibzugriff.
	test('AC-3: Katalog-Fehler → Fehlermeldung + Wiederholen sichtbar, kein Editor, kein PUT', async ({
		page,
		request
	}) => {
		const id = tripId('ac3');
		await createTrip(request, id, { metrics: seedMetrics(METRIC_IDS) });
		const puts = collectTripPuts(page, id);
		try {
			await page.route('**/api/metrics', (route) =>
				route.fulfill({ status: 500, body: JSON.stringify({ error: 'Serverfehler' }) })
			);
			await page.goto(`/trips/${id}`);
			await page.getByTestId('trip-detail-tab-wetter').click();

			await expect(page.getByTestId('weather-metrics-load-error')).toBeVisible();
			await expect(page.getByTestId('weather-metrics-load-retry')).toBeVisible();
			await expect(page.getByTestId('weather-metrics-tab')).toHaveCount(0);

			await page.waitForTimeout(1_500);
			expect(puts.map((p) => p.url())).toHaveLength(0);
		} finally {
			await deleteTrip(request, id);
		}
	});

	// AC-4: bewusstes Abwählen aller Metriken bleibt möglich — PUT mit
	// metrics:[] geht raus, nach Reload leer.
	test('AC-4: alle Metriken bewusst abwählen → PUT mit leerer Auswahl, bleibt nach Reload leer', async ({
		page,
		request
	}) => {
		const id = tripId('ac4');
		await createTrip(request, id, { metrics: seedMetrics(METRIC_IDS) });
		const puts = collectTripPuts(page, id);
		try {
			await page.goto(`/trips/${id}`);
			await page.getByTestId('trip-detail-tab-wetter').click();
			await expect(page.getByTestId('weather-metrics-tab')).toBeVisible();

			const activeToggles = page.locator('[data-testid="wm2-grundauswahl"] .toggle-btn.on');
			let remaining = await activeToggles.count();
			expect(remaining).toBeGreaterThan(0);
			while (remaining > 0) {
				await activeToggles.first().click();
				await page.waitForTimeout(50);
				remaining = await activeToggles.count();
			}

			await page.waitForResponse(
				(r) => r.url().includes(`/api/trips/${id}/weather-config`) && r.request().method() === 'PUT',
				{ timeout: 10_000 }
			);

			const configPuts = puts.filter((r) => r.url().includes('/weather-config'));
			expect(configPuts.length).toBeGreaterThan(0);
			const lastBody = configPuts[configPuts.length - 1].postDataJSON() as { metrics?: unknown[] };
			expect(activeMetricIds(lastBody.metrics as never)).toHaveLength(0);

			const trip = await fetchTrip(request, id);
			expect(activeMetricIds(trip.display_config?.metrics)).toHaveLength(0);
		} finally {
			await deleteTrip(request, id);
		}
	});

	// AC-5: normale Änderungen (Metrik zuschalten, Schwellwert ändern) speichern
	// weiterhin automatisch — das Absichts-Gate darf den legitimen Auto-Save
	// nicht mit-blockieren, es darf nur den ungewollten Leerungs-Autosave
	// verhindern (AC-1/AC-2/AC-6).
	test('AC-5: Metrik zuschalten UND Schwellwert ändern speichern automatisch, bleiben nach Reload erhalten', async ({
		page,
		request
	}) => {
		const id = tripId('ac5');
		// 'rain_probability' bewusst NICHT in der Seed-Auswahl — wird im Test
		// zugeschaltet. 'wind' ist aktiv und threshold-fähig.
		await createTrip(request, id, { metrics: seedMetrics(METRIC_IDS) });
		const puts = collectTripPuts(page, id);
		try {
			await page.goto(`/trips/${id}`);
			await page.getByTestId('trip-detail-tab-wetter').click();
			await expect(page.getByTestId('weather-metrics-tab')).toBeVisible();

			// 1) Bisher inaktive Metrik zuschalten.
			const rainToggle = page
				.locator('[data-testid="wm2-grundauswahl"] .toggle-btn')
				.filter({ hasText: 'Regenwahrscheinlichkeit' });
			await expect(rainToggle).toBeVisible();
			await expect(rainToggle).not.toHaveClass(/\bon\b/);
			await rainToggle.click();

			const [configPutResponse] = await Promise.all([
				page.waitForResponse(
					(r) => r.url().includes(`/api/trips/${id}/weather-config`) && r.request().method() === 'PUT',
					{ timeout: 10_000 }
				)
			]);
			expect(configPutResponse.ok()).toBeTruthy();

			// 2) Schwellwert einer threshold-fähigen, bereits aktiven Metrik ändern.
			const windRobustLevel = page.getByTestId('threshold-level-wind-robust');
			await expect(windRobustLevel).toBeVisible();
			const [thresholdPutResponse] = await Promise.all([
				page.waitForResponse(
					(r) => r.url().includes(`/api/trips/${id}/weather-config`) && r.request().method() === 'PUT',
					{ timeout: 10_000 }
				),
				windRobustLevel.click()
			]);
			expect(thresholdPutResponse.ok()).toBeTruthy();

			const configPuts = puts.filter((r) => r.url().includes('/weather-config'));
			expect(configPuts.length).toBeGreaterThanOrEqual(2);
			const lastBody = configPuts[configPuts.length - 1].postDataJSON() as {
				metrics?: Array<{ metric_id: string; enabled: boolean; sms_threshold?: number }>;
			};
			expect(activeMetricIds(lastBody.metrics as never)).toContain('rain_probability');
			const windEntry = (lastBody.metrics ?? []).find((m) => m.metric_id === 'wind');
			expect(windEntry?.sms_threshold).toBe(30);

			await page.reload();
			await page.getByTestId('trip-detail-tab-wetter').click();
			await expect(page.getByTestId('weather-metrics-tab')).toBeVisible();

			const trip = await fetchTrip(request, id);
			expect(activeMetricIds(trip.display_config?.metrics)).toContain('rain_probability');
			const persistedWind = (trip.display_config?.metrics ?? []).find(
				(m: { metric_id: string }) => m.metric_id === 'wind'
			);
			expect(persistedWind?.sms_threshold).toBe(30);
		} finally {
			await deleteTrip(request, id);
		}
	});

	// #3154 (#3122 B3b, Spec feat_3122_was_steht_wo.md Teil B Nr. 13/14): die E-Mail-Inhalt-Karte steht nicht mehr im
	// Reiter Zustellung; ihre Schalter (Etappen-Kennzahlen, Vortag-Vergleich, E-Mail-Format) bedient die Karte
	// „Was steht wo“ im Reiter Wetter, sie speichert jede Geste ohne Gesten-Gate (Teilfeld-PUT auf den Trip).
	//   #774-Regression (echter Klick speichert, ueberlebt Reload): Ersatz was-steht-wo-karte.spec.ts WS-4 (Trip).
	//   F004 programmatische Aktivierung (change ohne Pointer/Keydown speichert trotz Gesten-Gate): Wirkort ersatzlos
	//     entfallen — die Karte hat kein Gesten-Gate, jede Aenderung eines Schalters speichert.
	//   F004 Tastatur-Pfad und F003 Streuklick laufen an der Karte.
	test('F004 Tastatur-Pfad: Schalter der Karte per Tastatur (Fokus + Leertaste) speichert und bleibt nach Reload erhalten', async ({
		page,
		request
	}) => {
		const id = tripId('f004-tastatur');
		await createTrip(request, id, { metrics: [{ metric_id: 'temperature', enabled: true }, { metric_id: 'wind', enabled: true }] });
		try {
			let karte = await oeffneKarte(page, 'route', id);
			const sw = karte.getByTestId('was-steht-wo-show_stage_stats');
			await expect(sw).toHaveAttribute('aria-checked', 'true');
			const put = page.waitForResponse((r) => new URL(r.url()).pathname === `/api/trips/${id}` && r.request().method() === 'PUT', { timeout: 15_000 });
			await sw.focus();
			await page.keyboard.press('Space');
			expect((await put).ok()).toBeTruthy();
			expect((await fetchTrip(request, id)).report_config.show_stage_stats).toBe(false);
			await page.reload();
			karte = await oeffneKarte(page, 'route', id);
			await expect(karte.getByTestId('was-steht-wo-show_stage_stats')).toHaveAttribute('aria-checked', 'false');
		} finally {
			await deleteTrip(request, id);
		}
	});

	test('F003 Streuklick: Klick auf die Ueberschrift „Ganze Blöcke ein- und ausschalten“ loest keinen Speichervorgang aus', async ({
		page,
		request
	}) => {
		const id = tripId('f003-streuklick');
		await createTrip(request, id, { metrics: [{ metric_id: 'temperature', enabled: true }, { metric_id: 'wind', enabled: true }] });
		try {
			const karte = await oeffneKarte(page, 'route', id);
			const puts = collectTripPuts(page, id);
			await karte.getByText('Ganze Blöcke ein- und ausschalten').click();
			await karte.getByText('Etappen-Kennzahlen', { exact: true }).click();
			await page.waitForTimeout(2_000);
			expect(puts.length, 'F003 FAIL: ein Klick auf Text speichert').toBe(0);
		} finally {
			await deleteTrip(request, id);
		}
	});
});

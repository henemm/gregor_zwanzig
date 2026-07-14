// E2E (Staging) — Issue #1234: Auto-Save im Inhalt-Tab darf Metriken nicht
// stillschweigend leeren.
//
// Spec: docs/specs/modules/issue_1234_autosave_hydration_gate.md
//   § Test Plan, § Acceptance Criteria
// Kausalkette: docs/context/fix-1234-mount-autosave-metrics.md
//
// Nachweis über abgefangene Netzwerk-Requests (page.on('request') / page.route),
// nicht über Optik. Setup/Login-Muster analog compare-flow-navigation.spec.ts +
// playwright.1256-s2.staging.config.ts (storageState statt Login pro Test —
// vermeidet das Staging-Auth-Rate-Limit, #703).
//
// Ausführen (gegen Staging, aus frontend/):
//   set -a; source /home/hem/gregor_zwanzig/.claude/validator.env; set +a
//   npx playwright test --config=playwright.1234.staging.config.ts

import { test, expect, type Page, type Request, type APIRequestContext } from '@playwright/test';

const TRIP_PREFIX = 'e2e-1234';
const HORIZONS_ALL = { today: true, tomorrow: true, day_after: true };
const METRIC_IDS = ['temperature', 'wind', 'precipitation', 'wind_gust', 'uv_index'];

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
		const puts = collectTripPuts(page, id);
		try {
			await page.goto(`/trips/${id}`);
			await page.getByTestId('trip-detail-tab-weather').click();
			await expect(page.getByTestId('weather-metrics-tab')).toBeVisible();

			// > 700ms Debounce (saveStatusStore.svelte.ts schedule()).
			await page.waitForTimeout(3_000);
			await page.getByTestId('trip-detail-tab-stages').click();
			await page.waitForTimeout(500);

			expect(
				puts.map((p) => p.url()),
				'kein PUT auf /api/trips/{id} oder /api/trips/{id}/weather-config erwartet'
			).toHaveLength(0);

			const trip = await fetchTrip(request, id);
			expect(activeMetricIds(trip.display_config?.metrics).sort()).toEqual([...METRIC_IDS].sort());
			expect(trip.alert_rules).toHaveLength(1);
			expect(trip.alert_rules[0].metric).toBe('wind_gust');
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
			await page.getByTestId('trip-detail-tab-weather').click();

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
			await page.getByTestId('trip-detail-tab-weather').click();
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

	// Regressionsschutz #774 (Fix-Loop 1 / F001): das neue Absichts-Gate darf
	// nur die Normalisierungs-Rueckschreibung von EditReportConfigSection beim
	// Mounten blocken (AC-6), nicht einen echten Nutzerklick auf eine der
	// E-Mail-Inhalt-Checkboxen. Sonst waere AC-6 auf Kosten von #774 "gefixt".
	test('#774-Regression: echter Checkbox-Klick in der E-Mail-Inhalt-Karte speichert weiterhin und bleibt nach Reload erhalten', async ({
		page,
		request
	}) => {
		const id = tripId('reg774');
		await createTrip(request, id, { metrics: seedMetrics(METRIC_IDS) });
		try {
			await page.goto(`/trips/${id}`);
			await page.getByTestId('trip-detail-tab-weather').click();
			await expect(page.getByTestId('weather-metrics-tab')).toBeVisible();

			const checkbox = page.locator('[data-testid="report-show-outlook"] input[type="checkbox"]');
			await expect(checkbox).toBeVisible();
			const wasChecked = await checkbox.isChecked();

			// Der zweite PUT (Trip-Update mit report_config) — nicht der
			// weather-config-PUT — traegt die Checkbox-Aenderung.
			const [putResponse] = await Promise.all([
				page.waitForResponse(
					(r) =>
						r.url().includes(`/api/trips/${id}`) &&
						!r.url().includes('weather-config') &&
						r.request().method() === 'PUT',
					{ timeout: 10_000 }
				),
				checkbox.click()
			]);
			expect(putResponse.ok()).toBeTruthy();

			await page.reload();
			await page.getByTestId('trip-detail-tab-weather').click();
			await expect(page.getByTestId('weather-metrics-tab')).toBeVisible();
			const afterReload = page.locator('[data-testid="report-show-outlook"] input[type="checkbox"]');
			await expect(afterReload).toBeVisible();
			expect(await afterReload.isChecked()).toBe(!wasChecked);

			const trip = await fetchTrip(request, id);
			expect(trip.report_config?.show_outlook).toBe(!wasChecked);
		} finally {
			await deleteTrip(request, id);
		}
	});

	// Fix-Loop 2 / F004: Tastatur-Pfad. Checkbox per Tastatur fokussieren und mit
	// Leertaste umschalten — kein Maus-`pointerdown`, aber ein echtes `keydown`
	// UND ein `change`-Ereignis feuern. Muss weiterhin speichern.
	test('F004 Tastatur-Pfad: Checkbox per Tastatur (Fokus + Leertaste) speichert und bleibt nach Reload erhalten', async ({
		page,
		request
	}) => {
		const id = tripId('kbd');
		await createTrip(request, id, { metrics: seedMetrics(METRIC_IDS) });
		try {
			await page.goto(`/trips/${id}`);
			await page.getByTestId('trip-detail-tab-weather').click();
			await expect(page.getByTestId('weather-metrics-tab')).toBeVisible();

			const checkbox = page.locator('[data-testid="report-show-outlook"] input[type="checkbox"]');
			await expect(checkbox).toBeVisible();
			const wasChecked = await checkbox.isChecked();

			await checkbox.focus();
			const [putResponse] = await Promise.all([
				page.waitForResponse(
					(r) =>
						r.url().includes(`/api/trips/${id}`) &&
						!r.url().includes('weather-config') &&
						r.request().method() === 'PUT',
					{ timeout: 10_000 }
				),
				page.keyboard.press('Space')
			]);
			expect(putResponse.ok()).toBeTruthy();

			await page.reload();
			await page.getByTestId('trip-detail-tab-weather').click();
			await expect(page.getByTestId('weather-metrics-tab')).toBeVisible();
			const afterReload = page.locator('[data-testid="report-show-outlook"] input[type="checkbox"]');
			await expect(afterReload).toBeVisible();
			expect(await afterReload.isChecked()).toBe(!wasChecked);
		} finally {
			await deleteTrip(request, id);
		}
	});

	// Fix-Loop 2 / F004 (Kern-Nachweis): programmatische/AT-nahe Aktivierung ohne
	// jedes Maus- oder Tastatur-Ereignis auf dem Teilbaum — nur ein echtes
	// `change`-Ereignis auf der Checkbox (analog Screenreader-/AT-synthetisierter
	// Aktivierung). Ohne die change/input-Capture-Listener (F004-Fix) wuerde das
	// Absichts-Gate dies als "keine Nutzergeste" werten und die Aenderung still
	// verwerfen — genau das Loch, das dieser Test schliesst.
	test('F004 programmatische Aktivierung: change-Event ohne Pointerdown/Keydown speichert dennoch', async ({
		page,
		request
	}) => {
		const id = tripId('prog');
		await createTrip(request, id, { metrics: seedMetrics(METRIC_IDS) });
		try {
			await page.goto(`/trips/${id}`);
			await page.getByTestId('trip-detail-tab-weather').click();
			await expect(page.getByTestId('weather-metrics-tab')).toBeVisible();

			const checkbox = page.locator('[data-testid="report-show-outlook"] input[type="checkbox"]');
			await expect(checkbox).toBeVisible();
			const wasChecked = await checkbox.isChecked();

			const [putResponse] = await Promise.all([
				page.waitForResponse(
					(r) =>
						r.url().includes(`/api/trips/${id}`) &&
						!r.url().includes('weather-config') &&
						r.request().method() === 'PUT',
					{ timeout: 10_000 }
				),
				checkbox.evaluate((el: HTMLInputElement) => {
					// Kein Playwright-Pointer-/Tastatur-Event — nur der reine
					// DOM-Vorgang, den eine echte Wertaenderung ausloest.
					el.checked = !el.checked;
					el.dispatchEvent(new Event('change', { bubbles: true }));
				})
			]);
			expect(putResponse.ok()).toBeTruthy();

			await page.reload();
			await page.getByTestId('trip-detail-tab-weather').click();
			await expect(page.getByTestId('weather-metrics-tab')).toBeVisible();
			const afterReload = page.locator('[data-testid="report-show-outlook"] input[type="checkbox"]');
			await expect(afterReload).toBeVisible();
			expect(await afterReload.isChecked()).toBe(!wasChecked);
		} finally {
			await deleteTrip(request, id);
		}
	});

	// Fix-Loop 2 / F003: Streuklick auf die Überschrift "E-Mail-Inhalt" (kein
	// Bedienelement, kein Label-Kind) darf das Gate NICHT entwaffnen — sonst
	// wuerde ein einziger Klick fuer den Rest der Sitzung jede echte
	// Nutzeraenderung faelschlich als "Geste bereits vorhanden" durchwinken.
	test('F003 Streuklick: Klick auf Überschrift "E-Mail-Inhalt" löst keinen Speichervorgang aus', async ({
		page,
		request
	}) => {
		const id = tripId('stray');
		await createTrip(request, id, { metrics: seedMetrics(METRIC_IDS) });
		const puts = collectTripPuts(page, id);
		try {
			await page.goto(`/trips/${id}`);
			await page.getByTestId('trip-detail-tab-weather').click();
			await expect(page.getByTestId('weather-metrics-tab')).toBeVisible();

			await page.locator('[data-testid="report-mail-content"] h3', { hasText: 'E-Mail-Inhalt' }).click();
			await page.waitForTimeout(1_500);

			expect(
				puts.map((p) => p.url()),
				'Streuklick auf die Überschrift darf keinen PUT auslösen'
			).toHaveLength(0);
		} finally {
			await deleteTrip(request, id);
		}
	});
});

// TDD RED: Issue #774 — „Metriken-Überblick"-Checkbox wird nicht gespeichert + Einklapp-Element entfernen.
//
// Spec: docs/specs/bugfix/issue_774_metrics_summary_persist.md
// Workflow: bug-774-metriken-checkbox
//
// Ziel-Oberfläche: Trip-Detail, Reiter „Inhalt" (?tab=weather → WeatherMetricsTab),
// E-Mail-Inhalt-Karte (EditReportConfigSection, showMailContent=true).
//
// Diese E2E laufen als Verhaltensnachweis gegen die Remote-Staging-Umgebung
// (staging.gregor20.henemm.com). Lokal zeigt der SvelteKit-/api-Proxy per Default
// auf die Produktions-API — daher NICHT lokal gegen Prod fahren.
//
// RED (gegen aktuellen Staging-Stand), weil:
//   - AC-1: handleSave() im „Inhalt"-Reiter sendet KEIN report_config; zudem ignoriert
//           isDirty den reportConfig → der Speichern-Button bleibt deaktiviert.
//           → show_metrics_summary überlebt den Reload NICHT.
//   - AC-2: das „Inhalts-Bausteine (N aktiv)"-Einklapp-Element existiert noch
//           (data-testid="report-content-modules-toggle").
//   - AC-3: report_config wird im „Inhalt"-Reiter gar nicht persistiert.

import { test, expect } from '@playwright/test';
import type { APIRequestContext, Page } from '@playwright/test';

const TRIP_PREFIX = 'e2e-774';

function tripId(suffix: string) {
	return `${TRIP_PREFIX}-${suffix}`;
}

async function createTrip(
	request: APIRequestContext,
	id: string,
	report_config: Record<string, unknown> = { enabled: true, morning_time: '07:00', evening_time: '18:00' },
) {
	const res = await request.post('/api/trips', {
		data: {
			id,
			name: `Issue 774 ${id}`,
			stages: [
				{
					id: `${id}-s1`,
					name: 'Etappe',
					date: new Date().toISOString().slice(0, 10),
					waypoints: [
						{ id: `${id}-w1`, name: 'Start', lat: 46.5, lon: 8.1, elevation_m: 1800 },
						{ id: `${id}-w2`, name: 'Gipfel', lat: 46.6, lon: 8.2, elevation_m: 2400 },
					],
				},
			],
			report_config,
			alert_rules: [],
		},
	});
	expect([200, 201]).toContain(res.status());
}

async function deleteTrip(request: APIRequestContext, id: string) {
	await request.delete(`/api/trips/${id}`).catch(() => {});
}

// „Inhalt"-Reiter öffnen und auf die E-Mail-Inhalt-Karte warten.
async function openInhaltTab(page: Page, id: string) {
	await page.goto(`/trips/${id}?tab=weather`);
	await page.locator('[data-testid="weather-metrics-tab"]').waitFor({ state: 'visible', timeout: 15_000 });
	await page
		.locator('[data-testid="report-show-metrics-summary"] input[type="checkbox"]')
		.waitFor({ state: 'visible', timeout: 15_000 });
}

const metricsSummaryCheckbox = (page: Page) =>
	page.locator('[data-testid="report-show-metrics-summary"] input[type="checkbox"]');

test.describe('Issue #774: Metriken-Überblick Checkbox-Persistenz + Einklapp-Element', () => {
	// ── AC-1: Häkchen setzen → speichern → Reload → bleibt gesetzt ─────────────
	test('AC-1: „Metriken-Überblick" wird gespeichert und überlebt den Reload', async ({ page, request }) => {
		const id = tripId('ac1');
		// report_config OHNE show_metrics_summary (Default false).
		await createTrip(request, id);
		try {
			await openInhaltTab(page, id);

			const cb = metricsSummaryCheckbox(page);
			await expect(cb).not.toBeChecked();

			// Häkchen setzen.
			await cb.check();
			await expect(cb).toBeChecked();

			// Der „Speichern"-Button muss durch die report_config-Änderung aktiv werden.
			const saveBtn = page.locator('[data-testid="weather-metrics-tab-save"]');
			await expect(saveBtn).toBeEnabled();

			// Speichern → der Trip-PUT (report_config) muss erfolgen.
			const putResponsePromise = page.waitForResponse(
				(r) => r.url().endsWith(`/api/trips/${id}`) && r.request().method() === 'PUT' && r.ok(),
				{ timeout: 15_000 },
			);
			await saveBtn.click();
			await putResponsePromise;

			// Persistiert via API.
			const after = await request.get(`/api/trips/${id}`);
			expect(after.ok()).toBe(true);
			const rc = (await after.json()).report_config;
			expect(rc.show_metrics_summary, 'show_metrics_summary muss persistiert sein').toBe(true);

			// Und: nach echtem Reload ist die Checkbox weiterhin gesetzt.
			await openInhaltTab(page, id);
			await expect(metricsSummaryCheckbox(page)).toBeChecked();
		} finally {
			await deleteTrip(request, id);
		}
	});

	// ── AC-2: Einklapp-Element entfernt, Checkboxen direkt sichtbar ────────────
	test('AC-2: kein „Inhalts-Bausteine"-Einklapp-Element, Checkboxen direkt sichtbar', async ({
		page,
		request,
	}) => {
		const id = tripId('ac2');
		await createTrip(request, id);
		try {
			await page.goto(`/trips/${id}?tab=weather`);
			await page.locator('[data-testid="weather-metrics-tab"]').waitFor({ state: 'visible', timeout: 15_000 });

			// Das Einklapp-Element darf NICHT mehr existieren.
			await expect(page.locator('[data-testid="report-content-modules-toggle"]')).toHaveCount(0);

			// Die drei Inhalts-Checkboxen sind OHNE vorheriges Aufklappen sichtbar.
			await expect(metricsSummaryCheckbox(page)).toBeVisible();
			await expect(
				page.locator('[data-testid="report-show-outlook"] input[type="checkbox"]'),
			).toBeVisible();
			await expect(
				page.locator('[data-testid="report-show-stage-stats"] input[type="checkbox"]'),
			).toBeVisible();
		} finally {
			await deleteTrip(request, id);
		}
	});

	// ── AC-3: Wetter-Metriken (display_config) bleiben beim report_config-Save erhalten ─
	test('AC-3: vorhandene Wetter-Metriken bleiben nach dem Checkbox-Save unverändert', async ({
		page,
		request,
	}) => {
		const id = tripId('ac3');
		await createTrip(request, id);
		try {
			// Vorzustand der display_config (Wetter-Metriken) festhalten.
			const before = await request.get(`/api/trips/${id}`);
			const dcBefore = JSON.stringify((await before.json()).display_config ?? null);

			await openInhaltTab(page, id);

			// NUR die report_config-Checkbox ändern, dann speichern.
			await metricsSummaryCheckbox(page).check();
			const saveBtn = page.locator('[data-testid="weather-metrics-tab-save"]');
			await expect(saveBtn).toBeEnabled();
			const putResponsePromise = page.waitForResponse(
				(r) => r.url().endsWith(`/api/trips/${id}`) && r.request().method() === 'PUT' && r.ok(),
				{ timeout: 15_000 },
			);
			await saveBtn.click();
			await putResponsePromise;

			// display_config (Wetter-Metriken) unverändert.
			const after = await request.get(`/api/trips/${id}`);
			const dcAfter = JSON.stringify((await after.json()).display_config ?? null);
			expect(dcAfter, 'display_config darf durch report_config-Save nicht verloren gehen').toBe(dcBefore);
		} finally {
			await deleteTrip(request, id);
		}
	});
});

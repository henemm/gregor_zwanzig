// E2E-Tests für Issue #723 — E-Mail-Inhalt-Tab UI eindampfen (Slice 3 von #709).
//
// Spec: docs/specs/modules/issue_723_email_tab_eindampfen.md
// Workflow: issue-723-email-tab-eindampfen
//
// Ziel-Oberfläche: Edit-Seite /trips/[id]/edit, Reports-Tab
// (EditReportConfigSection.svelte). Der E-Mail-Inhalt-Bereich wird auf
// Format-Schalter + GENAU 3 Inhalts-Bausteine reduziert.
//
// Verbleibende TestIDs:
//   report-email-format-full / report-email-format-compact  — Format-Schalter (#722)
//   report-show-metrics-summary                             — Baustein Metriken-Überblick
//   report-show-outlook                                     — Baustein Ausblick (NEU, #721)
//   report-show-stage-stats                                 — Baustein Etappen-Kennzahlen
//
// Entfernte TestIDs (dürfen NICHT mehr im DOM sein):
//   report-show-quick-take, report-show-stability, report-show-highlights,
//   daily-summary-metric-*, report-daily-summary-toggle, report-show-daylight,
//   report-wind-exposition, report-compact-summary, report-show-advanced
//
// Diese Tests sind RED bis die UI eingedampft ist. Cleanup inline (DELETE).

import { test, expect } from '@playwright/test';
import { login } from './helpers.js';

const TRIP_PREFIX = 'e2e-issue-723';

function tripId(suffix: string) {
	return `${TRIP_PREFIX}-${suffix}`;
}

async function createTrip(
	request: import('@playwright/test').APIRequestContext,
	id: string,
	report_config: Record<string, unknown> = { enabled: true, morning_time: '07:00', evening_time: '18:00' }
) {
	const res = await request.post('/api/trips', {
		data: {
			id,
			name: `Issue 723 ${id}`,
			stages: [
				{
					id: `${id}-stage-1`,
					name: 'Etappe',
					date: new Date().toISOString().slice(0, 10),
					waypoints: [
						{ id: `${id}-wp-1`, name: 'Start', lat: 42.1, lon: 9.0, elevation_m: 500 },
						{ id: `${id}-wp-2`, name: 'Ziel', lat: 42.2, lon: 9.1, elevation_m: 900 }
					]
				}
			],
			report_config,
			alert_rules: []
		}
	});
	expect([200, 201]).toContain(res.status());
}

async function deleteTrip(
	request: import('@playwright/test').APIRequestContext,
	id: string
) {
	const res = await request.delete(`/api/trips/${id}`);
	expect([200, 204, 404]).toContain(res.status());
}

async function openReportsSection(page: import('@playwright/test').Page, id: string) {
	await page.goto(`/trips/${id}/edit`);
	await page.locator('[data-testid="edit-tab-reports"]').click();
	await page.locator('[data-testid="report-mail-content"]').waitFor({ state: 'visible' });
}

const REMOVED_TESTIDS = [
	'report-show-quick-take',
	'report-show-stability',
	'report-show-highlights',
	'report-daily-summary-toggle',
	'report-show-daylight',
	'report-wind-exposition',
	'report-compact-summary',
	'report-show-advanced'
];

test.describe('Issue #723: E-Mail-Inhalt-Tab eingedampft', () => {
	test.beforeEach(async ({ page }) => {
		await login(page);
	});

	// ── AC-1: Format-Schalter + genau 3 Bausteine, entfernte Optionen weg ──────
	test('AC-1: Format-Schalter + 3 Bausteine sichtbar, alte Optionen nicht im DOM', async ({
		page,
		request
	}) => {
		const id = tripId('ac1');
		await createTrip(request, id);
		try {
			await openReportsSection(page, id);

			// Format-Schalter (#722)
			await expect(page.locator('[data-testid="report-email-format-full"]')).toBeVisible();
			await expect(page.locator('[data-testid="report-email-format-compact"]')).toBeVisible();

			// Genau 3 Bausteine
			await expect(
				page.locator('[data-testid="report-show-metrics-summary"] input[type="checkbox"]')
			).toBeVisible();
			await expect(
				page.locator('[data-testid="report-show-outlook"] input[type="checkbox"]')
			).toBeVisible();
			await expect(
				page.locator('[data-testid="report-show-stage-stats"] input[type="checkbox"]')
			).toBeVisible();

			// Entfernte Optionen NICHT mehr im DOM
			for (const tid of REMOVED_TESTIDS) {
				await expect(page.locator(`[data-testid="${tid}"]`)).toHaveCount(0);
			}
			// keine Tages-Summe-Metrik-Checkboxen mehr
			await expect(page.locator('[data-testid^="daily-summary-metric-"]')).toHaveCount(0);
		} finally {
			await deleteTrip(request, id);
		}
	});

	// ── AC-3: fehlendes show_outlook → Checkbox initial AN (Default true) ───────
	test('AC-3: Trip ohne show_outlook → Ausblick-Checkbox ist angehakt', async ({
		page,
		request
	}) => {
		const id = tripId('ac3');
		// report_config OHNE show_outlook
		await createTrip(request, id, {
			enabled: true,
			morning_time: '07:00',
			evening_time: '18:00'
		});
		try {
			await openReportsSection(page, id);
			await expect(
				page.locator('[data-testid="report-show-outlook"] input[type="checkbox"]')
			).toBeChecked();
		} finally {
			await deleteTrip(request, id);
		}
	});

	// ── AC-4: Kompakt-Modus deaktiviert alle 3 Bausteine ───────────────────────
	test('AC-4: Format=Kompakt → 3 Bausteine disabled', async ({ page, request }) => {
		const id = tripId('ac4');
		await createTrip(request, id, {
			enabled: true,
			morning_time: '07:00',
			evening_time: '18:00',
			email_format: 'full'
		});
		try {
			await openReportsSection(page, id);

			await page.locator('[data-testid="report-email-format-compact"]').check();

			await expect(
				page.locator('[data-testid="report-show-metrics-summary"] input[type="checkbox"]')
			).toBeDisabled();
			await expect(
				page.locator('[data-testid="report-show-outlook"] input[type="checkbox"]')
			).toBeDisabled();
			await expect(
				page.locator('[data-testid="report-show-stage-stats"] input[type="checkbox"]')
			).toBeDisabled();
		} finally {
			await deleteTrip(request, id);
		}
	});

	// ── AC-5: Ausblick umschalten, speichern, persistiert über Reload ──────────
	test('AC-5: show_outlook abwählen wird gespeichert und überlebt Reload', async ({
		page,
		request
	}) => {
		const id = tripId('ac5');
		await createTrip(request, id, {
			enabled: true,
			morning_time: '07:00',
			evening_time: '18:00',
			show_outlook: true
		});
		try {
			await openReportsSection(page, id);

			// Ausblick abwählen
			await page.locator('[data-testid="report-show-outlook"] input[type="checkbox"]').click();

			const putPromise = page.waitForRequest(
				(req) => req.method() === 'PUT' && req.url().endsWith(`/api/trips/${id}`)
			);
			await page.locator('[data-testid="edit-save-btn"]').click();
			const putReq = await putPromise;
			const body = JSON.parse(putReq.postData() || '{}');
			expect(body.report_config.show_outlook).toBe(false);

			await page.waitForURL('/trips', { timeout: 5000 });

			// Persistiert via API
			const after = await request.get(`/api/trips/${id}`);
			expect(after.ok()).toBe(true);
			const rc = (await after.json()).report_config;
			expect(rc.show_outlook).toBe(false);
		} finally {
			await deleteTrip(request, id);
		}
	});

	// ── AC-2: Bestandsdaten entfernter Felder bleiben nach Save erhalten ────────
	test('AC-2: aus dem UI entfernte Felder bleiben nach Speichern erhalten', async ({
		page,
		request
	}) => {
		const id = tripId('ac2');
		await createTrip(request, id, {
			enabled: true,
			morning_time: '07:00',
			evening_time: '18:00',
			// Felder, die das neue UI nicht mehr anbietet:
			show_quick_take_tags: true,
			show_highlights: true,
			show_daylight: false,
			daily_summary_metrics: ['temperature'],
			wind_exposition_min_elevation_m: 1234,
			custom_unknown_field: 'preserve-me'
		});
		try {
			await openReportsSection(page, id);

			// Einen verbleibenden Baustein ändern, dann speichern
			await page.locator('[data-testid="report-show-stage-stats"] input[type="checkbox"]').click();
			await page.locator('[data-testid="edit-save-btn"]').click();
			await page.waitForURL('/trips', { timeout: 5000 });

			const after = await request.get(`/api/trips/${id}`);
			expect(after.ok()).toBe(true);
			const rc = (await after.json()).report_config;
			// Entfernte Felder unverändert erhalten:
			expect(rc.show_quick_take_tags).toBe(true);
			expect(rc.show_highlights).toBe(true);
			expect(rc.show_daylight).toBe(false);
			expect(rc.daily_summary_metrics).toContain('temperature');
			expect(rc.wind_exposition_min_elevation_m).toBe(1234);
			expect(rc.custom_unknown_field).toBe('preserve-me');
		} finally {
			await deleteTrip(request, id);
		}
	});
});

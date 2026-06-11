// E2E-Tests für Issue #619 — Auswahl-/Schalter-UI für E-Mail-Elemente.
//
// Spec: docs/specs/modules/issue_619_mail_elements_ui.md
// Workflow: issue-619-mail-elements-ui
//
// Ziel-Oberfläche: Edit-Seite /trips/[id]/edit, Sektion "reports"
// (EditReportConfigSection.svelte — kanonischer Report-Editor, #88).
//
// Erwartete neue TestIDs (aus der Spec):
//   report-mail-content               — Container des neuen Abschnitts
//   report-show-stage-stats           — Schalter Etappen-Kennzahlen
//   report-show-quick-take            — Schalter Quick-Take-Chips
//   report-show-stability             — Schalter Großwetterlage
//   report-show-highlights            — Schalter Zusammenfassung
//   daily-summary-metric-precipitation / -wind / -visibility / -thunder / -temperature
//
// Diese Tests sind RED bis die UI existiert. Cleanup inline (DELETE).

import { test, expect } from '@playwright/test';
import { login } from './helpers.js';

const TRIP_PREFIX = 'e2e-issue-619';

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
			name: `Issue 619 ${id}`,
			stages: [
				{
					id: `${id}-stage-1`,
					name: 'Etappe',
					date: new Date().toISOString().slice(0, 10),
					waypoints: [{ id: `${id}-wp-1`, name: 'Start', lat: 42.1, lon: 9.0, elevation_m: 500 }]
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
	// Editor nutzt einen Tab-Editor (TripEditView.svelte), nicht ein Accordion:
	// Reports-Tab via data-testid="edit-tab-reports" aktivieren.
	await page.locator('[data-testid="edit-tab-reports"]').click();
	await page.locator('[data-testid="report-mail-content"]').waitFor({ state: 'visible' });
}

test.describe('Issue #619: E-Mail-Elemente konfigurierbar', () => {
	test.beforeEach(async ({ page }) => {
		await login(page);
	});

	// ── AC-1: Drei verbleibende Bausteine + Ausblick sichtbar (Issue #723) ────────
	test('AC-1: Drei Bausteine (Metriken-Überblick/Ausblick/Etappen-Kennzahlen) sichtbar', async ({
		page,
		request
	}) => {
		const id = tripId('ac1');
		await createTrip(request, id, {
			enabled: true,
			morning_time: '07:00',
			evening_time: '18:00',
			show_stage_stats: true,
			show_metrics_summary: false,
			show_outlook: true
		});
		try {
			await openReportsSection(page, id);

			const stageStats = page.locator('[data-testid="report-show-stage-stats"] input[type="checkbox"]');
			const metricsSummary = page.locator('[data-testid="report-show-metrics-summary"] input[type="checkbox"]');
			const outlook = page.locator('[data-testid="report-show-outlook"] input[type="checkbox"]');

			await expect(stageStats).toBeVisible();
			await expect(metricsSummary).toBeVisible();
			await expect(outlook).toBeVisible();

			// Spiegeln den gespeicherten Stand
			await expect(stageStats).toBeChecked();
			await expect(metricsSummary).not.toBeChecked();
			await expect(outlook).toBeChecked();

			// Entfernte Optionen nicht mehr im DOM
			await expect(page.locator('[data-testid="report-show-quick-take"]')).toHaveCount(0);
			await expect(page.locator('[data-testid="report-show-stability"]')).toHaveCount(0);
			await expect(page.locator('[data-testid="report-show-highlights"]')).toHaveCount(0);
		} finally {
			await deleteTrip(request, id);
		}
	});

	// ── AC-2: Tages-Summe-Metriken entfernt aus UI (Issue #723) ────────────────
	// Kein UI-Test für daily_summary_metrics mehr (kein DOM-Zugang).
	// Persistence-Test: Feld bleibt nach Save via Spread-Beibehaltung erhalten.
	test('AC-2: daily_summary_metrics bleiben nach Save erhalten (Bestandsdaten-Schutz)', async ({
		page,
		request
	}) => {
		const id = tripId('ac2');
		await createTrip(request, id, {
			enabled: true,
			morning_time: '07:00',
			evening_time: '18:00',
			daily_summary_metrics: ['precipitation', 'thunder']
		});
		try {
			await openReportsSection(page, id);

			// show_stage_stats ändern (verbleibender Baustein) und speichern
			await page.locator('[data-testid="report-show-stage-stats"] input[type="checkbox"]').click();
			await page.locator('[data-testid="edit-save-btn"]').click();
			await page.waitForURL('/trips', { timeout: 5000 });

			const after = await request.get(`/api/trips/${id}`);
			expect(after.ok()).toBe(true);
			const rc = (await after.json()).report_config;
			// daily_summary_metrics via Spread unverändert erhalten
			expect([...rc.daily_summary_metrics].sort()).toEqual(['precipitation', 'thunder'].sort());
		} finally {
			await deleteTrip(request, id);
		}
	});

	// ── AC-3: show_outlook umschalten + speichern + persistiert ────────────────
	test('AC-3: Ausblick-Schalter ändern, speichern, persistiert', async ({
		page,
		request
	}) => {
		const id = tripId('ac3');
		await createTrip(request, id, {
			enabled: true,
			morning_time: '07:00',
			evening_time: '18:00',
			show_outlook: true
		});
		try {
			await openReportsSection(page, id);

			// Ausblick AUS
			await page.locator('[data-testid="report-show-outlook"] input[type="checkbox"]').click();

			const putPromise = page.waitForRequest(
				(req) => req.method() === 'PUT' && req.url().endsWith(`/api/trips/${id}`)
			);
			await page.locator('[data-testid="edit-save-btn"]').click();
			const putReq = await putPromise;
			const body = JSON.parse(putReq.postData() || '{}');

			expect(body.report_config.show_outlook).toBe(false);

			await page.waitForURL('/trips', { timeout: 5000 });

			// Reload via API: persistiert
			const after = await request.get(`/api/trips/${id}`);
			expect(after.ok()).toBe(true);
			const rc = (await after.json()).report_config;
			expect(rc.show_outlook).toBe(false);
		} finally {
			await deleteTrip(request, id);
		}
	});

	// ── AC-4: Read-Modify-Write — Fremdfelder bleiben erhalten ─────────────────
	test('AC-4: Unbekannte report_config-Felder bleiben nach Save erhalten', async ({
		page,
		request
	}) => {
		const id = tripId('ac4');
		await createTrip(request, id, {
			enabled: true,
			morning_time: '07:00',
			evening_time: '18:00',
			custom_unknown_field: 'preserve-me',
			change_threshold_temp_c: 5.0,
			change_threshold_wind_kmh: 20.0
		});
		try {
			await openReportsSection(page, id);

			// show_outlook ändern (verbleibender Baustein), dann speichern
			await page.locator('[data-testid="report-show-outlook"] input[type="checkbox"]').click();
			await page.locator('[data-testid="edit-save-btn"]').click();
			await page.waitForURL('/trips', { timeout: 5000 });

			const after = await request.get(`/api/trips/${id}`);
			expect(after.ok()).toBe(true);
			const rc = (await after.json()).report_config;
			expect(rc.custom_unknown_field).toBe('preserve-me');
			expect(rc.change_threshold_temp_c).toBe(5.0);
			expect(rc.change_threshold_wind_kmh).toBe(20.0);
		} finally {
			await deleteTrip(request, id);
		}
	});

	// ── AC-5: show_metrics_summary persistiert exakt ──────────────────────────
	test('AC-5: show_metrics_summary=true wird exakt gespeichert', async ({
		page,
		request
	}) => {
		const id = tripId('ac5');
		await createTrip(request, id, {
			enabled: true,
			morning_time: '07:00',
			evening_time: '18:00',
			show_metrics_summary: false
		});
		try {
			await openReportsSection(page, id);

			// Metriken-Überblick AN
			await page.locator('[data-testid="report-show-metrics-summary"] input[type="checkbox"]').click();

			await page.locator('[data-testid="edit-save-btn"]').click();
			await page.waitForURL('/trips', { timeout: 5000 });

			const after = await request.get(`/api/trips/${id}`);
			const rc = (await after.json()).report_config;
			expect(rc.show_metrics_summary).toBe(true);
		} finally {
			await deleteTrip(request, id);
		}
	});
});

// E2E-Tests für Issue #619 — Auswahl-/Schalter-UI für E-Mail-Elemente.
//
// Spec: docs/specs/modules/issue_619_mail_elements_ui.md
// Workflow: issue-619-mail-elements-ui
//
// Ziel-Oberfläche (migriert durch Fix #1047, docs/specs/modules/fix_1047_mail_content_tab_restore.md):
// Trip-Detail-Seite /trips/[id]?tab=weather, Reiter "Wetter-Metriken" (= "Inhalt",
// EditReportConfigSection.svelte eingebunden über WeatherMetricsTab.svelte). Der
// Reiter "Briefing-Zeitplan" (?tab=briefings) zeigt die Karte seit #736 bewusst NICHT
// mehr (Kanal-/Zeitplan-Reiter); zwischenzeitlich (#942) fehlte sie versehentlich auch
// im Wetter-Metriken-Reiter — Fix #1047 stellt sie dort wieder her.
//
// Aktuelle TestIDs (nach #664/#722/#785 — "Metriken-Überblick"-Checkbox seit #971/#774
// entfernt, `report-show-metrics-summary` existiert NICHT mehr im DOM):
//   report-mail-content               — Container des Abschnitts
//   report-show-outlook               — Schalter Ausblick
//   report-show-stage-stats           — Schalter Etappen-Kennzahlen
//   report-show-yesterday-comparison  — Schalter Vortagesvergleich (#785)
//   report-email-format-full / -compact — Format-Schalter (#722)

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
	// Fix #1047: Reiter "Wetter-Metriken" (?tab=weather), nicht mehr "Briefing-Zeitplan".
	await page.goto(`/trips/${id}?tab=weather`);
	await page.locator('[data-testid="weather-metrics-tab"]').waitFor({ state: 'visible' });
	await page.locator('[data-testid="report-mail-content"]').waitFor({ state: 'visible' });
}

test.describe('Issue #619: E-Mail-Elemente konfigurierbar', () => {
	test.beforeEach(async ({ page }) => {
		await login(page);
	});

	// ── AC-1: Drei verbleibende Bausteine + Ausblick sichtbar (Issue #723) ────────
	// Fix #1047: "Metriken-Überblick" (report-show-metrics-summary) hat seit #971/#774
	// keine UI-Checkbox mehr — ersetzt durch report-show-yesterday-comparison (#785).
	test('AC-1: Drei Bausteine (Ausblick/Etappen-Kennzahlen/Vortagesvergleich) sichtbar', async ({
		page,
		request
	}) => {
		const id = tripId('ac1');
		await createTrip(request, id, {
			enabled: true,
			morning_time: '07:00',
			evening_time: '18:00',
			show_stage_stats: true,
			show_outlook: true,
			show_yesterday_comparison: false
		});
		try {
			await openReportsSection(page, id);

			const stageStats = page.locator('[data-testid="report-show-stage-stats"] input[type="checkbox"]');
			const outlook = page.locator('[data-testid="report-show-outlook"] input[type="checkbox"]');
			const yesterdayComparison = page.locator('[data-testid="report-show-yesterday-comparison"] input[type="checkbox"]');

			await expect(stageStats).toBeVisible();
			await expect(outlook).toBeVisible();
			await expect(yesterdayComparison).toBeVisible();

			// Spiegeln den gespeicherten Stand
			await expect(stageStats).toBeChecked();
			await expect(outlook).toBeChecked();
			await expect(yesterdayComparison).not.toBeChecked();

			// Entfernte Optionen nicht mehr im DOM
			await expect(page.locator('[data-testid="report-show-quick-take"]')).toHaveCount(0);
			await expect(page.locator('[data-testid="report-show-stability"]')).toHaveCount(0);
			await expect(page.locator('[data-testid="report-show-highlights"]')).toHaveCount(0);
			await expect(page.locator('[data-testid="report-show-metrics-summary"]')).toHaveCount(0);
		} finally {
			await deleteTrip(request, id);
		}
	});

	// ── Fix #1047 AC-2: Zeitplan-Karten NICHT im Wetter-Metriken-Reiter (#942-Regressionsschutz) ──
	test('Fix #1047 AC-2: Morgen-/Abend-Report-Zeitplan im Wetter-Metriken-Reiter nicht sichtbar', async ({
		page,
		request
	}) => {
		const id = tripId('fix1047-ac2');
		await createTrip(request, id);
		try {
			await openReportsSection(page, id);

			await expect(page.locator('[data-testid="morning-master-switch"]')).toHaveCount(0);
			await expect(page.locator('[data-testid="evening-master-switch"]')).toHaveCount(0);
		} finally {
			await deleteTrip(request, id);
		}
	});

	// ── Fix #1047 AC-3: Mail-Inhalt-Karte bleibt im Versand-Reiter unsichtbar (unverändert) ──
	test('Fix #1047 AC-3: E-Mail-Inhalt-Karte auf ?tab=briefings weiterhin nicht im DOM', async ({
		page,
		request
	}) => {
		const id = tripId('fix1047-ac3');
		await createTrip(request, id);
		try {
			await page.goto(`/trips/${id}?tab=briefings`);
			// Kanal-Checkbox ist im Versand-Reiter unconditional gerendert (Ready-Marker,
			// da die Live-Route immer per Auto-Save läuft — kein Save-Button vorhanden).
			await page.locator('[data-testid="channel-email"]').waitFor({ state: 'visible' });
			await expect(page.locator('[data-testid="report-mail-content"]')).toHaveCount(0);
		} finally {
			await deleteTrip(request, id);
		}
	});

	// Fix #1047 AC-5 (Anlege-Assistent zeigt Karte nicht doppelt, #934-Regressionsschutz):
	// bewusst NICHT als automatisierter E2E-Test umgesetzt. Der Freischalt-Fluss des
	// Wetter-Metriken-Wizard-Schritts (GPX-Upload pro Etappe, `unlocked`-Ableitung) ist
	// eigenständig fragil und unabhängig von diesem Fix. Da der Fix lediglich den bereits
	// vor #942 vorhandenen `{#if !createMode}`-Schutz unverändert wiederverwendet (kein
	// neues Risiko), wird AC-5 stattdessen manuell in Phase 6 (Validierung) durchgeklickt.

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

			// show_stage_stats ändern (verbleibender Baustein) — Wetter-Metriken-Reiter
			// speichert per Auto-Save (kein expliziter Button, siehe WeatherMetricsTab.svelte
			// $effect + scheduleAutoSave, 700ms Debounce).
			const putResponsePromise = page.waitForResponse(
				(r) => r.url().endsWith(`/api/trips/${id}`) && r.request().method() === 'PUT' && r.ok()
			);
			await page.locator('[data-testid="report-show-stage-stats"] input[type="checkbox"]').click();
			await putResponsePromise;

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

			// Ausblick AUS — Auto-Save (kein expliziter Button im Wetter-Metriken-Reiter)
			const putRequestPromise = page.waitForRequest(
				(req) => req.method() === 'PUT' && req.url().endsWith(`/api/trips/${id}`)
			);
			const putResponsePromise = page.waitForResponse(
				(r) => r.url().endsWith(`/api/trips/${id}`) && r.request().method() === 'PUT' && r.ok()
			);
			await page.locator('[data-testid="report-show-outlook"] input[type="checkbox"]').click();
			const putReq = await putRequestPromise;
			const body = JSON.parse(putReq.postData() || '{}');

			expect(body.report_config.show_outlook).toBe(false);

			await putResponsePromise;

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

			// show_outlook ändern (verbleibender Baustein) — Auto-Save
			const putResponsePromise = page.waitForResponse(
				(r) => r.url().endsWith(`/api/trips/${id}`) && r.request().method() === 'PUT' && r.ok()
			);
			await page.locator('[data-testid="report-show-outlook"] input[type="checkbox"]').click();
			await putResponsePromise;

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

	// ── AC-5 → Fix #1047 AC-6: show_metrics_summary bleibt Bestandsdaten-erhalten ──
	// show_metrics_summary hat seit #971/#774 kein UI-Element mehr (Checkbox entfernt,
	// Feld wird seit #790 im Mail-Renderer unconditional gerendert). Statt eines nicht
	// mehr möglichen UI-Klicks wird hier geprüft, dass das Feld beim Speichern eines
	// ANDEREN Bausteins unverändert erhalten bleibt (Read-Modify-Write-Beweis).
	test('Fix #1047 AC-6: show_metrics_summary bleibt nach Save eines anderen Bausteins erhalten', async ({
		page,
		request
	}) => {
		const id = tripId('ac5');
		await createTrip(request, id, {
			enabled: true,
			morning_time: '07:00',
			evening_time: '18:00',
			show_metrics_summary: true
		});
		try {
			await openReportsSection(page, id);

			// Kein UI-Element für show_metrics_summary mehr vorhanden.
			await expect(page.locator('[data-testid="report-show-metrics-summary"]')).toHaveCount(0);

			// Anderen Baustein ändern und per Auto-Save speichern.
			const putResponsePromise = page.waitForResponse(
				(r) => r.url().endsWith(`/api/trips/${id}`) && r.request().method() === 'PUT' && r.ok()
			);
			await page.locator('[data-testid="report-show-stage-stats"] input[type="checkbox"]').click();
			await putResponsePromise;

			const after = await request.get(`/api/trips/${id}`);
			const rc = (await after.json()).report_config;
			expect(rc.show_metrics_summary).toBe(true);
		} finally {
			await deleteTrip(request, id);
		}
	});
});

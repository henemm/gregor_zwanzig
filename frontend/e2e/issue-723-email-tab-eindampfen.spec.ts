// E2E-Tests für Issue #723 — E-Mail-Inhalt-Tab UI eindampfen (Slice 3 von #709).
//
// Spec: docs/specs/modules/issue_723_email_tab_eindampfen.md
// Workflow: issue-723-email-tab-eindampfen
//
// Ziel-Oberfläche (migriert durch Fix #1047, docs/specs/modules/fix_1047_mail_content_tab_restore.md):
// Trip-Detail-Seite /trips/[id]?tab=wetter-metriken, Reiter "Wetter-Metriken" (= "Inhalt",
// MailInhaltCard.svelte eingebunden über WeatherMetricsTab.svelte).
//
// Aktuelle TestIDs (nach #664/#722/#785 — "Metriken-Überblick"-Checkbox seit #971/#774
// entfernt, `report-show-metrics-summary` existiert NICHT mehr im DOM):
//   report-email-format-full / report-email-format-compact  — Format-Schalter (#722)
//   report-show-outlook                                     — Baustein Ausblick (#721)
//   report-show-stage-stats                                 — Baustein Etappen-Kennzahlen
//   report-show-yesterday-comparison                        — Baustein Vortagesvergleich (#785)
//
// Entfernte TestIDs (dürfen NICHT mehr im DOM sein):
//   report-show-quick-take, report-show-stability, report-show-highlights,
//   daily-summary-metric-*, report-daily-summary-toggle, report-show-daylight,
//   report-wind-exposition, report-compact-summary, report-show-advanced,
//   report-show-metrics-summary (#971/#774)
//
// #3154 (#3122 B3b, Spec feat_3122_was_steht_wo.md Teil B Nr. 14, AC-30): die Karte „E-Mail-Inhalt“ steht
// nicht mehr im Reiter Zustellung. E-Mail-Format, Etappen-Kennzahlen, Vortag-Vergleich und der
// 3-Tages-Ausblick (je Briefing) stehen genau einmal in der Karte „Was steht wo“ im Reiter Wetter; die Fälle
// laufen dort. Die Sperre der Bausteine im Kompakt-Format (alt AC-4) hat die Karte nicht — AC-4 prüft statt-
// dessen, dass das Kompakt-Format gespeichert wird und das Neuladen übersteht.

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

/** #3154: die Mail-Inhalte stehen in der Karte „Was steht wo“ im Reiter Wetter. */
async function openKarte(page: import('@playwright/test').Page, id: string) {
	await page.goto(`/trips/${id}?tab=wetter`);
	const karte = page.getByTestId('was-steht-wo');
	await karte.getByTestId('was-steht-wo-show_stage_stats').waitFor({ state: 'visible', timeout: 20_000 });
	return karte;
}

const REMOVED_TESTIDS = [
	'report-show-quick-take',
	'report-show-stability',
	'report-show-highlights',
	'report-daily-summary-toggle',
	'report-show-daylight',
	'report-wind-exposition',
	'report-compact-summary',
	'report-show-advanced',
	'report-show-metrics-summary'
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
			const karte = await openKarte(page, id);

			// Format-Schalter (#722), seit #3154 in der Karte
			await expect(karte.getByTestId('was-steht-wo-email-format-full')).toBeVisible();
			await expect(karte.getByTestId('was-steht-wo-email-format-compact')).toBeVisible();

			// Bausteine: Ausblick je Briefing, Etappen-Kennzahlen, Vortag-Vergleich
			for (const tid of ['was-steht-wo-ausblick-morning', 'was-steht-wo-ausblick-evening', 'was-steht-wo-show_stage_stats', 'was-steht-wo-show_yesterday_comparison']) {
				await expect(karte.getByTestId(tid)).toBeVisible();
			}
			await expect(page.locator('[data-testid="report-mail-content"], [data-testid="report-show-outlook"]')).toHaveCount(0);

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

	// ── AC-3: fehlendes show_outlook → Ausblick an ─────────────────────────────
	// #3154: in der Karte je Briefing; Vorbelegung „nur im Abend-Briefing“ (Spec Teil B, Kartentext).
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
			const karte = await openKarte(page, id);
			await expect(karte.getByTestId('was-steht-wo-ausblick-evening')).toHaveAttribute('aria-checked', 'true');
			await expect(karte.getByTestId('was-steht-wo-ausblick-morning')).toHaveAttribute('aria-checked', 'false');
		} finally {
			await deleteTrip(request, id);
		}
	});

	// ── AC-4: Kompakt-Format wird gespeichert (#3154: Karte, ohne Bausteinsperre) ─
	test('AC-4: Format=Kompakt wird gespeichert und überlebt Reload', async ({ page, request }) => {
		const id = tripId('ac4');
		await createTrip(request, id, {
			enabled: true,
			morning_time: '07:00',
			evening_time: '18:00',
			email_format: 'full'
		});
		try {
			const karte = await openKarte(page, id);
			const put = page.waitForResponse((r) => r.url().endsWith(`/api/trips/${id}`) && r.request().method() === 'PUT' && r.ok());
			await karte.getByTestId('was-steht-wo-email-format-compact').click();
			const body = (await put).request().postDataJSON();
			expect(body.report_config.email_format).toBe('compact');
			expect(((await (await request.get(`/api/trips/${id}`)).json()).report_config).email_format).toBe('compact');
			await page.reload();
			await expect((await openKarte(page, id)).getByTestId('was-steht-wo-email-format-compact')).toHaveAttribute('aria-checked', 'true');
		} finally {
			await deleteTrip(request, id);
		}
	});

	// ── AC-5: Ausblick umschalten, speichern, persistiert über Reload ──────────
	// #3154: Ausblick im Abend-Briefing in der Karte (`outlook_reports` der Tabelle); `show_outlook` bleibt.
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
			const karte = await openKarte(page, id);
			const abend = karte.getByTestId('was-steht-wo-ausblick-evening');
			await expect(abend).toHaveAttribute('aria-checked', 'true');
			const tabelle = page.waitForResponse(
				(r) => r.request().method() === 'PUT' && new URL(r.url()).pathname === `/api/briefings/${id}/placements` && r.ok()
			);
			await abend.click();
			await tabelle;

			// Persistiert via API und nach dem Neuladen
			const after = await request.get(`/api/trips/${id}`);
			expect(after.ok()).toBe(true);
			const trip = await after.json();
			expect(trip.display_config.placements.outlook_reports).not.toContain('evening');
			expect(trip.report_config.show_outlook).toBe(true);
			await page.reload();
			await expect((await openKarte(page, id)).getByTestId('was-steht-wo-ausblick-evening')).toHaveAttribute('aria-checked', 'false');
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
			// Einen Baustein in der Karte ändern — Auto-Save (#3154)
			const karte = await openKarte(page, id);
			const putResponsePromise = page.waitForResponse(
				(r) => r.url().endsWith(`/api/trips/${id}`) && r.request().method() === 'PUT' && r.ok()
			);
			await karte.getByTestId('was-steht-wo-show_stage_stats').click();
			await putResponsePromise;

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

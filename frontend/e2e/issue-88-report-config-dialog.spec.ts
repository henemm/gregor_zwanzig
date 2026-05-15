// E2E-Tests fuer Issue #88 — Dialog "Report Konfiguration" optimieren.
//
// Spec: docs/specs/modules/issue_88_report_config_dialog.md
// Workflow: issue-88-report-config-dialog (Phase 5: TDD RED)
//
// Pattern: Trip wird via API angelegt, danach Edit-Seite geprueft.
// Cleanup inline am Ende jedes Tests (DELETE /api/trips/<id>).
//
// Erwartete neue TestIDs aus der Spec:
//   morning-master-switch, evening-master-switch
//   report-morning-time, report-evening-time (existieren bereits)
//   report-morning-quickpick-07, report-evening-quickpick-18
//   report-morning-trend, report-evening-trend
//   channel-email, channel-signal, channel-telegram
//   channel-signal-hint, channel-telegram-hint
//
// Alle Threshold-Inputs (change_threshold_*) sind in der Komponente entfernt.

import { test, expect } from '@playwright/test';
import { login } from './helpers.js';

const TRIP_PREFIX = 'e2e-issue-88';

function tripId(suffix: string) {
	return `${TRIP_PREFIX}-${suffix}`;
}

async function createTrip(
	request: import('@playwright/test').APIRequestContext,
	id: string,
	opts: {
		report_config?: Record<string, unknown>;
		alert_rules?: unknown[];
	} = {}
) {
	const res = await request.post('/api/trips', {
		data: {
			id,
			name: `Issue 88 ${id}`,
			stages: [
				{
					id: `${id}-stage-1`,
					name: 'Etappe',
					date: new Date().toISOString().slice(0, 10),
					waypoints: [
						{ id: `${id}-wp-1`, name: 'Start', lat: 42.1, lon: 9.0, elevation_m: 500 }
					]
				}
			],
			report_config: opts.report_config ?? {
				enabled: true,
				morning_time: '07:00',
				evening_time: '18:00'
			},
			alert_rules: opts.alert_rules ?? []
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
	await page.locator('[data-testid="edit-section-reports-header"]').click();
}

test.describe('Issue #88: Report Config Dialog', () => {
	test.beforeEach(async ({ page }) => {
		await login(page);
	});

	// ----------------------------------------------------------------------------
	// AC-1: Zwei Sektionen (Morgen + Abend), jede mit eigenem Master-Switch
	// ----------------------------------------------------------------------------
	test('AC-1: Zwei Report-Sektionen Morgen + Abend mit Master-Switches', async ({
		page,
		request
	}) => {
		const id = tripId('ac1');
		await createTrip(request, id, {
			report_config: { enabled: true, morning_time: '07:00', evening_time: '18:00' }
		});
		try {
			await openReportsSection(page, id);

			// Beide Master-Switches sind vorhanden und checked (Migration: enabled=true → beide an)
			const morningSwitch = page.locator('[data-testid="morning-master-switch"]');
			const eveningSwitch = page.locator('[data-testid="evening-master-switch"]');
			await expect(morningSwitch).toBeVisible();
			await expect(eveningSwitch).toBeVisible();

			// Sichtbare Sektions-Header / -Labels: "Morgen-Report" und "Abend-Report"
			const reportsPanel = page.locator('[data-testid="edit-section-reports"]');
			await expect(reportsPanel).toContainText(/Morgen[-\s]Report/i);
			await expect(reportsPanel).toContainText(/Abend[-\s]Report/i);
		} finally {
			await deleteTrip(request, id);
		}
	});

	// ----------------------------------------------------------------------------
	// AC-2: Bei Master-Switch AUS sind Time-Input, Quick-Picks und Trend disabled
	// ----------------------------------------------------------------------------
	test('AC-2: Master-Switch AUS deaktiviert Time/QuickPick/Trend in der Sektion', async ({
		page,
		request
	}) => {
		const id = tripId('ac2');
		await createTrip(request, id);
		try {
			await openReportsSection(page, id);

			// Morgen-Master-Switch ausschalten (Native input innerhalb des Master-Switch)
			const morningSwitch = page
				.locator('[data-testid="morning-master-switch"]')
				.locator('input[type="checkbox"]');
			// Aktuell Initial-State: checked (Migration enabled=true)
			if (await morningSwitch.isChecked()) {
				await morningSwitch.click();
			}
			await expect(morningSwitch).not.toBeChecked();

			// Time-Input in Morgen-Sektion: disabled
			const morningTime = page.locator('[data-testid="report-morning-time"]');
			await expect(morningTime).toBeDisabled();

			// Quick-Pick-Buttons in Morgen-Sektion: disabled
			const morningQuickpick = page.locator('[data-testid="report-morning-quickpick-07"]');
			await expect(morningQuickpick).toBeDisabled();

			// Trend-Switch in Morgen-Sektion: disabled
			const morningTrend = page
				.locator('[data-testid="report-morning-trend"]')
				.locator('input[type="checkbox"]');
			await expect(morningTrend).toBeDisabled();
		} finally {
			await deleteTrip(request, id);
		}
	});

	// ----------------------------------------------------------------------------
	// AC-3: Keine change_threshold_*-Inputs mehr in der Reports-Sektion
	// ----------------------------------------------------------------------------
	test('AC-3: change_threshold_*-Inputs sind aus EditReportConfigSection entfernt', async ({
		page,
		request
	}) => {
		const id = tripId('ac3');
		await createTrip(request, id, {
			report_config: {
				enabled: true,
				morning_time: '07:00',
				evening_time: '18:00',
				// Diese Felder waren historisch in der Komponente — duerfen NICHT mehr
				// als Inputs gerendert werden:
				change_threshold_temp_c: 5.0,
				change_threshold_wind_kmh: 20.0,
				change_threshold_precip_mm: 10.0
			}
		});
		try {
			await openReportsSection(page, id);

			const reportsPanel = page.locator('[data-testid="edit-section-reports"]');
			// In der Reports-Sektion duerfen keine input-Felder mit "threshold" in der ID existieren.
			await expect(reportsPanel.locator('input[id*="threshold"]')).toHaveCount(0);
			// Auch keine TestIDs der alten Form:
			await expect(reportsPanel.locator('[data-testid*="threshold"]')).toHaveCount(0);
			// Defensive: Beschriftungen der alten Threshold-Inputs ("Temperatur (C)", "Wind (km/h)",
			// "Niederschlag (mm)") tauchen in der Reports-Sektion nicht mehr auf.
			await expect(reportsPanel).not.toContainText(/Temperatur \(C\)/i);
			await expect(reportsPanel).not.toContainText(/Wind \(km\/h\)/i);
			await expect(reportsPanel).not.toContainText(/Niederschlag \(mm\)/i);
		} finally {
			await deleteTrip(request, id);
		}
	});

	// ----------------------------------------------------------------------------
	// AC-4: Channel-Conditional — E-Mail enabled, Signal disabled bei fehlender Nummer
	// ----------------------------------------------------------------------------
	// Note: Der Default-Test-User `admin` hat im Account-Setup typischerweise
	// `mail_to` gesetzt, aber `signal_phone` leer. Dieser Test verifiziert genau
	// dieses Standardszenario. Falls der Default-User in Zukunft eine Signal-Nummer
	// bekommt, muss der Test einen User mit leerem signal_phone benutzen (oder
	// die Profile-Felder vor dem Test via /api/account leeren).
	test('AC-4: Signal-Channel disabled bei fehlender signal_phone, Account-Link sichtbar', async ({
		page,
		request
	}) => {
		const id = tripId('ac4');
		await createTrip(request, id);
		try {
			await openReportsSection(page, id);

			// E-Mail-Channel-Checkbox ist enabled (Profile.mail_to vorhanden).
			const emailChannel = page
				.locator('[data-testid="channel-email"]')
				.locator('input[type="checkbox"]');
			await expect(emailChannel).toBeVisible();
			await expect(emailChannel).not.toBeDisabled();

			// Signal-Channel-Checkbox ist disabled (Profile.signal_phone leer).
			const signalChannel = page
				.locator('[data-testid="channel-signal"]')
				.locator('input[type="checkbox"]');
			await expect(signalChannel).toBeDisabled();

			// Hinweis-Link "im Account einrichten" mit href="/account" sichtbar.
			const signalHint = page.locator('[data-testid="channel-signal-hint"]');
			await expect(signalHint).toBeVisible();
			const accountLink = signalHint.locator('a[href="/account"]');
			await expect(accountLink).toBeVisible();
			await expect(accountLink).toContainText(/im Account einrichten/i);
		} finally {
			await deleteTrip(request, id);
		}
	});

	// ----------------------------------------------------------------------------
	// AC-5: Quick-Pick-Buttons setzen die Uhrzeit korrekt
	// ----------------------------------------------------------------------------
	test('AC-5: Quick-Pick-Buttons "Morgens 07:00" und "Abends 18:00" setzen Uhrzeit', async ({
		page,
		request
	}) => {
		const id = tripId('ac5');
		await createTrip(request, id, {
			report_config: {
				enabled: true,
				morning_time: '05:30',
				evening_time: '20:00'
			}
		});
		try {
			await openReportsSection(page, id);

			// Sicherstellen, dass Morgen-Sektion AN ist (sonst sind die Buttons disabled)
			const morningSwitch = page
				.locator('[data-testid="morning-master-switch"]')
				.locator('input[type="checkbox"]');
			if (!(await morningSwitch.isChecked())) {
				await morningSwitch.click();
			}

			// Time-Input zeigt initial 05:30
			const morningTime = page.locator('[data-testid="report-morning-time"]');
			await expect(morningTime).toHaveValue('05:30');

			// Quick-Pick "Morgens 07:00" klicken
			await page.locator('[data-testid="report-morning-quickpick-07"]').click();
			await expect(morningTime).toHaveValue('07:00');

			// Abend-Sektion an, Quick-Pick "Abends 18:00" klicken
			const eveningSwitch = page
				.locator('[data-testid="evening-master-switch"]')
				.locator('input[type="checkbox"]');
			if (!(await eveningSwitch.isChecked())) {
				await eveningSwitch.click();
			}
			const eveningTime = page.locator('[data-testid="report-evening-time"]');
			await expect(eveningTime).toHaveValue('20:00');
			await page.locator('[data-testid="report-evening-quickpick-18"]').click();
			await expect(eveningTime).toHaveValue('18:00');
		} finally {
			await deleteTrip(request, id);
		}
	});

	// ----------------------------------------------------------------------------
	// AC-6: Trend-Schalter pro Sektion — Toggle + Save sendet korrektes Feld
	// ----------------------------------------------------------------------------
	test('AC-6: Trend-Switch Morgen togglen und in PUT /api/trips/[id] persistieren', async ({
		page,
		request
	}) => {
		const id = tripId('ac6');
		await createTrip(request, id, {
			report_config: {
				enabled: true,
				morning_time: '07:00',
				evening_time: '18:00',
				multi_day_trend_morning: false
			}
		});
		try {
			await openReportsSection(page, id);

			// Master-Switch Morgen sicher AN
			const morningSwitch = page
				.locator('[data-testid="morning-master-switch"]')
				.locator('input[type="checkbox"]');
			if (!(await morningSwitch.isChecked())) {
				await morningSwitch.click();
			}

			// Trend-Switch innerhalb Morgen-Sektion togglen (war false → wird true)
			const morningTrend = page
				.locator('[data-testid="report-morning-trend"]')
				.locator('input[type="checkbox"]');
			await expect(morningTrend).not.toBeChecked();
			await morningTrend.click();
			await expect(morningTrend).toBeChecked();

			// Save → PUT abfangen und Body inspizieren
			const putPromise = page.waitForRequest(
				(req) => req.method() === 'PUT' && req.url().endsWith(`/api/trips/${id}`)
			);
			await page.locator('[data-testid="edit-save-btn"]').click();
			const putReq = await putPromise;
			const body = JSON.parse(putReq.postData() || '{}');

			expect(body.report_config).toBeTruthy();
			expect(body.report_config.multi_day_trend_morning).toBe(true);

			await page.waitForURL('/trips', { timeout: 5000 });

			// Reload via API: Wert ist persistiert
			const after = await request.get(`/api/trips/${id}`);
			expect(after.ok()).toBe(true);
			const afterJson = await after.json();
			expect(afterJson.report_config.multi_day_trend_morning).toBe(true);
		} finally {
			await deleteTrip(request, id);
		}
	});

	// ----------------------------------------------------------------------------
	// AC-7: Read-Modify-Write — unbekannte report_config-Felder bleiben erhalten
	// ----------------------------------------------------------------------------
	test('AC-7: Custom-Feld in report_config bleibt nach Save byte-identisch', async ({
		page,
		request
	}) => {
		const id = tripId('ac7');
		await createTrip(request, id, {
			report_config: {
				enabled: true,
				morning_time: '07:00',
				evening_time: '18:00',
				custom_unknown_field: 'preserve-me',
				// Auch die alten threshold-Felder (UI rendert sie nicht mehr) muessen erhalten
				// bleiben — Read-Modify-Write fuer Daten-Integritaet.
				change_threshold_temp_c: 5.0,
				change_threshold_wind_kmh: 20.0,
				change_threshold_precip_mm: 10.0
			}
		});
		try {
			await openReportsSection(page, id);

			// Nichts aendern, direkt speichern
			await page.locator('[data-testid="edit-save-btn"]').click();
			await page.waitForURL('/trips', { timeout: 5000 });

			// Reload via API: custom_unknown_field ist immer noch da
			const after = await request.get(`/api/trips/${id}`);
			expect(after.ok()).toBe(true);
			const afterJson = await after.json();
			expect(afterJson.report_config.custom_unknown_field).toBe('preserve-me');
			// Auch alte threshold-Felder muessen byte-identisch erhalten bleiben
			expect(afterJson.report_config.change_threshold_temp_c).toBe(5.0);
			expect(afterJson.report_config.change_threshold_wind_kmh).toBe(20.0);
			expect(afterJson.report_config.change_threshold_precip_mm).toBe(10.0);
		} finally {
			await deleteTrip(request, id);
		}
	});
});

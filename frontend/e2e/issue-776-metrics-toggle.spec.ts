// E2E — Issue #776: E-Mail-Inhalts-Sektionen reagieren nicht auf Frontend-Toggles
//
// Spec: docs/specs/modules/issue_783_776_778_briefing_fixes.md (AC-3)
//
// TDD RED — gegen Staging. MUSS fehlschlagen, solange WeatherMetricsTab.handleSave()
// nur display_config persistiert und das gebundene reportConfig NIE per PUT
// /api/trips/{id} sendet — und solange isDirty den Toggle nicht erkennt
// (Speichern-Button bleibt disabled).
//
// Verhaltenstest aus Nutzerperspektive: echtes Login + echtes Klick-Verhalten gegen
// den gerenderten Staging-Build, anschliessend echter GET /api/trips/{id}. Kein Mock.
//
// Ausfuehrung: cd frontend && npx playwright test issue-776-metrics-toggle

import { test, expect } from '@playwright/test';
import { login } from './helpers.js';

const TRIP_ID = 'e2e-cockpit-test';
const DESKTOP = { width: 1440, height: 900 };

test.describe('Issue #776 — Inhalts-Toggle persistiert in report_config', () => {
	test('metrics summary toggle in weather tab persists to report_config', async ({
		page,
		request
	}) => {
		/**
		 * GIVEN: Trip im "Wetter-Metriken"-Tab mit aktivem "Metriken-Ueberblick"
		 * WHEN:  Der Nutzer den Toggle deaktiviert und auf Speichern klickt
		 * THEN:  GET /api/trips/{id} liefert report_config.show_metrics_summary == false
		 *
		 * RED: handleSave sendet reportConfig nicht; isDirty ignoriert den Toggle, der
		 *      Speichern-Button bleibt disabled -> der Wert bleibt unveraendert.
		 */
		await page.setViewportSize(DESKTOP);
		await login(page);

		// Ausgangszustand: Metriken-Ueberblick aktivieren + speichern, damit der
		// Test deterministisch von "true" nach "false" schaltet.
		await page.goto(`/trips/${TRIP_ID}?tab=weather`);
		await expect(page.getByTestId('weather-metrics-tab')).toBeVisible({ timeout: 10000 });

		// Inhalts-Bausteine aufklappen
		await page.getByTestId('report-content-modules-toggle').click();

		const metricsToggle = page
			.getByTestId('report-show-metrics-summary')
			.locator('input[type="checkbox"]');
		await expect(metricsToggle).toBeVisible({ timeout: 8000 });

		// Sicherstellen, dass er aktiv ist (sonst erst aktivieren + speichern)
		if (!(await metricsToggle.isChecked())) {
			await metricsToggle.check();
			const saveBtn0 = page.getByTestId('weather-metrics-tab-save');
			await expect(saveBtn0).toBeEnabled({ timeout: 8000 });
			await saveBtn0.click();
			await expect(page.getByTestId('weather-metrics-tab-success')).toBeVisible({
				timeout: 8000
			});
		}

		// --- Eigentlicher Test: deaktivieren ---
		await metricsToggle.uncheck();

		// AC-3 (isDirty-Teil): der Toggle MUSS den Tab als geaendert markieren,
		// sonst bleibt Speichern disabled. RED: bleibt heute disabled.
		const saveBtn = page.getByTestId('weather-metrics-tab-save');
		await expect(saveBtn).toBeEnabled({ timeout: 8000 });
		await saveBtn.click();
		await expect(page.getByTestId('weather-metrics-tab-success')).toBeVisible({
			timeout: 8000
		});

		// AC-3 (Persistenz-Teil): der gespeicherte Trip traegt den abgeschalteten Wert.
		const resp = await request.get(`/api/trips/${TRIP_ID}`);
		expect(resp.ok()).toBeTruthy();
		const trip = await resp.json();
		expect(trip.report_config?.show_metrics_summary).toBe(false);
	});
});

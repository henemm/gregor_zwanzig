// E2E — Epic #1319 Scheibe B+C: Tagesfenster-Control NUR im Trip-Kontext
// (context="route"), im geteilten VersandTab-Organismus bei
// context="vergleich" (Compare-Editor) ausgeblendet (DEC-4, Praezedenz
// #1318 FB01).
//
// Spec: docs/specs/modules/daywindow_configurable_window.md (AC-6)
// Kontext: docs/context/issue-1319-slice-b.md
// Workflow: issue-1319-slice-b
//
// TDD RED: das Fenster-Control existiert in VTSchedulePlan.svelte noch gar
// nicht (weder route noch vergleich) -- der "route"-Teil dieses Tests
// (Control MUSS sichtbar sein) schlaegt heute fehl (Timeout, Locator nie
// sichtbar). Der "vergleich"-Teil (Control darf NICHT sichtbar sein) ist per
// Zufall bereits gruen (weil das Control ueberhaupt nicht existiert) -- das
// ist ein GUARD, kein echter Nachweis der Kontext-Ausschluss-Logik; er muss
// nach der Implementierung aus dem RICHTIGEN Grund (das {#if isRoute}-Gate)
// weiterhin gruen bleiben. Muster analog versand-tab-vergleich.spec.ts.
//
// Ausfuehren (sobald implementiert, gegen Staging/Preview):
//   cd frontend && npx playwright test e2e/daywindow-compare-exclusion.spec.ts

import { test, expect, type APIRequestContext, type Page } from '@playwright/test';
import { login } from './helpers.js';

const TRIP_PREFIX = 'e2e-1319-daywindow-ctx';
const tripId = (suffix: string) => `${TRIP_PREFIX}-${suffix}`;

async function createTrip(request: APIRequestContext, id: string): Promise<void> {
	const res = await request.post('/api/trips', {
		data: {
			id,
			name: `Issue 1319 Slice B Context ${id}`,
			stages: [
				{
					id: `${id}-stage-1`,
					name: 'Etappe 1',
					date: '2026-08-01',
					waypoints: [{ id: `${id}-wp-1`, name: 'Start', lat: 42.1, lon: 9.0, elevation_m: 500 }]
				}
			],
			report_config: { enabled: true, morning_enabled: true, morning_time: '07:00', send_email: true }
		}
	});
	expect([200, 201]).toContain(res.status());
}

async function deleteTrip(request: APIRequestContext, id: string): Promise<void> {
	const res = await request.delete(`/api/trips/${id}`);
	expect([200, 204, 404]).toContain(res.status());
}

async function createPreset(page: Page): Promise<{ id: string }> {
	const res = await page.request.post('/api/compare/presets', {
		data: {
			name: 'E2E-GZ-Daywindow-Vergleich-' + Date.now(),
			location_ids: [],
			schedule: 'daily',
			profil: 'wandern',
			hour_from: 7,
			hour_to: 16,
			empfaenger: ['daywindow-vergleich-e2e@example.com'],
			display_config: { active_metrics: ['wind_max_kmh'] }
		}
	});
	expect(res.ok(), 'Preset-Anlage fehlgeschlagen: ' + res.status()).toBeTruthy();
	const body = await res.json();
	return { id: body.id };
}

test.describe('Epic #1319 Scheibe B+C: Kontext-Ausschluss des Tagesfenster-Controls', () => {
	// AC-6 (route-Haelfte): Trip-Editor context="route" -- Control MUSS da sein.
	test('AC-6: Tagesfenster-Control ist im Trip-Versand-Tab (context=route) sichtbar', async ({ page }) => {
		const id = tripId('route');
		await page.request.delete(`/api/trips/${id}`).catch(() => {});
		await createTrip(page.request, id);
		try {
			await login(page);
			await page.goto(`/trips/${id}`);
			await expect(page.getByTestId('trip-detail-tab-list')).toBeVisible();
			await page.getByTestId('trip-detail-tab-briefings').first().click();
			await expect(page.getByTestId('trip-detail-panel-briefings')).toBeVisible();

			await expect(page.locator('[data-testid="day-window-control"]:visible').first()).toBeVisible({
				timeout: 10_000
			});
		} finally {
			await deleteTrip(page.request, id);
		}
	});

	// AC-6 (vergleich-Haelfte): Compare-Editor context="vergleich" -- Control
	// darf NICHT im DOM sein (Praezedenz #1318 FB01, DEC-4).
	test('AC-6: Tagesfenster-Control fehlt im Compare-Versand-Tab (context=vergleich)', async ({ page }) => {
		await page.setViewportSize({ width: 1280, height: 900 });
		const { id } = await createPreset(page);

		await page.goto(`/compare/${id}`);
		await page.waitForLoadState('networkidle');
		await page.locator('[data-testid="compare-detail-tab-versand"]:visible').first().click();

		await expect(page.locator('[data-testid="compare-step5-channel-email"]:visible').first()).toBeVisible({
			timeout: 10_000
		});
		await expect(page.locator('[data-testid="day-window-control"]')).toHaveCount(0);
	});
});

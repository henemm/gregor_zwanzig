// E2E-Tests für Issue #946 — AlertsTab: Onboarding-Zustand, Standard-Aktivierung, freezing_level.
//
// Spec: docs/specs/fast/fix-946-frontend-ac-tests.md
//
// ACs:
//   AC-4: Trip ohne metric_alert_levels/alert_preset → Onboarding-Zustand sichtbar
//   AC-5: Klick "Standard-Konfiguration übernehmen" → Tabelle erscheint + Backend persistiert
//   AC-6: Trip mit freezing_level-Metrik → "Nullgradgrenze"-Zeile in der Tabelle sichtbar

import { test, expect } from '@playwright/test';
import { login } from './helpers.js';

const TRIP_PREFIX = 'e2e-issue-946';
const tripId = (suffix: string) => `${TRIP_PREFIX}-${suffix}`;

async function createTrip(
	request: import('@playwright/test').APIRequestContext,
	id: string,
	displayConfig: Record<string, unknown> = {}
) {
	const res = await request.post('/api/trips', {
		data: {
			id,
			name: `Issue 946 ${id}`,
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
			display_config: displayConfig
		}
	});
	expect([200, 201]).toContain(res.status());
}

async function deleteTrip(
	request: import('@playwright/test').APIRequestContext,
	id: string
) {
	await request.delete(`/api/trips/${id}`).catch(() => {});
}

async function openAlertsTab(page: import('@playwright/test').Page, id: string) {
	await page.goto(`/trips/${id}?tab=alerts`);
	await expect(page.getByTestId('alerts-tab')).toBeVisible();
}

test.describe('Issue #946: AlertsTab Onboarding + freezing_level', () => {
	test.beforeEach(async ({ page }) => {
		await login(page);
	});

	test('AC-4: Unkonfigurierter Trip zeigt Onboarding-Zustand', async ({ page, request }) => {
		const id = tripId('ac4');
		await createTrip(request, id, { metric_alert_levels: null, alert_preset: null });
		try {
			await openAlertsTab(page, id);

			await expect(page.getByTestId('alerts-onboarding')).toBeVisible();
			await expect(page.getByTestId('alert-metric-level-table')).not.toBeVisible();
		} finally {
			await deleteTrip(request, id);
		}
	});

	test('AC-5: "Standard-Konfiguration übernehmen" persistiert metric_alert_levels', async ({
		page,
		request
	}) => {
		const id = tripId('ac5');
		await createTrip(request, id, { metric_alert_levels: null, alert_preset: null });
		try {
			await openAlertsTab(page, id);

			await page.getByTestId('alerts-activate-standard').click();

			await expect(page.getByTestId('alerts-onboarding')).not.toBeVisible();
			await expect(page.getByTestId('alert-metric-level-table')).toBeVisible();

			// Warte auf Auto-Save (SaveController debounce ~1 s)
			await page.waitForTimeout(2000);

			const res = await request.get(`/api/trips/${id}`);
			expect(res.status()).toBe(200);
			const body = await res.json();
			const levels = body.display_config?.metric_alert_levels;
			expect(levels).not.toBeNull();
			expect(typeof levels).toBe('object');
			expect(Object.keys(levels).length).toBeGreaterThan(0);
		} finally {
			await deleteTrip(request, id);
		}
	});

	test('AC-6: Trip mit freezing_level-Metrik zeigt "Nullgradgrenze" in Alert-Tabelle', async ({
		page,
		request
	}) => {
		const id = tripId('ac6');
		await createTrip(request, id, {
			metric_alert_levels: { freezing_level: 'standard' },
			metrics: [{ metric_id: 'freezing_level', enabled: true }]
		});
		try {
			await openAlertsTab(page, id);

			const row = page.getByTestId('alert-metric-row-freezing_level');
			await expect(row).toBeVisible();
			await expect(row).toContainText('Nullgradgrenze');
		} finally {
			await deleteTrip(request, id);
		}
	});
});

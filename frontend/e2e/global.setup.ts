import { test as setup, expect } from '@playwright/test';

const authFile = 'playwright/.auth/admin.json';

setup('authenticate and seed test data', async ({ page }) => {
	await page.goto('/login');
	await page.fill('input[name="username"]', 'admin');
	await page.fill('input[name="password"]', 'test1234');
	await page.click('button[type="submit"]');
	await page.waitForURL('/');
	await expect(page).toHaveURL('/');
	await page.context().storageState({ path: authFile });

	// Seed: E2E-Cockpit-Test-Trip mit dynamischem Datum (immer relativ zu heute)
	const today = new Date().toISOString().slice(0, 10);
	const tomorrow = new Date(Date.now() + 86400000).toISOString().slice(0, 10);
	const yesterday = new Date(Date.now() - 86400000).toISOString().slice(0, 10);

	await page.request.post('/api/trips', {
		data: {
			id: 'e2e-cockpit-test',
			name: 'E2E Cockpit Test Trip',
			stages: [
				{
					id: 'e2e-stage-1',
					name: 'Gestern',
					date: yesterday,
					waypoints: [
						{ id: 'e2e-wp-1', name: 'Start', lat: 42.1, lon: 9.0, elevation_m: 800 }
					]
				},
				{
					id: 'e2e-stage-2',
					name: 'Heute',
					date: today,
					waypoints: [
						{ id: 'e2e-wp-2', name: 'Mitte', lat: 42.2, lon: 9.1, elevation_m: 1200 },
						{ id: 'e2e-wp-3', name: 'Ziel', lat: 42.3, lon: 9.2, elevation_m: 600 }
					]
				},
				{
					id: 'e2e-stage-3',
					name: 'Morgen',
					date: tomorrow,
					waypoints: [
						{ id: 'e2e-wp-4', name: 'Ende', lat: 42.4, lon: 9.3, elevation_m: 400 }
					]
				}
			],
			report_config: {
				enabled: true,
				morning_time: '06:00:00',
				evening_time: '18:00:00',
				alert_on_changes: true
			},
			weather_config: {
				metrics: ['temp_min', 'temp_max', 'wind_max', 'precip_sum']
			},
			aggregation: {
				activity_profile: 'wandern'
			}
		}
	});
});

import { test as setup, expect, request as playwrightRequest } from '@playwright/test';
import * as fs from 'fs';

const authFile = 'playwright/.auth/admin.json';
const TRIP_ID = 'e2e-cockpit-test';

function isAuthFileValid(): boolean {
	if (!fs.existsSync(authFile)) return false;
	try {
		const state = JSON.parse(fs.readFileSync(authFile, 'utf-8'));
		const cookies = state.cookies ?? [];
		const sessionCookie = cookies.find((c: { name: string; expires: number }) => c.name === 'gz_session');
		if (!sessionCookie) return false;
		return sessionCookie.expires * 1000 > Date.now() + 60_000;
	} catch {
		return false;
	}
}

setup('authenticate and seed test data', async ({ page }) => {
	const user = process.env.E2E_USER ?? 'admin';
	const pass = process.env.E2E_PASS ?? 'test1234';

	if (!isAuthFileValid()) {
		await page.goto('/login');
		await page.fill('input[name="username"]', user);
		await page.fill('input[name="password"]', pass);
		await page.click('button[type="submit"]');
		await page.waitForURL('/');
		await expect(page).toHaveURL('/');
		await page.context().storageState({ path: authFile });
	} else {
		await page.context().addCookies(
			JSON.parse(fs.readFileSync(authFile, 'utf-8')).cookies
		);
	}

	// Seed: E2E-Test-Locations für Compare-Tests (Issue #263).
	// IDs sind stabil — FixtureProvider liefert per nearest-Lookup
	// passende Wetter-Daten für diese 3 Locations.
	const e2eLocations = [
		{ id: 'e2e-loc-innsbruck', name: 'Innsbruck (E2E)', lat: 47.2692, lon: 11.4041, elevation_m: 574 },
		{ id: 'e2e-loc-stubai', name: 'Stubai (E2E)', lat: 47.1015, lon: 11.2958, elevation_m: 1000 },
		{ id: 'e2e-loc-zillertal', name: 'Zillertal (E2E)', lat: 47.2190, lon: 11.8767, elevation_m: 540 }
	];
	for (const loc of e2eLocations) {
		await page.request.delete(`/api/locations/${loc.id}`);
		await page.request.post('/api/locations', { data: loc });
	}

	// Seed: E2E-Cockpit-Test-Trip mit dynamischem Datum (immer relativ zu heute)
	const today = new Date().toISOString().slice(0, 10);
	const tomorrow = new Date(Date.now() + 86400000).toISOString().slice(0, 10);
	const yesterday = new Date(Date.now() - 86400000).toISOString().slice(0, 10);

	// Sicherstellen dass ein altes Trip gelöscht wird (404 ignorieren)
	await page.request.delete(`/api/trips/${TRIP_ID}`);

	await page.request.post('/api/trips', {
		data: {
			id: TRIP_ID,
			name: 'E2E Cockpit Test Trip',
			region: 'Korsika',
			stages: [
				{
					id: 'e2e-stage-1',
					name: 'Gestern',
					date: yesterday,
					waypoints: [
						{ id: 'e2e-wp-1', name: 'Start', lat: 42.1, lon: 9.0, elevation_m: 800 },
						{ id: 'e2e-wp-1b', name: 'Zwischenstopp', lat: 42.15, lon: 9.05, elevation_m: 1000 }
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
					waypoints: []
				}
			],
			report_config: {
				enabled: true,
				morning_time: '06:00:00',
				evening_time: '18:00:00',
				alert_on_changes: true
			},
			display_config: {
				metrics: ['temp_min', 'temp_max', 'wind_max', 'precip_sum']
			},
			aggregation: {
				profile: 'wandern'
			}
		}
	});
});

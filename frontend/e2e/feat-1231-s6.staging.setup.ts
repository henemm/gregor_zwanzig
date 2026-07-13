import { test as setup, expect } from '@playwright/test';
import * as fs from 'fs';
// Staging-Auth + Seed für Slice 6 (#1231 Tab-Renames, AC-18-Beweis).
// Analog feat-880.staging.setup.ts, aber mit korrigierter Credential-Kette:
// nginx-Basic-Auth = GZ_VALIDATOR_*, App-Login = GZ_AUTH_* (getrennte Layer).
// Zusätzlich Seed von e2e-cockpit-test + e2e-loc-* (Voraussetzung für
// issue-302/issue-616/design-compliance-group-a — analog global.setup.ts).
const authFile = 'playwright/.auth/staging-1231-s6.json';
const TRIP_ID = 'e2e-cockpit-test';

setup('authenticate via API (staging) + seed — feat_1231_s6', async ({ playwright }) => {
	const base = process.env.GZ_SVELTE_BASE ?? 'https://staging.gregor20.henemm.com';
	const validatorUser = process.env.GZ_VALIDATOR_USER!;
	const validatorPass = process.env.GZ_VALIDATOR_PASS!;
	const appUser = process.env.GZ_AUTH_USER!;
	const appPass = process.env.GZ_AUTH_PASS!;

	const ctx = await playwright.request.newContext({
		baseURL: base,
		ignoreHTTPSErrors: true,
		httpCredentials: { username: validatorUser, password: validatorPass }
	});
	const res = await ctx.post('/api/auth/login', {
		data: { username: appUser, password: appPass }
	});
	expect(res.ok(), `login HTTP ${res.status()}`).toBeTruthy();

	// Seed: E2E-Test-Locations (Compare-Tests)
	const e2eLocations = [
		{ id: 'e2e-loc-innsbruck', name: 'Innsbruck (E2E)', lat: 47.2692, lon: 11.4041, elevation_m: 574 },
		{ id: 'e2e-loc-stubai', name: 'Stubai (E2E)', lat: 47.1015, lon: 11.2958, elevation_m: 1000 },
		{ id: 'e2e-loc-zillertal', name: 'Zillertal (E2E)', lat: 47.2190, lon: 11.8767, elevation_m: 540 }
	];
	for (const loc of e2eLocations) {
		await ctx.delete(`/api/locations/${loc.id}`);
		await ctx.post('/api/locations', { data: loc });
	}

	// Seed: E2E-Cockpit-Test-Trip mit dynamischem Datum
	const today = new Date().toISOString().slice(0, 10);
	const tomorrow = new Date(Date.now() + 86400000).toISOString().slice(0, 10);
	const yesterday = new Date(Date.now() - 86400000).toISOString().slice(0, 10);

	await ctx.delete(`/api/trips/${TRIP_ID}`);
	await ctx.post('/api/trips', {
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
				{ id: 'e2e-stage-3', name: 'Morgen', date: tomorrow, waypoints: [] }
			],
			report_config: { enabled: true, morning_time: '06:00:00', evening_time: '18:00:00', alert_on_changes: true },
			display_config: { metrics: ['temp_min', 'temp_max', 'wind_max', 'precip_sum'] },
			aggregation: { profile: 'wandern' }
		}
	});

	await ctx.storageState({ path: authFile });
	await ctx.dispose();
	fs.chmodSync(authFile, 0o600);
});

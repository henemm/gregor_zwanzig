import { test as setup, expect } from '@playwright/test';
import { assertNotProdBaseURL } from './prodUrlGuard';
import * as fs from 'fs';
// Staging-Validator-Setup fuer Issue #1258 Scheibe S3 (Trip-Alarme-Tab).
// nginx-Basic-Auth = GZ_VALIDATOR_*, App-Login = GZ_AUTH_* (getrennte Layer,
// mappt auf User "default" auf Staging). Seed: eigener Test-Trip statt des
// namensstabilen validator-issue110-Rolling-Trips (anderer User) — dediziert
// fuer die S3-Staging-Validierung, mit Default-report_config (nur send_email)
// als Grundlage fuer AC-15 (rekonstruierter Bestand-Kanal-Status).
const authFile = 'playwright/.auth/staging-1258-s3.json';
export const TRIP_ID = 'e2e-1258-s3-alarme';

setup('authenticate via API (staging) + seed — feat_1258_s3', async ({ playwright }) => {
	const base = process.env.GZ_SVELTE_BASE ?? 'https://staging.gregor20.henemm.com';
	assertNotProdBaseURL(base);
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

	await ctx.delete(`/api/trips/${TRIP_ID}`);
	const createRes = await ctx.post('/api/trips', {
		data: {
			id: TRIP_ID,
			name: 'E2E 1258 S3 Alarme Test Trip',
			region: 'Test',
			stages: [
				{
					id: 'e2e-1258-stage-1',
					name: 'Etappe 1',
					date: new Date(Date.now() + 86400000).toISOString().slice(0, 10),
					waypoints: [
						{ id: 'e2e-1258-wp-1', name: 'Start', lat: 47.2692, lon: 11.4041, elevation_m: 574 },
						{ id: 'e2e-1258-wp-2', name: 'Ziel', lat: 47.2802, lon: 11.3907, elevation_m: 830 }
					]
				}
			],
			// Bewusst KEIN alert_channels — Bestands-Rekonstruktion (AC-15) soll aus
			// report_config.send_* ableiten (send_email=true, telegram/sms unset->false).
			report_config: { enabled: true, send_email: true }
		}
	});
	expect(createRes.ok(), `seed trip HTTP ${createRes.status()}`).toBeTruthy();

	await ctx.storageState({ path: authFile });
	await ctx.dispose();
	fs.chmodSync(authFile, 0o600);
});

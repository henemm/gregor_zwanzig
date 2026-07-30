import { test as setup, expect } from '@playwright/test';
import { assertNotProdBaseURL } from './prodUrlGuard';
import * as fs from 'fs';
// Staging-Validierung Ortsvergleich-Ausblick (Metrik-Auswahl, Issue #1406
// Scheibe A). Muster identisch zu compare-metric-order.staging.setup.ts:
// nginx-Basic-Auth = GZ_VALIDATOR_*, App-Login = GZ_AUTH_* (getrennte Layer),
// eigener storageState statt Login pro Test (Token-Bucket 30/h).
const authFile = 'playwright/.auth/staging-compare-outlook.json';

setup('authenticate via API (staging) — compare_outlook_metric_selection', async ({ playwright }) => {
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

	await ctx.storageState({ path: authFile });
	await ctx.dispose();
	fs.chmodSync(authFile, 0o600);
});

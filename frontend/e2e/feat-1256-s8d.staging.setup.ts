import { test as setup, expect } from '@playwright/test';
import { assertNotProdBaseURL } from './prodUrlGuard';
import * as fs from 'fs';
// Staging-Auth für Issue #1256 Scheibe S8d (Mobile-Editor-Fidelity, R4+C1).
// Analog feat-1256-s8c.staging.setup.ts: nginx-Basic-Auth = GZ_VALIDATOR_*,
// App-Login = GZ_AUTH_* (getrennte Layer) — eigener storageState statt Login
// pro Testlauf (reference_staging_e2e_storagestate_login_rate_limit — 429).
const authFile = 'playwright/.auth/staging-1256-s8d.json';

setup('authenticate via API (staging) — feat_1256_s8d_mobile_editor_fidelity', async ({ playwright }) => {
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

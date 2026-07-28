import { test as setup, expect } from '@playwright/test';
import { assertNotProdBaseURL } from './prodUrlGuard';
import * as fs from 'fs';
// Staging-Auth für D2 von Epic #1301 (Amtliche-Warnungen-Schalter,
// Re-Validierung Fix-Loop 2, Commit 63c1fc95). Muster analog
// feat-1301-c2-hub-zugang.staging.setup.ts: nginx-Basic-Auth =
// GZ_VALIDATOR_*, App-Login = GZ_AUTH_* — eigener storageState statt
// Login pro Testlauf (reference_staging_e2e_storagestate_login_rate_limit).
const authFile = 'playwright/.auth/staging-1301-d2.json';

setup('authenticate via API (staging) — d2_1301_official_alerts', async ({ playwright }) => {
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

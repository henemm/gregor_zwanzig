import { test as setup, expect } from '@playwright/test';
import { assertNotProdBaseURL } from './prodUrlGuard';
import * as fs from 'fs';
// Staging-Auth für D3 von Epic #1301 (Alarm-Tab Struktur/Beschriftung,
// Commit e203a2d5). Muster analog d2-1301-official-alerts.staging.setup.ts:
// nginx-Basic-Auth = GZ_VALIDATOR_*, App-Login = GZ_AUTH_* — eigener
// storageState statt Login pro Testlauf (reference_staging_e2e_storagestate_login_rate_limit).
const authFile = 'playwright/.auth/staging-1301-d3.json';

setup('authenticate via API (staging) — d3_1301_alarm_tab_struktur', async ({ playwright }) => {
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

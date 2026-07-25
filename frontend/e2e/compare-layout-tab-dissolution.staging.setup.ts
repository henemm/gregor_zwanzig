import { test as setup, expect } from '@playwright/test';
import { assertNotProdBaseURL } from './prodUrlGuard';
import * as fs from 'fs';
// Staging-Auth für die Auflösung des Layout-Reiters im Ortsvergleich
// (Issue #1360, Scheibe S1a von Epic #1372). Muster identisch zu
// compare-metric-order.staging.setup.ts:
//   nginx-Basic-Auth = GZ_VALIDATOR_*, App-Login = GZ_AUTH_* (getrennte Layer),
//   eigener storageState statt Login pro Test (Token-Bucket 30/h → 429, s.
//   reference_staging_e2e_storagestate_login_rate_limit).
// `assertNotProdBaseURL` sperrt jeden Lauf gegen die Prod-Domain (#1265) —
// GZ_API_BASE zeigt per Default auf PRODUKTION.
const authFile = 'playwright/.auth/staging-compare-layout-tab.json';

setup('authenticate via API (staging) — compare_layout_tab_dissolution', async ({ playwright }) => {
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

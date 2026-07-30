import { test as setup, expect } from '@playwright/test';
import { assertNotProdBaseURL } from './prodUrlGuard';
// Staging-Auth für issue_953 (Alerts-Empfindlichkeit über Tab-Wechsel).
// ZWEI GETRENNTE Credential-Paare (Muster wie compare-hub-save-chip.staging.setup.ts
// und compare-outlook-metric-selection.staging.setup.ts): nginx-Basic-Auth =
// GZ_VALIDATOR_*, App-Login (gz_session-Cookie) = GZ_AUTH_*. Frueher stand hier
// EIN Paar fuer beides; seit die Paare auseinanderlaufen gab das am App-Login 401
// (gemessen 2026-07-30: Validator-Creds an der Schranke + App-Creds im Body -> 200,
// Validator-Creds in beiden Rollen -> 401).
const authFile = 'playwright/.auth/staging-953.json';

setup('authenticate via API (staging) — issue_953', async ({ playwright }) => {
	const base = process.env.GZ_SVELTE_BASE ?? 'https://staging.gregor20.henemm.com';
	assertNotProdBaseURL(base);
	const nginxUser = process.env.GZ_VALIDATOR_USER ?? 'admin';
	const nginxPass = process.env.GZ_VALIDATOR_PASS ?? 'test1234';
	const appUser = process.env.GZ_AUTH_USER ?? process.env.E2E_USER ?? 'admin';
	const appPass = process.env.GZ_AUTH_PASS ?? process.env.E2E_PASS ?? 'test1234';

	const ctx = await playwright.request.newContext({
		baseURL: base,
		ignoreHTTPSErrors: true,
		httpCredentials: { username: nginxUser, password: nginxPass }
	});
	const res = await ctx.post('/api/auth/login', {
		data: { username: appUser, password: appPass }
	});
	expect(res.ok(), `login HTTP ${res.status()}`).toBeTruthy();
	await ctx.storageState({ path: authFile });
	await ctx.dispose();
});

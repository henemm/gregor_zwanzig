import { test as setup, expect } from '@playwright/test';
import { assertNotProdBaseURL } from './prodUrlGuard';
import { ausUmgebung } from './stagingZugang';
// Staging-Auth via API-Login (umgeht flakigen UI-Login + CSRF-403 auf /login).
// Nutzt Validator-Creds (Issue #110) bzw. GZ_AUTH_* aus dem Staging-.env.
const authFile = 'playwright/.auth/staging-758.json';
setup('authenticate via API (staging) — #758', async ({ playwright }) => {
	const base = process.env.GZ_SVELTE_BASE ?? 'https://staging.gregor20.henemm.com';
	assertNotProdBaseURL(base);
	const ctx = await playwright.request.newContext({ baseURL: base, ignoreHTTPSErrors: true });
	const res = await ctx.post('/api/auth/login', {
		data: {
			username: ausUmgebung('GZ_VALIDATOR_USER', 'E2E_USER'),
			password: ausUmgebung('GZ_VALIDATOR_PASS', 'E2E_PASS')
		}
	});
	expect(res.ok(), `login HTTP ${res.status()}`).toBeTruthy();
	await ctx.storageState({ path: authFile });
	await ctx.dispose();
});

import { test as setup, expect } from '@playwright/test';
import { assertNotProdBaseURL } from './prodUrlGuard';
import { ausUmgebung } from './stagingZugang';
// Staging-Auth für feat_880 (Autospeicher-Overlay). Analog issue-758.staging.setup.ts.
// Staging steht hinter nginx-Basic-Auth (dieselben Validator-Creds) UND einem
// App-Login (gz_session-Cookie). Beide werden hier gesetzt.
const authFile = 'playwright/.auth/staging-880.json';

setup('authenticate via API (staging) — feat_880', async ({ playwright }) => {
	const base = process.env.GZ_SVELTE_BASE ?? 'https://staging.gregor20.henemm.com';
	assertNotProdBaseURL(base);
	const user = ausUmgebung('GZ_VALIDATOR_USER', 'E2E_USER');
	const pass = ausUmgebung('GZ_VALIDATOR_PASS', 'E2E_PASS');

	const ctx = await playwright.request.newContext({
		baseURL: base,
		ignoreHTTPSErrors: true,
		httpCredentials: { username: user, password: pass }
	});
	const res = await ctx.post('/api/auth/login', {
		data: { username: user, password: pass }
	});
	expect(res.ok(), `login HTTP ${res.status()}`).toBeTruthy();
	await ctx.storageState({ path: authFile });
	await ctx.dispose();
});

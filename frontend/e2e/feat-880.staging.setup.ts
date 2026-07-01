import { test as setup, expect } from '@playwright/test';
// Staging-Auth für feat_880 (Autospeicher-Overlay). Analog issue-758.staging.setup.ts.
// Staging steht hinter nginx-Basic-Auth (dieselben Validator-Creds) UND einem
// App-Login (gz_session-Cookie). Beide werden hier gesetzt.
const authFile = 'playwright/.auth/staging-880.json';

setup('authenticate via API (staging) — feat_880', async ({ playwright }) => {
	const base = process.env.GZ_SVELTE_BASE ?? 'https://staging.gregor20.henemm.com';
	const user = process.env.GZ_VALIDATOR_USER ?? process.env.E2E_USER ?? 'admin';
	const pass = process.env.GZ_VALIDATOR_PASS ?? process.env.E2E_PASS ?? 'test1234';

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

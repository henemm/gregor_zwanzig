import { test as setup, expect } from '@playwright/test';
import { assertNotProdBaseURL } from './prodUrlGuard';
// Staging-Auth für Issue #1059 (Fortsetzen-Button ohne Fehler-Feedback). Analog feat-880.staging.setup.ts.
// Staging steht hinter nginx-Basic-Auth (dieselben Validator-Creds) UND einem
// App-Login (gz_session-Cookie). Beide werden hier gesetzt.
const authFile = 'playwright/.auth/staging-1059.json';

setup('authenticate via API (staging) — #1059', async ({ playwright }) => {
	const base = process.env.GZ_SVELTE_BASE ?? 'https://staging.gregor20.henemm.com';
	assertNotProdBaseURL(base);
	// nginx-Basic-Auth (Validator-Creds) und App-Login (GZ_AUTH_*) sind unterschiedliche
	// Credential-Paare — siehe docs/reference/operations_playbook.md.
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

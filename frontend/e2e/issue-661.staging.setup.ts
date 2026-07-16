import { test as setup, expect } from '@playwright/test';
import { assertNotProdBaseURL } from './prodUrlGuard';
// Staging-Auth via API-Login (umgeht flakigen UI-Login + CSRF-403 auf /login).
const authFile = 'playwright/.auth/staging-661.json';
setup('authenticate via API (staging)', async ({ playwright }) => {
	const base = process.env.GZ_SVELTE_BASE ?? 'https://staging.gregor20.henemm.com';
	assertNotProdBaseURL(base);
	// Staging steht hinter nginx-Basic-Auth (Validator-Creds) UND einem App-Login.
	// Beide Schichten bleiben unabhängig — Basic-Auth kommt on top. Analog feat-880.
	const user = process.env.GZ_VALIDATOR_USER ?? process.env.E2E_USER ?? 'admin';
	const pass = process.env.GZ_VALIDATOR_PASS ?? process.env.E2E_PASS ?? 'test1234';
	// App-Login-Konto (GZ_AUTH_*) ist unabhaengig von den rotierenden
	// nginx-Basic-Auth-Validator-Creds (GZ_VALIDATOR_*). httpCredentials bleibt
	// bei den Validator-Creds, der Login-Body braucht das stabile App-Konto.
	const authUser = process.env.GZ_AUTH_USER ?? 'default';
	const authPass = process.env.GZ_AUTH_PASS;
	const ctx = await playwright.request.newContext({
		baseURL: base,
		ignoreHTTPSErrors: true,
		httpCredentials: { username: user, password: pass },
	});
	const res = await ctx.post('/api/auth/login', {
		data: {
			username: authUser,
			password: authPass,
		},
	});
	expect(res.ok(), `login HTTP ${res.status()}`).toBeTruthy();
	await ctx.storageState({ path: authFile });
	await ctx.dispose();
});

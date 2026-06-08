import { test as setup, expect } from '@playwright/test';
// Staging-Auth via API-Login (umgeht flakigen UI-Login + CSRF-403 auf /login).
const authFile = 'playwright/.auth/staging-661.json';
setup('authenticate via API (staging)', async ({ playwright }) => {
	const base = process.env.GZ_SVELTE_BASE ?? 'https://staging.gregor20.henemm.com';
	const ctx = await playwright.request.newContext({ baseURL: base, ignoreHTTPSErrors: true });
	const res = await ctx.post('/api/auth/login', {
		data: {
			username: process.env.GZ_VALIDATOR_USER ?? process.env.E2E_USER ?? 'admin',
			password: process.env.GZ_VALIDATOR_PASS ?? process.env.E2E_PASS ?? 'test1234',
		},
	});
	expect(res.ok(), `login HTTP ${res.status()}`).toBeTruthy();
	await ctx.storageState({ path: authFile });
	await ctx.dispose();
});

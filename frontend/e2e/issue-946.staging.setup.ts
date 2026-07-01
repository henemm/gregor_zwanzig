import { test as setup, expect } from '@playwright/test';

const authFile = 'playwright/.auth/staging-946.json';

setup('authenticate via API (staging #946)', async ({ playwright }) => {
	const base = process.env.GZ_SVELTE_BASE ?? 'https://staging.gregor20.henemm.com';
	const user = process.env.GZ_VALIDATOR_USER ?? 'admin';
	const pass = process.env.GZ_VALIDATOR_PASS ?? 'test1234';
	const basicAuth = Buffer.from(`${user}:${pass}`).toString('base64');

	const ctx = await playwright.request.newContext({
		baseURL: base,
		ignoreHTTPSErrors: true,
		extraHTTPHeaders: { Authorization: `Basic ${basicAuth}` }
	});
	const res = await ctx.post('/api/auth/login', {
		data: { username: user, password: pass }
	});
	expect(res.ok(), `login HTTP ${res.status()}`).toBeTruthy();
	await ctx.storageState({ path: authFile });
	await ctx.dispose();
});

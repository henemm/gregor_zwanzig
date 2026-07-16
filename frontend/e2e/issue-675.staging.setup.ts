import { test as setup, expect } from '@playwright/test';
import { assertNotProdBaseURL } from './prodUrlGuard';

// Staging-Auth für Issue #675 via API-Login (einmalig, umgeht Auth-Rate-Limit
// bei parallelen UI-Logins). Wegwerf-Testnutzer, keine echten Secrets.
const authFile = 'playwright/.auth/staging-675.json';
const E2E_USER = 'e2e675user';
const E2E_PASS = 'e2e675pass!';

setup('register + authenticate via API (staging)', async ({ playwright }) => {
	const base = process.env.GZ_SVELTE_BASE ?? 'https://staging.gregor20.henemm.com';
	assertNotProdBaseURL(base);
	const ctx = await playwright.request.newContext({ baseURL: base, ignoreHTTPSErrors: true });
	// Register idempotent — 201 (neu) oder 409/400 (vorhanden) sind beide ok.
	await ctx.post('/api/auth/register', { data: { username: E2E_USER, password: E2E_PASS } }).catch(() => {});
	const res = await ctx.post('/api/auth/login', { data: { username: E2E_USER, password: E2E_PASS } });
	expect(res.ok(), `login HTTP ${res.status()}`).toBeTruthy();
	await ctx.storageState({ path: authFile });
	await ctx.dispose();
});

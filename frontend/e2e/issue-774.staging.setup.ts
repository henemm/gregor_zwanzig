import { test as setup, expect } from '@playwright/test';
import type { APIRequestContext } from '@playwright/test';

// Staging-Auth für Issue #774 via API (Wegwerf-Testnutzer, keine echten Secrets).
// Einmaliger Register+Login im setup-Projekt → storageState; Tests laufen
// vorauthentifiziert (vermeidet Auth-Rate-Limit bei parallelen UI-Logins).
//
// Robust gegen Login-Rate-Limit (#703): bei HTTP 429 wird der Retry-After-Header
// respektiert und mehrfach nachgefasst. Register nur bei echtem 401 (User fehlt),
// nicht bei 429 — sonst verlängert jeder Auth-Hit das gleitende Limit-Fenster.
const authFile = 'playwright/.auth/staging-774.json';
const E2E_USER = 'e2e774user';
const E2E_PASS = 'e2e774pass!';

function sleep(ms: number) {
	return new Promise((r) => setTimeout(r, ms));
}

async function tryLogin(ctx: APIRequestContext) {
	return ctx.post('/api/auth/login', { data: { username: E2E_USER, password: E2E_PASS } });
}

setup('register + authenticate via API (staging)', async ({ playwright }) => {
	setup.setTimeout(420_000);
	const base = process.env.GZ_SVELTE_BASE ?? 'https://staging.gregor20.henemm.com';
	const ctx = await playwright.request.newContext({ baseURL: base, ignoreHTTPSErrors: true });

	let res = await tryLogin(ctx);
	let attempts = 0;
	while (!res.ok() && attempts < 6) {
		attempts++;
		if (res.status() === 429) {
			const retryAfter = parseInt(res.headers()['retry-after'] ?? '60', 10);
			await sleep((isNaN(retryAfter) ? 60 : retryAfter) * 1000 + 3_000);
			res = await tryLogin(ctx);
		} else {
			// 401/400 → Nutzer existiert vermutlich noch nicht: registrieren, dann erneut.
			await ctx.post('/api/auth/register', { data: { username: E2E_USER, password: E2E_PASS } }).catch(() => {});
			await sleep(2_000);
			res = await tryLogin(ctx);
		}
	}

	expect(res.ok(), `login HTTP ${res.status()} nach ${attempts} Versuchen`).toBeTruthy();
	await ctx.storageState({ path: authFile });
	await ctx.dispose();
});

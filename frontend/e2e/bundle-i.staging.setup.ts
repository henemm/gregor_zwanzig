import { test as setup, expect } from '@playwright/test';
import { assertNotProdBaseURL } from './prodUrlGuard';
import type { APIRequestContext } from '@playwright/test';

// Staging-Auth für Bündel I (#970/#971) via API (Wegwerf-Testnutzer, keine echten
// Secrets). Einmaliger Register+Login im setup-Projekt → storageState; Tests laufen
// vorauthentifiziert (vermeidet Auth-Rate-Limit bei parallelen UI-Logins).
//
// ZWEI unabhängige Auth-Schichten (Bündel-H-Erfahrung):
//   1. nginx-Basic-Auth vor Staging  → httpCredentials (GZ_VALIDATOR_USER/PASS)
//   2. App-Login (gz_session-Cookie) → /api/auth/login mit Wegwerf-Nutzer
// Beide MÜSSEN im request-Context gesetzt sein, sonst nginx-401 vor dem App-Login.
//
// Robust gegen Login-Rate-Limit (#703): bei HTTP 429 wird der Retry-After-Header
// respektiert und mehrfach nachgefasst. Register nur bei echtem 401 (User fehlt),
// nicht bei 429 — sonst verlängert jeder Auth-Hit das gleitende Limit-Fenster.
const authFile = 'playwright/.auth/staging-bundle-i.json';
const E2E_USER = 'bundle-i-e2e-user';
const E2E_PASS = 'bundleI-e2e-pass-2026!';

function sleep(ms: number) {
	return new Promise((r) => setTimeout(r, ms));
}

async function tryLogin(ctx: APIRequestContext) {
	return ctx.post('/api/auth/login', { data: { username: E2E_USER, password: E2E_PASS } });
}

setup('register + authenticate via API (staging) — Bündel I', async ({ playwright }) => {
	setup.setTimeout(420_000);
	const base = process.env.GZ_SVELTE_BASE ?? 'https://staging.gregor20.henemm.com';
	assertNotProdBaseURL(base);
	const nginxUser = process.env.GZ_VALIDATOR_USER ?? process.env.E2E_USER ?? 'admin';
	const nginxPass = process.env.GZ_VALIDATOR_PASS ?? process.env.E2E_PASS ?? 'test1234';
	const ctx = await playwright.request.newContext({
		baseURL: base,
		ignoreHTTPSErrors: true,
		httpCredentials: { username: nginxUser, password: nginxPass }
	});

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

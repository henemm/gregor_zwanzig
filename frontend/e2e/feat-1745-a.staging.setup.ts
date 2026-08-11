import { test as setup, expect } from '@playwright/test';
import { assertNotProdBaseURL } from './prodUrlGuard';
import * as fs from 'fs';
// Staging-Auth-Setup fuer Issue #1745 Scheibe A (Premium-SMS als vierter
// Alarm-Kanal). Muster: feat-1461-s3b2b.staging.setup.ts — API-Login (kein
// Formular-Login, vermeidet den /api/auth/login-Rate-Limiter bei
// Mehrfachlaeufen), nginx-Basic-Auth (GZ_VALIDATOR_*) getrennt vom
// App-Login (GZ_AUTH_*).
//
// 🔴 App-Zugangsdaten fuer Staging stehen in /home/hem/gregor_zwanzig_staging/.env,
// NICHT in der .env des Arbeitsordners (CLAUDE.md „DREI Quellen").
const authFile = 'playwright/.auth/staging-1745-a.json';

setup('authenticate via API (staging) — fix_1745_a', async ({ playwright }) => {
	const base = process.env.GZ_SVELTE_BASE ?? 'https://staging.gregor20.henemm.com';
	assertNotProdBaseURL(base);
	const validatorUser = process.env.GZ_VALIDATOR_USER!;
	const validatorPass = process.env.GZ_VALIDATOR_PASS!;
	const appUser = process.env.GZ_AUTH_USER!;
	const appPass = process.env.GZ_AUTH_PASS!;

	const ctx = await playwright.request.newContext({
		baseURL: base,
		ignoreHTTPSErrors: true,
		httpCredentials: { username: validatorUser, password: validatorPass }
	});
	const res = await ctx.post('/api/auth/login', {
		data: { username: appUser, password: appPass }
	});
	expect(res.ok(), `login HTTP ${res.status()}`).toBeTruthy();

	await ctx.storageState({ path: authFile });
	await ctx.dispose();
	fs.chmodSync(authFile, 0o600);
});

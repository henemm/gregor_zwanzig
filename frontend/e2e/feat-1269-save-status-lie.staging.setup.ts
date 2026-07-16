import { test as setup, expect } from '@playwright/test';
import { assertNotProdBaseURL } from './prodUrlGuard';
import * as fs from 'fs';
// Staging-Auth für Issue #1269 (Speicher-Status-Anzeige lügt). Analog
// feat-1234.staging.setup.ts: nginx-Basic-Auth = GZ_VALIDATOR_*, App-Login
// separat via Setup-Projekt = GZ_AUTH_* (getrennte Layer). Alle Tests dieser
// Datei teilen sich den storageState statt sich pro Test einzuloggen — sonst
// erschöpft die Suite das Staging-Login-Rate-Limit (#703).
const authFile = 'playwright/.auth/staging-1269.json';

setup('authenticate via API (staging) — issue_1269_save_status_lie', async ({ playwright }) => {
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

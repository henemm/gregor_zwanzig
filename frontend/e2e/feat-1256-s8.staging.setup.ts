import { test as setup, expect } from '@playwright/test';
import * as fs from 'fs';
// Staging-Auth für Issue #1256 Scheibe 8 (Mobile-Vervollständigung Orts-
// Vergleich, AC-21–AC-24). Analog feat-1256-s7.staging.setup.ts: nginx-
// Basic-Auth = GZ_VALIDATOR_*, App-Login = GZ_AUTH_* (getrennte Layer).
const authFile = 'playwright/.auth/staging-1256-s8.json';

setup('authenticate via API (staging) — feat_1256_s8_mobile', async ({ playwright }) => {
	const base = process.env.GZ_SVELTE_BASE ?? 'https://staging.gregor20.henemm.com';
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

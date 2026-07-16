import { test as setup, expect } from '@playwright/test';
import { assertNotProdBaseURL } from './prodUrlGuard';
import * as fs from 'fs';
// Staging-Auth fuer Issue #1258 Scheibe S4 (Compare-Editor-Integration).
// nginx-Basic-Auth = GZ_VALIDATOR_*, App-Login = GZ_AUTH_* (getrennte Layer).
// Kein Seed hier — Presets/Locations werden inline je Test angelegt und
// aufgeraeumt (Muster compare-alarm-config.spec.ts / compare-flow-navigation.spec.ts).
const authFile = 'playwright/.auth/staging-1258-s4.json';

setup('authenticate via API (staging) — feat_1258_s4_compare_editor', async ({ playwright }) => {
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

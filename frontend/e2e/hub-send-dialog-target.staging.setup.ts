import { test as setup, expect } from '@playwright/test';
import { fileURLToPath } from 'node:url';
import { assertNotProdBaseURL } from './prodUrlGuard';
// Staging-Validierung Issue #2347 S2 (vormals #1471) — geteilter Sende-Dialog nennt
// das tatsaechliche Ziel, fuer Trip UND Ortsvergleich (hub-send-dialog-target.staging.spec.ts).
// Umbenannt aus compare-send-dialog-target.staging.setup.ts: EIN API-Login, storageState
// geteilt ueber alle Tests dieser Datei (Login-Rate-Limit #703). Pfad unveraendert.
const authFile = fileURLToPath(new URL('./playwright/.auth/staging-1471.json', import.meta.url));

setup('authenticate via API (staging) — hub_send_dialog_target', async ({ playwright }) => {
	const base = process.env.GZ_SVELTE_BASE ?? 'https://staging.gregor20.henemm.com';
	assertNotProdBaseURL(base);
	const nginxUser = process.env.GZ_VALIDATOR_USER ?? 'admin';
	const nginxPass = process.env.GZ_VALIDATOR_PASS ?? 'test1234';
	const appUser = process.env.GZ_AUTH_USER ?? process.env.E2E_USER ?? 'admin';
	const appPass = process.env.GZ_AUTH_PASS ?? process.env.E2E_PASS ?? 'test1234';

	const ctx = await playwright.request.newContext({
		baseURL: base,
		ignoreHTTPSErrors: true,
		httpCredentials: { username: nginxUser, password: nginxPass }
	});
	const res = await ctx.post('/api/auth/login', {
		data: { username: appUser, password: appPass }
	});
	expect(res.ok(), `login HTTP ${res.status()}`).toBeTruthy();
	await ctx.storageState({ path: authFile });
	await ctx.dispose();
});

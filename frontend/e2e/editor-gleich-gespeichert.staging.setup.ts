import { test as setup, expect } from '@playwright/test';
import { assertNotProdBaseURL } from './prodUrlGuard';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
// Staging-Auth für Issue #2422 Scheibe S2a (AC-10/AC-11/AC-17: B9-/K8-Fix,
// Editor-Anzeige = gespeicherter Stand bei Kaskadenquelle 'global').
// Vorbild: metrik-abwahl-schreibt-alle-kanaele-durch.staging.setup.ts (#1719 S3).
const __dirname = path.dirname(fileURLToPath(import.meta.url));
const authFile = path.join(__dirname, 'playwright', '.auth', 'staging-2422-s2a-editor.json');

setup('authenticate via API (staging) — 2422_s2a_editor_gleich_gespeichert', async ({ playwright }) => {
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

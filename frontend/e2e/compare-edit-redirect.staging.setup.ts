import { test as setup, expect } from '@playwright/test';
import { assertNotProdBaseURL } from './prodUrlGuard';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
// Staging-Auth für Epic #1273 Slice S3 (Compare-Edit-Route wird reiner Redirect).
// Analog compare-hub-name-region-profil.staging.setup.ts: nginx-Basic-Auth
// (Validator-Creds) UND App-Login (gz_session-Cookie via GZ_AUTH_*) sind
// getrennte Credential-Paare. Alle Tests dieser Slice teilen sich EINEN
// storageState statt sich pro Test einzuloggen — sonst erschöpft die Suite das
// Staging-Login-Rate-Limit (#703). Eigener storageState-Pfad (staging-1273-s3.json)
// für Test-Isolation gegenüber S2.
const __dirname = path.dirname(fileURLToPath(import.meta.url));
const authFile = path.join(__dirname, 'playwright', '.auth', 'staging-1273-s3.json');

setup('authenticate via API (staging) — epic_1273_s3_compare_edit_redirect', async ({
	playwright
}) => {
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

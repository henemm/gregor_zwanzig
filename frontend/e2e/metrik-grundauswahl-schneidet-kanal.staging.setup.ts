import { test as setup, expect } from '@playwright/test';
import { assertNotProdBaseURL } from './prodUrlGuard';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
// Staging-Auth für Issue #1719 Scheibe 2 AC-10 Test B. Analog
// compare-hub-save-chip.staging.setup.ts: nginx-Basic-Auth (Validator-Creds)
// UND App-Login (gz_session-Cookie via GZ_AUTH_*) sind getrennte
// Credential-Paare (s. reference_staging_app_login_creds_live_in_staging_env
// bei Staging-Ziel). Ein storageState statt Login pro Test — sonst erschöpft
// die Suite das Staging-Login-Rate-Limit (#703).
const __dirname = path.dirname(fileURLToPath(import.meta.url));
const authFile = path.join(__dirname, 'playwright', '.auth', 'staging-1719-s2.json');

setup('authenticate via API (staging) — issue_1719_s2_kaskade_verfeinerung', async ({
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

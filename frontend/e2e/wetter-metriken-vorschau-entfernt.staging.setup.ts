import { test as setup, expect } from '@playwright/test';
import { assertNotProdBaseURL } from './prodUrlGuard';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
// Staging-Auth für Issue #1719 Scheibe 3 (AC-1/AC-2 — Live-Vorschau entfernt).
// Vorbild: metrik-grundauswahl-schneidet-kanal.staging.setup.ts (S2). nginx-
// Basic-Auth (Validator-Creds) UND App-Login (gz_session-Cookie via
// GZ_AUTH_*) sind getrennte Credential-Paare (s.
// reference_staging_app_login_creds_live_in_staging_env). Ein storageState
// statt Login pro Test — sonst erschöpft die Suite das Staging-
// Login-Rate-Limit (#703).
const __dirname = path.dirname(fileURLToPath(import.meta.url));
const authFile = path.join(__dirname, 'playwright', '.auth', 'staging-1719-s3-vorschau.json');

setup('authenticate via API (staging) — 1719_s3_vorschau_entfernt', async ({ playwright }) => {
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

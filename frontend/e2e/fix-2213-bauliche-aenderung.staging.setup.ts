import { test as setup, expect } from '@playwright/test';
import { assertNotProdBaseURL } from './prodUrlGuard';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
// Staging-Auth fuer #2213 (bauliche Etappen-Aenderungen sofort speichern).
// Vorbild: fix-1895-modus-rueckbau.staging.setup.ts.
const __dirname = path.dirname(fileURLToPath(import.meta.url));
const authFile = path.join(__dirname, 'playwright', '.auth', 'staging-2213.json');

setup('authenticate via API (staging) — 2213_bauliche_aenderung', async ({ playwright }) => {
	// Helfer-Konto des Staging-Betriebs (GZ_AUTH_USER/GZ_AUTH_PASS), nie die Projekt-.env.
	try { process.loadEnvFile('/home/hem/gregor_zwanzig_staging/.env'); } catch { /* fehlt: Fallbacks */ }
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

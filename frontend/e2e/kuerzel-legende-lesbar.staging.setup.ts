import { test as setup, expect } from '@playwright/test';
import { assertNotProdBaseURL } from './prodUrlGuard';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
// Staging-Auth fuer Issue #1888 (Kuerzel-Legende, AC-6/AC-7). Wie
// kuerzel-marken-sichtbar.staging.setup.ts: nginx-Basic-Auth (GZ_VALIDATOR_*)
// und App-Login (GZ_AUTH_*) sind ZWEI getrennte Credential-Paare, beide
// ausschliesslich aus der Umgebung — nie im Klartext in dieser Datei. Ein
// storageState statt Login je Test, sonst erschoepfen 8 Breiten x 2 Flaechen
// das Staging-Login-Rate-Limit (#703).
const __dirname = path.dirname(fileURLToPath(import.meta.url));
const authFile = path.join(__dirname, 'playwright', '.auth', 'staging-1888-legende.json');

setup('authenticate via API (staging) — issue_1888_kuerzel_legende', async ({ playwright }) => {
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

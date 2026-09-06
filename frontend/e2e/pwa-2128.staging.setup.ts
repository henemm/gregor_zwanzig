import { test as setup, expect } from '@playwright/test';
import { assertNotProdBaseURL } from './prodUrlGuard';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
// Staging-Anmeldung fuer Issue #2128 (PWA-Nachweis gegen Staging).
// Vorbild: issue-1080.staging.setup.ts.
//
// Staging hat ZWEI Schichten mit UNTERSCHIEDLICHEN Zugangsdaten:
//   1. nginx-Basic-Auth davor  -> GZ_VALIDATOR_USER / GZ_VALIDATOR_PASS
//   2. App-Login dahinter      -> GZ_AUTH_USER / GZ_AUTH_PASS (gz_session-Cookie)
// Siehe docs/reference/operations_playbook.md. Wer beide verwechselt, bekommt
// 401 an der falschen Schicht.
//
// Absoluter Pfad via __dirname statt String-Literal, damit Setup und Config
// unabhaengig vom Arbeitsordner exakt dieselbe Datei meinen.
const __dirname = path.dirname(fileURLToPath(import.meta.url));
const authFile = path.join(__dirname, 'playwright', '.auth', 'staging-2128.json');

setup('authenticate via API (staging) — issue_2128 PWA', async ({ playwright }) => {
	const base = process.env.GZ_SVELTE_BASE ?? 'https://staging.gregor20.henemm.com';
	// Issue #1265: kein E2E-Lauf gegen Produktion.
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

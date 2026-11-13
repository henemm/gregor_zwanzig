import { test as setup, expect } from '@playwright/test';
import { assertNotProdBaseURL } from './prodUrlGuard';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { ausUmgebung } from './stagingZugang';
// Staging-Auth fuer #1895 Schritt 1 (Rueckbau der Modus-Auswahl im
// Alarmregel-Editor). Vorbild: kanal-abwahl-bleibt-reversibel.staging.setup.ts.
const __dirname = path.dirname(fileURLToPath(import.meta.url));
const authFile = path.join(__dirname, 'playwright', '.auth', 'staging-1895.json');

setup('authenticate via API (staging) — 1895_modus_rueckbau', async ({ playwright }) => {
	const base = process.env.GZ_SVELTE_BASE ?? 'https://staging.gregor20.henemm.com';
	assertNotProdBaseURL(base);
	const nginxUser = ausUmgebung('GZ_VALIDATOR_USER');
	const nginxPass = ausUmgebung('GZ_VALIDATOR_PASS');
	const appUser = ausUmgebung('GZ_AUTH_USER', 'E2E_USER');
	const appPass = ausUmgebung('GZ_AUTH_PASS', 'E2E_PASS');

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

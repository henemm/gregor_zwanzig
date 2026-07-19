import { test as setup, expect } from '@playwright/test';
import { assertNotProdBaseURL } from './prodUrlGuard';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import * as fs from 'fs';
// Staging-Auth für Epic #1273 Slice S4c (E2E-Migration Compare-Hub/Wizard).
// Analog compare-edit-redirect.staging.setup.ts: nginx-Basic-Auth
// (GZ_VALIDATOR_*) UND App-Login (gz_session via GZ_AUTH_*) sind getrennte
// Credential-Paare. Die storageState-basierten Tests dieser Slice teilen sich
// EINEN storageState statt sich pro Test einzuloggen — sonst erschöpft die Suite
// das Staging-Login-Rate-Limit (#703). Eigener Pfad zur Isolation gegenüber S3.
const __dirname = path.dirname(fileURLToPath(import.meta.url));
const authFile = path.join(__dirname, 'playwright', '.auth', 'staging-1273-s4c.json');

setup('authenticate via API (staging) — epic_1273_s4c_e2e_migration', async ({ playwright }) => {
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
	fs.chmodSync(authFile, 0o600);
});

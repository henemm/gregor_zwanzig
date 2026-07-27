import { test as setup, expect } from '@playwright/test';
import { assertNotProdBaseURL } from './prodUrlGuard';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

// Staging-Auth fuer die Nachpruefung von Issue #1395 Scheibe S3
// (Frontend fuehrt den Aenderungsstempel: ETag-Registry + If-Match).
//
// Zwei getrennte Credential-Paare, wie bei allen *.staging.setup.ts:
//   - nginx-Basic-Auth  -> GZ_VALIDATOR_USER / GZ_VALIDATOR_PASS (httpCredentials)
//   - App-Login         -> GZ_AUTH_USER / GZ_AUTH_PASS (gz_session-Cookie)
//
// Genau EIN Login fuer die ganze Datei (gemeinsamer storageState) — das
// Staging-Login-Rate-Limit liegt bei 30/h (#703). storageState landet unter
// frontend/e2e/playwright/.auth/ (gitignored), niemals in /tmp (#199).

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const authFile = path.join(__dirname, 'playwright', '.auth', 'staging-1395-s3.json');

setup('authenticate via API (staging) — feat_1395_s3_etag_ifmatch', async ({ playwright }) => {
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

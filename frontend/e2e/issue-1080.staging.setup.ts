import { test as setup, expect } from '@playwright/test';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
// Staging-Auth für issue_1080 (compare/new: Ort per URL hinzufügen bleibt unsichtbar).
// Analog issue-1059.staging.setup.ts (aktuelleres Vorbild als issue-953: getrennte
// Credential-Paare). Staging steht hinter nginx-Basic-Auth (Validator-Creds) UND einem
// App-Login (gz_session-Cookie, eigene GZ_AUTH_*-Creds) — beide werden hier gesetzt.
//
// Abweichung vom 953-Vorbild: Diese Datei UND die zugehörige Config liegen (Edit-Gate,
// s. playwright.1080.staging.config.ts) beide unter frontend/e2e/. Absoluter Pfad via
// __dirname statt String-Literal, damit Setup und Config unabhängig vom CWD exakt
// dieselbe Datei referenzieren.
const __dirname = path.dirname(fileURLToPath(import.meta.url));
const authFile = path.join(__dirname, 'playwright', '.auth', 'staging-1080.json');

setup('authenticate via API (staging) — issue_1080', async ({ playwright }) => {
	const base = process.env.GZ_SVELTE_BASE ?? 'https://staging.gregor20.henemm.com';
	// nginx-Basic-Auth (Validator-Creds) und App-Login (GZ_AUTH_*) sind unterschiedliche
	// Credential-Paare — siehe docs/reference/operations_playbook.md.
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

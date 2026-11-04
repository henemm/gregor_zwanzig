import { test as setup, expect } from '@playwright/test';
import { assertNotProdBaseURL } from './prodUrlGuard';
import * as fs from 'fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
// Staging-Anmeldung für das Bündel kanal-je-wettergroesse-block (#1895 S3b1).
// Muster: compare-uebersicht-kanal.staging.setup.ts. Zwei getrennte Schichten:
// nginx-Schranke = GZ_VALIDATOR_*, Anwendung = GZ_AUTH_* (Staging-.env).
// Die Test-Objekte (Trip, Ortsvergleich, Orte) legt die Spec selbst an und räumt
// sie selbst ab (registerForCleanup/cleanupTracked bzw. finally).
const __dirname = path.dirname(fileURLToPath(import.meta.url));
const authFile = path.join(__dirname, 'playwright', '.auth', 'staging-1895-s3b1-kanal-block.json');

setup('authenticate via API (staging) — 1895_s3b1_kanal_je_wettergroesse_block', async ({ playwright }) => {
	const base = process.env.GZ_SVELTE_BASE ?? 'https://staging.gregor20.henemm.com';
	assertNotProdBaseURL(base);
	const ctx = await playwright.request.newContext({
		baseURL: base,
		ignoreHTTPSErrors: true,
		httpCredentials: { username: process.env.GZ_VALIDATOR_USER!, password: process.env.GZ_VALIDATOR_PASS! }
	});
	const res = await ctx.post('/api/auth/login', {
		data: { username: process.env.GZ_AUTH_USER!, password: process.env.GZ_AUTH_PASS! }
	});
	expect(res.ok(), `login HTTP ${res.status()}`).toBeTruthy();
	await ctx.storageState({ path: authFile });
	await ctx.dispose();
	// Session-Token nie weltlesbar ablegen (henemm-security #199).
	fs.chmodSync(authFile, 0o600);
});

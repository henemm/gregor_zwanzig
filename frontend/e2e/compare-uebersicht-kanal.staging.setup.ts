import { test as setup, expect } from '@playwright/test';
import { assertNotProdBaseURL } from './prodUrlGuard';
import * as fs from 'fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
// Staging-Anmeldung fuer beide #1703-S8-Klickpfad-Buendel (Uebersicht,
// Kanal-Reiter). Muster: compare-outlook-metric-selection.staging.setup.ts.
//
// 🔴 ZWEI getrennte Schichten, DREI Quellen (CLAUDE.md): die nginx-Schranke
// nimmt GZ_VALIDATOR_* (.claude/validator.env), die ANWENDUNG nimmt GZ_AUTH_*
// — auf Staging aus /home/hem/gregor_zwanzig_staging/.env, gleicher Benutzer,
// ANDERES Passwort als die Arbeitsordner-.env. Keine Vorgabewerte im Code:
// ein stiller Rueckfall auf falsche Zugangsdaten sieht aus wie ein Produktfehler.
const __dirname = path.dirname(fileURLToPath(import.meta.url));
const authFile = path.join(__dirname, 'playwright', '.auth', 'staging-1703-s8-kanal.json');

setup('authenticate via API (staging) — 1703_s8_compare_uebersicht_kanal', async ({ playwright }) => {
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

import { test as setup, expect } from '@playwright/test';
import { assertNotProdBaseURL } from './prodUrlGuard';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
// Staging-Auth fuer Issue #2155 S4: ZWEI Anmeldezustaende (Zwei-Nutzer-Test).
//  - Admin: Konto `gz-staging-admin`, Zugangsdaten aus GZ_STAGING_ADMIN_USER/_PASS
//    oder .claude/staging_admin.env (gitignoriert, nie im Klartext im Repo).
//  - Nicht-Admin: GZ_AUTH_USER/E2E_USER — das Setup bricht ab, falls dieses Konto
//    doch Admin ist (sonst waere der Zugriffsschutz-Test vakuum).
// nginx-Basic-Auth (GZ_VALIDATOR_*) und App-Login sind getrennte Credential-Paare.
const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ADMIN_STATE = path.join(__dirname, 'playwright', '.auth', 'staging-2155-s4-admin.json');
const USER_STATE = path.join(__dirname, 'playwright', '.auth', 'staging-2155-s4-user.json');

function adminCredentials(): { user: string; pass: string } {
	let user = process.env.GZ_STAGING_ADMIN_USER;
	let pass = process.env.GZ_STAGING_ADMIN_PASS;
	if (!user || !pass) {
		const datei = '/home/hem/gregor_zwanzig/.claude/staging_admin.env';
		for (const zeile of readFileSync(datei, 'utf8').split('\n')) {
			const m = zeile.trim().replace(/^export\s+/, '').match(/^(\w+)=(.*)$/);
			if (m?.[1] === 'GZ_STAGING_ADMIN_USER') user = m[2].replace(/^["']|["']$/g, '');
			if (m?.[1] === 'GZ_STAGING_ADMIN_PASS') pass = m[2].replace(/^["']|["']$/g, '');
		}
	}
	if (!user || !pass) throw new Error('Staging-Admin-Zugangsdaten fehlen (GZ_STAGING_ADMIN_*)');
	return { user, pass };
}

setup('Anmeldung Admin und Nicht-Admin (staging) — admin_ui_s4', async ({ playwright }) => {
	const base = process.env.GZ_SVELTE_BASE ?? 'https://staging.gregor20.henemm.com';
	assertNotProdBaseURL(base);
	const httpCredentials = {
		username: process.env.GZ_VALIDATOR_USER ?? 'admin',
		password: process.env.GZ_VALIDATOR_PASS ?? 'test1234'
	};
	const admin = adminCredentials();
	const normal = {
		user: process.env.GZ_AUTH_USER ?? process.env.E2E_USER ?? 'admin',
		pass: process.env.GZ_AUTH_PASS ?? process.env.E2E_PASS ?? 'test1234'
	};

	for (const [k, konto, datei, rolle] of [
		['Admin', admin, ADMIN_STATE, 'admin'],
		['Nicht-Admin', normal, USER_STATE, 'user']
	] as const) {
		const ctx = await playwright.request.newContext({
			baseURL: base, ignoreHTTPSErrors: true, httpCredentials
		});
		const res = await ctx.post('/api/auth/login', {
			data: { username: konto.user, password: konto.pass }
		});
		expect(res.ok(), `${k}: Login HTTP ${res.status()}`).toBeTruthy();
		const profil = await (await ctx.get('/api/auth/profile')).json();
		if (rolle === 'admin') {
			expect(profil.role, `${k}: Konto ist kein Admin`).toBe('admin');
		} else {
			expect(profil.role, `${k}: Konto ist Admin — kein Nicht-Admin-Beleg moeglich`).not.toBe('admin');
		}
		await ctx.storageState({ path: datei });
		await ctx.dispose();
	}
});

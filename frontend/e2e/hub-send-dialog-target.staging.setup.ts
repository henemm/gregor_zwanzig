import { test as setup, expect } from '@playwright/test';
import { writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { assertNotProdBaseURL } from './prodUrlGuard';
// Staging-Validierung Issue #2347 S2 (vormals #1471) — geteilter Sende-Dialog nennt
// das tatsaechliche Ziel, fuer Trip UND Ortsvergleich (hub-send-dialog-target.staging.spec.ts).
// Umbenannt aus dem früheren Compare-only-Setup (#1471). Pfad unveraendert.
//
// Fix-Loop 1 (F005): Die Sperre von „Senden" haengt am KONTO (keine/unbestaetigte
// Adresse, sendTargetLabel.ts), nicht am Objekt. Das Staging-Validatorkonto hat eine
// bestaetigte Adresse ⇒ ein WEGWERF-Nutzer: registrieren (gregor-test+…@henemm.com,
// eigenes Test-Postfach), ueber den Staging-Testweg bestaetigen (die angemeldete
// Validator-Sitzung holt das Token, Muster helpers.registriereBestaetigtenZweitnutzer),
// anmelden, dann beide Adressfelder leeren (auth.go: beide leer ⇒ direkt, ohne
// Bestaetigung). Der Validator-Account bleibt unberuehrt. Kennung + Kennwort liegen
// mit 0600 neben dem storageState; die Spec loescht das Konto in `afterAll`.
const authFile = fileURLToPath(new URL('./playwright/.auth/staging-1471.json', import.meta.url));
export const WEGWERF_DATEI = authFile.replace(/\.json$/, '.wegwerf.json');

setup('authenticate via API (staging) — hub_send_dialog_target', async ({ playwright }) => {
	const base = process.env.GZ_SVELTE_BASE ?? 'https://staging.gregor20.henemm.com';
	assertNotProdBaseURL(base);
	const nginxUser = process.env.GZ_VALIDATOR_USER ?? 'admin';
	const nginxPass = process.env.GZ_VALIDATOR_PASS ?? 'test1234';
	const appUser = process.env.GZ_AUTH_USER ?? process.env.E2E_USER ?? 'admin';
	const appPass = process.env.GZ_AUTH_PASS ?? process.env.E2E_PASS ?? 'test1234';
	const neu = () =>
		playwright.request.newContext({
			baseURL: base,
			ignoreHTTPSErrors: true,
			httpCredentials: { username: nginxUser, password: nginxPass }
		});

	const validator = await neu();
	const gast = await neu();
	try {
		const login = await validator.post('/api/auth/login', { data: { username: appUser, password: appPass } });
		expect(login.ok(), `Validator-Login HTTP ${login.status()}`).toBeTruthy();

		const suffix = `${Date.now()}`;
		const username = `e2egzsd${suffix}`;
		const kennwort = `Sd-${suffix}-x!`;
		const reg = await gast.post('/api/auth/register', {
			data: { username, password: kennwort, email: `gregor-test+sd${suffix}@henemm.com` }
		});
		expect([200, 201], `Registrierung HTTP ${reg.status()}`).toContain(reg.status());
		writeFileSync(WEGWERF_DATEI, JSON.stringify({ username, kennwort }), { mode: 0o600 });

		const tok = await validator.post('/api/auth/verify-email/staging-token', { data: { username } });
		expect(tok.ok(), `Staging-Token HTTP ${tok.status()}`).toBeTruthy();
		const { token } = (await tok.json()) as { token?: string };
		expect(token, 'Staging-Testweg lieferte kein Token').toBeTruthy();
		const best = await gast.post('/api/auth/verify-email', { data: { user: username, token } });
		expect(best.ok(), `Bestaetigung HTTP ${best.status()}`).toBeTruthy();

		const gastLogin = await gast.post('/api/auth/login', { data: { username, password: kennwort } });
		expect(gastLogin.ok(), `Wegwerf-Login HTTP ${gastLogin.status()}`).toBeTruthy();
		const leer = await gast.put('/api/auth/profile', { data: { email: '', mail_to: '' } });
		expect(leer.ok(), `Adressen leeren HTTP ${leer.status()}`).toBeTruthy();

		await gast.storageState({ path: authFile });
	} finally {
		await validator.dispose();
		await gast.dispose();
	}
});

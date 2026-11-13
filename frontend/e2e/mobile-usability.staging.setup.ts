// Setup für den Mobile-Usability-Audit (staging): App-Login via API, damit
// die Audit-Spec mit storageState läuft statt per UI-Login (vermeidet
// Auth-Rate-Limits und den CSRF-403 auf /login). Muster: issue-661.staging.setup.ts.

import { test as setup, expect } from '@playwright/test';
import { assertNotProdBaseURL } from './prodUrlGuard';
import { ausUmgebung } from './stagingZugang';

const authFile = 'playwright/.auth/staging-mobile-usability.json';

setup('authenticate via API (staging)', async ({ playwright }) => {
	const base = 'https://staging.gregor20.henemm.com';
	assertNotProdBaseURL(base);
	// nginx-Basic-Auth (Validator-Creds) kommt über httpCredentials in der
	// Config on top; der Login-Body braucht das stabile App-Konto.
	const user = ausUmgebung('GZ_VALIDATOR_USER', 'E2E_USER');
	const pass = ausUmgebung('GZ_VALIDATOR_PASS', 'E2E_PASS');
	// App-Konto: mobile-audit (realer Testdaten-Bestand, vgl. Setup in
	// docs/Workspaces). Das Passwort kommt aus GZ_MOBILE_AUDIT_PASS (#2961:
	// kein Passwort im Quelltext).
	const authUser = process.env.GZ_MOBILE_AUDIT_USER ?? 'mobile-audit';
	const authPass = ausUmgebung('GZ_MOBILE_AUDIT_PASS');
	const ctx = await playwright.request.newContext({
		baseURL: base,
		ignoreHTTPSErrors: true,
		httpCredentials: { username: user, password: pass },
	});
	const res = await ctx.post('/api/auth/login', {
		data: { username: authUser, password: authPass },
	});
	expect(res.ok(), `login HTTP ${res.status()}: ${await res.text()}`).toBeTruthy();
	await ctx.storageState({ path: authFile });
	await ctx.dispose();
});

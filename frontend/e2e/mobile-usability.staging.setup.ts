// Setup für den Mobile-Usability-Audit (staging): App-Login via API, damit
// die Audit-Spec mit storageState läuft statt per UI-Login (vermeidet
// Auth-Rate-Limits und den CSRF-403 auf /login). Muster: issue-661.staging.setup.ts.

import { test as setup, expect } from '@playwright/test';
import { assertNotProdBaseURL } from './prodUrlGuard';
import { resolveE2EUser } from './testUser.ts';

const authFile = 'playwright/.auth/staging-mobile-usability.json';

setup('authenticate via API (staging)', async ({ playwright }) => {
	const base = 'https://staging.gregor20.henemm.com';
	assertNotProdBaseURL(base);
	// nginx-Basic-Auth (Validator-Creds) kommt über httpCredentials in der
	// Config on top; der Login-Body braucht das stabile App-Konto.
	const user = process.env.GZ_VALIDATOR_USER ?? process.env.E2E_USER ?? 'admin';
	const pass = process.env.GZ_VALIDATOR_PASS ?? process.env.E2E_PASS ?? 'test1234';
	// App-Konto: mobile-audit (realer Testdaten-Bestand, vgl. Setup in
	// docs/Workspaces). GZ_MOBILE_AUDIT_* erlaubt ein abweichendes Passwort,
	// Default ist das bewusst feste Testpasswort des Staging-Nutzers.
	const fallback = resolveE2EUser();
	const authUser = process.env.GZ_MOBILE_AUDIT_USER ?? 'mobile-audit';
	const authPass = process.env.GZ_MOBILE_AUDIT_PASS ?? (fallback.pass === 'test1234' ? 'MobileAudit2026!' : fallback.pass);
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

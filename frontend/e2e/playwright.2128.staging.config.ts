import { defineConfig } from '@playwright/test';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
// E2E-Config fuer Issue #2128 (PWA: installierbar, ohne Netz startfaehig,
// Update erst auf Antippen) gegen STAGING. Kein lokaler webServer — geprueft
// wird der wirklich ausgelieferte Stand.
//
// Deckt genau die vier im Issue #2128 unter "Nachweis" geforderten Punkte ab
// (Manifest + registrierter Worker, Offline-Seite ohne Netz, Schriften ohne
// Fremdaufruf, Update-Hinweis wird erst auf Klick aktiv) -- NICHT die 24 ACs
// der lokalen Strecke. Die laufen in der CI (`--project=pwa`, ci.yml).
//
// Diese Datei laeuft NICHT in der CI: .staging.spec.ts ist dort ausgeschlossen
// (Filter A der e2e-Ratsche). Aufruf in /e2e-verify:
//   cd frontend && npx playwright test -c e2e/playwright.2128.staging.config.ts
//
// Ablageort UNTER frontend/e2e/ (nicht frontend/ root) wie beim Vorbild
// playwright.1080.staging.config.ts: der RED-Phasen-Edit-Gate blockt
// Code-Dateien ausserhalb der always_allowed_dirs (u.a. "e2e/"). `testDir: '.'`
// loest relativ zu DIESER Datei auf.
//
// Kein `globalTeardown` (Abweichung vom 1080-Vorbild, bewusst): diese Strecke
// legt keinerlei Daten an -- kein Ort, kein Trip, kein Preset. Der Raeumlauf
// wuerde nur die `E2E-GZ-`-Objekte einer moeglicherweise parallel laufenden
// Staging-Strecke loeschen, ohne hier etwas aufzuraeumen.
const __dirname = path.dirname(fileURLToPath(import.meta.url));
// Zwei Anmeldeschichten: nginx-Basic-Auth (Validator-Creds) davor, App-Login
// (gz_session-Cookie, GZ_AUTH_*) dahinter -- siehe pwa-2128.staging.setup.ts.
const nginxUser = process.env.GZ_VALIDATOR_USER ?? process.env.E2E_USER ?? 'admin';
const nginxPass = process.env.GZ_VALIDATOR_PASS ?? process.env.E2E_PASS ?? 'test1234';

export default defineConfig({
	testDir: '.',
	// Staging antwortet langsamer als der lokale Vorschauserver, und die
	// Worker-Aktivierung (install -> activate -> claim) kommt oben drauf.
	timeout: 90_000,
	retries: 0,
	// Die PWA-Nachweise brauchen einen ECHTEN Service Worker -- ohne
	// `serviceWorkers: 'allow'` misst diese Strecke nichts.
	use: {
		baseURL: process.env.GZ_SVELTE_BASE ?? 'https://staging.gregor20.henemm.com',
		headless: true,
		ignoreHTTPSErrors: true,
		serviceWorkers: 'allow',
		httpCredentials: { username: nginxUser, password: nginxPass }
	},
	projects: [
		{ name: 'setup', testMatch: /pwa-2128\.staging\.setup\.ts/ },
		{
			name: 'tests',
			testMatch: /pwa-nachweis\.staging\.spec\.ts/,
			dependencies: ['setup'],
			use: {
				storageState: path.join(__dirname, 'playwright', '.auth', 'staging-2128.json')
			}
		}
	]
});

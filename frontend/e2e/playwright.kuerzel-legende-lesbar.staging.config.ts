import { defineConfig } from '@playwright/test';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { ausUmgebung } from './stagingZugang';
// E2E-Config Issue #1888 (E6 Scheibe B, AC-6/AC-7): die Kuerzel-Legende bleibt
// zwischen 320 und 899 px vollstaendig lesbar und haelt WCAG AA.
// Kein lokaler webServer — geprueft wird die auf Staging deployte App selbst.
// Staging steht hinter nginx-Basic-Auth (GZ_VALIDATOR_*) + App-Login (GZ_AUTH_*).
//
// Liegt bewusst UNTER frontend/e2e/ (nicht frontend/ root); `testDir: '.'`
// loest relativ zu dieser Datei auf.
const __dirname = path.dirname(fileURLToPath(import.meta.url));
const user = ausUmgebung('GZ_VALIDATOR_USER', 'E2E_USER');
const pass = ausUmgebung('GZ_VALIDATOR_PASS', 'E2E_PASS');

export default defineConfig({
	testDir: '.',
	timeout: 180_000,
	retries: 0,
	use: {
		baseURL: process.env.GZ_SVELTE_BASE ?? 'https://staging.gregor20.henemm.com',
		headless: true,
		ignoreHTTPSErrors: true,
		httpCredentials: { username: user, password: pass }
	},
	projects: [
		{ name: 'setup', testMatch: /kuerzel-legende-lesbar\.staging\.setup\.ts/ },
		{
			name: 'tests',
			testMatch: /kuerzel-legende-lesbar\.staging\.spec\.ts/,
			dependencies: ['setup'],
			use: {
				storageState: path.join(__dirname, 'playwright', '.auth', 'staging-1888-legende.json')
			}
		}
	]
});

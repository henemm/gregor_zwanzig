import { defineConfig } from '@playwright/test';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { ausUmgebung } from './stagingZugang';

// Staging-Nachpruefung Issue #1393 — „Ich aendere eine Etappe z.B. auf den 26.7.
// und erwarte, dass die folgende Etappe auf den 27.7. geaendert wird."
//
// Faehrt gegen die laufende Staging-Oberflaeche (GZ_SVELTE_BASE), NICHT gegen
// einen lokalen Preview-Server: kein webServer-Block, baseURL = Staging-Domain.
// Zwei Credential-Ebenen: nginx-Basic-Auth (httpCredentials) + App-Login
// (eigener storageState aus dem setup-Projekt, EIN Login fuer die ganze Datei,
// Rate-Limit-Bucket #703).

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const nginxUser = ausUmgebung('GZ_VALIDATOR_USER', 'E2E_USER');
const nginxPass = ausUmgebung('GZ_VALIDATOR_PASS', 'E2E_PASS');

export default defineConfig({
	testDir: '.',
	timeout: 180_000,
	retries: 0,
	workers: 1,
	reporter: [['list']],
	use: {
		baseURL: process.env.GZ_SVELTE_BASE ?? 'https://staging.gregor20.henemm.com',
		headless: true,
		ignoreHTTPSErrors: true,
		// Ohne diese Schranke wartet ein nicht klickbares Element UNENDLICH
		// (Playwright-Default actionTimeout = 0) — die Testschranke schlaegt dann
		// ohne verwertbare Begruendung zu. Mit Schranke nennt Playwright das
		// ueberdeckende Element.
		actionTimeout: 15_000,
		screenshot: 'only-on-failure',
		httpCredentials: { username: nginxUser, password: nginxPass }
	},
	projects: [
		{ name: 'setup', testMatch: /fix-1393-stage-cascade\.staging\.setup\.ts/ },
		{
			name: 'tests',
			testMatch: /fix-1393-stage-cascade\.staging\.spec\.ts/,
			dependencies: ['setup'],
			use: { storageState: path.join(__dirname, 'playwright', '.auth', 'staging-1393.json') }
		}
	]
});

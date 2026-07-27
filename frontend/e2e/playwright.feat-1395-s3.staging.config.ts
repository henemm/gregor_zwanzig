import { defineConfig } from '@playwright/test';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

// Staging-Nachpruefung Issue #1395 Scheibe S3 — „Das Frontend fuehrt den
// Aenderungsstempel". Umschaltpunkt: ab hier traegt jeder Schreibvorgang aus
// dem Editor `If-Match`, und ein veralteter Schreibvorgang wird erstmals
// wirklich mit 412 abgelehnt.
//
// Faehrt gegen die laufende Staging-Oberflaeche (GZ_SVELTE_BASE), NICHT gegen
// einen lokalen Preview-Server: kein webServer-Block, baseURL = Staging-Domain.
// Zwei Credential-Ebenen: nginx-Basic-Auth (httpCredentials) + App-Login
// (eigener storageState aus dem setup-Projekt, EIN Login fuer die ganze Datei,
// Rate-Limit-Bucket #703).
//
// Ausfuehren (aus frontend/):
//   set -a; source /home/hem/gregor_zwanzig/.claude/validator.env; set +a
//   export GZ_AUTH_USER=… GZ_AUTH_PASS=…   (aus dem Staging-.env)
//   npx playwright test --config=e2e/playwright.feat-1395-s3.staging.config.ts

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const nginxUser = process.env.GZ_VALIDATOR_USER ?? process.env.E2E_USER ?? 'admin';
const nginxPass = process.env.GZ_VALIDATOR_PASS ?? process.env.E2E_PASS ?? 'test1234';

export default defineConfig({
	testDir: '.',
	timeout: 180_000,
	retries: 0,
	// Serialisiert: die Faelle legen eigene Test-Touren an und raeumen sie wieder
	// ab; parallele Worker wuerden sich beim Aufraeum-Kontrollfall gegenseitig
	// Reste vorwerfen.
	workers: 1,
	reporter: [['list']],
	use: {
		baseURL: process.env.GZ_SVELTE_BASE ?? 'https://staging.gregor20.henemm.com',
		headless: true,
		ignoreHTTPSErrors: true,
		// Ohne diese Schranke wartet ein nicht klickbares Element UNENDLICH
		// (Playwright-Default actionTimeout = 0) — die Testschranke schlaegt dann
		// ohne verwertbare Begruendung zu.
		actionTimeout: 15_000,
		screenshot: 'only-on-failure',
		httpCredentials: { username: nginxUser, password: nginxPass }
	},
	projects: [
		{ name: 'setup', testMatch: /feat-1395-s3-etag-ifmatch\.staging\.setup\.ts/ },
		{
			name: 'tests',
			testMatch: /feat-1395-s3-etag-ifmatch\.staging\.spec\.ts/,
			dependencies: ['setup'],
			use: { storageState: path.join(__dirname, 'playwright', '.auth', 'staging-1395-s3.json') }
		}
	]
});

import { defineConfig } from '@playwright/test';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { ausUmgebung } from './stagingZugang';
// E2E-Config Issue #2422 Scheibe S2a (AC-10/AC-11/AC-17: B9-/K8-Fix,
// Editor-Anzeige = gespeicherter Stand bei Kaskadenquelle 'global') gegen
// Staging. Vorbild: playwright.metrik-abwahl-schreibt-alle-kanaele-durch.staging.config.ts.
//
// Eigene Config statt Aufnahme in .github/ci_e2e_specs.txt: Filter A dort
// schliesst `.staging.spec.ts`-Dateien strukturell aus (kein Kandidat für die
// CI-Positivliste, die gegen den isolierten LOKALEN Stack läuft, nicht gegen
// Staging) — Spec erlaubt ausdrücklich die Alternative "eigene
// `*.staging.spec.ts`" (docs/specs/modules/fix_2422_s2a_editor_gleich_gespeichert.md,
// Abschnitt "File (E2E)"). Lauf erfolgt über `/e2e-verify` nach dem Merge.
const __dirname = path.dirname(fileURLToPath(import.meta.url));
const user = ausUmgebung('GZ_VALIDATOR_USER', 'E2E_USER');
const pass = ausUmgebung('GZ_VALIDATOR_PASS', 'E2E_PASS');

export default defineConfig({
	testDir: '.',
	timeout: 90_000,
	retries: 0,
	use: {
		baseURL: process.env.GZ_SVELTE_BASE ?? 'https://staging.gregor20.henemm.com',
		headless: true,
		ignoreHTTPSErrors: true,
		httpCredentials: { username: user, password: pass }
	},
	projects: [
		{ name: 'setup', testMatch: /editor-gleich-gespeichert\.staging\.setup\.ts/ },
		{
			name: 'tests',
			testMatch: /editor-gleich-gespeichert\.staging\.spec\.ts/,
			dependencies: ['setup'],
			use: {
				storageState: path.join(__dirname, 'playwright', '.auth', 'staging-2422-s2a-editor.json')
			}
		}
	]
});

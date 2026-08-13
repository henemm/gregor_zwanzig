import { defineConfig } from '@playwright/test';

// Dedizierte Config für Issue #1771 Scheibe 1 — isolierter Nachweis der
// Wartestrategie von `dragDndZoneItem` (frontend/e2e/helpers.ts).
//
// Der Test baut seine Fixture per `page.setContent()`: kein Backend, kein
// Staging, kein Login — daher bewusst KEIN `webServer`, KEINE `baseURL` und
// KEIN Setup-Projekt/Login-Dependency.
//
// Ausführen:
//   cd frontend && npx playwright test --config=playwright.1771-s1-finalize-wait.config.ts
export default defineConfig({
	testDir: 'e2e',
	timeout: 60_000,
	retries: 0,
	use: {
		headless: true
	},
	projects: [
		{
			name: 'tests',
			testMatch: /dnd-helper-finalize-wait\.spec\.ts/
		}
	]
});
